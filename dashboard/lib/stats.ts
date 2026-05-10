import summaryData from "@/data/summary.json";

export interface FrameworkStats {
  framework: string;
  count_total: number;
  count_valid: number;
  success_rate: number;
  latency_p50: number | null;
  latency_p95: number | null;
  latency_mean: number | null;
  latency_max: number | null;
  mean_input_tokens: number | null;
  mean_output_tokens: number | null;
  mean_tool_calls: number | null;
  estimated_cost_usd_per_run: number | null;
  hit_step_limit_rate: number | null;
  mean_judge_score: number | null;
  judge_n: number;
}

export interface Summary {
  metadata: {
    generated_at: string;
    n_frameworks: number;
    pricing_usd_per_m_tokens: { in_per_m: number; out_per_m: number };
  };
  frameworks: FrameworkStats[];
}

export const summary = summaryData as Summary;

const PYTHON_FRAMEWORKS = new Set([
  "baseline-python",
  "crewai",
  "google-adk",
  "langgraph",
  "pydantic-ai",
]);

const TYPESCRIPT_FRAMEWORKS = new Set([
  "baseline-typescript",
  "mastra",
  "vercel-ai-sdk",
]);

export function frameworkLanguage(framework: string): "Python" | "TypeScript" {
  if (PYTHON_FRAMEWORKS.has(framework)) return "Python";
  if (TYPESCRIPT_FRAMEWORKS.has(framework)) return "TypeScript";
  // Fallback heuristic: anything ending in -typescript or starting with mastra/vercel
  return framework.endsWith("-typescript") ? "TypeScript" : "Python";
}

const FRAMEWORK_LABELS: Record<string, string> = {
  "baseline-python": "baseline-python",
  "baseline-typescript": "baseline-typescript",
  "crewai": "crewai",
  "google-adk": "google-adk",
  "langgraph": "langgraph",
  "mastra": "mastra",
  "pydantic-ai": "pydantic-ai",
  "vercel-ai-sdk": "vercel-ai-sdk",
};

export function frameworkLabel(framework: string): string {
  return FRAMEWORK_LABELS[framework] ?? framework;
}

const FRAMEWORK_PATTERNS: Record<string, string> = {
  "baseline-python": "Hand-rolled tool loop",
  "baseline-typescript": "Hand-rolled tool loop",
  "crewai": "Agent + Task + Crew",
  "google-adk": "LlmAgent (LiteLlm wrapper)",
  "langgraph": "StateGraph + MessagesState",
  "mastra": "Mastra Agent",
  "pydantic-ai": "Agent + @agent.tool_plain",
  "vercel-ai-sdk": "ToolLoopAgent",
};

export function frameworkPattern(framework: string): string | null {
  return FRAMEWORK_PATTERNS[framework] ?? null;
}
