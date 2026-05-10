import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "Task definition, model choice, scoring rubric, and the caveats behind the same-model-same-task leaderboard.",
};

export default function MethodologyPage() {
  return (
    <main className="container mx-auto max-w-3xl px-4 pb-16">
      <header className="space-y-5 border-b border-border/60 py-14 md:py-20">
        <div className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-muted/40 px-3 py-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          <span className="size-1.5 rounded-full bg-blue-500" />
          Methodology
        </div>
        <h1 className="text-balance text-4xl font-semibold tracking-tight md:text-5xl">
          How the bench is run, and what to read into it.
        </h1>
        <p className="max-w-2xl text-pretty text-base text-muted-foreground md:text-lg">
          A fixed task, a fixed model, and eight framework adapters around them.
          Everything below documents the choices that make the numbers
          comparable — and the ones that limit how far they generalize.
        </p>
      </header>

      <div className="space-y-16 pt-12">
        <Section
          eyebrow="Task"
          title="What each framework is asked to do"
          description="A small recruiting task picked because it exercises tool-calling without rewarding model knowledge."
        >
          <p>
            The task isolates framework behavior, not model intelligence. Given
            a <Code>job_id</Code> drawn from a fixed set of 10, each adapter
            must return its top 3 candidates from a 50-row dataset, scored
            0–100 with a short justification.
          </p>
          <p>Four deterministic tools are exposed to the agent:</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              <Code>search_candidates(query, filters?)</Code> — free-text plus
              filters
            </li>
            <li>
              <Code>get_candidate_profile(candidate_id)</Code> — full profile
            </li>
            <li>
              <Code>score_match(candidate_id, job_id)</Code> — returns a
              breakdown, not an aggregate, so the model still has to reason
            </li>
            <li>
              <Code>list_jobs()</Code> — lightweight job summary
            </li>
          </ul>
          <p>
            Output is strict JSON. A run is invalid if the schema is wrong, an
            ID is hallucinated, a candidate is duplicated, or a justification
            exceeds 60 words.
          </p>
        </Section>

        <Section
          eyebrow="Model"
          title="The same model for every framework"
          description="One endpoint, one config, one set of sampling params — chosen for portability across all eight adapters."
        >
          <p>
            Every framework calls <Code>gemini-2.5-flash</Code> through Google
            AI Studio's OpenAI-compatible endpoint at{" "}
            <Code>generativelanguage.googleapis.com/v1beta/openai/</Code>, with{" "}
            <Code>temperature=0</Code> and <Code>MAX_STEPS=25</Code>.
          </p>
          <p>
            Gemini 3.1 Pro Preview was the original target; it was replaced
            because its <Code>thought_signature</Code> round-tripping fails on
            five of eight frameworks under the OpenAI-compat layer (see{" "}
            <a
              href="#thinking-model-trap"
              className="font-medium text-foreground underline decoration-muted-foreground/40 underline-offset-2 transition-colors hover:decoration-foreground"
            >
              The thinking-model trap
            </a>
            {" "}below). Flash is also the model most SaaS teams actually
            deploy — a working bench on a production model beats a broken bench
            on a flashier preview.
          </p>
        </Section>

        <Section
          eyebrow="Scoring"
          title="How outputs are evaluated"
          description="Hard checks first, then a model-based judge on the runs that survive — invalid runs never reach the rubric."
        >
          <ol className="list-decimal space-y-1 pl-5">
            <li>
              <strong className="font-semibold text-foreground">
                Programmatic validation
              </strong>
              {" "}— JSON shape, candidate IDs present in the dataset,
              justification length cap, no duplicates. A run that fails any of
              these is discarded before judging.
            </li>
            <li>
              <strong className="font-semibold text-foreground">LLM-as-judge</strong>
              {" "}— Gemini scores each surviving run on four criteria
              (relevance, score coherence, justification quality, format) and
              the criteria are aggregated into a /20 score.
            </li>
          </ol>
        </Section>

        <Section
          eyebrow="Caveats"
          title="Honest limits readers should hold"
          description="Four places where the numbers underdetermine the conclusion. Worth keeping in view while reading the leaderboard."
        >
          <Caveat label="Self-judging bias">
            Gemini judges Gemini outputs, and self-judging is documented at
            roughly 15–20% over-rating on a model's own work. The /20 scores
            are useful for ordering frameworks, not for cross-vendor comparison.
            A future swap to GPT-5 or Claude as judge would quantify the delta.
          </Caveat>
          <Caveat label="Per-framework metric availability">
            Not every SDK reports every metric the same way. CrewAI's{" "}
            <Code>tool_calls</Code> read as zero until its{" "}
            <Code>step_callback</Code> was wired in by hand; if a future SDK
            release changes that callback shape, the field will revert to{" "}
            <Code>null</Code> rather than silently mislead.
          </Caveat>
          <Caveat label="Sample size">
            The headline run is 30 trials per framework. That's enough to
            stabilize p50; p95 confidence intervals widen meaningfully below
            100 trials, so single-decimal differences shouldn't drive a
            decision.
          </Caveat>
          <Caveat label="The hidden max_tokens tax on Gemini 2.5 Flash">
            On the OpenAI-compatible endpoint, <Code>gemini-2.5-flash</Code>{" "}
            silently consumes part of the <Code>max_tokens</Code> budget on
            internal reasoning even though it is documented as a non-thinking
            model. The first judge run failed on every valid output (220 of
            220): with <Code>max_tokens=512</Code> the response was
            systematically truncated to ~20 tokens
            (<Code>finish_reason=length</Code>), producing valid-looking but
            incomplete JSON that broke at a key boundary. Bumping the budget
            to 4096 fixed it. If this bench were running on a credit-card
            account instead of an enterprise quota, the silent truncation
            would have looked like a budget save right up until someone tried
            to read the scores.
          </Caveat>
        </Section>

        <Section
          id="thinking-model-trap"
          eyebrow="The thinking-model trap"
          title={
            <>
              Why <Code>gemini-2.5-flash</Code>, not 3.x
            </>
          }
          description="The thought_signature round-trip is the single largest cross-framework gotcha this bench surfaced — and the reason for the model choice above."
        >
          <p>
            Gemini 3.x and 2.5-Pro are <strong>thinking models</strong>: they
            generate internal reasoning before each function call. Google's
            API attaches an opaque <Code>thought_signature</Code> to every
            function call returned by these models and{" "}
            <strong>expects that signature back</strong> when the agent
            re-injects the conversation history at the next turn.
          </p>
          <p>
            Frameworks that pass the response message through verbatim
            (baseline-python, baseline-typescript, Mastra, Vercel AI SDK)
            preserve the signature. Frameworks that rebuild messages into a
            "clean" provider-agnostic shape (LangGraph, PydanticAI) silently
            strip it. Google then rejects the next request with{" "}
            <Code>
              400: Function call is missing a thought_signature in functionCall parts
            </Code>
            .
          </p>
          <Callout title="Empirical breakage rates from this bench">
            <ul className="list-disc space-y-1 pl-5">
              <li>
                <Code>gemini-3.1-pro-preview</Code> — breaks 5/8 frameworks
              </li>
              <li>
                <Code>gemini-3-flash-preview</Code> — breaks 2/8 (LangGraph,
                PydanticAI)
              </li>
              <li>
                <Code>gemini-2.5-flash</Code> — works on 8/8 (not a thinking
                model, so there is no signature to preserve)
              </li>
            </ul>
          </Callout>
          <p>
            The bug doesn't surface in single-framework quickstarts. It only
            emerges when rebuilt messages meet a thinking model — exactly the
            shape most production teams arrive at by accident, having picked
            the framework first and the model second.
          </p>
        </Section>

        <Section
          eyebrow="Cross-vendor"
          title="This is bigger than Gemini"
          description="Every thinking-model vendor exposes a version of this bug. The failure mode is what differs."
        >
          <p>
            <Code>thought_signature</Code> is a Gemini-specific token, but the
            underlying class of bug — frameworks normalizing away
            vendor-specific reasoning artifacts — is universal across thinking
            models. The artifact and the symptom change; the root cause does
            not.
          </p>
          <BorderedTable
            headers={["Vendor / model", "Reasoning artifact", "Failure when stripped"]}
            rows={[
              [
                "Gemini 2.5 / 3.x",
                <Code key="g">thought_signature</Code>,
                <FailBadge key="g" kind="hard">HTTP 400</FailBadge>,
              ],
              [
                "Claude (extended thinking)",
                <span key="c">
                  <Code>signature</Code> on <Code>thinking</Code> blocks
                </span>,
                <FailBadge key="c" kind="hard">HTTP 400</FailBadge>,
              ],
              [
                "OpenAI o1 / o3 / GPT-5 thinking",
                <span key="o">
                  <Code>previous_response_id</Code> /{" "}
                  <Code>reasoning.encrypted_content</Code>
                </span>,
                <FailBadge key="o" kind="soft">Re-thinks · extra tokens</FailBadge>,
              ],
              [
                "DeepSeek R1, Qwen QwQ",
                <span key="d">
                  Inline <Code>{"<think>...</think>"}</Code> tags
                </span>,
                <FailBadge key="d" kind="soft">Reasoning truncated</FailBadge>,
              ],
            ]}
          />
          <p>
            Anthropic and Google fail loudly: HTTP 400, you find out
            immediately. OpenAI and the open-weight thinking models fail
            quietly: extra tokens, longer responses, no error to catch. The
            first kind shows up in CI; the second only shows up on the
            credit-card statement.
          </p>
        </Section>

        <Section
          eyebrow="Per-framework"
          title="How each framework should actually handle thinking models"
          description="Vendor-native paths preserve thinking artifacts; the OpenAI-compat path used here for uniformity does not."
        >
          <p>
            For transport parity, every framework in this bench is routed
            through Google's OpenAI-compatible endpoint. That single choice is
            what surfaces the <Code>thought_signature</Code> bug — it is not a
            verdict on the frameworks themselves. Each one ships a
            vendor-native path that handles thinking models correctly.
          </p>
          <BorderedTable
            headers={[
              "Framework",
              "Native Gemini path (preserves signatures)",
              "OpenAI-compat path (used here)",
            ]}
            rows={[
              [
                "LangGraph",
                <Code key="l">langchain-google-genai</Code>,
                <Code key="l2">langchain-openai + base_url</Code>,
              ],
              [
                "PydanticAI",
                <Code key="p">Agent('google-gla:gemini-3...')</Code>,
                <Code key="p2">OpenAIChatModel + base_url</Code>,
              ],
              [
                "CrewAI",
                <Code key="c">LLM(model='gemini/gemini-3...')</Code>,
                <Code key="c2">LLM(model='openai/...', api_base=...)</Code>,
              ],
              [
                "Google ADK",
                <Code key="a">LlmAgent(model='gemini-3...')</Code>,
                <Code key="a2">LlmAgent(model=LiteLlm(...))</Code>,
              ],
              [
                "Mastra",
                <Code key="m">@ai-sdk/google</Code>,
                <Code key="m2">@ai-sdk/openai-compatible</Code>,
              ],
              [
                "Vercel AI SDK",
                <Code key="v">@ai-sdk/google</Code>,
                <Code key="v2">@ai-sdk/openai-compatible</Code>,
              ],
            ]}
          />
          <Callout title="The trade-off this bench made explicitly">
            Transport uniformity (one SDK family, one endpoint) at the cost of
            vendor-specific features. Picking a non-thinking model
            (<Code>gemini-2.5-flash</Code>) keeps that trade-off from
            penalizing any single framework.
          </Callout>
          <Callout title="The trade-off your team likely makes implicitly">
            Routing through a gateway like OpenRouter or LiteLLM-as-proxy "for
            simplicity" silently drops vendor-specific features. If the
            framework is locked in (LangGraph, PydanticAI) and thinking models
            are required, the vendor-native path becomes mandatory — which
            means more SDKs in the dependency graph and more drift between
            framework adapters.
          </Callout>
        </Section>

        <Section
          eyebrow="Other caveats"
          title="What the headline numbers hide"
          description="Three findings from the 240-run dataset that deserve to be read alongside the leaderboard, not after it."
        >
          <p>
            Aggregated metrics flatten the shape of each framework's behavior.
            The three patterns below are the ones most likely to mislead a
            reader skimming p50 latency and success rate alone.
          </p>
          <Caveat label="Vercel AI SDK is the cost outlier — by design">
            At <strong>1,605 mean input tokens</strong> and{" "}
            <strong>$0.0060 per run</strong>, the Vercel AI SDK runs at roughly
            a third of the bench median ($0.018). Its{" "}
            <Code>ToolLoopAgent</Code> handles context differently from the
            other adapters — fewer tokens replayed each step, not a different
            model. Worth confirming the behavior matches expectations before
            reading the cost number as a free win.
          </Caveat>
          <Caveat label="CrewAI re-injects its DSL on every step">
            CrewAI sits at the opposite extreme:{" "}
            <strong>42,785 mean input tokens</strong> and{" "}
            <strong>$0.1072 per run</strong>, roughly 6× the bench average. The
            DSL re-serializes the agent and task configuration into the prompt
            on every step, which is invisible from the leaderboard but
            dominates the cost column.
          </Caveat>
          <Caveat label="Google ADK has no client-side step timeout">
            ADK's p95 latency is <strong>471.8s</strong> — one or two trials
            stalled for nearly eight minutes against a p50 of 19.9s. The event
            loop has no client-side cap, so a slow tool call or a stuck step
            blocks until the upstream gives up. In production, that translates
            to request handlers held open well beyond any reasonable SLO unless
            the host enforces its own timeout.
          </Caveat>
        </Section>
      </div>
    </main>
  );
}

/* ───── Layout primitives ───── */

function Section({
  id,
  eyebrow,
  title,
  description,
  children,
}: {
  id?: string;
  eyebrow: string;
  title: ReactNode;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 space-y-6">
      <div className="space-y-2">
        <div className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {eyebrow}
        </div>
        <h2 className="text-balance text-2xl font-semibold tracking-tight md:text-3xl">
          {title}
        </h2>
        {description ? (
          <p className="text-pretty text-sm text-muted-foreground md:text-base">
            {description}
          </p>
        ) : null}
      </div>
      <div className="space-y-4 text-sm leading-relaxed text-foreground/90 md:text-[15px]">
        {children}
      </div>
    </section>
  );
}

function Code({ children }: { children: ReactNode }) {
  return (
    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em]">
      {children}
    </code>
  );
}

function Caveat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border/70 bg-card/40 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1.5 text-sm leading-relaxed text-foreground/90">
        {children}
      </div>
    </div>
  );
}

function Callout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-border/70 bg-muted/30 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      <div className="mt-2 text-sm leading-relaxed text-foreground/90">
        {children}
      </div>
    </div>
  );
}

function BorderedTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border/70">
      <table className="w-full text-xs md:text-sm">
        <thead className="bg-muted/40">
          <tr>
            {headers.map((h) => (
              <th
                key={h}
                className="px-4 py-2.5 text-left font-medium text-muted-foreground"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className="border-t border-border/60 align-top last:border-b-0"
            >
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-3">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FailBadge({
  kind,
  children,
}: {
  kind: "hard" | "soft";
  children: ReactNode;
}) {
  const cls =
    kind === "hard"
      ? "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400"
      : "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-500";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${cls}`}
    >
      {children}
    </span>
  );
}
