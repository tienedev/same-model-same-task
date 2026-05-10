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
import math
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


def ndcg_at_3(agent_rels: list[int], gold_rels: list[int]) -> float:
    """Normalized Discounted Cumulative Gain @ 3.

    DCG = Σ rel_i / log2(i + 2)    (i is 0-indexed; position 1 → log2(2) = 1)
    IDCG = DCG of the gold's top-3 relevance vector.
    NDCG = DCG / IDCG, or 1.0 if IDCG == 0 (no relevant candidate exists).

    Both inputs must be length-3 lists of integer relevance values (rel ≥ 0).
    """
    def _dcg(rels: list[int]) -> float:
        return sum(rel / math.log2(i + 2) for i, rel in enumerate(rels))

    idcg = _dcg(gold_rels)
    if idcg == 0:
        return 1.0
    return _dcg(agent_rels) / idcg


def compute_deterministic_score(parsed_output: dict[str, Any], job_id: str) -> dict[str, Any]:
    """Compute the deterministic_score block for a single valid run.

    Returns a dict suitable to write under run["deterministic_score"] — see
    docs/plans/2026-05-10-deterministic-scorer-design.md § 6 for the schema.
    """
    ranked = parsed_output.get("ranked_candidates") or []
    agent_ids = [r.get("candidate_id") for r in ranked[:3]]

    valid_ids = set(_candidate_ids())
    invalid_id_in_ranked = any(cid not in valid_ids for cid in agent_ids)

    # Pad to length 3 in case the agent returned fewer (validation should
    # have caught this, but compute_deterministic_score must be total).
    while len(agent_ids) < 3:
        agent_ids.append(None)

    agent_rels = [
        gold_relevance(job_id, cid) if cid in valid_ids else 0
        for cid in agent_ids
    ]
    gold_pairs = gold_top_k(job_id, k=3)
    gold_ids = [cid for cid, _ in gold_pairs]
    gold_rels = [rel for _, rel in gold_pairs]

    # Hit@1: agent's #1 is relevant or better (rel ≥ 2). Stricter than
    # "agent_ids[0] == gold_ids[0]" — gives credit for any "Relevant" pick.
    hit_at_1 = (agent_rels[0] >= 2)

    # Precision@3: fraction of agent's top-3 that are relevant (rel ≥ 2)
    precision_at_3 = sum(1 for r in agent_rels if r >= 2) / 3

    # Recall@3: fraction of gold top-3 that the agent recovered
    gold_id_set = set(gold_ids)
    agent_id_set = {cid for cid in agent_ids if cid in valid_ids}
    recall_at_3 = len(agent_id_set & gold_id_set) / 3

    return {
        "ndcg_at_3": ndcg_at_3(agent_rels, gold_rels),
        "hit_at_1": hit_at_1,
        "precision_at_3": precision_at_3,
        "recall_at_3": recall_at_3,
        "invalid_id_in_ranked": invalid_id_in_ranked,
        # JSON-friendly snapshots: lists of [id, rel] pairs
        "gold_top_3": [[cid, rel] for cid, rel in gold_pairs],
        "agent_top_3": [[cid, rel] for cid, rel in zip(agent_ids, agent_rels, strict=True)],
    }
