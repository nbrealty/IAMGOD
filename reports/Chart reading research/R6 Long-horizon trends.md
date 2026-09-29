# R6: Chart reading for normal long-term stocks and ETFs (weeks to years)

> **Read `00 Fact-check corrections (read first).md` alongside this file.** Written on 28 Sept 2026 by a research agent; four independent fact-checkers then reviewed its main claims, and where they differ from the text below, the corrections file wins. Scripts behind the researcher's own calculations are in `scripts/` (paths such as `work/`, `r5/` or `research/` in the text point there; they expect data files downloaded separately). Terms like verified / UNVERIFIED are the researcher's own tags.


*Research report for the paper-trading project. Prepared 28 to 29 September 2026. Research only: nothing in the repo was edited, no git command was run, no order was placed and no broker or trading API was called. Data were pulled from public sources only (Ken French data library, Yahoo's public chart endpoint, Crossref, RePEc, arXiv, publisher and regulator pages).*

**How to read the labels**
- **verified** = I read the number in the paper (PDF), in the official abstract (publisher record via Crossref or RePEc), or on the official page.
- **UNVERIFIED** = seen only in a search snippet, blog, news story, a summarizer's paraphrase, or from my memory. Do not quote it as exact.
- **Own computation** = I ran code on public data (scripts and outputs are in this same folder). These are descriptive checks, not published results. About 30 rule variants were run, none tuned, and several time windows were chosen after looking at the data, so under rule MT-G7 they prove nothing by themselves.
- Strength scale: **Strong / Mixed / Weak / None / Not testable**.
- Limits of this session: the web-search tool hit its 200-call cap part-way through, so the hunt for independent tests of CAN SLIM, Minervini, Weinstein and Darvas, and for replications of the 52-week-high effect, is **not exhaustive** (section 5).

---

## 1. Plain-English summary

1. **Trend rules** (own an index while it is above its 10-month or 200-day average, otherwise sit in cash) have the longest track record in this area. What they reliably did was **cut the size and length of crashes, not raise profits.**
2. My recomputation on US stocks, 1927 to Aug 2026 (Ken French data): the 10-month rule made **9.8% a year against 10.3%** for buy-and-hold, with a worst loss of **-43% against -84%** and about a third less volatility. It lagged buy-and-hold in **44 of 98 calendar years**.
3. From April 2009 to Aug 2026 the same rule turned $1 into **$5.6 against $13.2**. Since 2013 it has not improved return per unit of risk (Sharpe 0.85 against 0.91). It paid off in 2000-02, 2008 and, partly, 2022.
4. **Sudden V-shaped drops hurt it.** In April 2025 and again in March-April 2026 the rules sold, then bought back 3% to 10% higher than they sold.
5. **Buying recent winners** (12-1 momentum) was real but has weakened: the long-short factor earned 8.8% a year before 1993 and 4.6% a year after (t-stat 1.6). It also crashes: in **July-August 2026 the top momentum decile fell 15.5% while the whole market rose 2.6%** (Ken French data, verified as data).
6. **CAN SLIM, Minervini, Weinstein, Darvas:** I found **no independent, replicated test**. Only their ingredients (momentum, 52-week highs, volume, trend filters) have academic support, each with decay or cost problems. The one live IBD-50 ETF (FFTY) grew $1 to $1.48 against $4.43 for SPY since 2015 (Yahoo data, UNVERIFIED).
7. **Weekly trend filter plus daily entry:** no published evidence that it beats either alone. In my test it was worse than the simple rules.
8. **Costs and tax:** small for SPY/QQQ (1 to 7 switches a year), large for baskets of momentum stocks. In a US taxable account, most in-market spells last under a year, so gains are taxed at short-term rates.
9. Two independent 2026 preprints (Goyal; Paz) show the same pattern: less drawdown, no outperformance, and published edges that shrink out of sample.
10. **For the bot:** use trend only as a slow, code-only risk overlay on SPY/QQQ, in shadow mode first, with 3 to 5 pre-registered rules. Tell the owner plainly that this cannot be proven in a 60-session paper test.

---

## 2. Findings table

Notation: "Own comp." = own computation. COI = conflict of interest. DOIs resolve at https://doi.org/. Numbers marked "(verified)" were read in the source named in the last two columns.

| # | Item | What it is | Evidence and strength | Horizon and market | After costs? | Source with URL | Verified? |
|---|---|---|---|---|---|---|---|
| 01 | Time-series momentum (Moskowitz, Ooi, Pedersen 2012) | Go long an asset if its past 12-month excess return is positive, short if negative, size by volatility | **Strong for a diversified futures portfolio** (58 instruments, gross Sharpe above 1, about 2.5 times the equity market's). Positive for every one of the 58 contracts. COI: two authors at AQR, which sells trend funds | Jan 1985 to Dec 2009; equity index, bond, currency, commodity futures | **No**: main results are gross | J. Financial Economics 104 (2012) 228-250. PDF https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf | Verified (PDF read) |
| 02 | A century of trend following (Hurst, Ooi, Pedersen 2017) | Same idea, 1/3/12-month signals, 67 markets, 10% volatility target, back to 1880 | **Strong for diversified futures, as a simulation.** Full sample: 18.0% gross, 11.0% after simulated costs, 7.3% after 2-and-20 fees; volatility 9.7%; Sharpe after fees and costs 0.76. Positive in every decade but 2010-2016 was weak (Sharpe 0.41 after fees and costs). Worst drawdown -24.7% (Aug 1947 to Dec 1948, then 26 months to recover). COI: AQR principals | 1880 to 2016; futures, and cash index returns before futures existed | **Partly**: costs are 2012 in-house estimates, roll costs left out, fees assumed 2-and-20 | J. Portfolio Management, Fall 2017. PDF https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-JPM-Fall-2017.pdf | Verified (PDF, Exhibits 1, 2, 7, 8) |
| 03 | Two centuries of trend following (Lempérière et al. 2014) | Trend rule on commodities, currencies, indices, bonds using spot data back to 1800 | **Strong that slow trends existed**: t-stat about 10 since 1800, about 5 since 1960, Sharpe 0.72. Fast (3-day) trends have **withered since 1990**; slow trends have not. Strategy was flat after 2011. COI: authors work at CFM, a trend-following manager | 1800 to 2013; spot and futures | Not clear (spot series, no full cost model read) | arXiv https://arxiv.org/abs/1404.3274 | Verified (PDF) |
| 04 | Critique of time-series momentum (Huang, Li, Wang, Zhou 2020) | Statistical re-test of item 01 | **Weak** evidence for predictability: asset-by-asset regressions show little, in or out of sample; the strategy works about as well as one that just bets on each asset's historical average | 1985 onward, futures | n/a | J. Financial Economics 135(3) 774-794. https://ideas.repec.org/a/eee/jfinec/v135y2020i3p774-794.html | Verified (abstract) |
| 05 | Faber 10-month moving average (2007 paper; 2013 update) | Hold an asset while its month-end price is above its 10-month average, else cash | **Mixed.** S&P 500 1901-2012: 10.18% compounded against 9.32% for buy-and-hold, invested about 70% of the time, fewer than one round trip a year, drawdown 2000-02 of 16.5% against 44.7%. Five-asset version 1973-2012: drawdown under 10% against 46%. Beat the index in only about half of years. COI: author runs Cambria, which sells funds | 1901 to 2012; US stocks and 4 other asset classes | **No**: taxes, commissions, slippage excluded; trades at the signal close | Spring 2007 J. Wealth Management. PDF (Feb 2013 update) https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf | Verified (PDF) |
| 06 | Independent checks of moving-average timing | Zakamulin (out-of-sample tests with realistic costs); Bajgrowicz and Scaillet (false-discovery test); Park and Irwin (survey); Brock et al. (original support) | **Mixed to Weak.** Zakamulin: performance of MA and momentum timing rules is "highly overstated" once data mining and costs are handled. Bajgrowicz and Scaillet: nobody could have picked the best rules in advance, and low costs wipe out even the in-sample profit. Park and Irwin: of 95 modern studies 56 positive, 20 negative, 19 mixed, most with testing flaws. Brock et al. 1992: supportive on the Dow. Marshall et al.: MA rules "perform best outside of large stock series" | Dow 1897-2011 (B&S); Dow 1897-1986 (BLL); various | Zakamulin and B&S: **yes, and it removes the profit** | https://doi.org/10.2139/ssrn.2242795 ; https://ideas.repec.org/a/eee/jfinec/v106y2012i3p473-491.html ; https://doi.org/10.1111/j.1467-6419.2007.00519.x ; https://doi.org/10.1111/j.1540-6261.1992.tb04681.x ; https://doi.org/10.2139/ssrn.2225551 | Verified (abstracts only). Sullivan et al. 1999 (https://doi.org/10.1111/0022-1082.00163): abstract read only in part, conclusion UNVERIFIED |
| 07 | Own comp.: 10-month and 12-month rules on all US stocks | Same rules as 05 and 01 on the Ken French total US market return, monthly, signal at month end, position held next month | **Mixed.** 1927-Aug 2026: 10-month rule CAGR 9.82%, volatility 12.5%, Sharpe 0.55, max drawdown -42.9%; buy-and-hold 10.33%, 18.4%, 0.45, -83.7%. 1973-2012: 10.18% against 9.89%, drawdown -24.3% against -50.3%. **2013-Aug 2026: 11.06% against 14.98%, Sharpe 0.85 against 0.91**, drawdown -17.6% against -24.8%. Against a constant 73% stocks / 27% bills mix, timing added value over 1927-2026 (Sharpe 0.55 against 0.45, drawdown -43% against -72%) and 1973-2012 (0.43 against 0.34), but **lost value in 2013-2026** (0.85 against 0.91 for an 84/16 mix) | 1927 to Aug 2026; all NYSE/AMEX/Nasdaq stocks (CRSP) | Yes at 10 bps a switch: CAGR 9.66%; taxes excluded | Data: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html (file made from the 202608 CRSP database). Scripts m1_monthly_market.py, m4_extra.py | Own comp. on verified public data |
| 08 | Own comp.: daily and weekly rules on SPY and QQQ | 200-day, 30-week, 10-month averages; Donchian 55/20; weekly filter plus 20-day breakout. Execution at next open, 5 bps a switch | **Mixed.** SPY Nov 1993-Aug 2026: buy-and-hold 10.88% a year, Sharpe 0.51, max drawdown -55.2%. 200-day: 8.63%, 0.54, -24.5%. 10-month: 9.64%, 0.59, -24.8%. 30-week: 7.69%, 0.47, -42.3%. QQQ Jan 2000-Aug 2026: buy-and-hold 8.60%, Sharpe 0.37, drawdown -83.0% (14.9 years under water); 200-day 8.34%, 0.44, -50.1%. **QQQ 2010-2019: buy-and-hold 17.9% against 4% to 10% for every rule.** Ranking of rules flips between sub-periods (SPY Sharpe: 30-week worst of the three average rules in 1993-2006 at 0.23, best in 2020-2026 at 0.82; 10-month best in 1993-2006, worst in 2020-2026) | SPY 1993-2026, QQQ 2000-2026; US large-cap ETFs | Yes: 5 bps a switch, 1.4 to 11 switches a year; taxes excluded | Yahoo adjusted closes (unofficial endpoint) + French daily risk-free. Script d1_daily.py | Own comp. (Yahoo data UNVERIFIED against issuer NAV) |
| 09 | Own comp.: Faber five-asset rule with real ETFs | SPY, EFA, IEF, VNQ, DBC, each held only while above its own 10-month average, else short-term Treasury ETF (SHY) | **Weak as an improvement, useful as insurance.** Jan 2007-Aug 2026: CAGR 5.5% (10 bps a switch), Sharpe 0.56, max drawdown -11%. SPY: 11.0%, 0.62, -51%. 60/40 SPY/IEF: 8.2%, 0.69, -30%. Did not beat 60/40 on Sharpe | 2007 to Aug 2026; 5 ETFs | Yes, 10 bps a switch | Yahoo adjusted closes. Script g1_gtaa.py | Own comp. |
| 10 | Trend-following funds 2020-2026 | SG Trend Index (large trend-following CTAs) and ETFs that copy them | **Mixed.** SG Trend Index: -4.9% in April 2025, -9.3% year to date to end-April 2025 (verified); **+16.03% year to date at 28 Sep 2026** (verified, "estimated"). Annual 2020-2024 index values not verified. ETF proxies (Yahoo, UNVERIFIED): DBMF 2022 +21.6%, 2023 -8.9%, 2025 +13.8%; KMLM 2022 +24.2%, 2023 -5.7%, 2025 -3.0%; CTA 2022 +9.6% (from March), 2024 +24.1%. Managers differ a lot: 2024 range of returns almost 15 points among index members | 2020 to Sep 2026; futures | ETFs are after fund fees, before tax | SG note (May 2025) https://content.sgmarkets.com/CTA_UPDATE_KEEPING_UP_WITH_THE_TRENDFOLLOWERS_2025 ; BarclayHedge page https://portal.barclayhedge.com/cgi-bin/indices/displayHfIndex.cgi?indexCat=SG-Prime-Services-Indices&indexName=SG-Trend-Index ; ETF numbers own comp. from Yahoo | SG figures verified; ETF figures UNVERIFIED |
| 11 | Cross-sectional momentum (Jegadeesh and Titman 1993) | Buy the past 3-12 month winners, sell the losers, hold 3-12 months | **Strong historically.** 1965-1989: about 1% a month; best strategy 12-month formation, 3-month hold 1.31% a month (1.49% with a one-week gap); 6-month/6-month strategy 12.01% a year; **9.29% a year after a 0.5% one-way cost**; turnover 84.8% every six months; part of the profit fades in years 2-3 | 1965 to 1989; NYSE/AMEX stocks | **Yes (assumed 0.5% one way)** | J. Finance 48(1) 65-91. PDF https://www.bauer.uh.edu/rsusmel/phd/jegadeesh-titman93.pdf | Verified (PDF) |
| 12 | Decay after publication (McLean and Pontiff 2016; Jacobs and Müller 2020; Hou, Xue, Zhang 2020) | Do published stock predictors keep working? | **Mixed.** 97 predictors: returns 26% lower out of sample and 58% lower after publication (momentum not singled out in the abstract). Jacobs and Müller: only the US shows a reliable post-publication decline across 39 markets. Hou et al.: 65% of 452 anomalies fail with microcaps controlled (momentum-type ones fare better, UNVERIFIED). **Own comp. on the momentum factor: mean 8.8% a year (t=4.4) to Feb 1993, 4.6% (t=1.6) from Mar 1993, 2.2% (t=0.7) since 2000** | US and 39 markets | Gross | https://doi.org/10.1111/jofi.12365 ; https://ideas.repec.org/a/eee/jfinec/v135y2020i1p213-230.html ; https://doi.org/10.1093/rfs/hhy131 | Verified (abstracts); own numbers from French Mom factor |
| 13 | Momentum crashes (Daniel and Moskowitz 2016) and July-Aug 2026 | Momentum has rare, long, partly forecastable crashes after market falls, when volatility is high and the market rebounds | **Strong** that crashes exist. Worst months Jul-Aug 1932; Mar-May 2009 losers +163% against winners +8%. **Own comp.: the factor fell -12.2% in Jul 2026 and -5.7% in Aug 2026 (15th worst of 1,196 months); the top decile (value-weighted) went +64.2% in H1 2026 then -15.5% in Jul-Aug while the market gained 2.6%.** News says a Goldman momentum index fell about 22% in five weeks (UNVERIFIED, blog) | 1927-2013 (paper); data to Aug 2026 | Gross | NBER https://www.nber.org/system/files/working_papers/w20439/w20439.pdf ; French library file above ; news https://llmquant.substack.com/p/22-gone-in-five-weeks-what-actually | Paper verified (PDF; COI: Moskowitz has an AQR relationship); Jul-Aug 2026 factor data verified as data; news UNVERIFIED |
| 14 | Risk-managed momentum (Barroso and Santa-Clara 2015; Daniel and Moskowitz dynamic version) | Scale momentum down when its recent volatility is high | **Mixed to Strong in-sample.** D&M: a dynamic version "approximately doubles the alpha and Sharpe ratio". **Own comp. (126-day volatility, 12% target, cap 2x): Sharpe 0.28 to 0.61 since Mar 1993; worst drawdown -57.8% to -25.2%; Jul 2026 loss -12.2% cut to -7.0%.** Uses shorts and leverage, gross of costs | 1927-2026; US stocks | No | https://doi.org/10.1016/j.jfineco.2014.11.010 (Barroso; title only) ; D&M PDF above ; script m3_volscale.py | D&M abstract verified; own numbers |
| 15 | 52-week-high effect (George and Hwang 2004) | Buy stocks priced near their 52-week high, sell those far below | **Mixed.** The 52-week high "explains a large portion" of momentum profits; 6-month/6-month versions of individual, industry and 52-week-high strategies all earned about 0.45% a month; no long-run reversal. One later, non-US preprint (India, 2004-2023) agrees. No independent US replication found (search cap) | Jul 1963 to Dec 2001; US stocks | **No**: gross, no cost analysis in the parts I read | https://doi.org/10.1111/j.1540-6261.2004.00695.x ; PDF https://www.bauer.uh.edu/tgeorge/papers/gh4-paper.pdf ; https://doi.org/10.2139/ssrn.4587697 | Verified (PDF, abstract) |
| 16 | Live momentum ETFs | MTUM, SPMO, QMOM (rules-based momentum funds) | **Mixed.** $1 grew to: MTUM 7.25 against SPY 6.24 (Apr 2013-Sep 2026); SPMO 6.81 against 4.54 (Oct 2015-); QMOM 3.08 against 4.39 (Dec 2015-). Relative to SPY, MTUM was ahead by 1.24x at end-2020, behind (0.94x) at end-2023 and ahead (1.16x) now; SPMO was about level (1.06x) at end-2023 and is 1.50x now. The leads came in 2020 and 2024-2026 and were lost in between | 2013 to 28 Sep 2026; US large caps | After fund fees, before tax | Own comp. from Yahoo adjusted closes | UNVERIFIED (issuer pages not read) |
| 17 | Costs of trading momentum | Trading cost estimates for momentum | **Mixed.** Novy-Marx and Velikov (Jul 1973-Dec 2012): long-short momentum gross 0.62% to 0.77% a month, costs 0.26% to 0.35%, net 0.31% to 0.51% with cost-saving tricks (buy/hold band works best). Lesmond et al.: momentum profits are concentrated in high-cost stocks, "illusory". Korajczyk and Sadka: profitable up to roughly $5 billion if liquidity-weighted. Frazzini et al.: live costs an order of magnitude below older studies (COI: AQR data, 21 markets) | 1973-2012 US (N-M and V) | **Yes, that is the point** | NBER https://www.nber.org/system/files/working_papers/w20721/w20721.pdf ; https://doi.org/10.1016/s0304-405x(03)00206-x ; https://doi.org/10.1111/j.1540-6261.2004.00656.x ; https://doi.org/10.2139/ssrn.3229719 | Verified (NBER Table 5; abstracts). Note: Novy-Marx discloses consulting for Dimensional |
| 18 | Moving averages across volatility-sorted stocks (Han, Yang, Zhou 2013) and the "trend factor" (Han, Zhou, Zhu 2016) | MA timing applied to portfolios sorted by volatility; combining moving averages of many lengths | **Mixed (in-sample, long-short).** H-Y-Z: high-volatility portfolios show large abnormal returns from MA timing, bigger than momentum. H-Z-Z: mixing short, medium, long averages "more than doubles" the Sharpe ratios of momentum and reversal factors; during the 2008 crisis it earned 0.75% a month while momentum lost 3.88% a month. Not a weekly-plus-daily test | US stocks | Not read | https://ideas.repec.org/a/cup/jfinqa/v48y2013i05p1433-1461_00.html ; https://ideas.repec.org/a/eee/jfinec/v122y2016i2p352-375.html | Verified (abstracts only) |
| 19 | Volatility-managed portfolios (Moreira and Muir 2017; Cederburg et al. 2020) | Hold less when recent volatility is high | **Weak out of sample.** M-M: large in-sample alphas. Cederburg et al. (103 strategies): managed versions do not systematically beat unmanaged ones, and realistic real-time versions earn lower Sharpe ratios. **Own comp. (no leverage, weight = min(1, 10% / last month's volatility)): 1927-2026 Sharpe 0.53 against 0.45, drawdown -44.7% against -83.7%; 2013-2026 Sharpe 0.91 against 0.91 with CAGR 10.4% against 15.0%.** Real-time Moreira-Muir version 2013-2026: 0.63 against 0.91 | 1926-2026 US stocks | Costs of 5 bps a turn barely matter | https://doi.org/10.1111/jofi.12513 ; https://ideas.repec.org/a/eee/jfinec/v138y2020i1p95-117.html ; script m3_volscale.py | Verified (abstracts); own numbers |
| 20 | Breakouts and volume | High trading volume as a signal; trading-range breaks | **Weak to Mixed, old evidence.** Gervais et al. 2001: stocks with unusually high volume over a day or week rose over the next month (visibility effect). Lee and Swaminathan 2000: past volume predicts the size and persistence of momentum; the 1998 working paper says high-volume winners beat plain momentum by 2% to 7% a year. Brock et al. found trading-range breaks useful on the Dow. No recent replication read | US stocks 1960s-1990s | Not shown | https://doi.org/10.1111/0022-1082.00349 ; https://doi.org/10.1111/0022-1082.00280 ; https://doi.org/10.1111/j.1540-6261.1992.tb04681.x | Verified (abstracts) |
| 21 | CAN SLIM (O'Neil) | Screen for growth stocks: strong earnings growth, price at or near new highs, volume surge, market uptrend | **Weak.** No independent replicated test found. (a) Lutey and Rayome 2022: author-built version, paper-traded Jul 2014-Feb 2017, 5 stocks, "outperforms" S&P 500 by 20%, Nasdaq 9%, Dow 17%; they stopped tracking in 2017; small journal, and not independent of the authors' own interpretation of the system. (b) AAII's screen since 1998: 19.2% a year price gain against 5.7% for the S&P 500 (AAII article, July 2023): methodology and costs not shown. (c) IBD-50 ETF (FFTY): $1 to $1.48 against SPY $4.43 since Apr 2015; -51% in 2022 (Yahoo) | 1998-2023 (AAII); 2014-2017 (Lutey); 2015-2026 (FFTY) | **No** for (a) and (b) | https://doi.org/10.33423/jaf.v22i2.5134 ; https://www.aaii.com/journal/article/68036-a-tribute-to-william-o-neil-revisiting-the-can-slim-strategy ; FFTY own comp. from Yahoo | (a) abstract verified; (b) UNVERIFIED (read through a summarizer, no method shown); (c) UNVERIFIED |
| 22 | Minervini trend template, Weinstein stage analysis, Darvas box | Book systems: price above rising 150/200-day (Minervini) or 30-week (Weinstein) averages, near 52-week highs, breakouts from bases or boxes | **Not testable as published** (they mix rules with discretionary chart reading). **None found** in the form of independent or replicated tests (Crossref search returned nothing relevant; search cap reached). Components map to items 05, 15 and 20. **Own comp. of Weinstein's 30-week filter alone on SPY: 7.7% against 10.9%, drawdown -42%** | n/a | n/a | Book claims only. Rule definitions above are from memory: UNVERIFIED, check the books before coding | Claim to test |
| 23 | Weekly trend filter plus daily entry | Trade daily breakouts only when the weekly trend is up | **None** for the combination. Levine and Pedersen show MA crossovers and time-series momentum are the same family of linear filters, so a second time frame is another filter on the same prices. **Own comp.: weekly 30-week filter + 20-day breakout entry, 10-day-low exit: SPY 5.4% a year, Sharpe 0.40 (200-day: 8.6%, 0.54); QQQ 3.5%, Sharpe 0.19.** It cut drawdown (SPY -14%) mainly by being invested only 46% of the time | 1993-2026 SPY, 2000-2026 QQQ | Yes, 5 bps a switch, 11 switches a year | https://doi.org/10.2469/faj.v72.n3.3 ; script d1_daily.py | Levine-Pedersen abstract verified; own numbers |
| 24 | Combining time horizons in trend following | Mix 1-, 3- and 12-month signals | **Mixed.** HOP Exhibit 2, gross Sharpe by signal, 1880-2016: 1-month 1.38, 3-month 1.19, 12-month 1.32; combined gross about 1.9 (my arithmetic: 18.0% / 9.7%). But costs took 7 points (18.0% to 11.0%), and in 2010-2016 the 1-month signal fell to **0.06** while the 12-month kept 0.73. Delaying the signal a month cut the 1-month Sharpe from 1.38 to 0.45 | 1880-2016; futures | Combined: partly | HOP PDF (item 02) | Verified (Exhibit 2) |
| 25 | Drawdown length | How long strategies stay under water | Diversified trend (HOP Ex. 8): worst -24.7%, 16 months down + 26 to recover; 2015-16 drawdown of -16.1% not recovered by the paper's end. Lempérière: typical drawdown lasts 1/S² years, so about 2 years at Sharpe 0.7, 4 years "not exceptional". **Own comp.: buy-and-hold US stocks 15.3 years under water (1929-1944); 10-month rule 6.8 years (1929-36), 2.1 years since 2007; SPY buy-and-hold 6.6 years (2000-06), QQQ 14.9 years; momentum long-short factor 24.4 years (1932-56) and still under water since Dec 2008 (17.8 years)** | Various | Various | HOP and CFM PDFs; own comp. | Verified (papers); own numbers |
| 26 | Survivorship and delisting bias | Tests on today's stocks leave out the failures | **Strong** (well established). Shumway 1997 and Shumway and Warther 1999 (as recorded in `reports/Why day traders lose.md`, AI-6; not re-checked by me). Norgate says it sells "survivorship bias-free data" for US, Australian and Canadian stocks. Ken French momentum deciles are CRSP-based (includes stocks that later vanished; delisting-return treatment not re-checked) | US stocks | n/a | https://norgatedata.com/ ; French library | Norgate line verified; the rest as noted |
| 27 | Taxes (US) | Capital gains rules for frequent switching | **Not a research question but a real cost.** More than one year held = long-term; one year or less = short-term. For tax years starting in 2025, long-term rates are 0%, 15% or 20%. Wash-sale rule: a loss is disallowed if you buy substantially identical securities within 30 days before or after the sale. **Own comp.: 74 in-market spells in 99 years; 62% lasted 12 months or less; median 8 months.** Faber (citing Gannon and Blum) says raising turnover from 20% to 70% cost under 0.5 point a year in taxes, UNVERIFIED | US taxpayer | n/a | https://www.irs.gov/taxtopics/tc409 ; https://www.irs.gov/publications/p550 | IRS pages verified (wash-sale text read directly) |
| 28 | Recent tests, 2023 to 2026 | Independent or new work | **Mixed.** Goyal 2026 (single-author preprint, code on GitHub): dual momentum with volatility targeting, Feb 2013-Jun 2026: lowers volatility and drawdown but does not beat 60/40 in any configuration; benefits not statistically significant; re-optimizing each year hurts. Paz 2026: independent replication of the SPY intraday-momentum strategy matches in sample (Sharpe 1.34) but out of sample (May 2024-Mar 2026) returned 9.4% against 29.5% buy-and-hold, Sharpe 0.39 (relevant to the minute-trading track). Abudy et al. 2023: moving-average distance signals work internationally after costs (preprint). Suominen and Hjalmarsson 2026 (preprint): equity time-series momentum breaks down near valuation extremes. Zarattini and Antonacci 2024 "A Century of Profitable Industry Trends": title only, abstract not read | 2013-2026 (Goyal); 2024-2026 (Paz) | Goyal: yes, turnover costs; others unknown | https://doi.org/10.2139/ssrn.7143882 ; https://doi.org/10.2139/ssrn.7290621 ; https://doi.org/10.2139/ssrn.4652949 ; https://doi.org/10.2139/ssrn.6867878 ; https://doi.org/10.2139/ssrn.4857230 | Abstracts verified; none peer reviewed as far as I could tell |
| 29 | 2022 and 2025-2026 | How the simple rules behaved | See section 2b (Q7). SPY 2022: buy-and-hold -18.2%; 200-day -12.5%; 30-week -17.4%; 10-month -21.1% (one marginal March re-entry). QQQ 2022: -32.6% against -16.4% / -21.2% / -7.2%. April 2025 and March-April 2026: all three sold, then re-bought 3% to 10% higher | 2022, 2025, 2026 | 5 bps a switch | Own comp. (d1_daily.py, m4_extra.py) | Own comp. |

---

### 2b. Short answers to the specific questions

**Q1. Did trend following work in 2020-2026?** Half and half. Trend funds gained in 2022 (ETF proxies +10% to +24%, UNVERIFIED) and are up 16.03% in 2026 to 28 Sep (SG Trend Index, verified), but lost in 2023 and early 2025 (SG Trend Index -9.3% by end-April 2025, verified). The SG note (May 2025) also says index members' returns differed by almost 15 points in 2024 even though they were 0.78 correlated, so which manager or rule speed you pick matters. A slower model did better in 2024 (SG note, verified).

**Q2. Momentum in 2020-2026?** Very lumpy (Ken French Mom factor, own comp.): 2020 -0.9%, 2021 -2.9%, 2022 +20.2%, 2023 -20.5%, 2024 +18.5%, 2025 -2.2%, 2026 to August +3.9% (first half +25.5%, then July-August -17.2%). Average 2.7% a year for 2020 to Aug 2026 with a Sharpe of 0.18.

**Q3. Does a weekly trend filter plus daily entry add value?** No evidence for it in the literature I could reach. The closest research (Han, Zhou, Zhu 2016) mixes many moving-average lengths inside a monthly, long-short stock portfolio and is in-sample. My own test says the combination gives up most of the return for a lower drawdown, and lands below the simple 200-day or 10-month rules on Sharpe ratio.

**Q4. Costs and taxes at low turnover.** For SPY and QQQ, costs are tiny: the 10-month rule changed position 1.5 times a year, the 200-day rule 6 to 7 times. Spread costs of 1 to 5 bps a switch are negligible against the 2% to 5% a year the rules give up in bull markets. Taxes are the real cost for a taxable account (item 27). The main protection is to run the rule in a tax-deferred account, if the owner ever goes live. Momentum stock baskets are different: turnover is high and costs took roughly 40% to 45% of the gross long-short profit in Novy-Marx and Velikov (0.26% to 0.35% a month against 0.62% to 0.77% gross), even with cost-saving tricks.

**Q5. Drawdowns and time under water.** See item 25. The honest description is: the rules shorten and shrink the worst bear markets but leave you under water for two to seven years in a real bear market, and they add a new kind of pain (lagging a rising market for years).

**Q6. Survivorship bias and what a fair stock test needs.** (1) A point-in-time list of who was in the universe on each date, including stocks later delisted, merged or bankrupt; (2) prices for those dead names, with the delisting return; (3) split and dividend adjustment; (4) a tradability filter (price, dollar volume); (5) realistic costs; (6) an untouched final period; (7) a count of every variant tried; (8) a random baseline with the same turnover; (9) results by sub-period and worst month, not only the average. Free daily bars for tickers that exist today do not meet (1) and (2); results would be too good. I could not verify whether Alpaca's free historical feed includes delisted tickers.

**Q7. 2022 and 2025-2026 in detail (own comp., SPY, adjusted closes).**
- 2022: SPY fell 24.5% from peak to trough (Jan to 12 Oct). The 200-day rule flipped on and off nine times between 21 Jan and 11 Apr, then stayed out from 11 Apr to 30 Nov (apart from a one-day flicker on 16 Aug). The 10-month rule re-entered on 31 Mar at 425.22 (SPY had just closed above its average of 418.90) and then lost 8.8% in April, so it ended 2022 at -21.1% against -18.2% for buy-and-hold. The same rule on the total US market ended -10.9% against -19.9%. One marginal signal decided the year.
- 2025: SPY fell 18.8% (close to close) into 8 April, then recovered. 200-day: out 10 Mar at 549.78, back 12 May at 573.48. 30-week: out 7 Mar at 564.82, back 16 May at 584.50. 10-month: out 31 Mar at 550.26, back 30 May at 579.77. Full year: SPY +17.7%, rules +11.8% / +14.4% / +12.6%.
- 2026 (to Aug): SPY fell 8.9% into 30 March, then rose 10.5% in April. 200-day: out 20 Mar at 645.30, back 8 Apr at 672.60. 30-week: out 13 Mar at 657.16, back 10 Apr at 676.04. 10-month: out 31 Mar at 647.06, **back 30 Apr at 715.04 (10.5% higher)**. Year to Aug: SPY +13.1%; rules +10.3% / +11.4% / +2.6%. The slower the rule, the more it cost.
- SPY closed at 765.61 on 28 Sep 2026, above its 200-day average of 715.29 (informational only, not advice).

---

## 3. What we can test with our data

**What we have:** cached SIP 1-minute bars for SPY and QQQ (Aug 2024 to Sep 2026), free Alpaca daily and minute bars from 2016 (verified: Alpaca's Basic plan lists "Since 2016", 200 calls a minute, IEX real-time, latest 15 minutes of SIP withheld, options "indicative" only), IEX live feed.

| Test | Feasible with our data? | Comment |
|---|---|---|
| 10-month, 200-day, 30-week rules on SPY and QQQ, 2016-2026 | **Yes** (Alpaca daily bars) | Only about five trend events (Q4 2018, 2020, 2022, April 2025, March-April 2026). Enough to check the code and costs, **not enough to rank the rules**: the ranking flipped between sub-periods in my longer test. Use a longer history for research (section 4C) and Alpaca for execution parity. |
| Same rules 1993/2000-2026 | Only with outside data (Yahoo worked in my sandbox for SPY from 1993; not an official API) | Cross-check Yahoo against Alpaca on the overlap 2016-2026 before trusting any longer series. |
| 12-1 momentum on 500+ stocks | **Not honestly.** We lack a survivorship-free universe and delisted prices | A test on today's S&P 500 members from 2016 is biased upward. If run, label it "upper bound". The Ken French decile files are the free stand-in I used. |
| Weekly + daily combination | Yes, but low priority | Already negative in my test. |
| Exposure-matched benchmark (same average time in market, but constant) | **Yes, essential** | Timing must beat a constant mix such as 73% stocks / 27% bills, or it is just holding less stock. Result: it beat it before 2013 and lost to it after 2013 (item 07). |
| Random-switching baseline (same number of switches at random dates) | Yes | The scalp lab already has this idea. Add it. |
| Options protection (puts) as an alternative to selling | **Not testable** | Options quotes are "indicative" only. |
| Minute bars (Aug 2024-Sep 2026) | Only as a data-quality check | Resample to daily and compare closes with Alpaca daily bars and Yahoo. Live IEX prices should not be used to compute a close-versus-average signal; use the SIP daily bar after the close (available free once older than 15 minutes). |
| Forward paper test | **Cannot prove anything** | A 10-month rule makes 1 to 2 trades a year. 60 sessions is about 3 months. |

**Suggested order of work (counting every variant under MT-G7):**
1. Data QA: Alpaca daily SPY/QQQ against Yahoo and against the minute-bar cache.
2. Pre-register the rule set in section 4A (no more than five rules, fixed parameters), test once on 2016-2026 (Alpaca) and once on the long history, report the number of variants.
3. Add the exposure-matched and random-switching baselines and the worst-year table.
4. Only after that, consider a shadow-mode 12-1 momentum scan, and only with survivorship-free data.

---

## 4. Recommendations for the agent design

### 4A. The 3 to 5 long-horizon rules with the best evidence, and what they honestly delivered

All figures are own computations unless marked. "B&H" = buy and hold. Costs: 5 to 10 bps a switch; no taxes.

| Rule | Best evidence | Honest performance | When it lagged |
|---|---|---|---|
| **R1. 10-month average on a broad stock index (Faber)** | Faber 2013 (author-run); Hurst et al. for the general idea; Zakamulin as the critic | US market 1927-Aug 2026: 9.8% against 10.3% B&H; volatility 12.5% against 18.4%; Sharpe 0.55 against 0.45; worst loss -43% against -84%. SPY 1993-2026: 9.6% against 10.9%, Sharpe 0.59 against 0.51, worst -24.8% against -55.2% | 44 of 98 years; 1990s (Jan 1995 to Mar 2000: x2.93 against x3.52); since Apr 2009 x5.6 against x13.2; 2019 (8.9% against 30.6%), 2023 (9.2% against 26.7%), 2026 to Aug (2.6% against 12.7%) |
| **R2. 200-day average on SPY or QQQ** | Practitioner standard; same family as R1 | SPY 1993-2026: 8.6% against 10.9%; Sharpe 0.54 against 0.51; worst -24.5% against -55.2%; 6.5 switches a year. QQQ 2000-2026: 8.3% against 8.6%; Sharpe 0.44 against 0.37; worst -50% against -83% | QQQ 2010-2019: 8.1% a year against 17.9%; SPY 2007-2019: 6.4% against 8.7%; many false exits in 2022 |
| **R3. 12-month absolute (time-series) momentum on a few broad ETFs** | Moskowitz et al. 2012; Hurst et al. 2017; critique by Huang et al. 2020 | US stocks 1927-2026: 10.0%, Sharpe 0.56, worst -44%. Five-asset ETF version 2007-2026: 5.5% a year, Sharpe 0.56, worst -11% (60/40: 8.2%, 0.69, -30%; SPY 11.0%, 0.62, -51%) | Bull markets; 2013-2019 for the five-asset version (about 4.6% a year against 14.6% for SPY) |
| **R4. Volatility-scaled exposure (risk targeting, no leverage)** | Moreira and Muir 2017, but Cederburg et al. 2020 show real-time gains vanish | US stocks: Sharpe 0.53 against 0.45 (1927-2026), drawdown -44.7% against -83.7%; since 2013 same Sharpe (0.91) but 10.4% against 15.0% CAGR | Any long bull market |
| **R5. 12-1 momentum, long-only top decile/quintile of large stocks, monthly, with a market filter** (volatility scaling of the long-only version is untested) | Jegadeesh and Titman 1993; costs by Novy-Marx and Velikov; crashes by Daniel and Moskowitz | Top decile (value-weighted, gross) 1993-Aug 2026: 14.7% against 11.0% market, but Sharpe 0.63 against 0.60 and volatility 22% against 15%. With the market filter: 13.5%, Sharpe 0.67, worst -27.8%. Live: MTUM x1.16 and SPMO x1.50 against SPY, QMOM x0.70 | 2021 (-28.8 points against market), 2025 (-13.1 points), Jul-Aug 2026 (-15.5% while the market rose 2.6%). **Needs survivorship-free stock data to be tested by us at all** |

Honest expectation for a beginner: R1 to R4 will most often **look worse than buying SPY**, and will look better only in the 1 to 3 years of a long bear market. R5 is the only one that might add return, and it has the highest costs, the biggest crash risk and the weakest data situation for us.

### 4B. Exact, look-ahead-free definitions (daily and weekly bars)

**Conventions for every rule**
- Prices: split- and dividend-adjusted **daily closes**. Signal for day t uses only closes up to and including day t.
- Timing: compute after the close; send the order for **day t+1's regular-session open** (limit order with a collar, MT-G21). Never assume a fill at the close that made the signal (Faber's paper does; it is optimistic).
- Position: 100% in the ETF or 0% (Treasury-bill ETF such as SHY or BIL, or cash). No leverage, no shorting.
- Signals change only at the stated frequency; nothing is checked in between.
- Parameters marked **conventional** were not tuned by anyone here; marked **mine** are my choices and count as variants.

| ID | Frequency | Rule (long only) | Parameters |
|---|---|---|---|
| R1 | Last trading day of each month | ON if the month-end adjusted close is above the simple average of the last 10 month-end closes (including this one); else OFF | 10 months: **conventional** (Faber; about 200 trading days) |
| R2 | Every trading day | ON if today's adjusted close is above the simple average of the last 200 daily closes (including today); else OFF | 200 days: **conventional** |
| R3 | Last trading day of each week | ON if this week's close is above the average of the last 30 weekly closes; else OFF | 30 weeks: **conventional** (Weinstein). It performed worst of the three in my SPY test, so treat it as a comparison, not a favorite |
| R4 | Last trading day of each month | ON if the 12-month total return of the ETF exceeds the 12-month return of Treasury bills; else OFF | 12 months: **conventional** (Moskowitz et al.) |
| R4b | Last trading day of each month, across a small basket (for example SPY, EFA, IEF, VNQ, DBC) | Each ETF is its own on/off switch with 1/5 of the money, using the R1 test on that ETF's own prices (this is the version I tested) or the R4 test; OFF slices go to SHY | Equal weights: **mine** |
| R5 | Last trading day of each month | Universe: index members on that date (point-in-time), price at least $5, minimum dollar volume. Score = price one month ago divided by price 12 months ago, minus 1 (skips the latest month). Hold the top decile equal-weighted; keep a current holding until it drops below the top 30% (buy/hold band). If R1 on SPY is OFF, hold cash. **Optional, untested for long-only:** scale total exposure by min(1, 12% divided by the annualized volatility of the strategy's own last 126 daily returns) | 12-1 and decile: **conventional** (Jegadeesh-Titman, Carhart). 30% band, 126 days and 12% target: **mine** |

The weekly-filter-plus-daily-breakout combination (ON when the 30-week flag is on and the close exceeds the highest close of the previous 20 days; OFF on a close below the lowest close of the previous 10 days or when the weekly flag turns off) was tested and is **not recommended**.

### 4C. Data we would need

Alpaca's free feed starts in 2016 (verified). That is ten years and about five trend events. For research we need decades.

| Source | What it gives | Terms and limits (as read) | Reliability notes |
|---|---|---|---|
| Alpaca (in use) | Daily and minute US stock/ETF bars since 2016 | Free Basic plan: since 2016, 200 calls/min, latest 15 minutes of SIP withheld (verified) | Good for execution parity; too short for validation. Delisted-ticker coverage UNVERIFIED |
| Ken French data library | US market return, momentum factor and momentum deciles, monthly and daily, 1926/1927 to Aug 2026 | Free download; "Copyright Eugene F. Fama and Kenneth R. French" (verified). Cite them | Best free long series. Portfolios, not tradable single stocks. Monthly files updated with a lag; latest months may be revised |
| Yahoo Finance chart endpoint | SPY from 1993, S&P 500 index from 1970 (in my pull), Nasdaq Composite from 1971 | Unofficial endpoint, no published service terms; it worked from my sandbox | Use only as a cross-check. Adjusted-price quirks are known (UNVERIFIED). Mostly survivors |
| Tiingo | End-of-day history 30+ years | Free plan: 50 requests/hour, 1,000/day, 500 unique symbols/month, personal use only; Power plan $30 a month (page read through the fetch tool) | Reasonable for a few hundred symbols. Delisted coverage UNVERIFIED |
| Massive (formerly Polygon) | Stocks history | Free Basic: 5 calls/min and 2 years; paid $29 to $199 a month, top tier "20+ years" (page read through the fetch tool) | Free tier too short |
| Alpha Vantage | Daily prices | Free: 25 API requests a day (verified) | Too small for a 500-stock scan |
| Robert Shiller data | Monthly US stock data from 1871 | Free download (verified). Price is the **monthly average of daily closes** (verified) | Averaging blurs signals and looks ahead within the month; do not use for month-end rules |
| FRED | S&P 500 index | Only 10 years of daily history for S&P series, by license (verified) | Not useful for long history |
| Norgate Data | US stocks with delisted names and index history | Says "survivorship bias-free data for US, Australian and Canadian stock markets" (verified); price and depth not read | The kind of source a stock-level test needs; paid |
| Stooq | Free daily CSVs | Could not reach it from my sandbox (connection reset) | UNVERIFIED |
| CRSP (via a university) and Sharadar | Gold standard / survivorship-free stock prices | Not checked | For a serious stock test |

### 4D. What an AI agent could plausibly do better than a person, and what it cannot

**Plausibly better (discipline and bookkeeping, not prediction):**
- Scan 500+ stocks after every close for the same rule, with no boredom, no gut feeling and no chasing of the day's top gainers.
- Rebalance on the stated day, at the stated time, with limit orders and collars, and log every skipped signal.
- Apply a drawdown rule or a volatility scale the same way every time, and never widen a stop.
- Keep an honest record: the count of rule variants tried, the exposure-matched benchmark, the random-switching baseline, and the worst month.
- Check data (Alpaca against a second source) and refuse to trade on a missing bar.
- Track tax lots and the 30-day wash-sale window in code, if it ever trades a taxable account.

**Cannot do:**
- Create an edge by "reading charts". I found no evidence that an AI reading chart images or patterns adds value. What earns anything here is a simple rule that code applies.
- Tell a whipsaw from a real bear market in advance. No rule can: April 2025 and April 2026 looked exactly like the start of a slide.
- Forecast momentum crashes reliably; Daniel and Moskowitz say they are only "partly forecastable".
- Repair missing history. It cannot make a survivor-only dataset survivorship-free.
- Prove a long-horizon rule in weeks of paper trading.
- Be trusted with numbers: code computes every number, and an LLM may only veto a trade (MT-G29). An LLM-run backtest can also "remember" the past (AI-11 in the repo).

### 4E. Design advice

**Include**
- A slow **trend-state module** for SPY and QQQ (R1 and R2, optionally R4b), written as a pure function of past closes, logged daily, run in **shadow mode first**.
- A **monthly review** report: state, number of switches this year, cost per switch measured against the quote, position versus the exposure-matched benchmark.
- **Pre-registration**: write the rule set, parameters and pass tests down before the run, with the variant count.
- The **exposure-matched** and **random-switching** baselines.
- A hard rule that the bot never uses leverage, shorts, options or social media/hype for this lane (MT-G23, MT-G24, MT-G28).
- A "no signal change while data is stale or a bar is missing" rule.

**Avoid**
- Searching for the best moving-average length. My own comparison shows the winner changes by sub-period (MT-G7).
- Fast trend signals (a few days to one month). Lempérière found 3-day trends withered after 1990, and Hurst et al. show the 1-month signal fell to a Sharpe of 0.06 in 2010-2016 while the 12-month signal held at 0.73. (The 200-day rule is slow and is not in this category.)
- Single-stock breakout trading from CAN SLIM, Minervini, Weinstein or Darvas until survivorship-free data and a pre-registered test exist.
- Any momentum stock basket without a crash control (market filter plus volatility scaling), and without measured costs.
- Trusting Yahoo or a summarized web page for anything that sets a signal.
- Reading a good paper-trading month or year as proof.

**Test first**
1. R1 and R2 on SPY and QQQ with next-open execution, Alpaca 2016-2026 plus a longer cross-checked history.
2. Exposure-matched benchmark and random switching.
3. Only then R4b, and last R5 (needs new data).

**What to tell the beginner (plain English)**
- A trend rule is **insurance**, not a money machine. You pay for it in most years, and it pays out in a few.
- Expect to **lag** simply owning SPY in most bull years. On US stocks since 1927 the 10-month rule lagged in 44 of 98 years, and since 2009 it made less than half as much.
- Expect **several false alarms** a year on the faster rules (April 2025 and April 2026 both sold low and bought back higher).
- The rule can be tested on history, but **a 60-session paper run cannot prove it**; it may make only one or two trades.
- **Momentum stocks** can be great for a year and then lose 15% in two weeks while the index does nothing (July-August 2026).
- **Costs and taxes matter more for frequent switching.** In a US taxable account, most holding periods are under a year, so gains are taxed as ordinary income (short-term).
- Anything that says "a trader made 155% a year" in a book or on YouTube is a claim to test, not evidence.

---

## 5. Open questions and things I could not verify

1. **Search cap.** The web-search tool stopped at 200 calls. Missing: a proper hunt for (a) independent or replicated tests of CAN SLIM, Minervini's trend template, Weinstein stage analysis and Darvas boxes, (b) independent US replications of the 52-week-high effect after 2004, (c) any test of "weekly trend + daily entry" in journals. I used Crossref, RePEc, arXiv and direct fetches instead. Absence in my results is **not** proof of absence.
2. **SG Trend Index calendar-year returns for 2020-2024** were not obtained (SocGen and Top Traders Unplugged pages blocked). Only April 2025 (-4.9%, -9.3% year to date, verified in SG's May 2025 note) and 28 Sep 2026 (+16.03% year to date, "estimated", verified on BarclayHedge) are verified. Mid-2025 figures (June +1.52%, 12-month -15.05%) came from a search snippet and are UNVERIFIED.
3. **July-August 2026 momentum crash:** the factor numbers are read straight from Ken French's library (file made from the 202608 CRSP database) and are verified as data. The story (Goldman index, trigger, crowding, leverage) comes from a Substack summary of Goldman commentary and other blogs: UNVERIFIED. French data can be revised.
4. **Yahoo-based numbers** (SPY/QQQ rule tests, ETF track records) rely on an unofficial endpoint. I did not compare against Alpaca or issuer fact sheets. The FFTY index rules and whether they changed were not checked.
5. **AAII's CAN SLIM screen**: figures read through a summarizer of AAII's own article; methodology (price only? costs? number of stocks?) not shown. The 5.7% S&P figure looks like price-only, which suggests AAII's 19.2% is also price-only.
6. **Practitioner rule definitions** (Minervini's eight criteria, Weinstein's stages, Darvas boxes) are from memory, not from the books. Do not code from this report.
7. **Papers read only as abstracts:** McLean-Pontiff, Moreira-Muir, Hou-Xue-Zhang, Han-Yang-Zhou, Han-Zhou-Zhu, Huang et al., Cederburg et al., Bajgrowicz-Scaillet, Zakamulin, Marshall et al., Park-Irwin, Brock et al., Gervais et al., Lee-Swaminathan, Levine-Pedersen, Lesmond et al., Korajczyk-Sadka, Frazzini et al., Da-Gurun-Warachka, Jegadeesh-Titman 2023, the 2023-2026 preprints. Sample periods for some are therefore unknown. Sullivan et al. 1999: abstract read only in part.
8. **Whether Alpaca's free historical feed covers delisted tickers**, and how Alpaca adjusts daily bars for dividends (the `adjustment` parameter), were not verified.
9. **Ken French delisting-return treatment** in the decile files was not re-checked.
10. **Tax:** US federal rules only, for tax years starting in 2025 (the IRS page shows 2025). Not tax advice. State tax, non-US rules and the owner's situation are unknown.
11. **Parameter and window choice.** My sub-periods (2007-, 2013-, 2020-) were picked after seeing the data. Roughly 30 variants were run. Please treat my numbers as descriptive.
12. **Open scientific questions:** whether trend rules on large-cap equity indexes have simply lost their edge since 2009 (a bull market with sharp V-shaped dips) or are just in a long drought (Lempérière: flat spells of 4 years "not exceptional"); whether high valuations (Suominen and Hjalmarsson, preprint) make trend rules unreliable now.
13. **Environment note.** I installed the PyMuPDF package inside the sandbox to read PDFs, and wrote scripts and downloads only under the research folder. Nothing in the repo changed.

---

## 6. Sources

Read in full or in the parts that matter (PDF or official page):
1. Moskowitz, Ooi, Pedersen (2012), Time series momentum, J. Financial Economics 104, 228-250. https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
2. Hurst, Ooi, Pedersen (2017), A Century of Evidence on Trend-Following Investing, J. Portfolio Management. https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-JPM-Fall-2017.pdf
3. Faber (2007; updated Feb 2013), A Quantitative Approach to Tactical Asset Allocation. https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf
4. Lempérière, Deremble, Seager, Potters, Bouchaud (2014), Two centuries of trend following. https://arxiv.org/abs/1404.3274
5. Jegadeesh and Titman (1993), J. Finance 48(1), 65-91. https://www.bauer.uh.edu/rsusmel/phd/jegadeesh-titman93.pdf
6. Daniel and Moskowitz (2016), Momentum crashes (NBER w20439; J. Financial Economics 122(2) 221-247). https://www.nber.org/system/files/working_papers/w20439/w20439.pdf
7. Novy-Marx and Velikov (2016), A Taxonomy of Anomalies and Their Trading Costs (NBER w20721; Review of Financial Studies 29(1) 104-147). https://www.nber.org/system/files/working_papers/w20721/w20721.pdf
8. George and Hwang (2004), The 52-Week High and Momentum Investing, J. Finance 59(5), 2145-2176. https://www.bauer.uh.edu/tgeorge/papers/gh4-paper.pdf
9. Société Générale, CTA Industry Update, May 2025. https://content.sgmarkets.com/CTA_UPDATE_KEEPING_UP_WITH_THE_TRENDFOLLOWERS_2025
10. BarclayHedge, SG Trend Index page (estimated performance as of 28 Sep 2026). https://portal.barclayhedge.com/cgi-bin/indices/displayHfIndex.cgi?indexCat=SG-Prime-Services-Indices&indexName=SG-Trend-Index
11. Kenneth French data library (files created from the 202608 CRSP database): F-F_Research_Data_Factors, F-F_Momentum_Factor, 10_Portfolios_Prior_12_2, daily versions. https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
12. IRS Topic 409, Capital gains and losses. https://www.irs.gov/taxtopics/tc409 ; IRS Publication 550 (2025), Wash sales. https://www.irs.gov/publications/p550
13. Alpaca, About Market Data API (plans). https://docs.alpaca.markets/us/docs/about-market-data-api ; Market Data FAQ. https://docs.alpaca.markets/us/docs/market-data-faq

Abstract or official record verified (through Crossref or RePEc):
14. McLean and Pontiff (2016), J. Finance 71(1), 5-32. https://doi.org/10.1111/jofi.12365
15. Moreira and Muir (2017), J. Finance 72(4), 1611-1644. https://doi.org/10.1111/jofi.12513
16. Hou, Xue, Zhang (2020), Replicating Anomalies, Rev. Financial Studies 33(5), 2019-2133. https://doi.org/10.1093/rfs/hhy131
17. Jacobs and Müller (2020), J. Financial Economics 135(1), 213-230. https://ideas.repec.org/a/eee/jfinec/v135y2020i1p213-230.html
18. Huang, Li, Wang, Zhou (2020), J. Financial Economics 135(3), 774-794. https://ideas.repec.org/a/eee/jfinec/v135y2020i3p774-794.html
19. Cederburg, O'Doherty, Wang, Yan (2020), J. Financial Economics 138(1), 95-117. https://ideas.repec.org/a/eee/jfinec/v138y2020i1p95-117.html
20. Han, Yang, Zhou (2013), J. Financial and Quantitative Analysis 48(5), 1433-1461. https://ideas.repec.org/a/cup/jfinqa/v48y2013i05p1433-1461_00.html
21. Han, Zhou, Zhu (2016), A trend factor, J. Financial Economics 122(2), 352-375. https://ideas.repec.org/a/eee/jfinec/v122y2016i2p352-375.html
22. Bajgrowicz and Scaillet (2012), J. Financial Economics 106(3), 473-491. https://ideas.repec.org/a/eee/jfinec/v106y2012i3p473-491.html
23. Zakamulin (2014), J. Asset Management 15(4), 261-278 (abstract read from the SSRN version). https://doi.org/10.2139/ssrn.2242795
24. Marshall, Nguyen, Visaltanachoti (2017), Quantitative Finance 17(3), 405-421 (SSRN abstract). https://doi.org/10.2139/ssrn.2225551
25. Park and Irwin (2007), J. Economic Surveys 21(4), 786-826. https://doi.org/10.1111/j.1467-6419.2007.00519.x
26. Brock, Lakonishok, LeBaron (1992), J. Finance 47(5), 1731-1764. https://doi.org/10.1111/j.1540-6261.1992.tb04681.x
27. Sullivan, Timmermann, White (1999), J. Finance 54(5), 1647-1691 (abstract read in part). https://doi.org/10.1111/0022-1082.00163
28. Gervais, Kaniel, Mingelgrin (2001), J. Finance 56(3), 877-919. https://doi.org/10.1111/0022-1082.00349
29. Lee and Swaminathan (2000), J. Finance 55(5), 2017-2069. https://doi.org/10.1111/0022-1082.00280
30. Levine and Pedersen (2016), Which Trend Is Your Friend?, Financial Analysts Journal 72(3), 51-66. https://doi.org/10.2469/faj.v72.n3.3
31. Lesmond, Schill, Zhou (2004), J. Financial Economics 71(2), 349-380. https://doi.org/10.1016/s0304-405x(03)00206-x
32. Korajczyk and Sadka (2004), J. Finance 59(3), 1039-1082. https://doi.org/10.1111/j.1540-6261.2004.00656.x
33. Frazzini, Israel, Moskowitz (2018), Trading Costs (SSRN). https://doi.org/10.2139/ssrn.3229719
34. Barroso and Santa-Clara (2015), Momentum has its moments, J. Financial Economics 116(1), 111-120 (title and description in item 6 only). https://doi.org/10.1016/j.jfineco.2014.11.010
35. Jegadeesh and Titman (2023), Momentum: Evidence and insights 30 years later, Pacific-Basin Finance J. 82, 102202 (abstract only). https://doi.org/10.1016/j.pacfin.2023.102202
36. Da, Gurun, Warachka (2014), Frog in the Pan (SSRN abstract). https://doi.org/10.2139/ssrn.2370931
37. Lutey and Rayome (2022), Live out-of-sample testing of CAN SLIM, J. Accounting and Finance 22(2). https://doi.org/10.33423/jaf.v22i2.5134
38. Raju (2023), The 52-week high effect and momentum investing: evidence from India (SSRN preprint). https://doi.org/10.2139/ssrn.4587697
39. Goyal (2026), When does risk-managed momentum add value? (SSRN preprint). https://doi.org/10.2139/ssrn.7143882
40. Paz (2026), Out-of-sample evaluation of an intraday momentum strategy for SPY (SSRN preprint). https://doi.org/10.2139/ssrn.7290621
41. Abudy, Kaplanski, Mugerman (2023), Market timing with moving average distance (SSRN preprint). https://doi.org/10.2139/ssrn.4652949
42. Suominen and Hjalmarsson (2026), Boundaries of time series momentum (SSRN preprint). https://doi.org/10.2139/ssrn.6867878
43. Zarattini and Antonacci (2024), A Century of Profitable Industry Trends (SSRN; title only). https://doi.org/10.2139/ssrn.4857230

Secondary, blogs, vendor pages and unofficial data (treat as UNVERIFIED unless stated):
44. AAII (July 2023), A Tribute to William O'Neil. https://www.aaii.com/journal/article/68036-a-tribute-to-william-o-neil-revisiting-the-can-slim-strategy
45. LLMQuant Substack, "22% Gone in Five Weeks" (July 2026 momentum crash). https://llmquant.substack.com/p/22-gone-in-five-weeks-what-actually
46. Yahoo Finance public chart endpoint (SPY, QQQ, ^GSPC, ^IXIC, EFA, IEF, VNQ, DBC, SHY, MTUM, SPMO, QMOM, FFTY, DBMF, KMLM, CTA), pulled 28 Sep 2026. https://query1.finance.yahoo.com/v8/finance/chart/SPY
47. Tiingo pricing https://www.tiingo.com/about/pricing ; Massive (formerly Polygon) pricing https://massive.com/pricing ; Alpha Vantage premium page https://www.alphavantage.co/premium/ ; FRED SP500 https://fred.stlouisfed.org/series/SP500 ; Shiller data https://shillerdata.com/ ; Norgate https://norgatedata.com/ (all read through the fetch tool).
48. Repo notes used for context, not re-verified: `MINUTE_TRADING.md`, `reports/Why day traders lose.md` (AI-6, AI-8, AI-11, AI-18), `reports/Minute trading backtest results.md`.

Own scripts and outputs (this folder): `lib.py`, `m1_monthly_market.py`, `m2_momentum.py`, `m3_volscale.py`, `m4_extra.py`, `d1_daily.py`, `g1_gtaa.py`, `e1_etfs.py`, `out_m1.txt`, `out_m2.txt`, `out_m3.txt`, `out_d1.txt`; downloaded PDFs in `pdf/`, data in `data/`.
