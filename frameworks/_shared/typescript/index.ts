/**
 * Shared constants + helpers for TS framework adapters.
 * Mirrors frameworks/_shared/python/ exactly so behavior stays identical.
 */

export { MODEL_NAME, MAX_STEPS, GEMINI_OPENAI_BASE_URL } from "./config.ts";
export { SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, FORCE_FINAL_PROMPT } from "./prompts.ts";
export {
  SEARCH_CANDIDATES_DESC,
  GET_CANDIDATE_PROFILE_DESC,
  SCORE_MATCH_DESC,
  LIST_JOBS_DESC,
} from "./tool_descriptions.ts";
export { parseFinalJson } from "./output.ts";
export { type RunResult, buildResult } from "./result.ts";
