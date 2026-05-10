| Framework | Valid | NDCG@3 | Hit@1 | JustifQ /5 [^j] | p50 (s) | p95 (s) | Mean tokens (in/out) | Mean tools | Cost / run (USD) |
|---|---|---|---|---|---|---|---|---|---|
| pydantic-ai | 29/30 | 0.857 | 100.0% | 3.41 | 16.2 | 31.5 | 6149 / 480 | 8.4 | $0.0181 |
| langgraph | 27/30 | 0.823 | 92.6% | 3.70 | 17.1 | 25.9 | 5167 / 502 | 8.8 | $0.0164 |
| vercel-ai-sdk | 27/30 | 0.662 | 77.8% | 2.89 | 21.2 | 28.4 | 1605 / 228 | 9.1 | $0.0060 |
| google-adk | 29/30 | 0.621 | 72.4% | 3.41 | 19.9 | 471.8 | 6128 / 510 | 9.3 | $0.0184 |
| mastra | 30/30 | 0.610 | 73.3% | 3.37 | 21.5 | 31.9 | 6154 / 548 | 11.2 | $0.0189 |
| crewai | 26/30 | 0.598 | 69.2% | 3.27 | 18.7 | 31.6 | 42785 / 1806 | 11.8 | $0.1072 |
| baseline-typescript | 29/30 | 0.589 | 69.0% | 3.00 | 20.5 | 32.7 | 5897 / 495 | 9.2 | $0.0177 |
| baseline-python | 23/30 | 0.570 | 65.2% | 3.09 | 22.1 | 54.8 | 7027 / 515 | 9.7 | $0.0202 |

[^j]: `JustifQ /5` is the LLM-judge's `justification_quality` axis only — the prose readability signal. The previous `/20` sum is preserved in the JSON but no longer surfaced: Gemini judging Gemini exhibits documented self-bias (up to 50% rubric-flip on objective rubrics; Panickssery et al. NeurIPS 2024). Use NDCG@3 + Hit@1 for ranking decisions.
