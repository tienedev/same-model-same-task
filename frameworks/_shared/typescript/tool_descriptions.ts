/** Descriptions for the 4 bench tools. Mirrors python/tool_descriptions.py. */

export const SEARCH_CANDIDATES_DESC =
  "Search candidates by free-text query and optional filters. " +
  "Filters dict can contain: min_years_experience (int), required_skills (list of strings), " +
  "location (string; 'remote' matches any remote-ok candidate), max_salary_eur (int). " +
  "Returns up to 10 candidate IDs sorted by match relevance.";

export const GET_CANDIDATE_PROFILE_DESC =
  "Get the full profile for a candidate by id. Returns null if the id does not exist.";

export const SCORE_MATCH_DESC =
  "Score how well a candidate matches a job. Returns a breakdown with " +
  "skill_match_pct (int 0-100), experience_fit ('match'|'under'|'over'), " +
  "location_fit ('match'|'remote_compatible'|'mismatch'), and " +
  "salary_fit ('in_range'|'below_min'|'above_max'). Not an aggregate score — " +
  "you must synthesize.";

export const LIST_JOBS_DESC =
  "List all jobs as a lightweight summary (id, title, location only).";
