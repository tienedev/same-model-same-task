import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Leaderboard } from "@/components/leaderboard";
import { ParetoChart } from "@/components/pareto-chart";
import { TokensStackChart } from "@/components/tokens-stack-chart";
import { summary } from "@/lib/stats";

function formatGenerated(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "UTC",
      timeZoneName: "short",
    });
  } catch {
    return iso;
  }
}

export default function Home() {
  const totalRuns = summary.frameworks.reduce(
    (acc, f) => acc + f.count_total,
    0,
  );
  const trialsPerFramework = Math.max(
    ...summary.frameworks.map((f) => f.count_total),
    0,
  );

  return (
    <main className="container mx-auto px-4 pb-16">
      {/* HERO */}
      <section className="border-b border-border/60 py-14 md:py-20">
        <div className="max-w-3xl space-y-5">
          <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-muted/40 px-3 py-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            Open benchmark · {summary.frameworks.length} frameworks
          </div>
          <h1 className="text-balance text-4xl font-semibold tracking-tight md:text-5xl">
            Same model. Same task.{" "}
            <span className="text-muted-foreground">
              Which framework wins?
            </span>
          </h1>
          <p className="max-w-2xl text-pretty text-base text-muted-foreground md:text-lg">
            A controlled comparison of {summary.frameworks.length} LLM agent
            frameworks running the same candidate-job matching task on{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em]">
              gemini-2.5-flash
            </code>{" "}
            with the same 4 tools. Only the framework varies.
          </p>
        </div>

        {/* KPI STRIP */}
        <dl className="mt-10 grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-border md:grid-cols-4">
          <Kpi label="Frameworks tested" value={String(summary.frameworks.length)} />
          <Kpi
            label="Trials per framework"
            value={String(trialsPerFramework)}
            hint={`${totalRuns} runs total`}
          />
          <Kpi label="Model" value="gemini-2.5-flash" mono />
          <Kpi
            label="Generated"
            value={formatGenerated(summary.metadata.generated_at)}
            mono
          />
        </dl>
      </section>

      {/* LEADERBOARD */}
      <section className="space-y-4 pt-12">
        <SectionHeader
          eyebrow="Leaderboard"
          title="Frameworks ranked by latency p50"
          description={`Lower is faster. Frameworks with no valid runs sort last. Pricing: $${summary.metadata.pricing_usd_per_m_tokens.in_per_m}/M input · $${summary.metadata.pricing_usd_per_m_tokens.out_per_m}/M output tokens.`}
        />
        <Leaderboard stats={summary.frameworks} />
      </section>

      {/* CHARTS */}
      <section className="space-y-4 pt-16">
        <SectionHeader
          eyebrow="Trade-offs"
          title="Cost, quality, and token mix"
          description="Pareto frontier (quality vs cost) and stacked input/output tokens per valid run."
        />
        <div className="grid gap-6 md:grid-cols-2">
          <Card className="rounded-xl">
            <CardHeader>
              <CardTitle>Cost vs Judge score</CardTitle>
              <p className="text-xs text-muted-foreground">
                Upper-left is better — higher quality per dollar spent.
              </p>
            </CardHeader>
            <CardContent className="pb-4">
              <ParetoChart stats={summary.frameworks} />
            </CardContent>
          </Card>
          <Card className="rounded-xl">
            <CardHeader>
              <CardTitle>Tokens (input / output, stacked)</CardTitle>
              <p className="text-xs text-muted-foreground">
                Mean per valid run.
              </p>
            </CardHeader>
            <CardContent className="pb-4">
              <TokensStackChart stats={summary.frameworks} />
            </CardContent>
          </Card>
        </div>
      </section>
    </main>
  );
}

function Kpi({
  label,
  value,
  hint,
  mono = false,
}: {
  label: string;
  value: string;
  hint?: string;
  mono?: boolean;
}) {
  return (
    <div className="bg-background p-5">
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={
          mono
            ? "mt-1.5 truncate font-mono text-sm font-medium tabular-nums md:text-[15px]"
            : "mt-1.5 text-2xl font-semibold tracking-tight tabular-nums"
        }
        title={value}
      >
        {value}
      </div>
      {hint ? (
        <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
      ) : null}
    </div>
  );
}

function SectionHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="space-y-1">
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {eyebrow}
      </div>
      <h2 className="text-xl font-semibold tracking-tight md:text-2xl">
        {title}
      </h2>
      {description ? (
        <p className="max-w-3xl text-sm text-muted-foreground">{description}</p>
      ) : null}
    </div>
  );
}
