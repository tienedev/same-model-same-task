"""Deterministic gold ranking + NDCG@3 scoring for the candidate-matching task.

The rubric below is *opinionated, not ground truth*. It maps `score_match()`
breakdowns to a graded relevance score 0..3 used by NDCG@3. Reasonable
recruiters would disagree on edge cases; we own the rubric publicly in the
README "Scoring" section so disagreement is visible.

See docs/plans/2026-05-10-deterministic-scorer-design.md for the rationale.
"""

from __future__ import annotations

from typing import Any

# Categorical values returned by tools/python/tools.py:score_match
_HARD_EXPERIENCE = "under"           # candidate under-experienced
_HARD_LOCATION = "mismatch"          # incompatible location, no remote
_HARD_SALARY = "above_max"           # candidate expects more than ceiling
_SOFT_EXPERIENCE = "over"            # over-qualified by 5+ years
_SOFT_LOCATION = "remote_compatible" # remote workable but not co-located
_SOFT_SALARY = "below_min"           # candidate accepts less than floor


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
