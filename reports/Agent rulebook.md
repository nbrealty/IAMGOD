# Agent rulebook: rules for the two paper-trading books

*Draft for owner review, 27 September 2026. Sources: the eight book study notes, the three 2025–26 current-practice notes (snippet-level, so treat their figures as indicative), the strategy playbook, and a line-by-line read of `trading/`. Nothing here is implemented yet.*

## Summary

The books disagree about how to make money and agree almost completely about how to lose it. Graham, Malkiel and Marks doubt that price trends can be traded. Livermore, the Market Wizards, Minervini and the trend-following literature are built on them. A century of evidence says the doubters are too absolute. Faber's model halving out of sample says they are right to be sceptical.

On defence, every author says the same things:
- survive first, and risk very little per trade;
- decide the exit before entering;
- never average down;
- keep speculation small and separate;
- distrust tips and stories;
- judge by many trades, not the latest ones;
- assume any published edge is already partly used up.

The market in September 2026 makes that defence more urgent:
- The S&P 500 is near record highs with a calm VIX (about 15).
- CAPE is about 41, momentum is crowded in AI and semiconductor stocks, and quant momentum unwound twice this year.
- The 10-year yield is above 5%, and stocks and bonds have fallen together, so bonds are not a dependable hedge.

The resulting philosophy:
- Slow price trends decide how much market exposure to hold.
- Each bet is tiny, and every exit is enforced in code, in both books.
- Claude is a disciplined operator, not a forecaster. Every deviation from the rules needs a reason code and a falsifiable prediction, and it gets scored.
- Everything is compared with boring benchmarks (SPY and a 60/40 mix).
- New ideas run as logged shadow signals until a backtest and live evidence justify them.
- The target stays 6–10% a year with drawdowns under 15–20%. Risk rises only through a statistical gate, never because of a story or a good month.

## How to read the tables

**Status.**
- **BUILD NOW:** can be coded today from daily bars, low risk, well supported. "(exists)" means the rule is already in the code and is restated so the rulebook is complete.
- **TEST FIRST:** computed and logged every day as a *shadow signal* with no effect on orders, until it passes gate M-12.
- **LATER:** needs data we do not have.

**Evidence grade.**
- **Strong:** large-sample or replicated academic evidence.
- **Moderate:** several independent books or practitioners agree, or the academic evidence is mixed.
- **Weak:** a single source, an anecdote, a vendor backtest or a snippet-only figure.
- **Design choice:** engineering or governance, where the question is not empirical.

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
| CODE | a defect or gap found in the current code |

**Conventions.**
- **Data:** Alpaca IEX daily bars (adjusted), unless stated otherwise.
- **Indicators:** SMA(n) is a simple moving average of closes. ATR20 is Wilder's average true range over 20 days. RSI2 is Wilder's RSI over 2 days.
- **Units:** *E* is account equity, and 1R = 0.5% of *E*.
- **Counting:** "Sessions" means daily bars.

## (a) Market regime and "temperature"

The existing five-regime classifier stays as it is. The changes make it binding on both books and add a temperature reading that is shown to Claude but never traded. Graham, Marks and Malkiel all find valuation and sentiment nearly useless for 1-year timing. The 2026 evidence agrees: the BofA "cash rule" sell signal was on for most of the year while the market kept rising.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| REG-1 | Trend: `spy_above = close(SPY) > SMA200(SPY)`, on the daily close. | MW, LF, PB | Strong | BUILD NOW (exists) |
| REG-2 | Label, most restrictive first. **panic:** SPY 504-session return < 0 and vol20 ≥ the 80th percentile of the last 756 sessions. **bear:** not `spy_above`. **choppy:** ≥3 SPY/SMA200 crossings in the last 60 sessions. **bull_volatile:** vol20 > its 252-session median. **bull_calm:** otherwise. | PB, CV | Moderate | BUILD NOW (exists) |
| REG-3 | Permission multipliers (A/B/C/D): bull_calm 1/1/1/1; bull_volatile 1/.5/.5/.5; bear 1/0/0/1; panic 1/0/0/.5; choppy 1/.5/0/1. **New:** also binding on the Claude book (CL-11). | MW, MK, PB | Moderate | BUILD NOW |
| REG-4 | **Temperature T** (display only) = mean of five percentiles, each against its own last 1,260 sessions: (1) SPY 504-session return; (2) 1 − percentile of SPY vol20; (3) share of the 40-stock C universe above its SMA200; (4) close/SMA200 − 1 for SPY; (5) 126-session change in HYG/IEF. **hot** if T ≥ 0.80, **cold** if T ≤ 0.20. Also show the share of the C universe above its SMA50, to reveal breadth divergence. | MK, GR | Weak (as timing) | BUILD NOW (display) |
| REG-5 | Hot cap: if T ≥ 0.80, B and C weights are capped at their `default` in both books. | MK | Weak | TEST FIRST |
| REG-6 | Credit canary: if 13612W(HYG) − 13612W(IEF) < 0 on month-end closes, downgrade bull_calm to bull_volatile. | MK | Moderate / Weak | TEST FIRST |
| REG-7 | Stock–bond monitor: show the 60-session correlation of SPY and IEF daily returns; if > +0.30, flag "bonds not hedging". No trade effect. | MC | Moderate | BUILD NOW (display) |
| REG-8 | DAA canary (VWO and BND 13612W both > 0) stays computed and displayed only. | PB | Weak | BUILD NOW (exists) |
| REG-9 | CAPE, HY OAS, equity risk premium, FMS cash, AAII, VIX: display once a feed exists, and never let them drive weights. | MK, GR, MA, MC | Weak | LATER |

**Current reading, from snippet data.** SPY is about 7.5% above its SMA200 and has not crossed it since 8 April, so the regime is bull_calm or bull_volatile. T would very likely read *hot*, even though only 31% of stocks are above their 50-day average. The rules let the trend keep the book invested and let the heat show up only as limits on Claude's freedom.

## (b) Sleeves

### A. Trend core (50–60%)

This sleeve has the best evidence, and that evidence is about cutting drawdowns: out of sample, Faber's rule returned about 6% a year with a max drawdown of about 12%. Claude cannot veto it in the rules book (CL-7).

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| A-1 | Universe: SPY, EFA, IEF, DBC, VNQ; cash in BIL. | PB | Strong | BUILD NOW (exists) |
| A-2 | Hold asset *i* iff its last *completed* month-end close > the mean of its last 10 month-end closes. | PB, CV, ST | Strong | BUILD NOW (exists) |
| A-3 | Weight = 1/5 of the sleeve × `min(1, 0.10/vol60_i)`, where vol60 is from daily log returns up to that month-end. The remainder goes to BIL. | PB | Moderate | BUILD NOW (exists) |
| A-4 | Trade only if \|target − current\| / max ≥ 0.20. | MA, GR | Strong (costs) | BUILD NOW (exists) |
| A-5 | No stops, not measured in R, excluded from heat. Judged under M-4. | TH | Design choice | BUILD NOW (exists) |
| A-6 | GEM stays **off**. The shadow GEM uses AGG only if AGG's 12-month return > BIL's (otherwise BIL), and holds its US leg in **VOO** so SPY's 30% cap cannot silently clip it. | AN, ST, MC | Moderate / Weak | TEST FIRST |
| A-7 | Second vote: `w_i = 1/5 × scale_i × (0.5·[close > SMA10m] + 0.5·[r12_i > r12_BIL])`. | AN (Zakamulin), ST | Moderate | TEST FIRST |
| A-8 | Vol-target the whole sleeve at 10% rather than each ETF (less cash drag). | MA | Weak | TEST FIRST |
| A-9 | Add GLD as a sixth asset under the A-2 and A-3 rules. | CV, MC | Weak | TEST FIRST |

### B. RSI(2) dips (15–25%, capped at 20% until validated)

B is the only daily edge and the most challenged: Hite and O'Neil distrust oscillators, its evidence comes from practitioners only, and it is reportedly weaker in 2025.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| B-1 | Universe: SPY, QQQ, IWM, DIA; at most 2 positions. | CO, PB | Moderate | BUILD NOW (exists) |
| B-2 | Entry on the close: `close > SMA200(sym)` and `RSI2 < 10`, with regime permission > 0. Rank by RSI2, lowest first. | CO, ST | Moderate / Weak | BUILD NOW (exists) |
| B-3 | `qty = min(perm × 0.005 × breaker_mult × E / (3·ATR20), (w_B·E/2) / close)`. | TH, CO | Moderate | BUILD NOW (exists) |
| B-4 | Exit on the first of: (a) close > SMA5; (b) 10 sessions held; (c) close ≤ stop = entry − 3·ATR20, never trailed or tightened. **New:** (b) and (c) are enforced in `risk.py` for both books. | CO, TH | Moderate | BUILD NOW |
| B-5 | Index-cluster heat: Σ (price − stop)·qty over B positions ≤ 0.75% of *E*. The four ETFs are 0.85–0.95 correlated in selloffs, which are the days B buys. | MK, MW | Moderate | BUILD NOW |
| B-6 | Log `gap_R = (fill − signal_close) / (entry − stop)` for every B fill. This measures the cost of next-open fills against Connors's on-close fills. | CO, LF | Design choice | BUILD NOW |
| B-7 | A 15:45 ET run using the IEX last trade as a proxy close, sending market-on-close orders (`time_in_force=cls`) for B only. | CO | Moderate / Weak | TEST FIRST |
| B-8 | Variants, shadowed one at a time: exit when RSI2 > 70; time stop off or 15 sessions; full size when RSI2 < 5 and half size for 5–10. | CO | Weak | TEST FIRST |
| B-9 | No bull_volatile halving while SPY > SMA200, tested against a vol20 < 25% gate. | CO vs ST | Conflicting | TEST FIRST |
| B-10 | One extra trigger sharing B's slots: 2-day cumulative RSI2 < 35 **or** Double 7s, never both. | CO, PB | Weak | TEST FIRST |

### C. Breakouts (10–20%, on probation, capped at 15%)

Malkiel's critique lands hardest here. The universe is today's 40 megacaps (survivorship bias), the sleeve has about 10 parameters, it has no fundamentals, and it sits in 2026's crowded trade. Notional per name is w_C/5 ≈ 3% of *E*, so each trade risks ≤0.24% of equity, deliberately below 1R.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| C-1 | Universe: the 40 names in `playbook.yaml`, each with ≥260 bars. Documented as a survivorship-biased large-cap variant. | MA | Design choice | BUILD NOW (exists) |
| C-2 | Template, all required: close > SMA150 and SMA200; SMA150 > SMA200; SMA200 > its value 21 sessions earlier; SMA50 > SMA150 and SMA200; close > SMA50; close ≥ 1.25 × the 252-session low; close ≥ 0.75 × the 252-session high; RS ≥ 70. | MV, MW | Moderate | BUILD NOW (exists) |
| C-3 | RS = percentile of 252-session return **within the 40 names**, labelled "peer RS" for Claude. | MV | Weak | BUILD NOW (exists) |
| C-4 | Trigger: close > the maximum high of the prior 50 sessions, and today's volume ≥ 1.5 × mean volume of the prior 50. IEX volume is partial, so this is noisy (EX-10). | MW, LF, TH | Moderate | BUILD NOW (exists) |
| C-5 | Regime permission (off in bear, panic, choppy; half in bull_volatile). Rank by RS; at most 5 positions. | MW, MV, PB | Moderate | BUILD NOW (exists) |
| C-6 | Stop = max(close − 2·ATR20, 0.92·close). `qty = min(perm × 0.005 × mult × E / (close − stop), (w_C·E/5) / close)`. | MW, TH | Moderate | BUILD NOW (exists) |
| C-7 | **Trailing stop, enforced in `risk.py` for both books:** each run, before the stop check, `stop = max(stop, min(low of the prior 10 sessions))`. | TH, CODE | Strong (design) | BUILD NOW |
| C-8 | Close < SMA50 → exit. Mandatory in the rules book, advisory in the Claude book. | MV | Moderate | BUILD NOW (exists) |
| C-9 | At most 2 open C positions per group. **Semis/AI** NVDA, AVGO, AMD, AMAT, ANET. **Software** MSFT, ORCL, CRM, ADBE, NOW, INTU, PANW. **Platforms** GOOGL, META, AMZN, NFLX, UBER, BKNG. **Hardware/auto** AAPL, TSLA. **Health** LLY, UNH, MRK, ABBV, TMO, ISRG. **Financials** JPM, V, MA, BAC. **Staples/retail** COST, HD, PG, PEP, KO, WMT. **Industrial/energy** XOM, CAT, GE, LIN. | PP, MW | Moderate | BUILD NOW |
| C-10 | Failed breakout: within the first 10 sessions, close < pivot → exit. | MW, LF | Weak | TEST FIRST |
| C-11 | Extension: skip the entry if close > 1.05 × pivot. | MW | Weak | TEST FIRST |
| C-12 | Stricter template: close ≥ 1.30 × the 52-week low, and SMA200 rising over 84 sessions. | MV | Weak | TEST FIRST |
| C-13 | Market-relative RS: close/SPY within 5% of its 252-session high, or 0.4·r63 + 0.2·r126 + 0.2·r189 + 0.2·r252. | MV | Moderate | TEST FIRST |
| C-14 | VCP proxy: 15-session range/close ≤ 0.12, ATR10/ATR50 < 0.8, and 10-session mean volume < 50-session mean volume. | MV | Weak | TEST FIRST |
| C-15 | Once close ≥ entry + 2R, raise the stop to at least entry. | MV, DG | Weak | TEST FIRST |
| C-16 | Exit if +1R has not been reached after 20 sessions. | MW, TH | Weak | TEST FIRST |
| C-17 | After 5 consecutive losing C lots, halve C risk until the next winner. | MV, MW vs DG, TH | Conflicting | TEST FIRST |
| C-18 | No new entry if earnings fall within the next 5 sessions. | MW, PB | Moderate | LATER (calendar) |
| C-19 | Quality filter from SEC EDGAR: EPS > 0 in each of the last 5 years; long-term debt < 50% of capital. | GR | Moderate | LATER |
| C-20 | Point-in-time S&P 500 membership as the universe. | MA | Strong | LATER |

### D. Crypto trend (off; if enabled, ≤5%)

BTC fell about 50% from October 2025 while stocks set records. Two correlated coins diversify little.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| D-1 | `enabled: false`. Only the owner can enable it, and only after the phase 1 fixes are live. | MA, MC | Design choice | BUILD NOW |
| D-2 | Band: min 0, default 0.03, max **0.05**. | MA, MC | Moderate | BUILD NOW |
| D-3 | `score = mean over n ∈ {20,30,50,80,120,180,250} of [close > (max high_n + min low_n)/2]`. Weight per coin = `score × min(1, 0.25/vol30) × perm_D / 2`, inside the 20% band. | CV, PB | Moderate | BUILD NOW (exists) |
| D-4 | Stop = entry − 3·ATR20, never widened. Exit on the stop or when score = 0. | TH, CV | Moderate | BUILD NOW (exists) |
| D-5 | Go to zero only on a close below the N-day low, not the midpoint; trail the stop at `max(stop, close − 3·ATR20)`. | CV, TH | Weak | TEST FIRST |

## (c) Portfolio risk limits and circuit breakers

Every rule is the current policy or **tighter**. None raises risk.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| RISK-1 | Long only: no leverage, shorts or options; allowlist only. | all, PB | Strong | BUILD NOW (exists) |
| RISK-2 | 1R = 0.5% of *E*; hard cap 2%. Moving to 1% needs M-10, per sleeve. | MW, TH | Strong | BUILD NOW (exists) |
| RISK-3 | B, C and D need a stop below price. Stops never widen. No increase while price < average entry. | MW, LF, DG, TH | Strong | BUILD NOW (exists) |
| RISK-4 | Close ≤ stop exits at the next open, in both books. The stop is ratcheted first (C-7). | TH, DG | Strong | BUILD NOW (exists) |
| RISK-5 | Per-symbol caps summed across sleeves: ETF 30%, stock 10%, crypto 10%. Cash ≥ 5%. Heat ≤ 6%. At most 2 held stocks with ρ60 > 0.7 against a new stock. | PB, MW | Moderate | BUILD NOW (exists) |
| RISK-6 | **Equity-like cap:** notional of SPY, VOO, EFA, VEU, VNQ, QQQ, IWM, DIA and all single stocks ≤ 75% of *E*. Breaching increases are clipped. | GR | Moderate | BUILD NOW |
| RISK-7 | **Speculative cap:** w_C + w_D ≤ 0.20. | GR (Zweig) | Moderate | BUILD NOW |
| RISK-8 | **Probation cap:** a sleeve that has not passed M-10 has weight ≤ its `default` (B 0.20, C 0.15, D 0.03), in both books. | TH, MA, LF | Moderate | BUILD NOW |
| RISK-9 | Drawdown from the high-water mark: 10% halves risk; 15% blocks new entries; 20% halts (exits only) until a human resets. | MW, PB | Strong / Design | BUILD NOW (exists) |
| RISK-10 | **Watch tier at 5% drawdown:** flag it; the Claude book may not raise B, C or D weights. | PP | Moderate | BUILD NOW |
| RISK-11 | Daily loss ≤ −1% of *E* → no new entries today; weekly ≤ −2.5% → none this week. These are the existing −2R/−5R limits, relabelled in % of *E* for Claude. | MW, TH | Moderate | BUILD NOW (exists, relabel) |
| RISK-12 | **Monthly cap:** if month-to-date P&L ≤ −4% of prior-month-end equity, no new B, C or D entries for the rest of the month. A is exempt. | MW (Jones) | Moderate | BUILD NOW |
| RISK-13 | **Sleeve tiers (B, C, D):** if a sleeve's cumulative P&L falls from its peak by ≥ 3% of *E*, its new entries run at half risk. At ≥ 5%, its new entries stop until the owner reviews. | PP, MW | Moderate | BUILD NOW |
| RISK-14 | Stress line (display only): −20% × equity-like, −10% × DBC, −30% × crypto, as % of *E*, shown next to heat. | TH, MC | Design choice | BUILD NOW (display) |
| RISK-15 | Kill switch; a human re-enables after a halt. | PB | Design choice | BUILD NOW (exists) |

## (d) Execution and costs

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| EX-1 | Run at 21:35 UTC on weekdays. Signals on the close. Stock and ETF orders are DAY market orders that fill at the next open; crypto orders are GTC. | PB | Design choice | BUILD NOW (exists) |
| EX-2 | Exits are always market orders. | LF | Moderate | BUILD NOW (exists) |
| EX-3 | Sells first. At most 10 orders a day, $25 minimum. **New:** buys that must be dropped are dropped in reverse priority, so the order kept is A → B → C → D, then by notional, largest first. | MA, TH | Moderate | BUILD NOW |
| EX-4 | **Real fills:** each run reads the previous orders' `filled_avg_price` and `filled_qty` into the lots and logs `slippage_bps = (fill/signal_close − 1)·10⁴`, signed so that positive means worse for us. | CODE, TH | Design choice | BUILD NOW |
| EX-5 | Costs of 5 / 10 / 25 bps per side (ETF / stock / crypto) go into R_net. If the median measured slippage over ≥30 fills in a class is more than twice the model, raise the model to that median. | MA, TH | Strong | BUILD NOW |
| EX-6 | B and C entries as DAY limit orders at close + 0.5·ATR20. Shadow: record whether the order would have filled. | TH vs MW (Kovner) | Conflicting | TEST FIRST |
| EX-7 | Block entries in a symbol whose last bar is stale by more than 5 days, has a close ≤ 0, has zero volume, or moved more than 25% in one day with no known corporate action. | TH | Moderate | BUILD NOW |
| EX-8 | Tax lots, wash sales, after-tax returns. | MA | Strong (live) | LATER |
| EX-9 | A second price source, so disagreements between sources can be caught. | PB | Moderate | LATER |
| EX-10 | Consolidated (SIP) volume for C-4. | CODE | Moderate | LATER |

## (e) What Claude may and may not do

Across the books, discretion is where traders lose money: Seykota's management overrides, Livermore's tips, the LLM trading contests, and the retail base rates. In 2026, professionals keep LLMs inside rules-based processes. So Claude's freedom is bounded, and **every deviation is recorded as a scored bet**.

**Both books**

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| CL-1 | Claude cannot change config, policy or parameters. Output must pass a strict JSON schema. Invalid output → hold, with stops still enforced. | PB, DG | Strong | BUILD NOW (exists) |
| CL-2 | **Evidence discipline:** each reason carries `evidence: [context paths]`, for example `rule_signals.C.indicators[NVDA].volume_ratio`. Code drops any action or skip whose paths are empty or missing from today's context. News and remembered narratives are not evidence. | LF, DG, MK, PP | Moderate | BUILD NOW |
| CL-3 | Stamp `prompt_version` (hash of the role text, brief and schema), `model`, `effort` and `context_schema` on every decision and lot. Change them only at evaluation boundaries; each version is its own sample. | DG, PP | Design choice | BUILD NOW |
| CL-4 | Daily fields: `journal_note` (≤5 sentences), `temperature_ack`, `likely_error ∈ {commission, omission, none}` with one sentence, and `flags[]`. | MK, LF | Design choice | BUILD NOW |
| CL-5 | **Predictions:** 0–3 a day, each `{id, symbol ∈ allowlist, horizon ∈ {5,20,60} sessions, direction ∈ {above, below}, threshold_pct, probability ∈ [0.05, 0.95], linked_decision}`. Resolved from closes and scored under M-7. Required for every deviation (CL-13) and every skip. | LF, MK, ST | Moderate | BUILD NOW |
| CL-6 | Prompt changes: think in samples (Douglas); include the expected losing-streak table (M-2); "doing nothing is usually right"; "in bear or panic the rules already defend, so add no discretionary selling at lows". Replace the blended `win_rate`/`avg_R` with per-sleeve statistics. | DG, TH, MK, MA | Moderate | BUILD NOW |

**Rules book: skip or halve only**

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| CL-7 | `skip_entries` and `halve_sleeves` apply only to new increases in **B, C and D**. Claude never touches sleeve A, exits or stops. *(Today it can skip A rebalances.)* | MW (Hite, Seykota), CODE | Moderate | BUILD NOW |
| CL-8 | Each skip or halve needs a `reason_code` from this list. **EARNINGS_IN_WINDOW:** C only, with a stated date and `verified=false` until C-18 exists. **DATA_SUSPECT:** must cite `data_problems` or a price field. **SCHEDULED_EVENT:** FOMC, CPI or payrolls on the next session; B and C only. **HALT_OR_ILLIQUID.** **CORPORATE_ACTION.** Mood, macro and recent losses are not codes. | DG | Moderate | BUILD NOW |
| CL-9 | **Shadow trades:** each vetoed entry opens a shadow lot at the next open, with the rule's stop and size, and is closed by the sleeve's exits. `veto_value = −Σ(shadow R_net × fraction vetoed)`. After ≥30 scored vetoes with Σ < 0, the allowed codes shrink to DATA_SUSPECT and HALT_OR_ILLIQUID until the owner resets them. | DG, MW | Moderate | BUILD NOW |

**Claude book: decides, inside hard limits**

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| CL-10 | Claude sets sleeve weights inside [min, max], after RISK-7 and RISK-8, and sets target positions. Every limit in `risk.py` applies. | PB | Design choice | BUILD NOW (exists) |
| CL-11 | **Eligibility.** B increases only in B symbols with close > SMA200 and perm_B > 0. New C positions only in names passing C-2 today, with perm_C > 0. D only when enabled. A only in A assets and BIL. Per-trade risk × regime permission. | MW, PP, LF | Moderate | BUILD NOW |
| CL-12 | **Weight rate limit:** ±0.05 per sleeve per change, at most once per 5 sessions. Increases in B, C or D need `reason_code ∈ {SIGNAL_COUNT_CHANGE, REGIME_CHANGE, VOLATILITY_CHANGE, RETURN_TO_DEFAULT}`. There is no performance code. | MK, DG | Moderate | BUILD NOW |
| CL-13 | **Deviation record:** whenever Claude's target differs from the rule target by more than 20% (of the larger) or in direction, Claude must emit `{symbol, sleeve, rule_pct, claude_pct, reason_code, evidence, prediction_id}`. Otherwise the action is dropped. | DG, LF, MW | Moderate | BUILD NOW |
| CL-14 | **Stop floor:** Claude's stops are raised to at least the rule stop: B and D at price − 3·ATR20; C at max(price − 2·ATR20, 0.92·price). A tighter stop is allowed, a wider one is not. | TH, CODE | Moderate | BUILD NOW |
| CL-15 | Run `decide` twice and act only where both runs agree; otherwise do nothing and log the disagreement. | DG | Weak | TEST FIRST |

## (f) Measurement

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| M-1 | Daily benchmarks on the same capital and dates: (1) SPY buy-and-hold; (2) 60/40 SPY/IEF rebalanced monthly; (3) GTAA-5 at 20% each, rebalanced annually. For each: return, volatility, Sharpe and max drawdown. | GR, MA, PB | Strong | BUILD NOW |
| M-2 | Per sleeve (B, C, D), net of costs: n, win rate, average win and loss in R, E = mean(R_net), sd, `SQN = √min(n,100)·E/sd` (shown from n ≥ 30, labelled "t-stat of mean R"), max losing streak, best and worst R, share of R from the top 5% of lots, MAE and MFE in R, median hold. Brief: at a 35–45% win rate, the longest streak in 100 trades is typically 7–9, and 11–15 in the worst 5% of cases. | TH, DG, MW | Strong / Design | BUILD NOW |
| M-3 | **R bookkeeping:** a trade is one lot's life from first fill to zero. `initial_risk_$ = Σ over buys of qty_add × (fill_add − stop_at_add)`; `R_net = (realized P&L − costs) / initial_risk_$`. Partial sells add realized P&L to the lot and do not create a new trade. | TH, CODE | Design choice | BUILD NOW |
| M-4 | Sleeve A: return, max drawdown, time in BIL, and the share of SPY's 20 best and 20 worst days each year spent in cash, compared with benchmark (3). | MA, ST | Moderate | BUILD NOW |
| M-5 | Claude-book attribution: per deviation, `value_20d = (claude_pct − rule_pct) × (close_{t+20}/fill_t − 1)` in % of *E*. Report the sum, hit rate and n, plus the monthly Claude-minus-rules return by sleeve. | DG, MK | Moderate | BUILD NOW |
| M-6 | Override report: n vetoes and Σ veto_value, by reason code. | DG | Moderate | BUILD NOW |
| M-7 | Prediction scoring: Brier score, and skill = 1 − Brier/Brier_ref, where Brier_ref uses the event's frequency for that symbol and horizon over the last 1,260 sessions. Calibration in 10% bins. Reported once 50 predictions have resolved. | MK, LF | Moderate | BUILD NOW |
| M-8 | Monthly up- and down-capture against SPY, and the share of rolling 6- and 12-month windows with a positive return. | MK, MW (Hite) | Moderate | BUILD NOW |
| M-9 | API cost per call, in tokens and dollars. Report each book's return net of its API cost, and that cost as an annual % of *E*. Malkiel's ceiling of 0.50% a year is $50 on $10k. | MA | Strong | BUILD NOW |
| M-10 | **Promotion gate** (a sleeve goes to 1% R, and C leaves probation), all required: ≥100 closed paper lots after the phase 1 fixes; E_net > 0; SQN ≥ 2.0; live E ≥ 0.5 × backtest E where a backtest exists; no halt in the last 63 sessions. Then the owner edits `risk_pct_by_sleeve` by hand; code only reports that the gate has passed. | TH, PB, DG | Strong | BUILD NOW (report) |
| M-11 | **Demotion:** if n ≥ 30 and the one-sided 90% bootstrap upper bound of mean R_net < 0, the sleeve goes to its min weight at half risk. If n ≥ 50 and SQN ≤ −1.0, its new entries stop pending review. | TH, MA | Moderate | BUILD NOW |
| M-12 | **TEST FIRST → BUILD**, all required: (i) a backtest over at least 2016–2026 (2005 onwards if a longer daily source is added), with next-open fills and EX-5 costs; (ii) higher net expectancy, or max drawdown down ≥20% with CAGR down ≤10%; (iii) the sign holds when each parameter moves ±25%; (iv) the gain still matters when halved; (v) ≥30 live shadow signals agree in sign; (vi) owner sign-off. At most one promotion per sleeve per quarter. | TH, MW (Dennis), PB, ST (Davey) | Strong | BUILD NOW (process) |
| M-13 | Every parameter set and prompt version ever tried is appended to `state/experiments.jsonl`, with a date and reason. | PB, ST | Strong | BUILD NOW |
| M-14 | Sleeve kill when live results fall below the 5th percentile of bootstrapped backtest paths. | PB | Moderate | LATER (backtester) |

## (g) Going-live gate

Graham and Zweig say to trade on paper for about a year and then compare with an index fund. Davey incubates for 6–12 months. Douglas allows discretion only after a clean mechanical sample. The gate combines all three and is **pre-registered**: changing it restarts the clock.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| G-1 | At least 252 paper sessions **after** the phase 1 fixes are live. Any bug that corrupts P&L records restarts the count. | GR, ST | Moderate | BUILD NOW (report) |
| G-2 | Net of trading and API costs, the book beats 60/40 (M-1 benchmark 2) on Sharpe, **and** its max drawdown is ≤ 0.7 × SPY's. Beating SPY's return is not required. | GR, MA, PB | Moderate | BUILD NOW (report) |
| G-3 | Live, sleeve A runs, plus any sleeve that passed M-10. B runs at its min weight until it passes. C and D run at 0 until they pass. | TH, MA | Moderate | BUILD NOW (policy) |
| G-4 | The Claude book goes live only if a paired block bootstrap of daily return differences against the rules book over ≥252 sessions gives one-sided p < 0.10, **and** Σ value_20d (M-5) exceeds its API cost. Otherwise the rules book is the live candidate, and it keeps its Claude review only if Σ veto_value exceeds the review's API cost. | MK, PP, ST | Moderate | BUILD NOW (report) |
| G-5 | No unexplained reconciliation difference > 1% in the last 60 sessions; the kill switch and halt reset have been rehearsed; no data-sanity blocks left unresolved. | TH | Design choice | BUILD NOW |
| G-6 | A tax-advantaged account, or EX-8 built. | MA | Strong | LATER |
| G-7 | Live capital ≤ 10% of the owner's investable assets, at the same 0.5% R, with no increase for 6 months. If median live slippage over 30 fills is more than twice the model, go back to paper. | GR (Zweig), LF | Moderate | BUILD NOW (policy) |

## Conflicts resolved

1. **Malkiel and Graham versus trend following.**
   - *The conflict:* both say price history cannot beat buy-and-hold after costs. Their evidence is old single-stock filter-rule tests. Neither tests diversified asset-class trend, which has a long, cost-adjusted record of *cutting drawdowns*.
   - *Decision:* keep trend as the core, but judge it as a drawdown tool against 60/40 and a passive mix (M-1, G-2). Take Malkiel's cost and survivorship warnings: C is capped and flagged (RISK-7, RISK-8, C-20).
2. **Connors "stops hurt" versus a disaster stop.**
   - *The conflict:* Connors tested 1995–2007. Record margin debt and leveraged-ETF assets in 2026 make gaps likelier.
   - *Decision:* keep the 3·ATR stop, wide and never tightened. It is catastrophe insurance, and it rarely sets size because B is notional-capped. Other stop widths go to the backtest only.
3. **Marks's panic buying versus no averaging down.**
   - *The conflict:* Marks buys fear because he has a value anchor and permanent capital. The bot has neither, and momentum crashes cluster in panic rebounds.
   - *Decision:* B and C stay off in bear and panic regimes, with no averaging down. From Marks we take the other half: no discretionary selling at lows (CL-6).
4. **Pod-shop limits versus the current breakers.**
   - *The conflict:* pods halve at −5% and close at −7.5%, but a pod can be replaced. A trend core must sit through 10–12% drawdowns, and tight book-level stops would lock in A's losses at the lows.
   - *Decision:* keep the book breakers at 10/15/20%. Add the pod *structure* where it fits: a −5% watch tier, a monthly cap, and sleeve-level tiers (RISK-10, RISK-12, RISK-13).
5. **Next-open versus on-close fills for RSI(2).**
   - *The conflict:* Connors's edge includes the overnight move.
   - *Decision:* keep next-open fills and measure the cost (B-6). Market-on-close execution is TEST FIRST (B-7), because it needs a second scheduled run and an IEX proxy close. B's backtest must use next-open fills.
6. **2026: stocks and bonds falling together, 10-year yield near 5%.**
   - *Decision:* no change to A. IEF is held only above its own 10-month SMA, and cash is BIL, which yields about 4%. GEM's unconditional AGG leg was exactly the 2022 failure, so GEM stays off and its shadow gets a trend filter (A-6). No TLT.
7. **Crowding in semis.**
   - *The conflict:* momentum leads 2026, but its volatility is near a six-year high, positioning is the most crowded trade in the survey, and it unwound in January and reportedly in July–August.
   - *Decision:* add a sector cap (C-9) and the speculative and probation caps (RISK-7, RISK-8). Heat is shown but does not cut exposure while the trend is up, because the 2026 "sell" signals failed.
8. **Douglas's "take every signal" versus veto rights and streak cuts.**
   - *Decision:* vetoes are allowed but shadow-scored, and revoked if they lose (CL-9). Streak cuts are TEST FIRST (C-17).
9. **How many trades is enough: 20 (Douglas), 100 (Tharp), or 100–225 (statistics)?**
   - *Decision:* promotion needs 100 trades plus SQN ≥ 2 (M-10). Demotion can come sooner (M-11), because cutting risk needs less proof than adding it.
10. **Volatility targeting is procyclical** (PP), but its evidence is strong (Moreira–Muir).
    - *Decision:* keep it. The bot is too small to contribute to a selling cascade.
11. **Hot valuation versus a risk-on trend.**
    - *Decision:* the trend decides exposure. Heat only narrows Claude's freedom (RISK-10, CL-12, REG-5).
12. **Crypto:** Dalio and Druckenmiller hold some; Malkiel compares bitcoin promoters to John Law.
    - *Decision:* D stays off. If enabled, it is capped at 5% and counted in the 20% speculative cap.

## Rejected

- **Scaling out:** it cuts the right tail that pays for trend and breakout trades, and Tharp calls it reverse position sizing.
- **Pyramiding (Livermore, Turtles):** too many added parameters while C is on probation. Revisit after C passes M-10.
- **Conviction sizing:** it caused most of the blow-ups in the books and in the LLM contests.
- **Covel's 5% risk per trade:** ten times our 1R.
- **Graham's 25% equity floor:** A is built to leave equities in long bear markets. Only the 75% ceiling is kept.
- **Valuation-timed exposure (CAPE, FMS cash rule):** weak 1-year evidence, and the 2026 signal failed.
- **Graham screens and net-nets:** they need fundamentals and micro-caps.
- **Shorting, options, pairs and covered calls:** excluded by policy, and the edges have decayed.
- **Climax exits:** futures-specific, and they cut winners.
- **Weekday, Friday-close and end-of-month rules:** data-mined.
- **Claude recalling fundamentals or earnings dates from memory:** unverifiable. Wait for real data (C-18, C-19).
- **"Zone" or intuition prompts:** unfalsifiable.
- **Multi-week trading pauses after losses:** the breakers already cover this with defined thresholds.
- **A passive "sleeve 0":** benchmark (2) already provides the passive comparison.
- **Dollar-cost averaging:** the account is fully funded with no new deposits.

## Implementation plan (BUILD NOW rules)

**Phase 1: bookkeeping bugs** (everything downstream depends on these).

1. **`update_lots` keeps the original stop when a lot is added to, so R is wrong** (`engine.py`). When quantity rises, `entry_price` is blended, `initial_stop` stays, and `lot.stop` is overwritten.
   - Fix: add `lot_id`, `initial_risk_dollars`, `realized_pnl`, `costs` and `events[]` to `Lot` (`models.py`).
   - On each add: `initial_risk_dollars += add_qty × (fill − stop_at_add)`.
   - Compute R as in M-3.
2. **Partial reductions never create a closed-trade record.** A sale that leaves qty > 0 just lowers the quantity, and its P&L disappears. D's rebalance band, Claude trims and `reconcile()` scaling all do this.
   - Fix: `realized_pnl += sold_qty × (fill − avg_entry) − costs`, logged as an event.
   - Write the closed-trade record at zero quantity with the lot's total P&L.
   - `reconcile()` writes the same event, with reason `reconcile`.
3. **The sleeve C trailing stop is not enforced in `risk.py`.** The 10-day-low exit exists only in `strategies.sleeve_c`, so the Claude book can hold through it, and heat uses the stale initial stop.
   - Fix: add `RiskEngine._ratchet_stops()` before step 1 of `apply()`. For C lots: `stop = max(stop, low.iloc[-11:-1].min())`. For B lots: the 10-session time stop.
   - Persist the ratcheted stop through the targets (C-7, B-4).
4. **Lots record the signal-day close, not the fill** (`update_lots(..., prices, ...)`).
   - Fix: add `broker.fills_since()`. On Alpaca, use `get_orders(status=closed)` → `filled_avg_price`, `filled_qty`. In the simulator, fill at the next bar's open.
   - Keep pending orders in state and settle the lots at the start of the next run (EX-4).
5. **`apply_review` can skip sleeve A increases.** Restrict it to B, C and D (CL-7).

**Phase 2: risk** (`risk.py`, `risk_policy.yaml`).
- Add these policy keys:
  - `portfolio.max_equity_like: 0.75` and `equity_like_symbols`
  - `portfolio.max_speculative_weight: 0.20`
  - `portfolio.cluster_heat.B_index: {symbols, max: 0.0075}`
  - `breakers.watch_drawdown: 0.05`
  - `breakers.monthly_loss_pct: 0.04`
  - `breakers.sleeve_dd_halve: 0.03` and `breakers.sleeve_dd_off: 0.05`
  - `per_trade.risk_pct_by_sleeve`, set to 0.005 for each sleeve
- Enforce them in `apply` and `_clip_portfolio`.
- `breaker_status`: add the watch, monthly and sleeve tiers. The sleeve tiers need a new `state.sleeve_pnl` (cumulative P&L and peak per sleeve, updated daily). Relabel the daily and weekly limits in % of *E*.
- Add the Claude stop floor (CL-14) and the buy-drop priority in `_orders` (EX-3).
- `engine.normalize_weights`: apply the RISK-7 and RISK-8 caps, reading `state.promoted_sleeves`.
- `data.validate`: add the EX-7 checks.

**Phase 3: strategies and config.**
- `sleeve_c`: sector cap from a new `sectors:` map in `playbook.yaml`.
- `playbook.yaml`: D band 0 / 0.03 / 0.05; add HYG to the fetched symbols.
- Each TEST FIRST rule gets a `shadow_*` function that writes flags to `plan.candidates` and the journal, and never touches targets.

**Phase 4: regime.**
- Add `temperature` and `stock_bond_corr` to `Regime`. This means fetching about 1,800 sessions of SPY, HYG and IEF.
- Make the permissions binding in `decision_to_targets` (CL-11).

**Phase 5: Claude** (`llm.py`, `engine.py`).
- Schema fields:
  - Skips gain `reason_code`, `evidence` and `prediction_id`.
  - Both roles gain `temperature_ack`, `likely_error` and `predictions`.
  - Decide gains `deviations[]` and `weight_change_reasons`.
- Prompt additions (CL-6), plus a `prompt_version` hash (CL-3).
- `decision_to_targets`: eligibility, rate limit, deviation checks and evidence-path checks (CL-11 to CL-13, CL-2).
- `build_context`: per-sleeve statistics, temperature, the stress line, and breakers in %.

**Phase 6: measurement.**
- New `trader/shadow.py`: veto lots, and resolving predictions and deviations.
- New `trader/metrics.py`: M-1 to M-11, including SQN, the bootstrap, capture ratios and the Brier score.
- `state.py`: add `shadow_lots`, `predictions`, `deviations`, `sleeve_pnl`, `promoted_sleeves` and `api_cost`.
- `__main__.py report`: benchmarks, the per-sleeve table, and gate status.
- `state/experiments.jsonl` (M-13).

**Phase 7: backtester.** Add `trader/backtest.py`, which replays `build_plans`, then `RiskEngine`, then next-open fills with costs, over 2016–2026. This is required before any TEST FIRST promotion (M-12).

**Tests to add:**
- add, then partial sell, then close gives one trade with the correct R;
- the C ratchet is enforced in the Claude book;
- the B time stop is enforced in the Claude book;
- an A skip is rejected in the rules book;
- the equity-like, speculative, cluster and monthly caps each clip correctly;
- a Claude stop below the floor is raised;
- a deviation without a record is dropped;
- a prediction resolves and is scored;
- a shadow veto lot closes under the sleeve's rules.

## Rule count

| Status | Rules |
|---|---|
| BUILD NOW, already in code | 32 |
| BUILD NOW, new or changed | 52 |
| TEST FIRST | 21 |
| LATER | 9 |
| **Total** | **114** |
