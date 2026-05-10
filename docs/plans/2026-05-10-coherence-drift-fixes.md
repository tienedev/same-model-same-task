# Cohérence drift fixes — implementation plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve the 8 cross-surface drifts identified in the cohérence audit (2026-05-10), so the README, /methodology, /findings, /[framework] and the underlying data tell the same story at the same precision.

**Architecture:** 5 prose-only edits + 3 small dashboard changes (one label flip, one dynamic computation, one conditional callout component). All fixes are additive or replacement; no schema/data changes. Single branch, ~6 commits.

**Tech Stack:** Markdown (README), Next.js 15 App Router + TSX (dashboard), no test runner for prose surfaces — verification is visual via `bun run dev` + a quick consistency grep.

---

## Pre-flight

```bash
cd /Users/tiene/Projets/same-model-same-task
git status                 # confirm clean tree
git checkout -b fix/coherence-drift
```

Start the dev server in one terminal so each task can be eyeballed:

```bash
cd dashboard && bun run dev   # http://localhost:3000
```

---

## Task 1: Align p95 precision (471s → 471.8s) in README + methodology

**Why:** `(471.806).toFixed(0)` renders as `"472"` on /findings; README and /methodology hardcode `"471s"`. Standardize on one decimal — matches the leaderboard's `.1f` rendering for p50/p95.

**Files:**
- Modify: `README.md:43`
- Modify: `dashboard/app/methodology/page.tsx:354`

**Step 1: README.md:43**

Old:

```
- **Google ADK's event loop has no client-side step timeout**: p95 is 471s on a task with a 19.9s p50, blocking on stuck upstream calls.
```

New:

```
- **Google ADK's event loop has no client-side step timeout**: p95 is 471.8s on a task with a 19.9s p50, blocking on stuck upstream calls.
```

**Step 2: dashboard/app/methodology/page.tsx:354**

Old:

```tsx
ADK's p95 latency is <strong>471s</strong> — one or two trials
```

New:

```tsx
ADK's p95 latency is <strong>471.8s</strong> — one or two trials
```

**Step 3: Verify the dashboard /findings still rounds to the same value**

In the browser, open `/findings`, scroll to Finding 3. The H2 description should still read "Google ADK runs 19.9s on a typical trial and 472s on its 95th percentile". Now change the description in `dashboard/app/findings/page.tsx:164` from `${p95Worst.p95.toFixed(0)}s` to `${p95Worst.p95.toFixed(1)}s` so all three surfaces read **471.8s**.

```tsx
// Before
description={`${p95Worst.framework} runs ${p95Worst.p50.toFixed(1)}s on a typical trial and ${p95Worst.p95.toFixed(0)}s on its 95th percentile. One trial reached ${p95Worst.max.toFixed(0)}s — over twelve minutes on a task that usually takes twenty seconds.`}

// After
description={`${p95Worst.framework} runs ${p95Worst.p50.toFixed(1)}s on a typical trial and ${p95Worst.p95.toFixed(1)}s on its 95th percentile. One trial reached ${p95Worst.max.toFixed(0)}s — over twelve minutes on a task that usually takes twenty seconds.`}
```

(Leave `max.toFixed(0)` — "752s" is fine for the worst-case anecdote.)

**Step 4: Commit**

```bash
git add README.md dashboard/app/methodology/page.tsx dashboard/app/findings/page.tsx
git commit -m "fix(prose): align p95 precision to one decimal across all surfaces"
```

---

## Task 2: Soften README JUDGE_MODEL claim

**Why:** README:104 promises a one-env-var swap to GPT-5/Claude via OpenRouter, but `harness/judge.py:118–150` always uses `GEMINI_API_KEY` + `GEMINI_OPENAI_BASE_URL`. The methodology page already phrases it correctly — copy that phrasing.

**Files:**
- Modify: `README.md:104`

**Step 1: README.md:104**

Old:

```
- **Gemini judges Gemini.** Self-judging bias is documented at ~15-20% over-rating on a model's own outputs. Set `JUDGE_MODEL` env var to swap for GPT-5 / Claude via OpenRouter to quantify the delta.
```

New:

```
- **Gemini judges Gemini.** Self-judging bias is documented at ~15-20% over-rating on a model's own outputs. The `/20` scores are useful for ordering frameworks, not for cross-vendor comparison; a follow-up swapping the judge for GPT-5 or Claude would quantify the delta.
```

**Rationale for the change:** removes the implication that `JUDGE_MODEL` alone is sufficient. If the user wants the actual swap to work, that's a separate (larger) change to `harness/judge.py` to read `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` when `JUDGE_MODEL` doesn't start with `gemini-`. Out of scope for this drift fix.

**Step 2: Commit**

```bash
git add README.md
git commit -m "fix(readme): soften JUDGE_MODEL swap claim to match harness/judge.py reality"
```

---

## Task 3: Fix home leaderboard sort label

**Why:** `dashboard/app/page.tsx:80–82` claims "ranked by latency p50, lower is faster" but `dashboard/components/leaderboard.tsx:30–33` actually sorts by `mean_judge_score` desc.

**Decision (from question 1):** keep the judge-score sort, fix the label.

**Files:**
- Modify: `dashboard/app/page.tsx:78–82`

**Step 1: Replace the SectionHeader call**

Old:

```tsx
<SectionHeader
  eyebrow="Leaderboard"
  title="Frameworks ranked by latency p50"
  description={`Lower is faster. Frameworks with no valid runs sort last. Pricing: $${summary.metadata.pricing_usd_per_m_tokens.in_per_m}/M input · $${summary.metadata.pricing_usd_per_m_tokens.out_per_m}/M output tokens.`}
/>
```

New:

```tsx
<SectionHeader
  eyebrow="Leaderboard"
  title="Frameworks ranked by judge score"
  description={`Higher is better. Frameworks with no valid runs sort last. Pricing: $${summary.metadata.pricing_usd_per_m_tokens.in_per_m}/M input · $${summary.metadata.pricing_usd_per_m_tokens.out_per_m}/M output tokens.`}
/>
```

**Step 2: Verify in browser**

Reload `/`. The leaderboard heading now reads "Frameworks ranked by judge score · Higher is better." Rank 1 is `langgraph` (15.59) — that already matched judge-score sort, so no row order changes; only the label.

**Step 3: Commit**

```bash
git add dashboard/app/page.tsx
git commit -m "fix(home): leaderboard heading describes the actual sort (judge score)"
```

---

## Task 4: Make /findings baseline-python flake-list data-driven

**Why:** Hardcoded `"jobs 002, 003, 005, 006"` in `dashboard/app/findings/page.tsx:226` misses `job-007` (also 2/3). Compute from `summary.per_job_success` so it stays accurate.

**Files:**
- Modify: `dashboard/app/findings/page.tsx` (top-of-component compute, then bullet)

**Step 1: Add a computed string at the top of `FindingsPage()`**

Add right after the existing `p95Worst` block (around `findings/page.tsx:51`):

```tsx
const baselinePythonFlakes = summary.per_job_success
  .filter((j) => j.framework === "baseline-python" && j.success_rate < 1.0)
  .map((j) => j.job_id.replace("job-", ""))
  .sort();
const baselinePythonFlakesText = formatJobList(baselinePythonFlakes);
```

And add a small helper above the component (or just inline it):

```tsx
function formatJobList(ids: string[]): string {
  if (ids.length === 0) return "no jobs";
  if (ids.length === 1) return `job ${ids[0]}`;
  if (ids.length === 2) return `jobs ${ids[0]} and ${ids[1]}`;
  return `jobs ${ids.slice(0, -1).join(", ")}, and ${ids[ids.length - 1]}`;
}
```

**Step 2: Replace the hardcoded bullet (~line 226)**

Old:

```tsx
<strong>Baseline-python flakes on jobs 002, 003, 005, 006</strong>
{" "}— without framework discipline, the manual loop hits its
step ceiling on tasks that demand more exploration.
```

New:

```tsx
<strong>Baseline-python flakes on {baselinePythonFlakesText}</strong>
{" "}— without framework discipline, the manual loop hits its
step ceiling on tasks that demand more exploration.
```

**Step 3: Verify**

Reload `/findings`. The bullet should now read: "Baseline-python flakes on jobs 002, 003, 005, 006, and 007 — …". Cross-check by counting amber + orange + red cells in the baseline-python row of the heatmap above (should be 5).

**Step 4: Commit**

```bash
git add dashboard/app/findings/page.tsx
git commit -m "fix(findings): compute baseline-python flake list at render time from summary data"
```

---

## Task 5: Align "DevOps / SRE" label between heatmap and prose

**Why:** Heatmap (`per-job-heatmap.tsx:9`) shows `"DevOps / SRE"`; /findings prose (`findings/page.tsx:219`) calls it `"DevOps / SRE remote role"`. The actual job title in `data/jobs.json` is "DevOps / Site Reliability Engineer", and "Remote-only role" appears in the description, not the title — so `"remote role"` in the prose is editorial and breaks visual symmetry with the heatmap.

**Files:**
- Modify: `dashboard/app/findings/page.tsx:219–221`

**Step 1: Drop "remote role" from the prose**

Old:

```tsx
<strong>Vercel AI SDK fails 0/3 on the DevOps / SRE remote
role</strong> — the only red cell in its row, despite 100% on
everything else. A specific class of input (long location string
+ many remote-related keywords) defeats its lean context
handling.
```

New:

```tsx
<strong>Vercel AI SDK fails 0/3 on the DevOps / SRE job</strong>
{" "}— the only red cell in its row, despite 100% on everything
else. A specific class of input (long location string + many
remote-related keywords) defeats its lean context handling.
```

The "remote-related keywords" phrase in the explanation already conveys the location detail without needing it in the headline.

**Step 2: Commit**

```bash
git add dashboard/app/findings/page.tsx
git commit -m "fix(findings): align job-006 label with the heatmap (drop 'remote role' qualifier)"
```

---

## Task 6: Clarify methodology native-path table header

**Why:** `dashboard/app/methodology/page.tsx:271–308` shows a table where the "Native Gemini path (preserves signatures)" column lists `gemini-3...` slugs. The bench actually runs on `gemini-2.5-flash`. A casual reader could mistake the native column for "what these adapters do today". Add one word to the column header.

**Files:**
- Modify: `dashboard/app/methodology/page.tsx:271–276`

**Step 1: Update the BorderedTable headers**

Old:

```tsx
<BorderedTable
  headers={[
    "Framework",
    "Native Gemini path (preserves signatures)",
    "OpenAI-compat path (used here)",
  ]}
```

New:

```tsx
<BorderedTable
  headers={[
    "Framework",
    "Native Gemini path (for thinking models)",
    "OpenAI-compat path (used by this bench)",
  ]}
```

**Step 2: Commit**

```bash
git add dashboard/app/methodology/page.tsx
git commit -m "fix(methodology): clarify native-path table is hypothetical (bench uses 2.5-flash)"
```

---

## Task 7: Add /findings anchors so /[framework] can deep-link

**Why:** /findings sections currently lack `id`s. The Task-8 callout needs anchors like `/findings#finding-1`.

**Files:**
- Modify: `dashboard/app/findings/page.tsx` (Section primitive at line 244)

**Step 1: Make the Section primitive accept an `id` prop**

Old (line 244–275 area):

```tsx
function Section({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: ReactNode;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-6">
```

New:

```tsx
function Section({
  id,
  eyebrow,
  title,
  description,
  children,
}: {
  id?: string;
  eyebrow: string;
  title: ReactNode;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 space-y-6">
```

(Mirrors the methodology page's Section signature for consistency.)

**Step 2: Pass `id` on the four findings sections**

In the JSX inside `FindingsPage()`:

```tsx
<Section id="finding-1" eyebrow="Finding 1 · Token cost" ...>
<Section id="finding-2" eyebrow="Finding 2 · Efficiency frontier" ...>
<Section id="finding-3" eyebrow="Finding 3 · Outliers" ...>
<Section id="finding-4" eyebrow="Finding 4 · Job-level breakdown" ...>
```

**Step 3: Verify**

Visit `http://localhost:3000/findings#finding-3` — the page should scroll to the p95 outliers section.

**Step 4: Commit**

```bash
git add dashboard/app/findings/page.tsx
git commit -m "feat(findings): add section anchors (finding-1..4) for deep-linking"
```

---

## Task 8: Add conditional /findings callout on /[framework] pages

**Why:** /[framework] is currently a dead-end — no link back into the cross-framework narrative on /findings even when that framework is named in a section there.

**Decision (from question 3):** conditional callout for the 3 frameworks discussed.

**Files:**
- Create: `dashboard/components/framework-findings-callout.tsx`
- Modify: `dashboard/app/[framework]/page.tsx` (insert callout after the KPIs section)

**Step 1: Create the callout component**

```tsx
// dashboard/components/framework-findings-callout.tsx
import Link from "next/link";

const FRAMEWORK_FINDINGS: Record<string, Array<{ section: string; label: string }>> = {
  "crewai": [
    { section: "finding-1", label: "Token cost — the 27× outlier" },
    { section: "finding-2", label: "Efficiency frontier — Pareto-dominated" },
  ],
  "google-adk": [
    { section: "finding-3", label: "p95 latency outliers" },
  ],
  "vercel-ai-sdk": [
    { section: "finding-1", label: "Token cost — the lean baseline" },
    { section: "finding-2", label: "Efficiency frontier — top quality-per-dollar" },
    { section: "finding-4", label: "Per-job breakdown — fails on job-006" },
  ],
};

export function FrameworkFindingsCallout({ framework }: { framework: string }) {
  const items = FRAMEWORK_FINDINGS[framework];
  if (!items || items.length === 0) return null;

  return (
    <aside className="rounded-xl border border-border/60 bg-muted/30 p-4">
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        Discussed in /findings
      </div>
      <ul className="mt-2 space-y-1 text-sm">
        {items.map((item) => (
          <li key={item.section}>
            <Link
              href={`/findings#${item.section}`}
              className="text-foreground/90 underline decoration-muted-foreground/40 underline-offset-2 transition-colors hover:decoration-foreground"
            >
              {item.label}
            </Link>
            <span className="ml-1 text-muted-foreground">→</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
```

**Step 2: Render on /[framework]**

In `dashboard/app/[framework]/page.tsx`, import the component near the top:

```tsx
import { FrameworkFindingsCallout } from "@/components/framework-findings-callout";
```

Then insert the callout *between* the KPIs section and the DETAIL TABLE section (around line 167). Wrap in a `pt-8` section for spacing:

```tsx
{/* CROSS-LINK to /findings if this framework is discussed there */}
<section className="pt-8">
  <FrameworkFindingsCallout framework={framework} />
</section>
```

The component returns `null` for frameworks not in `FRAMEWORK_FINDINGS` (baseline-python, baseline-typescript, langgraph, mastra, pydantic-ai), so those pages stay unchanged.

**Step 3: Verify**

Visit each:
- `/crewai` — callout shows 2 items
- `/google-adk` — callout shows 1 item
- `/vercel-ai-sdk` — callout shows 3 items
- `/langgraph` — no callout (component returns null)
- Click each link, confirm it scrolls to the right `/findings#finding-N` section.

**Step 4: Commit**

```bash
git add dashboard/components/framework-findings-callout.tsx dashboard/app/[framework]/page.tsx
git commit -m "feat(framework-page): conditional callout linking to /findings deep-dives"
```

---

## Task 9: Final verification + push

**Step 1: Type-check + build**

```bash
cd dashboard
bun run build       # confirms no TS errors / Next.js build issues
```

Expected: clean build, all 8 framework static params generated, /findings + /methodology + / pages compiled.

**Step 2: Re-run audit spot-checks**

```bash
# Confirm README precision matches
grep -n "471" README.md dashboard/app/methodology/page.tsx
# Both should show "471.8" (not "471s")

# Confirm JUDGE_MODEL claim is softened
grep -n "JUDGE_MODEL\|judge" README.md
# Should NOT say "Set JUDGE_MODEL env var to swap..."

# Confirm leaderboard label
grep -n "ranked by" dashboard/app/page.tsx
# Should say "ranked by judge score"
```

**Step 3: Visual smoke pass**

In the browser:
- `/` — heading "ranked by judge score · Higher is better"
- `/findings` — Finding 3 description reads "471.8s"; Finding 4 bullet lists 5 baseline-python jobs
- `/methodology` — Native path column header reads "(for thinking models)"
- `/crewai`, `/google-adk`, `/vercel-ai-sdk` — each shows the new callout

**Step 4: Push**

```bash
git push -u origin fix/coherence-drift
```

Then open a PR or merge directly to main per the project's preference (single-author OSS, fast-forward merge is fine).

---

## Out of scope (deferred)

These showed up in the audit but are bigger changes the user may want to tackle separately:

- **Make `JUDGE_MODEL` actually work for non-Gemini judges** — needs an `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` branch in `harness/judge.py`. Larger change; the README is now honest without it.
- **Make the leaderboard sort configurable** (option B from the question) — would need new state/UI; not chosen.

## Cohérence rules of thumb (encode for next time)

To prevent these from recurring:

1. **Numbers cited in prose should be computed from `summary.json` at render time** when reasonably possible. Anything hardcoded becomes a drift candidate. (Findings page already does this for H2 numbers — extend to bullet lists when feasible.)
2. **Two surfaces describing the same thing should agree on precision.** Either both render `.toFixed(1)` or both use the same hardcoded string sourced from a shared constant.
3. **README claims about `harness/` behavior should match the harness docstring.** When they disagree (as JUDGE_MODEL did), the harness docstring is right by default.
