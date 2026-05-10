# Scouting Results — 8 Frameworks

**Date scouting** : 2026-05-07 (verbatim re-vérifié le même jour)
**Méthodologie** : 8 subagents Explore en parallèle, deux passes. Première passe : capture initiale. Deuxième passe : vérification verbatim stricte avec URL exacte de chaque snippet, sans synthèse multi-page. Tous les snippets ci-dessous proviennent d'une seule page documentée + URL référencée.

> 🔄 **Recadrage v2 / v2.1 (2026-05-07 evening + night)** : après revue stratégique (cible employeur = SaaS scale-ups), le projet pivote sur :
> - **Modèle headline** : Gemini 3.1 Pro Preview (`gemini-3.1-pro-preview`) via API Google AI Studio, $2/$12 in/out per 1M tokens. **Plus de Qwen local**, plus de Claude Sonnet.
> - **Liste finale benchmark = 6 frameworks + baseline** :
>   - Python (4) : LangGraph, Google ADK, PydanticAI, CrewAI
>   - TypeScript (2) : Mastra, Vercel AI SDK
>   - Baseline : raw Gemini API + boucle tool-calling manuelle (Py + TS)
> - **Droppés** (raisons documentées dans le design doc) :
>   - **OpenAI Agents Python** : Gemini via OpenRouter détour, doublon avec JS.
>   - **OpenAI Agents JS** : Gemini via wrapper Vercel AI SDK (`aisdk()`), pas pattern officiel — risque dismiss OpenAI.
>   - **Flue** : 50★, catégorie différente (agent harness vs orchestration), parasiterait le narratif.
> - **LLM-judge** = Claude Sonnet 4.6 (pas Gemini, anti self-judging).
>
> Conséquence : ce qui compte pour les 6 frameworks au benchmark = "**savoir pointer vers Gemini 3.1 Pro**" (provider Google natif, wrapper Vercel AI SDK `@ai-sdk/google`, ou LiteLLM `gemini/...`). À re-vérifier framework par framework pendant l'impl. Les colonnes "Compat Anthropic" ci-dessous deviennent reliquats du scouting initial — gardées pour traçabilité.
>
> Sections OpenAI Agents Python + OpenAI Agents JS plus bas conservées pour traçabilité historique. **Ne pas implémenter ces deux frameworks**.
>
> Voir le design doc v2.1 (`2026-05-07-same-model-same-task-design.md`) pour la justification complète.

**Caveats résiduels honnêtes** :
- npmjs.com a renvoyé 403 sur plusieurs requêtes pendant le scouting → les versions npm sont confirmées via doc primaire / package.json du repo, pas via la page registre.
- La page quickstart actuelle de LangGraph présente un exemple `mock_llm` minimaliste, pas le pattern complet `bind_tools` (qui est sur une page concept séparée). Le snippet capturé est verbatim mais introductif → on ira chercher l'exemple agent complet sur la page concepts pendant l'impl.
- ~~La doc CrewAI référence `claude-3-5-sonnet-20241022` dans le quickstart (modèle daté).~~ → caduc avec le pivot MLX local.

---

## Tableau récapitulatif

| Framework | Langue | Version (au 2026-05-07) | Pattern | Compat Anthropic | Statut |
|---|---|---|---|---|---|
| LangGraph | Python | 1.1.10 (2026-04-27) | Graph state machine (`StateGraph` + `MessagesState` + nodes) | Native via `langchain-anthropic`, `claude-sonnet-4-6` | ✅ |
| Google ADK | Python | 1.32.0 (2026-05-01) | Class-based (`LlmAgent(model, name, tools=[])`) | Via LiteLLM (`google.adk.models.lite_llm.LiteLlm`), exemple officiel Claude documenté | ✅ (caveat LiteLLM) |
| PydanticAI | Python | 1.91.0 | Decorator (`Agent` + `@agent.tool` / `@agent.tool_plain`) | Native, `Agent('anthropic:claude-sonnet-4-6')` | ✅ |
| CrewAI | Python | 1.14.4 (2026-04-30) | DSL Crew (décorateurs `@agent`/`@task`/`@crew` + YAML config) | Via `LLM(model="anthropic/...")` | ✅ (modèle doc daté) |
| OpenAI Agents Python | Python | 0.16.0 (2026-05-07) | Class + decorator (`Agent` + `@function_tool`) + `Runner` | Via `LitellmModel` + OpenRouter (path officiel, retenu) | ✅ (caveat OpenRouter, voir methodology) |
| Mastra | TypeScript | 1.32.x (2026-05-06) | Class-based (`new Agent({ id, model, tools })`), modèle en string | Native via `@ai-sdk/anthropic`, syntaxe string `"anthropic/claude-sonnet-4-6"` | ✅ |
| Vercel AI SDK | TypeScript | v6 (Latest) | Class-based (`new ToolLoopAgent({ model, tools })`) | Native, syntaxe string OU factory `anthropic('claude-...')` | ✅ |
| OpenAI Agents JS | TypeScript | 0.9.1 (2026-05-06) | Class (`new Agent({...})` + `tool({...})` + `run()`) | Via extension `@openai/agents-extensions/ai-sdk`, wrapper `aisdk(anthropic(...))` | ✅ |

**Drapeau rouge initial sur Google ADK : LEVÉ**. La doc `adk.dev/agents/models/litellm/` documente l'exemple Claude.
**Drapeau rouge initial sur Vercel AI SDK : LEVÉ**. `ToolLoopAgent` existe bien dans la doc `ai-sdk.dev/docs/agents/building-agents`.

---

## Sections par framework

### LangGraph

- **Version** : 1.1.10 (released 2026-04-27, source: PyPI)
- **Page snippet** : https://docs.langchain.com/oss/python/langgraph/ (200 OK)
- **Page Anthropic** : https://docs.langchain.com/oss/python/integrations/chat/anthropic
- **Modèle Claude documenté** : `claude-sonnet-4-6` (aussi mentionnés : `claude-opus-4-6`, `claude-haiku-4-5-20251001`)
- **Pattern** : Graph state machine (`StateGraph` + `MessagesState`)

#### Snippet verbatim depuis https://docs.langchain.com/oss/python/langgraph/

```python
from langgraph.graph import StateGraph, MessagesState, START, END

def mock_llm(state: MessagesState):
    return {"messages": [{"role": "ai", "content": "hello world"}]}

graph = StateGraph(MessagesState)
graph.add_node(mock_llm)
graph.add_edge(START, "mock_llm")
graph.add_edge("mock_llm", END)
graph = graph.compile()

graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
```

#### Notes
- ⚠️ Cet exemple introductif utilise `mock_llm` (pas un vrai LLM) et n'inclut pas `bind_tools`. Pour l'impl, le pattern complet `ChatAnthropic + bind_tools + add_conditional_edges` est sur les pages concept (`/agents/agents/`) — à capturer pendant l'écriture de l'adapter.
- Pas de surprise structurelle : le pattern de référence (graph + nodes typés) est inchangé.

---

### Google ADK (Python)

- **Version** : 1.32.0 (released 2026-05-01, source: PyPI, package `google-adk`)
- **Page snippet agent** : https://adk.dev/agents/llm-agents/ (200 OK)
- **Page Anthropic (LiteLLM)** : https://adk.dev/agents/models/litellm/ (200 OK)
- **Pattern** : Class-based, `LlmAgent(model=, name=, instruction=, tools=[...])`
- **Compat Anthropic** : Via `google.adk.models.lite_llm.LiteLlm` — path documenté avec exemple Claude concret. Pas de provider Anthropic natif (contrairement à la version Java où `com.google.adk.models.Claude` existe).

#### Snippet agent + tools verbatim depuis https://adk.dev/agents/llm-agents/

```python
def get_capital_city(country: str) -> str:
    """Retrieves the capital city for a given country."""
    capitals = {"france": "Paris", "japan": "Tokyo", "canada": "Ottawa"}
    return capitals.get(country.lower(),
        f"Sorry, I don't know the capital of {country}.")

capital_agent = LlmAgent(
    model="gemini-flash-latest",
    name="capital_agent",
    description="Answers questions about country capitals.",
    instruction="""You are an agent providing capital cities.
When asked: 1. Identify the country. 2. Use the get_capital_city
tool. 3. Respond clearly with the result.""",
    tools=[get_capital_city]
)
```

#### Snippet Anthropic verbatim depuis https://adk.dev/agents/models/litellm/

```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

agent_claude = LlmAgent(
    model=LiteLlm(model="anthropic/claude-3-haiku-20240307"),
    name="claude_agent",
    instruction="You are an assistant powered by Claude Haiku.",
    # ... other agent parameters
)
```

#### Notes
- L'exemple LiteLLM officiel utilise un modèle Claude daté (Haiku 20240307). Pour l'impl, on substitue par `anthropic/claude-sonnet-4-6` — substitution low-risk (LiteLLM accepte tout modèle Anthropic, c'est le même provider).
- Caveat fairness : ADK + Claude = ADK + LiteLLM + Anthropic. Trois layers, à documenter dans `methodology.md` mais pas un blocker.

---

### PydanticAI

- **Version** : 1.91.0 (source: PyPI, date non confirmée pendant ce scouting)
- **Page snippet** : https://pydantic.dev/docs/ai/tools-toolsets/tools/ (301 redirect depuis ai.pydantic.dev → nouveau domaine officiel pydantic.dev/docs/ai)
- **Modèle Claude documenté** : `'anthropic:claude-sonnet-4-6'`
- **Pattern** : Decorator — instance `Agent` + `@agent.tool` (avec ctx) ou `@agent.tool_plain` (sans ctx)

#### Snippet verbatim depuis https://pydantic.dev/docs/ai/tools-toolsets/tools/

```python
import random
from pydantic_ai import Agent, RunContext

agent = Agent(
    'google-gla:gemini-3-flash-preview',
    deps_type=str,
    instructions=(
        "You're a dice game. Roll the die, check if it matches "
        "the user's guess. Use the player's name in responses."
    ),
)

@agent.tool_plain
def roll_dice() -> str:
    """Roll a six-sided die and return the result."""
    return str(random.randint(1, 6))

@agent.tool
def get_player_name(ctx: RunContext[str]) -> str:
    """Get the player's name."""
    return ctx.deps

result = agent.run_sync('My guess is 4', deps='Anne')
print(result.output)
```

#### Notes
- L'exemple utilise Gemini, mais le swap vers Claude est trivial (`Agent('anthropic:claude-sonnet-4-6', ...)`).
- Domaine doc déplacé de `ai.pydantic.dev` vers `pydantic.dev/docs/ai/` — penser à utiliser le nouveau dans `SOURCE.md`.

---

### CrewAI

- **Version** : 1.14.4 (released 2026-04-30, source: PyPI)
- **Page snippet** : https://docs.crewai.com/en/quickstart (200 OK)
- **Page LLM config** : https://docs.crewai.com/en/concepts/llms (200 OK)
- **Pattern** : DSL Crew avec décorateurs `@CrewBase` + YAML config (`agents.yaml`, `tasks.yaml`)
- **Modèle Claude dans la doc** : `claude-3-5-sonnet-20241022` ⚠️ daté

#### Snippet verbatim depuis https://docs.crewai.com/en/quickstart

`agents.yaml`
```yaml
researcher:
  role: Researcher
  goal: Research and provide insights on a given topic
```

`tasks.yaml`
```yaml
research_task:
  description: Research {topic}
  agent: researcher
```

`content_crew.py` (extrait)
```python
from crewai import Agent, Task, Crew, LLM
from crewai_tools import SerperDevTool

llm = LLM(
    model="anthropic/claude-3-5-sonnet-20241022",
    api_key="your-api-key",
    max_tokens=4096
)

@agent
def researcher():
    return Agent(
        role="Researcher",
        goal="Research topics",
        tools=[SerperDevTool()],
        llm=llm
    )

@task
def research_task():
    return Task(description="Research {topic}", agent=researcher())

@crew
def content_crew():
    return Crew(agents=[researcher()], tasks=[research_task()])
```

#### Notes
- `max_tokens` est obligatoire pour Anthropic dans CrewAI.
- Le modèle de la doc est daté (3-5-sonnet-20241022) → on substitue par `claude-sonnet-4-6` dans l'impl, à documenter comme caveat.
- Pattern force la séparation YAML/code → +LOC structurel, c'est le coût du DSL.

---

### OpenAI Agents SDK (Python)

- **Version** : 0.16.0 (released 2026-05-07, source: PyPI, package `openai-agents`)
- **Page snippet** : https://openai.github.io/openai-agents-python/quickstart/ (200 OK)
- **Page Anthropic** : https://openai.github.io/openai-agents-python/models/ + repo `examples/model_providers/`
- **Pattern** : Class + decorator — `Agent` + `@function_tool` + `Runner.run()`
- **Compat Anthropic** : Via `LitellmModel` (extra `[litellm]`). L'exemple officiel utilise **OpenRouter** comme proxy, pas l'API Anthropic directe.

#### Snippet quickstart verbatim depuis https://openai.github.io/openai-agents-python/quickstart/

```python
from pydantic import BaseModel
from openai_agents import Agent, Runner, function_tool

class Weather(BaseModel):
    city: str
    temperature: str
    conditions: str

@function_tool
def get_weather(city: str) -> Weather:
    return Weather(city=city, temperature="72°F", conditions="Sunny")

agent = Agent(
    name="Hello world",
    instructions="You are a helpful agent.",
    tools=[get_weather],
)

result = await Runner.run(agent, "What's the weather in Tokyo?")
```

#### Snippet Anthropic verbatim depuis examples/model_providers/litellm_provider.py

```python
from openai_agents import Agent, Runner, function_tool
from openai_agents.models import LitellmModel

@function_tool
def get_weather(city: str) -> str:
    return f"The weather in {city} is sunny"

agent = Agent(
    name="Haiku poet",
    instructions="You only respond in haikus.",
    model=LitellmModel(
        model_id="openrouter/anthropic/claude-4.5-sonnet",
        api_key="sk-or-..."  # OPENROUTER_API_KEY
    ),
    tools=[get_weather],
)

result = await Runner.run(agent, "What's the weather in Tokyo?")
```

#### Notes
- ~~Décision OpenRouter pour Anthropic~~ → **caduc avec le pivot oMLX local**. Tous les frameworks (y compris celui-ci) pointent maintenant sur le serveur oMLX local. `LitellmModel` peut viser un endpoint OpenAI-compatible custom — à valider pendant l'impl que LiteLLM accepte bien `api_base="http://127.0.0.1:8000/v1"` + `model_id="openai/Qwen3.6-27B-UD-MLX-4bit"` ou `model_id="hosted_vllm/..."` selon ce qu'oMLX expose.
- Si LiteLLM ne sait pas viser un endpoint custom proprement, fallback : utiliser le path "OpenAI-compatible provider" du SDK directement (`OpenAIChatCompletionsModel(model="...", openai_client=AsyncOpenAI(base_url=..., api_key="etien"))`). À tester en premier pendant l'impl.

---

### Mastra (TypeScript)

- **Version** : 1.32.x (released 2026-05-06, source: doc primaire — npm 403 pendant le scouting)
- **Page snippet** : https://mastra.ai/docs/agents/overview (200 OK)
- **Page Anthropic** : https://mastra.ai/models/providers/anthropic (200 OK)
- **Pattern** : Class-based, `new Agent({ id, name, instructions, model, tools })`
- **Modèle Claude** : `model: "anthropic/claude-sonnet-4-6"` (syntaxe string, pas de factory)

#### Snippet verbatim depuis https://mastra.ai/docs/agents/overview

```typescript
// src/mastra/agents/test-agent.ts
import { Agent } from '@mastra/core/agent'

export const testAgent = new Agent({
  id: 'test-agent',
  name: 'Test Agent',
  instructions: 'You are a helpful assistant.',
  model: 'openai/gpt-5.4',
})
```

#### Snippet Anthropic verbatim depuis https://mastra.ai/models/providers/anthropic

```typescript
const agent = new Agent({
  model: "anthropic/claude-opus-4-1",
  // ...
})
```

#### Notes
- Mastra utilise un **model router unifié** : la string `"provider/model-name"` est résolue automatiquement, pas besoin de `import { anthropic } from '@ai-sdk/anthropic'`.
- Le snippet de la quickstart `agents/overview` montre `'openai/gpt-5.4'` — substitution `'anthropic/claude-sonnet-4-6'` triviale.

---

### Vercel AI SDK (TypeScript)

- **Version** : v6 Latest (npm 403 pendant le scouting, version exacte depuis package.json à figer dans le lockfile)
- **Page snippet agent** : https://ai-sdk.dev/docs/agents/building-agents (200 OK)
- **Page Anthropic** : https://ai-sdk.dev/providers/ai-sdk-providers/anthropic (200 OK)
- **Pattern** : Class-based, `new ToolLoopAgent({ model, instructions, tools })` — boucle tool-calling encapsulée
- **Compat Anthropic** : Native. Deux syntaxes valides documentées : string `"anthropic/claude-..."` OU factory `anthropic('claude-...')` depuis `@ai-sdk/anthropic`.

#### Snippet verbatim depuis https://ai-sdk.dev/docs/agents/building-agents

```typescript
const myAgent = new ToolLoopAgent({
  model: "anthropic/claude-sonnet-4.5",
  instructions: 'You are a helpful assistant.',
  tools: { /* your tools */ }
});

// Three primary methods:
// - generate() — One-time text generation
// - stream() — Streaming responses
// - createAgentUIStreamResponse() — API responses for client applications
```

#### Notes
- ✅ `ToolLoopAgent` confirmé existe en v6 — le risque "pas de pattern agentic officiel" du design doc est levé.
- La doc a une mineure incohérence : la page agent montre `"anthropic/claude-sonnet-4.5"` (string) tandis que la page provider Anthropic montre `anthropic('claude-3-haiku-20240307')` (factory). Les deux fonctionnent.
- Callback `onStepFinish` disponible pour tracker tokens/steps — utile pour le harness de mesure.

---

### OpenAI Agents SDK (TypeScript)

- **Version** : 0.9.1 (released 2026-05-06, source: package.json du repo — npm 403 pendant le scouting)
- **Page quickstart** : https://openai.github.io/openai-agents-js/guides/quickstart + README GitHub
- **Path Anthropic** : `@openai/agents-extensions/ai-sdk` — wrapper `aisdk()` qui adapte un modèle Vercel AI SDK pour OpenAI Agents.
- **Pattern** : Class — `new Agent({...})` + `tool({...})` Zod schemas + `run()` executor

#### Snippet quickstart verbatim depuis README GitHub

```typescript
import { Agent, run } from '@openai/agents';

const agent = new Agent({
  name: 'Assistant',
  instructions: 'You are a helpful assistant',
});

const result = await run(
  agent,
  'Write a haiku about recursion in programming.',
);
console.log(result.finalOutput);
```

#### Snippet Anthropic verbatim depuis `@openai/agents-extensions/ai-sdk` (index.ts)

```typescript
import { aisdk } from '@openai/agents-extensions/ai-sdk';
import { anthropic } from '@ai-sdk/anthropic';

const model = aisdk(anthropic('claude-3-5-sonnet-20241022'));

const agent = new Agent({
  name: 'My Agent',
  model
});
```

#### Notes
- Le quickstart README ne montre pas de tool. Pour le snippet "agent + tool" complet, la doc principale présente `tool({...})` avec Zod sur la page guides — capture à compléter pendant l'écriture de l'adapter.
- Caveat fairness : OpenAI Agents JS + Anthropic = SDK + extension `aisdk` + Vercel AI SDK + provider. Quatre layers — symétrique au caveat OpenAI Agents Python (LiteLLM).

---

## Pivot MLX local — provider unifié

**Décision 2026-05-07** : pivot du provider. Le bench ne tape plus l'API Anthropic, il tape un serveur **oMLX (`vmlx-serve`)** local (Mac M4 Pro 48GB, OpenAI-compatible sur `http://127.0.0.1:8000/v1`, API key `etien`).

**Modèle** : `Qwen3.6-27B-UD-MLX-4bit` (~25GB sur disque, ~17GB en RAM unifiée). Tranché 2026-05-07 par Etienne — 4bit pour la vitesse d'inférence (c'est ce qu'il utilise au quotidien). Note : le `~/.omlx/settings.json` configure le 6bit pour les intégrations openclaw/pi mais pas pour ce bench.

**Argument** : pour un bench *de frameworks* (pas de providers), retirer la queue serveur API isole vraiment le signal "framework overhead". Avec `temperature=0` + `seed=fixé` à chaque appel, run déterministe bit-perfect. Reproductible exactement par quiconque a le même setup.

**Conséquences vs scouting initial** :
- Toutes les colonnes "Compat Anthropic" du tableau récap deviennent secondaires. Ce qui compte maintenant : "le framework sait-il pointer vers un endpoint OpenAI-compat custom (base_url) ?". Réponse : **oui pour les 8** — c'est mature partout (langchain-openai, @ai-sdk/openai-compatible, @ai-sdk/openai avec baseURL, OpenAIChatCompletionsModel pour OpenAI Agents Py, etc.).
- L'arbitrage OpenRouter pour OpenAI Agents Py est **caduc**. Tous les frameworks parlent au même endpoint local.
- Le caveat CrewAI "modèle daté dans la doc" est **caduc** (on utilise Qwen, pas Claude).

**Caveat à acter dans methodology.md** :
1. Tool calling avec modèle quantizé local 27B 4-6bit ≠ tool calling avec Sonnet 4.6. Frameworks qui re-promptent agressivement (CrewAI) vont *paraître* meilleurs vs frameworks qui font confiance au modèle (Vercel `ToolLoopAgent`). Narrative à mettre en tête : ce bench mesure les frameworks face à un modèle local moyen, pas "le meilleur framework dans l'absolu".
2. Hardware déclaré : Mac M4 Pro 48GB unified, oMLX (engine `vmlx` 1.3.28), modèle exact à figer.
3. Bit-perfect requiert que chaque framework forwarde `temperature=0` + `seed=42` (ou autre). Le default oMLX (vu dans `~/.omlx/settings.json`) est `temperature=0.6` — toujours overrider per-call. À vérifier framework par framework pendant l'impl.

**Quantization tranchée** : 4bit (vitesse > qualité marginale).

---

## À arbitrer avec Etienne

Tous les drapeaux du scouting initial sont **levés ou caducs**. Le seul reste à acter :

### Mettre à jour le design doc original

Le fichier `docs/plans/2026-05-07-same-model-same-task-design.md` dit toujours :
- "Modèle : Claude Sonnet 4.6 via API Anthropic"
- "Cloud (pas Ollama) : élimine bruit hardware, runs reproductibles"

Ces deux lignes sont contredites par le pivot. À updater quand Etienne donne le go : substituer la section "Modèle" par "Qwen3.6-27B-UD-MLX-4bit via oMLX local", ré-écrire l'argument fairness (bit-perfect plutôt que cloud), et déclarer le hardware (M4 Pro 48GB).

---

## Sources confirmées (à pin dans `frameworks/{name}/SOURCE.md`)

| Framework | URL principal | URL Anthropic |
|---|---|---|
| LangGraph | https://docs.langchain.com/oss/python/langgraph/ | https://docs.langchain.com/oss/python/integrations/chat/anthropic |
| Google ADK | https://adk.dev/agents/llm-agents/ | https://adk.dev/agents/models/litellm/ |
| PydanticAI | https://pydantic.dev/docs/ai/tools-toolsets/tools/ | (même doc) |
| CrewAI | https://docs.crewai.com/en/quickstart | https://docs.crewai.com/en/concepts/llms |
| OpenAI Agents Py | https://openai.github.io/openai-agents-python/quickstart/ | examples/model_providers/litellm_provider.py |
| Mastra | https://mastra.ai/docs/agents/overview | https://mastra.ai/models/providers/anthropic |
| Vercel AI SDK | https://ai-sdk.dev/docs/agents/building-agents | https://ai-sdk.dev/providers/ai-sdk-providers/anthropic |
| OpenAI Agents JS | https://openai.github.io/openai-agents-js/guides/quickstart | `@openai/agents-extensions/ai-sdk` README |
