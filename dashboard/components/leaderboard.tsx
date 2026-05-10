import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  frameworkLabel,
  frameworkLanguage,
  type FrameworkStats,
} from "@/lib/stats";

function fmt(value: number | null, digits: number = 1, prefix: string = ""): string {
  if (value === null) return "—";
  return `${prefix}${value.toFixed(digits)}`;
}

function fmtTokens(input: number | null, output: number | null): string {
  if (input === null || output === null) return "—";
  return `${input.toLocaleString()} / ${output.toLocaleString()}`;
}

function rankSortValue(stats: FrameworkStats): number {
  // Sort by NDCG@3 descending — deterministic IR scorer is the primary axis.
  // Frameworks without a score yet (n_scored=0 / null) drop to the bottom.
  // Negate so that higher = better still works with ascending .sort().
  return stats.mean_ndcg_at_3 === null ? Number.POSITIVE_INFINITY : -stats.mean_ndcg_at_3;
}

const rankBadgeStyles: Record<number, string> = {
  1: "bg-amber-100 text-amber-900 ring-amber-300/60 dark:bg-amber-400/10 dark:text-amber-300 dark:ring-amber-400/30",
  2: "bg-zinc-200 text-zinc-800 ring-zinc-300/60 dark:bg-zinc-300/10 dark:text-zinc-200 dark:ring-zinc-300/30",
  3: "bg-orange-100 text-orange-900 ring-orange-300/60 dark:bg-orange-400/10 dark:text-orange-300 dark:ring-orange-400/30",
};

function RankBadge({ rank, hasResult }: { rank: number; hasResult: boolean }) {
  if (!hasResult) {
    return (
      <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-muted text-[11px] font-medium text-muted-foreground ring-1 ring-inset ring-border">
        —
      </span>
    );
  }
  return (
    <span
      className={cn(
        "inline-flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-mono font-semibold ring-1 ring-inset",
        rankBadgeStyles[rank] ??
          "bg-muted text-muted-foreground ring-border",
      )}
    >
      {rank}
    </span>
  );
}

function LanguageBadge({ language }: { language: "Python" | "TypeScript" }) {
  const isPy = language === "Python";
  return (
    <Badge
      variant="outline"
      className={cn(
        "h-5 rounded font-mono text-[10px] tracking-wide uppercase",
        isPy
          ? "border-blue-500/30 bg-blue-500/5 text-blue-700 dark:text-blue-300"
          : "border-sky-500/30 bg-sky-500/5 text-sky-700 dark:text-sky-300",
      )}
    >
      {isPy ? "Py" : "TS"}
    </Badge>
  );
}

export function Leaderboard({ stats }: { stats: FrameworkStats[] }) {
  const ranked = [...stats].sort((a, b) => rankSortValue(a) - rankSortValue(b));

  const validCosts = ranked
    .map((s) => s.estimated_cost_usd_per_run)
    .filter((c): c is number => c !== null);
  const maxCost = validCosts.length > 0 ? Math.max(...validCosts) : 0;

  return (
    <div className="overflow-hidden rounded-xl border border-border/60">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            <TableHead className="w-12 text-center">#</TableHead>
            <TableHead>Framework</TableHead>
            <TableHead className="text-right">Valid</TableHead>
            <TableHead className="text-right">NDCG@3</TableHead>
            <TableHead className="text-right">Hit@1</TableHead>
            <TableHead className="text-right">p50 (s)</TableHead>
            <TableHead className="text-right">p95 (s)</TableHead>
            <TableHead className="text-right">Tokens (in / out)</TableHead>
            <TableHead className="text-right">Tools</TableHead>
            <TableHead className="text-right">Cost / run</TableHead>
            <TableHead className="text-right" title="Justification quality axis only (1–5). Judge /20 retired as primary signal — see README Scoring section.">JustifQ /5</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {ranked.map((s, i) => {
            const hasResult = s.mean_ndcg_at_3 !== null;
            const rank = i + 1;
            const lang = frameworkLanguage(s.framework);
            const cost = s.estimated_cost_usd_per_run;
            const costRatio =
              cost !== null && maxCost > 0 ? cost / maxCost : 0;
            return (
              <TableRow key={s.framework} className="group">
                <TableCell className="text-center">
                  <RankBadge rank={rank} hasResult={hasResult} />
                </TableCell>
                <TableCell>
                  <Link
                    href={`/${s.framework}`}
                    className="flex items-center gap-2 hover:underline"
                  >
                    <LanguageBadge language={lang} />
                    <span className="font-mono text-[13px] font-medium">
                      {frameworkLabel(s.framework)}
                    </span>
                  </Link>
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                  {s.count_valid}/{s.count_total}
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums font-medium">
                  {fmt(s.mean_ndcg_at_3, 3)}
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                  {s.hit_at_1_rate === null ? "—" : `${(s.hit_at_1_rate * 100).toFixed(1)}%`}
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                  {fmt(s.latency_p50)}
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                  {fmt(s.latency_p95)}
                </TableCell>
                <TableCell className="text-right font-mono text-muted-foreground">
                  {fmtTokens(s.mean_input_tokens, s.mean_output_tokens)}
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                  {fmt(s.mean_tool_calls)}
                </TableCell>
                <TableCell className="text-right">
                  <CostCell value={cost} ratio={costRatio} />
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums text-muted-foreground">
                  {fmt(s.mean_justification_quality, 2)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function CostCell({ value, ratio }: { value: number | null; ratio: number }) {
  if (value === null) {
    return <span className="font-mono tabular-nums text-muted-foreground">—</span>;
  }
  return (
    <div className="relative inline-flex min-w-[90px] items-center justify-end">
      <div
        aria-hidden
        className="absolute inset-y-0.5 right-0 -z-0 rounded-sm bg-foreground/[0.06]"
        style={{ width: `${Math.max(ratio * 100, 4)}%` }}
      />
      <span className="relative font-mono tabular-nums">
        ${value.toFixed(4)}
      </span>
    </div>
  );
}
