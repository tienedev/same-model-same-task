"""PydanticAI adapter — Agent + @agent.tool_plain decorators.

Routes to Gemini via Google's OpenAI-compatible endpoint using
PydanticAI's OpenAIChatModel + OpenAIProvider with custom base_url.

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

from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.models.openai import OpenAIChatModel  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.usage import UsageLimits  # noqa: E402

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


def run(job_id: str) -> RunResult:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    provider = OpenAIProvider(api_key=api_key, base_url=GEMINI_OPENAI_BASE_URL)
    model = OpenAIChatModel(MODEL_NAME, provider=provider)
    agent = Agent(model, system_prompt=SYSTEM_PROMPT)

    @agent.tool_plain
    def search_candidates(query: str, filters: dict[str, Any] | None = None) -> list[str]:
        """Search candidates by free-text query and optional filters.

        Filters dict can contain: min_years_experience (int), required_skills (list of strings),
        location (string; "remote" matches any remote-ok candidate), max_salary_eur (int).
        Returns up to 10 candidate IDs sorted by match relevance.
        """
        return _search_candidates(query, filters)

    @agent.tool_plain
    def get_candidate_profile(candidate_id: str) -> dict | None:
        """Get the full profile for a candidate by id. Returns None if the id does not exist."""
        return _get_candidate_profile(candidate_id)

    @agent.tool_plain
    def score_match(candidate_id: str, job_id: str) -> dict:
        """Score how well a candidate matches a job.

        Returns a breakdown with skill_match_pct, experience_fit, location_fit,
        salary_fit. Not an aggregate score — you must synthesize.
        """
        return _score_match(candidate_id, job_id)

    @agent.tool_plain
    def list_jobs() -> list[dict]:
        """List all jobs as a lightweight summary (id, title, location only)."""
        return _list_jobs()

    t0 = time.perf_counter()
    result = agent.run_sync(
        USER_PROMPT_TEMPLATE.format(job_id=job_id),
        model_settings={"temperature": 0},
        usage_limits=UsageLimits(request_limit=MAX_STEPS),
    )

    final_text = result.output if isinstance(result.output, str) else str(result.output)

    usage = result.usage()
    in_tokens = getattr(usage, "input_tokens", 0) or getattr(usage, "request_tokens", 0) or 0
    out_tokens = getattr(usage, "output_tokens", 0) or getattr(usage, "response_tokens", 0) or 0

    tool_calls = sum(
        1
        for msg in result.all_messages()
        for part in (getattr(msg, "parts", []) or [])
        if part.__class__.__name__ == "ToolCallPart"
    )

    return build_result(
        framework="pydantic-ai",
        job_id=job_id,
        model=MODEL_NAME,
        t0=t0,
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        tool_calls=tool_calls,
        final_text=final_text,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python run.py <job_id>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(run(sys.argv[1]), indent=2, ensure_ascii=False))
