/**
 * Bench-wide constants — single source of truth.
 *
 * Mirrors frameworks/_shared/python/config.py.
 */

/**
 * Gemini 2.5 Flash: non-thinking by default in the OpenAI-compat layer,
 * stable (not preview), broadly deployed in SaaS prod. See
 * frameworks/_shared/python/config.py for the rationale on why we
 * pinned away from gemini-3.1-pro-preview.
 */
export const MODEL_NAME = "gemini-2.5-flash";

/**
 * Google AI Studio's OpenAI-compatible endpoint.
 * Auth via `Authorization: Bearer ${GEMINI_API_KEY}`.
 * https://ai.google.dev/gemini-api/docs/openai
 */
export const GEMINI_OPENAI_BASE_URL =
  "https://generativelanguage.googleapis.com/v1beta/openai/";

/** Hard ceiling on tool-calling iterations within a single run. */
export const MAX_STEPS = 25;
