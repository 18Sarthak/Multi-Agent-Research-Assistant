"""
api.py — FastAPI backend for the Research Assistant UI.

Endpoints
---------
POST /api/research
    Body : { "query": "<research question>" }
    Returns: text/event-stream (SSE)

SSE event shapes
----------------
    {"event": "agent_start", "agent": "<name>", "index": <int>}
    {"event": "agent_done",  "agent": "<name>", "index": <int>, "output": "<string>"}
    {"event": "report",      "report": "<full markdown>"}
    {"event": "done"}
    {"event": "error",       "message": "<string>"}
"""

import asyncio
import json
import time
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ── Local imports ──────────────────────────────────────────────────────────────
from state import ResearchState
from agents import planner_agent, researcher_agent, writer_agent, reviewer_agent

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Research Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request schema ────────────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    query: str


# ── Agent pipeline (synchronous, runs in a thread) ────────────────────────────

AGENT_PIPELINE = [
    ("planner",    planner_agent,    0),
    ("researcher", researcher_agent, 1),
    ("writer",     writer_agent,     2),
    ("reviewer",   reviewer_agent,   3),
]

MAX_REVIEWS = 2


def _format_agent_output(agent_name: str, result: dict) -> str:
    """Extract a short human-readable output line for the agent card."""
    if agent_name == "planner":
        questions = result.get("sub_questions", [])
        return f"{len(questions)} sub-questions generated."
    if agent_name == "researcher":
        findings = result.get("research_findings", [])
        return f"{len(findings)} findings synthesized from search results."
    if agent_name == "writer":
        report = result.get("final_report", "")
        word_count = len(report.split())
        return f"Draft report written ({word_count} words)."
    if agent_name == "reviewer":
        msgs = result.get("messages", [])
        if msgs:
            return msgs[-1].content
        return "Review complete."
    return "Done."


def run_pipeline_sync(query: str, emit):
    """
    Run the four-agent pipeline step by step, calling `emit(event_dict)`
    after each agent completes.  Handles the reviewer→writer revision loop.

    `emit` must be callable from a synchronous context.
    """
    state: ResearchState = {
        "research_query": query,
        "sub_questions": [],
        "research_findings": [],
        "final_report": "",
        "current_step": "planning",
        "review_count": 0,
        "review_feedback": "",
        "messages": [],
    }

    # ── Planner ────────────────────────────────────────────────────────────────
    emit({"event": "agent_start", "agent": "planner", "index": 0})
    result = planner_agent(state)
    state.update(result)
    emit({"event": "agent_done",  "agent": "planner", "index": 0,
          "output": _format_agent_output("planner", result)})

    # ── Researcher ─────────────────────────────────────────────────────────────
    emit({"event": "agent_start", "agent": "researcher", "index": 1})
    result = researcher_agent(state)
    state.update(result)
    emit({"event": "agent_done",  "agent": "researcher", "index": 1,
          "output": _format_agent_output("researcher", result)})

    # ── Writer + Reviewer loop ─────────────────────────────────────────────────
    review_round = 0
    while True:
        emit({"event": "agent_start", "agent": "writer", "index": 2})
        result = writer_agent(state)
        state.update(result)
        emit({"event": "agent_done",  "agent": "writer", "index": 2,
              "output": _format_agent_output("writer", result)})

        emit({"event": "agent_start", "agent": "reviewer", "index": 3})
        result = reviewer_agent(state)
        state.update(result)
        emit({"event": "agent_done",  "agent": "reviewer", "index": 3,
              "output": _format_agent_output("reviewer", result)})

        review_round += 1
        if state.get("current_step") == "done" or review_round >= MAX_REVIEWS:
            break

    # ── Final report ───────────────────────────────────────────────────────────
    emit({"event": "report", "report": state.get("final_report", "")})
    emit({"event": "done"})


# ── SSE streaming endpoint ────────────────────────────────────────────────────

async def _stream_research(query: str) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted lines."""
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(event: dict):
        """Called from the sync thread — puts events onto the async queue."""
        # schedule coroutine to put the item from the background thread
        asyncio.run_coroutine_threadsafe(queue.put(event), loop)

    # Run the blocking pipeline in a thread-pool so we don't block the event loop
    future = loop.run_in_executor(None, run_pipeline_sync, query, emit)

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=600.0)
        except asyncio.TimeoutError:
            yield "data: " + json.dumps({"event": "error", "message": "Pipeline timed out (>10 min). Try a shorter/simpler query."}) + "\n\n"
            break

        yield "data: " + json.dumps(event) + "\n\n"

        if event.get("event") in ("done", "error"):
            break

    # Await the pipeline future so any exception surfaces
    try:
        await future
    except Exception as exc:
        yield "data: " + json.dumps({"event": "error", "message": str(exc)}) + "\n\n"


@app.post("/api/research")
async def research(req: ResearchRequest):
    return StreamingResponse(
        _stream_research(req.query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if behind a proxy
        },
    )


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Root endpoint — keeps Render's health check happy."""
    return {"status": "ok", "service": "Research Assistant API"}


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
