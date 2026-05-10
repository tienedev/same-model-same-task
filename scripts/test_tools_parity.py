"""Test parity between Python and TypeScript tool implementations.

Runs the same fixture inputs through both implementations and asserts
identical outputs. Critical for benchmark fairness.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.python import (  # noqa: E402
    get_candidate_profile,
    list_jobs,
    score_match,
    search_candidates,
)

# 12 fixture cases covering edge cases
FIXTURES: list[tuple[str, dict]] = [
    ("search_candidates", {"query": "Python Django backend"}),
    ("search_candidates", {"query": "React TypeScript", "filters": {"min_years_experience": 5}}),
    (
        "search_candidates",
        {"query": "ML PyTorch", "filters": {"required_skills": ["Python", "PyTorch"]}},
    ),
    ("search_candidates", {"query": "iOS", "filters": {"location": "Paris, France"}}),
    ("search_candidates", {"query": "remote senior", "filters": {"location": "remote"}}),
    (
        "search_candidates",
        {"query": "designer", "filters": {"max_salary_eur": 60000}},
    ),
    ("search_candidates", {"query": ""}),  # empty query — should return up to 10
    ("get_candidate_profile", {"candidate_id": "cand-001"}),
    ("get_candidate_profile", {"candidate_id": "cand-999"}),  # not found
    ("score_match", {"candidate_id": "cand-001", "job_id": "job-001"}),
    ("score_match", {"candidate_id": "cand-003", "job_id": "job-001"}),  # salary above
    ("list_jobs", {}),
]


def run_python(fixture_name: str, args: dict) -> object:
    if fixture_name == "search_candidates":
        return search_candidates(**args)
    if fixture_name == "get_candidate_profile":
        return get_candidate_profile(**args)
    if fixture_name == "score_match":
        return score_match(**args)
    if fixture_name == "list_jobs":
        return list_jobs()
    raise ValueError(f"unknown fixture: {fixture_name}")


def run_typescript() -> list[object]:
    """Run the TS test runner and return results as parsed JSON."""
    result = subprocess.run(
        ["bun", "run", str(ROOT / "tools" / "typescript" / "src" / "test_runner.ts")],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        print(f"TS runner failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def main() -> int:
    py_results = [run_python(name, args) for name, args in FIXTURES]
    ts_results = run_typescript()

    assert len(py_results) == len(ts_results), (
        f"length mismatch: py={len(py_results)} ts={len(ts_results)}"
    )

    failures = []
    for i, ((name, args), py, ts) in enumerate(zip(FIXTURES, py_results, ts_results)):
        # Normalize through JSON to handle dict ordering / None vs null
        py_norm = json.loads(json.dumps(py))
        ts_norm = json.loads(json.dumps(ts))
        if py_norm != ts_norm:
            failures.append(
                f"  [{i}] {name}({args})\n    py: {py_norm}\n    ts: {ts_norm}"
            )

    if failures:
        print(f"❌ {len(failures)} parity failures:")
        for f in failures:
            print(f)
        return 1

    print(f"✓ All {len(FIXTURES)} fixtures match between Python and TypeScript.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
