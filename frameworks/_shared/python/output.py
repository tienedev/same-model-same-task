"""Final-output parsing & exception formatting helpers.

All adapters use these so the bench measures framework behavior, not
per-adapter cleanup logic differences.
"""

from __future__ import annotations

import json
import re
from typing import Any

# Strips ```json ... ``` or ``` ... ``` Markdown fences. Anchored to start/end
# only — does NOT consume backticks inside content. The TypeScript mirror is
# in frameworks/_shared/typescript/output.ts.
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_final_json(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse the agent's final text as JSON.

    Strips Markdown code fences (``` and ```json) if the model wrapped
    the JSON despite the prompt asking it not to. Returns
    (parsed_dict_or_none, error_message_or_none).
    """
    cleaned = _FENCE_RE.sub("", (text or "").strip()).strip()
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as e:
        return None, f"JSONDecodeError: {e}"


def format_exception(e: BaseException) -> str:
    """Stable single-line exception formatter used in tool dispatch / loops."""
    return f"{type(e).__name__}: {e}"
