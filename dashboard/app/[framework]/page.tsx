import type { Metadata } from "next";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  frameworkLabel,
  frameworkLanguage,
  frameworkPattern,
  summary,
} from "@/lib/stats";
import { notFound } from "next/navigation";
import { cn } from "@/lib/utils";

export function generateStaticParams() {
  return summary.frameworks.map((s) => ({ framework: s.framework }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ framework: string }>;
}): Promise<Metadata> {
  const { framework } = await params;
  const stats = summary.frameworks.find((s) => s.framework === framework);
  if (!stats) return {};
  const label = frameworkLabel(framework);
  const lang = frameworkLanguage(framework);
  return {
    title: label,
    description: `${label} (${lang}) on the same-model-same-task bench: ${stats.count_valid}/${stats.count_total} valid runs against gemini-2.5-flash.`,
  };
}

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

export default async function Page({
  params,
}: {
  params: Promise<{ framework: string }>;
}) {
  const { framework } = await params;
  const stats = summary.frameworks.find((s) => s.framework === framework);
  if (!stats) notFound();

  const language = frameworkLanguage(framework);
  const pattern = frameworkPattern(framework);
  const successPct = (stats.success_rate * 100).toFixed(0);
  const noResults = stats.count_valid === 0;

  return (
    <main className="container mx-auto px-4 pb-16">
      {/* HEADER */}
      <section className="space-y-5 border-b border-border/60 py-10">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
        >
          <span aria-hidden>←</span> Back to leaderboard
        </Link>
        <div className="flex flex-col gap-3">
          <h1 className="font-mono text-3xl font-semibold tracking-tight md:text-4xl">
            {stats.framework}
          </h1>
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant="outline"
              className="h-5 rounded font-mono text-[10px] uppercase tracking-wide"
            >
              {language === "Python" ? "Python" : "TypeScript"}
            </Badge>
            {pattern ? (
              <span className="text-sm text-muted-foreground">{pattern}</span>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>
              Model:{" "}
              <code className="font-mono">gemini-2.5-flash</code>
            </span>
            <span className="hidden sm:inline">·</span>
            <span>
              Generated:{" "}
              <code className="font-mono">
                {formatGenerated(summary.metadata.generated_at)}
              </code>
            </span>
          </div>
        </div>
      </section>

      {/* KPIs */}
      <section className="pt-8">
        {noResults ? (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-900 dark:text-amber-200">
            No valid runs for this framework on the current dataset. Metrics
            below are unavailable.
          </div>
        ) : null}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Stat
            label="Judge score"
            value={
              stats.mean_judge_score === null
                ? "—"
                : `${stats.mean_judge_score.toFixed(2)}/20`
            }
            sub={
              stats.mean_judge_score === null
                ? `${stats.count_valid}/${stats.count_total} valid`
                : `${stats.judge_n} judged · ${stats.count_valid}/${stats.count_total} valid`
            }
          />
          <Stat
            label="Latency p50"
            value={
              stats.latency_p50 === null ? "—" : `${stats.latency_p50.toFixed(1)}s`
            }
            sub={
              stats.latency_p95 === null
                ? undefined
                : `p95 ${stats.latency_p95.toFixed(1)}s`
            }
          />
          <Stat
            label="Mean tokens"
            value={
              stats.mean_input_tokens === null ||
              stats.mean_output_tokens === null
                ? "—"
                : `${(stats.mean_input_tokens + stats.mean_output_tokens).toLocaleString()}`
            }
            sub={
              stats.mean_input_tokens === null ||
              stats.mean_output_tokens === null
                ? undefined
                : `${stats.mean_input_tokens.toLocaleString()} in · ${stats.mean_output_tokens.toLocaleString()} out`
            }
          />
          <Stat
            label="Cost / run"
            value={
              stats.estimated_cost_usd_per_run === null
                ? "—"
                : `$${stats.estimated_cost_usd_per_run.toFixed(4)}`
            }
            sub={
              stats.mean_tool_calls === null
                ? undefined
                : `${stats.mean_tool_calls.toFixed(1)} avg tool calls`
            }
          />
        </div>
      </section>

      {/* DETAIL TABLE */}
      <section className="pt-12">
        <h2 className="mb-4 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          All metrics
        </h2>
        <div className="overflow-hidden rounded-xl border border-border/60 divide-y divide-border/60">
          <DetailRow label="count_total" value={String(stats.count_total)} />
          <DetailRow label="count_valid" value={String(stats.count_valid)} />
          <DetailRow
            label="success_rate"
            value={`${(stats.success_rate * 100).toFixed(1)}%`}
          />
          <DetailRow
            label="latency_p50"
            value={fmt(stats.latency_p50, 3, "", "s")}
          />
          <DetailRow
            label="latency_p95"
            value={fmt(stats.latency_p95, 3, "", "s")}
          />
          <DetailRow
            label="latency_mean"
            value={fmt(stats.latency_mean, 3, "", "s")}
          />
          <DetailRow
            label="latency_max"
            value={fmt(stats.latency_max, 3, "", "s")}
          />
          <DetailRow
            label="mean_input_tokens"
            value={
              stats.mean_input_tokens === null
                ? "—"
                : stats.mean_input_tokens.toLocaleString()
            }
          />
          <DetailRow
            label="mean_output_tokens"
            value={
              stats.mean_output_tokens === null
                ? "—"
                : stats.mean_output_tokens.toLocaleString()
            }
          />
          <DetailRow
            label="mean_tool_calls"
            value={fmt(stats.mean_tool_calls, 2)}
          />
          <DetailRow
            label="estimated_cost_usd_per_run"
            value={fmt(stats.estimated_cost_usd_per_run, 6, "$")}
          />
          <DetailRow
            label="mean_judge_score"
            value={fmt(stats.mean_judge_score, 2, "", "/20")}
          />
          <DetailRow
            label="judge_n"
            value={String(stats.judge_n)}
          />
          <DetailRow
            label="hit_step_limit_rate"
            value={
              stats.hit_step_limit_rate === null
                ? "—"
                : `${(stats.hit_step_limit_rate * 100).toFixed(1)}%`
            }
          />
        </div>
      </section>
    </main>
  );
}

function fmt(
  v: number | null,
  digits: number = 1,
  prefix: string = "",
  suffix: string = "",
): string {
  if (v === null) return "—";
  return `${prefix}${v.toFixed(digits)}${suffix}`;
}

function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-xl border border-border/60 p-4">
      <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          "mt-1.5 font-mono text-2xl font-semibold tracking-tight tabular-nums",
        )}
      >
        {value}
      </div>
      {sub ? (
        <div className="mt-1 font-mono text-xs text-muted-foreground tabular-nums">
          {sub}
        </div>
      ) : null}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-2 px-4 py-2.5 text-sm">
      <div className="font-mono text-xs text-muted-foreground">{label}</div>
      <div className="text-right font-mono tabular-nums">{value}</div>
    </div>
  );
}
