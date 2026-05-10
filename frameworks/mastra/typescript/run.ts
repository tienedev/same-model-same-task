/**
 * Mastra adapter — Agent with @ai-sdk/openai-compatible provider.
 *
 * Routes to Gemini via Google's OpenAI-compatible endpoint. Mastra wraps
 * Vercel AI SDK for providers; @ai-sdk/openai-compatible is the
 * documented way to target any OpenAI-shaped HTTP API.
 *
 * Usage:
 *   GEMINI_API_KEY=... bun run run.ts job-001
 */

import { Agent } from "@mastra/core/agent";
import { createTool } from "@mastra/core/tools";
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { z } from "zod";

import {
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

export async function run(jobId: string): Promise<RunResult> {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) throw new Error("GEMINI_API_KEY not set");

  const provider = createOpenAICompatible({
    name: "gemini-openai",
    apiKey,
    baseURL: GEMINI_OPENAI_BASE_URL,
  });

  const tools = {
    search_candidates: createTool({
      id: "search_candidates",
      description: SEARCH_CANDIDATES_DESC,
      inputSchema: z.object({
        query: z.string(),
        filters: z
          .object({
            min_years_experience: z.number().int().optional(),
            required_skills: z.array(z.string()).optional(),
            location: z.string().optional(),
            max_salary_eur: z.number().int().optional(),
          })
          .optional(),
      }),
      execute: async ({ query, filters }) => searchCandidates(query, filters),
    }),
    get_candidate_profile: createTool({
      id: "get_candidate_profile",
      description: GET_CANDIDATE_PROFILE_DESC,
      inputSchema: z.object({ candidate_id: z.string() }),
      execute: async ({ candidate_id }) => getCandidateProfile(candidate_id),
    }),
    score_match: createTool({
      id: "score_match",
      description: SCORE_MATCH_DESC,
      inputSchema: z.object({ candidate_id: z.string(), job_id: z.string() }),
      execute: async ({ candidate_id, job_id }) => scoreMatch(candidate_id, job_id),
    }),
    list_jobs: createTool({
      id: "list_jobs",
      description: LIST_JOBS_DESC,
      inputSchema: z.object({}),
      execute: async () => listJobs(),
    }),
  };

  const agent = new Agent({
    id: "recruitment-assistant",
    name: "Recruitment Assistant",
    instructions: SYSTEM_PROMPT,
    model: provider(MODEL_NAME),
    tools,
  });

  const t0 = performance.now();
  const result = await agent.generate(USER_PROMPT_TEMPLATE(jobId), {
    maxSteps: MAX_STEPS,
    providerOptions: { "gemini-openai": { temperature: 0 } },
  });

  const inTokens = result.usage?.inputTokens ?? 0;
  const outTokens = result.usage?.outputTokens ?? 0;
  let toolCalls = 0;
  for (const step of result.steps ?? []) {
    toolCalls += step.toolCalls?.length ?? 0;
  }

  return buildResult({
    framework: "mastra",
    jobId,
    model: MODEL_NAME,
    t0,
    inTokens,
    outTokens,
    toolCalls,
    finalText: result.text ?? "",
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
