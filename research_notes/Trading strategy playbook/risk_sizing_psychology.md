# Position Sizing, Risk Management, Trading Psychology, and Realistic Expectations for Retail Traders

Scope: codeable risk and sizing rules for an autonomous AI paper-trading agent, plus evidence on what retail traders actually achieve. The research is current as of September 2026. Books are summarized in my own words. There is a Brazil/EU focus because the user is likely Portuguese-speaking.

---

## 1. Position sizing: R-multiples, fixed-fractional, ATR/volatility sizing, Kelly, risk parity

### Takeaway
Size every trade from a predefined stop, so that one loss (1R) equals a fixed small fraction of equity (0.5–1%, with 2% as a hard cap). Use volatility (ATR or realized vol) to set stop distance and exposure. Measure the system in R-multiples. Treat Kelly only as an upper bound and use at most half-Kelly, because the edge estimates that feed it are noisy.

### Cited Findings
- **R-multiple / expectancy (Van Tharp).** R is the initial risk per trade: entry minus stop, times the number of shares. Every result is expressed in multiples of that risk. Example: 100 shares at $100 with a stop at $90 gives R = $1,000. Expectancy is the average profit per trade in R units. — [TraderLion](https://traderlion.com/risk-management/r-and-r-multiples/); [Van Tharp Institute](https://vantharpinstitute.com/tharp-think-trading-concepts/)
- **System Quality Number (Tharp).** SQN = (mean R / stdev R) × sqrt(number of trades). Tharp's bands, usually quoted at 100 trades: <1.6 no edge; 1.6–1.9 poor; 2.0–2.4 average; 2.5–2.9 good; 3.0–4.9 excellent; 5–6.9 superb; 7+ "holy grail". Tharp's claim is that a higher SQN makes it easier to meet goals through position sizing. These bands are practitioner heuristics, not peer-reviewed. — [QuantStrategy.io](https://quantstrategy.io/blog/system-quality-number-sqn-evaluating-your-strategys/); [TradingView SQN script](https://www.tradingview.com/script/vTaMXYEn-SQN/)
- **The Market Wizards risk convention.** Paul Tudor Jones is widely summarized as keeping losses to about 1% per trade, aiming for roughly 5:1 reward-to-risk, and putting defence ("protect what you have") ahead of making money. — [TurtleTrader quotes page](https://www.turtletrader.com/market-quotes/); [Arvy summary of the Market Wizards series](https://arvy.ch/en/market-wizards-series-jack-schwager/)
- **Kelly criterion.** Kelly maximizes the long-run exponential growth rate of wealth (expected log wealth). Its main drawback is that the suggested bets can be very large and very risky in the short term. Fractional Kelly mixes the Kelly bet with cash to reduce risk, at the cost of lower expected final wealth. — [MacLean, Thorp & Ziemba, "The Kelly Capital Growth Investment Criterion" (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1797366); [Ziemba chapter, "Using the Kelly Criterion for Investing"](https://webhomes.maths.ed.ac.uk/mckinnon/blackouts/StochOptFinanceAndEnergySpringer/Chap1_KellyZiemba.pdf); [Thorp, Kelly simulations](http://www.edwardothorp.com/wp-content/uploads/2016/11/KellySimulationsNew.pdf)
- **Half-Kelly trade-off.** Half-Kelly is commonly cited as keeping about 75% of the full-Kelly growth rate while sharply cutting risk (MacLean, Sanegre, Zhao & Ziemba 2004, as summarized). — [Medium summary citing MacLean et al.](https://medium.com/@tmapendembe_28659/the-dangers-of-full-kelly-criterion-why-most-traders-should-use-fractional-kelly-criterion-instead-0338e3bcc705). *Caveat:* that secondary source says half-Kelly "reduces volatility by approximately 75%". The standard continuous-time result is that half-Kelly roughly halves volatility and cuts **variance** by 75%, while keeping 75% of the growth rate. The "75% volatility" wording appears to confuse variance with volatility.
- **Volatility targeting.** Moreira & Muir (Journal of Finance 2017) scaled monthly exposure by the inverse of the prior month's realized variance. Portfolios that cut risk when volatility is high showed higher Sharpe ratios and alphas across the market, value, momentum, profitability, ROE, investment, and betting-against-beta factors, and the currency carry trade. The mechanism: changes in volatility are not matched by proportional changes in expected return. — [Moreira & Muir, Journal of Finance (Wiley)](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513); [NBER w22208](https://www.nber.org/papers/w22208); [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431)
- **Critique of volatility targeting.** A later literature, e.g. "Understanding Volatility-Managed Portfolios", questions how robust these gains are out of sample. — [ResearchGate](https://www.researchgate.net/publication/342497053_Understanding_Volatility-Managed_Portfolios). I did not read this paper in full.

### Inferences (codeable rules, derived from the sources above plus standard formulas)
- **Fixed-fractional risk sizing:**
  `shares = floor( (equity × risk_pct) / (entry − stop) )`
  - Default `risk_pct` = 0.5% for new or unvalidated strategies. Raise to 1.0% only after 100+ out-of-sample trades with positive expectancy. Hard cap: 2%.
- **ATR stop:**
  - `stop = entry − k × ATR(14)`, with k = 2–3 for swing trades.
  - Combine with the formula above, so shares ∝ 1/ATR. This is ATR-based sizing in the style of the Turtles.
- **Volatility-target sizing, for portfolio or ETF strategies:**
  - `weight_i = (target_vol / realized_vol_i)`, where `realized_vol_i` is the 20–60 day annualized volatility of asset i.
  - Cap weight_i at 1.0, i.e. no leverage in a retail paper account.
  - Portfolio `target_vol` of about 10% a year is a reasonable conservative default.
- **Kelly as an upper bound only:**
  - Simple binary form: `f* = W − (1 − W)/B`, where W is the win rate and B is the average win / average loss in R.
  - Continuous form: `f* = μ/σ²`.
  - Use `min(0.25–0.5 × f*, risk cap)`. Never use full Kelly, because estimated μ is noisy and overestimating the edge leads to overbetting and ruin-like drawdowns.
- **Risk parity basics:**
  - Naive version: weight each sleeve or asset in inverse proportion to its volatility, so each contributes roughly equal risk.
  - Full equal-risk-contribution also uses correlations. Inverse-volatility weighting is adequate for a small agent.
- **Track every trade in R**, and compute expectancy, SQN, win rate, and average win/loss in R after each trade.
  - Refuse to increase size unless SQN at N ≥ 100 is ≥ 2.0.
  - This SQN threshold is a Tharp heuristic, not a statistical test. Pair it with the deflated-Sharpe checks in section 5.

### Gaps
- I did not retrieve primary text from Tharp's *Trade Your Way to Financial Freedom* on his specific position-sizing models (percent risk, percent volatility, units per fixed dollars, etc.). The descriptions above come from secondary summaries and the Institute site.
- I found no peer-reviewed study showing that one specific risk percentage (1% vs 2%) is optimal. This is practitioner convention.
- I did not fetch the MacLean–Sanegre–Zhao–Ziemba 2004 paper directly.

---

## 2. Portfolio-level risk: drawdown limits, correlation and concentration, diversification, regime filters

### Takeaway
Put portfolio-level controls on top of per-trade sizing: total open risk ("heat"), a drawdown circuit breaker, caps on correlated exposure, and a simple trend or regime filter. Faber's 10-month SMA rule is the best-documented simple regime filter for cutting drawdowns.

### Cited Findings
- **Faber's regime filter.** Hold an asset when its month-end price is above its 10-month SMA; otherwise hold cash for that asset's share of the portfolio. Applied across several asset classes, it substantially cut maximum drawdowns while keeping equity-like returns. Faber's updates (2009, 2013) reported that real-time performance held up: "equity-like returns with bond-like volatility and drawdowns". — [Faber, SSRN 962461](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461); [PDF](https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf); [CXO Advisory review](https://www.cxoadvisory.com/technical-trading/long-term-outperformance-from-trends-defined-by-moving-averages/)
- **Volatility scaling as a risk control.** Reducing exposure when realized variance is high improved risk-adjusted returns historically across many factors (Moreira & Muir). — [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513)
- **Different styles can all work.** Market Wizards interviewees use opposite styles (trend vs contrarian, fundamental vs technical). What they share is strict risk control, which supports diversifying across strategies instead of looking for one "right" method. — [Arvy series summary](https://arvy.ch/en/market-wizards-series-jack-schwager/); [TraderLion Market Wizards summary](https://traderlion.com/trading-books/market-wizards/)

### Inferences (codeable rules; practitioner-standard, not from one cited study)
- **Portfolio heat.** Keep the sum of open risk (entry − stop, times size) at 6% of equity or less; 4–6% is typical.
- **Concentration.**
  - At most 20% of equity notional in any single stock.
  - At most 25–30% of open risk in one sector or theme.
  - At most 2–3 open positions whose 60-day return correlation is above 0.7. Otherwise treat them as one position for risk purposes.
- **Drawdown circuit breakers, measured from the equity peak:**
  - At −10%: halve `risk_pct`.
  - At −15%: stop opening new trades and review.
  - At −20%: halt the strategy and re-validate it out of sample.
  - Daily loss limit: 2–3R. Weekly loss limit: 5–6R.
- **Regime filter.** Take long-only equity trades only when the index is above its 10-month (≈200-day) SMA. Otherwise reduce size, or trade only in the direction of the trend.
- **Strategy diversification.**
  - Run 2–4 weakly correlated sleeves, for example a trend/momentum sleeve and a mean-reversion sleeve, allocated by inverse volatility.
  - Kill a sleeve whose live performance falls below a pre-set threshold, such as a live Sharpe more than 2 standard errors below its backtest.
- **Tail risk (Taleb-style reasoning).**
  - No short options, no martingale or averaging down, and no position whose worst case is undefined.
  - Assume that historical maximum drawdown understates future maximum drawdown. For planning, a common rule of thumb is 1.5–2× the backtest maximum drawdown.

### Gaps
- I did not source a primary Taleb text in this session (*Fooled by Randomness* / *The Black Swan* / *Antifragile*). The tail-risk inferences are my own summary of well-known themes and need a citation if used.
- I did not retrieve precise Faber drawdown numbers, e.g. S&P 500 buy-and-hold vs timing maximum drawdown.

---

## 3. Lessons from Market Wizards and other trader books (own-words summary)

### Takeaway
Across Schwager's interviews and related books, the same principles keep coming back:
- cut losses quickly;
- let winners run;
- size small enough to survive;
- follow a written process consistently;
- judge decisions by process rather than by any single outcome;
- accept that losses are a normal cost of doing business.

### Cited Findings
- **Ed Seykota** reduces good trading to cutting losses, repeated three times. — [TurtleTrader quotes](https://www.turtletrader.com/market-quotes/); [Zhipeng Yan study notes (Brandeis)](https://www.people.brandeis.edu/~yanzp/Study%20Notes/Market%20Wizards.pdf)
- **Paul Tudor Jones** puts defence first (protect capital before chasing profit), risks about 1% per trade, and looks for asymmetric reward-to-risk. — [TurtleTrader](https://www.turtletrader.com/market-quotes/); [InvestaDaily, "5 Lessons from Market Wizards"](https://www.investagrams.com/daily/2023/10/5-lessons-from-market-wizards/)
- **The series as a whole.** The series now runs to six books, 1989–2026. Summaries agree that the common thread among very different winning traders is disciplined risk management plus mastery of their own psychology, not a shared method. — [Arvy / Thierry von Arvy series overview](https://thierryvonarvy.substack.com/p/the-market-wizards-series-all-6-books); [The Little Book of Market Wizards (Schwager, 2014)](https://sushilparajuli.com/wp-content/uploads/2024/02/The-little-book-of-market-wizards-lessons-from-the-greatest-traders.-4th-ed.-Schwager-Jack.-John-Wiley-2014.-ISBN-9781118858622-SA7-Unit-10.pdf)

### Inferences (own-words synthesis, mapped to agent behaviour)
1. **Cut losses.** Place a hard stop at entry and never widen it. Exit when the thesis is invalidated, even if the stop has not been hit.
2. **Let winners run.** Use trailing stops (ATR or chandelier) instead of fixed small profit targets. That lets average win / average loss exceed 1.5–2R, so a 40% win rate can still be profitable.
3. **Survive first.** Keep per-trade risk small, so a streak of 10–15 losses, which is statistically normal, does not end the account. At 1% risk, 15 straight losses is about a −14% drawdown.
4. **Consistency and process over outcome** (Mark Douglas, *Trading in the Zone*, themes). Treat every trade as one draw from a distribution of outcomes. Accept the risk in advance, execute the rules without discretion, and evaluate the system over large samples, not single trades.
   - For an AI agent, this means no ad-hoc overrides.
   - Log the reason for every deviation.
   - Evaluate performance in batches of 20 or more trades.
5. **No revenge trading or tilt.** After hitting the daily or weekly loss limit, stop for the day or week. Never increase size to "win it back".
6. **Match strategy to personality or temperament.** Schwager's recurring point is that a method only works if it can be followed. For an agent, that means choosing strategies whose drawdown profile the owner can tolerate without switching the system off at the worst moment.
7. **Humility about tails (Taleb).** Avoid strategies that earn small, steady gains while carrying rare catastrophic losses, such as naked option selling or martingale.

### Gaps
- I did not fetch primary summaries of Mark Douglas's *Trading in the Zone* or Taleb's books this session. The points above are own-words summaries from general knowledge and should be labelled as such, or given an additional citation.
- Some quotes circulate online in paraphrased form. The Seykota "cutting losses" line is consistently attributed, but I did not verify page numbers.

---

## 4. Evidence on retail trading outcomes (global, Brazil, EU, options, active vs passive)

### Takeaway
The evidence is overwhelming and consistent across countries and decades:
- Most retail active traders lose money, and very few earn a living wage.
- Losses grow with trading frequency.
- Most professional active funds lag their index over 10+ years.
- A passive index benchmark is the bar any agent strategy must beat after costs.

### Cited Findings

**Brazil**
- **Chague, De-Losso & Giovannetti, "Day Trading for a Living?"** The study covers everyone who began day trading Brazilian equity index futures from 2013 to 2015.
  - Among those who persisted for more than 300 days (1,551 individuals), 97% lost money.
  - Only 1.1% earned more than the Brazilian minimum wage, and only 0.5% earned more than a bank teller's starting salary.
  - There was no evidence of learning with experience.
  - — [SSRN 3423101](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101); [RePEc](https://ideas.repec.org/p/fgv/eesptd/525.html); [QuantPedia summary](https://quantpedia.com/retail-day-trading-is-an-uphill-battle/)
- **FGV EESP study on CVM data during the pandemic.** Up to 100k people day traded daily at the peak.
  - Individuals lost R$9.9 billion between 11 March 2020 and end-2023, about R$10.2k per person.
  - These figures exclude brokerage, exchange fees, courses, and platforms, so real losses were larger.
  - Individuals as a group had a negative result on 95.8% of days before the pandemic and 96.4% after.
  - Most of this trading was in the mini-index contract (WIN).
  - — [FGV EESP PDF](https://portal.fgv.br/sites/default/files/uploads/eesp-pesquisa-day-trade-e-pandemia.pdf); [CenárioMT coverage](https://www.cenariomt.com.br/mundo/brasileiros-perderam-r-99-bilhoes-com-day-trade-durante-a-pandemia-de-covid-19-aponta-estudo-da-fgv-eesp/)
- **Grana Capital survey, 2025.** 33,995 retail day traders over the 12 months to 31 July 2025.
  - 71.87% lost money and about 28% gained.
  - Only 0.18% gained more than R$100k, while 1.02% lost more than R$100k.
  - This is a broker/fintech sample, not a regulator census, and it covers a shorter window than the academic studies.
  - — [Monitor Mercantil](https://monitormercantil.com.br/day-trade-causa-perdas-para-7187-dos-investidores-pessoas-fisicas/); [BB Investalk](https://investalk.bb.com.br/noticias/mercado/day-trade-gera-perdas-para-72-dos-investidores-pessoas-fisicas-aponta-estudo)
- **CVM educational booklet on day trade** (Caderno CVM 15). — [gov.br/CVM](https://www.gov.br/investidor/pt-br/educacional/publicacoes-educacionais/cadernos/caderno-cvm-15-day_trade.pdf/@@display-file/file)

**EU / ESMA**
- **ESMA, 2018.** Analyses by national regulators found that 74–89% of retail CFD accounts typically lose money, with average losses per client of €1,600 to €29,000. This led ESMA to ban binary options for retail clients and restrict CFDs: leverage caps, margin close-out, and negative-balance protection. EU brokers must still show a "% of retail accounts lose money" warning. — [ESMA press release](https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors); [ESMA PDF](https://www.esma.europa.eu/sites/default/files/library/esma71-98-128_press_release_product_intervention.pdf); [CNMV](http://www.cnmv.es/DocPortal/Aldia/medidascfdyopciones_ingles.pdf)

**US / Taiwan (Barber & Odean et al.)**
- **Barber & Odean, "Trading Is Hazardous to Your Wealth"** (Journal of Finance 2000). 66,465 US discount-broker households, 1991–1996.
  - The most active traders earned 11.4% a year against 17.9% for the market.
  - The average household earned 16.4%, with 75% annual turnover.
  - — [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=219228); [PDF](https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/individual_investor_performance_final.pdf)
- **Barber, Lee, Liu & Odean, "Just How Much Do Individual Investors Lose by Trading?"** (RFS 2009). In Taiwan, 1995–1999, individual investors' aggregate trading losses exceeded 2% of Taiwan's GDP. — [PDF](https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/justhowmuchdoindividualinvestorslose_rfs_2009.pdf)
- **Taiwan day traders** (Barber, Lee, Liu, Odean; "The Cross-Section of Speculator Skill" and related papers).
  - More than 80% of day traders lost money in a typical six-month period.
  - Profitable day traders were about 5% of active traders in 1995–2006.
  - Day traders lost on average about 23.9 bps per day net of fees, and the aggregate was negative in 14 of 15 years.
  - — [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1386418113000190); [PDF](https://faculty.haas.berkeley.edu/odean/papers/day%20traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf)
  - *Note:* the popular claim that "less than 1% are predictably profitable" comes from the same research line ("Do Day Traders Rationally Learn…"). I did not verify that exact figure this session. The ~5% figure is for profitable traders in a period, not persistent skill.

**Options**
- **Bryzgalova, Pavlova & Sikorskaya** (Journal of Finance 2023).
  - Retail options trading, facilitated by payment for order flow, reached more than 60% of total market volume at points.
  - The aggregate retail options portfolio lost about $2.1 billion from November 2019 to June 2021.
  - — [LBS Research Online](https://lbsresearch.london.edu/id/eprint/2827/); [PDF](https://www.sikorskaya.net/files/Bryzgalova_Pavlova_Sikorskaya_2022.pdf)
- **Retail option losses around earnings and in short-dated options.**
  - Retail traders lose on option trades around earnings announcements, mainly through high spreads and overpaying for volatility (de Silva, Smith & So).
  - Bogousslavsky & Muravyev (2025) and Beckmeyer et al. document retail losses in short-dated / 0DTE options.
  - — [de Silva et al., "Losing is Optional"](https://www.timdesilva.me/files/papers/losing_optional.pdf); [Bogousslavsky & Muravyev](https://www.lsu.edu/business/files/event-files/2025-finance-mardi-gras/retail_option_trading_v2.pdf)
  - The search-engine summary also gave: 0DTE retail losses of about $184k/day, naked sales earning 20%, and purchases losing 3.95%. I could not confirm which paper these specific numbers come from, so treat them as unverified.

**Active vs passive (SPIVA)**
- **SPIVA U.S. Year-End 2025.** 79% of active large-cap US equity funds underperformed the S&P 500 in 2025, up from 65% in 2024. It was the fourth-worst year in the 25-year SPIVA history. — [SPIVA U.S. Year-End 2025](https://www.spglobal.com/spdji/en/documents/spiva/spiva-us-year-end-2025.pdf); [InvestmentNews](https://www.investmentnews.com/equities/active-managers-stumble-again-in-2025-as-large-caps-dominate/265541)
- **Longer horizons.** Per year-end 2024 data, about 89.5% of large-cap funds lagged the S&P 500 over 15 years. Over 20 years, almost none beat it net of fees. — [Ritholtz summary of SPIVA](https://ritholtz.com/2025/05/the-data-on-active-large-cap-underperformance/)
  - The spglobal.com site was blocked by my network proxy, so I could not pull the exact 10/15/20-year figures for year-end 2025 from the primary PDF.
- **Methodology challenge.** One study disputes parts of the SPIVA methodology. — [WealthManagement.com](https://www.wealthmanagement.com/mutual-funds/new-report-challenges-methodology-in-long-running-active-scorecard)

### Inferences
- Losses rise with activity: day trading loses the most, then high-turnover trading, then options buying. For an agent aiming at modest extra income, this argues for:
  - low turnover (swing or position timeframes, days to months);
  - liquid, low-cost instruments such as large-cap stocks and ETFs;
  - no leveraged CFDs, no 0DTE options, and no mini-index day trading.
- The benchmark for "success" is not "made money". It is **beating a buy-and-hold index ETF after costs and taxes, on a risk-adjusted basis**. Most professionals fail this over 10–20 years.
- The Brazilian evidence shows no learning over time, so practice alone does not create an edge. The agent should not assume it will "get better with experience" without statistical evidence.

### Gaps
- I did not find FINRA/SEC aggregated retail P&L statistics comparable to ESMA's. US regulators publish investor alerts, but no cross-broker loss-rate disclosure like the EU CFD warning.
- I did not retrieve current (2025–2026) broker CFD loss disclosures. Individual EU brokers publish them quarterly, commonly in the 60–80% range, but I did not verify specific figures.
- SPIVA Europe and Latin America (Brazil) scorecard figures were not retrieved because of the spglobal.com block.

---

## 5. Realistic return targets, account size, costs and taxes

### Takeaway
Realistic long-run targets for a disciplined systematic retail strategy:
- **Return:** roughly equity-like, about 6–10% nominal a year, before any claimed edge. Real global equities have returned about 6.6% a year since 1900.
- **Drawdowns:** peak-to-trough drawdowns of 15–30% are normal, even for good systems.
- **Account size:** income is return × capital. €5k at 10% is €500 a year before tax, which is "extra income", not a living.

### Cited Findings
- **Long-run equity returns.** UBS Global Investment Returns Yearbook 2026 (Dimson, Marsh, Staunton):
  - Equities delivered about 6.6% a year in real (after-inflation) terms over 1900–2025.
  - Developed markets returned 8.5% a year vs 6.9% for emerging markets since 1900; emerging markets returned 10.9% vs 9.6% over 1960–2025.
  - The press summary does not say clearly which of these figures are real vs nominal or USD-based, so check the primary document before quoting precisely.
  - — [UBS press page](https://www.ubs.com/global/en/media/display-page-ndp/en-20260303-global-investment-returns-yearbook-2026.html); [LBS](https://www.london.edu/news/ubs-global-investment-returns-yearbook-2026-history-risk-and-return-in-turbulent-times)
- **Earning a living is nearly impossible.** Only 1.1% of persistent Brazilian day traders earned more than minimum wage. — [SSRN 3423101](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101)
- **Costs from turnover.** Heavy trading cut household returns from the market's 17.9% to 11.4% a year. — [Barber & Odean 2000](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=219228)
- **Taxes — Portugal.**
  - Capital gains are taxed at a 28% flat rate on the net annual gain, or optionally aggregated at the marginal rate. Aggregation is beneficial for taxable income below about €22,306 (2025 incomes).
  - Since 2024, gains on securities held 2–5 years exclude 10% (effective 25.2%), 5–8 years exclude 20% (22.4%), and more than 8 years exclude 30% (19.6%).
  - This favours long holding periods over active trading.
  - — [Rankia PT](https://www.rankia.pt/fiscalidade/fiscalidade-das-acoes-em-portugal/); [Comparajá](https://www.comparaja.pt/financas-pessoais/artigos/irs-dividendos-e-mais-valias); [DECO Proteste](https://www.deco.proteste.pt/investe/investimentos/impostos/dossie/fiscalidade-acoes/como-declarar-acoes-irs)
- **Taxes — Brazil (2026).**
  - Stock swing trade / buy-and-hold is taxed at 15%. Gains are exempt when monthly stock **sales** total R$20k or less.
  - Day trade is taxed at 20% with no exemption.
  - — [InfoMoney](https://www.infomoney.com.br/guias/declarar-acoes-imposto-de-renda-ir/); [B3 Bora Investir](https://borainvestir.b3.com.br/noticias/imposto-de-renda/renda-variavel-imposto-de-renda/comprou-ou-vendeu-acoes-veja-como-declarar-swing-trade-day-trade-e-proventos-no-imposto-de-renda/); [XP](https://conteudos.xpi.com.br/aprenda-a-investir/relatorios/day-trade-no-imposto-de-renda/)
  - One blog refers to "new rules from 2026" ([ITC blog](https://www.blog.itcnet.com.br/post/novas-regras-do-imposto-de-renda-para-quem-investe-na-bolsa-a-partir-de-2026)). The mainstream 2026 sources above still show 15% / 20% and the R$20k exemption. Verify before relying on this.

### Inferences (worked examples, simple arithmetic)
- **Pre-tax income by capital and return:**

  | Capital | 5% / yr | 8% / yr | 10% / yr | 15% / yr |
  |---|---|---|---|---|
  | €/R$ 5k | 250 | 400 | 500 | 750 |
  | 20k | 1,000 | 1,600 | 2,000 | 3,000 |
  | 50k | 2,500 | 4,000 | 5,000 | 7,500 |

- **After tax:**
  - Portugal, 28% flat: a 10% gross return becomes 7.2% net. €5k → €360 a year.
  - Brazil day trade, 20%: 10% becomes 8%.
- **Costs:**
  - Formula: `annual cost drag = turnover × round-trip cost`.
  - Example: 100 round trips a year × 0.2% (commission + spread + slippage) ≈ 20% of traded notional. At full-equity turnover that is a 20%-a-year drag, larger than any plausible edge.
  - Small accounts suffer most from fixed minimum commissions. Example: a €1 minimum on a €500 trade is 0.2% per side.
- **Suggested agent targets (paper trading):**
  - Aim for 8–12% a year, a Sharpe ratio of 0.5–1.0 after costs, and a maximum drawdown of 20% or less.
  - A backtest Sharpe above about 2 or returns above about 30% a year for a simple retail strategy should be treated as a sign of overfitting or bugs, not success. This is a heuristic consistent with the deflated-Sharpe logic in section 6.
- **Always compare against a benchmark:** a buy-and-hold index ETF (e.g. MSCI World/ACWI UCITS ETF, or BOVA11/IVVB11 for Brazil) with the same capital. If the agent does not beat it after costs and taxes, index investing is the better answer.

### Gaps
- I did not find a peer-reviewed source for typical Sharpe ratios or drawdowns of *retail* systematic strategies specifically. The targets above are inferences.
- I did not retrieve exact CTA / trend-following index drawdown statistics, e.g. SG Trend Index maximum drawdown, as a professional reference point.

---

## 6. Strategy evaluation hygiene: overfitting, deflated Sharpe, walk-forward, minimum samples

### Takeaway
Backtests are biased upward by multiple testing and non-normal returns. Before trusting any strategy, the agent should:
- record every configuration it tried;
- deflate the Sharpe ratio for the number of trials;
- respect the minimum backtest length;
- validate walk-forward or out of sample;
- require roughly 100 or more trades.

### Cited Findings
- **Deflated Sharpe Ratio** (Bailey & López de Prado, 2014). It tests whether an estimated Sharpe ratio is still significant after correcting for selection bias under multiple testing and for non-normal returns (skew and kurtosis). — [SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551); [PDF](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf)
- **Probability of Backtest Overfitting (PBO)** (Bailey, Borwein, López de Prado & Zhu; Journal of Computational Finance 2017). It uses combinatorially symmetric cross-validation (CSCV) to estimate how likely it is that the in-sample-best configuration underperforms the median configuration out of sample. — [SSRN 2326253](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253); [PDF](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)
- **Minimum Backtest Length** (Bailey, Borwein, López de Prado & Zhu, Notices of the AMS 2014).
  - With only 5 years of data, trying more than about 45 independent configurations almost guarantees finding an in-sample annualized Sharpe of 1 whose expected out-of-sample Sharpe is zero.
  - The approximate formula is MinBTL ≈ 2·ln(N) / SR_target² years, where N is the number of independent trials.
  - — [AMS Notices PDF](https://www.ams.org/notices/201405/rnoti-p458.pdf); [SSRN 2308659](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659)
- **Harvey, Liu & Zhu** (RFS 2016). Because of extensive data mining, a newly claimed return factor should clear a t-statistic above 3.0, not the usual 2.0. Many published factors are likely false discoveries. — [SSRN 2249314](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2249314); [RFS](https://academic.oup.com/rfs/article/29/1/5/1843824)

### Inferences (codeable validation checklist)
1. **Log every trial:** each parameter set, feature, and rule variant, giving N_trials. The effective N is lower when trials are correlated, but never report "1".
2. **Minimum backtest length.** Require `years_of_data ≥ 2·ln(N_trials) / SR_target²`. Example: 100 trials targeting SR = 1 needs about 9.2 years; 1,000 trials needs about 13.8 years.
3. **Deflated Sharpe.** Compute DSR using N_trials, the variance of Sharpe ratios across trials, skew, kurtosis, and sample length. Deploy to paper trading only if DSR ≥ 0.95.
4. **t-stat hurdle.** The Sharpe t-stat is about SR_annual × sqrt(years). Require ≥ 3.0 (Harvey–Liu–Zhu). Example: SR = 1.0 needs about 9 years of data for t = 3; SR = 0.5 needs about 36 years.
   - This is why short retail backtests rarely prove anything.
5. **Walk-forward.** Use rolling or anchored train/test windows, e.g. 3–5 years in-sample and 1 year out-of-sample, stepping forward. Report only the concatenated out-of-sample results. Keep a final untouched holdout of 20% or more of the data.
6. **Minimum trades.**
   - Do not evaluate expectancy or SQN on fewer than about 30 trades.
   - Require 100 or more trades before increasing risk.
   - The standard error of mean R is σ_R / sqrt(n). With σ_R ≈ 1.5R and n = 100, SE ≈ 0.15R. An expectancy of 0.2R is therefore only about 1.3 standard errors from zero.
7. **Costs in the backtest.** Include commissions, spread, and slippage of at least 1 tick or 0.05–0.1% per side for liquid stocks and ETFs, plus the relevant taxes.
8. **Live paper-trading gate.** Paper-trade for 3–6 months or 50+ trades. Compare live results with the backtest distribution, and halt if live results fall outside the 5th percentile of bootstrapped backtest paths.

### Gaps
- I did not fetch López de Prado's *Advances in Financial Machine Learning* (purged K-fold / embargo, meta-labeling) in this session. Purged and embargoed cross-validation is the recommended refinement over naive walk-forward when labels overlap.
- I found no single authoritative "minimum number of trades" figure. The 30 and 100 thresholds are statistical rules of thumb, reasoned above from the standard error.
