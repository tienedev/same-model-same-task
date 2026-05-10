# same-model-same-task — Design Doc

**Date** : 2026-05-07
**Owner** : Etienne Brun
**Status** : v2 — révisé après scouting + recadrage stratégique (cible employeur SaaS scale-ups, modèle Gemini 3.1 Pro, ajout Flue, baseline no-framework)

> **Strategic intent** : portfolio public OSS pour postuler à un poste d'AI Software Engineer. Audience cible des artifacts (README, blog post, dashboard) = product/eng leads de SaaS scale-ups qui doivent choisir un framework agentic pour leur prod. Tout choix de design est filtré par "qu'est-ce que ça signale à un hiring manager qui scanne le repo en 30 secondes".

---

## Context

Side project public OSS. Le profil GitHub de l'auteur est vide (projets pro privés) — il faut un artifact concret qui démontre maîtrise des frameworks agentiques 2026.

État de l'art benchmarks frameworks agentiques :
- [`LukaszGrochal/agent-framework-benchmark`](https://github.com/LukaszGrochal/agent-framework-benchmark) — 5 frameworks Python, tâche "Company Research". Blog post ~10k vues. Référence à dépasser.
- [AgentRace (OpenReview)](https://openreview.net/forum?id=eUuxWAQA5F) — académique, focus efficiency.
- [AIMultiple](https://aimultiple.com/multi-agent-frameworks) — 4 frameworks Python, marketing-flavored.

**Gap identifié** : aucun benchmark public ne couvre **cross-language Python + TypeScript**. C'est pourtant la décision concrète d'une équipe d'archi : "on prend Mastra (TS) ou LangGraph (Py) ?". Personne n'a mesuré.

## Goal

Premier benchmark public qui fixe **modèle + tâche + tools + dataset** et fait varier uniquement le **framework**, en couvrant Python *et* TypeScript dans la même comparaison, avec **baseline raw API** pour quantifier ce que les frameworks apportent réellement.

## Non-goals

- Refaire τ-bench / GAIA / SWE-bench (benchmarks model-vs-model).
- Benchmarker des coding agents (Claude Code, Cursor, Aider) — catégorie différente.
- Benchmarker des no-code builders (LangFlow, Flowise, n8n) — catégorie différente.
- Trouver "le meilleur framework" en absolu — but : exposer trade-offs measurables.

---

## Frameworks (6 + 1 baseline)

Liste resserrée sur les frameworks que la cible (product/eng leads SaaS scale-ups) peut sérieusement envisager d'adopter en prod en 2026. Asymétrie Py (4) / TS (2) assumée — c'est la réalité du marché : l'écosystème Python est plus mature, le TS converge sur 2 leaders.

| Framework | Langue | Pourquoi | Stars (mai 2026) |
|---|---|---|---|
| **LangGraph** | Python | Référence production, LangSmith ecosystem | 24.8k★ |
| **Google ADK** | Python | First-class avec Gemini headline — angle "vendor-native" | 17.8k★ |
| **PydanticAI** | Python | Type-safe, hype FastAPI/Pydantic | 16.9k★ |
| **CrewAI** | Python | Overlap LukaszGrochal → cross-validation crédibilité | 49.9k★ |
| **Mastra** | TypeScript | Leader TS, batteries-included | 150k weekly dl, $13M seed |
| **Vercel AI SDK** | TypeScript | Massif côté Next.js, `ToolLoopAgent` confirmé v6 | majeur |

### Baseline (no framework)

| "Framework" | Langue | Pourquoi |
|---|---|---|
| **Raw API + manual loop** | Python ET TypeScript | Référence : ~50 lignes max, appel direct Gemini, tool-calling loop manuel. Mesure ce que les 6 frameworks apportent vraiment. **Sans cette ligne, le bench n'a pas de référent.** |

**Frameworks droppés** (et pourquoi, pour traçabilité) :
- ~~OpenAI Agents Python~~ : Gemini via LiteLLM/OpenRouter détour, pas le pattern officiel.
- ~~OpenAI Agents JS~~ : Gemini via wrapper Vercel AI SDK (`aisdk()`), pas le pattern officiel non plus. Risque "vous l'avez utilisé hors-spec" de la team OpenAI.
- ~~Flue~~ : catégorie différente (agent harness vs orchestration), 50★ trop niche, risque apples-to-oranges parasitant le narratif principal. À mentionner dans le blog post comme "framework émergent à surveiller" mais pas dans le bench.

**Critère d'inclusion** : ≥ 1 pattern agent + tools officiel documenté + voie native ou first-class vers Gemini 3.1 Pro.

---

## Tâche

**Matching candidat ↔ offre** (domaine staffing — connu de l'auteur).

- Inputs : 1 offre d'emploi (titre + description + compétences requises) + N profils candidats
- Output : top 3 candidats avec score de match + justification courte par candidat
- Tools agent (4) :
  - `search_candidates(query, filters)` — recherche dans une base de profils
  - `get_candidate_profile(id)` — détails d'un profil
  - `score_match(candidate_id, job_id)` — heuristique scoring
  - `list_jobs()` — exploration alternative

**Dataset** : généré synthétiquement, **figé dans `data/candidates.json` + `data/jobs.json`** committés au repo. 50 candidats × 10 offres. Chaque framework reçoit le même dataset bit-pour-bit.

**Pourquoi cette tâche** :
- Réaliste pour audience SaaS (matching/recommandation est un cas d'usage récurrent)
- Multi-tools, multi-step (3-5 LLM calls minimum)
- Output déterministe-ish (top N triable, justifications gradables par LLM-judge)
- Domaine connu de l'auteur → narrative crédible ("voici comment je résoudrais le problème de mon prochain employeur")

---

## Modèle

**Gemini 3.1 Pro Preview** via Google AI Studio's **OpenAI-compatible endpoint** (`GEMINI_API_KEY`).

- **Endpoint** : `https://generativelanguage.googleapis.com/v1beta/openai/` ([doc Google](https://ai.google.dev/gemini-api/docs/openai)). Auth via `Authorization: Bearer ${GEMINI_API_KEY}`.
- **Modèle** : `gemini-3.1-pro-preview` (passé tel quel, pas de prefix).
- **Transport** : **un seul SDK family — OpenAI** — partout :
  - baseline (Py) : `openai` Python SDK
  - baseline (TS) : `openai` Node SDK
  - LangGraph : `langchain-openai` (`ChatOpenAI`) avec custom `base_url`
  - CrewAI : LiteLLM avec slug `openai/gemini-3.1-pro-preview` + `api_base` custom
  - PydanticAI : `OpenAIChatModel` + `OpenAIProvider` avec custom `base_url`
  - Google ADK : LiteLlm wrapper avec slug `openai/gemini-3.1-pro-preview` + `api_base` custom
  - Mastra : `@ai-sdk/openai-compatible` avec `baseURL` custom
  - Vercel AI SDK : `@ai-sdk/openai-compatible` avec `baseURL` custom
- **Pricing** : $2 in / $12 out par 1M tokens (≤200K context). Compte Gemini entreprise = pas de markup gateway.
- **Sampling fixé** : `temperature=0`, `seed=42` à chaque appel. Pas bit-perfect (queue Google côté serveur introduit variance), reproductible à ±5% sur 30 trials.

**Pourquoi cette architecture** :
- **Une seule clé** (`GEMINI_API_KEY`), pas de markup intermédiaire, pas de gateway tiers facturé.
- **Une seule API surface** (OpenAI-compat) → le code des 8 adapters est uniforme, lisible. Single point of swap pour tester un autre modèle (changer l'env var et le slug).
- **Trade-off accepté** : Google ADK utilise le wrapper LiteLlm pour parler OpenAI-compat plutôt que son provider Gemini natif. C'est le coût méthodologique d'un transport unifié — tous les frameworks tapent le même endpoint avec le même format. Documenté en commentaire dans `frameworks/google_adk/python/run.py`.

**Caveat preview à acter** : si Google rename `gemini-3.1-pro-preview` avant la publication, le bench est cassé. Mitigation : on pin la string dans `methodology.md` et on capture le `model` retourné par l'API dans chaque trace.

---

## Métriques

| Métrique | Comment mesurer | Format dashboard |
|---|---|---|
| **Latence p50/p95** | End-to-end, 30 runs minimum par framework, run en série (pas parallèle) pour éviter contention API | Bar chart |
| **Tokens (in / out)** | Total per run, distinguer prompt vs completion | Stacked bar |
| **Coût €/run** | Tokens × Gemini 3.1 Pro pricing officiel — vrai signal pour audience SaaS | Scatter (vs success rate) |
| **Succès** | LLM-judge (rubric explicit, voir ci-dessous) + checks programmatiques (top 3 retourné, format valide JSON, justifications non-vides) | Heatmap par run |
| **LOC tool definition** | Lignes de code pour définir UN tool (moyenne sur les 4 tools) — apples-to-apples cross-language | Bar chart |
| **LOC agent setup** | Lignes pour instancier l'agent + lui donner les tools + lancer un appel — apples-to-apples cross-language | Bar chart |
| **Framework overhead tokens** | Tokens "non-tâche" (system prompts framework, ré-injections, tool wrapping) — extrait des traces vs baseline | Stacked bar (vs baseline) |

**LLM-judge** : **Gemini 3.1 Pro Preview** (même modèle que le générateur, faute de clé Anthropic / OpenRouter dans ce setup). ⚠️ **Self-judging bias documenté ~15-20%** dans la littérature LLM-as-judge — à expliciter en tête de blog post. Mitigation possible en follow-up : re-juger le même set de outputs avec un judge tiers (GPT-5, Claude) pour quantifier le delta. Rubric à 4 critères (top 3 valide, score justifié, format respecté, justifications cohérentes), 1-5 par critère, agrégé en score /20.

---

## Règles de fairness

**Règle d'or** : chaque framework utilise son **pattern officiel recommandé** (capturé verbatim dans le scouting). Si un mainteneur peut dire "ce n'est pas comme ça qu'on utilise mon framework", on a perdu.

Pour chaque framework, dans `frameworks/{name}/SOURCE.md` :
1. **Version** exacte pinnée dans lockfile
2. **URL** verbatim du quickstart officiel utilisé comme base (déjà capturé pour les 8 — voir `scouting-results.md`)
3. **Diff minimal** entre l'exemple officiel et notre implémentation (typiquement : on substitue les tools, on garde le scaffolding)

**Pin de version** :
- Versions strictement gravées (`package-lock.json` / `uv.lock` figés). README en haut : "tested as of 2026-05-07 with Gemini 3.1 Pro Preview, framework versions pinned in lockfiles."
- Pas de CI cron auto-update (pivot v2 — coûteux, faible ROI). À la place : engagement à un re-run manuel mensuel commit dans le repo. Voir section "Maintenance".

**Hardware / env** : runs depuis Mac M4 Pro (réseau résidentiel, fenêtre temporelle fixée — un dimanche matin pour homogénéité). Versions Node + Python pinnées. Documenté dans `methodology.md`.

---

## Per-framework deep dive (le vrai signal recrutement)

Pour chaque framework, **1 page Markdown dans le repo** (`frameworks/{name}/ANALYSIS.md`) qui contient :
1. **Architecture** (1 schéma simple) — comment le framework structure agent + tools + memory
2. **Design choices** — 3 décisions notables des mainteneurs et leur trade-off
3. **Gotchas** — 2 trucs trouvés en debugant l'impl que la doc ne dit pas
4. **Verdict d'usage** — pour quel cas d'usage ce framework brille / pour lequel il rame

C'est *cette* matière qui transforme le projet de "j'ai copié 8 quickstarts" en "j'ai vraiment pigé chaque framework". Sans ces analyses, la legitimacy retombe à 30%.

---

## Dashboard (scope réduit v2)

### Stack

```
Next.js 15 (App Router) · shadcn/ui · Tremor · Vercel
```

### Routes (4 au lieu de 5)

| Route | Contenu |
|---|---|
| `/` | Hero + leaderboard triable + 2 charts headline |
| `/{framework}` | Code sample, distribution histogramme, lien `ANALYSIS.md` |
| `/methodology` | Tâche, modèle, scoring, env, **disclaimers honnêtes** |
| ~~`/reproduce`~~ | **Folded into README** — pas de route séparée |
| ~~`/embed/{framework}`~~ | **Drop** — over-engineering pour un MVP |
| ~~`/latest`~~ | **Drop** — pas de CI cron sustainable, voir Maintenance |

### Charts headline (2 au lieu de 4)

- **Scatter cost vs success rate** — Pareto frontier, le visuel le plus partageable. Coût en € avec pricing Gemini réel.
- **Stacked bar tokens (in/out) vs baseline** — révèle re-prompting et framework overhead. La baseline "no framework" est la référence.

Les autres charts (latence, LOC) restent dispo dans `/methodology` et `/{framework}` mais ne polluent pas la home.

---

## README — l'artifact principal pour le recrutement

Le README est l'artifact que **80% des hiring managers liront**. Optimiser pour décision-en-30-secondes :

1. **Hero** : 1 phrase de pitch + 1 chart cost-vs-success en image (généré au build)
2. **Tableau leaderboard** Markdown (succinct)
3. **Liens vers les `ANALYSIS.md` par framework**
4. **Section "What I learned"** : 5 takeaways narratifs (le vrai contenu pour un staff eng qui lit le repo)
5. **Section "Reproduce"** : `npm run bench` + setup en 3 commandes
6. **Section "Caveats"** : 3 limites honnêtes du bench

Le dashboard est un *complément*. Le README est l'artifact.

---

## Maintenance

Pas de CI cron auto-update (pivot v2 : coût d'infra > ROI portfolio). À la place :
- **Re-run manuel mensuel** : 30 min, commit du nouveau JSON, push. Discipline.
- **Re-run après major release** d'un framework : si LangGraph 2.0 sort, on re-runne et on note la différence.
- **Changelog visible** dans le README ("last updated YYYY-MM-DD, 3 frameworks bumped").

---

## Effort (révisé v2)

| Phase | Estimation |
|---|---|
| ✅ Scouting des 8 frameworks initiaux | fait (2 droppés ensuite) |
| Lock task spec + dataset synthétique | 0.25 weekend |
| Implémentation tâche + 6 adapters + baseline | 1.5 weekend |
| Harness mesure (latence, tokens, judge Claude) | 0.5 weekend |
| Per-framework `ANALYSIS.md` (6 × 1 page) | 0.5 weekend |
| Dashboard Next.js réduit (3 routes, 2 charts) | 0.5 weekend |
| README polish + blog post + deploy | 0.5 weekend |
| **Total restant** | **~3.75 weekends** |

MVP encore plus court : drop PydanticAI ou Vercel AI SDK → 5 frameworks + baseline, ~3 weekends.

---

## Open questions

Résolues pendant le scouting :
- [x] Vercel AI SDK : `ToolLoopAgent` confirmé en v6.
- [x] PydanticAI : 16.9k stars, inclus.

Résolues v2 (cette révision) :
- [x] Modèle : Gemini 3.1 Pro Preview cloud.
- [x] Local Qwen : drop (cohérence audience SaaS).
- [x] OpenAI Agents Python : drop (détour Gemini, doublon avec JS).
- [x] OpenAI Agents JS : drop (Gemini via wrapper, pas pattern officiel — risque dismiss OpenAI).
- [x] Flue : drop (50★ niche + catégorie différente — mention dans blog post comme "à surveiller", pas dans le bench).
- [x] LLM-judge : Claude Sonnet 4.6 (pas Gemini, pour éviter self-judging).
- [x] Baseline no-framework : ajoutée.

Restantes :
- [ ] Format final du dataset candidats (50×10, structure exacte des fields)
- [ ] Rubric LLM-judge précise (4 critères × 1-5)
- [ ] Risque deprecation `gemini-3.1-pro-preview` avant publication — comment réagir si ça arrive

---

## Next steps

1. ~~**Scouting**~~ ✅ fait — voir `docs/plans/scouting-results.md`.
2. **Lock task spec** : structure exacte du dataset + signature des 4 tools + format output JSON canonique.
3. **Build harness** mesure (latence, tokens, judge). Faire d'abord le baseline (raw Gemini API + manual loop) — c'est aussi le canary pour valider que `gemini-3.1-pro-preview` répond comme attendu.
4. **Implement framework adapters** dans `frameworks/{name}/` un par un. Pendant l'écriture de chaque adapter, drafter en parallèle son `ANALYSIS.md`.
5. **Build dashboard** Next.js / Tremor (scope réduit).
6. **Polish README** (l'artifact prioritaire) + blog post + deploy.

---

## Appendix — Sources consultées pendant le design

- [LukaszGrochal/agent-framework-benchmark](https://github.com/LukaszGrochal/agent-framework-benchmark)
- [DEV — I Benchmarked 5 AI Agent Frameworks](https://dev.to/lukaszgrochal/i-benchmarked-5-ai-agent-frameworks-heres-what-actually-matters-3ela)
- [AgentRace (OpenReview)](https://openreview.net/forum?id=eUuxWAQA5F)
- [Speakeasy — Choosing an agent framework](https://www.speakeasy.com/blog/ai-agent-framework-comparison)
- [Pharos Production — AI Agent Frameworks 2026](https://pharosproduction.com/insights/engineering/ai-agent-frameworks-comparison-2026/)
- [Gemini 3.1 Pro pricing & function calling](https://ai.google.dev/gemini-api/docs/pricing)
- [Flue — withastro/flue](https://github.com/withastro/flue)

---

## Changelog

- **v1 (2026-05-07 initial)** : Claude Sonnet 4.6 cloud, 7 frameworks (8 après ajout OpenAI Agents Py).
- **v1.1 (2026-05-07 PM)** : pivot Qwen3.6-27B-UD-MLX-4bit local via oMLX (bit-perfect).
- **v2 (2026-05-07 evening)** : recadrage stratégique (cible SaaS scale-ups). Gemini 3.1 Pro cloud headline, drop Qwen local, drop OpenAI Agents Python, ajout Flue (catégorie "agent harness"), ajout baseline raw API, ajout per-framework `ANALYSIS.md`, scope dashboard réduit, README priorisé comme artifact #1.
- **v2.1 (2026-05-07 night)** : raffinage frameworks. Drop OpenAI Agents JS (Gemini via wrapper non-officiel) et Flue (niche + catégorie différente, parasiterait le narratif). Liste finale = **6 frameworks + baseline** : 4 Py (LangGraph, Google ADK, PydanticAI, CrewAI) + 2 TS (Mastra, Vercel AI SDK).
- **v2.2 (2026-05-07 night, post-canary)** : pivot transport vers **OpenRouter unifié**. Tout le bench (générateur Gemini 3.1 Pro + judge Claude Sonnet 4.6) passe par `https://openrouter.ai/api/v1` avec OpenAI SDK. Une seule clé, un seul SDK, model swap trivial. Slug requis : `google/gemini-3.1-pro-preview-customtools` (le bare slug se coince en thinking infini sans émettre tool_calls). Trade-off : Google ADK perd son angle "vendor-native" mais le bench gagne en cohérence et reflète mieux la réalité des SaaS scale-ups (qui utilisent un gateway type OpenRouter en 2026).
- **v2.3 (2026-05-07 night, post-credit-drain)** : retour à **Gemini direct** (Google AI Studio, `GEMINI_API_KEY` only). Raisons : (a) credits OpenRouter cramés pendant la phase d'impl, (b) chaque framework retrouve son provider natif documenté → fairness renforcée, (c) le judge passe à Gemini avec self-judging caveat documenté en tête de blog post (pas de clé Claude/OpenRouter). Refactor passant : extraction de `frameworks/_shared/{python,typescript}/` (DRY) — SYSTEM_PROMPT, MODEL_NAME, descriptions tools, parse_final_json centralisés.
- **v2.4 (2026-05-08)** : pivot vers **OpenAI SDK partout via Gemini OpenAI-compat endpoint** (`https://generativelanguage.googleapis.com/v1beta/openai/`). Toujours `GEMINI_API_KEY` only (pas d'OpenRouter). Avantages : un seul SDK family (Python `openai` + Node `openai`), code uniforme à travers les 8 adapters, model swap = 1 ligne. Coût : ADK utilise LiteLlm wrapper au lieu du provider Gemini natif (l'angle "vendor-native first-class" est de toute façon dilué dès qu'on unifie le transport). Le compte entreprise Gemini de l'auteur prend à charge tous les coûts API.
