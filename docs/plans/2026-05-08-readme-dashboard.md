# README + Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the presentation layer (summarize.py + README.md + Next.js dashboard) BEFORE the headline run, so chart format and table columns are locked before data is seen — preventing post-hoc bias.

**Architecture:** Pure stdlib Python aggregator reads `results/*.json` → produces `dashboard/data/summary.json` (consumed by RSC) + `results/summary.md` (human) + injected leaderboard in README. Next.js 15 dashboard reads `summary.json` at build time, deployable on Vercel.

**Tech Stack:** Python 3.11 stdlib (json, statistics, pathlib, click), Next.js 15 App Router, shadcn/ui, Tremor (charts), TypeScript strict, Tailwind, bun.

**Reference:** See `docs/plans/2026-05-08-readme-dashboard-design.md` for context and rationale.

---

## Phase 1 — `scripts/summarize.py` (TDD)

### Task 1: Set up test fixture

**Files:**
- Create: `scripts/test_summarize.py`
- Create: `scripts/fixtures/run-frameworkA-job-001.json`
- Create: `scripts/fixtures/run-frameworkA-job-002.json`
- Create: `scripts/fixtures/run-frameworkB-job-001.json` (one invalid run)

**Step 1: Write the failing test**

```python
"""Unit tests for scripts/summarize.py.
Uses synthetic fixture data so tests don't depend on real results/.
"""
from pathlib import Path
import json

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

def test_load_results_finds_all_json():
    from scripts.summarize import load_results
    runs = load_results(FIXTURES_DIR)
    assert len(runs) == 3
    frameworks = {r["framework"] for r in runs}
    assert frameworks == {"frameworkA", "frameworkB"}
```

**Step 2: Create fixtures**

`scripts/fixtures/run-frameworkA-job-001.json`:
```json
{
  "framework": "frameworkA",
  "started_at": "2026-05-08T10:00:00Z",
  "runs": [
    {"framework": "frameworkA", "job_id": "job-001", "trial": 1, "valid": true,
     "elapsed_s": 10.0, "input_tokens": 1000, "output_tokens": 200, "tool_calls": 5,
     "parsed_output": {"job_id": "job-001", "ranked_candidates": [
        {"rank": 1, "candidate_id": "cand-001", "score": 100, "justification": "x"},
        {"rank": 2, "candidate_id": "cand-002", "score": 90, "justification": "y"},
        {"rank": 3, "candidate_id": "cand-003", "score": 80, "justification": "z"}
     ]}}
  ]
}
```

`scripts/fixtures/run-frameworkA-job-002.json`: same shape, elapsed_s=20.0, in=2000, out=400.
`scripts/fixtures/run-frameworkB-job-001.json`: `valid: false`, `validation_error: "..."`, no parsed_output.

**Step 3: Run test → expected FAIL** (`scripts.summarize` doesn't exist)

`source .venv/bin/activate && pytest scripts/test_summarize.py::test_load_results_finds_all_json -v`

**Step 4: Implement `load_results`**

Create `scripts/summarize.py`:
```python
"""Aggregates results/*.json into stats consumable by README + dashboard."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def load_results(input_dir: Path) -> list[dict[str, Any]]:
    """Returns flat list of all runs across all framework files in input_dir."""
    runs: list[dict[str, Any]] = []
    for f in sorted(input_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue  # skip malformed
        runs.extend(data.get("runs", []))
    return runs
```

**Step 5: Run test → expected PASS**

**Step 6: Commit**
```bash
git add scripts/summarize.py scripts/test_summarize.py scripts/fixtures/
git commit -m "test(summarize): scaffolding + load_results"
```

---

### Task 2: `compute_stats` per framework

**Files:**
- Modify: `scripts/test_summarize.py`
- Modify: `scripts/summarize.py`

**Step 1: Add failing tests**

```python
def test_compute_stats_aggregates_per_framework():
    from scripts.summarize import load_results, compute_stats
    runs = load_results(FIXTURES_DIR)
    stats = compute_stats(runs)
    by_fw = {s["framework"]: s for s in stats}
    a = by_fw["frameworkA"]
    assert a["count_total"] == 2
    assert a["count_valid"] == 2
    assert a["success_rate"] == 1.0
    assert a["latency_p50"] == 15.0  # median of 10, 20
    assert a["latency_mean"] == 15.0
    assert a["mean_input_tokens"] == 1500
    assert a["mean_output_tokens"] == 300
    assert a["mean_tool_calls"] == 5.0
    b = by_fw["frameworkB"]
    assert b["count_total"] == 1
    assert b["count_valid"] == 0
    assert b["success_rate"] == 0.0

def test_compute_stats_handles_none_tool_calls():
    """Some adapters may report tool_calls=None when API doesn't expose it."""
    from scripts.summarize import compute_stats
    runs = [
        {"framework": "x", "valid": True, "elapsed_s": 1.0, "input_tokens": 1,
         "output_tokens": 1, "tool_calls": None}
    ]
    stats = compute_stats(runs)
    assert stats[0]["mean_tool_calls"] is None
```

**Step 2: Run → FAIL**
**Step 3: Implement**

```python
import statistics

GEMINI_PRICING = {"in_per_m": 2.0, "out_per_m": 12.0}  # USD per 1M tokens

def _percentile(values: list[float], p: float) -> float:
    if not values: return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)

def compute_stats(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_fw: dict[str, list[dict[str, Any]]] = {}
    for r in runs:
        by_fw.setdefault(r["framework"], []).append(r)
    out = []
    for fw, fw_runs in by_fw.items():
        valid = [r for r in fw_runs if r.get("valid")]
        latencies = [r["elapsed_s"] for r in valid if "elapsed_s" in r]
        in_tok = [r.get("input_tokens", 0) for r in valid]
        out_tok = [r.get("output_tokens", 0) for r in valid]
        tc_values = [r["tool_calls"] for r in valid if r.get("tool_calls") is not None]
        any_none = any(r.get("tool_calls") is None for r in valid)
        mean_tc = (statistics.mean(tc_values) if tc_values else 0) if not any_none or tc_values else None
        # Pricing: USD per 1M
        sum_in, sum_out = sum(in_tok), sum(out_tok)
        cost_total = (sum_in * GEMINI_PRICING["in_per_m"] + sum_out * GEMINI_PRICING["out_per_m"]) / 1_000_000
        out.append({
            "framework": fw,
            "count_total": len(fw_runs),
            "count_valid": len(valid),
            "success_rate": len(valid) / len(fw_runs) if fw_runs else 0.0,
            "latency_p50": _percentile(latencies, 0.50),
            "latency_p95": _percentile(latencies, 0.95),
            "latency_mean": statistics.mean(latencies) if latencies else 0.0,
            "latency_max": max(latencies) if latencies else 0.0,
            "mean_input_tokens": int(statistics.mean(in_tok)) if in_tok else 0,
            "mean_output_tokens": int(statistics.mean(out_tok)) if out_tok else 0,
            "mean_tool_calls": mean_tc,
            "estimated_cost_usd_per_run": cost_total / len(valid) if valid else 0.0,
            "hit_step_limit_rate": sum(1 for r in valid if r.get("hit_step_limit")) / len(valid) if valid else 0.0,
        })
    return sorted(out, key=lambda s: s["framework"])
```

**Step 4: Run → PASS**
**Step 5: Commit**
```bash
git commit -am "feat(summarize): compute_stats with percentiles + cost"
```

---

### Task 3: `write_summary_json` and `write_summary_md`

**Files:**
- Modify: `scripts/test_summarize.py`
- Modify: `scripts/summarize.py`

**Step 1: Failing tests**

```python
def test_write_summary_json(tmp_path):
    from scripts.summarize import compute_stats, write_summary_json, load_results
    stats = compute_stats(load_results(FIXTURES_DIR))
    out = tmp_path / "summary.json"
    write_summary_json(stats, out)
    data = json.loads(out.read_text())
    assert "frameworks" in data
    assert "metadata" in data
    assert len(data["frameworks"]) == 2

def test_write_summary_md(tmp_path):
    from scripts.summarize import compute_stats, write_summary_md, load_results
    stats = compute_stats(load_results(FIXTURES_DIR))
    out = tmp_path / "summary.md"
    write_summary_md(stats, out)
    text = out.read_text()
    assert "| Framework |" in text
    assert "frameworkA" in text
    assert "frameworkB" in text
```

**Step 2: Run → FAIL**
**Step 3: Implement**

```python
from datetime import datetime, timezone

def write_summary_json(stats: list[dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_frameworks": len(stats),
            "pricing_usd_per_m_tokens": GEMINI_PRICING,
        },
        "frameworks": stats,
    }, indent=2, ensure_ascii=False))

def _fmt_or_dash(v: float | None, fmt: str) -> str:
    return "—" if v is None else format(v, fmt)

def write_summary_md(stats: list[dict[str, Any]], out: Path) -> None:
    rows = ["| Framework | Valid | p50 (s) | p95 (s) | Mean tokens (in/out) | Mean tools | Cost / run (USD) |",
            "|---|---|---|---|---|---|---|"]
    for s in stats:
        rows.append(
            f"| {s['framework']} | {s['count_valid']}/{s['count_total']} "
            f"| {s['latency_p50']:.1f} | {s['latency_p95']:.1f} "
            f"| {s['mean_input_tokens']} / {s['mean_output_tokens']} "
            f"| {_fmt_or_dash(s['mean_tool_calls'], '.1f')} "
            f"| ${s['estimated_cost_usd_per_run']:.4f} |"
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(rows) + "\n")
```

**Step 4: Run → PASS**
**Step 5: Commit**
```bash
git commit -am "feat(summarize): JSON + Markdown writers"
```

---

### Task 4: CLI entry point

**Files:**
- Modify: `scripts/summarize.py`

**Step 1: Add `main()` with click**

```python
import click

@click.command()
@click.option("--input", "input_dir", default="results", type=click.Path(exists=True, file_okay=False))
@click.option("--out-json", default="dashboard/data/summary.json", type=click.Path())
@click.option("--out-md", default="results/summary.md", type=click.Path())
def main(input_dir: str, out_json: str, out_md: str) -> None:
    runs = load_results(Path(input_dir))
    stats = compute_stats(runs)
    write_summary_json(stats, Path(out_json))
    write_summary_md(stats, Path(out_md))
    click.echo(f"Wrote {out_json} and {out_md} ({len(stats)} frameworks, {len(runs)} runs)", err=True)

if __name__ == "__main__":
    main()
```

**Step 2: Run end-to-end on canary**

`mkdir -p dashboard/data && python scripts/summarize.py --input results --out-json dashboard/data/summary.json --out-md results/summary.md`

Expected: writes both files; stderr `Wrote dashboard/data/summary.json and results/summary.md (8 frameworks, 8 runs)`.

**Step 3: Commit**
```bash
git commit -am "feat(summarize): click CLI + e2e test on canary results"
```

---

### Task 5: README leaderboard injection

**Files:**
- Modify: `scripts/summarize.py`
- Modify: `scripts/test_summarize.py`

**Step 1: Failing test**

```python
def test_inject_leaderboard_replaces_between_sentinels(tmp_path):
    from scripts.summarize import inject_leaderboard
    p = tmp_path / "README.md"
    p.write_text("# Hi\n\n<!-- LEADERBOARD-START -->\nold content\n<!-- LEADERBOARD-END -->\n\nbye")
    inject_leaderboard(p, "| F | V |\n|---|---|\n| x | 1 |")
    text = p.read_text()
    assert "old content" not in text
    assert "| x | 1 |" in text
    assert "# Hi" in text and "bye" in text
```

**Step 2: Implement**

```python
import re

LEADERBOARD_BLOCK_RE = re.compile(
    r"<!-- LEADERBOARD-START -->.*?<!-- LEADERBOARD-END -->",
    re.DOTALL,
)

def inject_leaderboard(readme_path: Path, table_md: str) -> None:
    if not readme_path.exists():
        return
    text = readme_path.read_text()
    block = f"<!-- LEADERBOARD-START -->\n{table_md}\n<!-- LEADERBOARD-END -->"
    new = LEADERBOARD_BLOCK_RE.sub(block, text)
    if new != text:
        readme_path.write_text(new)
```

Update `main()` to also call `inject_leaderboard(Path("README.md"), build_leaderboard_md(stats))` (extract leaderboard MD building into `build_leaderboard_md(stats)` reusing the `write_summary_md` body — refactor for DRY).

**Step 3: Run tests → PASS**
**Step 4: Commit**
```bash
git commit -am "feat(summarize): inject leaderboard between README sentinels"
```

---

## Phase 2 — `README.md`

### Task 6: README skeleton

**Files:**
- Create: `README.md`

**Step 1: Write the file**

Sections:
1. Title + 1-paragraph hero pitch
2. `## Leaderboard` with `<!-- LEADERBOARD-START -->` … `<!-- LEADERBOARD-END -->` containing a "—" placeholder row
3. `## Charts` with link to dashboard URL placeholder
4. `## Frameworks` with bulleted list (linking to `dashboard/{framework}` paths)
5. `## What I learned` — 5 placeholder bullets to be filled post-run
6. `## Reproduce` — concrete commands
7. `## Caveats` — 3 honest limits

**Step 2: Run summarize.py to inject canary leaderboard**

`python scripts/summarize.py`

Verify the leaderboard between sentinels is now populated with canary data.

**Step 3: Commit**
```bash
git add README.md
git commit -m "docs: README skeleton with leaderboard sentinels + first canary inject"
```

---

## Phase 3 — Next.js dashboard

### Task 7: Dashboard project init

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/tsconfig.json`
- Create: `dashboard/next.config.mjs`
- Create: `dashboard/tailwind.config.ts`
- Create: `dashboard/postcss.config.mjs`
- Create: `dashboard/.gitignore`

**Step 1: Init**

```bash
cd dashboard
bun create next-app . --typescript --tailwind --app --no-src-dir --import-alias "@/*" --turbopack=false
```

Accept defaults. Add `dashboard/.gitignore` with `.next`, `node_modules`, `out`.

**Step 2: Install Tremor + shadcn deps**

```bash
bun add @tremor/react clsx tailwind-merge class-variance-authority lucide-react
bun add -D @types/node
```

**Step 3: Init shadcn**

```bash
bunx shadcn@latest init -y -d
bunx shadcn@latest add card table button badge
```

**Step 4: Smoke check**

```bash
bun run build
```

Expected: build succeeds.

**Step 5: Commit**
```bash
cd ..
git add dashboard/
git commit -m "feat(dashboard): scaffold Next.js 15 + shadcn + Tremor"
```

---

### Task 8: `lib/stats.ts` types

**Files:**
- Create: `dashboard/lib/stats.ts`

**Step 1: Write types matching summary.json**

> ⚠️ **Per-valid metrics are `number | null`**: when a framework has `count_valid == 0`, all per-valid metrics are emitted as `null` by `compute_stats` (Task 2 I1 fix). The TS interface below reflects that. Components consuming these fields must handle `null` (use `?? "—"` or `value === null ? "—" : value.toFixed(1)`).

```typescript
export interface FrameworkStats {
  framework: string;
  count_total: number;
  count_valid: number;
  success_rate: number;
  latency_p50: number | null;
  latency_p95: number | null;
  latency_mean: number | null;
  latency_max: number | null;
  mean_input_tokens: number | null;
  mean_output_tokens: number | null;
  mean_tool_calls: number | null;
  estimated_cost_usd_per_run: number | null;
  hit_step_limit_rate: number | null;
}

export interface Summary {
  metadata: {
    generated_at: string;
    n_frameworks: number;
    pricing_usd_per_m_tokens: { in_per_m: number; out_per_m: number };
  };
  frameworks: FrameworkStats[];
}

import summaryData from "@/data/summary.json";
export const summary = summaryData as Summary;
```

**Step 2: Verify types compile**

```bash
cd dashboard && bunx tsc --noEmit
```

Expected: green (after `data/summary.json` exists with the right shape — already exists from Task 4).

**Step 3: Commit**

```bash
git commit -am "feat(dashboard): add Summary types"
```

---

### Task 9: `app/page.tsx` — Hero + Leaderboard

**Files:**
- Create: `dashboard/components/leaderboard.tsx`
- Modify: `dashboard/app/page.tsx`

**Step 1: Build Leaderboard component**

Use shadcn Table. Columns: Framework, Valid, p50 (s), p95 (s), Mean tokens (in/out), Mean tools, Cost / run.

```tsx
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { FrameworkStats } from "@/lib/stats";

export function Leaderboard({ stats }: { stats: FrameworkStats[] }) {
  return (
    <Table>
      <TableHeader><TableRow>
        <TableHead>Framework</TableHead>
        <TableHead>Valid</TableHead>
        <TableHead>p50 (s)</TableHead>
        <TableHead>p95 (s)</TableHead>
        <TableHead>Mean in/out tokens</TableHead>
        <TableHead>Mean tools</TableHead>
        <TableHead>Cost / run (USD)</TableHead>
      </TableRow></TableHeader>
      <TableBody>{stats.map((s) => (
        <TableRow key={s.framework}>
          <TableCell className="font-mono">{s.framework}</TableCell>
          <TableCell>{s.count_valid}/{s.count_total}</TableCell>
          <TableCell>{s.latency_p50 === null ? "—" : s.latency_p50.toFixed(1)}</TableCell>
          <TableCell>{s.latency_p95 === null ? "—" : s.latency_p95.toFixed(1)}</TableCell>
          <TableCell>{s.mean_input_tokens === null || s.mean_output_tokens === null ? "—" : `${s.mean_input_tokens} / ${s.mean_output_tokens}`}</TableCell>
          <TableCell>{s.mean_tool_calls === null ? "—" : s.mean_tool_calls.toFixed(1)}</TableCell>
          <TableCell>{s.estimated_cost_usd_per_run === null ? "—" : `$${s.estimated_cost_usd_per_run.toFixed(4)}`}</TableCell>
        </TableRow>
      ))}</TableBody>
    </Table>
  );
}
```

**Step 2: `app/page.tsx`**

```tsx
import { summary } from "@/lib/stats";
import { Leaderboard } from "@/components/leaderboard";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <main className="container mx-auto px-4 py-8 space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>same-model-same-task</CardTitle>
          <CardDescription>
            Cross-language benchmark of {summary.frameworks.length} agent frameworks.
            Same model, same task, same tools — only the framework varies.
          </CardDescription>
        </CardHeader>
      </Card>
      <Leaderboard stats={summary.frameworks} />
    </main>
  );
}
```

**Step 3: Smoke check**

`cd dashboard && bun run build`

Expected: green.

**Step 4: Commit**

```bash
git commit -am "feat(dashboard): hero + leaderboard table on /"
```

---

### Task 10: Pareto + Tokens stack charts

**Files:**
- Create: `dashboard/components/pareto-chart.tsx`
- Create: `dashboard/components/tokens-stack-chart.tsx`
- Modify: `dashboard/app/page.tsx`

**Step 1: ParetoChart (cost vs success)**

```tsx
"use client";
import { ScatterChart } from "@tremor/react";
import type { FrameworkStats } from "@/lib/stats";

export function ParetoChart({ stats }: { stats: FrameworkStats[] }) {
  const data = stats.map((s) => ({
    framework: s.framework,
    "Cost (USD/run)": s.estimated_cost_usd_per_run,
    "Success rate (%)": s.success_rate * 100,
  }));
  return (
    <ScatterChart
      data={data}
      x="Cost (USD/run)"
      y="Success rate (%)"
      category="framework"
      sizeRange={[40, 80]}
      className="h-72"
    />
  );
}
```

**Step 2: TokensStackChart**

```tsx
"use client";
import { BarChart } from "@tremor/react";
import type { FrameworkStats } from "@/lib/stats";

export function TokensStackChart({ stats }: { stats: FrameworkStats[] }) {
  const data = stats.map((s) => ({
    framework: s.framework,
    Input: s.mean_input_tokens,
    Output: s.mean_output_tokens,
  }));
  return (
    <BarChart
      data={data}
      index="framework"
      categories={["Input", "Output"]}
      stack
      className="h-72"
    />
  );
}
```

**Step 3: Add to `app/page.tsx`**

After Leaderboard:
```tsx
<div className="grid md:grid-cols-2 gap-6">
  <Card><CardHeader><CardTitle>Cost vs Success</CardTitle></CardHeader>
    <CardContent><ParetoChart stats={summary.frameworks} /></CardContent></Card>
  <Card><CardHeader><CardTitle>Tokens (in/out stacked)</CardTitle></CardHeader>
    <CardContent><TokensStackChart stats={summary.frameworks} /></CardContent></Card>
</div>
```

**Step 4: Build**

`cd dashboard && bun run build`

**Step 5: Commit**

```bash
git commit -am "feat(dashboard): Pareto + tokens stacked charts on home"
```

---

### Task 11: `app/[framework]/page.tsx` — per-framework page

**Files:**
- Create: `dashboard/app/[framework]/page.tsx`

**Step 1: Implement**

```tsx
import { summary } from "@/lib/stats";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { notFound } from "next/navigation";

export function generateStaticParams() {
  return summary.frameworks.map((s) => ({ framework: s.framework }));
}

export default async function Page({ params }: { params: Promise<{ framework: string }> }) {
  const { framework } = await params;
  const stats = summary.frameworks.find((s) => s.framework === framework);
  if (!stats) notFound();
  return (
    <main className="container mx-auto px-4 py-8 space-y-6">
      <Card>
        <CardHeader><CardTitle className="font-mono">{stats.framework}</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <Stat label="Valid runs" value={`${stats.count_valid}/${stats.count_total}`} />
          <Stat label="Success rate" value={`${(stats.success_rate * 100).toFixed(0)}%`} />
          <Stat label="Latency p50" value={stats.latency_p50 === null ? "—" : `${stats.latency_p50.toFixed(1)}s`} />
          <Stat label="Latency p95" value={stats.latency_p95 === null ? "—" : `${stats.latency_p95.toFixed(1)}s`} />
          <Stat label="Mean tokens in" value={stats.mean_input_tokens?.toString() ?? "—"} />
          <Stat label="Mean tokens out" value={stats.mean_output_tokens?.toString() ?? "—"} />
          <Stat label="Mean tool calls" value={stats.mean_tool_calls?.toFixed(1) ?? "—"} />
          <Stat label="Cost / run" value={stats.estimated_cost_usd_per_run === null ? "—" : `$${stats.estimated_cost_usd_per_run.toFixed(4)}`} />
        </CardContent>
      </Card>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-muted-foreground text-xs">{label}</div>
      <div className="text-lg font-mono">{value}</div>
    </div>
  );
}
```

**Step 2: Build → all framework routes generated**
**Step 3: Commit**

```bash
git commit -am "feat(dashboard): per-framework deep-dive route"
```

---

### Task 12: `app/methodology/page.tsx`

**Files:**
- Create: `dashboard/app/methodology/page.tsx`

**Step 1: Implement** — static MDX-style content from design doc:

- Task description
- Model + endpoint
- Scoring rubric
- Caveats (Flash vs Pro tradeoff, self-judging, per-framework metric availability gaps)

Keep it simple: 1-page markdown rendered with shadcn Card sections. No MDX library needed for this scope.

**Step 2: Build → green**
**Step 3: Commit**

```bash
git commit -am "feat(dashboard): /methodology page with caveats"
```

---

### Task 13: Layout + nav

**Files:**
- Modify: `dashboard/app/layout.tsx`

**Step 1: Add nav header**

```tsx
import Link from "next/link";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><body>
      <header className="border-b">
        <nav className="container mx-auto px-4 py-3 flex gap-6 text-sm">
          <Link href="/" className="font-semibold">same-model-same-task</Link>
          <Link href="/methodology">Methodology</Link>
          <a href="https://github.com/tiene9/same-model-same-task" className="ml-auto">GitHub</a>
        </nav>
      </header>
      {children}
    </body></html>
  );
}
```

**Step 2: Build → green**
**Step 3: Commit**

```bash
git commit -am "feat(dashboard): top nav + GitHub link"
```

---

### Task 14: Visual smoke test (manual)

**Step 1: Start dev server**

```bash
cd dashboard && bun run dev
```

Open `http://localhost:3000` — verify:
- [ ] Leaderboard renders with 8 framework rows
- [ ] Pareto chart renders (8 dots even if clustered)
- [ ] Tokens stack chart renders
- [ ] Click a framework name → goes to `/{framework}` and shows the stats card
- [ ] Click Methodology → renders the page

**Step 2: Fix anything broken iteratively (commit per fix)**

---

### Task 15: Vercel deploy config

**Files:**
- Create: `dashboard/vercel.json` (optional)
- Create: `.github/workflows/deploy-dashboard.yml` (optional, can skip for MVP)

**Step 1: Add `vercel.json` if needed**

For MVP, just ensure `bun run build` works locally. Vercel auto-detects Next.js. Manual deploy via `vercel --prod` from `dashboard/` is sufficient.

**Step 2: Commit**

```bash
git commit -am "chore(dashboard): vercel deploy ready"
```

---

## Final smoke check

```bash
# From repo root
python scripts/summarize.py     # regen summary.json + leaderboard
cd dashboard && bun run build   # build dashboard
```

Both should succeed with no errors.

```bash
git log --oneline -20  # verify clean commit history
```

---

## Sequencing summary

1. Tasks 1-5 → `summarize.py` working with tests, e2e on canary results
2. Task 6 → README skeleton + first leaderboard inject
3. Tasks 7-13 → dashboard scaffolded, 3 routes, 2 charts
4. Task 14 → manual visual smoke test
5. Task 15 → Vercel-ready

**Then** the headline run + judge phase, after which:
- `python scripts/summarize.py --input results/headline/`
- `cd dashboard && bun run build`
- README leaderboard auto-updates, dashboard data refreshes, redeploy.

No code change needed in the presentation layer at that point. Pre-registration discipline preserved.
