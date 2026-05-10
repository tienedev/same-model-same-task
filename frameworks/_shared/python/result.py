"""Shared result schema + builder for adapter `run()` functions.

Single source of truth for the dict shape persisted to results/*.json.
Every adapter calls `build_result(...)` at the end of its `run()`.
"""

from __future__ import annotations

import time
from typing import Any, TypedDict

from .output import parse_final_json


class RunResult(TypedDict, total=False):
    framework: str
    job_id: str
    model: str
    elapsed_s: float
    input_tokens: int
    output_tokens: int
    tool_calls: int | None  # None when the framework's API doesn't expose it (e.g. crewai 1.14)
    hit_step_limit: bool
    raw_output: str
    parsed_output: dict[str, Any] | None
    parse_error: str | None


def build_result(
    *,
    framework: str,
    job_id: str,
    model: str,
    t0: float,
    in_tokens: int,
    out_tokens: int,
    tool_calls: int | None,
    final_text: str,
    hit_step_limit: bool = False,
) -> RunResult:
    """Build the canonical run-result dict. Centralizes elapsed timing,
    JSON parsing, and field naming so adapters never drift."""
    parsed, err = parse_final_json(final_text)
    return {
        "framework": framework,
        "job_id": job_id,
        "model": model,
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "tool_calls": tool_calls,
        "hit_step_limit": hit_step_limit,
        "raw_output": final_text,
        "parsed_output": parsed,
        "parse_error": err,
    }
