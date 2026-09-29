# Value, Quality, Factor and Mean-Reversion Strategies (for a ~$1k–$25k retail account, daily cadence)

Research date: 2026-09-26. Sixteen web searches and fetches. alphaarchitect.com and quantifiedstrategies.com were blocked by the network proxy, so claims from those sites rely on search-result snippets only. Rules marked "book summary" are my own paraphrase of the named book and have no web source. Check them against the book before coding.

---

## Q0. Cross-cutting evidence: how much do published anomalies decay?

### Takeaway
Expect a published anomaly to earn about half of its backtested premium once it is live. Costs cut into it further, especially for small caps and high-turnover rules.

### Cited Findings
- McLean & Pontiff (J. Finance 2016) studied 97 return predictors. Portfolio returns were 26% lower out-of-sample (before publication but after the sample ended) and 58% lower after publication. That leaves about 32 points attributable to publication-informed trading. — [Wiley JF](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623); summary in [arXiv 2512.11913](https://arxiv.org/html/2512.11913v1)
- A later study of 72 factors (Falck et al. 2021, as cited) found that publication year explains about 30% of the variance in Sharpe-ratio decay. — [arXiv 2512.11913](https://arxiv.org/html/2512.11913v1) (secondary citation)
- An international study, "Anomalies across the globe: once public, no longer existent?" (JFE), examines the same question outside the US. — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0304405X19301618)

### Inferences
- Rule of thumb for planning: take the headline backtest, halve the excess return, then subtract realistic costs.

### Gaps
- I did not fetch the international paper's exact decay figure.

---

## Q1. Benjamin Graham: defensive-investor screens and net-nets

### Takeaway
Net-nets have spectacular historical returns, but the stocks are tiny, illiquid and scarce in the US. That makes them feasible for a small account but high-risk and hard to backtest cleanly. The defensive screens are a sensible quality/value filter with no strong standalone academic evidence.

### Rules precise enough to code (book summary of *The Intelligent Investor*, ch. 14; no URL)
Defensive-investor screen, applied annually:
- Adequate size (Graham's dollar threshold was set in the 1970s, so inflate it; a practical modern proxy is market cap above about $2B).
- Strong finances:
  - Industrials: current ratio of at least 2, and long-term debt no larger than net current assets.
  - Utilities: debt no more than 2x equity.
- Earnings stability: positive EPS in each of the past 10 years.
- Dividend record: uninterrupted dividends for at least 20 years.
- Earnings growth: 10-year EPS growth of at least one-third, using 3-year averages at the start and end of the period.
- Moderate valuation: P/E of 15 or less on 3-year average earnings, P/B of 1.5 or less, and P/E × P/B of 22.5 or less.
- Hold a diversified basket of 10–30 names and rebalance annually.

Net-net (NCAV) rule:
- NCAV = current assets − total liabilities (preferred stock is also subtracted in some versions).
- Buy when market cap is at most two-thirds of NCAV.
- Hold about 1 year, or sell earlier when price reaches NCAV.
- Diversify across 20–30 or more names.

### Cited Findings
- Oppenheimer (1986) used the two-thirds-of-NCAV rule on 645 net-nets over 13 years, with 18–89 stocks per year. The portfolio averaged 29.4% a year versus 11.5% for the NYSE-AMEX index. — [ResearchGate: Testing Graham's NCAV model](https://www.researchgate.net/publication/282969845_Testing_Benjamin_Graham's_net_current_asset_value_model); [GuruFocus](https://www.gurufocus.com/news/488854/testing-grahams-net-current-asset-value-strategy-part-1)
- Carlisle, Mohanty & Oxman (2010) covered US stocks from 1983 to 2008. Net-nets averaged 35.3% a year, beating the market by 22.4% a year. — same sources
- Other US tests: Vu (1988), Lauterbach & Vu (1993), An et al. (2015). There is also a London test. — [ResearchGate](https://www.researchgate.net/publication/282969845_Testing_Benjamin_Graham's_net_current_asset_value_model); [Alpha Architect London analysis](https://alphaarchitect.com/an-analysis-of-testing-benjamin-grahams-net-current-asset-value-strategy-in-london/) (not fetched)
- Quantpedia has a critical review of the NCAV rule. — [Quantpedia](https://quantpedia.com/a-closer-look-at-ben-grahams-net-current-asset-value-ncav-rule/) (not fetched)

### Inferences
- **Flag:** These are equal-weighted returns on micro-caps. They are very likely overstated by bid-ask spreads, price impact and possibly delisting or survivorship handling.
- In most years in recent decades, only a handful of US net-nets exist. Many are foreign-domiciled (for example Chinese reverse mergers) or OTC-traded, which adds fraud and governance risk.
- A $1k–$25k account can actually trade these illiquid names, which institutions cannot. That is one of the few real edges a small account has. But 20+ positions at $1k total means $50 lots, which fractional shares cannot fix for OTC stocks.
- Daily cadence adds nothing. Monitoring is quarterly or annual.

### Gaps
- No reliable post-2010 US net-net performance series that includes costs was found.
- Drawdown data was not retrieved. Micro-caps fell well over 50% in 2008, but I found no source specific to net-nets.

---

## Q2. Greenblatt Magic Formula

### Takeaway
It worked in its 1988–2004 backtest and for some years after publication. It has lagged the S&P 500 for much of the past decade, which fits with value's poor run and with the formula being well known.

### Rules (from Greenblatt's *The Little Book That Beats the Market*; summarized on Wikipedia)
- Universe: US stocks with market cap above about $50–100M (Greenblatt's site uses above $50M). Exclude utilities and financials, and exclude ADRs.
- Measures:
  - Earnings yield = EBIT / Enterprise Value.
  - Return on capital = EBIT / (net working capital + net fixed assets).
- Rank all stocks on each measure, add the two ranks, and buy the top 20–30 names.
- Build the portfolio gradually: buy 2–3 names a month over the first year.
- Hold each position about 1 year. For taxes, sell losers just before 1 year and winners just after.
- Source: [Wikipedia: Magic formula investing](https://en.wikipedia.org/wiki/Magic_formula_investing)

### Cited Findings
- The original backtest (1988–2004) showed about 30.8% a year versus about 12.3% for the S&P 500. — [Wikipedia](https://en.wikipedia.org/wiki/Magic_formula_investing)
- Out-of-sample studies:
  - Europe, 2000–2010 (Persson & Selander): outperformance in several countries, varying by country.
  - Finland (2016): higher risk-adjusted returns.
  - Sweden: outperformance over 2005–2015 and 2007–2017.
  - Source: [Wikipedia](https://en.wikipedia.org/wiki/Magic_formula_investing); [Poznań literature review](https://www.journals.ue.poznan.pl/REF/article/view/2790)
- A practitioner source says the strategy did very well in the 2000s but has lagged the market for more than 10 years. — [QuantifiedStrategies (search snippet; site blocked)](https://www.quantifiedstrategies.com/the-magic-formula-strategy/)
- A lower-quality blog claims live replications confirmed alpha through about 2017, followed by weakness ("stopped working in 2024"). — [invest-like blog](https://invest-like.com/blog/why-magic-formula-stopped-working-2024/) (unvetted source; treat as anecdotal)
- Erasmus thesis "Unravelling the magic of Magic Formula investing". — [EUR thesis](https://thesis.eur.nl/pub/65582/MasterThesis_MartijnKreft_474788.pdf) (not fetched)
- Related academic variant: Conservative Formula (low volatility + momentum + payout), by van Vliet / Robeco. — [Wikipedia](https://en.wikipedia.org/wiki/Conservative_Formula_Investing)

### Inferences
- **Flag:** The original backtest used equal-weighted small caps and did not report costs.
- The formula mostly repackages value and quality exposure. Its 2010s underperformance tracks the value drawdown.
- Suitability: feasible with 20–30 names at $5k+ using fractional shares. Turnover is low (annual), so costs are small. There is no benefit to daily cadence.

### Gaps
- No peer-reviewed US post-2005 study with costs and a drawdown figure was retrieved. Magic Formula drawdowns in 2008 were reportedly worse than the S&P 500's, but I have no source for that.

---

## Q3. Piotroski F-Score

### Takeaway
The original 2000 result was strong within cheap (high book-to-market) stocks. Straight replications of the long–short version show losses over the last 10–20 years. As a quality filter inside a value portfolio it still captures known factors, but it has little standalone alpha.

### Rules (Piotroski 2000; [Wikipedia](https://en.wikipedia.org/wiki/Piotroski_F-score))
Score 9 binary signals, 1 point each:
- Profitability:
  - ROA > 0
  - Cash flow from operations > 0
  - ΔROA > 0
  - Accruals: CFO > net income
- Leverage and liquidity:
  - Δ(long-term debt / assets) < 0
  - Δ current ratio > 0
  - No new equity issued
- Efficiency:
  - Δ gross margin > 0
  - Δ asset turnover > 0

Portfolio construction:
- Universe: the top book-to-market quintile.
- Buy scores of 8–9. The short side (scores 0–1) is optional.
- Rebalance annually after 10-K filings.

### Cited Findings
- A Portfolio123 replication on Compustat, using Piotroski's original criteria, found that long high-F / short low-F lost about −9.53% a year over the last 10 years and −11.75% a year over the last 20. — [Portfolio123 blog](https://blog.portfolio123.com/why-piotroskis-f-score-no-longer-works/) (practitioner, not peer-reviewed)
- Piotroski himself warned about data-snooping, since the signals were chosen with knowledge of prior research. — [UCLA F-Score PDF](https://www.anderson.ucla.edu/documents/areas/prg/asam/2019/F-Score.pdf)
- A 2024 study (Review of Quantitative Finance and Accounting) tested the F-score and similar formulas on US data from 1963 to 2022. All of them earned significant raw and risk-adjusted returns, mainly through exposure to established style factors, and no single formula dominated. — [Springer RQFA 2024](https://link.springer.com/article/10.1007/s11156-024-01331-y)
- Australian evidence exists. — [ResearchGate](https://www.researchgate.net/publication/301600517_The_Piotroski_F_-score_evidence_from_Australia)

### Inferences
- Use it as a filter (for example, require F ≥ 7) on top of a value screen. Do not use it as a standalone signal.
- It is low-turnover and suits a small account.

### Gaps
- No drawdown figures were retrieved.

---

## Q4. Fama-French factors, quality, low volatility / BAB, and value's drawdown and recovery

### Takeaway
Value (HML) went through its worst drawdown on record from about 2007 to 2020. It rebounded in 2021–22, then recovered strongly outside the US in 2025, while US large-cap growth kept leading over 5-year windows. Profitability and quality are the most robust additions. Low-beta / BAB is real but heavily cost- and model-dependent.

### Rules
- **HML (value):**
  - Sort stocks by book-to-market: top 30% versus bottom 30%.
  - Split by size at the NYSE median.
  - Rebalance annually each June.
  - Holding it long-only means owning cheap-B/M stocks.
- **Size (SMB):** small minus big.
- **RMW (profitability):** operating profitability, robust minus weak.
- **CMA (investment):** conservative minus aggressive asset growth.
- **AQR "HML Devil":** uses current price instead of 6-month-lagged price, rebalanced monthly. It earns 305–378 bp a year of alpha against the 5-factor model. — [AQR dataset](https://www.aqr.com/Insights/Datasets/The-Devil-in-HMLs-Details-Factors-Monthly) (via search summary)
- **Gross profitability (Novy-Marx 2013):**
  - Signal: (revenue − COGS) / total assets.
  - Buy the top tercile or quintile, rebalance annually.
  - GP/A predicts returns about as strongly as B/M. Combining profitability with value "dramatically" improves value strategies, especially among the largest, most liquid stocks. — [Novy-Marx, The Other Side of Value (AQR PDF)](https://www.aqr.com/-/media/AQR/Documents/AQR-Insight-Award/2012/The-Other-Side-of-Value.pdf); [Stockopedia summary](https://www.stockopedia.com/academy/articles/the-quality-factor/)
- **Quality Minus Junk (Asness, Frazzini, Pedersen):**
  - A composite of profitability, growth, safety and payout.
  - Quality beat junk in 24 countries by more than 5% a year. — [Stockopedia](https://www.stockopedia.com/academy/articles/the-quality-factor/); [CFA Institute](https://rpc.cfainstitute.org/research/cfa-magazine/2014/quality-control)
- **Betting Against Beta (Frazzini & Pedersen 2014):**
  - Long leveraged low-beta stocks, short de-leveraged high-beta stocks, both scaled to beta 1.
  - Rebalanced monthly.
  - The retail long-only version is simply the lowest-volatility or lowest-beta quintile. — [NYU PDF](https://pages.stern.nyu.edu/~lpederse/papers/BettingAgainstBeta.pdf)

### Cited Findings
- BAB criticisms:
  - Novy-Marx & Velikov (2021) find that transaction costs cut BAB profitability by almost 60%.
  - Ehsani & Linnainmaa (2021) find the BAB factor loses significance once 4 or more other factors are controlled for.
  - A 2025 "Betting Against Bad Beta" variant reports a gross 15.0% a year return with 13.8% volatility (Sharpe 1.09), versus BAB's 11.4% / 11.3% in the same sample.
  - Source: [Quantitative Finance 2025 / arXiv 2409.00416](https://arxiv.org/html/2409.00416v1)
- Value in 2025:
  - MSCI EAFE Value rose 36.5% through November 2025 in USD, beating EAFE Growth.
  - MSCI World ex-USA Value beat Growth by about 21% in 2025. — [Timeline](https://www.timeline.co/resources/international-values-comeback-patience-pays-off) (secondary); [MSCI blog](https://www.msci.com/research-and-insights/blog-post/international-value-has-outshone-us-growth)
- AQR's view: value spreads remained wide after 2020, and it describes the value comeback as being "in its early innings". — [AQR, Value: Why Now?](https://www.aqr.com/Insights/Research/White-Papers/Value-Why-Now-Capturing-the-Comeback-in-Its-Early-Innings)
- JPMAM asks whether value stocks are staging a comeback in 2026. — [J.P. Morgan AM](https://am.jpmorgan.com/wr/en/asset-management/liq/insights/market-insights/market-updates/on-the-minds-of-investors/are-value-stocks-staging-a-comeback-in-2026/) (not fetched)
- US style spread:
  - Russell 1000 Value's 5-year annualized return trails Growth by about 1.68% a year as of August 2026, compared with a long-term average of −7.63%. (That average likely reflects the growth-dominated sample on that site.)
  - Growth's valuation premium was about 12.8x versus a historical median of about 5.4x.
  - Source: [GuruFocus indicator](https://www.gurufocus.com/economic_indicators/4528/5year-annualized-return-difference-between-russell-1000-value-and-growth); [Artisan](https://www.artisanpartners.com/content/dam/documents/insights/vxus/Insights-A-Case-for-Value-vXUS.pdf)
- Long-run value premium:
  - Global value minus growth was 7.6% a year over 1975–95, with value winning in 12 of 13 markets (Fama & French 1998).
  - International large value returned 10.4% a year versus 8.2% for growth over 1975–July 2025 (Dimensional data as cited by American Century).
  - Source: [SSRN/JF](https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00080); [American Century](https://www.americancentury.com/institutional-investors/insights/why-value-and-why-now/)
- AQR's market-neutral multi-factor style premia fund (QSPRX) is reported to have returned about 6.5% a year since 2015 (as cited, not independently verified). — [Timeline](https://www.timeline.co/resources/international-values-comeback-patience-pays-off)
- Quantpedia: 100 years of the small-value versus large-growth spread, with timing implications. — [Quantpedia](https://quantpedia.com/timing-value-vs-growth-evidence-from-100-years-of-small-value-large-growth-spread/)

### Inferences
- **Regimes:**
  - Value does well when rates rise, during recoveries after recessions, and when very wide spreads narrow (2000–02, 2021–22, 2025 ex-US).
  - Value fails during long periods of low rates and mega-cap tech leadership (2010s, 2023–24 US).
- **Worst drawdown:** HML's peak-to-trough loss over roughly 2007–2020 is widely reported at around 50–60% for the long–short factor. I did not retrieve a source, so verify this against Ken French data.
- **Retail implementation:**
  - Factor ETFs are the cheapest route: value (e.g. international or small-cap value), quality, and minimum volatility.
  - Stock-level replication needs 20–50 names. Fractional shares make that possible at $5k+.
  - Annual or monthly rebalancing is enough. Daily cadence adds costs and no benefit.
  - Retail cannot hold the long–short versions (BAB, HML) cheaply because of borrow costs.

### Gaps
- Exact Ken French HML/RMW/CMA returns for 2025–2026 were not retrieved.
- Maximum-drawdown statistics for each factor were not sourced.

---

## Q5. Short-term mean reversion: RSI(2), Connors/Alvarez, the reversal anomaly, pairs trading, Bollinger bands

### Takeaway
Buying short-term oversold dips in an uptrend, on liquid index ETFs, has kept working since the 2008–2010 publications in practitioner backtests, with low exposure and moderate drawdowns. The single-stock reversal anomaly and distance-based pairs trading have both decayed sharply and are cost-sensitive. They mostly survive in large caps with careful execution.

### Rules
**Connors RSI(2)** (from *Short Term Trading Strategies That Work*, Connors & Alvarez 2008; see [StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2)):
- Long-only rule:
  - Trend filter: close above its 200-day SMA.
  - Entry: 2-period RSI below 10 (more aggressive versions use below 5).
  - Exit: close crosses above the 5-day SMA.
  - No stop loss in the original. The authors argued that stops hurt performance in their tests.
- Short side (mirror image): close below the 200-day SMA, RSI(2) above 90, cover when price crosses below the 5-day SMA.
- Instruments: SPY, QQQ, IWM, DIA and other liquid ETFs.
- Signals on the close, executed at the close or the next open.

**Other Connors/Alvarez book rules** (book summary):
- Buy after 3+ consecutive lower closes (or lower highs/lows) while above the 200-day SMA, and exit on a close above the 5-day SMA.
- Cumulative RSI: the sum of the last 2 days' RSI(2) below 35 (entry), exit when RSI(2) is above 65.
- "Double 7s": buy at a 7-day closing low while above the 200-day SMA, and sell at a 7-day closing high.
- Buy after a VIX spike above its 10-day moving average.

**Bollinger reversion:**
- Buy a close below the lower band (20-day, 2σ) while above the 200-day SMA.
- Exit at the middle band (the 20-day SMA) or after N days.
- In function this is the same trade as RSI(2).

**Short-term reversal anomaly (Jegadeesh 1990 / Lehmann 1990):**
- Each week or month, buy the prior period's losers and short its winners across the cross-section.
- Hold 1 week or 1 month.

**Pairs trading, distance method (Gatev, Goetzmann & Rouwenhorst):**
- Formation: over 12 months, normalize prices and choose pairs with the minimum sum of squared differences.
- Trading: over the next 6 months, open when the spread diverges by more than 2 historical standard deviations. Close when the prices cross, or at the end of the period.
- Source: [GGR SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=141615); [Wharton PDF](http://stat.wharton.upenn.edu/~steele/Courses/434/434Context/PairsTrading/PairsTradingGGR.pdf)

### Cited Findings
- RSI(2) on SPY, 1993 to present: about 9% a year while invested only about 28% of the time, with a maximum drawdown of about 34%. It has remained profitable since the 2010 publication in backtest. — [QuantifiedStrategies substack](https://quantifiedstrategies.substack.com/p/rsi-2-strategy-explained-larry-connors) (search snippet; practitioner backtest, cost assumptions not verified)
- The same practitioner source says the strategy works best in stable uptrends and degrades in high-volatility or strongly trending markets, and that frequent trading raises costs. — same source
- WealthLab publishes a runnable RSI2 backtest. — [WealthLab](https://www.wealth-lab.com/Strategy/RunBacktestPublished?strategyID=5)
- De Groot, Huij & Zhou (J. Banking & Finance 2011):
  - Reversal profits disappear after costs mainly because of small-cap trading.
  - Restricting the strategy to large caps and cutting turnover leaves 30–50 bp a week net of costs.
  - Source: [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0378426611002263); [Erasmus PDF](https://repub.eur.nl/pub/25718/AnotherLook_2011.pdf)
- A residual-reversal variant (Blitz, Huij et al.) ranks stocks on residual rather than total returns. — [EFMA PDF](https://www.efmaefm.org/0EFMSYMPOSIUM/2012/papers/017_update.pdf); [Quantpedia](https://quantpedia.com/strategies/short-term-reversal-in-stocks)
- Pairs trading:
  - GGR (1962–2002) found up to 11% a year excess returns on self-financing pair portfolios.
  - Do & Faff (2010), extending the sample to 2008, found profits declining after 2002, because historical close substitutes stop behaving as substitutes.
  - Source: [ResearchGate: Does naive pairs trading still work?](https://www.researchgate.net/publication/228641482_Does_Naive_Pairs_Trading_Still_Work); [arbitragelab docs](https://hudson-and-thames-arbitragelab.readthedocs-hosted.com/en/latest/distance_approach/distance_approach.html)
- A 2024 Yale paper examines pairs-trading profitability. — [Yale Zhu PDF](https://economics.yale.edu/sites/default/files/2024-05/Zhu_Pairs_Trading.pdf) (not fetched)
- For equity indices, the overnight-intraday reversal earns 2–5x the return and Sharpe of the conventional daily reversal. — [Della Corte & Kosowski](https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/c953a0e6-e93e-4bf7-b839-45a90cedced4.pdf)
- Quantpedia documents short-term reversal in futures. — [Quantpedia](https://quantpedia.com/strategies/short-term-reversal-with-futures)

### Inferences
- **ETFs versus single stocks:**
  - Index ETFs: diversification removes idiosyncratic blowups (earnings, fraud, delisting) that a single stock's oversold signal cannot anticipate, and spreads are about 1 bp. RSI(2)-style rules remain viable for retail with commission-free brokers.
  - Single stocks: the edge is larger on paper, but backtests usually suffer survivorship bias because delisted losers are missing.
- **Flag:** Most practitioner RSI(2) and Connors backtests ignore slippage, and many single-stock versions use current index constituents, which introduces survivorship bias.
- **Regimes:**
  - Works in bull markets with volatility spikes (buy-the-dip regimes, 2010–2021, 2023–25).
  - Fails in persistent downtrends. The 200-day filter helps, but crashes that start from above the 200-day, such as February–March 2020 and 1987-style gaps, cause the worst losses.
  - No stops means occasional large single-trade losses.
- **Suitability:** the best fit in this set for a daily-cadence small account. One to three ETFs, end-of-day signals, market-on-close or next-open execution, and a few trades a month.
  - Watch the pattern-day-trader rule (under $25k in a margin account): these are overnight holds, so they are generally not day trades.
  - Watch short-term capital gains tax.
- **Pairs and cross-sectional reversal:** need shorting, borrow and many positions. They are not suitable for a sub-$25k account.

### Gaps
- No peer-reviewed post-2015 out-of-sample study of the Connors rules with costs was found.
- The quantifiedstrategies.com page with detailed statistics was blocked.

---

## Q6. Dividend and income approaches

### Takeaway
Covered-call funds trade upside for "income" and have lagged their underlying index in total return. Dividend-growth screens mostly add value and quality tilts, with no separate premium.

### Cited Findings
- Israelov & Dong (J. Alternative Investments):
  - Higher derivative income mechanically lowers expected total return.
  - High-yield covered calls underperformed low-yield ones.
  - Covered-call ETFs trailed their benchmarks by about 2.6 percentage points a year (yield 7.37% versus 3.43% for the underlying).
  - They underperformed in more than 70% of rolling 3-year windows and about 85% of rolling 4-year windows.
  - They also come with higher tax drag and negative skew.
  - Source: [Alpha Architect summary (search snippet)](https://alphaarchitect.com/covered-calls/); [Rational Reminder ep. 375](https://rationalreminder.ca/podcast/375)
- ProShares argues that covered-call "downside protection" is a myth. — [ProShares](https://www.proshares.com/browse-all-insights/insights/covered-call-etfs-the-myth-of-downside-protection)

### Inferences
- For a small account, dividends and option premium are not "free" returns. Total return is what matters.
- Covered calls on ETFs require 100-share lots, which is roughly $50k+ for SPY. Retail would use funds such as JEPI or QYLD instead, which carry the documented drag.

### Gaps
- No rigorous dividend-growth (e.g. "Dividend Aristocrats") factor-adjusted study was fetched. The claim that it is a value/quality tilt is an inference.

---

## Q7. Crypto non-trend strategies: funding and basis carry, DCA, rebalancing

### Takeaway
The cash-and-carry basis and funding trade offered 20–25% annualized at peaks in 2024. It compressed to about 10% or less in 2025 as capital flooded in. It is a genuine carry trade, but it carries exchange, liquidation and collateral risk.

### Cited Findings
- The annualized BTC basis peaked at about 20–25% in early and late 2024. It fell to about 10% by mid-2025 and stayed below 10% for much of 2025 (Velo data), because of ETF inflows slowing and arbitrage capital. — [bit.com](https://www.bit.com/insights/knowledge-hub/basis-trade); [Yahoo/CoinDesk](https://finance.yahoo.com/news/federal-rate-cut-could-spark-091651943.html)
- Funding rates above the 0.01% per 8h baseline get arbitraged quickly by institutions and DeFi protocols (for example delta-neutral yield products), which compresses funding. — [BitMEX Q3 2025 derivatives report](https://www.bitmex.com/blog/2025q3-derivatives-report)

### Rules (general construction)
- Hold 1x long spot and 1x short perpetual (or dated future) of equal notional.
- Collect positive funding.
- Close the position when funding turns negative or the annualized basis falls below the T-bill rate plus a margin.
- Keep low leverage on the short leg to avoid liquidation on spikes.

### Inferences
- Minimum practical size is small, since perps are available on retail venues, but US retail access to perps is restricted. Counterparty risk (e.g. FTX-style failures) dominates the return.
- After 2025 compression, net carry is close to T-bill yields for much of the time.

### Gaps
- No academic evidence was retrieved on crypto DCA versus lump sum, or on rebalancing premiums. No reliable sourced figures were found; the report writer should treat any claims here as unsupported.

---

## Summary table for the report writer (inferences, built from the sourced material above)

| Strategy | Turnover | Post-pub / after-cost evidence | Small-account fit (daily cadence) |
|---|---|---|---|
| Graham defensive | Annual | No strong standalone evidence | OK, but daily cadence irrelevant |
| Net-nets | Annual | Huge gross returns, micro-cap costs, scarce | Unique small-account edge; high risk |
| Magic Formula | Annual | Lagged for about 10+ years | OK with 20–30 names |
| F-Score | Annual | Long–short broke down in replication | Use as a filter only |
| Value / quality / low-vol ETFs | Low | Value back in 2025 ex-US; quality robust; BAB cost-sensitive | Best core holdings |
| RSI(2) / Connors on ETFs | ~Weekly | Survived after publication in practitioner backtests; ~34% max drawdown | Best fit for daily cadence |
| Single-stock reversal / pairs | High | Decayed; needs large caps and shorting | Poor |
| Covered calls | — | About −2.6 pts a year versus underlying | Poor for growth |
| Crypto basis | Continuous | Compressed to ~T-bill+ | Marginal; counterparty risk |
