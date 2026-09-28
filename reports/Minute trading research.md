# Minute trading: what people do, and what the evidence says

*Research for a beginner who wants to learn intraday "minute trading" (scalping and day trading) on a paper account with small amounts. 28 Sep 2026. Public sources only. The numbers from our own test are in `Minute trading backtest results.md`.*

---

## 1. The short version

- **Most day traders lose money.** This is not a guess. It comes from complete records of millions of trades in Taiwan and Brazil.
- **A few intraday patterns have real published evidence.** The strongest are "intraday momentum" ideas on SPY. The popular chart setups (EMA crosses, previous-day-high breaks, VWAP-band fades) have **no** good evidence.
- **Costs decide everything.** Many "profitable" day-trading backtests leave out the bid-ask spread and slippage. Once those are added, several edges shrink to about zero.
- **Several famous papers are co-written by people who sell day-trading courses.** We still tested their rules, because the rules are public and exact.
- **Our own test agreed with the sceptics.** We ran 9 setups (plus 5 pre-set variants) on SPY and QQQ minute data from Sep 2024 to Sep 2026. **None made money after costs in the most recent 12 months.** Same-day options versions lost badly.
- **Scalp only in a separate paper account.** Scalping in the account the rules book uses would mix its profit and loss into the rules book (section 9).

---

## 2. What a minute trader actually does

- Watches 1-minute or 5-minute candle charts of very liquid symbols (SPY, QQQ, big tech stocks, index futures).
- Trades a small set of repeatable patterns: opening-range breakouts, VWAP (the day's volume-weighted average price), moving-average pullbacks, yesterday's high/low, opening gaps.
- Holds for minutes to a few hours. Is **flat by the close**, so nothing is held overnight.
- Uses a **stop** (a price where you admit you were wrong) and often a **target**.
- Makes many small trades. So the **spread** (the gap between the buy and sell price) and **slippage** (getting a worse price than you saw) are paid over and over.

A cousin who "trades the minute chart" is doing this. The question is not whether it can be done. It is whether the patterns earn more than they cost. Section 3 shows that most people who try do not.

---

## 3. Who wins at day trading? (large studies)

| Study | Who / where | What they found | Checked? |
|---|---|---|---|
| Barber, Lee, Liu & Odean (J. Financial Markets, 2014) | All day traders, Taiwan, 1992–2006 | **Less than 1%** can predictably earn money after fees | Yes, abstract read |
| Barber, Lee, Liu, Odean & Zhang, *Learning Fast or Slow* (2018 draft) | Same Taiwan data | **97%** of day traders can expect to lose money on a given day. **Over 75% quit within 2 years.** Day traders lost money as a group in **every one of 15 years** | Yes, text read |
| Chague, De-Losso & Giovannetti, *Day Trading for a Living?* (2020) | Brazil index futures, people who day traded 300+ days | **97% lost money.** Only **0.4%** earned more than a bank teller (US$54 a day). No sign of learning | Yes, abstract read |
| Jordan & Diltz (Financial Analysts Journal, 2003) | US day traders, 1998–99 | About **twice as many lose as win** | Yes, summary read. The "35% profitable" detail is not checked |
| Beckmeyer, Branger & Gayda (2023) | US retail same-day (0DTE) S&P 500 options | Retail lost **$241,000 a day** on average (2021–2023), and **$350,000 a day** after daily expiries began (May 2022). **Over 75%** of retail S&P 500 option trades are 0DTE | Yes, abstract read |
| ESMA (EU regulator), 2018 | Retail CFD accounts | **74–89%** of accounts lose money. Average loss per client **€1,600–€29,000** | Yes, press release read |

**What this means for you.** If you pick a setup from YouTube at random, the most likely result is a slow loss. That is why we test first, even on paper.

**A useful fact.** In US stocks, most of the long-run gain has come **overnight**, not during the day (Cliff, Cooper & Gulen). So a day-trading strategy gets no free "market goes up" boost. Its benchmark is **zero**, not buy-and-hold.

---

## 4. The setups we tested

All rules were fixed **before** testing. We used the published rules where they exist, and changed nothing after seeing results.

**Common rules for every setup**
- Data: Alpaca SIP 1-minute bars, regular hours (9:30–16:00 ET), 3 Sep 2024 to 25 Sep 2026 (513 sessions). History back to 2016 is available for a later, longer test.
- Decide at a bar's **close**. Fill at the **next bar's open**.
- Stops and targets are checked inside each 1-minute bar. If both could have hit in the same bar, assume the **stop** hit first.
- Everything is flat by **15:55 ET**. Some papers exit at 16:00; we note this.
- One position at a time per setup and symbol. $1,000 per trade.

### 4a. Setups with published evidence

| ID | In plain words | Entry | Exit | Source & what it claims | Costs in the source | Our test (last 12 months, after costs) |
|---|---|---|---|---|---|---|
| **ORB5_QQQ** | First 5-min candle up → buy; down → short | 9:35 open, in the direction of the 9:30–9:34 candle. No trade if open = close | Stop at the other end of the first candle. Target 10× risk. Else 15:55 | Zarattini & Aziz 2023: QQQ 2016–23, 24% win rate, +0.13R per trade | $0.0005/share, **no spread, no slippage** | Lost. Gross +0.15R over two years (the pattern replicated), but it faded to about 0R in 2026 |
| **NOISE_MOM_SPY** | Trade only when SPY moves further from its open than it normally does at that time of day | Check at :00 and :30 from 10:00 to 15:30. Buy above the upper band, short below the lower band. Bands = open × (1 ± 14-day average move at that minute), adjusted for the overnight gap | Exit when price crosses back through the band or VWAP (checked at :00/:30). Reverse if it breaks the far band. 15:55 | Zarattini, Aziz & Barbon 2024: SPY 2007–24, 9.7%/yr at 1×, Sharpe 1.24 | $0.0035/share **+ $0.001 slippage** | Lost on SPY |
| **VWAP_TREND_QQQ** | Above VWAP → long; below → short; flip on every cross | 9:31 open, by side of VWAP. Flip when a 1-min candle closes on the other side | The flip is the stop. 15:55 | Zarattini & Aziz 2023: QQQ 2018–23, +671%, Sharpe 2.1 | $0.0005/share, **no slippage** | About zero before costs, then a steady loss (16 trades a day) |
| **LAST30_MOM_SPY** | If SPY is up from yesterday's close at 10:00, buy at 15:30; if down, short | 15:30 open. Variants: use the return up to 15:30, or require 15:00–15:30 to agree | 15:55. The papers use the 16:00 close (we tested that too) | Gao, Han, Li & Zhou (JFE 2018): SPY 1993–2013, 6.67%/yr, **4.46%/yr after paying the spread**. Baltussen et al. (JFE 2021): the same effect in 60+ futures markets | Real bid/ask used | About +1 bp before costs, a loss after |

### 4b. Popular retail setups with no good evidence

These are here because this is what retail minute traders actually use. We expected them to fail after costs. They did.

| ID | In plain words | Entry | Exit | Our test |
|---|---|---|---|---|
| **ORB30_CLASSIC** (and ORB15) | Break of the first-30 (or 15) minute high/low | First 1-min close above the range high (long) or below the low (short), up to 14:59. One trade a day | Stop at the other side of the range. Target 1× range height. 15:55 | Lost |
| **EMA9_21_PULLBACK_5M** | In an uptrend (9 EMA above 21 EMA), buy a dip to the 9 EMA | A 5-min candle touches the 9 EMA and closes above it, green (mirror for shorts). 10:00–15:00 | Stop below the candle or the 21 EMA. Target 2× risk. 15:55 | Lost in year one, small plus before costs in year two. Not reliable |
| **PDH_PDL_BREAK_5M** | Break of yesterday's high or low | First 5-min close above yesterday's high, if the day opened below it (mirror for the low). 9:45–15:00 | Stop at the breakout candle's low/high. Target 2× risk. 15:55 | Lost |
| **VWAP_2SD_FADE_1M** | Buy big stretches below VWAP, sell big stretches above | A 1-min close more than 2 standard deviations from VWAP, with RSI(2) under 10 (or over 90). 10:00–15:30 | Back to VWAP, a 1-standard-deviation stop, 30 minutes, or 15:55 | Lost steadily |
| **GAP_FADE_SPY** | "Gaps get filled" | A gap of 0.5% or more, not filled by 9:34 → trade against it at 9:35 | Target yesterday's close. Stop 1× gap size. 15:55. We also tested the opposite ("gap-and-go") | Small plus on SPY with a very wide range; lost on QQQ. Gap-and-go lost |

### 4c. Not tested (and why)

| ID | Why not |
|---|---|
| ORB on "Stocks in Play" (Zarattini, Barbon & Aziz 2024) | Needs about 7,000 stocks, including delisted ones, to avoid survivorship bias. Using only mega-caps would change the published rule |
| Small-cap "Gap and Go" | Needs pre-market data, halts and wide small-cap spreads. Its best-known promoter paid a $3M FTC settlement (section 10) |

---

## 5. Honest verdict on the evidence

| Setup | Evidence quality | Survives realistic costs? |
|---|---|---|
| LAST30_MOM_SPY | **Best.** Two peer-reviewed JFE papers, and a plausible reason it works (option dealers and leveraged ETFs hedge near the close) | **Yes in the papers** (to 2013 for SPY, 2020 for futures). **No in our 2024–26 test.** One weak blog also says it went flat in 2022–26 |
| NOISE_MOM_SPY | Medium. Vendor authors, but it models commission **and** measured slippage | Claimed yes (2007–24). **No on SPY in our test.** One independent replication says it is quite cost-sensitive |
| ORB5_QQQ | Medium-low. Vendor authors, no spread or slippage, no out-of-sample test | **No.** The gross pattern replicated, but net was about zero or negative, as an independent CFD replication also found |
| VWAP_TREND_QQQ | Low. Vendor authors, no slippage, many flips a day | **No.** The most cost-sensitive setup |
| ORB30, EMA 9/21, PDH/PDL, VWAP fade, gap fade | **None** for these exact rules. Marshall et al. (2008): none of 7,846 popular intraday rules beat chance after correcting for data mining. Grant et al. (2005): the gap-reversal edge in S&P futures is "sharply reduced" by the spread | **No** |

**Why to stay sceptical even of "good" results:**
- **Published edges shrink.** Anomaly returns fall about 58% after publication (McLean & Pontiff 2016).
- **Testing many setups creates false winners.** With 28 setup-and-symbol tests, one or two look good by luck. We demanded p < 0.0018, not p < 0.05.
- **Paper trading is optimistic** (section 7).

---

## 6. Costs: what a trade really costs

**Shares (measured from SIP quotes on 28 Sep 2026):**

| | Median spread | 90th percentile | Median spread in bps | Size at the best price (median) |
|---|---|---|---|---|
| SPY (~$768) | 2.0¢ | 2¢ | 0.26 bps | bid 320 / ask 160 shares |
| QQQ (~$737) | 2.0¢ | 3¢ | 0.27 bps | bid 200 / ask 160 shares |

**Fees:**
- Alpaca charges no commission.
- SEC fee: **$20.60 per $1M of sales since 4 Apr 2026** (0.206 bps of what you sell).
- FINRA TAF: $0.000195 per share sold. Tiny. (A reported pause from 1 Oct to 31 Dec 2026 is **not verified**.)
- CAT fee: charged on both sides, but tiny.

**Same-day options (approximate, from Alpaca's "indicative" feed):**
- The real options feed (OPRA) is not enabled on this account. The free "indicative" quotes are, in Alpaca staff's words, "randomized a bit… not real data".
- SPY 0DTE at the money: premium $0.73–$1.68, spread 1–5¢, which is **0.8–3% of the price**.
- QQQ 0DTE: premium $1.1–$2.0, spread **0.7–4.4%**. 1DTE options are a bit cheaper to trade.

**Cost per side to use in backtests:**

| | Low | Realistic | Pessimistic |
|---|---|---|---|
| SPY/QQQ shares, bps of notional per side | 0.2 | **0.5** | 2.0 (the open, news, fast markets) |
| 0DTE/1DTE at-the-money SPY/QQQ options, % of premium per side | 0.5% | **1.5–2%** | 5%+ (late-day 0DTE under $0.30) |

**Put that next to how much prices move.** The median 1-minute SPY move is about 1.25 bps. A realistic round trip in shares costs about 1 bp, which is **about 80% of a typical 1-minute move**. Any minute strategy has to clear that every time. (The backtest's own "realistic" level was set more cautiously, at 1.5 bps per side. The results report shows both.)

---

## 7. Paper fills vs real fills

From Alpaca's paper-trading docs:
- Orders fill against the current best bid and offer, "based on real-time quotes". A limit order fills only once it becomes marketable.
- About 10% of the time an order gets a random partial fill.
- **Order size is not checked** against the size available at the quote.
- Not simulated: market impact, information leakage, **latency slippage**, **your place in the queue** for a resting limit order, price improvement, **regulatory fees**, dividends.

What this means for scalping:
- **Paper overstates resting limit orders.** A real order at the bid waits in line. On paper it fills as soon as the price trades through it.
- **Paper understates costs.** There are no fees and no latency slippage.
- **Option paper fills are unclear.** On a free data plan they may be priced from the randomised indicative quotes (not verified). Treat option profit and loss on paper as optimistic and noisy.
- **Do this:** record the bid and ask at the moment of each paper order, and apply the cost table in section 6 afterwards.

---

## 8. The Pattern Day Trader rule (as of 28 Sep 2026)

- The old rule: a margin account that made 4+ day trades in 5 business days needed **$25,000**.
- The SEC approved FINRA's replacement on **14 Apr 2026**. It removes the "pattern day trader" label and the $25,000 minimum. It replaces them with an **intraday margin** standard.
- It took effect on **4 Jun 2026**. Brokers may phase it in until **20 Oct 2027**, so other brokers may still use the old rule.
- **Alpaca adopted it on 4 Jun 2026: "Unlimited day trades."** Margin still needs about $2,000 of equity. An intraday margin shortfall brings a margin call due within 2 business days.
- **Checked on this paper account:** the PDT flags and counters come back empty. The margin multiplier is 2 (maximum 4). The options level is 3.
- **Cash accounts:** the PDT rule never applied. The limit there is settlement (T+1). Trading with unsettled money is a "good-faith violation".

---

## 9. Account safety: where to scalp

The rules book trades in one Alpaca paper account. The same-day options lab (`LAB-` orders) already runs there. We checked how the rules book reads that account.

**Why scalping in the shared account is a problem:**
1. **Profit and loss leaks into the rules book.** The rules book's equity figure removes only book O. So a scalper's gains and losses count as rules-book gains and losses. That affects its **daily loss breaker (1% of equity, about $1,000)**, its weekly and monthly limits, its high-water mark and drawdown, and its position sizes. A bad scalp day can stop the rules book's new trades. A good one can raise its peak permanently. **The options lab already causes this today** (worst case $750).
2. **Alpaca keeps one net position per symbol.** SPY and QQQ are rules-book symbols. A scalp short, or selling too many shares, eats into the rules book's own shares.
3. **A scalp that fails to flatten gets adopted.** At reconcile, leftover SPY shares are booked into the rules book's sleeve at the close, with a stop. After that the rules book trades them as its own.
4. **Wash-trade rejections.** Alpaca rejects an order when an opposite-side market or stop order on the same symbol is already open. The rules book's orders sit open from about 17:05 until the next 9:30 open. So scalp orders near the open can be rejected, or can cause the rules book's order to be rejected.
5. **Options are safer, but not clean.** The rules book ignores option contracts, so reconcile is safe. The profit-and-loss leak (item 1) remains. A long in-the-money 0DTE option left open at expiry is exercised into 100 shares per contract, which then hits item 3.

**Conclusion:**

| Choice | Verdict |
|---|---|
| **(b) A second Alpaca paper account for all scalping, shares and options** | **Recommended.** It is the only choice that keeps the rules book's equity, breakers, peak and holdings clean |
| (a) Option-only scalps in the shared account | A stopgap only: `SCALP-` order ids, long single options only, flat by 15:50, daily loss cap $250 or less, and the leak written down as known contamination. Our backtest also shows same-day option scalps losing heavily, so we do not recommend them at all |
| Share scalps in SPY or QQQ in the shared account | **Never** |

Separately, the main session should decide whether the rules book's equity should also exclude the options lab's profit and loss. Today it does not.

**Owner's steps for a second paper account:**
1. Log in at app.alpaca.markets and open the account switcher (top left).
2. Choose "Open New Paper Account". Set a starting balance of $2,000–$10,000. (Margin needs $2,000 of equity.)
3. Switch to the new account. Generate its own API key and secret. Keys belong to one paper account.
4. Save them as `ALPACA_SCALP_KEY` / `ALPACA_SCALP_SECRET`. Never reuse the `RULES` keys. Never commit keys.
5. Accounts cannot be reset. To start over, delete one and create a new one. Each owner may have 3 paper accounts.

(The button names come from Alpaca's docs. We did not click through them.)

---

## 10. Red flags for gurus, courses and Discords

Our rule: **distrust anything that is being sold.** Warning signs:

1. **Income or "verified P&L" claims.** The FTC sued Warrior Trading over ads like "$101,280.47 in verified profits… in under 45 days". It alleged "the vast majority of customer accounts actually lost money". The company settled for $3M (2022).
2. **"Double or triple your account" testimonials, and subscriptions that are hard to cancel.** The FTC's RagingBull case settled for $2.425M (2022).
3. **Discord and Twitter "I'm buying" alerts.** The SEC charged 8 influencers in an alleged $100M pump-and-dump (Dec 2022). They told followers to buy, then sold.
4. **The seller profits from selling, not from trading.** This applies to courses, memberships, prop-firm "challenges" and broker affiliate links. Even the ORB and VWAP papers are co-written by the founder of a paid day-trading community.
5. **Backtests with no spread and no slippage.** For small stops or many trades, the spread is the whole game.
6. **Leverage used to turn small edges into huge headlines.** TQQQ or 4× margin multiplies losses too, and does not create an edge. (In our test, 4× leverage turned ORB5's small costs into a -23% year.)
7. **Settings chosen after looking at the results.** Examples: "best stop = 5% ATR" from a heatmap, or a "top 25 stocks" list.
8. **No out-of-sample test and no year-by-year results.**
9. **Win-rate bragging.** A win rate without the average win, the average loss and costs means nothing. (ORB15 won 54% of its trades in our test and still lost money.)
10. **"You lose because of psychology — buy my mentorship."** The data say most people lose because there is no edge after costs.
11. **Urgency, guarantees, "no risk".** These are classic fraud signs according to the SEC.
12. **Screenshots or simulated accounts instead of full statements.**
13. **Pushing 0DTE options or leveraged products "for small accounts".**
14. **"Everyone watches this level, so it works."** Popularity is not evidence.

---

## 11. How to use this safely

1. **Backtest first,** with fixed rules and costs. Done: see `Minute trading backtest results.md`. Nothing passed.
2. **Paper-test only to learn and to measure costs.** Use a **separate paper account**, 1 share per trade, and a **$25 daily loss stop**. The full caps are in the results report, section 8.
3. **Keep a journal.** Record every trade, the reason for it, the quote at the time and the fill.
4. **Check the rules.** The $25,000 PDT minimum is gone at Alpaca, but other brokers may still apply it until Oct 2027.
5. **Real money only if** a setup is positive after measured costs over 60+ paper sessions **and** a longer backtest (2016–2024) agrees. Even then, start small. Based on today's results, expect that bar not to be met.

---

## Sources

**Strategy papers (read directly)**
- Zarattini & Aziz (2023), *Can Day Trading Really Be Profitable?* — SSRN 4416622: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416622 ; PDF: https://concretumgroup.com/wp-content/uploads/2026/02/Can-Day-Trading-Really-Be-Profitable.pdf
- Zarattini, Aziz & Barbon (2024), *Beat the Market: An Effective Intraday Momentum Strategy for SPY* — SSRN 4824172: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172 ; PDF: https://concretumgroup.com/wp-content/uploads/2026/02/Beat-the-Market.pdf
- Zarattini & Aziz (2023), *VWAP: The Holy Grail for Day Trading Systems* — SSRN 4631351: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4631351 ; PDF: https://concretumgroup.com/wp-content/uploads/2026/02/Volume-Weighted-Average-Price.pdf
- Zarattini, Barbon & Aziz (2024), *A Profitable Day Trading Strategy for the U.S. Equity Market* (Stocks in Play) — SSRN 4729284: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284
- Gao, Han, Li & Zhou (2018), *Market Intraday Momentum*, JFE 129 — https://www.sciencedirect.com/science/article/abs/pii/S0304405X18301351 ; PDF: https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/ee7dac49-530b-4950-b5d0-e0b5eee08f2e.pdf
- Baltussen, Da, Lammers & Martens (2021), *Hedging Demand and Market Intraday Momentum*, JFE 142 — https://www3.nd.edu/~zda/intramom.pdf
- Li, Sakkas & Urquhart (2021), *Intraday time series momentum: global evidence* — https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf
- Holmberg, Lönnbark & Lundström (2013), *Assessing the profitability of intraday ORB strategies*, FRL — http://www.econ.umu.se/ueslpnr/ues845.pdf
- Marshall, Cahan & Cahan (2008), *Does intraday technical analysis in the U.S. equity market have value?*, JEF — https://ideas.repec.org/a/eee/empfin/v15y2008i2p199-210.html
- Schulmeister (2009), *Profitability of technical stock trading: has it moved from daily to intraday data?* — https://www.wifo.ac.at/wp-content/uploads/upload-9748/WP_2007_323_.pdf
- Grant, Wolf & Yu (2005), *Intraday price reversals in the US stock index futures market*, JBF — https://ideas.repec.org/a/eee/jbfina/v29y2005i5p1311-1327.html
- Plastun, Sibande, Gupta & Wohar (2019), *Price Gap Anomaly in the US Stock Market* — https://ideas.repec.org/p/pre/wpaper/201963.html
- Cliff, Cooper & Gulen (2008), *Return Differences between Trading and Non-Trading Hours* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081
- McLean & Pontiff (2016), *Does Academic Research Destroy Stock Return Predictability?* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623

**Independent replications (low authority, not peer reviewed)**
- mql5 blog, ORB replicated on five index CFDs, gross reproduced and net about zero (25 Sep 2026) — https://www.mql5.com/en/blogs/post/776235
- Mesfin (2026), *Structural Limits of OHLCV-Based Intraday Momentum Signals in MNQ Futures*, arXiv — https://arxiv.org/abs/2605.04004
- francesco-nicolo, intraday-momentum replication (GitHub) — https://github.com/francesco-nicolo/intraday-momentum-replication
- firmtape, "Is intraday momentum still alive?" (blog) — https://dev.to/firmtape/intraday-momentum-is-dead-in-the-0dte-era-we-measured-it-on-1085-spx-sessions-43g0

**Day-trader outcomes**
- Barber, Lee, Liu & Odean (2014), JFM — https://faculty.haas.berkeley.edu/odean/papers/day%20traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf
- Barber, Lee, Liu, Odean & Zhang, *Learning Fast or Slow* — https://www.aeaweb.org/conference/2019/preliminary/paper/ZKnGb4Zh ; earlier draft: https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trading%20and%20Learning%20110217.pdf
- Chague, De-Losso & Giovannetti (2020), *Day Trading for a Living?* — https://ideas.repec.org/p/fgv/eesptd/525.html ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101
- Jordan & Diltz (2003), FAJ — https://rpc.cfainstitute.org/research/financial-analysts-journal/2003/the-profitability-of-day-traders
- Beckmeyer, Branger & Gayda (2023), 0DTE — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4404704 ; PDF: https://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-146-Leander-Gayda.pdf
- SEC DERA working paper (2025), *Hope at a Reasonable Price* (about costs, not profits) — https://www.sec.gov/files/dera-hope-reasonable-prc-2503.pdf
- ESMA CFD press release (2018) — https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors

**Costs, fills and account mechanics**
- SEC fee rate advisory 2026-2 — https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
- FINRA information notice (fee rates) — https://www.finra.org/rules-guidance/notices/information-notice-20260317
- Alpaca regulatory fees — https://alpaca.markets/support/regulatory-fees
- Alpaca paper trading — https://docs.alpaca.markets/us/docs/paper-trading
- Alpaca user protection (wash-trade check) — https://docs.alpaca.markets/us/docs/user-protection ; forum: https://forum.alpaca.markets/t/apierror-potential-wash-trade-detected-use-complex-orders/13441
- Alpaca forum on indicative option quotes — https://forum.alpaca.markets/t/what-is-the-indicative-pricing-feed-for-options/14595 ; https://forum.alpaca.markets/t/paper-trading-options-pricing/17795
- Alpaca forum on the number of paper accounts — https://forum.alpaca.markets/t/feature-request-more-paper-trading-accounts/18125

**Pattern Day Trader rule change**
- SEC approval (Release 34-105226, 14 Apr 2026) — https://www.sec.gov/files/rules/sro/finra/2026/34-105226.pdf
- Federal Register notice — https://www.federalregister.gov/documents/2026/04/17/2026-07485/self-regulatory-organizations-financial-industry-regulatory-authority-inc-notice-of-filing-of
- WilmerHale client alert — https://www.wilmerhale.com/en/insights/client-alerts/20260423-sec-approves-amendments-to-finra-rule-4210-replacing-day-trading-margin-requirements-with-a-modernized-intraday-margin-standard
- FINRA Regulatory Notice 26-10 — https://www.finra.org/rules-guidance/notices/26-10
- Alpaca: The Intraday Margin Rule — https://docs.alpaca.markets/us/docs/the-intraday-margin-rule ; blog: https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/
- FINRA Rule 2270, Day-Trading Risk Disclosure — https://www.finra.org/rules-guidance/rulebooks/finra-rules/2270

**Regulators and red flags**
- FTC v. Warrior Trading (2022) — https://www.ftc.gov/news-events/news/press-releases/2022/04/federal-trade-commission-cracks-down-warrior-trading-misleading-consumers-false-investment-promises
- FTC v. RagingBull (2022) — https://www.ftc.gov/news-events/news/press-releases/2022/03/online-investment-site-pay-more-24-million-bogus-stock-earnings-claims-hard-cancel-subscription
- SEC charges 8 social-media influencers (2022) — https://www.sec.gov/newsroom/press-releases/2022-221
- SEC Investor Alert, Social Media and Investing — https://www.sec.gov/resources-for-investors/investor-alerts-bulletins/ia_socialmediafraud

**Popularity (shows what retail uses, not whether it works)**
- https://www.warriortrading.com/opening-range-breakout/ · https://www.warriortrading.com/gap-go/ · https://ftmo.com/en/blog/opening-range-breakout-strategy-how-to-master-the-1530-us-session/ · https://crosstrade.io/learn/trading-strategies/opening-range-breakout · https://www.trade-ideas.com/learning-center/trading-strategies/opening-range-breakout-strategy/ · https://www.tradingview.com/script/W0EEFzqO-9-21-EMA-Pullback-Scalper-5m/ · https://www.tradingview.com/script/HeerhWmG-Premarket-Previous-Day-High-Low/ · https://members.bearbulltraders.com/magic-of-vwap-the-holy-grail-of-day-trading-systems/ · https://alphaarchitect.com/attention-prop-traders-the-first-half-hour-of-trading-predicts-the-last-half-hour/ · https://concretumgroup.com/beat-the-market-an-effective-intraday-momentum-strategy-for-sp500-etf-spy/

**Not verified (quoted elsewhere, but we could not read the original):** the "1.6% profitable in the average year" and "roulette" lines from an early Barber et al. version; the Brazil sample size of 19,646; the Jordan & Diltz "35% profitable / 14% > $10k" figures; the FINRA TAF pause from 1 Oct 2026; the per-contract option fee total (about $0.02–$0.06); whether Alpaca's paper engine prices option fills from indicative quotes.
