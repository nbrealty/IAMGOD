# Options playbook for beginners

*A plain-English course for the owner, 28 September 2026. Built from five research notes written today (strategy catalog, greeks and IV, reading charts, short-dated trading, execution and risk), with each key claim checked against its source and corrected where needed. Examples use SPY at about $770. Numbers marked **model** come from our own Black-Scholes calculation, not from market prices. Numbers marked **real** come from the 25 Sep 2026 SPY chain in `reports/Options rulebook.md`. Nothing here changes a rule. Book O's rules (OPT-5 bans entries under 25 DTE) still apply to book O. The same-day lab in section 8 is a separate, owner-requested paper experiment (`trading/lab/options_lab.py`).*

**The five things to remember**
1. An option is a bet with a **deadline**. You can be right about direction and still lose if the move comes too late or is too small.
2. Every strategy is a bet on three things: **direction** (delta), **size of the move** (gamma and vega) and **time** (theta). Choose the strategy from your view.
3. **Costs decide most short-dated results.** Retail traders lost over $125M on same-day S&P options from 2021 to 2023, and most of that was bid-ask costs.
4. Charts are good at telling you **how big** moves will be and bad at telling you **which way** they will go.
5. **One day of paper trading tests the plumbing, not the skill.** All trades made on one day ride the same SPY path, so the day counts as about one data point.

---

## 1. How an option works

- A **call** is the right to **buy** 100 shares at a fixed price (the **strike**) until the **expiry** date. A **put** is the right to **sell** at the strike.
- The buyer pays a **premium** up front. The seller keeps the premium but takes on the obligation.
- **One contract covers 100 shares**, so a quoted price of $12.08 costs $1,208.
- **Intrinsic value** is what the option would be worth if exercised now. **Extrinsic (time) value** is the rest of the price.
- SPY options are **American** (they can be exercised on any day) and **physically settled** (shares change hands). SPX and XSP options are European and settled in cash.

**Worked (model).** SPY $770. You buy the $770 call with 30 days to expiry (DTE) for $12.08, which costs $1,208.
- Breakeven at expiry = strike + premium = **$782.08**.
- SPY at $790 on expiry: the call is worth $20, so you make $2,000 − $1,208 = **+$792**.
- SPY at or below $770 on expiry: the call is worth $0, so you lose **−$1,208**, the most you can lose.
- SPY unchanged after 7 days: the call is worth less, because time value leaks away every day (theta, section 3).

**The seller's side.** Whoever sold you that call has the mirror image of your position: a gain of at most $1,208 and an unlimited loss. That is why we **never sell an option without buying another one to cap the risk** (defined risk).

## 2. Reading an option chain

A chain shows one expiry. Each row is a strike, usually with calls on the left and puts on the right. **Real row:** the SPY $741 put expiring 6 Nov 2026, as of 25 Sep 2026 with SPY at $771.35 and 42 DTE.

| Column | Value | How to read it |
|---|---|---|
| Symbol | SPY261106P00741000 | Underlying, expiry (YYMMDD), P or C, strike × 1000 |
| Bid / Ask | $4.74 / $4.96 | You **sell** at the bid and **buy** at the ask |
| Mid | $4.85 | A fair-value guess, not a promised fill |
| Spread | $0.22 = 4.5% of mid | Roughly what a round trip costs you |
| Last | (varies) | Can be hours old. **Never price from it** |
| Volume / Open interest | e.g. 1,200 / 15,000 (illustrative) | Contracts traded today / contracts still open. More means easier fills |
| IV | 15.9% | The implied volatility that reproduces the mid. Higher than at the money because of skew |
| Delta | −0.20 | The put gains about $0.20 for each $1 SPY falls |

**The checklist code runs on every row:** (1) the quote is live: bid > 0, the quote is recent and bid < ask; (2) the spread is narrow (rulebook: ≤ max($0.05, 5% of mid)); (3) there is depth (OI ≥ 500); (4) volume far above OI means new positions today, but it does not tell you the direction; (5) read delta and IV. On Alpaca's free plan the feed is **indicative**, not the real OPRA quotes. Every report must say so.

## 3. Greeks and implied volatility

**The greeks are "what if" numbers from a model.** Model example: SPY $770, $770 call, 30 DTE, IV 12.75%, price $12.08.

| Greek | Value | Plain meaning |
|---|---|---|
| Delta | +0.53 | SPY +$1 → the call gains about $0.53 |
| Gamma | 0.014 | SPY +$1 → delta rises by 0.014 (moves speed up gains for buyers and losses for sellers) |
| Theta | −$0.22/day | One day passes with nothing else changing → −$0.22 ($22 per contract) |
| Vega | $0.88 | IV up 1 point → +$0.88 |
| Rho | $0.33 | Rates up 1 point → +$0.33 (barely matters under 60 days) |

- **Delta is only roughly the chance of finishing in the money.** It is a "risk-neutral" number that includes an insurance premium, and the chance of *touching* the strike before expiry is roughly double.
- **IV is the market's price of movement.** One standard deviation (SD) over T days ≈ price × IV × √(T/365). For SPY $770 at 12.75% that is ±$28 over 30 days. **Rule of 16:** IV ÷ 16 ≈ the typical daily move in %, so 12.75% ≈ 0.8% ≈ $6 a day. An at-the-money straddle costs about 0.8 × the one-SD move.
- **IV rank vs IV percentile.** Say IV ranged from 12% to 38% last year and is 18% now. IV rank = (18 − 12)/(38 − 12) = 23. If IV was lower on 150 of 252 days, IV percentile = 60. A single spike squashes IV rank, so **prefer IV percentile**. Neither one predicts that IV will fall.
- **Skew.** Since the 1987 crash, low-strike index puts carry higher IV than calls. In the project's SPY calibration at VIX 15, a put 10% below spot is priced at 21.6% IV against 12.75% at the money. Skew cuts a put credit spread's credit from $0.41 (flat IV) to $0.26 (model).
- **IV crush.** IV rises into a known event and drops right after it. In Dubinsky and Johannes's study, Intel's front-month IV went from 71% to 43% the day after earnings. Buyers can be right on direction and still lose. For SPY, events move IV only a point or two.
- **Near expiry, gamma and theta explode** (model, ATM $770 call). Theta: $0.22/day at 30 DTE, $1.05 at 1 DTE. Gamma: 0.014 at 30 DTE, 0.31 with 1.5 hours left, so a $1 SPY move flips the option between "almost stock" and "almost worthless".
- **The seller's asymmetry** (model, book O's $2 put spread at 35 DTE): theta +$0.26/day, but a 1% SPY drop costs about $11, which is **about 40 days of theta**.

## 4. Reading charts: evidence vs folklore

For an options trader, a chart mostly answers **"how far and how fast?"** Our own checks used SPY from 2016 to 2026, one decade and in-sample, so they illustrate rather than prove.

| Tool | Verdict | Why |
|---|---|---|
| Volatility clustering | **Strong** | Big days follow big days. The autocorrelation of SPY's absolute returns is 0.35 at one day; for returns it is about 0 |
| IV vs later realised moves | **Strong** | VIX was above the next month's realised volatility on 84% of days. SPY finished inside the 30-day ±1 SD band 81.5% of the time (a normal distribution gives 68%), but the worst month was −7 SD (Feb–Mar 2020) |
| 200-day moving average | **Moderate as a regime label** | Below it, SPY's next-month volatility averaged 21.5% against 12.7% above it. As a direction signal it is weak |
| Volume | **Moderate for size** | Volume spikes come with big moves (correlation 0.48) and not with direction (−0.02) |
| ATR | A definition | Median ATR14 was 1.08% of price, about the same as VIX/16 |
| VWAP | **A good yardstick, no evidence as a signal** | Use it to judge your own fills |
| Opening range | **Size yes, direction no** | The first 30 minutes' range correlates 0.77 with the day's range; its direction matched the rest of the day only 51% of the time. Breakout profits vanish after about 2¢/share of costs |
| Intraday momentum | **Weak on SPY since 2016** | The published effect appears before costs and when dealers are short gamma. On SPY we found a small reversal when VIX < 20 |
| Support and resistance | **Weak** | Random levels "held" 56% of the time (Osler 2000). Round numbers attract orders, and stops speed up the break |
| Chart patterns, candlesticks | **Folklore** | Careful tests find nothing after costs. On SPY, "bullish" hammers were followed by *below-average* returns |

**How to read a trade chart (P&L over time).** Real case: $741/$739 put spread, credit $22, max loss $178. At SPY $741, the P&L is −$45 today, −$53 at 21 DTE, −$61 at 7 DTE and +$22 at expiry. The expiry line is a cliff and the earlier lines are ramps. SPY *touched* a level like this on 27.8% of start dates but *finished* below it on only 9.1%.

## 5. Strategy catalog

Signs: + helps, − hurts, ≈0 small or depends. Per OIC, time helps and higher IV hurts the **credit (short)** versions of spreads, condors and butterflies. The **long (debit)** iron butterfly and condor have the reverse effects. The Alpaca level is shown in brackets after each strategy's name.

| Strategy | View | Max loss | Max gain | Breakeven (expiry) | Δ Γ Θ Vega | When to use | Common mistake |
|---|---|---|---|---|---|---|---|
| Long call [2] | Up, soon, a lot | Premium | Unlimited | Strike + premium | + + − + | Your move forecast beats the IV | Far-OTM "lottery tickets"; buying before an event and losing to IV crush |
| Long put [2] | Down, soon, a lot | Premium | Strike − premium | Strike − premium | − + − + | Hedge or crash bet | Paying the ask on wide quotes; holding into the last week |
| Bull call spread (debit) [3] | Up, moderately | Debit | Width − debit | Long strike + debit | + ≈0 ≈0/− ≈0 | A directional view with a fixed cost | Short strike beyond a realistic target |
| Bear put spread (debit) [3] | Down, moderately | Debit | Width − debit | Long strike − debit | − ≈0 ≈0/− ≈0 | Same; skew makes it relatively cheap | Forgetting that full value arrives only at expiry |
| Bull put spread (credit) [3] | Not down | Width − credit | Credit | Short strike − credit | + − + − | Harvesting the volatility premium with a capped tail | Tiny credits that costs eat; rolling losers |
| Bear call spread (credit) [3] | Not up | Width − credit | Credit | Short strike + credit | − − + − | Same, above the price (less premium: skew) | Short ITM call the day before an ex-dividend date |
| Iron condor (short) [3, 4 legs] | Stays in a range | **Wider wing** − total credit | Total credit | Short put − credit; short call + credit | ≈0 − + − | Quiet market, no event | Paying 4 legs of costs; adjusting the tested side again and again |
| Iron butterfly (short) [3, 4 legs] | Pinned at one price | Wing − credit (wider wing if unequal) | Credit, only at the body | Body ± credit | ≈0 −− + − | Very quiet market | Reading a good reward-to-risk ratio as a good trade: the breakevens are close |
| Calendar (long) [3, verify margin] | Quiet now, move or IV up later | About the debit | Largest at the strike on the near expiry | Depends on IV | ≈0 − + + | Near-term IV rich compared with later months | Forgetting it is long vega: an IV drop erases the theta gains |
| Diagonal (long) [3?, not named] | Slow drift one way | About the debit, if the long leg covers the short | Depends on IV | Varies | ± − ≈0/+ + | Stock replacement | Rolling the short strike past the long strike |
| Covered call [1] | Flat to slightly up; you own the stock | Stock to 0, minus premium | Strike − cost + premium | Cost − premium | + − + − | Overwriting stock you hold | Calling the premium "income" while carrying almost full stock risk |
| Cash-secured put [1] | Flat to up; happy to buy lower | Strike − premium | Premium | Strike − premium | + − + − | Buying stock at a discount | One SPY put ties up about $77k |

**Twins.** A bull call spread and a bull put spread with the same strikes have almost the same payoff; so do a covered call and a cash-secured put. **Pick the twin with the cheaper quoted cost.** Credit versus debit is not a view.

**Benchmark (Cboe, before costs and taxes, partly backtested).** CNDR sells about 0.20-delta SPX puts and calls, buys about 0.05-delta wings and holds the rest in T-bills. It returned 0–2% in 59% of months. Its worst peak-to-trough drawdown, measured at month-ends, was 19% over about 35 years, against 47.1% for the iron butterfly index (BFLY) and 51% for the S&P 500. Over 2006–2019 it had the mildest drawdown (−13.7%) of the 13 series on Cboe's chart; BFLY was not on that chart. (That the T-bill collateral cushions these drawdowns is our inference, not Cboe's claim.)

**What Alpaca allows** (docs checked today). **Level 1:** covered calls and cash-secured puts. **Level 2:** adds buying calls and puts. **Level 3:** adds spreads; the docs name call and put spreads, and Alpaca's Learn page gives examples such as condors, butterflies, long straddles, long strangles and long calendars. **Paper accounts are approved automatically.** A multi-leg `mleg` order takes **2 to 4 legs**. A positive `limit_price` is a debit and a negative one is a credit. **Every short leg must be covered inside the same order.** Leg ratios must be in lowest terms. **No stock legs**, so covered calls go in as separate orders. **Margin** comes from the "universal spread rule": premiums are ignored, the requirement is the worst combined payoff at expiry (never below $0), and it is computed separately for each expiry date. That implies an iron condor is margined on one wing, but this is a derivation to confirm on paper. **Stop orders work on single legs only.** A spread's stop must be watched in code and then closed with an `mleg` limit order (a market order is allowed but risky on wide quotes).

## 6. Short-dated and intraday options: what the evidence says

- **Mostly a cost game.** Retail lost $241k a day in 0DTE SPX from 2021 to 2023. Depending on how you count, 60–76% of that was bid-ask costs. **Buyers of single options lost; sellers of premium made money on average; multi-leg trades did better** (Beckmeyer et al.).
- **Limit orders change the picture.** Customers who used midpoint limit orders filled about 60% of the time and paid about $0.021 against $0.05 for a market order (SEC staff study).
- **The same-day premium is tiny.** The median 0DTE variance premium is about 0.0011% of the index: **less than one penny per SPY share**, so one tick of slippage wipes it out (Vilkov 2026). Most of the options premium is earned **overnight**, not during the session (Muravyev and Ni).
- **The tails are large.** On the worst 1% of days, near-the-money 0DTE structures lost about 0.6–1.6% of the index: about $450–$1,200 per SPY-sized contract unless the **width** caps it. Width, not a stop, is the real risk control.
- **Spreads widen during the day.** In SPX 0DTE the quoted spread was 9.6% with 3–24 hours left and 19% in the **last hour**, and 98% for options more than 2% OTM. Spreads are lowest and steadiest **10:00–14:00 ET**. SPY trades in penny ticks, so SPX percentages do not carry over; we must measure SPY ourselves.
- **No published study finds a lasting edge after costs.** One mispricing paid until 2022 and then vanished. The best 2026 result depends on a put *ratio* spread that our defined-risk rule forbids; iron condors and butterflies had a net Sharpe of **−0.20**.
- **Alpaca expiry-day rules.** Orders on expiring SPY options are rejected after 15:30 ET, and expiring positions are liquidated from 15:45. The lab avoids this by never holding a same-day expiry and closing by 15:50.
- **Paper is wrong in both directions.** It is **too kind**: no fees, no dividends, no size check, early assignment undocumented. It is **too harsh**: mid-priced limits fill only when the quote moves through them, so fills are adversely selected.

## 7. Execution and risk checklist

**Before the open**
- [ ] The account is **paper** (code refuses any live URL), options level ≥ 3, and there are no stray positions.
- [ ] Calendar checked: FOMC, CPI, jobs report, expiry day, the day before a SPY ex-dividend date (next one: **18 Dec 2026**, so avoid short ITM calls on 17 Dec).
- [ ] Caps in code: max loss per trade, total open risk, daily loss cap, number of opens, last-entry time, flat-by time.
- [ ] Chain logger running; feed labelled indicative or OPRA; journal started with the prompt and code versions.

**Before each trade**
- [ ] Not in the first 15–30 minutes. Defined risk only, sent as **one** `mleg` limit order, with the sign checked (credit negative).
- [ ] Every leg: bid > 0, fresh quote, leg spread ≤ $0.20. Round trip at natural ≤ 20% of the credit.
- [ ] **Size by max loss:** contracts = floor(cap ÷ ((width − credit) × 100 + exit cost)). If that gives 0, there is no trade. Never round up.
- [ ] Target, stop and time exit written down **in dollars** before entry.
- [ ] **Walk the price:** start at mid, step $0.01 toward natural every 60 s after refreshing the quotes, give up at most half the combo width, stop after 10 steps, and log no-fills. Never chase.

**In the trade and at the exit**
- [ ] Stops are triggered by **SPY's price** or by two marks in a row, not by one jumpy quote. Never move the stop, never add to a position, never roll.
- [ ] Close as one `mleg`; **never leg out**, which would leave a naked short. After the close, check positions for stray stock.
- [ ] Report P&L three ways: paper fill, cost model (mid ± half spread + $0.04/contract/side), and "fill-rate honest" (include the later P&L of trades that did not fill).

**The arithmetic you cannot escape.** Break-even win rate = loss ÷ (win + loss). A 50%-of-credit target with a stop at 1× the credit needs a **67%** win rate before costs. Hold-to-expiry at 20% credit on width needs **80%**. With 1% risked per trade, ten straight losses cost 9.6% of the account; with 5% per trade, **40%**. Kelly sizing is useless here: a 2-point error in the win rate swings it from "bet 10%" to "don't trade".

## 8. Lab strategies: today's paper experiments

**Common frame for all five** (matches `trading/lab/options_lab.py` where marked ✓):
- SPY in the examples (the lab also allows QQQ ✓), paper only. Expiry 1–10 DTE, never same-day ✓. Width $2 ✓.
- Size = floor(cap ÷ max loss per contract) ✓. **Proposed change:** add the estimated exit cost to the max loss before dividing, as the section 7 formula does.
- Max loss ≤ **$250 per trade** and ≤ **$750 total** ✓; at most 4 opens ✓. Entry checkpoints 10:15, 11:30, 13:00 and 14:15 ET ✓; no entries after 14:30 ✓.
- Strike pick: the listed strike whose |delta| is nearest the target, from the Alpaca snapshot greeks ✓. Skip the trade if the leg spread is > $0.20 or the bid is 0 ✓.
- Exits: take profit at **50% of max gain** ✓; stop at **50% of max loss** ✓; time exit starts 15:35, hard close 15:45, last resort 15:48, everything flat by **15:50** ✓.
- **Proposed stop change:** also stop if SPY trades through the short strike, and require the mark stop to hold on two snapshots at least 60 s apart.

**Model example prices** (SPY $770, 3 DTE, IV about 14% with a mild put skew; real quotes will differ; the sizes shown include the exit cost):

| # | Name | Exact entry rule (code-checkable) | Strikes by delta | Model price → size | Status |
|---|---|---|---|---|---|
| L1 | **Trend-day credit spread** | At a checkpoint with ≥ 45 minute bars: spot > 30-min opening-range high **and** > VWAP → bull put; spot < OR low **and** < VWAP → bear call. Skip if \|60-min move\| ≥ 0.4% (that goes to L3) | Short ≈ 0.30Δ, long $2 further OTM | Short 764P / long 762P: credit $0.45, max loss $155 + ~$4 exit → **1 contract** | ✓ in lab |
| L2 | **Clock control (no signal)** | At 10:15 exactly, unconditionally: bull put spread | Short ≈ 0.30Δ put, long $2 lower | Same as L1 → 1 contract | Shadow-log, or send if the cap allows |
| L3 | **Momentum debit spread** | \|SPY return over the last 60 min\| ≥ 0.4% → bull call spread (up) or bear put spread (down) | Long ≈ 0.50Δ (ATM), short $2 further OTM | Long 770C / short 772C: debit $0.92, max loss $92 + ~$4 → **2 contracts** ($192) | ✓ in lab |
| L4 | **Cheaper twin** | Whenever L1 fires a bull put at strikes K1/K2, also price the bull call spread at the same K1/K2 at natural. Send whichever has the lower (natural − mid) cost as a share of max gain | Same strikes as L1 | Log both combo quotes | Needs code (pricing and log only is easy) |
| L5 | **Range-day iron condor** | At 13:00: SPY inside the opening range, \|60-min move\| < 0.2%, VIX < 20, no FOMC/CPI today | Short puts and calls ≈ 0.20Δ, wings $2 further out | 762P/760P + 778C/780C: credit $0.72; max loss = wider wing − credit = $128 + ~$8 → **1 contract** | **Shadow only**: the lab allows 2 legs, and this needs 4 |

**What each can and cannot tell us after one day**

| # | Can show today | Cannot show today |
|---|---|---|
| L1 | Whether the `mleg` credit order, sign, walk and 50/50 exits work; real SPY spread costs at each checkpoint | Whether opening range + VWAP has an edge. Its published evidence is weak after costs, and all of today's trades share one path |
| L2 | A baseline for L1: same structure, no signal | Whether the signal beats the clock. That needs hundreds of paired days |
| L3 | Debit-order mechanics; how fast theta eats a 3-DTE debit spread over a session; slippage on a near-ATM spread | Whether intraday momentum persists (on SPY since 2016 it did not, net) |
| L4 | Which twin is cheaper **today** at the same strikes, and by how many cents | Whether that holds across days, volatility regimes and strikes |
| L5 | Four-leg quote costs versus two, measured on real quotes; how the condor's mark reacts to SPY moves through the afternoon | Anything about condor returns. Cboe's CNDR history is monthly and before costs; Vilkov's 0DTE condors had a negative net Sharpe |

**Honest scorecard for today.** Twenty trades today are about **one** observation. Telling a +0.03R edge from zero needs about 1,100 trading days. Today measures **plumbing, fills, costs and timing**, not whether the agent is good. Treat any profit or loss as noise.

**Mechanics tests to run alongside (one contract each, paper):** (a) a 2-leg SPY 30/60-day call calendar: is it accepted, and what margin is charged? (b) two SPY call diagonals, one covered and one with the strikes reversed: accepted or rejected? (c) one `mleg` with 100 SPY shares plus a short call: are stock legs still rejected? (d) a far-from-market limit order during a fast move: does paper fill at your limit or at a better quote? Log each answer in the rulebook's ALP section.

## 9. Sources

**Primary, read:** OIC (OCC) [Options Strategies Quick Guide](https://www.optionseducation.org/getattachment/007fe864-029a-490d-8dc1-3b58bd558f64/options-strategies-quick-guide.pdf); OIC pages on [short condor](https://www.optionseducation.org/strategies/all-strategies/short-condor), [short iron butterfly](https://www.optionseducation.org/strategies/all-strategies/short-iron-butterfly), [long iron butterfly](https://www.optionseducation.org/strategies/all-strategies/long-iron-butterfly), [long call calendar](https://www.optionseducation.org/strategies/all-strategies/long-call-calendar-spread-call-horizontal), [bull call spread](https://www.optionseducation.org/strategies/all-strategies/bull-call-spread-debit-call-spread), [greeks](https://www.optionseducation.org/advancedconcepts/understanding-options-greeks), [Rule of 16](https://www.optionseducation.org/news/understanding-the-rule-of-16-in-plain-terms), [IV crush](https://www.optionseducation.org/news/the-crush-is-real), [exercise](https://www.optionseducation.org/optionsoverview/exercising-options) · Alpaca [options trading](https://docs.alpaca.markets/docs/options-trading), [level 3](https://docs.alpaca.markets/docs/options-level-3-trading), [level 3 strategies](https://alpaca.markets/learn/level-3-options-trading), [alpaca-py requests](https://alpaca.markets/sdks/python/api_reference/trading/requests.html), [create order](https://docs.alpaca.markets/reference/postorder), [paper trading](https://docs.alpaca.markets/docs/paper-trading), [0DTE cutoffs](https://alpaca.markets/support/what-are-the-cutoff-times-for-trading-0dte-options-on-alpaca) · Cboe [BFLY and CNDR](https://www.cboe.com/insights/posts/benchmark-indices-series-volatility-management-with-cboes-bfly-and-cndr-indices/), [benchmark factsheet](https://cdn.cboe.com/resources/indices/documents/benchmarks-fact-sheet.pdf), [SKEW white paper](https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf), [VIX backwardation](https://www.cboe.com/insights/posts/inside-volatility-trading-is-vix-backwardation-necessarily-a-sign-of-a-future-down-market), [complex orders](https://www.cboe.com/markets/us/options/trading/complex-orders) · FINRA [assignment](https://www.finra.org/investors/insights/trading-options-understanding-assignment).

**Papers, read:** Beckmeyer, Branger and Gayda, "Retail Traders Love 0DTE Options" ([SSRN 4404704](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4404704)) · Fu, Li, Musto and Pearson, "Hope at a Reasonable Price" ([SEC DERA](https://www.sec.gov/files/dera-hope-reasonable-prc-2503.pdf)) · Vilkov, "0DTE Trading Rules" ([SSRN 4641356](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4641356)) · Almeida, Freire and Hizmeri, "0DTE Asset Pricing" ([PDF](https://www.fma.org/assets/docs/Derivatives2025/Almeida.pdf)) · Dubinsky and Johannes, earnings and options ([PDF](https://business.columbia.edu/sites/default/files-efs/pubfiles/6051/DJ_2006.pdf)) · Baltussen, Da, Lammers and Martens, JFE 2021 ([PDF](https://www3.nd.edu/~zda/intramom.pdf)) · Osler, "Support for Resistance" ([NY Fed](https://www.newyorkfed.org/research/epr/00v06n2/0007osle.html)) · Li, Musto and Pearson, "Simple Roles for Complex Options" ([SEC DERA](https://www.sec.gov/files/dera-simp-rule-complx-opt-2503.pdf)) · Bogousslavsky and Muravyev, retail options (2024).

**Abstracts or snippets only:** Muravyev and Ni, JFE 2020 (day vs night) · Sullivan, Timmermann and White 1999; Bajgrowicz and Scaillet 2012 (technical rules) · Marshall, Young and Rose 2006; Duvinage et al. 2013 (candlesticks) · Lo, Mamaysky and Wang 2000 (patterns) · Vasquez 2017 (term structure) · Pool, Stoll and Whaley 2008; Barraclough and Whaley 2012 (early exercise).

**Vendor (weak, unaudited):** [FlashAlpha SPY fills](https://flashalpha.com/articles/spy-put-credit-spread-active-backtest-mm-fills-vrp-signal-drawdown-breaker) (only 20–25% of mid orders filled) · [Option Alpha](https://optionalpha.com/blog/spy-put-credit-spread-backtest) (targets and stops).

**Our own work:** full notes and scripts are in the session scratchpad `mastery/` (strategy catalog, greeks and IV, charts, short-dated, execution). SPY 2016–2026 checks use Alpaca SIP bars and Cboe VIX history; they are in-sample.
