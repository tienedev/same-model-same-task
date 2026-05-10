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
