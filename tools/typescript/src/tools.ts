/**
 * 4 deterministic tools shared by all framework adapters.
 *
 * Pure-TS functions operating on the static datasets in
 * data/candidates.json and data/jobs.json. Mirror semantics of
 * tools/python/tools.py exactly.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_DIR = join(__dirname, "..", "..", "..", "data");

export interface Candidate {
  id: string;
  name: string;
  current_title: string;
  skills: string[];
  years_experience: number;
  location: string;
  remote_ok: boolean;
  bio: string;
  availability: string;
  expected_salary_eur: number;
  previous_roles: { title: string; company: string; years: number }[];
}

export interface Job {
  id: string;
  title: string;
  description: string;
  required_skills: string[];
  nice_to_have_skills: string[];
  min_years_experience: number;
  location: string;
  remote_ok: boolean;
  salary_range_eur: { min: number; max: number };
  contract_type: string;
}

export interface SearchFilters {
  min_years_experience?: number;
  required_skills?: string[];
  location?: string;
  max_salary_eur?: number;
}

export interface MatchScore {
  skill_match_pct: number;
  experience_fit: "match" | "under" | "over";
  location_fit: "match" | "remote_compatible" | "mismatch";
  salary_fit: "in_range" | "below_min" | "above_max";
}

let _candidatesCache: Candidate[] | null = null;
let _jobsCache: Job[] | null = null;
let _candidateById: Map<string, Candidate> | null = null;
let _jobById: Map<string, Job> | null = null;

function getCandidates(): Candidate[] {
  if (_candidatesCache === null) {
    _candidatesCache = JSON.parse(
      readFileSync(join(DATA_DIR, "candidates.json"), "utf-8"),
    ) as Candidate[];
  }
  return _candidatesCache;
}

function getJobs(): Job[] {
  if (_jobsCache === null) {
    _jobsCache = JSON.parse(
      readFileSync(join(DATA_DIR, "jobs.json"), "utf-8"),
    ) as Job[];
  }
  return _jobsCache;
}

function getCandidateById(): Map<string, Candidate> {
  if (_candidateById === null) {
    _candidateById = new Map(getCandidates().map((c) => [c.id, c]));
  }
  return _candidateById;
}

function getJobById(): Map<string, Job> {
  if (_jobById === null) {
    _jobById = new Map(getJobs().map((j) => [j.id, j]));
  }
  return _jobById;
}

/**
 * Search candidates by free-text query and optional filters.
 * Returns up to 10 candidate IDs sorted by match relevance, then id ascending.
 */
export function searchCandidates(query: string, filters?: SearchFilters): string[] {
  const queryTokens = query
    .split(/\s+/)
    .map((t) => t.toLowerCase())
    .filter(Boolean);

  const candidatesWithScore: [number, string][] = [];
  for (const c of getCandidates()) {
    // Filters first (hard reject)
    if (
      filters?.min_years_experience !== undefined &&
      c.years_experience < filters.min_years_experience
    ) {
      continue;
    }
    if (filters?.required_skills) {
      const candSkillsLower = new Set(c.skills.map((s) => s.toLowerCase()));
      if (!filters.required_skills.every((s) => candSkillsLower.has(s.toLowerCase()))) {
        continue;
      }
    }
    if (filters?.location !== undefined) {
      const locLower = filters.location.toLowerCase();
      if (locLower === "remote") {
        if (!c.remote_ok) continue;
      } else if (locLower !== c.location.toLowerCase()) {
        continue;
      }
    }
    if (
      filters?.max_salary_eur !== undefined &&
      c.expected_salary_eur > filters.max_salary_eur
    ) {
      continue;
    }

    const haystack = (
      c.current_title +
      " " +
      c.skills.join(" ") +
      " " +
      c.bio
    ).toLowerCase();

    let score = 0;
    for (const t of queryTokens) {
      if (haystack.includes(t)) score += 1;
    }

    if (score > 0 || queryTokens.length === 0) {
      candidatesWithScore.push([score, c.id]);
    }
  }

  candidatesWithScore.sort((a, b) => {
    if (b[0] !== a[0]) return b[0] - a[0];
    return a[1].localeCompare(b[1]);
  });

  return candidatesWithScore.slice(0, 10).map(([, id]) => id);
}

/**
 * Get full profile for a candidate, or null if not found.
 */
export function getCandidateProfile(candidateId: string): Candidate | null {
  return getCandidateById().get(candidateId) ?? null;
}

/**
 * Score how well a candidate matches a job. Returns breakdown, not aggregate.
 */
export function scoreMatch(
  candidateId: string,
  jobId: string,
): MatchScore | { error: string } {
  const cand = getCandidateById().get(candidateId);
  const job = getJobById().get(jobId);
  if (!cand || !job) {
    return { error: `unknown candidate_id=${candidateId} or job_id=${jobId}` };
  }

  // Skill match
  const candSkillsLower = new Set(cand.skills.map((s) => s.toLowerCase()));
  const requiredLower = job.required_skills.map((s) => s.toLowerCase());
  const matchedRequired = requiredLower.filter((s) => candSkillsLower.has(s)).length;
  const skill_match_pct =
    requiredLower.length > 0
      ? Math.round((100 * matchedRequired) / requiredLower.length)
      : 0;

  // Experience fit
  let experience_fit: MatchScore["experience_fit"];
  if (cand.years_experience >= job.min_years_experience) {
    const yearsAbove = cand.years_experience - job.min_years_experience;
    experience_fit = yearsAbove >= 5 ? "over" : "match";
  } else {
    experience_fit = "under";
  }

  // Location fit
  let location_fit: MatchScore["location_fit"];
  if (cand.location.toLowerCase() === job.location.toLowerCase()) {
    location_fit = "match";
  } else if (job.remote_ok && cand.remote_ok) {
    location_fit = "remote_compatible";
  } else {
    location_fit = "mismatch";
  }

  // Salary fit
  const sal = cand.expected_salary_eur;
  let salary_fit: MatchScore["salary_fit"];
  if (sal < job.salary_range_eur.min) {
    salary_fit = "below_min";
  } else if (sal > job.salary_range_eur.max) {
    salary_fit = "above_max";
  } else {
    salary_fit = "in_range";
  }

  return { skill_match_pct, experience_fit, location_fit, salary_fit };
}

/**
 * List all jobs with id/title/location only (lightweight).
 */
export function listJobs(): { id: string; title: string; location: string }[] {
  return getJobs().map((j) => ({ id: j.id, title: j.title, location: j.location }));
}
