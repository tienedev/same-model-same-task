"""Descriptions for the 4 bench tools.

Frameworks that auto-extract from docstrings (LangGraph, PydanticAI,
Google ADK) use the docstrings on the tool wrappers in tools/python/tools.py.
Frameworks that take an explicit description string (CrewAI's Task descriptions,
Mastra createTool, Vercel AI SDK tool()) import these.
"""

SEARCH_CANDIDATES_DESC = (
    "Search candidates by free-text query and optional filters. "
    "Filters dict can contain: min_years_experience (int), required_skills (list of strings), "
    "location (string; 'remote' matches any remote-ok candidate), max_salary_eur (int). "
    "Returns up to 10 candidate IDs sorted by match relevance."
)

GET_CANDIDATE_PROFILE_DESC = (
    "Get the full profile for a candidate by id. Returns null if the id does not exist."
)

SCORE_MATCH_DESC = (
    "Score how well a candidate matches a job. Returns a breakdown with "
    "skill_match_pct (int 0-100), experience_fit ('match'|'under'|'over'), "
    "location_fit ('match'|'remote_compatible'|'mismatch'), and "
    "salary_fit ('in_range'|'below_min'|'above_max'). Not an aggregate score — "
    "you must synthesize."
)

LIST_JOBS_DESC = (
    "List all jobs as a lightweight summary (id, title, location only)."
)
