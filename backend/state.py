from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class ResearchState(TypedDict):
    messages: Annotated[list, add_messages]
    research_query: str
    sub_questions: list[str]
    research_findings: list[dict]
    final_report: str
    current_step: str
    review_count: int
    review_feedback: str        # reviewer's notes passed back to the writer