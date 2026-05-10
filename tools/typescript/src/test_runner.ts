/**
 * Test runner: same fixtures as scripts/test_tools_parity.py.
 * Outputs JSON array to stdout for parity check.
 */

import {
  getCandidateProfile,
  listJobs,
  scoreMatch,
  searchCandidates,
} from "./tools.ts";

const fixtures: [string, Record<string, unknown>][] = [
  ["search_candidates", { query: "Python Django backend" }],
  [
    "search_candidates",
    { query: "React TypeScript", filters: { min_years_experience: 5 } },
  ],
  [
    "search_candidates",
    { query: "ML PyTorch", filters: { required_skills: ["Python", "PyTorch"] } },
  ],
  ["search_candidates", { query: "iOS", filters: { location: "Paris, France" } }],
  ["search_candidates", { query: "remote senior", filters: { location: "remote" } }],
  ["search_candidates", { query: "designer", filters: { max_salary_eur: 60000 } }],
  ["search_candidates", { query: "" }],
  ["get_candidate_profile", { candidate_id: "cand-001" }],
  ["get_candidate_profile", { candidate_id: "cand-999" }],
  ["score_match", { candidate_id: "cand-001", job_id: "job-001" }],
  ["score_match", { candidate_id: "cand-003", job_id: "job-001" }],
  ["list_jobs", {}],
];

const results: unknown[] = [];
for (const [name, args] of fixtures) {
  let r: unknown;
  if (name === "search_candidates") {
    r = searchCandidates(
      args.query as string,
      args.filters as Parameters<typeof searchCandidates>[1],
    );
  } else if (name === "get_candidate_profile") {
    r = getCandidateProfile(args.candidate_id as string);
  } else if (name === "score_match") {
    r = scoreMatch(args.candidate_id as string, args.job_id as string);
  } else if (name === "list_jobs") {
    r = listJobs();
  } else {
    throw new Error(`unknown fixture: ${name}`);
  }
  results.push(r);
}

process.stdout.write(JSON.stringify(results));
