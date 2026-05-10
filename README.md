# same-model-same-task

A cross-language benchmark of 8 LLM agent frameworks (5 Python + 3 TypeScript) calling the same Gemini model on the same matching task with the same 4 deterministic tools — only the framework varies. Goal: pick the right framework for your team's stack, not the highest leaderboard number.

> **Status:** Headline run complete — 240 runs (8 frameworks × 10 jobs × 3 trials). Numbers below are aggregated across the full run.

## Leaderboard

<!-- LEADERBOARD-START -->
| Framework | Valid | Judge /20 | p50 (s) | p95 (s) | Mean tokens (in/out) | Mean tools | Cost / run (USD) |
|---|---|---|---|---|---|---|---|
| baseline-python | 23/30 | 13.65 | 22.1 | 54.8 | 7027 / 515 | 9.7 | $0.0202 |
| baseline-typescript | 29/30 | 13.41 | 20.5 | 32.7 | 5897 / 495 | 9.2 | $0.0177 |
| crewai | 26/30 | 13.81 | 18.7 | 31.6 | 42785 / 1806 | 11.8 | $0.1072 |
| google-adk | 29/30 | 15.03 | 19.9 | 471.8 | 6128 / 510 | 9.3 | $0.0184 |
| langgraph | 27/30 | 15.59 | 17.1 | 25.9 | 5167 / 502 | 8.8 | $0.0164 |
| mastra | 30/30 | 13.97 | 21.5 | 31.9 | 6154 / 548 | 11.2 | $0.0189 |
| pydantic-ai | 29/30 | 15.31 | 16.2 | 31.5 | 6149 / 480 | 8.4 | $0.0181 |
| vercel-ai-sdk | 27/30 | 13.07 | 21.2 | 28.4 | 1605 / 228 | 9.1 | $0.0060 |

<!-- LEADERBOARD-END -->

> Re-run `python scripts/summarize.py` after a bench run to refresh the table above.

## Charts

Live dashboard (Pareto cost-vs-success, tokens stacked vs baseline) is online — see the `dashboard/` Next.js app. Run `bun run dev` from `dashboard/` to view locally.

## Frameworks

- **baseline-python / baseline-typescript** — raw `openai` SDK + manual tool-calling loop. Reference point.
- **LangGraph** (Python) — `StateGraph` + nodes/edges + `MessagesState`.
- **CrewAI** (Python) — `Agent` + `Task` + `Crew` constructors, LiteLLM internally.
- **PydanticAI** (Python) — `Agent` + `@agent.tool_plain` decorators.
- **Google ADK** (Python) — `LlmAgent` with `LiteLlm` wrapper to OpenAI-compat.
- **Mastra** (TypeScript) — `Agent` + `@ai-sdk/openai-compatible` provider.
- **Vercel AI SDK** (TypeScript) — `ToolLoopAgent` (v6 canonical pattern).

## What I learned

- **Vercel AI SDK's `ToolLoopAgent` runs at ~1.6k input tokens vs 5–7k elsewhere** — same task, same model, ~3× cheaper per run.
- **CrewAI's DSL re-injects agent and task config every step**, pushing input tokens to 42k and cost to $0.107 — 6× the bench average.
- **Google ADK's event loop has no client-side step timeout**: p95 is 471s on a task with a 19.9s p50, blocking on stuck upstream calls.
- **Picking a framework first and a model second is how thinking-model bugs reach production** — the `thought_signature` round-trip breaks 5/8 frameworks under OpenAI-compat.
- **Single-framework quickstarts hide the hard cases**; only a cross-framework bench surfaces both vendor-specific failures and per-framework cost behavior.

## Reproduce

```bash
# 1. Clone + Python deps
git clone https://github.com/tienedev/same-model-same-task
cd same-model-same-task
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. TypeScript deps (for Mastra + Vercel AI SDK + baselines)
bun install

# 3. Set the only env var you need (enterprise account is fine)
export GEMINI_API_KEY=...

# 4. Single-job canary (one trial per framework, ~1 minute total)
for fw in baseline-python baseline-typescript langgraph crewai pydantic-ai google-adk mastra vercel-ai-sdk; do
  python harness/run_bench.py --framework "$fw" --jobs job-001 --trials 1 --out "results/canary-$fw.json"
done

# 5. Full headline run (8 × 10 jobs × 3 trials, ~30-60 min, ~$3-5 in API costs)
mkdir -p results/headline
for fw in baseline-python baseline-typescript langgraph crewai pydantic-ai google-adk mastra vercel-ai-sdk; do
  python harness/run_bench.py --framework "$fw" --all-jobs --trials 3 --out "results/headline/$fw.json"
done

# 6. Aggregate + LLM-as-judge
python scripts/summarize.py --input results/headline
python harness/judge.py results/headline/*.json   # judges valid runs only
python scripts/summarize.py --input results/headline   # re-aggregate with judge scores
```

## Caveats

### 1. The `thought_signature` trap (why we use 2.5-Flash, not 3.x)

Gemini 3.x and 2.5-Pro are **thinking models**: they generate internal reasoning before each function call. Google's API attaches an opaque `thought_signature` to each function call returned by these models, and **expects that signature back** when the agent re-injects the conversation history at the next turn.

Frameworks that pass the response message through verbatim (baseline-python, baseline-typescript, Mastra, Vercel AI SDK) preserve the signature. Frameworks that rebuild messages with a "clean" provider-agnostic shape (LangGraph, PydanticAI) silently strip it. Google then rejects the next request:

```
400: Function call is missing a thought_signature in functionCall parts.
Additional data: function call `default_api:list_jobs`, position 2.
```

Empirical breakage rates measured by this bench (1 trial per framework on `job-001`):

| Model | Frameworks working |
|---|---|
| `gemini-3.1-pro-preview` | 3/8 |
| `gemini-3-flash-preview` | 6/8 (breaks LangGraph, PydanticAI) |
| `gemini-2.5-flash` | **8/8** (not a thinking model → no signature to preserve) |

This bug doesn't surface in single-framework quickstarts. It only emerges in a cross-framework bench where rebuilt messages meet thinking models — which is exactly the setup most production teams adopt by accident when they pick a framework first and a model later.

### 2. Other limits

- **Gemini judges Gemini.** Self-judging bias is documented at ~15-20% over-rating on a model's own outputs. Set `JUDGE_MODEL` env var to swap for GPT-5 / Claude via OpenRouter to quantify the delta.
- **Per-framework metric availability gaps.** CrewAI's `tool_calls` was historically zero before we wired its `step_callback`. If a future SDK upgrade changes its callback shape, that field reverts to `null` rather than silently misleading.
- **Sample size.** The headline run is 30 trials per framework. Confidence intervals on `p95` get noisy below 100 trials — interpret single-decimal differences with caution.

## Methodology

See `docs/plans/2026-05-07-same-model-same-task-design.md` for the full design rationale (model + task + tools + fairness rules) and `docs/plans/task-spec.md` for the dataset shape.

## License

MIT.
