# main.py
from graph import research_graph

def run(query: str) -> str:
    """Run the full research pipeline and return the final report."""
    print(f"\n🔍 Researching: {query}\n")

    result = research_graph.invoke({
        "research_query": query,
        "review_count":   0,
        "review_feedback": "",
    })

    print("\n✅ Pipeline complete!")
    print(f"   Sub-questions answered : {len(result.get('sub_questions', []))}")
    print(f"   Findings collected     : {len(result.get('research_findings', []))}")
    print(f"   Review rounds          : {result.get('review_count', 0)}")
    print("\n" + "─" * 60)
    print(result["final_report"])
    return result["final_report"]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Usage: python main.py "your question here"
        query = " ".join(sys.argv[1:])
    else:
        query = "tell about rl environment"   # default if no argument given

    run(query)
