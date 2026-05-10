"""Bench-wide constants — single source of truth.

All adapters route to Gemini via Google's OpenAI-compatible endpoint, using
their native OpenAI SDK / OpenAI-compat client. Single SDK family across
the bench, single env var (GEMINI_API_KEY). One adapter (Google ADK) has
to wrap through LiteLlm to talk OpenAI-compat — documented inside ADK's
adapter file.
"""

# Gemini 2.5 Flash: non-thinking by default in the OpenAI-compat layer,
# stable (not preview), broadly deployed by SaaS teams. Earlier attempts
# with gemini-3.1-pro-preview hit `thought_signature` round-tripping
# issues across 5/8 frameworks (langgraph, pydantic-ai, mastra,
# vercel-ai-sdk, google-adk-via-litellm), with no portable workaround.
# A working bench on a real production model beats a broken bench on
# a flashier preview.
MODEL_NAME = "gemini-2.5-flash"

# Google AI Studio's OpenAI-compatible endpoint. Authenticated via
# `Authorization: Bearer ${GEMINI_API_KEY}`. Documented at
# https://ai.google.dev/gemini-api/docs/openai
GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Hard ceiling on tool-calling iterations within a single run. Frameworks
# expose this differently (max_iter, recursion_limit, stopWhen, etc.).
MAX_STEPS = 25
