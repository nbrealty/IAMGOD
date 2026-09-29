# R1. What discretionary chart readers look at, and how they combine many charts

> **Read `00 Fact-check corrections (read first).md` alongside this file.** Written on 28 Sept 2026 by a research agent; four independent fact-checkers then reviewed its main claims, and where they differ from the text below, the corrections file wins. Scripts behind the researcher's own calculations are in `scripts/` (paths such as `work/`, `r5/` or `research/` in the text point there; they expect data files downloaded separately). Terms like verified / UNVERIFIED are the researcher's own tags.


*Research memo for the IAMGOD paper-trading project, 28 Sept 2026 (pages checked on 28 Sept 2026, US Eastern). Research only: nothing in the repo was edited, no orders were placed, no broker or trading API was called. Companion file: `R1_features.json` (59 features a computer can calculate every minute).*

**How this file is organised.** The six sections requested come first (1 summary, 2 findings table, 3 what we can test, 4 design recommendations, 5 open questions, 6 sources). The full catalog (definitions, formulas, data, failure modes for about 90 items) is in **Appendix A**; the two top-down checklists are in **Appendix B**; the list of things humans do that are hard to code is **Appendix C**; look-ahead rules for the feature file are **Appendix D**.

**Other memos in this folder** (`R2_evidence_technical_analysis.md`, `R3_intraday_evidence.md`, `R4_options_chart_reading.md`, `R6_long_horizon_trends.md`, `R7_ai_vs_human.md`) appear to cover the academic evidence; I did not read them, so nothing here depends on them.

**Tags.** *verified* = I read it on the named page, paper or official document. *UNVERIFIED* = only a search snippet, a blog, memory, or a page that would not load. "Practitioner claim" = a book, course, vendor or educator says it; a claim to test, not evidence. Where a source sells books, courses, memberships or data, I say so. The colleague who grades academic evidence is separate, so the evidence column mostly says "practitioner claim". Numbers marked "our backtest" come from `reports/Minute trading backtest results.md` (SPY and QQQ, 1-minute SIP bars, Sept 2024 to Sept 2026, out-of-sample half, 1.5 bps a side).

---

## 1. Plain-English summary

1. Chart readers use a funnel: (0) risk rules and the news calendar, (1) weekly and daily trend, (2) a map of price levels, (3) what kind of day it is, (4) a setup on the 5-minute chart, (5) an exact entry on the 1-minute chart.
2. The higher chart can veto a trade; the lower chart only times it; when charts disagree the answer is "do nothing".
3. I catalogued about 90 things they look at (Appendix A): roughly half are exact formulas, about a third need judgment calls, the rest are essentially discretionary (tape feel, Brooks' "always in", Elliott counts, ICT zones).
4. Many charts are not many pieces of evidence: indicators are built from the same prices (Bollinger's own rule 4, verified).
5. Nothing here is shown by our data to make money: none of our 14 minute setups passed the pre-set bar out of sample after costs; sources claiming otherwise sell books, courses, memberships or data.
6. Bulkowski's pattern statistics are end-of-day, best-case and hand-identified, and his own test found IBD "distribution days" do not predict drops in rising markets (both verified).
7. Dealer-gamma (GEX) maps are estimates, not data: public open interest does not say who is long or short (SpotGamma says so outright, SqueezeMetrics builds its own estimate); on Alpaca, same-day options have no Greeks and quotes are only "indicative" (verified).
8. Free-plan limits: live data is IEX only (about 2.5% of volume) with no futures, TICK/ADD, level 2 or VIX, so live volume-based tools are not the tools in our SIP backtests (verified).
9. Popular "swing high", "order block" and "break of structure" code looks forward N bars and leaks the future (verified in a library README); the 59 features in `R1_features.json` use only completed bars.
10. The best use of chart context is to say when to stand aside and where the risk is, not to predict direction; those tests have big samples and few hypotheses, so run them first (section 3).
11. Recommendation: write the cousin's method as exact rules plus a journal that includes the trades he skips; log the 59 features in shadow; pre-register a few tests (MT-G7); the language model only vetoes (MT-G29).
12. Tell the owner: chart reading is mostly about deciding where you would be wrong, not a crystal ball.

---

## 2. Findings table

Strength scale: **Strong / Mixed / Weak / None / Not testable**. "Not graded" = practitioner claim that I did not test and the colleague will grade. "After costs?" = does any source or our backtest show it survives realistic costs? IDs refer to Appendix A. `SC` = StockCharts ChartSchool (a charting vendor that sells subscriptions), base `https://chartschool.stockcharts.com/table-of-contents/`.

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source with URL | Verified? |
|---|---|---|---|---|---|---|
| A1 Timeframe ladder (M/W/D/4h/1h/15m/5m/1m) | Big chart sets bias and levels, small chart times entry | Practitioner claim (Grimes, Elder, Shannon); Not graded | All; US stocks and futures | Unknown | [Grimes](https://www.adamhgrimes.com/trade-pullbacks/) | Quote verified; efficacy UNVERIFIED |
| A2 Triple Screen and Impulse System | Weekly trend, daily pullback, intraday trigger; EMA13 + MACD-histogram colour rule | Practitioner claim (Elder sells books, passes and a course); Not graded | Weekly to intraday; futures, stocks | Unknown | [SC Impulse](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-types/elder-impulse-system), [elder.com](https://www.elder.com/) | Impulse rule verified; Triple Screen details UNVERIFIED |
| B1 Swing highs and lows | Local peaks/valleys, confirmed N bars later | Definition only | Any | n/a | [SMC README](https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/master/README.md) | Verified (uses bars after the peak) |
| B2 HH/HL trend classification | Rising peaks and valleys = uptrend | Practitioner claim (Grimes, Brooks, Dow) | Any | Unknown | [Grimes](https://www.adamhgrimes.com/trade-pullbacks/) | Quote verified |
| B3 Break of structure / change of character | Close beyond last swing (continuation / turn) | Practitioner claim (ICT-inspired vocabulary); no performance evidence seen | Intraday; forex, futures, equities | Unknown | [SMC README](https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/master/README.md) | Definition verified; efficacy UNVERIFIED |
| B4 Trendlines and channels | Lines through swings; regression channel | Practitioner claim; Not testable if hand-drawn | Any | Unknown | [SC channel](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-patterns/price-channel) | Definition verified |
| C1 SMA/EMA 9, 20, 50, 200 | Average price; trend and dynamic support | Practitioner claim; our backtest EMA 9/21 pullback: None | 5m SPY/QQQ (our test); all | No (-0.94 and -0.25 bps per trade) | [SC MAs](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/moving-averages-simple-and-exponential), repo file `reports/Minute trading backtest results.md` | Verified |
| C2/C3 MA slope, distance from MA | Direction and stretch | Practitioner claim; Not graded | Any | Unknown | [SC distance](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/distance-from-moving-average) | Definition verified |
| C4 Crosses, stage analysis, "trend template" | 50/200 crosses; 30-week average; checklists | Practitioner claim (Weinstein, Minervini: books); Not graded | Daily/weekly; single stocks | Unknown | [SC MA strategies index](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-average-trading-strategies) (page listed, not read) | Crosses: definition only; templates UNVERIFIED |
| D1 Session VWAP | Volume-weighted average price since the open | Practitioner claim + Zarattini and Aziz 2023 (co-author runs a members site); our backtest VWAP trend QQQ: None | 1m QQQ 2018-23 (paper); SPY/QQQ 2024-26 (ours) | Paper: +671%, Sharpe 2.1 net of commission (abstract on authors' site); ours: No (-2.74 bps) | [SC VWAP](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/volume-weighted-average-price-vwap), [Concretum](https://concretumgroup.com/volume-weighted-average-price-vwap-the-holy-grail-for-day-trading-systems/) | Formula and abstract verified; performance is the authors' claim |
| D2 VWAP bands | VWAP plus/minus k volume-weighted standard deviations | Practitioner claim; our backtest 2-SD fade: None | 1m SPY/QQQ | No (-2.84 / -3.22 bps) | repo file `reports/Minute trading backtest results.md` | Our result verified; formula is ours |
| D3 Anchored VWAP | VWAP from a chosen event | Practitioner claim (Shannon); Not graded | 5m to daily | Unknown | [SC AVWAP](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/anchored-vwap) | Definition verified |
| E1/E2 Volume, RVOL, time-of-day RVOL | Volume versus normal | Practitioner claim; Not graded | 1m to daily | Unknown | [SC RVOL](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-volume-rvol) | Verified |
| E3 OBV, accumulation/distribution | Volume signed by price direction or close location | Practitioner claim (Granville, Chaikin) | 5m to daily | Unknown | [SC OBV](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/on-balance-volume-obv), [SC ADL](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/accumulation-distribution-line) | Formula verified |
| E4 Effort versus result (VSA) | Volume relative to range and close | Practitioner claim (Wyckoff, Williams); Not graded | 1m to 15m | Unknown | [SC Wyckoff](https://chartschool.stockcharts.com/table-of-contents/market-analysis/wyckoff-analysis-articles/the-wyckoff-method-a-tutorial) | Concept verified; formula ours |
| E5 Volume profile: POC, value area, HVN/LVN | Volume at price; 70% area | Practitioner claim; Not graded | Session to week | Unknown | [SC Volume by Price](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/volume-by-price), [CQG](https://help.cqg.com/cqgic/25/Documents/marketprofilevalueareasmpva.htm) | Verified |
| E6 TPO / Market Profile, initial balance | Time-at-price letters; first-hour range | Practitioner claim (Steidlmayer, Dalton: books, vendor training) | 30m/session; futures | Unknown | [WindoTrader glossary](https://www.windotrader.com/market-profile/market-profile-glossary-index/) | IB verified |
| F1 Prior-day high/low/close | Yesterday's extremes | Practitioner claim; our backtest PDH/PDL break: None | 5m SPY/QQQ | No (-1.52 / -4.51 bps) | repo file `reports/Minute trading backtest results.md`, [Alpaca auctions](https://docs.alpaca.markets/us/reference/stockauctions-1.md) | Our result verified |
| F2 Overnight / pre-market high-low | Range before 09:30 | Practitioner claim; Not tested by us | Pre-market; SPY/QQQ | Unknown | [IEX hours](https://www.iex.io/resources/trading/trading-hours-holidays) | Hours verified (IEX trades from 08:00) |
| F3 Opening range (5/15/30/60 min) | First-minutes high/low, breakout | Practitioner claim (Crabel 1990); our backtest ORB5 partly replicated before costs, faded in year 2: Weak; ORB15/30: None | 5m QQQ/SPY | No | [SC NR7 page (Crabel)](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7), repo file `reports/Minute trading backtest results.md` | Verified |
| F4 Weekly/monthly highs and lows | Big shelves | Practitioner claim | Daily/weekly | Unknown | (definition) | Not sourced |
| F5 Round numbers | Whole-dollar magnets | Practitioner claim; Not graded | Intraday | Unknown | none read | UNVERIFIED |
| F6 Pivot points | Levels from prior high/low/close | Practitioner claim (floor traders) | Intraday to daily | Unknown | [SC pivots](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/pivot-points) | Description verified; standard formulas UNVERIFIED |
| F7 Fibonacci retracements | 23.6/38.2/50/61.8% pullbacks | Practitioner claim; Not testable by hand | Any | Unknown | [SC Fibonacci](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-annotation-tools/fibonacci-retracements) | Levels verified |
| F8 Prior-day value area / open location | Where the day opens relative to yesterday's 70% area | Practitioner claim (Dalton) | Session; futures | Unknown | [Timeless Market Theory](https://timelessmarkettheory.com/concepts/day-types) | Secondary; UNVERIFIED for outcomes |
| F9 Support and resistance zones | Areas where buyers or sellers appeared before; broken support turns into resistance | Practitioner claim; hindsight-prone when hand-drawn | Any | Unknown | [SC support and resistance](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/support-and-resistance) | Concept verified |
| G1/G2 Gaps, types and fill | Overnight jump; usually-filled common gaps | Practitioner claim; our backtest gap fade SPY +3.94 bps but 95% range -8.72 to +16.74: None | Open; SPY/QQQ | Not significant | [SC gaps](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/gaps-and-gap-analysis), repo file `reports/Minute trading backtest results.md` | Verified |
| H1/H2 Candlestick patterns | Doji, hammer, engulfing, inside bar... | Practitioner claim (Nison); Not graded | 1m to daily | Unknown | [SC dictionary](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/candlestick-charts/candlestick-pattern-dictionary) | Definitions verified |
| I1-I5 Flags, wedges, triangles, head-and-shoulders, double tops | Classic chart patterns | Practitioner claim; author's stats are end-of-day, best-case, hand-identified; Weak for minute trading | Daily stocks (Bulkowski); not SPY/QQQ minute | Unknown | [Bulkowski FAQ](https://www.thepatternsite.com/faq.html), [Lo, Mamaysky, Wang](https://www.nber.org/papers/w7613) | Quotes/abstract verified |
| J1 RSI | Wilder momentum 0-100 | Practitioner claim (Wilder 1978) | Any | Unknown | [SC RSI](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-strength-index-rsi) | Formula verified |
| J2 MACD (12,26,9) | Fast minus slow EMA | Practitioner claim (Appel) | Any | Unknown | [SC MACD](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/macd-moving-average-convergence-divergence-oscillator) | Formula verified |
| J3 Stochastic (14,3,3) | Close in recent range | Practitioner claim (Lane) | Any | Unknown | [SC Stochastic](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/stochastic-oscillator-fast-slow-and-full) | Formula verified |
| J4 ADX/DMI | Trend strength and side | Practitioner claim (Wilder) | Any | Unknown | [SC ADX](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-directional-index-adx) | Formula verified |
| J5 Divergences | Price vs oscillator disagreement | Practitioner claim; Not testable until swing rules fixed | Any | Unknown | [SC RSI](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-strength-index-rsi) | Described, not tested |
| K1 ATR | Typical bar range incl. gaps | Definition; used for risk, not alpha | Any | n/a | [SC ATR](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr-and-average-true-range-percent-atrp) | Verified |
| K2 Bollinger Bands, %b, BandWidth | Envelope 2 SD around 20-bar SMA | Practitioner claim (Bollinger sells books, DVDs, reports); own rules say "tags not signals" | Any | Unknown | [Bollinger rules](https://www.bollingerbands.com/bollinger-band-rules), [SC BandWidth](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/bollinger-bandwidth) | Verified |
| K3 Keltner channels | EMA20 +/- 2 ATR10 | Practitioner claim (Raschke, Keltner) | Any | Unknown | [SC Keltner](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/keltner-channels) | Verified |
| K4 Squeeze (Bollinger inside Keltner) | Low-volatility state before expansion | Practitioner claim (Carter, of a trading-education company) | Any | Unknown | [SC TTM Squeeze](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/ttm-squeeze) | Verified |
| K5 NR4/NR7, inside day | Narrowest range in 4/7 days precedes expansion | Practitioner claim (Crabel 1990); Not tested by us yet | Daily; futures/stocks | Unknown | [SC NR7](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7) | Verified |
| K6 Realized volatility, expected move, range used | How much price has moved vs normal | Volatility clustering is a widely reported regularity (general knowledge, no source read here); not tested here; Not graded | Intraday/daily | n/a (risk use) | [Cboe VIX method](https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf) | Definition verified |
| L1 NYSE TICK | Upticks minus downticks across NYSE stocks | Practitioner claim; no data on free plan | Intraday; US stocks | Unknown | [MyPivots](https://www.mypivots.com/dictionary/definition/139/nyse-tick) | Educational vendor page; thresholds UNVERIFIED |
| L2-L4 ADD, VOLD, TRIN | Advance/decline and volume breadth | Practitioner claim (Arms 1967) | Intraday/daily | Unknown | [SC TRIN](https://chartschool.stockcharts.com/table-of-contents/market-indicators/arms-index-trin), [SC A/D line](https://chartschool.stockcharts.com/table-of-contents/market-indicators/advance-decline-line) | TRIN/ADD verified; VOLD UNVERIFIED |
| L5 % of stocks above MA / VWAP | Participation | Practitioner claim | Daily/intraday | Unknown | [SC % above MA](https://chartschool.stockcharts.com/table-of-contents/market-indicators/percent-above-moving-average) | MA version verified; VWAP version UNVERIFIED |
| L6 McClellan Oscillator | Momentum of net advances | Practitioner claim | Daily | Unknown | [SC McClellan](https://chartschool.stockcharts.com/table-of-contents/market-indicators/mcclellan-oscillator) | Verified |
| M1 VIX | 30-day implied volatility of S&P 500 | Exchange definition; forecasting value not read | Daily/intraday; US index | n/a | [Cboe VIX method](https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf), [FRED VIXCLS](https://fred.stlouisfed.org/series/VIXCLS) | Verified |
| M2 VIX1D | 1-day implied volatility from same-day weeklies | Exchange definition; two 2024-25 papers seen by title only | Intraday; US index | n/a | [Cboe VIX1D method](https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_1-Day_Volatility_Index.pdf) | Definition verified; papers UNVERIFIED |
| M3 Volatility term structure | VIX9D/VIX/VIX3M/VIX6M/VIX1Y | Practitioner claim | Daily | n/a | [Cboe term indices](https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Selected_SPX_Target_Expected_Volatility_Term_Indices.pdf) | Index list verified; interpretation UNVERIFIED |
| M4 SKEW index | Priced skewness of 30-day returns | Exchange definition; timing value not read | Daily | n/a | [Cboe SKEW](https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf) | Verified |
| N1 ES/NQ futures overnight | Futures direction before the open | Practitioner claim; no futures data on Alpaca | Overnight | Unknown | [Alpaca docs index](https://docs.alpaca.markets/us/llms.txt) | Absence verified in index |
| N2-N5 Yields, dollar, oil, credit | Risk-on/off context | Practitioner claim | Intraday/daily | Unknown | [SC sector rotation](https://chartschool.stockcharts.com/table-of-contents/market-analysis/sector-rotation-analysis) | Concept verified; proxies/series IDs UNVERIFIED |
| O1 Relative-strength line | Ratio of one chart to another | Practitioner claim | Any | Unknown | [SC Price Relative](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/price-relative-relative-strength) | Verified |
| O2 Sector rotation, RRG | 11 sector ETFs vs market | Practitioner claim; textbook cycle map | Daily/weekly | Unknown | [SC sector rotation](https://chartschool.stockcharts.com/table-of-contents/market-analysis/sector-rotation-analysis), [SC RRG](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/rrg-relative-strength) | Verified |
| O3 Zweig breadth thrust | 10-day EMA of A/(A+D) rising from below 0.40 to above 0.615 within 10 days | Practitioner claim; very few signals | Daily; NYSE | Unknown | [StockCharts article](https://articles.stockcharts.com/article/articles-arthurhill-2025-03-two-ways-to-use-the-zweig-brea-495/) | Verified |
| O4 Distribution days / follow-through days | IBD market-timing signals | Practitioner claim; author's own test (Bulkowski): None in rising markets | Daily; US indices and stocks | Unknown | [Bulkowski](https://www.thepatternsite.com/DistributionDay.html) | Test verified; follow-through rules UNVERIFIED |
| P1 Time and sales | Trade prints | Practitioner claim; Not graded | Seconds-minutes | Unknown | [Alpaca FAQ](https://docs.alpaca.markets/docs/market-data-faq) | Data availability verified |
| P2 Level 2 depth | Resting orders by price | Practitioner claim; vendor says visible liquidity is "a bluff" | Seconds | Unknown | [SqueezeMetrics](https://squeezemetrics.com/download/The_Implied_Order_Book.pdf), [IEX products](https://iexexchange.io/products/market-data-connectivity) | Quote and availability verified |
| P3 Footprint / delta / CVD | Buy vs sell volume by price | Practitioner claim; Not graded | 1m-15m | Unknown | none read | UNVERIFIED (vendor definitions not opened) |
| P4 Tape reading | Feel for print speed and size | Practitioner claim; Not testable | Seconds | Unknown | (Wyckoff 1910: not opened) | UNVERIFIED |
| P5 Auction imbalance | Open/close order imbalance feeds | Practitioner claim; no data | Around 09:30 and 16:00 | Unknown | [Alpaca auctions](https://docs.alpaca.markets/us/reference/stockauctions-1.md) | Prices verified; imbalance data not offered |
| Q1 IV rank / percentile | IV vs its 52-week range | Practitioner claim (tastytrade-style) | Daily | Unknown | none loaded | UNVERIFIED |
| Q2/Q3 Skew, IV term structure | Put-call IV gap; front vs back IV | Practitioner claim | Daily | Unknown | [Alpaca options data](https://docs.alpaca.markets/docs/historical-option-data) | Data limits verified |
| Q4 Put/call ratio | Put volume / call volume | Practitioner claim (contrarian) | Daily | Unknown | [SC Put/Call](https://chartschool.stockcharts.com/table-of-contents/market-indicators/put-call-ratio) | Verified |
| Q5 OI walls, "max pain" | Big open-interest strikes as magnets | Practitioner claim; Not graded | Expiry week | Unknown | [Alpaca options](https://docs.alpaca.markets/docs/options-trading) | OI availability verified; theory UNVERIFIED |
| Q6 Dealer gamma exposure (GEX), zero-gamma | Modelled dealer hedging flows | Vendor claim (both sell subscriptions); Not testable without dealer books | Daily/intraday; SPX/SPY | Unknown | [SqueezeMetrics](https://squeezemetrics.com/download/The_Implied_Order_Book.pdf), [SpotGamma](https://spotgamma.com/gamma-exposure-gex/) | Caveats verified |
| Q7 0DTE volume share | Same-day share of SPX volume | Exchange statistic (Cboe sells the products); predictive value not read | Monthly; SPX | n/a | [Cboe](https://www.cboe.com/insights/posts/spx-0-dte-options-jumped-to-record-56-share-in-feb/) | 56% (Feb 2025) verified; later figures UNVERIFIED |
| Q8 Unusual options activity | Volume far above normal or OI | Practitioner claim; hedging flow dominates index ETFs | Intraday | Unknown | none loaded | UNVERIFIED |
| R1 Market Profile day types | Six day shapes from first-hour width and extension | Practitioner claim (Dalton); Not graded; label known only late | Session; futures | Unknown | [Timeless Market Theory](https://timelessmarkettheory.com/concepts/day-types) | Secondary; book not read |
| R2 Wyckoff phases | Accumulation/distribution schematics | Practitioner claim; hindsight-prone; Not testable by eye | 15m to weekly | Unknown | [SC Wyckoff](https://chartschool.stockcharts.com/table-of-contents/market-analysis/wyckoff-analysis-articles/the-wyckoff-method-a-tutorial) | Verified |
| R3 Brooks price action | "Always in", bar counting, second entries | Practitioner claim (sells a $399 course and rooms); Not testable as taught | 5m; futures | Unknown | [Brooks](https://www.brookstradingcourse.com/price-action/always-in/) | Page is members-only; definitions UNVERIFIED |
| R4 Crabel ORB and NR days | Opening range breakout; narrow-range days | Practitioner claim (1990); ORB: see F3 | Intraday/daily | ORB: No (ours) | [SC NR7](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/narrow-range-day-nr7) | Verified |
| R5 Grimes pullbacks | Buy trending pullbacks near "average"; avoid exhaustion | Practitioner claim (plugs his research firm and a free course); discretionary filter | 2m to weekly | Unknown | [Grimes](https://www.adamhgrimes.com/trade-pullbacks/) | Verified as described |
| R6 Bulkowski pattern statistics | Performance stats by pattern | Practitioner claim (sells books; his pattern software is free per his FAQ); author warns best-case | Daily stocks | Unknown | [Bulkowski FAQ](https://www.thepatternsite.com/faq.html) | Verified |
| R7 ICT / smart-money concepts | Fair value gaps, order blocks, liquidity sweeps, kill zones | None seen; mentorship-seller vocabulary | Intraday; forex, futures | Unknown | [SMC README](https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/master/README.md) | Code description verified; efficacy UNVERIFIED |
| S1 Economic calendar | FOMC, CPI, jobs, GDP... | Scheduled events move markets at a known second (claim; colleague to grade) | Daily/intraday | Use as a gate | [Fed FOMC](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm), [BLS CPI](https://www.bls.gov/schedule/news_release/cpi.htm) | Dates verified |
| S2 Earnings of index heavyweights | Top weights reporting | Practitioner claim | Daily | Use as a gate | none read | UNVERIFIED |
| S3 Expiration, rebalance, half-day calendar | Monthly/quarterly opex, index changes | Practitioner claim | Daily | Use as a gate | [Cboe VIX method (SPX expiry rules)](https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf) | Opex rule verified; rebalance dates UNVERIFIED |
| S4 Time-of-day pattern | Busy open/close, quiet midday | Practitioner claim | Intraday | n/a | [SC RVOL](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-volume-rvol) | Statement verified |


---

## 3. What we can test with our data

### 3.1 What we have and what we can get free

| Source | What it gives | Limits (verified unless marked) |
|---|---|---|
| Cached SIP 1-minute bars, SPY and QQQ, Aug 2024 to Sep 2026 | Everything computed from completed bars in the feature file | About 2 years; already used for the 14-setup backtest ([S84]) |
| Alpaca free historical bars, SIP, back to 2016 | Daily and minute bars for any symbol; trades and quotes; opening and closing auction prices | SIP data must be at least 15 minutes old; 200 REST calls a minute; history "since 2016" ([S1], [S2], [S9]). A page holds up to 10,000 rows on the endpoints I checked; for bars this is UNVERIFIED |
| Alpaca live free feed | IEX real-time trades, quotes and bars; snapshots (latest trade, latest quote, minute bar, daily bar, previous daily bar) | IEX is about 2.5% of volume; 30 WebSocket symbols; IEX itself trades 08:00 to 17:00 ET ([S2], [S3], [S10], [S12]) |
| Alpaca options | Contract lists with open interest, chains with Greeks, bars, trades | "Indicative" feed (quotes are derivatives, trades delayed 15 minutes); history only since Feb 2024; no Greeks for same-day contracts ([S4], [S1]) |
| Alpaca not offered | Stock futures, stock level 2, TICK/ADD/VOLD, VIX, Cboe put/call, earnings calendar | Absence checked in Alpaca's documentation index ([S8]) |
| Free outside sources | FRED VIX daily close ([S22]); Fed and BLS calendars ([S20], [S21]); IEX historical DEEP/TOPS files, T+1 ([S13]) | IEX files are one exchange only. FRED IDs for yields, dollar, oil and credit were not verified. Cboe data terms not checked |

**Rough download cost (estimate from the documented limits, not measured):** 8 years of 1-minute SPY plus QQQ is under 200 REST pages; 500 index constituents on daily bars back to 2016 is about 500 calls (a few minutes); 500 constituents on 1-minute bars for 2 years is on the order of 10,000 calls (about 50 minutes at 200 calls a minute).

### 3.2 Data traps that change results (verified in Alpaca's FAQ [S1], unless marked)

1. **Bars are stamped at their start.** A 10:04:00 bar is complete at 10:05:00.
2. **No trade, no bar.** A minute with no eligible trade (or only an odd-lot trade) produces no bar, so low-volume minutes are missing, especially on IEX and in pre-market.
3. **Minute and daily bars follow different update rules.** Odd lots update volume only; extended-hours trades update minute bars but not daily prices. PDH/PDL from daily bars and from minute bars can differ.
4. **IEX-only live bars are not SIP bars.** The AAPL example shows 12,630 IEX trades against more than 535,136 in total on one day. Price features are close; volume features are not the same thing (MT-G35).
5. **Adjusted prices.** The lab's backtest used prices adjusted for splits and dividends ([S84]); for round numbers use raw prices (reasoning, not from a source).
6. **Regime breaks.** Daily SPX expirations began 16 May 2022 (as recorded in [S85]); 0DTE volume has grown since (Cboe, [S19]); the VIX1D exists only from 2022. Options-based features have short, non-stationary histories.
7. **Half-days** exist; take session times from the calendar.

### 3.3 A short, ranked test plan (each test counts toward N_trials, MT-G7)

The lab already tested the *setups*. The better use of chart-reading ideas is to test whether **context** explains when those setups (or any trading) work, and whether **levels** carry any information at all. Every test below should be written down (direction, threshold, horizon) **before** looking at results, run first on 2016 to 2024 data (fresh for these ideas) and confirmed once on Sept 2024 to Sept 2026.

| # | Question (plain English) | Features (JSON ids) | Data and sample | Pre-registered rule (example) | Hypotheses added |
|---|---|---|---|---|---|
| T1 | **When should the bot stand aside?** Do a narrow prior day (NR7/inside), a squeeze at 10:30, a narrow first hour, low RVOL at 10:00 or a high prior-day VIX predict a small or large range for the rest of the day? | F43, F42, F45, F20, F52, F39 | SPY, QQQ daily and minute, 2016 to 2026, about 2,500 days each | Rank correlation of each feature with the rest-of-day range in ATR units; walk-forward by year | 6 |
| T2 | **Do scheduled-news days hurt the baseline?** Compare ORB5, LAST30 and NOISE_MOM results on FOMC and CPI/jobs days versus other days | F03 | Same setups, 2016 to 2026; needs verified calendars (Fed and BLS dates verified; other releases need checking) | Mean net R on event days minus other days, bootstrap by day | 3 |
| T3 | **Does the daily trend help?** Trade the three baseline setups only when the trade direction agrees with the daily trend state, versus a random filter that keeps the same number of trades | F06, F11 | 2016 to 2024 for the three *unfiltered* setups first (never run there: the backtest report's own follow-up), then filtered | Net R per trade, filtered versus random-filtered, bootstrap by day | 6 (3 replication + 3 filter) |
| T4 | **Do levels matter at all?** After price touches PDH, PDL, PDC, the 15-minute opening-range edges, VWAP, prior-day POC/VAH/VAL, round numbers or the pivot, is the next 15 to 30 minutes different from what happens near a *fake* level (the same level shifted by a random 0.5 to 1.5 ATR)? | F25, F29, F16, F33, F31, F32 | SPY, QQQ minute, 2016 to 2026 | Difference in signed move in ATR units, real minus fake level, cluster bootstrap by day; Bonferroni over 9 level types | 9 |
| T5 | **Gaps.** Probability that a gap fills by 10:30 and by the close, by gap size in ATR units and daily trend | F26, F27, F06 | About 2,500 days per symbol | Fill rate and mean drift by gap-size bucket (3 buckets) | 4 |
| T6 | **Day type at 10:30.** Does a narrow versus wide first hour, plus open location versus yesterday's value, predict range expansion and direction persistence for the rest of the day? | F45, F33 | 2016 to 2026 | 3 pre-set states, 2 outcomes | 3 |
| T7 | **Breadth.** Does the share of index stocks above their own VWAP, or the advance/decline proxy, at 10:00 predict SPY's return from 10:00 to 15:30? | F46, F48 | 500 constituents minute bars, 2016 to 2026 (survivorship risk: today's list) | Rank correlation; two features only | 2 |
| T8 | **The cousin's own method.** Once written as exact rules, record his decisions in a journal for 40+ sessions and score them like any other setup | all | Forward, paper only | Exploratory lane (MT-G5 amendment); needs 100 trades over 40 sessions to say anything (MT-G11) | rules-dependent |

Why this order: T1, T2, T5 have large samples and few hypotheses, and their answers feed **vetoes and sizing**, which is the only role chart context is allowed to play. T4 is the most informative single test of the *premise* of chart reading: if real levels behave no differently from fake ones, the whole "map of levels" step is decoration. A null result is a useful answer. Even a real effect must be larger than costs (about 1 to 3 bps a round trip in our lab) to matter.

### 3.4 What we cannot test now

- **TICK, VOLD, exact ADD:** not in any free feed; only the constituent proxies (F46 to F49) exist.
- **Footprint, delta, tape, level 2:** live free data is IEX only; history is SIP trades and quotes with a 15-minute delay, so delta can be back-tested but not run live on comparable data. IEX depth files are T+1 and single-exchange ([S13]).
- **Futures lead-lag (ES/NQ), VIX1D intraday, put/call, SKEW, 0DTE share:** no free Alpaca source; Cboe data terms not checked.
- **Dealer gamma (GEX):** OI is daily, Alpaca's Greeks are missing for 0DTE, options history starts Feb 2024, and the sign of dealer positions is unobservable. Any result depends on the vendor's assumption ([S69], [S71]).
- **Unusual options activity, IV rank:** indicative-only quotes and short history.
- **Every discretionary item** (tape feel, "best pullback", Brooks' always-in, Elliott, hand-drawn lines, order-block zones as taught) until it is written as rules or logged in a journal.

---

## 4. Recommendations for the agent design

### 4.1 Include (all computed by code, shadow-first, LLM may only veto: MT-G29)

1. **One "context snapshot" per minute**, computed from the 59 features in `R1_features.json`, stored with a feed tag (IEX or SIP) and the `known_at` time of each input. Logging all 59 is cheap; at most about six should ever touch a decision, and only as gates.
2. **Hard gates first:** event calendar (unknown dates block), clock and half-days, spread and data health, halts. These are the "risk chart" that has the final say.
3. **Regime tags used only for vetoes and size caps:** daily trend (F06), volatility state (F39 to F45), event class (F03). They never add a trade.
4. **Levels as risk geometry, not signals:** distance to the nearest level in ATR (F25, F29, F33). Use it to reject trades whose target is closer than a cost multiple, and to place the stop, after T4 shows levels carry information.
5. **Same-feed discipline (MT-G35):** compute each volume-based feature on the feed it will be used on; keep both IEX and SIP versions in shadow and report the difference.
6. **Breadth and sector context from constituents** (F46 to F51), shadow only, with a point-in-time universe.
7. **A decision journal for the cousin's trades:** timestamp, symbol, screenshot set, the feature snapshot at that minute, rule tags (catalog IDs), entry/stop/target, and, most important, **every trade he considered and skipped, with the reason**.

### 4.2 Avoid (at least until the tests above are done)

- Anything drawn with future data: two-sided swing detection, kernel-smoothed patterns, ZigZag legs before confirmation, "significant low" anchors, ready-made libraries whose swing function looks N candles forward ([S72]).
- Hand-drawn objects as inputs (trendlines, Fibonacci, Elliott counts, channels).
- Named candlestick and chart-pattern triggers: they multiply trials (MT-G7) and Bulkowski's own statistics are end-of-day, best-case and hand-identified ([S64]).
- GEX/dealer levels, max pain and unusual options activity as triggers: model output, indicative-only quotes, no 0DTE Greeks.
- "Smart money" vocabulary (order blocks, liquidity sweeps) unless defined precisely in code and tested; it comes from mentorship sellers, and MT-G24 already forbids course-driven shortcuts.
- Any input from social media, headlines, "top gainer" lists or crowd scanners (MT-G23, MT-G24).
- Stacking correlated indicators. Bollinger: "if more than one indicator is used the indicators should not be directly related to one another" ([S63]). Pick one per family: trend (one average family), momentum (one oscillator), volatility (ATR), volume (RVOL), levels (few).
- IBD-style distribution-day counting: the one independent test I read says it does not predict declines in rising markets ([S65]).
- Live decisions on IEX volume compared with SIP-based thresholds.

### 4.3 Test first

In this order: **T1, T2, T5, T3, T4, T6, T7** (section 3.3). Keep the total number of pre-registered hypotheses small (MT-G7 raises the bar with each addition), and hold back Jan to Sept 2026 as an untouched final check.

### 4.4 What a beginner should be told (plain English)

1. A chart is a picture of *past* prices. Reading it well means knowing where the market has already agreed on a price and where you would be proved wrong. It does not tell you the future.
2. Your cousin uses many charts because each answers a different question: what is the trend, where are the important prices, how big is a normal move, and when exactly to act. The skill is the order of the questions and which chart wins a disagreement.
3. Ten indicators built from the same prices are not ten confirmations. They are one opinion said ten ways.
4. Most named patterns (triangles, head-and-shoulders, "order blocks") are recognised with hindsight. If two people cannot draw the same line, a computer cannot test it.
5. Books, courses and Discord groups can sell certainty. None of the famous chart rules we tested beat trading costs on SPY and QQQ. That does not prove the cousin wrong; it means we need his exact rules, and his skipped trades, to test him fairly.
6. If a discretionary trader has an edge, it is most likely in *which days and moments he refuses to trade* and *how he exits*, not in the entry pattern. Both can be recorded and tested.
7. The free data feed shows about 2.5% of all trades. Tools that depend on volume, order flow or the order book do not mean the same thing on it.
8. "Dealer gamma" maps are somebody's estimate of who owns which option, because public data does not say. One seller admits this outright; the other builds its own guess from trade data.
9. More screens can mean more trades, and more trades mean more costs. The bot's job right now is to measure, record and say "no", not to find the perfect chart.

---

## 5. Open questions and things I could not verify

**Questions for the cousin (needed before anything can be tested):**
1. Exactly which charts are on the screen, on which timeframes, with which indicators and settings? Which symbols (SPY/QQQ only, or single stocks)?
2. Which chart does he look at first each morning, and which one decides when there is a conflict?
3. What is his exact entry trigger, stop rule, target rule and time exit? How long does a trade last?
4. Which days or conditions does he refuse to trade? What makes him skip a valid-looking setup?
5. Does he use futures, TICK/ADD, VIX, options levels, order flow or news? Which ones actually change a decision?
6. Can he show six to twelve months of broker statements (not screenshots of single wins)?
7. Will he journal the next 40 sessions in the format in section 4.1 item 7?

**Could not verify (UNVERIFIED unless a note says otherwise):**
- Elder's Triple Screen details and its 1986 origin (search snippets only); Weinstein and Minervini thresholds; IBD follow-through-day rules (the IBD page returned a video page, [S86]); the definition of "Always In" and H1/H2 counting (Brooks' page is members-only, [S67]).
- NYSE's own TICK definition (an educational vendor page was read, [S76]); TICK "extreme" thresholds; VOLD as a difference; "percent of stocks above VWAP" as an established tool.
- Standard pivot-point formulas (not present in the extracted page text); the 78.6% Fibonacci level; Wyckoff's 1910 *Studies in Tape Reading* (a Gutenberg search returned a server error).
- IV rank and IV percentile definitions (tastytrade's help page and Barchart's page would not load; only secondary snippets, [S87], [S88]); unusual-options-activity rules; footprint imbalance ratios.
- 0DTE share after Feb 2025: SpotGamma's page cites "59% in 2025" and a news headline says 65% in Q2 2026; I found neither on a Cboe page ([S71], [S87]). The Cboe Q2 2026 post I read says 0DTE volume across products rose 46.2% year to date to more than 20 million contracts a day and SPX 0DTE volume nearly tripled since the start of 2024 ([S19]).
- The two VIX1D papers (Albers 2025 in the *Journal of Futures Markets*; a 2024 *Finance Research Letters* paper on an "overnight bias"): titles only, publishers blocked access ([S90]).
- The full Zarattini and Aziz (2023) and Zarattini, Aziz and Barbon (2024) papers: SSRN returned HTTP 403 to both of my fetch routes ([S91]). I read the abstract on a University of St. Gallen repository record ([S78]) and the authors' own site ([S79], [S80]). Their results are the authors' claims; Aziz's Bear Bull Traders runs a members site (rooms and an education center; pricing not read) and Concretum Group runs a newsletter.
- FRED series IDs for yields, dollar, oil, credit spreads; Cboe data terms; whether Alpaca's forex endpoint is on the free plan; whether Alpaca SIP extended-hours history covers the full 04:00 to 20:00 window; the exact number of missing minute bars for SPY/QQQ on IEX.
- Sector ETF tickers other than XLC (StockCharts says "eleven" Sector SPDRs on one page, "nine" on an older RRG page).

**Where my search stopped:** the web-search tool reported that its session limit (200 of 200 calls) was used up near the end. Not yet looked up: academic tests of intraday levels and round numbers, 2024 to 2026 papers on 0DTE and dealer gamma (for example whether market-maker gamma from 0DTE is small), evidence on vision-language models reading price charts, IBD's own follow-through rules, official rebalance and VIX-expiry calendars, and CME's own Market Profile education pages. The colleague grading academic evidence may cover several of these.

**A small inconsistency in the repo worth knowing:** `MINUTE_TRADING.md` says every setup "lost between about $0.03 and $0.45 a trade", but the backtest table shows a SPY gap fade at +$0.39 and a QQQ NOISE_MOM check at +$0.00 per trade (both statistically indistinguishable from zero). The verdict (nothing passed the pre-set bar) is unaffected.

---

## 6. Sources

Status: **V** = read on the page or document named (for pages, I read the extracted text; for PDFs, the full text). **U** = UNVERIFIED (search snippet only, blocked, failed to load, or memory). Conflict-of-interest notes come from what each site itself shows.

**Alpaca (broker; official docs)**
- S1 Market Data FAQ (bar rules, feeds, Greeks) [V]: https://docs.alpaca.markets/docs/market-data-faq
- S2 About Market Data API (Basic vs Algo Trader Plus: IEX only, 30 symbols, 200 calls a minute, history since 2016, 15-minute SIP limit) [V]: https://docs.alpaca.markets/docs/about-market-data-api
- S3 Historical Stock Data (feeds; IEX about 2.5% of volume) [V]: https://docs.alpaca.markets/docs/historical-stock-data-1
- S4 Historical Option Data (since Feb 2024; indicative feed wording) [V]: https://docs.alpaca.markets/docs/historical-option-data
- S5 Real-time Option Data (indicative or OPRA stream) [V]: https://docs.alpaca.markets/docs/real-time-option-data
- S6 Options Trading (contracts with open_interest and open_interest_date) [V]: https://docs.alpaca.markets/docs/options-trading
- S7 Option snapshots reference (latest trade, quote, Greeks; indicative = delayed trades, modified quotes) [V]: https://docs.alpaca.markets/reference/optionsnapshots
- S8 Documentation index (list of endpoints; no futures, stock order book only for crypto) [V]: https://docs.alpaca.markets/us/llms.txt
- S9 Historical auctions (opening and closing auction prices; SIP only) [V]: https://docs.alpaca.markets/us/reference/stockauctions-1.md
- S10 Stock snapshots (latest trade, quote, minute bar, daily bar, previous daily bar) [V]: https://docs.alpaca.markets/us/reference/stocksnapshots-1.md
- S11 Forex historical rates (exists; plan and coverage U): https://docs.alpaca.markets/us/reference/rates-1.md

**Exchanges, regulators, official statistics**
- S12 IEX trading hours (pre-market 08:00, regular 09:30 to 16:00, post-market to 17:00 ET) [V]: https://www.iex.io/resources/trading/trading-hours-holidays
- S13 IEX market data products (TOPS, DEEP, DEEP+, free HIST downloads T+1) [V]: https://iexexchange.io/products/market-data-connectivity
- S14 Cboe VIX methodology (30-day; SPX and SPXW; hours; expiry rules) [V]: https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf
- S15 Cboe VIX1D methodology [V]: https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_1-Day_Volatility_Index.pdf
- S16 Cboe term-structure indices methodology (VIX9D, VIX3M, VIX6M, VIX1Y) [V]: https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Selected_SPX_Target_Expected_Volatility_Term_Indices.pdf
- S17 Cboe SKEW white paper (SKEW = 100 - 10 x S) [V]: https://cdn.cboe.com/resources/indices/documents/SKEWwhitepaperjan2011.pdf
- S18 Cboe insights, "SPX 0DTE Options Jumped to Record 56% Share in Feb", 3 Mar 2025 (Cboe sells these products) [V]: https://www.cboe.com/insights/posts/spx-0-dte-options-jumped-to-record-56-share-in-feb/
- S19 Cboe insights, Q2 2026 options market report [V]: https://www.cboe.com/insights/posts/state-of-the-options-industry-options-market-continued-to-break-records-in-q-2-2026
- S20 Federal Reserve FOMC calendars (2026 dates) [V]: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- S21 BLS CPI release schedule (read through a fetch tool summary; 08:30 ET) [V]: https://www.bls.gov/schedule/news_release/cpi.htm
- S22 FRED VIXCLS (daily close; Cboe copyright note) [V]: https://fred.stlouisfed.org/series/VIXCLS
- S82 State Street XLC page [V]: https://www.ssga.com/us/en/intermediary/etfs/the-communication-services-select-sector-spdr-fund-xlc
- S89 Cboe options market statistics page (little text extracted) [U for content]: https://www.cboe.com/us/options/market_statistics/

**StockCharts ChartSchool (charting vendor; educational pages; base `https://chartschool.stockcharts.com/table-of-contents/`) [all V]**
- S23 technical-indicators-and-overlays/technical-overlays/moving-averages-simple-and-exponential
- S24 .../technical-overlays/volume-weighted-average-price-vwap
- S25 .../technical-overlays/anchored-vwap
- S26 .../technical-overlays/volume-by-price
- S27 .../technical-overlays/keltner-channels
- S28 .../technical-overlays/bollinger-bands
- S29 technical-indicators-and-overlays/technical-indicators/bollinger-bandwidth
- S30 .../technical-indicators/ttm-squeeze
- S31 .../technical-indicators/macd-moving-average-convergence-divergence-oscillator
- S32 .../technical-indicators/stochastic-oscillator-fast-slow-and-full
- S33 .../technical-indicators/relative-strength-index-rsi
- S34 .../technical-indicators/average-directional-index-adx
- S35 .../technical-indicators/average-true-range-atr-and-average-true-range-percent-atrp
- S36 .../technical-indicators/relative-volume-rvol
- S37 .../technical-indicators/price-relative-relative-strength
- S38 .../technical-indicators/on-balance-volume-obv
- S39 .../technical-indicators/accumulation-distribution-line
- S40 .../technical-overlays/pivot-points
- S41 chart-analysis/gaps-and-gap-analysis
- S42 trading-strategies-and-models/trading-strategies/narrow-range-day-nr7 (also carries Crabel's ORB description)
- S43 market-indicators/arms-index-trin
- S44 market-indicators/advance-decline-line
- S45 market-indicators/mcclellan-oscillator
- S46 market-indicators/percent-above-moving-average
- S47 market-indicators/put-call-ratio
- S48 chart-analysis/chart-patterns/head-and-shoulders-top
- S49 chart-analysis/chart-patterns/flag-pennant
- S50 chart-analysis/chart-patterns/symmetrical-triangle
- S51 chart-analysis/chart-patterns/double-top-reversal
- S52 chart-analysis/chart-patterns/falling-wedge
- S53 chart-analysis/chart-patterns/price-channel
- S54 chart-analysis/candlestick-charts/candlestick-pattern-dictionary
- S55 chart-analysis/chart-annotation-tools/fibonacci-retracements
- S56 market-analysis/wyckoff-analysis-articles/the-wyckoff-method-a-tutorial
- S57 chart-analysis/chart-types/elder-impulse-system
- S58 market-analysis/sector-rotation-analysis
- S59 technical-indicators-and-overlays/technical-indicators/rrg-relative-strength
- S60 technical-indicators-and-overlays/technical-indicators/distance-from-moving-average
- S61 chart-analysis/support-and-resistance (fetched; not cited above)
- S62 StockCharts article, Arthur Hill, "Two Ways to Use the Zweig Breadth Thrust" (March 2025) [V]: https://articles.stockcharts.com/article/articles-arthurhill-2025-03-two-ways-to-use-the-zweig-brea-495/

**Authors, educators and vendors (each sells something; claims to test)**
- S63 John Bollinger, "Bollinger Bands Rules" (sells books, DVDs, reports) [V]: https://www.bollingerbands.com/bollinger-band-rules
- S64 Thomas Bulkowski, FAQ (sells books; says his pattern software is free; end-of-day tests, failure = under 5% move, best-case measure, hand-identified patterns) [V]: https://www.thepatternsite.com/faq.html
- S65 Bulkowski, "Distribution Days" (test result) [V]: https://www.thepatternsite.com/DistributionDay.html
- S66 Adam Grimes, "How to trade pullbacks" (plugs his research firm Waverly Advisors and a free trading course; commercial terms not read) [V]: https://www.adamhgrimes.com/trade-pullbacks/
- S67 Al Brooks, "Always In" (members-only page; sells a $399 course and trading-room subscriptions) [V for the paywall and price; definitions U]: https://www.brookstradingcourse.com/price-action/always-in/
- S68 Alexander Elder's site (sells books, webinar and video passes and a course; runs the SpikeTrade members community; pricing not read) [V for what is offered]: https://www.elder.com/
- S69 SqueezeMetrics, "The Implied Order Book" (GEX and DDOI; July 2020 edition) [V]: https://squeezemetrics.com/download/The_Implied_Order_Book.pdf
- S70 SqueezeMetrics monitor page (shows "Plans", "Signup") [V for what is sold]: https://squeezemetrics.com/monitor/dix
- S71 SpotGamma, "Gamma Exposure (GEX)" (sells subscriptions; states the model-assumption caveats) [V]: https://spotgamma.com/gamma-exposure-gex/
- S72 Smart Money Concepts Python library README (open source; includes a donation address) [V]: https://raw.githubusercontent.com/joshyattridge/smart-money-concepts/master/README.md
- S73 CQG help, Market Profile Value Areas (70% rule algorithm; vendor documentation) [V]: https://help.cqg.com/cqgic/25/Documents/marketprofilevalueareasmpva.htm
- S74 WindoTrader Market Profile glossary (initial balance = first hour; vendor) [V]: https://www.windotrader.com/market-profile/market-profile-glossary-index/
- S75 Timeless Market Theory, "Market Profile Day Types" (secondary summary of Dalton, Jones & Dalton, *Mind Over Markets*) [V for what the page says; the book was not read]: https://timelessmarkettheory.com/concepts/day-types
- S76 MyPivots, "NYSE TICK" (educational vendor) [V]: https://www.mypivots.com/dictionary/definition/139/nyse-tick
- S77 NBER working paper 7613, Lo, Mamaysky and Wang, "Foundations of Technical Analysis" (abstract) [V]: https://www.nber.org/papers/w7613
- S78 University of St. Gallen repository record for Zarattini, Aziz and Barbon (2024), "Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)" (abstract) [V for the abstract; results are the authors' claim]: https://alexandria.unisg.ch/entities/publication/71ef0a23-34e3-4b37-a8d7-d98285579662
- S79 Concretum Group page on the same paper (authors' commercial site) [V]: https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/
- S80 Concretum Group page on Zarattini and Aziz (2023), "VWAP: The Holy Grail for Day Trading Systems" (QQQ, 2018 to 2023, +671% net of commission, Sharpe 2.1) [V for the page; results are the authors' claim]: https://concretumgroup.com/volume-weighted-average-price-vwap-the-holy-grail-for-day-trading-systems/
- S81 Bear Bull Traders page on the VWAP paper (members site: rooms, "ELITE", education center; pricing not read) [V for navigation]: https://members.bearbulltraders.com/magic-of-vwap-the-holy-grail-of-day-trading-systems/

**Repo (read-only)**
- S83 `MINUTE_TRADING.md` (standing brief, owner decisions, lanes) [V]
- S84 `reports/Minute trading backtest results.md` (14 setups, SPY/QQQ, Sept 2024 to Sept 2026; sections 1 to 3 and 8 read) [V]
- S85 `reports/Why day traders lose.md` (sections 1 to 3 and the guardrails MT-G7, MT-G23, MT-G24, MT-G29, MT-G35) [V]

**Not usable or not opened (UNVERIFIED)**
- S86 IBD "follow through day" page returned a video page, not the article: https://www.investors.com/ibd-university/market-direction/follow-through-day/
- S87 Seen only as search snippets: Elder Triple Screen explainers (https://blog.elearnmarkets.com/triple-screen-trading-method-alexander-elder-way-trading/, https://www.dailyforex.com/forex-articles/2020/09/elder-triple-screen-system/151378); IV rank explainers (https://flashalpha.com/articles/iv-rank-vs-iv-percentile-which-to-use, https://volradar.com/glossary/iv-rank); Investing.com headline on Cboe Q2 2026 0DTE share (https://ca.investing.com/news/company-news/cboe-q2-2026-slides-record-revenue-0dte-options-surge-to-65-of-spx-93CH-4768656).
- S88 Failed to load: tastytrade help (https://support.tastytrade.com/support/s/solutions/articles/43000539059); Barchart unusual activity (https://www.barchart.com/options/unusual-activity/stocks).
- S90 Blocked (HTTP 403): Albers (2025), *Journal of Futures Markets* (https://onlinelibrary.wiley.com/doi/full/10.1002/fut.70023); *Finance Research Letters* VIX1D paper (https://www.sciencedirect.com/science/article/pii/S1544612324002162).
- S91 Blocked (HTTP 403): SSRN abstracts https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172 and https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4631351.

*Raw page text I read is cached under `research/raw/` (same folder as this file) so any quote can be re-checked.*

## Appendix A. The catalog in detail

### A.0 Conventions used in every formula (read this first)

- **Decision time t** = the moment just after the 1-minute bar stamped (t minus 1 minute) has closed. Alpaca stamps a minute bar with its **start**: a bar stamped 10:04:00 holds trades from 10:04:00 up to (not including) 10:05:00, so it can be used only from 10:05:00 (verified, [S1]). In the lab's `Day` object (repo file `trading/lab/scalp/signals.py`, read only) `m` is the bar start in minutes from the open and `upto(i)` returns only bars 0..i, which is the right pattern.
- **Symbols.** o, h, l, c, v = open, high, low, close, volume of a *completed* bar. TP = (h + l + c) / 3. True range TR_i = max(h_i - l_i, |h_i - c_(i-1)|, |l_i - c_(i-1)|). ATR_n uses Wilder smoothing: ATR_i = (ATR_(i-1) x (n-1) + TR_i) / n, with the first ATR the plain average of the first n true ranges (verified, [S35]). EMA_n: alpha = 2 / (n + 1), seeded with an SMA of n bars; an EMA needs far more than n bars to settle (verified, [S23]). "Prior day" = the previous regular session (09:30 to 16:00 ET) unless stated.
- **Higher-timeframe (HTF) bars** are built from 1-minute bars in fixed buckets labelled by their start time. A bucket is usable only after its last minute bar has completed. Never use the still-forming HTF bar as if it were closed (the classic look-ahead bug).
- **Numbers are parameters, not evidence.** Every threshold (a doji is a body of at most 10% of the range, a 20-day baseline, a 70% value area, +/-2 standard deviations) is either a convention from the cited source or a first choice made by us. None of them has been tested.
- **Data legend.** *yes* = usable live on the free plan (IEX real time, or calendar data) and rebuildable from free history. *delayed* = needs SIP data (free only when 15 minutes old or older, fine for research and next-day use) **or** is volume-based, so a live IEX number is not the same measurement as our SIP backtests (rule MT-G35). *no* = not offered on Alpaca's free plan (futures, TICK, VIX, level 2, OPRA options quotes, Cboe statistics, earnings calendars).
- **Subjectivity legend.** 0 = fully codeable; 1 = codeable but needs judgment calls (parameters, thresholds, anchor rules); 2 = essentially discretionary.
- **Feed facts that shape everything** (all verified): the free live feed is IEX only, about 2.5% of market volume ([S3]); on 29 Sept 2023 AAPL had 12,630 IEX trades against more than 535,136 in total ([S1]). SIP history is free once the `end` time is at least 15 minutes old ([S1], [S2]). Minute bars ignore odd-lot trades for price; a minute with no eligible trade produces **no bar**; daily bars ignore extended-hours trades for price ([S1]). WebSocket: 30 symbols; REST: 200 calls a minute; history back to 2016 ([S2]).

---

### A. Workflow and multi-timeframe

**A1. Timeframe ladder (monthly, weekly, daily, 4h, 1h, 15m, 5m, 1m)**
- *Plain English:* Look at the big chart first, then zoom in. Each chart answers one question. Monthly and weekly: what is the big trend and where are the major levels? Daily: what is the trend, where is yesterday's structure, how big is a normal day (ATR)? 1h (and 4h where used): what is the swing structure of the week, where is the intraday support and resistance? 15m: which setup is forming, where is the opening range? 5m: the chart most day traders act on (trigger and management). 1m: exact entry timing and stop.
- *Exact definition:* MTF alignment score = mean over frames k in {W, D, 60m, 15m, 5m} of sign(close_k - EMA20_k), each taken from the **last completed** bar of that frame; range -1 to +1. Frames are built from completed 1-minute bars; weekly and monthly from daily bars, and a week ending on a holiday must use the last trading day.
- *TF / decision:* all; trend and context. *Data:* daily since 2016 free; intraday frames from minute bars (SIP history or IEX live). 4h is awkward in a 6.5-hour US session (9:30 to 13:30, 13:30 to 16:00); Alpaca builds hour bars from minute bars ([S1]).
- *Subjectivity:* 1 (choice of frames, average and weights).
- *Failure modes:* using an unfinished HTF bar; treating frames as independent evidence when they are all built from the same prices (Bollinger rule 4: "the indicators should not be directly related to one another", verified, [S63]); the frames often disagree, so a rule needs a tie-break.
- *Evidence:* practitioner claim (Grimes says "multiple timeframe confluences" are powerful, verified as a claim, [S66]; Elder, Shannon, Brooks in books and courses). No source read here tests it.

**A2. Elder's Triple Screen and Impulse System**
- *Plain English:* Three screens on three timeframes (Elder's "factor of five" spacing rule: UNVERIFIED). Screen 1 (weekly) sets the allowed direction. Screen 2 (daily) uses an oscillator to find a pullback against that direction. Screen 3 (intraday) is the entry when price turns back with the trend. The higher screen can only veto; the lower screen only times.
- *Exact definition (Impulse System, verified in [S57]):* bar is **green** if EMA13 is rising and the MACD histogram is rising; **red** if both are falling; otherwise **blue**. Triple Screen (our coding of the description, [S87] UNVERIFIED): allowed_side = sign(slope of weekly MACD histogram); pullback = daily oscillator (Stochastic 14,3,3 or Force Index) against allowed_side; trigger = intraday close through the prior bar's extreme in the allowed direction.
- *TF / decision:* W, D, intraday; trend then timing. *Data:* yes (bars only).
- *Subjectivity:* 1 (oscillator choice and trigger).
- *Failure modes:* slow screen 1 lags turns; screen 2 in a strong trend never gives a pullback, so no trades; many parameters to tune (see MT-G7).
- *Evidence:* practitioner claim, Elder (his site sells books, webinar and video passes and a course, and runs a members community called SpikeTrade; verified from the site navigation, pricing not read, [S68]). The 1986 origin and the three-screen description come from search snippets only: UNVERIFIED.

---

### B. Trend structure

**B1. Swing highs and lows (pivots)**
- *Plain English:* A swing high is a peak that is higher than the bars around it; a swing low is a valley lower than the bars around it. Everything else in "market structure" is built on these.
- *Exact definition:* fractal of order N: bar j is a swing high if h_j > max(h_(j-N..j-1)) and h_j >= max(h_(j+1..j+N)); mirror for lows. **It becomes known only when bar j+N has completed**, so record `confirmed_at = end of bar j+N`, never the time of bar j. The open-source Smart Money Concepts library defines it the same way (a high that is the highest of `swing_length` candles before *and after*, verified, [S72]). Alternative: ZigZag with a reversal threshold of k x ATR, whose last leg repaints until the reversal is confirmed.
- *TF / decision:* any; trend and levels. *Data:* yes.
- *Subjectivity:* 1 (N or k changes every label).
- *Failure modes:* the delay of N bars; different N gives different structure; labels drawn on charts by tools using both-side windows *look* perfect and leak the future into backtests.
- *Evidence:* definitional (no performance claim).

**B2. Higher highs / higher lows trend classification**
- *Plain English:* An uptrend is a series of rising peaks and rising valleys; a downtrend is falling peaks and falling valleys; a mix is a range.
- *Exact definition:* from the two most recent **confirmed** swing highs (H1 older, H2 newer) and lows (L1, L2): uptrend if H2 > H1 and L2 > L1; downtrend if H2 < H1 and L2 < L1; else range. Trend age = bars since the first swing of the current sequence.
- *TF / decision:* 5m to weekly; trend. *Data:* yes.
- *Subjectivity:* 1.
- *Failure modes:* whipsaws in ranges; lags by N bars; timeframes contradict each other.
- *Evidence:* practitioner claim (Grimes: "you have to be able to read market structure and understand trends", verified quote, [S66]; Brooks; Dow theory).

**B3. Break of structure (BOS) and change of character (CHoCH)**
- *Plain English:* A break of structure is price closing beyond the last swing point in the direction of the trend (trend continues). A change of character is the first close beyond the last swing point *against* the trend (a possible turn).
- *Exact definition:* with the trend up, BOS = close > last confirmed swing high; CHoCH = close < last confirmed swing low. The SMC library offers both with a `close_break` option (close versus wick, verified, [S72]). Educators differ on the exact wording.
- *TF / decision:* 1m to 1h; timing and trend change. *Data:* yes.
- *Subjectivity:* 1 to 2 (terms are not standardised).
- *Failure modes:* the library's swing function looks N candles forward, so its BOS and order-block outputs at bar t **use future bars** (verified, [S72]); do not use it as is. False breaks are common in ranges.
- *Evidence:* practitioner claim. The library says it is "inspired by Inner Circle Trader (ICT) concepts" (verified, [S72]); that this community sells mentorships is general knowledge I did not verify. No primary source read. Treat as a story until tested.

**B4. Trendlines and channels**
- *Plain English:* A line through two or more swing lows (uptrend) or highs (downtrend); a channel adds a parallel line through the opposite swings.
- *Exact definition (codeable version):* regression channel over the last n closes: y_hat +/- k x sd(residual), slope b = cov(t, c) / var(t). Anchor-based version: line through the two most recent confirmed swing lows (uptrend) and a parallel through the intervening swing high. StockCharts describes a channel as a continuation pattern with a rising or falling pair of boundaries ([S53]).
- *TF / decision:* 5m to weekly; trend and levels. *Data:* yes.
- *Subjectivity:* 2 when drawn by hand (which two points?); 1 for regression.
- *Failure modes:* drawn after the fact; many valid lines through the same swings; a line break is not confirmation.
- *Evidence:* practitioner claim; verified only as a definition.

---

### C. Moving averages

**C1. SMA and EMA, lengths 9, 20, 50, 200**
- *Plain English:* The average close of the last n bars (SMA), or the same with more weight on recent bars (EMA). Price above a rising average is "up"; the 200-day average is the long-term dividing line for many investors; 9 and 20 are used for short-term pullbacks.
- *Exact definition:* SMA_n = mean of the last n closes. EMA_n = alpha x c + (1 - alpha) x EMA_prev with alpha = 2/(n+1), seeded with an SMA (verified, [S23]). Use at least 5n bars of warm-up.
- *TF / decision:* 1m to weekly; trend and dynamic support. *Data:* yes (daily 200 needs 200 completed daily bars; free history to 2016).
- *Subjectivity:* 0.
- *Failure modes:* lag; whipsaw in ranges; different vendors seed EMAs differently; the current forming bar changes the value all day (use completed bars only). Grimes says he has "written at great length about how moving averages don't work" as signals, yet finds an edge in trading *near* an average after a strong move (verified quote, [S66]).
- *Evidence:* practitioner claim. Our backtest: EMA 9/21 pullback on 5-minute bars lost after costs out of sample (SPY -0.94 bps, QQQ -0.25 bps per trade at 1.5 bps a side; not significant) ([S84]).

**C2. Moving-average slope**
- *Plain English:* Is the average pointing up, down or flat? Flat means range.
- *Exact definition:* slope_k = (EMA_t - EMA_(t-k)) / (k x ATR14) in ATR per bar; flat if |slope_k| < epsilon (e.g., 0.02 ATR per bar, our choice).
- *TF / decision:* 5m to daily; trend versus range filter. *Data:* yes. *Subjectivity:* 1 (k and epsilon).
- *Failure modes:* the range/trend line is arbitrary; slope of an EMA is itself lagged.
- *Evidence:* practitioner claim.

**C3. Distance from the average**
- *Plain English:* How far price is stretched from its average. Far away means "extended" (risk of snap-back); close means "at value".
- *Exact definition:* (close - MA) / MA (StockCharts' "Distance From Moving Average", verified, [S60]) or in ATR units (close - EMA20) / ATR14.
- *TF / decision:* 1m to daily; risk and mean reversion. *Data:* yes. *Subjectivity:* 0.
- *Failure modes:* in strong trends "extended" stays extended; units differ across regimes (use ATR units).
- *Evidence:* practitioner claim.

**C4. Crosses and stage rules (golden cross, 30-week average, "trend template")**
- *Plain English:* Fast average crossing the slow one (EMA 9/20 short-term; SMA 50/200 "golden cross" and "death cross"); Weinstein's stage analysis uses the 30-week average; Minervini's "trend template" is a checklist of average relationships and distance from the 52-week high and low.
- *Exact definition:* cross = sign(MA_fast - MA_slow) changes on a completed bar. Stage/template rules are lists of inequalities among SMA50/150/200, their slopes, and 52-week high and low distance. Exact thresholds for the last two were not verified here (UNVERIFIED).
- *TF / decision:* daily and weekly; position trend. *Data:* yes. *Subjectivity:* 0 for crosses, 1 for checklists.
- *Failure modes:* very late signals; many false crosses in ranges; template and stage rules were designed for single stocks, not SPY/QQQ.
- *Evidence:* practitioner claim (Weinstein, Minervini: books; whether they also sell paid services was not verified).

---

### D. VWAP family

**D1. Session VWAP**
- *Plain English:* The day's volume-weighted average price: the average price paid by everyone so far today. Institutions use it as a benchmark; day traders use it as "fair value" and a trend filter (above = buyers in control).
- *Exact definition:* VWAP_t = sum over completed bars since 09:30 of TP_i x v_i, divided by the sum of v_i (verified, [S24]). It resets every day, the first value equals the first bar's typical price, and it is not defined on daily bars. The exact tick version uses trade price x size from SIP trades.
- *TF / decision:* 1m to 15m; trend filter, fair value, mean-reversion anchor. *Data:* **delayed** in the strict sense: live IEX volume is about 2.5% of consolidated volume, so weights differ from SIP history (MT-G35).
- *Subjectivity:* 0.
- *Failure modes:* few data points early in the day (verified, [S24]); it lags more as the day goes on; flips every few minutes in a range (a "flip on every cross" rule made about 16 trades a day and lost to costs in our test).
- *Evidence:* practitioner claim plus a paper co-authored by the founder of a members-only trading community (the repo's research notes call it a paid community; I saw only its members-site navigation) (Zarattini & Aziz 2023: QQQ, 2018 to 2023, +671% net of commission, Sharpe 2.1, abstract read on the authors' site, [S80]; Aziz's Bear Bull Traders runs a members site with rooms, an "ELITE" tier and an education center, pricing not read, [S81]). Our backtest: VWAP trend on QQQ lost after costs out of sample (-2.74 bps per trade at 1.5 bps a side) ([S84]).

**D2. VWAP deviation bands**
- *Plain English:* Bands a number of "normal wiggles" above and below VWAP. Price far outside is "stretched".
- *Exact definition (ours; vendors differ):* sigma_t squared = sum(v_i x (TP_i - VWAP_t)^2) / sum(v_i), computed with running sums; bands = VWAP_t +/- k x sigma_t for k in {1, 2, 3}; z_t = (c - VWAP_t) / sigma_t. Undefined for the first ~15 minutes.
- *TF / decision:* 1m to 5m; mean reversion versus trend-day detection. *Data:* delayed. *Subjectivity:* 1.
- *Failure modes:* on a trend day price "rides" the outer band; sigma definition changes the signal.
- *Evidence:* practitioner claim. Our backtest: 2-SD VWAP fade lost steadily after costs (SPY -2.84, QQQ -3.22 bps per trade) ([S84]).

**D3. Anchored VWAP (AVWAP)**
- *Plain English:* VWAP started from a chosen event (a swing low, a gap, earnings) instead of the daily open. It shows whether buyers or sellers have been in charge since that event.
- *Exact definition:* AVWAP_t = sum from anchor bar a through t-1 of TP_i x v_i / sum of v_i (verified, [S25]); same formula as VWAP, different start bar. Rule-based anchors for code: prior-day low bar, prior-day high bar, the open of a gap day, last confirmed weekly swing.
- *TF / decision:* 5m to daily; levels and trend. *Data:* delayed (volume).
- *Subjectivity:* 2 when the anchor is picked by eye; 0 to 1 when rule-based.
- *Failure modes:* "significant low" is known only in hindsight, so anchors must use confirmed swings; many anchors give many lines, some always near price.
- *Evidence:* practitioner claim (popularised by Brian Shannon; the StockCharts page links a video with him, [S25]; his courses are commercial: not verified).

---

### E. Volume

**E1. Volume and relative volume (RVOL)**
- *Plain English:* Is this bar busier or quieter than normal? A move on heavy volume is "committed"; on light volume it is "thin".
- *Exact definition:* RVOL_t = v_t / SMA_n(v), default n = 50 (verified, [S36]). StockCharts notes many day traders want RVOL above 2.0 and that a spike of 4.0 or more can foreshadow a reversal (verified, [S36]).
- *TF / decision:* 1m to daily; context and confirmation. *Data:* delayed (same-feed rule).
- *Subjectivity:* 0.
- *Failure modes:* volume differs by time of day (use E2); IEX-versus-SIP mismatch; opex, index-rebalance and half-days distort the baseline.
- *Evidence:* practitioner claim.

**E2. Time-of-day RVOL and cumulative RVOL**
- *Plain English:* Compare with the same minute on earlier days, because the open and close are always busier than lunch.
- *Exact definition:* RVOL-TOD_t = v_t (or a 5-bar sum) divided by the mean of the same slot over the previous 20 sessions (verified as a concept, [S36]). Cumulative version: cumulative volume so far today divided by the mean cumulative volume at the same minute over the previous 20 sessions. Baseline excludes today.
- *TF / decision:* 1m to 5m; "is today active?". *Data:* delayed. *Subjectivity:* 0.
- *Failure modes:* missing minutes (Alpaca emits no bar if a minute had no eligible trade, verified, [S1]); early closes; using today in its own baseline.
- *Evidence:* practitioner claim.

**E3. On-balance volume and accumulation/distribution**
- *Plain English:* Running totals of volume signed by whether price rose or fell (OBV), or by where the bar closed in its range (accumulation/distribution).
- *Exact definition:* OBV_t = OBV_(t-1) + v_t if c_t > c_(t-1); minus v_t if c_t < c_(t-1); unchanged if equal (verified idea, [S38]). Accumulation/distribution (Chaikin): Money Flow Multiplier = ((c - l) - (h - c)) / (h - l); ADL_t = ADL_(t-1) + multiplier x v_t (verified, [S39]).
- *TF / decision:* 5m to daily; confirmation and divergence. *Data:* delayed. *Subjectivity:* 0 (divergences: 2).
- *Failure modes:* the level depends on the start date; only the slope and divergence are used, and divergence is judgment.
- *Evidence:* practitioner claim (Granville, Chaikin).

**E4. Effort versus result (volume spread analysis, Wyckoff)**
- *Plain English:* Big volume with a small price move suggests someone is absorbing the other side; big volume with a big move and a close at the extreme suggests genuine push or a climax.
- *Exact definition (ours):* z_v = (v - mean20)/sd20 for the same time slot; z_r = same for bar range; CLV as above. absorption = z_v >= 2 and z_r <= 0; climax = z_v >= 3 and z_r >= 2 and |CLV| >= 0.8.
- *TF / decision:* 1m to 15m; reversals versus continuation. *Data:* delayed. *Subjectivity:* 1 to 2.
- *Failure modes:* the story is constructed after the fact ("absorption" versus "trend" looks identical until the next bars).
- *Evidence:* practitioner claim (Wyckoff method; Tom Williams). Not verified beyond the Wyckoff description in [S56].

**E5. Volume profile (point of control, value area, high and low volume nodes)**
- *Plain English:* A sideways histogram showing how much volume traded at each price. The peak is the **point of control (POC)**; the band holding most of the volume is the **value area**; thick zones (HVN) are "accepted" prices, thin zones (LVN) are prices the market ran through quickly.
- *Exact definition:* choose window W (today so far, prior day, prior week) and bin size b (e.g., $0.05 for SPY). Allocate each bar's volume to bins (choice: at TP, at close, or spread evenly over [l, h]). POC = bin with the most volume. Value area = start at POC and add the adjacent bin with more volume, one at a time, until 70% of total volume is inside (CQG describes this expansion rule for TPO counts, verified, [S73]). HVN/LVN = local maxima/minima of a smoothed profile (thresholds ours). StockCharts' version uses **closing prices only** and 12 equal zones over the chart window (verified, [S26]).
- *TF / decision:* levels (prior-day POC/VAH/VAL are the usual map). *Data:* delayed (needs SIP volume by price; trade-level data is best).
- *Subjectivity:* 1.
- *Failure modes:* bin size and volume allocation change the peaks; a developing profile's POC moves; StockCharts warns that a profile built from the whole chart window cannot validate past levels ("current bars should not be used to validate past support", verified, [S26]), which is look-ahead if the window contains the future.
- *Evidence:* practitioner claim.

**E6. TPO / Market Profile (initial balance, single prints)**
- *Plain English:* A time-based cousin of volume profile: every 30 minutes gets a letter, and each price touched in that half hour gets one letter. The **initial balance (IB)** is the first hour (letters A and B) (verified, [S74]).
- *Exact definition:* for each 30-minute bracket, add one TPO at every price tick between that bracket's low and high; POC = price with the most TPOs; value area = 70% of TPOs by the CQG expansion rule ([S73]); IB = high and low of 09:30 to 10:30; single prints = prices with exactly one TPO.
- *TF / decision:* 30m, session; day type and levels. *Data:* yes for price-only TPO from bars (delayed if volume is used).
- *Subjectivity:* 1.
- *Failure modes:* tick size and bracket length change the shape; profile "shape" reading is largely visual.
- *Evidence:* practitioner claim (Steidlmayer, Dalton; taught by charting vendors and educators, several of whom sell software or courses; not checked for each).

---

### F. Levels

**F1. Prior-day high, low and close (PDH / PDL / PDC)**
- *Plain English:* Yesterday's extremes and closing price, the most-watched levels on any day chart.
- *Exact definition:* PDH = max high and PDL = min low of the previous regular session; PDC = last regular-session price (best: the closing-auction price, which Alpaca provides through its historical auctions endpoint, SIP only, verified, [S9]). Alpaca's daily bars ignore extended-hours prices and treat some prints differently from minute bars ([S1]); so compute all levels from one source consistently. Distance to level in ATR14 (daily) units.
- *TF / decision:* levels, risk, targets. *Data:* yes (prior-day values from SIP history; live price from IEX).
- *Subjectivity:* 0.
- *Failure modes:* IEX versus SIP daily extremes differ; using today's forming daily bar by mistake.
- *Evidence:* practitioner claim. Our backtest: PDH/PDL break on 5m lost after costs (SPY -1.52, QQQ -4.51 bps per trade) ([S84]).

**F2. Overnight and pre-market high and low**
- *Plain English:* The range traded before the open (04:00 to 09:30 ET on SIP; after-hours of the previous day can be added). Traders watch these as early support and resistance and for the size of the gap.
- *Exact definition:* PMH = max price, PML = min price over 04:00 to 09:30 ET from SIP extended-hours bars; position = (price - PML) / (PMH - PML). IEX itself only trades from 08:00 ET (verified, [S12]), so a live IEX-only value covers 08:00 to 09:30 and is not comparable.
- *TF / decision:* levels and gap context. *Data:* **delayed** (SIP history for research; live IEX covers only 08:00 onward).
- *Subjectivity:* 0 (which hours: 1).
- *Failure modes:* thin trading gives unreliable extremes (bars exist only for minutes with eligible trades); feed mismatch.
- *Evidence:* practitioner claim.

**F3. Opening range (OR)**
- *Plain English:* The high and low of the first few minutes. A break above or below is read as "which way the day may go".
- *Exact definition:* OR_n high = max h and low = min l over bars starting 09:30 to 09:30 + n - 1 minutes, n in {5, 15, 30, 60}; usable only after the n-th minute bar completes. Toby Crabel's 1990 book defined the opening range breakout on the first five minutes (verified via [S42]).
- *TF / decision:* 1m to 5m; timing and levels. *Data:* yes (price-only; IEX extremes can differ slightly from SIP).
- *Subjectivity:* 0 (n and entry rule: 1).
- *Failure modes:* first minutes are the widest-spread, noisiest part of the day; trades cluster.
- *Evidence:* practitioner claim; our backtest: ORB5 on QQQ replicated before costs in year 1 and faded to about zero in year 2; ORB15/ORB30 lost after costs ([S84]).

**F4. Weekly and monthly highs and lows; 52-week extremes**
- *Plain English:* Prior week's and month's high and low, and the year's high and low: the big shelves on which price often pauses.
- *Exact definition:* from completed weekly/monthly bars (built from daily bars); distance in ATR14 (daily) units. Current-week developing extremes update daily.
- *TF / decision:* W/M; levels for swing targets, stops and context. *Data:* yes. *Subjectivity:* 0.
- *Failure modes:* the more levels you draw, the more likely one is always near price ("confirmation bias by map density").
- *Evidence:* practitioner claim.

**F5. Round numbers**
- *Plain English:* Prices like 750.00 or 700.00 attract orders and attention.
- *Exact definition:* distance to the nearest multiple of R (R = $5 and $10 for SPY and QQQ, our choice) in ATR14 (5m) units.
- *TF / decision:* levels. *Data:* yes. *Subjectivity:* 1 (R).
- *Failure modes:* any grid of levels will sometimes "work"; without a placebo test it proves nothing.
- *Evidence:* practitioner claim (not verified).

**F6. Pivot points (floor-trader levels)**
- *Plain English:* Levels computed from yesterday's high, low and close. Price above the central pivot is "strong", below is "weak".
- *Exact definition:* P = (H + L + C)/3 of the prior period. Standard: R1 = 2P - L, S1 = 2P - H, R2 = P + (H - L), S2 = P - (H - L) (numeric formulas UNVERIFIED: the extracted page text does not contain them). Fibonacci pivots add 38.2%, 61.8% and 100% of (H - L) to P for R1..R3 and subtract for S1..S3 (verified, [S40]). Intraday charts use the prior day; 30-120 minute charts use the prior week (verified, [S40]).
- *TF / decision:* levels. *Data:* yes. *Subjectivity:* 0.
- *Failure modes:* many levels close together; levels do not use volume; no known reason for the specific multiples.
- *Evidence:* practitioner claim (floor-trader tradition).

**F7. Fibonacci retracements**
- *Plain English:* After a move, price often pulls back part of the way (commonly 38.2%, 50%, 61.8%) before continuing.
- *Exact definition:* between a confirmed swing low S and swing high H: level_x = H - x x (H - S) for x in {0.236, 0.382, 0.5, 0.618} (the four common levels on StockCharts' tool, verified, [S55]; some tools add 0.786, not verified here). Which swing is used is the whole game.
- *TF / decision:* 5m to weekly; pullback targets. *Data:* yes.
- *Subjectivity:* 2 by hand; 1 with a rule for the swing.
- *Failure modes:* choose the swing after the fact; with several levels, one always catches some reversal.
- *Evidence:* practitioner claim (StockCharts describes the tool, verified, [S55]).

**F8. Prior-day value area and open location**
- *Plain English:* Where today opens relative to yesterday's value area. Opening inside it hints at a balanced day; opening outside hints at a possible trend or a failed attempt.
- *Exact definition:* VAH/VAL/POC from yesterday's profile (E5/E6); location = {inside, above, below}; distance in ATR.
- *TF / decision:* 30m/session; day type. *Data:* delayed.
- *Subjectivity:* 1.
- *Failure modes:* profile-construction choices; the "rules" for what each location implies are folklore.
- *Evidence:* practitioner claim (Dalton; secondary summaries only, [S75]).

**F9. Support and resistance zones (the umbrella idea)**
- *Plain English:* Price areas where buyers (support) or sellers (resistance) showed up before. A broken support can turn into resistance, and the other way round (verified, [S61]). F1 to F8 are all ways of drawing such zones.
- *Exact definition (ours):* cluster confirmed swing highs and lows that lie within 0.3 x ATR14 of each other into a zone; strength = number of touches and recency; a zone is "broken" when a completed bar closes beyond it by at least 0.25 x ATR14. Ages are counted from each swing's confirmation time, not its own bar.
- *TF / decision:* any; levels, targets, stops. *Data:* yes.
- *Subjectivity:* 1 to 2 (which swings, what tolerance).
- *Failure modes:* zones are drawn after the fact; wide zones always contain price; clustering parameters decide the answer; more zones means one is always nearby.
- *Evidence:* practitioner claim; concept verified on [S61].

---

### G. Gaps

**G1. Gap size and type**
- *Plain English:* The jump between yesterday's close and today's open. StockCharts lists common gaps (uneventful), breakaway gaps (out of a range, on heavy volume), runaway/measuring gaps (mid-trend) and exhaustion gaps (near the end of a trend on very high volume) (verified, [S41]).
- *Exact definition:* gap = open_today - close_prev, using the auction prices when available ([S9]); gap% = gap / close_prev; gap in ATR = gap / ATR14 (daily). Type proxies (ours): breakaway = gap out of a 20-day range with volume >= 1.5x average; exhaustion = gap after a 10-day trend with RVOL >= 3.
- *TF / decision:* daily/open; context and bias. *Data:* delayed (official auction prices are SIP only).
- *Subjectivity:* 0 for size; 1 to 2 for type.
- *Failure modes:* "type" is known only in hindsight; the first 1-minute bar's open is not the opening-auction price.
- *Evidence:* practitioner claim; our backtest: gap fade on SPY +3.94 bps per trade at 1.5 bps a side but the 95% range was -8.72 to +16.74 (74 trades), and the QQQ check lost ([S84]).

**G2. Gap fill**
- *Plain English:* "Getting filled" means price later retraces to yesterday's close (verified, [S41]). Common gaps usually fill; breakaway and runaway gaps may not, and the adage that "all gaps get filled" is not reliable (verified, [S41]).
- *Exact definition:* for a gap up, fill fraction f_t = (open - min low so far) / (open - close_prev), capped at 1; filled if low <= close_prev. Time-to-fill in minutes.
- *TF / decision:* open to close; target and bias. *Data:* yes.
- *Subjectivity:* 0.
- *Failure modes:* selection: only filled gaps are remembered; conditioning on gap size and context is needed.
- *Evidence:* practitioner claim; testable with 2016 to 2026 daily and minute data (section 3).

---

### H. Candlesticks

**H1. Single-bar patterns (doji, hammer, shooting star, marubozu)**
- *Plain English:* The shape of one bar: body (open to close) and wicks (shadows). A doji is open equal to close (indecision); a hammer has a small body high in the range after a decline (rejection of lower prices) (verified descriptions, [S54]).
- *Exact definition (ours):* body = |c - o|, range = h - l, upper = h - max(o, c), lower = min(o, c) - l. Doji: body <= 0.1 x range. Hammer: lower >= 2 x body, upper <= 0.1 x range, and the prior 5-bar trend is down. Marubozu: upper and lower <= 0.05 x range.
- *TF / decision:* 1m to daily; timing at levels. *Data:* yes (but candle shape depends on the feed).
- *Subjectivity:* 1.
- *Failure modes:* thresholds arbitrary; needs a "trend before" definition; **on 1-minute bars the shape depends on the data source**: Bulkowski notes that even a one-second offset changes minute candles (verified quote, [S64]), and IEX-only bars differ from SIP bars.
- *Evidence:* practitioner claim (Nison's book, taught in courses).

**H2. Multi-bar patterns (engulfing, inside/outside bar, stars)**
- *Plain English:* Two- and three-bar shapes. A bullish engulfing bar has a body that covers the whole body of the previous down bar (verified: "does not require the entire range to be engulfed, just the open and close", [S54]).
- *Exact definition:* engulfing_up: c_(t-1) < o_(t-1), c_t > o_t, o_t <= c_(t-1), c_t >= o_(t-1). Inside bar: h_t <= h_(t-1) and l_t >= l_(t-1). Outside bar: h_t > h_(t-1) and l_t < l_(t-1).
- *TF / decision:* 5m to daily; timing. *Data:* yes. *Subjectivity:* 1.
- *Failure modes:* dozens of named patterns multiply the number of trials (MT-G7); "context" rules are unlimited.
- *Evidence:* practitioner claim.

---

### I. Classic chart patterns

Bulkowski's own FAQ states the limits of his numbers (verified, [S64]): tests use **end-of-day** data on stocks (he says intraday results may differ); "failure" means price does not move more than 5% after the breakout; the reported move is measured to the *ultimate high or low* (best case), which he says "is best for comparing one chart pattern to another but not as a gauge for how successful you will be trading a chart pattern"; he identified patterns by eye (38,500 of them), and his own free software "makes mistakes". He sells books (his FAQ calls his pattern software free). None of these statistics applies to 1-minute SPY or QQQ.

**I1. Flags and pennants**
- *Plain English:* A sharp move (the pole), a short tight pause (the flag), then a break in the same direction.
- *Exact definition (ours):* pole = move >= 3 x ATR14 within <= 15 bars on volume above average; flag = next 5 to 20 bars with range <= 0.5 x pole, sloping against the pole, volume falling; trigger = close beyond the flag boundary in the pole direction; measured target = pole length. Description verified in [S49].
- *TF / decision:* 5m to daily; continuation. *Data:* yes. *Subjectivity:* 1 to 2.
- *Failure modes:* every parameter is free; flags "found" only in hindsight; false breakouts.
- *Evidence:* practitioner claim.

**I2. Wedges (rising and falling)**
- *Plain English:* Two lines both sloping the same way and converging. Falling wedge = bullish bias; rising wedge = bearish bias (verified description, [S52]).
- *Exact definition:* fit lines to >= 2 confirmed swing highs and >= 2 confirmed swing lows; same-sign slopes, converging, with fit error under a tolerance.
- *TF / decision:* 15m to daily; reversal. *Data:* yes. *Subjectivity:* 2.
- *Failure modes:* line fitting is arbitrary; confirmation lag.
- *Evidence:* practitioner claim.

**I3. Triangles (symmetrical, ascending, descending)**
- *Plain English:* Price squeezes between converging lines and then breaks out. StockCharts requires at least four swing points, lower highs and higher lows, and shrinking volume (verified, [S50]).
- *Exact definition:* as I2 with slope rules: symmetrical = upper falling and lower rising; ascending = flat top and rising lows; descending = flat bottom and falling highs.
- *TF / decision:* 15m to daily; breakout timing. *Data:* yes. *Subjectivity:* 2.
- *Failure modes:* the direction is unknown until the break ("can only be determined after a valid breakout", [S50]); false breaks.
- *Evidence:* practitioner claim.

**I4. Head and shoulders (top and bottom)**
- *Plain English:* Three peaks, the middle one highest, two similar shoulders, a "neckline" through the lows between them; confirmed when price closes through the neckline (verified description, [S48]).
- *Exact definition (ours):* five confirmed alternating swings P1 (left shoulder), T1, P2 (head), T2, P3 (right shoulder) with P2 > P1, P2 > P3, |P1 - P3| <= 0.15 x (P2 - neckline), neckline = line through T1 and T2; trigger = close below the neckline. Lo, Mamaysky and Wang (2000) proposed detecting such shapes with kernel smoothing to remove subjectivity (abstract verified: shapes are "in the eye of the beholder", [S77]). Two-sided smoothing uses future points: use a trailing window.
- *TF / decision:* daily and weekly (rare intraday). *Data:* yes. *Subjectivity:* 2.
- *Failure modes:* few examples so results are noisy; many near-misses.
- *Evidence:* practitioner claim; academic test to be graded by the colleague.

**I5. Double top and double bottom**
- *Plain English:* Two peaks (or valleys) at about the same price with a dip between; the pattern is only confirmed when the dip's low breaks (verified, [S51]).
- *Exact definition (ours):* two confirmed swing highs within 0.5 x ATR14 of each other, separated by >= 10 bars, with an intervening swing low at least 1 x ATR14 lower; trigger = close below that low.
- *TF / decision:* 5m to daily; reversal. *Data:* yes. *Subjectivity:* 1 to 2.
- *Failure modes:* triple tops, "almost equal" peaks; confirmation lag.
- *Evidence:* practitioner claim.

**I6. Base patterns (cup and handle, flat base, volatility contraction)**
- *Plain English:* Multi-week consolidations before breakouts in strong stocks.
- *Exact definition:* not specified here (books describe them visually). *Data:* yes. *Subjectivity:* 2.
- *Failure modes:* single-stock tools; not relevant for SPY/QQQ minute trading.
- *Evidence:* practitioner claim (O'Neil, Minervini; UNVERIFIED).

---

### J. Momentum and oscillators

**J1. RSI (relative strength index)**
- *Plain English:* A 0-100 gauge of how one-sided recent moves have been. Above 70 "overbought", below 30 "oversold" (Wilder's convention).
- *Exact definition (verified, [S33]):* first average gain and loss = simple 14-period averages; then AvgGain_t = (AvgGain_(t-1) x 13 + gain_t) / 14 (same for loss); RS = AvgGain / AvgLoss; RSI = 100 - 100 / (1 + RS). Values depend on how much history is used (StockCharts starts 250 bars earlier). Connors' RSI(2) is a popular short version.
- *TF / decision:* 1m to daily; overextension. *Data:* yes. *Subjectivity:* 0 (divergences 2).
- *Failure modes:* in trends RSI stays "overbought"; the StockCharts page itself notes overbought "can also be a sign of strength" ([S33]).
- *Evidence:* practitioner claim (Wilder 1978).

**J2. MACD (12, 26, 9)**
- *Plain English:* The gap between a fast and a slow moving average, and its own average; crossing zero or its signal line is read as a momentum shift.
- *Exact definition (verified, [S31]):* MACD = EMA12(c) - EMA26(c); signal = EMA9(MACD); histogram = MACD - signal.
- *TF / decision:* 5m to weekly; momentum. *Data:* yes. *Subjectivity:* 0.
- *Failure modes:* lags; unbounded, so not useful for overbought/oversold (StockCharts, verified, [S31]).
- *Evidence:* practitioner claim (Appel).

**J3. Stochastic oscillator (14, 3, 3)**
- *Plain English:* Where the close sits inside the recent high-low range (0 to 100).
- *Exact definition (verified, [S32]):* %K = (close - lowest low_14) / (highest high_14 - lowest low_14) x 100; %D = 3-period SMA of %K; slow versions smooth %K again.
- *TF / decision:* 5m to daily; pullback timing. *Data:* yes. *Subjectivity:* 0.
- *Failure modes:* pinned at extremes in trends.
- *Evidence:* practitioner claim (Lane).

**J4. ADX and directional indicators (trend strength)**
- *Plain English:* ADX says how strong a trend is (not its direction); +DI versus -DI says which side is winning.
- *Exact definition (verified, [S34]):* +DM and -DM from consecutive highs and lows; smoothed with Wilder's method over 14 periods; +DI = 100 x smoothed(+DM) / smoothed(TR); DX = 100 x |+DI - -DI| / (+DI + -DI); ADX = Wilder-smoothed DX. Needs about 150 bars to settle.
- *TF / decision:* 5m to daily; trend versus range. *Data:* yes. *Subjectivity:* 0 for the numbers; 1 for the threshold (Wilder suggests a strong trend when ADX is above 25; many traders use 20; verified, [S34]).
- *Failure modes:* lag; late in trends.
- *Evidence:* practitioner claim (Wilder 1978).

**J5. Divergences (price versus oscillator)**
- *Plain English:* Price makes a new high but the oscillator does not: momentum is "fading".
- *Exact definition:* between two consecutive confirmed swing highs, price higher and RSI (or MACD histogram) lower.
- *TF / decision:* any; reversal warning. *Data:* yes. *Subjectivity:* 2 (which oscillator, which swings).
- *Failure modes:* in strong trends divergences pile up while price keeps rising; confirmation lag.
- *Evidence:* practitioner claim (Wilder, Cardwell; StockCharts notes the disagreement between them, [S33]).


---

### K. Volatility and range

**K1. ATR (average true range)**
- *Plain English:* How much price normally moves per bar, including gaps. Used to size stops and to express every distance in comparable units.
- *Exact definition (verified, [S35]):* see A.0. Percent form ATRP = ATR / close x 100 (StockCharts lists ATR percent as a separate indicator).
- *TF / decision:* 1m to daily; risk (stop distance, position size) and normalising other features. *Data:* yes. *Subjectivity:* 0.
- *Failure modes:* lags a volatility jump; ATR of a low-priced stock is not comparable (StockCharts, verified, [S35]).
- *Evidence:* practitioner claim. Grimes gives "2-4 ATRs beyond the entry" as "a very rough guideline" for pullback stops (verified quote, [S66]).

**K2. Bollinger Bands, %b and BandWidth**
- *Plain English:* A moving average with an envelope two standard deviations away. %b says where price is inside the envelope; BandWidth says how wide the envelope is.
- *Exact definition:* middle = SMA20(c); upper/lower = middle +/- 2 x standard deviation of the last 20 closes; %b = (c - lower) / (upper - lower); BandWidth = (upper - lower) / middle x 100 (verified, [S29]); overlay defaults are 20 periods and 2 standard deviations ([S28]). With default settings BandWidth is four times the coefficient of variation (verified, [S63]).
- *TF / decision:* 1m to weekly; stretch and volatility state. *Data:* yes. *Subjectivity:* 0 (parameters are defaults, rule 9 in [S63]).
- *Failure modes:* Bollinger's own rules say band tags "are just that, tags not signals", closes outside the bands are "initially continuation signals, not reversal signals", and make "no statistical assumptions" from the standard deviation (in practice "90%, not 95%" of data sits inside) (verified, [S63]). He sells books, DVDs and reports.
- *Evidence:* practitioner claim (Bollinger).

**K3. Keltner channels**
- *Plain English:* Like Bollinger Bands but the width comes from ATR, so it is smoother.
- *Exact definition:* Raschke version: middle = EMA20, bands = EMA20 +/- 2 x ATR10 (verified, [S27]). Keltner's original (1960): 10-day SMA of the typical price, plus and minus the 10-day SMA of the high-low range (verified, [S27]).
- *TF / decision:* 5m to daily; trend and stretch. *Data:* yes. *Subjectivity:* 0.
- *Failure modes:* the two versions differ, so "Keltner" is ambiguous.
- *Evidence:* practitioner claim. Grimes prefers Keltner channels to Bollinger Bands and says useful bands should contain "roughly 80% - 90% of the price action" (verified quote, [S66]).

**K4. The squeeze**
- *Plain English:* When volatility gets unusually low (Bollinger Bands narrow inside the Keltner channel), a big move often follows, but the squeeze does not say which way.
- *Exact definition:* squeeze_on when the upper Bollinger Band (20, 2) is below the upper Keltner line and the lower Bollinger Band is above the lower Keltner line, using Carter's settings of 20 periods and a 1.5 multiplier (verified, [S30]; the page notes StockCharts uses Keltner's original range-based formula for this indicator). The "fire" is the first bar where the condition turns false. Direction comes from a momentum histogram (linear-regression based; details in [S30]).
- *TF / decision:* 5m to daily; timing (range expansion). *Data:* yes. *Subjectivity:* 0 for the state, 1 for direction.
- *Failure modes:* no direction; whipsaws; the TTM Squeeze comes from a trading-education company ("John Carter of Trade the Markets (now Simpler Trading)", verified, [S30]).
- *Evidence:* practitioner claim.

**K5. Narrow-range days (NR4, NR7) and inside days**
- *Plain English:* A day whose high-low range is the smallest in the last 4 (or 7) days. Crabel's idea: a quiet day is followed by a bigger one.
- *Exact definition (verified, [S42]):* NR7 if range_d < min(range of the previous 6 days) (the StockCharts scan is `Range < 1 day ago Min(6, Range)`); NR4 with 3 days. Signal (Crabel): next day buy above the NR day's high, sell below its low; Crabel took profits at the first profitable close. Inside day: h_d <= h_(d-1) and l_d >= l_(d-1).
- *TF / decision:* daily; volatility expansion timing. *Data:* yes (SIP daily history since 2016).
- *Subjectivity:* 0.
- *Failure modes:* NR7 is common (StockCharts: dozens per year for a typical stock) and "the chances of whipsaw are above average" (verified, [S42]); neutral on direction.
- *Evidence:* practitioner claim (Crabel 1990, out of print; StockCharts summary). Cheap to test on SPY/QQQ daily data (section 3).

**K6. Realized volatility, expected move and "range used"**
- *Plain English:* How much the market has actually been moving, versus how much the options market expects, and how much of today's normal range is already used up.
- *Exact definition:* RV_n = sqrt(sum of squared 1-minute log returns over the last n completed minutes) (scale to a day by x sqrt(390/n)); compare with the same window on the previous 20 sessions (ratio). Expected daily move from VIX (approximation): VIX / sqrt(252) percent. Range used = (HOD - LOD) / ATR14 (daily).
- *TF / decision:* intraday; risk regime, stop and target sizing. *Data:* RV and range yes; VIX no (daily close is on FRED, [S22]).
- *Subjectivity:* 0.
- *Failure modes:* VIX is a 30-day measure (verified, [S14]), so the daily conversion is rough; returns are not normal.
- *Evidence:* practitioner claim. Volatility clustering (big days tend to follow big days) is a widely reported regularity (general knowledge, no source read here), which makes range and risk a good first thing to test (section 3).

---

### L. Market internals (breadth)

**L1. TICK (NYSE)**
- *Plain English:* At this instant, how many NYSE stocks last traded up versus down. Traders read big positive or negative extremes as buying or selling pressure or exhaustion.
- *Exact definition:* $TICK = number of NYSE stocks whose last trade was an uptick minus the number whose last trade was a downtick; zero-plus ticks are excluded; vendors take it from the NYSE, recalculated about every 6 seconds (verified on an educational vendor page, [S76]; NYSE's own definition not found). Trader thresholds (for example plus or minus 1000) are folklore (UNVERIFIED).
- *TF / decision:* seconds to minutes; timing and confirmation. *Data:* **no** (needs every NYSE trade in real time). Proxy: among the S&P 500 constituents, (# whose last completed 1-minute close is above the prior minute's close) minus (# below); label it PROXY.
- *Subjectivity:* 1 (thresholds).
- *Failure modes:* includes ETFs and odd securities; structural changes in the market shift "extreme" levels; the proxy differs from the real TICK.
- *Evidence:* practitioner claim.

**L2. ADD (advancers minus decliners)**
- *Plain English:* How many stocks are up on the day versus down.
- *Exact definition:* Net advances = advances - declines (verified, [S44]); the A/D line is the running sum; ratio-adjusted version (A - D) / (A + D) (verified, [S45]). Proxy from constituents: count of stocks whose latest price is above the prior close, minus below.
- *TF / decision:* minutes to weeks; breadth and divergence. *Data:* no for the NYSE series; **yes** for a constituent proxy from IEX snapshots (price versus previous close, [S10]), with noisy prints for quiet names.
- *Subjectivity:* 0.
- *Failure modes:* Nasdaq's A/D line can fall while the index rises because of many small listings (StockCharts, verified, [S44]); point-in-time constituent lists are needed to avoid survivorship bias.
- *Evidence:* practitioner claim.

**L3. VOLD (up volume minus down volume)**
- *Plain English:* How much trading volume is in rising stocks versus falling stocks.
- *Exact definition:* Sum of volume of advancing stocks minus sum of volume of declining stocks; the ratio (advancing volume / declining volume) is verified in [S43]. VOLD as a difference is standard usage but was not verified in a source here (UNVERIFIED).
- *TF / decision:* intraday breadth. *Data:* no for NYSE; **delayed** for a constituent proxy (volume from SIP).
- *Subjectivity:* 0.
- *Failure modes:* dominated by a few heavy names; IEX volume is not comparable.
- *Evidence:* practitioner claim.

**L4. TRIN / Arms Index**
- *Plain English:* Compares breadth with volume breadth. Below 1 = volume is flowing into advancers (strong); above 1 = volume is in decliners (weak); it moves opposite to the market.
- *Exact definition (verified, [S43]):* TRIN = (advances / declines) / (advancing volume / declining volume) (Richard Arms, 1967). StockCharts describes surges above 3 as oversold and dips below 0.5 as overbought on daily closes.
- *TF / decision:* intraday/daily; exhaustion. *Data:* no (constituent proxy: delayed). *Subjectivity:* 1 (levels).
- *Failure modes:* unstable when either ratio is near zero; levels depend on smoothing.
- *Evidence:* practitioner claim.

**L5. Percent of stocks above a moving average (and above VWAP)**
- *Plain English:* What share of stocks are above their 50-day or 200-day average (long horizon) or above their own VWAP today (intraday).
- *Exact definition:* count(stocks above MA) / count(stocks) (verified, [S46]); StockCharts uses the 50-day for short-to-medium horizons and the 150/200-day for longer ones. "Percent above own intraday VWAP" is a trader extension: count(price_i > VWAP_i) / N (UNVERIFIED as a named tool).
- *TF / decision:* daily and intraday; breadth. *Data:* yes for daily MA versions from free SIP history; delayed for the VWAP version.
- *Subjectivity:* 0.
- *Failure modes:* survivorship (today's constituents); heavy-weight names dominate the index but count once in the percentage.
- *Evidence:* practitioner claim.

**L6. McClellan Oscillator and new highs minus new lows**
- *Plain English:* A momentum version of the advance-decline line.
- *Exact definition (verified, [S45]):* RANA = (A - D) / (A + D); McClellan Oscillator = 19-day EMA(RANA) - 39-day EMA(RANA). New highs minus new lows: count of stocks at 52-week highs minus lows (definition standard; not verified in a source read here).
- *TF / decision:* daily; breadth momentum. *Data:* constituent proxy yes (daily SIP). *Subjectivity:* 0.
- *Failure modes:* signals are late; breadth can stay weak in rallies led by few names.
- *Evidence:* practitioner claim (McClellan).

---

### M. VIX and the volatility complex

**M1. VIX**
- *Plain English:* The market's expected 30-day volatility of the S&P 500, annualised, read from index option prices. Rises when the market is afraid.
- *Exact definition (verified, [S14]):* constant 30-day maturity, computed from SPX (standard, third-Friday) and SPXW (weekly, PM-settled) options; introduced in 1993 (first value date January 1990), disseminated every 15 seconds between 09:31 and 16:15 ET (regular hours) and 03:15 to 09:25 ET (global hours). Features: prior close, 1-day change, 252-day percentile, and change versus SPY's return (divergence).
- *TF / decision:* daily and intraday; regime, risk, sizing. *Data:* **no** on Alpaca. Daily close is on FRED ("Daily, Close", copyright Cboe, reprinted with permission, verified, [S22]); intraday from Cboe delayed pages (terms not checked).
- *Subjectivity:* 0 (level "thresholds" like 20 are folklore: 1).
- *Failure modes:* VIX is disseminated until 16:15 ET ([S14]), so the day's final value arrives after the 16:00 equity close and must not be used for same-day decisions; it is also mean-reverting, so "high VIX" has no fixed meaning.
- *Evidence:* practitioner claim.

**M2. VIX1D (1-day volatility)**
- *Plain English:* Like VIX but for the expected move over one day, built only from same-day-expiring weekly options.
- *Exact definition (verified, [S15]):* constant 1-day maturity from PM-settled SPXW options; time measured in business minutes (102,060 per year = 252 x 6.75 x 60); special handling when the near-term option has less than 60 business minutes left (about 15:00 ET); disseminated every 15 seconds between 09:31 and 16:15 ET; first value May 2022, launched 24 April 2023. Features: VIX1D / VIX; approximate expected daily move = VIX1D / sqrt(252) percent.
- *TF / decision:* intraday; day-range expectation, event-day detection. *Data:* **no** on Alpaca.
- *Subjectivity:* 0.
- *Failure modes:* short history (from 2022) and it changes as the day passes (time decay of the near-term option); two recent papers discuss its intraday and overnight behaviour (Albers 2025, *Journal of Futures Markets*; a 2024 *Finance Research Letters* paper on an "overnight bias"); I could only see titles because both publishers blocked access: UNVERIFIED.
- *Evidence:* exchange documentation for the definition; no performance evidence read.

**M3. Volatility term structure**
- *Plain English:* Short-dated fear versus longer-dated fear. When near-term implied volatility is above long-term ("inverted"), markets are stressed.
- *Exact definition:* Cboe's constant-maturity family: VIX9D (9 days), VIX (30 days), VIX3M, VIX6M, VIX1Y (verified list, [S16]). Slope = VIX3M / VIX - 1; stress flag when VIX9D > VIX or VIX > VIX3M. The VIX futures curve (contango or backwardation) was not checked (UNVERIFIED).
- *TF / decision:* daily; regime. *Data:* **no** on Alpaca (Cboe; FRED carries some series, not verified). *Subjectivity:* 1 (thresholds).
- *Failure modes:* inversion is a coincident indicator, not a forecast; data licensing.
- *Evidence:* practitioner claim.

**M4. SKEW index**
- *Plain English:* How expensive crash protection is relative to normal option pricing.
- *Exact definition (verified, [S17]):* SKEW = 100 - 10 x S, where S is the priced skewness of 30-day S&P 500 log returns, derived from a portfolio of out-of-the-money SPX options.
- *TF / decision:* daily; tail-risk context. *Data:* **no** on Alpaca. *Subjectivity:* 1.
- *Failure modes:* SKEW and VIX measure different things: in the white paper's 2009 examples SKEW rose from 112.95 to 125.11 while VIX fell from 49.68 to 32.68 (verified, [S17]); whether SKEW helps timing was not read.
- *Evidence:* exchange documentation for the definition; no performance evidence read.

---

### N. Cross-asset context

**N1. E-mini S&P (ES) and Nasdaq (NQ) futures, overnight and pre-market**
- *Plain English:* Index futures trade almost 24 hours, so many day traders read them for the overnight direction and for "where the market wants to open".
- *Exact definition:* overnight change = ES (or NQ) at 09:29 minus the prior 16:00 cash-close-equivalent level; "premium to fair value" = futures minus (cash x (1 + carry)). We have no futures feed.
- *TF / decision:* overnight to open; bias and gap context. *Data:* **no** (Alpaca's documentation index lists no futures data, verified, [S8]). Proxy: SPY/QQQ extended-hours moves from SIP history (delayed), or IEX from 08:00 ET (verified hours, [S12]).
- *Subjectivity:* 0.
- *Failure modes:* proxy is thin and only partially overlaps the futures session; dividend and carry adjustments.
- *Evidence:* practitioner claim.

**N2. Yields, N3. Dollar, N4. Oil, N5. Credit (risk-on / risk-off context)**
- *Plain English:* Falling yields with a rising dollar and widening credit spreads is "risk-off"; the opposite is "risk-on". Oil matters for energy stocks and inflation expectations.
- *Exact definition (ours):* use ETF proxies traded on Alpaca: rates = TLT or IEF return since open (price moves opposite to yields); dollar = UUP return; oil = USO return; credit = HYG return minus IEF return. Daily official series from FRED (series IDs such as DGS10, DGS2, DTWEXBGS, DCOILWTICO, BAMLH0A0HYM2 are standard but were **not verified** here). Alpaca also lists "historical rates for currency pairs" (forex), coverage and plan not checked ([S11]).
- *TF / decision:* intraday and daily; context and divergence (for example SPY up while HYG down). *Data:* proxies **yes** (IEX, sparse prints); official series no.
- *Subjectivity:* 1.
- *Failure modes:* correlations flip between regimes; ETF prints on IEX can be sparse; stale-quote artefacts.
- *Evidence:* practitioner claim (intermarket analysis, Pring; StockCharts sector page links the business cycle to sector leadership, [S58]).

---

### O. Relative strength, sector rotation and breadth thrusts

**O1. Relative strength line (price relative)**
- *Plain English:* Divide one chart by another. If the line rises, the first asset is beating the second.
- *Exact definition (verified, [S37]):* price relative = close of the base security / close of the comparison security (for example QQQ / SPY, or XLK / SPY). Trend of the ratio (moving average, breakout) is the signal. JdK RS-Ratio and RS-Momentum are normalised versions centred on 100 (verified, [S59]).
- *TF / decision:* intraday to weekly; leadership and rotation. *Data:* yes.
- *Subjectivity:* 0 (interpretation 1).
- *Failure modes:* the ratio's level is meaningless; only the trend matters; lags.
- *Evidence:* practitioner claim (relative strength leadership is popular with position traders; academic momentum literature is graded elsewhere).

**O2. Sector rotation and relative rotation graphs**
- *Plain English:* Which sectors are leading and lagging, mapped to the business cycle. StockCharts describes eleven Sector SPDR ETFs (verified, [S58]); the communication-services fund XLC exists (verified, [S82]). The other standard tickers (XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, XLRE) are well known but were not each verified.
- *Exact definition:* for each sector ETF, return since the open (and 1-day, 5-day, 20-day) minus SPY's return, ranked; risk-on spread = mean(XLK, XLY, XLC) minus mean(XLU, XLP, XLV) (our choice). RRG quadrants use RS-Ratio and RS-Momentum around 100 ([S59]).
- *TF / decision:* intraday to monthly; context and stock/sector selection. *Data:* yes (11 sector ETFs fit inside the 30-symbol WebSocket limit, together with SPY, QQQ, IWM, DIA and a few others).
- *Subjectivity:* 1.
- *Failure modes:* the cycle map is a textbook ideal (StockCharts says so, [S58]); sector weights are dominated by a few stocks.
- *Evidence:* practitioner claim.

**O3. Breadth thrusts (Zweig)**
- *Plain English:* A very fast swing from few advancing stocks to many, which some see as the start of a strong advance.
- *Exact definition (verified, [S62]):* ratio = advances / (advances + declines) each day; take its 10-day EMA; a *setup* occurs when it falls below 0.40, and the *thrust* triggers when it rises above 0.615 within 10 trading days. Arthur Hill suggests updating it with S&P 500 or S&P 1500 data because Nasdaq stocks were missing from the NYSE version ([S62]), which makes it codeable from constituent data.
- *TF / decision:* daily; regime (rare event). *Data:* yes with constituent data (daily SIP since 2016).
- *Subjectivity:* 0.
- *Failure modes:* very few signals (statistical power near zero); survivorship in constituent data.
- *Evidence:* practitioner claim.

**O4. Distribution days and follow-through days (IBD)**
- *Plain English:* A distribution day is an index down day (at least 0.2%) on heavier volume than the day before; a cluster of them is said to warn of a top. A follow-through day is described (search snippets only, UNVERIFIED) as a big up day on higher volume from day 4 of a rally attempt, said to confirm a new uptrend.
- *Exact definition:* distribution day: return <= -0.2% and volume > prior day's volume (the 0.2% and the "4 to 5 times in 2 to 3 weeks" come from secondary quotes on [S65], verified as quotes only). Follow-through day thresholds: **UNVERIFIED** (the IBD page I opened returned a video page, [S86]).
- *TF / decision:* daily; market regime for swing trading. *Data:* yes (SPY/QQQ daily; volume from SIP).
- *Subjectivity:* 0 (thresholds vary by source).
- *Failure modes:* **Bulkowski's own test found the signal does not work**: "A cluster of distribution days within 21 calendar days during a rising price trend is supposed to predict a price drop. It doesn't." (verified, [S65]; he tested about 58,800 samples, mostly individual stocks, and the S&P 500; blogger Rob Hanna reported the same).
- *Evidence:* practitioner claim that failed the one independent test read (Weak or None). Bulkowski sells books.

---

### P. Order flow

**P1. Time and sales (the tape)**
- *Plain English:* The live list of trades: price, size, venue, time, and special conditions.
- *Exact definition:* per minute: trade count, mean and max trade size, share of trades above a size threshold, and trade-side estimate by the tick rule (price above the previous trade price = buy) or the quote rule (trade at or above the ask = buy). Alpaca's trade conditions include intermarket sweep orders (code F) and odd lots (code I) (verified, [S1]).
- *TF / decision:* seconds to minutes; timing and confirmation. *Data:* **delayed**: free live trades are IEX only (about 2.5% of volume); full history is SIP trades older than 15 minutes ([S1], [S8]).
- *Subjectivity:* 0 for counts and tick-rule side; 2 for "reading the tape".
- *Failure modes:* IEX prints are a small, biased sample; the tick rule mislabels many trades.
- *Evidence:* practitioner claim (Wyckoff's 1910 "Studies in Tape Reading": I could not open a copy, UNVERIFIED).

**P2. Level 2 (depth of book)**
- *Plain English:* The list of resting buy and sell orders at each price near the market.
- *Exact definition:* bid and ask size by level; imbalance = (sum bid size - sum ask size) / (sum bid size + sum ask size) over the top k levels; add/cancel rates.
- *TF / decision:* seconds; short-term pressure and liquidity. *Data:* **no** for US stocks on Alpaca (its docs index shows an order-book endpoint only for crypto, [S8]). IEX offers real-time TOPS, DEEP and DEEP+ feeds (pricing not checked) and **free historical downloads on a T+1 basis** for equities and options, but that is one exchange only ([S13]).
- *Subjectivity:* 1 for imbalance; 2 for "spoof detection".
- *Failure modes:* quotes are often not real: SqueezeMetrics (a data vendor) writes that "most of the liquidity that is visible is, in one way or another, a bluff" and that a quote's information content is "either zero or less than zero" (verified quote, [S69]; its own opinion, and it sells subscriptions, [S70]).
- *Evidence:* practitioner claim.

**P3. Footprint, delta and cumulative delta (CVD)**
- *Plain English:* For each price in a bar, how much volume traded at the bid versus at the ask. Delta = buying at the ask minus selling at the bid; CVD is the running total.
- *Exact definition:* classify each SIP trade against the prevailing quote (at or above ask = buy, at or below bid = sell, else tick rule); delta per bar = sum(buy size) - sum(sell size); CVD = cumulative sum; imbalance at a price when ask volume / bid volume exceeds a ratio (vendor tools use 3:1, UNVERIFIED).
- *TF / decision:* 1m to 15m; absorption, divergence. *Data:* **delayed** (needs SIP trades and quotes; history free after 15 minutes; live IEX-only is a partial sample).
- *Subjectivity:* 0 for delta; 2 for reading footprints.
- *Failure modes:* trade-side classification error; the pattern stories ("absorption", "trapped traders") are assembled after the fact.
- *Evidence:* practitioner claim.

**P4. Tape reading (discretionary)**
- *Plain English:* Feeling the speed, size and rhythm of prints to judge who is in control.
- *Exact definition:* not codeable as such; approximations are P1 statistics.
- *Subjectivity:* 2. *Data:* delayed. *Failure modes:* pattern-finding in noise; cannot be audited.
- *Evidence:* practitioner claim; **Not testable** until turned into rules.

**P5. Auction imbalance (open and close)**
- *Plain English:* Before 9:30 and 16:00, the exchanges publish the buy/sell order imbalance that will be matched in the auction; traders use it to judge the open and the close.
- *Exact definition:* imbalance size and side from the exchange imbalance feeds. Alpaca offers historical opening and closing **auction prices** (SIP only, verified, [S9]) but not imbalances.
- *TF / decision:* around 9:30 and 15:50 to 16:00; open/close pressure. *Data:* **no**. *Subjectivity:* 1.
- *Failure modes:* indicative imbalance changes until the cross; not available here.
- *Evidence:* practitioner claim (our LAST30_MOM setup is a related, price-only idea; it lost after costs, [S84]).

---

### Q. Options-specific context

Alpaca facts that apply to the whole group (verified): options history only since **February 2024**; the free "indicative" feed is "a free derivative of the original OPRA feed: the quotes are not actual OPRA quotes, they're just indicative derivatives. The trades are also derivatives and they're delayed by 15 minutes" ([S4]); the free plan allows 200 option quote subscriptions ([S2]); Greeks and IV come from Alpaca's own Black-Scholes calculation and need a non-zero bid and ask and a recent underlying trade, and **0DTE contracts have no Greeks** ([S1]); contract listings carry `open_interest` and `open_interest_date` ([S6]); snapshots and the chain return the latest trade, latest quote and Greeks for each contract ([S7]); streams are either the indicative or the OPRA feed ([S5]).

**Q1. IV rank and IV percentile**
- *Plain English:* Is implied volatility high or low compared with its own past year? Used to decide whether options are "cheap" or "expensive".
- *Exact definition:* IV rank = (IV - min IV over 252 days) / (max IV - min IV) x 100; IV percentile = share of the last 252 days with IV below today's. Both are as quoted on secondary sites (UNVERIFIED; tastytrade's own help page would not load).
- *TF / decision:* daily; option pricing regime. *Data:* **delayed**: ATM IV from the indicative chain; only about 2.6 years of history exist.
- *Subjectivity:* 1 (which IV: ATM 30-day? which strikes).
- *Failure modes:* one spike can stretch the range for a year (rank); IV of near-dated options behaves differently.
- *Evidence:* practitioner claim (tastytrade-style education).

**Q2. Skew (25-delta risk reversal, SKEW)**
- *Plain English:* How much more puts cost than equally-far calls.
- *Exact definition:* RR25 = IV(25-delta put) - IV(25-delta call) at a fixed expiry; or the Cboe SKEW index (M4).
- *TF / decision:* daily; sentiment and tail hedging. *Data:* delayed (needs Greeks/IV from the indicative chain). *Subjectivity:* 1.
- *Failure modes:* bad IV inputs from wide, indicative quotes.
- *Evidence:* practitioner claim.

**Q3. Implied-volatility term structure**
- *Plain English:* IV by expiry. A high front week versus later weeks means an event is priced in.
- *Exact definition:* IV(expiry_1) / IV(expiry_2) for ATM options; event premium = IV front / IV back.
- *TF / decision:* daily; event pricing. *Data:* delayed. *Subjectivity:* 0.
- *Failure modes:* holiday and weekend effects; 0DTE has no Greeks.
- *Evidence:* practitioner claim.

**Q4. Put/call ratio**
- *Plain English:* Put volume divided by call volume, read as sentiment (usually contrarian).
- *Exact definition (verified, [S47]):* Put Volume / Call Volume; Cboe publishes equity, index and total versions; index options are mostly professionals and hedging, equity options more retail, so their normal levels differ.
- *TF / decision:* daily; sentiment. *Data:* **no** on Alpaca (Cboe statistics pages; access terms not checked, [S89]).
- *Subjectivity:* 1.
- *Failure modes:* hedging flow dominates index ratios.
- *Evidence:* practitioner claim (contrarian sentiment).

**Q5. Open-interest walls and "max pain"**
- *Plain English:* Strikes with the most open contracts are said to act like magnets or barriers near expiry. "Max pain" is the strike at which option buyers would lose the most.
- *Exact definition:* call wall = strike above spot with the largest call OI; put wall = strike below spot with the largest put OI; max pain = argmin over K of the total payoff owed to option holders at K. OI is published once a day, so intraday walls are up to a day stale.
- *TF / decision:* daily and expiry week; levels. *Data:* **yes** for SPY/QQQ (Alpaca contracts endpoint, [S6]); history of OI is limited (no stored daily OI history unless we save it ourselves).
- *Subjectivity:* 1.
- *Failure modes:* same-day 0DTE positions are not in OI; who is long or short is unknown.
- *Evidence:* practitioner claim; "max pain" theory: UNVERIFIED.

**Q6. Dealer gamma exposure (GEX), zero-gamma level**
- *Plain English:* A model estimate of how much stock dealers must buy or sell when price moves, because they hedge the options they hold. Positive GEX is said to calm markets (dealers sell rallies and buy dips); negative GEX to amplify moves.
- *Exact definition:* dollar GEX per strike = gamma x open interest x 100 x spot^2 x 0.01 (gamma exposure for a 1% move), summed over strikes with a **sign convention** (public-data versions: calls positive, puts negative). Zero-gamma = the spot at which total GEX, recomputed for hypothetical spots, crosses zero (verified, [S71]).
- *Vendors' own caveats (verified):* SpotGamma: "every public GEX figure depends on modeling assumptions", the call-positive/put-negative formula "is a simplifying inventory convention - not a rule of option mathematics and not a direct observation of every dealer book", and "two legitimate GEX charts can disagree because GEX is a model output, not an exchange-published statistic" ([S71]). SqueezeMetrics: uses a proprietary "dealer directional open interest" built from transaction-level trade direction and OI changes, and says "GEX is very rarely negative" and higher GEX means "tighter returns" ([S69]). Both sell subscriptions (verified from their navigation, [S70], [S71]).
- *TF / decision:* daily and intraday; volatility regime and levels. *Data:* **delayed / poor**: OI daily (yes), gamma from Alpaca greeks (missing for 0DTE, the most gamma-dense contracts, [S1]) or our own Black-Scholes from indicative quotes.
- *Subjectivity:* 2 (the sign assumption is the model).
- *Failure modes:* cannot be validated without dealer books; OI excludes same-day trades; flows changed with 0DTE growth (Cboe: 0DTE contracts more than 20 million a day in Q2 2026 across products, SPX 0DTE volume nearly tripled since the start of 2024 while average trade size shrank, [S19]).
- *Evidence:* vendor claims. Zarattini, Aziz and Barbon (2024) say they test whether "estimated gamma imbalance of dealers" predicts their strategy's profitability; I read only the abstract, not the result ([S78]).

**Q7. 0DTE volume share**
- *Plain English:* The fraction of SPX option volume that expires the same day. A high share means a lot of short-dated speculation and hedging.
- *Exact definition:* SPX 0DTE contracts / all SPX contracts that day. Cboe reported a record 56% in February 2025 (monthly average daily volume 3.49 million contracts; verified, [S18], post dated 3 March 2025). Later numbers (59% for 2025, 65% in Q2 2026) came from a vendor page and a news headline: UNVERIFIED.
- *TF / decision:* daily/monthly; regime context. *Data:* **no** on Alpaca (Cboe).
- *Subjectivity:* 0.
- *Failure modes:* no proven link to next-day returns in anything read here; Cboe sells these products, so its commentary is marketing as well as data.
- *Evidence:* exchange statistics for the number; no predictive evidence read.

**Q8. Unusual options activity (UOA)**
- *Plain English:* Contracts trading far more than usual, often read as "smart money" positioning.
- *Exact definition:* vendor rules such as volume > open interest, volume > k x its 20-day average, or premium above a threshold (definitions UNVERIFIED; the Barchart page would not load).
- *TF / decision:* intraday/daily; sentiment. *Data:* **delayed** (indicative trades are derived and delayed 15 minutes, [S4]).
- *Subjectivity:* 1 to 2.
- *Failure modes:* on SPY/QQQ, heavy volume is mostly hedging and market-making, so direction cannot be read from it; a rule that ranks "unusual" names is a crowd list (MT-G23).
- *Evidence:* practitioner claim. Keep as a shadow log at most.

---

### R. Day-type and analysis frameworks

**R1. Market Profile day types (Dalton)**
- *Plain English:* Six kinds of days, judged by how wide the first hour was and how far price travelled beyond it: normal, normal variation, trend, double distribution, neutral, non-trend. The idea is to notice by the second or third half hour which "personality" the day has and stop trading against it.
- *Exact definition (ours, from a secondary summary of *Mind Over Markets*, [S75]):* IB = high/low of 09:30 to 10:30 (first hour, verified, [S74]). Extension_up = max(0, HOD - IB_high), Extension_down = max(0, IB_low - LOD), in units of IB range. Proxies: normal = wide IB, both extensions <= 0.25; normal variation = one extension between 0.25 and 1; trend = narrow IB, one extension > 1 and no extension on the other side, close in the outer 20% of the range; neutral = both extensions > 0.25; non-trend = total range below 0.5 x ADR; double distribution needs a profile. **The final day type is only known at the close**: causal inputs at 10:30 are IB width, open location versus prior value (F8) and early extension.
- *TF / decision:* 30m/session; fade versus follow. *Data:* price-only version yes; volume version delayed.
- *Subjectivity:* 1 for our proxies; the book's own reading is 2.
- *Failure modes:* labels are assigned after the fact; thresholds are ours.
- *Evidence:* practitioner claim (Dalton, Jones and Dalton, 1990; the book was not read; a secondary page was).

**R2. Wyckoff phases and events**
- *Plain English:* Markets alternate between trading ranges (accumulation or distribution) and trends. Inside a range, named events mark supply drying up: selling climax (SC), automatic rally (AR), secondary test (ST), a "spring" (a dip below the range that closes back inside), sign of strength (SOS), last point of support (LPS); five phases A to E (verified, [S56]).
- *Exact definition:* spring = low < range low and close >= range low within the same or next bar (StockCharts' description: price "takes price below the low of the TR and then reverses to close within the TR", [S56]); SOS = up bar with range > 1.5 x ATR and volume z > 1 after a spring; LPS = pullback on falling range and volume. Range detection (ADX low, flat MAs, bounded swings) is the hard part.
- *TF / decision:* 15m to weekly; turning points. *Data:* yes / delayed. *Subjectivity:* 2.
- *Failure modes:* phases are labelled with hindsight; range boundaries move.
- *Evidence:* practitioner claim. Wyckoff founded a school whose central offering was a course (verified, [S56]).

**R3. Al Brooks price action ("always in", bar counting, second entries)**
- *Plain English:* Reading every bar as a buyer-versus-seller contest: "always in long/short" (the side you would pick if forced to be in the market), counting pullback attempts (H1, H2, L1, L2), measured moves, trend versus range bars.
- *Exact definition:* not published in a form I could read: the "Always In" page is **members-only** (verified, [S67]); the description "the side a trader would choose if forced to be either long or short" and the H1/H2 counting come from a search snippet (UNVERIFIED). Algorithmic proxy (ours): always_in_long when close > EMA20, EMA20 rising, and >= 60% of the last 10 bars are up bars; H2 = the second break above the prior bar's high after a pullback.
- *TF / decision:* 5m mainly; timing and direction. *Data:* yes.
- *Subjectivity:* 2 for Brooks' own reading; 1 for the proxy.
- *Failure modes:* cannot be audited; almost everything is contextual.
- *Evidence:* practitioner claim. Brooks sells a course ("Sign Up Now - Only $399") and trading-room subscriptions (verified, [S67]).

**R4. Crabel: opening range breakout and narrow-range days**
- *Plain English:* The first five minutes set a range; a break of it tends to carry. Quiet days (NR4/NR7) precede busy days.
- *Exact definition:* see F3 and K5. Verified pieces: ORB uses the first five minutes; NR4/NR7 as above; profit taken at the first profitable close ([S42]).
- *TF / decision:* intraday/daily. *Data:* yes. *Subjectivity:* 0.
- *Failure modes:* see F3.
- *Evidence:* practitioner claim (Crabel 1990). Our backtest: no after-cost edge out of sample ([S84]).

**R5. Grimes: pullbacks, failure tests and structure**
- *Plain English:* Trade pullbacks in trending markets (buy near an "average" after a strong move), avoid exhaustion, wait for the best pullbacks rather than every pullback.
- *Exact definition (verified as described, [S66]):* setup = price touches bands that contain roughly 80% to 90% of price action after a strong move; entry near the average with a lower-timeframe break of the previous bar's high; stop about 2 to 4 ATR beyond entry (a rough guideline); first profit at 1R, then scale out. Distinguishing "true with-trend strength" from exhaustion is "perhaps the key technical skill of with-trend trading" (quote) and is a judgment.
- *TF / decision:* 2m to weekly; pullback timing. *Data:* yes.
- *Subjectivity:* 1 for the mechanical parts; 2 for "best pullback".
- *Failure modes:* the discretionary filter is where the claimed edge lives, and it cannot be tested until written down.
- *Evidence:* practitioner claim. The article plugs Grimes's research firm Waverly Advisors and a free trading course (verified, [S66]); commercial terms not read.

**R6. Bulkowski: statistics on chart patterns**
- *Plain English:* Reference statistics for about 63 to 76 chart and event patterns.
- *Exact definition:* see the limits in section I; and distribution days in O4.
- *Evidence:* practitioner claim by a seller of books; the author himself warns his statistics are best-case, end-of-day, hand-identified ([S64]).

**R7. ICT / "smart money concepts" (fair value gaps, order blocks, liquidity sweeps, kill zones)**
- *Plain English:* A vocabulary from online mentors: price leaves "imbalances" it later revisits (fair value gaps), "institutional" candles mark zones (order blocks), stops cluster above highs and below lows (liquidity) and get "swept", and certain clock windows matter (kill zones).
- *Exact definition (an open-source implementation, verified as described, [S72]):* fair value gap: bullish when the previous bar's high is below the next bar's low around a bullish middle bar (a three-bar gap); order block: computed from swings and volume; liquidity: several swing highs (or lows) within `range_percent` (default 1%) of each other, "swept" when a later candle trades through them; sessions: clock windows for London and New York.
- *TF / decision:* 1m to 1h; entry timing at zones. *Data:* yes.
- *Subjectivity:* 1 for the library; 2 for the courses' version.
- *Failure modes:* **the library's swing function uses candles after the current one**, so BOS, order blocks and liquidity outputs at bar t contain future information (verified, [S72]); zones proliferate, so one always sits near price; promoted mostly by mentorship sellers (general knowledge, not verified from a specific page).
- *Evidence:* none read. Treat as a story until precisely defined and tested. Every variant adds to N_trials (MT-G7).

---

### S. Event and calendar context

**S1. Economic calendar (FOMC, CPI, jobs, GDP, PCE, and so on)**
- *Plain English:* Scheduled news that moves the whole market at a known second. Traders avoid or adjust around it.
- *Exact definition:* a table of (datetime ET, event, impact class) built from official calendars before the day. Verified: FOMC 2026 meetings 27-28 Jan, 17-18 Mar, 28-29 Apr, 16-17 Jun, 28-29 Jul, 15-16 Sep, 27-28 Oct, 8-9 Dec ([S20]; the Fed marks the March, June, September and December meetings as associated with a Summary of Economic Projections); BLS CPI release time 08:30 ET, next release for September data on 14 Oct 2026 ([S21]). Features: event class today, minutes to the next event, minutes since the last one.
- *TF / decision:* daily/intraday; **risk gate** (block or reduce). *Data:* yes (official pages, free). The repo already keeps `events_2026.json` for 29 Sep to 31 Dec 2026 ([S83]).
- *Subjectivity:* 0 (impact classes: 1).
- *Failure modes:* unscheduled events (geopolitics, speeches) are not in a calendar; dates can move.
- *Evidence:* practitioner claim; the market-moving power of announcements is documented elsewhere (colleague).

**S2. Earnings of index heavyweights**
- *Plain English:* SPY and QQQ contain a few companies that dominate the index; their earnings move the index next morning.
- *Exact definition:* flag if any of the top-10 index weights reports after yesterday's close or before today's open. *Data:* **no** (not on Alpaca; company investor-relations pages). *Subjectivity:* 0.
- *Failure modes:* confirmed versus estimated dates; weights change.
- *Evidence:* practitioner claim.

**S3. Expiration, rebalance and session-length calendar**
- *Plain English:* Days with unusual flows: monthly option expiration, quarterly "triple witching", index rebalances, month-end, half-days.
- *Exact definition:* monthly opex = third Friday (standard SPX options are deemed to expire at the 9:30 open on the third Friday, or the day before if a holiday; weekly SPXW options expire at the 4:00 p.m. close, typically every other Friday, verified, [S14]); quarterly = March, June, September, December (standard practice, not verified); half-days from Alpaca's market calendar API ([S8]). VIX derivatives settle on a special opening quotation on their settlement days (verified, [S14]); the weekday of VIX expiry and the index-rebalance dates are UNVERIFIED.
- *TF / decision:* daily; volume/volatility context, risk gate. *Data:* yes (calendar).
- *Subjectivity:* 0.
- *Failure modes:* holiday shifts; rules change (for example index reconstitution schedules).
- *Evidence:* practitioner claim.

**S4. Time of day (the intraday "U-shape") and day of week**
- *Plain English:* The first and last half hours are the busiest; midday is quiet.
- *Exact definition:* session_phase buckets (F-series in the feature file) and RVOL time-of-day (E2). StockCharts states volume "can be much higher at the beginning or end of the trading day" (verified, [S36]).
- *TF / decision:* intraday; setup filtering. *Data:* yes. *Subjectivity:* 0.
- *Failure modes:* buckets are arbitrary; day-of-week effects are easily data-mined (the 2024 SPY paper reports a day-of-week analysis; I did not see the result, [S78]).
- *Evidence:* practitioner claim.


---

## Appendix B. Top-down checklists: how the charts are combined, and which one has the final say

**How a many-chart screen is usually arranged** (common practice; described from general knowledge, not from a verified source): a daily chart with the 20/50/200 averages and yesterday's levels; a 60-minute or 15-minute chart with VWAP and anchored VWAPs; a 5-minute execution chart; a 1-minute chart or the tape; an index or futures panel with internals (TICK/ADD/VOLD) and the VIX; a sector or leaders panel; a news/calendar pane; sometimes an options-levels pane. The panes are not averaged. They are a **decision tree**: each pane answers one question, and a fixed order says which answer wins when they disagree.

**Which timeframe answers which question** (common practice; consistent with the Grimes and Elder descriptions, but no single verified source):

| Timeframe | Question it answers | Typical tools |
|---|---|---|
| Monthly, weekly | What is the big trend, where are the major shelves? | 10/30-week averages, prior week/month high-low, 52-week extremes, swing structure |
| Daily | Trend, yesterday's structure, how big is a normal day, what is the plan? | 20/50/200 averages, ATR, PDH/PDL/PDC, gaps, NR7, RSI, volume |
| 4-hour | Swing structure of the week (a crypto and forex habit; awkward for a 6.5-hour stock session) | Swing highs/lows, channels |
| 1-hour | Trend of the day and week, intraday support and resistance | EMAs, swing structure, anchored VWAP |
| 15-minute | Which setup is forming; where is the opening range | Flags, pullbacks, VWAP, opening-range edges |
| 5-minute | The trigger and management chart | EMA 9/20, VWAP, bar patterns, squeeze |
| 1-minute | Exact entry and stop placement | Prior-bar high/low, VWAP reclaim, tape or delta |

**Order of authority (both checklists):**
1. Risk rules and the news calendar (a hard veto; in our bot this is code).
2. The higher-timeframe trend and regime (can veto a *direction*, never creates a trade).
3. The setup timeframe (decides whether a valid setup exists).
4. The trigger timeframe (decides *when*; never overrides 1 to 3).
5. If the timeframes disagree and the higher one has no clear view: **stand aside**.

### B.1 One-minute (day) trader

| Step | When | Charts and questions | Output |
|---|---|---|---|
| 0 | Before the session (code) | Event class today, half-day, halts, spread and data health, daily loss so far (F01 to F05, F56) | GO / REDUCED / NO-TRADE. **Final veto** |
| 1 | Evening or pre-open | Weekly and daily: trend state, distance to the 20/50/200 averages, ATR, last week's range (F06 to F08, F14, F30, F39) | Allowed direction: long-only / short-only / both / none |
| 2 | Pre-open, 08:00 to 09:29 | Futures or pre-market change, gap size in ATR, pre-market high/low, VIX change, big-company earnings (F26, F28, F52 to F55, F04) | Gap scenario: continuation, fill attempt, or unclear |
| 3 | Map | List levels sorted by distance in ATR: PDH/PDL/PDC, pre-market extremes, weekly extremes, VWAP/AVWAP, prior value area, round numbers, pivots (F25, F28 to F33, F19) | A short list of decision prices |
| 4 | 09:30 to 10:00 | Opening range 5/15/30, time-of-day RVOL, open location versus prior value, first breadth and sector readings (F29, F20, F21, F33, F46, F50) | Hypothesis: trend day or rotation day |
| 5 | 10:00 to 10:30 | First-hour balance forming, VWAP side and crosses, internals, sector leadership (F45, F16 to F18, F46 to F51) | Day-type call at 10:30 (initial balance closed) |
| 6 | 10:30 to 15:30, 5m chart | If trend: pullback to VWAP or the 20 EMA that holds, or a range break on RVOL above normal. If rotation: fade the range edges at the bands or IB edges, avoid breakouts. If event pending: wait (F09 to F13, F34 to F37, F41, F42) | A candidate setup with a level and a direction |
| 7 | Trigger, 1m chart | Close beyond the previous bar's high or low, VWAP reclaim, optional tape or delta confirmation (F16, F24, F56) | Exact entry price |
| 8 | Risk | Stop beyond structure or 2 to 4 ATR (Grimes' rough starting guideline, [S66]), fixed size, target at the next level, skip if target distance is less than a cost multiple (F25, F39) | Order plan with stop and target set before entry |
| 9 | Management | First profit at 1R then scale (Grimes), trail behind 5m structure or the 20 EMA, time exit, exit if internals or VWAP side flip | Exit |
| 10 | Close and review | Last-30-minute behaviour, flatten by rule, journal every taken **and skipped** trade | Journal row |

*Which chart has the final say:* the calendar and risk rules; then the daily trend (direction veto); then the 5-minute chart (is there a setup); the 1-minute chart only times the entry.

*For our bot:* steps 0 to 5 are computed as features and used only as gates. Steps 6 to 9 correspond to whichever setup is registered (today ORB5, LAST30 momentum and NOISE_MOM in the exploratory lane); a new pullback-style setup would have to be registered and counted in N_trials first. The steps that need human judgment (the "best pullback", exhaustion versus strength, tape feel) cannot be coded (Appendix C); the language model may veto but never add.

### B.2 Swing / position trader (days to weeks; for us: SPY, QQQ, sector ETFs)

| Step | Charts and questions | Output |
|---|---|---|
| 0 | Portfolio rules: risk per trade, total exposure, events in the holding window (FOMC, CPI, earnings) | Allowed risk |
| 1 | **Market regime** (monthly, weekly, daily index): trend versus 10/30-week and 50/200-day averages, breadth (percent above 50/200-day averages, A/D line), VIX level and term structure, credit spreads, yields, dollar (F06, F08, F52, F53, F54). IBD-style distribution-day counts are popular but failed the one independent test read ([S65]) | Risk-on / neutral / risk-off and an exposure cap |
| 2 | **Leadership:** relative-strength lines against SPY, sector ETF trends, relative rotation quadrants (F50, F51) | Which sectors or themes to favour |
| 3 | **Candidate structure** on the daily chart: stage or trend template, prior base and its tightness (NR days, squeeze), volume dry-up then expansion (F43, F42, F20) | Watch-list of levels |
| 4 | **Entry plan** on the daily chart: break of the range on above-normal volume, or a pullback to a rising 10/20-day average that holds, or a gap that holds. The buy price and stop are set before the day | Planned entry and stop |
| 5 | **Risk:** stop by ATR or structure; size from the risk budget; check event proximity and correlation with existing positions (F39, F03) | Position size |
| 6 | **Execution** on 15m/5m charts for timing only; the daily decision is not reversed by an intraday wiggle | Entry |
| 7 | **Management:** trail below the 10/20-day average or the last swing low, partial profits at multiples of risk, exit on regime flip or loss of relative strength, time stop | Exit |
| 8 | Weekly review and journal (including trades skipped) | Journal |

*Which chart has the final say:* market regime and the weekly/daily structure. Intraday charts can delay an entry but cannot reverse a daily decision.

---

## Appendix C. What humans do that is hard to code (and how to make each one testable)

| Human skill | Why it is hard to code | How to make it testable |
|---|---|---|
| Choosing *the* trendline, channel, Fibonacci swing or pattern | Many equally valid lines; chosen with hindsight; two people draw different ones | Rule-based swings with a confirmation lag (F12); have the cousin mark his lines *live* in a journal before the outcome |
| "Find the best pullback, not every pullback" (Grimes) | The quality filter is the strategy, and it is a judgment ([S66]) | Log all candidate pullbacks with features; log which he took and skipped; compare skipped versus taken |
| Telling exhaustion from true strength (Grimes calls it "perhaps the key technical skill of with-trend trading", [S66]) | Depends on context and feel | Proxies F22, F40; record his calls and score them later |
| "Always in" direction and bar-by-bar reading (Brooks) | Rules are taught in paid material and depend on the whole picture ([S67]) | Coded proxies (R3); record his reads with timestamps |
| Reading the tape (speed, size, absorption) | Needs tick-level data, and pattern-finding in noise is easy | Formal features (F24, F56) first; treat "feel" as untestable |
| Reading the order book (spoofing, real versus fake liquidity) | Quotes are often not real ([S69]); no depth data for US stocks here | Not attempted with our data |
| Recognising the day type early | The label is only certain at the close; judged by shape | Causal proxies (F45, F33); score the 10:30 call against the finish |
| Deciding which indicators matter *today* | Attention shifts with the regime; not written down | Ask which pane he looks at first each morning; journal it |
| Skipping trades ("it doesn't feel right") | The refusal is invisible in trade logs | Skip log with reasons; test whether skipped setups did worse |
| Discretionary sizing, adding and cutting | Sized by confidence and feel | Fixed-size rules in the bot; record his sizes to see if they help |
| Judging news, Fed speech, geopolitics, "priced in" | Requires understanding language and context; MT-G24 forbids feeding news to trades | LLM may veto around flagged events; calendar for scheduled ones |
| Spotting regime change (for example a market driven by headlines) | Slow, unlabelled shifts | Volatility and correlation-shift features; retire-on-drift rules (MT-G12/G13) |
| Multi-chart "gestalt" (index, sectors, VIX, internals disagreeing) | A holistic impression, not a formula | Turn each divergence into a number (F46 to F55) and test the combinations sparingly |
| Knowing which levels other traders are watching | Reflexive and unobservable | Test whether real levels beat fake ones (T4) |
| Adapting plans mid-day | Contingent rules that change during the session | Write the branches (if-then) as a decision tree |
| Emotional control and stopping for the day | A bot does this better than people (repo: MT-1 to MT-6) | Already handled by guardrails |

**A general point.** Skills that need hindsight to define (pattern labels, day types, "significant lows") look excellent on a finished chart and cannot be checked without a rule that works in real time. The route to evidence is a decision journal made *before* outcomes are known, kept for at least 40 sessions.

---

## Appendix D. The feature file `R1_features.json`, and look-ahead rules

**What it is.** A JSON list of 59 objects with the keys `id`, `name`, `group`, `definition`, `inputs`, `timeframes`, `needs`, `available_free` (`yes` | `delayed` | `no`), `subjectivity` (`0` | `1` | `2`) and `lookahead_risks`. Each `definition` ends with the catalog item it implements, for example `[catalog D1]`.

**Counts (computed from the file):**

| Group | Features |
|---|---|
| calendar_time | 5 |
| trend_mtf | 10 |
| vwap | 4 |
| volume | 5 |
| levels | 9 |
| candles_momentum | 5 |
| volatility_range | 7 |
| breadth_internals | 4 |
| sector_relative_strength | 2 |
| vol_complex_cross_asset | 4 |
| options_flow | 4 |
| **Total** | **59** |

| `available_free` | Meaning | Count |
|---|---|---|
| `yes` | Live on the free plan (IEX real time, or calendar data) and rebuildable from free history | 38 |
| `delayed` | Needs SIP data (free only when 15 minutes old), or is volume-based so live IEX is not comparable | 16 |
| `no` | Not on Alpaca's free plan (futures, VIX, Cboe statistics, earnings calendar) | 5 |

| `subjectivity` | Meaning | Count |
|---|---|---|
| 0 | Fully codeable | 38 |
| 1 | Codeable with judgment calls (thresholds, anchors, universes) | 20 |
| 2 | Essentially discretionary | 1 |

The one subjectivity-2 feature is the dealer-gamma proxy (F58): its sign convention *is* the model. Discretionary items (tape feel, hand-drawn lines, Brooks' reading) are deliberately **not** in the file because they cannot be computed.

**Look-ahead rules that apply to every feature** (rules 1, 3, 4, 5 and 6 rest on verified facts about Alpaca's data; the others are standard practice and reasoning):

1. **Bars are stamped at their start.** At decision time t use only bars whose stamp is at least one minute before t ([S1]).
2. **Higher-timeframe bars are closed buckets only.** Build 5m/15m/60m from 1-minute bars with start-labelled buckets and drop the forming bucket. Resampling with end-labelled windows leaks the future.
3. **Daily features are as of the prior session.** Alpaca daily bars ignore extended-hours prices and treat odd lots differently from minute bars; take all levels from one source ([S1]).
4. **A minute with no eligible trade has no bar.** Do not forward-fill volume; treat empties the same way in the baseline and live ([S1]).
5. **Volume baselines exclude today and use one feed.** IEX live is about 2.5% of SIP volume ([S3]); MT-G35 forbids mixing.
6. **Options open interest is a daily number** with an `open_interest_date`; use the value dated before today ([S6]). Same-day contracts have no Greeks ([S1]).
7. **Swing points, ZigZag legs and pattern vertices are known only after their confirmation bars.** Store `confirmed_at`. Libraries whose swing function looks N candles forward leak the future into BOS, order-block and liquidity outputs ([S72]).
8. **Smoothers must be one-sided.** Kernel or centred filters (as in pattern-recognition papers) use points after t; use trailing windows.
9. **Volume profiles:** yesterday's profile is complete; today's developing profile may only use bars up to t.
10. **Calendars:** use only dates known before the session; unknown coverage blocks. FOMC and CPI dates in this research are verified ([S20], [S21]); other releases and earnings need checking.
11. **Universe:** use point-in-time index constituents for breadth features; today's list creates survivorship bias.
12. **Prices:** use raw prices for round-number features; dividend adjustment factors depend on later events.
13. **Daily VIX:** VIX is disseminated until 16:15 ET ([S14]), after the equity close, and reaches FRED later; only the prior day's value is usable intraday.
14. **Opening auction price** is not the first 1-minute bar's open. Alpaca serves official auction prices through a SIP-only historical endpoint ([S9]); a live IEX-only bot has to approximate and flag it.
15. **Time zones:** store UTC, decide in Eastern time from the exchange calendar (daylight-saving changes and half-days).

