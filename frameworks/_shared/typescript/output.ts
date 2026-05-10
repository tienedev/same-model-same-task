/**
 * Final-output parsing & helpers.
 *
 * Mirrors frameworks/_shared/python/output.py.
 */

const FENCE_RE = /^```(?:json)?\s*|\s*```\s*$/gi;

export function parseFinalJson(text: string): {
  parsed: unknown | null;
  error: string | null;
} {
  const cleaned = (text || "").trim().replace(FENCE_RE, "").trim();
  try {
    return { parsed: JSON.parse(cleaned), error: null };
  } catch (e) {
    return { parsed: null, error: `${(e as Error).name}: ${(e as Error).message}` };
  }
}
