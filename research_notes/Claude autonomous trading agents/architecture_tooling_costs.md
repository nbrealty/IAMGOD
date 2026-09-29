# Multi-agent LLM trading architectures, Claude tooling, MCP servers, and running costs (as of 2026-09-26)

Research method note: Anthropic pricing was fetched live from platform.claude.com on 2026-09-26. Several primary sites (arxiv.org, interactivebrokers.com, docs.coingecko.com, financialmodelingprep.com) were blocked by the research environment's egress proxy, so some findings below rest on search-result snippets and registry pages rather than the primary page. Those items are flagged.

## (a) Which architectures are used, which role split and decision flow works best, and should execution/risk be deterministic code or LLM?

### Takeaway
The dominant open-source pattern is the TradingAgents "trading firm" pipeline: parallel analysts, then a bull/bear debate, then a trader, then a risk debate, then a portfolio-manager gate, with a cheap "quick-think" model for data work and a strong "deep-think" model for judgement. Other designs add layered memory with reflection (FinMem) or investor-persona ensembles (ai-hedge-fund). Live and population-scale evaluations published in 2025–2026 show most LLM agents do not beat buy-and-hold on a risk-adjusted basis, and their returns are mostly market/factor exposure. The defensible production design keeps the LLM in the research and proposal loop and puts position limits, risk checks and order execution in deterministic code.

### Cited Findings
**TradingAgents (TauricResearch)**
- Roles: an Analyst Team (Fundamentals analyst for financial statements and valuation; Sentiment analyst for StockTwits/Reddit; News analyst for macro and global news; Technical analyst for MACD/RSI etc.), then a Researcher Team of bullish and bearish researchers who "critically debate analyst insights through structured discussion", a Trader agent that sets timing and position size, and Risk Management plus a Portfolio Manager who "approves/rejects trade proposals before execution". — [TradingAgents GitHub](https://github.com/TauricResearch/TradingAgents)
- Flow: analysts → researchers (debate rounds) → trader → risk assessment → portfolio manager approval. Built on **LangGraph**. — [TradingAgents GitHub](https://github.com/TauricResearch/TradingAgents)
- Config splits `deep_think_llm` (complex reasoning) from `quick_think_llm` (routine tasks). Other settings are `max_debate_rounds` and `temperature`. Anthropic Claude is one of 15+ supported providers. The README's defaults are OpenAI models. — [TradingAgents GitHub](https://github.com/TauricResearch/TradingAgents)
- Memory: a Decision Log appends outcomes to `~/.tradingagents/memory/trading_memory.md`, and later runs "fetch realized returns and inject prior lessons". There is an optional per-ticker SQLite checkpoint for resuming runs. — [TradingAgents GitHub](https://github.com/TauricResearch/TradingAgents)
- Data vendors: SEC EDGAR, FRED, Alpha Vantage, Yahoo Finance. — [TradingAgents GitHub](https://github.com/TauricResearch/TradingAgents)
- Releases: v0.4.0 (2026-08) fixed look-ahead and added trader price grounding. v0.5.0 (2026-09) added "point-in-time integrity, portfolio-aware runs, backtesting grid support". v0.5.1 (2026-09) followed. The repo shows about 108.8k stars and 20.8k forks. It is labelled "designed for research purposes… not intended as financial… advice". — [TradingAgents GitHub](https://github.com/TauricResearch/TradingAgents)

**AI Hedge Fund (virattt/ai-hedge-fund)**
- Uses "investor agents" (famous-investor personas) plus a risk manager and a portfolio manager. Supports Anthropic, OpenAI, DeepSeek, Google, xAI and Kimi. Data comes from the Financial Datasets API. States "the system does not actually make any trades". Has a `--backtest` mode that "withholds the ticker, industry and calendar dates from the investor agents' prompts" to reduce model memorization bias. About 63.8k stars. — [ai-hedge-fund GitHub](https://github.com/virattt/ai-hedge-fund)
- Note: the fetched README excerpt did not list the persona names, so the exact persona roster is not verified here.

**FinMem**
- Three modules: Profiling (agent character and risk disposition), Memory ("working memory and layered long-term memory" that ranks information by relevance and timeliness), and Decision-making. — [arXiv 2311.13743](https://arxiv.org/abs/2311.13743); also [AAAI Symposium Series](https://ojs.aaai.org/index.php/AAAI-SS/article/view/31290)

**FinAgent**
- Described as having "diversified memory retrieval" and tool augmentation, plus multimodal inputs. This comes from a search snippet only; the primary paper was not fetched. — [search result context, arXiv 2406.11903 survey](https://arxiv.org/pdf/2406.11903)

**FinRobot (AI4Finance)**
- Four layers: Financial AI Agents (Financial Chain-of-Thought), Financial LLM Algorithms, LLMOps/DataOps, and Multi-source Foundation Models. Agents follow a perception→brain→action loop. Agent types are Market Forecasting, Document Analysis and Trading Strategies. The main strength is equity-research report generation. V0 ran on AutoGen, V1 on the OpenAI Agents SDK, V2 on PydanticAI, and V3 is in development. About 8.1k stars. — [FinRobot GitHub](https://github.com/AI4Finance-Foundation/FinRobot)

**Evidence on performance (why deterministic guardrails matter)**
- StockBench: "most models struggle to outperform the simple buy-and-hold baseline", though some show higher returns and better risk management. — [StockBench arXiv 2510.02209](https://arxiv.org/html/2510.02209v2) (search snippet; arXiv fetch blocked)
- A live multi-market benchmark reported LLM agents trading profitably in real time and "often surpassing simple buy-and-hold". It also found that performance "depends heavily on design philosophy and market context" and that model rankings shifted between downturn and upturn periods. — [When Agents Trade, arXiv 2510.11695](https://arxiv.org/html/2510.11695v2) (search snippet)
- A 2026 study found LLM agents' headline returns are "largely explained by passive exposure to market and style factors", with one model at "near-zero stock-selection alpha and the rest measurably negative". The search snippet did not say clearly which paper this was. The likely source is the six-month production study [arXiv 2609.05663](https://arxiv.org/pdf/2609.05663) or [arXiv 2605.28359](https://arxiv.org/html/2605.28359v1). Unverified.
- A hybrid design that combined "LLM specialists and rule-based signals" finished first in the FinMMEval 2026 live task on TSLA: +13.51% against −14.7% for buy-and-hold. — [arXiv 2607.12233](https://arxiv.org/pdf/2607.12233) (search snippet; a single short live window, not statistically meaningful)

### Inferences
- A good role split for a Claude build is:
  1. Deterministic data layer (Python), which fetches and computes indicators and factors.
  2. Cheap per-ticker analyst summarizers (Haiku 4.5 or Sonnet 5 at low effort) that return structured JSON.
  3. An optional bull/bear critique pass (Sonnet 5).
  4. One portfolio-level decision call on a strong model (Opus 5.5 / Opus 5) that outputs target weights with rationale as schema-validated JSON.
  5. A **deterministic** risk engine that enforces max position %, gross/net exposure, sector caps, drawdown kill-switch, liquidity/ADV limits, and a whitelist of symbols and order types.
  6. **Deterministic** execution code that diffs targets against positions and sends orders via the broker SDK. The LLM never places orders directly in live mode.
- A portfolio-level decision call (all tickers in one prompt) is far cheaper than TradingAgents' per-ticker full pipeline. It also lets the model reason about correlation and cash, which the per-ticker design handles poorly. TradingAgents v0.5.0 only recently added "portfolio-aware runs".
- Reflection memory (FinMem- or TradingAgents-style decision log plus realized P&L) is cheap to add. Given the factor-exposure findings, evaluate it with factor-adjusted metrics, not raw return.
- Backtests of LLM agents are contaminated by look-ahead and memorization: the models were trained on the historical outcomes being tested. Mitigations include ai-hedge-fund's anonymization and TradingAgents' point-in-time work. Paper-trading forward tests are the only clean evaluation.

### Gaps
- Could not fetch the arXiv primary texts (egress blocked), so the numeric results of StockBench, 2609.05663 and 2605.28359 are not verified beyond snippets.
- No controlled study was found comparing "debate" against "single strong model" role designs on the same live window.

## (b) Claude-specific tooling: Agent SDK (Python), API tool use, structured outputs, MCP integration, caching, batch

### Takeaway
There are three self-hosted ways to build this in Python.
- **Messages API with tool use.** You own the loop, or use the SDK's `tool_runner`. This is the best fit for a deterministic pipeline of fixed LLM calls.
- **Claude Agent SDK** (`pip install claude-agent-sdk`, which is the Claude Code harness as a library). It gives you subagents, hooks, `can_use_tool` permission callbacks, in-process MCP tools, `output_format` JSON schema and `max_budget_usd`. It suits a more autonomous research agent.
- **Managed Agents.** Anthropic hosts both the loop and the sandbox.

For a trading loop, use structured outputs (`output_config.format` / `client.messages.parse()`, or `strict: true` tools) for every decision object. Cache the static prefix, and use the Batch API (−50%) for non-urgent overnight analysis.

### Cited Findings
**Claude Agent SDK (Python)**
- Install with `pip install claude-agent-sdk`. `query()` creates a new session per call and returns an `AsyncIterator[Message]`. `ClaudeSDKClient` keeps a session across exchanges and supports interrupts. — [Agent SDK Python reference](https://code.claude.com/docs/en/agent-sdk/python)
- `ClaudeAgentOptions` fields include `allowed_tools`, `disallowed_tools` (scoped rules like `"Bash(rm *)"` are supported), `permission_mode`, `can_use_tool` (custom callback), `mcp_servers`, `agents` (dict of `AgentDefinition`), `model`, `system_prompt`, `output_format` (`{"type": "json_schema", "schema": {...}}`), `max_turns`, `max_budget_usd` ("Stop when cost reaches this USD value"), `hooks`, `skills` and `thinking`. — [Agent SDK Python reference](https://code.claude.com/docs/en/agent-sdk/python)
- Custom tools are declared with `@tool("name", "description", {"param": type})` async functions, optionally with `ToolAnnotations(readOnlyHint=True, ...)`. They are bundled in-process with `create_sdk_mcp_server(name=..., version=..., tools=[...])` and whitelisted as `mcp__<server>__<tool>`. — [Agent SDK Python reference](https://code.claude.com/docs/en/agent-sdk/python)
- Subagents: `AgentDefinition(description, prompt, tools, disallowedTools, model, skills, memory, mcpServers, maxTurns, background, effort, permissionMode, ...)`. The `model` and `effort` can be set per subagent, which is how you would run Haiku analysts under an Opus orchestrator. — [Agent SDK Python reference](https://code.claude.com/docs/en/agent-sdk/python)
- Hooks: `PreToolUse` and `PostToolUse` (plus others) configured with `HookMatcher`. The `can_use_tool` callback returns `PermissionResultAllow(updated_input=...)` or `PermissionResultDeny(message=..., interrupt=True)`. This is the natural place to hard-block `place_order` calls that breach risk limits, or to force paper mode. — [Agent SDK Python reference](https://code.claude.com/docs/en/agent-sdk/python)
- The Agent SDK ships the Claude Code built-in tools (Read/Write/Edit/Bash/Glob/Grep/WebSearch/WebFetch), MCP and subagents. It is "harness only": you host it. The Messages API Tool Runner (`client.beta.messages.tool_runner` with `@beta_tool`) is a separate, lighter option that runs only your own tools. — Anthropic claude-api skill reference (bundled docs, mirrors [platform.claude.com docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview))

**Messages API features relevant to trading**
- Structured outputs: `output_config: {format: {...}}` (the old `output_format` on messages.create is deprecated), or `client.messages.parse()` with schema validation. `strict: true` on a tool definition guarantees `tool_use.input` validates against a schema with `additionalProperties: false`. — bundled Anthropic API docs ([tool use overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview))
- Forced `tool_choice` (`any`/`tool`) returns 400 on Claude Opus 5.5 and Fable 5.1. Use `auto` + `strict: true`, or structured outputs, instead. — bundled Anthropic migration docs ([migration guide](https://platform.claude.com/docs/en/about-claude/models/migration-guide))
- Thinking/effort: current models use `thinking: {type: "adaptive"}` plus `output_config.effort` (`low`…`max`). Opus 5.5 cannot disable thinking, and its default effort is `medium`. `budget_tokens` returns 400 on Opus 5/5.5, Sonnet 5 and Fable. — bundled Anthropic docs ([migration guide](https://platform.claude.com/docs/en/about-claude/models/migration-guide))
- MCP connector on the Messages API: `mcp_servers=[{type:"url", url, name}]` plus `tools=[{type:"mcp_toolset", mcp_server_name}]` with beta `mcp-client-2025-11-20`. This works only with remote (URL) MCP servers. — bundled Anthropic docs
- Prompt caching: a prefix match in the order tools → system → messages, with at most 4 breakpoints. A 5-min write costs 1.25× input and a 1-hour write costs 2×. Reads cost 0.1× on most models, 0.05× on Opus 5.5 and 0.025× on Fable 5.1. A read refreshes the TTL. Caching "pays off after one cache read for the 5-minute duration… or after two cache reads for the 1-hour duration". The multipliers stack with the Batch discount. — [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing) (fetched 2026-09-26)
- The minimum cacheable prefix is 512 tokens on the newest models, but 4096 on Haiku 4.5 and Opus 4.6. Shorter prefixes silently don't cache. — bundled Anthropic prompt-caching docs ([prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching))
- Batch API: "50% discount on both input and output tokens", asynchronous. Results come back in any order and must be keyed by `custom_id`. Fast mode is not available with Batch. — [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- Managed Agents: tokens are billed at model rates plus $0.08 per session-hour of `running` time. No batch discount applies. — [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- Server tools: web search costs $10 per 1,000 searches plus tokens. Web fetch has no extra charge. — [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)

### Inferences
- For a scheduled rebalance, a plain Messages-API pipeline (Python orchestrating fixed calls, with `messages.parse()` into Pydantic models) is simpler, cheaper and more auditable than the Agent SDK. The Agent SDK's built-in Claude Code tools and system prompt add token overhead and autonomy you may not want near a broker.
- If you use the Agent SDK, set `disallowed_tools` for Bash/Write. Expose broker actions only through your own `@tool` functions that call the deterministic risk engine. Add a `can_use_tool` or `PreToolUse` deny for any order tool when `LIVE=false`. Set `max_budget_usd` per cycle.
- Stdio MCP servers (Alpaca, EDGAR) work with the Agent SDK's `mcp_servers`. The Messages API MCP connector requires a remote HTTPS MCP URL (e.g. IBKR's hosted endpoint or CoinGecko's remote server).

### Gaps
- The exact token overhead of the Agent SDK's default system prompt and tool definitions was not measured. Use `count_tokens` or the usage logs to check it.
- The full Agent SDK hook-event list beyond PreToolUse/PostToolUse was not enumerated on the fetched page.

## (c) Existing MCP servers for brokers and market data: maturity and features

### Takeaway
Alpaca has the most mature **official** trading MCP: v2, 80+ tools, paper trading by default. Interactive Brokers now offers an **official hosted** MCP endpoint plus several community servers. The official ones found here are Massive (formerly Polygon), FMP, Alpha Vantage and CoinGecko. EDGAR and Yahoo Finance servers are community projects.

### Cited Findings
- **Alpaca (official)**:
  - v2 is "a complete rewrite built with FastMCP and OpenAPI". v1 is deprecated, and tool names changed between them.
  - 80+ tools: account, orders (stocks, crypto, options), positions and options exercise, watchlists, calendar/clock/corporate actions, stock/crypto/options market data (chains, Greeks, IV), news, and docs search.
  - The `ALPACA_PAPER_TRADE` env var defaults to `true`.
  - Runs over stdio, with optional streamable HTTP on localhost:8000. There is "no built-in remote authentication", so it should not be exposed to the internet.
  - Install with `uvx alpaca-mcp-server`. Claude Code setup: `claude mcp add alpaca --scope user --transport stdio uvx alpaca-mcp-server`.
  - About 994 stars. Docker and Helm are supported.
  — [alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server)
- **Interactive Brokers (official, hosted)**: "Interactive Brokers acts as an MCP server… tools and account actions — like checking order status or retrieving portfolio data… only after your explicit authorization". The endpoint is `https://api.ibkr.com/v1/api/mcp-public`. IBKR keeps control of authentication (OAuth-style; credentials are not passed to the AI), and the server is listed in Claude's connector directory. — [IBKR AI integrations](https://www.interactivebrokers.com/en/trading/ai-integrations.php) (via search snippet; direct fetch blocked). Whether it allows order placement or is read-only was not verified.
- **IBKR community servers**: one is read-only over Gateway/TWS (account, positions, executions, contracts, historical data; released 2026-04-04). Another offers "account, market research, risk checks, and preview-only order drafts" (2026-05-09). Also available: [code-rabi/interactive-brokers-mcp](https://github.com/code-rabi/interactive-brokers-mcp). — [PulseMCP listings](https://www.pulsemcp.com/servers/osauer-interactive-brokers), [PulseMCP](https://www.pulsemcp.com/servers/christospappas-ibkr)
- **Massive (formerly Polygon.io)**: the official MCP exposes "three composable tools — search, call, and query — that cover the entire Massive.com API surface", with results loadable into an in-memory SQLite database and built-in financial functions. The earlier `polygon-io/mcp_polygon` server provides real-time and historical data. — [mcpservers.org Polygon](https://mcpservers.org/servers/polygon-io/mcp_polygon); [Glama mcp_polygon](https://glama.ai/mcp/servers/@polygon-io/mcp_polygon/tree/519b6666c02863481fcbf10ba9274cac6bc7125b) (snippet)
- **Financial Modeling Prep (official)**: supports MCP, giving AI agents access to "70,000+ stock data points". — [FMP MCP docs](https://site.financialmodelingprep.com/developer/docs/mcp-server) (snippet; direct fetch blocked, so tool count and plan limits were not verified)
- **Alpha Vantage (official MCP endpoint)**: covers stocks, ETFs, options, FX, crypto, commodities, fundamentals, technical indicators and economic indicators. — [marketxls comparison](https://marketxls.com/blog/best-financial-data-mcp-servers-ai-market-data); [PulseMCP](https://www.pulsemcp.com/servers/alpha-vantage-stock-market) (secondary sources)
- **CoinGecko (official, remote)**: covers 15,000+ coins across 1,000+ exchanges, plus on-chain DEX data for 8M+ tokens across 200 networks, NFTs and history. Remote server at `mcp.api.coingecko.com`. — [ethereum.org CoinGecko MCP](https://ethereum.org/developers/tools/coingecko-mcp/); [CoinGecko MCP](https://mcp.api.coingecko.com/)
- **SEC EDGAR (community)**: `stefanoamorelli/sec-edgar-mcp` v1.0.6 (Sept 2025) offers company lookup, 10-K/10-Q/8-K retrieval, XBRL financial statements and insider trading data, with SEC URLs in every response. It is on PyPI and Docker Hub (`mcp/sec-edgar`), and is not affiliated with the SEC. — [GitHub](https://github.com/stefanoamorelli/sec-edgar-mcp); [PyPI](https://pypi.org/project/sec-edgar-mcp/); [Docker Hub](https://hub.docker.com/r/mcp/sec-edgar)
- **Yahoo Finance (community)**: several yfinance-based MCPs exist, e.g. "YFinance-Trader-MCP-ClaudeDesktop". These are unofficial and depend on scraping-style yfinance access. — [TensorBlock awesome-mcp-servers finance list](https://github.com/TensorBlock/awesome-mcp-servers/blob/main/docs/finance--crypto.md)

### Inferences
- For live execution, prefer calling the broker's Python SDK (alpaca-py, ib_async) from deterministic code over letting the LLM call an order-placing MCP tool. Use MCP servers read-only for research, or run Alpaca MCP in paper mode for prototyping.
- yfinance-based and community EDGAR servers are fine for research but carry rate-limit and ToS risk in production. Paid vendors (Massive, FMP, Alpha Vantage premium) are more reliable.

### Gaps
- The IBKR official MCP's tool list, order capability and launch date could not be verified (site blocked).
- Tool counts and plan requirements for FMP, Massive and Alpha Vantage MCP were not verified from primary pages.
- News-specific MCP servers (Benzinga, Finnhub, etc.) were not researched. Alpaca MCP includes a news tool.

## (d) Claude model lineup, pricing (2026-09-26) and cost per decision cycle / month; which model for which role

### Takeaway
As of 2026-09-26, per MTok input/output:
- Opus 5.5: $4/$20 (cache read $0.20).
- Opus 5: $5/$25.
- Sonnet 5: $2/$10. The introductory price has been made permanent.
- Haiku 4.5: $1/$5.
- Fable 5.1 (top tier): $10/$50.

Batch is −50%. A lean design (Haiku/Sonnet summarizers plus one Opus 5.5 portfolio decision) costs roughly $10–30 per month for a daily rebalance of 20–50 tickers. Running a full TradingAgents-style per-ticker pipeline instead costs roughly $150–600 per month at the same cadence, and an hourly loop multiplies either by about 7 (equities) or about 24 (crypto 24/7).

### Cited Findings (pricing, fetched 2026-09-26 from [Anthropic pricing page](https://platform.claude.com/docs/en/about-claude/pricing))
| Model | Input | 5m cache write | 1h cache write | Cache read | Output | Batch in/out |
|---|---|---|---|---|---|---|
| Claude Fable 5.1 | $10 | $12.50 | $20 | $0.25 | $50 | $5 / $25 |
| Claude Opus 5.5 | $4 | $5 | $8 | $0.20 | $20 | $2 / $10 |
| Claude Opus 5 | $5 | $6.25 | $10 | $0.50 | $25 | $2.50 / $12.50 |
| Claude Opus 4.8 / 4.7 / 4.6 | $5 | $6.25 | $10 | $0.50 | $25 | $2.50 / $12.50 |
| Claude Sonnet 5 | $2 | $2.50 | $4 | $0.20 | $10 | $1 / $5 |
| Claude Sonnet 4.6 | $3 | $3.75 | $6 | $0.30 | $15 | $1.50 / $7.50 |
| Claude Haiku 4.5 | $1 | $1.25 | $2 | $0.10 | $5 | $0.50 / $2.50 |

- Sonnet 5's $2/$10 "announced at launch as introductory pricing through August 31, 2026, is now the standard price. The previously scheduled increase to $3/$15… will not occur." — [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- The "Claude 4.7 and later models… use a newer tokenizer… approximately 30% more tokens for the same text." — [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- The 1M-token context is billed at standard rates on Claude 4.6+ with no long-context premium. US-only inference (`inference_geo: "us"`) costs 1.1×. — [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- Fast mode costs Opus 5.5 $8/$40 and Opus 5 $10/$50. It is first-party API only and not available with Batch. — [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- Context windows: 1M for Opus/Sonnet/Fable current models and 200K for Haiku 4.5. Opus 5.5 is newly launched: thinking cannot be disabled and its default effort is `medium`. — bundled Anthropic model docs ([models overview](https://platform.claude.com/docs/en/about-claude/models/overview))
- The tool-use system prompt adds about 286 tokens on Opus 5/5.5, 354 on Sonnet 5 and 496 on Haiku 4.5 per request. — [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- Anthropic's own guidance: "Choose Haiku for simple tasks, Sonnet for most production workloads, and Opus for the most complex reasoning." — [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)
- TradingAgents' own design separates `quick_think_llm` from `deep_think_llm`. — [TradingAgents GitHub](https://github.com/TauricResearch/TradingAgents)

### Inferences: cost model (my estimates, using the prices above; token counts are assumptions and include the new tokenizer and thinking tokens in output)

**Design A: lean portfolio-level loop (recommended)**
- Per ticker, a Haiku 4.5 analyst summary of about 6k input tokens (prices, indicators, news headlines, fundamentals) and about 0.6k output (JSON) costs 6k×$1 + 0.6k×$5 = **$0.009**.
- One Opus 5.5 portfolio decision reads all summaries plus portfolio state and a cached system prompt (about 40k input, about 8k output including thinking): 40k×$4 + 8k×$20 = **$0.32**. With about 5k of static prefix cached the saving is small (about $0.02).
- Per cycle:

| Tickers | Cost per cycle |
|---|---|
| 20 | ≈ $0.18 + $0.30 ≈ **$0.48** |
| 30 | ≈ $0.27 + $0.32 ≈ **$0.59** |
| 50 | ≈ $0.45 + $0.36 ≈ **$0.81** |

- Swapping the analysts to Sonnet 5 (6k×$2 + 0.6k×$10 = $0.018 per ticker) roughly doubles the analyst portion.
- Monthly cost:

| Cadence | 20–50 tickers |
|---|---|
| Daily rebalance (21 trading days) | ≈ **$10–17/month** |
| Daily, analyst step via Batch overnight | ≈ **$8–13/month** |
| Hourly, equities RTH (~7 cycles/day × 21 ≈ 147 cycles) | ≈ **$70–120/month** |
| Hourly, crypto 24/7 (~720 cycles) | ≈ **$350–580/month** |

**Design B: full TradingAgents-style per-ticker pipeline on Claude**
- Per ticker per cycle:
  - 4 analysts on Sonnet 5 (8k in / 1k out each): ≈ $0.10.
  - Bull/bear debate, 2 rounds = 4 Sonnet 5 calls (10k / 1.5k): ≈ $0.14.
  - Trader on Opus 5.5 (15k / 2k): ≈ $0.10.
  - 3 risk debaters on Sonnet 5 (12k / 1k): ≈ $0.10.
  - Portfolio manager on Opus 5.5 (15k / 2k): ≈ $0.10.
  - Total **≈ $0.55 per ticker per cycle**.
- Monthly cost:

| Cadence | Tickers | Per cycle | Per month |
|---|---|---|---|
| Daily | 20 | $11 | ≈ **$230/month** |
| Daily | 30 | $16.5 | ≈ **$345/month** |
| Daily | 50 | $27.5 | ≈ **$580/month** |
| Daily via Batch (the whole pipeline is not latency-sensitive if run pre-open) | 20–50 | – | ≈ **$115–290/month** |
| Hourly, equities RTH | 30 | – | ≈ **$2,400/month** |
| Hourly, crypto 24/7 | 30 | – | ≈ **$11,900/month** |

**Caching notes for loops**
- With a 5-min TTL, an hourly loop gets no reuse between cycles. It only gets reuse within a cycle (for example, the 30 analyst calls that share a system prompt and tool definitions, which run inside 5 minutes).
- A 1-hour TTL (2× write) is borderline for an exactly-hourly cadence, because the TTL is measured start-to-start.
- Keep the static system prompt and tool list byte-identical and ahead of the volatile market data.
- Opus 5.5's cheap cache read ($0.20) makes a large static "strategy/policy" prefix nearly free once warm.

**Model per role**
- Data fetching, indicator math and risk checks: no LLM (Python).
- News/filing summarization and per-ticker analyst JSON: Haiku 4.5 (cheapest; 200K context; caching minimum 4096 tokens), or Sonnet 5 at low/medium effort when judgement matters.
- Debate/critique: Sonnet 5.
- Final portfolio decision: Opus 5.5 at effort `medium`/`high` (cheaper than Opus 5 with the same capability tier). Keep Fable 5.1 ($10/$50) for occasional deep research such as a weekly strategy review, not for the loop.
- Anthropic's cost guidance suggests measuring first whether a single strong model at lower effort matches a cascade. Caches are model-scoped, so a multi-model cascade gives up cross-model cache reuse.

**Other cost items**
- Web search is $10 per 1,000 if used. At 30 searches per day that adds about $6/month.
- Managed Agents adds $0.08 per running session-hour.
- Market-data vendor subscriptions (Massive, FMP, etc.) will likely exceed the LLM cost in Design A.

### Gaps
- The token counts per call are assumptions, not measurements. Real numbers depend on how much raw data (full 10-K text versus pre-computed metrics) is placed in context. Measure with `messages.count_tokens` and `response.usage` on a paper-trading week before committing.
- No public benchmark was found comparing Claude model tiers specifically on trading-decision quality, so the model-per-role mapping rests on general capability and cost reasoning.
- Opus 5.5 is newly launched (per Anthropic's docs its fast-mode details were still being finalized). Rate limits by usage tier were not researched.
