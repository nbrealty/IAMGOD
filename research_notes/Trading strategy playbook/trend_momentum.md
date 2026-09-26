# Trend-Following and Momentum Strategies (Classic Books + Academic Evidence) — as of Sept 2026

Research method note: web search worked, but direct fetches of aqr.com, alphaarchitect.com, allocatesmartly.com, mebfaber.com, aaii.com, arxiv.org were blocked by the network proxy. Several figures below therefore come from search-result excerpts rather than full-text reads; these are marked "[snippet]". Items marked "[paper, not re-verified this session]" are well-known results of the cited primary paper that I could not re-open. Items with no reliable source are in Gaps. Book content is paraphrased, not quoted.

---

## 1. Turtle Trading rules (Dennis/Eckhardt; Curtis Faith) and Covel's "Trend Following"

### Takeaway
The Turtle rules are fully codeable (Donchian breakouts + ATR-based "N" sizing + 2N stops + pyramiding) and are the template for classic CTA trend following; the edge comes from diversification across many futures markets and a few very large winners, which makes a faithful version hard to run on a $1k–$25k account.

### Cited Findings
- Rules (codeable): System 1 enters long on a break above the prior 20-day high (short below 20-day low); exits on a 10-day opposite breakout; skips a System 1 signal if the previous System 1 breakout in that direction would have been a winner. — [TurtleTrader.com original rules](https://www.turtletrader.com/rules/); [Original Turtle Rules PDF (Oxford Strat mirror)](https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf)
- System 2 (per the same rules doc [paper, not re-verified this session]): enter on 55-day breakout (no skip rule), exit on 20-day opposite breakout. — [Original Turtle Rules PDF](https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf)
- Volatility unit "N" = 20-day ATR (exponentially smoothed in the original); initial stop at 2N from entry. — [Trading Dude/Medium summary](https://medium.com/@trading.dude/discipline-over-prediction-why-the-turtle-trading-rules-still-matter-f0f1d400d58d); [TurtleTrader rules](https://www.turtletrader.com/rules/)
- Sizing (original doc [not re-verified]): 1 Unit = 1% of account / (N × dollars per point); add units every ½N up to 4 units per market, with caps of ~6 units in closely correlated markets, 10 in loosely correlated, 12 per direction. — [Original Turtle Rules PDF](https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf)
- Post-1980s evidence: sources widely state the original rules lost much of their edge without adaptation, results vary widely by market/timeframe, and long drawdowns are normal; I found no rigorous out-of-sample study isolating post-1990 performance of the exact rules. — [search synthesis incl. QuantifiedStrategies](https://www.quantifiedstrategies.com/turtle-trading-strategy/); [PapersWithBacktest "Modernising the Turtle"](https://paperswithbacktest.com/strategies/turtle-trading-strategy)
- Covel's "Trend Following" (book): a practitioner/popular treatment arguing that price-only, rules-based systems with cut-losses/let-profits-run and small per-trade risk explain the long records of trend CTAs (Dunn, Chesapeake, Campbell, JWM etc.). It is advocacy, not a controlled backtest; its performance tables are manager track records (net of fees but survivorship-selected). — [Covel's trendfollowing.com hosts related papers, e.g. Faber whitepaper](https://www.trendfollowing.com/whitepaper/CMT-Simple.pdf) (book content summarized from general knowledge; no direct source fetched)

### Inferences
- Code spec: universe = diversified liquid futures (or ETF proxies); daily bars; signal on close, execute next open; ATR(20); risk 0.5–1% per unit; stop 2N; exits via 10/20-day channel.
- Retail suitability: poor in the original form. One ES futures contract has ~$50/pt; with N of ~60–100 pts, 1N ≈ $3k–5k, so 1% risk sizing needs a ~$300k+ account. Micro futures (MES, MGC, MCL, M2K etc.) and ETFs make a 5–10-market version feasible at $10k–25k but with much less diversification (which is where the edge comes from). On single stocks/ETFs, breakout win rates are low (~30–40% typical for trend systems) so psychological tolerance for long losing streaks is essential.
- Short-side and whipsaw costs matter most in range-bound, low-volatility, mean-reverting regimes (e.g., 2011–2019 and 2023–mid-2025 for CTAs, see §4).

### Gaps
- No verified cost-inclusive, post-1990 out-of-sample backtest of the exact Turtle rules was found; Curtis Faith's "Way of the Turtle" reports backtests for 1996–2006 but I could not verify figures.
- Win rate/drawdown statistics for Turtle rules on stocks not verified.

---

## 2. Moving-average crossovers and the 10-month SMA filter (Faber)

### Takeaway
A monthly "price above 10-month SMA = hold, else cash" rule mainly cuts drawdowns rather than boosting returns; out-of-sample (2006–2025) the 5-asset GTAA kept a low drawdown but CAGR roughly halved vs its original backtest.

### Cited Findings
- Faber (2006, updated 2013): apply 10-month SMA timing separately to each of 5 asset classes — S&P 500, 10-yr Treasuries, MSCI EAFE, GSCI commodities, NAREIT REITs — equal-weight, monthly. — [Faber SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461); [CXO Advisory review](https://www.cxoadvisory.com/technical-trading/long-term-outperformance-from-trends-defined-by-moving-averages/)
- CXO notes the evidence supports enhanced *gross* risk-adjusted performance — i.e., costs/taxes largely not modeled. — [CXO Advisory](https://www.cxoadvisory.com/technical-trading/long-term-outperformance-from-trends-defined-by-moving-averages/)
- Original backtest 1972–2005: Sharpe 0.81, CAGR 11.7%, max DD 9.5%. Out-of-sample 2006–Mar 2025: Sharpe 0.68, CAGR 6.05%, max DD 11.7% (spanning GFC, COVID, 2022). [snippet] — [Concretum Group / Substack GTAA replication](https://concretumgroup.substack.com/p/global-tactical-asset-allocation)
- A 10-year "revisited" edition of the paper exists. — [Faber revisited PDF](https://allocatortraining.com/wp-content/uploads/2023/06/A-Quantitative-Approach-to-Tactical-Asset-Allocation.pdf)

### Inferences
- Code spec: at last trading day of month, for each asset: if close > SMA(10 monthly closes) hold 20%, else put that 20% in T-bills (BIL/SGOV). ~1–3 round trips per asset per year; ETF implementation costs are tiny, but taxable accounts suffer from short-term gains.
- 50/200-day SMA "golden/death cross" is the daily analog; it has similar logic and similar whipsaw vulnerability (e.g., V-shaped recoveries like 2020, late-2018/early-2019, April 2025 tariff shock would be expected to whipsaw — not verified with a source this session).
- Very suitable for $1k–$25k: 5 ETFs, monthly checks, fractional shares make it feasible even at $1k.

### Gaps
- No verified cost-inclusive figures for the 50/200 SMA crossover on SPY post-publication; I did not find a primary source.

---

## 3. Time-series momentum (Moskowitz, Ooi & Pedersen 2012)

### Takeaway
An asset's own past 12-month excess return predicts its next-month return across 58 futures; a vol-scaled diversified TSMOM portfolio earned strong returns with low factor exposure and did best in extreme markets.

### Cited Findings
- 58 liquid futures (equity index, currency, commodity, bond); past 12-month excess return positively predicts future returns; persistence 1–12 months with partial reversal at longer horizons. — [MOP 2012, JFE via ScienceDirect](https://www.sciencedirect.com/science/article/pii/S0304405X11002613); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463)
- Standard factor: 12-month lookback, 1-month hold, each position scaled to a constant ex-ante vol (40% per instrument in the paper [not re-verified]). A diversified portfolio has little exposure to standard factors and performs best in extreme markets. — [AQR TSMOM page](https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum); [AQR data set (updated monthly)](https://www.aqr.com/Insights/Datasets/Time-Series-Momentum-Original-Paper-Data)

### Inferences
- Code spec: monthly, for each instrument sign(r_{t-12,t} − rf) × (target vol / σ_ex-ante); σ from EWMA of daily returns (~60-day center of mass). Retail version: ETFs (SPY, EFA, EEM, TLT, IEF, GLD, DBC, UUP) long/flat rather than long/short.
- Same behavior and regime profile as CTA trend (see §4).

### Gaps
- Exact Sharpe of the original sample (commonly cited >1 gross) not re-verified. Post-2012 out-of-sample Sharpe for the AQR TSMOM dataset not retrieved (aqr.com blocked).

---

## 4. Managed futures / CTA evidence ("A Century of Evidence on Trend-Following", Hurst/Ooi/Pedersen)

### Takeaway
A 1-, 3-, 12-month TSMOM blend across 67 markets was positive in every decade from 1880–2016 after simulated fees and costs, and gained in 8 of the 10 largest 60/40 drawdowns — but real-world CTA indices have had long flat/negative stretches, including a ~15–20% trend-index drawdown in 2024–2025.

### Cited Findings
- Sample: 67 markets (29 commodities, 11 equity indices, 15 bond markets, 12 currency pairs), Jan 1880–Dec 2016; equal-weighted 1-, 3-, 12-month TSMOM signals, portfolio scaled to 10% annualized ex-ante vol. — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026); [AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
- Results reported net of implementation costs and a simulated 2-and-20 fee; performance consistent across the Great Depression, wars, stagflation, 2008, and rising/falling rate periods; positive returns in 8 of the 10 largest 60/40 drawdowns over 137 years. [snippet] — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026); [AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
- Recent live performance: SG Trend Index was down ~15% trailing 12 months as of June 2025 with a max drawdown of ~20.6%, and down >12.5% since April 1, 2024. — [Top Traders Unplugged, June 2025 report](https://www.toptradersunplugged.com/trend-following-performance-report-june-2025/); see also [The Full FX: "CTAs tough start to 2025 continues"](https://thefullfx.com/ctas-tough-start-to-2025-continues/)
- Individual CTA returns are dispersed even within "trend" (CFM study). — [CFM](https://www.cfm.com/steady-trends-the-reality-of-cta-return-dispersion/)

### Inferences
- Regimes: works in sustained macro trends of either direction (1970s inflation, 2008, 2014 oil/USD, 2022 rates/commodities); fails in choppy, reversal-driven markets and sharp V-shaped reversals (2011–2019 low-vol QE era; 2023; spring 2025 tariff shock-and-rebound).
- Note paper-simulated 2/20 fees are larger than retail ETF costs, but simulated returns still exceed live CTA index results after 2009, which suggests some combination of crowding, lower trend strength, and backtest optimism.
- Retail: easiest access is managed-futures ETFs (e.g., DBMF, KMLM, CTA) rather than DIY futures; DIY is feasible only with micro futures and ≥$25k.

### Gaps
- Numeric gross/net CAGR, Sharpe and worst drawdown of the century study not retrieved (paper PDFs blocked). Full-year 2025 and 2026 YTD SG CTA/Trend index numbers not found.

---

## 5. Cross-sectional stock momentum (Jegadeesh & Titman 1993; 12-1) and momentum crashes (Daniel & Moskowitz)

### Takeaway
Buying past 12-month winners (skipping the latest month) and shorting losers has earned a premium for decades out-of-sample, but it is exposed to rare, severe crashes after market rebounds (–45.6% in Mar–Apr 2009), and net-of-cost profitability depends heavily on turnover and trade size; long-only retail versions via ETFs are the practical route.

### Cited Findings
- JT (1993) is the seminal paper; "30 years later" review surveys robustness. — [Springer FMPM review](https://link.springer.com/article/10.1007/s11408-022-00417-8)
- Standard spec (general knowledge of JT/Carhart/UMD, not re-verified this session): rank on returns from t−12 to t−2 (skip most recent month to avoid short-term reversal), long top decile/tercile, short bottom, monthly rebalance; JT's 6/6 strategy earned about 1%/month in 1965–1989.
- Momentum crash: –45.60% in March–April 2009; crashes are partly forecastable, occurring in "panic states" after market declines with high volatility, when losers (high-beta) rebound sharply. A dynamic, vol-/forecast-scaled momentum roughly doubles alpha and Sharpe of static momentum. — [Daniel & Moskowitz, JFE 2016 (PDF)](https://www.kentdaniel.net/papers/published/jfe_16.pdf); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2371227); [NBER WP](https://www.nber.org/system/files/working_papers/w20439/w20439.pdf)
- Costs: Lesmond, Schill & Zhou (2004) argue trading costs erase momentum profits since it trades high-cost stocks; Korajczyk & Sadka find profits survive at smaller scale, with excess returns disappearing only at $4.5–5bn+ invested. Novy-Marx & Velikov estimate ~$5bn capacity for momentum. [snippet] — [Korajczyk & Sadka](https://www.kellogg.northwestern.edu/faculty/korajczy/htm/wp289.pdf); [Novy-Marx & Velikov](https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf); [Patton & Weller on costs of anomalies](https://public.econ.duke.edu/~ap172/Patton_Weller_MF_25sep18.pdf)
- Post-publication decay (general anomalies): across 97 predictors, returns are 26% lower out-of-sample and 58% lower post-publication (≈32% attributable to publication-informed trading); decay is larger for high in-sample-return predictors and smaller where stocks are illiquid/high-idiosyncratic-risk. — [McLean & Pontiff 2016, J. Finance](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623)
- Alpha Architect has a piece on "30 years of out-of-sample" momentum data (could not fetch). — [Alpha Architect](https://alphaarchitect.com/momentum-factor-investing-30-years-of-out-of-sample-data/)

### Inferences
- Regimes: works in trending bull/bear markets with persistent leadership; fails at sharp bear-market reversals (1932, 2009, Nov 2020 "vaccine rotation", early 2016) — the short leg is the main crash driver, so long-only retail versions crash less but have higher market beta.
- Retail ($1k–$25k): a DIY decile portfolio of 20–50 stocks is impractical at $1k and marginal at $25k (position sizes, spreads). Practical options: momentum ETFs (e.g., MTUM) or a concentrated top-10 12-1 ranking of S&P 500 stocks, monthly rebalance, with a market-regime filter (e.g., SPY > 200-day SMA) to reduce crash exposure.
- Daily cadence adds little for 12-1 momentum; monthly rebalance is the evidence-based frequency.

### Gaps
- Exact post-1993 out-of-sample UMD Sharpe/decay magnitude not retrieved (Alpha Architect blocked). No verified estimate of momentum-specific post-publication decay (vs anomaly average).

---

## 6. Dual Momentum — Antonacci's Global Equities Momentum (GEM)

### Takeaway
GEM is a simple monthly rule (US vs. international vs. bonds) whose long backtest shows equity-like returns with roughly half the drawdown of stocks, but it relies on a single signal per month and is prone to whipsaws; post-publication (2014+) results have been notably weaker than the backtest.

### Cited Findings
- Rules: monthly; if SPY 12-month total return > T-bills (BIL), hold the better 12-month performer of SPY vs. VEU (ex-US); otherwise hold aggregate bonds (AGG). — [BestFolio GEM](https://bestfolio.app/strategies/gem); [TuringTrader](https://www.turingtrader.com/portfolios/antonacci-dual-momentum/)
- Backtest 1986-02 to 2026-09: CAGR 12.3%, max drawdown –33.7%, Sharpe 0.99 (vendor backtest; cost treatment not stated — treat as largely cost-ignorant). [snippet] — [BestFolio](https://bestfolio.app/strategies/gem)
- Antonacci's own extended backtest back to earlier decades. — [Antonacci, Medium](https://medium.com/@garyantonacci_30463/extended-backtest-of-global-equities-momentum-dual-momentum-eb12902612e0)
- ReSolve's "Craftsman's perspective" examines GEM's sensitivity to lookback and rebalance-day choices (specification/"luck" risk). — [ReSolve](https://investresolve.com/global-equity-momentum-executive-summary/)

### Inferences
- Regimes: works in extended bear markets (2000–02, 2008); fails in fast V-shaped selloffs (Oct 2018/Dec 2018, Mar 2020, 2022 when bonds also fell — the bond "safe" asset lost too).
- Retail: excellent fit for $1k–$25k (3 ETFs, 1 trade/month at most, commission-free). Daily cadence not needed; checking only at month-end is the rule.

### Gaps
- Independent cost-inclusive live/out-of-sample (2014–2026) CAGR for GEM not verified (AllocateSmartly blocked).

---

## 7. Tactical asset allocation: Faber GTAA and Keller's VAA/DAA

### Takeaway
Keller/Keuning's VAA and DAA add "breadth momentum" crash protection using a fast 13612W momentum score; they produced very low backtest drawdowns but are more prone to whipsaw and overfitting risk than Faber's simpler 10-month SMA.

### Cited Findings
- 13612W momentum = 12×(p0/p1−1) + 4×(p0/p3−1) + 2×(p0/p6−1) + 1×(p0/p12−1). — [penny-vault VAA implementation (GitHub)](https://github.com/penny-vault/vigilant-asset-allocation)
- VAA (2017, "Winning More by Losing Less"): if any offensive asset has negative 13612W, move to the best defensive asset (breadth-based); variants G4 (aggressive, holds 1 asset) and G12 (balanced, up to 5 assets, partial defensive). — [TrendXplorer](https://indexswingtrader.blogspot.com/2017/07/breadth-momentum-and-vigilant-asset.html); [penny-vault](https://github.com/penny-vault/vigilant-asset-allocation)
- DAA separates a "canary" universe (VWO and BND) to signal crash protection. — [Keller & Keuning DAA, SSRN](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3307823_code1935527.pdf?abstractid=3212862)
- Later variant: Bold Asset Allocation (BAA) for rising-yield regimes. — [ResearchGate BAA](https://www.researchgate.net/publication/362263377_Relative_and_Absolute_Momentum_in_Times_of_RisingLow_Yields_Bold_Asset_Allocation_BAA)
- VAA-G4 assets (general knowledge of the paper, not re-verified): offensive SPY, EFA, EEM, AGG; defensive LQD, IEF, SHY; hold top offensive if all four positive, else best defensive; monthly.

### Inferences
- VAA's hair-trigger breadth rule spends large fractions of time defensive; that caps upside in strong bull markets and whipsaws in quick corrections. Keller's papers are in-sample-optimized; treat reported drawdowns as optimistic.
- Retail: ideal for $1k–$25k (monthly, ETFs).

### Gaps
- AllocateSmartly's cost-inclusive VAA/DAA results and post-publication performance not retrieved (site blocked).

---

## 8. Breakout/growth swing trading: O'Neil CAN SLIM, Minervini SEPA/Trend Template, Darvas box

### Takeaway
These are discretionary-leaning growth-stock breakout methods with only partial systematic evidence; academic tests of CAN SLIM show positive abnormal returns in older samples, and a large-sample test of Minervini's rules finds relative strength and a rising 200-day MA are the key filters — but most published evidence is gross of costs and from promoters or small samples.

### Cited Findings
- CAN SLIM derives from O'Neil's study of big winners 1953–1993 (C = current quarterly EPS growth, A = annual EPS growth, N = new product/high, S = supply/demand, L = leader/RS, I = institutional sponsorship, M = market direction). — [Wikipedia: CAN SLIM](https://en.wikipedia.org/wiki/CAN_SLIM); [AAII](https://www.aaii.com/journal/article/william-oneil-can-slim-approach-to-selecting-growth-stocks)
- Olson, Nelson, Witt & Mossman (1998): CAN SLIM on S&P 500 stocks 1984–1992 produced market-adjusted abnormal returns of ~1.81%/month. [snippet] — [ResearchGate: CAN SLIM application](https://www.researchgate.net/publication/326548848_OUTPERFORMING_THE_BROAD_MARKET_AN_APPLICATION_OF_CAN_SLIM_STRATEGY)
- Counter-evidence: a pattern study found no chart pattern produced statistically and economically significant profits across stocks/indices. [snippet, source not clearly identified] — [search synthesis](https://www.researchgate.net/publication/328391954_An_Application_of_Can_Slim_Investing_in_the_Dow_Jones_Benchmark)
- AAII ran a long-lived CAN SLIM screen and published a "revisiting" tribute after O'Neil's death (numbers not retrieved). — [AAII tribute](https://www.aaii.com/journal/article/68036-a-tribute-to-william-o-neil-revisiting-the-can-slim-strategy)
- Minervini-rule test (non-peer-reviewed GitHub project): 44,475 graded breakouts 1985–2026; profit factor rose from 1.75 (RS <50) to 2.42 (RS 95+); a falling 200-day MA cut PF to 1.16. [snippet; unverified, likely gross of costs] — [nipunhsud/signal PR](https://github.com/nipunhsud/signal/pull/9)
- Trend Template (paraphrase of commonly published criteria): price > 150- and 200-day SMA; 150 > 200; 200-day rising ≥1 month; 50 > 150 and 200; price > 50-day; ≥25–30% above 52-week low; within 25% of 52-week high; RS rank ≥70. — [StockGeniuses summary](https://stockgeniuses.com/blog/mark-minervini-trend-template/); [PapersWithBacktest Minervini](https://paperswithbacktest.com/strategies/mark-minervini)

### Inferences
- Code spec (hybrid): daily universe filter = Trend Template + EPS growth (e.g., quarterly EPS +25% YoY); entry = close above base/pivot high (e.g., 20–50-day high after a volatility contraction) on volume ≥1.5× 50-day avg; initial stop 7–8% below entry (O'Neil's rule) or under base low; trail with 50-day SMA or 10-day low; only trade when index is above its 50/200-day (the "M").
- Darvas box: buy breakout above a consolidation "box" top in a stock making new highs, stop just below box bottom, raise stops box by box — essentially a Donchian-style breakout with trailing stop on individual stocks (no rigorous independent evidence found).
- Regimes: works in strong growth-led bull markets (1990s, 2003–07, 2020, 2023–24 AI leadership); fails badly in bear/choppy markets (2000–02, 2008, 2022) where breakouts fail — the "M" filter is essential.
- Retail: well suited to $5k–$25k on a daily cadence (few positions, liquid stocks), but PDT rule (<$25k margin accounts limited to 3 day-trades per 5 days — note FINRA was revising PDT rules in 2025–26; verify current status) and single-stock concentration create high variance. Expect ~35–50% win rates with big dependence on a few winners.

### Gaps
- No peer-reviewed, cost-inclusive, post-2000 test of the full CAN SLIM, SEPA, or Darvas methods found. AAII CAN SLIM screen performance figures not retrieved. Minervini's USIC results are self-reported competition returns and not a systematic test.

---

## 9. Crypto trend/momentum

### Takeaway
Trend following on crypto has strong reported backtests (Sharpe ~1–1.6) mainly because crypto trends are large and persistent; results mostly come from 2015–2026 samples with a few big bull/bear cycles, so data-mining and regime risk are high.

### Cited Findings
- Zarattini, Pagani & Barbon (2025) "Catching Crypto Trends": ensemble of Donchian channels over nine lookbacks with vol-targeted sizing (25% annual vol); on a rotational top-20 liquid coin portfolio Jan 2015–Mar 2025: CAGR ~30%, Sharpe ~1.58, Sortino 2.03, alpha +14%/yr vs BTC, net of 0.10–0.50% fees. For BTC alone, reported net-of-fee Sharpe ~1.56 with max DD ~19% [snippet; this BTC figure may be misattributed — verify in paper]. — [SSRN 5209907](https://papers.ssrn.com/sol3/Delivery.cfm/5209907.pdf?abstractid=5209907&mirid=1); [Concretum summary](https://concretumgroup.com/catching-crypto-trends-a-tactical-approach-for-bitcoin-and-altcoins/)
- TSMOM on six crypto assets, daily data Jan 2018–Mar 2026: annualized 18.0% pre-spot-BTC-ETF (Sharpe 0.82) vs 28.6% post-ETF (Sharpe 1.22); underperformed buy-and-hold by 7.7 pp in the pre-ETF bull market but outperformed by 21.0 pp post-ETF. [snippet; Zenodo preprint, not peer reviewed] — [Zenodo](https://zenodo.org/records/19671502)
- Another study of 8 cryptos (2020–Oct 2025): TSMOM ~32% annual return and better risk-adjusted performance than cross-sectional momentum. [snippet] — [Vilnius University journal](https://www.journals.vu.lt/BATP/en/article/download/44540/42590/138419)
- "A Decade of Evidence of Trend Following Investing in Cryptocurrencies" (arXiv 2009.12155) exists (could not fetch). — [arXiv](https://arxiv.org/pdf/2009.12155)

### Inferences
- Code spec: daily close, long-only (or long/flat) BTC/ETH when price > N-day Donchian high (entry) and exit on shorter-channel low or ATR trailing stop; size by inverse vol (target 20–30%). Long-only crypto trend primarily avoids the –70% to –80% bear markets (2018, 2022).
- Retail: very suitable operationally (24/7, fractional, spot ETFs now available), but fees/spreads on retail exchanges (often 0.1–0.6% per side) and taxes can eat much of the edge for short lookbacks.

### Gaps
- Peer-reviewed crypto trend studies with long out-of-sample periods are scarce; most are preprints. Worst-case drawdowns in live implementations not verified.

---

## Cross-cutting: post-publication decay, costs, and retail suitability summary

### Takeaway
Expect published backtests to overstate live results by roughly a third to a half (McLean–Pontiff), with trend/momentum edges concentrated in rare crisis/trend periods and long flat spells in between; for $1k–$25k, monthly ETF-based rules (GTAA, GEM, VAA/DAA, long-only momentum ETFs) are the most implementable, while Turtle-style multi-futures trend requires micro futures and ≥$25k, and growth-breakout swing trading is feasible but least validated.

### Cited Findings
- Anomaly returns 26% lower out-of-sample and 58% lower post-publication. — [McLean & Pontiff 2016](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365)
- Diversified trend has historically hedged 60/40 crises (8 of 10 worst). — [Hurst/Ooi/Pedersen SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026)
- Live CTA trend index suffered a ~20% drawdown and –15% trailing year into mid-2025. — [Top Traders Unplugged](https://www.toptradersunplugged.com/trend-following-performance-report-june-2025/)
- Momentum crashes follow bear-market rebounds (–45.6% Mar–Apr 2009). — [Daniel & Moskowitz](https://www.kentdaniel.net/papers/published/jfe_16.pdf)
- Out-of-sample Faber GTAA: CAGR fell from 11.7% (1972–2005) to ~6% (2006–2025), max DD only modestly higher. — [Concretum](https://concretumgroup.substack.com/p/global-tactical-asset-allocation)

### Inferences
- Backtests flagged as ignoring/understating costs: Faber GTAA (gross), vendor GEM stats (BestFolio), Minervini GitHub test, most Turtle blog backtests, many crypto preprints. Cost-inclusive: Hurst/Ooi/Pedersen (simulated 2/20 + transaction costs), Zarattini et al. (0.10–0.50% fees), Korajczyk–Sadka/Novy-Marx–Velikov momentum.
- Daily cadence: the monthly strategies do not benefit from daily monitoring (doing so tends to add whipsaw); daily cadence fits Turtle/Donchian systems, Minervini/O'Neil breakouts, and crypto trend.

### Gaps
- Could not access AllocateSmartly, Portfolio Visualizer, Quantpedia, or AQR full texts for cost-inclusive, up-to-2026 comparable statistics; report writer should treat vendor CAGR/drawdown numbers as indicative only.
