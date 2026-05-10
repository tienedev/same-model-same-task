"use client";

import {
  Bar,
  BarChart as RechartsBar,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FrameworkStats } from "@/lib/stats";

const INPUT_COLOR = "#2563eb"; // blue — input/incoming
const OUTPUT_COLOR = "#f59e0b"; // amber — output/outgoing

export function TokensStackChart({ stats }: { stats: FrameworkStats[] }) {
  const data = stats
    .filter((s) => s.mean_input_tokens !== null && s.mean_output_tokens !== null)
    .map((s) => ({
      framework: s.framework,
      Input: s.mean_input_tokens as number,
      Output: s.mean_output_tokens as number,
    }));

  return (
    <ResponsiveContainer width="100%" height={288}>
      <RechartsBar data={data} margin={{ top: 16, right: 24, bottom: 60, left: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="framework"
          angle={-30}
          textAnchor="end"
          height={60}
          fontSize={11}
          stroke="var(--muted-foreground)"
          interval={0}
        />
        <YAxis
          stroke="var(--muted-foreground)"
          fontSize={11}
          tickFormatter={(v: number) => v.toLocaleString()}
        />
        <Tooltip
          contentStyle={{
            background: "var(--background)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            fontSize: 12,
          }}
          formatter={(value) => (typeof value === "number" ? value.toLocaleString() : String(value))}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="Input" stackId="tokens" fill={INPUT_COLOR} />
        <Bar dataKey="Output" stackId="tokens" fill={OUTPUT_COLOR} />
      </RechartsBar>
    </ResponsiveContainer>
  );
}
