"""Unit tests for scripts/summarize.py.
Uses synthetic fixture data so tests don't depend on real results/.
"""
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_load_results_finds_all_json():
    from scripts.summarize import load_results
    runs = load_results(FIXTURES_DIR)
    assert len(runs) == 3
    frameworks = {r["framework"] for r in runs}
    assert frameworks == {"frameworkA", "frameworkB"}


def test_compute_stats_aggregates_per_framework():
    from scripts.summarize import compute_stats, load_results
    runs = load_results(FIXTURES_DIR)
    stats = compute_stats(runs)
    by_fw = {s["framework"]: s for s in stats}
    a = by_fw["frameworkA"]
    assert a["count_total"] == 2
    assert a["count_valid"] == 2
    assert a["success_rate"] == 1.0
    assert a["latency_p50"] == 15.0  # median of 10, 20
    assert a["latency_p95"] == 19.5  # interpolated between 10 and 20 at k=0.95*1=0.95
    assert a["latency_mean"] == 15.0
    assert a["mean_input_tokens"] == 1500
    assert a["mean_output_tokens"] == 300
    assert a["mean_tool_calls"] == 6.5  # mean of 5, 8
    assert a["estimated_cost_usd_per_run"] == pytest.approx(0.0066)  # (3000*2 + 600*12)/1e6 / 2
    b = by_fw["frameworkB"]
    assert b["count_total"] == 1
    assert b["count_valid"] == 0
    assert b["success_rate"] == 0.0
    assert b["latency_p50"] is None
    assert b["latency_p95"] is None
    assert b["latency_mean"] is None
    assert b["mean_input_tokens"] is None
    assert b["mean_output_tokens"] is None
    assert b["mean_tool_calls"] is None
    assert b["estimated_cost_usd_per_run"] is None
    assert b["hit_step_limit_rate"] is None


def test_compute_stats_handles_none_tool_calls():
    """Some adapters report tool_calls=None when their API doesn't expose it."""
    from scripts.summarize import compute_stats
    runs = [
        {"framework": "x", "valid": True, "elapsed_s": 1.0, "input_tokens": 1,
         "output_tokens": 1, "tool_calls": None}
    ]
    stats = compute_stats(runs)
    assert stats[0]["mean_tool_calls"] is None


def test_percentile_edge_cases():
    """Direct test of _percentile across empty, single-value, and interpolation cases."""
    from scripts.summarize import _percentile
    assert _percentile([], 0.5) == 0.0
    assert _percentile([42.0], 0.95) == 42.0
    assert _percentile([10.0, 20.0], 0.95) == 19.5  # interpolated
    # 21 values [1..21]: p95 is exact-index (k = 20*0.95 = 19, lo=hi=19, value=20)
    assert _percentile([float(i) for i in range(1, 22)], 0.95) == 20.0


def test_write_summary_json(tmp_path):
    import json

    from scripts.summarize import compute_stats, load_results, write_summary_json
    runs = load_results(FIXTURES_DIR)
    stats = compute_stats(runs)
    out = tmp_path / "summary.json"
    write_summary_json(stats, out, runs)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "frameworks" in data
    assert "metadata" in data
    assert "per_job_success" in data
    assert "latency_distribution" in data
    assert len(data["frameworks"]) == 2
    assert data["metadata"]["n_frameworks"] == 2
    assert "generated_at" in data["metadata"]
    assert "pricing_usd_per_m_tokens" in data["metadata"]


def test_write_summary_md_renders_dash_for_none(tmp_path):
    from scripts.summarize import compute_stats, load_results, write_summary_md
    stats = compute_stats(load_results(FIXTURES_DIR))
    out = tmp_path / "summary.md"
    write_summary_md(stats, out)
    text = out.read_text(encoding="utf-8")
    assert "| Framework |" in text  # header
    assert "frameworkA" in text
    assert "frameworkB" in text
    # frameworkB has count_valid=0 → all per-valid metrics are None → render as "—"
    # The frameworkB row must contain the dash placeholder, not "0.0" or "$0.0000"
    fwb_lines = [line for line in text.splitlines() if "frameworkB" in line]
    assert len(fwb_lines) == 1
    assert "—" in fwb_lines[0]
    assert "0.0000" not in fwb_lines[0]  # no misleading zero cost


def test_inject_leaderboard_replaces_between_sentinels(tmp_path):
    from scripts.summarize import inject_leaderboard
    p = tmp_path / "README.md"
    p.write_text(
        "# Hi\n\n<!-- LEADERBOARD-START -->\nold content\n<!-- LEADERBOARD-END -->\n\nbye",
        encoding="utf-8",
    )
    inject_leaderboard(p, "| F | V |\n|---|---|\n| x | 1 |")
    text = p.read_text(encoding="utf-8")
    assert "old content" not in text
    assert "| x | 1 |" in text
    # Surrounding content preserved
    assert "# Hi" in text
    assert "bye" in text
    # Sentinels still present
    assert "<!-- LEADERBOARD-START -->" in text
    assert "<!-- LEADERBOARD-END -->" in text


def test_inject_leaderboard_skips_if_file_missing(tmp_path):
    """No-op if README doesn't exist (during dashboard-only runs, etc.)."""
    from scripts.summarize import inject_leaderboard
    p = tmp_path / "README.md"
    inject_leaderboard(p, "anything")
    assert not p.exists()


def test_inject_leaderboard_skips_if_no_sentinels(tmp_path):
    """No-op (file unchanged) if sentinels are missing."""
    from scripts.summarize import inject_leaderboard
    p = tmp_path / "README.md"
    p.write_text("# README without sentinels\n\nNothing to update.\n", encoding="utf-8")
    original = p.read_text(encoding="utf-8")
    inject_leaderboard(p, "| F | V |\n|---|---|\n| x | 1 |")
    assert p.read_text(encoding="utf-8") == original


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
