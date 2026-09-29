# Van K. Tharp, *Trade Your Way to Financial Freedom*: study notes

Source read: the whole of the supplied text (title page and contents through the index, about 14,300 lines). This is the **first edition (McGraw-Hill, 1998)**, 13 chapters. The file does **not** contain the System Quality Number (SQN). SQN arrived in Tharp's later work (the 2007 second edition and his position-sizing books). Section 3 gives it from those later works and marks it as not from this text.

Chapter map used below: Ch1 Holy Grail, Ch2 judgmental biases, Ch3 objectives (Tom Basso interview), Ch4 twelve steps to build a system, Ch5 concepts (trend following, fundamentals, seasonals, spreads, arbitrage, neural nets, "order in the universe"), Ch6 expectancy and R-multiples, Ch7 setups, Ch8 entry, Ch9 protective stops, Ch10 profit exits, Ch11 opportunity and costs, Ch12 position sizing, Ch13 conclusion (Q&A on data, testing, discipline).

---

## 1. What the book is about

Tharp is a trading psychologist and coach. He argues that most traders obsess over entry signals ("being right") and neglect what actually drives results: exits, the cost and frequency of trades, and above all **position sizing**. The book gives a checklist for designing a personal trading system: objectives, concept, setup, entry, protective stop, profit exit, costs, opportunity and sizing. It also supplies the vocabulary that later became standard in retail systematic trading: R (initial risk), R-multiples and expectancy per dollar risked. The first and last parts insist that the trader's beliefs and self-discipline are the real "Holy Grail". The middle is a survey of techniques with his opinions attached, and it reviews well-known systems (O'Neil CANSLIM, Buffett, the Motley Fool "Foolish Four", Kaufman's adaptive average, Gallacher, Ken Roberts) component by component.

## 2. Key lessons (own words, with chapter)

1. **A system is more than an entry.** A complete system has setup, entry trigger, a worst-case exit decided *before* entry, profit exits and a sizing rule. Most published "systems" are only setups (Ch2, Ch7, Appendix II).
2. **The "cut losses, let profits run" rule is entirely about exits.** Entry is where people feel in control, but once a trade is on, the only thing you control is how you get out (Ch1 preface, Ch2 lotto bias, Ch9).
3. **Measure every trade in R.** R is the initial risk per unit (entry minus initial stop). A trade's result divided by R is its R-multiple. This makes trades in different instruments and prices comparable (Ch6, Ch9).
4. **Win rate is not the goal.** A 90%-accurate method can lose money if its rare losses are large. Judge a system by expectancy per unit risked, not by hit rate (Ch6). In Tharp's words: "Expectancy and probability of winning are not the same thing."
5. **Expectancy alone doesn't make money; expectancy times opportunity does.** A lower-expectancy system that trades often can beat a high-expectancy one that trades rarely, as long as costs are covered (Ch6, Ch11).
6. **Costs grow with trade frequency.** Tharp says most systems pay out about as much in costs as they earn in net profit, and tight stops multiply the number of trades. Short-term traders must treat execution cost as a first-order variable (Ch9, Ch11).
7. **Size positions small enough to survive the bad sequences you will certainly see.** With a 60% win rate, three or four losses in a row are routine, and betting big after losses (gambler's fallacy) is how a positive-expectancy game goes broke (Ch2 Ralph Vince experiment, Ch6, Ch12). His wording: "Remember that your position size on a given trade must be low enough so that you can realize the long-term expectancy of your system over many trades."
8. **Use anti-martingale sizing.** Tie size to current equity so risk grows after gains and shrinks after losses. Never double up after losses (Ch12).
9. **Percent-risk sizing makes 1R mean the same thing in every market**, and it lets small and large accounts grow smoothly (Ch12).
10. **Put stops outside the noise.** A multiple of recent average true range, or a level beyond the maximum adverse excursion (MAE) of past winners, beats arbitrary dollar or percentage stops (Ch9).
11. **Big R-multiple winners carry most systems.** In his worked examples one trade often supplies the whole year's profit. Designing exits that capture 10R+ trades matters more than the entry (Ch4 step 9, Ch6, Ch11).
12. **Don't scale out.** Selling part of a winner early means you hold full size on losers and partial size on your biggest winners. He calls this "reverse position sizing" (Ch10).
13. **Keep degrees of freedom to about four or five.** Each tunable parameter or extra indicator improves the fit to history and harms the future. Filters built from the same price data add little. Setups built from *different* data (volume, fundamentals, time, breadth) can help (Ch2, Ch7).
14. **Data are not the market.** Vendor errors and look-ahead ("postdictive") errors can make a bad system look good, or the reverse. If results look too good, suspect the test (Ch2, Ch13).
15. **Write objectives first.** That means return targets, the largest drawdown you can bear, and how you will know the system is broken (results outside a pre-planned best and worst range). Tharp suggests spending 20 to 50% of development time here (Ch3, Ch4).
16. **Rehearse the worst case.** List disasters (price shocks, outages, data failure, personal crises), write several responses to each, and rehearse them. The system is not complete until this is done (Ch4 step 12, Ch13).
17. **Add independent markets and uncorrelated systems.** More opportunity and smoother equity mean a larger base when the big winner arrives (Ch4 step 11, Ch13).
18. **Use psychological stops.** Stand aside when the operator is compromised (divorce, bereavement, a new child, moving, burnout, euphoria) or unable to watch the market (travel) (Ch9, Ch10).

## 3. Codeable rules, precisely

### 3.1 R and R-multiples (Ch6, Ch9)

- `R_per_unit = entry_price - initial_stop` (long).
- `R_multiple = (exit_price - entry_price) / R_per_unit`. A loss exactly at the stop is -1R. Gaps can make it -2R or -3R.
- Tharp's fallback when the true initial stop wasn't recorded: take the typical *smallest* non-scratch loss as 1R and bucket trades by multiples of it (Ch6 steps 3-4). The bot records real initial stops, so it doesn't need this.
- Rule of thumb: with a trailing stop, the average loss comes out near 0.5R (Ch9).
- Costs: compute expectancy after commissions and slippage. His worked stock example shows costs turning a 6R gain into about 2.6R net (Ch9).

### 3.2 Expectancy (Ch6)

- Formula 6-1: `E = PW*AW - PL*AL`, with AW and AL as average win and loss. Expressed in R, this is expectancy per dollar risked.
- Formula 6-2 (by payoff bucket): `E = Σ_i p_i * payoff_i - Σ_j q_j * loss_j`. It is the same as the mean R-multiple.
- Worked checks from the book:
  - 60/40 odds at 1:1 gives E = 0.20.
  - A 36%-win "marble bag" with large payoffs gives E = 0.78.
  - 90% winners at $275 against 10% losers at $2,700 gives E = -22.5 per trade (negative).
- Opportunity comparison: `E * trades_per_period`. Example: 0.20 × 60 draws beats 0.78 × 12 draws.
- Quality guidance (Ch6 review step 6): a system with **at least 100 trades and E above 0.5R** is "good" for long-term trading, and a lower E is acceptable with enough opportunity. In live trading, E at or below 0.15R may reflect execution or psychological errors rather than the system (Ch4 note 8).
- Worked systems in Ch11 (after costs): long-term high-R trend following at 18% wins × 23:1 gives 3.32R before costs and 2.90R after. Standard trend following at 44% wins, average win 2.4R, average loss 0.5R gives 0.776R before and 0.63R after. Short-term volatility breakout: 0.50R before, 0.30R after. Market maker: about 0.012R per trade.

### 3.3 SQN (not in this edition; from Tharp's later work, cited from memory, so verify before use)

- `SQN = sqrt(N) * mean(R) / stdev(R)`. In later versions N is capped at 100, so large samples don't inflate the score.
- This is simply the t-statistic of the mean R-multiple. Treat it as a significance test, not a magic number.
- Tharp's later scale (approximate):
  - 1.6–1.9: poor but tradable
  - 2.0–2.4: average
  - 2.5–2.9: good
  - 3.0–5.0: excellent
  - 5.1–6.9: superb
  - 7+: "Holy Grail"
  - Below about 1.6: hard to trade
- He also said to use a reasonable minimum sample, about 30 trades, before reading it at all.

### 3.4 How many trades before judging a system (Ch4, Ch6)

- Collect at least **50–100 historical example moves** before forming a concept (Ch4 step 5).
- Treat a system as "good" only with **≥100 trades** and E > 0.5R (Ch6).
- For the 60-trade marble demonstration he says you would want roughly **ten times as many trades** before settling the sizing (Ch6).
- Critique: 100 trades with a positive mean is not proof. Trades needed for a t-stat (SQN) of 2 is `N ≈ (2*sd/E)^2`. At E = 0.2R and sd = 1.5R that is about 225 trades. At E = 0.3R, sd = 2.0R, about 178. At E = 0.5R, sd = 2.5R, about 100.

### 3.5 Losing streaks to expect (my simulation, 100 independent trades)

| Win rate | Median longest losing streak | 95th percentile | P(streak ≥ 10) |
|---|---|---|---|
| 35% | 9 | 15 | 38% |
| 45% | 7 | 11 | 11% |
| 50% | 6 | 9 | 4% |
| 60% | 4 | 7 | 0.6% |

Tharp's own example: a 50%-win, 2:1 system "could easily" show 10 losses in a row (Ch3).

### 3.6 Position-sizing models (Ch12)

All four are anti-martingale because they scale with current equity.

1. **Units per fixed amount of money.** `units = floor(equity / X)`, e.g. 1 contract per $50k.
   - Tharp's objections: it treats unlike instruments alike (a T-bond contract vs a corn contract), grows size only in large steps, and never rejects an over-risky trade.
   - Backtest (55/21-day breakout, 10 futures, 1981–91, $1M start): 1 contract per $100k gave 18.2%/yr with a 36.7% max drawdown. 1 per $50k gave 32.3% with a 61%(!) drawdown. 1 per $20k went bust.
2. **Equal units (equal value).** `shares = (equity * gross_leverage / N_units) / price`.
   - Common for stocks, and it shows total leverage at a glance.
   - Tharp's objections: it is slow to scale and exposure isn't equal in risk.
3. **Percent risk.** `units = (equity * r) / (R_per_unit * point_value)`.
   - Example: $50k × 2.5% = $1,250 of risk; a $1,000-per-contract stop gives 1 gold contract; a $250 stop gives 5 corn contracts.
   - Guidance: under 1% per position when trading other people's money; up to about 3% with your own; above 3% is "gunslinger" territory (Ch12, also Seykota and Basso in Ch2). Roughly halve these if stops sit inside one day's range.
   - Basso (Ch3) risks 0.8–1.0% per trade in his funds and would use 1–1.5% personally.
   - Backtest (same 55/21 system): about 1% risk gave about 7%/yr with about a 13% drawdown. About 2.5% risk gave about 19%/yr with about a 29% drawdown. Margin calls started near 10% risk. The best return-to-drawdown ratio came at 25% risk, with about an 84% drawdown.
   - Caveat he concedes (via Gallacher): a tight stop allows a large position, and a stop is not a guaranteed fill.
4. **Percent volatility.** `units = (equity * v) / (ATR_n * point_value)`, with the ATR taken as a 10- or 20-day average of true range.
   - Example: $50k × 2% = $1,000; gold ATR $3 × $100 = $300 per contract, so 3 contracts.
   - Recommended for tight-stop traders.
   - Backtest: 0.5% volatility gave about 20%/yr with about a 31% drawdown; 1% gave about 40%/yr with about a 50% drawdown. Tharp suggests 0.5–1.0% for that system.
   - Calibration he notes: 5% risk against a 21-day-extreme stop was about equal to 1% volatility against a 20-day ATR. **The percentage only means something relative to the distance it is applied to.**
5. **Other schemes reviewed:**
   - O'Neil: position count by account size (2 stocks under $5k, 3 for $5–20k, 4–5 for $20–160k, 6–7 above).
   - Foolish Four: 40/20/20/20.
   - Gallacher: one unit per $40k for each $1,000 of daily range when traded alone; per $28k with one other market; per $20k with three others.
   - Kaufman: pick leverage so a 1-standard-deviation drawdown is tolerable. This assumes normality, which Tharp flags.
   - Gallacher's LEED: assume your largest tolerable equity drop happens tomorrow.
6. **Dow-30 demonstration.** Same signals throughout: 45-day high breakout, 3×ATR trailing stop, long only, 1992–mid-1997, 595 trades, 45.9% winners, 0.5% costs.

   | Sizing | CAGR | Max drawdown |
   |---|---|---|
   | 100 shares flat | 0.58% | 0.75% |
   | 100 shares per $100k | ~5.75% | 7.1% |
   | 3% equal value | 3.9% | 3.7% |
   | 1% risk | 20.9% | 14.1% |
   | 0.5% volatility (10-day ATR) | 22.9% | 16.6% |

   See the critique in section 5.

### 3.7 Stops (Ch9)

- **Volatility stop:** `stop = entry - k * ATR10`, with k between 2.7 and 3.4 (from Wilder). Tharp says these are "among the best" stops. On weekly ATR, k = 0.7–2.
- **MAE stop:** tabulate each winning trade's maximum adverse excursion in ATR units and set the stop just beyond where winners rarely go.
  - Book example (British pound, 1985–92): no winner went beyond 1.5 ATR, and only 12.5% of winners exceeded 1 ATR. Losers averaged 1.44 ATR of MAE.
  - Re-check periodically. The same approach can improve O'Neil's fixed 7–8%, perhaps by price band.
- **Dev-stop (Kase):** over 30 days, `ATR + 1 SD(TR)` plus a 10% skew correction, or `ATR + 2 SD` plus 20%.
- **Percent retracement:** e.g. O'Neil caps losses at 7–8% and targets an average loss of 5–6%. Fine only if backed by MAE analysis.
- **Dollar stop:** only sensible when derived from volatility or MAE. Calling a fixed-dollar stop "money management" is naive.
- **Channel or moving-average stops** (e.g. exit at the N-day low): workable, but they give back a lot because the same level serves as protection and as profit exit.
- **Support or resistance stops:** add an offset so they aren't where everyone else's stops sit.
- **Time stops:** e.g. exit after X days without a profit, or re-justify the trade each day. Good for short-term trading. Test whether they cut you out before big moves.
- **Tight stops:** fewer R lost, larger R-multiples and several attempts at a move, but lower reliability and much higher costs. Worked example: five $100 stop-outs then a $2,000 win nets $900 after costs, while a $600 stop that holds nets $1,900.
- **Psychological or discretionary stops:** see lesson 18.

### 3.8 Profit exits (Ch10)

- **Timed exit:** e.g. at the close in 2 days if not profitable.
- **Trailing volatility stop:** `stop_t = max(stop_{t-1}, close_t - k * ATR)` with k = 3, recomputed from the close. It only moves in the trade's favour, so it also rises when volatility shrinks. Dollar, channel (N-day low) and moving-average trails are variants; the 200-day average is his stock example.
- **Profit-retracement stop:** activate after +2R and allow a 30% giveback of open profit, tightening to 25% at 3R, 20% at 4R, and down to 5% at about 7R. The gold example tightens to 10% at 4R.
- **Profit objective:** e.g. exit or tighten at 4R. O'Neil takes 20%, about 2.5R against his 8% stop.
- **Large adverse volatility day:** exit if price moves more than 2×ATR against you from the prior close in one day. Never use this as the only exit.
- **Parabolic SAR:** good for locking in gains, poor as initial risk. Pair it with a hard initial stop and a way to re-enter.
- **Multiple simple exits, nearest one active.** Tharp's untested example: a 3×ATR trailing stop from the close, plus the 2×ATR one-day adverse move, plus tightening the trail to 1.6×ATR once +4R is reached.
- **Avoid:** scaling out (lesson 12).

### 3.9 Setups and filters (Ch7)

- **Four phases of entry:** market selection, market direction, setup, timing.
- **Market selection:**
  - Liquidity: avoid stocks trading under 10,000 shares a day.
  - Avoid instruments less than a year old.
  - Know the exchange's rules.
  - Volatility must allow a target of **2–3× the initial risk**.
  - Capitalization should fit the strategy.
  - Prefer independent markets.
- **Market direction:** markets trend only about 15–20% of the time, so stay out of sideways markets rather than always being in.
- **Useful setups (from data other than plain price):**
  - **Kaufman efficiency ratio:** `ER = |C_t - C_{t-10}| / Σ_{10} |C_i - C_{i-1}|`. Require ER above a threshold, e.g. 0.6.
  - **Narrow range inside a trend:** range of the last 5 days ≤ 60% of the range of the last 50 days. Tharp claims this adds 0.10–0.15R to a long-term trend system's expectancy.
  - Inside day that is also the narrowest range of the last X days, then trade the breakout.
  - Volatility climax: 5-day ATR at 2–3× the 50-day ATR. He calls these trades dangerous; long-term traders should use them only to avoid entering.
  - Arms index (TRIN), 5-day average: above 1.2 suggests a bottom, below 0.8 a top, for 1–3 day trades.
  - Retracement setup: trend, then pullback, then resumption. It allows tight stops, catching up on a missed move and re-entry.
  - Failed tests such as "Turtle Soup" fades of 20-day breakouts, for short-term trading.
- **Filters** (more indicators computed on the same price series): avoid them, because they only improve the fit to history.

### 3.10 Entry (Ch8)

- **Random entry is the benchmark.** Coin-flip entry, a 3×ATR stop (10-day exponential ATR) trailed from the close, and 1% risk sizing across 10 futures markets: profitable in 80% of runs at one contract and 100% of runs with 1% risk, with a 38% win rate.
- **Reliability test (LeBeau and Lucas):** measure the percentage of signals profitable at 1, 2, 5, 10 and 20 days with no stops. Random is about 50% (45–55%). Anything useful should be at least 55%, especially at 1–5 days. Expect it to drop to 50–55% once stops and costs are added.
- **His preferred entries:**
  - A channel breakout of 40–100+ days (he says 20-day breakouts stopped working).
  - A one-day volatility breakout of about 0.8×ATR from the prior close, especially for "predictors" who need price confirmation.
  - ADX rising above 15, a rise of more than 4 points in 2 days, or ADX at a 10-day high, with direction taken from something else.
  - A DI+/DI- cross plus a break of the prior high or low.
  - Speed or acceleration turning in the trend's direction.
  - A turn in Kaufman's adaptive moving average (AMA) that clears a noise filter.
  - An oscillator extreme *against* the main trend followed by resumption. This is the only way he endorses using oscillators.
- **Kaufman AMA:**
  - `fast = 2/(2+1)`, `slow = 2/(30+1)`
  - `SC = (ER*(fast - slow) + slow)^2`
  - `AMA_t = AMA_{t-1} + SC*(P_t - AMA_{t-1})`
  - Filter = `k * stdev(ΔAMA over 20 days)`, with k = 0.1 for futures and FX and k = 1.0 for equities and rates.
- **O'Neil entry:** a breakout from a 7-week to 15-month base on volume at least 50% above average.

## 4. Psychology (the book's view)

- **The Holy Grail is internal.** No perfect system exists. The "secret" is finding a method that fits you and reaching a state where wins and losses feel equally part of the business. In his words: "The Holy Grail is not a magical trading system; it is an inner struggle." (Ch1)
- **Trading is "100 percent psychology".** He argues that system design and position sizing are behaviours too. Others split it 60% psychology, 30% sizing, 10% system. The Seykota anecdote: two weeks to teach a class a moving-average system, eight weeks to get them to follow it (Ch1).
- **You trade your beliefs.** In his words: "You don’t trade or invest in markets—you trade or invest according to your beliefs about the markets." (Ch4) Treat "facts" as more or less *useful beliefs*, write your market beliefs down, and test them (Ch4, Ch13). Beliefs about yourself (worthiness, capability) can sink a good system (Ch13).
- **Judgmental biases (Ch2):**
  - In design: representation (the bar or indicator is not the market), reliability (bad data), lotto (illusion of control through entry), law of small numbers, conservatism (ignoring disconfirming evidence), randomness, need-to-understand.
  - In testing: degrees of freedom, postdictive error, not enough protection.
  - In trading: gambler's fallacy, taking gains early while gambling on losses (the prospect-theory choices in his examples), needing the current trade to be a winner, and public predictions locking in your ego.
- **Self-sabotage.**
  - Examples: the FX trader with a 75%-win, gains-equal-losses method who couldn't trade size because of "his stomach"; the forecaster whose public accuracy made him a poor trader; the partners who skipped the one British-pound trade that would have made their year (Ch4 note 5, Ch2, Ch11).
  - Remedy: take total responsibility for outcomes, including broker or partner failures, and look for your own repeating patterns (Ch13).
- **Seven discipline steps (Ch13):**
  1. Have a tested plan.
  2. Take total responsibility.
  3. Find weaknesses with a diary.
  4. Plan globally for everything that could go wrong.
  5. Analyse yourself daily.
  6. Rehearse the day's possible problems each morning.
  7. Debrief daily with one question: *did I follow my rules?* Praise yourself twice for following them and losing money.
- **Games reveal behaviour.** If you can't make money in a positive-expectancy bead game without taking large risk, you won't in markets (Ch13).

## 5. Claims to check against evidence

1. **"Position sizing explains most performance differences"**, supported by Brinson, Hood and Beebower's 91.5% (Ch12 note 8). This misreads the study, which measured how much of *one fund's variation over time* is explained by its policy asset mix. It says nothing about variation across managers (see Ibbotson and Kaplan, 2000). Sizing scales an edge and its risk; it cannot create an edge.
2. **The Dow-30 sizing comparison.** The models differ mainly in *gross exposure*, and 1992–97 was a strong bull market, so the larger-exposure models naturally made more. Returns aren't risk-adjusted or compared at equal drawdown, and there is one sample path. At equal volatility the differences would shrink a lot.
3. **"Random entry plus a 3×ATR trailing stop and 1% risk is profitable."** This comes from futures in the 1980s–90s, an era of strong trend-following returns. It shows the trailing exit captured the trend premium of that period, not that exits create an edge in any market. Replicate it on recent data and on equities before believing it.
4. **"Most entries are no better than random; oscillators are a fool's game"** (LeBeau and Lucas, Ch8). This conflicts with the short-horizon mean-reversion evidence that sleeve B relies on (Connors RSI(2) on index ETFs). Both can be true in different regimes and time frames. Check B's post-publication decay directly.
5. **"20-day breakouts stopped working, 40–100+ days still work."** Unsourced. Check on the bot's universe.
6. **The narrow-range setup "adds 0.10–0.15R"** to trend systems. No data shown.
7. **"Markets trend only 15–20% of the time"** (elsewhere 15% trending and 85% consolidating). Unsourced, and it depends on the definition.
8. **"Infinite variance" of price changes** (Ch2). Heavy tails are real, but the evidence (e.g. the tail-exponent-near-3 "inverse cubic law") points to finite variance with fat tails. The practical conclusion still holds: risk estimates from normal models understate extremes.
9. **The Vince experiment** (38 of 40 PhDs lost money in a 60% game) is cited second-hand. It is plausible, but the exact figures aren't checkable here.
10. **"Scaling out is reverse position sizing."** Partly true. Scaling out lowers expected R when the trailing piece has positive expectancy, but it also lowers variance. Test it with the bot's own trades rather than assuming.
11. **Setups from different data sets: "more is generally better"** (Ch7). This conflicts with his own limit of four or five degrees of freedom. Each setup is a parameter.
12. **Performance anecdotes:** Mobley's 40%+ a year, Kelly's 40–60% a year, "people who understand these principles can easily make 50 percent per year" (Ch13), and a floor trader's $1.7M in three months. These are unaudited and survivor-selected, and some are marketing for his own programmes and the Athena software he helped develop. Treat them as not evidence.
13. **"If there were no trends, organized markets would not exist"** (Basso, Ch5). This is an argument, not data. The time-series momentum literature (e.g. Moskowitz, Ooi and Pedersen, 2012) supports trend premia in futures, and they have been weaker since about 2010.
14. **"Anti-martingale works in gambling"** (Ch12). Increasing bets with equity only compounds a *positive* expectancy. In negative-expectancy casino games it just loses more slowly.

## 6. Fit with the bot (risk.py, risk_policy.yaml, playbook, engine)

Checked against the current code:
- `trader/risk.py` enforces stops at the close, clips increases to `risk_pct_default × equity / (price − stop)`, enforces the notional, cash and 6% heat caps, and blocks averaging down.
- `trader/engine.py` records `R` per closed lot, using `initial_stop`, and reports one `avg_R` and `win_rate` across all sleeves.
- `trader/strategies.py` implements the sleeve rules.

### 6.1 What already matches Tharp (keep)

| Tharp rule | Bot | Verdict |
|---|---|---|
| Percent-risk sizing (model 3), under 1% when careful | 0.5% of equity per trade, 2% hard cap, halved at a 10% drawdown | Matches, and conservative. Keep. |
| Anti-martingale | Risk scales with current equity; the drawdown breaker halves it | Matches. Keep. |
| No martingale or averaging down | `no_averaging_down: true` | Matches. |
| Stop set before entry, outside the noise | ATR stops (B 3×, C 2× capped at 8%, D 3×), `never_widen_stop` | Matches Ch9 (his range is 2.7–3.4× a 10-day ATR; C's 2× a 20-day ATR is tighter, see 6.4). |
| Time stop for short-term trades | B: 10-day time stop plus exit on close > 5-day SMA | Matches Ch9 and Ch10. |
| Percent-volatility sizing | Sleeve A volatility target 10%, sleeve D 25% | This is model 4 at portfolio level. Keep. |
| Ongoing risk kept at a fixed % of equity (Basso) | `max_open_risk_heat` 6%, measured as (price − stop) × qty | Matches. Keep. |
| No scaling out | None in code | Matches Ch10. |
| Objectives with limits and "results outside the range means something is wrong" | Brief: 6–10%/yr, drawdown under 15–20%, "much better is likely luck or a bug"; breakers at 10/15/20% | Matches Basso in Ch3. |
| Costs inside expectancy | `cost_model_per_side_bps` exists | Partial: R in `closed_trades` is gross (see 6.2 item c). |

### 6.2 Concrete changes I recommend

**a) Compute expectancy and SQN per sleeve, net of costs, and show it to Claude and the owner. (Accept.)**
`engine.py` currently computes one `avg_R` over all sleeves. Tharp's whole framework is per system, and the four sleeves are four systems. Mixing A's non-R trades with B's short mean-reversion and C's breakouts hides everything. Proposed per-sleeve block, computed only from trades with a real initial stop (B, C, D):
```
n, win_rate, avg_win_R, avg_loss_R, E = mean(R_net),
sd = stdev(R_net), SQN = sqrt(min(n,100)) * E / sd,
trades_per_year, E_per_year = E * trades_per_year,
max_losing_streak, worst_R, best_R, share_of_total_R_from_top_3_trades
```
Show SQN only when n ≥ 30, and label it "t-stat of mean R" to keep expectations honest. `share_of_total_R_from_top_3_trades` captures Tharp's point that one or two trades make the year; it helps Claude avoid "fixing" a system after a normal drought.

**b) Fix R when a lot is added to. (Accept, a real bug.)**
`update_lots` blends `entry_price` when quantity increases but keeps the old `initial_stop`, and `lot.stop` is overwritten by the target's stop. Once a lot has been added to, `R = (exit − blended_entry) / (blended_entry − first_stop)` no longer measures anything. This can happen:
- in C, where a Claude target can raise quantity above the current price;
- in D, where band rebalancing raises quantity whenever the Donchian score or volatility scale rises.

Fix: store `initial_risk_dollars = qty × (entry − initial_stop)` at open and add each add-on's own risk. Compute `R = pnl_dollars / initial_risk_dollars`. Alternatively, record each add as its own lot for statistics.

**c) Record R net of costs. (Accept.)**
Use `R_net = (exit − entry − cost_per_share_round_trip) / R_per_share`, with cost taken from `cost_model_per_side_bps × 2 × price`. For C at 10 bps a side against stops 3–8% away, this is a 0.03–0.07R drag per trade. That's small, but Tharp's point is that it compounds with frequency, and B trades most often.

**d) Make the validation gate statistical, per sleeve. (Accept as a change to the manual gate, not automation.)**
The policy's `risk_pct_validated` requires "≥100 trades with positive expectancy". That is Tharp's trade count without his 0.5R bar, and neither is enough (section 3.4). Proposed text, still human-approved:
- raise a sleeve from 0.5% to 1% only after ≥100 **live/paper** trades in that sleeve;
- net E > 0 **and** SQN ≥ 2.0;
- live E at least half the backtest E (the brief's "halve backtests" rule);
- no breaker halt in the last 3 months.

At plausible E and sd this takes 100–225 trades. With B limited to 2 slots on 4 ETFs and C to 5 slots behind a bull-market gate, that is likely years of paper trading. That's acceptable; it just shouldn't surprise anyone.

**e) Make C's trailing exit enforceable by code, including in the Claude book. (Accept, the most important exit change.)**
C's exits (close below the 10-day low, close below the 50-day SMA) live only in `strategies.sleeve_c`. `risk.py` enforces only the stored `stop`, which for C stays at the initial 2×ATR/8% level. In the Claude book, `run` enforces stops, but Claude's own targets decide everything else. So Claude can hold a C name after it has broken its 10-day low, with only the initial stop as backstop.

Tharp's rule is that the exit is part of the system and must be decided in advance. Fix: each day ratchet the C stop to `max(current_stop, low_10d, sma50_offset?)`. Use the plain 10-day low; the 50-day SMA exit can stay as a strategy rule. `never_widen_stop` already guarantees it only rises, and `risk.py` then enforces it for both books. This also makes the heat metric (price − stop) reflect real open risk rather than the stale initial risk.

**f) Test, don't adopt, Tharp's alternative C trail. (Test.)**
Candidates, one new parameter each, to respect his limit of four or five degrees of freedom:
1. 3×ATR(10) trailed from the close;
2. the current 10-day-low exit;
3. his three-exit bundle: 3×ATR trail, plus the 2×ATR adverse-day exit, plus tightening to 1.6×ATR after +4R.

Judge them on net E, SQN and the share of R from the top trades. Because C's edge comes from a few big winners (the brief says 35–50% win rates), the tighter variants should be expected to *lower* E. Reject any that cut the right tail.

**g) Log MAE and MFE per lot in R. (Accept, cheap.)**
Each day, update `mae_R = min((low − entry)/R_per_share)` and `mfe_R = max((high − entry)/R_per_share)`. After 50+ trades per sleeve this supports Tharp's MAE stop analysis: do B's winners ever go below −1R? If not, the 3×ATR disaster stop may be wider than needed. It also supports the profit-retracement idea (how much open R do C's winners give back?). No behaviour change until the data exists.

**h) State the losing-streak expectations in the brief. (Accept.)**
From the simulation in 3.5: at a 35–45% win rate (sleeve C), the longest losing streak in 100 trades is typically 7–9 and reaches 11–15 in a bad 5% of cases. Put "C losing streaks up to about 12 are within normal range; judge C on SQN after ≥100 trades, not on a streak" into `playbook_brief.md`. This is Tharp's (and Basso's) "know the range of expected results in advance" rule. It protects against the conservatism and gambler's-fallacy biases, which an LLM advisor is also prone to.

### 6.3 Finding: in sleeves B and C, notional caps usually set the size, not percent risk

Tharp's model 3 is what the policy intends. The code's sizing is `qty = min(risk_budget / (price − stop), sleeve_capital / max_positions / price)`.

- **C:** sleeve 15% of equity divided by 5 slots is 3% of equity per name. Risk per name = 3% × stop distance, and the stop distance is at most 8%, so actual risk is **at most 0.24% of equity** and often 0.1–0.15%. The 0.5% risk budget can bind only if the stop were more than 16.7% away, which the 8% cap forbids. **C is really Tharp's model 2 (equal units)**, and each trade risks well under half the nominal 1R.
- **B:** 20% ÷ 2 slots is 10% of equity per ETF, so the 0.5% risk budget binds only when 3×ATR is more than 5% of price (ATR above about 1.7%). In calm markets (SPY ATR about 1%) B risks about 0.3%. In volatile markets it risks the full 0.5%.

Consequences and recommendations:
- The **R-multiples are still valid** (they are per share), so the statistics in 6.2 are unaffected.
- The **daily and weekly breakers and `one_R_dollars` use nominal 1R = 0.5% of equity**, so "−2R today" really means "−1% of equity today". That is a sensible equity rule but the label misleads: it isn't 2 stopped-out trades, it might be 5–8 C stop-outs. Rename it in the Claude context to `loss_pct_equity`, or report both.
- **Log `risk_pct_at_entry` per lot**, so reviews can see the true sizing model.
- I would **not** raise C's notional cap now. C is on probation, and sizing it under the 0.5% budget is the conservative choice Tharp would support for an unvalidated system. Revisit only if C passes the gate in 6.2(d).
- **Reject switching B or C to percent-volatility sizing.** Their stops are already fixed ATR multiples, so percent risk and percent volatility are equivalent up to a constant (0.5% risk at 3×ATR = 0.167% volatility). Tharp recommends volatility sizing specifically for *tight* stops, which the bot doesn't use.

### 6.4 Other ideas considered and rejected

- **The large adverse-volatility-day exit for B.** Reject: B buys *after* sharp down days, so this exit would fire on the very condition that creates the entry. Possibly test it for C only (part of 6.2(f)).
- **The profit-retracement stop (+2R, then 30% giveback, tightening) for B.** Reject: B's median hold is a few days, and its exit (close above the 5-day SMA) already takes profits quickly. It could be tested for C via the MFE data from 6.2(g).
- **Tharp's 40–100-day breakout preference for C** (C uses a 50-day pivot). Already within his range. No change.
- **Widening C's 2×ATR stop toward Tharp's 2.7–3.4×.** Not without MAE data. A wider stop at a fixed 3% notional would just shift risk toward the 8% cap. Decide after 6.2(g).
- **More setups for C "from different data".** Reject for now. C already has over 10 fixed parameters (SMAs 50/150/200, rising-200 check, 25%/25% bands, RS ≥ 70, 50-day pivot, 1.5× volume, 2×ATR, 8% cap, 10-day-low exit, SPY 200-day gate). That is well past Tharp's four-or-five limit. They weren't optimised on the bot's data, which lowers but doesn't remove curve-fit risk. The fair response is the probation label plus the statistical gate, not more conditions.
- **Tharp's "equal leverage" or O'Neil position count for sleeve A.** Not needed. A is a monthly allocation rule, not a trade system. Keep it out of R statistics (it has no stop) and judge it on drawdown and return against SPY and a 60/40 mix, which is what the brief already frames.

### 6.5 Gap and data risks Tharp would flag

- **Stops are enforced at the daily close and filled at the next price.** Tharp (via Gallacher) warns that a stop is not a guaranteed price. The 6% heat cap covers only stopped sleeves, and **sleeve A (50–60% of equity, no stops) is excluded from heat**. A 1987-style −20% day would cost A's equity-like holdings roughly 8–10% of total equity before any rule reacts. The 20% drawdown halt is the only backstop. **Proposal:** a scenario stress line in the daily Claude context: `gross_exposure × −20%` for equities and REITs and `× −10%` for commodities, next to heat. This is his Ch4 step-12 worst-case planning, informational rather than a new limit.
- **Reliability bias (Ch2, Branscomb's data story).** Add a data sanity check before any increase: a stale last bar, a zero-volume bar, or a price jump over 25% without a matching split flag would block entries for that symbol. It is effectively a "psychological stop" for the pipeline, since the bot has no emotions but does have data failures.

---

*Quotations: four one-sentence quotes (marked "in his words"/quoted) plus a few quoted two-to-four-word terms of art; everything else paraphrased. The "~5.75%" CAGR for the fixed-amount model is a reading of a garbled figure in the source text. Book figures cited are Tharp's own and unaudited. Streak and sample-size numbers are my calculations. SQN details come from Tharp's later publications, cited from memory and flagged in 3.3.*
