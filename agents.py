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
    prompt = f"""You are a research planner. Break this question into
3-5 focused sub-questions covering the topic comprehensively.

Question: {query}

Return ONLY a JSON list of strings, no markdown, no preamble."""

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
            prompt = f"""Answer using the search results. Return ONLY JSON:
{{"question": "...", "answer": "...", "sources": ["..."]}}

Question: {question}
Search Results:
{context}"""
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
        prompt = f"""You are an expert technical writer. Write a comprehensive, well-structured
research report on the topic below using ONLY the provided findings.

Topic: {query}

Findings:
{findings_block}

Requirements:
- Use markdown with clear headings (##, ###)
- Open with an executive summary
- One section per finding with inline citations [Source: URL]
- Close with a 'Key Takeaways' section
- Do NOT invent facts beyond the findings
- Aim for ~600 words

Return ONLY the markdown text, no preamble."""

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

    prompt = f"""You are a rigorous research editor. Evaluate this report against the original topic.

Topic: {query}

Report:
{report}

Respond with ONLY JSON — no markdown fences, no extra text:
{{
  "score": <integer 1-10>,
  "approved": <true|false>,
  "feedback": "<concise bullet-point notes for the writer, or empty string if approved>"
}}

Approve (approved=true, score >= 8) when the report:
- Has a clear executive summary and 'Key Takeaways' section
- Cites sources inline
- Covers the topic comprehensively without inventing facts"""

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
