# Task Spec — same-model-same-task

**Date** : 2026-05-07
**Status** : v1 validé. Décisions arbitrées : 30 runs (10×3), dataset généré par Claude + relecture Etienne, failed runs taxés en robustesse seulement.

---

## 1. Tâche en 1 phrase

Étant donné une offre d'emploi (job_id) parmi 10, retourner les **3 meilleurs candidats** (parmi 50) avec un score de match et une justification courte par candidat, en consommant les 4 tools fournis.

## 2. Inputs

L'agent reçoit un seul argument utilisateur :

```
"For job <job_id>, find the top 3 best matching candidates. Use the available tools to search and evaluate. Return your answer as JSON with the schema described in the system prompt."
```

Le `job_id` est passé tel quel (`"job-001"`, `"job-002"`, …). L'agent doit utiliser `list_jobs()` ou directement `score_match()` pour avoir le contexte de l'offre.

**Pas d'autre input via prompt** : pas de tips, pas d'instructions spéciales par run. C'est le test : chaque framework s'arrange avec ce qu'il a.

## 3. Schema dataset

### `data/candidates.json` — 50 entries

```json
{
  "id": "cand-001",
  "name": "Marie Dubois",
  "current_title": "Senior Backend Engineer",
  "skills": ["Python", "Django", "PostgreSQL", "Docker", "AWS"],
  "years_experience": 6,
  "location": "Paris, France",
  "remote_ok": true,
  "bio": "Backend engineer with 6 years of experience in fintech, focused on building scalable APIs. Led the migration of a monolith to microservices at PreviousCo.",
  "availability": "1 month",
  "expected_salary_eur": 65000,
  "previous_roles": [
    {"title": "Backend Engineer", "company": "PreviousCo", "years": 3},
    {"title": "Junior Developer", "company": "FirstCo", "years": 2}
  ]
}
```

**Distribution de la base** (pour rendre le matching non-trivial) :
- 12 Backend (Python, Node, Java, Go)
- 10 Frontend (React, Vue, Angular)
- 8 Full-stack
- 6 Data/ML
- 5 DevOps/SRE
- 5 Mobile (iOS, Android, React Native)
- 4 Design (Product designer, UX)

Variation : seniorités junior/mid/senior, locations FR/UE/remote-only, salaires réalistes 35k-90k. Quelques candidats avec **fit partiel volontaire** (bonnes skills mauvaise location, ou bonnes skills mauvais niveau) pour tester le raisonnement.

### `data/jobs.json` — 10 entries

```json
{
  "id": "job-001",
  "title": "Senior Backend Engineer",
  "description": "We're hiring a Senior Backend Engineer to lead the design of our payment infrastructure. You'll work with a team of 4 engineers, own the API roadmap, and partner with product. Strong Python required.",
  "required_skills": ["Python", "Django", "PostgreSQL"],
  "nice_to_have_skills": ["AWS", "Docker", "Stripe API"],
  "min_years_experience": 5,
  "location": "Paris, France",
  "remote_ok": true,
  "salary_range_eur": {"min": 60000, "max": 80000},
  "contract_type": "CDI"
}
```

Couverture : 1 backend Python, 1 backend Node, 1 frontend React, 1 full-stack, 1 data/ML, 1 DevOps, 1 mobile iOS, 1 designer, 1 senior fullstack remote-only, 1 junior backend (pour test rejet de candidats over-qualifiés).

**Langue dataset** : **anglais**. Public artifact, audience internationale. Les noms de candidats restent variés (FR, UK, ES, IT) pour le réalisme.

## 4. Tools (4 tools, signatures exactes)

Tous implémentés en code déterministe (pas de LLM dans les tools). Une implémentation Py + une TS, équivalentes sémantiquement.

### `search_candidates(query: string, filters?: object) → string[]`

Recherche dans `candidates.json` par texte libre + filtres optionnels.

- `query` : texte libre, matché contre `current_title + skills + bio` (case-insensitive, OR sur les tokens)
- `filters` (optionnel) :
  - `min_years_experience: number`
  - `required_skills: string[]` — AND sur les skills
  - `location: string` — match exact ou "remote"
  - `max_salary_eur: number`
- **Retour** : array de `candidate_id`, max 10, triés par nombre de tokens query matchés décroissant

### `get_candidate_profile(candidate_id: string) → CandidateProfile | null`

Retourne le profil complet du candidat ou `null` si l'id n'existe pas.

### `score_match(candidate_id: string, job_id: string) → MatchScore`

Calcule un score heuristique. **Important** : retourne la décomposition, pas un score global, pour forcer l'agent à raisonner.

```json
{
  "skill_match_pct": 75,
  "experience_fit": "match" | "under" | "over",
  "location_fit": "match" | "remote_compatible" | "mismatch",
  "salary_fit": "in_range" | "below_min" | "above_max"
}
```

L'agent doit interpréter et synthétiser. Pas de score agrégé fourni.

### `list_jobs() → JobSummary[]`

Retourne les 10 jobs sous forme légère :
```json
[{ "id": "job-001", "title": "Senior Backend Engineer", "location": "Paris, France" }, …]
```

## 5. Output schema attendu

L'agent doit produire **un JSON exactement à ce format** :

```json
{
  "job_id": "job-001",
  "ranked_candidates": [
    {
      "rank": 1,
      "candidate_id": "cand-023",
      "score": 87,
      "justification": "Strong Python+Django match (4/5 required), 6y experience exceeds minimum, Paris location."
    },
    {
      "rank": 2,
      "candidate_id": "cand-007",
      "score": 79,
      "justification": "..."
    },
    {
      "rank": 3,
      "candidate_id": "cand-031",
      "score": 72,
      "justification": "..."
    }
  ]
}
```

Contraintes :
- `score` : integer 0-100 (l'agent calcule lui-même à partir de `score_match()` breakdown)
- `justification` : 1-2 phrases, **max 50 mots** (cap pour réduire variance tokens)
- Exactement 3 candidats, ordre `rank=1,2,3` strict

## 6. Validation programmatique (avant LLM-judge)

Un run est marqué `failed` (et n'entre pas dans le scoring qualitatif) si :
- Output non-JSON parsable
- Schéma incomplet ou invalide
- Moins de 3 candidats
- `candidate_id` qui n'existe pas dans `candidates.json`
- Justification > 60 mots ou vide

Ces failures sont logguées et reportées (taux de robustesse par framework = signal en soi).

## 7. LLM-judge — Claude Sonnet 4.6

Pour les runs qui passent la validation programmatique, judge Claude évalue sur 4 critères, 1-5 par critère, total /20 :

1. **Pertinence du top 3** : les 3 candidats sélectionnés sont-ils plausiblement parmi les meilleurs pour ce job ? (1=non-pertinent, 5=excellent shortlist)
2. **Score cohérent** : le score numérique reflète-t-il les éléments mentionnés dans la justification ? (1=incohérent, 5=parfait alignement)
3. **Justification utile** : un recruteur peut-il agir sur ces justifications ? (1=banal/vague, 5=actionnable et précis)
4. **Format & concision** : respect du format, pas de remplissage ? (1=verbeux/désordonné, 5=clean)

Prompt judge à drafter pendant l'impl du harness, mais structure verrouillée ici.

---

**Update 2026-05-10** : the LLM-judge is now a **secondary** signal. The primary leaderboard ranking is the deterministic NDCG@3 + Hit@1 scorer over a graded-relevance rubric — see `docs/plans/2026-05-10-deterministic-scorer-design.md`. Of the 4 axes above, only `justification_quality` is surfaced in the leaderboard; `relevance` is replaced by the deterministic scorer, `score_coherence` is circular (agent generates both the score and the justification), and `format` is filtered upstream by validation.

## 8. Plan de runs

**Par framework + baseline** :
- 10 jobs × 3 runs/job = **30 runs** par framework
- Couvre variance (3 runs/job) ET généralisation (10 jobs distincts)
- Total : 7 cibles (6 frameworks + baseline) × 30 = **210 runs au headline**

**Estimation budget Gemini** :
- ~7k tokens/run (estimation : 1 system prompt 1k + history 4-5 rounds × 1.2k + final output 500)
- 210 × 7k = ~1.5M tokens
- Pricing Gemini 3.1 Pro : $2 in + $12 out per 1M ; en supposant 70% input / 30% output → ~$5-7 pour le run complet
- LLM-judge Claude : 210 × ~3k tokens = 630k → ~$3 (Sonnet 4.6)
- **Budget total ~$10-15**, soutenable

## 9. Décisions design notables (et pourquoi)

| Choix | Décision | Raison |
|---|---|---|
| Langue dataset | Anglais | Public artifact, audience internationale |
| Score agrégé fourni par tool ? | Non, breakdown seulement | Force l'agent à raisonner, sinon les frameworks deviennent "lookup wrappers" |
| Output strict JSON | Oui, schéma fixé | Apples-to-apples ; failures logguées comme signal robustesse |
| Tool implémentation | Code déterministe, pas LLM | Reproductibilité, isolation framework overhead |
| Cap justification | 50 mots max | Réduit variance tokens, force concision |
| Runs / job | 3 (× 10 jobs) | Compromis variance / généralisation |
| Judge | gemini-2.5-flash (defaulted to agent model; original plan was Claude Sonnet 4.6) | Self-bias documented in § 7 update |

---

## Décisions arbitrées (2026-05-07)

- **Runs** : 30 par framework (10 jobs × 3 runs/job). Bumpable à 60 si la variance est trop large au headline.
- **Dataset** : généré par Claude (cette session), relecture + retouche de 5-10 entries par Etienne pour le réalisme staffing FR.
- **Failed runs** : taxés dans la métrique "robustness rate" (% runs valides), skippés dans le score qualitatif LLM-judge.
- **Salaires** : EUR uniquement (simplification).
