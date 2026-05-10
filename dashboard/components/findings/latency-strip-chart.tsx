"use client";

import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { LatencyDistribution } from "@/lib/stats";

const POINT_COLOR = "#3b82f6";
const OUTLIER_THRESHOLD = 100; // seconds; anything past is highlighted

interface Point {
  framework: string;
  elapsed: number;
}

interface PointPayload {
  payload: Point;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: PointPayload[];
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-background px-3 py-2 text-xs shadow-md">
      <div className="font-mono font-semibold">{p.framework}</div>
      <div className="text-muted-foreground">
        {p.elapsed.toFixed(1)}s
      </div>
    </div>
  );
}

/**
 * Per-trial latency strip plot with a log-scale x-axis. One row per framework,
 * one dot per valid trial. Outlier trials past 100s show in red so the
 * "1 stuck trial" pattern (Google ADK at 752s, PydanticAI at 638s) is
 * visible without reading any number.
 */
export function LatencyStripChart({
  distribution,
}: {
  distribution: LatencyDistribution[];
}) {
  // Y axis is categorical (framework name), but scatter charts want numeric.
  // Map each framework to an integer index, then render the YAxis with a
  // tickFormatter to display the name.
  const sortedFrameworks = [...distribution].sort(
    (a, b) => b.max - a.max,
  );

  const points: Array<Point & { fwIdx: number }> = [];
  sortedFrameworks.forEach((fw, idx) => {
    fw.values.forEach((v) => {
      points.push({
        framework: fw.framework,
        elapsed: v,
        fwIdx: idx,
      });
    });
  });

  return (
    <ResponsiveContainer width="100%" height={400}>
      <ScatterChart margin={{ top: 16, right: 24, bottom: 32, left: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          type="number"
          dataKey="elapsed"
          name="Elapsed"
          scale="log"
          domain={[8, 1000]}
          ticks={[10, 30, 100, 300, 1000]}
          tickFormatter={(v: number) => `${v}s`}
          stroke="var(--muted-foreground)"
          fontSize={11}
        />
        <YAxis
          type="number"
          dataKey="fwIdx"
          domain={[-0.5, sortedFrameworks.length - 0.5]}
          ticks={sortedFrameworks.map((_, i) => i)}
          tickFormatter={(idx: number) =>
            sortedFrameworks[idx]?.framework ?? ""
          }
          stroke="var(--muted-foreground)"
          fontSize={11}
          width={140}
        />
        <ZAxis range={[60, 60]} />
        <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: "3 3" }} />
        <Scatter
          data={points.filter((p) => p.elapsed <= OUTLIER_THRESHOLD)}
          fill={POINT_COLOR}
          fillOpacity={0.5}
        />
        <Scatter
          data={points.filter((p) => p.elapsed > OUTLIER_THRESHOLD)}
          fill="#dc2626"
          fillOpacity={0.85}
        />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
