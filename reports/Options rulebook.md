# Options rulebook: rules for a separate paper-only options book (O)

*Draft for owner review, 27 September 2026, revised 28 September 2026 after an independent critique. An addition to `reports/Agent rulebook.md`: every rule there still applies unless this file says otherwise. Sources: five research notes written this week (strategy evidence, Alpaca mechanics, risk practice, retail and AI outcomes, system fit and a model-priced backtest), with the key claims checked again against the original papers. Where a check changed a number, the corrected number is used here. Nothing here is implemented yet. No orders were placed while writing it.*

## Summary

Options have one well-proven fact behind them: **people who sell index options get paid on average, and people who buy them pay.** From 1990 to 2018 the VIX averaged 19.3% while the S&P 500 then moved only 15.1%. That gap is the "volatility risk premium". It is payment for crash risk, and it arrives as many small wins and a few large losses.

The same evidence says the edge is small now and easy to lose:
- Since 2007 the Cboe put-writing index (PUT) earned a **lower** Sharpe ratio than the S&P 500 (0.52 vs 0.61). A 2025 Chicago Fed working paper finds index-option returns over the last 15 years, after adjusting for market risk, are statistically zero.
- Our own 2016–2026 model-priced replay of a monthly SPY put spread 2% of spot wide (about $15 today, a maximum loss near $1.4k a contract) made **+0.017R per trade**, about zero. This book can afford only about a **$2-wide** spread. Replayed at that share of spot it made **−0.076R per trade**, because costs eat a bigger share of a smaller credit.
- Retail option traders lose money mostly through trading costs. Famous option sellers (LJM, OptionSellers.com, Malachite) blew up by selling risk with no cap.
- No audited result shows an AI agent trading options profitably. On an options benchmark, LLMs scored only 18–53 out of 100 for greeks accuracy.

So book O is a **measurement experiment, not a source of profit.** Its job is to learn the mechanics (multi-leg orders, fills, assignment) and to measure real costs against the model, with paper money and tiny risk. **The replay expects the affordable spread to lose slightly.** The philosophy:
- **Defined risk only.** Every short option is paired with a long option in the same order, so the loss **at expiry** is capped at the width minus the credit. Closing costs, fees, gaps and assignment can make the realised loss larger, so R_net can be worse than −1.
- **One structure first:** a monthly SPY bull put spread, sized so the worst case including an estimated exit cost is about $250 (0.25% of equity).
- **Code decides everything.** Claude may only skip the month's single spread, with a reason code. Skips are logged and scored for information.
- **Shadow first.** The book runs on logged option chains with no orders until the paper-start gate (OPT-41) passes.
- **Never live under this rulebook.** At the rate the book can trade (about half of months), the main rulebook's promotion gate (100 trades) would take at least 16 years.

## What this changes in the main rulebook

| ID | Change |
|---|---|
| RISK-1 (amended **for book O only**) | Books A–D stay exactly as they are: long only, no leverage, shorts or options, and `account.options: false` stays in `risk_policy.yaml`. Book O shares the rules book's Alpaca paper account (owner decision 6 in `OPERATION_INVEST.md`) through its own ledger and may hold options only as the defined-risk vertical spreads in OPT-3. Short stock stays forbidden everywhere; stock delivered by an O assignment belongs to O's ledger and is sold by O (OPT-26), never adopted by the rules book. |
| RISK-5, RISK-6 (exception) | O's SPY delta is **not** summed with the other books' SPY holdings for the per-symbol and equity-like caps. It is shown next to them (OPT-11). O's own caps (OPT-9, OPT-10) apply instead. |
| CL-8 (amended **for book O only**) | O skips may use SCHEDULED_EVENT only when FOMC, CPI or payrolls falls on the **order session**, not anywhere in the holding window. Every four-week window holds one of them, so the wider reading would allow a skip every month. |
| CL-9 (for book O) | O's skip scores are **informational**. At one decision a month, 30 scored vetoes would take years, so CL-9's code-shrinking rule does not apply to O. |
| Rejected list | "Options" moves from *rejected* to *paper experiment, defined risk only*. Shorting, pairs and covered calls stay rejected. |
| Everything else | Every limit below is equal to or tighter than the main rulebook's (1R = 0.5% of *E*, heat ≤ 6%, sleeve tiers at 3% and 5%, daily loss 1%). Risk rises only through a statistical gate (OPT-8), as in RISK-2. |

## How to read the tables

Status (**BUILD NOW**, **TEST FIRST**, **LATER**) and evidence grades (**Strong**, **Moderate**, **Weak**, **Design choice**) mean the same as in the main rulebook. For options, TEST FIRST rules pass through OPT-40, not M-12, because option history on Alpaca starts only in February 2024.

**New source keys** (the main rulebook's keys, such as TH, MW, MK, PB and CODE, still apply). "Read" means the text was read in full; "snippet" means only an abstract or search summary.

| Key | Source |
|---|---|
| BO19 | Bondarenko, *Historical Performance of Put-Writing Strategies*, Cboe 2019, [PDF](https://cdn.cboe.com/resources/education/research_publications/PutWriteCBOE19_v14_by_Prof_Oleg_Bondarenko_as_of_June_14.pdf) (read) |
| WC19 | Wilshire for Cboe, options-based benchmark indexes, June 1986–Dec 2018, [PDF](https://cdn.cboe.com/resources/spx/wilshire-options-based-benchmark-indexes-2019.pdf) (read) |
| CBF | Cboe [PUT](https://cdn.cboe.com/resources/indices/factsheet/CboeGlobalIndices_PUT-Index.pdf) and [BXM](https://res-certification.cboe.com/resources/indices/factsheet/CboeGlobalIndices_BXM-Index.pdf) factsheets as of 31 Aug 2026 (read) |
| CS01 | Coval and Shumway, "Expected Option Returns", *J. Finance* 2001, [Wiley](https://onlinelibrary.wiley.com/doi/10.1111/0022-1082.00352) (abstract) |
| DG25 | Dew-Becker and Giglio, "The Decline of the Variance Risk Premium", Chicago Fed WP 2025-17, [PDF](https://www.chicagofed.org/-/media/publications/working-papers/2025/wp2025-17.pdf) (abstract and introduction read; a working paper, not peer-reviewed) |
| AQR | Israelov, "Pathetic Protection", *JAI* 2019, [PDF](https://images.aqr.com/-/media/AQR/Documents/Journal-Articles/Pathetic-Protection-JAI-Wint19.pdf) (read; pp. 7–8); Israelov and Klein, collars, *JAI* 2016, [PDF](https://images.aqr.com/-/media/AQR/Documents/Journal-Articles/Risk-and-Return.pdf) (read; Exhibit 2); Israelov and Nielsen, "Covered Calls Uncovered", *FAJ* 2015, [PDF](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Covered-Calls-Uncovered.pdf) (read) |
| LEV | Frazzini and Pedersen, "Embedded Leverage", [NBER](https://www.nber.org/papers/w18558); Ilmanen, *FAJ* 2012, [AQR](https://www.aqr.com/Insights/Research/Journal-Article/Do-Financial-Markets-Reward-Buying-or-Selling-Insurance-and-Lottery-Tickets) (snippets) |
| SS09 | Santa-Clara and Saretto, "Option Strategies: Good Deals and Margin Calls", *JFM* 2009, [PDF](https://www.anderson.ucla.edu/documents/areas/fac/finance/santa_clara_option.pdf) (working paper read) |
| RET | Bryzgalova, Pavlova and Sikorskaya, *J. Finance* 2023, [PDF](https://www.sikorskaya.net/files/Bryzgalova_Pavlova_Sikorskaya_2023.pdf) (read); Bogousslavsky and Muravyev, [SSRN 4682388](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4682388) (Aug 2024 draft read); de Silva, Smith and So, *Rev. Finance* 2026, [PDF](https://www.timdesilva.me/files/papers/losing_optional.pdf) (abstract read); Muravyev and Pearson, *RFS* 2020, [OUP](https://academic.oup.com/rfs/article-abstract/33/11/4973/5732665) (snippet) |
| 0DTE | Beckmeyer, Branger and Gayda, [SSRN 4404704](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4404704) (snippet and summaries) |
| AI | TraderBench, [arXiv 2603.00285](https://arxiv.org/html/2603.00285v1) (read); Alpha Arena press reports; Barton et al., [arXiv 2609.05663](https://arxiv.org/abs/2609.05663) (summaries and abstracts) |
| BLOW | LJM, OptionSellers.com, Malachite and "Karen the Supertrader": [Reuters/Yahoo](https://finance.yahoo.com/news/u-ljm-fund-lost-most-152828038.html), [CNBC](https://www.cnbc.com/2018/11/21/a-risky-natural-gas-bet-gone-awry-leads-to-weepy-youtube-confessional.html), [SEC](https://www.sec.gov/litigation/litreleases/2021/lr25246.htm) (news and regulator pages) |
| ALP | Alpaca docs: [options trading](https://docs.alpaca.markets/docs/options-trading), [level 3](https://docs.alpaca.markets/docs/options-level-3-trading), [paper trading](https://docs.alpaca.markets/us/docs/paper-trading), [historical option data](https://docs.alpaca.markets/docs/historical-option-data), [fee schedule](https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf); alpaca-py 0.44.0 source (read) |
| ASN | Assignment and pin risk: [Cboe](https://www.cboe.com/insights/posts/dont-get-stuck-paying-the-dividend-on-your-short-trade), [Fidelity](https://www.fidelity.com/learning-center/investment-products/options/dividends-options-assignment-risk), [IBKR](https://www.interactivebrokers.com/campus/traders-insight/securities/options/understanding-special-exercises-and-pin-risk/) (snippets) |
| VEN | Vendor and practitioner rules of thumb (tastylive 45 DTE / 21 DTE / 50%, [Option Alpha](https://optionalpha.com/blog/spy-put-credit-spread-backtest), [FlashAlpha](https://flashalpha.com/articles/spy-put-credit-spread-active-backtest-mm-fills-vrp-signal-drawdown-breaker)) |
| RPL | Our own model-priced replay, 2016–2026: Black-Scholes on raw SIP closes, Cboe volatility index × a skew table calibrated on Alpaca option bars since Feb 2024, costs as in the cost model below with a modelled quoted spread of 2.5% of each leg's price. In sample; checked against real 2024–26 option bars (correlation 0.99, n = 27). Width runs: `work/widths.py`. |
| SNAP | Alpaca SPY put chain snapshot, 25 Sep 2026, indicative feed, 30 Oct and 6 Nov expiries (`work/spy_chain.json`) |

**Conventions.**
- *E* is the **shared paper account's** equity (Alpaca's default paper equity is $100,000). 1R = 0.5% of *E*, as in RISK-2. O's own capital is the ledger's committed max loss plus its realised P&L; the rules book's equity is the account equity minus O's ledger value.
- A **bull put spread** sells a put and buys a cheaper put at a lower strike, same expiry. It collects a credit and makes money if SPY stays above the short strike.
- A put's **delta** is negative: −0.20 means the put gains about $0.20 for each $1 SPY falls. "|delta| 0.20" drops the sign. A bull put spread's net delta is positive.
- **MaxLoss** of a credit spread = (width − credit) × 100 × contracts; of a debit spread = debit × 100 × contracts. It is the loss if the spread is held to expiry with SPY below both strikes. It is the position's `initial_risk_dollars` (M-3).
- **R_net** = (P&L − costs) / MaxLoss. It **can be below −1**: fees, closing costs, an overnight gap or an assignment can add to MaxLoss.
- **Mid** = (bid + ask) / 2 per leg. **Quoted cost** of a spread = the sum of its legs' (ask − bid). **Natural price** = the price if every leg trades at its worse side (open a credit spread: short bid − long ask; close it: short ask − long bid). Mid and natural differ by half the quoted cost.
- **Budgeted loss** = MaxLoss + quoted cost at entry × 100 × contracts (an estimate of the exit cost). Size caps apply to the budgeted loss.
- **Cost model (one model everywhere):** each leg pays half its quoted spread on each side, plus $0.04 per contract per side in fees. A round trip therefore costs about the full quoted cost. The backtest uses modelled quotes; shadow and paper results use logged quotes.
- **DTE** = calendar days to the contract's `expiration_date` (holiday expiries can move to Thursday). Quotes and greeks come from the chain snapshot taken at the run.
- **Early assignment:** the owner of a put we sold may exercise it before expiry, handing us 100 shares per contract. **Pin risk:** at expiry, with SPY near a strike, we cannot know whether we will be assigned.

## What the evidence says (the numbers behind the rules)

| Finding | Source | Grade |
|---|---|---|
| VIX averaged 19.3% vs 15.1% later realised S&P 500 volatility, 1990–2018. Implied beat realised in every *annual* average except 2008 (32.7 vs 35.2), but not in every month: in crash months realised was higher. | BO19 | Strong |
| June 1986–Dec 2018, before costs and taxes, early years backfilled: PUT 9.54% a year at 9.9% volatility, Sharpe 0.64, max DD −35.5%, skew −2.10; BXM 8.50% (Sharpe 0.51); PPUT 6.64% (0.29); S&P 500 9.80% at 14.9% (0.45, DD −50.9%). | WC19 | Strong |
| Since Jan 2007 (PUT launched June 2007): PUT Sharpe 0.52 vs 0.61 for the S&P 500 TR, 7.1% vs 11.0% a year, DD −32.7% vs −50.9%. BXM's full history (backtested before its 2002 launch) gives 0.56 vs 0.57. Lower risk, equal or lower risk-adjusted return, clearly lower total return. | CBF | Strong |
| Premium selling cushions slow bears (2022: PUT −7.7% vs −18.1%) but trails badly in fast crashes with V-shaped recoveries (2020: PUT +2.1%, BXM −2.8% vs +18.4%) and in sharp selloffs (2018: −5.9% vs −4.4%). Worst month −17.65% (Oct 2008), month-end data. | CBF, BO19 | Strong |
| Index-option alphas over the last 15 years are indistinguishable from zero. | DG25 | Moderate (one working paper) |
| 1990s index data: zero-beta ATM straddles lost about 3% a week; puts returned less than cash. Long index volatility pays sellers. Calls still beat the index, so not every long option loses. | CS01 | Strong |
| More embedded leverage (short-dated, deep OTM options) means lower leverage-adjusted returns on average, before costs. | LEV | Strong |
| Short-option Sharpe ratios are high before frictions; costs cut them severely, and margin calls can turn some of the best strategies negative. | SS09 | Strong |
| Protective puts: PPUT's excess return was 2.5% a year vs 5.8% for the S&P 500, mostly from lower beta; the puts themselves had −1.8% a year of alpha. 36.5% S&P 500 plus cash matched PPUT's return at about half its volatility (6.6% vs 13.5%). The 95–110 collar's Sharpe was 0.30 vs 0.47. | AQR | Strong (AQR backtests) |
| Covered calls are mostly equity beta (about two-thirds of risk); the short-volatility part had a Sharpe near 1.0 but under 10% of risk (7% in the summary table). | AQR | Strong |
| Retail favourites (under 1 week) have 12.6% quoted and 6.6% effective spreads; losses come mainly from costs. A sample of retail traders that the authors call "relatively sophisticated" (trading-journal users) lost only −0.9% per trade, including commissions; the authors say they "likely" use limit orders but do not measure it. | RET | Strong / Moderate |
| Retail lost about $241k a day in SPX 0DTE (Feb 2021–Sep 2023), most of it trading costs (76% in the summary our notes used; not re-checked against the paper), mostly on single-leg premium-buying trades. | 0DTE | Moderate |
| Monthly SPY bull put spread, 20 delta, 35 → 7 DTE, **2% of spot wide**: E = +0.017R, 84% wins, SQN 0.8, n = 128, worst −1.2R. Doubled costs: +0.005R. Ignoring skew makes it look four times better. | RPL | Moderate (in sample) |
| **The same spread at the widths this book can afford**, as a share of spot equal to today's $5 / $3 / $2 (0.65% / 0.39% / 0.26%): E = −0.016R / −0.052R / −0.076R, 78% / 73% / 66% wins, worst −1.75R / −2.49R / −2.49R. Modelled round-trip costs take 13% of the gross credit at 2% wide, 61% at $3 and 81% at $2. Bull_calm entries only (n = 56): +0.012R at 2%, −0.065R at $2. | RPL | Moderate (in sample) |
| On 25 Sep 2026 a 20-delta SPY put spread paid a mid credit of about 9–12% of its width, and a $2 spread's quoted cost was 29% (30 Oct) and 218% (6 Nov) of its mid credit. | SNAP | Moderate (one day, indicative feed) |

*Break-even, for beginners.* A credit of about 10% of the width means that if every loss were a full loss, the spread would need about 90% wins to break even. The replay won 84% and still came out near zero at 2% wide only because most losses were closed early and were partial. At $2 wide it won only 66%, because costs turn many small wins into small losses.

*Why the replay's worst losses exceed −1R.* The model closes at its own price plus exit costs, which can exceed the width. OPT-15 never pays more than the width to close, so a real close should not do that. Fees, gaps and assignment still can.

## (a) Scope and instruments

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| OPT-1 | Book O is `enabled: false` by default; only the owner turns it on (like D-1). It trades in the rules book's paper account (owner decision 6), using `ALPACA_OPTIONS_KEY` / `ALPACA_OPTIONS_SECRET` if set, else the rules keys, with its own ledger and `OPT-` order ids; it never trades in the Claude book's account. Code refuses any non-paper base URL. | MA, BLOW | Design choice | BUILD NOW |
| OPT-2 | Only the new O path in `risk.py` accepts OCC option symbols. The stock path, including its `max(0, qty)` clip and `account.options: false`, is not loosened. | CODE | Design choice | BUILD NOW |
| OPT-3 | **Defined risk only.** A position is one vertical spread: 2 legs, same underlying, expiry and type, ratio 1:1, one `BUY_TO_OPEN` and one `SELL_TO_OPEN`, sent as **one** `mleg` order. For a credit spread the long leg is further out of the money. Code rejects any order, fill or position state that would leave a short option without its long partner. This caps the loss **at expiry**; R_net can still be below −1 (see Conventions). | BLOW, SS09, ALP | Strong (tail cap) | BUILD NOW |
| OPT-4 | Underlying: **SPY only**. QQQ and IWM run as shadows (OPT-39). DIA (quoted put spreads about 11% of mid) and single stocks are out. | RPL, RET | Moderate | BUILD NOW |
| OPT-5 | Never: 0DTE or any entry below 25 DTE; single-leg long or short options; naked shorts; ratios, calendars, diagonals, straddles, strangles, iron condors; equity legs; rolling. | 0DTE, LEV, BLOW | Strong / Design | BUILD NOW |
| OPT-6 | **Start-up checks**, each run: account is paper; `options_trading_level` ≥ 3; `max_options_trading_level` is set to 3 in the account configuration; no stock is held that neither book's ledger owns. Any failure → no new entries; exits still run. | ALP | Design choice | BUILD NOW |

## (b) Size and exposure limits

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| OPT-7 | Code computes MaxLoss and the budgeted loss from strikes and the actual fill, never from Claude's numbers. MaxLoss is the lot's `initial_risk_dollars`, and `R_net = (P&L − costs) / MaxLoss`. The ledger handles **partial mleg fills** (paper fills 10% of orders partially, at a random size): a lot's contracts are what filled, and an unfilled remainder is cancelled, not chased. | TH, AI, ALP | Design choice | BUILD NOW |
| OPT-8 | **Per-trade cap:** budgeted loss ≤ 0.25% of *E* (half of 1R, about $250). `contracts = floor(cap / budgeted loss per contract)`; 0 means no trade. Never round up. The owner may raise the cap by hand to 0.5% of *E* (1R) only after an OPT-40 pass **at the width being traded**, with ≥ 30 closed paper spreads, E_net > 0, and E_net above BIL (OPT-38). At about half of months eligible, 30 spreads take about 5 years. Never higher under this rulebook. | TH, MW, M-10 | Moderate (principle) / Weak (number) | BUILD NOW |
| OPT-9 | **Book caps:** total open budgeted loss ≤ 1.0% of *E*; at most 3 open spreads; at most 1 new spread per week. **Assignment cover:** the account's cash not committed to the rules book must be at least Σ (short strike × 100 × contracts) over all open short legs, so every short put could be assigned at once without a margin call. At $100k and SPY near $770, this allows one open spread. | MK, PB, ALP | Weak (numbers) / Design | BUILD NOW |
| OPT-10 | **Greek caps:** \|Σ delta × 100 × contracts × SPY price\| ≤ 20% of *E*; total short vega ≤ 0.05% of *E* per volatility point. Greeks come from the broker snapshot; missing greeks block entries (OPT-27). At 1–2 contracts these caps never bind; they are backstops. | Design | Design choice | BUILD NOW |
| OPT-11 | The owner's report shows O's delta notional next to the rules book's SPY holdings, so the combined SPY exposure is visible. No cross-account clipping (an exception to RISK-5 and RISK-6; see "What this changes"). | GR | Design choice | BUILD NOW (display) |

*Worked example, from the real chain of 25 Sep 2026 (SNAP).* SPY $771.35, *E* = $100,000, cap $250. The 20-delta short put for 6 Nov is the $741 strike (bid 4.74, ask 4.96).

| Width | Mid credit | MaxLoss per contract | Quoted cost (share of credit) | Budgeted loss | Contracts at $250 |
|---|---|---|---|---|---|
| $2 | $0.22 | $178 | $0.48 (218%) | $226 | 1, but OPT-13 blocks it |
| $3 | $0.37 | $263 | $0.42 (114%) | $305 | 0 |
| $5 | $0.60 | $440 | $0.40 (67%) | $480 | 0 |

For 30 Oct (short $744), the $2 spread paid $0.175 with a quoted cost of $0.05 (29%), which also fails OPT-13's 20%. So on that day the book would not trade. The credit is about 11% of the width. Neither expiry is the standard monthly (20 Nov was 56 DTE); they only illustrate the arithmetic.

## (c) Liquidity and execution

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| OPT-12 | **Per-leg filter:** `tradable`; open interest ≥ 500 (from `get_option_contracts`, which reports the prior day's figure with `open_interest_date`); day volume ≥ 50 (from `get_option_bars`; the snapshot has no volume); bid > 0; quote timestamp at or after 15:45 ET today; leg ask − bid ≤ max($0.05, 5% of mid). All quotes, IV and greeks come from Alpaca's free **indicative feed**, which is derived from OPRA but is not real OPRA quotes; every report says so. | RET, RPL, ALP | Strong (costs matter) / Weak (thresholds) | BUILD NOW |
| OPT-13 | **Spread filter:** quoted cost ≤ 20% of the spread's mid credit. Otherwise skip. On the 25 Sep snapshot every affordable spread failed this (29% and 218%). **Decision:** keep 20% and do not relax it on end-of-day indicative quotes. The shadow book reports the **no-trade rate** (share of eligible months blocked by this rule) as a result in its own right, and measures the same spreads on the 15:45 ET snapshots (OPT-17). After 40 sessions the owner chooses: keep 20%, buy OPRA quotes ($99 a month), or relax to a stated threshold with full costs charged. | RET, SNAP | Moderate | BUILD NOW |
| OPT-14 | **Limit orders only**, never market: `mleg`, `LIMIT`, `DAY`, integer qty, no extended hours. **Sign:** alpaca-py treats a negative mleg `limit_price` as a credit and a positive one as a debit, so a credit entry sends a negative limit and a debit close a positive one. Code rejects an order whose sign does not match its intent. Minimum credit = mid credit − 10% of quoted cost. Unfilled → the order expires at the close; the next OPT-17 run re-prices once at mid credit − 25% of quoted cost; then the idea is dropped for that month. | ALP, RET | Moderate | BUILD NOW |
| OPT-15 | **Exits** close the whole spread in one `mleg` order with `*_TO_CLOSE` intents; never leg out. **Ladder**, one try per run: try 1 at mid; try 2 at the natural price; then marketable limits at natural + $0.05 more each try. **Forced exits** (OPT-23, OPT-31, OPT-26, and any exit after DTE ≤ 5) start at the natural price. Never pay more than width × 100 per contract to close. A spread still open at DTE ≤ 2 freezes new entries and alerts the owner. | ALP, ASN | Design choice | BUILD NOW |
| OPT-16 | **Honest costs:** log bid, ask and mid at decision and at fill; `slippage = fill − mid` in $ and % of mid. Report results twice: at the paper fill, and under the cost model (half the quoted cost at entry, half the logged quoted cost at exit, plus fees). Paper charges no fees and fills at the NBBO without checking size. Also report SPY's move from the decision close to each fill: a credit limit fills more easily after SPY falls, so paper fills can be adversely selected. | ALP, EX-5 | Design choice | BUILD NOW |
| OPT-17 | **Order run at 15:45 ET** (entries and exits). Before submitting, code refetches the chain and re-checks the short put's \|delta\| (0.15–0.25), OPT-8 to OPT-10, OPT-12 and OPT-13 on fresh quotes. It cancels the entry if SPY is more than 1% from the decision close. It also logs a chain snapshot for OPT-13. Orders are never queued overnight. Comparing a 10:15 ET run with 15:45 ET is logged only (TEST FIRST). | RET (Muravyev–Pearson, snippet), B-7 | Weak (timing) / Design | BUILD NOW |

## (d) Entry: one structure

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| OPT-18 | **Monthly SPY bull put spread.** Target 35 DTE to the standard monthly expiry (DTE from `expiration_date`). The first decision is at the first run with DTE ≤ 36. If anything blocks it (regime, filters, a skip, no fill), it retries at each run until DTE < 30, then the cycle is lost. Short put with \|delta\| 0.15–0.25, nearest 0.20. Long put at the widest strike ($1 steps, $2–5 wide) whose budgeted loss fits OPT-8; today that is about $2. At most one new spread per monthly cycle. | BO19, CBF, RPL, VEN | Moderate (premise) / Weak (parameters) | BUILD NOW |
| OPT-19 | **Regime permission** (REG-2 labels), checked at each run in the entry window: bull_calm 1; bull_volatile 0.5 (contracts halved and rounded down, so **1 contract always becomes 0**); choppy, bear and panic 0. In practice only bull_calm trades: about half of months in 2017–2026 (REG-2 recomputed on SPY closes). A regime change after entry does not close the spread. Exits are always allowed. | BO19, CBF, REG-3 | Moderate | BUILD NOW |
| OPT-20 | Gate variants, logged only: (i) no entry when VIX/VIX3M > 1; (ii) the reverse idea, entering after volatility spikes when premiums are richest. | VEN (CAIA, snippet) | Weak | TEST FIRST |
| OPT-21 | FOMC and CPI dates inside the holding window are shown to Claude, not blocked on. | RET (de Silva et al. is single-stock earnings) | Weak | BUILD NOW (display) |

## (e) Exits (code-enforced at every daily run, on closing marks)

Priority: assignment clean-up (OPT-26) > expiry exit > short-strike exit > book breakers. **Exits never wait for option data.** They trigger from the SPY close and DTE alone. If a leg's quote is missing or stale, the exit is priced at the width cap (OPT-15), which fills at the best available price up to that cap. Only entries block on missing data.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| OPT-22 | **Expiry exit:** close at the first run with DTE ≤ 7, using the OPT-15 ladder. Never hold into expiry week. Alpaca starts its own expiry handling at 3:30 pm ET on expiry day, and this system cannot manage that. | ALP, ASN | Strong (mechanism) / Design (7 DTE) | BUILD NOW |
| OPT-23 | **Short-strike exit:** if SPY closes below the short strike, close the spread at the next order run, starting at the natural price. An in-the-money short put can be assigned early, more so with T-bill yields near 4%. There is no rule for an IV spike or widening quotes before the strike is breached (in August 2024 put spreads widened sharply); the width cap limits the damage. A gap through both strikes costs MaxLoss plus exit costs. | ASN | Moderate | BUILD NOW |
| OPT-24 | No rolling, no adding to a spread, and no second spread in the same expiry after a loss exit. Rolling a loser hid over $50M of losses in the "Karen" case. | BLOW, MW, LF | Moderate | BUILD NOW |
| OPT-25 | Exit variants, logged only: take profit at 50% of credit; time exit at 21 DTE; stop at 2× and at 1× the credit; hold to 7 DTE only. Vendor backtests disagree on stops. | VEN | Weak (conflicting) | TEST FIRST |

## (f) Assignment, expiry and broker safety

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| OPT-26 | **Incident detector**, every run, from `positions` (paper posts `OPASN`/`OPEXC`/`OPEXP` activities only the next day, but still poll them): any stock, or any option leg without its partner, freezes new entries and writes a report. **Clean-up order:** stock plus the long put is still defined risk, so (1) sell the stock first with a marketable limit, then (2) close the long put. The reverse order leaves about $77k of unhedged SPY (77% of *E*) per contract. Never let an orphan long put reach expiry in the money: automatic exercise would create short stock, which is forbidden. Close it by DTE ≤ 2. | ALP, ASN | Strong (mechanism) | BUILD NOW |
| OPT-27 | **Data and reconciliation guard:** no new entries if a greek, IV or quote is missing or stale (OPT-12), if Alpaca's maintenance margin differs from width × 100 × contracts by more than $1 per contract (Alpaca's spread margin ignores premiums), or if a position does not match the ledger. | ALP, CODE | Design choice | BUILD NOW |
| OPT-28 | Call spreads, with an ex-dividend guard (close if a short call is in the money with extrinsic value < 1.5 × the dividend and the ex-date within 3 sessions). | ASN | Moderate | LATER |
| OPT-29 | Move to XSP (European, cash-settled, 1/10 of SPX: no early assignment or share delivery) once Alpaca serves its quotes and greeks. Tradable in paper since July 2026, but no market data yet. | ALP | Strong (contract terms) | LATER |

## (g) Breakers for book O

These are **backstops**. In units of budgeted loss at the 0.25% cap, the daily breaker is 2 full losses and the drawdown tiers are 4 and 8. The replay's worst year was −0.93R, about 1 loss. The per-trade and book caps (OPT-8, OPT-9) do the real work.

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| OPT-30 | Mark-to-market loss on a day ≥ 0.5% of *E* → no new entries the next session. Exits still run. | RISK-11 | Design choice | BUILD NOW |
| OPT-31 | Drawdown from O's own high-water mark: ≥ 1% of *E* halves OPT-8's cap; ≥ 2% of *E* closes every spread and halts O until the owner resets it (RISK-15 kill switch). Tighter than RISK-13's 3% / 5%, to match O's 1% exposure cap. | RISK-13, SS09 | Moderate (pattern) / Design | BUILD NOW |
| OPT-32 | Demotion as in M-11: with n ≥ 30 closed spreads and a one-sided 90% bootstrap upper bound of mean R_net < 0, O stops new entries pending owner review. | TH, M-11 | Moderate | BUILD NOW |

## (h) What Claude may and may not do

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| OPT-33 | Code builds a menu of **one** spread a month (or none). Claude may only `skip` it, with a CL-8 reason code (DATA_SUSPECT, HALT_OR_ILLIQUID, or SCHEDULED_EVENT on the order session only; see "What this changes") and evidence paths (CL-2). Claude never chooses strikes, widths, sizes or exits, and never computes greeks or MaxLoss. | AI, CL-1, CL-7 | Moderate | BUILD NOW |
| OPT-34 | Every skip opens a shadow spread at the modelled fill and needs a CL-5 prediction that argues **against** the trade: `{symbol: SPY, horizon: 20, direction: below, threshold_pct: short strike / close − 1, probability}`. Code drops a skip whose probability is not above the short put's \|delta\|, since that argues for the trade. Skips are scored as in M-6 but, at one a month, the scores are informational only (CL-9's code shrink does not apply). | DG, CL-5, CL-9 | Moderate | BUILD NOW |

## (i) Shadow signals, backtest and measurement

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| OPT-35 | **Chain logger**, at the after-close run and the 15:45 ET run: SPY, QQQ and IWM, 0–70 DTE, puts at 70–105% of spot and calls up to 115% of spot, **plus every held or shadow leg whatever its range**. Fields: bid, ask, quote time, IV, greeks, open interest with its date, and day volume, to `state/options/chains/<date>.parquet`, tagged with the feed. Also fetch the free Cboe VIX, VIX3M, VIX9D and SKEW CSVs for display (this makes REG-9's VIX display buildable). This is our only source of historical option quotes. | ALP, RPL | Design choice | BUILD NOW |
| OPT-36 | **Shadow book O:** the full O rules run on the logged snapshots and book shadow spreads under the cost model (entry at mid credit − ½ quoted cost, exit at mid + ½ quoted cost, plus fees), with the same exits and R. It runs before and alongside paper orders. | M-12 (v) | Design choice | BUILD NOW |
| OPT-37 | **Options backtester** (`trader/backtest_options.py`), using the RPL method on **raw** (not dividend-adjusted) closes. It always prints, next to the base: the **width actually traded** (as a share of spot and as fixed dollars), the doubled-cost run, the biased flat-volatility and realised-volatility runs, and a cross-check against Cboe PUT for 2008, 2018, 2020 and 2022. | RPL, BO19 | Moderate | BUILD NOW |
| OPT-38 | **Report**, per M-2: n, win rate, average win and loss in R, E = mean R_net, SQN, worst R, slippage in % of *E*, max drawdown, OPT-13's no-trade rate. Benchmarks: **zero**, and BIL earned on the collateral (width × 100 × contracts) over the same holding days. | DG25, M-1 | Moderate | BUILD NOW (report) |
| OPT-39 | Shadow-only variants: the same put spread on QQQ and IWM; a put spread on every B signal; a call spread on every C signal. The replay already found all three at or below zero. | RPL | Weak–Moderate | TEST FIRST |
| OPT-40 | **Options TEST FIRST → BUILD**, all required: (i) the OPT-37 backtest 2016–2026 at the width to be traded, plus real Alpaca bars since Feb 2024; (ii) the gain survives doubled costs; (iii) the sign holds when each parameter moves ±25%; (iv) ≥ 30 shadow or paper spreads agree in sign; (v) **E_net > 0 and above BIL (OPT-38) in both the backtest and the shadow or paper results**; (vi) owner sign-off. At most one promotion per quarter. | M-12, TH | Strong (process) | BUILD NOW (process) |

## (j) Going-live gates

| ID | Rule | Source | Grade | Status |
|---|---|---|---|---|
| OPT-41 | **Paper-start gate** (shadow → paper orders), all required: OPT-35 to OPT-38 and the OPT-17 order run built and tested; ≥ 40 sessions with a complete logged chain (a missing day does not count and does not reset the count); ≥ 2 monthly shadow cycles; the model's gross mid credit within 0.8–1.25× the logged gross mid credit, as a median over every entry-window session of those cycles (n ≥ 10); the no-trade rate reported (OPT-13); the shared-account separation is built and tested (O's orders tagged `OPT-`, each book reconciles and cancels only its own orders and positions, O's assigned stock never enters the rules book); the owner says yes in writing. | GR, ST | Design choice | BUILD NOW |
| OPT-42 | **No live options under this rulebook.** Live would need M-10 (≥ 100 closed spreads, SQN ≥ 2: at least 16 years at about half of months, longer after skips and OPT-13 no-trades), G-1 to G-7, the owner's own live options approval (Alpaca may grant a new trader level 1 or 2, not 3), and an account where one spread's budgeted loss is ≤ 0.5% of *E*. The planned $100 live account can never meet this: one spread would be 30–100% of it. | M-10, G-gates, ALP | Strong (arithmetic) / Moderate (approval) | BUILD NOW (policy) |

## Conflicts resolved

1. **"Sellers get paid" versus "the edge has faded".**
   - *The conflict:* the volatility risk premium is decades-strong (BO19), but since 2007 PUT's Sharpe trails the index, DG25 finds zero alpha, and our replay gives about zero at best.
   - *Decision:* run O as a measurement experiment, judged against zero and BIL (OPT-38), at a quarter of the equity books' per-trade risk.
2. **Cash-secured put-writing (the best-documented index) versus account size.**
   - *The conflict:* one SPY put controls about $77k, 77% of *E*, breaking the 30% ETF cap on its own.
   - *Decision:* spreads. The long leg gives back part of the premium (the out-of-the-money puts it buys are the most overpriced part of the market), but it caps the crash loss and removes the margin-call channel that SS09 shows can wreck short-option returns.
3. **Stop-losses on credit spreads.**
   - *The conflict:* Option Alpha found stops cut drawdowns; FlashAlpha found a 2× stop worse than none.
   - *Decision:* the spread's structure already caps ruin. Base exits are 7 DTE and the short-strike exit; stop variants are shadows (OPT-25).
4. **Block entries in bad regimes versus "premiums are richest after spikes".**
   - *Decision:* survive first. No entries in choppy, bear or panic (OPT-19). The reverse is a shadow (OPT-20). 2022 shows selling cushioning a slow bear, but 2008 and 2020 show the loss arriving at the bottom.
5. **How much retail really loses.**
   - *The conflict:* de Silva et al. find retail losing 5–9% around earnings announcements (10–14% around high-volatility ones); Bryzgalova et al. report an aggregate loss (about $2.1B), not a per-trade figure; Bogousslavsky and Muravyev find −0.9% per trade for a relatively sophisticated sample.
   - *Decision:* all agree costs dominate. Limit orders at or near the mid (OPT-14) are sensible, but no cited study measures their effect, so we measure our own slippage (OPT-16).
6. **Start at 1R or below it, and which width.**
   - *The conflict:* the tested spread (2% of spot, about $15, MaxLoss near $1.4k) does not fit any cap this book allows. R is measured per contract, so position size does not change it. The replay's negative results come from **narrower widths**, where costs are a bigger share of the credit: −0.016R at $5-equivalent, −0.052R at $3, −0.076R at $2. A smaller cap forces a narrower, worse spread.
   - *Decision:* keep 0.25% of *E* and accept a structure the replay expects to lose slightly (about $14 a trade), because O exists to measure costs and mechanics. Raising the cap goes only through OPT-8's gate. The tested width at 0.25% would need about $560k of O equity, unlike any account the owner will run.
7. **Let Claude pick strikes, or only skip?**
   - *Decision:* skip only (OPT-33). LLMs build the right structure but misjudge the risk numbers (TraderBench greeks accuracy scores 18–53 out of 100).
8. **Separate account versus a shared ledger.**
   - *Decision (owner, 28 Sept 2026):* a shared account with a strict ledger split. O's orders carry the `OPT-` prefix; each book reconciles, cancels and values only its own orders and positions; stock from an O assignment is O's to sell; the rules book's equity excludes O. Because the rules book invests most of the cash, the assignment-cover check (OPT-9) may block O's entries until cash allows; that no-trade result is reported, never bypassed. A separate account remains the cleaner option later.
9. **Leg spread threshold of 10% (practitioners) or 5% (system-fit note).**
   - *Decision:* 5% of mid, with a $0.05 floor. SPY's real leg spreads (about 2% of mid) usually pass, and the tighter filter only blocks bad quotes. The binding cost test is OPT-13.
10. **A cost filter that blocks every affordable trade versus one loose enough to trade.**
    - *Decision:* keep 20%, report the no-trade rate, and measure 15:45 ET quotes before the owner decides (OPT-13). A book that never trades is an acceptable result for a measurement experiment.

## Rejected

- **Long calls or puts as directional bets:** they pay the volatility premium, time decay and the spread (CS01, LEV). Our trend signals are better expressed in shares.
- **Protective puts or collars on sleeve A:** about −1.8% a year of alpha, and holding less stock did better (AQR). A's trend rule already steps out of falling assets. The replay put the drag at 2.4% a year.
- **Cash-secured puts instead of BIL:** adds equity beta (about 0.56) exactly when A has stepped into cash, and one contract needs $77k.
- **Covered calls and buy-writes:** mostly equity beta; the paying part is under 10% of the risk (AQR), and Sharpe is level with the index (CBF).
- **0DTE:** retail lost about $241k a day, mostly to costs (0DTE), and it needs intraday management a once-a-day system cannot give.
- **Iron condors, straddles and strangles:** the call side collects little premium, doubles costs and loses in rallies; evidence is vendor-only. Strangles are naked.
- **Option versions of sleeves B and C for trading:** the replay found both worse than shares (C's spread capped its +15R winners; B's spread lost −0.125R). Shadow only (OPT-39).
- **Single-stock premium selling and DIA:** earnings jumps and quoted spreads of 11–48% of mid.
- **Rolling for credit, and "steady monthly income" framing:** that is how every blow-up in BLOW looked until the crash.
- **LLM options success stories:** unaudited and survivorship-biased.

## Implementation plan (fits the existing `trading/` code)

**Phase O0: data, no risk.**
- `data.py`: fetch `Adjustment.RAW` bars for anything strike-related (the current `Adjustment.ALL` bars put SPY's 2016 closes 17.8% below traded prices). Add `option_chain(underlying)` via `OptionHistoricalDataClient.get_option_chain` (indicative feed, tagged), open interest via `get_option_contracts`, day volume via `get_option_bars`, and a Cboe index CSV fetch.
- New `trader/options/logger.py` for OPT-35, run after the close and at 15:45 ET. Add `vix`, `vix3m` and `skew` to the context as display only.

**Phase O1: models and shadow.**
- `models.py`: `OptionLeg` (OCC symbol, type, strike, expiry, side, qty) and `SpreadLot` (legs, width, credit, `max_loss`, `budgeted_loss`, contracts, `initial_risk_dollars`, `events[]`).
- `ledger.py`: multi-leg and partial fills, and R from MaxLoss (OPT-7).
- New `strategies.sleeve_o`: builds the single OPT-18 candidate after OPT-12, OPT-13 and OPT-19.
- `shadow.py`: shadow O lots (OPT-36), skip shadows (OPT-34), and the OPT-20, OPT-25 and OPT-39 variants.

**Phase O2: backtester.** `trader/backtest_options.py` (OPT-37), reusing `backtest.py`'s calendar and metrics, with the calibration table stored in `config/options_skew.yaml`.

**Phase O3: risk.** A separate `RiskEngine._apply_options()` path; the stock path is unchanged. It enforces OPT-3, OPT-5, OPT-8 to OPT-10, OPT-14, OPT-15, OPT-22 to OPT-24, OPT-26, OPT-27, OPT-30 and OPT-31. New policy block, separate from `account.options: false`:

```yaml
options_book:            # book O only; books A-D keep account.options: false
  enabled: false
  underlyings: [SPY]
  max_budgeted_loss_per_trade_pct: 0.0025   # MaxLoss + quoted cost at entry
  max_open_budgeted_loss_pct: 0.010
  max_open_spreads: 3
  max_new_per_week: 1
  require_assignment_cover: true            # equity >= sum(short strike x 100 x qty)
  max_delta_notional_pct: 0.20
  max_short_vega_pct: 0.0005
  entry_dte: {first: 36, last: 30}
  min_dte_entry: 25
  exit_dte: 7
  alert_dte: 2
  leg_filter: {min_oi: 500, min_volume: 50, max_spread_pct: 0.05, max_spread_abs: 0.05, quote_after_et: "15:45"}
  max_quoted_cost_pct: 0.20
  exit_ladder: {try1: mid, try2: natural, step_abs: 0.05, cap: width}
  entry_recheck: {max_spx_move_pct: 0.01}
  permission: {bull_calm: 1.0, bull_volatile: 0.5, choppy: 0, bear: 0, panic: 0}
  breakers: {daily_loss_pct: 0.005, dd_halve: 0.01, dd_halt: 0.02}
```

**Phase O4: broker.** `AlpacaPaperBroker.for_book("options")` already reads `ALPACA_OPTIONS_KEY`. Add:
- `submit_mleg()` with `OrderClass.MLEG`, `OptionLegRequest(symbol, ratio_qty=1, position_intent)`, `LIMIT` and `DAY`, and the OPT-14 sign check;
- mleg fills (including partial fills) in `order_fills`, OCC symbols in `positions`, an activities poll, and a margin read for OPT-27;
- the OPT-6 start-up checks and the 15:45 ET order run (OPT-17);
- a simulator that fills a limit spread only if it crosses the logged mid ± ½ quoted cost.

**Phase O5: session and Claude.** `session.prepare --book options` writes the one-item menu; `schemas.py` gains the O skip, its reason codes and the OPT-34 prediction check; `decisions.py` applies OPT-33.

**Phase O6: report.** OPT-38 in `metrics.py` and `__main__.py report`; OPT-41 and OPT-42 gate status.

**Tests to add:**
- an order that would leave a naked short leg is rejected, and so is a 3-leg or mixed-expiry order;
- a credit entry with a positive `limit_price`, or a debit close with a negative one, is rejected;
- sizing uses the budgeted loss, rounds down, and 0 contracts means no order;
- the 1% total, 3-spread, weekly, assignment-cover and delta caps each clip correctly;
- a spread at 7 DTE is closed; SPY below the short strike triggers a close at the natural price; a close never pays more than the width; DTE ≤ 2 with a spread open freezes entries and alerts;
- an exit fires with the option chain missing; an entry does not;
- after an assignment, the stock sell is sent before the long-put sale, and the put sale waits until the stock is flat;
- stock appearing in the O account freezes entries;
- margin equal to width × 100 × contracts passes OPT-27; a mismatch blocks entries;
- a partial mleg fill books only the filled contracts;
- an entry is cancelled when SPY has moved more than 1% since the decision close;
- a Claude skip opens a shadow spread; a skip with probability ≤ \|delta\| is dropped; a Claude strike choice is dropped;
- the stock path still rejects any OCC symbol;
- a non-paper base URL is refused.

## Rule count

| Status | Rules |
|---|---|
| BUILD NOW | 37 |
| TEST FIRST | 3 |
| LATER | 2 |
| **Total** | **42** |
