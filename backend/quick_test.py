# quick_test.py
from agents import planner_agent, researcher_agent, writer_agent, reviewer_agent

QUERY = "What are the latest advances in protein folding prediction?"

# ── 5a. Planner ───────────────────────────────────────────────────────────────
print("=== Step 1: Planner ===")
plan = planner_agent({"research_query": QUERY})
print("Sub-questions:", plan["sub_questions"])

# ── 5b. Researcher ────────────────────────────────────────────────────────────
print("\n=== Step 2: Researcher ===")
research = researcher_agent(plan)
print("Status:", research["messages"][0].content)

# ── 5c. Writer ────────────────────────────────────────────────────────────────
print("\n=== Step 3: Writer (first draft) ===")
writer_state = {
    "research_query": QUERY,   # planner doesn't echo this back, so pass it explicitly
    **plan,
    **research,
    "review_feedback": "",   # no feedback yet on the first pass
    "review_count": 0,
}
draft = writer_agent(writer_state)
print(draft["final_report"][:800], "...\n[truncated]")

# ── 5d. Reviewer ──────────────────────────────────────────────────────────────
print("\n=== Step 4: Reviewer ===")
reviewer_state = {
    **writer_state,
    **draft,
}
review = reviewer_agent(reviewer_state)
print("Reviewer says:", review["messages"][0].content)
print("Next step:", review["current_step"])

if review["current_step"] == "writing":
    print("\n--- Revision pass ---")
    revision_state = {**reviewer_state, **review}
    revised = writer_agent(revision_state)
    print(revised["final_report"][:800], "...\n[truncated]")

    final_review = reviewer_agent({**revision_state, **revised})
    print("\nFinal reviewer says:", final_review["messages"][0].content)