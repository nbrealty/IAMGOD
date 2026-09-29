# R2. Which chart-reading techniques have real evidence, at any horizon?

> **Read `00 Fact-check corrections (read first).md` alongside this file.** Written on 28 Sept 2026 by a research agent; four independent fact-checkers then reviewed its main claims, and where they differ from the text below, the corrections file wins. Scripts behind the researcher's own calculations are in `scripts/` (paths such as `work/`, `r5/` or `research/` in the text point there; they expect data files downloaded separately). Terms like verified / UNVERIFIED are the researcher's own tags.


*Research note for the minute-trading bot project. Written 28-29 Sept 2026. Research only: nothing in the repo was changed, no orders, no broker calls. Every claim is marked **verified** (I read it in the paper's full text, its abstract on a publisher or repository page, or an official page) or **UNVERIFIED** (seen only in a search snippet, a press story or from memory). Where I only read an abstract, I say so. The web-search budget for this session ran out (200 of 200) before I finished, so some planned checks are missing. They are listed in section 5.*

Where a horizon, market or sample is not in the abstract I read, the table says "not read" or "(from memory)". Where I mention a person's or firm's commercial interest without having seen it on a page I read, it is marked UNVERIFIED.

**How to read the grades.** "Strength" means: how strong is the evidence that this technique gives a tradeable, after-cost edge that survived out-of-sample?
- **Strong** = several independent, out-of-sample, after-cost, post-publication confirmations. (Nothing here earns this at our horizon.)
- **Mixed** = a real effect is documented, but it is sample-specific, has faded, is cost-sensitive, or is contested.
- **Weak** = a few positive papers that snooping or later tests undo, or negative tests outnumber positive.
- **None** = no credible test found, or the tests are negative.
- **Not testable** = too subjective to turn into exact code.

---

## 1. Plain-English summary

1. **Bottom line: I found no chart-reading technique with strong, after-cost, out-of-sample proof at the one-minute level on SPY and QQQ.** That matches our own two-year backtest.
2. The best-supported ideas are slow and unglamorous: trends over months, the fact that calm and stormy periods last (volatility), and controlling risk with position size and stops. They are not "reading patterns".
3. The famous 1992 moving-average study (Brock, Lakonishok, LeBaron) still looked good after a data-snooping correction on its own era. But the next ten years (1987-96) were a flop (Sullivan, Timmermann, White 1999). Later work finds the profits vanish once small costs are charged (Bajgrowicz and Scaillet 2012; Rink 2023, whose sample ends May 2016).
4. Intraday: the big US intraday test I found, of 7,846 popular rules, found **none** profitable once you correct for having tried so many (Marshall, Cahan, Cahan 2008).
5. Chart patterns (head-and-shoulders, double tops, triangles): a careful computer test found some information (Lo, Mamaysky, Wang 2000), but the authors said it does not prove profit. Follow-ups found little or no stand-alone profit. Candlesticks, Fibonacci, Elliott wave and hand-drawn trendlines have no credible after-cost evidence.
6. Support, resistance and round numbers are real in one sense: orders pile up there (Osler 2000, 2003), and people who cross the spread near round numbers lose about $1 billion a year (Bhattacharya, Holden, Jacobsen 2012). Use that to place or avoid orders, not to predict.
7. Volume adds little to patterns (Lo et al.). For "multi-timeframe" I found **no direct test**; the nearest evidence is for forecasting volatility and ranking stocks, not for entries.
8. Machine learning on chart images (Jiang, Kelly, Xiu 2023) works on 1993-2019 US stocks but turns over about 175% of its portfolio a month (200% would mean replacing everything), and its value-weighted Sharpe (about 0.5) is close to plain momentum (0.36). I found no independent replication. LSTM profits vanished after 2010 (Fischer and Krauss 2018). AI vision models ignore injected candlestick evidence and just extrapolate the trend (Wang 2026 preprint).
9. **Data snooping (own calculation):** with 2 years of data, about 8 independent tries give a "Sharpe 1.0" by luck alone; about 240 tries give "Sharpe 2.0". Our pass bar (0.05/28) is right, but one year of test data has almost no power to pass it, even for a real edge.
10. **Advice:** teach the machine costs, volatility, time-of-day and risk rules, not named patterns. Test a few pre-written ideas on 10 years of data (2016-2026) and count every variant.

---

## 2. Findings table

Columns: item | what it is | evidence and strength | horizon and market | after costs? | source | verified?
Links marked "IDEAS" or "EconPapers" are repository pages that carry the publisher's abstract.

### 2A. Moving-average and other "technical trading rules"

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Brock, Lakonishok, LeBaron 1992 | Buy when price is above a moving average or breaks out of a recent range; sell otherwise | **Mixed.** Said to give "strong support" to the rules; buy signals earned more than sell signals; not explained by four standard null models. Later work shows it faded (rows below) | Daily; Dow Jones Industrials 1897-1986 | Not in the abstract. (STW later computed a break-even cost of 0.27% per trade for its best rule) | [IDEAS](https://ideas.repec.org/a/bla/jfinan/v47y1992i5p1731-64.html) | verified (abstract) |
| Sullivan, Timmermann, White 1999 (STW) | Re-tests BLL against a universe of 7,846 rules over 100 years, correcting for "data snooping" (trying many rules and reporting the winner). Rule families: filters, moving averages, support/resistance, channel breakouts, on-balance volume | **Weak after 1986.** Best rule earned 17.17% a year over 1897-1996 with 6,310 trades (63 a year) and stayed significant after snooping (p < 0.002). But in the next 10 years (1987-96) "the best-performing trading rule is not even statistically significant"; on S&P 500 futures (1984-96) "no evidence that any trading rule outperforms". A rule with p = 0.04 alone had p = 0.90 after snooping. The "best" rule changed in almost every sub-period | Daily; DJIA 1897-1996; S&P 500 futures 1984-96 | Partly: break-even cost 0.27% per trade for the best rule; the futures test (cheap to trade) still shows nothing | [PDF](https://www.kevinsheppard.com/files/teaching/mfe/advanced-econometrics/Sullivan_Timmermann_White.pdf) | verified (full text) |
| Marshall, Cahan, Cahan 2008 | Intraday technical rules on US equities | **None.** "None of the 7846 popular technical trading rules we test are profitable after data snooping bias is taken into account. There is no evidence that the market is inefficient over this time horizon." Notes that market participants use technical analysis more the shorter the horizon. Same rule count as STW's universe; I did not confirm it is the same set | Intraday; US equity market (sample details not read) | Not stated in the abstract (the failure is reported without reference to costs) | [EconPapers](https://econpapers.repec.org/RePEc:eee:empfin:v:15:y:2008:i:2:p:199-210) | verified (abstract). Sample details UNVERIFIED |
| Bajgrowicz and Scaillet 2012 | Re-test with the false-discovery-rate method; can you pick winners in advance? | **None / Weak.** Even in-sample, performance is "completely offset by the introduction of low transaction costs"; persistence tests show an investor could not have picked the future best rules in advance | Daily; DJIA 1897-2011 | Yes (costs kill it) | [EconPapers](https://econpapers.repec.org/article/eeejfinec/v_3a106_3ay_3a2012_3ai_3a3_3ap_3a473-491.htm) | verified (abstract) |
| Park and Irwin 2007 | Survey of the field | **Mixed.** Of 95 "modern" studies, 56 positive, 20 negative, 19 mixed; profits in many markets "at least until the early 1990s". Most studies have problems: data snooping, choosing rules after the fact, hard-to-measure risk and costs | Many markets; to early 1990s | Varies; costs are a named weakness | [Illinois](https://experts.illinois.edu/en/publications/what-do-we-know-about-the-profitability-of-technical-analysis/) | verified (abstract) |
| Rink 2023 | 6,406 rules on 41 stock indices (23 developed, 18 emerging), up to 66 years, superior-predictive-ability test | **Weak / None in recent data.** In-sample outperformance in most markets, but predictability "diminishes drastically over time" and "markets turn unpredictable in the last years of our sample". Recently-best rules do significantly worse than buy-and-hold afterwards. Only 5 of 23 developed and 4 of 18 emerging markets have significant rules at costs of 20 bps per trade or more. Rules that trade less are less cost-sensitive | Daily indices; sample ends May 2016 (S&P 500 from Jan 1950) | Yes: "very sensitive" to moderate costs | [IDEAS](https://ideas.repec.org/a/kap/fmktpm/v37y2023i4d10.1007_s11408-023-00433-2.html), [PDF](https://www.econstor.eu/bitstream/10419/312389/1/s11408-023-00433-2.pdf) | verified (abstract + full text) |
| Hsu and Kuan 2005 | Snooping-corrected tests on four US indices | **Mixed.** Profitable rules exist in "young" markets (Nasdaq Composite, Russell 2000) but not in the DJIA or S&P 500 | Daily; US indices | Yes: best strategies beat buy-and-hold after costs in most periods for young markets | [IDEAS](https://ideas.repec.org/a/oup/jfinec/v3y2005i4p606-628.html) | verified (abstract) |
| Hsu, Taylor, Wang 2016 | Over 21,000 rules on 30 currencies, stepwise snooping control | **Mixed (FX, not stocks).** "Substantial predictability and excess profitability" with out-of-sample cross-validation; varies by period and region; authors link it to "market immaturity" | Daily; 30 currencies over 45 years | Not stated in abstract | [IDEAS](https://ideas.repec.org/a/eee/inecon/v102y2016icp188-208.html) | verified (abstract) |
| Sermpinis et al. (arXiv, 2019 revision) | Over 21,000 rules, 12 MSCI markets, new false-discovery method | **Mixed.** "Technical analysis still has short-term value" in advanced, emerging and frontier markets; frequent rebalancing matters. Preprint | Daily; MSCI indices 2004-2015 | Not stated in abstract | [arXiv](https://arxiv.org/abs/1811.06766) | verified (abstract) |
| Schulmeister 2009 | 2,580 technical models on S&P 500 spot and futures | **Weak / fading.** Daily-data profits declined since 1960 and were unprofitable since the early 1990s. With 30-minute data the models averaged 7.2% a year gross over 1983-2007, but did worse in 2001-2007 | 30-minute and daily; S&P 500 | **No** (gross returns) | [IDEAS](https://ideas.repec.org/a/eee/revfin/v18y2009i4p190-201.html) | verified (abstract) |
| Neely, Rapach, Tu, Zhou 2014 | Technical indicators used to forecast the monthly US equity risk premium | **Mixed.** Indicators have significant in- and out-of-sample predictive power, "matching or exceeding" macro variables; they help most near business-cycle peaks | US stock market; monthly horizon (from memory, not in the abstract) | Forecast accuracy, not a cost-tested trading rule | [IDEAS](https://ideas.repec.org/a/inm/ormnsc/v60y2014i7p1772-1791.html) | verified (abstract) |
| Zhu and Zhou 2009 | Moving-average rule as an aid to portfolio allocation | **Weak-Mixed (theory).** The rule adds value when returns are predictable and the investor is unsure of the model; robust to model uncertainty | Allocation model for stocks (sample not read) | No | [IDEAS](https://ideas.repec.org/a/eee/jfinec/v92y2009i3p519-544.html) | verified (abstract) |
| Han, Yang, Zhou 2013 | Moving-average timing on portfolios sorted by volatility | **Mixed.** "Substantially outperform" buy-and-hold, most for high-volatility portfolios (and other high-information-uncertainty sorts); not explained by market timing, sentiment, default or liquidity risk | US stock portfolios (sample not read) | Not stated in abstract | [IDEAS](https://ideas.repec.org/a/cup/jfinqa/v48y2013i05p1433-1461_00.html) | verified (abstract) |
| Detzel, Liu, Strauss, Zhou, Zhu 2021 | Price-to-moving-average ratio as a predictor | **Mixed.** Forecasts daily Bitcoin returns in and out of sample; similar for small-cap, young, low-coverage stocks and Nasdaq stocks in the dot-com era. Not SPY/QQQ-like assets | Daily; Bitcoin and hard-to-value stocks | Not stated in abstract | [DOI](https://doi.org/10.1111/fima.12310) | verified (abstract via Crossref record) |
| Chong and Ng 2008; Chong, Ng, Liew 2014 | MACD and RSI rules on stock indices | **Weak.** UK FT30 (monthly data, 1935-94): rules beat buy-and-hold "in most cases". Five OECD indices (daily, Jan 1976-Dec 2002): a handful of rule variants worked in Italy and Canada (net of a 1% round-trip cost) and RSI(14) in the DJIA; none beat buy-and-hold in Japan. Nine rule variants (3 MACD, 6 RSI, my count from the text) across five markets is 45 combinations, and I found no snooping correction | Monthly and daily; UK, Italy, Canada, US, Japan, Germany | Yes, 1% round trip, for the best variants only | [EconPapers](https://econpapers.repec.org/RePEc:taf:apeclt:v:15:y:2008:i:14:p:1111-1114), [PDF](https://mpra.ub.uni-muenchen.de/54149/1/MPRA_paper_54149.pdf) | verified (abstract; full text of 2014 paper) |
| "Volume-price-adjusted MACD" (Lin et al., 2026 preprint) | A new MACD variant with a fitted sensitivity parameter | **Weak.** Says it beats a plain-MACD baseline out-of-sample (2023 to Feb 2026) on three US indices. The text I searched has no buy-and-hold comparison over a strong bull market, and the parameter is fitted per index | Daily; S&P 500, Nasdaq-100, DJIA | Yes, 8 bps round trip | [arXiv](https://arxiv.org/abs/2604.26063) | verified (abstract + text search) |

### 2B. Chart patterns (head-and-shoulders, double tops, flags, triangles)

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Lo, Mamaysky, Wang 2000 | A computer (kernel regression) finds 10 patterns and checks whether returns after them differ from normal returns | **Mixed.** "Several technical indicators do provide incremental information and may have some practical value". Stronger for Nasdaq stocks. The authors add that this "does not necessarily imply" excess trading profits. Volume trend gave "little incremental information" | Daily; NYSE/AMEX and Nasdaq stocks 1962-1996 (random samples of 50 stocks per 5-year sub-period) | No trading test | [NBER](https://www.nber.org/papers/w7613), [MIT PDF](https://web.mit.edu/wangj/www/pap/LoMamayskyWang00.pdf) | verified (abstract + full text) |
| Savin, Weller, Zvingelis 2007 | Head-and-shoulders using the Lo et al. algorithm plus filters | **Weak-Mixed.** "Little or no support for the profitability of a stand-alone trading strategy", but the pattern predicts excess returns; a strategy conditioned on it gained about 5-7% a year risk-adjusted (as summarised on the publisher page) | Daily; S&P 500 and Russell 2000, 1990-1999 | Stand-alone: no profit | [OUP](https://academic.oup.com/jfec/article-abstract/5/2/243/785044) | verified (abstract) |
| Dawson and Steeley 2003 | Replication of Lo et al. in the UK | **Weak.** "UK stock returns are less influenced by technical patterns than was the case for US stock returns" | Daily; FTSE 100 and 250, 1986-2001 | No trading test | [DOI](https://doi.org/10.1111/1468-5957.00492) | verified (abstract via Crossref record) |
| Chang and Osler 1999 | Head-and-shoulders rule on currencies | **Weak-Mixed.** Profitable for the mark and the yen but not for four other currencies (as described in Osler 2000). The paper's own abstract, seen in a search summary, says the rule is profitable but "dominated by simpler trading rules" | Daily; dollar exchange rates 1973-1994 | Not confirmed | [DOI](https://doi.org/10.1111/1468-0297.00466) | Osler's description verified (full text). Own abstract UNVERIFIED (search snippet) |
| Friesen, Weller, Dunham 2009 | A theory of why patterns might exist: traders bias how they read new information ("confirmation bias") | **Theory + one test.** Predicts patterns like head-and-shoulders and double tops, and positive autocorrelation of price jumps; they report "statistically and economically significant" autocorrelations | Individual US stocks | No | [IDEAS](https://ideas.repec.org/a/eee/jbfina/v33y2009i6p1089-1100.html) | verified (abstract) |
| Tsinaslanidis and Guijarro 2020 | Searches any past shape (dynamic time warping), not just named patterns | **Weak-Mixed.** On 560 NYSE stocks, "on average the proposed system dominates the market index in the mean-variance sense"; costs reduce profit; 92.5% of experiments profitable when limited to parameter values aligned with technical analysis. Controls for snooping and costs (sample period not read) | Daily; NYSE stocks | Yes, but profit reduced | [DOI](https://doi.org/10.1111/exsy.12596) | verified (abstract via Crossref record) |
| Bulkowski's statistics (Encyclopedia of Chart Patterns, thepatternsite.com) | Success rates and average moves for dozens of patterns, from his own data | **None as evidence (claims to test).** I found no independent peer-reviewed replication. His site sells the book and points readers to it; the head-and-shoulders page I read gives average declines of 19-25% by sub-type but no sample size, benchmark, cost or failure definition. Widely quoted "90%+ success" figures depend on what "success" means (UNVERIFIED, from secondary sources) | Daily; US stocks (his data) | Not addressed | [his page](https://www.thepatternsite.com/HSTExplained.html) | verified that the page lacks those details. Sample and rates UNVERIFIED |

### 2C. Candlestick patterns

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Marshall, Young, Rose 2006 | Japanese candlestick reversal patterns on US large caps | **None / Weak.** Reported: no value for Dow Jones stocks once compared with bootstrapped random prices | Daily; Dow Jones stocks, roughly 1992-2002 | Reported no excess return | [IDEAS](https://ideas.repec.org/a/eee/jbfina/v30y2006i8p2303-2323.html) | Bibliographic verified. Finding UNVERIFIED (search summary; abstract not accessible) |
| Duvinage, Mazza, Petitjean 2013 | Candlestick rules at the 5-minute interval on the 30 Dow stocks | **None.** About a third of rules beat buy-and-hold at the conservative Bonferroni level, before costs; "just a few" after costs; after snooping correction "no single candlestick rule beats the buy-and-hold strategy after transaction costs"; combined systems also fail | 5-minute; DJIA constituents | Yes | [IDEAS](https://ideas.repec.org/p/ajf/louvlr/2013001.html) | verified (abstract) |
| Tharavanij, Siraprapasiri, Rajchamaha 2017 | Candlestick reversal patterns, with and without stochastic/RSI/Money Flow filters | **None.** "Mean returns of most patterns are not statistically different from zero"; oscillator filters did not help | Daily; SET50 (Thailand) 2006-2016 | Not stated | [IDEAS](https://ideas.repec.org/a/sae/sagope/v7y2017i4p2158244017736799.html) | verified (abstract) |
| Lu, Shiu, Liu 2012; Lu and Shiu 2016 | Positive candlestick studies | **Weak.** Taiwan Top 50 fund stocks 2002-08: three bullish reversal patterns profitable (with bootstrap and out-of-sample checks). Dow 30, 1974-2009: predictive power rose "from 1992 onwards". Small, market-specific, costs not stated | Daily; Taiwan; Dow 30 | Not stated | [2012](https://ideas.repec.org/a/eee/revfin/v21y2012i2p63-68.html), [2016](https://ideas.repec.org/a/taf/applec/v48y2016i35p3345-3354.html) | verified (abstracts) |
| Wang 2026 (arXiv) | Tests whether AI vision models actually use candlestick evidence | **None for AI chart reading.** Across seven commercial and open vision-language models, coefficients on injected candlestick evidence are "zero or opposite to the rule-implied sign"; models load on past trend. Single-author preprint; explicitly makes no claim that candlesticks are profitable | Rendered charts (public price data and synthetic markets) | n/a | [arXiv](https://arxiv.org/abs/2606.17423) | verified (abstract + parts of text) |

### 2D. Volume-based rules

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Blume, Easley, O'Hara 1994 | Theory: volume carries information about the quality of information that price alone does not | **Theory only.** Traders who use volume and price sequences do better than those who ignore them (in the model) | Model | n/a | [IDEAS](https://ideas.repec.org/a/bla/jfinan/v49y1994i1p153-81.html) | verified (abstract) |
| Gervais, Kaniel, Mingelgrin 2001 | Stocks with unusually high volume over a day or week | **Mixed.** Such stocks "tend to appreciate" over the next month; not explained by return autocorrelation, announcements, risk or liquidity | Monthly; US stocks | Not stated | [IDEAS](https://ideas.repec.org/a/bla/jfinan/v56y2001i3p877-919.html) | verified (abstract) |
| Lee and Swaminathan 2000 | Past trading volume and momentum | **Mixed.** Volume predicts the size and duration of momentum; high-volume winners and losers reverse faster | Monthly to multi-year; US stocks | Not stated | [IDEAS](https://ideas.repec.org/a/bla/jfinan/v55y2000i5p2017-2069.html) | verified (abstract) |
| "Volume confirms the breakout" (retail rule) | Only act on a breakout if volume is high | **None found.** Lo et al. found the volume trend gave "little incremental information" for their patterns (one exception: increasing volume with broadening tops). STW's on-balance-volume rules were part of the snooped universe: an on-balance-volume rule was the best in-sample rule in 1939-86 and on S&P 500 futures 1984-96 (mean-return criterion), yet nothing held up out-of-sample | Daily; US stocks | No | see Lo et al. and STW above | verified (full text of both) |

### 2E. Support, resistance and round numbers

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Osler 2000 | Support and resistance levels published daily by six trading firms | **Mixed (as a statistical fact).** Trends stopped at the published levels more often than at 10,000 sets of arbitrary levels; the power lasted at least five business days for most firms; firms differed a lot; none judged which level was more likely to hold. No profit test | Intraday (one-minute indicative quotes); dollar vs mark, yen, pound, Jan 1996-Mar 1998 | Not tested | [NY Fed PDF](https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.pdf) | verified (full text) |
| Osler 2003 | Why: stop-loss and take-profit orders cluster | **Mixed.** Take-profit orders cluster strongly at round numbers (so trends reverse there); stop-loss orders cluster just beyond round numbers (so moves speed up after a break) | Intraday; currencies | Not tested | [IDEAS](https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html), [DOI](https://doi.org/10.1111/1540-6261.00588) | verified (abstract) |
| Kavajecz and Odders-White 2004 | Do technical support/resistance and moving averages reflect the limit order book? | **Mixed.** Support/resistance levels coincide with peaks in depth on the order book; the moving-average signal tells you where depth sits; technical rules are finding depth "already in place" | Equity limit order book (market and sample not read) | Not tested | [IDEAS](https://ideas.repec.org/a/oup/rfinst/v17y2004i4p1043-1071.html) | verified (abstract) |
| Bhattacharya, Holden, Jacobsen 2012 | Trading around round-number prices | **Mixed, useful for execution.** Over 100 million transactions: traders who demand liquidity buy one penny below and sell one penny above round numbers; the authors estimate their losses "approach $1 billion per year" | Tick data; US stocks | Shows cost to the people crossing the spread | [IDEAS](https://ideas.repec.org/a/inm/ormnsc/v58y2012i2p413-431.html) | verified (abstract) |
| Donaldson and Kim 1993 | Support/resistance at multiples of 100 in the Dow | **Mixed, dated.** Dow "restrained by support and resistance levels at multiples of 100", and after breaking one it moves more than expected; "does not necessarily suggest that the market is inefficient" | Daily; DJIA (period not read) | Not tested | [IDEAS](https://ideas.repec.org/a/cup/jfinqa/v28y1993i03p313-330_00.html) | verified (abstract) |
| Ni, Pearson, Poteshman 2005 | Stock prices clustering at option strikes on expiry days | **Relevant to SPY/QQQ (weekly and daily options), but not read.** | US stocks | n/a | [IDEAS](https://ideas.repec.org/a/eee/jfinec/v78y2005i1p49-87.html) | bibliographic only; finding UNVERIFIED (from memory) |

### 2F. Fibonacci, Elliott wave, Dow theory, trendlines

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Fibonacci retracements | Expect pullbacks of 38.2%, 50%, 61.8% of a prior move | **Weak / None.** Gurrib et al. 2022: the rule beat buy-and-hold for 6 of 10 energy stocks, but with tiny Sharpe ratios (best 0.139), a short sample, no explicit costs; crypto had too few signals. Tsinaslanidis et al. 2022 (automatic Fibonacci zones on three equity markets) reportedly find a positive link between zone width and bounce probability, which is what any wide zone would show (UNVERIFIED) | Daily; energy stocks Nov 2017-Jan 2020; three equity markets | No | [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8752186/), [DOI](https://doi.org/10.1016/j.eswa.2021.115893) | Gurrib verified (abstract + results). Tsinaslanidis UNVERIFIED (search summary) |
| Elliott wave | A market is said to move in a fixed count of five waves up and three down | **Not testable / None.** The counting is subjective. The only paper found (D'Angelo and Grimaldi 2017, a business-research journal) says EUR/USD 2009-2015 "could be forecasted with great accuracy", which reads as a wave count fitted to past data (my reading), with no costs or benchmark. Critics such as Mandelbrot and Aronson are cited in a secondary summary (UNVERIFIED) | Daily; EUR/USD 2009-15 | No | [IDEAS](https://ideas.repec.org/a/ibn/ibrjnl/v10y2017i6p1-18.html) | verified (abstract). Critics UNVERIFIED |
| Dow theory | Trend confirmed only when two Dow indexes agree; historical calls by W. P. Hamilton | **Weak, dated, hard to code.** Cowles (1934) found no skill; Brown, Goetzmann, Kumar 1998 re-read the same editorials and found "high Sharpe ratios and positive alphas" for 1902-1929, then used a neural net to imitate Hamilton out of sample. Based on an editor's judgement, not a rule | Daily; Dow indexes 1902-1929 | Not stated | [DOI](https://doi.org/10.1111/0022-1082.00054) | verified (abstract via Crossref record) |
| Trendlines and channels | Lines drawn through highs or lows | **None found / Not testable by eye.** I found no dedicated test. Algorithmic channel breakouts sit inside the snooped rule universes above (STW: the best channel-type rule changed from period to period, and the universe as a whole had no significant winner in 1987-96) | Daily | n/a | see STW | verified for the STW part; "no dedicated test found" is limited by my search budget |

### 2G. RSI, stochastics, Bollinger Bands

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| RSI and MACD stand-alone | Momentum oscillators | **Weak.** See Chong-Ng rows in 2A (old samples, several variants, best ones highlighted) and the 2026 preprint | Daily/monthly | Only for the best variants | see 2A | verified |
| Stochastic oscillator | Where the close sits in the recent range | **None found.** Tested only as a "filter" on candlesticks (Tharavanij 2017): no improvement | Daily; Thailand | Not stated | see 2C | verified (abstract) |
| Bollinger Bands | Bands two standard deviations around a moving average | **Weak.** Leung and Chong 2003: "Bollinger Bands do not outperform the Moving Average Envelopes" | Daily; sample not read | Not stated | [IDEAS](https://ideas.repec.org/a/taf/apeclt/v10y2003i6p339-341.html) | verified (abstract) |

### 2H. Multi-timeframe and multi-scale approaches

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Retail "top-down" or "triple screen" confirmation (trade the 5-minute signal only if the hourly and daily agree) | Require several timeframes to agree | **None found (no direct test).** I found no peer-reviewed test of this method. Each extra timeframe adds parameters, which raises the snooping bar | n/a | n/a | n/a | "none found" is limited by my search budget |
| Corsi 2009 (HAR-RV) | Forecast volatility from daily, weekly and monthly components | **Strong for volatility forecasting** (not direction): a simple additive cascade of volatility components over different horizons reproduces long memory and fat tails and shows "notably strong forecasting capabilities". (Daily, weekly and monthly components are the standard version; the abstract does not list them.) | Realised volatility (frequency not in the abstract) | n/a | [IDEAS](https://ideas.repec.org/a/oup/jfinec/v7y2009i2p174-196.html) | verified (abstract) |
| Han, Zhou, Zhu 2016 (trend factor) | Combines moving averages of many lengths (short, medium, long trends) to rank stocks | **Mixed.** "More than doubling" the Sharpe ratios of short-term reversal, momentum and long-term reversal factors; earned 0.75% a month in "the recent financial crisis" (as the abstract words it) while the market lost 2.03% | Stock cross-section (US, from memory); monthly factor returns | Not stated in abstract | [IDEAS](https://ideas.repec.org/a/eee/jfinec/v122y2016i2p352-375.html) | verified (abstract) |
| Jiang, Kelly, Xiu 2023 ("context independence") | Patterns learned on short windows work on longer windows, and US patterns work abroad | **Mixed.** Shows transfer across scales, not a rule for combining timeframes | Daily to monthly; US and international stocks | See 2K | see 2K | verified (abstract) |
| Lempérière et al. 2014 | Trend following over two centuries | **Mixed.** Long-term trends stable, "shorter-term trends have deteriorated" | Multi-decade; four asset classes | Not stated | [arXiv](https://arxiv.org/abs/1404.3274) | verified (abstract) |
| Pei et al. 2024 (multi-scale CNN on A-share charts) | Combines sequence and image features | **Weak.** Abstract quotes a 165% "total profit" and 61% prediction accuracy with no benchmark or cost shown; the authors warn that image models "are more prone to overfitting" | 5-day; China A-shares | Not shown | [arXiv](https://arxiv.org/abs/2410.19291) | verified (abstract) |

### 2I. Volatility filters and stop-losses

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Moreira and Muir 2017 | Take less risk when recent volatility is high | **Mixed.** "Large alphas" and higher factor Sharpe ratios | US equity factors and currency carry (horizon not read) | Not stated | [NBER](https://www.nber.org/papers/w22208) | verified (abstract) |
| Cederburg, O'Doherty, Wang, Yan 2020 | Same idea, tested as a real-time investor | **Weak-Mixed (a critique).** Across 103 strategies, volatility-managed portfolios "do not systematically outperform"; real-time versions typically earn lower returns and Sharpe ratios than the unmanaged ones | 103 equity strategies (horizon not read) | Not stated | [IDEAS](https://ideas.repec.org/a/eee/jfinec/v138y2020i1p95-117.html) | verified (abstract) |
| Barroso and Santa-Clara 2015 | Scale momentum by its own recent risk | **Mixed to strong for momentum risk.** Momentum risk is "highly variable over time and predictable"; managing it "virtually eliminates crashes and nearly doubles the Sharpe ratio" | Momentum factor (horizon and market not read) | Not stated | [IDEAS](https://ideas.repec.org/a/eee/jfinec/v116y2015i1p111-120.html) | verified (abstract) |
| Kaminski and Lo 2014 | Stop-loss rules | **Mixed.** "At longer sampling frequencies, certain stop-loss policies can increase expected return while substantially reducing volatility" (index futures). That stops hurt when prices are a random walk is from my memory of the paper, not the abstract | Daily futures; longer holding periods | Framework includes costs of stopping; not read | [IDEAS](https://ideas.repec.org/a/eee/finmar/v18y2014icp234-254.html) | verified (abstract). Random-walk point UNVERIFIED |

### 2J. 52-week high, momentum and trend following

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| George and Hwang 2004 | Buy stocks near their 52-week high | **Mixed.** "Nearness to the 52-week high dominates and improves upon" past returns for forecasting; returns "do not reverse in the long run" | US stocks (monthly portfolios, from memory) | Not stated | [DOI](https://doi.org/10.1111/j.1540-6261.2004.00695.x) | verified (abstract via Crossref record) |
| Li and Yu 2012 | Nearness of the Dow to its 52-week and historical highs | **Mixed.** Nearness to the 52-week high positively forecasts market returns; distance from the historical high negatively; consistent across G7 | Market-level forecasts; Dow and G7 (horizon not read) | Not stated | [IDEAS](https://ideas.repec.org/a/eee/jfinec/v104y2012i2p401-419.html) | verified (abstract) |
| Jegadeesh and Titman 1993 | Buy recent winners, sell recent losers (relative strength) | **Mixed.** Significant returns over 3-12 months; gains fade over the following two years. Turnover makes costs decisive (see next row) | Monthly; US stocks | Not in abstract | [IDEAS](https://ideas.repec.org/a/bla/jfinan/v48y1993i1p65-91.html) | verified (abstract) |
| Novy-Marx and Velikov 2016 | Which anomalies survive trading costs | **Key cost rule.** "Most anomalies with less than 50% turnover per month generate significant net spreads when designed to mitigate transaction costs; few with higher turnover do." Costs also "increase data-snooping concerns" | Monthly; US stocks | Yes | [IDEAS](https://ideas.repec.org/a/oup/rfinst/v29y2016i1p104-147..html) | verified (abstract) |
| Moskowitz, Ooi, Pedersen 2012 | Trend following ("time series momentum") in 58 futures and currencies | **Mixed, best of the class.** Persistence for 1-12 months, partly reversing later; diversified portfolio has "substantial abnormal returns" | Monthly; 58 instruments | Not stated | [IDEAS](https://ideas.repec.org/a/eee/jfinec/v104y2012i2p228-250.html) | verified (abstract) |
| Huang, Li, Wang, Zhou 2020 | Challenge to the above | **A critique.** Asset-by-asset regressions "reveal little evidence" of time-series momentum; the pooled t-statistic is not reliable; the strategy is profitable but no better than one that uses each asset's own historical average | Monthly; same assets | Not stated | [IDEAS](https://ideas.repec.org/a/eee/jfinec/v135y2020i3p774-794.html) | verified (abstract) |
| Lempérière et al. 2014 | Trend following since 1800 | **Mixed to strong for slow trends.** t-statistic about 5 since 1960 and about 10 since 1800 after removing drift; short-term trends weaker recently. Authors appear to be from a quant fund (affiliation not on the page I read: UNVERIFIED) | Multi-decade; commodities, currencies, indices, bonds | Not stated | [arXiv](https://arxiv.org/abs/1404.3274) | verified (abstract). Affiliation UNVERIFIED |

### 2K. Intraday-specific evidence

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Gao, Han, Li, Zhou 2018 | First half-hour return predicts last half-hour return | **Mixed.** Documented for the S&P 500 ETF 1993-2013 and ten other ETFs; stronger on volatile, high-volume, recession and news days. **Our own test (backtest report):** LAST30_MOM_SPY gross +0.96 bps, net -2.04 bps at 1.5 bps a side (test year Sep 2025-Sep 2026) | Intraday; S&P 500 ETF | Not stated in abstract | [IDEAS](https://ideas.repec.org/a/eee/jfinec/v129y2018i2p394-414.html) | verified (abstract). Our result from repo report |
| Limkriangkrai, Chai, Zheng 2023 | Replication of the above in Asia-Pacific ETFs | **Mixed / weaker.** "Mainly evident in China and Japan", weak in South Korea, none in Hong Kong or Singapore; "not as pervasive" as in the US; weaker in the COVID period | Intraday; APAC ETFs | Not stated | Pacific-Basin Finance Journal 80 (2023) 102086 | verified (abstract, from the open-access PDF). URL not recorded |
| Opening range breakout, VWAP trend, "noise area" bands (Zarattini and co-authors, 2023-2025) | Firm-published day-trading rules on SPY/QQQ/stocks | **Claims to test.** Our own out-of-sample tests found no net edge (ORB5_QQQ -3.2 bps and VWAP_TREND_QQQ -2.7 bps at 1.5 bps a side). The authors' commercial position (research and tools for sale) is UNVERIFIED | Intraday; SPY/QQQ | Our test: no | SSRN pages returned HTTP 403 | UNVERIFIED (paper pages not read) |

### 2L. Machine learning on price charts and raw price windows

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| Jiang, Kelly, Xiu 2023 (J. Finance 78(6): 3193-3249) | A convolutional neural network reads 5-, 20-, 60-day OHLC-plus-volume chart images of US stocks and predicts direction | **Mixed.** Trained once on 1993-2000, held fixed for 2001-2019. One-month holding, equal-weight long-short Sharpe 2.4 / 2.2 / 1.3 (5-/20-/60-day images) vs 0.3 momentum, 0.6 monthly reversal, 1.2 weekly reversal. **Value-weight Sharpe only about 0.45-0.49 (5-/20-day images) vs 0.36 for momentum.** Turnover about 175-187% a month vs 63-76% for momentum; the authors say it is "nearly identical" to weekly short-term reversal, and note that short-term reversal is viewed as a strategy that does not survive trading costs while momentum is viewed as one that does. They say their 1-week Sharpe of 7.2 should not be read as "achievable in practice". Sharpe stays about 0.9 in some cases even with a one-week trading delay. Co-author Kelly is also at AQR Capital Management (stated on the paper) | Daily bars; US stocks 1993-2019 (test 2001-2019); patterns also work abroad (abstract) | **Not netted out** in the working paper I read; the published version's cost treatment is UNVERIFIED | [IDEAS](https://ideas.repec.org/a/bla/jfinan/v78y2023i6p3193-3249.html), [working paper](https://www.aidf.nus.edu.sg/wp-content/uploads/2022/02/Xiu-Re-Imagining-Price-Trends.pdf) | verified (abstract of published paper; full text of the working paper; numbers may differ in the final version) |
| Murray, Xia, Xiao 2024 ("Charting by machines") | Machine learning on past prices/returns to forecast US stocks | **Mixed.** Forecasts "strongly predict" the cross-section, hold in most sub-periods and "among the largest 500 stocks", differ from momentum, reversal and known technical signals; the authors conclude "technical analysis and charting have merit". Cost results not read | US stocks (horizon not read) | UNVERIFIED | [IDEAS](https://ideas.repec.org/a/eee/jfinec/v153y2024ics0304405x2400014x.html) | verified (abstract) |
| Zhu and Zhu 2024 | Uses chart-image networks to re-weight momentum/reversal signals | **Weak-Mixed.** Extends Jiang et al. to Chinese stocks; better Sharpe and lower turnover than the original signals. I found no transaction-cost results in the text | 1-day and 1-week; China A-shares | Not found | [arXiv](https://arxiv.org/abs/2408.08483) | verified (abstract + text search) |
| Avramov, Cheng, Metzker 2023 | Do machine-learning signals survive real-world limits? | **A critique.** Profit comes from "difficult-to-arbitrage stocks" and high-stress markets; excluding microcaps, distressed stocks or volatile periods "considerably attenuates" it; costs erode the rest through high turnover and extreme positions | US stocks (horizon not read) | Yes (deteriorates) | [EconPapers](https://econpapers.repec.org/RePEc:inm:ormnsc:v:69:y:2023:i:5:p:2587-2619) | verified (abstract) |
| Fischer and Krauss 2018 | LSTM network on S&P 500 stocks | **Weak after 2010.** 1992-2015: 0.46% a day and Sharpe 5.8 **before** costs, but "arbitraged away with LSTM profitability fluctuating around zero after transaction costs" from 2010. Profit sources were high volatility and short-term reversal | Daily; S&P 500 stocks | Yes (about zero since 2010) | [EconPapers](https://econpapers.repec.org/RePEc:eee:ejores:v:270:y:2018:i:2:p:654-669) | verified (abstract) |
| Lim, Zohren, Roberts 2019 | Deep network that learns trend and position size for 88 futures | **Mixed.** Sharpe more than doubled versus classic methods without costs, "continue outperforming" with costs up to 2-3 bps; needs a turnover penalty for less liquid assets | Daily futures | Yes, only up to 2-3 bps | [arXiv](https://arxiv.org/abs/1904.04912) | verified (abstract) |
| Cohen, Balch, Veloso 2019 | Turns candlestick images into classification tasks | **Not evidence of profit.** Shows networks can recover "algebraically-defined" trade labels from images; the labels are rules, not future returns | Synthetic labels on price charts | n/a | [arXiv](https://arxiv.org/abs/1907.10046) | verified (abstract) |
| Shi et al. 2025 ("Kronos") | Foundation model for candlestick (K-line) data across 45 exchanges | **Not tested for trading.** Reports better forecasting rank-correlation (RankIC +93% over the leading time-series model) and volatility forecasts; no after-cost trading result in the abstract | Multi-market K-lines | Not shown | [arXiv](https://arxiv.org/abs/2508.02739) | verified (abstract) |
| Lin et al. 2026 (image models on line, candlestick and bar charts) | Compares chart image types for a neural net | **Weak.** Six companies, predicting next-day/week/month price; no trading-profit test in the abstract | Daily; six stocks | No | [DOI](https://doi.org/10.1002/for.70099) | verified (abstract via Crossref record) |
| Gu, Kelly, Xiu 2020; Kelly, Malamud, Zhou 2024 | Broad machine-learning studies | **Context.** All methods rely on "variations on momentum, liquidity, and volatility". "Complex" models are argued to help (Kelly et al.); critiques of that claim exist but I did not verify them | US stocks and market (horizon not read) | Not stated | [GKX](https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2223-2273..html), [KMZ](https://ideas.repec.org/a/bla/jfinan/v79y2024i1p459-503.html) | verified (abstracts) |

### 2M. Data snooping, p-hacking and decay

| Item | What it is | Evidence and strength | Horizon and market | After costs? | Source | Verified? |
|---|---|---|---|---|---|---|
| White 2000 | "Reality Check": a test that accounts for having tried many rules | **The standard tool** used by STW, Hsu-Kuan and others | Method | n/a | [IDEAS](https://ideas.repec.org/a/ecm/emetrp/v68y2000i5p1097-1126.html) | bibliographic only; described via STW full text |
| Harvey, Liu, Zhu 2016; Harvey and Liu 2020 | Multiple-testing hurdles for new findings | "A new factor needs to clear a much higher hurdle, with a t-statistic greater than 3.0"; "most claimed research findings in financial economics are likely false". 2020: a double-bootstrap that also counts missed discoveries | Cross-section of US returns | n/a | [2016](https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html), [2020](https://doi.org/10.1111/jofi.12951) | verified (abstracts) |
| Hou, Xue, Zhang 2020 | Replication of 452 anomalies | With microcaps mitigated and value weights, **65% fail** the usual test (t-statistic of 1.96 in absolute value) and **82% fail** the stricter multiple-testing hurdle of 2.78; even the survivors are much smaller than originally reported | US stocks | n/a | [IDEAS](https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html) | verified (abstract) |
| Jensen, Kelly, Pedersen 2023 | The counter-view | Using a Bayesian approach, most factors **can be replicated**, cluster into 13 themes and work out of sample in 93 countries. (These are firm-characteristic factors, not chart techniques) | 93 countries | n/a | [IDEAS](https://ideas.repec.org/a/bla/jfinan/v78y2023i5p2465-2518.html) | verified (abstract) |
| McLean and Pontiff 2016 | What happens after a finding is published | 97 predictors: returns are **26% lower out-of-sample and 58% lower after publication** (the repo already cites this) | US stocks, 97 predictors | n/a | [DOI](https://doi.org/10.1111/jofi.12365) | verified (abstract via Crossref record) |
| Bailey, Borwein, López de Prado, Zhu | How few tries it takes to fool a backtest | "For a model based on 5 years of data, one can be misled by looking at even as few as 45 sample configurations." Hold-out tests "tend to be unreliable and inaccurate" for backtests; a probability-of-overfitting method (CSCV) is proposed. My own calculation (section 3) reproduces the 45-tries / 5-years / Sharpe-1 figure | Method | n/a | [PBO paper PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf), [press release quote](https://www.sciencedaily.com/releases/2014/04/140410103005.htm) | PBO abstract verified (full text). The 45/5-year quote is verified only in the press release (AMS PDF not read) |

---

## 3. What we can test with our data

**What we have.** SIP 1-minute bars for SPY and QQQ from Aug 2024 to Sep 2026 (about 2 years); Alpaca free historical SIP daily and minute bars back to 2016 (about 10 years); real-time IEX only; options quotes only "indicative". Two symbols only.

**What that means.** Anything that needs a **cross-section of many stocks** cannot be tested: cross-sectional momentum and relative strength, 52-week-high at the stock level, the Jiang-Kelly-Xiu and Murray-Xia-Xiao image or ML models, and Lo-Mamaysky-Wang-style pattern statistics (which used hundreds of stocks over 35 years). Ten years of two symbols is about 20 symbol-years. Anything involving options cannot be tested with "indicative" quotes.

### 3.1 The statistical bar (own calculation)

Method: for N independent rules whose true edge is zero, the best in-sample Sharpe you expect by luck is about E[max of N normals] divided by the square root of the years of data. This is a standard extreme-value approximation, and as I recall the one Bailey et al. use (I did not read their formula in the text I could open; my numbers do reproduce their published example of 45 tries, 5 years, Sharpe about 1.0). Assumptions that flatter the result: independent tries and no fat tails. Rules that are near-copies of each other count as fewer tries, but hidden tries (which papers you read, which timeframe, which symbol, how many times you looked at the same test year) count as more. The code is `luck_table.py` in this folder.

**How many tries until luck alone gives an impressive Sharpe?**

| Sharpe that looks impressive | 1 year of data | 2 years | 5 years | 10 years |
|---|---|---|---|---|
| 0.5 | 2 tries | 3 | 5 | 11 |
| 1.0 | 4 | 8 | 46 | 725 |
| 1.5 | 9 | 34 | 1,423 | 536,958 |
| 2.0 | 26 | 243 | 145,786 | more than a million |
| 3.0 | 421 | 51,135 | more than a million | more than a million |

**Best Sharpe you should expect from luck, by number of tries:**

| N rules tried | 1 year | 2 years | 5 years | 10 years | Chance at least one shows t > 2 by luck |
|---|---|---|---|---|---|
| 5 | 1.19 | 0.84 | 0.53 | 0.38 | 21% |
| 14 | 1.74 | 1.23 | 0.78 | 0.55 | 48% |
| 28 | 2.04 | 1.45 | 0.91 | 0.65 | 73% |
| 100 | 2.53 | 1.79 | 1.13 | 0.80 | 99% |
| 7,846 (STW's universe) | 3.80 | 2.69 | 1.70 | 1.20 | 100% |

**Sharpe you need before you believe a result (Bonferroni: p below 0.05 divided by N):**

| N tests | t needed | 1 year | 2 years | 5 years | 10 years |
|---|---|---|---|---|---|
| 1 | 1.96 | 1.96 | 1.39 | 0.88 | 0.62 |
| 3 | 2.39 | 2.39 | 1.69 | 1.07 | 0.76 |
| 8 | 2.73 | 2.73 | 1.93 | 1.22 | 0.86 |
| 28 (our current run: 14 setups x 2 symbols) | 3.12 | 3.12 | 2.21 | 1.40 | 0.99 |
| 60 | 3.34 | 3.34 | 2.36 | 1.49 | 1.06 |

**Power problem.** Against the N = 28 bar, a strategy whose *true* Sharpe is 1.5 passes only about 5% of the time with one year of test data, 16% with two years, 59% with five, 95% with ten. A true Sharpe of 1.0 passes 52% of the time with ten years. So: the bar protects us from false positives (good), but a single test year cannot confirm a real edge (bad). More history is the fix, not a looser bar.

### 3.2 Tests worth running (ranked; each one is written down before looking)

| # | Test | Why | Data | Tries it adds | Cost/risk |
|---|---|---|---|---|---|
| T1 | **Re-run the frozen 14 setups on 2016-2024 minute data** with the same code and cost model (the backtest report already lists this as "not yet run") | Decay check and 10x the power. Caveat: the ORB and VWAP papers used samples that overlap 2016-2023 (from memory, UNVERIFIED), so that span may be *their* in-sample, not out-of-sample. For the last-30-minute effect (Gao et al., 1993-2013), 2014-2024 is a genuine out-of-sample | Alpaca history from 2016 | 0 new tries if nothing is changed (add years, not rules) | Do not tune anything after seeing it |
| T2 | **One daily trend gate on SPY/QQQ**: hold when the close is above the 200-day average, else cash; compare with buy-and-hold on drawdown, Sharpe, turnover, at 2 bps a side | It is the best-supported idea in this note (slow trend, risk control), and the only one whose main benefit (smaller drawdowns) does not depend on a tiny edge. Judge it as **risk control**, not alpha: 2016-2026 has only about three real bear episodes (2018 Q4, 2020, 2022), so a significance test will be weak | Daily bars from 2016 | 1 (do not also try 50/100/150-day without counting them) | Cheap |
| T3 | **Round-number event study (no trading)**: after SPY/QQQ touch a round level ($5 or $10 multiples), does price reverse more within 30 minutes than after touching matched non-round control levels? Also test Osler's second prediction (faster moves after a break) | Turns "support and resistance" into one measurable claim; also tells the execution code when spreads and adverse selection are worst | Minute bars 2016-2026 | 1 to 2 | Any trading rule built from it counts as new tries |
| T4 | **Regime check for the one published intraday effect**: is the last-30-minute effect larger on volatile prior days? (Gao et al. report it is) | One hypothesis taken from a paper, not from our data | Minute bars 2016-2026 | 1 | Low |
| T5 | **Install the snooping tools**: Deflated Sharpe Ratio, White's Reality Check or Hansen's SPA, and a trial counter on every lab run | Makes MT-G7 automatic and stops us fooling ourselves with 10 years of data | Lab outputs | 0 | Cheap |
| T6 | **Cost measurement** from the paper account (already planned) | Costs decide almost everything in this literature (Novy-Marx and Velikov; Rink; Duvinage) | Paper fills | 0 | Already in plan |

**Not worth testing (no trial budget spent):** candlesticks, Fibonacci, Elliott wave, Dow theory, hand-drawn trendlines, Bollinger/stochastic/RSI/MACD variants, "confluence" rules with several timeframes and indicators. Each would add tries and the literature gives no reason to expect a result.

---

## 4. Recommendations for the agent design

### 4.1 Include

1. **A technique registry.** For each technique: exact frozen definition, source, number of tries so far, years of data, the Sharpe needed from the table in 3.1, cost assumption, and status (blocked / shadow / exploratory / validated). Every threshold, timeframe, symbol and indicator variant counts as a try (this is MT-G7 made concrete).
2. **Volatility state as context, not a signal.** Realised volatility (from the bars we already have) to size down or skip when spreads and moves are wide. This has the best evidence (Corsi; Barroso and Santa-Clara), with the caveat that the "volatility-managed portfolio" gains are contested (Cederburg et al.).
3. **A daily trend gate** (T2) as a regime switch for how much risk to run, judged on drawdown.
4. **Round-number-aware execution.** Do not rest stops at round numbers; avoid crossing the spread at round numbers; keep limit orders with collars (Osler 2003; Bhattacharya et al.).
5. **Time-of-day and spread awareness** as a cost filter (measured on our own data, not taken from a paper).
6. **Fixed, pre-set stops and targets** (already in the guardrails). The evidence I read says stops can add value at longer horizons (Kaminski and Lo); I did not verify the further point, from my memory, that they cost money when prices are close to random. Treat them as risk control, not as an edge.
7. **Snooping controls in code**: Deflated Sharpe, Reality Check or SPA, trial counter, minimum data length. Require the Sharpe from the table above for the number of tries so far.
8. **A "decay" report**: gross and net bps by half-year for every setup. All the literature above ends the same way: profits fade after they are published.

### 4.2 Avoid

1. **Teaching named patterns** (head-and-shoulders, flags, triangles, candlesticks, Fibonacci, Elliott wave, Dow theory, trendlines). No credible after-cost evidence, and a named-pattern library is a machine for generating tries.
2. **Letting an AI model read charts.** Vision-language models trade on trend extrapolation and ignore candlestick evidence (Wang 2026, preprint). This matches MT-G29 (the LLM only vetoes; code computes every number).
3. **Multi-indicator "confluence" and multi-timeframe confirmation** as an add-on to a setup that failed. It multiplies tries, and volume/indicator filters showed no benefit in tests (Lo et al.; Tharavanij et al.).
4. **Chart-image neural nets on two symbols.** The published results need thousands of stocks. For machine-learning return signals in general, much of the gain sits in hard-to-trade stocks and shrinks after costs (Avramov et al.), and Jiang et al.'s own value-weighted Sharpe is far below its equal-weighted one.
5. **Trusting the published pass rate of any pattern book or educator.** Treat as "claims to test", especially where the seller profits (Bulkowski sells the book and data; firm-published day-trading papers).
6. **Optimising on one test year.** It has almost no power (section 3.1) and invites hidden tries.

### 4.3 What to test first (in order)

T5 (tools) then T1 (frozen setups on 2016-2024) then T2 (daily trend gate) then T3 (round-number study) then T4. Everything is written down before it runs. Stop after T1 if nothing survives the bar. That is an acceptable, useful outcome.

### 4.4 Technique scorecard and "should a machine be taught this?"

Verdict codes: **A** = teach as a risk, cost or context input. **B** = test once, cheaply, with the numbers written down first. **C** = shadow or exploratory only. **D** = do not teach. **E** = cannot be tested with our data.

| Technique | Grade | Verdict | One-line reason |
|---|---|---|---|
| Volatility state / vol-scaling | Strong (forecasting), Mixed (as a return source) | **A** | Volatility is predictable; direction is not |
| Daily trend gate (200-day style) | Mixed | **B** | Best-supported idea; judge on drawdown, not alpha |
| Time-series momentum (months) | Mixed, contested | **B** (as the same gate) | Long history but contested (Huang et al.); short-term trends have weakened |
| Cross-sectional momentum / relative strength | Mixed | **E** | Needs many stocks; turnover kills it |
| 52-week high (stock level) / index level | Mixed | **E** / **B** | Stock level needs a cross-section; index level is monthly, low power |
| Intraday momentum (last 30 minutes) | Mixed | **C** | Published effect; our test is net negative; T1 and T4 will show if it is decaying |
| Opening range, VWAP, noise-area bands | Weak (our tests negative) | **C** | Exploratory lane only |
| Moving-average crossovers on minute charts | None | **D** | 7,846 rules, none survive (Marshall et al.) |
| Long-horizon MA on indexes | Mixed, decaying | **B** (as the gate) | In-sample support, then faded; costs matter |
| RSI / MACD / stochastic / Bollinger | Weak / None | **D** | Old samples, few variants, best highlighted; filters do not help |
| Chart patterns (head-and-shoulders, double tops, triangles, flags) | Weak-Mixed | **D** (or **E** for Lo-style stats) | Some information, no stand-alone profit |
| Candlesticks | Weak / None | **D** | No rule survives snooping and costs (Duvinage) |
| Support / resistance / round numbers | Mixed as a fact, None as a profit rule | **A** for execution, **B** as an event study, **D** as an entry rule | Orders cluster there; that is a cost to avoid, not a forecast |
| Volume: "confirmation" of breakouts | None | **D** | Little incremental information (Lo et al.) |
| Volume: liquidity checks (RVOL, spread) | n/a | **A** | A cost and safety input, not a signal |
| Fibonacci | Weak / None | **D** | Wide zones catch more bounces by construction |
| Elliott wave | None / Not testable | **D** | Subjective counting |
| Dow theory | Weak, dated | **D** | Editor's judgement; 1902-1929 |
| Trendlines drawn by eye | None found / Not testable | **D** | Subjective |
| Multi-timeframe confluence (retail) | None found | **D** | No test; adds tries |
| Stop-losses / targets | Mixed | **A** (already in rules) | Risk control, not edge |
| Image CNNs / ML on price windows | Mixed (cross-section only) | **E** / **D** | Needs a stock cross-section and cost work |
| AI vision reading charts | None | **D** | Extrapolates trend (Wang 2026) |
| Snooping controls (DSR, SPA, trial counter) | n/a | **A** | The most valuable code we can add |

### 4.5 The ten techniques with the best evidence, and the ten with the worst

"Best" is relative: none is Strong for a one-minute, SPY/QQQ, after-cost trader. Ranked by strength and replication of the evidence, at any horizon.

**Best ten**
1. Volatility clustering and its forecastability (Corsi 2009; Barroso and Santa-Clara 2015). Strong for forecasting.
2. Trend following at 1-12 months on many markets (Moskowitz et al. 2012; Lempérière et al. 2014). Mixed; contested by Huang et al. 2020.
3. Cross-sectional momentum / relative strength (Jegadeesh and Titman 1993). Mixed; decays, costly.
4. 52-week-high nearness (George and Hwang 2004; Li and Yu 2012). Mixed.
5. Long-horizon moving-average filters on stock indexes (Brock et al.; Zhu and Zhou; Neely et al.; Han et al.). Mixed; faded after 1986.
6. Volume-conditioned monthly effects (Gervais et al. 2001; Lee and Swaminathan 2000). Mixed.
7. Stop-loss rules as conditional risk control (Kaminski and Lo 2014). Mixed.
8. Order clustering at support and round numbers (Osler 2000, 2003; Kavajecz and Odders-White 2004; Bhattacharya et al. 2012). Mixed as a fact; no profit test.
9. Intraday momentum, first to last half-hour (Gao et al. 2018). Mixed; weaker abroad; our own test net negative.
10. Machine learning on price charts in the stock cross-section (Jiang et al. 2023; Murray et al. 2024). Mixed; cost and capacity unresolved. (Just outside: algorithmic chart patterns, Lo et al. 2000.)

**Worst ten**
1. Elliott wave: subjective; the only paper I found reads like a fit to past data (my reading), with no costs.
2. Fibonacci retracements: wider zones catch more bounces; tiny Sharpe; no costs.
3. Candlestick patterns, especially intraday: no rule survives snooping and costs.
4. Trendlines and channels by eye: no dedicated test.
5. "Multi-timeframe confirmation" as retail teaches it: no test.
6. Bulkowski-style success-rate tables: not replicated; seller's own data.
7. AI vision models reading charts: trend extrapolation, no use of the evidence.
8. Stochastic oscillator: no dedicated evidence; filter tests show no help.
9. Bollinger Bands as a stand-alone rule: no better than a plain moving-average envelope.
10. "Volume confirms the breakout" as a filter: little incremental information.
(Honourable mentions for worst: RSI and MACD stand-alone, stand-alone head-and-shoulders, Dow theory.)

### 4.6 What a beginner should be told

- A chart pattern is often a story we tell about noise. Careful tests mostly find that these stories do not pay after costs.
- What has held up in studies is slow (trends over months), plus the fact that calm and stormy periods last, plus good risk control. None of that is "spotting shapes on a one-minute chart".
- Every time you try another version of a rule, you raise the chance that the winner is luck. With two years of data, eight tries can already produce a "Sharpe 1.0" that means nothing. That is why we count every variation.
- Rules stop working once many people know them. The famous 1992 result failed in the following ten years. The opening-range breakout faded in our own test.
- Costs are the enemy of small edges. On a minute chart a 1-2 cent cost can be most of the move.
- Paper trading flatters you. Fills are better than real ones.
- An AI that "reads" a chart is guessing from the trend. The AI's job here is to enforce rules and veto, not to find patterns.
- If nothing passes, the right answer is to trade nothing. That means the system worked.

---

## 5. Open questions and things I could not verify

**Search limits.** The session's web-search budget (200 calls, shared) ran out mid-task. I then used only direct page fetches of specific papers (IDEAS, EconPapers, arXiv, Crossref records, author or publisher PDFs) and did not use other search routes. As a result:
- **No direct test of multi-timeframe confirmation found.** This is "none found", not "none exists".
- **No independent replication or critique of Jiang, Kelly, Xiu (2023) found.** A search for one returned only extensions (Zhu and Zhu 2024; Chinese-market and other image papers whose abstracts I did not read). This could be a search gap.
- **Bulkowski:** I found no independent test, but did not run a full search of the literature.
- **Trendline tests:** none found.

**Read only as abstracts or bibliographic entries (details not checked):** Marshall, Young, Rose 2006 (abstract inaccessible; finding taken from a search summary); Chang and Osler 1999 (own abstract only from a search summary); Tsinaslanidis, Guijarro, Voukelatos 2022 on Fibonacci (search summary only); Marshall, Young, Cahan 2008 (Japan, candlesticks: no abstract); Ni, Pearson, Poteshman 2005; Allen and Karjalainen 1999; Lesmond, Schill, Zhou 2004; Müller et al. 1997; White 2000; Bailey and López de Prado 2014 (Deflated Sharpe Ratio).

**Not checked at all, but seen in search summaries or known to me:** Ready 2002 and Allen and Karjalainen 1999 (cited by Rink 2023 as consistent with costs killing technical profits); Byun et al. 2025 (a vision transformer on candlestick charts); Lu and Wu (Chinese stock price images, SSRN 4171663); a 2026 Finance Research Letters paper on chart-image factors; Brogaard and Zareei 2023 (machine-learned trading rules); critiques of Kelly, Malamud, Zhou 2024 (Nagel; Buncic); Hurst, Ooi, Pedersen 2017 (AQR, trend following); Zarattini et al. papers (SSRN pages blocked); Faber 2007 and other practitioner moving-average papers.

**Conflicts of interest to keep in mind.** Bulkowski sells books and data (his page directs readers to buy the book; verified). Kelly (Jiang-Kelly-Xiu) is at AQR Capital Management (stated on the paper; verified). Lempérière et al. are, to my knowledge, fund-affiliated (not on the page I read). Firm-published day-trading papers (Zarattini and co-authors) and Elliott-wave promoters may sell products or subscriptions (UNVERIFIED). Osler's tests use levels published by trading firms.

**Limits of the evidence itself.**
- Rink 2023 ends in May 2016. The 2016-2026 period is not covered by that paper.
- Almost all positive technical results are daily or monthly, on many assets, before or barely after costs. Almost none are minute-level, on two ETFs, after realistic costs.
- The Jiang et al. numbers I quote are from the SSRN working paper (Chicago Booth version on the NUS site). The published version may differ, especially in how costs are treated.
- The Sharpe/luck tables are my own calculation with simple assumptions (independent tries, normal returns). Real trades cluster by day, and returns are fat-tailed, so treat the tables as a guide, not a proof.
- "Verified" here means the abstract or full text says it. It does not mean I re-ran the study. Abstracts on repository pages sometimes shorten the original wording; quotes come from those pages.

**Questions for the owner.** (1) Should the 2016-2024 re-run (T1) be allowed before any new paper trades? (2) Is a daily trend gate an acceptable use of the bot's time even though it is not "minute trading"? (3) Should the technique registry (4.1) also list "blocked" techniques so a future session does not re-propose them?

---

## 6. Sources

Full text was read for: Sullivan-Timmermann-White, Lo-Mamaysky-Wang, Osler 2000, Jiang-Kelly-Xiu (working-paper version), Rink 2023, Chong-Ng-Liew 2014 and the Bailey et al. overfitting paper, plus parts of Zhu and Zhu 2024, the 2026 MACD preprint, Wang 2026 and Limkriangkrai et al. 2023. Everything else was checked at abstract level (or less, as marked).

Verification key: **full** = full text read; **abs** = abstract read on a publisher or repository page; **bib** = bibliographic record only; **UNVERIFIED** = search summary or memory only.

**Moving-average and technical trading rules**
1. Brock, Lakonishok, LeBaron (1992), J. Finance 47(5):1731-64. https://ideas.repec.org/a/bla/jfinan/v47y1992i5p1731-64.html (abs)
2. Sullivan, Timmermann, White (1999), J. Finance 54(5):1647-91. https://www.kevinsheppard.com/files/teaching/mfe/advanced-econometrics/Sullivan_Timmermann_White.pdf (full)
3. Marshall, Cahan, Cahan (2008), J. Empirical Finance 15(2):199-210. https://econpapers.repec.org/RePEc:eee:empfin:v:15:y:2008:i:2:p:199-210 (abs)
4. Bajgrowicz, Scaillet (2012), J. Financial Economics 106(3):473-91. https://econpapers.repec.org/article/eeejfinec/v_3a106_3ay_3a2012_3ai_3a3_3ap_3a473-491.htm (abs)
5. Park, Irwin (2007), J. Economic Surveys 21(4):786-826. https://experts.illinois.edu/en/publications/what-do-we-know-about-the-profitability-of-technical-analysis/ (abs)
6. Rink (2023), Financial Markets and Portfolio Management 37(4):403-56. https://ideas.repec.org/a/kap/fmktpm/v37y2023i4d10.1007_s11408-023-00433-2.html ; https://www.econstor.eu/bitstream/10419/312389/1/s11408-023-00433-2.pdf (abs + full)
7. Hsu, Kuan (2005), J. Financial Econometrics 3(4):606-28. https://ideas.repec.org/a/oup/jfinec/v3y2005i4p606-628.html (abs)
8. Hsu, Taylor, Wang (2016), J. International Economics 102:188-208. https://ideas.repec.org/a/eee/inecon/v102y2016icp188-208.html (abs)
9. Sermpinis, Hassanniakalager, Stasinakis, Psaradellis (arXiv 1811.06766). https://arxiv.org/abs/1811.06766 (abs)
10. Schulmeister (2009), Review of Financial Economics 18(4):190-201. https://ideas.repec.org/a/eee/revfin/v18y2009i4p190-201.html (abs)
11. Neely, Rapach, Tu, Zhou (2014), Management Science 60(7):1772-91. https://ideas.repec.org/a/inm/ormnsc/v60y2014i7p1772-1791.html (abs)
12. Zhu, Zhou (2009), J. Financial Economics 92(3):519-44. https://ideas.repec.org/a/eee/jfinec/v92y2009i3p519-544.html (abs)
13. Han, Yang, Zhou (2013), JFQA 48(5):1433-61. https://ideas.repec.org/a/cup/jfinqa/v48y2013i05p1433-1461_00.html (abs)
14. Detzel, Liu, Strauss, Zhou, Zhu (2021), Financial Management 50. https://doi.org/10.1111/fima.12310 (abs, via Crossref record)
15. Chong, Ng (2008), Applied Economics Letters 15(14):1111-14. https://econpapers.repec.org/RePEc:taf:apeclt:v:15:y:2008:i:14:p:1111-1114 (abs)
16. Chong, Ng, Liew (2014), J. Risk and Financial Management 7(1):1-12. https://mpra.ub.uni-muenchen.de/54149/1/MPRA_paper_54149.pdf (full)
17. Lin, Lin, Zhang, Zheng, Wang (2026), arXiv 2604.26063. https://arxiv.org/abs/2604.26063 (abs + text search)
18. Leung, Chong (2003), Applied Economics Letters 10(6):339-41. https://ideas.repec.org/a/taf/apeclt/v10y2003i6p339-341.html (abs)

**Chart patterns**
19. Lo, Mamaysky, Wang (2000), J. Finance 55(4):1705-65. https://www.nber.org/papers/w7613 ; https://web.mit.edu/wangj/www/pap/LoMamayskyWang00.pdf (abs + full)
20. Savin, Weller, Zvingelis (2007), J. Financial Econometrics 5(2):243-65. https://academic.oup.com/jfec/article-abstract/5/2/243/785044 (abs)
21. Dawson, Steeley (2003), J. Business Finance & Accounting 30:263-93. https://doi.org/10.1111/1468-5957.00492 (abs via Crossref record)
22. Chang, Osler (1999), Economic Journal 109(458):636-61. https://doi.org/10.1111/1468-0297.00466 (own abstract UNVERIFIED; result described in Osler 2000, full)
23. Friesen, Weller, Dunham (2009), J. Banking & Finance 33(6):1089-1100. https://ideas.repec.org/a/eee/jbfina/v33y2009i6p1089-1100.html (abs)
24. Tsinaslanidis, Guijarro (2020), Expert Systems 38. https://doi.org/10.1111/exsy.12596 (abs via Crossref record)
25. Bulkowski, head-and-shoulders top page. https://www.thepatternsite.com/HSTExplained.html (page read; claims to test)

**Candlesticks**
26. Marshall, Young, Rose (2006), J. Banking & Finance 30(8):2303-23. https://ideas.repec.org/a/eee/jbfina/v30y2006i8p2303-2323.html (bib; finding UNVERIFIED)
27. Duvinage, Mazza, Petitjean (2013), Quantitative Finance 13(7):1059-70. https://ideas.repec.org/p/ajf/louvlr/2013001.html (abs)
28. Tharavanij, Siraprapasiri, Rajchamaha (2017), SAGE Open 7(4). https://ideas.repec.org/a/sae/sagope/v7y2017i4p2158244017736799.html (abs)
29. Lu, Shiu, Liu (2012), Review of Financial Economics 21(2):63-68. https://ideas.repec.org/a/eee/revfin/v21y2012i2p63-68.html (abs)
30. Lu, Shiu (2016), Applied Economics 48(35):3345-54. https://ideas.repec.org/a/taf/applec/v48y2016i35p3345-3354.html (abs)
31. Marshall, Young, Cahan (2008), Review of Quantitative Finance and Accounting 31(2):191-207. https://ideas.repec.org/a/kap/rqfnac/v31y2008i2p191-207.html (bib)
32. Wang (2026), arXiv 2606.17423. https://arxiv.org/abs/2606.17423 (abs + parts)

**Volume, support/resistance, round numbers**
33. Blume, Easley, O'Hara (1994), J. Finance 49(1):153-81. https://ideas.repec.org/a/bla/jfinan/v49y1994i1p153-81.html (abs)
34. Gervais, Kaniel, Mingelgrin (2001), J. Finance 56(3):877-919. https://ideas.repec.org/a/bla/jfinan/v56y2001i3p877-919.html (abs)
35. Lee, Swaminathan (2000), J. Finance 55(5):2017-69. https://ideas.repec.org/a/bla/jfinan/v55y2000i5p2017-2069.html (abs)
36. Osler (2000), FRBNY Economic Policy Review 6(2):53-68. https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.pdf (full)
37. Osler (2003), J. Finance 58(5):1791-1819. https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html ; https://doi.org/10.1111/1540-6261.00588 (abs)
38. Kavajecz, Odders-White (2004), Review of Financial Studies 17(4):1043-71. https://ideas.repec.org/a/oup/rfinst/v17y2004i4p1043-1071.html (abs)
39. Bhattacharya, Holden, Jacobsen (2012), Management Science 58(2):413-31. https://ideas.repec.org/a/inm/ormnsc/v58y2012i2p413-431.html (abs)
40. Donaldson, Kim (1993), JFQA 28(3):313-30. https://ideas.repec.org/a/cup/jfinqa/v28y1993i03p313-330_00.html (abs)
41. Ni, Pearson, Poteshman (2005), J. Financial Economics 78(1):49-87. https://ideas.repec.org/a/eee/jfinec/v78y2005i1p49-87.html (bib; finding UNVERIFIED)

**Fibonacci, Elliott, Dow**
42. Gurrib, Nourani, Bhaskaran (2022), Financial Innovation. https://pmc.ncbi.nlm.nih.gov/articles/PMC8752186/ (abs + results)
43. Tsinaslanidis, Guijarro, Voukelatos (2022), Expert Systems with Applications 187:115893. https://doi.org/10.1016/j.eswa.2021.115893 (UNVERIFIED; abstract not read)
44. D'Angelo, Grimaldi (2017), International Business Research 10(6):1-18. https://ideas.repec.org/a/ibn/ibrjnl/v10y2017i6p1-18.html (abs)
45. Brown, Goetzmann, Kumar (1998), J. Finance 53(4):1311-33. https://doi.org/10.1111/0022-1082.00054 (abs via Crossref record)

**Multi-timeframe, volatility, stops**
46. Corsi (2009), J. Financial Econometrics 7(2):174-96. https://ideas.repec.org/a/oup/jfinec/v7y2009i2p174-196.html (abs)
47. Han, Zhou, Zhu (2016), J. Financial Economics 122(2):352-75. https://ideas.repec.org/a/eee/jfinec/v122y2016i2p352-375.html (abs)
48. Müller et al. (1997), J. Empirical Finance 4(2-3):213-39. https://ideas.repec.org/a/eee/empfin/v4y1997i2-3p213-239.html (bib)
49. Moreira, Muir (2017), NBER w22208 / J. Finance 72(4). https://www.nber.org/papers/w22208 (abs)
50. Cederburg, O'Doherty, Wang, Yan (2020), J. Financial Economics 138(1):95-117. https://ideas.repec.org/a/eee/jfinec/v138y2020i1p95-117.html (abs)
51. Barroso, Santa-Clara (2015), J. Financial Economics 116(1):111-20. https://ideas.repec.org/a/eee/jfinec/v116y2015i1p111-120.html (abs)
52. Kaminski, Lo (2014), J. Financial Markets 18:234-54. https://ideas.repec.org/a/eee/finmar/v18y2014icp234-254.html (abs)

**52-week high, momentum, trend following, intraday**
53. George, Hwang (2004), J. Finance 59(5):2145-76. https://doi.org/10.1111/j.1540-6261.2004.00695.x (abs via Crossref record)
54. Li, Yu (2012), J. Financial Economics 104(2):401-19. https://ideas.repec.org/a/eee/jfinec/v104y2012i2p401-419.html (abs)
55. Jegadeesh, Titman (1993), J. Finance 48(1):65-91. https://ideas.repec.org/a/bla/jfinan/v48y1993i1p65-91.html (abs)
56. Novy-Marx, Velikov (2016), Review of Financial Studies 29(1):104-47. https://ideas.repec.org/a/oup/rfinst/v29y2016i1p104-147..html (abs)
57. Lesmond, Schill, Zhou (2004), J. Financial Economics 71(2):349-80. https://ideas.repec.org/a/eee/jfinec/v71y2004i2p349-380.html (bib)
58. Moskowitz, Ooi, Pedersen (2012), J. Financial Economics 104(2):228-50. https://ideas.repec.org/a/eee/jfinec/v104y2012i2p228-250.html (abs)
59. Huang, Li, Wang, Zhou (2020), J. Financial Economics 135(3):774-94. https://ideas.repec.org/a/eee/jfinec/v135y2020i3p774-794.html (abs)
60. Lempérière, Deremble, Seager, Potters, Bouchaud (2014), arXiv 1404.3274. https://arxiv.org/abs/1404.3274 (abs)
61. Gao, Han, Li, Zhou (2018), J. Financial Economics 129(2):394-414. https://ideas.repec.org/a/eee/jfinec/v129y2018i2p394-414.html (abs)
62. Limkriangkrai, Chai, Zheng (2023), Pacific-Basin Finance Journal 80:102086 (open-access PDF read; URL not recorded) (abs)
63. Zarattini and co-authors (2023-2025), SSRN, e.g. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172 (HTTP 403; UNVERIFIED)

**Machine learning on charts and price windows**
64. Jiang, Kelly, Xiu (2023), J. Finance 78(6):3193-3249. https://ideas.repec.org/a/bla/jfinan/v78y2023i6p3193-3249.html ; working paper https://www.aidf.nus.edu.sg/wp-content/uploads/2022/02/Xiu-Re-Imagining-Price-Trends.pdf ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3756587 (abs + full text of working paper)
65. Murray, Xia, Xiao (2024), J. Financial Economics 153. https://ideas.repec.org/a/eee/jfinec/v153y2024ics0304405x2400014x.html (abs)
66. Zhu, Zhu (2024), arXiv 2408.08483. https://arxiv.org/abs/2408.08483 (abs + text search)
67. Avramov, Cheng, Metzker (2023), Management Science 69(5):2587-2619. https://econpapers.repec.org/RePEc:inm:ormnsc:v:69:y:2023:i:5:p:2587-2619 (abs)
68. Fischer, Krauss (2018), EJOR 270(2):654-69. https://econpapers.repec.org/RePEc:eee:ejores:v:270:y:2018:i:2:p:654-669 (abs)
69. Lim, Zohren, Roberts (2019), arXiv 1904.04912 / J. Financial Data Science. https://arxiv.org/abs/1904.04912 (abs)
70. Cohen, Balch, Veloso (2019), arXiv 1907.10046. https://arxiv.org/abs/1907.10046 (abs)
71. Shi et al. (2025), arXiv 2508.02739 (Kronos). https://arxiv.org/abs/2508.02739 (abs)
72. Pei et al. (2024), arXiv 2410.19291. https://arxiv.org/abs/2410.19291 (abs)
73. Lin, Wang, Tsai, Hsu (2026), J. Forecasting 45. https://doi.org/10.1002/for.70099 (abs via Crossref record)
74. Gu, Kelly, Xiu (2020), Review of Financial Studies 33(5):2223-73. https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2223-2273..html (abs)
75. Kelly, Malamud, Zhou (2024), J. Finance 79(1):459-503. https://ideas.repec.org/a/bla/jfinan/v79y2024i1p459-503.html (abs)

**Data snooping, multiple testing, decay**
76. White (2000), Econometrica 68(5):1097-1126. https://ideas.repec.org/a/ecm/emetrp/v68y2000i5p1097-1126.html (bib)
77. Harvey, Liu, Zhu (2016), Review of Financial Studies 29(1):5-68. https://ideas.repec.org/a/oup/rfinst/v29y2016i1p5-68..html (abs)
78. Harvey, Liu (2020), J. Finance 75. https://doi.org/10.1111/jofi.12951 (abs via Crossref record)
79. Hou, Xue, Zhang (2020), Review of Financial Studies 33(5):2019-2133. https://ideas.repec.org/a/oup/rfinst/v33y2020i5p2019-2133..html (abs)
80. Jensen, Kelly, Pedersen (2023), J. Finance 78(5):2465-2518. https://ideas.repec.org/a/bla/jfinan/v78y2023i5p2465-2518.html (abs)
81. McLean, Pontiff (2016), J. Finance 71(1):5-32. https://doi.org/10.1111/jofi.12365 (abs via Crossref record)
82. Bailey, Borwein, López de Prado, Zhu, "The Probability of Backtest Overfitting". https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf (abs + text)
83. Bailey, Borwein, López de Prado, Zhu (2014), Notices of the AMS 61(5):458. Quote via https://www.sciencedaily.com/releases/2014/04/140410103005.htm and abstract at https://scholarworks.wmich.edu/math_pubs/40/ (press release quote only; AMS PDF not read)
84. Bailey, López de Prado (2014), J. Portfolio Management 40(5):94-107. https://doi.org/10.3905/jpm.2014.40.5.094 (bib)
85. Allen, Karjalainen (1999), J. Financial Economics 51(2):245-71. https://ideas.repec.org/a/eee/jfinec/v51y1999i2p245-271.html (bib)

**Files in this folder.** `luck_table.py` (the calculation in section 3.1), `txt/` (text extracted from PDFs I read; working files).
