import type { PerJobSuccess } from "@/lib/stats";

const JOB_TITLES: Record<string, string> = {
  "job-001": "Senior Backend (Py)",
  "job-002": "Mid Backend (Node)",
  "job-003": "Senior FE (React)",
  "job-004": "Senior Full-Stack",
  "job-005": "ML Engineer",
  "job-006": "DevOps / SRE",
  "job-007": "Senior iOS",
  "job-008": "Product Designer",
  "job-009": "Staff FS Remote",
  "job-010": "Junior Backend (Py)",
};

function colorFor(rate: number): string {
  if (rate >= 1.0) return "bg-emerald-500/80 text-white";
  if (rate >= 2 / 3) return "bg-emerald-300/60 text-emerald-950";
  if (rate >= 1 / 3) return "bg-amber-400/70 text-amber-950";
  if (rate > 0) return "bg-orange-500/70 text-white";
  return "bg-red-600/80 text-white";
}

export function PerJobHeatmap({
  data,
}: {
  data: PerJobSuccess[];
}) {
  const frameworks = [...new Set(data.map((d) => d.framework))].sort();
  const jobs = [...new Set(data.map((d) => d.job_id))].sort();

  const lookup = new Map<string, PerJobSuccess>();
  for (const d of data) lookup.set(`${d.framework}|${d.job_id}`, d);

  return (
    <div className="overflow-x-auto">
      <table className="border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th className="sticky left-0 z-10 bg-background pr-3 text-right font-normal text-muted-foreground" />
            {jobs.map((job) => (
              <th
                key={job}
                className="px-1 pb-2 align-bottom font-mono font-normal text-muted-foreground"
              >
                <div className="flex flex-col items-center">
                  <span className="text-[10px]">{job.replace("job-", "#")}</span>
                  <span
                    className="mt-1 max-w-[60px] truncate text-[9px] text-muted-foreground/60"
                    title={JOB_TITLES[job] ?? job}
                  >
                    {(JOB_TITLES[job] ?? job).split(" ").slice(0, 2).join(" ")}
                  </span>
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {frameworks.map((fw) => (
            <tr key={fw}>
              <td className="sticky left-0 z-10 whitespace-nowrap bg-background pr-3 text-right font-mono">
                {fw}
              </td>
              {jobs.map((job) => {
                const cell = lookup.get(`${fw}|${job}`);
                const rate = cell?.success_rate ?? 0;
                const trials = cell?.n_trials ?? 0;
                const passed = Math.round(rate * trials);
                return (
                  <td
                    key={job}
                    className={`h-9 w-12 rounded text-center font-mono text-[11px] tabular-nums ${colorFor(
                      rate,
                    )}`}
                    title={`${fw} on ${JOB_TITLES[job] ?? job}: ${passed}/${trials} valid`}
                  >
                    {passed}/{trials}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-[10px] text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="size-3 rounded bg-emerald-500/80" /> 3/3 valid
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-3 rounded bg-emerald-300/60" /> 2/3
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-3 rounded bg-amber-400/70" /> 1/3
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-3 rounded bg-red-600/80" /> 0/3
        </span>
      </div>
    </div>
  );
}
