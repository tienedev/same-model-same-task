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
