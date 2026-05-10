import Link from "next/link";

const FRAMEWORK_FINDINGS: Record<
  string,
  Array<{ section: string; label: string }>
> = {
  "crewai": [
    { section: "finding-1", label: "Token cost — the 27× outlier" },
    { section: "finding-2", label: "Efficiency frontier — Pareto-dominated" },
  ],
  "google-adk": [
    { section: "finding-3", label: "p95 latency outliers" },
  ],
  "vercel-ai-sdk": [
    { section: "finding-1", label: "Token cost — the lean baseline" },
    { section: "finding-2", label: "Efficiency frontier — top quality-per-dollar" },
    { section: "finding-4", label: "Per-job breakdown — fails on job-006" },
  ],
};

export function FrameworkFindingsCallout({ framework }: { framework: string }) {
  const items = FRAMEWORK_FINDINGS[framework];
  if (!items || items.length === 0) return null;

  return (
    <section className="pt-8">
      <aside className="rounded-xl border border-border/60 bg-muted/30 p-4">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          Discussed in /findings
        </div>
        <ul className="mt-2 space-y-1 text-sm">
          {items.map((item) => (
            <li key={item.section}>
              <Link
                href={`/findings#${item.section}`}
                className="text-foreground/90 underline decoration-muted-foreground/40 underline-offset-2 transition-colors hover:decoration-foreground"
              >
                {item.label}
              </Link>
              <span className="ml-1 text-muted-foreground">→</span>
            </li>
          ))}
        </ul>
      </aside>
    </section>
  );
}
