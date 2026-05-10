# Deterministic Scorer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic IR-style scorer (NDCG@3 + Hit@1 over graded relevance) that becomes the primary ranking signal in the leaderboard, demoting the Gemini-judge to a single qualitative axis.

**Architecture:** Two new pure-Python files (`harness/gold_ranking.py` for the relevance rubric + NDCG math, `harness/score_deterministic.py` for the CLI), edits to `scripts/summarize.py` to aggregate and surface the new metrics, and docstring/doc updates elsewhere. Pure functions throughout — no network, no LLM, fully cacheable on disk. Schema for `run["deterministic_score"]` and aggregation rules are defined by the spec at `docs/plans/2026-05-10-deterministic-scorer-design.md` (read it first).

**Tech Stack:** Python 3.11, `click` for the CLI (already a dep), `pytest` for tests, in-tree `tools/python/tools.py:score_match`, no new dependencies.

---

## File Structure

| File | Responsibility | Status |
|---|---|---|
| `harness/gold_ranking.py` | Pure functions: `_rel_from_breakdown`, `gold_relevance`, `gold_top_k`, `ndcg_at_3`, `compute_deterministic_score`. Disk cache. | Create |
| `harness/score_deterministic.py` | CLI: read results JSON, augment each valid run with `deterministic_score`, write back. | Create |
| `scripts/test_deterministic_scorer.py` | Unit tests for the above. | Create |
| `scripts/summarize.py` | Aggregate `deterministic_score` per framework; new leaderboard columns; demote `/20`. | Modify |
| `harness/judge.py` | Docstring update only — citing the stronger self-bias finding. | Modify |
| `README.md` | New "Scoring" section; update Caveat § 2. | Modify |
| `docs/plans/task-spec.md` | § 7 pointer to the new design doc. | Modify |
| `.gitignore` | Add `results/.gold-cache/`. | Modify |

The rubric (graded-relevance mapping) lives **only** in `_rel_from_breakdown()` in `harness/gold_ranking.py`. The README "Scoring" section quotes the rubric but does not re-implement it. Single source of truth.

---

## Task 1: `_rel_from_breakdown()` — the graded-relevance rubric

**Files:**
- Create: `harness/gold_ranking.py`
- Create: `scripts/test_deterministic_scorer.py`

- [ ] **Step 1: Write the failing tests (one per tier + dealbreaker)**

Create `scripts/test_deterministic_scorer.py`:

```python
"""Unit tests for harness/gold_ranking.py and harness/score_deterministic.py.

Pure-function tests use synthetic breakdown dicts so the rubric is verified
in isolation, decoupled from the real dataset.
"""

import pytest


def _bd(skill=100, exp="match", loc="match", sal="in_range"):
    """Shorthand builder for score_match()-shaped breakdown dicts."""
    return {
        "skill_match_pct": skill,
        "experience_fit": exp,
        "location_fit": loc,
        "salary_fit": sal,
    }


class TestRelFromBreakdown:
    def test_tier_3_ideal_candidate(self):
        from harness.gold_ranking import _rel_from_breakdown
        # 100% skills, no hard dealbreaker, no soft concern
        assert _rel_from_breakdown(_bd()) == 3

    def test_tier_3_at_skill_threshold(self):
        from harness.gold_ranking import _rel_from_breakdown
        # exactly at the 67% threshold
        assert _rel_from_breakdown(_bd(skill=67)) == 3

    def test_tier_2_one_soft_concern(self):
        from harness.gold_ranking import _rel_from_breakdown
        # remote_compatible is a soft concern
        assert _rel_from_breakdown(_bd(loc="remote_compatible")) == 2

    def test_tier_2_below_min_salary_is_soft(self):
        from harness.gold_ranking import _rel_from_breakdown
        # candidate accepts less than min — soft, not hard
        assert _rel_from_breakdown(_bd(sal="below_min")) == 2

    def test_tier_2_over_experience_is_soft(self):
        from harness.gold_ranking import _rel_from_breakdown
        assert _rel_from_breakdown(_bd(exp="over")) == 2

    def test_tier_1_two_soft_concerns(self):
        from harness.gold_ranking import _rel_from_breakdown
        # high skills but 2 soft concerns
        assert _rel_from_breakdown(_bd(loc="remote_compatible", sal="below_min")) == 1

    def test_tier_1_mid_skills(self):
        from harness.gold_ranking import _rel_from_breakdown
        # skill in [34, 67) with no hard dealbreaker → rel=1
        assert _rel_from_breakdown(_bd(skill=50)) == 1

    def test_tier_0_low_skills(self):
        from harness.gold_ranking import _rel_from_breakdown
        assert _rel_from_breakdown(_bd(skill=33)) == 0
        assert _rel_from_breakdown(_bd(skill=0)) == 0

    def test_tier_0_hard_dealbreaker_under_experience(self):
        from harness.gold_ranking import _rel_from_breakdown
        # under-experienced disqualifies even with perfect skills
        assert _rel_from_breakdown(_bd(exp="under")) == 0

    def test_tier_0_hard_dealbreaker_location_mismatch(self):
        from harness.gold_ranking import _rel_from_breakdown
        assert _rel_from_breakdown(_bd(loc="mismatch")) == 0

    def test_tier_0_hard_dealbreaker_above_max_salary(self):
        from harness.gold_ranking import _rel_from_breakdown
        # candidate wants more than max — won't accept
        assert _rel_from_breakdown(_bd(sal="above_max")) == 0

    def test_tier_0_any_hard_overrides_everything(self):
        from harness.gold_ranking import _rel_from_breakdown
        # perfect on every other axis but one hard → still 0
        assert _rel_from_breakdown(_bd(skill=100, loc="mismatch")) == 0
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
cd /Users/tiene/Projets/same-model-same-task
.venv/bin/pytest scripts/test_deterministic_scorer.py -v
```

Expected: 11 failures with `ModuleNotFoundError: No module named 'harness.gold_ranking'` (or `ImportError`).

- [ ] **Step 3: Implement `_rel_from_breakdown`**

Create `harness/gold_ranking.py`:

```python
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
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
.venv/bin/pytest scripts/test_deterministic_scorer.py -v
```

Expected: all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add harness/gold_ranking.py scripts/test_deterministic_scorer.py
git commit -m "feat(scorer): graded-relevance rubric _rel_from_breakdown()"
```

---

## Task 2: `gold_relevance()` and `gold_top_k()` — disk-cached lookup

**Files:**
- Modify: `harness/gold_ranking.py`
- Modify: `scripts/test_deterministic_scorer.py`
- Modify: `.gitignore`

- [ ] **Step 1: Add `.gold-cache/` to `.gitignore`**

Open `.gitignore`, append:

```
# Deterministic scorer cache — re-buildable from data/ at any time
results/.gold-cache/
```

- [ ] **Step 2: Write failing tests for `gold_relevance` and `gold_top_k`**

Append to `scripts/test_deterministic_scorer.py`:

```python
class TestGoldRelevance:
    def test_known_perfect_match(self):
        """cand-001 is the textbook perfect match for job-001 (per task-spec § 3)."""
        from harness.gold_ranking import gold_relevance
        # 100% skills, Paris match, in-range salary, 6y exp on a 5y-min job
        assert gold_relevance("job-001", "cand-001") == 3

    def test_unknown_returns_zero(self):
        from harness.gold_ranking import gold_relevance
        # Unknown ids: score_match returns {"error": ...} → no skill_pct → rel=0
        assert gold_relevance("job-001", "cand-999") == 0
        assert gold_relevance("job-999", "cand-001") == 0


class TestGoldTopK:
    def test_returns_k_items_sorted(self):
        from harness.gold_ranking import gold_top_k
        top3 = gold_top_k("job-001", k=3)
        assert len(top3) == 3
        # sorted by (rel desc, candidate_id asc) — non-increasing rel
        rels = [rel for _, rel in top3]
        assert rels == sorted(rels, reverse=True)

    def test_stability_across_calls(self):
        """Re-running gold_top_k must yield byte-identical output (no hidden RNG)."""
        from harness.gold_ranking import gold_top_k
        first = gold_top_k("job-001", k=3)
        second = gold_top_k("job-001", k=3)
        assert first == second
        # Also a 3rd call after explicit re-import
        import importlib
        import harness.gold_ranking as gr
        importlib.reload(gr)
        third = gr.gold_top_k("job-001", k=3)
        assert first == third

    def test_tie_break_by_candidate_id_asc(self):
        """When two candidates share the same rel, lower candidate_id wins."""
        from harness.gold_ranking import gold_top_k
        # job-001: cand-001 (rel=3) is unambiguously #1; below it, ties are sorted asc
        top10 = gold_top_k("job-001", k=10)
        # Group by rel; within each group, candidate_ids must be ascending
        from itertools import groupby
        for rel, group in groupby(top10, key=lambda x: x[1]):
            ids_in_group = [cid for cid, _ in group]
            assert ids_in_group == sorted(ids_in_group), (
                f"tie-break violated within rel={rel} bucket: {ids_in_group}"
            )


class TestDiskCache:
    def test_cache_file_created_and_reused(self, tmp_path, monkeypatch):
        """First call writes a cache file; second call reads it (file mtime unchanged)."""
        import harness.gold_ranking as gr
        cache_dir = tmp_path / ".gold-cache"
        monkeypatch.setattr(gr, "CACHE_DIR", cache_dir)
        gr.gold_relevance("job-001", "cand-001")
        assert cache_dir.exists()
        files = list(cache_dir.glob("*.json"))
        assert len(files) == 1
        mtime_before = files[0].stat().st_mtime_ns
        # Second call must not rewrite the file
        gr.gold_relevance("job-001", "cand-001")
        mtime_after = files[0].stat().st_mtime_ns
        assert mtime_before == mtime_after, "cache file rewritten on hit"
```

- [ ] **Step 3: Run tests, verify they fail**

```bash
.venv/bin/pytest scripts/test_deterministic_scorer.py::TestGoldRelevance scripts/test_deterministic_scorer.py::TestGoldTopK scripts/test_deterministic_scorer.py::TestDiskCache -v
```

Expected: failures with `ImportError: cannot import name 'gold_relevance'` etc.

- [ ] **Step 4: Implement `gold_relevance`, `gold_top_k`, disk cache**

Append to `harness/gold_ranking.py`:

```python
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "results" / ".gold-cache"

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
```

- [ ] **Step 5: Run tests, verify they pass**

```bash
.venv/bin/pytest scripts/test_deterministic_scorer.py -v
```

Expected: all tests pass (11 from Task 1 + 5 new = 16).

- [ ] **Step 6: Commit**

```bash
git add harness/gold_ranking.py scripts/test_deterministic_scorer.py .gitignore
git commit -m "feat(scorer): gold_relevance/gold_top_k with disk cache"
```

---

## Task 3: `ndcg_at_3()` — the IR metric

**Files:**
- Modify: `harness/gold_ranking.py`
- Modify: `scripts/test_deterministic_scorer.py`

- [ ] **Step 1: Write failing tests**

Append to `scripts/test_deterministic_scorer.py`:

```python
class TestNdcgAt3:
    def test_perfect_order_is_1(self):
        from harness.gold_ranking import ndcg_at_3
        # Agent matches gold exactly: NDCG = 1.0
        assert ndcg_at_3(agent_rels=[3, 3, 2], gold_rels=[3, 3, 2]) == pytest.approx(1.0)

    def test_all_zeros_in_agent_is_0(self):
        from harness.gold_ranking import ndcg_at_3
        # Agent picked 3 irrelevant candidates while gold had 3 relevant ones
        assert ndcg_at_3(agent_rels=[0, 0, 0], gold_rels=[3, 3, 2]) == pytest.approx(0.0)

    def test_swap_rank1_rank3_strictly_between(self):
        from harness.gold_ranking import ndcg_at_3
        # Same items, wrong order — must be strictly between 0 and 1
        score = ndcg_at_3(agent_rels=[1, 3, 3], gold_rels=[3, 3, 1])
        assert 0.0 < score < 1.0

    def test_idcg_zero_fallback_returns_1(self):
        from harness.gold_ranking import ndcg_at_3
        # Pathological: no relevant candidates in the pool — agent can't fail
        assert ndcg_at_3(agent_rels=[0, 0, 0], gold_rels=[0, 0, 0]) == 1.0

    def test_log2_discount_shape(self):
        """DCG@3 with rels=[1,0,0] = 1/log2(2) = 1. With rels=[0,1,0] = 1/log2(3)."""
        import math
        from harness.gold_ranking import ndcg_at_3
        # Both agent and gold have a single rel=1; check the discount math
        # agent: rel=1 at position 2 → DCG = 1/log2(3) ≈ 0.6309
        # gold:  rel=1 at position 1 → IDCG = 1/log2(2) = 1.0
        # NDCG = 0.6309 / 1.0
        expected = (1 / math.log2(3)) / 1.0
        assert ndcg_at_3(agent_rels=[0, 1, 0], gold_rels=[1, 0, 0]) == pytest.approx(expected)
```

- [ ] **Step 2: Run, verify failure**

```bash
.venv/bin/pytest scripts/test_deterministic_scorer.py::TestNdcgAt3 -v
```

Expected: 5 failures with `ImportError`.

- [ ] **Step 3: Implement `ndcg_at_3`**

Append to `harness/gold_ranking.py`:

```python
import math


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
```

- [ ] **Step 4: Run, verify pass**

```bash
.venv/bin/pytest scripts/test_deterministic_scorer.py::TestNdcgAt3 -v
```

Expected: all 5 pass.

- [ ] **Step 5: Commit**

```bash
git add harness/gold_ranking.py scripts/test_deterministic_scorer.py
git commit -m "feat(scorer): ndcg_at_3 with log2 discount"
```

---

## Task 4: `compute_deterministic_score()` — wraps it for a single run

**Files:**
- Modify: `harness/gold_ranking.py`
- Modify: `scripts/test_deterministic_scorer.py`

- [ ] **Step 1: Write failing test**

Append to `scripts/test_deterministic_scorer.py`:

```python
class TestComputeDeterministicScore:
    def test_known_good_baseline_python_trial_2(self):
        """trial 2 of baseline-python on job-001 picks cand-001/026/003.
        cand-001 (rel=3) is the textbook winner → Hit@1 must be True.
        """
        from harness.gold_ranking import compute_deterministic_score
        parsed_output = {
            "job_id": "job-001",
            "ranked_candidates": [
                {"rank": 1, "candidate_id": "cand-001", "score": 100, "justification": "..."},
                {"rank": 2, "candidate_id": "cand-026", "score": 96, "justification": "..."},
                {"rank": 3, "candidate_id": "cand-003", "score": 93, "justification": "..."},
            ],
        }
        result = compute_deterministic_score(parsed_output, "job-001")
        assert result["hit_at_1"] is True
        assert 0.0 <= result["ndcg_at_3"] <= 1.0
        assert 0.0 <= result["precision_at_3"] <= 1.0
        assert 0.0 <= result["recall_at_3"] <= 1.0
        assert result["invalid_id_in_ranked"] is False
        # Snapshot shape: 3 tuples in agent and gold
        assert len(result["agent_top_3"]) == 3
        assert len(result["gold_top_3"]) == 3
        # The agent's #1 is cand-001 with rel=3 → first element
        assert result["agent_top_3"][0] == ["cand-001", 3]

    def test_invalid_id_detected(self):
        from harness.gold_ranking import compute_deterministic_score
        parsed_output = {
            "job_id": "job-001",
            "ranked_candidates": [
                {"rank": 1, "candidate_id": "cand-001", "score": 100, "justification": "x"},
                {"rank": 2, "candidate_id": "cand-FAKE", "score": 50, "justification": "x"},
                {"rank": 3, "candidate_id": "cand-003", "score": 33, "justification": "x"},
            ],
        }
        result = compute_deterministic_score(parsed_output, "job-001")
        assert result["invalid_id_in_ranked"] is True

    def test_hit_at_1_requires_rel_at_least_2(self):
        """Agent's #1 with rel=1 (marginal) does NOT count as a hit."""
        from harness.gold_ranking import compute_deterministic_score, gold_relevance
        # Find any candidate with rel <= 1 for job-001 by scanning
        from harness.gold_ranking import _candidate_ids
        marginal = next(
            cid for cid in _candidate_ids() if gold_relevance("job-001", cid) <= 1
        )
        parsed_output = {
            "job_id": "job-001",
            "ranked_candidates": [
                {"rank": 1, "candidate_id": marginal, "score": 50, "justification": "x"},
                {"rank": 2, "candidate_id": "cand-001", "score": 40, "justification": "x"},
                {"rank": 3, "candidate_id": "cand-003", "score": 30, "justification": "x"},
            ],
        }
        result = compute_deterministic_score(parsed_output, "job-001")
        assert result["hit_at_1"] is False
```

- [ ] **Step 2: Run, verify failure**

```bash
.venv/bin/pytest scripts/test_deterministic_scorer.py::TestComputeDeterministicScore -v
```

Expected: failures with `ImportError`.

- [ ] **Step 3: Implement `compute_deterministic_score`**

Append to `harness/gold_ranking.py`:

```python
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
        "agent_top_3": [[cid, rel] for cid, rel in zip(agent_ids, agent_rels, strict=False)],
        "gold_top_3": [[cid, rel] for cid, rel in gold_pairs],
    }
```

- [ ] **Step 4: Run, verify pass**

```bash
.venv/bin/pytest scripts/test_deterministic_scorer.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add harness/gold_ranking.py scripts/test_deterministic_scorer.py
git commit -m "feat(scorer): compute_deterministic_score for a single run"
```

---

## Task 5: `score_deterministic.py` CLI — the user-facing entry point

**Files:**
- Create: `harness/score_deterministic.py`
- Modify: `scripts/test_deterministic_scorer.py`

- [ ] **Step 1: Write failing test (end-to-end on a synthetic results file)**

Append to `scripts/test_deterministic_scorer.py`:

```python
class TestScoreDeterministicCli:
    def _synthetic_results(self):
        return {
            "framework": "synthetic-fw",
            "runs": [
                {
                    "framework": "synthetic-fw",
                    "job_id": "job-001",
                    "valid": True,
                    "parsed_output": {
                        "job_id": "job-001",
                        "ranked_candidates": [
                            {"rank": 1, "candidate_id": "cand-001", "score": 100, "justification": "x"},
                            {"rank": 2, "candidate_id": "cand-003", "score": 50, "justification": "x"},
                            {"rank": 3, "candidate_id": "cand-023", "score": 33, "justification": "x"},
                        ],
                    },
                },
                {
                    "framework": "synthetic-fw",
                    "job_id": "job-001",
                    "valid": False,
                    "parsed_output": None,
                    "parse_error": "nope",
                },
            ],
        }

    def test_augments_valid_runs_and_skips_invalid(self, tmp_path):
        import json
        import subprocess
        import sys

        p = tmp_path / "results.json"
        p.write_text(json.dumps(self._synthetic_results()))

        result = subprocess.run(
            [sys.executable, "harness/score_deterministic.py", str(p)],
            capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr

        data = json.loads(p.read_text())
        valid = data["runs"][0]
        invalid = data["runs"][1]
        assert "deterministic_score" in valid
        assert valid["deterministic_score"]["hit_at_1"] is True
        assert "deterministic_score" not in invalid or invalid["deterministic_score"].get("skipped")
        assert data["deterministic_summary"]["n_scored"] == 1
        assert data["deterministic_summary"]["n_skipped"] == 1

    def test_idempotence(self, tmp_path):
        """Running the CLI twice on the same file yields byte-identical output."""
        import json
        import subprocess
        import sys

        p = tmp_path / "results.json"
        p.write_text(json.dumps(self._synthetic_results()))

        for _ in range(2):
            r = subprocess.run(
                [sys.executable, "harness/score_deterministic.py", str(p)],
                capture_output=True, text=True, check=False,
            )
            assert r.returncode == 0

        first_pass = p.read_text()
        # Run a 3rd time and compare
        subprocess.run(
            [sys.executable, "harness/score_deterministic.py", str(p)],
            capture_output=True, text=True, check=False,
        )
        assert p.read_text() == first_pass
```

- [ ] **Step 2: Run, verify failure**

```bash
.venv/bin/pytest scripts/test_deterministic_scorer.py::TestScoreDeterministicCli -v
```

Expected: `FileNotFoundError` or non-zero return code (the script doesn't exist).

- [ ] **Step 3: Implement the CLI**

Create `harness/score_deterministic.py`:

```python
"""Augment a results JSON with a deterministic_score block per valid run.

Mirrors harness/judge.py in shape but makes zero API calls — pure functions
over score_match() output. Idempotent: re-running on the same file is a no-op.

Usage:
    python harness/score_deterministic.py results/headline/baseline-python.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.gold_ranking import compute_deterministic_score  # noqa: E402


@click.command()
@click.argument("results_file", type=click.Path(exists=True))
@click.option("--out", default=None, type=click.Path(), help="Output file (default: in-place)")
def main(results_file: str, out: str | None) -> None:
    summary = json.loads(Path(results_file).read_text())

    n_scored = 0
    n_skipped = 0
    for run in summary.get("runs", []):
        if not run.get("valid"):
            run["deterministic_score"] = {"skipped": True, "reason": "invalid"}
            n_skipped += 1
            continue
        parsed = run.get("parsed_output") or {}
        job_id = run.get("job_id")
        run["deterministic_score"] = compute_deterministic_score(parsed, job_id)
        n_scored += 1

    summary["deterministic_summary"] = {"n_scored": n_scored, "n_skipped": n_skipped}

    out_path = Path(out) if out else Path(results_file)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    click.echo(f"Wrote {out_path} (n_scored={n_scored} n_skipped={n_skipped})", err=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run, verify pass**

```bash
.venv/bin/pytest scripts/test_deterministic_scorer.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add harness/score_deterministic.py scripts/test_deterministic_scorer.py
git commit -m "feat(scorer): score_deterministic.py CLI (idempotent, no API calls)"
```

---

## Task 6: `summarize.py` — aggregate deterministic_score per framework

**Files:**
- Modify: `scripts/summarize.py`
- Modify: `scripts/test_summarize.py`
- Modify: `scripts/fixtures/run-frameworkA-job-001.json` (synthetic data may need deterministic_score blocks)

- [ ] **Step 1: Read existing fixture files to understand shape**

```bash
cat scripts/fixtures/run-frameworkA-job-001.json
cat scripts/fixtures/run-frameworkA-job-002.json
cat scripts/fixtures/run-frameworkB-job-001.json
```

Note: these fixtures may or may not contain `deterministic_score`. For Task 6 tests, we'll write fixture data inline rather than rely on these files.

- [ ] **Step 2: Write failing tests**

Append to `scripts/test_summarize.py`:

```python
class TestDeterministicAggregation:
    def _runs_with_det_scores(self):
        return [
            {
                "framework": "fwX", "valid": True, "elapsed_s": 1.0,
                "input_tokens": 100, "output_tokens": 50, "tool_calls": 3,
                "deterministic_score": {
                    "ndcg_at_3": 1.0, "hit_at_1": True,
                    "precision_at_3": 1.0, "recall_at_3": 1.0,
                    "invalid_id_in_ranked": False,
                    "agent_top_3": [], "gold_top_3": [],
                },
            },
            {
                "framework": "fwX", "valid": True, "elapsed_s": 2.0,
                "input_tokens": 200, "output_tokens": 80, "tool_calls": 5,
                "deterministic_score": {
                    "ndcg_at_3": 0.5, "hit_at_1": False,
                    "precision_at_3": 0.33, "recall_at_3": 0.33,
                    "invalid_id_in_ranked": False,
                    "agent_top_3": [], "gold_top_3": [],
                },
            },
            {
                "framework": "fwX", "valid": False,
                "deterministic_score": {"skipped": True, "reason": "invalid"},
            },
        ]

    def test_aggregates_ndcg_and_hit_at_1(self):
        from scripts.summarize import compute_stats
        stats = compute_stats(self._runs_with_det_scores())
        fwx = next(s for s in stats if s["framework"] == "fwX")
        # Mean of 1.0 and 0.5
        assert fwx["mean_ndcg_at_3"] == pytest.approx(0.75)
        # Hit@1 rate: 1 of 2 valid runs
        assert fwx["hit_at_1_rate"] == pytest.approx(0.5)
        assert fwx["n_scored"] == 2

    def test_handles_missing_det_score(self):
        """Old results JSONs without deterministic_score → metrics are None."""
        from scripts.summarize import compute_stats
        runs = [
            {"framework": "old", "valid": True, "elapsed_s": 1.0,
             "input_tokens": 1, "output_tokens": 1, "tool_calls": 0}
        ]
        stats = compute_stats(runs)
        s = stats[0]
        assert s["mean_ndcg_at_3"] is None
        assert s["hit_at_1_rate"] is None
        assert s["n_scored"] == 0
```

(Add `import pytest` at the top of `scripts/test_summarize.py` if not already present.)

- [ ] **Step 3: Run, verify failure**

```bash
.venv/bin/pytest scripts/test_summarize.py::TestDeterministicAggregation -v
```

Expected: `KeyError: 'mean_ndcg_at_3'`.

- [ ] **Step 4: Add aggregation logic to `compute_stats`**

In `scripts/summarize.py`, inside the `for fw, fw_runs in by_fw.items():` loop, add deterministic aggregation alongside the existing judge-score block. Locate the block that ends with `judge_n = len(judge_totals)` and **insert immediately after it** (and update `per_valid_metrics` accordingly):

```python
            # Deterministic scores: only counted for runs with a non-skipped
            # deterministic_score block (i.e., post-hoc scoring already ran).
            det_ndcgs: list[float] = []
            det_hits: list[bool] = []
            det_precisions: list[float] = []
            det_recalls: list[float] = []
            for r in valid:
                d = r.get("deterministic_score")
                if not d or d.get("skipped"):
                    continue
                try:
                    det_ndcgs.append(float(d["ndcg_at_3"]))
                    det_hits.append(bool(d["hit_at_1"]))
                    det_precisions.append(float(d["precision_at_3"]))
                    det_recalls.append(float(d["recall_at_3"]))
                except (KeyError, TypeError, ValueError):
                    continue
            n_scored = len(det_ndcgs)
            mean_ndcg_at_3 = statistics.mean(det_ndcgs) if det_ndcgs else None
            hit_at_1_rate = (sum(det_hits) / n_scored) if n_scored else None
            mean_precision_at_3 = statistics.mean(det_precisions) if det_precisions else None
            mean_recall_at_3 = statistics.mean(det_recalls) if det_recalls else None
```

Then in `per_valid_metrics` (the dict assignment a few lines below), add:

```python
                "mean_ndcg_at_3": mean_ndcg_at_3,
                "hit_at_1_rate": hit_at_1_rate,
                "mean_precision_at_3": mean_precision_at_3,
                "mean_recall_at_3": mean_recall_at_3,
                "n_scored": n_scored,
```

And in the `else:` branch (no-valid-runs) `per_valid_metrics`, add:

```python
                "mean_ndcg_at_3": None,
                "hit_at_1_rate": None,
                "mean_precision_at_3": None,
                "mean_recall_at_3": None,
                "n_scored": 0,
```

- [ ] **Step 5: Run, verify pass**

```bash
.venv/bin/pytest scripts/test_summarize.py -v
```

Expected: all tests pass (existing + new).

- [ ] **Step 6: Commit**

```bash
git add scripts/summarize.py scripts/test_summarize.py
git commit -m "feat(summarize): aggregate deterministic_score per framework"
```

---

## Task 7: `summarize.py` — leaderboard columns + footnote

**Files:**
- Modify: `scripts/summarize.py`
- Modify: `scripts/test_summarize.py`

- [ ] **Step 1: Write failing test for the new leaderboard shape**

Append to `scripts/test_summarize.py`:

```python
class TestLeaderboardColumns:
    def test_headline_columns_present(self, tmp_path):
        from scripts.summarize import compute_stats, write_summary_md
        runs = [
            {"framework": "fwY", "valid": True, "elapsed_s": 1.0,
             "input_tokens": 100, "output_tokens": 50, "tool_calls": 3,
             "deterministic_score": {
                 "ndcg_at_3": 0.85, "hit_at_1": True,
                 "precision_at_3": 1.0, "recall_at_3": 1.0,
                 "invalid_id_in_ranked": False,
                 "agent_top_3": [], "gold_top_3": [],
             },
             "judgment": {
                 "relevance": 4, "score_coherence": 4,
                 "justification_quality": 5, "format": 5,
             }},
        ]
        out = tmp_path / "summary.md"
        write_summary_md(compute_stats(runs), out)
        text = out.read_text(encoding="utf-8")
        # New headline columns
        assert "NDCG@3" in text
        assert "Hit@1" in text
        # Legacy column kept but narrowed
        assert "JustifQ /5" in text
        # The old "Judge /20" total column is removed from the rendered table
        assert "Judge /20" not in text

    def test_justifq_renders_only_justification_quality(self, tmp_path):
        """JustifQ /5 must come from judgment.justification_quality only."""
        from scripts.summarize import compute_stats, write_summary_md
        runs = [
            {"framework": "fwZ", "valid": True, "elapsed_s": 1.0,
             "input_tokens": 100, "output_tokens": 50, "tool_calls": 3,
             "deterministic_score": {
                 "ndcg_at_3": 0.9, "hit_at_1": True,
                 "precision_at_3": 1.0, "recall_at_3": 1.0,
                 "invalid_id_in_ranked": False,
                 "agent_top_3": [], "gold_top_3": [],
             },
             "judgment": {
                 "relevance": 1, "score_coherence": 1,
                 "justification_quality": 5, "format": 1,
             }},
        ]
        out = tmp_path / "summary.md"
        write_summary_md(compute_stats(runs), out)
        text = out.read_text(encoding="utf-8")
        # justification_quality=5 → JustifQ cell shows "5.00"
        assert "5.00" in text
        # Crucially, the /20 sum (which would be 8) must NOT appear
        # in the fwZ row
        fwz_line = [l for l in text.splitlines() if "fwZ" in l][0]
        assert "8" not in fwz_line.split("|")[3]  # 3rd visible cell is the score
```

- [ ] **Step 2: Run, verify failure**

```bash
.venv/bin/pytest scripts/test_summarize.py::TestLeaderboardColumns -v
```

Expected: `assert "NDCG@3" in text` fails — the table still shows the old `Judge /20` column.

- [ ] **Step 3: Add `mean_justification_quality` aggregation**

In `scripts/summarize.py`, inside the existing judge-totals loop, add a parallel accumulator. Find this block:

```python
            judge_totals: list[int] = []
            for r in valid:
                j = r.get("judgment")
                if not j or j.get("skipped") or j.get("error"):
                    continue
                try:
                    judge_totals.append(
                        int(j["relevance"])
                        + int(j["score_coherence"])
                        + int(j["justification_quality"])
                        + int(j["format"])
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            mean_judge_score = statistics.mean(judge_totals) if judge_totals else None
            judge_n = len(judge_totals)
```

Replace it with:

```python
            judge_totals: list[int] = []           # legacy /20 — preserved in JSON only
            justif_qualities: list[int] = []       # new headline secondary signal
            for r in valid:
                j = r.get("judgment")
                if not j or j.get("skipped") or j.get("error"):
                    continue
                try:
                    judge_totals.append(
                        int(j["relevance"])
                        + int(j["score_coherence"])
                        + int(j["justification_quality"])
                        + int(j["format"])
                    )
                    justif_qualities.append(int(j["justification_quality"]))
                except (KeyError, TypeError, ValueError):
                    continue
            mean_judge_score = statistics.mean(judge_totals) if judge_totals else None
            mean_justification_quality = (
                statistics.mean(justif_qualities) if justif_qualities else None
            )
            judge_n = len(judge_totals)
```

In `per_valid_metrics` (valid-runs branch), add:

```python
                "mean_justification_quality": mean_justification_quality,
```

In `per_valid_metrics` (else branch), add:

```python
                "mean_justification_quality": None,
```

- [ ] **Step 4: Rewrite `_build_leaderboard_md` for the new columns**

In `scripts/summarize.py`, replace the body of `_build_leaderboard_md` with:

```python
def _build_leaderboard_md(stats: list[dict[str, Any]]) -> str:
    """Build the Markdown leaderboard table. Reused by README injection.

    Headline columns: NDCG@3 (mean), Hit@1 (rate).
    JustifQ /5 is shown as a secondary signal with a footnote on self-bias —
    see the README "Scoring" section for the rationale on demoting the old /20.
    """
    rows = [
        "| Framework | Valid | NDCG@3 | Hit@1 | JustifQ /5 [^j] | p50 (s) | p95 (s) | Mean tokens (in/out) | Mean tools | Cost / run (USD) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in stats:
        if s["mean_input_tokens"] is None or s["mean_output_tokens"] is None:
            tokens_cell = "—"
        else:
            tokens_cell = f"{s['mean_input_tokens']} / {s['mean_output_tokens']}"
        cost_cell = (
            "—"
            if s["estimated_cost_usd_per_run"] is None
            else f"${s['estimated_cost_usd_per_run']:.4f}"
        )
        ndcg_cell = _fmt_or_dash(s.get("mean_ndcg_at_3"), ".3f")
        hit_cell = (
            "—"
            if s.get("hit_at_1_rate") is None
            else f"{s['hit_at_1_rate'] * 100:.1f}%"
        )
        justifq_cell = _fmt_or_dash(s.get("mean_justification_quality"), ".2f")
        rows.append(
            f"| {s['framework']} | {s['count_valid']}/{s['count_total']} "
            f"| {ndcg_cell} | {hit_cell} | {justifq_cell} "
            f"| {_fmt_or_dash(s['latency_p50'])} | {_fmt_or_dash(s['latency_p95'])} "
            f"| {tokens_cell} "
            f"| {_fmt_or_dash(s['mean_tool_calls'])} "
            f"| {cost_cell} |"
        )
    rows.append("")
    rows.append(
        "[^j]: `JustifQ /5` is the LLM-judge's `justification_quality` axis only — "
        "the prose readability signal. The previous `/20` sum is preserved in the JSON "
        "but no longer surfaced: Gemini judging Gemini exhibits documented self-bias "
        "(up to 50% rubric-flip on objective rubrics; Panickssery et al. NeurIPS 2024). "
        "Use NDCG@3 + Hit@1 for ranking decisions."
    )
    return "\n".join(rows) + "\n"
```

- [ ] **Step 5: Run, verify pass**

```bash
.venv/bin/pytest scripts/test_summarize.py -v
```

Expected: all tests pass. Pay attention to the existing `test_compute_stats_aggregates_per_framework` — if it relied on the absence of new fields, it may fail and need a small touch-up (add `mean_ndcg_at_3` assertion as needed).

- [ ] **Step 6: Run summarize on real data and inspect**

```bash
.venv/bin/python scripts/summarize.py --input results/headline
cat results/summary.md
```

Expected: leaderboard shows `NDCG@3` and `Hit@1` columns filled with `—` for all rows (since no run has `deterministic_score` yet — that gets backfilled in Task 9).

- [ ] **Step 7: Commit**

```bash
git add scripts/summarize.py scripts/test_summarize.py
git commit -m "feat(summarize): leaderboard headline → NDCG@3 + Hit@1, demote /20"
```

---

## Task 8: Docs — `judge.py` docstring, README "Scoring" section, task-spec.md § 7

**Files:**
- Modify: `harness/judge.py` (docstring only)
- Modify: `README.md` (new section + caveat update)
- Modify: `docs/plans/task-spec.md` (§ 7 pointer)

- [ ] **Step 1: Update `harness/judge.py` docstring**

In `harness/judge.py`, replace the top-of-file docstring (lines 1-16) with:

```python
"""LLM judge: scores valid runs on 4 criteria using Gemini.

**As of 2026-05-10 the judge is a SECONDARY signal.** The leaderboard's primary
ranking is the deterministic NDCG@3 + Hit@1 scorer in `harness/score_deterministic.py`
(see `docs/plans/2026-05-10-deterministic-scorer-design.md`). Only the
`justification_quality` axis is surfaced; `relevance` and `score_coherence` are
subsumed by the deterministic scorer or circular (the agent invents both the
score and the justification in the same generation step), and `format` is
filtered by validation upstream.

The judge is Gemini — same family as the generator — and the literature
documents self-preference bias *up to 50%* on objective rubrics, traced to
perplexity-based familiarity (Panickssery et al. NeurIPS 2024; arXiv 2410.21819).
The judge's output is preserved in the JSON for historical comparison; the
leaderboard renders `justification_quality` only, with a footnote citing the
self-bias finding.

Caches judgments by (framework, job_id, output content hash) — content-keyed,
so cached values survive prompt-text changes. Skips runs that failed
programmatic validation.

Usage:
    GEMINI_API_KEY=... python harness/judge.py results/baseline-python.json
"""
```

- [ ] **Step 2: Update `README.md` — add "Scoring" section**

Insert a new top-level section **before** the existing `## Charts` line in `README.md`:

```markdown
## Scoring

The leaderboard is anchored on **NDCG@3** (Normalized Discounted Cumulative Gain at rank 3) over a graded-relevance gold ranking, with **Hit@1** as the secondary signal. Both are deterministic and re-computable from `data/` alone — no API calls.

**How the gold relevance is assigned.** For each (job, candidate) pair we compute `score_match()` (a pure function over the dataset — see `tools/python/tools.py`) and map its breakdown to a graded relevance `rel ∈ {0, 1, 2, 3}`:

- **3** — `skill_match_pct ≥ 67`, no hard dealbreaker (under-experienced, location mismatch, above-max salary), no soft concern (over-qualified, remote-compatible-only, below-min salary).
- **2** — same as 3 but with exactly one soft concern.
- **1** — strong skills with 2+ soft concerns, *or* mid-range skills (34-66%) with no dealbreaker.
- **0** — any hard dealbreaker, or `skill_match_pct < 34`.

NDCG@3 then evaluates how well the agent's top-3 prioritizes the highest-`rel` candidates with a log₂ position discount. Hit@1 is `True` when the agent's #1 has `rel ≥ 2`. The mapping is *opinionated, not ground truth*: a "skills-first lex" or "strict 80%" rubric would yield different gold rankings on edge candidates. The rubric lives in one place — `_rel_from_breakdown()` in `harness/gold_ranking.py` — so disagreement is visible.

The previous `/20` LLM-judge score is preserved in the JSON for historical comparison but no longer surfaced: Gemini judging Gemini exhibits documented self-preference bias (see Caveats § 2 below).
```

- [ ] **Step 3: Strengthen `README.md` Caveats § 2 (Other limits)**

In `README.md`, replace the first bullet of `### 2. Other limits` (the "Gemini judges Gemini" line) with:

```markdown
- **Gemini judges Gemini.** Self-preference bias is documented at *up to 50% rubric-flip* on objective rubrics (Panickssery et al. NeurIPS 2024; arXiv 2410.21819), traced to perplexity-based familiarity — a mechanical effect, not fixable by prompt tweaks. This is why the leaderboard now anchors on the deterministic NDCG@3 + Hit@1 scorer (see § Scoring) and the LLM-judge is reduced to `justification_quality` (a prose-readability signal that's harder to evaluate deterministically).
```

- [ ] **Step 4: Update `docs/plans/task-spec.md` § 7**

In `docs/plans/task-spec.md`, append a note at the end of § 7 (after line 176):

```markdown

---

**Update 2026-05-10** : the LLM-judge is now a **secondary** signal. The primary leaderboard ranking is the deterministic NDCG@3 + Hit@1 scorer over a graded-relevance rubric — see `docs/plans/2026-05-10-deterministic-scorer-design.md`. Of the 4 axes above, only `justification_quality` is surfaced in the leaderboard; `relevance` is replaced by the deterministic scorer, `score_coherence` is circular (agent generates both the score and the justification), and `format` is filtered upstream by validation.
```

- [ ] **Step 5: Verify by reading**

```bash
.venv/bin/pytest scripts/test_summarize.py scripts/test_deterministic_scorer.py -v
```

Re-read changes:

```bash
head -30 harness/judge.py
grep -A 20 "^## Scoring" README.md
tail -15 docs/plans/task-spec.md
```

- [ ] **Step 6: Commit**

```bash
git add harness/judge.py README.md docs/plans/task-spec.md
git commit -m "docs(scorer): demote judge to secondary signal in README + task-spec"
```

---

## Task 9: End-to-end backfill on the headline run

**Files:**
- Modify (in-place): `results/headline/*.json`
- Re-runs: `scripts/summarize.py`

- [ ] **Step 1: Run the deterministic scorer over every headline file**

```bash
for f in results/headline/*.json; do
  echo "Scoring $f..."
  .venv/bin/python harness/score_deterministic.py "$f"
done
```

Expected: each file gets in-place augmented. `results/.gold-cache/` populates after the first run; subsequent files reuse it.

- [ ] **Step 2: Verify augmentation on one file**

```bash
.venv/bin/python -c "
import json
d = json.load(open('results/headline/baseline-python.json'))
print('det_summary:', d.get('deterministic_summary'))
valid = next(r for r in d['runs'] if r.get('valid'))
print('sample det_score:')
import pprint; pprint.pprint(valid['deterministic_score'])
"
```

Expected: `deterministic_summary` shows `n_scored` matching the framework's valid count; sample run shows `ndcg_at_3`, `hit_at_1`, `agent_top_3`, `gold_top_3`.

- [ ] **Step 3: Re-aggregate and inspect the leaderboard**

```bash
.venv/bin/python scripts/summarize.py --input results/headline
cat results/summary.md
```

Expected: the `NDCG@3`, `Hit@1`, and `JustifQ /5` columns are now populated for all 8 frameworks. The `[^j]` footnote appears below the table.

- [ ] **Step 4: Sanity-check the rankings**

Compare the new ranking (sorted by NDCG@3 desc) against the old one (sorted by `/20` desc). Frameworks that ranked high on the old `/20` should be roughly the same as those high on NDCG@3 — large reorderings are a signal to investigate (likely a bug, not insight).

```bash
.venv/bin/python -c "
import json
data = json.load(open('dashboard/data/summary.json'))
fws = sorted(data['frameworks'], key=lambda s: -(s.get('mean_ndcg_at_3') or 0))
print(f'{\"framework\":<22} {\"NDCG@3\":>8} {\"Hit@1\":>8} {\"JustifQ\":>8} {\"valid\":>8}')
for s in fws:
    print(f'{s[\"framework\"]:<22} {s.get(\"mean_ndcg_at_3\") or 0:>8.3f} '
          f'{(s.get(\"hit_at_1_rate\") or 0)*100:>7.1f}% '
          f'{s.get(\"mean_justification_quality\") or 0:>8.2f} '
          f'{s[\"count_valid\"]:>4}/{s[\"count_total\"]}')
"
```

Read the table. If anything looks off, stop and debug before committing.

- [ ] **Step 5: Commit the backfilled headline results**

```bash
git add results/headline/*.json dashboard/data/summary.json results/summary.md README.md
git commit -m "data(scorer): backfill deterministic_score on headline run + refresh README"
```

Note: `README.md` may have been auto-refreshed by `summarize.py` via the `<!-- LEADERBOARD-START -->` injection. If so the leaderboard markdown will be different; include it in the commit.

---

## Self-Review

**Spec coverage (against `docs/plans/2026-05-10-deterministic-scorer-design.md`):**

| Spec requirement | Task |
|---|---|
| § 2 D1 NDCG@3 primary | Task 3 (impl), Task 7 (column) |
| § 2 D2 Hit@1 secondary | Task 4 (impl), Task 7 (column) |
| § 2 D3 graded relevance 0-3 | Task 1 |
| § 2 D5 reduce judge surface | Task 7 (`JustifQ /5`), Task 8 (docstring + README) |
| § 2 D6 backward compat, `/20` preserved | Task 7 (kept in `mean_judge_score`, not surfaced) |
| § 2 D7 Precision@3, Recall@3 in JSON | Task 4 (impl), Task 6 (aggregated to `mean_precision_at_3`/`mean_recall_at_3`) |
| § 2 D8 disk cache `.gold-cache/` | Task 2 |
| § 3 graded-relevance mapping | Task 1 |
| § 4 metrics: NDCG, Hit@1, P@3, R@3, invalid_id | Task 4 |
| § 5 file structure | Tasks 1-7 |
| § 5 tests: stability, idempotence, bounds, fallback | Tasks 2 (stability + cache), 3 (NDCG bounds + IDCG=0), 5 (idempotence), 4 (invalid_id) |
| § 6 data flow | Tasks 4-6 (end-to-end) |
| § 8 acceptance: end-to-end on real data | Task 9 |

**Placeholder scan:** no TBD/TODO; every step shows code or exact commands.

**Type consistency:** `compute_deterministic_score` returns `dict[str, Any]` with keys `ndcg_at_3` (float), `hit_at_1` (bool), `precision_at_3` (float), `recall_at_3` (float), `invalid_id_in_ranked` (bool), `agent_top_3` / `gold_top_3` (list of [str, int] pairs). Aggregators in Task 6 read those exact key names. ✓

**One known limitation flagged in spec § 3:** the rubric does not special-case job-010 (junior role where "over"-experienced should be a hard dealbreaker). Same as accepting that small data tweaks shouldn't flip metrics — it's a fairness choice, not an oversight.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-05-10-deterministic-scorer.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best when tasks are independent enough to context-isolate.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Best when later tasks need to read intermediate results from earlier tasks (true here: Task 9 depends on Tasks 1-8 being merged).

Given Task 9 explicitly backfills real headline data and the leaderboard rendering is hard to verify without re-running summarize, **I'd suggest inline execution** with checkpoints at the end of each task group: after Task 3 (pure math), after Task 5 (CLI works end-to-end on synthetic), after Task 7 (summarize integration), after Task 9 (real data backfilled). Which approach do you want?
