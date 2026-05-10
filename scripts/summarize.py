"""Aggregates results/*.json into stats consumable by README + dashboard."""
from __future__ import annotations

import json
import re
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

# Gemini 2.5 Flash pricing per 1M tokens (USD).
# https://ai.google.dev/gemini-api/docs/pricing
GEMINI_PRICING = {"in_per_m": 2.0, "out_per_m": 12.0}


def load_results(input_dir: Path) -> list[dict[str, Any]]:
    """Returns flat list of all runs across all framework files in input_dir.

    Skips malformed JSON files silently so a single bad file doesn't break
    the whole aggregation.
    """
    runs: list[dict[str, Any]] = []
    for f in sorted(input_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        runs.extend(data.get("runs", []))
    return runs


def _percentile(values: list[float], p: float) -> float:
    """Linear-interpolated percentile. p in [0, 1]."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def compute_stats(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate runs into per-framework stats.

    Returns a list of stat dicts (one per framework), sorted by framework name.

    Note on `mean_tool_calls`: if any valid run reports tool_calls=None
    (framework doesn't expose the metric), the mean is reported as None
    to avoid silently misleading downstream consumers.
    """
    by_fw: dict[str, list[dict[str, Any]]] = {}
    for r in runs:
        by_fw.setdefault(r["framework"], []).append(r)

    out: list[dict[str, Any]] = []
    for fw, fw_runs in by_fw.items():
        valid = [r for r in fw_runs if r.get("valid")]

        if valid:
            latencies = [r["elapsed_s"] for r in valid if "elapsed_s" in r]
            in_tok = [r.get("input_tokens", 0) for r in valid]
            out_tok = [r.get("output_tokens", 0) for r in valid]

            tc_values = [r["tool_calls"] for r in valid if r.get("tool_calls") is not None]
            any_none = any(r.get("tool_calls") is None for r in valid)
            if any_none:
                mean_tool_calls: float | None = None
            else:
                mean_tool_calls = statistics.mean(tc_values) if tc_values else 0.0

            sum_in, sum_out = sum(in_tok), sum(out_tok)
            cost_total = (
                sum_in * GEMINI_PRICING["in_per_m"]
                + sum_out * GEMINI_PRICING["out_per_m"]
            ) / 1_000_000

            # Judge scores: only counted for runs where the judge produced a
            # parseable rubric (relevance + score_coherence + justification_quality
            # + format, each 1-5, sum 4-20). Errors and `skipped` runs are
            # ignored — leaves judge_n=0 cleanly when the judge hasn't run.
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

            per_valid_metrics: dict[str, Any] = {
                "latency_p50": _percentile(latencies, 0.50),
                "latency_p95": _percentile(latencies, 0.95),
                "latency_mean": statistics.mean(latencies) if latencies else 0.0,
                "latency_max": max(latencies) if latencies else 0.0,
                "mean_input_tokens": int(statistics.mean(in_tok)) if in_tok else 0,
                "mean_output_tokens": int(statistics.mean(out_tok)) if out_tok else 0,
                "mean_tool_calls": mean_tool_calls,
                "estimated_cost_usd_per_run": cost_total / len(valid),
                "hit_step_limit_rate": (
                    sum(1 for r in valid if r.get("hit_step_limit")) / len(valid)
                ),
                "mean_judge_score": mean_judge_score,
                "judge_n": judge_n,
                "mean_ndcg_at_3": mean_ndcg_at_3,
                "hit_at_1_rate": hit_at_1_rate,
                "mean_precision_at_3": mean_precision_at_3,
                "mean_recall_at_3": mean_recall_at_3,
                "n_scored": n_scored,
            }
        else:
            per_valid_metrics = {
                "latency_p50": None,
                "latency_p95": None,
                "latency_mean": None,
                "latency_max": None,
                "mean_input_tokens": None,
                "mean_output_tokens": None,
                "mean_tool_calls": None,
                "estimated_cost_usd_per_run": None,
                "hit_step_limit_rate": None,
                "mean_judge_score": None,
                "judge_n": 0,
                "mean_ndcg_at_3": None,
                "hit_at_1_rate": None,
                "mean_precision_at_3": None,
                "mean_recall_at_3": None,
                "n_scored": 0,
            }

        out.append({
            "framework": fw,
            "count_total": len(fw_runs),
            "count_valid": len(valid),
            "success_rate": len(valid) / len(fw_runs) if fw_runs else 0.0,
            **per_valid_metrics,
        })

    return sorted(out, key=lambda s: s["framework"])


def _fmt_or_dash(value: float | int | None, fmt: str = ".1f") -> str:
    """Format a value or render '—' if None."""
    if value is None:
        return "—"
    return format(value, fmt)


def compute_per_job_success(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For each (framework, job_id) pair, return success rate.

    Used by the /findings page heatmap: which jobs break which frameworks?
    """
    by_pair: dict[tuple[str, str], list[bool]] = {}
    for r in runs:
        key = (r["framework"], r["job_id"])
        by_pair.setdefault(key, []).append(bool(r.get("valid")))

    return [
        {
            "framework": fw,
            "job_id": job,
            "success_rate": sum(valids) / len(valids) if valids else 0.0,
            "n_trials": len(valids),
        }
        for (fw, job), valids in sorted(by_pair.items())
    ]


def compute_latency_distribution(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-framework latency distribution (min, p50, p95, max + raw points).

    Used by the /findings page outlier analysis.
    """
    by_fw: dict[str, list[float]] = {}
    for r in runs:
        if r.get("valid") and "elapsed_s" in r:
            by_fw.setdefault(r["framework"], []).append(r["elapsed_s"])

    out = []
    for fw, lats in sorted(by_fw.items()):
        sorted_lats = sorted(lats)
        out.append({
            "framework": fw,
            "n": len(lats),
            "min": min(lats),
            "p50": _percentile(sorted_lats, 0.50),
            "p95": _percentile(sorted_lats, 0.95),
            "max": max(lats),
            # Raw values for the strip plot — sorted ascending so stable rendering
            "values": sorted_lats,
        })
    return out


def write_summary_json(stats: list[dict[str, Any]], out: Path, runs: list[dict[str, Any]]) -> None:
    """Write the structured summary as JSON. Creates parent dirs if needed."""
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "n_frameworks": len(stats),
            "pricing_usd_per_m_tokens": GEMINI_PRICING,
        },
        "frameworks": stats,
        "per_job_success": compute_per_job_success(runs),
        "latency_distribution": compute_latency_distribution(runs),
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_summary_md(stats: list[dict[str, Any]], out: Path) -> None:
    """Write a human-readable Markdown table to `out`. Creates parent dirs."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_build_leaderboard_md(stats), encoding="utf-8")


def _build_leaderboard_md(stats: list[dict[str, Any]]) -> str:
    """Build the Markdown leaderboard table. Reused by README injection (Task 5)."""
    rows = [
        "| Framework | Valid | Judge /20 | p50 (s) | p95 (s) | Mean tokens (in/out) | Mean tools | Cost / run (USD) |",
        "|---|---|---|---|---|---|---|---|",
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
        judge_cell = _fmt_or_dash(s.get("mean_judge_score"), ".2f")
        rows.append(
            f"| {s['framework']} | {s['count_valid']}/{s['count_total']} "
            f"| {judge_cell} "
            f"| {_fmt_or_dash(s['latency_p50'])} | {_fmt_or_dash(s['latency_p95'])} "
            f"| {tokens_cell} "
            f"| {_fmt_or_dash(s['mean_tool_calls'])} "
            f"| {cost_cell} |"
        )
    return "\n".join(rows) + "\n"


LEADERBOARD_BLOCK_RE = re.compile(
    r"<!-- LEADERBOARD-START -->.*?<!-- LEADERBOARD-END -->",
    re.DOTALL,
)


def inject_leaderboard(readme_path: Path, table_md: str) -> None:
    """Replace the content between LEADERBOARD-START / LEADERBOARD-END
    sentinels in `readme_path` with `table_md`.

    No-op if `readme_path` doesn't exist or if the sentinels are missing.
    Preserves all surrounding content (intro, other sections, etc.).
    """
    if not readme_path.exists():
        return
    text = readme_path.read_text(encoding="utf-8")
    block = f"<!-- LEADERBOARD-START -->\n{table_md}\n<!-- LEADERBOARD-END -->"
    new_text, n_subs = LEADERBOARD_BLOCK_RE.subn(block, text)
    if n_subs > 0 and new_text != text:
        readme_path.write_text(new_text, encoding="utf-8")


@click.command()
@click.option(
    "--input",
    "input_dir",
    default="results",
    type=click.Path(exists=True, file_okay=False),
    help="Directory containing per-framework *.json result files.",
)
@click.option(
    "--out-json",
    default="dashboard/data/summary.json",
    type=click.Path(),
    help="Where to write the structured summary.",
)
@click.option(
    "--out-md",
    default="results/summary.md",
    type=click.Path(),
    help="Where to write the human-readable Markdown summary.",
)
def main(input_dir: str, out_json: str, out_md: str) -> None:
    """Aggregate results/*.json into summary.json + summary.md, refresh README."""
    runs = load_results(Path(input_dir))
    stats = compute_stats(runs)
    write_summary_json(stats, Path(out_json), runs)
    write_summary_md(stats, Path(out_md))
    # Refresh README leaderboard if README exists with sentinel block.
    inject_leaderboard(Path("README.md"), _build_leaderboard_md(stats))
    click.echo(
        f"Wrote {out_json} and {out_md} ({len(stats)} frameworks, {len(runs)} runs)",
        err=True,
    )


if __name__ == "__main__":
    main()
