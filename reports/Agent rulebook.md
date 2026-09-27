# Agent rulebook: rules for the two paper-trading books

*Draft for owner review, 27 September 2026. Built from the eight book study notes in `research_notes/Book study notes/`, the three current-practice notes in `research_notes/Current market practice/`, the strategy playbook, and a line-by-line read of `trading/`. Nothing here is implemented yet.*

## Summary

The books disagree about how to make money and agree almost completely about how to lose it. Graham, Malkiel and Marks doubt that price trends can be traded. Livermore, the Market Wizards, Minervini and the trend-following literature are built on them. The century of trend evidence says the doubters are too absolute, but Faber's model halving out of sample says they are right to be sceptical. On defence, every author says the same things: survive first, risk very little per trade, decide exits before entry, never average down, keep speculation small and separate, distrust tips and stories, judge by many trades rather than recent ones, and assume any published edge is already partly used up. The market in September 2026 makes that defence more urgent:

- The S&P 500 is near record highs with a calm VIX (about 15).
- CAPE is about 41, momentum is crowded in AI and semiconductor stocks, and quant momentum unwound twice this year.
- The 10-year yield is above 5%, and stocks and bonds have been falling together, so bonds are not a dependable hedge.

The philosophy that follows is this. Let slow price trends decide how much market exposure to hold. Keep each bet tiny, and enforce every exit in code for both books. Treat Claude as a disciplined operator, not a forecaster: every deviation from the rules must carry a reason code and a falsifiable prediction, and it is scored. Compare everything with boring benchmarks (SPY and a 60/40 mix). New ideas run as logged shadow signals until a backtest and live evidence justify them. The target stays 6–10% a year with drawdowns under 15–20%. Risk rises only through a statistical gate, never because of a story or a good month.

## How to read the tables

**Status.** **BUILD NOW** means it can be coded today from daily bars, is low risk and well supported. "(exists)" means the rule is already in the code and is restated so the rulebook is complete. **TEST FIRST** means the rule is computed and logged every day as a *shadow signal* with no effect on orders, until it passes gate M-12. **LATER** means it needs data we do not have.

**Evidence grade.** **Strong** means large-sample or replicated academic evidence. **Moderate** means several independent books or practitioners agree, or the academic evidence is mixed. **Weak** means one source, an anecdote, a vendor backtest or a snippet-only figure. **Design choice** means engineering or governance, where the question is not empirical.

**Source keys:**

| Key | Source |
|---|---|
| GR | Graham and Zweig, *The Intelligent Investor* |
| MW | *Market Wizards* |
| MK | Marks, *The Most Important Thing* |
| MA | Malkiel, *A Random Walk Down Wall Street* |
| LF | Lefèvre, *Reminiscences of a Stock Operator* |
| CO | Connors |
| MV | Minervini |
| AN | Antonacci |
| CV | Covel |
| TH | Tharp |
| DG | Douglas, *Trading in the Zone* |
| PP | professional_practice |
| ST | successful_traders |
| MC | market_conditions |
| PB | Trading strategy playbook report |
| CODE | defect or gap found in the current code |

**Other conventions.**
- **Data.** Unless a rule says otherwise, the data is Alpaca IEX daily bars with `Adjustment.ALL`: open, high, low, close and volume, adjusted for splits and dividends.
- **Indicators.** SMA(n) is a simple moving average of closes. ATR20 is Wilder's average true range over 20 days. RSI2 is Wilder's RSI over 2 days.
- **Units.** *E* is account equity. 1R is 0.5% of *E*.
- **Session counts.** Where a rule counts sessions, it counts daily bars.

## (a) Market regime and "temperature"

The code already classifies each day into one of five regimes. That classifier stays as it is. The changes make it binding on both books and add a *temperature* reading that is **shown, never traded**. Graham, Marks and Malkiel all find that valuation and sentiment say little about the next year. The 2026 evidence agrees: the BofA "cash rule" sell signal was on for most of the year while the market kept rising.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| REG-1 | Trend state: `spy_above = close(SPY) > SMA200(SPY)`, evaluated on the daily close. | MW (O'Neil "M"), LF, PB | Strong | BUILD NOW (exists) |
| REG-2 | Regime label, most restrictive first: **panic** if the 504-session SPY return < 0 and 20-day realized vol ≥ the 80th percentile of the last 756 sessions; **bear** if not `spy_above`; **choppy** if SPY crossed its SMA200 at least 3 times in the last 60 sessions; **bull_volatile** if vol20 > the median vol20 of the last 252 sessions; otherwise **bull_calm**. | PB, CV, Daniel-Moskowitz via PB | Moderate | BUILD NOW (exists) |
| REG-3 | Permission multipliers (A/B/C/D): bull_calm 1/1/1/1; bull_volatile 1/0.5/0.5/0.5; bear 1/0/0/1; panic 1/0/0/0.5; choppy 1/0.5/0/1. **New:** these are binding on the Claude book too. A multiplier of 0 blocks new B/C entries, and 0.5 halves per-trade risk (see CL-11). | MW (Ryan, O'Neil), MK, PB | Moderate | BUILD NOW |
| REG-4 | **Temperature T**, for display only. Take five components, each converted to a percentile against its own trailing 1,260-session history: (1) SPY 504-session total return; (2) 1 − percentile of SPY vol20; (3) share of the 40-stock C universe above its SMA200; (4) close(SPY)/SMA200 − 1; (5) the 126-session change in close(HYG)/close(IEF). T = the mean of the five. The label is **hot** if T ≥ 0.80, **cold** if T ≤ 0.20, and neutral otherwise. Also show the share of the C universe above its SMA50, as a breadth-divergence field. | MK Ch 6, 9, 15; GR (rule of opposites) | Weak (as a timing signal) | BUILD NOW (display only) |
| REG-5 | Hot cap: if T ≥ 0.80, the B and C sleeve weights in both books are capped at their `default`. Shadow log: record the weights with and without the cap. | MK ("tilt, don't time") | Weak | TEST FIRST |
| REG-6 | Credit canary: if the 13612W momentum of HYG minus that of IEF is < 0 (month-end closes), downgrade bull_calm to bull_volatile. | MK Ch 8; Gilchrist-Zakrajšek via MK notes | Moderate (credit leads) / Weak (timing) | TEST FIRST |
| REG-7 | Stock–bond hedge monitor: show the 60-session correlation of SPY and IEF daily returns. If it is > +0.30, flag "bonds not hedging". No trade effect, because sleeve A's IEF position already follows its own 10-month SMA. | MC §2 (2026 positive correlation) | Moderate | BUILD NOW (display only) |
| REG-8 | DAA canary (VWO, BND 13612W both > 0): stays computed and displayed. Any trading use goes through REG-6-style testing. | PB (Keller) | Weak (in-sample optimized) | BUILD NOW (exists, display) |
| REG-9 | Valuation and sentiment inputs (CAPE, HY OAS, equity risk premium, FMS cash, AAII, VIX term structure): display only, and only once a data feed exists. They must never drive weights. | MK, GR, MA, MC | Weak for 1-year timing | LATER |

**Current reading (snippet data, 25 Sep 2026).** SPY is about 7.5% above its SMA200 and has had no SMA200 cross since 8 April, so the regime is bull_calm or bull_volatile. Temperature would very likely read *hot*: trailing return is high, volatility is low, and price is well above trend. Yet only 31% of stocks are above their 50-day average. The rules above let the trend keep the book invested, and let the heat show up only as caution in Claude's context.

## (b) Sleeves

### Sleeve A: trend core (50–60% of equity)

A is the sleeve with the best evidence, and the evidence is about **cutting drawdowns, not boosting returns**: Faber's out-of-sample CAGR was about 6% with a max drawdown of about 12%. Claude may not veto it in the rules book (CL-7).

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| A-1 | Universe: SPY, EFA, IEF, DBC, VNQ; cash = BIL. | PB (Faber) | Strong | BUILD NOW (exists) |
| A-2 | Signal: at the last *completed* month-end, hold asset *i* iff its adjusted month-end close > the mean of its last 10 month-end closes. | PB, CV (Bouchaud 10-month t≈5.6), ST (Faber unchanged since 2007) | Strong | BUILD NOW (exists) |
| A-3 | Sizing: base weight 1/5 of the sleeve × `min(1, 0.10 / vol60_i)`, where vol60 uses daily log returns up to that month-end. Assets that are out, plus any leftover weight, go to BIL. | PB, Moreira-Muir via PB | Moderate | BUILD NOW (exists) |
| A-4 | Trade only when \|target − current\| / max(target, current) ≥ 0.20. | MA (costs), GR (mechanical rebalancing) | Strong (costs) | BUILD NOW (exists) |
| A-5 | Sleeve A has no stops, is not measured in R, and is excluded from open-risk heat. It is judged under M-4. | TH §6.4 | Design choice | BUILD NOW (exists) |
| A-6 | GEM stays **off**. A shadow GEM runs daily with two fixes. First, the defensive leg holds AGG only if AGG's 12-month return > BIL's, otherwise BIL (so 2022-style bond losses are avoided). Second, the US leg uses **VOO**, so that SPY's 30% ETF cap does not silently clip it. | AN, ST (specification risk), MC (bonds fell with stocks) | Moderate / Weak | TEST FIRST |
| A-7 | Second vote: `w_i = 1/5 × scale_i × (0.5·[close > SMA10m] + 0.5·[r12_i > r12_BIL])`. | AN (Zakamulin: 12-month MOM best), ST (blend lookbacks) | Moderate | TEST FIRST |
| A-8 | Vol-target the *sleeve* to 10% rather than each ETF, to reduce cash drag. | MA §6.4 | Weak | TEST FIRST |
| A-9 | Add GLD as a sixth trend asset under the same A-2/A-3 rules. | CV (diversification), MC (Dalio, real assets) | Weak | TEST FIRST |

### Sleeve B: RSI(2) dips on index ETFs (15–25%, capped at 20% until validated)

B is the only daily-cadence edge and also the most challenged. Hite and O'Neil distrust oscillators, the edge has decayed since publication, and it has only practitioner backtests. Win rates reportedly fell in 2025. It stays small and heavily measured.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| B-1 | Universe: SPY, QQQ, IWM, DIA; at most 2 open positions. | CO, PB | Moderate | BUILD NOW (exists) |
| B-2 | Entry signal on the close: `close > SMA200(symbol)` and `RSI2 < 10`, with regime permission > 0. Rank by RSI2, lowest first. | CO, ST (QuantifiedStrategies 1993–2025) | Moderate / Weak (post-2010) | BUILD NOW (exists) |
| B-3 | Size: `qty = min(perm × 0.005 × mult × E / (3·ATR20), (w_B·E/2) / close)`, where *mult* is the breaker multiplier. | TH (percent risk), CO (size small) | Moderate | BUILD NOW (exists) |
| B-4 | Exits, whichever comes first: (a) close > SMA5; (b) 10 sessions held; (c) close ≤ stop = entry close − 3·ATR20. The stop is never tightened or trailed. **New:** (b) and (c) are enforced in `risk.py` for **both** books. | CO (dynamic exit, wide stops), TH (time stops) | Moderate | BUILD NOW |
| B-5 | Index-cluster heat: the combined open risk Σ(price − stop)·qty of B positions ≤ 0.75% of *E*. These ETFs are 0.85–0.95 correlated in selloffs, which are exactly the days B buys, so two positions are one bet. | MK Ch 18, MW (Kovner, Marcus), Longin-Solnik via MK | Moderate | BUILD NOW |
| B-6 | Fill logging: for every B entry and exit, log `gap_R = (fill − signal_close) / (entry − stop)`. This measures what next-open execution costs versus Connors's on-close fill. | CO, LF (venue changes the edge) | Design choice | BUILD NOW |
| B-7 | On-close execution: a second run at 15:45 ET uses the IEX last trade as a proxy close and submits market-on-close orders (`time_in_force=cls`) for B entries and exits only. | CO (overnight edge) | Moderate (overnight effect) / Weak (for this bot) | TEST FIRST |
| B-8 | Exit and entry variants, shadowed one at a time: RSI2 > 70 exit; time stop off or 15 sessions; full size when RSI2 < 5 and half size for 5–10. | CO | Weak | TEST FIRST |
| B-9 | Remove the bull_volatile halving while SPY > SMA200 (Connors: the edge is largest when VIX is high). Test this against a "vol20 < 25% annualized" gate (the practitioner VIX < 25 finding). | CO vs ST | Conflicting | TEST FIRST |
| B-10 | One additional trigger, sharing B's 2 slots: 2-day cumulative RSI2 < 35 **or** Double 7s. Never both. | CO, PB ("run one, don't stack") | Weak | TEST FIRST |

### Sleeve C: trend-template breakouts (10–20%, on probation, capped at 15%)

C is where Malkiel's critique lands hardest: a fixed list of today's 40 megacaps (survivorship bias), about 10 parameters, and no fundamentals. It is also where the 2026 crowding sits. Because per-name notional is capped at w_C/5 ≈ 3% of *E*, each trade actually risks ≤0.24% of equity, well under 1R. That is deliberately conservative for an unvalidated system.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| C-1 | Universe: the 40 names in `playbook.yaml`, each needing ≥260 bars. Documented as a large-cap variant with survivorship bias. | MA, strategy_sources §2.4 | Design choice | BUILD NOW (exists) |
| C-2 | Trend template, all required: close > SMA150 and > SMA200; SMA150 > SMA200; SMA200 today > SMA200 22 sessions ago; SMA50 > SMA150 and > SMA200; close > SMA50; close ≥ 1.25 × 252-session low; close ≥ 0.75 × 252-session high; RS ≥ 70. | MV, MW (O'Neil, Ryan) | Moderate | BUILD NOW (exists) |
| C-3 | RS = percentile of the 252-session return **within the 40-name universe**. Label it "peer RS" in the context: this is not IBD RS. | MV, strategy_sources | Weak | BUILD NOW (exists, relabel) |
| C-4 | Trigger: close > the maximum high of the prior 50 sessions, **and** today's volume / mean volume of the prior 50 sessions ≥ 1.5. IEX volume is only a small share of the consolidated tape, so treat the ratio as noisy (EX-10). | MW (O'Neil ≥1.5×), LF (line of least resistance), TH (40–100-day breakouts) | Moderate | BUILD NOW (exists) |
| C-5 | Gate: regime permission (off in bear, panic and choppy; half in bull_volatile). Rank by RS; at most 5 positions. | MW, MV, PB (the "M" filter is decisive) | Moderate | BUILD NOW (exists) |
| C-6 | Initial stop = max(close − 2·ATR20, 0.92·close). Size: `qty = min(perm × 0.005 × mult × E / (close − stop), (w_C·E/5) / close)`. | MW (7–8% max loss), TH | Moderate | BUILD NOW (exists) |
| C-7 | **Trailing stop enforced in `risk.py` (both books):** before the stop check each run, `stop = max(stop, min(low over the prior 10 sessions, excluding today))`. The stop can only rise, and it exits when close ≤ stop. | TH (the exit is part of the system), CODE | Strong (as a design requirement) | BUILD NOW |
| C-8 | Close < SMA50 → exit. Mandatory in the rules book; advisory in the Claude book. | MV, strategy_sources | Moderate | BUILD NOW (exists) |
| C-9 | Sector cap: at most 2 open C positions per static group. **Semis/AI hardware** {NVDA, AVGO, AMD, AMAT, ANET}; **Software** {MSFT, ORCL, CRM, ADBE, NOW, INTU, PANW}; **Platforms** {GOOGL, META, AMZN, NFLX, UBER, BKNG}; **Hardware/auto** {AAPL, TSLA}; **Health** {LLY, UNH, MRK, ABBV, TMO, ISRG}; **Financials** {JPM, V, MA, BAC}; **Staples/retail** {COST, HD, PG, PEP, KO, WMT}; **Industrial/energy** {XOM, CAT, GE, LIN}. | PP (semis the most crowded trade; Jan and Jul 2026 unwinds), MW (Kovner) | Moderate | BUILD NOW |
| C-10 | Failed-breakout exit: within the first 10 sessions, close < pivot → exit. | MW (Ryan), LF (Anaconda) | Weak | TEST FIRST |
| C-11 | Extension filter: skip if close > 1.05 × pivot. | MW (O'Neil ≤10%, Ryan a few %) | Weak | TEST FIRST |
| C-12 | Stricter template: close ≥ 1.30 × the 52-week low, and SMA200 rising over 84 sessions. | MV (full book) | Weak | TEST FIRST |
| C-13 | Market-relative RS: require close(sym)/close(SPY) to be within 5% of its own 252-session high, **or** use weighted RS 0.4·r63 + 0.2·r126 + 0.2·r189 + 0.2·r252. | MV, strategy_sources | Moderate (52-week-high momentum) | TEST FIRST |
| C-14 | VCP proxy: (15-session high − low)/close ≤ 0.12, ATR10/ATR50 < 0.8, and mean volume over sessions −10…−1 < mean over −50…−1. | MV | Weak | TEST FIRST |
| C-15 | Breakeven stop: once close ≥ entry + 2R, set stop ≥ entry. | MV, DG | Weak | TEST FIRST |
| C-16 | Time stop: exit if +1R has not been reached after 20 sessions. | MW (Dennis, Jones), TH | Weak | TEST FIRST |
| C-17 | Streak cut: after 5 consecutive losing C lots, halve C risk until the next winning lot. | MV, MW (Schwartz) vs DG, TH | Conflicting | TEST FIRST |
| C-18 | Earnings blackout: no new C entry if earnings fall within the next 5 sessions. | MW (Jones), PB | Moderate | LATER (needs an earnings calendar) |
| C-19 | Quality filter from SEC EDGAR: EPS > 0 in each of the last 5 years, and long-term debt < 50% of capital. | GR (Zweig) | Moderate | LATER |
| C-20 | Point-in-time universe (historical S&P 500 membership) for backtests and live selection. | MA, strategy_sources | Strong (survivorship bias is real) | LATER |

### Sleeve D: crypto trend (off by default; if enabled, at most 5%)

BTC fell about 50% between October 2025 and mid-2026 while equities set records. Two coins that are highly correlated with each other give little diversification.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| D-1 | `enabled: false`. It may be enabled only by the owner, and only after the bookkeeping fixes (Implementation plan, phase 1) are live. | MA, MC, PB | Design choice | BUILD NOW |
| D-2 | Weight band lowered to min 0, default 0.03, max **0.05**. | MA (≤5% for gold-like bets), MC | Moderate | BUILD NOW |
| D-3 | Signal: `score = mean over n in {20,30,50,80,120,180,250} of [close > (max high_n + min low_n)/2]`. Weight per coin = `score × min(1, 0.25/vol30_365) × perm_D / 2`, with the 20% rebalance band. | CV (ensembles), PB (Zarattini) | Moderate (short samples) | BUILD NOW (exists) |
| D-4 | Stop = entry − 3·ATR20, never widened. Exit on stop or when score = 0. | TH, CV | Moderate | BUILD NOW (exists) |
| D-5 | Less churn: move to zero only on a close below the N-day low, not the midpoint. | CV (holds of 60–80 days) | Weak | TEST FIRST |
| D-6 | Trailing stop: `stop = max(stop, close − 3·ATR20)`. | TH | Weak | TEST FIRST |

## (c) Portfolio risk limits and circuit breakers

Every limit here is either the current policy or **tighter** than it. None raises risk.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| RISK-1 | Long only: no leverage, shorts or options, and allowlisted symbols only. | all books, PB | Strong | BUILD NOW (exists) |
| RISK-2 | 1R = 0.5% of *E* per trade; hard cap 2%. The 1% level is reachable only per sleeve through M-10. | MW (Kovner, Hite), TH | Strong | BUILD NOW (exists) |
| RISK-3 | B, C and D entries need a stop below price. Stops never widen. No increase while price < average entry. | MW, LF, DG, TH | Strong | BUILD NOW (exists) |
| RISK-4 | A close ≤ stop exits at the next open, whoever is deciding. The stop is ratcheted first (C-7, D-6 once promoted). | TH, DG | Strong | BUILD NOW (exists) |
| RISK-5 | Caps: ETF 30%, stock 10%, crypto 10% of *E* per symbol (summed across sleeves); cash buffer ≥ 5%; open-risk heat ≤ 6% of *E*; at most 2 held stocks with ρ60 > 0.7 against a new stock. | PB, MW | Moderate | BUILD NOW (exists) |
| RISK-6 | **Equity-like cap:** the gross notional of {SPY, VOO, EFA, VEU, VNQ, QQQ, IWM, DIA} plus all single stocks must be ≤ 75% of *E*. Increases that would breach it are clipped. | GR (25–75% band) | Moderate | BUILD NOW |
| RISK-7 | **Speculative cap:** the sleeve weights w_C + w_D ≤ 0.20. | GR (Zweig: speculative money ≤10%, kept small and separate) | Moderate | BUILD NOW |
| RISK-8 | **Probation cap:** a sleeve that has not passed M-10 has its weight ≤ its `default` (B 0.20, C 0.15, D 0.03), in both books. | TH, MA, LF (keep B low until proven) | Moderate | BUILD NOW |
| RISK-9 | Drawdown from the high-water mark: at 10%, risk per trade is halved; at 15%, no new entries; at 20%, halt with exits only until a human resets. | MW (Jones, Seykota), PB | Strong (direction) / Design choice (levels) | BUILD NOW (exists) |
| RISK-10 | **Watch tier at a 5% drawdown:** shown to the owner and to Claude. The Claude book may not raise B, C or D weights. The rules book is unchanged. | PP (pod "on watch" at 2.5–3%, soft stop at 5%) | Moderate | BUILD NOW |
| RISK-11 | Daily loss ≤ −1% of *E* (currently "−2R") → no new entries today. Weekly loss ≤ −2.5% of *E* ("−5R") → none this week. The context must label these in % of equity, not R. | MW (Jones), TH §6.3 | Moderate | BUILD NOW (exists, relabel) |
| RISK-12 | **Monthly loss cap:** if month-to-date P&L ≤ −4% of the equity at the last run of the prior month, no new B, C or D entries for the rest of the calendar month. Sleeve A is exempt. | MW (Jones: never a double-digit month) | Moderate | BUILD NOW |
| RISK-13 | **Sleeve drawdown tiers (B, C, D):** track each sleeve's cumulative realized + unrealized P&L. If the drop from its peak ≥ 3% of current *E*, that sleeve's new entries run at half risk. If ≥ 5%, new entries are off until the owner reviews. | PP (tiered pod stops), MW (Schwartz) | Moderate | BUILD NOW |
| RISK-14 | Stress line, display only: −20% × equity-like notional, −10% × DBC, and −30% × crypto, as a % of *E*. Shown next to heat. | TH (Gallacher's "assume the worst tomorrow"), MC (record leverage, gap risk) | Design choice | BUILD NOW (display only) |
| RISK-15 | Kill switch; a human re-enables after a halt. | PB | Design choice | BUILD NOW (exists) |

## (d) Execution and costs

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| EX-1 | The run starts at 21:35 UTC on weekdays. Signals come from the daily close. Stock and ETF orders are DAY market orders that fill at the next open; crypto orders are GTC. | PB | Design choice | BUILD NOW (exists) |
| EX-2 | Exits are always market orders, never limits. | LF (Livermore missed moves using limits) | Moderate | BUILD NOW (exists) |
| EX-3 | Sells go first. At most 10 orders a day and a $25 minimum order. **New:** if buys must be dropped, keep them in sleeve order A → B → C → D, then by notional, largest first. | MA, TH (costs) | Moderate | BUILD NOW |
| EX-4 | **Record real fills:** at the start of each run, read the previous run's filled orders (average fill price and filled quantity) and write them into the lots. Store `slippage_bps = (fill / signal_close − 1) × 10⁴`, signed so that positive means worse for us. | CODE, TH (data are not the market) | Design choice | BUILD NOW |
| EX-5 | Costs: charge 5 / 10 / 25 bps per side (ETF / stock / crypto) inside R_net. If the median measured slippage over ≥30 fills in a class is more than twice the model, raise that class's model to the measured median. | MA, TH | Strong (costs matter) | BUILD NOW |
| EX-6 | Entry limit: for B and C entries, a DAY limit at signal close + 0.5·ATR20; unfilled orders expire. Shadow: record whether the order would have filled and the risk overshoot that was avoided. | TH, versus MW (Kovner: gap breakouts are more reliable) | Conflicting | TEST FIRST |
| EX-7 | Data sanity (extends `validate`): block new entries in a symbol whose last bar is stale by more than 5 days, has a close ≤ 0, has zero volume, or moved more than 25% in one day with no known corporate action. | TH (reliability bias) | Moderate | BUILD NOW |
| EX-8 | Tax lots and wash sales (30-day repurchase of B's four ETFs), plus estimated after-tax returns. | MA §6.3 | Strong (for live money) | LATER (required before G-6) |
| EX-9 | A second price source, to catch cases where two sources disagree. | PB | Moderate | LATER |
| EX-10 | Consolidated (SIP) volume for C-4. | CODE (IEX volume is partial) | Moderate | LATER |

## (e) What Claude may and may not do

Across the books, the lesson is that discretion is where traders lose money. Examples include Seykota's management overriding his system, Livermore's "Percy Thomas" tips, the LLM contest losses, and the Taiwan and Brazil base rates. The professional pattern in 2026 is to keep the LLM inside a rules-based process (Man Group's AlphaGPT, AIA Labs). So Claude's freedom is bounded, and **every deviation is recorded as a scored bet**.

### Rules for both books

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| CL-1 | Claude cannot change config, policy or parameters. Its output must validate against a strict JSON schema; invalid output → hold positions, stops still enforced. | PB, DG | Strong | BUILD NOW (exists) |
| CL-2 | **Evidence discipline:** every reason carries `evidence: [context paths]`, for example `rule_signals.C.indicators[NVDA].volume_ratio`. Code checks that each path exists in today's context and drops any action or skip whose evidence is empty or invalid. News, remembered narratives and outside opinions are not valid evidence. | LF (tips), DG Ch 8, MK ("who doesn't know that?"), PP | Moderate | BUILD NOW |
| CL-3 | **Version stamp** on every decision and every lot: `prompt_version` (hash of the role text, brief and schema), `model`, `effort` and `context_schema`. Change these only at an evaluation boundary; each version is its own sample. | DG (don't change variables mid-sample), PP (model risk) | Design choice | BUILD NOW |
| CL-4 | **Daily fields, both books:** `journal_note` (≤5 sentences); `temperature_ack` (the T label from REG-4); `likely_error ∈ {commission, omission, none}` plus one sentence; `flags[]`. | MK Ch 18, LF (score your calls) | Design choice | BUILD NOW |
| CL-5 | **Falsifiable predictions:** 0–3 per day, each `{id, symbol ∈ allowlist, horizon_sessions ∈ {5, 20, 60}, direction ∈ {above, below}, threshold_pct, probability ∈ [0.05, 0.95], linked_decision}`. Code resolves each one from closes at the horizon and scores it (M-7). Every Claude-book deviation (CL-13) and every rules-book skip must link to one. | LF (the "book of hits and misses"), MK (calibration), ST (pre-registration) | Moderate | BUILD NOW |
| CL-6 | Tighten the prompts. Add Douglas's "think in samples" paragraph, the expected losing-streak table (M-2), "doing nothing is usually right", and "in bear or panic regimes the rules already defend; do not add discretionary selling at lows". Replace the blended `win_rate`/`avg_R` with per-sleeve statistics. | DG, TH, MK, MA | Moderate | BUILD NOW |

### Rules book: Claude may only skip or halve

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| CL-7 | `skip_entries` and `halve_sleeves` apply only to **new increases in sleeves B, C and D**. Claude may never touch sleeve A, exits or stops. *(Today `apply_review` can skip A rebalances; this rule fixes that.)* | MW (Hite, Seykota: no override), CODE | Moderate | BUILD NOW |
| CL-8 | Each skip or halve needs `reason_code`, one of the following. **EARNINGS_IN_WINDOW** (C only; must state a date and `verified=false` until C-18 data exists). **DATA_SUSPECT** (must cite `data_problems` or a price field). **SCHEDULED_EVENT** (FOMC, CPI or payrolls on the next session; B and C only). **HALT_OR_ILLIQUID**. **CORPORATE_ACTION**. Mood, macro stories and recent losses are not codes. | DG Ch 8, trading_in_the_zone §6.2(d) | Moderate | BUILD NOW |
| CL-9 | **Shadow trades:** every skipped or halved entry opens a shadow lot at the next session's open, with the rule's stop and size, and the sleeve's normal exits close it. `veto_value = −Σ(shadow R_net × fraction vetoed)`, so a positive value means the vetoes helped. After ≥30 scored vetoes, if Σ veto_value < 0, allowed codes shrink to DATA_SUSPECT and HALT_OR_ILLIQUID until the owner resets. | DG (take every signal), MW (Seykota), trading_in_the_zone §6.2(c) | Moderate | BUILD NOW |

### Claude book: Claude decides, inside hard limits

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| CL-10 | Claude sets sleeve weights inside [min, max], after RISK-7 and RISK-8, and sets target positions. Every limit in `risk.py` applies unchanged. | PB | Design choice | BUILD NOW (exists) |
| CL-11 | **Eligibility:** new or increased B positions only in B symbols with close > SMA200 and perm_B > 0. New C positions only in names that pass C-2 today, with perm_C > 0. D only when enabled. A only A assets and BIL (plus the GEM tickers if A-6 is promoted). Per-trade risk is multiplied by the regime permission. | MW (O'Neil "M"), PP (autonomous LLM trading failed), LF (tips) | Moderate | BUILD NOW |
| CL-12 | **Weight rate limit:** each sleeve's weight moves by at most ±0.05 per change, and at most once per 5 sessions. An increase in B, C or D needs `reason_code ∈ {SIGNAL_COUNT_CHANGE, REGIME_CHANGE, VOLATILITY_CHANGE, RETURN_TO_DEFAULT}`. There is no code for recent performance. | MK Ch 10 and 13 (envy, reaching for return), DG (house money) | Moderate | BUILD NOW |
| CL-13 | **Deviation records:** whenever Claude's target for a symbol differs from the rules' target by more than 20% of the larger, or in direction, Claude must emit `{symbol, sleeve, rule_pct, claude_pct, reason_code, evidence, prediction_id}`. An action without a record is dropped. | DG, LF, MW | Moderate | BUILD NOW |
| CL-14 | **Stop floor:** Claude's stops for B, C and D are raised to at least the rule stop, which is price − 3·ATR20 for B and D, and max(price − 2·ATR20, 0.92·price) for C. Claude may set a tighter stop but never a wider one. *(Today only `stop < price` is checked.)* | TH, CODE | Moderate | BUILD NOW |
| CL-15 | Self-consistency: run `decide` twice and act only on actions both runs agree on. On disagreement, do nothing and log it. | DG (don't add random variables) | Weak | TEST FIRST |

## (f) Measurement

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| M-1 | **Benchmarks,** computed daily from closes over the same capital and dates: (1) SPY buy-and-hold; (2) 60/40 SPY/IEF rebalanced monthly; (3) GTAA-5 buy-and-hold at 20% each, rebalanced annually. Report return, volatility, Sharpe and max drawdown for each book and benchmark. | GR, MA (risk-matched placebo), PB | Strong | BUILD NOW |
| M-2 | **Per-sleeve trade statistics (B, C, D),** from closed lots, net of costs: n, win rate, average win and loss in R, E = mean(R_net), sd, `SQN = √min(n,100) × E / sd` (shown only when n ≥ 30, labelled "t-stat of mean R"), max losing streak, worst and best R, share of total R from the top 5% of lots, MAE and MFE in R, and median hold. The brief should state expected streaks: at a 35–45% win rate, the longest losing streak in 100 trades is typically 7–9 and 11–15 in the worst 5% of cases. | TH, DG, MW (Dennis 95/5) | Strong (statistics) / Design choice | BUILD NOW |
| M-3 | **R bookkeeping:** a trade is one lot's life from first fill to zero quantity. `initial_risk_$ = Σ over each buy of qty_add × (fill_add − stop_at_add)`. `R_net = (realized P&L − costs) / initial_risk_$`. Partial sells add realized P&L to the lot and do not open a new trade. | TH, CODE | Design choice | BUILD NOW |
| M-4 | **Sleeve A report:** return, max drawdown, time spent in BIL, and the share of SPY's 20 best and 20 worst days each year that were spent in cash. Compare with benchmark (3). | MA (missed best days), ST (Faber: 70–80% of extreme days fall below the 200-day) | Moderate | BUILD NOW |
| M-5 | **Claude-book attribution:** for each deviation (CL-13), `value_20d = (claude_pct − rule_pct) × (close_{t+20}/fill_t − 1)`, as % of *E*. Report the sum, the hit rate and n. Also report the monthly return difference between the Claude and rules books, by sleeve. | DG, MK Ch 19 | Moderate | BUILD NOW |
| M-6 | **Override report** (rules book): n vetoes, Σ veto_value (CL-9), and the value by reason code. | DG | Moderate | BUILD NOW |
| M-7 | **Prediction scoring:** Brier score, against a reference Brier score that uses the event's frequency for that symbol and horizon over the last 1,260 sessions. Skill = 1 − Brier/Brier_ref, with a calibration table in 10% bins. Reported once 50 predictions have resolved. | MK (calibration), LF | Moderate | BUILD NOW |
| M-8 | **Asymmetry and consistency:** monthly up-capture and down-capture versus SPY, and the share of rolling 6- and 12-month windows with a positive return. | MK Ch 19, MW (Hite) | Moderate | BUILD NOW |
| M-9 | **API cost as an expense ratio:** record the tokens and dollars of each Claude call. Report each book's return net of its own API cost, and the cost annualized as % of *E*. Malkiel's ceiling for an active fund is 0.50% a year, which is $50 on $10k. | MA §6.2 | Strong (costs) | BUILD NOW |
| M-10 | **Promotion gate** (a sleeve's risk from 0.5% to 1% R, and C off probation), all required: ≥100 closed paper lots in the sleeve after the phase 1 fixes; E_net > 0; SQN ≥ 2.0; if a backtest exists, live E ≥ 0.5 × backtest E; no halt in the last 63 sessions; the owner edits `risk_pct_by_sleeve` by hand. Code only reports whether the gate has passed. | TH, PB (halve backtests), DG | Strong | BUILD NOW (report) |
| M-11 | **Demotion:** if n ≥ 30 and the one-sided 90% bootstrap upper bound of mean R_net < 0, the sleeve drops to its min weight at half risk. If n ≥ 50 and SQN ≤ −1.0, the sleeve's new entries turn off pending review. | TH, MA (decay), PB | Moderate | BUILD NOW |
| M-12 | **TEST FIRST → BUILD gate,** all required: (i) a backtest over at least 2016–2026 on Alpaca bars (2005 onwards if a longer daily source is added), with next-open fills and EX-5 costs; (ii) higher net expectancy, or a max drawdown at least 20% lower with CAGR down no more than 10%; (iii) the effect keeps its sign when each parameter moves ±25%; (iv) the effect still matters when halved; (v) ≥30 live shadow signals agree in sign; (vi) owner sign-off. Promote at most one rule per sleeve per quarter. | TH (degrees of freedom), MW (Dennis: robust over optimal), PB (Bailey–López de Prado, Harvey), ST (Davey) | Strong | BUILD NOW (process) |
| M-13 | **Pre-registration log:** every parameter set or prompt version ever tried is appended to `state/experiments.jsonl` with a date and the reason. | PB, ST (dev.to pre-registration) | Strong | BUILD NOW |
| M-14 | Sleeve kill when live results fall below the 5th percentile of bootstrapped backtest paths. | PB | Moderate | LATER (needs a backtester) |

## (g) Going-live gate

Graham and Zweig say to trade on paper for about a year and then compare with an index fund. Davey incubates for 6–12 months. Douglas allows discretion only after a clean mechanical sample. The gate combines all three and is **pre-registered**: changing it restarts the clock.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| G-1 | At least 252 sessions of paper trading **after** the phase 1 bookkeeping fixes are deployed. Any bug that corrupts P&L records restarts the count. | GR (Zweig), ST (Davey) | Moderate | BUILD NOW (report) |
| G-2 | Over that window, net of trading and API costs, the book must beat benchmark (2), 60/40, on Sharpe, **and** its max drawdown must be ≤ 0.7 × SPY's max drawdown. Beating SPY's return is not required. | GR, MA, PB | Moderate | BUILD NOW (report) |
| G-3 | Live, only sleeve A and sleeves that passed M-10 may run. B runs at its min weight until it passes. C and D run at 0 until they pass. | TH, MA | Moderate | BUILD NOW (policy) |
| G-4 | The Claude book goes live only if it beats the rules book: a paired block bootstrap of daily return differences over ≥252 sessions, one-sided p < 0.10, **and** Σ value_20d (M-5) > the Claude book's API cost. Otherwise the rules book is the live candidate, and it keeps the Claude review only if Σ veto_value (M-6) > the review's API cost. | MK (luck is large; skill needs many observations), PP, ST (LLM contests) | Moderate | BUILD NOW (report) |
| G-5 | Operations: no unexplained reconciliation difference > 1% in the last 60 sessions; the kill switch and halt reset have been rehearsed; no data-sanity blocks left unresolved. | TH (rehearse the worst case) | Design choice | BUILD NOW |
| G-6 | Tax: live trading only in a tax-advantaged account, or after EX-8 is built. | MA | Strong | LATER |
| G-7 | Initial live capital ≤ 10% of the owner's investable assets, at the same 0.5% R, with no increase for 6 live months. If median live slippage over 30 fills is more than twice the model, go back to paper. | GR (Zweig: ≤10%), LF (venue changes the edge) | Moderate | BUILD NOW (policy) |

## Conflicts resolved

1. **Malkiel and Graham versus trend following.** Both say price history cannot beat buy-and-hold after costs. Their evidence is old tests of single-stock filter rules. Neither tests diversified asset-class trend, which has a long cost-adjusted record of *cutting drawdowns* (Hurst–Ooi–Pedersen; Faber out of sample). **Decision:** keep trend as the core, and judge it as a drawdown tool against 60/40 and a risk-matched passive mix (M-1, G-2), not as an alpha source. From Malkiel we take his cost, turnover and survivorship warnings: C is capped (RISK-7, RISK-8) and its universe is flagged (C-1, C-20).

2. **Connors "stops hurt" versus a disaster stop.** Connors found tighter stops worse for mean reversion. But his tests ran from 1995 to 2007, and 2026 brings record margin debt and leveraged-ETF assets, which make overnight gaps more likely. **Decision:** keep the 3·ATR stop, wide and never tightened or trailed. It is catastrophe insurance, and because B's size is set by notional, it rarely drives position size. Stop variants such as 5·ATR or no stop go only to the backtest.

3. **Marks's "buy in panics" versus no averaging down and B/C off in a panic.** Marks buys fear because he has an intrinsic-value anchor and permanent capital. The bot has neither, and momentum crashes cluster in panic rebounds. **Decision:** no contrarian buying and no averaging down (RISK-3). B and C stay off in bear and panic (REG-3). What we take from Marks is the other half: the Claude book must not add discretionary selling at lows (CL-6), because the forced seller is his worst position.

4. **Pod-shop drawdown limits versus the current breakers.** Pod shops halve a book at −5% and close it at −7.5%. But a pod is fired and replaced, while a trend core must sit through 10–12% drawdowns to earn its keep. Tight book-level stops would crystallize A's losses at lows. **Decision:** keep the book breakers at 10/15/20%. Add the pod *structure* where it fits: a −5% watch tier (RISK-10), a monthly cap (RISK-12) and tiered drawdown limits per sleeve for the satellite sleeves (RISK-13).

5. **Next-open versus on-close fills for RSI(2).** Connors's edge includes the overnight move, and our fills arrive at the next open. **Decision:** keep next-open fills and measure what they cost (B-6). A pre-close run with market-on-close orders is TEST FIRST (B-7), because it adds a second scheduled run and relies on an IEX proxy close. B's backtest must use next-open fills, and we expect a weaker edge.

6. **2026: stocks and bonds falling together, 10-year yield near 5%.** Bonds did not hedge in 2022 or in 2026's oil-driven moves. **Decision:** no change to A's per-asset rule. IEF is held only while it is above its own 10-month SMA, and the cash leg is BIL, which yields about 4%. GEM's unconditional AGG leg is exactly the 2022 failure, so GEM stays off and its shadow gets a trend filter (A-6). REG-7 displays the correlation. Long-duration Treasuries (TLT) are not added.

7. **Crowding in semis and momentum fragility.** Momentum leads 2026, but its volatility is near a six-year high, the crowding is at record levels, and it unwound in January and reportedly in July–August. **Decision:** C keeps its regime gate, and adds the sector cap (C-9), the speculative cap (RISK-7) and the probation cap (RISK-8). Temperature is shown but does not cut exposure while the trend is up (REG-4 and REG-5), because the low-cash sell signal failed all year.

8. **Douglas's "take every signal" versus veto rights and streak cuts** (Minervini, Schwartz). **Decision:** Claude's vetoes are allowed but shadow-scored, and they are revoked if they lose (CL-9). Streak-based size cuts are TEST FIRST (C-17), because trades are not independent and streaks may really signal a regime, but the book evidence is anecdotal.

9. **How many trades is enough:** Douglas says 20, Tharp says 100, and statistics says 100–225. **Decision:** at 20 trades, show statistics but draw no conclusion. A sleeve needs 100 trades plus SQN ≥ 2 before promotion (M-10). Demotion can come earlier (M-11), because cutting risk needs less proof than adding it.

10. **Volatility targeting: sound practice, but procyclical.** **Decision:** keep it (A-3, D-3). The bot is too small to feed a cascade of forced selling, and the evidence behind vol management (Moreira–Muir) is strong.

11. **Hot market (CAPE 41, low VIX) versus a risk-on trend.** **Decision:** the trend decides exposure. Heat only limits Claude's freedom, through RISK-10, CL-12 and the REG-5 shadow.

12. **Crypto:** Dalio and Druckenmiller hold some bitcoin, while Malkiel likens bitcoin promoters to John Law. **Decision:** D stays off. If the owner enables it, it is capped at 5% and counted in the 20% speculative cap.

## Rejected

- **Scaling out in thirds** (Douglas): it cuts off the right tail that pays for trend and breakout sleeves, and Tharp calls it reverse position sizing.
- **Pyramiding** (Livermore, Turtles): it adds parameters to C while C is still on probation. Revisit after C passes M-10.
- **Conviction sizing or "bet big on A+ setups"** (Marcus, Steinhardt): this is where most of the book's blow-ups came from, and the LLM contests lost money the same way.
- **Covel's 5% risk per trade**: that is ten times our 1R.
- **Graham's 25% equity floor**: sleeve A is designed to leave equities in long bear markets. Only the 75% ceiling is kept (RISK-6).
- **Valuation-timed exposure** (CAPE, FMS cash rule, Grantham): weak 1-year evidence, and the 2026 sell signal failed. Display only.
- **Graham value screens and net-nets**: they need fundamentals and micro-caps, and do not fit a daily ETF/megacap bot.
- **Shorting, options, pairs and covered calls**: excluded by policy, and pairs trading has decayed.
- **Climax or blow-off exits** (Marcus): futures-specific, and they cut the right tail.
- **Weekday and Friday-close rules, end-of-month day rankings**: data-mined, with weak modern evidence.
- **Claude checking fundamentals or earnings from memory**: training-data recall is unverifiable. This waits for real data (C-18, C-19).
- **"Market zone" or intuition prompts** (Douglas): unfalsifiable discretion.
- **Marcus-style 3–4-week trading pauses**: crude, and the breakers already cover this with defined thresholds.
- **A passive "sleeve 0" core** (Malkiel): benchmark (2) already provides the passive comparison without adding a sleeve.
- **Dollar-cost averaging**: the account is fully funded with no new deposits.

## Implementation plan (BUILD NOW rules only)

**Phase 1: bookkeeping bugs.** These come first, because every statistic and gate depends on them.

1. **`update_lots` keeps the original stop when a lot is added to, so R is wrong** (engine.py). When quantity rises, `entry_price` is blended but `initial_stop` stays and `lot.stop` is overwritten, so R divides by a stale distance. Fix: add `initial_risk_dollars`, `realized_pnl`, `costs`, `lot_id` and `opened_fill_date` to `Lot` (models.py). For each add, `initial_risk_dollars += add_qty × (fill − stop_at_add)`. R follows M-3.
2. **Partial reductions never create a closed-trade record** (engine.py). A sale that leaves qty > 0 just lowers the quantity, so its P&L disappears from the trade statistics. D's rebalance band, reconcile scaling and Claude trims all trigger this. Fix: record `realized_pnl += sold_qty × (fill − avg_entry) − costs`, and append a partial-fill event to `lot.events`. The closed-trade record is written at zero quantity with the total P&L (M-3). `reconcile()` scaling must write the same event, with reason `reconcile`.
3. **The sleeve C trailing stop is not enforced in `risk.py`.** C's 10-day-low exit lives only in `strategies.sleeve_c`. The Claude book can hold through it, and heat uses the stale initial stop. Fix: add `RiskEngine._ratchet_stops()` before step 1 of `apply()`. For C lots, `stop = max(stop, low.iloc[-11:-1].min())`; for B lots, enforce the 10-session time stop from `entry_date`. Persist the ratcheted stop through the targets (C-7, B-4).
4. **Lots record the signal-day close, not the fill** (engine.py `update_lots(..., prices, ...)`). Entry and exit prices, P&L and R are all taken at the signal close, while real fills happen at the next open. Fix: add `broker.fills_since(ts)` (Alpaca `get_orders(status=closed)` returns `filled_avg_price` and `filled_qty`; the simulator fills at the next bar's open). Store pending orders in state and settle lots at the start of the next run (EX-4).
5. **`apply_review` can skip sleeve A increases** (engine.py). Fix: restrict it to sleeves B, C and D (CL-7).

**Phase 2: risk rules** (`risk.py`, `risk_policy.yaml`).

- New policy keys, all enforced in `RiskEngine.apply` or `_clip_portfolio`:

  ```yaml
  portfolio.max_equity_like: 0.75
  portfolio.equity_like_symbols: [...]
  portfolio.max_speculative_weight: 0.20
  portfolio.cluster_heat: {B_index: {symbols: [SPY, QQQ, IWM, DIA], max: 0.0075}}
  breakers.watch_drawdown: 0.05
  breakers.monthly_loss_pct: 0.04
  breakers.sleeve_dd_halve: 0.03
  breakers.sleeve_dd_off: 0.05
  per_trade.risk_pct_by_sleeve: {B: 0.005, C: 0.005, D: 0.005}
  ```

- `breaker_status`: add the watch tier, the monthly cap (month-start equity comes from `equity_history`) and the per-sleeve tiers. The sleeve tiers need `state.sleeve_pnl` with cumulative P&L and a peak per sleeve, updated daily in engine.py. Relabel the daily and weekly limits as % of *E*.
- Claude-book stop floor (CL-14) and the buy-drop priority (EX-3, in `_orders`).
- `engine.normalize_weights`: apply the RISK-7 and RISK-8 caps. RISK-8 reads `state.promoted_sleeves`.
- `data.validate`: add the EX-7 checks (zero volume, one-day moves > 25%).

**Phase 3: strategies and config.**

- `strategies.sleeve_c`: sector cap (C-9) from a new `sectors:` map in `playbook.yaml`.
- `playbook.yaml`: D `max: 0.05`, `default: 0.03`; add HYG to the data list for REG-4.
- Every TEST FIRST rule gets a `shadow_*` function returning flags added to `plan.candidates` and `journal.jsonl`, with no effect on targets.

**Phase 4: regime** (`regime.py`). Add `temperature()` (REG-4) and `stock_bond_corr` (REG-7) to `Regime`, and fetch about 1,800 sessions of SPY, HYG and IEF for them. Make REG-3 binding in the Claude book through `decision_to_targets` (CL-11).

**Phase 5: Claude layer.**

- `llm.py` schemas: RulesReview gains `reason_code`, `evidence`, `prediction_id` per skip, plus `temperature_ack`, `likely_error` and `predictions`. ClaudeDecision gains `deviations[]`, `weight_change_reasons` and `predictions`.
- Prompt additions (CL-6) and a `prompt_version` hash (CL-3).
- `engine.decision_to_targets`: eligibility (CL-11), the weight rate limit and reason codes (CL-12), dropping deviation actions with no record (CL-13), and checking evidence paths (CL-2).
- `build_context`: per-sleeve statistics, temperature, stress line, and breakers in %.

**Phase 6: measurement.**

- New `trader/shadow.py`: shadow lots for vetoes, and resolution of predictions and deviations.
- New `trader/metrics.py`: M-1 to M-11, SQN, bootstrap, capture ratios, Brier score.
- `state.py`: new fields `shadow_lots`, `predictions`, `deviations`, `sleeve_pnl`, `promoted_sleeves` and `api_cost`.
- `llm.py`: store API cost using usage multiplied by the price table.
- `__main__.py report`: benchmarks, per-sleeve table, gate status (M-10, G-1 to G-5).
- `state/experiments.jsonl` (M-13).

**Phase 7: backtester** (the prerequisite for any TEST FIRST promotion, M-12). Add `trader/backtest.py`. It replays `build_plans`, then `RiskEngine`, then next-open fills over history using the same code paths, with the cost model applied. It starts with the 2016–2026 Alpaca history.

**Tests** (in `tests/`):
- a lot with an add, then a partial sell, then a full close gives one trade with the correct R;
- a C stop ratchets and is enforced in the Claude book;
- a B time stop in the Claude book;
- a sleeve A skip is rejected in the rules book;
- the equity-like, speculative, cluster and monthly caps each clip correctly;
- a Claude stop below the floor is raised;
- a deviation without a record is dropped;
- a prediction resolves and is scored;
- a shadow veto lot closes under the sleeve's rules.

## Rule count

| Status | Count |
|---|---|
| BUILD NOW (existing rules, kept) | 25 |
| BUILD NOW (new or changed) | 42 |
| TEST FIRST | 26 |
| LATER | 9 |
| **Total** | **102** |
