"""Google ADK adapter — LlmAgent with LiteLlm wrapper to Gemini OpenAI-compat.

The bench unifies on Google's OpenAI-compat endpoint, so even ADK (which
has a native Gemini path) routes through LiteLlm here, using slug
`openai/<model>` + custom `api_base`. This keeps the entire bench on a
single transport. The native ADK path is documented in the design doc as
the alternative we explored in v2.3 — see commit history for that variant.

Usage:
    GEMINI_API_KEY=... python run.py job-001
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.models.lite_llm import LiteLlm  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.adk.tools import FunctionTool  # noqa: E402
from google.genai import types as genai_types  # noqa: E402

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

LITELLM_MODEL = f"openai/{MODEL_NAME}"


def search_candidates(query: str, filters: dict[str, Any] | None = None) -> list[str]:
    """Search candidates by free-text query and optional filters.

    Filters dict can contain: min_years_experience (int), required_skills (list of strings),
    location (string; "remote" matches any remote-ok candidate), max_salary_eur (int).
    Returns up to 10 candidate IDs sorted by match relevance.
    """
    return _search_candidates(query, filters)


def get_candidate_profile(candidate_id: str) -> dict | None:
    """Get the full profile for a candidate by id. Returns None if the id does not exist."""
    return _get_candidate_profile(candidate_id)


def score_match(candidate_id: str, job_id: str) -> dict:
    """Score how well a candidate matches a job.

    Returns a breakdown with skill_match_pct, experience_fit, location_fit,
    salary_fit. Not an aggregate score — you must synthesize.
    """
    return _score_match(candidate_id, job_id)


def list_jobs() -> list[dict]:
    """List all jobs as a lightweight summary (id, title, location only)."""
    return _list_jobs()


async def _run_async(job_id: str) -> RunResult:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    model = LiteLlm(
        model=LITELLM_MODEL,
        api_base=GEMINI_OPENAI_BASE_URL,
        api_key=api_key,
        temperature=0,
    )

    agent = LlmAgent(
        model=model,
        name="recruitment_assistant",
        description="Find top 3 best-matching candidates for a job.",
        instruction=SYSTEM_PROMPT,
        tools=[
            FunctionTool(search_candidates),
            FunctionTool(get_candidate_profile),
            FunctionTool(score_match),
            FunctionTool(list_jobs),
        ],
    )

    runner = InMemoryRunner(agent=agent, app_name="bench")
    session = await runner.session_service.create_session(app_name="bench", user_id="bench-user")

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=USER_PROMPT_TEMPLATE.format(job_id=job_id))],
    )

    in_tokens = 0
    out_tokens = 0
    tool_calls = 0
    final_text = ""
    hit_step_limit = False

    t0 = time.perf_counter()
    runner_iter = runner.run_async(
        user_id="bench-user",
        session_id=session.id,
        new_message=user_message,
    )
    async for event in runner_iter:
        usage = getattr(event, "usage_metadata", None)
        if usage:
            in_tokens += getattr(usage, "prompt_token_count", 0) or 0
            out_tokens += getattr(usage, "candidates_token_count", 0) or 0

        content = getattr(event, "content", None)
        if content and content.parts:
            for part in content.parts:
                if getattr(part, "function_call", None):
                    tool_calls += 1
                if getattr(part, "text", None) and event.is_final_response():
                    final_text = part.text

        if tool_calls >= MAX_STEPS:
            hit_step_limit = True
            await runner_iter.aclose()  # cooperative cancellation
            break

    return build_result(
        framework="google-adk",
        job_id=job_id,
        model=LITELLM_MODEL,
        t0=t0,
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        tool_calls=tool_calls,
        final_text=final_text,
        hit_step_limit=hit_step_limit,
    )


def run(job_id: str) -> RunResult:
    return asyncio.run(_run_async(job_id))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python run.py <job_id>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(run(sys.argv[1]), indent=2, ensure_ascii=False))
