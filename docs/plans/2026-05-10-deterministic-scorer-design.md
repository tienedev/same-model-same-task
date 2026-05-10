# Deterministic Scorer — Design

**Date** : 2026-05-10
**Status** : validated, ready for implementation plan
**Companion to** : `docs/plans/task-spec.md` § 7 (LLM-judge becomes secondary signal)

---

## 1. Why

`harness/judge.py` uses Gemini 2.5 Flash to judge Gemini 2.5 Flash outputs. The literature documents **self-preference bias** at 15-50% over-rating depending on rubric type, traced to perplexity-based familiarity (Panickssery et al. NeurIPS 2024 ; arXiv 2410.21819). With single-decimal `/20` deltas driving the leaderboard, self-bias is the noise floor.

The task — pick top-3 candidates from 50 against a deterministic `score_match` tool — is a textbook **information retrieval / graded-relevance ranking** problem. The IR community has converged on a small set of metrics (NDCG, Hit@1, Precision@k, Recall@k) for exactly this shape. This design imports that machinery rather than inventing custom scores.

After this change the judge keeps a single role — qualitative prose evaluation — and the leaderboard is anchored by deterministic, computable, position-aware metrics.

## 2. Decisions arbitrated

| # | Decision | Choice |
|---|---|---|
| D1 | Primary headline metric | **NDCG@3** (mean across all valid runs) |
| D2 | Secondary deterministic metric | **Hit@1** rate (= agent's #1 has gold relevance ≥ 2) |
| D3 | Aggregation model | **Graded relevance 0-3 per (job, candidate)** — NOT a weighted scalar |
| D4 | Tie handling within a gold tier | None needed — NDCG@3 treats equal-relevance items as interchangeable |
| D5 | Judge re-scope | Drop `relevance`, `score_coherence`, `format`. Keep `justification_quality` /5. |
| D6 | Backward compat | `judge.py` still runnable. Old `/20` summed score kept in JSON as `mean_judge_score`, shown in summaries with footnote citing self-bias literature. |
| D7 | Debug metrics in JSON | Precision@3 and Recall@3 stored per run for cross-check; not surfaced in headline. |
| D8 | Cache location | `results/.gold-cache/` (gitignored) — keyed by `(job_id, candidate_id, score_match_output_hash)`. |

## 3. Graded relevance mapping (D3)

Per (job, candidate), `score_match()` returns 4 fields. The gold relevance score `rel ∈ {0, 1, 2, 3}` is derived as:

```
Inputs from score_match():
  skill_pct      ∈ [0, 100]
  experience_fit ∈ {match, over, under}
  location_fit   ∈ {match, remote_compatible, mismatch}
  salary_fit     ∈ {in_range, below_min, above_max}

Helpers:
  hard_dealbreaker  = (experience_fit == "under")
                       OR (location_fit == "mismatch")
                       OR (salary_fit == "above_max")
                       — candidate is unwilling/unable to take the role
  soft_concern      = (experience_fit == "over")
                       OR (location_fit == "remote_compatible")
                       OR (salary_fit == "below_min")
                       — workable but flagged
```

Define `hard_count = int(experience_fit=="under") + int(location_fit=="mismatch") + int(salary_fit=="above_max")` and `soft_count = int(experience_fit=="over") + int(location_fit=="remote_compatible") + int(salary_fit=="below_min")`.

Tiers are **mutually exclusive** and evaluated in order:

| `rel` | Definition (first match wins) | Verbal label |
|---|---|---|
| **0** | `hard_count ≥ 1` (any hard dealbreaker disqualifies) | Irrelevant |
| **0** | `skill_pct < 34` | Irrelevant |
| **3** | `skill_pct ≥ 67` AND `soft_count == 0` | Highly relevant |
| **2** | `skill_pct ≥ 67` AND `soft_count == 1` | Relevant |
| **1** | `skill_pct ≥ 67` AND `soft_count ≥ 2` | Marginal (strong skills, multiple flags) |
| **1** | `34 ≤ skill_pct < 67` (regardless of soft_count, since hard_count == 0 here) | Marginal (mid-skills, no dealbreakers) |

**Rationale for the thresholds.** With 3 required skills in most jobs the practical `skill_pct` quantization is `{0, 33, 67, 100}`; the thresholds 67 and 34 land on natural quantum boundaries so small data tweaks don't flip a candidate between tiers. Hard dealbreakers always force `rel=0`: the candidate is genuinely unwilling or unable to take the role (under-experienced for the minimum, location mismatch with no remote option, expects more than the salary ceiling). Soft concerns degrade ranking but don't disqualify.

**Known asymmetry (and why we accept it).** `score_match()` returns `experience_fit == "over"` regardless of job seniority. For job-010 (junior backend, where over-qualified candidates *should* be rejected per task-spec § 3), this means a 12-year senior keeps `rel ≥ 1` instead of `rel = 0`. We could special-case job-010 but we don't, because: (a) it would couple `gold_ranking.py` to specific job IDs; (b) the agent receives the same `score_match` output and faces the same ambiguity, so the metric is **fair to both sides** of the comparison; (c) we'd rather flag this in the README "Scoring" caveat than hide it in code.

**Caveat we own publicly.** This mapping is *opinionated*. A different rubric (skills-first lex, or strict "skill_pct ≥ 80") would yield different gold rankings on edge candidates. Two safeguards: (a) the mapping lives in `gold_relevance()` in `harness/gold_ranking.py` with the docstring above; (b) the README "Scoring" section quotes the table verbatim so readers can disagree explicitly. We do **not** present this as ground truth — we present it as *a defensible reference rubric*.

## 4. Metrics

For each **valid** run with a non-null `parsed_output.ranked_candidates`:

- **NDCG@3** — standard formulation with gain = `rel` and log₂ discount:
  ```
  DCG@3   = Σ_{i=1..3}  rel_i / log₂(i + 1)
  IDCG@3  = same, computed on the gold top-3 (highest-rel candidates, ties broken by candidate_id asc)
  NDCG@3  = DCG@3 / IDCG@3        if IDCG@3 > 0
          = 1.0                    if IDCG@3 == 0   (no relevant candidate exists; agent can't fail)
  ```
- **Hit@1** — `True` if the agent's rank-1 candidate has `rel ≥ 2` (relevant or better). Stricter than "matches gold #1" because it gives credit for any "Relevant" pick.
- **Precision@3** — `|agent_set ∩ {cand with rel ≥ 2}| / 3`. Debug only.
- **Recall@3** — `|agent_set ∩ gold_top_3| / 3`. Debug only.
- **invalid_id_in_ranked** — `True` if any candidate_id in `ranked_candidates` doesn't exist in `candidates.json`. Should always be `False` for `valid=True` runs (validation already filters), but cross-checked here.

Per-framework summary fields:
- `mean_ndcg_at_3` (headline)
- `hit_at_1_rate`
- `mean_precision_at_3`, `mean_recall_at_3` (debug, not surfaced in leaderboard)
- `n_scored` (count of runs with deterministic scores; equals `count_valid` minus any cross-check failures)

## 5. Architecture

### New files

**`harness/gold_ranking.py`**

Pure functions, no CLI. Importable from `harness/score_deterministic.py` and tests.

```python
# Public API
def gold_relevance(job_id: str, candidate_id: str) -> int:
    """Returns 0-3 graded relevance. Caches on disk under results/.gold-cache/."""

def gold_top_k(job_id: str, k: int = 3) -> list[tuple[str, int]]:
    """Returns [(candidate_id, rel), ...] of length k, sorted by (rel desc, candidate_id asc).
    Pads with rel=0 entries if fewer than k candidates exist (impossible here, 50 > 3)."""

def compute_deterministic_score(parsed_output: dict, job_id: str) -> dict:
    """Returns the dict written under run['deterministic_score'] — see § 6 schema."""
```

The aggregation rule (§ 3) lives in `gold_relevance()` with the mapping table as its docstring. **Single source of truth.**

**`harness/score_deterministic.py`**

CLI mirroring `harness/judge.py` shape:

```bash
python harness/score_deterministic.py results/headline/baseline-python.json
# → in-place augment; each valid run gets run["deterministic_score"] = {...}
# → adds summary["deterministic_summary"] = {n_scored, n_skipped}
```

No API calls. Idempotent. Re-runnable. `--out` flag to redirect output.

### Updated files

**`scripts/summarize.py`**

- Add per-framework fields: `mean_ndcg_at_3`, `hit_at_1_rate`, `mean_precision_at_3`, `mean_recall_at_3`, `n_scored`.
- Aggregate from `run["deterministic_score"]` exactly as judge fields are aggregated from `run["judgment"]`.
- Update `_build_leaderboard_md()` columns:
  - New headline columns: **NDCG@3** (3 decimals), **Hit@1** (% with 1 decimal).
  - Demote `Judge /20` → side column labelled `JustifQ /5` (mean of new `justification_quality` only) with a footnote linking to the README caveat.
  - Keep `Valid`, `p50`, `p95`, tokens, tools, cost.
- Preserve `mean_judge_score` in `summary.json` for any consumer that depended on it; do not display.

**`harness/judge.py`**

- **No prompt change. No cache invalidation.** The current 4-axis output (relevance, score_coherence, justification_quality, format) already includes `justification_quality` as one of its fields — we just consume that field downstream and ignore the others in the leaderboard.
- Only edit: update the leading docstring to (a) point at this design doc, (b) cite the stronger self-bias finding ("up to 50% rubric-flip on objective rubrics — Panickssery et al. NeurIPS 2024 ; arXiv 2410.21819"), (c) note that `relevance` and `score_coherence` are kept in the JSON for historical comparison but are no longer surfaced because they're subsumed by the deterministic scorer (relevance) or circular (score_coherence — agent invents the score AND the justification in the same call, so they always cohere).
- The 240 existing judged runs stay valid. No re-judging cost.

**`README.md`**

- Refresh leaderboard (auto-injected).
- Add **Scoring** section (<100 words) explaining: NDCG@3 over a graded-relevance gold (rule quoted verbatim from § 3), with Hit@1 as secondary. Mention judge is now justification-only with documented self-bias caveat.
- Update Caveat § 2 to cite the stronger finding.

**`docs/plans/task-spec.md`**

- § 7 → note: "judge LLM is now secondary, rule-based deterministic scorer is primary. See `docs/plans/2026-05-10-deterministic-scorer-design.md`."

### Tests

**`scripts/test_deterministic_scorer.py`** (new), patterned on `scripts/test_summarize.py`.

Must cover:
1. **Stability** — `gold_top_k("job-001")` returns identical output on repeated calls (no hidden non-determinism).
2. **Boundary cases** in `gold_relevance` — one (job, cand) hand-computed per tier (0/1/2/3) verified against the mapping.
3. **NDCG@3 sanity** — synthetic case where the agent picks gold top-3 in correct order → NDCG@3 == 1.0; agent picks the 3 worst candidates → NDCG@3 == 0.0; agent swaps rank-1 and rank-3 → NDCG@3 strictly between 0 and 1.
4. **IDCG@3 == 0 fallback** — synthetic job with no candidate having rel ≥ 1 → NDCG@3 returns 1.0 (agent can't fail), and a test asserts this.
5. **invalid_id cross-check** — run with a fabricated candidate_id has `invalid_id_in_ranked == True` (should never trigger for `valid=True` runs in practice; this guards against a regression in validation).
6. **Idempotence** — running `score_deterministic.py` twice on the same file is a no-op.
7. **Summarize integration** — synthetic results fixture with `deterministic_score` blocks produces correct `mean_ndcg_at_3` etc.

## 6. Data flow

```
data/jobs.json
data/candidates.json
            ↓
tools/python/tools.py: score_match(cand_id, job_id)  ← deterministic, pre-existing
            ↓
harness/gold_ranking.py:
  gold_relevance(job_id, cand_id) → int 0-3        ← caches to results/.gold-cache/
  gold_top_k(job_id, k=3)         → [(id, rel)]
            ↓
harness/score_deterministic.py (CLI):
  for run in results.runs:
    if run.valid:
      run.deterministic_score = {
        ndcg_at_3: float,
        hit_at_1: bool,
        precision_at_3: float,
        recall_at_3: float,
        invalid_id_in_ranked: bool,
        gold_top_3: [(cand_id, rel)],     # snapshot for transparency
        agent_top_3: [(cand_id, rel)]
      }
            ↓
scripts/summarize.py:
  aggregates run.deterministic_score → per-framework stats
  emits dashboard/data/summary.json (frameworks[].mean_ndcg_at_3 etc.)
  rewrites README leaderboard block
```

## 7. Cache schema (D8)

`results/.gold-cache/<sha256-hex[:16]>.json` — content keyed by canonical JSON of `{"job_id", "candidate_id", "score_match_output"}`. Value:

```json
{"rel": 3, "breakdown": {"skill_match_pct": 100, "experience_fit": "match", "location_fit": "match", "salary_fit": "in_range"}, "computed_at": "2026-05-10T..."}
```

`results/.gold-cache/` is added to `.gitignore`. Pure function of inputs → safe to delete and rebuild any time.

## 8. Out of scope (non-goals)

- We do **not** change the agent's output schema (`ranked_candidates` stays as task-spec § 5).
- We do **not** change `score_match()` semantics or any tool.
- We do **not** add a pairwise / panel-of-judges LLM eval. Mentioned in literature; valuable; deferred.
- We do **not** add RBO or Kendall τ. NDCG@3 + Hit@1 covers the headline; the article can cite RBO as "what we'd add if we extended to top-10".
- We do **not** modify `harness/run_bench.py`. Scoring is strictly post-hoc.

## 9. Acceptance

- `python harness/score_deterministic.py results/headline/baseline-python.json` augments each valid run with a `deterministic_score` block matching § 6.
- `python scripts/summarize.py --input results/headline` produces a leaderboard whose headline columns are **NDCG@3** and **Hit@1**; `JustifQ /5` is a side column with footnote; `mean_judge_score` is preserved in JSON only.
- `pytest scripts/test_deterministic_scorer.py` passes, including the stability and idempotence tests.
- README "Scoring" section exists and is short enough (<100 words main para) that a reader can replicate the rubric by hand.
- `docs/plans/task-spec.md` § 7 is updated to point here.

## 10. References

- Webber, Moffat, Zobel (2010). *A Similarity Measure for Indefinite Rankings* (ACM TOIS) — RBO.
- Panickssery et al. (NeurIPS 2024). *LLM Evaluators Recognize and Favor Their Own Generations*.
- *Self-Preference Bias in LLM-as-a-Judge* — arXiv 2410.21819.
- *Play Favorites: A Statistical Method to Measure Self-Bias in LLM-as-a-Judge* — arXiv 2508.06709.
- Sierra Research (2024). *τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains* — outcome-based eval pattern.
