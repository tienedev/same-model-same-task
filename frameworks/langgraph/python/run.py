"""LangGraph adapter — graph state machine with explicit nodes/edges.

Routes to Gemini via Google's OpenAI-compat endpoint using
`langchain-openai`'s ChatOpenAI.

Usage:
    GEMINI_API_KEY=... python run.py job-001
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from langgraph.graph import END, START, MessagesState, StateGraph  # noqa: E402

from frameworks._shared.python import (  # noqa: E402
    GEMINI_OPENAI_BASE_URL,
    MAX_STEPS,
    MODEL_NAME,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    RunResult,
    build_result,
    format_exception,
)
from tools.python import (  # noqa: E402
    get_candidate_profile as _get_candidate_profile,
    list_jobs as _list_jobs,
    score_match as _score_match,
    search_candidates as _search_candidates,
)


@tool
def search_candidates(query: str, filters: dict[str, Any] | None = None) -> list[str]:
    """Search candidates by free-text query and optional filters.

    Filters dict can contain: min_years_experience (int), required_skills (list of strings),
    location (string; "remote" matches any remote-ok candidate), max_salary_eur (int).
    Returns up to 10 candidate IDs sorted by match relevance.
    """
    return _search_candidates(query, filters)


@tool
def get_candidate_profile(candidate_id: str) -> dict | None:
    """Get the full profile for a candidate by id. Returns None if the id does not exist."""
    return _get_candidate_profile(candidate_id)


@tool
def score_match(candidate_id: str, job_id: str) -> dict:
    """Score how well a candidate matches a job.

    Returns a breakdown with skill_match_pct, experience_fit, location_fit,
    salary_fit. Not an aggregate score — you must synthesize.
    """
    return _score_match(candidate_id, job_id)


@tool
def list_jobs() -> list[dict]:
    """List all jobs as a lightweight summary (id, title, location only)."""
    return _list_jobs()


TOOLS = [search_candidates, get_candidate_profile, score_match, list_jobs]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def run(job_id: str) -> RunResult:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    model = ChatOpenAI(
        model=MODEL_NAME,
        api_key=api_key,
        base_url=GEMINI_OPENAI_BASE_URL,
        temperature=0,
    ).bind_tools(TOOLS)

    metrics = {"in": 0, "out": 0, "tool_calls": 0}

    def llm_node(state: MessagesState) -> dict:
        response = model.invoke(state["messages"])
        usage = getattr(response, "usage_metadata", None) or {}
        metrics["in"] += usage.get("input_tokens", 0)
        metrics["out"] += usage.get("output_tokens", 0)
        return {"messages": [response]}

    def tools_node(state: MessagesState) -> dict:
        last = state["messages"][-1]
        out = []
        for tc in last.tool_calls:
            metrics["tool_calls"] += 1
            try:
                result = TOOLS_BY_NAME[tc["name"]].invoke(tc["args"])
            except Exception as e:  # noqa: BLE001
                result = {"error": format_exception(e)}
            out.append(ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=tc["id"]))
        return {"messages": out}

    def should_continue(state: MessagesState) -> str:
        return "tools" if getattr(state["messages"][-1], "tool_calls", None) else END

    graph = StateGraph(MessagesState)
    graph.add_node("llm", llm_node)
    graph.add_node("tools", tools_node)
    graph.add_edge(START, "llm")
    graph.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    app = graph.compile()

    t0 = time.perf_counter()
    state = app.invoke(
        {"messages": [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=USER_PROMPT_TEMPLATE.format(job_id=job_id)),
        ]},
        {"recursion_limit": MAX_STEPS * 2},
    )
    final_text = state["messages"][-1].content if state["messages"] else ""
    final_text = final_text if isinstance(final_text, str) else str(final_text)

    return build_result(
        framework="langgraph",
        job_id=job_id,
        model=MODEL_NAME,
        t0=t0,
        in_tokens=metrics["in"],
        out_tokens=metrics["out"],
        tool_calls=metrics["tool_calls"],
        final_text=final_text,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python run.py <job_id>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(run(sys.argv[1]), indent=2, ensure_ascii=False))
