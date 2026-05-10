"""CrewAI adapter — DSL Crew with @tool decorators.

Quickstart pattern from docs.crewai.com/en/quickstart. CrewAI uses
LiteLLM internally; LiteLLM routes to Google AI Studio with slug
`gemini/<model>` when GEMINI_API_KEY is set.

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

# Silence CrewAI's chatty telemetry before import side-effects.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from crewai.tools import tool  # noqa: E402

from frameworks._shared.python import (  # noqa: E402
    GEMINI_OPENAI_BASE_URL,
    MAX_STEPS,
    MODEL_NAME,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    RunResult,
    build_result,
)
from tools.python import (  # noqa: E402
    get_candidate_profile as _get_candidate_profile,
    list_jobs as _list_jobs,
    score_match as _score_match,
    search_candidates as _search_candidates,
)

# LiteLLM 'openai/<model>' + custom api_base routes to Google AI Studio's
# OpenAI-compatible endpoint. Coherent with the rest of the bench
# (every other adapter uses OpenAI SDK pointed at this base URL).
LITELLM_MODEL = f"openai/{MODEL_NAME}"


@tool("search_candidates")
def search_candidates(query: str, filters: dict[str, Any] | None = None) -> str:
    """Search candidates by free-text query and optional filters.

    Filters dict can contain: min_years_experience (int), required_skills (list of strings),
    location (string; 'remote' matches any remote-ok candidate), max_salary_eur (int).
    Returns up to 10 candidate IDs sorted by match relevance.
    """
    return json.dumps(_search_candidates(query, filters), ensure_ascii=False)


@tool("get_candidate_profile")
def get_candidate_profile(candidate_id: str) -> str:
    """Get the full profile for a candidate by id. Returns null if the id does not exist."""
    return json.dumps(_get_candidate_profile(candidate_id), ensure_ascii=False)


@tool("score_match")
def score_match(candidate_id: str, job_id: str) -> str:
    """Score how well a candidate matches a job.

    Returns a breakdown with skill_match_pct, experience_fit, location_fit,
    salary_fit. Not an aggregate score — you must synthesize.
    """
    return json.dumps(_score_match(candidate_id, job_id), ensure_ascii=False)


@tool("list_jobs")
def list_jobs() -> str:
    """List all jobs as a lightweight summary (id, title, location only)."""
    return json.dumps(_list_jobs(), ensure_ascii=False)


TOOLS = [search_candidates, get_candidate_profile, score_match, list_jobs]


def run(job_id: str) -> RunResult:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    llm = LLM(
        model=LITELLM_MODEL,
        api_key=api_key,
        api_base=GEMINI_OPENAI_BASE_URL,
        temperature=0,
    )

    # CrewAI 1.14 changed the tasks_output schema; counting via step_callback is
    # the documented way to track tool-call activity reliably.
    tool_call_count = 0

    def _step_callback(step_output: object) -> None:
        nonlocal tool_call_count
        # AgentAction (tool invocation) has a `.tool` attribute; AgentFinish does not.
        if getattr(step_output, "tool", None):
            tool_call_count += 1

    agent = Agent(
        role="Recruitment Assistant",
        goal="Find the top 3 best-matching candidates for a given job using the available tools",
        backstory=SYSTEM_PROMPT,
        tools=TOOLS,
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=MAX_STEPS,
        step_callback=_step_callback,
    )
    task = Task(
        description=USER_PROMPT_TEMPLATE.format(job_id=job_id),
        expected_output=(
            "A single JSON object with keys 'job_id' and 'ranked_candidates'. "
            "ranked_candidates is a list of 3 items each with rank (1-3), candidate_id, "
            "score (0-100 int), and justification (≤50 words). Return ONLY the JSON."
        ),
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

    t0 = time.perf_counter()
    crew_output = crew.kickoff()

    final_text = str(crew_output.raw if hasattr(crew_output, "raw") else crew_output)
    metrics = getattr(crew_output, "token_usage", None)
    in_tokens = getattr(metrics, "prompt_tokens", 0) if metrics else 0
    out_tokens = getattr(metrics, "completion_tokens", 0) if metrics else 0

    return build_result(
        framework="crewai",
        job_id=job_id,
        model=LITELLM_MODEL,
        t0=t0,
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        tool_calls=tool_call_count,
        final_text=final_text,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python run.py <job_id>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(run(sys.argv[1]), indent=2, ensure_ascii=False))
