"""Shared constants + helpers for framework adapters.

Single source of truth for: model name, system prompt, tool descriptions,
output parsing, force-final prompt. Imported by every adapter to keep the
bench fair (every framework gets the exact same instructions).
"""

from .config import GEMINI_OPENAI_BASE_URL, MAX_STEPS, MODEL_NAME
from .output import format_exception, parse_final_json
from .result import RunResult, build_result
from .prompts import FORCE_FINAL_PROMPT, SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .tool_descriptions import (
    GET_CANDIDATE_PROFILE_DESC,
    LIST_JOBS_DESC,
    SCORE_MATCH_DESC,
    SEARCH_CANDIDATES_DESC,
)

__all__ = [
    "FORCE_FINAL_PROMPT",
    "GEMINI_OPENAI_BASE_URL",
    "GET_CANDIDATE_PROFILE_DESC",
    "LIST_JOBS_DESC",
    "MAX_STEPS",
    "MODEL_NAME",
    "RunResult",
    "SCORE_MATCH_DESC",
    "SEARCH_CANDIDATES_DESC",
    "SYSTEM_PROMPT",
    "USER_PROMPT_TEMPLATE",
    "build_result",
    "format_exception",
    "parse_final_json",
]
