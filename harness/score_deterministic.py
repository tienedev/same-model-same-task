"""Augment a results JSON with a deterministic_score block per valid run.

Mirrors harness/judge.py in shape but makes zero API calls — pure functions
over score_match() output. Idempotent: produces byte-identical output on re-runs (pure functions, no in-place mutation).

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
