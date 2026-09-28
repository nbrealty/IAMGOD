# Where AI can beat human traders

*28 Sept 2026. Written after the options lab's first day (see `Options lab day 1 post-mortem.md`). Built on the existing reports: `Options rulebook.md` (OPT rules), `Why day traders lose.md` (MT-G rules), `Agent rulebook.md` (M rules), `AI options trading research.md`, `Options playbook for beginners.md`, `Minute trading backtest results.md`, `Market psychology and news signals.md`. Research only: no orders, no code edits, no commits. Two skeptics checked the evidence; anything they could not confirm is marked **UNVERIFIED**.*

**Owner's goal:** "take humanity's strategies and apply the ability of AI to surpass humanity in everything involving trading." This report takes that goal seriously. It says where the goal is realistic, where it is not, and what to test next.

## 1. The honest answer in 10 lines

1. AI plus code can already beat **most retail traders** on process: discipline, exact maths, breadth, memory, cost control and honest testing.
2. Most retail traders lose mainly through costs and bad habits, so "make fewer of their mistakes" is a real, reachable edge.
3. It cannot beat **professional firms** on speed. They react in milliseconds or less; our scheduled sessions run hourly at best.
4. It cannot beat them on data either. The best academic results use 25 years of quotes; we have trade bars from Jan 2024 and no historical quotes.
5. We have **no proven profit edge** today. Both lab signals and all 14 minute setups tested at about zero before costs.
6. Published edges shrink: stock anomalies earn about 58% less after publication, and index-option alphas look like zero over the last 15 years.
7. Paper results flatter us: the free option quotes are not real exchange quotes, and paper fills ignore queues, latency and market impact.
8. The "beyond human" part is scale and rigour: test thousands of ideas honestly, watch every option on every name, and never skip a rule.
9. That rigour mostly produces a lot of "no". Refusing bad trades is the most reliable advantage we have.
10. "Don't trade" is a valid choice until the cost engine and the testing factory (agenda items 1–2) are built.

## 2. Where AI and code really do better than humans

| Strength | What code does | Evidence | How strong |
|---|---|---|---|
| **Discipline** | Exits and size set before the trade and run the same way on trade 1 and trade 500 | Individual investors sold 14.8% of winning positions vs 9.8% of losers (Odean 1998). LLM agents show "a pronounced disposition effect" too (Ouyang & Sui), so **code**, not Claude, must own exits | Strong for humans; the LLM result means the discipline must be in code |
| **Exact pricing** | Reprice every leg every minute; log fair value next to each fill | Today's post-mortem: this is how the cost question was found. LLMs score 18–53/100 on greeks tasks (TraderBench), so the maths must be code, not the model | Strong (mechanism) |
| **Cost control** | Patient limits near fair value; never market orders; a slippage ledger | Traders who time their option orders pay effective spreads "less than 40%" of the usual measures (Muravyev & Pearson 2020). Retail option losses are mostly costs: of about $125M lost, about $90M was costs (Beckmeyer et al.) | Strong, but the fast part of this edge belongs to HFT firms |
| **Breadth** | Scan every strike and expiry, 2,000 earnings reports a quarter, full option surfaces | Option-surface signals that need machine-scale data: smirk (10.9% a year, Xing, Zhang & Zhao 2010), call-put gap (50 bp a week, Cremers & Weinbaum 2010), IV changes (about 1% a month, An et al. 2014). All before costs; Cremers & Weinbaum say their own effect faded | Medium; needs data we must log ourselves |
| **Honest testing at scale** | Count every attempt; raise the pass mark with the count; plant fakes to test the tester | After 316 factors, a new one should clear t > 3, not t > 2 (Harvey, Liu & Zhu 2016). A leaky Sharpe-35 strategy passed standard overfitting checks and only a no-peek design caught it (Gençay 2026, **single-author preprint, not peer-reviewed**) | Strong (principle) |
| **Clock discipline** | Act at the same chosen time every day | Hedged S&P 500 option sellers earn about 1% a day overnight and lose about 0.3% a day intraday, before costs (Muravyev & Ni 2020) | Medium; not yet checked on our instruments |
| **Tail memory** | Replay every known crash against every position daily, including wider quotes | VIX: 17.31 → 37.32 (5 Feb 2018), 82.69 (16 Mar 2020), 65.73 intraday (5 Aug 2024). Short-vol products lost over 90% in one day in 2018 (Augustin, Cheng & Van den Bergen, FAJ 2021) | Strong as a risk tool; not a profit edge |
| **Machine learning on big panels** | Nonlinear models across millions of option observations | Profits "even after accounting for transaction costs" on 12M+ observations, 1996–2020 (Bali et al. 2023); hedged option Sharpe "above two" after costs (Zhan et al. 2022) | Strong in papers; **we lack the data** |

**What these have in common:** the advantage is process, scale and honesty, not prediction. That is also where the money leaks for retail traders.

## 3. Where AI and code do not beat humans (limits and myths)

| Belief | Reality | Evidence |
|---|---|---|
| "AI wins by being faster" | We can't compete. Our sessions are hourly at best; option bar requests must end 16+ minutes in the past | Scheduled routines are limited to hourly ([docs](https://code.claude.com/docs/en/routines)). Prices react to macro news within milliseconds (Chordia et al. 2018, cited in our earlier reports, **not re-checked today**) |
| "An LLM can read the market and trade on its own" | Mostly not. Code must do maths and exits; the model is useful only if a scorecard shows it adds value | Letting models choose their own bet size raised bankruptcy: Claude-3.5-Haiku went from 0% to 20.5% in a game with −10% expected value ([arXiv 2509.22818](https://arxiv.org/html/2509.22818)). Alpha Arena contests: most models lost (**press only, UNVERIFIED**). The famous "GPT-4 beats analysts" paper was withdrawn ([arXiv 2407.17866v3](https://arxiv.org/abs/2407.17866v3)) |
| "Published strategies still work" | They shrink, often a lot | Anomalies earn about 58% less after publication (McLean & Pontiff 2016). Index-option alphas "indistinguishable from zero" over 15 years (Dew-Becker & Giglio 2025). The 0DTE mispricing "dissipates" after 2022 (Almeida et al.). LLM news-trading Sharpe fell 6.54 → 3.68 → 2.33 → 1.22, and 20 bp round-trip costs make it unprofitable (Lopez-Lira & Tang) |
| "Many option 'alphas' are free money" | Most are pay for risk. A factor model built from characteristics explains nearly all of them | Across 46 option strategies, average alpha is "close to zero" under IPCA, against raw returns above 80 bp a month, before costs (Goyal & Saretto, RFS 2025) |
| "Selling index insurance is a sure edge" | Small or zero after risk; the return is mostly stock-market exposure | The PUT index's alpha was about +0.38% a year at a beta of 0.47 (Wilshire study, cited in our rulebook). Our own replay: −0.076R per trade at the $2 width we can afford (−0.114R with default settings) |
| "Hiding company names removes LLM hindsight" | It doesn't | "Masking fails as LLMs reconstruct entities and dates from minimal context" (Lopez-Lira, Tang & Zhu, [arXiv 2504.14765](https://arxiv.org/abs/2504.14765)) |
| "Paper P&L is real" | It is optimistic | Paper does not model latency slippage, queue position or market impact, and charges no fees ([Alpaca](https://docs.alpaca.markets/docs/paper-trading)). The free option feed "is not actual OPRA quotes" ([Alpaca](https://docs.alpaca.markets/docs/historical-option-data)) |
| "Better exits can fix a bad trade" | Not if the entry has no edge | Day-1 two-year replay: every exit rule lost about the cost ($4–9 per spread) |
| "A high win rate means a good strategy" | No | TP 10% won 61% of the time and still averaged −$7.2 per spread (t −2.9) |
| "Crashes can be forecast" | Not reliably | No volatility model predicted 2018, 2020 or Aug 2024. Our quick HAR check raised the average premium but not the win rate or the worst loss. Survival comes from size and width caps |
| "AI can prove an edge quickly" | The calendar can't be sped up | At one SPY spread a month, 100 trades take about 8 years. Finding a $2-per-spread intraday edge at t = 3 needs roughly 2,000 trades |

## 4. Ranked research agenda

**How ranked:** (1) strength of evidence after costs, (2) fit with data we have or can cheaply buy, (3) time to a useful answer, (4) risk. **Changes after review:** the index-premium item moved from #5 to #7 (our own replay is negative), and the Claude-veto scorecard moved up to #5 (it decides whether the LLM belongs in the trade path at all). Headings say "why code helps", not "why AI wins": most of these are things professional desks already do.

| # | Item | Type | Data we have? | First answer in | Cost |
|---|---|---|---|---|---|
| 1 | Execution and cost engine | Cut losses | Partly; needs one month of real quotes | 2–3 months | $0–80 |
| 2 | Testing factory with planted fakes | Stop false positives | Yes | 1–2 sessions | $0 |
| 3 | Do option sellers earn overnight or intraday? | Timing rule | Yes (trade bars only) | 1–2 sessions | $0 |
| 4 | Crash-stress tool | Risk control | Partly (modelled before 2024) | 2–3 sessions | $0 |
| 5 | Scorecard for Claude's vetoes | Decide the LLM's role | Yes (decision log) | 50+ vetoes | $0 |
| 6 | Event calendar and earnings move table | Risk + measurement | Yes (forward only for earnings) | 1 session to build; 4 quarters | $0 |
| 7 | Index insurance premium, perfect discipline | Monitor / shadow | Yes | Years | $0 |
| 8 | Volatility regime gates (HAR, VIX curve) | Risk filter | Modelled from VIX | 1–2 sessions | $0 |
| 9 | Filing changes and news vetoes | Stock-book filter | Needs point-in-time data | Months | $0 unless data bought |
| 10 | Option-surface logger for three stock signals | Long-term | Forward only | 5+ years (or buy history) | $0 or paid data |
| 11 | Machine learning on an option panel | Long-term | No | Years, or buy a dataset | Expensive |

### 1. Execution and cost engine

- **Hypothesis:** if code prices every leg and never gives away more than it must, we lose at least $0.02 less per spread each way than accepting the quoted price.
- **Why code helps:** the day-1 cost figure ranged from a $6 gain to a $19 loss depending on the yardstick. We cannot even measure costs properly yet. A person cannot reprice two legs every minute without slips.
- **Evidence:** effective spreads "less than 40%" of usual measures for traders who time orders (Muravyev & Pearson 2020). The fast part of that gain goes to HFT firms; we can only get the slow part.
- **First test:**
  1. **Step 1:** get real quotes. Use Databento's $125 free credit (or ThetaData Standard, $80 for one month). Compare real OPRA mids with the indicative mids we log, for SPY and QQQ, including 28 Sept.
  2. Fix the exit floor (line 695) and the stale-quote problem.
  3. Log on every order: model fair value, indicative mid, natural price, quote age, limit, fill, a "filled better than limit" flag, and estimated fees.
  4. Alternate days between rule A (cross at natural) and rule B (start at mid, step toward natural over about 5 minutes).
- **Success:** after 30+ orders per rule, rule B saves a median of at least $0.02 per spread per side with at least 80% filled.
- **Kill:** saving under $0.01, fill rate under 70%, or the indicative mid differs from the real mid by more than $0.03 median. In that last case, the free feed can't be trusted: buy the $99/month feed or stop options work.
- **Caveat:** paper fills resting orders whenever the indicative quote crosses them, with no queue. So both the saving and the fill rate are **ceilings**. 30 orders per rule on alternating days takes about 2–3 months.
- **Data:** indicative quotes (free), one month of real quotes ($0–80).

### 2. Testing factory with planted fakes

- **Hypothesis:** our pipeline rejects a strategy that peeks at the future, rejects random signals at the expected rate, and still finds a small real edge we plant.
- **Why code helps:** AI can test thousands of ideas. That only helps if every attempt is counted and the pass mark rises with the count.
- **Evidence:** t > 3 hurdle (Harvey, Liu & Zhu 2016). The leaky Sharpe-35 strategy that passed standard checks (Gençay 2026, preprint). Our record: 14 of 14 minute setups failed.
- **First test:** in `trading/lab/scalp/backtest.py`, plant (a) a signal that peeks one bar ahead, (b) 1,000 random signals, (c) a real +0.1R edge.
- **Success:** the peeking signal is rejected; random signals pass at about the chance rate (about 1–3 of 1,000 at t > 3); the planted edge's detection rate is reported.
- **Kill:** the peeking signal passes, **or** random signals pass clearly above the chance rate. Then freeze all promotions until fixed. (One or two random passes is expected, not a failure.)
- **Data:** everything is on hand (SIP minute bars, `state/experiments.jsonl`).

### 3. Do option sellers earn overnight or intraday?

- **Hypothesis:** for SPY options since Jan 2024, hedged sellers earn mostly from about 15:45 to the next morning, and about zero or less from 10:00 to 15:45.
- **Why code helps:** a scheduled system acts at the same clock time every day, which is exactly what a timing effect needs.
- **Evidence:** −1% a day close-to-open and +0.3% open-to-close for hedged S&P 500 option holders; equity options show the same pattern (Muravyev & Ni 2020). Before costs; may have shrunk. Day 1 fits it: about +$1.70 of decay in 4 hours.
- **First test:** back out IV from trade prints (as in the post-mortem) for near-the-money SPY options, 0–10 days to expiry, about 650 days. Compute the hedged value change 15:45 → next 10:00 and 10:00 → 15:45. Use only contracts with enough prints in each window.
- **Success:** overnight seller gain at least 2× the modelled round-trip cost with t > 3, and intraday ≤ 0. Then stop same-day premium-selling tests and keep book O's 15:45 order time.
- **Kill:** overnight and intraday are the same within noise, or the effect is smaller than print bounce.
- **Big risks:** we have prints, not quotes. On a $1 SPY option, bid-ask bounce (about $0.01–0.02) is the same size as the effect. Opening and closing prints may lean toward buyers or sellers. Also, a scheduled system cannot delta-hedge overnight, so the tradeable version is unhedged and riskier.
- **Data:** Alpaca option trade bars from 18 Jan 2024; SIP stock bars.

### 4. Crash-stress tool

- **Hypothesis:** checking every open and planned spread against past crash days, with quotes 3–5× wider, keeps the book's worst case within 1% of equity (OPT-9).
- **Why code helps:** people underweight rare disasters after calm periods. Code re-runs every crash every day.
- **Evidence:** VIX figures above (Cboe CSV). The BIS found the Aug 2024 VIX spike was partly driven by wider put quotes, and VIX is computed from quotes, so the 65.73 high is partly a quote effect ([BIS Bulletin 95](https://www.bis.org/publ/bisbull95.pdf)). Use Aug 2024 for spread-widening costs, not as the size of the volatility shock.
- **First test:** scenario sets (SPY −4/−7/−12%, IV +15/+30/+50 points, leg spreads ×3/×5) as a gate in the book O backtest. Build on 2018 and 2020; check on Aug 2024 and Apr 2025.
- **Success:** worst case within 1% of equity in every scenario, and the gate blocks fewer than half of eligible months.
- **Kill:** the gate blocks more than 50% of months.
- **Be honest about it:** 2018 and 2020 option prices are modelled (we have none). The 3–5× widening is an assumption. The out-of-sample check has **two crashes**, so it cannot prove "losses avoided > gains skipped". This is a **risk tool, not a tested edge.**
- **Data:** Cboe VIX CSVs, SIP bars from 2016, option bars from 2024.

### 5. Scorecard for Claude's vetoes

- **Hypothesis:** trades Claude vetoes turn out worse than trades it lets through. If not, Claude leaves the trade path.
- **Why this matters for the goal:** it is the direct test of whether the AI's judgement adds anything beyond the code.
- **Evidence:** LLM agents show human-style biases (Ouyang & Sui). Model-chosen bet sizes raised bankruptcy (arXiv 2509.22818).
- **Test:** a code-only shadow book against the Claude-filtered book.
- **Success:** after 50+ vetoes, the bootstrap 90% lower bound of **(taken-trade R − vetoed-trade R)** is above 0.
- **Kill:** otherwise, remove Claude from trade decisions.
- **Note:** Claude runs only in scheduled sessions, so vetoes happen at fixed times.

### 6. Event calendar and earnings "implied move vs history" table

- **Hypothesis:** short-dated trades opened on CPI, FOMC or jobs days lose more per unit of risk. Separately, a table of the move priced in before earnings, against each stock's past moves, shows where options are cheap or dear.
- **Why code helps:** code never forgets the calendar and can measure about 2,000 reports a quarter.
- **Evidence:** at-the-money straddles bought 3 days before earnings earned +3.34% (Gao, Xing & Zhang 2018). In the working paper (1996–2010), short-dated (4–10 day) straddles kept +1.64% a day (t = 5.14) with costs at half the quoted spread and +0.61% (t = 2.08) at the full spread; longer maturities turned negative. The 14–16% quoted spread figure is **UNVERIFIED**. Retail traders lose 5–9% around earnings (de Silva, So & Smith, Review of Finance 2026).
- **First test:** tag every lab trade "event day" or not. Log implied and actual earnings moves for the 100 most liquid names each quarter (display only).
- **Success:** after 50+ trades, the bootstrap 90% upper bound of (event-day R − normal-day R) is below 0: keep the event block. The straddle idea continues only if positive at natural prices (buy at ask, sell at bid) in the most liquid third of names after 4 quarters.
- **Kill:** otherwise.
- **Data:** FOMC and CPI dates (store in config; BLS blocks scripts). Earnings: Alpha Vantage or Nasdaq (free). Option quotes around earnings are forward-only.

### 7. Index insurance premium with perfect discipline (book O, shadow only)

- **Hypothesis:** a SPY bull put spread entered every eligible month, never skipped, rolled or upsized, beats T-bills after costs.
- **Why code helps:** human insurance sellers fail by habit (skipping after scares, sizing up after wins, rolling losers).
- **Evidence:** buyers pay a variance premium, strongly for the S&P 500, S&P 100 and Dow, less for the Nasdaq-100 and most single stocks (Carr & Wu 2009). VIX was above later realized volatility on 84.5% of days, 2016–2026 (our check; overlapping windows, so only about 125 independent months; in 2018 only 61% of days). But option alphas are "indistinguishable from zero" for 15 years (Dew-Becker & Giglio 2025), and our replay gives −0.076R per trade at our width.
- **Label:** small or zero risk-adjusted edge. **Monitor, don't promote.**
- **Test:** OPT-37 backtest plus a code-only shadow that never skips (OPT-36). Benchmarks: zero and BIL.
- **Success:** OPT-40. **Kill:** OPT-32; also flag a regime change if the 12-month rolling VIX-minus-realized gap turns negative.
- **Time:** about 8 years for 100 trades.

### 8. Volatility regime gates (HAR forecast, VIX curve)

- **Hypothesis:** selling only when IV is clearly above a volatility forecast, or blocking entries when VIX/VIX3M > 1, improves the worst months without hurting the average.
- **Evidence:** HAR forecasts well (Corsi 2009); the VIX curve slope predicts variance-swap and straddle returns (Johnson 2017). Our quick checks were weak: the HAR gap tracked the size of the premium but not safety (correlation 0.10 vs 0.13 for VIX alone). On inverted-curve days VIX beat later realized volatility 79% of the time vs 87% on steep days. Our HAR used daily data; the idea needs intraday data to be tested fairly.
- **First test:** rebuild HAR from 5-minute bars. Fit 2016–2020, test 2021 on, as a gate on the #7 shadow. Option P&L before 2024 is **modelled from VIX**, not real prices. Fix quartile cut-offs using the fit period only.
- **Success:** the worst 3 months (not the single worst month, which is too noisy) improve by at least 25%, and average R does not fall, with costs doubled.
- **Kill:** no better than plain VIX out of sample.

### 9. Filing changes and news vetoes

- **Hypothesis:** a code-only score of how much a 10-K/10-Q changed, used as an "avoid" list, beats the universe after costs. A news veto cuts losses on stocks we hold.
- **Evidence:** firms that changed filings earned up to 188 bp a month less (Cohen, Malloy & Nguyen 2020). A hobby replication found nothing (alpha −0.93%, t −0.49), but it used today's S&P 100 (survivorship bias) and annual rebalancing, so it is not comparable. LLM news signals decayed sharply (Lopez-Lira & Tang, above). Name masking does not stop LLM hindsight.
- **First test:** backtest the code-only score (no LLM) on liquid mid caps from 2015, **with delisted stocks and filing dates as known at the time**. Alpaca does not obviously provide that universe; check before building. Forward-shadow the news veto 3 months.
- **Success:** t > 3 after costs. **Kill:** less.
- **Data:** SEC EDGAR (free; needs a User-Agent with a contact email), Alpaca news (free).

### 10. Option-surface logger for three stock signals

- **Hypothesis:** the smirk, the call-put IV gap and last month's call-IV change predict next month's stock returns.
- **Evidence:** section 2 table. All before costs, and at least one decayed per its own authors.
- **Problem:** **underpowered by design.** Twelve monthly sorts with about a 1% spread and 3% noise give t ≈ 1. A real effect would be killed. Needs about 5+ years of our own logs, or bought history. Indicative quotes on thin out-of-the-money puts are also doubtful.
- **Action now:** start the daily logger (it is cheap and also feeds #11). Decide after pricing historical data in section 5.
- **Success:** t > 3 after the 58% decay haircut. **Kill:** otherwise.

### 11. Machine learning on an option panel

- **Hypothesis:** a walk-forward model predicts next month's hedged option returns better than a single signal.
- **Evidence:** Bali et al. 2023, Zhan et al. 2022 (section 2). Counterpoint: IPCA explains most option alphas (Goyal & Saretto 2025).
- **Honest status:** 2–3 years of our own logs on 200 names cannot replace a 25-year panel. Either price a historical dataset (OptionMetrics via a university, or ORATS from $199/month) or drop it.

## 5. Data and infrastructure upgrades worth paying for

| Item | Cost | What it unlocks | Verdict |
|---|---|---|---|
| Databento historical OPRA 1-minute quotes | **$125 free credit**, then pay per use or $199/mo ([pricing](https://databento.com/pricing)); per-GB rate not verified | First check of the indicative feed against real quotes | **Do first** |
| ThetaData Standard: OPRA NBBO history, 10 years | **$80 for one month** ([pricing](https://www.thetadata.net/pricing)) | Real historical spreads for SPY/QQQ; tests our cost model and the day/night study with quotes | **Buy one month, download, cancel** |
| Alpaca Algo Trader Plus: real-time OPRA, no 15-min delay | **$99/month** ([alpaca.markets/data](https://alpaca.markets/data)); no historical quotes | Honest live spreads; builds our own quote history from now on | Before any live options money |
| Cboe DataShop Option EOD Summary (15:45 ET NBBO snapshot, from 2012) | About $50/day, capped at $300/month of data (**UNVERIFIED**, search snippet) ([page](https://datashop.cboe.com/option-eod-summary)) | Matches book O's 15:45 decision time exactly | Price it before #7/#8 |
| ORATS delayed API (smoothed IV, from 2007) | $199/month; intraday $599 ([page](https://orats.com/data-api)) | Clean IV surfaces for #8, #10, #11 | Only if #10/#11 continue |
| Massive (ex-Polygon) options | $29/$79/$199 per month; historical NBBO only at $199 ([pricing](https://massive.com/pricing?product=options)) | Similar to others | Not needed |
| OptionMetrics IvyDB (from 1996) | University access only (WRDS) | The academic standard for #11 | Only via a university |
| Free: Cboe VIX/VIX3M/VIX9D/SKEW CSVs, FRED rates, CFTC positioning, Fed/BLS calendars, Alpaca bars/trades/news/dividends, Dolt free SPY chains (quality unknown) | $0 | Everything in #2–#8 | Use now |
| Compute | Current session: 4 CPUs, 15 GB RAM | Enough for daily and minute-bar work | No upgrade needed |

**Not worth paying for:** anything sold as a speed edge (co-location, faster feeds). Our sessions are scheduled; speed money would be wasted.

## 6. What to do this week

1. **Decide about the 0DTE lab (owner).** From 29 Sept it trades same-day spreads with the same no-edge signals. Either run it strictly as a mechanics and cost test (expect about minus costs), or pause it until items 1–2 are done. Both are defensible. Pausing costs nothing we can measure.
2. **Fix the defects before the next lab day (owner or developer; I did not edit code):**
   - line 695: exit floor at natural when we receive money;
   - line 484: `mom60` is a 45-minute move at 10:15 (fix or rename; no signal before 10:30);
   - stale entry quotes (refuse or re-fetch if old);
   - keep the original size in `trades.json`.
3. **Add fill logging:** model fair, indicative mid, natural, quote age, limit, fill, "better than limit" flag, estimated fees, best/worst P&L, and a P&L split into stock move, decay, volatility and costs.
4. **Claim the Databento free credit** and compare real vs indicative quotes for SPY/QQQ on a few days, including 28 Sept.
5. **Build the testing factory's planted-fakes check** (item 2, 1–2 sessions).
6. **Start the day/night study** (item 3) on SPY trade bars.
7. **Put free data in config:** FOMC dates (27–28 Oct, 8–9 Dec 2026), CPI dates (14 Oct, 10 Nov, 10 Dec, 08:30 ET), Cboe CSVs, FRED 3-month rate.

## 7. Sources

**Checked by the skeptic reviews on 28 Sept 2026 (primary source or abstract):**
- Alpaca paper trading: https://docs.alpaca.markets/docs/paper-trading
- Alpaca historical option data: https://docs.alpaca.markets/docs/historical-option-data
- Alpaca market data plans: https://alpaca.markets/data
- Claude Code routines: https://code.claude.com/docs/en/routines
- Muravyev & Ni 2020, JFE 136(1):219–238: https://econpapers.repec.org/RePEc:eee:jfinec:v:136:y:2020:i:1:p:219-238
- Muravyev & Pearson 2020, RFS 33(11):4973: https://academic.oup.com/rfs/article-abstract/33/11/4973/5732665
- Dew-Becker & Giglio, Chicago Fed WP 2025-17: https://www.chicagofed.org/publications/working-papers/2025/2025-17
- Goyal & Saretto 2025, RFS 38(6):1783–1821 (IPCA): https://ideas.repec.org/a/oup/rfinst/v38y2025i6p1783-1821..html ; working paper: https://www.dallasfed.org/research/papers/2022/wp2214
- Carr & Wu 2009, RFS 22(3):1311: https://academic.oup.com/rfs/article-abstract/22/3/1311/1581057
- McLean & Pontiff 2016, JF: https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365
- Harvey, Liu & Zhu 2016, RFS 29(1):5–68: https://academic.oup.com/rfs/article/29/1/5/1843824
- Gençay 2026, "What survives honest evaluation?" (preprint): https://arxiv.org/abs/2608.27734
- Bali, Beckmeyer, Moerke & Weigert 2023, RFS 36(9):3548: https://academic.oup.com/rfs/article-abstract/36/9/3548/7056660
- Zhan, Han, Cao & Tong 2022, RFS 35(3):1394: https://academic.oup.com/rfs/article-abstract/35/3/1394/6294944
- Xing, Zhang & Zhao 2010, JFQA 45(3):641: https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/what-does-the-individual-option-volatility-smirk-tell-us-about-future-equity-returns/ECFD16BA9ACBDC8D577D1BD866FBEA72
- Cremers & Weinbaum 2010, JFQA 45(2):335: https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/deviations-from-putcall-parity-and-stock-return-predictability/D9BA8F97580328AAFD7988B092FE5D50
- An, Ang, Bali & Cakici 2014, JF 69(5):2279: https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12181
- Gao, Xing & Zhang 2018, JFQA 53(6):2587: https://ideas.repec.org/a/cup/jfinqa/v53y2018i06p2587-2617_00.html (working paper SSRN 2204549)
- Corsi 2009, J. Financial Econometrics 7(2):174: https://academic.oup.com/jfec/article-abstract/7/2/174/856522
- Johnson 2017, JFQA 52(6):2461: https://econpapers.repec.org/RePEc:cup:jfinqa:v:52:y:2017:i:06:p:2461-2490_00
- Almeida, Freire & Hizmeri, "0DTE Asset Pricing" (2025 draft): https://www.fma.org/assets/docs/Derivatives2025/Almeida.pdf
- BIS Bulletin 95 (Todorov & Vilkov, Aug 2024 VIX): https://www.bis.org/publ/bisbull95.pdf
- Volmageddon, FAJ 2021: https://rpc.cfainstitute.org/research/financial-analysts-journal/2021/volmageddon-failure-short-volatility-products
- Cboe VIX history: https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv
- Ouyang & Sui (LLM disposition effect): https://arxiv.org/pdf/2604.18373
- TraderBench: https://arxiv.org/html/2603.00285v1
- LLM bet sizing and bankruptcy: https://arxiv.org/html/2509.22818
- Lopez-Lira, Tang & Zhu (masking fails): https://arxiv.org/abs/2504.14765
- Withdrawn "GPT-4 beats analysts" paper: https://arxiv.org/abs/2407.17866v3
- Odean 1998 (disposition effect): https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/areinvestorsreluctant.pdf

**Data vendor pages (prices as shown on 28 Sept 2026):** https://databento.com/pricing ; https://www.thetadata.net/pricing ; https://massive.com/pricing?product=options ; https://orats.com/data-api ; https://datashop.cboe.com/option-eod-summary (price **UNVERIFIED**)

**Cited but not re-checked today, or UNVERIFIED:**
- Chordia et al. 2018 (millisecond reaction to macro news): cited from earlier reports.
- Beckmeyer, Branger & Gayda (retail 0DTE losses, $241k a day; about $90M of $125M was costs): SSRN 4404704. Figures confirmed by one skeptic; link via the Options rulebook.
- Lopez-Lira & Tang Sharpe path (6.54 → 1.22): confirmed by one skeptic, not the other.
- Cohen, Malloy & Nguyen 2020 (188 bp a month): abstract confirmed; the hobby replication is not comparable.
- de Silva, So & Smith 2026 (retail loses 5–9% around earnings): Review of Finance 30:489–535, via the Options rulebook.
- Wilshire PUT index alpha (+0.38% a year, beta 0.47): https://cdn.cboe.com/resources/spx/wilshire-options-based-benchmark-indexes-2019.pdf, not re-read today.
- Alpha Arena results: press only.
- Gao, Xing & Zhang 14–16% quoted spreads; Goyal & Saretto 2009 size figures; PUT worst month −17.65%; XIV −96%: all UNVERIFIED.
- Alpaca fee rate ($0.04 per contract per side is the rulebook's assumption): https://alpaca.markets/support/regulatory-fees, not checked today.
