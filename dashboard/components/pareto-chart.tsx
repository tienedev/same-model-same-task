"use client";

import {
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart as RechartsScatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FrameworkStats } from "@/lib/stats";

// One distinct hue per framework. Order is alphabetical to match
// summary.frameworks ordering, so colors stay stable across renders.
const FRAMEWORK_COLORS = [
  "#2563eb", // blue
  "#06b6d4", // cyan
  "#10b981", // emerald
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#ec4899", // pink
  "#f97316", // orange
  "#84cc16", // lime
];

interface Point {
  framework: string;
  cost: number;
  quality: number;
}

interface PointPayload {
  payload: Point;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: PointPayload[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-background px-3 py-2 text-xs shadow-md">
      <div className="font-mono font-semibold">{p.framework}</div>
      <div className="text-muted-foreground">
        Cost: <span className="font-mono text-foreground">${p.cost.toFixed(4)}</span>
      </div>
      <div className="text-muted-foreground">
        NDCG@3: <span className="font-mono text-foreground">{p.quality.toFixed(3)}</span>
      </div>
    </div>
  );
}

export function ParetoChart({ stats }: { stats: FrameworkStats[] }) {
  const data: Point[] = stats
    .filter(
      (s) =>
        s.estimated_cost_usd_per_run !== null && s.mean_ndcg_at_3 !== null,
    )
    .map((s) => ({
      framework: s.framework,
      cost: s.estimated_cost_usd_per_run as number,
      quality: s.mean_ndcg_at_3 as number,
    }));

  return (
    <div className="space-y-3">
      <ResponsiveContainer width="100%" height={288}>
        <RechartsScatter margin={{ top: 16, right: 24, bottom: 24, left: 24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            type="number"
            dataKey="cost"
            name="Cost (USD/run)"
            tickFormatter={(v: number) => `$${v.toFixed(4)}`}
            stroke="var(--muted-foreground)"
            fontSize={11}
          />
          <YAxis
            type="number"
            dataKey="quality"
            name="NDCG@3"
            domain={[0, 1]}
            tickFormatter={(v: number) => v.toFixed(2)}
            stroke="var(--muted-foreground)"
            fontSize={11}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={data}>
            {data.map((d, i) => (
              <Cell key={d.framework} fill={FRAMEWORK_COLORS[i % FRAMEWORK_COLORS.length]} />
            ))}
          </Scatter>
        </RechartsScatter>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {data.map((d, i) => (
          <div key={d.framework} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: FRAMEWORK_COLORS[i % FRAMEWORK_COLORS.length] }}
            />
            <span className="font-mono text-muted-foreground">{d.framework}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
