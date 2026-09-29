# R3: What the evidence says about 1- to 60-minute patterns on SPY, QQQ and large caps

> **Read `00 Fact-check corrections (read first).md` alongside this file.** Written on 28 Sept 2026 by a research agent; four independent fact-checkers then reviewed its main claims, and where they differ from the text below, the corrections file wins. Scripts behind the researcher's own calculations are in `scripts/` (paths such as `work/`, `r5/` or `research/` in the text point there; they expect data files downloaded separately). Terms like verified / UNVERIFIED are the researcher's own tags.


*Research report for the minute-trading project. Task date 28 Sept 2026. Research only: nothing in the repo was edited, no git was run, no order was placed, no broker or trading API was called. The only files written are in this folder (analysis scripts and downloaded papers are in `work/`).*

**How to read the labels**
- **Verified** = I read it in the paper, the official page or the official abstract (RePEc, arXiv, Crossref metadata, regulator or exchange page). "Abstract only" means I could not open the full text.
- **UNVERIFIED** = seen only in a search snippet, a blog, a vendor page, or taken from the repo without re-checking.
- **Strength** = how well the pattern is documented as a statistical fact (Strong / Mixed / Weak / None / Not testable). It is **not** a promise of profit. The "After costs?" column says whether costs were included and what happened.
- **bp** = basis point = 0.01%. On a $766 SPY share, 1 bp = 7.7 cents.
- "Measured" numbers are my own calculations from the repo's cached SIP 1-minute bars (3 Aug to 28 Sep 2026, 40 sessions, a **calm** period: realized volatility 6.9% a year for SPY and 11.0% for QQQ) and from the cached quotes of 28 Sep 2026. They are not sources; scripts are in `work/`.

---

## 1. Plain-English summary

1. **Bottom line:** I found no 1-to-60-minute pattern on SPY, QQQ or large caps with strong, independent, after-cost evidence that still holds today. That matches our own 2-year backtest.
2. **Best-supported effect:** "late-day momentum" (how the market moved earlier in the day, including overnight, predicts the last 30 minutes). It is real in peer-reviewed data (Gao 2018; Baltussen 2021, 60+ futures, 1974-2020) but tiny: R² of 1.7-2.9%, which is worth about **1 bp per trade** on SPY at today's volatility (my calculation).
3. **The toll:** at our measured 2-cent spread, a SPY or QQQ round trip costs at least **0.47-0.49 bp** (0.26 bp spread + 0.21 bp SEC fee, about 3.6 cents a share). Allow about 1 bp for slippage in real life.
4. **Moves vs the toll:** the average 1-minute move is only 1.5 bp, the 5-minute move 3.5 bp, the 30-minute move 8.6 bp. To break even with a 1 bp cost you must call the direction right about **82%** of the time on a 1-minute trade, **64%** at 5 minutes, **56%** at 30 minutes. Published patterns give about 54-55%.
5. **Edges fade once known:** overnight drift ~3.7% a year before 2021, about zero since (NY Fed, 1 Jul 2026); pre-FOMC drift gone after 2015; an independent replication of a popular SPY momentum system went from Sharpe 1.34 in sample to 0.39 out of sample (2026 preprint); a pre-registered study of 225 opening-range variants found zero survivors after costs (2026 preprint).
6. **Order flow, lead-lag, news speed:** real, but they live at milliseconds: ES-SPY return correlation is 0.008 at 1 ms; prices react to macro news within 5 ms; order-flow forecasts last about two price changes. Minute bars, IEX-only live data and delayed SIP data cannot reach them.
7. **Dealer hedging and 0DTE:** the evidence is split (some papers say 0DTE dampens volatility, one says it raises it) and it is about the **size** of moves, not their direction. Using it needs options open-interest data we do not have.
8. **VWAP rules and "trend day vs range day":** VWAP-rule evidence comes only from vendors and educators. I found no rigorous study that predicts the day type early. Volatility size is forecastable; direction is not.
9. **What we can test:** the free Alpaca history (2016 onward) can test late-day momentum, big-gap fades, a volatility gate, and overnight-vs-intraday drift. Order flow, ES lead-lag, gamma signals and retail-flow signals cannot be tested properly with our data.
10. **Testing reality:** a one-trade-a-day, 30-minute setup needs about **1,100 trades (4.5 years)** to detect a true +1 bp net edge; a 60-session paper test can only see edges above about 4 bp. Paper trading teaches mechanics and measures costs; it cannot prove an edge.
11. **Ranked hypotheses to test next (one pre-registered version each):** late-day continuation on big-move days; long-side fade of big gap-downs; a high-volatility gate; a post-selloff 5-minute reversal; an overnight-vs-intraday control. Only the first two have any real chance; expect "no" answers.
12. **Design advice:** add an edge-over-cost gate and a volatility-regime tag; keep the LLM as a veto only; re-measure spreads when the SEC half-penny tick rule starts on **2 Nov 2026**.
13. **What to tell a beginner:** every trade pays a toll about as big as the best published edge, so doing nothing is a valid result.

---

## 2. Findings table

Six sub-tables. "Verified?" is per item; details of each source are in section 6. Conflicts of interest are flagged in the "Evidence" cell.

### 2A. Momentum, reversal and rule-based setups

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| **A1 Market intraday momentum (Gao)** | Return from yesterday's close to 10:00 predicts the 15:30-16:00 return, same sign | **Strong that it existed** (1993-2013, peer-reviewed): stronger on volatile, high-volume, recession and news days; also in ten other ETFs. **Small:** an independent replication on SPY 1996-2013 got R² 1.7% (first half-hour), 2.6% (with the 15:00-15:30 return), out-of-sample R² 1.7% and 2.3%. Outside the US it is patchy: China and Japan yes, Korea weak, Hong Kong and Singapore none; where it exists it was weaker in the Feb-Mar 2020 COVID crash | Last 30 min; SPY (S&P 500 ETF) | Not stated in the abstract; the replication paper has no cost analysis | [Gao et al. 2018 (RePEc)](https://ideas.repec.org/a/eee/jfinec/v129y2018i2p394-414.html); [Limkriangkrai et al. 2023 (PDF)](https://researchmgt.monash.edu/ws/files/519509174/494419119_oa.pdf) | Verified (abstract + replication PDF). Gao full text not opened |
| **A2 Rest-of-day predictor (Baltussen)** | Return from yesterday's close to 15:30 predicts the last 30 min; linked to dealers and leveraged ETFs hedging short gamma; reverses over following days | **Strong**: 60+ futures, Dec 1974-May 2020; pooled equity-index futures t = 7.29, out-of-sample R² 2.88%; similar in 1974-99 and 2000-20; timing-strategy Sharpe 0.87-1.73 by asset class. Caveat: authors thank SqueezeMetrics (a gamma-data vendor) for data; two authors are at Robeco | Last 30 min; equity, bond, commodity, FX futures | **No** in main results. Authors: S&P futures stay positive only if cost is no more than 1 tick | [Baltussen et al. 2021 (PDF)](https://academicweb.nd.edu/~zda/intramom.pdf) | Verified (PDF) |
| **A3 Same idea elsewhere** | First-half-hour return predicts last-half-hour return in FX and other stock markets | **Mixed.** RUB/USD 2005-2014: linked to liquidity providers' risk aversion to holding overnight. 16 developed markets 2005-2017: significant; the equally weighted global portfolio has Sharpe 1.26-1.77 as reported | Last 30 min; FX and 16 countries | Li et al.: no cost analysis found (I searched the text); Elaut: full text not opened | [Elaut et al. 2018](https://ideas.repec.org/a/eee/finmar/v37y2018icp35-51.html); [Li, Sakkas, Urquhart 2022 (PDF)](https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf) | Verified (RePEc abstract; PDF) |
| **A4 Decay since publication and since the 0DTE boom** | Does A1/A2 still work on SPY after ~2014 and after daily 0DTE expiries? (Cboe: 0DTE was 5% of SPX option volume in 2016, ~50% in Aug 2023) | **Mixed, leaning weaker.** Baltussen still finds it in 2000-2020. Adams et al. 2025: dealer hedging needs predict "stronger order-flow reversals, lower momentum returns, and lower volatility". Paz 2026 (independent replication of a popular SPY system): Sharpe 1.34 in sample, **0.39 out of sample** (May 2024-Mar 2026), return 9.4% vs 29.5% buy-and-hold. Concretum's own Aug 2026 note: trend profits "have not disappeared, but they have weakened during certain parts of the trading session" (paywalled). My 40 sessions: correlation of the open-to-15:29 return (no overnight part) with the last-30-min return is negative (-0.32 SPY, -0.14 QQQ), **not evidence** (n = 40, standard error ~0.16) | Last 30 min to full day; SPY | Paz: not stated in abstract | [Adams et al. 2025 (Crossref abstract)](https://doi.org/10.2139/ssrn.5641974); [Paz 2026](https://doi.org/10.2139/ssrn.7290621); [Cboe](https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options); [Concretum preview](https://concretumgroup.substack.com/p/the-intraday-seasonality-of-market) | Abstracts only; Paz and Adams are unrefereed SSRN preprints; Concretum is a vendor blog (substance UNVERIFIED) |
| **A5 "Noise Area" SPY momentum (Zarattini, Aziz, Barbon)** | Trade with the trend when price leaves a band around the open; trailing stop; leverage up to 4x | **Weak to mixed.** Paper: 2007-early 2024, 1,985% total, 19.6% a year, Sharpe 1.33 (1.17 with a market-impact model); $0.09 a share per trade on average, $0.18 over the last 7 years. **Conflict:** authors run Concretum Research (research/software) and Bear Bull Traders (trading education). Independent replication: in-sample matches, out-of-sample Sharpe 0.39 (A4). Our lab's approximate replication: gross per trade fell from +2.4 bp (2024) to +1.2 (2025) to -1.0 (2026) (derived from the repo's yearly table plus 3.0 bp) | Intraday, 1-2 trades a day; SPY | **Light costs:** $0.0035 a share commission + $0.001 a share slippage = about $0.009 round trip = **0.12 bp** at $766 (ours: 0.47+ bp). Text search finds no SEC or FINRA fees. Slippage was measured against the minute's opening print, which may understate the half-spread (my inference) | [Beat the Market (PDF)](https://concretumgroup.com/wp-content/uploads/2026/02/Beat-the-Market.pdf) | Verified (PDF) for what the paper says; not independently verified as true |
| **A6 Opening range breakout (ORB)** | Trade a break of the first 5/15/30/60-minute high or low | **Weak; none after costs.** Holmberg 2013 reports positive returns (abstract; market and costs not stated). Zarattini et al. positive on QQQ/"stocks in play" (vendor authors, thin costs, see A5). **Fetna 2026, pre-registered: 0 of 225 cells pass** (9 futures, 2010-2026, 1-minute data); median gross edge -0.01 tick; the 5-minute range is the worst. Mesfin 2026: ORB long T = 0.88, unstable. Our lab: ORB5_QQQ gross +9.0 bp/trade in 2024 fading to +1.2 in 2025 and -1.6 in 2026 (derived) | 5-60 min; QQQ, stocks, futures | Fetna and Mesfin: yes, fail | [Holmberg et al. 2013](https://ideas.repec.org/a/eee/finlet/v10y2013i1p27-33.html); [Fetna 2026](https://doi.org/10.2139/ssrn.7428398); [Mesfin 2026](https://arxiv.org/abs/2605.04004) | Verified (abstracts); Fetna and Mesfin are single-author preprints |
| **A7 Rule mining on 5-minute bars** | Thousands of moving-average, breakout and indicator rules | **None.** Marshall et al. 2008: none of 7,846 popular intraday rules profitable after correcting for data snooping. Mesfin 2026: 14 signal families built from open/high/low/close/volume bars on Micro E-mini Nasdaq futures, 947 days 2021-2025, walk-forward: none pass; 11 fail because gross return (0.07-1.50 points) is below the 2.0-point friction | 5 min; US equities (2008), futures (2026) | Yes (Mesfin): fail | [Marshall et al. 2008](https://ideas.repec.org/a/eee/empfin/v15y2008i2p199-210.html); [Mesfin 2026](https://arxiv.org/abs/2605.04004) | Verified (abstracts) |
| **A8 Short-term reversal and liquidity** | After a sharp move, part reverses within an hour as liquidity providers get paid | **Mixed to weak for our use.** Heston et al. 2010: reversal from temporary liquidity imbalances lasting under an hour, plus bid-ask bounce (NYSE stocks 2001-2005, cross-section). Brogaard-Han-Kim 2024: stock residual-reversal strategy "earns 162.3% annualized" (abstract; cost handling unknown; cross-section, not SPY). SPY event-time preprint: expected response near zero at short lags (1-5,000 ticks); at longer lags, big negative moves are followed by stronger rebounds than big positive moves are followed by pullbacks. **My data:** lag-1 autocorrelation of 1-minute returns -0.016 (SPY), 5-minute -0.05; those imply a maximum gross edge of only **0.03 bp** and **0.19 bp** per trade | 1 min to 1 hour; stocks, SPY | Mostly no | [Heston et al. 2010](https://arxiv.org/abs/1005.3535); [Brogaard et al. 2024](https://doi.org/10.2139/ssrn.4731947); [Vlasiuk and Smirnov 2025](https://arxiv.org/abs/2511.06177) | Verified (PDF / abstracts); preprints |

### 2B. Time of day, the open, the close, overnight

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| **B1 Time-of-day profile** | Volume and volatility are highest at the open and into the close; spreads are widest at the open | **Strong as a description; no direction.** McInish & Wood 1992: minute-by-minute spread against time of day is a reverse-J shape. **Measured (40 sessions):** SPY does 11.6% of the day's volume in the first 30 min and **21.3% in the last 30 min**; mean 1-minute move is 2.5 bp in the first 30 min vs 1.1-1.4 bp in the afternoon (QQQ 5.0 vs 1.5-1.8). **Measured (one day of quotes, 28 Sep):** SPY median spread 2 cents, but **1 cent from 15:30-16:00**; QQQ median **4 cents** in the first half-hour vs 2-3 cents later | Whole day; SPY, QQQ | Costs vary by time of day | [McInish & Wood 1992](https://ideas.repec.org/a/bla/jfinan/v47y1992i2p753-64.html); my scripts `work/tod.py`, `work/spreads.py` | Verified (abstract; my own measurement, 1 day of quotes only) |
| **B2 Same-time-of-day continuation** | Return in one half-hour slot predicts the same slot on following days | **Mixed.** Heston et al. 2010: lasts at least 40 trading days (NYSE stocks 2001-2005, cross-section). Volume, order imbalance, volatility and spreads show similar patterns but do not explain it. Authors: "timing trades can reduce execution costs by the equivalent of the effective spread". Bogousslavsky 2016: infrequent-rebalancing model that produces such autocorrelations. Not tested on SPY alone | Half-hour; NYSE stocks | Not a trading test; cost benefit is on execution timing | [Heston et al. 2010](https://arxiv.org/abs/1005.3535); [Bogousslavsky 2016](https://ideas.repec.org/a/bla/jfinan/v71y2016i6p2967-3006.html) | Verified (PDF / RePEc abstract) |
| **B3 Overnight vs intraday returns** | Most stock-market gains came overnight; intraday was flat or negative | **Strong description for stocks (1990s-2010s), decaying for futures.** Lou, Polk, Skouras 2019: 14 strategies earn their profits either overnight or intraday, usually with opposite signs. Glasserman et al. 2025 (preprint): "over the past 30 years, nearly all the gains ... overnight, while average intraday returns have been negative or flat". Berkman et al. 2012: overnight gains reverse during the day in retail-attention stocks; the extra cost of buying near the open often exceeds the effective half spread. Our bot is flat every night, so it cannot collect the overnight part | Daily; US stocks and indices | n/a | [Lou et al. 2019 (PDF)](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf); [Glasserman et al. 2025](https://arxiv.org/abs/2507.04481); [Berkman et al. 2012](https://ideas.repec.org/a/cup/jfinqa/v47y2012i04p715-741_00.html) | Verified (PDF / abstracts) |
| **B4 Overnight drift (2:00-3:00 a.m. ET) in S&P futures** | Long E-mini during the European open | **Was strong, now gone.** Sharpe 1.1 before costs and **-0.5 after bid-ask spreads** (the authors' own words). NY Fed, 1 Jul 2026: about 3.7% a year (1998-2020) and about zero since 2021; the spread of closing order imbalances halved (SD 6.5% to 2.9%) | 1 hour overnight; E-mini futures | **Yes: negative** | [Boyarchenko et al. 2023 (PDF)](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf); [NY Fed 2026](https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/) | Verified (PDF; official page) |
| **B5 Pre-market and after-hours information** | Prices move before the open; after-hours trades carry more information per trade | **Mixed.** Barclay (& Hendershott) 2003: after-hours price discovery is real but inefficient; prices are less noisy before the open than after the close. Not usable by a regular-hours bot. Whether Alpaca's SIP bars include extended hours was not verified | Extended hours; US stocks | n/a | [Barclay 2003 (RePEc)](https://ideas.repec.org/a/oup/rfinst/v16y2003i4p1041-1073.html) | Verified (abstract). RePEc lists only Barclay; the co-author is from memory (UNVERIFIED) |

### 2C. VWAP, day type, volatility

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| **C1 VWAP trend rules** | Long when price is above VWAP, short when below | **Weak.** Zarattini & Aziz (vendor and education authors): QQQ 2018-Sep 2023, +671% vs +126% buy-and-hold, Sharpe 2.1, max drawdown 9.4%; 1-minute bars; 56% of 1-minute candles closed above VWAP in a market that went from $156 to $358 (bull-market drift); TQQQ (3x) version +8,242%. Our lab OOS: 4,013 trades, gross only +0.26 bp, about 16 trades a day. No independent replication found | 1 min; QQQ | **Commission $0.0005 a share; zero slippage assumed** | [VWAP paper (PDF)](https://concretumgroup.com/wp-content/uploads/2026/02/Volume-Weighted-Average-Price.pdf); repo backtest report | Verified (PDF) for what it says |
| **C2 VWAP as execution benchmark** | Institutions measure and schedule orders against VWAP | **Strong as practice; no evidence it predicts.** Theory only: Choi, Larsen, Seppi: benchmark-driven trading creates predictable intraday price-pressure patterns and reduces liquidity (model, not data). No peer-reviewed test of VWAP predicting SPY/QQQ found | Full day | n/a | [Choi, Larsen, Seppi](https://arxiv.org/abs/1803.08336) | Verified (abstract) |
| **C3 Trend day vs range day, predicted early** | Use the gap, overnight range, VIX, prior range, first-hour range | **None found.** No study I could open predicts day type early with out-of-sample evidence. Practitioner pages claim narrow prior ranges and big gaps raise trend-day odds; those are claims to test. What is predictable is the **size** of moves (C4) | Day; SPY | n/a | Practitioner pages seen in search results only (not opened) | UNVERIFIED |
| **C4 Volatility clustering as a filter** | Volatility is persistent and has a daily rhythm, so it can be forecast | **Strong for size, not direction.** Corsi 2009 (HAR model): "remarkably good forecasting performance". Ardia & Vaudescal 2026 (preprint): public-data dealer net gamma predicts about 36% lower next-half-hour variance (SPX; also SPY and QQQ options). Singh 2026 (preprint): a related signal "improves in 2024 and reverses in 2025". Amaya et al. 2025 (Cboe-provided data): typical dealer-gamma effect lowers 30-minute volatility; the maximum raise is 6.4 percentage points vs a 4.6-point standard deviation of all causes. Momentum studies find effects stronger on volatile days (A1, A3) | 5-30 min to day; SPX, SPY | n/a | [Corsi 2009](https://ideas.repec.org/a/oup/jfinec/v7y2009i2p174-196.html); [Ardia & Vaudescal 2026](https://doi.org/10.2139/ssrn.7202999); [Singh 2026](https://doi.org/10.2139/ssrn.7350465); [Amaya et al. 2025 (PDF)](https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf) | Verified (abstracts / PDF); several are preprints; Amaya used Cboe data |

### 2D. Order flow, lead-lag, competition and speed

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| **D1 Order-flow imbalance (OFI)** | Net buying pressure at the best bid and ask | **Strong at the same instant; weak as a forecast.** Cont et al.: OFI explains 65% (R²) of 10-second mid-price changes (50 stocks, TAQ), same-time only. Chordia, Roll, Subrahmanyam 2005: past imbalance predicted the next 5-minute return in 1996 (150 NYSE stocks) but the effect shrank in 1999 and 2002 and "may not be substantial after accounting for transaction costs". Kolm et al. 2023: deep learning on 115 Nasdaq stocks; forecast effective horizon "approximately two average price changes". Briola et al. 2025: 15 Nasdaq stocks 2017-2019; high forecast accuracy "does not necessarily correspond to actionable trading signals", usefulness depends on low-latency hardware, and the authors say history alone cannot reliably backtest such a strategy | Ticks to seconds; US stocks | No (and not testable with zero-cost history) | [Cont et al. 2014](https://arxiv.org/abs/1011.6402); [Chordia et al. 2005 (PDF)](https://escholarship.org/uc/item/8wb6140g); [Kolm et al. 2023](https://doi.org/10.1111/mafi.12413); [Briola et al. 2025](https://arxiv.org/abs/2403.09267) | Verified (PDFs; Kolm via Crossref abstract) |
| **D2 Trade-sign persistence** | Buy/sell signs repeat for tens of thousands of orders | **Strong fact, no profit.** Tóth et al.: persistence is mostly big orders being split (London data). Chordia et al. 2005: order imbalances persist day to day, yet the S&P 500's daily first-order autocorrelation was -0.0015 (1996-2002) because sophisticated traders offset the pressure | Minutes to days | n/a | [Tóth et al.](https://arxiv.org/abs/1108.1632); [Chordia et al. 2005](https://escholarship.org/uc/item/8wb6140g) | Verified |
| **D3 VPIN "flow toxicity"** | Volume-based measure sold as an early-warning signal | **Weak, contested.** Andersen & Bondarenko: VPIN is a poor volatility predictor; its predictive content comes from a mechanical link to trading intensity | Volume buckets | n/a | [Andersen & Bondarenko](https://ideas.repec.org/p/aah/create/2011-50.html) | Verified (abstract) |
| **D4 ES / SPY / QQQ lead-lag** | Futures move first, ETFs follow | **Strong, but at milliseconds.** Hasbrouck (data Mar-May 2000): the E-mini has roughly 90% of price discovery. Budish, Cramton, Shim (2011 data): ES-SPY return correlation is 0.10 at 10 ms and 0.008 at 1 ms; arbitrage windows shrank from a median 97 ms (2005) to 7 ms (2011). Nothing found on lead-lag between QQQ and its top constituents | Milliseconds; S&P 500 | n/a | [Hasbrouck (draft PDF)](https://archive.nyu.edu/bitstream/2451/27374/2/FIN-00-046.pdf); [Budish et al. 2015 (PDF)](http://econweb.umd.edu/~sweeting/hft-arms-race.pdf) | Verified (PDFs; old samples) |
| **D5 Latency-arbitrage tax** | Speed races between fast traders | **Strong.** Aquilina, Budish, O'Neill (London, Aug-Oct 2015, FTSE 350): races are about 20% of volume; take **0.42-0.5 bp** of traded value; roughly one-third of the effective spread (just over 3 bp) and of price impact; typical race 5-10 microseconds; top six firms win over 80% | Microseconds; UK large caps | n/a | [Aquilina et al. 2022 (PDF)](https://ericbudish.org/wp-content/uploads/2022/02/Quantifying-the-High-Frequency-Trading-Arms-Race.pdf) | Verified (PDF; UK, not US) |
| **D6 Speed on macro news** | Trading the seconds after a release | **Strong that prices move fast; weak that profits exist.** SPY and E-mini respond within **5 ms**; profits from trading quickly are small (about $19,000 per event for SPY, $50,000 for ES); speed rose but profits did not | Milliseconds; SPY, ES | Small even before our costs | [Chordia, Green, Kottimukkalur 2018](https://ideas.repec.org/a/oup/rfinst/v31y2018i12p4650-4687..html) | Verified (abstract) |

### 2E. Dealer hedging, 0DTE, leveraged ETFs

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| **E1 Dealer gamma and 0DTE** | Options dealers hedge by trading the underlying; short-dated options have large gamma | **Mixed (split).** Baltussen links it to late-day momentum. Dim, Eraker, Vilkov (2012-Jun 2023, 30-minute data): high 0DTE gamma "does not propagate past volatility"; volume shocks "do not amplify recent past index returns". Adams et al. 2025: 0DTEs dampen volatility. Amaya et al. 2025: see C4. **Opposite view:** Brogaard, Han, Won 2023: a one-SD rise in 0DTE trading raises volatility 9.10% relative to its mean, "primarily driven by speculative retail investors". Maurer & Müller 2026 (1,027 days): 0DTE put-call ratio at the open weakens the next hour, but a rule built on it earns nothing significant out of sample, "before costs as much as after". Cboe (the exchange selling these options): 0DTE share 5% (2016) to 50% (Aug 2023) | 30 min to day; SPX / SPY | Maurer & Müller: no | [Dim et al. 2024 (PDF)](https://westernfinance-portal.org/viewpaper?n=950096); [Brogaard et al. 2023](https://doi.org/10.2139/ssrn.4426358); [Maurer & Müller 2026](https://doi.org/10.2139/ssrn.7339718); [Cboe](https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options) | Verified (PDF / abstracts); several preprints. **Not testable with our data** (needs option open interest by strike) |
| **E2 Leveraged-ETF rebalancing** | Leveraged funds must buy after up-days and sell after down-days, near the close | **Mixed; old numbers.** Tuzun 2013 (Fed): a 1% rise in broad indexes induces rebalancing flows equal to **$1.04 billion** of stock (period not in the abstract); Baltussen ties it to last-30-minute momentum. Current size not verified | Last 30 min; US indices | n/a | [Tuzun 2013](https://www.federalreserve.gov/econres/feds/are-leveraged-and-inverse-etfs-the-new-portfolio-insurers.htm) | Verified (abstract) |

### 2F. Announcements and retail flow

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| **F1 Macro announcements and drift** | Scheduled releases (FOMC decisions in the afternoon; jobs and CPI reports before the open; exact times are in the repo's event calendar) move prices; drift before or after them | **Mixed; decayed.** Lucca & Moench: S&P 500 rose **49 bp** in the 24 hours before FOMC decisions (1994-2011, t above 4.5). Kurov, Wolfe, Gilbert: "essentially disappeared after 2015". No minute-scale post-announcement drift study found. Volatility around known times is the reliable part | 24 hours (FOMC); milliseconds (news) | Not tested | [Lucca & Moench (NY Fed PDF)](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf); [Kurov et al. 2021 (PDF)](https://www.skidmore.edu/economics/documents/KurovWolfeGilbert-TheDisappearingPre-FOMC-Announce-Drift-200914.pdf) | Verified (PDFs) |
| **F2 Retail order flow** | What small investors buy and sell | **Weak for our use.** Boehmer et al. 2021: stocks with net retail buying beat net-selling stocks by about 10 bp over the next week; less than half is order-flow persistence. Barber et al. 2024: the identification method finds only 35% of retail trades and mis-signs 28%; uninformative for 30% of stocks; a quote-midpoint fix cuts signing error to 5%. Berkman et al. 2012 (B3). **No source found on the intraday timing of retail flow in SPY or QQQ** | Weekly; US stocks | No | [Boehmer et al. 2021](https://ideas.repec.org/a/bla/jfinan/v76y2021i5p2249-2305.html); [Barber et al. 2024](https://ideas.repec.org/a/bla/jfinan/v79y2024i4p2403-2427.html) | Verified (abstracts) |

**Conflicts of interest noted:** Concretum Research and Bear Bull Traders (A5, C1: they sell research, software and education); Cboe (E1: sells the options; supplied data to Amaya et al.); SqueezeMetrics (A2: sells gamma data; supplied data to Baltussen et al.); QuantPedia and gamma dashboards such as SpotGamma (sell products; seen in search results, not used as evidence). Preprints without peer review: Paz, Fetna, Mesfin, Adams, Brogaard-Han-Won, Ardia, Maurer, Singh, Valenti, Vlasiuk.

### 2G. Our own backtest, for context (from the repo; not re-run)

Gross bp per trade by year = the repo's net figure at 1.5 bp a side plus 3.0 bp. It shows the same story as the literature: small, and shrinking.

| Setup | 2024 (Sep-Dec) | 2025 | 2026 (to 25 Sep) |
|---|---|---|---|
| ORB5_QQQ | +9.0 (n=82) | +1.2 (n=245) | -1.6 (n=183) |
| NOISE_MOM_SPY (approx. of A5) | +2.4 (n=77) | +1.2 (n=223) | -1.0 (n=182) |
| LAST30_MOM_SPY | -1.5 (n=82) | +0.6 (n=247) | +1.3 (n=184) |
| VWAP_TREND_QQQ | +0.5 (n=1,355) | +0.2 (n=3,971) | 0.0 (n=2,945) |
| GAP_FADE_SPY (both sides) | +4.1 (n=15) | +6.1 (n=71) | +3.8 (n=57) |

Source: `reports/Minute trading backtest results.md`, section 6. Only the gap fade keeps a gross edge above a 1 bp round-trip cost, on very few trades.

---

## 2b. Why minute-scale edges vanish after costs (plain English)

Think of each trade as flipping a slightly weighted coin while paying a toll at the booth every time.

1. **The toll is fixed; the moves are small.** Crossing a 2-cent spread and paying the SEC fee costs about 0.47 bp round trip. The average 1-minute SPY move is 1.5 bp. So the toll takes about **a third** of a typical 1-minute move (two-thirds at a realistic 1 bp cost) and only about 5-12% of a 30-minute move.
2. **The coin is barely weighted.** The best documented patterns explain 1.7-2.9% of the variation (R²). That means being right about 54-55% of the time, not 65-80%.
3. **Faster, cheaper players get there first.** ES and SPY move together only after about 100 ms (correlation 0.008 at 1 ms; Budish et al.). News is priced in 5 ms (Chordia et al. 2018). Speed races take about 0.5 bp of traded value in London large caps (Aquilina et al.). By the time a one-minute bar closes, the information is already in the price.
4. **Order-flow signals expire in a blink.** The forecast horizon of the best order-book models is about two price changes (Kolm et al.), and high accuracy did not mean actionable trades (Briola et al.).
5. **Known edges shrink.** Overnight drift (3.7% a year to about 0) and pre-FOMC drift (49 bp to about 0) faded after publication; the popular SPY momentum system fell from Sharpe 1.34 to 0.39 out of sample.
6. **Costs kill even good-looking edges.** The overnight drift had a Sharpe of 1.1 before spreads and **-0.5 after** (Boyarchenko et al.). A pre-registered study found opening-range breakouts earn "inside the spread" (Fetna).
7. **Small edges hide in noise.** A 1 bp edge on 30-minute moves with a 12 bp standard deviation needs over a thousand trades to see (section 3), so published t-statistics from long samples do not tell you what a few months of trading will show.
8. **Published backtests often assume very low costs.** The popular SPY paper (A5) uses about 0.12 bp round trip (no spread, no SEC fee); the VWAP paper (C1) uses commission only. Ours is 0.47 bp or more.

## 2c. How big a move must a minute trade capture to break even? (SPY and QQQ)

**Explicit cost of one long round trip (buy at the ask, sell at the bid), using our measured spread.** SPY median price $766.4, QQQ $716.6 (40 sessions). SEC fee $20.60 per $1M of sales (0.206 bp, from the repo, not re-verified; the rate is reset by SEC advisories and I could not read the rate on the SEC page). FINRA fee and CAT are below 0.01 bp. Alpaca commission $0.

| Spread | SPY: spread bp | SPY: round trip (bp) | SPY: cents a share | QQQ: spread bp | QQQ: round trip (bp) | QQQ: cents a share |
|---|---|---|---|---|---|---|
| 1 cent | 0.13 | 0.34 | 2.6 | 0.14 | 0.35 | 2.5 |
| **2 cents (measured median)** | **0.26** | **0.47** | **3.6** | **0.28** | **0.49** | **3.5** |
| 3 cents | 0.39 | 0.60 | 4.6 | 0.42 | 0.63 | 4.5 |
| 4 cents | 0.52 | 0.73 | 5.6 | 0.56 | 0.77 | 5.5 |

- **Break-even move: about 0.5 bp (3.6 cents) at best; about 1 bp (7.7 cents) with a realistic slippage allowance** (the repo's "realistic" cost of 0.5 bp a side); **3 bp (23 cents)** at the repo's cautious 1.5 bp a side.
- The measured spread was 1 cent in 34% of SPY quotes, 2 cents in 45%, and 3 cents or more in 21% (one day, 28 Sep 2026, three samples a minute).

**How often you must be right.** If you call the direction right with probability p and a typical move is M, you gain (2p-1) × M on average. Break-even when (2p-1) × M equals the cost C, so p = 0.5 + C / (2M). M below is the measured mean absolute move.

| Horizon | SPY M (bp) | SPY needs at C=0.47 | at C=1.0 | at C=3.0 | QQQ M (bp) | QQQ needs at C=0.49 | at C=1.0 | at C=3.0 |
|---|---|---|---|---|---|---|---|---|
| 1 min | 1.54 | 65% | 82% | impossible | 2.43 | 60% | 71% | impossible |
| 5 min | 3.46 | 57% | 64% | 93% | 5.34 | 55% | 59% | 78% |
| 15 min | 5.97 | 54% | 58% | 75% | 9.26 | 53% | 55% | 66% |
| 30 min | 8.62 | 53% | 56% | 67% | 13.44 | 52% | 54% | 61% |
| 60 min | 11.39 | 52% | 54% | 63% | 16.86 | 51% | 53% | 59% |

(QQQ figures at C=0.47 differ from C=0.49 by less than 1 point.) **Reading:** at 1-minute horizons the toll needs an 80%-plus hit rate, which no published signal comes near. From 30 minutes up, the needed hit rate (53-56%) is in the range of the best published effects (54-55%), which is why the only candidates worth testing are 30-minute-scale ones.

**What the published effect is worth.** A first-half-hour or rest-of-day R² of 1.7% means a correlation of 0.13, a hit rate of 54.2%, and a gross gain of about 0.8 × 0.13 × 10.4 bp (the standard deviation of SPY's last-half-hour return now) = **1.1 bp per trade** (R² 2.6%: 1.3 bp). That is the same size as the toll, and it matches the lab's measured LAST30_MOM_SPY gross of +0.96 bp. (My calculation; `work/calc.py`.)

**Costs move with time of day and events.** On 28 Sep QQQ's median spread was 4 cents in the first half-hour (round trip about 0.77 bp) against 2-3 cents later. The SEC's half-penny tick rule and lower access-fee cap start on the first business day of November 2026 (Monday 2 Nov). Whether SPY or QQQ qualify (they need a time-weighted average quoted spread of $0.015 or less; my one-day samples averaged 1.9 and 2.2 cents) is **UNVERIFIED**, so re-measure spreads in November.

---

## 3. What we can test with our data

We have cached SIP 1-minute bars for SPY and QQQ (Aug 2024 to Sep 2026 in the main lab run; the cache on disk now holds Aug-Sep 2026), can download SIP daily and minute bars back to 2016 from Alpaca's free historical feed (**verified**: Alpaca's docs list free-plan historical data "since 2016" with the most recent 15 minutes withheld, 200 calls a minute; live real-time data on the free plan is IEX only), and have options quotes that are only "indicative".

| Effect | Exact data needed | Have it? | Verdict |
|---|---|---|---|
| Late-day momentum (A1, A2) | SIP 1-min (or 5/30-min) bars, regular hours; previous session's official close (daily bar); the 15:29 bar close, or the 09:59 bar close | Yes, 2016-2026 | **Testable now.** Split at May 2022 (daily 0DTE expiries) |
| Opening range, Noise Area, VWAP, EMA, PDH/PDL (A5-A7, C1) | 1-min bars with volume (VWAP needs SIP volume; IEX live volume is only a few percent of SIP) | Yes | Testable; mostly done for 2024-26; 2016-2024 run outstanding |
| Big-gap fade (H2) | 09:30 bar open, previous official close, bars 09:30-09:34 | Yes | Testable; low power (below) |
| Time-of-day cost and volatility profile (B1) | Bars (range, volume, trade count) plus historical quotes for spreads | Bars yes; quotes 1 day cached, more downloadable (heavy) | Testable; spreads by time of day need quotes |
| Overnight vs intraday (B3, H5) | Daily bars (open, close) | Yes | Testable in minutes |
| Half-hour periodicity (B2) | 30-min SPY/QQQ returns (index test); many stocks for the real cross-sectional test | Yes | Testable; index version has little power |
| Trend/range day prediction (C3) | Prior-day high/low/close, first-hour range, gap; overnight range needs pre-market bars or ES; VIX needs another source | OHLC yes; the rest unverified | Partly testable; for volatility, not direction |
| Volatility gate (C4, H3) | Realized range from bars | Yes | Testable |
| Order-flow imbalance, trade sign (D1, D2) | Historical trades plus quotes (tick data) for sample days | Historical yes; **live SIP no** (IEX only) | Research only; not usable live; minute-bar proxies are crude (UNVERIFIED) |
| ES lead-lag (D4) | E-mini ticks with millisecond timestamps | No | **Not testable** |
| Dealer gamma, 0DTE (E1) | Option open interest and greeks by strike, 0DTE volume | No (indicative quotes only) | **Not testable** |
| Macro announcements (F1) | 1-min bars (with pre-market for 08:30 releases) plus exact release times | Bars yes; the repo's event calendar starts 29 Sep 2026; 2016-2025 dates are public but not in the repo | Testable for volatility around known times; direction not exploitable |
| Retail flow (F2) | Trades with exchange code and sub-penny prices | Historical trades yes | Low value: the method is inaccurate and works at weekly horizons |
| Pre-market information (B5) | Extended-hours bars | Unverified | Unknown |

### Sample-size reality check (my calculation; 80% power)

Trades needed to detect a true **net** edge, using the measured standard deviation of returns over the holding period (80% power). "Strict" uses the lab's 0.0018 bar.

| Horizon | Trade std dev (bp) | Edge to detect (bp) | Trades, p<0.05 | Trades, p<0.0018 | Years at 250 a year (p<0.05) |
|---|---|---|---|---|---|
| 1 min | 2.19 | 0.25 | 602 | 1,203 | 2.4 |
| 1 min | 2.19 | 0.50 | 150 | 301 | 0.6 |
| 5 min | 4.81 | 0.50 | 726 | 1,451 | 2.9 |
| 30 min | 12.04 | 0.50 | 4,546 | 9,093 | 18 |
| 30 min | 12.04 | 1.00 | 1,136 | 2,273 | 4.5 |

Smallest edge a 30-minute, one-trade-a-day test can detect: **60 trades: 4.4 bp; 250 trades: 2.1 bp; 500 trades: 1.5 bp; about 2,300 trades (2016-2024 sessions): 0.7 bp.** Conclusion: the 2016-2024 history is the only way to get evidence that could settle a 1 bp question; a 60-session paper test cannot.

### Facts measured from the cached bars (Aug-Sep 2026; my own numbers)

| | SPY | QQQ |
|---|---|---|
| Median price | $766.4 | $716.6 |
| Realized volatility (annualized, from 1-min returns) | 6.9% | 11.0% |
| Mean / median absolute 1-min move (bp) | 1.54 / 1.11 | 2.43 / 1.68 |
| Mean absolute 5 / 15 / 30 / 60-min move (bp) | 3.5 / 6.0 / 8.6 / 11.4 | 5.3 / 9.3 / 13.4 / 16.9 |
| Std dev of last-30-min return (bp) | 10.4 | 15.9 |
| Lag-1 autocorrelation, 1-min / 5-min | -0.016 / -0.050 (standard errors 0.008 / 0.018) | -0.011 / -0.031 |
| Median daily high-low range (bp) | 56.7 | 94.0 |
| Share of day volume: first / last 30 min | 11.6% / 21.3% | 14.6% / 15.6% |

The period is unusually calm: if typical SPY volatility is about 15% a year (my assumption), costs weigh roughly twice as much now as in a typical year.

---

## 4. Recommendations for the agent design

### 4a. What to include

1. **An edge-over-cost gate (code, not the LLM).** Before any entry, compute the live spread in bp and the setup's own *historical* mean gross edge per trade (from the pre-registered 2016-2024 run). Skip unless historical edge is at least 2x (spread + SEC fee + a 0.5 bp slippage allowance). Today this will skip most setups, and that is the system working.
2. **A volatility-regime tag on every journal line**, and (only if H3 below confirms) a gate. Costs are fixed in bp; moves scale with volatility. In this 6.9%-volatility regime, patterns that need big moves will mostly not trigger.
3. **Time-of-day awareness.** The 15:30-15:55 window has the tightest spreads (SPY median 1 cent on 28 Sep) and 21% of the day's volume; the first half-hour has double the volatility but wider spreads (QQQ 4 cents). Log the spread by time of day for every paper order so the cost curve comes from real fills, not one day of quotes.
4. **Data parity.** Research on SIP, live on IEX: volume-based signals (VWAP, relative volume) differ (the repo's MT-G35 already covers this). Prefer signals that use price only, decided on completed bars, filled at the next bar's open.
5. **Pre-registration and trial counting** (MT-G7): one written definition per hypothesis, thresholds estimated only from earlier sessions, every variant counted. With about 8 variants use 0.05/8 = 0.006 at least; keep the lab's 0.0018 for continuity.
6. **Honest labels on samples:** keep the repo's "INSUFFICIENT SAMPLE" label, and add that even 100 trades of a 30-minute setup can only detect edges of about 3.4 bp or more (section 3), and 60 trades about 4.4 bp.
7. **A cost-model refresh** when the SEC half-penny tick and lower access-fee cap start on 2 Nov 2026, and each October when the SEC fee advisory resets.

### 4b. What to avoid

- **Order-flow, VPIN, tape-reading and level-2 signals:** they live at seconds or less (D1-D3) and need real-time SIP quotes we do not have.
- **ES lead-lag and news-speed trading** (D4, D6): milliseconds.
- **Dealer-gamma and "GEX" dashboards as trade triggers** (E1): the evidence is split, is about volatility size rather than direction, and the dashboards are sold by vendors.
- **Overnight and pre-FOMC drift strategies** (B4, F1): faded, and the bot is flat overnight.
- **Predicting "trend day vs range day" from the gap or prior range** (C3): no evidence; use it only as descriptive tags.
- **Stacking indicators, tuning parameters, or adding variants without counting them** (A7).
- **Trusting backtests that assume commission-only costs, or leveraged ETFs (TQQQ) to inflate returns** (A5, C1).
- **0DTE options** (E1; the repo's own results lost 4-47% of premium per trade).
- **Asking the LLM to predict direction.** No evidence supports it at this horizon; the LLM should stay a veto only (MT-G29).

### 4c. What to test first (order), and the ranked list of hypotheses

**Test order:** H5 (control), then H1, H3, H2, H4. Run them on 2016-01-04 to 2024-08-30 (the period before the lab's 2024-2026 window), with 2024-2026 held out as the final check. One version each. Write the definition, costs and pass rule down before looking at results.

**Costs for every test:** gross, plus 0.5 bp a side (headline) and 1.5 bp a side (stress). **Baselines:** same days and same holding window with a coin-flip direction, and "always long" (to expose drift). **Statistics:** bootstrap over days. **Timing convention:** a bar stamped hh:mm covers hh:mm:00-hh:mm:59; a decision uses only bars completed before the decision time; the fill is at the next bar's open; "previous close" is the previous session's official closing-auction price; every threshold is estimated only from sessions strictly before the day being traded.

**Honest statement first:** none of these five is expected to be a reliable edge. Only H1 and H2 have peer-reviewed or repo evidence *and* a per-trade edge that could plausibly exceed costs. H3 can only make H1/H2 better or show they are dead; H4 has the thinnest evidence; H5 is a control, not a strategy.

#### H1 (rank 1): Late-day continuation of the rest-of-day move, big-move days only

- **Definition.** SPY only (QQQ afterwards as a replication, never for selection). At 15:30:00, using bars through the 15:29 bar: R = 10,000 × ln(close of 15:29 bar / previous official close). Threshold T = the 80th percentile of |R| over the previous 250 sessions (no trades in the first 250 sessions). If |R| is at least T, trade in the direction of R: enter at the open of the 15:30 bar, exit at the open of the 15:55 bar, no stop. Report long and short sides separately (the live bot is long-only; the long-only cut counts as one extra trial).
- **Why it might survive costs.** (i) Baltussen's mechanism (hedging demand grows with the size of the move) predicts a bigger effect on big-move days: if the published effect is linear and returns are roughly normal, the top fifth of days by |R| should earn about 2.2 times the average, roughly 2.4 bp gross (my estimate); (ii) 15:30-15:55 has the tightest spreads of the day; (iii) about 50 round trips a year; (iv) about 490 trades over 2016-2024 (my estimate), enough to detect about 1.8 bp.
- **Why it might not.** Post-2022 dealer gamma may have flipped the sign (Adams et al.); my 40 sessions show a negative correlation; the independent replication (Paz) decayed.
- **Pass rule.** Gross of at least 2 bp in **both** 2016-Apr 2022 and May 2022-Aug 2024, net 95% range above zero at 0.5 bp a side, and p below 0.0018 against the random-direction baseline. Fail = write "decayed" and stop.

#### H2 (rank 2): Long-side fade of a big opening gap-down

- **Definition.** This is the lab's registered GAP_FADE_SPY, long side only. O = open of the 09:30 bar; PC = previous official close; g = O / PC - 1. Trigger: g at most -0.5% **and** the highest high of the 09:30-09:34 bars is below PC (gap not filled). Enter long at the open of the 09:35 bar; target = PC (limit); stop = entry minus |O - PC|; otherwise exit at the open of the 15:55 bar.
- **Why it might survive costs.** The move is large (a 0.5% gap is 50 bp), so a 1 bp cost is about 2% of it; the lab's version was positive gross in each of 2024, 2025 and 2026 (+4.1, +6.1, +3.8 bp, derived); overnight moves partly reverse in stocks (Berkman, Lou). The repo cites Grant, Wolf and Yu 2005 (gap reversals in S&P futures reduced by the spread; **not re-verified by me**).
- **Why it might not.** Index gaps are usually news-driven and can keep going; the lab's 95% range at 1.5 bp a side was -8.7 to +16.7 bp; QQQ showed nothing.
- **Power warning.** Roughly 350 long trades in ten years (my estimate from the lab's counts) with a trade standard deviation of about 56 bp (backed out of the lab's 95% range) means only edges above about **8 bp net** are detectable. A "no" would be inconclusive. Say so in the report.
- **Pass rule.** Net 95% range above zero at 0.5 bp a side and p below 0.0018; otherwise "not shown".

#### H3 (rank 3): High-volatility gate (a test of *when* H1 and H2 work)

- **Definition.** Known at 09:30: V = previous session's range, (high - low) / close, divided by the median of the same statistic over the 250 sessions before it. High-volatility day if V is in the top third of the prior 250 sessions; otherwise low. Run H1 and H2 separately in each state.
- **Why it might help.** Costs are fixed in bp while moves grow with volatility; the momentum papers find effects stronger on volatile days (Gao abstract; Limkriangkrai: volatility matters more than volume).
- **Pass rule.** Gross edge in the high state at least 2 bp and in the low state at most 1 bp. This cannot create an edge; it tells the bot when to stay out. It counts as extra trials.

#### H4 (rank 4): Post-selloff 5-minute liquidity reversal, long only

- **Definition.** At each 5-minute boundary between 10:00 and 15:25, r5 = 10,000 × ln(close now / close 5 minutes earlier). Scale s = 1.4826 × the median |r5| for the same clock time over the previous 60 sessions. z = r5 / s. Trigger the first time each day that z is at most -3 (skip days with a scheduled major event). Enter long at the next bar's open; exit 15 minutes later or at the open of the 15:55 bar, whichever is first. No stop (record the worst dip).
- **Why it might survive costs.** A 3-sigma drop is about 14 bp, so a 1 bp cost is small; liquidity-driven selling tends to revert within an hour (Heston et al.; the SPY event-time preprint hints at stronger rebounds after negative pushes).
- **Why it might not.** Evidence is thin (a cross-sectional paper and preprints); news-driven drops continue; events cluster in crash weeks. I expect very roughly 100-250 events in ten years, able to detect about 3.5 bp (rough estimate).

#### H5 (rank 5, run first): Overnight vs intraday drift, as a control

- **Definition.** Daily bars for SPY and QQQ, 2016-2026. Overnight = ln(open / previous close); intraday = ln(close / open). Report by calendar year: mean bp per day, t-statistic, and the long-only "buy at the open, sell at 15:55" baseline.
- **Why it matters.** It is not an edge. It tells us whether long-only intraday trades carry a positive, zero or negative drift, which fixes a known lab follow-up ("market drift is not matched" in the random baseline), and whether the overnight premium has faded in ETFs the way the NY Fed found for futures. The bot cannot hold overnight, so it cannot collect it.

**Considered and not recommended:** ORB (Fetna: 0 of 225 pass); VWAP trend (vendor evidence only, about 16 trades a day); EMA 9/21 (lab gross +2.1 bp but negative in year one); same-slot continuation on the index (little power); OFI and lead-lag (milliseconds); gamma signals (no data); pre-FOMC and overnight drift (decayed).

### 4d. What a beginner should be told

- "A basis point is one hundredth of a percent. Every SPY or QQQ trade costs about half a basis point just to get in and out, and about one in practice. The best pattern anyone has published is worth about one basis point. So the toll and the prize are the same size."
- "Patterns are like coins weighted 55/45. That is enough at 30 minutes and useless at 1 minute, because the toll is a third of the average 1-minute move."
- "Patterns that were published stopped working: overnight drift, pre-Fed drift, and the popular SPY momentum system after 2024. Assume any pattern you read about has already faded."
- "You can not prove a one-basis-point edge with a few months of paper trades. Paper trading is for learning the mechanics and measuring real costs."
- "Most days the right answer is to do nothing."

---

## 5. Open questions and things I could not verify

1. **No peer-reviewed post-2013 SPY-specific test** of late-day momentum was found. The nearest are Baltussen (futures, to May 2020, still present), the Paz and Adams preprints, and the vendor's Aug 2026 note. H1 on 2016-2024 is what settles it.
2. **Blocked pages:** SSRN, ScienceDirect and Wiley returned "403". For Gao et al., Kolm et al., Adams et al., Brogaard et al., Paz, Fetna and the 2026 preprints I read only the abstract (via RePEc, arXiv or Crossref metadata). Gao's R² figures come from the independent replication, not from Gao's own tables.
3. **Not opened:** Barbon & Buraschi "Gamma fragility" (cited by Baltussen as an unpublished paper); Andersen & Bollerslev 1997 and Admati & Pfleiderer 1988 (RePEc shows no abstract, so I did not use them for claims); Kambouroudis et al. 2021 (seen in a search snippet); Berkowitz-Logue-Noser 1988 (VWAP benchmark origin; page not found); Grant, Wolf & Yu 2005 (cited in the repo only).
4. **Search budget:** the web-search tool hit its 200-call limit near the end. That stopped me from searching for the intraday timing of retail order flow, for trend-day prediction studies beyond one search, and for further 2025-2026 SPY/QQQ intraday work. Crossref and arXiv lookups filled some gaps. Absence of a source is not proof that none exists.
5. **Costs from the repo, not re-verified:** SEC fee $20.60 per $1M, FINRA fee $0.000195 a share, CAT fee. I confirmed the SEC publishes fee advisories (FY2025 dated 8 Apr 2025; FY2026 dated 27 Feb 2026) but could not read the rate. The rate changes; FY2027 starts 1 Oct 2026.
6. **Tick-size change:** the SEC notice of 20 Mar 2026 confirms a compliance date of the first business day of November 2026 (temporary relief granted 31 Oct 2025), and an exchange (MEMX) had applied for relief on the access-fee part so that the tick change could proceed in November 2026 "without further delay"; I did not confirm whether the SEC acted on it or whether SPY and QQQ qualify.
7. **Zarattini cost critique is my inference.** I believe the slippage test (orders sent just before a minute starts, compared with that minute's opening print) understates the half-spread; the paper does not say how the half-spread is treated.
8. **My 40-session numbers** are from a very calm regime and a small sample. The negative last-30-minute correlation is a caution, not a finding (I looked at two symbols and two predictors, so some chance results are expected).
9. **Whether Alpaca SIP bars include pre-market and after-hours**, and where to get VIX history, were not verified.
10. **Retail-flow timing, QQQ-constituent lead-lag, and minute-bar proxies for order flow** (for example, bulk-volume classification) have no source in this report.
11. **Effective spread vs quoted spread:** my spread figures are quoted, from one day, three samples a minute. Real fills (price improvement, queue position, IEX-vs-NBBO differences) will differ; the planned paper-fill review should replace these estimates.

---

## 6. Sources

Verified means read in full text or on the official page/abstract listed. "Crossref" = the abstract in Crossref's metadata record for the DOI. Access date for all web pages: 28-29 Sep 2026.

**A. Momentum, reversal, rules**
1. Gao, Han, Li, Zhou (2018), Market intraday momentum, JFE 129(2):394-414. https://ideas.repec.org/a/eee/jfinec/v129y2018i2p394-414.html. Verified (abstract).
2. Limkriangkrai, Chai, Zheng (2023), Market intraday momentum: APAC evidence, Pacific-Basin Finance Journal 80:102086. https://researchmgt.monash.edu/ws/files/519509174/494419119_oa.pdf. Verified (PDF).
3. Baltussen, Da, Lammers, Martens (2021), Hedging demand and market intraday momentum, JFE 142(1):377-403. https://academicweb.nd.edu/~zda/intramom.pdf (DOI 10.1016/j.jfineco.2021.04.029). Verified (PDF).
4. Elaut, Frömmel, Lampaert (2018), Intraday momentum in FX markets, J. Financial Markets 37:35-51. https://ideas.repec.org/a/eee/finmar/v37y2018icp35-51.html. Verified (abstract).
5. Li, Sakkas, Urquhart (2022), Intraday time series momentum: global evidence, J. Financial Markets 57:100619. https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf. Verified (PDF).
6. Zarattini, Aziz, Barbon, Beat the Market (version 22 Sep 2025; SSRN 4824172). https://concretumgroup.com/wp-content/uploads/2026/02/Beat-the-Market.pdf. Verified (PDF). Conflict: vendor and education authors.
7. Zarattini, Aziz (2023), VWAP: The Holy Grail for Day Trading Systems (SSRN 4631351). https://concretumgroup.com/wp-content/uploads/2026/02/Volume-Weighted-Average-Price.pdf. Verified (PDF). Conflict as above.
8. Paz (2026), Out-of-Sample Evaluation of an Intraday Momentum Strategy for the S&P 500 ETF (SPY), SSRN 7290621. https://doi.org/10.2139/ssrn.7290621. Verified (Crossref abstract); preprint.
9. Fetna (2026), Opening-Range Breakout Does Not Survive Trading Costs, SSRN 7428398. https://doi.org/10.2139/ssrn.7428398. Verified (Crossref abstract); preprint.
10. Mesfin (2026), Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures, arXiv 2605.04004 v3. https://arxiv.org/abs/2605.04004. Verified (abstract); single-author preprint.
11. Concretum Research (7 Aug 2026), The Intraday Seasonality of Market Trends. https://concretumgroup.substack.com/p/the-intraday-seasonality-of-market. Preview only (paywalled); vendor blog; substance UNVERIFIED.
12. Holmberg, Lönnbark, Lundström (2013), Assessing the profitability of intraday opening range breakout strategies, Finance Research Letters 10(1):27-33. https://ideas.repec.org/a/eee/finlet/v10y2013i1p27-33.html. Verified (abstract).
13. Marshall, Cahan, Cahan (2008), Does intraday technical analysis in the U.S. equity market have value?, J. Empirical Finance 15(2):199-210. https://ideas.repec.org/a/eee/empfin/v15y2008i2p199-210.html. Verified (abstract).
14. Heston, Korajczyk, Sadka (2010), Intraday patterns in the cross-section of stock returns, J. Finance 65(4):1369-1407. https://arxiv.org/abs/1005.3535 (PDF read). Verified.
15. Brogaard, Han, Kim (2024), Intraday Residual Reversal in the U.S. Stock Market, SSRN 4731947. https://doi.org/10.2139/ssrn.4731947. Verified (Crossref abstract); preprint.
16. Vlasiuk, Smirnov (2025), Push-response anomalies in high-frequency S&P 500 price series, arXiv 2511.06177. https://arxiv.org/abs/2511.06177. Verified (abstract); preprint.

**B. Time of day, overnight**
17. McInish, Wood (1992), An analysis of intraday patterns in bid/ask spreads for NYSE stocks, J. Finance 47(2):753-764. https://ideas.repec.org/a/bla/jfinan/v47y1992i2p753-64.html. Verified (abstract).
18. Bogousslavsky (2016), Infrequent rebalancing, return autocorrelation, and seasonality, J. Finance 71(6):2967-3006. https://ideas.repec.org/a/bla/jfinan/v71y2016i6p2967-3006.html. Verified (abstract).
19. Lou, Polk, Skouras (2019), A tug of war: overnight versus intraday expected returns, JFE 134(1):192-213. https://personal.lse.ac.uk/polk/research/TugOfWar.pdf. Verified (PDF).
20. Boyarchenko, Larsen, Whelan (2023), The Overnight Drift, RFS 36(9):3502-3547 (NY Fed Staff Report 917). https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr917.pdf. Verified (PDF).
21. Boyarchenko, Larsen, Whelan (1 Jul 2026), The Disappearing Overnight Drift, Liberty Street Economics. https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/. Verified (official page).
22. Glasserman, Krstovski, Laliberte, Mamaysky (2025), Does Overnight News Explain Overnight Returns?, arXiv 2507.04481. https://arxiv.org/abs/2507.04481. Verified (abstract); preprint.
23. Berkman, Koch, Tuttle, Zhang (2012), Paying attention: overnight returns and the hidden cost of buying at the open, JFQA 47(4):715-741. https://ideas.repec.org/a/cup/jfinqa/v47y2012i04p715-741_00.html. Verified (abstract).
24. Barclay (and Hendershott) (2003), Price discovery and trading after hours, RFS 16(4):1041-1073. https://ideas.repec.org/a/oup/rfinst/v16y2003i4p1041-1073.html. Verified (abstract); co-author from memory.

**C. VWAP, volatility**
25. Choi, Larsen, Seppi, Equilibrium effects of intraday order-splitting benchmarks, arXiv 1803.08336. https://arxiv.org/abs/1803.08336. Verified (abstract); theory.
26. Corsi (2009), A simple approximate long-memory model of realized volatility, J. Financial Econometrics 7(2):174-196. https://ideas.repec.org/a/oup/jfinec/v7y2009i2p174-196.html. Verified (abstract).
27. Ardia, Vaudescal (2026), The Intraday Gamma-Variance Channel with Public Options Data, SSRN 7202999. https://doi.org/10.2139/ssrn.7202999. Verified (Crossref abstract); preprint.
28. Singh (2026), Inherited State, New Flow, and Intraday Volatility in SPX 0DTE Options, SSRN 7350465. https://doi.org/10.2139/ssrn.7350465. Verified (Crossref abstract); preprint.
29. Valenti (2026), Intraday Price Asymmetry and Next-Day Intraday Returns in the S&P 500, SSRN 6074846. https://doi.org/10.2139/ssrn.6074846. Verified (Crossref abstract); preprint; not used in the table (daily horizon).

**D. Order flow, lead-lag, speed**
30. Cont, Kukanov, Stoikov (2014), The price impact of order book events, J. Financial Econometrics 12(1):47-88. https://arxiv.org/abs/1011.6402. Verified (PDF).
31. Chordia, Roll, Subrahmanyam (2005), Evidence on the speed of convergence to market efficiency, JFE 76:271-292. https://escholarship.org/uc/item/8wb6140g. Verified (PDF, 2004 working-paper version).
32. Kolm, Turiel, Westray (2023), Deep order flow imbalance, Mathematical Finance 33(4):1044-1081. https://doi.org/10.1111/mafi.12413. Verified (Crossref abstract).
33. Briola, Bartolucci, Aste, Deep limit order book forecasting: a microstructural guide (arXiv 2403.09267 v4). https://arxiv.org/abs/2403.09267. Verified (PDF). Search results list a 2025 Quantitative Finance version (UNVERIFIED).
34. Tóth, Palit, Lillo, Farmer (2015), Why is equity order flow so persistent?, JEDC 51:218-239. https://arxiv.org/abs/1108.1632. Verified (abstract).
35. Andersen, Bondarenko, VPIN and the flash crash (J. Financial Markets 17:1-46, 2014). https://ideas.repec.org/p/aah/create/2011-50.html. Verified (abstract).
36. Hasbrouck (2003), Intraday price formation in U.S. equity index markets, J. Finance 58(6):2375-2400 (Nov 2000 draft read). https://archive.nyu.edu/bitstream/2451/27374/2/FIN-00-046.pdf. Verified (draft PDF).
37. Budish, Cramton, Shim (2015), The high-frequency trading arms race, QJE 130(4):1547-1621. http://econweb.umd.edu/~sweeting/hft-arms-race.pdf. Verified (PDF).
38. Aquilina, Budish, O'Neill (2022), Quantifying the high-frequency trading "arms race", QJE 137(1):493-564. https://ericbudish.org/wp-content/uploads/2022/02/Quantifying-the-High-Frequency-Trading-Arms-Race.pdf. Verified (PDF).
39. Chordia, Green, Kottimukkalur (2018), Rent seeking by low-latency traders, RFS 31(12):4650-4687. https://ideas.repec.org/a/oup/rfinst/v31y2018i12p4650-4687..html. Verified (abstract).

**E. Hedging, options, leveraged ETFs**
40. Dim, Eraker, Vilkov (2024), 0DTEs: Trading, gamma risk and volatility propagation (WFA version 14 May 2024). https://westernfinance-portal.org/viewpaper?n=950096. Verified (PDF).
41. Amaya, Garcia-Ares, Pearson, Vasquez (25 Jan 2025), 0DTE Index Options and Market Volatility: How Large is Their Impact? https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf. Verified (PDF); Cboe supplied data.
42. Adams, Dim, Eraker, Fontaine, Ornthanalai, Vilkov (2025), Do S&P500 Options Increase Market Volatility? Evidence from 0DTEs, SSRN 5641974. https://doi.org/10.2139/ssrn.5641974. Verified (Crossref abstract); preprint.
43. Brogaard, Han, Won (2023), Does 0DTE Options Trading Increase Volatility?, SSRN 4426358. https://doi.org/10.2139/ssrn.4426358. Verified (Crossref abstract); preprint.
44. Maurer, Müller (2026), Intraday 0DTE Option Order Flow and S&P 500 Downside Risk, SSRN 7339718. https://doi.org/10.2139/ssrn.7339718. Verified (Crossref abstract); preprint.
45. Xu (Cboe, 8 Sep 2023), Volatility Insights: Much Ado About 0DTEs. https://www.cboe.com/insights/posts/volatility-insights-evaluating-the-market-impact-of-spx-0-dte-options. Verified (page); the exchange is conflicted.
46. Tuzun (2013), Are leveraged and inverse ETFs the new portfolio insurers?, Fed FEDS. https://www.federalreserve.gov/econres/feds/are-leveraged-and-inverse-etfs-the-new-portfolio-insurers.htm. Verified (official abstract).

**F. Announcements, retail**
47. Lucca, Moench (2015), The pre-FOMC announcement drift, J. Finance 70(1):329-371 (NY Fed Staff Report 512). https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf. Verified (PDF).
48. Kurov, Wolfe, Gilbert (2021), The disappearing pre-FOMC announcement drift, Finance Research Letters 40. https://www.skidmore.edu/economics/documents/KurovWolfeGilbert-TheDisappearingPre-FOMC-Announce-Drift-200914.pdf. Verified (PDF).
49. Boehmer, Jones, Zhang, Zhang (2021), Tracking retail investor activity, J. Finance 76(5):2249-2305. https://ideas.repec.org/a/bla/jfinan/v76y2021i5p2249-2305.html. Verified (abstract).
50. Barber, Huang, Jorion, Odean, Schwarz (2024), A (sub)penny for your thoughts, J. Finance 79(4):2403-2427. https://ideas.repec.org/a/bla/jfinan/v79y2024i4p2403-2427.html. Verified (abstract).

**G. Rules, data, costs**
51. SEC Release 34-105058 (20 Mar 2026), notice of MEMX application; states the tick-size and access-fee compliance date of the first business day of November 2026 after the 31 Oct 2025 relief. https://www.sec.gov/files/rules/exorders/2026/34-105058.pdf. Verified (PDF).
52. SEC, Tick sizes small-entity compliance guide (rule text: $0.005 tick where time-weighted average quoted spread is $0.015 or less; the page still shows the original 2025 date). https://www.sec.gov/resources-small-businesses/small-business-compliance-guides/tick-sizes. Verified (page).
53. SEC, Section 31 fee rate advisories (list only; rate not readable). https://www.sec.gov/rules-regulations/fee-rate-advisories. Verified (page list).
54. Alpaca, About Market Data API (free plan: IEX real-time, historical since 2016, latest 15 minutes withheld, 200 calls a minute). https://docs.alpaca.markets/us/docs/about-market-data-api. Verified (page).
55. Alpaca, Market Data FAQ (free live data is IEX only; SIP history must be at least 15 minutes old). https://docs.alpaca.markets/us/docs/market-data-faq. Verified (page).
56. Repo documents read: `MINUTE_TRADING.md`; `reports/Why day traders lose.md` (sections 1-3); `reports/Minute trading backtest results.md` (sections 1-3, 6, 8); `reports/Minute trading research.md` (section 6 costs); `trading/lab/scalp/signals.py` (setup definitions). Local files.

**My scripts (in `work/`, reading the repo's cache read-only):** `movesize.py` (move sizes), `spreads.py` (spreads by time of day), `ac.py` (autocorrelation, last-30-min statistics), `calc.py` (break-even, hit-rate and power tables), `tod.py` (volume and volatility by half-hour). Downloaded PDFs and extracted text are in `work/pdfs` and `work/txt`.
