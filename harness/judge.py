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

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import click
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from frameworks._shared.python import (  # noqa: E402
    GEMINI_OPENAI_BASE_URL,
    MODEL_NAME,
    parse_final_json,
)

JUDGE_MODEL = os.environ.get("JUDGE_MODEL", MODEL_NAME)
CACHE_DIR = ROOT / "results" / ".judge-cache"

JUDGE_PROMPT_TEMPLATE = """You are an expert recruiter evaluating an AI agent's candidate-ranking output.

# Job offer
{job_json}

# Candidate database (relevant entries only)
{candidates_json}

# Agent output
{output_json}

# Rubric
Score on 4 criteria, each 1-5 (1=poor, 5=excellent):

1. **Relevance of top 3**: Are these plausibly among the best matches? Consider skill overlap, experience fit, location, salary.
2. **Score coherence**: Does the numeric score reflect the elements mentioned in the justification?
3. **Useful justifications**: Could a recruiter act on these justifications? (Specific > vague.)
4. **Format & concision**: Format respected, no padding?

Output ONLY a JSON object:
{{
  "relevance": <1-5>,
  "score_coherence": <1-5>,
  "justification_quality": <1-5>,
  "format": <1-5>,
  "comment": "<one sentence on the strongest/weakest aspect>"
}}"""


def cache_key(framework: str, job_id: str, output: dict) -> str:
    canonical = json.dumps(
        {"framework": framework, "job_id": job_id, "output": output},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def load_cached(key: str) -> dict | None:
    p = CACHE_DIR / f"{key}.json"
    return json.loads(p.read_text()) if p.exists() else None


def save_cache(key: str, judgment: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(judgment, ensure_ascii=False))


def load_jobs() -> dict[str, dict]:
    return {j["id"]: j for j in json.loads((ROOT / "data" / "jobs.json").read_text())}


def load_candidates() -> dict[str, dict]:
    return {c["id"]: c for c in json.loads((ROOT / "data" / "candidates.json").read_text())}


def judge_run(client: OpenAI, run: dict, jobs: dict, candidates: dict) -> dict:
    output = run.get("parsed_output") or {}
    job = jobs.get(run["job_id"], {})
    referenced_ids = [item.get("candidate_id") for item in output.get("ranked_candidates", [])]
    referenced_candidates = [candidates[cid] for cid in referenced_ids if cid in candidates]

    key = cache_key(run.get("framework", "?"), run["job_id"], output)
    cached = load_cached(key)
    if cached is not None:
        return {**cached, "from_cache": True}

    prompt = JUDGE_PROMPT_TEMPLATE.format(
        job_json=json.dumps(job, indent=2, ensure_ascii=False),
        candidates_json=json.dumps(referenced_candidates, indent=2, ensure_ascii=False),
        output_json=json.dumps(output, indent=2, ensure_ascii=False),
    )

    # max_tokens=4096 because Gemini 2.5 Flash on the OpenAI-compat endpoint
    # silently consumes ~tokens of internal reasoning against this budget,
    # even when not configured as a thinking model. With 512 the actual JSON
    # output gets truncated to ~20 tokens (finish_reason=length); 4096 leaves
    # ample headroom and only costs more if the model actually needs it.
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
        temperature=0,
    )

    text = response.choices[0].message.content or ""
    parsed, parse_err = parse_final_json(text)
    if parsed is None:
        judgment = {"error": f"judge produced non-JSON: {parse_err}", "raw": text[:500]}
    else:
        judgment = parsed

    judgment["judge_model"] = JUDGE_MODEL
    if response.usage:
        judgment["judge_input_tokens"] = response.usage.prompt_tokens
        judgment["judge_output_tokens"] = response.usage.completion_tokens

    save_cache(key, judgment)
    return judgment


@click.command()
@click.argument("results_file", type=click.Path(exists=True))
@click.option("--out", default=None, type=click.Path(), help="Output file (default: in-place)")
def main(results_file: str, out: str | None) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        click.echo("error: GEMINI_API_KEY not set", err=True)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=GEMINI_OPENAI_BASE_URL)
    jobs = load_jobs()
    candidates = load_candidates()
    summary = json.loads(Path(results_file).read_text())

    judged = 0
    skipped = 0
    for run in summary.get("runs", []):
        if not run.get("valid"):
            run["judgment"] = {"skipped": True, "reason": run.get("validation_error", "invalid")}
            skipped += 1
            continue
        click.echo(f"  judging {run.get('framework')} {run.get('job_id')} trial {run.get('trial')}…", err=True)
        run["judgment"] = judge_run(client, run, jobs, candidates)
        judged += 1

    summary["judge_summary"] = {"judged": judged, "skipped": skipped, "judge_model": JUDGE_MODEL}

    out_path = Path(out) if out else Path(results_file)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    click.echo(f"Wrote {out_path} (judged={judged} skipped={skipped})", err=True)


if __name__ == "__main__":
    main()
