import type { Metadata } from "next";
import type { ReactNode } from "react";
import { LatencyStripChart } from "@/components/findings/latency-strip-chart";
import { PerJobHeatmap } from "@/components/findings/per-job-heatmap";
import { QualityPerDollarChart } from "@/components/findings/quality-per-dollar-chart";
import { TokenBreakdownChart } from "@/components/findings/token-breakdown-chart";
import { summary } from "@/lib/stats";

export const metadata: Metadata = {
  title: "Findings",
  description:
    "Four findings the leaderboard hides: token cost variance, the real efficiency frontier, p95 outliers, and which job categories break which frameworks.",
};

export default function FindingsPage() {
  // Pre-compute the punchline numbers once so the prose doesn't drift from data.
  const sorted = [...summary.frameworks].sort(
    (a, b) =>
      (a.mean_input_tokens ?? 0) - (b.mean_input_tokens ?? 0),
  );
  const leanest = sorted[0];
  const fattest = sorted[sorted.length - 1];
  const tokenRatio =
    leanest.mean_input_tokens && fattest.mean_input_tokens
      ? fattest.mean_input_tokens / leanest.mean_input_tokens
      : 0;

  const qpdSorted = [...summary.frameworks]
    .filter(
      (s) =>
        s.mean_judge_score !== null && s.estimated_cost_usd_per_run !== null,
    )
    .sort(
      (a, b) =>
        (b.mean_judge_score as number) /
          (b.estimated_cost_usd_per_run as number) -
        (a.mean_judge_score as number) /
          (a.estimated_cost_usd_per_run as number),
    );
  const topQpd = qpdSorted[0];
  const bottomQpd = qpdSorted[qpdSorted.length - 1];
  const topQpdValue =
    (topQpd.mean_judge_score as number) /
    (topQpd.estimated_cost_usd_per_run as number);
  const bottomQpdValue =
    (bottomQpd.mean_judge_score as number) /
    (bottomQpd.estimated_cost_usd_per_run as number);

  const p95Worst = [...summary.latency_distribution].sort(
    (a, b) => b.p95 - a.p95,
  )[0];

  return (
    <main className="container mx-auto max-w-3xl px-4 pb-16">
      <header className="space-y-5 border-b border-border/60 py-14 md:py-20">
        <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-muted/40 px-3 py-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          <span className="size-1.5 rounded-full bg-orange-500" />
          Findings
        </div>
        <h1 className="text-balance text-4xl font-semibold tracking-tight md:text-5xl">
          Four things the leaderboard hides.
        </h1>
        <p className="max-w-2xl text-pretty text-base text-muted-foreground md:text-lg">
          Aggregated p50 and success-rate columns flatten the more interesting
          shape of the dataset. These four sections walk through patterns the
          headline numbers obscure — token cost spread, the real efficiency
          frontier, p95 stalls, and which job categories break which frameworks.
        </p>
      </header>

      <div className="space-y-20 pt-12">
        {/* FINDING 1 — token cost variance */}
        <Section
          eyebrow="Finding 1 · Token cost"
          title={
            <>
              The same task runs on{" "}
              <span className="text-orange-600 dark:text-orange-400">
                {tokenRatio.toFixed(0)}× more input tokens
              </span>{" "}
              depending on the framework.
            </>
          }
          description={`${fattest.framework} averages ${fattest.mean_input_tokens?.toLocaleString()} input tokens per run. ${leanest.framework} averages ${leanest.mean_input_tokens?.toLocaleString()}. Same model, same prompt, same tools.`}
        >
          <TokenBreakdownChart stats={summary.frameworks} />
          <p>
            The variance lives in <em>how each framework rebuilds the prompt at
            every step of the tool-calling loop</em>. A framework that re-injects
            its own scaffolding (agent backstory, task description, ReAct
            preamble, verbose tool descriptions) on each turn pays for that
            choice every step.
          </p>
          <Callout title={`Why ${fattest.framework} runs at ${tokenRatio.toFixed(0)}× the lean baseline`}>
            <p>
              CrewAI's DSL re-serializes the agent persona and the task
              specification into the prompt on every step. Twelve steps × ~3,000
              tokens of framework boilerplate ≈ 36,000 tokens of repeated
              scaffolding, on top of the ~6,000 tokens of actual conversation
              state. The cost shows up in the bill, not the leaderboard.
            </p>
          </Callout>
          <Callout title={`Why ${leanest.framework} runs at 1×`}>
            <p>
              Vercel's <code>ToolLoopAgent</code> keeps a single message thread,
              ships compact JSON-schema tool descriptions, and trusts the model
              to manage its own internal reasoning. No "Thought / Action /
              Observation" preamble, no per-step persona reset. The model gets
              the conversation as-is and replies.
            </p>
          </Callout>
        </Section>

        {/* FINDING 2 — quality-per-dollar */}
        <Section
          eyebrow="Finding 2 · Efficiency frontier"
          title={
            <>
              {topQpd.framework} delivers{" "}
              <span className="text-emerald-600 dark:text-emerald-400">
                {(topQpdValue / bottomQpdValue).toFixed(0)}× the judge points
                per dollar
              </span>{" "}
              of {bottomQpd.framework}.
            </>
          }
          description="Cost and quality alone are misleading axes. Cost / quality together is the metric a buyer should care about — and it crowns a different framework than either column individually."
        >
          <QualityPerDollarChart stats={summary.frameworks} />
          <p>
            On absolute quality, LangGraph wins (15.59/20). On absolute cost,
            Vercel AI SDK wins ($0.0060/run). The efficiency frontier — judge
            points per dollar — surfaces a third story: <strong>Vercel AI
            SDK delivers more quality per dollar than every other framework
            in the bench, despite ranking last on raw quality.</strong> Its
            13.07/20 paid for at $0.0060 still beats LangGraph's 15.59/20 paid
            for at $0.0164.
          </p>
          <Callout title="The Pareto-dominated framework">
            <p>
              CrewAI sits at {bottomQpdValue.toFixed(0)} pts/$ — the only
              framework that loses on every individual axis except success rate.
              Higher cost than the average, lower quality than the top group.
              Its 27× input-token spend doesn't translate to better judge
              outputs; it's pure framework overhead being billed as if it were
              capability.
            </p>
          </Callout>
        </Section>

        {/* FINDING 3 — p95 outliers */}
        <Section
          eyebrow="Finding 3 · Outliers"
          title={
            <>
              <span className="font-mono">{p95Worst.framework}</span>'s p95
              latency is{" "}
              <span className="text-red-600 dark:text-red-400">
                {(p95Worst.p95 / p95Worst.p50).toFixed(0)}× its p50
              </span>
              .
            </>
          }
          description={`${p95Worst.framework} runs ${p95Worst.p50.toFixed(1)}s on a typical trial and ${p95Worst.p95.toFixed(1)}s on its 95th percentile. One trial reached ${p95Worst.max.toFixed(0)}s — over twelve minutes on a task that usually takes twenty seconds.`}
        >
          <Callout title="Quick refresher: p50 and p95">
            <p>
              Sort the latencies of all trials from fastest to slowest. The{" "}
              <strong>p50 (median)</strong> is the middle value: half the trials
              are faster, half are slower. It describes what a typical user
              experiences. The <strong>p95</strong> is the value below which 95%
              of trials fall — meaning <strong>1 trial in 20 is slower</strong>.
              It describes the worst case that real users will still hit
              regularly.
            </p>
            <p className="mt-2">
              A framework with a good p50 but a bad p95 looks fast on average
              and intermittently freezes. A framework with both numbers close
              together is predictable. The gap between them — how far p95 is
              from p50 — is the more actionable signal than either column alone.
            </p>
          </Callout>
          <LatencyStripChart distribution={summary.latency_distribution} />
          <p>
            The strip plot above shows every valid trial as a dot. Most
            frameworks cluster tightly between 10s and 50s. Two — Google ADK
            and PydanticAI — have outliers past the 100-second mark, drawn in
            red. These aren't "the framework is slow"; they're "one trial
            stuck for ten minutes against a task that the same framework
            handles in twenty seconds the other 28 times".
          </p>
          <Callout title="Why this matters in production">
            <p>
              A user-facing agent product needs a client-side step timeout. A
              framework that doesn't expose one — or that swallows the timeout
              configuration — turns a latent upstream stall into a stuck
              request. The p95 column on the leaderboard tells you to set the
              timeout; the p50 column lies about how often you'll need it.
            </p>
          </Callout>
        </Section>

        {/* FINDING 4 — per-job heatmap */}
        <Section
          eyebrow="Finding 4 · Job-level breakdown"
          title="Failures cluster on specific job × framework pairs."
          description="The success-rate column averages over ten job categories. Some frameworks are uniformly reliable; others fail consistently on specific shapes of input."
        >
          <PerJobHeatmap data={summary.per_job_success} />
          <p>
            Each cell is a framework × job combination, three trials deep.
            Green is full pass, red is full fail. The pattern surfaces
            framework-specific weaknesses that the aggregate success rate
            obscures.
          </p>
          <Callout title="Patterns worth reading the table for">
            <ul className="list-disc space-y-1 pl-5">
              <li>
                <strong>Vercel AI SDK fails 0/3 on the DevOps / SRE remote
                role</strong> — the only red cell in its row, despite 100% on
                everything else. A specific class of input (long location string
                + many remote-related keywords) defeats its lean context
                handling.
              </li>
              <li>
                <strong>Baseline-python flakes on jobs 002, 003, 005, 006</strong>
                {" "}— without framework discipline, the manual loop hits its
                step ceiling on tasks that demand more exploration.
              </li>
              <li>
                <strong>job-001 (the simple Senior Python Backend) is 100% across the board</strong> —
                use it as your "smoke test" job before committing to a 30-trial run.
              </li>
            </ul>
          </Callout>
        </Section>
      </div>
    </main>
  );
}

/* ───── Layout primitives (mirrors /methodology) ───── */

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
      <div className="space-y-2">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {eyebrow}
        </div>
        <h2 className="text-balance text-2xl font-semibold tracking-tight md:text-3xl">
          {title}
        </h2>
        {description ? (
          <p className="text-pretty text-sm text-muted-foreground md:text-base">
            {description}
          </p>
        ) : null}
      </div>
      <div className="space-y-4 text-sm leading-relaxed text-foreground/90 md:text-[15px]">
        {children}
      </div>
    </section>
  );
}

function Callout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border/70 bg-muted/30 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      <div className="mt-2 text-sm leading-relaxed text-foreground/90">
        {children}
      </div>
    </div>
  );
}
