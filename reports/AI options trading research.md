# How people use AI to trade options, and what it means for our bot

This report sums up five research notes on AI and options (September 2026): pro firms, AI trading
contests, studies of AI models doing options work, retail AI tools, and agent design. It ends with
design rules for our options book. Every claim was checked against its source. Where a source
said less than the notes did, the claim here says less too. Sources marked "snippet" were only
readable as search results.

## The short version

- **Nobody has shown that an AI model makes money choosing options trades.** No public study,
  contest or retail product shows it after costs. No AI trading contest has even traded listed
  options.
- **AI models understand options ideas but get the math wrong.** They explain a strategy well and
  then miscalculate the greeks.
- **What works is the setup around the model**: code does the math, fixed limits cap the risk,
  the model picks from a short menu, and every result gets scored.
- Our design already follows this pattern. The rules at the end make it tighter.

## 1. What professional firms do

The big options market makers (Citadel Securities, Optiver, SIG, IMC) use a lot of machine
learning, but not to replace their core:

- **Pricing and greeks come from fixed models in code.** Optiver says it is "not looking to
  replace traditional models", only adding ML on top of them.
- **ML does narrow jobs**: short-term signals, fitting the volatility surface faster, predicting
  fills.
- **Risk limits and kill switches are hard rules, not ML.** Humans decide what goes live.
- **SIG trains its traders on sizing and bias control**, for example "search for information that
  disconfirms our estimates". The skill it trains is discipline, not prediction.
- **JP Morgan's "deep hedging"** is the best documented ML inside a bank. It took about 4 years to
  roll out product by product (snippet). Its authors warn that a model trained on data with a trend
  turns from a hedger into a speculator unless it is scored on tail losses.
- **Knight Capital (2012)** is the classic failure: broken code sent more than 4 million orders
  and lost over $460M in 45 minutes. The lesson: pre-trade limits and a kill switch must sit
  outside the strategy.
- **Research on option returns** finds ML works best as a *filter* on a known source of profit,
  the "variance risk premium" (options usually price in more movement than actually happens). It is
  not a source of profit by itself. Selling options has rare but large losses.

## 2. What retail tools and hobby projects do

- **No retail AI options product publishes audited live results.** Option Alpha, Unusual Whales,
  Robinhood Cortex and Public Agents either make no claims or call the output "educational".
- **Brokers keep a human in the loop.** Interactive Brokers, tastytrade and Public all let AI
  models read accounts, but each order needs a human to confirm or re-enter it.
- **ORATS** (an options data firm) uses the same rule we do: code computes the numbers, and the AI
  "needs tools it must call to get numbers, so it can't improvise them".
- **Option Alpha's own advice**: paper trade 30–60 days first, and expect paper fills to be better
  than live fills.
- **Hobby bots on Alpaca** look like ours. One (himanshu2394i) gives Claude only a pre-filtered
  list of contracts plus 12 fixed gates, such as spread at most 10% of mid, 2% of equity per trade
  and a -3% daily loss halt. Another (YoByron) ran an iron condor bot on paper and honestly
  reported **no edge after 69 trades (23% win rate)**.
- **0DTE (same-day expiry) options**: retail traders lost about $241k per day on average in
  2021–2023, and about 76% of that was trading costs (snippet).

## 3. What the AI contests showed

None of these traded options, but they show how AI traders fail.

| Contest | Result |
|---|---|
| Alpha Arena S1 (real money, crypto, 2025) | 4 of 6 models lost; Claude Sonnet 4.5 about -42% (press figures) |
| Alpha Arena S1.5 (real money, US stocks) | 6 of 32 accounts ended positive; Claude averaged -51%; total about -35% |
| StockBench (20 stocks, 4 months) | Returns of about -3% to +2.5%, all within noise of buy-and-hold |
| LiveTradeBench (21 models, 50 days) | General model ranking did not predict trading results |
| Agent Market Arena (live) | The agent setup drove risk style more than the model did |

The failures were mechanical, not a lack of intelligence:

- the model chose its own leverage (up to 20x) and position size;
- overtrading, where fees ate the profits;
- telling models their ranking made them trade far more, and lose more;
- misreading the order of data, or its own earlier plans;
- stated confidence had nothing to do with results.

A "capital preservation" mode lost the least. Rankings did not repeat from one season to the next.

## 4. What studies say about AI models and options

**Math and greeks**

- **TraderBench (Feb 2026)** tested 12 models on options tasks. They scored 80–93 on P&L accuracy
  (which includes breakevens) but only 18–53 on greeks, which had to be within 5% of the right
  value. That is a gap of about 54 points. GPT-4o scored 87.8 on P&L and 17.8 on greeks. The best
  greeks score was 53.3. The authors call it a "competence mirage". Claude was not among the models
  tested.
- **Giving the model a pricing tool did not fix it.** The authors *suggest* the model sets the
  tool's inputs wrong (expiry, implied volatility) or misreads its precise outputs. They did not
  prove this call by call.
- **More "thinking" did not help options.** In one test on one model (Qwen3-32B), extended thinking
  added +26 on fact look-up but changed the options score by -0.1.
- **Finance math benchmarks**: the best model scored 60.9% against about 92% for human experts
  (FinanceMath), and o1 scored 67.3%, 12.5 points below experts (XFinBench). Common errors were
  rounding in middle steps and wrong formulas, such as ignoring early exercise on American options.
- **Describing a strategy in a special query language (OQL)**, which code then builds, gave strong
  models 87–95% valid queries but only 60–70% that matched what was asked (GPT-4.1 0.698). Small
  models did worse. The authors say free-form code generation makes up tickers and breaks rules.

**Forecasting and confidence**

- **Volatility**: a GPT-5.6 news-importance score was added to VIX/VXN to forecast next-day SPY
  and QQQ risk. All four of its weights came out as zero, so it added nothing beyond what option
  prices already said. One study, one model, but it is a warning.
- **KalshiBench**: on prediction-market questions, Claude Opus 4.5 was the best calibrated model
  (error 0.120, 69.3% accuracy). Every model was overconfident: at 90%+ stated confidence they were
  wrong 15–32% of the time. The one heavy-reasoning model was the worst calibrated.
- **Overconfidence about its own success**: every model tested overestimated its chances, and bad
  decisions followed from that. Most did not learn from past results shown in context. Claude
  Sonnet models and GPT-4.5 were the exceptions: they became less overconfident and decided better.
- **GPT-4 stock-return ranges** were only slightly too narrow (76.9% coverage for an 80% range).
  The miss was mainly on the *upside*. For us this points at short calls more than short puts.
- **Run-to-run variation**: the same model classifying the same news gives different answers,
  which changes portfolios. Repeating the call and combining the answers reduces this, at a cost.

**Risk-taking**

- **Gambling study**: six models played slot-machine games. Examples of loss chasing, illusion of
  control and gambler's fallacy appeared. Bankruptcy was near zero with a fixed bet and jumped when
  models chose their own bets (Claude-3.5-Haiku 0% to 20.5%, Gemini-2.5-Flash 3% to 48%).
- **Instruction following**: in a simulated market, AI agents kept following their strategy even
  while it lost money. The authors *warn* (without testing) that similar models could act alike.
- **Strategy discovery**: a strict test with no look-ahead, corrected for how many strategies were
  tried, rejected *every* strategy two frontier models found across 453 stocks and 39 ETFs, while
  passing simple buy-and-hold. A cheating strategy with a Sharpe of about 35 passed the usual
  overfitting tests and was caught only by the no-look-ahead design.
- **Backtest leakage**: agent results fall 51–62% (Sharpe) when tested after the model's training
  cutoff. Any backtest of Claude on dates before mid-2026 is contaminated.

## 5. Honest bottom line on expected results

- **Expect no proven edge at first.** The best realistic hope is the variance risk premium, earned
  with small defined-risk spreads, minus real trading costs. Claude's job is to filter and to
  explain, not to find hidden profit.
- **Most results in the first months will be noise.** Two weeks of P&L proves nothing. You need
  about 50–100 closed trades before the numbers start to mean something.
- **Paper fills are too kind.** Alpaca paper fills at the quoted price and ignores size. Real
  multi-leg fills often lose half the spread or more on each leg.
- **The "amazing stuff" to look for** is not big profits. It is a clean, honest scorecard: every
  trade, the money at risk, what Claude predicted and what happened. That is what pros look at.
- **Compare against a baseline.** Report the same spreads chosen by a plain rule with no Claude,
  and SPY buy-and-hold. If Claude does not beat the plain rule, it is not adding value.

## 6. Design rules for our options book

### Code does all the math

1. Code computes every greek, implied volatility, max loss, breakeven and probability of profit.
   Code also builds every input to any pricer (expiry, IV, rate). Claude never does.
2. Code builds a menu of pre-checked defined-risk trades (vertical spreads, iron condors) with
   their numbers attached. Claude returns one menu ID or SKIP, forced by a strict schema enum, so it
   cannot invent a symbol, strike or price.
3. If any greek, IV or quote is missing, stale or null, code rejects that trade and shows it to
   Claude as UNAVAILABLE. Claude never fills in a missing number.
4. Code checks every number Claude writes in its reasoning (for example a breakeven or delta).
   A mismatch is logged as a "hallucination" event with its own reason code.
5. The prompt includes a short definitions block for each field (for example IV rank vs IV
   percentile), as ORATS does.

### Code owns size and risk

6. Code fixes size, width and number of contracts from the risk limits. Claude cannot change them.
   No action raises size after a loss, and Claude cannot set a "win it back" target.
7. Fixed gates, all in code: each leg's bid-ask spread at most about 10% of mid; open-interest and
   volume floors; a delta band per strategy; a days-to-expiry band with no 0DTE at first; max loss
   per trade as a % of equity; a cap on total options capital; a cap per underlying; net vega and
   gamma caps; daily loss and drawdown halts.
8. A final pre-trade checker runs after Claude's vote and can only *veto*: all limits above, order
   count and rate caps, and a manual plus automatic kill switch (the Knight lesson).
9. Rank candidates by tail risk (max loss, plus the worst-case average loss from a simulated P&L
   that includes fees and bid-ask), not by expected profit.
10. Close or roll before Alpaca's expiry-day auto-liquidation window. Never hold a short leg into
    expiry.
11. Limit orders only. Start at mid and step toward the worse price, with a cap on how far to give.

### What Claude does, and must not do

12. Claude **does**: pick one menu item or SKIP, give a reason code, a falsifiable prediction
    (probability of profit, expected move), and a "disconfirming evidence" field (the SIG habit).
13. Claude **does not**: forecast volatility against option prices, compute numbers, size trades,
    place orders, or see its ranking or P&L pressure in the prompt.
14. Code computes regime features (IV rank, term structure slope, IV minus realized volatility with
    a simple HAR forecast). Claude only chooses among trades that pass a favourable IV-minus-forecast
    threshold.
15. Show Claude its own scored history: hit rate by reason code, and stated confidence vs actual
    results. Treat any stated confidence above 90% as lower than stated.
16. Run 3 samples and act only on the majority. If they split, the answer is NO_TRADE. Log the
    split rate. The vote cuts random noise, not shared model bias, so later consider a second
    prompt or model as the extra voter.

### Tracking in the shared account

17. Tag every options order with a client_order_id prefix (for example `OPT-`). Keep a separate
    ledger per trade: premium paid or received, max-loss capital committed ("amount invested"),
    and realized and unrealized P&L.
18. Report two P&Ls: the paper fill, and a haircut version that crosses half the spread on every
    leg. Charge these costs in every backtest and simulation too.
19. For short-premium trades, compare the predicted chance of max loss with how often it actually
    happens.
20. Report results against a plain-rule shadow book (same menu, no Claude) and SPY.

### Testing and change control

21. Any new options rule Claude suggests must pass a forward paper test with realistic fills and a
    Sharpe corrected for how many ideas were tried. Mid-price backtests don't count, and neither do
    backtests on dates before Claude's training cutoff.
22. Keep a version log for every pricing and data component, watch for drift in forecast error,
    and give each change that goes live a written reason code.
23. The owner approves new structures, limit changes and event blackouts (earnings, FOMC), and
    reviews a weekly scorecard of predictions vs outcomes. Keep an optional confirm-each-order mode,
    and log every decision.
24. Skip reinforcement learning and deep hedging for now. Defined-risk spreads need no dynamic
    hedge. Note it as future research only.

### How we talk about results

25. Say "Claude selects from code-generated menus under fixed risk limits". Never say "AI predicts"
    or "AI-driven forecasts". The SEC has fined firms for overstating AI (Delphia, Global
    Predictions, 2024). Always label results as paper, and give the number of trades and the cost
    assumptions.

## Main sources

TraderBench arXiv 2603.00285 · OQL arXiv 2603.16434 · FinanceMath arXiv 2311.09797 · XFinBench
arXiv 2508.15861 · Calibration-Induced Degeneracy arXiv 2608.20304 · KalshiBench arXiv 2512.16030 ·
Barkan et al. arXiv 2512.24661 · Chen et al. arXiv 2409.11540 · Gambling arXiv 2509.22818 · Honest
evaluation arXiv 2608.27734 · Agent Market Arena arXiv 2510.11695 · Can LLMs Trade? arXiv
2504.10789 · LLM volatility arXiv 2311.15180 · Profit Mirage arXiv 2510.07920 · StockBench arXiv
2510.02209 · LiveTradeBench arXiv 2511.03628 · Deep Hedging arXiv 1802.03042 · SEC press releases
2013-222 (Knight) and 2024-36 (AI-washing) · Optiver, SIG and ORATS pages · Alpaca docs.
