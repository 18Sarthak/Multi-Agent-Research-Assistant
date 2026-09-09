# agents.py
import json
from langchain_core.messages import HumanMessage, AIMessage
from langchain_tavily import TavilySearch
from config import model
from state import ResearchState

def _safe_json(text: str):
    """Strip markdown fences models love to add, then parse."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text.strip())

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
search_tool = TavilySearch(max_results=3)

def researcher_agent(state: ResearchState) -> dict:
    findings, errors = [], []
    for question in state["sub_questions"]:
        try:
            raw = search_tool.invoke({"query": question})
            results = raw.get("results", []) if isinstance(raw, dict) else raw
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
            findings.append(_safe_json(response.content))
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
        f"### {f['question']}\n{f['answer']}\nSources: {', '.join(f.get('sources', []))}"
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
        prompt = f"""You are an expert technical writer and researcher. Write a professional, in-depth research report.

Topic: {query}

Research Findings:
{findings_block}

Report Structure (follow exactly):
1. ## Executive Summary (3-4 sentences: what the topic is, why it matters, key conclusion)
2. ## Background (1 short paragraph: context needed to understand the findings)
3. One ## section per finding — use the finding's question as the section title
   - Start with the core answer
   - Expand with key facts and technical details from the finding
   - Add inline citations like [Source](URL) for every claim
4. ## Challenges & Limitations (synthesize limitations mentioned across findings)
5. ## Key Takeaways (5-7 bullet points — concrete, specific, actionable insights)
6. ## References (numbered list of all URLs used)

Strict rules:
- 700-900 words total
- ONLY use facts from the provided findings — never invent
- Every factual claim must have an inline citation
- Use bold for key terms on first use
- Write for an informed technical audience

Return ONLY the markdown report. No preamble, no commentary."""

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
        approved, feedback, score = True, "", "parse-error"

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
