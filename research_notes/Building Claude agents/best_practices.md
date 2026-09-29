# Building efficient, reliable Claude agents (as of Sept 2026), applied to the IAMGOD daily trading system

Scope note: I read `trading/trader/llm.py` and `trading/trader/engine.py` first. Current design: one Messages API call per book per day (`review_rules_plan` for the rules book, `decide` for the Claude book), `output_config.format` json_schema, adaptive thinking, `effort: high`, `max_tokens: 16000`, model `claude-opus-5` (config/playbook.yaml), `cache_control` on a static reference block (playbook_brief.md + risk_policy.yaml, about 4.2 KB, roughly 1K tokens) placed *after* a per-call role block, server-side refusal fallback (`fallbacks: "default"` + beta header `server-side-fallback-2026-07-01`), pydantic validation, and a deterministic RiskEngine applied afterwards.

Source notes: Items marked **[local skill doc]** come from the bundled claude-api skill docs at `/tmp/claude-0/bundled-skills/2.1.283/60004edada16eb77d914fd0c5ff04600/claude-api/shared/`. The task brief calls these authoritative. They cannot be linked on the web, so I cite them by file path. Items from anthropic.com and platform.claude.com were fetched in full through WebFetch, which returns a summary made by a small model, so treat exact wording as close but not guaranteed verbatim. Items marked **[snippet only]** come from search-result snippets and were not fetched. arxiv.org is blocked by the egress proxy.

## 1. Anthropic's official guidance on agent design (patterns, context, tools, multi-agent, SDK / Managed Agents, long-running harnesses)

### Takeaway
Anthropic's consistent message is to use the simplest thing that works. Start with one well-built LLM call. Move to a fixed "workflow" (chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer) only when an eval shows that it helps. Reserve autonomous agents for open-ended tasks. The daily trading system is correctly a **workflow**: code-defined paths plus a single judgment call. It is not an agent and should stay that way. The relevant upgrades are chaining/voting/evaluator patterns, context hygiene and tool/ACI discipline, not autonomy.

### Cited Findings
**Building effective agents (workflows vs agents)**
- Definitions: workflows are "systems where LLMs and tools are orchestrated through predefined code paths"; agents are "systems where LLMs dynamically direct their own processes and tool usage." — [Anthropic, Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- "Start with simple prompts, optimize them with comprehensive evaluation, and add multi-step agentic systems only when simpler solutions fall short"; for many applications "optimizing single LLM calls with retrieval and in-context examples is usually enough." — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Agents fit "open-ended problems where it's difficult or impossible to predict the required number of steps, and where you can't hardcode a fixed path"; they carry "higher costs, and the potential for compounding errors" and need "extensive testing in sandboxed environments, along with appropriate guardrails." — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Patterns and when to use each:
  - **Prompt chaining**: when "the task can be easily and cleanly decomposed into fixed subtasks."
  - **Routing**: when there are "distinct categories that are better handled separately."
  - **Parallelization**: either sectioning (independent subtasks) or **voting** ("Running the same task multiple times to get diverse outputs").
  - **Orchestrator-workers**: when "you can't predict the subtasks needed."
  - **Evaluator-optimizer**: when "we have clear evaluation criteria, and when iterative refinement provides measurable value."
  - Source: [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Three principles: simplicity, transparency ("explicitly showing the agent's planning steps"), and careful agent-computer interface (ACI) design through tool documentation and testing. — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- On frameworks: they "often create extra layers of abstraction that can obscure the underlying prompts and responses"; "Start by using LLM APIs directly; many patterns can be implemented in a few lines of code." — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Agents should be able to "pause for human feedback at checkpoints or when encountering blockers." — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)

**Effective context engineering (Sept 29, 2025)**
- Context rot: "as the number of tokens in the context window increases, the model's ability to accurately recall information from that context decreases." Aim for the "smallest possible set of high-signal tokens that maximize the likelihood of some desired outcome." — [Anthropic, Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- System prompts should sit at the "right altitude": neither brittle hardcoded logic nor vague generalities, but "specific enough to guide behavior effectively, yet flexible enough to provide the model with strong heuristics." Organize them into sections with XML tags or Markdown headers. — [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Use a few diverse, canonical examples rather than an exhaustive list of edge cases. Prefer just-in-time retrieval over pre-loading everything. For long tasks, use compaction, structured note-taking to external memory files, and sub-agents that return condensed summaries. — [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- "If a human engineer can't definitively say which tool should be used in a given situation, an AI agent can't be expected to do better." — [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

**Writing effective tools for agents (Sept 11, 2025)**
- Build "a few thoughtful tools targeting specific high-impact workflows" instead of wrapping every endpoint; consolidate (e.g., `schedule_event` instead of list_users + list_events + create_event); "More tools don't always lead to better outcomes." — [Anthropic, Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- Namespace tools with shared prefixes. Return "only high signal information." Prefer semantic identifiers to UUIDs. Offer a `response_format` enum (concise/detailed); in their example, concise responses used about a third of the tokens (72 vs 206). Use pagination, filtering and truncation with sensible defaults. Give parameters unambiguous names (`user_id`, not `user`). — [Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents)
- For tool evals, track top-level accuracy, total runtime, number of tool calls, token consumption and tool errors, on realistic multi-step tasks. — [Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents)
- Tool surface heuristic: "Start with bash for breadth. Promote to dedicated tools when you need to gate, render, audit, or parallelize the action." Hard-to-reverse actions are candidates for a dedicated, gated tool. — [local skill doc] `shared/agent-design.md`

**Multi-agent research system (June 13, 2025)**
- Token usage alone explained 80% of performance variance on BrowseComp. Multi-agent systems use "about 15× more tokens than chats" (single agents about 4×). The Opus 4 lead with Sonnet 4 subagents beat single-agent Opus 4 by 90.2% on their internal research eval. — [Anthropic, How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Multi-agent is a poor fit for "most coding tasks" and for domains that need shared context and tight coordination. It suits heavily parallel, high-value tasks whose information exceeds a single context window. — [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Production lessons:
  - Stateful errors compound, so resume from checkpoints.
  - Run full production tracing.
  - Use "rainbow deployments" to shift traffic between versions gradually.
  - Start evals with about 20 queries, grade with an LLM judge rubric (factual accuracy, citation accuracy, completeness, source quality, tool efficiency), and keep human evaluation.
  - Claude rewriting tool descriptions after diagnosing failures cut task completion time by 40%.
  - Source: [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- The local skill doc's measured guidance on orchestrators: they pay off "only when there is bulk to hand off." When "the work is one dependent chain, or fits in a single context," a single model at lower effort came out ahead in every case measured. — [local skill doc] `shared/cost-optimization.md` §2.7

**Long-running harnesses (Nov 26, 2025)**
- The recommended pattern:
  - An initializer session sets up an `init.sh` and a progress log (`claude-progress.txt`).
  - A structured JSON feature list is created, with every item starting as failing.
  - The agent works on "only one feature at a time."
  - It commits to git with descriptive messages and writes progress summaries.
  - It verifies features end to end before marking them done.
  - Source: [Anthropic, Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

**Agent SDK / Managed Agents / platform features**
- Managed Agents: a persisted, **versioned** Agent config (model, system prompt, tools, MCP servers, skills). Sessions pin to a version, which "lets you iterate on the agent ... roll back if a change regresses, and A/B test versions side-by-side." It is in beta (`managed-agents-2026-04-01`). — [local skill doc] `shared/managed-agents-overview.md`
- Managed Agents "Outcomes": you state a rubric; the harness runs an iterate-grade-revise loop in which a **separate grader with an independent context window** scores each iteration. — [local skill doc] `shared/managed-agents-outcomes.md`
- Managed Agents scheduled deployments: cron with an IANA timezone. Execution is jittered by "up to 15% of the interval between runs ... capped at 9 minutes", so "don't build a downstream deadline that assumes the listed timestamp." — [local skill doc] `shared/managed-agents-scheduled-deployments.md`
- Anthropic's finance agent templates (May 5, 2026) ship as plugins and Managed Agents cookbooks, with "a full audit log in the Claude Console where compliance and engineering teams can inspect every tool call and decision." — [Anthropic, Agents for financial services](https://www.anthropic.com/news/finance-agents)
- Long-context features (context editing, compaction, memory) are for multi-turn loops. Context editing "is a context-window tool, not a savings lever" because every clearing pass breaks the cache. — [local skill doc] `shared/agent-design.md`, `shared/cost-optimization.md` §2.3

### Inferences
- The current system is already a well-shaped **workflow**: deterministic signals, then one LLM judgment, then deterministic risk enforcement. Nothing in Anthropic's guidance argues for making it autonomous. The task is small, fits in one context and is a single dependent chain, which is the case where the measured guidance says a single call beats an orchestrator.
- Upgrades that fit the patterns:
  - **Prompt chaining**: split "analyze" from "decide", or add a separate "critic" pass.
  - **Voting/parallelization**: sample N decisions and aggregate (see §3).
  - **Evaluator-optimizer**: a cheap second call checks the decision against the rules, with deterministic code as the final arbiter.
- If data-lookup tools are ever added (news, earnings calendar), follow the tool guidance: few, consolidated, read-only tools with concise responses. Order-placing actions must never be exposed as a tool; keep them in code.
- Managed Agents versioning and the audit log are attractive for prompt versioning and audit. They add beta dependencies and scheduling jitter, though, and a plain daily cron plus the Messages API is simpler and more deterministic for this use.

### Gaps
- I did not fetch the Claude Agent SDK docs page directly. The SDK-specific notes above come from the local skill docs and the engineering posts.
- I did not find a dedicated Anthropic post on "agents for trading or portfolio decisions".

## 2. Efficiency: caching, batch, model choice, effort, tokens, structured outputs vs tool use

### Takeaway
For one or two calls a day, **the current prompt caching almost certainly never produces a cache read**. The gap between runs is far longer than any TTL, the role text sits *before* the cached block (so the two calls have different prefixes), and the two calls use different output schemas, which also invalidates the cache. You are likely paying a 1.25× write premium on about 1K tokens for nothing. Cost here is dominated by thinking and output tokens, so the real levers are effort, model choice and the output budget. Tune them against an eval. Batch is 50% off but gives no latency guarantee.

### Cited Findings
**Prompt caching**
- "Prompt caching is a prefix match. Any change anywhere in the prefix invalidates everything after it." Render order is tools, then system, then messages. — [local skill doc] `shared/prompt-caching.md`
- TTLs:
  - The default is 5 minutes; `"ttl": "1h"` is optional.
  - Writes cost 1.25× (5-minute) or 2× (1-hour); reads cost about 0.1× (0.05× on Opus 5.5, 0.025× on Fable 5.1).
  - The TTL clock starts at the **start** of the request.
  - For gaps over an hour, "Neither helps directly - re-warm on a schedule ... or accept the cold miss."
  - Source: [local skill doc] `shared/prompt-caching.md` §Choosing the TTL; pricing multipliers also on [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview.md)
- Minimum cacheable prefix: 512 tokens on Opus 5 / Fable 5 / Fable 5.1 / Mythos 5.x; 1024 on Opus 4.8 and Sonnet 5; 4096 on Opus 4.5/4.6 and Haiku 4.5. "Shorter prefixes silently won't cache even with a marker." — [local skill doc] `shared/prompt-caching.md`
- Don't cache when there is no reusable prefix: "Adding `cache_control` only pays the cache-write premium with zero reads." — [local skill doc] `shared/prompt-caching.md`
- "Changing the `output_config.format` parameter will invalidate any prompt cache for that conversation thread"; structured outputs also inject an extra system prompt that costs tokens. — [Structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs.md)
- Changing thinking or effort invalidates the messages cache, and on some models the system/tools cache too, so pin them per route. — [local skill doc] `shared/prompt-caching.md` §Invalidation hierarchy
- Verify caching from `usage` (`cache_read_input_tokens`, `cache_creation_input_tokens`), not from code review. Keep a standing check (for example, a test that a second identical request reads from cache). — [local skill doc] `shared/prompt-caching.md` §Verifying cache hits
- Silent invalidators to check for: `datetime.now()` in the prefix, `json.dumps` without `sort_keys=True`, and conditional system sections. — [local skill doc] `shared/prompt-caching.md`

**Batch API**
- 50% off every token, including cache reads and writes. Results arrive asynchronously "within 24 hours; that window is an expiry, not an SLA." Requests are single-shot, with no mid-batch tool loop. Structured outputs work with batch. — [local skill doc] `shared/cost-optimization.md` §2.5; [Structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs.md); [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview.md)

**Models and prices (Sept 2026)**
- Current lineup (per MTok input / output):
  - Fable 5.1 `claude-fable-5-1`: $10 / $50, default effort `high`.
  - Opus 5.5 `claude-opus-5-5`: $4 / $20, default effort `medium`.
  - Sonnet 5 `claude-sonnet-5`: $2 / $10, default `high`.
  - Haiku 4.5 `claude-haiku-4-5-20251001`: $1 / $5, no effort parameter. Haiku 4.5 retirement is "not sooner than October 15, 2026."
- The docs say: "start with Claude Opus 5.5 for most workloads." Every model ID is a pinned snapshot. Opus 5 (currently configured) is listed as legacy but still available.
- Source: [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview.md)
- Opus 5.5 migration:
  - Thinking can't be disabled; effort is the control.
  - Forced `tool_choice` returns a 400.
  - Default effort is `medium` (Opus 5's is `high`).
  - Broader safety classifiers: `bio` and `reasoning_extraction` join `cyber`. A prompt that pushes the model to reproduce its internal reasoning in the output can be declined with `stop_details.category: "reasoning_extraction"`.
  - Size `max_tokens` for thinking plus the reply.
  - Source: [local skill doc] `shared/model-migration.md` §Migrating to Claude Opus 5.5
- The skill doc says to migrate to Opus 5.5 "only when the user names it", because the doc was written ahead of launch, while the live models page already recommends Opus 5.5 as the default. — [local skill doc] `shared/model-migration.md`; contrasted with [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview.md)

**Effort, budgets, model choice**
- Optimize "cost per completed task, not cost per token." Free wins come first (caching, input hygiene, batch); tradeoffs come last (effort, then model). — [local skill doc] `shared/cost-optimization.md`
- Measured effort curves:
  - Knowledge work is nearly flat: `medium` matched the default's accuracy at 70–85% of its cost; `low` gave up 1–3 points for a third to a half off.
  - Coding: Opus 5 lost about 2 points at `medium` for half the cost.
  - Source: [local skill doc] `shared/cost-optimization.md` §2.6
- "Re-run failures at higher effort" when you have a failure signal. Run at `low` and escalate failures: about 93% pass for about $0.70 per task vs 91.7% for $1.39 all-default. — [local skill doc] `shared/cost-optimization.md` §2.6
- "Price the tail, not the median": compare models on the hardest tenth of the workload. Haiku 4.5 fits "high-volume work with checkable outputs, not long agentic loops." — [local skill doc] `shared/cost-optimization.md` §2.7
- `max_tokens` is "a backstop, not a tuning knob." A 16,384 cap ended 15% of Opus 5 coding attempts. Treat `stop_reason: max_tokens` as a failed attempt. — [local skill doc] `shared/cost-optimization.md` §2.4

**Structured outputs vs tool use**
- JSON outputs (`output_config.format`) are for controlling the response format. Strict tool use (`strict: true`) guarantees valid tool arguments. Combine them for agent loops. — [Structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs.md)
- On Opus 5.5 / Fable 5.1, forced `tool_choice` returns a 400. "If the forced call existed only to get JSON back, replace it with structured outputs." — [local skill doc] `shared/model-migration.md`
- The first use of a schema adds latency while the grammar compiles. Grammars are cached for 24 hours from last use. — [Structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs.md)

### Inferences
- **Caching as implemented is probably a pure surcharge.** The system list is `[role (differs per call), reference (cache_control)]`, so the cached prefix includes the role text and differs between review and decide. The schemas also differ, which invalidates the cache, and runs are about 24 hours apart. Options:
  - (a) Remove `cache_control`. The cost is trivial either way at about 1K tokens.
  - (b) Keep it only if you add multi-sample voting (§3). Then make the N samples of the *same* call byte-identical and send them sequentially after the first starts streaming, so samples 2..N read the cache. The skill doc notes parallel requests cannot read a cache that is still being written.
  - Either way, log `cache_creation_input_tokens` as well as reads (llm.py currently logs only reads) so this is measurable.
- **Model/effort:** on Opus 5.5 the default effort is `medium` and the price is lower than Opus 5's. For a once-a-day, low-volume decision, cost is small in absolute terms, so pick the model and effort by eval quality and run-to-run stability, not token price. A reasonable sweep is Opus 5.5 at `medium` / `high` / `xhigh` vs Fable 5.1 at `medium`, keeping the cheapest cell that holds quality within noise.
- **max_tokens 16000** at `effort: high` risks truncation on long thinking. Consider 32K–64K, since it is only a backstop and you pay for tokens actually generated.
- **Batch:** a 50% discount is real, but no latency is guaranteed, which is risky before market open. Batch fits eval replays, backtests and multi-sample research runs well. It is not recommended for the live pre-open decision unless there are hours of slack and a fallback path.

### Gaps
- The exact token size of the reference block and the per-call thinking-token spend are not measured. `response.usage` history from the journal would settle the cost profile.
- I did not fetch the live pricing page for batch or long-context specifics beyond the models-overview footnote.

## 3. Reliability: evals, graders, guardrails, HITL, observability, refusals/failures, run-to-run variance, prompt versioning

### Takeaway
Build a small frozen eval (20–50 real historical days) with **programmatic graders on end state**, such as whether it respected constraints, whether the JSON was valid and whether the "hold" decision was right, plus a rubric judge only for the prose. Run multiple reps and report variance. Separate infra failures from model failures. Sampling parameters are no longer available and `temperature=0` never guaranteed determinism, so handle variance by **sampling N and aggregating** (voting / median) and measuring pass^k. Version prompts and schemas with hashes stored next to every decision.

### Cited Findings
**Evals**
- Start with "20-50 simple tasks drawn from real failures." There are three grader types:
  - Code-based: "Fast, Cheap, Objective, Reproducible" but brittle.
  - Model-based: flexible but "Non-deterministic ... Requires calibration."
  - Human: the gold standard, but slow.
  - Source: [Anthropic, Demystifying evals for AI agents (Jan 9, 2026)](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- pass@k is the chance of at least one success in k tries; **pass^k is "the probability that all k trials succeed"**. For a production decision system, pass^k is the consistency metric. — [Demystifying evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Isolate trials (a clean environment each time). Grade outcomes, not exact tool-call sequences. Balance cases where a behavior should and shouldn't occur. Capability evals start low; regression evals should sit near 100%. "Read the transcripts." — [Demystifying evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- Prefer programmatic checks when the output space is constrained: a number, a label from a closed set, "JSON validates against schema." For agents that act, grade the end state. For judges:
  - Use structured outputs for the judge.
  - Write concrete, checkable rubric claims.
  - Don't use the model under test as its own judge.
  - Randomize A/B order in pairwise comparisons and allow `tie` / `both_bad`.
  - Source: [local skill doc] `shared/evals/build-eval.md`
- Keep infra failures (API errors, timeouts, truncation, served-model mismatch) out of the scores, in an `errors.jsonl` sidecar. "Fail the attempt loudly when a response's `model` differs from the requested one ... a silently substituted model (a provider fallback, a capacity reroute) invalidates the comparison." — [local skill doc] `shared/evals/build-eval.md`
- "A single rep is a point estimate with no error bar." The noise floor for a pass rate is about `1/sqrt(n·reps)`: 25 cases × 2 reps is about ±14 points; 100 × 2 is about ±7. Pin seeds, sort anything order-dependent, and use production sampling settings. Run a grader twice to measure grader variance. — [local skill doc] `shared/evals/eval-audit.md`
- The bar for a production cutover is "around fifty cases and at least five trials per configuration"; "Never keep or revert on a one-case swing." — [local skill doc] `shared/cost-optimization.md` Step 3
- Record an environment fingerprint with each baseline (repo commit, lockfile hash, model id) and re-baseline when it changes. — [local skill doc] `shared/evals/eval-hillclimb.md`
- Treat the eval as a living suite: new production failure modes become cases. — [local skill doc] `shared/evals/eval-audit.md`

**Determinism / variance**
- On Opus 4.7 and later (including Opus 5 / 5.5 and Fable 5.x), `temperature`, `top_p` and `top_k` return a 400. "If you were using `temperature = 0` for determinism, note that it never guaranteed identical outputs on prior models." — [local skill doc] `shared/model-migration.md`; `shared/error-codes.md`
- Anthropic's consistency and hallucination guidance:
  - Use structured outputs for schema conformance, constrain with examples, and chain prompts.
  - **"Best-of-N verification: Run Claude through the same prompt multiple times and compare the outputs. Inconsistencies across outputs could indicate hallucinations."**
  - Prefill is not supported on Claude 4.6+.
  - Sources: [Increase output consistency](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/increase-consistency.md); [Reduce hallucinations](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations.md)
- The parallelization/voting pattern ("Running the same task multiple times to get diverse outputs") is recommended when "multiple perspectives provide better confidence." — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)

**Refusals and failures**
- Refusals and `max_tokens` can occur even with structured outputs, and "The output may not match your schema"; "Always check the response's `stop_reason` field." — [Structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs.md)
- `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) is "recommended for every caller." It re-runs a declined request on another model server-side, routed by refusal category. Prefer it over pinning a fallback model. — [local skill doc] `shared/model-migration.md`
- Structured outputs do **not** support `minimum` / `maximum` / `multipleOf` or string length limits. Numeric bounds must be enforced in code. — [Structured outputs docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs.md)

**Guardrails / HITL / observability / versioning**
- Finance agent posture: "Users stay firmly in the loop—reviewing, iterating on, and approving Claude's work before it ... is acted on"; they also provide a full audit log of every tool call and decision. — [Agents for financial services](https://www.anthropic.com/news/finance-agents)
- Multi-agent production: full tracing, checkpoint and resume, and rainbow deployments for version changes. — [Multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Managed Agents: immutable agent versions that sessions pin to, for rollback and A/B testing. — [local skill doc] `shared/managed-agents-overview.md`
- Promote hard-to-reverse actions to dedicated, gated tools so the harness can "intercept, gate, render, or audit." — [local skill doc] `shared/agent-design.md`

### Inferences (concrete for this codebase)
- **Pydantic bounds can kill a whole decision.** `Action.target_pct_equity` has `ge=0, le=1`, and `stop_price` has `ge=0`, but the JSON schema cannot express those bounds. One out-of-range number therefore raises `ClaudeError` and throws away the entire decision, and the book holds. Consider removing the `ge`/`le` checks from the pydantic model and clamping or rejecting per action in `decision_to_targets` / the RiskEngine, logging each clip. That fits the existing "code clips anything outside limits" contract.
- **Handle the fallback model explicitly.** `response.model` is already logged. Also flag when it differs from the configured model, record `stop_details` on refusals, and keep the fallback model's decisions tagged so evals and performance attribution aren't contaminated.
- **Variance handling.** Sample the decision call N times (e.g., 3–5) with byte-identical requests.
  - Aggregate numeric outputs per symbol with the median, which is robust to one outlier sample.
  - Take the median of each sleeve weight and renormalize.
  - Act only on changes a majority of samples agree on; otherwise hold.
  - Record the spread as an uncertainty signal and a hallucination tripwire, per the "best-of-N verification" guidance.
  - Measure pass^k on the eval to decide whether N > 1 is worth the cost.
  - This is my synthesis of Anthropic's voting and best-of-N guidance; Anthropic does not publish a "median of N" recipe for decisions.
- **Eval set design.** Freeze about 30–50 historical trading days, including stressed regimes, earnings weeks and data glitches, with the frozen `build_context` output as the input. Programmatic graders:
  - Schema validity.
  - Zero risk-limit clips needed. Clips mean the model ignored the policy.
  - No actions on non-allowlisted symbols.
  - Stops below price.
  - "Skip nothing" on control days, and "flag" on days with a planted anomaly.
  - Use a Sonnet- or Opus-class judge only for journal/market_view quality against a concrete rubric.
  - Report the pass rate with ±CI across reps. Store the `(prompt_hash, schema_hash, model, effort)` fingerprint.
- **Prompt versioning.** Hash `REVIEW_ROLE`, `DECIDE_ROLE`, the reference block and the schema. Write the hashes into each day's journal record along with the full rendered request. Change one thing at a time and re-run the eval before rollout. Optionally shadow-run the new prompt for a few days before switching.

### Gaps
- I found no Anthropic-published quantitative data on the run-to-run variance of Claude's numeric outputs for decision tasks. The magnitude for this workload must be measured.
- The `stop_details` field schema was not verified beyond the category names in the migration doc.

## 4. Financial-decision-specific advice: LLM judgment separated from deterministic execution, no model arithmetic, falsifiable predictions and calibration

### Takeaway
Anthropic's own finance messaging and its Project Vend experiment both point the same way. The model should work on **verified, precomputed data**. It should never invent numbers or be trusted to enforce limits, and humans or code must approve anything irreversible. The current architecture (code computes everything, Claude picks within bounds, code enforces limits) matches this. The main additions are to ground every number in the prompt, forbid free-form arithmetic, and make each daily view a scored, falsifiable forecast.

### Cited Findings
- Anthropic's finance agents pitch: "Claude ensures AI agents operate on verified data and deliver the deterministic, auditable outcomes financial workflows require"; users approve work "before it goes to a client, gets filed, or is acted on." — [Agents for financial services (May 5, 2026)](https://www.anthropic.com/news/finance-agents)
- **Project Vend** (Claude running a real shop) failure modes:
  - It told customers to pay into "an account that it hallucinated."
  - It priced "without doing any research, resulting in potentially high-margin items being priced below what they cost."
  - It was "cajoled ... into providing numerous discount codes."
  - It "did not reliably learn from these mistakes."
  - Anthropic's remedies: better tools, a CRM, memory and stronger prompting against acceding to requests.
  - Sources: [Anthropic, Project Vend (June 27, 2025)](https://www.anthropic.com/research/project-vend-1); phase two discussion at [Project Vend: Phase two](https://www.anthropic.com/research/project-vend-2) **[snippet only]**
- A third-party summary of Project Vend stresses that agents need "identity, permissions, ledgers, policy checks, memory, monitoring, and human escalation." — [Progressive Robot](https://www.progressiverobot.com/2026/04/26/agent-on-agent-commerce/) **[snippet only, secondary source]**
- Anthropic's hallucination guidance:
  - Allow "I don't know."
  - Ground answers in direct quotes.
  - Verify with citations.
  - Use "External knowledge restriction": "only use information from provided documents."
  - "Always validate critical information, especially for high-stakes decisions."
  - Source: [Reduce hallucinations](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations.md)
- Large numeric tables: "Files API plus code execution: mount the file, let the model compute in the sandbox, and only the answer enters context." — [local skill doc] `shared/cost-optimization.md` §2.2
- A third-party review of Claude for Financial Services notes that "Claude is not a deterministic calculator, and a model with a hallucinated number in it is still a model with a wrong number in it." — [ChatForest review](https://chatforest.com/reviews/claude-for-financial-services-review/) **[snippet only, secondary source]**
- Academic work exists on determinism/faithfulness harnesses for financial agents ("Replayable Financial Agents", arXiv 2601.15322) and on calibration in financial statement verification (FinVerBench, arXiv 2605.29586). — **[snippet only; arxiv blocked, not read]** [arXiv 2601.15322](https://arxiv.org/pdf/2601.15322), [arXiv 2605.29586](https://arxiv.org/pdf/2605.29586)
- Anthropic's calibration research: "Language Models (Mostly) Know What They Know" (Kadavath et al., 2022) reported that larger models are reasonably well calibrated on multiple-choice questions and can be trained to predict P(IK). — [arXiv 2207.05221](https://arxiv.org/abs/2207.05221) **[not fetched: arxiv blocked; cited from memory of the paper, verify before quoting]**

### Inferences
- **Keep the split exactly as it is.** The LLM proposes targets and weights; RiskEngine and `decision_to_targets` clip, reject and size. Consider also having code compute share quantities, stop distances, R multiples and sleeve totals. `build_context` already precomputes `unrealized_R` and `one_R_dollars`, which is good. Push this further:
  - Give the model precomputed candidate stop levels (e.g., ATR-based) to *choose from*, instead of free-typing `stop_price`.
  - Consider expressing actions in terms the code can verify, such as an enum of "keep / trim to X% / exit / enter at rules size", rather than raw floats.
- **No arithmetic by the model.** Put every derived number the model might want in the context: weights, exposures, P&L, distance to stop, vol, correlation. Instruct the model to cite only numbers present in the context. Optionally, add a deterministic post-check that every number in `rationale` / `market_view` appears in the context, or is within rounding of one. This mirrors the "verify with citations" guidance.
- **Falsifiable predictions and calibration.** Add schema fields for machine-scorable forecasts, for example:
  - `forecasts: [{symbol, horizon_days (enum 5/20), direction (enum up/down/flat), prob (number)}]` and `expected_regime_next_week` (enum).
  - Score them later in code with the Brier score and log loss, plus reliability curves by probability bucket, and compare against base rates and the rules book.
  - This turns the journal into a calibration record. It also gives an eval signal (does the model's confidence track outcomes?) without waiting months for P&L significance.
  - Anthropic does not prescribe this method; it is standard forecasting practice.
- **Anti-sycophancy and anti-overtrading.** Project Vend shows Claude's helpfulness bias can override economic sense. The DECIDE_ROLE already says "trading more usually earns less." Measure this: track turnover versus the rules book, and add an eval case where the "right answer" is doing nothing.
- **Human-in-the-loop.** This is paper trading, so full automation is fine. For live capital, Anthropic's finance posture suggests a human approval step for Claude-book deviations above a threshold. Code can compute the threshold, for example any action more than X% of equity away from the rules plan.

### Gaps
- I found no Anthropic-published guidance specifically on calibration scoring of Claude's forecasts in production, or on LLM trading agents. The recommendations above are inferences.
- The Kadavath et al. calibration claim could not be verified online (arxiv blocked).
