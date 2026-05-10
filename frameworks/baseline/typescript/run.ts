/**
 * Baseline (no framework): raw openai SDK + manual tool-calling loop.
 *
 * Routes to Gemini via Google's OpenAI-compatible endpoint.
 *
 * Usage:
 *   GEMINI_API_KEY=... bun run run.ts job-001
 */

import OpenAI from "openai";

import {
  FORCE_FINAL_PROMPT,
  GEMINI_OPENAI_BASE_URL,
  GET_CANDIDATE_PROFILE_DESC,
  LIST_JOBS_DESC,
  MAX_STEPS,
  MODEL_NAME,
  type RunResult,
  SCORE_MATCH_DESC,
  SEARCH_CANDIDATES_DESC,
  SYSTEM_PROMPT,
  USER_PROMPT_TEMPLATE,
  buildResult,
} from "../../_shared/typescript/index.ts";

import {
  getCandidateProfile,
  listJobs,
  scoreMatch,
  searchCandidates,
} from "../../../tools/typescript/src/tools.ts";

const TOOL_FUNCTIONS: Record<string, (args: Record<string, unknown>) => unknown> = {
  search_candidates: (a) =>
    searchCandidates(a.query as string, a.filters as Parameters<typeof searchCandidates>[1]),
  get_candidate_profile: (a) => getCandidateProfile(a.candidate_id as string),
  score_match: (a) => scoreMatch(a.candidate_id as string, a.job_id as string),
  list_jobs: () => listJobs(),
};

const TOOL_DECLARATIONS: OpenAI.Chat.Completions.ChatCompletionTool[] = [
  {
    type: "function",
    function: {
      name: "search_candidates",
      description: SEARCH_CANDIDATES_DESC,
      parameters: {
        type: "object",
        properties: {
          query: { type: "string" },
          filters: {
            type: "object",
            properties: {
              min_years_experience: { type: "integer" },
              required_skills: { type: "array", items: { type: "string" } },
              location: { type: "string" },
              max_salary_eur: { type: "integer" },
            },
          },
        },
        required: ["query"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "get_candidate_profile",
      description: GET_CANDIDATE_PROFILE_DESC,
      parameters: {
        type: "object",
        properties: { candidate_id: { type: "string" } },
        required: ["candidate_id"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "score_match",
      description: SCORE_MATCH_DESC,
      parameters: {
        type: "object",
        properties: {
          candidate_id: { type: "string" },
          job_id: { type: "string" },
        },
        required: ["candidate_id", "job_id"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "list_jobs",
      description: LIST_JOBS_DESC,
      parameters: { type: "object", properties: {} },
    },
  },
];

function executeTool(name: string, args: Record<string, unknown>): unknown {
  const fn = TOOL_FUNCTIONS[name];
  if (!fn) return { error: `unknown tool: ${name}` };
  try {
    return fn(args);
  } catch (e) {
    return { error: `${(e as Error).name}: ${(e as Error).message}` };
  }
}

export async function run(jobId: string): Promise<RunResult> {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) throw new Error("GEMINI_API_KEY not set");

  // 10-minute timeout per request (default is 10 min on Python httpx but
  // 10 min on Node openai-node yet seems shorter under bun for complex jobs;
  // explicit override eliminates spurious APIConnectionTimeoutError).
  const client = new OpenAI({
    apiKey,
    baseURL: GEMINI_OPENAI_BASE_URL,
    timeout: 600_000,
    maxRetries: 2,
  });
  const messages: OpenAI.Chat.Completions.ChatCompletionMessageParam[] = [
    { role: "system", content: SYSTEM_PROMPT },
    { role: "user", content: USER_PROMPT_TEMPLATE(jobId) },
  ];

  let inTokens = 0;
  let outTokens = 0;
  let toolCalls = 0;
  let hitStepLimit = false;
  let finalText = "";

  const t0 = performance.now();
  for (let step = 0; step < MAX_STEPS; step++) {
    const response = await client.chat.completions.create({
      model: MODEL_NAME,
      messages,
      tools: TOOL_DECLARATIONS,
      temperature: 0,
    });

    if (response.usage) {
      inTokens += response.usage.prompt_tokens ?? 0;
      outTokens += response.usage.completion_tokens ?? 0;
    }

    const msg = response.choices[0]?.message;
    if (!msg) break;
    messages.push(msg);

    if (!msg.tool_calls || msg.tool_calls.length === 0) {
      finalText = msg.content ?? "";
      break;
    }

    for (const tc of msg.tool_calls) {
      if (tc.type !== "function") continue;
      toolCalls += 1;
      let args: Record<string, unknown> = {};
      try {
        args = JSON.parse(tc.function.arguments || "{}") as Record<string, unknown>;
      } catch {
        // ignore malformed args
      }
      const result = executeTool(tc.function.name, args);
      messages.push({
        role: "tool",
        tool_call_id: tc.id,
        content: JSON.stringify(result),
      });
    }

    if (step === MAX_STEPS - 1) hitStepLimit = true;
  }

  if (hitStepLimit && !finalText) {
    messages.push({ role: "user", content: FORCE_FINAL_PROMPT });
    const response = await client.chat.completions.create({
      model: MODEL_NAME,
      messages,
      temperature: 0,
    });
    if (response.usage) {
      inTokens += response.usage.prompt_tokens ?? 0;
      outTokens += response.usage.completion_tokens ?? 0;
    }
    finalText = response.choices[0]?.message.content ?? "";
  }

  return buildResult({
    framework: "baseline-typescript",
    jobId,
    model: MODEL_NAME,
    t0,
    inTokens,
    outTokens,
    toolCalls,
    finalText,
    hitStepLimit,
  });
}

if (import.meta.main) {
  const jobId = process.argv[2];
  if (!jobId) {
    console.error("usage: bun run run.ts <job_id>");
    process.exit(1);
  }
  console.log(JSON.stringify(await run(jobId), null, 2));
}
