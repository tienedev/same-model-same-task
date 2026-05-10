"""Bench harness: runs adapters across job_ids, captures metrics, persists results.

Usage examples:
    # Run baseline-python on a single job, 3 trials
    GEMINI_API_KEY=... python harness/run_bench.py --framework baseline-python --jobs job-001 --trials 3

    # Run baseline-typescript via subprocess
    GEMINI_API_KEY=... python harness/run_bench.py --framework baseline-typescript --jobs job-001 --trials 1

    # Run all 10 jobs × 3 trials for one framework
    GEMINI_API_KEY=... python harness/run_bench.py --framework baseline-python --all-jobs --trials 3
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

import click

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# Adapter registry: framework -> ("python" | "typescript", path-to-run)
ADAPTERS: dict[str, tuple[str, Path]] = {
    "baseline-python": ("python", ROOT / "frameworks" / "baseline" / "python" / "run.py"),
    "baseline-typescript": ("typescript", ROOT / "frameworks" / "baseline" / "typescript" / "run.ts"),
    "langgraph": ("python", ROOT / "frameworks" / "langgraph" / "python" / "run.py"),
    "crewai": ("python", ROOT / "frameworks" / "crewai" / "python" / "run.py"),
    "pydantic-ai": ("python", ROOT / "frameworks" / "pydantic_ai" / "python" / "run.py"),
    "google-adk": ("python", ROOT / "frameworks" / "google_adk" / "python" / "run.py"),
    "mastra": ("typescript", ROOT / "frameworks" / "mastra" / "typescript" / "run.ts"),
    "vercel-ai-sdk": ("typescript", ROOT / "frameworks" / "vercel_ai_sdk" / "typescript" / "run.ts"),
}

ALL_JOB_IDS = [f"job-{i:03d}" for i in range(1, 11)]


def run_python_adapter(framework: str, job_id: str) -> dict[str, Any]:
    """Run a Python adapter in-process via importlib."""
    _, path = ADAPTERS[framework]
    # Convert path to module : frameworks/baseline/python/run.py -> frameworks.baseline.python.run
    module_name = ".".join(path.relative_to(ROOT).with_suffix("").parts)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run(job_id)


def run_typescript_adapter(framework: str, job_id: str) -> dict[str, Any]:
    """Run a TypeScript adapter via bun subprocess."""
    _, path = ADAPTERS[framework]
    result = subprocess.run(
        ["bun", "run", str(path), job_id],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ},
        check=False,
    )
    if result.returncode != 0:
        return {
            "framework": framework,
            "job_id": job_id,
            "error": f"subprocess exited {result.returncode}",
            "stderr": result.stderr[:2000],
        }
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        return {
            "framework": framework,
            "job_id": job_id,
            "error": f"could not parse adapter stdout as JSON: {e}",
            "stdout_head": result.stdout[:1000],
        }


def run_one(framework: str, job_id: str) -> dict[str, Any]:
    """Dispatch to the correct runner for the framework."""
    lang, _ = ADAPTERS[framework]
    if lang == "python":
        return run_python_adapter(framework, job_id)
    if lang == "typescript":
        return run_typescript_adapter(framework, job_id)
    raise ValueError(f"unknown adapter language: {lang}")


@cache
def _valid_candidate_ids() -> frozenset[str]:
    candidates = json.loads((ROOT / "data" / "candidates.json").read_text())
    return frozenset(c["id"] for c in candidates)


def validate_output(output: Any) -> tuple[bool, str | None]:
    """Programmatic validation per task-spec § 6. Returns (valid, error_msg)."""
    if not isinstance(output, dict):
        return False, "output is not a dict"
    if "ranked_candidates" not in output:
        return False, "missing key: ranked_candidates"
    rc = output["ranked_candidates"]
    if not isinstance(rc, list) or len(rc) != 3:
        n = len(rc) if hasattr(rc, "__len__") else "?"
        return False, f"ranked_candidates must be list of 3, got {type(rc).__name__} len={n}"
    valid_ids = _valid_candidate_ids()
    expected_ranks = [1, 2, 3]
    seen_ids: set[str] = set()
    for i, item in enumerate(rc):
        if not isinstance(item, dict):
            return False, f"ranked_candidates[{i}] not a dict"
        for key in ("rank", "candidate_id", "score", "justification"):
            if key not in item:
                return False, f"ranked_candidates[{i}] missing {key}"
        if item["rank"] != expected_ranks[i]:
            return False, f"ranked_candidates[{i}].rank != {expected_ranks[i]}"
        if not isinstance(item["score"], int) or not (0 <= item["score"] <= 100):
            return False, f"ranked_candidates[{i}].score must be int 0-100"
        cid = item["candidate_id"]
        if cid not in valid_ids:
            return False, f"ranked_candidates[{i}].candidate_id={cid!r} is not in the dataset (hallucinated)"
        if cid in seen_ids:
            return False, f"duplicate candidate_id: {cid}"
        seen_ids.add(cid)
        words = len(item["justification"].split())
        if words == 0:
            return False, f"ranked_candidates[{i}].justification is empty"
        if words > 60:
            return False, f"ranked_candidates[{i}].justification is too long ({words} words)"
    return True, None


@click.command()
@click.option("--framework", required=True, type=click.Choice(list(ADAPTERS.keys())))
@click.option("--jobs", multiple=True, help="Job IDs to run (e.g. --jobs job-001 --jobs job-002)")
@click.option("--all-jobs", is_flag=True, help="Run all 10 jobs")
@click.option("--trials", default=1, type=int, help="Trials per job (default 1)")
@click.option("--out", default=None, type=click.Path(), help="Output JSON file (default: stdout)")
def main(framework: str, jobs: tuple[str, ...], all_jobs: bool, trials: int, out: str | None) -> None:
    job_ids = list(jobs) if not all_jobs else ALL_JOB_IDS
    if not job_ids:
        click.echo("error: provide --jobs or --all-jobs", err=True)
        sys.exit(1)

    runs: list[dict[str, Any]] = []
    started_at = datetime.now(UTC).isoformat()
    t_total = time.perf_counter()

    for job_id in job_ids:
        for trial in range(1, trials + 1):
            click.echo(f"  {framework} {job_id} trial {trial}/{trials}…", err=True)
            try:
                result = run_one(framework, job_id)
            except Exception as e:  # noqa: BLE001
                result = {
                    "framework": framework,
                    "job_id": job_id,
                    "error": f"{type(e).__name__}: {e}",
                }

            result["trial"] = trial
            # Separate "parse failed" from "parsed but schema-invalid". A parse
            # failure already populates `parse_error`; only run the schema
            # validator if we have actual parsed JSON to inspect.
            if result.get("parsed_output") is None:
                result["valid"] = False
            else:
                valid, validation_error = validate_output(result["parsed_output"])
                result["valid"] = valid
                if validation_error:
                    result["validation_error"] = validation_error

            runs.append(result)

    summary = {
        "framework": framework,
        "started_at": started_at,
        "total_elapsed_s": round(time.perf_counter() - t_total, 3),
        "runs": runs,
    }

    output_text = json.dumps(summary, indent=2, ensure_ascii=False)
    if out:
        Path(out).write_text(output_text)
        click.echo(f"Wrote {out}", err=True)
    else:
        click.echo(output_text)


if __name__ == "__main__":
    main()
