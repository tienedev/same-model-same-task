import { ImageResponse } from "next/og";
import { summary } from "@/lib/stats";

export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "same-model-same-task — open benchmark of LLM agent frameworks";

export default async function OpengraphImage() {
  const totalRuns = summary.frameworks.reduce(
    (acc, f) => acc + f.count_total,
    0,
  );
  const totalValid = summary.frameworks.reduce(
    (acc, f) => acc + f.count_valid,
    0,
  );
  const trialsPer = Math.max(...summary.frameworks.map((f) => f.count_total));

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          padding: "80px",
          background: "linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%)",
          color: "#fafafa",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {/* Eyebrow */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            color: "#a3a3a3",
            fontSize: 18,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "#34d399",
            }}
          />
          Open benchmark · {summary.frameworks.length} frameworks
        </div>

        {/* Headline */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            marginTop: 40,
            fontSize: 76,
            fontWeight: 600,
            lineHeight: 1.05,
            letterSpacing: "-0.02em",
          }}
        >
          <div>Same model. Same task.</div>
          <div style={{ color: "#737373" }}>Which framework wins?</div>
        </div>

        {/* Sub */}
        <div
          style={{
            display: "flex",
            marginTop: 32,
            fontSize: 26,
            color: "#a3a3a3",
            maxWidth: 900,
            lineHeight: 1.3,
          }}
        >
          {summary.frameworks.length} LLM agent frameworks · gemini-2.5-flash ·
          same task, same 4 tools
        </div>

        {/* Stats strip */}
        <div
          style={{
            display: "flex",
            marginTop: "auto",
            gap: 80,
            fontSize: 22,
          }}
        >
          <Stat label="Frameworks" value={String(summary.frameworks.length)} />
          <Stat label="Trials each" value={String(trialsPer)} />
          <Stat label="Total runs" value={String(totalRuns)} />
          <Stat label="Valid" value={String(totalValid)} />
        </div>
      </div>
    ),
    { ...size },
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div
        style={{
          color: "#737373",
          fontSize: 16,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
      <div
        style={{
          marginTop: 8,
          fontSize: 56,
          fontWeight: 600,
          letterSpacing: "-0.02em",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {value}
      </div>
    </div>
  );
}
