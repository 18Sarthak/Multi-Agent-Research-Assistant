# agents.py
import json
from langchain_core.messages import HumanMessage, AIMessage
from langchain_tavily import TavilySearch
from config import model
from state import ResearchState

import re as _re

def _safe_json(text: str):
    """Parse JSON from LLM output robustly with multiple fallback strategies."""
    text = text.strip()

    # Strategy 1: strip markdown fences then parse directly
    clean = text
    if clean.startswith("```"):
        clean = clean.strip("`").strip()
        if clean.lower().startswith("json"):
            clean = clean[4:].strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract the first {...} block (handles trailing text / preamble)
    m = _re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    # Strategy 3: regex-extract individual fields from raw text as last resort
    score_m    = _re.search(r'"?score"?\s*[=:]\s*(\d+)', text, _re.I)
    approved_m = _re.search(r'"?approved"?\s*[=:]\s*(true|false)', text, _re.I)
    feedback_m = _re.search(r'"?feedback"?\s*[=:]\s*"([^"]*)"', text, _re.I)

    if score_m or approved_m:
        score    = int(score_m.group(1)) if score_m else 5
        approved = approved_m.group(1).lower() == "true" if approved_m else score >= 8
        feedback = feedback_m.group(1) if feedback_m else ""
        return {"score": score, "approved": approved, "feedback": feedback}

    raise ValueError(f"Could not extract JSON from reviewer output: {text[:200]}")

def planner_agent(state: ResearchState) -> dict:
    query = state["research_query"]
    prompt = f"""You are a senior research strategist. Your job is to decompose a broad research question
into 4-5 precise, non-overlapping sub-questions that together give a COMPLETE picture of the topic.

Rules:
- Each sub-question must cover a DIFFERENT angle (e.g. mechanisms, applications, limitations, comparisons, recent developments)
- Questions must be specific enough to search the web for — avoid vague or abstract questions
- Do NOT repeat the same angle in different wording
- Order them logically: fundamentals first, advanced topics last

Topic: {query}

Return ONLY a JSON array of strings. No markdown, no explanation, no preamble.
Example format: ["Question 1?", "Question 2?", "Question 3?", "Question 4?"]"""

    response = model.invoke([HumanMessage(content=prompt)])
    try:
        sub_questions = _safe_json(response.content)
    except json.JSONDecodeError:
        sub_questions = [query]  # fallback: treat whole query as one question

    return {
        "research_query": query,   # echo so downstream agents always find it in state
        "sub_questions": sub_questions,
        "current_step": "research",
        "messages": [AIMessage(content=f"{len(sub_questions)} sub-questions created", name="planner")]
    }

# Researcher
search_tool = TavilySearch(max_results=4, include_images=True)

def researcher_agent(state: ResearchState) -> dict:
    findings, errors = [], []
    for question in state["sub_questions"]:
        try:
            raw = search_tool.invoke({"query": question})
            results = raw.get("results", []) if isinstance(raw, dict) else raw

            # Collect image URLs returned by Tavily (deduplicated, up to 2 per question)
            raw_images = raw.get("images", []) if isinstance(raw, dict) else []
            image_urls = []
            for img in raw_images:
                url = img.get("url") if isinstance(img, dict) else img
                if url and url not in image_urls:
                    image_urls.append(url)
                if len(image_urls) >= 2:
                    break

            if not results:
                errors.append(f"No results: {question}")
                continue
            context = "\n".join(f"Source: {r['url']}\nContent: {r['content']}" for r in results)
            prompt = f"""You are a precise research analyst. Read the search results carefully and answer the question.

Question: {question}

Search Results:
{context}

Instructions:
- Extract ONLY information directly supported by the search results
- Include specific names, numbers, dates, or technical terms when present
- Note any limitations or caveats mentioned in the sources
- Do NOT add knowledge from outside these search results

Return ONLY valid JSON — no markdown fences, no extra text:
{{"question": "<the original question>", "answer": "<comprehensive 2-4 sentence answer with specific facts>", "key_facts": ["<fact 1>", "<fact 2>", "<fact 3>"], "sources": ["<url1>", "<url2>"]}}"""
            response = model.invoke([HumanMessage(content=prompt)])
            finding = _safe_json(response.content)
            finding["images"] = image_urls   # attach images to this finding
            findings.append(finding)
        except json.JSONDecodeError:
            errors.append(f"Bad JSON for: {question}")
        except Exception as e:
            errors.append(f"{question}: {e}")

    error_summary = f" | Errors: {'; '.join(errors)}" if errors else ""
    return {
        "research_findings": findings,
        "current_step": "writing",
        "messages": [AIMessage(content=f"{len(findings)}/{len(state['sub_questions'])} researched.{error_summary}", name="researcher")]
    }


# ── Writer ────────────────────────────────────────────────────────────────────

def writer_agent(state: ResearchState) -> dict:
    """Turn research findings into a polished markdown report."""
    findings = state["research_findings"]
    query    = state["research_query"]

    findings_block = "\n\n".join(
        "### {q}\n{a}\nKey Facts:\n{kf}\nImages: {imgs}\nSources: {src}".format(
            q=f["question"],
            a=f["answer"],
            kf="\n".join(f"- {kf}" for kf in f.get("key_facts", [])),
            imgs=", ".join(f.get("images", [])) or "none",
            src=", ".join(f.get("sources", [])),
        )
        for f in findings
    )

    feedback = state.get("review_feedback", "")
    if feedback:
        # Revision pass — tell the model exactly what to fix
        prompt = f"""You are revising a research report based on reviewer feedback.

Reviewer feedback:
{feedback}

Original findings (ground truth — do not contradict these):
{findings_block}

Return the FULLY revised markdown report. No preamble."""
    else:
        # First draft
        prompt = f"""You are an expert academic researcher and technical writer. Write a formal research paper on the given topic using the findings provided.

Topic: {query}

Research Findings (each includes question, answer, key facts, image URLs, and sources):
{findings_block}

─────────────────────────────────────────────
PAPER FORMAT — follow this exact academic structure:
─────────────────────────────────────────────

# [Paper Title — a concise, descriptive academic title for the topic]

**Authors:** AI Research Pipeline  
**Date:** {__import__('datetime').date.today().strftime('%B %Y')}  
**Keywords:** [5-7 relevant keywords comma-separated]

---

## Abstract
*(150-200 words: problem statement, methodology, key findings, and conclusion — written in past tense)*

---

## 1. Introduction
*(2-3 paragraphs: motivate the topic, state why it matters, outline what this paper covers)*

## 2. Background & Related Work
*(2-3 paragraphs: prior work, historical context, how this topic fits into the broader field)*

## 3. Core Concepts & Terminology
*(Define every key technical term precisely. Use ### sub-headings for each concept.)*

## 4. [Section per Finding — rename each heading to a substantive academic title]
*For EACH finding, create a numbered section (4.1, 4.2, etc.) with:*
- **Opening paragraph**: direct answer to the research sub-question
- **Detailed analysis**: ALL key facts, numbers, dates — cite every claim inline as [Author/Site](URL)
- **Figure** (if images are available for this finding): embed as:
  `![Figure N: Brief descriptive caption](image_url)`
  Place the figure right after the paragraph that references it.
- **Comparison/contrast** with related approaches where relevant
- **Sub-section summary**: 2-3 sentence synthesis

## 5. Discussion
*(2-3 paragraphs: synthesize findings, identify patterns, connect insights across sections)*

## 6. Limitations
*(One paragraph per limitation — explain the *root cause* of each limitation, not just its existence)*

## 7. Future Directions
*(Numbered list of 4-6 concrete open research questions, each with 2-3 sentences of explanation)*

## 8. Conclusion
*(1 solid paragraph: restate the problem, summarize what was learned, state the significance)*

## References
*(Numbered list: [N] Author/Source. "Title or description." URL)*

─────────────────────────────────────────────
STRICT RULES:
- **Minimum 2000 words** — this is an academic paper, not a summary
- ONLY use facts from the provided findings — never hallucinate
- Every factual claim must have an inline citation [Source](URL)
- Embed images using `![Figure N: caption](url)` — use image URLs from findings; skip if none available
- Use **bold** for key terms on first use, `code` for formulas/identifiers
- Use sub-headings (###) freely within sections for scanability
- Paragraphs must be 3-5 sentences — no one-liners
- Write in formal academic tone (third person, past tense for methods, present for facts)
- Section 4 sub-sections should be numbered: 4.1, 4.2, 4.3, etc.

Return ONLY the markdown paper. No preamble, no meta-commentary."""

    report = model.invoke([HumanMessage(content=prompt)]).content.strip()

    return {
        "final_report": report,
        "current_step": "reviewing",
        "messages": [AIMessage(content="Draft report written.", name="writer")],
    }


# ── Reviewer ──────────────────────────────────────────────────────────────────

MAX_REVIEWS = 2   # writer gets at most this many revision passes before auto-approve

def reviewer_agent(state: ResearchState) -> dict:
    """Score the report; request a targeted rewrite or approve it.

    State transitions:
        current_step = "writing"  → send back to writer (score < 8 and cap not hit)
        current_step = "done"     → approved, or MAX_REVIEWS reached
    """
    report       = state["final_report"]
    query        = state["research_query"]
    review_count = state.get("review_count", 0)

    # Hard cap — never loop more than MAX_REVIEWS times regardless of score
    if review_count >= MAX_REVIEWS:
        return {
            "review_count": review_count,
            "current_step": "done",
            "review_feedback": "",
            "messages": [AIMessage(
                content=f"Review cap ({MAX_REVIEWS}) reached — report accepted as-is.",
                name="reviewer",
            )],
        }

    prompt = f"""You are a rigorous research editor with high standards. Score this report and decide if it needs revision.

Original Topic: {query}

Report to Review:
{report}

Score the report on these 7 criteria (each worth up to 1-10 points, give ONE overall score):
1. Executive summary clarity — does it explain topic + why it matters in 3-4 sentences?
2. Citation quality — is every factual claim backed by an inline [Source](URL)?
3. Comprehensiveness — does it cover all major angles of the topic?
4. Technical depth — does it include specific names, numbers, and technical terms?
5. Structure — does it have Background, per-finding sections, Challenges, Key Takeaways, References?
6. Accuracy — does it stick to facts from sources without inventing information?
7. Writing quality — clear, professional, well-connected paragraphs?

Respond with ONLY valid JSON — no markdown fences:
{{
  "score": <integer 1-10>,
  "approved": <true if score >= 8, false otherwise>,
  "feedback": "<if not approved: specific bullet points naming EXACTLY what is missing or weak — reference section names and criteria numbers. If approved: empty string>"
}}"""

    try:
        raw    = model.invoke([HumanMessage(content=prompt)]).content
        review = _safe_json(raw)
        approved = bool(review.get("approved", False))
        feedback = review.get("feedback", "")
        score    = review.get("score", "?")
    except Exception:
        # Bad JSON → approve to avoid an infinite loop
        approved, feedback, score = True, "", 0

    new_count = review_count + 1

    if approved:
        return {
            "review_count": new_count,
            "current_step": "done",
            "review_feedback": "",
            "messages": [AIMessage(
                content=f"Report approved. Score: {score}/10 (review #{new_count}).",
                name="reviewer",
            )],
        }

    return {
        "review_count": new_count,
        "current_step": "writing",      # loop back to writer for a revision
        "review_feedback": feedback,
        "messages": [AIMessage(
            content=f"Revision requested (score {score}/10, review #{new_count}): {feedback}",
            name="reviewer",
        )],
    }
