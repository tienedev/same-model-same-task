"""Baseline (no framework): raw openai SDK + manual tool-calling loop.

Reference point for the bench. Routes to Gemini via Google's
OpenAI-compatible endpoint (one SDK family across the entire bench).

Usage:
    GEMINI_API_KEY=... python run.py job-001
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from openai import OpenAI  # noqa: E402

from frameworks._shared.python import (  # noqa: E402
    FORCE_FINAL_PROMPT,
    GEMINI_OPENAI_BASE_URL,
    GET_CANDIDATE_PROFILE_DESC,
    LIST_JOBS_DESC,
    MAX_STEPS,
    MODEL_NAME,
    SCORE_MATCH_DESC,
    SEARCH_CANDIDATES_DESC,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    RunResult,
    build_result,
    format_exception,
)
from tools.python import (  # noqa: E402
    get_candidate_profile,
    list_jobs,
    score_match,
    search_candidates,
)

TOOL_FUNCTIONS = {
    "search_candidates": search_candidates,
    "get_candidate_profile": get_candidate_profile,
    "score_match": score_match,
    "list_jobs": list_jobs,
}

TOOL_DECLARATIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_candidates",
            "description": SEARCH_CANDIDATES_DESC,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "filters": {
                        "type": "object",
                        "properties": {
                            "min_years_experience": {"type": "integer"},
                            "required_skills": {"type": "array", "items": {"type": "string"}},
                            "location": {"type": "string"},
                            "max_salary_eur": {"type": "integer"},
                        },
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_candidate_profile",
            "description": GET_CANDIDATE_PROFILE_DESC,
            "parameters": {
                "type": "object",
                "properties": {"candidate_id": {"type": "string"}},
                "required": ["candidate_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_match",
            "description": SCORE_MATCH_DESC,
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string"},
                    "job_id": {"type": "string"},
                },
                "required": ["candidate_id", "job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_jobs",
            "description": LIST_JOBS_DESC,
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _execute_tool(name: str, args: dict) -> object:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"unknown tool: {name}"}
    try:
        return fn(**(args or {}))
    except Exception as e:  # noqa: BLE001
        return {"error": format_exception(e)}


def run(job_id: str) -> RunResult:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url=GEMINI_OPENAI_BASE_URL)
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(job_id=job_id)},
    ]

    in_tokens = 0
    out_tokens = 0
    tool_calls = 0
    final_text = ""
    hit_step_limit = False

    t0 = time.perf_counter()
    for step in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=TOOL_DECLARATIONS,
            temperature=0,
        )
        if response.usage:
            in_tokens += response.usage.prompt_tokens or 0
            out_tokens += response.usage.completion_tokens or 0

        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            final_text = msg.content or ""
            break

        for tc in msg.tool_calls:
            tool_calls += 1
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _execute_tool(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

        if step == MAX_STEPS - 1:
            hit_step_limit = True

    if hit_step_limit and not final_text:
        messages.append({"role": "user", "content": FORCE_FINAL_PROMPT})
        response = client.chat.completions.create(
            model=MODEL_NAME, messages=messages, temperature=0,
        )
        if response.usage:
            in_tokens += response.usage.prompt_tokens or 0
            out_tokens += response.usage.completion_tokens or 0
        final_text = response.choices[0].message.content or ""

    return build_result(
        framework="baseline-python",
        job_id=job_id,
        model=MODEL_NAME,
        t0=t0,
        in_tokens=in_tokens,
        out_tokens=out_tokens,
        tool_calls=tool_calls,
        final_text=final_text,
        hit_step_limit=hit_step_limit,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python run.py <job_id>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(run(sys.argv[1]), indent=2, ensure_ascii=False))
