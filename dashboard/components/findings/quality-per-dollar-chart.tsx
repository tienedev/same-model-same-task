"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FrameworkStats } from "@/lib/stats";

interface Datum {
  framework: string;
  qpd: number;
  judgeScore: number;
  cost: number;
}

const TOP_COLOR = "#10b981"; // green
const MID_COLOR = "#3b82f6"; // blue
const LOW_COLOR = "#f59e0b"; // amber
const OUTLIER_LOW = "#dc2626"; // red — pareto-dominated

export function QualityPerDollarChart({ stats }: { stats: FrameworkStats[] }) {
  const data: Datum[] = stats
    .filter(
      (s) =>
        s.mean_judge_score !== null && s.estimated_cost_usd_per_run !== null,
    )
    .map((s) => ({
      framework: s.framework,
      qpd: (s.mean_judge_score as number) / (s.estimated_cost_usd_per_run as number),
      judgeScore: s.mean_judge_score as number,
      cost: s.estimated_cost_usd_per_run as number,
    }))
    .sort((a, b) => b.qpd - a.qpd);

  if (data.length === 0) return null;

  const top = data[0].qpd;
  const bottom = data[data.length - 1].qpd;

  const colorFor = (qpd: number): string => {
    if (qpd === top) return TOP_COLOR;
    if (qpd === bottom) return OUTLIER_LOW;
    if (qpd > top * 0.5) return MID_COLOR;
    return LOW_COLOR;
  };

  return (
    <ResponsiveContainer width="100%" height={360}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 8, right: 96, bottom: 8, left: 24 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          type="number"
          tickFormatter={(v: number) => v.toFixed(0)}
          stroke="var(--muted-foreground)"
          fontSize={11}
          label={{
            value: "Judge points per USD",
            position: "insideBottom",
            offset: -4,
            fontSize: 11,
            fill: "var(--muted-foreground)",
          }}
        />
        <YAxis
          type="category"
          dataKey="framework"
          width={140}
          fontSize={12}
          stroke="var(--muted-foreground)"
        />
        <Tooltip
          contentStyle={{
            background: "var(--background)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            fontSize: 12,
          }}
          formatter={(value, name, item) => {
            if (name === "qpd" && typeof value === "number") {
              const d = item.payload as Datum;
              return [
                `${value.toFixed(0)} pts/$ (${d.judgeScore.toFixed(2)}/20 ÷ $${d.cost.toFixed(4)})`,
                "Quality per dollar",
              ];
            }
            return [String(value), name];
          }}
        />
        <Bar dataKey="qpd" name="qpd">
          {data.map((d) => (
            <Cell key={d.framework} fill={colorFor(d.qpd)} />
          ))}
          <LabelList
            dataKey="qpd"
            position="right"
            formatter={(v) =>
              typeof v === "number" ? v.toFixed(0) : String(v ?? "")
            }
            fontSize={11}
            fill="var(--foreground)"
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
