/**
 * Shared result schema + builder for adapter `run()` functions.
 * Mirrors frameworks/_shared/python/result.py.
 */

import { parseFinalJson } from "./output.ts";

export interface RunResult {
  framework: string;
  job_id: string;
  model: string;
  elapsed_s: number;
  input_tokens: number;
  output_tokens: number;
  tool_calls: number | null;
  hit_step_limit?: boolean;
  raw_output: string;
  parsed_output: unknown | null;
  parse_error: string | null;
}

interface BuildArgs {
  framework: string;
  jobId: string;
  model: string;
  t0: number;
  inTokens: number;
  outTokens: number;
  toolCalls: number | null;
  finalText: string;
  hitStepLimit?: boolean;
}

export function buildResult(args: BuildArgs): RunResult {
  const { parsed, error } = parseFinalJson(args.finalText);
  return {
    framework: args.framework,
    job_id: args.jobId,
    model: args.model,
    elapsed_s: Math.round((performance.now() - args.t0)) / 1000,
    input_tokens: args.inTokens,
    output_tokens: args.outTokens,
    tool_calls: args.toolCalls,
    hit_step_limit: args.hitStepLimit,
    raw_output: args.finalText,
    parsed_output: parsed,
    parse_error: error,
  };
}
