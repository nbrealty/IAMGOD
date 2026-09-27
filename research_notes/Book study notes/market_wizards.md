# Market Wizards (Jack D. Schwager, 1989): study notes

Read in full (all 17 interviews, Schwager's own story, the "Trade" and "Dreams" chapters, the Final Word and both appendices).
Written for the owner's Claude-run paper-trading bot. Summaries are in my own words, and direct quotes are kept to a few short lines.
Bot context checked: `trading/config/playbook.yaml`, `risk_policy.yaml`, `playbook_brief.md`, plus `trader/risk.py` and `trader/strategies.py` (sleeve C logic).

---

## 1. What the book is about

Schwager interviews about seventeen traders who were famous in 1987-88: futures and currency traders (Marcus, Kovner, Dennis, Jones, Bielfeldt, Seykota, Hite), stock traders (Steinhardt, O'Neil, Ryan, Schwartz), generalists (Rogers, Weinstein), floor traders (Gelber, Baldwin, Saliba) and a trading psychologist (Van Tharp). They trade in very different ways: systematic trend following, discretionary macro, growth-stock breakouts, value and contrarian bets, pit scalping and options spreads. Schwager's conclusion is that what they share is attitude and process rather than method. They control risk rigidly, stick to one approach, wait patiently for good setups, think independently and accept losses as normal. The book is a set of stories and rules of thumb, not a backtested manual. Almost every performance figure in it is self-reported, unaudited and taken from the high-inflation, strongly trending markets of 1970-1988.

---

## 2. Key lessons (in my words)

1. **Survive first, because a single oversized trade is what ruins people.** Marcus lost everything on one corn trade and nearly did again in lumber. Jones's clients lost 60-70% of equity on one cotton trade. Kovner came close to going bust in soybeans. Schwager himself wiped out several times in his early trading. *(Marcus, Jones, Kovner, Schwager's own story)*
2. **Risk per trade should be small and fixed: about 1% of equity, never 5-10%.** Hite's first rule is 1%. Kovner says beginners take 5-10% risks when they should take 1-2%, and advises trading at half the size you think is right. Marcus puts the ceiling at 5% per *idea*. *(Hite, Kovner, Marcus)*
3. **Correlated positions add up to one big position.** Kovner's losing year (1981) came from too many correlated trades. After it he measured total portfolio risk and correlations every day. Marcus counts two related grain positions as one idea. *(Kovner, Marcus)*
4. **Decide the exit before you enter, and size the trade from the stop.** Put the stop where the trade idea is proven wrong, beyond a technical barrier, and then reduce position size until the dollar risk is acceptable. Do not set the stop by how much money you are willing to lose. *(Kovner, with Schwager's commentary; Marcus; Seykota; Schwartz's "uncle point")*
5. **Cut losses and let winners run, and treat both as equally important.** Marcus's worst experience was getting out of a winning soybean trade too early. Dennis says about 95% of his profits came from about 5% of his trades, so missing a big trend is the costliest mistake. O'Neil and Ryan are right only about half the time and make their money on the few stocks that double. *(Marcus, Dennis, O'Neil, Ryan, Seykota)*
6. **Trade smaller when you are losing and stop trading after a destabilizing loss.** Jones keeps cutting size so that he is smallest when he trades worst, and caps losses so no month is down double digits. Dennis pauses after a big loss and says never to double up. Schwartz drops to a fifth or a tenth of normal size after a big loss. Marcus takes three to four weeks off. Seykota lowers risk steadily as equity falls. *(Jones, Dennis, Schwartz, Marcus, Seykota, Gelber)*
7. **Be wary after winning streaks too.** Schwartz, Jones and Seykota all say their biggest losses came right after their biggest gains, because success led to complacency and oversizing. *(Schwartz, Jones, Seykota)*
8. **Follow the system and do not override it.** Management's second-guessing turned Seykota's best trade of a year into a loss. Hite's partners signed an agreement never to override their system, and one of Hite's friends lost his estate after skipping a single sell signal. Dennis says good rules are easy to write and the hard part is sticking to them. *(Seykota, Hite, Dennis)*
9. **Choose robust parameters rather than optimal ones.** Dennis would accept a parameter set that tested about 10% worse if he expected it to hold up better in future. Hite says Mint looks for the hardiest method, not the best-fitting one. Dennis discarded any system that did not work on both bonds and beans. *(Dennis, Hite)*
10. **Wait for the high-probability setup and do nothing in between.** Rogers waits until the money is "lying in the corner". Bielfeldt compares it to folding weak poker hands. Marcus says trades taken on marginal conditions are entertainment. Baldwin and Bielfeldt both say the public simply overtrades. *(Rogers, Bielfeldt, Marcus, Baldwin, Weinstein)*
11. **Trade with the trend and avoid buying cheap or averaging down.** Dennis admits his counter-trend trades lost money overall. O'Neil found that big winners were bought at new highs, not near lows, and calls averaging down an amateur habit. Schwartz calls bottom-fishing expensive gambling. Hite trades nothing against the trend. *(Dennis, O'Neil, Schwartz, Hite, Seykota)*
12. **Stay out of the market in bad regimes.** O'Neil's "M" says three of four stocks follow the market, so be in cash during bear phases. Ryan lost everything he had made by trading a 1983-84 bear market as aggressively as the bull market before it. Hite's three-light filter stops new entries, or closes positions, when volatility gets extreme. *(O'Neil, Ryan, Hite)*
13. **When in doubt, get out, and do not hold big risk through known events.** Marcus and Gelber flatten positions to think clearly. Kovner closed everything in the week of the October 1987 crash because he did not understand what was happening. Jones will not risk much before key reports. Schwager lost a quarter of his profits by adding to a losing soybean position right before a crop report. *(Marcus, Kovner, Jones, Gelber, Schwager)*
14. **A breakout that fails is a signal to exit.** Ryan sells at least half when a breakout closes back inside its base, and notes that good trades usually show a profit from the first day. Hite re-enters only when the market makes a new high. *(Ryan, Hite)*
15. **Judge a strategy over long periods and many trades, not single results.** Dennis says any one trade is mostly luck and even a year is too short to judge. Hite evaluates his systems by the share of rolling 6-, 12- and 18-month periods that were profitable. Tharp and Hite separate a good bet that lost from a bad bet. *(Dennis, Hite, Tharp)*
16. **Crowded, well-known edges get weaker.** Marcus, Kovner, Dennis and Bielfeldt all complained in 1988 that computerized trend following was producing more false breakouts. Kovner says the less a market is watched, the better the trade. *(Marcus, Kovner, Dennis, Bielfeldt)*
17. **Keep a journal and do the work every day.** Ryan annotates a chart for every trade. Dennis writes down what he did right and wrong. Saliba reviews each day and plans for the next. Schwager's closing chapter concludes that skipping the daily homework is what cost him. *(Ryan, Dennis, Saliba, Schwager)*
18. **Leave out ego and money-thinking.** Baldwin says a trader cannot trade for money. Weinstein's worst loss came from sizing a trade to pay for a castle. Schwartz became a winner when making money mattered more to him than being right. *(Baldwin, Weinstein, Schwartz, Tharp)*

---

## 3. Codeable rules

Each rule is stated tightly enough to program. The book gives very few exact parameters, so values marked **(book)** come from the text and values marked **(my proposal)** are suggestions to test.

### 3.1 Position sizing and per-trade risk
| # | Rule | Source |
|---|---|---|
| S1 | `risk_$ = equity * 0.01`; `qty = risk_$ / (entry - stop)`. (book: 1%) | Hite (Mint), Kovner (tries not to exceed 1%) |
| S2 | Hard ceiling: risk per trade <= 2% (book: Kovner's 1-2% for beginners); Marcus's absolute ceiling is 5% per *idea*. | Kovner, Marcus, Seykota (below 5%) |
| S3 | Treat correlated positions as one idea: sum the risk of all positions with 60-day return correlation > threshold, and cap the total at the single-idea limit. | Marcus, Kovner |
| S4 | Recompute size from **current** equity every time (never keep a fixed share count after equity falls). | Hite (manager who kept size after half the money was withdrawn) |
| S5 | Do not raise the base risk % until capital has doubled or tripled. | Schwartz |
| S6 | Concentration by account size (O'Neil): $5k -> 1-2 stocks, $10k -> 3-4, $25k -> 4-5, $50k -> 5-6, $100k+ -> 6-7. | O'Neil |

### 3.2 Stops and exits
| # | Rule | Source |
|---|---|---|
| X1 | Every entry has a stop order placed at entry time; no entry without a stop. | Marcus, Kovner, Seykota, Dennis |
| X2 | Stock max loss: exit at market if `close <= entry * (1 - 0.07)` (book: 7%; O'Neil and Ryan). Short side 6-7%. | O'Neil, Ryan |
| X3 | Stop placed beyond a technical level (e.g. below base low / consolidation low), not inside a range; then size down to fit risk. | Kovner |
| X4 | Failed-breakout exit: if a breakout position closes back below the pivot (top of base), sell >= 50% (book). | Ryan |
| X5 | Time stop: if a trade is losing after 1-2 weeks, or is still about flat after "significant time", exit (book, loosely stated). Jones also exits when an expected move fails to arrive on time. | Dennis, Jones (via Tullis) |
| X6 | Trailing stop: move the protective stop up as the trend continues; never widen it. | Seykota, Bielfeldt |
| X7 | Climax exit (futures): cautious on the 3rd consecutive limit-up day, usually out on the 4th, mandatory exit on the 5th. Equity analogue (my proposal): exit when price is > N ATR above the 50-day SMA after k consecutive up days. | Marcus |
| X8 | Exit after the stock breaks down from a new base that forms after a run-up (no fixed profit target). | Ryan |
| X9 | Weekend rule: do not hold a losing short into the weekend when Friday closes at the high, or a losing long when Friday closes at the low. | Dennis |
| X10 | Scale out: when covering, sell half before the obvious stop cluster (prior high/low) and half beyond it. | Jones (execution, big size) |

### 3.3 Entries and filters
| # | Rule | Source |
|---|---|---|
| E1 | Trend filter: go long only when price is above its moving average (Schwartz: "works better than any tool I have"); no counter-trend initiations. | Schwartz, Dennis, Hite, Seykota |
| E2 | Breakout entry: buy on the first close above the base high (new high relative to the base), on volume >= 1.5x the recent (50-day) average. Be wary if volume is only up ~10%. | O'Neil, Ryan |
| E3 | Extension filter: do not buy if price is > 10% above the base/pivot (O'Neil); Ryan says within a few %, and lost money buying 15-20% extended. | O'Neil, Ryan |
| E4 | CANSLIM screen (stocks): quarterly EPS growth y/y >= 20-50% (best winners averaged +70%); 5-year annual EPS growth ~24%+ with no down years; relative strength >= 80 (Ryan: prefers 90+, and exits when the RS uptrend breaks); industry group in top 50 of 200; < 25-30M shares outstanding; 1-20% fund ownership; "something new"; price >= $10; P/E between 1x and 2x the S&P P/E (Ryan's addition, O'Neil disagrees). | O'Neil, Ryan |
| E5 | Market gate: long entries only when the general market is not topping. Topping signs: new index high on low volume; several days of heavy volume with no price progress; leaders breaking down; A/D line failing to confirm a new high; Fed raising the discount rate 2-3 times; 5-6 consecutive stopped-out trades. | O'Neil, Ryan |
| E6 | Range expansion entry: after a narrow range, a sudden range expansion signals the direction of the move (Jones's system; no parameters given). | Jones |
| E7 | Volatility breakouts out of tight, unexplained congestion are better than news-driven ones; violent gap breakouts are "more reliable" even with worse fills. | Kovner |
| E8 | Re-entry after a money-management stop: re-enter only on a new high in the trend direction. | Hite |
| E9 | Intermarket confirmation: stay flat when T-bond and T-bill prices sit on opposite sides of their moving averages. | Schwartz |
| E10 | Divergence filter: a stock holding above its recent low while the index breaks its recent low is relatively strong. | Schwartz |
| E11 | Event filter: no significant new risk right before major scheduled reports (for stocks: earnings). | Jones, Schwager (crop report) |
| E12 | Volatility filter ("three lights"): green takes all signals; yellow exits on signals but takes no new entries; red liquidates and takes no new entries. Triggered when volatility over 10-100 day windows makes the return/risk ratio unacceptable. Thresholds not disclosed. | Hite |

### 3.4 Portfolio and account-level risk limits
| # | Rule | Source |
|---|---|---|
| P1 | Monthly loss cap: once down X% in a month, the rest of the month's risk budget is limited so the month cannot finish down >= 10%. (book: down 6.5%, remaining stop 3.5%) | Jones |
| P2 | Intraday/daily equity drop of 1-2% may trigger liquidation of everything. | Jones |
| P3 | Losing streak: cut size progressively; if really bad, stop and flatten (Dennis/Gelber: including the winners). Marcus: stop 3-4 weeks. | Jones, Dennis, Gelber, Marcus, Seykota |
| P4 | After a large loss: next trades at 1/5 to 1/10 of normal size until back in the black. | Schwartz |
| P5 | After a strong winning run: size down, not up. | Schwartz |
| P6 | Equity curve: if the equity trend is down, or equity falls faster than it rose, cut back and reassess. | Marcus |
| P7 | Never add to a losing position; never average down. | Jones, Gelber, O'Neil, Schwartz |
| P8 | Diversify across many uncorrelated systems and time frames, not just many markets. | Hite, Dennis |
| P9 | Treat every position as if entered at last night's close, i.e. mark to market with no "profit cushion" when deciding to hold. | Jones |

### 3.5 Areas where the book gives nothing codeable
- **Discretionary macro and contrarian methods** (Kovner scenarios, Steinhardt "variant perception", Rogers "sell hysteria", Jones's 1929 analog). These have no testable rules, and Steinhardt explicitly uses no stops.
- **Floor methods** (Baldwin scalping, Gelber reading other traders, Weinstein's gut timing). They depend on order flow and intraday data that the bot does not have.
- **Options** (Saliba butterflies and "explosion" positions; Appendix 2 is only a primer). Options are banned by policy.
- **Exact trend-system parameters.** Seykota (Donchian 5/20 MA crossover, exponential MAs), Dennis/Turtles and Mint describe ideas only; the Turtle rules are not in this book.
- **Crypto and ETF allocation.** The book covers neither.

---

## 4. Psychology and discipline principles

- **Losing is part of the game.** A loss that came from following sound rules is not a mistake. A mistake means breaking the rules. (Kovner, Hite's "good bets vs winning bets", Tharp, Final Word)
- **Separate ego from P&L.** Traders fail because they would rather lose money than admit being wrong, and "I'll get out when I'm even" protects the ego, not the account. (Schwartz, Gelber, Baldwin)
- **Do not think in dollars or in things money buys.** Weinstein's castle trade and Baldwin's comments on house-money thinking show how it distorts judgment. Tharp's surveyed winners believe money is not important and that trading is a game.
- **Avoid impulsive trades.** Schwager thinks impulsive trades, as opposed to intuitive ones, have the highest failure rate of any kind of trade. Examples are acting on a friend's tip or abandoning a plan mid-trade. Kovner's worst loss came from a snap decision made on a phone call.
- **Follow your own method.** Borrowing another trader's style tends to combine the worst of both. Dennis's test for trainees was to buy on your own signal even if Dennis himself is selling. (Marcus, Dennis, Seykota, O'Neil's list of common mistakes)
- **Humility is protective.** Seykota and Jones both felt most confident right before losing streaks. Jones says that once you think you are very good, you are finished. (Jones, Schwartz, Weinstein)
- **Keep the emotional response to wins and losses equal and small.** If you let yourself feel too good about gains, you will feel too bad about losses. (Dennis)
- **Step away to regain clarity.** Flattening, taking a nap or a day off, and changing physical state (Tharp's posture and breathing exercise) all break stress-driven tunnel vision. Stress narrows options and pushes people to repeat old habits harder. (Marcus, Dennis, Saliba, Tharp)
- **Prepare "what-if" plans in advance.** Saliba and Kovner write scenarios and set trigger levels ahead of time. Saliba could act on 19 October 1987 while others froze, because his worst case was known. (Saliba, Kovner, Bielfeldt)
- **Review daily.** Tharp suggests reading the rules at the start of the day and checking them at the end, and praising yourself for following the rules even on a losing day.
- **Seykota's hypothesis that everybody gets what they want.** Hidden motives such as excitement, martyrdom or fear of success drive trading results. Tharp found that half of his clients had internal conflicts of this kind. For a bot, the equivalent is objectives that are misaligned or not stated.
- **Keep a balanced life.** Marcus says traders who last have a life outside trading. Otherwise they overtrade or get too upset by temporary failures.

---

## 5. Claims to check against evidence

| Claim | Who | Assessment / how to test |
|---|---|---|
| Returns such as 2,500x in 10 yrs, 250,000%, 87%/yr, triple digits five years running, 25%/month, 99% winners and no losing weeks | Marcus, Seykota, Kovner, Jones, Preface, Weinstein | **Survivorship and selection bias.** The book interviews winners chosen after the fact from 1970s-80s commodity bull and inflation markets. Almost none of these records is audited, and Schwager himself could not verify Weinstein's. Marcus admits buy-and-hold "couldn't lose" in that period. Treat these numbers as anecdotes. They are the opposite of the retail base rates the bot's brief cites (97% of Brazilian day traders lose; 74-89% of EU CFD accounts lose; Barber and Odean's heavy traders earn 11.4% against the market's 17.9%). |
| Trend following is over and doomed by crowding (1988) | Marcus, Kovner, Bielfeldt, Dennis | **Partly wrong on timing, right on the mechanism.** Trend following had strong periods afterwards (for example 2008) and long-horizon studies such as Hurst, Ooi and Pedersen's "Century of Evidence" find it persists over a century of data. It also had a weak decade in the 2010s. This matches McLean and Pontiff's result that edges shrink after publication. **Test:** subperiod performance of sleeve A and D signals before and after publication (Faber 2007) and by decade. |
| Stocks are close to random and do not trend like commodities | Dennis | **Conflicts with later research.** Time-series momentum exists in equity index futures (Moskowitz, Ooi and Pedersen 2012), 12-1 cross-sectional stock momentum is documented (Jegadeesh and Titman 1993), and 1-month stock returns reverse. Dennis's single-stock observation partly fits the short-term reversal effect. **Test:** sleeve C results versus a same-universe 12-1 momentum baseline. |
| Stock indexes chop more than commodities, and trend systems on them need very wide stops | Kovner | Plausible and consistent with RSI(2) dip buying having worked on indexes. **Test:** compare sleeve B's 3 ATR disaster stop with sleeve C's 2 ATR stop by holding period. |
| Overbought/oversold indicators do not prove out in testing | Hite, O'Neil | **Directly challenges sleeve B (RSI(2) < 10).** The evidence for RSI(2) (Connors, around 1993-2008) comes later than this book, and short-term index reversal has reportedly weakened since publication. **Test:** sleeve B expectancy by year and before/after 2008, net of 5 bps per side, against buy-and-hold SPY over the same exposure. |
| CANSLIM: the best winners had EPS +70%, RS 87, fewer than 25M shares, bought at new highs; P/E does not matter; "diversification is a hedge for ignorance" | O'Neil | **Built from past winners with no control group** (look-ahead and survivorship). Parts are backed by later research: post-earnings drift, 52-week-high momentum (George and Hwang 2004) and price momentum. "P/E does not matter" conflicts with the value premium, though value was weak from 2007 to 2020. Concentration raises idiosyncratic risk. The small-share-count effect sits in illiquid names with high costs. **Test:** does adding an EPS-growth or earnings-surprise filter to sleeve C improve out-of-sample expectancy? The bot's 40 megacaps cannot meet the "S" criterion at all. |
| Breakouts with no news, or with worse fills and gaps, are more reliable | Kovner | Testable. **Test:** in sleeve C, split breakouts by gap size and by whether there was an earnings date in the prior 2 days, then compare 20-day forward R. |
| Stocks at new highs have less overhead supply and run further | O'Neil, Ryan | Consistent with 52-week-high momentum research. Already built into the trend template's "within 25% of the 52-week high". |
| 95% of profits come from 5% of trades | Dennis | Plausible for trend systems because returns are skewed to the right. **Test:** share of sleeve C and D P&L from the top 5% and 10% of trades. If profits are not concentrated, the exits may be cutting winners short. |
| Markets trend only about 15% of the time | Jones | Unsourced figure that depends on the definition. Do not rely on it. |
| 90% of options expire worthless, so always sell options | Rogers | **Commonly repeated myth.** OCC/CBOE data show most options are closed before expiry and only a minority expire worthless. Not relevant, since options are banned. |
| Losing when markets close within 2% of the day's high or low 20% of the time "is mathematically impossible by chance" | Schwartz | **Statistically unsupported.** Closes near the extremes are common in random walks. Ignore. |
| After 2-3 Fed discount-rate hikes the market "runs into trouble" | O'Neil | Folk rule ("three steps and a stumble"); the evidence is mixed. Low priority to test. |
| Friday strong close predicts Monday follow-through | Dennis, Saliba | Weekday-effect research is weak and mostly arbitraged away. **Test cheaply:** SPY Monday return conditional on Friday closing in the top or bottom 10% of its range. |
| 20 Turtles averaged about 100% a year | Dennis | Leveraged futures in a favourable period, self-reported. Later public Turtle results were mixed, and Dennis's own public funds hit about a 50% drawdown in 1987-88 (in the book). This shows even large edges come with deep drawdowns. |
| Price limits and program trading caused or worsened the 1987 crash | several | Mostly beside the point for the bot. The appendix itself argues that arbitrage-style program trading was not the cause. |
| Weinstein's near-perfect win rate from gut-timed indicator mixes | Weinstein | **Unverifiable** (Schwager says so). The approach cannot be reproduced or tested. Exclude it. |

**Overall caveat.** A book of winners cannot tell you how often the same behaviour fails. Schwager says so in the Prologue, noting that with enough traders some will win by chance. Use the book for **risk and process rules**, which are cheap and robust, and not as evidence that any particular edge exists.

---

## 6. Fit with the bot

Bot facts that decide fit: small account (~$10k simulated), long only, no leverage, no shorts or options, daily bars, systematic sleeves plus a "Claude book" with bounded discretion, and a target of 6-10% a year with drawdown under 15-20%.

### 6.1 Already done (keep as is)
| Book lesson/rule | Where the bot has it |
|---|---|
| Small fixed % risk sized from the stop (S1, X1) | `risk_pct_default 0.005` (more conservative than Hite's 1%), with `qty = risk / (entry - stop)` in sleeve C. Keep 0.5%; it fits Kovner's "undertrade". |
| Hard risk ceiling (S2) | `risk_pct_hard_cap 0.02`, matching Kovner's 1-2% upper bound. |
| Do not raise size until proven (S5) | `risk_pct_validated 0.01` only after 100 or more trades with positive expectancy, a stricter version of Schwartz's rule. |
| Correlated positions are one bet (S3, lesson 3) | `correlated_positions: rho_60d 0.7, max_count 2` plus `max_open_risk_heat 0.06`. |
| Stock stop max around 7-8% (X2) | Sleeve C `max_stop_distance_pct 0.08` (O'Neil's is 7%; see 6.2). |
| Never widen stops or average down (P7, X6) | `never_widen_stop`, `no_averaging_down`. |
| Cut size in drawdown, stop at worst (P3, P6, Seykota's gradual reduction) | Breakers: halve risk at -10%, no new entries at -15%, halt at -20%; daily 2R and weekly 5R caps. |
| Time stop (X5) | Sleeve B 10-day time stop. |
| Trend filter and market gate (E1, E5) | Sleeve A 10-month SMA; B requires close > 200-day; C requires SPY > 200-day, the trend template and regime gating. |
| Breakout on a volume surge at new highs (E2) | Sleeve C: close > 50-day pivot high on 1.5x volume, which matches O'Neil's "at least 50% above average". |
| High relative strength (E4, part) | `rs_min_percentile 70`, lower than O'Neil's 80 and Ryan's 90. |
| Volatility regime filter (E12, Hite's lights) | Regimes: `bull_volatile` halves B/C, `bear` turns them off (a yellow/red analogue); sleeve A and D are volatility-targeted. |
| Wait and do nothing (lesson 10) | Playbook brief: "Doing nothing is often the best decision"; `max_orders_per_day 10`; rebalance band 20%. |
| Robust multi-parameter trend (lesson 9, P8) | Sleeve D uses a 7-lookback Donchian ensemble rather than one optimized lookback. |
| Journal (lesson 17) | `journal.jsonl` plus Claude `journal_note` and rationale per target. |

### 6.2 Worth adding (test first, then add if it holds up)
| Proposal | Sleeve / policy | Why and how |
|---|---|---|
| **Failed-breakout exit** (X4): exit sleeve C if `close < pivot` within the first N (e.g. 10) days after entry, or sell half as the book says (exit fully for simplicity, since positions are small). | C, `strategies.sleeve_c` exit block | Sleeve C currently exits only on the stop, a 10-day low or the 50-day SMA. A failed breakout can drift down to the 8% stop. Ryan's rule cuts those losers earlier. Test the effect on expectancy and win rate. |
| **Extension filter** (E3): skip entry if `close > pivot * 1.05` (O'Neil allows up to 10%). | C entry | Sleeve C enters on the breakout day, but a gap can put the close far above the pivot and make the stop wide. This is cheap to add. |
| **Time stop for C** (X5): exit if a C position has not reached +1R, or is below entry, after 15-20 trading days. | C, `risk_policy.per_trade.time_stop_days.C` | Dennis and Jones use this. It frees slots on the capped 5 positions. Test against the no-time-stop version, since it may cut the rare big winners. |
| **Earnings blackout** (E11): no new C entry within 3 trading days before a scheduled earnings date; optionally cut to half size before earnings. | C, new filter (needs an earnings calendar) | Jones's and Schwager's point about not risking money before key reports. Single-stock earnings gaps can jump the 2 ATR stop and turn a 0.5R trade into a 2-3R loss. |
| **Monthly loss cap** (P1): if month-to-date P&L <= -4% of starting-month equity, no new entries for the rest of the month. | `risk_policy.breakers.monthly_loss_pct` | Adds Jones's "never a double-digit month" as a calendar layer between the weekly 5R and the drawdown breakers. Cheap. |
| **Consecutive-stop gate** (E5, part): after 5 consecutive C stop-outs, block new C entries until SPY makes a new 20-day high, or for 10 days. | C / regime | O'Neil and Ryan used strings of stopped-out breakouts as a sign of a market top, before index filters react. This reacts to the bot's own results. |
| **Post-big-win size check** (P5, lesson 7): after equity rises more than X% in 20 days, keep risk at default (it already is) and log an "overconfidence" flag to the Claude book. | Claude book prompt | Mostly a prompt and discipline addition. Code already prevents size increases. |
| **Rule "no override" for the Claude book** (lesson 8): rules-book signals stand; Claude can only *skip* or *reduce*, never add or enlarge beyond rules, and must log a reason; track the P&L of overrides versus the rules book. | Claude book / `engine.py` | Seykota's and Hite's stories are the case for measuring whether discretion adds value. If Claude's overrides lose over 50 or more instances, disable them. |
| **Evaluation metrics** (lesson 15): report (a) the share of rolling 6, 12 and 18-month windows with positive return (Hite); (b) the share of P&L from the top 5% of trades (Dennis); (c) rule-adherence rate (Tharp). | reporting / backtests | Keeps judgment focused on process and makes it obvious when exits cut winners short. |
| **Robustness check on parameters** (lesson 9): for every sleeve, show backtest results for the neighbouring parameter values (e.g. RSI entry 5/10/15, pivot 40/50/60, SMA 9/10/11 months) and reject any sleeve whose result depends on one exact value. | backtest / tests | Dennis and Hite. Especially relevant given the rule in the brief to halve backtests. |
| **Tighter stock max loss, 7% vs 8%** (X2) | C `max_stop_distance_pct` | Low priority. A 1-point difference is noise unless a test shows otherwise. O'Neil's number is folklore, not a derived result. |

### 6.3 Reject (does not fit a small, long-only, daily, systematic account)
| Idea | Source | Why reject |
|---|---|---|
| Pyramiding and "bet 5-6x on the A+ setup", "raise on the good poker hands" | Marcus, Bielfeldt, Steinhardt, Schwager's doubled trade | Conviction sizing is where most of the book's blow-ups came from. The bot cannot measure conviction reliably, and Alpha Arena losses came from exactly this. Keep fixed-fractional sizing. |
| Contrarian "sell hysteria", fading crowds, variant perception, holding losers on fundamental conviction without stops | Rogers, Steinhardt, Jones (turning points) | Not codeable, needs shorting, and conflicts with stops. Schwager himself labels Rogers's method dangerous for unskilled traders. |
| Holding a losing position while "the thesis is intact" / "first loss is best loss only if analysis flawed" | Rogers, Steinhardt | Directly conflicts with `never_widen_stop` and the hard stops. |
| Shorting, spreads, cross-rate pairs, "if long something, be short something" | Kovner, Rogers, Steinhardt, Saliba | Policy: long only, no shorts or options. The hedging idea is partly covered by the BIL/IEF allocation in sleeve A. |
| Options structures (butterflies, "explosion" positions, selling calls) | Saliba, Rogers | Options are banned. |
| Intraday tape reading, scalping, pit order flow, reading other traders, round-the-clock currencies | Baldwin, Gelber, Weinstein, Marcus, Kovner | The bot runs once a day on daily bars. Costs and latency would destroy any edge (Tharp is sceptical of short-term trading too). |
| CANSLIM small-cap focus (< 25M shares, OTC names, "trade the small ones") | O'Neil, Marcus | Liquidity and cost risk, and the edge sits in microcaps. The bot's universe is 40 megacaps. At most, use the EPS-growth component as a *test* filter (see section 5). |
| Extreme concentration ("diversification is a hedge for ignorance") | O'Neil | A 10-20% sleeve with 5 slots is already concentrated. More concentration raises idiosyncratic and gap risk against the 15-20% drawdown target. |
| Climax exits on consecutive limit-up days (X7) | Marcus | Futures-specific. An equity "blow-off" exit would cut the right-tail winners that Dennis says pay for everything. Consider only if the top-5% P&L check shows profits are being given back after climaxes. |
| Friday-close and weekday rules (X9) | Dennis, Saliba | Weak modern evidence. Test cheaply if curious but do not add without out-of-sample support. |
| Dreams, gut feel, "into-wishing", Elliott Wave, 1929 analogs, Fibonacci | Seykota, Tharp, Jones, Weinstein, Schwager | Not testable. Keep them out of Claude's rationale; the prompt should ask Claude to cite rule-based evidence only. |
| Discretionary override of system signals as a "creative outlet" | Seykota (admits it is roughly breakeven to negative) | For the bot, overrides should be measured and constrained, not encouraged (see 6.2). |
| Shutting everything down for 3-4 weeks after a losing streak | Marcus | Crude for a systematic account, and the drawdown breakers already do this with defined thresholds. Arbitrary pauses would cause missed trend entries in sleeve A, which Dennis considers the worst error. |

### 6.4 Priorities
1. Add the **failed-breakout exit** and **extension filter** to sleeve C (small code change, directly from O'Neil/Ryan, testable).
2. Add a **monthly loss cap** to `risk_policy.yaml` breakers.
3. Add **Claude-override tracking** and the rule that Claude may skip or shrink positions but never enlarge them.
4. Run the **sleeve B decay test**. Hite's and O'Neil's scepticism about overbought/oversold indicators is the most important challenge in this book to a current sleeve.
5. Add **rolling-window and top-5% P&L metrics** to reporting.
