"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FrameworkStats } from "@/lib/stats";

const HIGHLIGHT_COLOR = "#dc2626"; // red — the outlier
const NEUTRAL_COLOR = "#3b82f6"; // blue — normal range
const FRUGAL_COLOR = "#10b981"; // green — efficient

interface Datum {
  framework: string;
  input: number;
  output: number;
}

export function TokenBreakdownChart({ stats }: { stats: FrameworkStats[] }) {
  const data: Datum[] = stats
    .filter(
      (s) =>
        s.mean_input_tokens !== null && s.mean_output_tokens !== null,
    )
    .map((s) => ({
      framework: s.framework,
      input: s.mean_input_tokens as number,
      output: s.mean_output_tokens as number,
    }))
    .sort((a, b) => b.input - a.input);

  const maxInput = Math.max(...data.map((d) => d.input));

  return (
    <ResponsiveContainer width="100%" height={360}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 8, right: 64, bottom: 8, left: 24 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          type="number"
          tickFormatter={(v: number) => v.toLocaleString()}
          stroke="var(--muted-foreground)"
          fontSize={11}
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
          formatter={(value, name) =>
            typeof value === "number"
              ? [`${value.toLocaleString()} tokens`, name]
              : [String(value), name]
          }
        />
        <Bar dataKey="input" name="Input tokens" stackId="t">
          {data.map((d) => (
            <Cell
              key={d.framework}
              fill={
                d.input === maxInput
                  ? HIGHLIGHT_COLOR
                  : d.input < 2000
                    ? FRUGAL_COLOR
                    : NEUTRAL_COLOR
              }
            />
          ))}
        </Bar>
        <Bar
          dataKey="output"
          name="Output tokens"
          stackId="t"
          fill="var(--muted-foreground)"
          fillOpacity={0.4}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
