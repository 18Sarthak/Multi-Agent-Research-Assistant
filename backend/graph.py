# graph.py
from langgraph.graph import StateGraph, END

from state import ResearchState
from agents import planner_agent, researcher_agent, writer_agent, reviewer_agent


# ── Routing logic ──────────────────────────────────────────────────────────────

def route_after_reviewer(state: ResearchState) -> str:
    """
    Reads current_step set by reviewer_agent and decides the next node.

      "writing" → back to writer for a revision
      "done"    → END
    """
    return state["current_step"]   # "writing" or "done"


# ── Build the graph ────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(ResearchState)

    # Nodes — one per agent
    graph.add_node("planner",    planner_agent)
    graph.add_node("researcher", researcher_agent)
    graph.add_node("writer",     writer_agent)
    graph.add_node("reviewer",   reviewer_agent)

    # Fixed edges (always go straight through)
    graph.set_entry_point("planner")
    graph.add_edge("planner",    "researcher")
    graph.add_edge("researcher", "writer")
    graph.add_edge("writer",     "reviewer")

    # Conditional edge — reviewer decides: revise or finish
    graph.add_conditional_edges(
        "reviewer",
        route_after_reviewer,
        {
            "writing": "writer",   # loop back for a revision
            "done":    END,        # pipeline complete
        },
    )

    return graph.compile()


# Compiled graph — import this in main.py / quick_test.py
research_graph = build_graph()
