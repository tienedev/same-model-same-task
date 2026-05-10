"""Deterministic gold ranking + NDCG@3 scoring for the candidate-matching task.

The rubric below is *opinionated, not ground truth*. It maps `score_match()`
breakdowns to a graded relevance score 0..3 used by NDCG@3. Reasonable
recruiters would disagree on edge cases; we own the rubric publicly in the
README "Scoring" section so disagreement is visible.

See docs/plans/2026-05-10-deterministic-scorer-design.md for the rationale.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

# Categorical values returned by tools/python/tools.py:score_match
_HARD_EXPERIENCE = "under"           # candidate under-experienced
_HARD_LOCATION = "mismatch"          # incompatible location, no remote
_HARD_SALARY = "above_max"           # candidate expects more than ceiling
_SOFT_EXPERIENCE = "over"            # over-qualified by 5+ years
_SOFT_LOCATION = "remote_compatible" # remote workable but not co-located
_SOFT_SALARY = "below_min"           # candidate accepts less than floor


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "results" / ".gold-cache"


def _rel_from_breakdown(breakdown: dict[str, Any]) -> int:
    """Map a `score_match()` breakdown to a graded relevance 0..3.

    Tiers are mutually exclusive (first match wins, in evaluation order):
      0  hard_count ≥ 1 (any hard dealbreaker)
      0  skill_pct < 34
      3  skill_pct ≥ 67 AND soft_count == 0
      2  skill_pct ≥ 67 AND soft_count == 1
      1  skill_pct ≥ 67 AND soft_count ≥ 2
      1  34 ≤ skill_pct < 67 (no hard dealbreaker by this point)

    Hard dealbreakers: experience=under, location=mismatch, salary=above_max.
    Soft concerns:     experience=over,  location=remote_compatible, salary=below_min.
    """
    hard_count = (
        int(breakdown.get("experience_fit") == _HARD_EXPERIENCE)
        + int(breakdown.get("location_fit") == _HARD_LOCATION)
        + int(breakdown.get("salary_fit") == _HARD_SALARY)
    )
    if hard_count >= 1:
        return 0

    skill_pct = int(breakdown.get("skill_match_pct", 0))
    if skill_pct < 34:
        return 0

    soft_count = (
        int(breakdown.get("experience_fit") == _SOFT_EXPERIENCE)
        + int(breakdown.get("location_fit") == _SOFT_LOCATION)
        + int(breakdown.get("salary_fit") == _SOFT_SALARY)
    )

    if skill_pct >= 67:
        if soft_count == 0:
            return 3
        if soft_count == 1:
            return 2
        return 1
    # 34 ≤ skill_pct < 67, no hard dealbreaker
    return 1


# Lazy import — keep top-of-module import-time light
def _score_match(candidate_id: str, job_id: str) -> dict[str, Any]:
    from tools.python.tools import score_match
    return score_match(candidate_id, job_id)


def _candidate_ids() -> list[str]:
    """All candidate IDs, sorted asc for deterministic iteration."""
    candidates_path = ROOT / "data" / "candidates.json"
    return sorted(c["id"] for c in json.loads(candidates_path.read_text()))


def _cache_key(job_id: str, candidate_id: str, breakdown: dict[str, Any]) -> str:
    """Hash of (job, candidate, breakdown) so cache invalidates if score_match changes."""
    canonical = json.dumps(
        {"job_id": job_id, "candidate_id": candidate_id, "breakdown": breakdown},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def gold_relevance(job_id: str, candidate_id: str) -> int:
    """Graded relevance 0..3 for a (job, candidate) pair.

    Caches to disk under results/.gold-cache/ for re-runnability. Cache key
    includes the breakdown so any change to score_match() auto-invalidates.
    """
    breakdown = _score_match(candidate_id, job_id)
    if "error" in breakdown:
        return 0
    key = _cache_key(job_id, candidate_id, breakdown)
    cache_path = CACHE_DIR / f"{key}.json"
    if cache_path.exists():
        return int(json.loads(cache_path.read_text())["rel"])
    rel = _rel_from_breakdown(breakdown)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({
        "job_id": job_id,
        "candidate_id": candidate_id,
        "rel": rel,
        "breakdown": breakdown,
        "computed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, ensure_ascii=False))
    return rel


def gold_top_k(job_id: str, k: int = 3) -> list[tuple[str, int]]:
    """Top-k candidates for a job, sorted by (rel desc, candidate_id asc).

    Returns exactly k entries (the dataset has 50 candidates and k is small,
    so we never need padding in practice).
    """
    scored = [(cid, gold_relevance(job_id, cid)) for cid in _candidate_ids()]
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored[:k]
