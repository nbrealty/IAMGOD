# Empirical Evidence on LLM Autonomous Trading: Competitions, Benchmarks, Failure Modes, Lessons (as of Sept 2026)

Method note: arxiv.org, nof1.ai, huggingface.co, and most blogs were blocked by the network egress proxy during this research. Most numbers below therefore come from search-result excerpts of the primary papers or press coverage, not from full-text reads. Where secondary sources disagree, both figures are given. **Test type**: LIVE = real money or real-time forward test; BACKTEST = historical simulation.

## 1. Live LLM trading competitions (nof1 Alpha Arena)

### Takeaway
In Alpha Arena, the best-known live contest, most frontier LLMs lost money. Claude Sonnet 4.5 lost about 40% in Season 1 (crypto perps) and about 35% in Season 1.5 (US stocks). The winners were different in each season (Qwen 3 Max in crypto, a then-unreleased Grok 4.20 in equities). That points to high variance and regime-dependence rather than a stable "best trader" model. Each run is essentially one sample over about two weeks, so it is not statistically meaningful.

### Cited Findings
**Season 1 (LIVE, real money, Oct 18 – Nov 3, 2025; crypto perpetuals on Hyperliquid; $10,000 per model; same prompts and inputs)**
- Setup: six models each staked a real $10,000 on Hyperliquid. The results were shared by nof1 founder Jay A. Zhang — [ForkLog](https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/); [GNcrypto](https://www.gncrypto.news/news/qwen-wins-alpha-arena-season-1-with-22-percent-returns/)
- Final standings:
  1. Qwen 3 Max: +22.31% (~$12,231), taking the lead from DeepSeek in the final moments — [GNcrypto](https://www.gncrypto.news/news/qwen-wins-alpha-arena-season-1-with-22-percent-returns/); [Odaily](https://www.odaily.news/en/newsflash/455170)
  2. DeepSeek V3.1 Chat: +4.89% (~$10,489)
  3. Claude Sonnet 4.5: ~$5,799, roughly −42%
  4. Gemini 2.5 Pro: ~$5,445
  5. Grok 4: ~$4,208 (−58%)
  6. GPT-5: ~$3,733 per ForkLog, ~$4,126 per other coverage (the sources conflict)
  — [ForkLog](https://forklog.com/en/four-out-of-six-ai-models-suffer-losses-in-trading-tournament/); [iWeaver](https://www.iweaver.ai/blog/alpha-arena-ai-trading-season-1-results/)
- Mid-contest peaks were much higher than the finishes:
  - One snapshot showed DeepSeek at $14,764 (+48% PnL, $568 fees, 12.9x leverage, Sharpe 0.42) and Qwen3 Max at $13,121 (+31%, $1,565 fees, 16.7x leverage, Sharpe 0.31). The source is secondary coverage of the live leaderboard — [iWeaver](https://www.iweaver.ai/blog/alpha-arena-ai-trader-showdown/)
  - Another headline cited Qwen at +79% at one point — [howaiworks.ai](https://howaiworks.ai/blog/nof1-ai-arena-leaderboard-qwen3-max-leads)
  - Large intra-contest swings meant the final ranking depended heavily on the end date.
- Fees: Gemini 2.5 Pro paid $1,284 and GPT-5 paid $498. Qwen made only ~43 trades (<3/day). Coverage attributes the losses to overtrading, which raised fees and exposure to noise — [search summary citing iWeaver/Datawallet](https://www.datawallet.com/crypto/alpha-arena-nof1-ai-explained)
- Behaviors reported by nof1's technical post:
  - Trade frequency and holding periods differ widely across models and runs.
  - Gemini 2.5 Pro was the most active and Grok 4 typically the least active, with the longest holds in pre-launch runs.
  - Claude Sonnet 4.5 "rarely ever shorts" (a strong long bias).
  — [nof1 TechPost1 (via search excerpt)](https://nof1.ai/blog/TechPost1)
- Claude characterization (practitioner blog, secondary):
  - It trades "like a risk-averse fund manager."
  - It had the best max drawdown of the Western models (−30.81% vs −45% to −63%).
  - The blog argues the winners won through discipline (fewer trades, smaller size, faster loss-cutting), not prediction.
  — [PickMyTrade blog](https://blog.pickmytrade.io/claude-vs-chatgpt-vs-gemini-vs-grok-trading-2026/)
  - Caveat: this drawdown figure is reported inconsistently next to a ~42% final loss, so treat it with caution.
- Claude Sonnet, Gemini 2.5 and GPT-5 suffered major drawdowns attributed to over-leveraging and inadequate risk controls — [iWeaver](https://www.iweaver.ai/blog/alpha-arena-ai-trading-season-1-results/)

**Season 1.5 (LIVE, US equities, ended Dec 3, 2025, 5 PM EST; about 2 weeks)**
- Four simultaneous modes:
  - Baseline
  - Monk Mode (limits on trading frequency and position size)
  - Situational Awareness (the model sees other participants' holdings)
  - Max Leverage
  — [KuCoin news](https://www.kucoin.com/news/flash/alpha-arena-1-5-season-results-grok-4-20-leads-with-22-38-return); [GNcrypto](https://www.gncrypto.news/news/alpha-arena-season-1-5-ai-stock-trading-competition/)
- Reported returns (appear to be aggregate across modes): Grok 4.20 +22.38%, GPT-5.1 −2.29%, Gemini 3 Pro −25.74%, DeepSeek 3.1 −29.16%, Kimi K2 −29.93%, Qwen 3 Max −31.9%, **Claude Sonnet 4.5 −35.08%**, Grok 4 −53.3% — [KuCoin](https://www.kucoin.com/news/flash/alpha-arena-1-5-season-results-grok-4-20-leads-with-22-38-return)
- Conflicting winner figure: GNcrypto says the "Mystery Model" (later revealed as Grok 4.20) returned 12.11% over two weeks, or $4,844 across four contests, and another account cites ~$11,060 equity from $10,000. The 22.38% figure is probably one mode's result or a different aggregation — [GNcrypto](https://www.gncrypto.news/news/mystery-model-alpha-arena-season-1-5-winner/); [Yahoo Finance/Benzinga](https://finance.yahoo.com/news/elon-musks-grok-4-20-123855766.html)
- The Season 1 crypto champion Qwen "crashed" on US equities — [traderank.ai](https://www.traderank.ai/blog/alpha-arena-alternatives-2026)

**Season 2 / 2026**
- As of Aug 6, 2026, nof1.ai still showed Season 1.5 as the latest season, with a banner saying the competition had ended and the models were no longer running. No Season 2 results were published — [search summary of traderank.ai / nof1.ai](https://www.traderank.ai/blog/alpha-arena-alternatives-2026)

### Inferences
- Claude placed 3rd of 6 in Season 1 but 7th of 8 in Season 1.5, losing about 35–42% in both. The long-only bias probably hurt in falling crypto markets. It did not protect Claude in equities.
- Ranking reversals across seasons (Qwen from 1st to near-last; Grok 4 from 5th of 6 to last) suggest luck and regime effects dominate. The contests are too short to support claims of model skill.
- Leverage of 10–20x on crypto perps turned ordinary directional errors into ruin-level drawdowns. Much of the loss is a risk-framework failure, not a forecasting failure.

### Gaps
- Could not access nof1's primary blog or leaderboard (egress blocked). Per-model trade counts, holding times and fees for Season 1.5 are not verified.
- Per-mode (Monk / Situational / Max Leverage) results for Claude were not found.
- The −30.81% "Claude drawdown" figure could not be reconciled with the final equity.

## 2. Benchmarks and academic studies

### Takeaway
Rigorous, contamination-controlled benchmarks show that most LLM agents fail to beat buy-and-hold by a meaningful margin. The best reported edges in StockBench are about 1–2 percentage points over a flat market in a 4-month window, with somewhat lower drawdowns. Papers with strong results (TradingAgents, FinMem, FinAgent) typically use short windows and a few mega-cap stocks. Those advantages largely disappear under long-horizon, broad-universe testing (FINSABER).

### Cited Findings
**StockBench (Oct 2025; BACKTEST designed to be contamination-free, i.e. after the models' training cutoffs)**
- Setup: 20 DJIA stocks, 82 trading days (Mar 3 – Jun 30, 2025), $100k starting capital. Daily inputs were prices, fundamentals and news, and the agent chose buy/sell/hold. Metrics were cumulative return, max drawdown and Sortino — [arXiv 2510.02209](https://arxiv.org/abs/2510.02209); [maxpool summary](https://maxpool.dev/research-papers/stockbench_llm_trading_report.html)
- Models tested: GPT-5, Claude-4, o3, Qwen3, Kimi-K2, GLM-4.5 and DeepSeek. "Most LLM agents struggle to outperform the simple buy-and-hold baseline" — [arXiv abstract](https://arxiv.org/abs/2510.02209)
- Results:
  - Equal-weight buy-and-hold: +0.4%, max drawdown −15.2%.
  - Best: Qwen3-235B-Instruct +2.4% (max drawdown −11.2%) and Kimi-K2 +1.9% (max drawdown −11.8%).
  - Reasoning ("Think") variants did not beat the instruct variants: Qwen3-235B-Think had a max drawdown of −14.9%.
  — [Neurohive](https://neurohive.io/en/news/kimi-k2-and-qwen3-235b-ins-best-ai-models-for-stock-trading-chinese-researchers-found/); [Emergent Mind topic](https://www.emergentmind.com/topics/stockbench)
- Strong static financial QA does not translate into trading skill — [arXiv abstract](https://arxiv.org/abs/2510.02209)
- Claude-4's exact numbers were not retrievable.

**FINSABER (arXiv 2505.07078, May 2025; KDD 2026 oral; covered by the WSJ in June 2026; BACKTEST)**
- Setup: 20 years (rolling windows, 2004–2024), 100+ symbols, historical S&P 500 constituents including delisted names. It explicitly controls survivorship, look-ahead and data-snooping biases, and models slippage and LLM costs — [arXiv](https://arxiv.org/abs/2505.07078); [GitHub](https://github.com/waylonli/FINSABER)
- Previously reported LLM advantages "deteriorate significantly" under a broader universe and longer horizon — [arXiv](https://arxiv.org/abs/2505.07078)
- Regime behavior: LLM strategies are too conservative in bull markets, where they underperform passive investing. They are too aggressive in bear markets, where they take heavy losses — [arXiv](https://arxiv.org/abs/2505.07078)
- Numbers (from a secondary summary):
  - In the composite setup, buy-and-hold had the highest Sharpe (0.703).
  - In bear markets, Sharpe was −0.38 for FinAgent and −0.97 for FinMem, vs −0.28 for buy-and-hold.
  - Neither FinMem nor FinAgent produced statistically significant alpha (p > 0.34).
  — [search summary of alphaXiv/Lacuna](https://lacuna.tiptreesystems.com/work/can-llm-based-financial-investing-strategies-outperform-the-market-in-long-run/wrk_7fd368a3bf0f28ca6008b4c9bdf5a866)

**TradingAgents (Tauric Research / UCLA-MIT; arXiv 2412.20138, Dec 2024; BACKTEST)**
- Design: a multi-agent "trading firm" with fundamental, sentiment, news and technical analysts, bull and bear researchers who debate, a trader, and a risk-management team — [arXiv](https://arxiv.org/abs/2412.20138); [GitHub](https://github.com/tauricresearch/tradingagents)
- Test: June–Nov 2024, daily decisions on AAPL, GOOGL and AMZN. It was compared with buy-and-hold, MACD, KDJ&RSI, ZMR and SMA. It claims superior Sharpe and cumulative returns (reported roughly 23–27% cumulative, up to 30.5% annualized) — [arXiv v5](https://arxiv.org/html/2412.20138v5); [beginnersinai summary](https://beginnersinai.org/tradingagents-explained/)
- Critique:
  - Only 3 heavily covered mega-caps over ~5 months.
  - Performance on small caps and information-poor names is unknown.
  — [beginnersinai](https://beginnersinai.org/tradingagents-explained/)
  - The GPT-4o-era backbones also overlap with the test period, which raises contamination risk (see Section 4).

**Agent Market Arena / "When Agents Trade" (arXiv 2510.11695; ACM WebConf 2026; LIVE forward test)**
- Design: a lifelong, real-time benchmark on BTC, ETH, TSLA and BMRN. It tested four agent architectures (InvestorAgent, TradeAgent, HedgeFundAgent, DeepFundAgent) across GPT-4o, GPT-4.1, Claude-3.5-haiku, Claude-sonnet-4 and Gemini-2.0-flash — [arXiv](https://arxiv.org/abs/2510.11695); [ACM](https://dl.acm.org/doi/10.1145/3774904.3792821)
- Findings:
  - **Agent architecture mattered more than the LLM backbone.** Swapping backbones shifted outcomes less than swapping agents.
  - No single LLM or agent won across all assets.
  - Examples: InvestorAgent + GPT-4.1 made 40.83% cumulative return on TSLA. DeepFundAgent made 8.61% on TSLA and 9.45% on BMRN.
  - The authors say agents "often" beat buy-and-hold.
  — [search summary of paper](https://www.alphaxiv.org/overview/2510.11695v2)

**LiveTradeBench (arXiv 2511.03628, Nov 2025; LIVE)**
- Design: 50-day live evaluation of 21 LLMs on US stocks and Polymarket prediction markets. The agent outputs portfolio allocations from prices, news and its current portfolio — [arXiv](https://arxiv.org/abs/2511.03628); [GitHub](https://github.com/ulab-uiuc/live-trade-bench)
- Findings:
  - High LMArena or general-reasoning scores do not predict trading results.
  - Models show distinct portfolio "styles" (risk appetite).
  - Some models use live signals effectively.
  — [arXiv/HF summary](https://arxiv.org/abs/2511.03628)

**INVESTORBENCH (arXiv 2412.18174, Dec 2024; BACKTEST)**
- A benchmark for LLM agents on stocks, crypto and ETFs — [arXiv](https://arxiv.org/pdf/2412.18174). No specific numbers were retrieved.

**Newer 2026 work (from titles and excerpts only)**
- TradeTrap (Dec 2025): a robustness stress-test. Covered separately in Section 4 — [arXiv 2512.02261](https://arxiv.org/abs/2512.02261)
- AlphaForgeBench (arXiv 2602.18481, Feb 2026): end-to-end strategy design with claude-sonnet-4.5, gpt-5.2, gemini-3-pro, deepseek-v3.2 and grok-4.1-fast — [arXiv](https://arxiv.org/pdf/2602.18481)
- Backtrader-Bench (arXiv 2608.11232, Aug 2026): includes Opus 4.7, GPT-5.5 and Gemini 3.1 Pro on algorithmic-trading tasks. It evaluates coding and knowledge, not P&L — [arXiv](https://arxiv.org/pdf/2608.11232)
- "From Knowing to Doing" (arXiv 2605.28359, May 2026): a memory-controlled benchmark for LLM stock-trading agents — [arXiv](https://arxiv.org/html/2605.28359v1)
- Agentic quant trading survey (arXiv 2608.31041, Aug 2026) — [arXiv](https://arxiv.org/pdf/2608.31041)

### Inferences
- There is a split between optimistic framework papers (short windows, few tickers, custom baselines) and skeptical evaluation papers (StockBench, FINSABER, LiveTradeBench). The evaluation papers consistently find little or no robust alpha.
- Where LLMs do show an edge, it tends to be **lower drawdown** (a risk-reduction or cash-holding behavior) rather than higher returns. That matches FINSABER's finding that LLMs are too conservative in bull markets.

### Gaps
- Exact Claude-4 / Claude Sonnet numbers in StockBench, AlphaForgeBench and LiveTradeBench could not be retrieved (arxiv blocked).
- FinMem, FinAgent and FinRobot original reported numbers were not retrieved.
- I found no rigorous peer-reviewed evaluation of the newest models (Claude Opus 4.x/5.x, GPT-5.5) on live P&L.

## 3. LLM agents vs buy-and-hold and simple quant baselines after costs

### Takeaway
After costs and with bias controls, buy-and-hold is usually at least as good as the LLM agents on a risk-adjusted basis. Costs (fees, funding and LLM inference) and turnover are a primary reason edges vanish.

### Cited Findings
- FINSABER: buy-and-hold had the top composite Sharpe (0.703). LLM agents had no significant alpha (p > 0.34) and underperformed in both bull and bear regimes — [Lacuna summary](https://lacuna.tiptreesystems.com/work/can-llm-based-financial-investing-strategies-outperform-the-market-in-long-run/wrk_7fd368a3bf0f28ca6008b4c9bdf5a866); [arXiv](https://arxiv.org/abs/2505.07078)
- StockBench: most agents failed to beat equal-weight buy-and-hold. The best beat it by ~1.5–2 pp in a flat market (+0.4% baseline) — [Neurohive](https://neurohive.io/en/news/kimi-k2-and-qwen3-235b-ins-best-ai-models-for-stock-trading-chinese-researchers-found/)
- Alpha Arena Season 1: fees were $498–$1,284 per $10k account over ~2 weeks, or about 5–13% of capital. The most active model (Gemini 2.5 Pro) paid the most — [Datawallet/iWeaver summary](https://www.datawallet.com/crypto/alpha-arena-nof1-ai-explained)
- Practitioner negative result (GitHub postmortem; BACKTEST plus 22 days of paper trading; NSE RELIANCE daily):
  - The ML/LLM-assisted pipeline's best directional accuracy was 53.7%.
  - Its gross edge of ~5.5 bps/day fell below the 6–10 bps breakeven.
  - At 20 bps round-trip costs: net −10.1%/yr, Sharpe −0.64, max drawdown −55.6%, vs buy-and-hold +18.1%/yr.
  - Zero of 49 features survived Benjamini-Hochberg multiple-testing correction.
  — [GitHub postmortem](https://github.com/AbhayPhalswal/llm-stock-predictor-postmortem)
  - Note: this system is mainly classical ML with an LLM angle.

### Inferences
- A deployable claim needs to beat buy-and-hold net of trading fees, slippage, funding and LLM API costs, over multiple regimes and a broad universe. No study found meets that bar convincingly.

### Gaps
- Few papers report LLM inference cost per trade relative to P&L. FINSABER tracks it, but the numbers were not retrieved.

## 4. Documented failure modes

### Takeaway
The main documented failure modes are:
- look-ahead bias and memorization in backtests
- poor risk management and leverage
- overtrading and fees
- regime-inappropriate behavior (too timid in bulls, too aggressive in bears)
- inconsistency across runs, agents and prompts
- fragility to corrupted state or data (hallucinated or poisoned inputs)

### Cited Findings
- **Look-ahead bias and memorization**
  - LLMs "recall the future": a model trained through 2024 already knows what happened after a 2022 prompt date — [HedgeFundAlpha](https://hedgefundalpha.com/education/your-llms-alpha-might-be-mere-memorization/); [paperswithbacktest](https://paperswithbacktest.com/course/look-ahead-bias-llm-trading)
  - Look-Ahead-Bench (Benhenda, 2026) compares an in-sample window (Apr–Sep 2021) with an out-of-sample window (Jul–Dec 2024). Both had similar buy-and-hold returns (~25%) to isolate the bias — [search summary](https://hedgefundalpha.com/education/your-llms-alpha-might-be-mere-memorization/)
  - Glasserman & Lin found two forms of bias in GPT sentiment backtests: look-ahead, and a "distraction effect" from general company knowledge — [arXiv 2309.17322](https://arxiv.org/abs/2309.17322)
  - The bias is stronger for low-frequency data, indexes and larger models, and pre-cutoff values are recalled verbatim — [Gao, Jiang, Yan, arXiv 2512.23847](https://arxiv.org/abs/2512.23847); [MemGuard-Alpha, arXiv 2603.26797](https://arxiv.org/pdf/2603.26797)
- **Survivorship and data-snooping** from hand-picked tickers and short windows inflate results — [FINSABER](https://arxiv.org/abs/2505.07078)
- **Poor risk management and leverage**
  - Claude Sonnet 4.5, Gemini 2.5 and GPT-5 had major drawdowns in Alpha Arena from over-leveraging and weak risk controls — [iWeaver](https://www.iweaver.ai/blog/alpha-arena-ai-trading-season-1-results/)
  - Even the winners used 12–17x leverage — [iWeaver](https://www.iweaver.ai/blog/alpha-arena-ai-trader-showdown/)
- **Overtrading and fees**: Gemini 2.5 Pro traded most and paid $1,284 in fees on $10k — [Datawallet](https://www.datawallet.com/crypto/alpha-arena-nof1-ai-explained)
- **Directional bias**: Claude Sonnet 4.5 "rarely ever shorts" — [nof1 TechPost1](https://nof1.ai/blog/TechPost1)
- **Regime misbehavior**: too conservative in bull markets and too aggressive in bear markets — [FINSABER](https://arxiv.org/abs/2505.07078)
- **Reasoning ≠ trading**
  - Reasoning-tuned models did not beat instruct models in StockBench — [Emergent Mind](https://www.emergentmind.com/topics/stockbench)
  - LMArena rank does not predict P&L — [LiveTradeBench](https://arxiv.org/abs/2511.03628)
- **Inconsistency and heterogeneity**
  - Agents given identical conditions reach divergent decisions, producing large variation in returns and drawdowns — [search excerpt, TrustTrade arXiv 2603.22567](https://arxiv.org/pdf/2603.22567)
  - Holding times and trade frequency vary widely across runs of the same model — [nof1 TechPost1](https://nof1.ai/blog/TechPost1)
  - Agents' style-switching (loss aversion, herding) is only partly consistent with behavioral-finance theory — [arXiv 2602.07023](https://arxiv.org/abs/2602.07023)
- **Prompt sensitivity**: financial reasoning is sensitive to how prompts are crafted — [ATLAS arXiv 2510.15949](https://arxiv.org/html/2510.15949v1)
- **Corrupted or hallucinated state (TradeTrap, Dec 2025)**
  - Agents were tested under injected fake news, MCP tool hijacking with false prices, and memory, position or state tampering.
  - Small perturbations propagate into extreme concentration and runaway exposure.
  - A tiny account-state error can drive ~61% loss with 100% exposure to one stock.
  - State corruption is the worst case because agents "blindly trust" it.
  — [arXiv 2512.02261](https://arxiv.org/abs/2512.02261); [Rohan Paul on X](https://x.com/rohanpaul_ai/status/1996505756984803652)
- **Backtest-to-live gap (practitioner)**: backtests showed a 65–80% win rate. Live trading produced a 23% win rate and a 40.25% loss — [Medium, J. Dolejs](https://medium.com/@kojott/i-lost-40-of-my-trading-account-by-trusting-an-ai-and-how-i-fixed-it-91b63d2f565a)

### Inferences
- Several failure modes compound. High leverage turns inconsistency and directional bias into ruin, and fees compound overtrading.
- Latency did not surface as a documented primary failure. Alpha Arena and most benchmarks run at minute-to-daily cadence. LLM latency effectively rules out HFT-style strategies rather than appearing as a measured failure.

### Gaps
- There is no quantitative study specifically on latency or slippage for LLM agents.
- Hallucinated-data rates (for example, fabricated prices or arithmetic errors) in live trading are not quantified in the sources I could reach.

## 5. Practical lessons from builders

### Takeaway
Practitioners converge on a few rules:
- Let the LLM analyze but let deterministic code execute and enforce risk.
- Paper-trade for a long time before going live.
- Benchmark honestly against buy-and-hold with realistic costs.
- Distrust backtests on pre-cutoff data.

### Cited Findings
- "LLMs are for analysis and code is for execution … hard-code your risk management" — [Medium, J. Dolejs](https://medium.com/@kojott/i-lost-40-of-my-trading-account-by-trusting-an-ai-and-how-i-fixed-it-91b63d2f565a)
- A bot lost 14% in 16 hours in a flash crash. It read oversold RSI on 3-minute bars as "buy the dip" without checking market structure. The fix was the decision framework, not better indicators — [Medium, J. Dolejs](https://medium.com/@kojott/my-ai-trading-bot-just-lost-money-heres-why-i-m-excited-about-it-e466c877366b)
- Engineering bugs matter: a zero-quantity position could not be closed and locked capital. After a premature live loss, the author adopted a 90-day paper-trading rule — [Medium, J. Dolejs](https://medium.com/@kojott/why-llm-trading-backtests-need-two-weeks-and-twenty-dollars-5a19a525a095)
- A bot reported it was trading for four days when it was not. The monitoring and observability gap was the root issue — [DEV Community](https://dev.to/jugeni/60-of-my-921-wasnt-strategy-the-other-40-wasnt-even-visible-4m30)
- Pre-registration: a builder whose LLM bots beat the benchmark declared the win invalid under rules written beforehand — [DEV Community](https://dev.to/nunc/my-llm-trading-bots-beat-the-benchmark-the-rules-i-wrote-beforehand-say-it-doesnt-count-3455)
- Honest methodology reveals the absence of edge:
  - walk-forward validation with embargo gaps
  - comparison against base rate and buy-and-hold, not against a 50% coin flip
  - multiple-testing correction
  - cost sensitivity at 0–30 bps
  — [GitHub postmortem](https://github.com/AbhayPhalswal/llm-stock-predictor-postmortem)
- Alpha Arena lesson: the winners were distinguished by fewer trades, smaller size and faster loss-cutting — [PickMyTrade](https://blog.pickmytrade.io/claude-vs-chatgpt-vs-gemini-vs-grok-trading-2026/)
- Nof1 added a "Monk Mode" (caps on frequency and size) in Season 1.5, which reflects the same lesson — [KuCoin](https://www.kucoin.com/news/flash/alpha-arena-1-5-season-results-grok-4-20-leads-with-22-38-return)
- Architecture beats backbone: agent design choices (memory, risk agents, debate) moved results more than swapping GPT, Claude or Gemini — [Agent Market Arena](https://arxiv.org/abs/2510.11695)

### Inferences
- For a Claude-based trading agent, the evidence points to these design choices:
  - Hard-coded position and leverage limits and stop-losses outside the LLM.
  - Low turnover.
  - Explicit instructions or permission for shorting and hedging, given Claude's long bias.
  - Ensembling or consensus across runs to reduce inconsistency.
  - Only post-cutoff, forward-test evaluation.
- Practitioner blogs are anecdotal, often self-promotional, and survivorship-biased. Use them for engineering lessons, not performance evidence.

### Gaps
- No major-press (Bloomberg, FT, Reuters) postmortems were retrieved. The WSJ covered FINSABER in June 2026, but the article was not accessed.
- No public audited long-run live track record of any LLM-run fund was found.
