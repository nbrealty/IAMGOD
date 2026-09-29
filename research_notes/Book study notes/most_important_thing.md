# The Most Important Thing (Illuminated) — Howard Marks

Study notes for the owner's copy (Columbia Business School Publishing, 2013 "Illuminated" edition, with annotations by Seth Klarman, Joel Greenblatt, Christopher Davis and Paul Johnson). Written against the bot's rules as they stand in `trading/config/playbook.yaml`, `risk_policy.yaml`, `playbook_brief.md` and `trader/regime.py`.

---

## 1. What the book is about

This is Marks's investment philosophy, assembled from his client memos at Oaktree (a distressed-debt and credit firm). It is a book about how to think, not how to calculate. Marks says outright that it has no formulas and that investing cannot be turned over to a computer. Its central claims are these. Returns come from buying below intrinsic value. Risk is mainly the chance of permanent loss, and it is highest when prices are high and investors feel safe. Markets swing like a pendulum between greed and fear, so the most useful thing an investor can do is judge where the cycle stands now, not forecast where it is going. Over a career, defence (avoiding losers, margin of safety, no leverage, surviving the bad years) matters more than offence. The Illuminated edition adds a chapter on reasonable expectations and margin notes from four other value investors.

---

## 2. Key lessons (own words, with chapter)

1. **Second-level thinking (Ch 1).** Being right is not enough. You have to be right where the consensus is wrong, because the consensus view is already in the price. Ask what everyone else expects and what the price assumes.
2. **Efficiency is the default assumption (Ch 2).** Heavily followed markets (large US stocks, FX) are hard to beat. Treat efficiency as true until you can show why a specific mispricing exists. His son's test for any idea is "who doesn't know that?"
3. **Value is the anchor (Ch 3).** Without a firm estimate of intrinsic value you cannot hold or add when prices fall, and you cannot resist buying when others are making money. Marks dismisses technical analysis and momentum. His dismissal is not backed by evidence (see §5).
4. **No asset is good or bad regardless of price (Ch 4).** A great company bought at 80–90x earnings (the Nifty Fifty) can lose most of its value, and a weak asset bought cheaply can be safe. "Well bought is half sold."
5. **Short-run prices are driven by psychology and technicals (Ch 4).** Forced selling (margin calls, redemptions) creates the best bargains. The worst position to be in is a forced seller.
6. **Risk is permanent loss, not volatility (Ch 5).** Volatility became the academic definition because it can be measured, not because it is what investors fear. Risk is mostly invisible beforehand and often afterwards too. A good outcome does not prove a trade was safe.
7. **Probability is not outcome (Ch 5, 18).** Think in distributions. Worst-case assumptions often turn out not to be bad enough, and risk shows up in clumps.
8. **Risk is highest when it feels lowest (Ch 6).** When investors believe risk is gone, they bid prices up and demand no premium, and that is what makes things risky. Marks calls this the "perversity of risk".
9. **Risk control is not risk avoidance (Ch 7).** The job is to take risk only when you are well paid for it. Its value shows only in bad years, like insurance, so it looks like a cost in good years.
10. **Everything is cyclical (Ch 8).** Trends carry the causes of their own reversal. The credit cycle is the strongest example: easy money leads to bad loans, then losses, a credit crunch, cheap assets and a recovery. Treat "this time it's different" as a warning sign.
11. **The pendulum (Ch 9).** Sentiment rarely rests at the midpoint. The three stages of a bull market are "a few see improvement", "most see it" and "everyone thinks it will go on forever". The bear market runs the same three stages in reverse. The swing back from an extreme is usually faster than the swing out.
12. **Emotions are the main source of error (Ch 10).** Greed, fear, suspension of disbelief, herding, envy (comparing yourself with others), ego and capitulation. The biggest losses come from psychology, not from bad analysis.
13. **Contrarianism needs a reason (Ch 11).** Doing the opposite of the crowd pays at extremes, but only when you know why the crowd is wrong. Skepticism means doubting both too-good and too-bad stories. You cannot call the bottom, and waiting for the dust to settle means the bargains are gone.
14. **Bargains are found among the unloved (Ch 12).** Look for things that are ignored, controversial, recently sold off, trailing poor returns or "not respectable". Perception has to be worse than reality.
15. **Patient opportunism (Ch 13).** You never have to swing. Do not reach for return in a low-return environment. Keep dry powder and stay insulated from forced selling. As Peter Bernstein put it, "it won't provide high returns just because you need them."
16. **Know what you don't know (Ch 14).** Macro forecasts are of little use. The accurate forecasts at turning points come from different people each time. Invest as a member of the "I don't know" school: diversify, avoid leverage, prepare for a range of outcomes.
17. **Know where we stand (Ch 15).** "Take the market's temperature" from present evidence: sentiment, credit terms, issuance quality, P/Es and spreads against history. Be cautious when others are carefree and aggressive when they panic.
18. **Luck is large (Ch 16).** A decision's quality cannot be judged from its outcome ("alternative histories"). Short-term gains and losses are both impostors. You need many observations before judging skill.
19. **Invest defensively (Ch 17–18).** "If we avoid the losers, the winners will take care of themselves." Use margin for error, avoid leverage and understand correlation. Ask what today's likely mistake is: acting (commission) or not acting (omission)?
20. **Skill is asymmetry; expectations must be reasonable (Ch 19–20).** Skill means capturing more of the market's gains than its losses, relative to your style. Single-digit to low-double-digit returns are reasonable. Anything that is both steady and high (Madoff) is too good to be true.

---

## 3. Codeable rules

**Plainly: the book gives no trading rules.** Marks says repeatedly that risk "isn't machinable", that no formula tells you when a market is at an extreme, and that avoiding pitfalls is not "susceptible to rules, algorithms or roadmaps". There are no thresholds, lookbacks or valuation cut-offs anywhere. The "Poor Man's Guide to Market Assessment" (Ch 15) is a two-column checklist of hot versus cold market traits. It is an image in the original and **did not survive in this text copy**, so only the surrounding questions are available. Everything below is **my translation** of his principles into testable form. None of it comes from the book as a specification, and each item must be backtested before adoption.

### 3.1 Market temperature score (from Ch 6, 9, 15)
Marks's questions: Are investors optimistic? Is capital easy to get? Are P/Es high against history? Are yield spreads tight? Is junk issuance strong? A daily score can proxy these. Each component is scored as a percentile against its own trailing 10-year history (0 = coldest, 1 = hottest):

| Component | Data | Hot means |
|---|---|---|
| Credit spread | FRED `BAMLH0A0HYM2` (HY OAS) | low OAS, so use 1 − percentile |
| Credit trend (price-only fallback) | HYG/IEF ratio, 6-month change | strongly positive |
| Valuation | Shiller CAPE, or S&P forward P/E | high percentile |
| Trailing return | SPY 24-month total return | high percentile |
| Complacency | SPY 20d realised vol (or VIX) | low vol, so use 1 − percentile |
| Breadth | % of the stock universe above its 200d SMA (already computed) | very high |

`temperature = mean(component percentiles)`. Labels: `hot` if ≥ 0.80, `cold` if ≤ 0.20, else `neutral`.

Proposed use (conservative, inside existing bounds only):
- `hot`: Claude-book sleeve weights for B and C are capped at their `default` (not `max`). Journal note must state the temperature.
- `cold`: no automatic action (reasons in §6). Claude may not cut sleeve A below what its own rules say.
- No component or combined signal ever raises risk above current limits.

### 3.2 Credit canary (from Ch 8, credit cycle)
Add a price-based credit check next to VWO/BND: `credit_ok = momentum_13612w(HYG) − momentum_13612w(IEF) > 0` on month-end closes. Test it as (a) an extra canary and (b) a condition that downgrades `bull_calm` to `bull_volatile`. Adopt it only if out-of-sample drawdown falls without a proportionate loss of CAGR.

### 3.3 Stressed correlation (from Ch 18, "hidden fault lines")
Correlations rise in crises, so a 60-day ρ measured in calm markets understates risk. Rule: the pairwise ρ for the `correlated_positions` check is `max(ρ_60d, ρ_on_high_vol_days)`. The second term is the correlation of daily returns over the past 3 years restricted to days when SPY's 20d vol was in its top quintile. Simpler alternative: treat {SPY, QQQ, IWM, DIA} as one cluster, so sleeve B's two positions count as one correlated bet.

### 3.4 Skill as asymmetry (from Ch 19)
Add to monthly reporting, for both books against SPY and against each other:
- `up_capture = mean(book return | SPY month > 0) / mean(SPY return | SPY month > 0)`
- `down_capture = mean(book return | SPY month < 0) / mean(SPY return | SPY month < 0)`
- Skill evidence: `up_capture / down_capture > 1` sustained over at least 36 months, **and** the difference between the Claude and rules books significant (paired bootstrap on monthly returns, p < 0.05).

### 3.5 Anti-envy and anti-reaching-for-return (from Ch 10, 13, 20)
- The Claude book may change sleeve weights at most once per calendar month, by at most ±0.05 per sleeve per change.
- A weight increase must cite a non-performance reason. It may not be justified by recent under-performance against SPY or the rules book. The daily `review_rules_plan` flow can already only reduce risk, so this applies to `decide`.

### 3.6 "Today's mistake" field (from Ch 18)
Add a required enum `likely_error ∈ {commission, omission, none}` plus one sentence to Claude's JSON output, so the journal records whether it thought the danger was over-acting or under-acting. Track it against outcomes over time. It costs nothing and it audits calibration.

### 3.7 Things that stay unprogrammable
Intrinsic value of individual stocks, "who doesn't know that?", the three bull and bear stages, and whether a narrative is a "silver bullet". These can go in Claude's prompt as questions to consider. They should not be rules.

---

## 4. Psychology and risk principles

- **Second-level thinking.** Before any discretionary deviation, ask what the price already assumes and why this bot would know better. For a bot trading SPY and mega-caps from public price data, the honest answer is usually that it doesn't. Its edge, if any, is discipline and risk control, not insight.
- **Risk means permanent loss.** For this bot, permanent loss comes from (a) a large drawdown that triggers breakers and stops so that losses are realised near lows, (b) overtrading costs, and (c) a bug or a runaway LLM decision. Volatility targeting is a proxy that controls (a) only partly.
- **The perversity of risk.** The moment the regime classifier says `bull_calm` (low vol, trend up, high breadth) is also the moment Marks would call most dangerous. The bot has no reading for that danger. Everything in `regime.py` is trend and volatility, and low volatility maps to maximum permissions.
- **Cycles and the pendulum.** Marks: "We may never know where we're going, but we'd better have a good idea where we are." The classifier already measures "where we are" in price terms. It measures neither valuation nor credit, which are the two gauges Marks leans on most.
- **Contrarianism.** Marks buys in panics because he has a value anchor and permanent capital. The bot has neither. Its B and C sleeves turn off in bear and panic, the opposite of Marks. That is deliberate: RSI(2) does worst in high-vol declines and momentum crashes in panic rebounds. Marks himself warns that contrarianism without a reason is just standing in front of a truck.
- **Forced sellers.** "Being a forced seller is the worst." The bot's stops and drawdown breakers are forced selling it imposes on itself. They cap the loss per trade but, in a V-shaped crash, can turn a paper loss into a permanent one. This trade-off should be measured, not assumed.
- **Luck and outcome bias.** "Risk means more things can happen than will happen" (Dimson, Ch 5). Judge the Claude book on process and on many observations, never on one good month.
- **Invest scared, and don't insist on being clever.** "When there's nothing particularly clever to do, the potential pitfall lies in insisting on being clever" (Ch 18). This matches the brief's "doing nothing is often the best decision".

---

## 5. Claims to check against evidence

| # | Claim (chapter) | What to check | Prior view |
|---|---|---|---|
| 1 | Momentum and technical analysis don't work; prices follow a random walk (Ch 3) | Jegadeesh–Titman 1993; Moskowitz–Ooi–Pedersen 2012 (time-series momentum); Faber 2007; Hurst–Ooi–Pedersen "Century of Evidence on Trend-Following" | **Likely wrong as stated.** Trend following has a long out-of-sample record, mainly in cutting deep drawdowns. The bot's core relies on it. |
| 2 | High price means low future return and high risk (Ch 4, 6) | Campbell–Shiller CAPE vs 10-yr returns; Asness, Ilmanen & Maloney 2017 "Market timing: sin a little" | True at 7–10 year horizons, weak at 1 year. Valuation timing has mostly lost to buy-and-hold. |
| 3 | Buying at extreme pessimism earns high returns at low risk (Ch 9, 11) | Returns after VIX > 40, after HY OAS > 90th pct, after AAII bear extremes; Baker–Wurgler sentiment index | Forward returns are high on average, but paths are brutal (Oct 2008 → Mar 2009 fell another ~20%, as Greenblatt notes). |
| 4 | Macro forecasts have little value (Ch 14) | Marks's own evidence is 3 WSJ polls, which he calls anecdotal. Compare Tetlock; the Philadelphia Fed SPF track record | Probably right for markets and rates. |
| 5 | Correlations rise in crises (Ch 18) | Longin & Solnik 2001; Ang & Chen 2002 | Supported for down-market tails. |
| 6 | The credit cycle drives asset cycles; tight spreads and loose terms signal danger (Ch 8, 15) | Gilchrist & Zakrajšek 2012 excess bond premium; López-Salido, Stein & Zakrajšek 2017 | Good support that credit exuberance predicts later spread widening and weaker growth. Timing is imprecise. |
| 7 | Quality doesn't make an asset safe; only price does (Ch 6, 12) | Asness, Frazzini & Pedersen "Quality Minus Junk"; low-volatility anomaly (Frazzini–Pedersen BAB) | **Partly contradicted.** Quality earns a premium even after price. The low-vol evidence supports his "dull beats hot" point. |
| 8 | Past outperformance "borrows from the future" (Ch 11) | De Bondt–Thaler 1985 long-term reversal vs 12-month momentum | True at 3–5 years, false at 3–12 months. Horizon matters. |
| 9 | Swings back from extremes are faster than swings out (Ch 9) | Bull vs bear market durations; skew of index returns | Broadly true: bears are shorter and sharper. |
| 10 | Most professionals didn't know a decline could exceed 5%, the largest drop from 1982–1999 (Intro) | S&P 500 history | **Internally inconsistent.** He names the 1987 crash (−22.6% in one day) in the same paragraph. At most it holds for calendar-year S&P total returns (worst about −3% in 1990). Don't cite it. |
| 11 | Nifty Fifty buyers lost ~90% (Ch 4) | Siegel 1995 "The Nifty-Fifty Revisited"; Davis's own annotation | Large drawdowns yes, but a 1972-peak portfolio held 25+ years roughly matched the S&P. His point about overpaying still stands. |
| 12 | 79% of 2000s top-quartile managers spent 3+ yrs in the bottom quartile; best 2000s fund made 18%/yr while its average investor lost 8%/yr (Greenblatt notes) | Davis Advisors study; the fund is widely reported as CGM Focus; Morningstar "Mind the Gap" | Directionally consistent with the flow-chasing literature. Verify the exact figures. |
| 13 | You need ~64 years of data to prove skill statistically (Ch 2) | Unsourced "figure I remember". Compute for realistic Sharpe gaps. | The order of magnitude is plausible for small alpha. Relevant to how long the Claude-vs-rules comparison must run. |
| 14 | Plain risk-bearing yields single digits to low double digits (Ch 20) | Dimson–Marsh–Staunton long-run returns | Consistent. Matches the brief's 6–10% target. |

---

## 6. Fit with the bot

| Idea | Bot today | Verdict | Why |
|---|---|---|---|
| Reasonable expectations (Ch 20) | **Already does it.** Brief targets 6–10%/yr and says much better is likely luck or a bug | Keep | Direct match. |
| No leverage; survive first (Ch 7, 17) | **Already does it.** `leverage: 0`, long only, 0.5% risk per trade, 6% heat cap, drawdown breakers | Keep | Matches "invest scared". |
| Patience; doing nothing (Ch 13, 18) | **Already does it.** Brief says activity is the main source of loss; turnover caps and a 20% rebalance band | Keep | Matches. |
| Judge over many trials, not outcomes (Ch 16) | **Partly.** 1% risk only after ≥100 trades with positive expectancy | **Add** the up/down capture and paired-bootstrap test (§3.4) | Marks's asymmetry test is a better yardstick than raw return for the Claude-vs-rules contest. 100 trades is not enough to show alpha against the rules book. |
| Risk = permanent loss, not volatility (Ch 5) | Sizing is volatility-based (ATR stops, 10% vol target) | **Keep the vol sizing, add a check** | Vol is the only risk measure a price-only bot can compute; Marks himself concedes Sharpe is "the best we have" for liquid markets. Add a backtest check: how much drawdown was realised by stops/breakers and then recovered within 6 months? That is the bot's own forced-selling cost. |
| Temperature / valuation (Ch 6, 15) | **Missing.** Regime is price-only; `bull_calm` gives full permissions at exactly the point Marks calls most dangerous | **Add as information to Claude, plus the "hot" cap only (§3.1)**. Reject valuation-based market timing. | The evidence that valuation times the market over 1 year is weak (§5 #2), so it must not drive sleeve A or exits. A cap on B/C at `default` when hot costs little and matches his "tilt, don't time" advice. Needs CAPE/OAS data (FRED is free); if you don't want new data sources, use only the HYG/IEF, vol and breadth parts. |
| Credit cycle canary (Ch 8) | Canaries are VWO and BND (EM and aggregate bonds), not credit spreads | **Test** HYG−IEF momentum (§3.2) | Credit has decent evidence as a leading signal (§5 #6) and needs only price bars, which fits the existing data path. Adopt only if the out-of-sample backtest improves. |
| Correlation rises in crises (Ch 18) | `rho_60d 0.7, max_count 2` | **Add** stressed correlation or an index-ETF cluster (§3.3) | SPY/QQQ/IWM/DIA are about 0.85–0.95 correlated in selloffs. Two RSI(2) positions are effectively one leveraged bet on the same dip. |
| Contrarian buying in panics (Ch 9, 11, 13) | B and C are **off** in bear and panic; A moves to T-bills on its own trend rules | **Reject** turning B/C on in panics | The bot has no intrinsic-value anchor, which Marks says is required. Its sleeves do worst in high-vol declines, and momentum crashes cluster in panic rebounds. Where Marks does apply: Claude should **not** add discretionary exits on top of the rules in a panic. The rules already defend, and extra selling at lows is the error he calls the greatest in investing (Ch 18). Put that line in the decide prompt. |
| Anti-momentum / technical analysis is "Ouija boards" (Ch 3) | Every sleeve is trend or technical | **Reject** | Contradicted by a century of trend-following evidence (§5 #1). Keep the lesson that trends end ("trees don't grow to the sky"), which the 200d gates and stops already respect. |
| Second-level thinking / "who doesn't know that?" (Ch 1–2) | Signals are public, well-known rules (Faber, Connors, Minervini) | **Add as a prompt question for Claude's deviations**, not as a rule | Marks would say these edges are known and crowded, which is consistent with the brief's "halve backtests". It should make Claude humbler about deviating: any deviation must say what Claude sees that the price and the rules don't. |
| Don't reach for return; don't chase peers (Ch 10, 13) | "Never raise risk to win back losses" exists; nothing stops Claude raising sleeve weights after lagging | **Add** the weight rate-limit and non-performance-reason rule (§3.5) | Envy of the rules book or SPY is exactly the pressure Marks describes, and LLM agents in contests lost mainly through overtrading and risk-raising. |
| "Today's mistake" (Ch 18) | Not recorded | **Add** the `likely_error` field (§3.6) | Cheap, and it builds a calibration record. |
| Forced sellers (Ch 4, 13) | Breakers and stops are self-imposed forced selling; the 20% breaker allows exits only | **Measure, don't change yet** | Stops are defensible for a small, unvalidated system. The open question is the RSI(2) 3-ATR disaster stop: Connors-style tests often find stops hurt mean-reversion returns. Backtest with and without it. |
| Sell overvalued / short bubbles (Ch 12, 18) | Long only, no shorts | **Reject** | Outside the risk policy and outside the bot's competence, and Marks himself treats it as an optional error of omission. |

**Critical overall judgment.** The book strongly supports the bot's *risk culture*: small size, no leverage, modest targets, patience, humility about forecasts, and judging over many trials. It does **not** support the bot's *return engine*. Marks is a valuation-anchored contrarian in inefficient credit markets, while the bot is a price-trend follower in the most efficient markets there are. That is fine, because the trend evidence is stronger than his dismissal of it. The mistake would be bolting Marks-style contrarian buying onto a trend system that has no value model. The useful imports are the ones that make the bot *more defensive at hot extremes*: temperature, credit and stressed correlation. The asymmetry test should become the yardstick for whether Claude adds anything over the rules.

Quotes used (short, cited): Dimson (Ch 5), "We may never know where we're going…" (Ch 15), "insisting on being clever" (Ch 18), "If we avoid the losers…" (Ch 17), Bernstein (Ch 13).
