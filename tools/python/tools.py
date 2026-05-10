"""4 deterministic tools shared by all framework adapters.

These are pure-Python functions that operate on the static datasets in
`data/candidates.json` and `data/jobs.json`. No LLM calls inside tools.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@cache
def _candidates() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "candidates.json").read_text())


@cache
def _jobs() -> list[dict[str, Any]]:
    return json.loads((DATA_DIR / "jobs.json").read_text())


@cache
def _candidate_by_id() -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in _candidates()}


@cache
def _job_by_id() -> dict[str, dict[str, Any]]:
    return {j["id"]: j for j in _jobs()}


def search_candidates(
    query: str,
    filters: dict[str, Any] | None = None,
) -> list[str]:
    """Search candidates by free-text query and optional filters.

    Args:
        query: Free-text query, matched (case-insensitive, OR on tokens) against
            current_title, skills, and bio.
        filters: Optional dict with keys:
            - min_years_experience: int
            - required_skills: list[str] (AND match)
            - location: str (exact match or "remote" — matches remote_ok=True)
            - max_salary_eur: int

    Returns:
        List of candidate IDs (max 10), sorted by number of matched query tokens
        descending then by id ascending for determinism.
    """
    filters = filters or {}
    query_tokens = [t.lower() for t in query.split() if t]

    candidates_with_score: list[tuple[int, str]] = []
    for c in _candidates():
        # Filters first (hard reject)
        if (min_y := filters.get("min_years_experience")) is not None:
            if c["years_experience"] < min_y:
                continue
        if req_skills := filters.get("required_skills"):
            cand_skills_lower = {s.lower() for s in c["skills"]}
            if not all(s.lower() in cand_skills_lower for s in req_skills):
                continue
        if (loc := filters.get("location")) is not None:
            loc_lower = loc.lower()
            if loc_lower == "remote":
                if not c["remote_ok"]:
                    continue
            elif loc_lower != c["location"].lower():
                continue
        if (max_sal := filters.get("max_salary_eur")) is not None:
            if c["expected_salary_eur"] > max_sal:
                continue

        # Score by token matches
        haystack = (
            c["current_title"].lower()
            + " "
            + " ".join(s.lower() for s in c["skills"])
            + " "
            + c["bio"].lower()
        )
        score = sum(1 for t in query_tokens if t in haystack)
        if score > 0 or not query_tokens:
            candidates_with_score.append((score, c["id"]))

    candidates_with_score.sort(key=lambda x: (-x[0], x[1]))
    return [cid for _, cid in candidates_with_score[:10]]


def get_candidate_profile(candidate_id: str) -> dict[str, Any] | None:
    """Get full profile for a candidate, or None if not found."""
    return _candidate_by_id().get(candidate_id)


def score_match(candidate_id: str, job_id: str) -> dict[str, Any]:
    """Score how well a candidate matches a job.

    Returns the breakdown (skill_match_pct, experience_fit, location_fit,
    salary_fit) — NOT an aggregate score. The agent must synthesize.
    """
    cand = _candidate_by_id().get(candidate_id)
    job = _job_by_id().get(job_id)
    if cand is None or job is None:
        return {"error": f"unknown candidate_id={candidate_id} or job_id={job_id}"}

    # Skill match: % of job required_skills present in candidate skills
    cand_skills_lower = {s.lower() for s in cand["skills"]}
    required_lower = [s.lower() for s in job["required_skills"]]
    matched_required = sum(1 for s in required_lower if s in cand_skills_lower)
    skill_match_pct = (
        round(100 * matched_required / len(required_lower)) if required_lower else 0
    )

    # Experience fit
    if cand["years_experience"] >= job["min_years_experience"]:
        years_above = cand["years_experience"] - job["min_years_experience"]
        # 5+ years above min for a junior role = "over"
        experience_fit = "over" if years_above >= 5 else "match"
    else:
        experience_fit = "under"

    # Location fit
    if cand["location"].lower() == job["location"].lower():
        location_fit = "match"
    elif job["remote_ok"] and cand["remote_ok"]:
        location_fit = "remote_compatible"
    else:
        location_fit = "mismatch"

    # Salary fit
    sal = cand["expected_salary_eur"]
    smin, smax = job["salary_range_eur"]["min"], job["salary_range_eur"]["max"]
    if sal < smin:
        salary_fit = "below_min"
    elif sal > smax:
        salary_fit = "above_max"
    else:
        salary_fit = "in_range"

    return {
        "skill_match_pct": skill_match_pct,
        "experience_fit": experience_fit,
        "location_fit": location_fit,
        "salary_fit": salary_fit,
    }


def list_jobs() -> list[dict[str, Any]]:
    """List all jobs with id/title/location only (lightweight)."""
    return [
        {"id": j["id"], "title": j["title"], "location": j["location"]}
        for j in _jobs()
    ]
