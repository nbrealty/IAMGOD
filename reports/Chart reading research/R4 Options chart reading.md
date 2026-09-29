# R4: How options traders read charts, and what the evidence says about minute-scale options trading

> **Read `00 Fact-check corrections (read first).md` alongside this file.** Written on 28 Sept 2026 by a research agent; four independent fact-checkers then reviewed its main claims, and where they differ from the text below, the corrections file wins. Scripts behind the researcher's own calculations are in `scripts/` (paths such as `work/`, `r5/` or `research/` in the text point there; they expect data files downloaded separately). Terms like verified / UNVERIFIED are the researcher's own tags.


*Research report for the IAMGOD paper-trading project. Written 29 Sep 2026. Research only: no orders, no broker or trading API calls, no repo edits, `options_lab.py` and the options book code not read. Everything below was found on the public web or computed by me from public files.*

**How to read this report**

- **verified** = I read it in the paper or on the official page (PDF text, the page itself, or the publisher-supplied abstract). **verified (abstract only)** = I read only the abstract. **UNVERIFIED** = seen only in a search snippet, a summary tool or a secondary source. Do not quote UNVERIFIED numbers as exact.
- **Strength scale:** Strong / Mixed / Weak / None / Not testable (with the data we have).
- **Preprint** = SSRN working paper, not peer reviewed. SSRN blocked my downloads (Cloudflare), so for SSRN-only papers I read the abstract text supplied through the Crossref record and did not read the full text.
- **My calculation** = my own arithmetic on public files or textbook formulas. Scripts are saved next to this file: `calc_bs_illustration.py` and `calc_vix_csv.py`. Downloaded files are in `_cache/`.
- **Honest limit of the search:** the session's web-search allowance ran out about two-thirds of the way through. After that I used direct page fetches and the Crossref and arXiv APIs. Gaps that resulted are listed in section 5.
- Rule IDs (MT-G7, MT-G23, MT-G24, MT-G28, MT-G29, MT-G35) are from `reports/Why day traders lose.md`.

---

## 1. Plain-English summary

1. Options traders look at three kinds of things beyond the price chart: how big a move the options market expects (VIX, VIX1D, implied volatility), what crash insurance costs (skew, term structure), and who might be forced to trade (open interest, put/call ratio, dealer "gamma").
2. Most of these numbers say **how big** the next move may be, not **which way**. For "how big" the evidence is decent: VIX and VIX1D forecast volatility, and a 2026 preprint finds that gamma built from free open-interest data predicts the next half-hour's variance on SPX, SPY and QQQ.
3. For **direction at minute scale** I found no credible after-cost evidence for SPY or QQQ. The direction evidence that exists is for single stocks over one day to a few weeks, needs paid trade-by-trade data, and faded over the sample in the one study that checked (Cremers and Weinbaum 2010).
4. "Gamma flip", "call wall" and "put wall" levels rest on a guess about who owns which options. Exchange data show dealers usually hold positive gamma and their hedging effect is small (Amaya et al. 2025). The only careful test of walls on SPY I found (a 2026 preprint) found them no different from neighbouring strikes. Treat all of it as claims to test.
5. The one strong peer-reviewed link is Baltussen et al. (2021): the last 30 minutes follow the earlier move only on days when estimated dealer gamma is negative (1996 to May 2020, R-squared 3.6%). A 2026 independent replication of a related SPY strategy weakened out of sample, and our own LAST30 result agrees (net negative).
6. **0DTE:** retail lost about $241,000 a day in SPX 0DTE (Feb 2021 to Sep 2023). Researchers disagree on how much was spread cost (Beckmeyer et al.: about 60%; SEC staff: limit orders are cheap). The most relevant rules paper (Vilkov) had a cost bug; after the August 2026 fix "no strategy or basket retains a positive net Sharpe ratio".
7. **Selling volatility** earns a premium on average but has crash risk: on 5 Feb 2018 the VIX rose 102% open to close and the inverse-VIX products were down 97% by the next open.
8. So our proxy result (same-day at-the-money options lose 4% to 47% of premium per trade) is what the literature predicts in direction. But a 33% loss is far more than spreads alone (about 3% to 4% of premium in my illustration), so run the decomposition (H3) before treating the size as a market fact.
9. **Defined-risk verticals at 7+ days (rule MT-G28)** cap the loss but add no edge. My calculation, assuming 1-cent half-spreads: four half-spreads cost about 1.8% of the amount paid for a $5-wide call spread and about 4 bps of its stock-equivalent exposure, against about 0.5 bps for one at-the-money call. Real SPY and QQQ quotes must be measured first.
10. **Free and useful:** Cboe's daily VIX, VIX1D (from May 2022), VIX9D, VIX3M, VVIX and SKEW files run to 28 Sep 2026. **Trap:** VIX1D rises through the day by construction (it closed above its open on 90.8% of 519 days, my calculation).
11. Alpaca's free options feed is "indicative"; an Alpaca-affiliated forum account (July 2024) says it is for debugging code, not for testing strategy efficacy. Real OPRA data costs $99 a month on Alpaca.
12. **Recommendation:** use options data only as risk, size and veto context computed by code; log the rest in shadow; run three cheap tests first (VIX1D yardstick, proxy decomposition, data audit); build no options-derived direction signal.
13. **Beginner message:** an option is a price for movement, not a shortcut. It multiplies costs. Read the VIX to know whether today is calm or nervous. Do not trade "levels" that come from someone's guess about dealer positions.

---

## 2. Findings table

Strength is about **predicting something useful for trading**, at the stated horizon, not about whether the concept is real. "After costs?" says whether the evidence I read included realistic trading costs.

| # | Item | What it is | Evidence and strength | Horizon and market | After costs? | Source with URL | Verified? |
|---|---|---|---|---|---|---|---|
| F1 | Implied volatility (IV) and the VIX level | The market's price for future swings, read from option prices. VIX = expected S&P 500 volatility over 30 days. Says size, not direction. | **Strong for volatility; None for direction.** IV holds information about later realised volatility beyond past volatility, but sits above realised volatility on average (the variance risk premium, see F19; Carr and Wu is the method paper for measuring it). | 1 day to 1 month; US equity indices | n/a (used as a filter) | [Christensen and Nielsen](https://doi.org/10.2139/ssrn.686021); [Carr and Wu](https://doi.org/10.2139/ssrn.577222); [Albers 2025](https://ideas.repec.org/a/wly/jfutmk/v45y2025i11p2092-2108.html) | verified (abstracts only) |
| F2 | IV rank and IV percentile | Where today's IV sits in the last 52 weeks. Rank = (now minus low) / (high minus low). Percentile = share of days with IV below now. | **Weak.** The rule is a broker/educator idea: high rank suggests selling options, low rank buying, because IV mean-reverts; the same page says profit is "by no means guaranteed". I found no paper testing rank rules after costs on SPY or QQQ. Nearest academic tests use different signals (see F4, F5). Example: VIX on 28 Sep 2026 = 16.07, 52-week range 13.47 to 31.05, so "rank" 15 and percentile 28% (my calculation). | Weeks to months; equity index options | Not tested | [tastylive definitions](https://www.tastylive.com/concepts-strategies/implied-volatility-rank-percentile); [Goyal and Saretto](https://doi.org/10.2139/ssrn.889947) | definitions verified (page read); absence of tests UNVERIFIED (search ended) |
| F3 | VIX1D | Cboe index of expected S&P 500 volatility for the **current day**, built from SPXW options expiring today and at the next expiry. Cboe history starts 13 May 2022; launch date 24 Apr 2023 is UNVERIFIED (taken from a Cboe press-release URL in search results). | **Mixed** (one peer-reviewed forecasting study plus one on its quirks). Raw VIX1D overestimates S&P 500 volatility; a simple adjustment gives next-day forecasts more precise than HAR models. It also has an "overnight bias": rises during trading hours, falls overnight. My calculation from Cboe's file, 3 Sep 2024 to 28 Sep 2026 (519 days): closed above its open on 90.8% of days; mean open 11.80, mean close 15.15. | Next day; S&P 500 | n/a | [Albers 2025](https://ideas.repec.org/a/wly/jfutmk/v45y2025i11p2092-2108.html); [Albers and Kestner 2024](https://ideas.repec.org/a/eee/finlet/v62y2024ipas1544612324002162.html); [Cboe method PDF](https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_1-Day_Volatility_Index.pdf); [Cboe VIX1D file](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX1D_History.csv) | abstracts verified; method PDF opened; CSV read; Albers' sample period not checked |
| F4 | Term structure (VIX9D, VIX, VIX3M; VIX futures curve) | Compares implied volatility at different horizons. Near above far ("backwardation") means stress. | **Mixed.** Johnson (2017): the slope predicts excess returns of variance swaps, VIX futures and straddles (payoffs from buying or selling volatility), not the future VIX itself. No evidence found that it predicts SPY direction. A 2026 preprint finds VIX3M/VIX and SKEW carry only weak calm-regime signals for overnight gap size. | Days to months; S&P 500 | Not shown in abstract | [Johnson 2017](https://ideas.repec.org/a/cup/jfinqa/v52y2017i06p2461-2490_00.html); [Maurer 2026 preprint](https://doi.org/10.2139/ssrn.6650858) | verified (abstracts only) |
| F5 | Skew or "smirk" (single stocks) | Out-of-the-money puts priced richer than calls; how steep. | **Mixed.** Xing, Zhang and Zhao: stocks with the steepest smirks underperform the flattest by 10.9% a year risk-adjusted, lasting at least 6 months. An, Ang, Bali and Cakici: rising call IV goes with higher next-month returns (about 1% a month spread between the top and bottom tenths of stocks). Long-short portfolios across many stocks. | 1 to 6 months; US single stocks | Not in abstracts | [Xing et al.](https://doi.org/10.1017/s0022109010000220); [An et al.](https://www.nber.org/papers/w19590) | verified (abstracts only) |
| F6 | Index skew and the Cboe SKEW index | Same idea for the index. | **Weak.** Kozhan, Neuberger and Schneider: almost half of the index implied-volatility skew is explained by a skew **risk premium**, i.e. skew is mostly the price of crash insurance, not a forecast. I did not find a verified test of SKEW as a direction signal. | n/a; S&P 500 | n/a | [Kozhan et al. (working-paper abstract)](https://doi.org/10.2139/ssrn.2565731); RFS version doi 10.1093/rfs/hht039 | verified (abstract only) |
| F7 | Put/call ratios (market level) | Puts traded divided by calls traded; read as a contrarian sentiment gauge. | **Weak.** Simon and Wiggins: VIX, put/call and TRIN were "frequently" significant contrarian predictors of S&P futures at 10, 20 and 30 days (Jan 1989 to Jun 1999; no costs). A 2026 preprint (1,027 days, May 2022 to Jun 2026): a gamma-weighted 0DTE put/call at the open relates to the next hour's return, but "out of sample, a rule built on the signal brings no statistically significant returns, before costs as much as after". Cboe's free put/call history files are stale (end 2012 and 2019). | 1 hour (preprint) to 30 days (old); S&P 500 and futures | 0DTE preprint: no edge before or after | [Simon and Wiggins](https://doi.org/10.1002/fut.4); [Maurer and Muller 2026 preprint](https://doi.org/10.2139/ssrn.7339718); [Cboe total put/call file](https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv) | verified (abstracts; CSV tails read) |
| F8 | Option-volume signals in single stocks (open-buy put/call; option-to-stock volume; call-put IV gap; IV changes) | Traders with news may use options first, so option activity may hint at the stock's next move. | **Mixed** for single stocks, **None** found for SPY or QQQ. Pan and Poteshman: low put/call stocks beat high by more than 40 bps next day and more than 1% next week. Johnson and So: lowest option/stock-volume decile beats highest by 0.34% a week (1996 to 2010). Cremers and Weinbaum: 50 bps a week, but "the degree of predictability decreases over the sample period", "consistent with mispricing during the earlier years". Goncalves-Pinto et al.: predictability mainly comes from stock **price pressure**, not option-market information. | 1 day to 1 week; US single stocks | Not in abstracts; Muravyev and Pearson (2020) say patient traders' effective spreads are below 40% of conventional measures, which changes cost conclusions | [Pan and Poteshman](https://econpapers.repec.org/article/ouprfinst/v_3a19_3ay_3a2006_3ai_3a3_3ap_3a871-908.htm); [Johnson and So](https://www.travislakejohnson.com/pdfs/Johnson%20So%20OS%202012%20(JFE).pdf); [Cremers and Weinbaum](https://ideas.repec.org/a/cup/jfinqa/v45y2010i02p335-367_00.html); [Goncalves-Pinto et al.](https://doi.org/10.1287/mnsc.2019.3398); [Muravyev and Pearson](https://doi.org/10.1093/rfs/hhaa010) | verified (Johnson and So full PDF; others abstracts) |
| F9 | Do option quotes lead the stock over seconds to minutes? | If options were ahead, option prices could act as an early warning. | **None.** Muravyev, Pearson and Broussard (tick data, 39 liquid stocks): option quotes adjust to the stock; "no economically significant price discovery occurs in the option market". | Ticks to minutes; US single stocks | n/a | [Muravyev et al.](https://econpapers.repec.org/article/eeejfinec/v_3a107_3ay_3a2013_3ai_3a2_3ap_3a259-283.htm) | verified (abstract only) |
| F10 | "Unusual options activity", sweeps, large prints | Scanners flagging big or aggressive option orders. | **Weak; not testable with free data.** Academic support is for signed open-buy volume from non-market-makers in single stocks (F8). A 2026 preprint finds 30-minute signed option order imbalance predicts **next-day** single-stock returns, strongest near the close. I found no primary evidence for "sweeps" or for SPY and QQQ. Needs signed OPRA trades (paid). Under MT-G23/24, log only, and only from code-computed OPRA data. | Next day; US single stocks | Not shown | [Lin, Luo and Shao 2026 preprint](https://doi.org/10.2139/ssrn.7318198) | verified (abstract only) |
| F11 | Open-interest walls, pinning, "max pain" | Big open interest at a strike may pull price toward it (pinning) or act as a barrier. | **Strong for one narrow thing, Weak for intraday walls.** Ni, Pearson and Poteshman (2005): on expiry dates optionable stocks' closes cluster at strikes, shifting returns by at least 16.5 bps (about $9 billion of value). Golez and Jackwerth (2012): S&P 500 futures are pulled toward the at-the-money strike on serial-option expiry days (at least $115 million notional per expiry day). But a **pre-registered SPY test** in the daily-expiry era (2026 preprint) found wall strikes "statistically indistinguishable from rank 2-5 GEX strikes" for break-resistance, pinning and volatility damping. "Max pain": only practitioner pages seen. | Expiry-day close (older data) versus intraday (2020s); stocks, S&P futures, SPY | Not tested | [Ni et al. 2005](https://doi.org/10.2139/ssrn.519044); [Golez and Jackwerth PDF](https://d-nb.info/1112655492/34); [Popovici 2026 preprint](https://doi.org/10.2139/ssrn.7082418) | Golez PDF verified; others abstracts only |
| F12 | Dealer gamma (GEX) as a **volatility** regime indicator | Estimate of whether option dealers' hedging calms moves (long gamma) or amplifies them (short gamma). | **Mixed, leaning useful for volatility; contested for 0DTE.** For: Ni et al. (2021; single stocks; the 2006 draft backs out market-maker positions from OCC customer and firm open-interest data); Amaya et al. (2025, Cboe trade data with trader type, SPX/SPXW, Jul 2020 to Jun 2023): dealer gamma is usually positive and lowers volatility, and at its worst adds 3.3 points to annualised daily volatility and 6.4 points to 30-minute volatility; Ardia and Vaudescal (2026 preprint): +1 standard deviation of non-0DTE net gamma from public open interest predicts next-half-hour variance about 36% lower, reproduces on SPY and QQQ, but its correlation with a dealer-inventory benchmark is 0.99 for non-0DTE and only 0.53 for 0DTE. Against or limits: Dim, Eraker and Vilkov (2024): 0DTE open-interest gamma "does not propagate past volatility"; Brogaard et al.: higher 0DTE share raises volatility; Singh (2026 preprint): flow-based gamma effect "improves in 2024 and reverses in 2025"; Hu et al. (2025): only 4 of 43 Korean market makers consistently delta-hedge. | 30 minutes to 1 day; SPX, SPY, QQQ | n/a (filter) | [Ni et al. 2021](https://econpapers.repec.org/article/ouprfinst/v_3a34_3ay_3a2021_3ai_3a4_3ap_3a1952-1986..htm); [Amaya et al. PDF](https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf); [Ardia and Vaudescal](https://doi.org/10.2139/ssrn.7202999); [Dim et al. PDF](https://westernfinance-portal.org/viewpaper?n=950096); [Brogaard et al.](https://doi.org/10.2139/ssrn.4426358); [Singh](https://doi.org/10.2139/ssrn.7350465); [Hu et al. PDF](https://www.fma.org/assets/docs/Derivatives2025/Muravyev.pdf) | PDFs read for Amaya, Dim, Hu; abstracts only for the rest (preprints) |
| F13 | Dealer-gamma sign and **direction** (intraday momentum or reversal) | Idea: when dealers are short gamma they hedge with the move (momentum); when long gamma, against it (reversal). | **Mixed, weakening.** Baltussen et al. (JFE 2021): last-30-minute return follows the earlier move when prior-day net gamma exposure (an open-interest proxy with stated assumptions) is negative (slope 0.066, t 4.78, R-squared 3.58%) but not when positive (slope 0.008, t 1.03, R-squared 0.05%); S&P 500 futures, Jan 1996 to May 2020; main results ignore costs; the paper says the futures version still has a positive net Sharpe ratio if costs are one tick. Paz (2026 preprint): an independent replication of a SPY intraday-momentum strategy fell apart out of sample (May 2024 to Mar 2026: 9.4% versus 29.5% buy-and-hold; Sharpe 0.39). Our lab: LAST30_MOM_SPY out of sample gross +0.96 bps, net -2.04 bps per trade at 1.5 bps a side. Adams, Fontaine and Ornthanalai (abstract seen only in a search snippet, UNVERIFIED): intraday variation in hedging needs predicts stronger order-flow reversals, lower momentum returns and lower volatility. | Last 30 minutes; S&P 500 futures and SPY | Mostly no | [Baltussen et al. PDF](https://www3.nd.edu/~zda/intramom.pdf); [Barbon and Buraschi](https://alexandria.unisg.ch/bitstreams/25fec636-90a2-4735-a3a4-dfc0b68d3feb/download); [Paz 2026](https://doi.org/10.2139/ssrn.7290621); [Adams et al. (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4881008) | Baltussen and Barbon PDFs read; Paz abstract only; Adams et al. UNVERIFIED |
| F14 | "Gamma flip", call wall, put wall (vendor levels) | Vendor-computed prices from open interest. Flip = where estimated net dealer gamma crosses zero. | **Weak.** No independent test of the flip level found. Wall test is a null (F11). The **sign** is an assumption: Chilingarian (2026 preprint) says public treatments "disagree-silently-on the one thing that determines its meaning: the sign", and flipping it inverts the regime. The original vendor paper (SqueezeMetrics, 2020) shows a scatter plot of GEX against one-day returns; a text search of all 12 pages finds no regression or significance test. Vendors sell subscriptions. | Intraday; SPX and SPY | Not tested | [SqueezeMetrics PDF](https://squeezemetrics.com/download/The_Implied_Order_Book.pdf); [Chilingarian 2026](https://doi.org/10.2139/ssrn.7131778) | SqueezeMetrics PDF read; Chilingarian abstract only; SpotGamma pages returned 403, not read |
| F15 | 0DTE volume share | Share of index option volume in same-day contracts. | **None as a trading signal.** Facts: SPX 0DTE averaged 2.3 million contracts a day, 59% of SPX volume, in 2025; Q2 2026 industry-wide 0DTE volume up 46.2% year to date to more than 20 million contracts a day. Cboe estimates retail at 50% to 60% of SPX 0DTE (Cboe earns from volume). Whether 0DTE raises or lowers volatility is contested (F12). | Context; SPX | n/a | [Cboe 2025 review](https://www.cboe.com/insights/posts/the-state-of-the-options-industry-2025); [Cboe Q2 2026](https://www.cboe.com/insights/posts/state-of-the-options-industry-options-market-continued-to-break-records-in-q-2-2026); [Cboe 0DTEs Decoded](https://www.cboe.com/insights/posts/0-dt-es-decoded-positioning-trends-and-market-impact/) | verified (page text) |
| F16 | How retail short-dated option traders fare | The people on the other side of the "cheap lottery ticket". | **Strong that the average result is negative** in several independent datasets; **disagreement about why.** Beckmeyer et al. (SPX 0DTE, Feb 2021 to Sep 2023): retail lost $241,000 a day ($350,000 since daily expiries in May 2022); roughly 60% of daily losses from transaction costs; multi-leg trades fare better than single-leg but also lose on average; short positions were profitable even after fees. Bryzgalova et al. (Nov 2019 to Jun 2021): weekly options average quoted spread 12.6% (effective 6.6%), retail lost $2.1 billion at a 10-day horizon, sellers of short-term options profited after costs. Bogousslavsky and Muravyev (5,182 traders, 2020 to 2022): only -0.9% per option trade on average, 0DTE trades 3 points lower, median hold half an hour; "concerns about severe retail option losses may be overstated". Bauer et al.: most investors incur "substantial losses" on options. SEC staff (Fu et al., 2025): patient limit orders cost about half as much as crossing the spread in their examples, so they doubt costs are the main loss. | Minutes to days; SPX, US options | Yes (net) | [Beckmeyer et al. PDF](https://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-146-Leander-Gayda.pdf); [Bryzgalova et al.](https://lbsresearch.london.edu/id/eprint/2827/); [Bogousslavsky and Muravyev PDF](https://www.brettonwoodsskiconference.com/uploads/b/f9bfc8b0-0251-11ed-a646-3dea17112d2f/An%20Anatomy%20of%20Retail%20Option%20Trading.pdf); [Bauer et al.](https://ideas.repec.org/a/eee/jbfina/v33y2009i4p731-746.html); [SEC DERA paper PDF](https://www.sec.gov/files/dera-hope-reasonable-prc-2503.pdf) | PDFs read for four; Bauer abstract only |
| F17 | Costs: SPY and QQQ option spreads, and time of day | What you pay to get in and out. | **Not testable with our data.** Facts: SPY and QQQ options quote in $0.01 steps at all prices; SPX/SPXW use $0.05 or $0.10 steps. In SPX 0DTE, relative spreads are highest at the open and the close and lowest 10:00 to 14:00 (Almeida et al.). SEC staff: at 1 pm in July 2023 the ATM SPXW bid-ask was one tick ($0.05) wide 64.7% of the time and two ticks 35.3%. Real SPY and QQQ spreads by time and expiry: **not verified** (no free real quotes). | Intraday; SPY, QQQ, SPX | Yes, but only SPX evidence | [SEC filing on penny pricing](https://www.sec.gov/files/rules/sro/cboe/2020/34-89075-ex5.pdf); [Almeida et al. PDF](https://www.fma.org/assets/docs/Derivatives2025/Almeida.pdf); [SEC DERA paper PDF](https://www.sec.gov/files/dera-hope-reasonable-prc-2503.pdf) | verified (PDFs read) |
| F18 | Time decay (theta) and gamma late in the day | Options lose value as the clock runs; near expiry the delta swings fast. | **Strong (arithmetic).** With one hour left, at-the-money gamma is about 12 times a 30-day option's, counting the hour as a trading hour (my calculation, IV 15%). Dim et al. quote "roughly 25 times" for IV 20%; the sentence I read does not state their time convention, so treat 12 to 25 as the range. A fairly priced option has about zero expected profit before spread; "decay" is how the price pays for movement, not an extra fee. Buyers lose to the spread, to the volatility premium and to having no direction edge. | Minutes to hours | n/a | [Dim et al. PDF](https://westernfinance-portal.org/viewpaper?n=950096); my calculation (`calc_bs_illustration.py`) | verified (quote); my calculation |
| F19 | Volatility risk premium and its crash risk | Options are priced for slightly more movement than usually happens, so sellers earn a premium, and sometimes lose a lot. | **Strong that the premium existed at monthly horizons in older data; Weak in 0DTE after costs; the tail is severe.** Coval and Shumway: zero-beta at-the-money straddles lost about 3% a week (S&P 500 options, Jan 1990 to Oct 1995). Bakshi and Kapadia: delta-hedged long S&P 500 option positions underperform zero. Almeida et al.: selling delta-hedged 0DTE at-the-money calls had mostly negative net Sharpe ratios with ask/bid pricing (2012 to Mar 2025). Vilkov: the 0DTE premium is small and hard to monetise after frictions. Augustin et al.: 5 Feb 2018 VIX +102% open to close, VIX futures index +72%, XIV and SVXY down 97% by the next open; combined assets $3.5 billion. | Weeks (old); intraday (0DTE); S&P 500 | Mixed | [Coval and Shumway PDF](https://backend.production.deepblue-documents.lib.umich.edu/server/api/core/bitstreams/3b55995a-7728-41ce-af29-a0ed1354ea76/content); [Bakshi and Kapadia](https://doi.org/10.2139/ssrn.267106); [Augustin et al. manuscript](https://utoronto.scholaris.ca/server/api/core/bitstreams/7f0a59c4-4070-4d48-ac2c-c42e7bb6ecbc/content) | PDFs read for Coval, Almeida, Augustin; Bakshi abstract only |
| F20 | Rule-based 0DTE strategies (enter 10:00, hold to close) | Straddles, condors, spreads, ratio spreads on SPX, with timing rules. | **None after costs.** Vilkov's replication package (SPXW 0DTE, Sep 2016 to Jan 2026): a units bug charged half-spreads at 1/100 of their size; after the Aug 2026 fix "no strategy or basket retains a positive net Sharpe ratio". Conditional put-ratio net Sharpe went from +0.93 to -0.75 and the top-three basket from +0.82 to -0.82. A May 2026 sign bug on short days was also fixed. Both found by outside users. The SSRN paper is still being revised. | Intraday to close; SPX | Yes (after fix) | [Vilkov repo README](https://github.com/vilkovgr/0dte-strategies); [Vilkov paper (SSRN)](https://ssrn.com/abstract=4641356) | repo files read (README, KNOWN-ISSUES, annotated paper); SSRN page blocked |
| F21 | Central-bank warnings about 0DTE | "Dealer hedging could amplify swings." | **None as trading evidence.** The ECB box (Nov 2023) is scenario reasoning ("might", "could"), not measurement; the measured papers above find small average effects. I did not find a Fed or BIS note specifically on 0DTE (search ended). | n/a | n/a | [ECB FSR box](https://www.ecb.europa.eu/press/financial-stability-publications/fsr/focus/2023/html/ecb.fsrbox202311_02~0cf2c71d00.en.html) | verified (page read) |
| F22 | An AI model "reading" gamma | Can a language model spot gamma-exposure patterns? | **None as trading evidence.** A paper reports 71.5% detection of dealer-hedging patterns from raw numbers with unbiased prompts (242 days of S&P 500 options). It measures pattern recognition, not returns. | n/a | n/a | [arXiv 2512.17923](https://arxiv.org/abs/2512.17923) | verified (abstract via arXiv API) |

### 2a. Horizon map (what, if anything, works at each speed)

| Horizon | What the evidence supports | What it does not support |
|---|---|---|
| Minutes | Nothing directional for SPY or QQQ. Only weak hints on volatility (gamma proxies, F12) | Any option-derived direction signal; option quotes leading the stock (F9) |
| Hours (30 minutes to 1 day) | Variance forecasts: VIX1D yardstick (F3), public-open-interest gamma (F12, preprint). Last-30-minute momentum on negative-gamma days, in 1996 to 2020 data (F13) | Wall or flip levels (F11, F14); 0DTE put/call at the open as a profitable rule (F7) |
| Days to weeks | Single-stock option-volume, skew and put-call-parity signals (F5, F8); old index put/call results (F7); expiry-day pinning at the close (F11) | Any of these on SPY or QQQ at minute scale; after-cost profits |
| Weeks to months | Term-structure slope for variance-selling payoffs (F4); volatility premium (F19) | Safe income: tail risk (Feb 2018) |

### 2b. Claims from non-academic sources (all are claims to test)

| Claim (source type) | Evidence status |
|---|---|
| "Positive GEX means calm, range-bound trading; negative GEX means trending and volatile" (GEX vendors) | Volatility half: supported by Amaya et al., Ni et al., and a preprint on public data. Direction half: partial (Baltussen, 1996 to 2020), unstable (Singh 2026), weakening out of sample (Paz 2026) |
| "The gamma flip is a pivot level" (vendors) | No independent test found |
| "Call wall is resistance, put wall is support, price is pulled to big strikes intraday" (vendors, max-pain sites) | One pre-registered SPY test found no wall effect (Popovici 2026). Older close-of-expiry-day pinning exists (F11) |
| "Dealers always delta-hedge, so open interest tells you their flows" (GEX method) | Doubtful: 4 of 43 Korean market makers consistently delta-hedge; S&P 500 market-maker volume is 32 times their net position change (Hu et al.) |
| "0DTE dealer hedging is destabilising" (media, some banks, ECB scenario) | Measured effects are small on average (Amaya et al., Dim et al.); Cboe says hedging is "de minimis", at best 0.2% of daily SPX liquidity (Cboe is an interested party) |
| "High IV rank means sell premium" (tastylive) | Definition verified; no after-cost test found (F2) |
| "Vanna and charm flows move the market" (SqueezeMetrics) | Vendor explanation only; no independent test found (UNVERIFIED absence) |
| "Unusual activity shows smart money" (scanners, social media) | Single-stock, day-to-week, signed-volume evidence only (F8, F10). Barred by MT-G23 and MT-G24 unless code-computed and shadow-only |

---

## 3. What we can test with our data

### 3.1 Data we have, or can get, and their limits

| Source | What | History | Cost and terms | Verified? |
|---|---|---|---|---|
| Our cache | SPY and QQQ SIP 1-minute bars | Aug 2024 to Sep 2026 | Already ours | from the brief |
| Alpaca historical stock bars (free plan) | SIP daily and minute bars | "Since 2016"; free plan has a 15-minute lag on the latest data | Free ([Alpaca docs](https://docs.alpaca.markets/us/docs/about-market-data-api)) | verified (page read) |
| Cboe daily index files | VIX (from 2 Jan 1990), VIX1D (from 13 May 2022; 1,097 rows), VIX9D (from 4 Jan 2011), VIX3M (from 18 Sep 2009), VVIX (from 6 Mar 2006), SKEW (from 2 Jan 1990); open, high, low, close; last row 28 Sep 2026 | see left | Free download, e.g. [VIX](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv), [VIX1D](https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX1D_History.csv), [SKEW](https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv). I found no licence text on these files. Cboe's put/call files say use is "subject to the Terms and Conditions of the Cboe Websites"; check before redistributing or commercial use. VIX1D has daily OHLC only, no intraday values | files downloaded and read on 29 Sep 2026; licence not found |
| Cboe put/call | Daily snapshot page (free); history files | History files end 7 Jun 2012 (index) and 4 Oct 2019 (total, equity). Current history needs [Cboe DataShop](https://www.cboe.com/us/options/market_statistics/historical_data/) (paid) or a forward log | see left | verified (files and page read) |
| Cboe delayed option chain (public JSON behind the website) | Whole SPY chain (13,294 series on 28 Sep 2026): bid, ask, IV, open interest, volume, delta, gamma, vega, theta; SPY 30-day IV field | Snapshot only, no history; quotes delayed | Free. **Terms for scheduled downloads UNVERIFIED.** May be Cboe-exchange quotes rather than the national best bid and offer (UNVERIFIED). URL: cdn.cboe.com/api/global/delayed_quotes/options/SPY.json | fetched once, fields inspected |
| Alpaca options "indicative" feed | Free options quotes and trades | Historical options data only since Feb 2024; free plan limited to the latest 15 minutes | Free. Alpaca: quotes are "not actual OPRA quotes, they're just indicative derivatives"; trades delayed 15 minutes. A reply from the Alpaca-affiliated forum account Dan_Whitnable_Alpaca (3 Jul 2024): use is "to debug ones code and not generally to be used for live trading or to test the efficacy of ones strategy" ([docs](https://docs.alpaca.markets/us/docs/historical-option-data); [forum](https://forum.alpaca.markets/t/what-is-the-indicative-pricing-feed-for-options/14595)) | verified (pages read) |
| Alpaca OPRA feed | Real consolidated options quotes | Real time | **$99 a month** (Algo Trader Plus, which also gives all-exchange stock data) ([docs](https://docs.alpaca.markets/us/docs/about-market-data-api)) | verified |
| Alpaca contracts reference endpoint | Per-contract `open_interest` and `open_interest_date` (docs show an example) | Daily, no history | Part of the trading API's reference data. **I did not call it.** The operations session should decide. | verified (docs read) |
| Massive (massive.com) | Options REST and streaming; docs list individual plans Options Basic free, Starter $29, Developer $79, Advanced $199 a month | see docs | What each tier includes: UNVERIFIED. "Individual use only" appears on the stock plan | prices verified; contents UNVERIFIED |
| ThetaData, Databento, OCC, FRED, SpotGamma pages | (not read) | | Pricing or terms pages were dynamic, blocked or errored | UNVERIFIED |

### 3.2 What each item lets us test

| Item | Data it needs | Free history? | Testable on history now? | Note |
|---|---|---|---|---|
| VIX and VIX1D as a yardstick for the day's size | Cboe files plus SPY bars | Yes (VIX1D from May 2022, VIX from 1990) | **Yes** | Cheapest, highest-value test (H1, H2) |
| VIX rank, VIX9D/VIX, VIX/VIX3M, SKEW | Cboe files | Yes | Yes | Low prior for direction; useful as regime flags |
| Put/call ratio | Daily put/call | No (stale) | No | Forward log only; the one careful test found no edge (F7) |
| Open-interest gamma, walls, flip level | Open interest by strike and Greeks, daily | No | **No** | Forward log only (H4, H5, H7); about 250 sessions to reach power |
| Unusual activity or signed option flow | Signed OPRA trades | No | No | Paid data; low prior; MT-G23/24 |
| Real option spreads for SPY and QQQ | OPRA quotes | No | No | One month at $99 would answer it (H8) |
| Why the 0DTE proxy lost 4% to 47% | The lab's saved trades | n/a | Yes, by the lab | H3 (I did not read the lab code) |

### 3.3 Shadow-mode hypotheses (no orders; answer to (c))

Common rules for all: no orders; each run is appended to the experiments log and counts toward N_trials (MT-G7); feed tags per MT-G35 (`OPTIONS_FEED = CBOE_CSV / CBOE_DELAYED / ALPACA_INDICATIVE / OPRA`); full regular sessions only; split dates fixed and written down before looking; where a trade is simulated, report gross and net at 0.5 and 1.5 bps a side as the backtest report does. Pure forecasting tests that only scale risk are not edge claims.

**Tier A: free, can run on history now**

- **H1: VIX1D as a yardstick for the day's realised volatility (risk scaling, no direction).**
  - Data: Cboe VIX1D file (1,097 rows, 13 May 2022 to 28 Sep 2026); SPY 1-minute SIP bars.
  - Definitions: for session t, RV_t = square root of the sum of squared 5-minute log returns from 09:30 to 16:00 (78 returns). Yardstick Y_t = VIX1D open on day t / 100 / sqrt(252). Second yardstick Y'_t = VIX1D close on day t-1 / 100 / sqrt(252). q_t = RV_t / Y_t.
  - Train: 13 May 2022 to 31 Dec 2023 (410 rows). Freeze k = median of q_t. Test: 1 Jan 2024 to 28 Sep 2026 (687 rows). Forecast = k times Y_t (and k' times Y'_t).
  - Benchmark: HAR-RV (yesterday's RV, mean of last 5, mean of last 22) fitted on the train period only.
  - Scoring: QLIKE loss on variance; one-sided Diebold-Mariano test with day-level HAC errors; also coverage = share of test days with |close-to-close return| at most 2 times k times Y_t (a well-calibrated yardstick gives about 95%).
  - Pass: lower QLIKE than HAR with DM p below 0.05 for at least one of the two yardsticks (2 trials).
  - If it passes: use only to scale stop and target distances and to skip days when Y_t is above its train-period 90th percentile. Never as a direction signal.
  - Why: Albers (2025) found the adjusted VIX1D forecasts next-day volatility better than HAR; the unadjusted index is biased upward (F3).
- **H2: same test with the long VIX history.** Y'' = VIX close on day t-1 / 100 / sqrt(252); SPY bars 2016 to 2026 (download from Alpaca); train 2016 to 2021, test 2022 to Sep 2026. Pass rule as H1 (1 trial). Purpose: check that H1 is not a short-sample fluke.
- **H6: big-move filter for the late-day momentum setups (cheap stand-in for the dealer-hedging story).**
  - Definitions: r_ROD(t) = return from the prior close to 15:30 (Baltussen's "rest of day" return; I did not read how the lab defines it, but the lab has a rest-of-day variant, LAST30_ROD_SPY). Z_t = r_ROD(t) / (VIX close on day t-1 / 100 / sqrt(252)). Flag F_t = 1 if |Z_t| is at least 1.0 (one fixed threshold, chosen now).
  - Test: run the lab's unchanged LAST30_ROD_SPY and LAST30_MOM_SPY functions on SPY bars from 2016 to 31 Aug 2024 (discovery, never touched by the lab) and on 1 Sep 2024 to 25 Sep 2026 (already seen unflagged). Compare mean gross and net bps for F=1 versus F=0. Counts as 2 trials.
  - Pass (all required, for a given variant): F=1 minus F=0 net difference above zero with t at least 3 in discovery, same sign out of sample, and the F=1 group's out-of-sample net mean above zero with a 95% day-bootstrap range above zero. Expect fail.
  - Prior: hedging flow scales with gamma times the size of the move (Baltussen); no paper tests this exact flag. Note the lab's out-of-sample gross for the rest-of-day variant was -0.36 bps (base LAST30_MOM_SPY: +0.96 bps), so the starting point is weak.
- **H3: decompose the 0DTE proxy loss (to be run by the operations session, not by me).**
  - For each setup's saved out-of-sample entries and exits, reprice the same-day option proxy four ways: (a) as is; (b) random direction, same times, 20 seeded draws per trade; (c) real direction but with the proxy's volatility set to that window's realised volatility; (d) zero spread.
  - Reading: (b) close to (a) means the signal added nothing and the loss is structural; (a) minus (c) is the size of any assumed-volatility premium; (a) minus (d) is spread cost. No new data needed.
  - Why: a 25-minute at-the-money call on SPY (S = 766, IV 15%) costs about $0.73 (my calculation), so a 1-cent half-spread is 1.4% of it and two sides about 3%. Even the proxy's own "2% of premium a side" rule is about 4%. A 33% average loss therefore needs an assumed-volatility gap or wrong-way direction.

**Tier B: free, needs a small forward log**

- **H0: is the indicative options feed good enough to compute anything? (data audit)**
  - Sample: SPY and QQQ; 10 sessions drawn with a seed written down first; 10:00, 12:00, 14:00 and 15:30 ET; per symbol the ATM call, ATM put and the calls and puts nearest +1%, -1%, +3%, -3% strikes; first expiry at least 7 calendar days out (12 contracts).
  - Compare the Alpaca indicative mid to a reference mid at the same second: real OPRA (a one-month $99 trial is the clean way) or the Cboe delayed chain (free but 15 minutes late, so compare at matching delayed times).
  - Metric: absolute percentage difference of mids; also spread widths.
  - Pass: median at most 2% and 95th percentile at most 10%. Fail: indicative data stay for code debugging only and are never used for IV, Greeks, gamma or costs. 1 trial (data audit).
- **H4: does public open-interest gamma predict the next half-hour's variance on SPY and QQQ? (volatility filter; forward log)**
  - Data: daily open interest by strike and expiry for SPY and QQQ (Alpaca contracts endpoint, or the Cboe delayed chain), logged each morning before 09:20 ET. Flat volatility sigma = VIX close on day t-1 / 100 (a deliberate simplification that needs no option quotes).
  - Definition: G_t = sum over calls of [Black-Scholes gamma(S, K, T, sigma) x open interest x 100 x S squared x 0.01] minus the same sum over puts, over expiries 1 to 45 days out (exclude 0DTE, where the proxy is weak, F12). S = prior close. Sign convention stated: calls +, puts - (the Baltussen and SqueezeMetrics convention, which Chilingarian calls "Model A"; it assumes customers are long puts and short calls). z_t = (G_t minus its 60-day mean) / its 60-day standard deviation.
  - Outcome: for each 30-minute block b, V_(t,b) = sum of squared 1-minute log returns. Regression: log V_(t,b) = a_b + beta x z_t + gamma x log V_(t-1,b) + error, day-level HAC errors.
  - Pass: beta below 0 with |t| at least 3, for SPY and QQQ separately (Holm correction), after at least 250 logged sessions, with the same sign in both halves of the log.
  - If it passes: reduce size or skip entries in the highest predicted-variance quintile. Never adds trades.
- **H5: Baltussen conditional momentum, forward (direction; slow; run only if H4 passes).**
  - Tag each day with sign(G_t). Run the lab's LAST30_ROD_SPY (Baltussen's rest-of-day version) and LAST30_MOM_SPY functions unchanged. Compare mean gross bps, and the slope of the last-30-minute return on the earlier return, between G<0 and G>=0 days.
  - Baltussen's values for reference: slope 0.066 (t 4.78) on negative days, 0.008 (t 1.03) on positive days (a 1% earlier move goes with about a 0.066% last-half-hour move).
  - Power (my calculation): with R-squared 3.6%, about 242 negative-gamma days are needed for t = 3. In the 0DTE era dealers' gamma is "typically positive" (Amaya et al.), so this may need 2 or more years of logging.
- **H7: wall null replication (low priority; only if the owner is curious).** Each session at 09:30, wall = SPY strike with the largest open-interest-weighted gamma within 2% of the open; controls = ranks 2 to 5. Measure over the next 60 minutes: (i) whether price crosses the strike, (ii) dwell time within 0.05% of it, (iii) realised variance within 0.1% of it. Paired day-level bootstrap, wall versus controls. Expected result, from Popovici: no difference.

**Tier C: paid or owner's decision**

- **H8: real spread study for the MT-G28 verticals.** Rent one month of OPRA ($99). For 20 sessions, at 10:30 and 14:30, record NBBO bid and ask for SPY and QQQ: ATM call, ATM put, and both legs of a 5-wide call spread, at the first expiry at least 7 and at least 14 days out. Compute half-spread in cents and as a percent of mid; the cost of a vertical as four half-spreads, as a percent of its debit and in bps of net-delta exposure; and the share of samples where each leg meets the MT-G28 gate (spread at most the larger of $0.05 and 5% of mid). Output: whether a compliant vertical can be entered at all, and its cost against 1.5 bps a side for shares. Not an edge test.
- **Not recommended to build:** opening 0DTE put/call rule (F7), unusual-activity or option-flow signals (F10), any short-volatility structure (F19).

---

## 4. Recommendations for the agent design

### 4.1 What to include

1. **A small read-only "options context" block, computed by code from the free Cboe files** each morning: VIX close (prior day); VIX percentile over 252 days; VIX9D/VIX; VIX/VIX3M; VIX1D close (prior day); SKEW; each with source and as-of date. Use it in reports, in size scaling, and as evidence the LLM veto may cite (MT-G29). Code computes every number; the LLM only reads them.
2. **Treat VIX1D with care.** Never compare an intraday VIX1D reading with a fixed threshold; it drifts up through the day by construction (F3). Use the previous close, or compare with the same time-of-day median.
3. **Volatility scaling, if H1 passes:** stop and target distances, and "skip today" rules, scaled to the implied move. Each change is a new registered setup version and counts toward N_trials.
4. **Log-only fields, marked EXPERIMENTAL:** Cboe daily put/call snapshot, top open-interest strikes, the H4 gamma proxy. Do not analyse before about 250 sessions.
5. **Feed tags:** `OPTIONS_FEED` on every option-derived number (MT-G35). Every options report keeps the sentence that Alpaca's options quotes are indicative (MT-G28).
6. **Replication humility:** treat every published net-of-cost result as unreplicated until an outsider reproduces it. The most relevant 0DTE rules paper changed sign after a cost-units bug found by outside users (F20).

### 4.2 What to avoid

- Minute-scale options trading of any kind, and 0DTE (MT-G28 already forbids it; keep it).
- Any single-leg long options, naked short options, or short-volatility products (the Feb 2018 collapse, F19).
- Using call walls, put walls, the gamma flip or "max pain" as entry or exit triggers.
- Using put/call, skew or "unusual activity" as a direction signal.
- Computing IV, Greeks, gamma or spreads from Alpaca's indicative feed before H0 passes.
- Any social-media, influencer or hype source of option flow (MT-G23, MT-G24). If unusual-activity data are ever tested, they must be OPRA-derived, code-computed and shadow-only.
- Letting a language model compute or "detect" gamma levels and act on them (F22 shows pattern recognition, not returns).

### 4.3 What to test first (in order)

1. **H1 and H2** (free, one afternoon of work): does VIX1D or VIX give a usable yardstick for the day's size of moves?
2. **H3** (no new data): find out how much of the proxy's 4% to 47% loss is spread, volatility assumption, or a signal with no edge.
3. **H0** (small forward log, plus one month of OPRA if the owner agrees): can the indicative feed be trusted for anything?
4. **H8** (owner's decision, $99): the measured cost of a compliant vertical.
5. **H4** (forward log, about a year): a volatility filter from public open interest.
6. **H6** (cheap, expected to fail): keep only if the pre-set bar is met.
7. Everything else (H5, H7) only if H4 passes or the owner asks.

### 4.4 What a beginner should be told

**(a) Is there any credible way to trade options at minute scale, and which structures limit the damage?**

- **Who makes money at minute scale:** option market makers, who earn the spread and manage risk within minutes (Korean account data: profitable on 74% of days; Hu et al.). That needs exchange-level speed and fees. I found no credible evidence that a retail trader or a bot with a rented data feed can do it. Every retail dataset I read shows average losses (F16), the best rules-based 0DTE study lost its edge after a cost fix (F20), and a 0DTE mispricing that was profitable before 2022 disappeared once daily expiries arrived (Almeida et al.).
- **What limits the damage (it does not create edge):**
  - Defined-risk debit verticals: the most you can lose is what you paid (MT-G28: 7+ calendar days, loss at most 0.25% of equity, one multi-leg limit order near mid, closed by 15:50).
  - A longer expiry (7+ days) removes the same-day gamma and decay cliff. With 7 to 14 days left, the option's premium moves roughly with delta times the stock's move.
  - Trade rarely; avoid the first and last 30 minutes, when 0DTE spreads are widest (Almeida et al.); use limit orders (SEC staff find patient limit orders cost about half as much as crossing the spread in their examples).
  - Warning from my calculation (1-cent half-spreads assumed, quotes UNVERIFIED): a 7-day $5-wide call spread has a net delta of about 0.12, so four half-spreads cost about 1.8% of the debit but about 4.2 bps of the stock-equivalent exposure, against about 0.5 bps for a single at-the-money call. Narrow verticals concentrate costs. The share version of the same minute setup costs 1 to 3 bps a round trip in the lab's assumptions. So an option version is not a cheaper way to run the same signal.
  - Standard mechanics, not researched here (UNVERIFIED): SPY and QQQ options are American-style and can be exercised early, so a short leg can be assigned.

**(b) What extra "chart-like" information from options could a stock-trading agent use as a filter, and is it free?**

| Filter | What it tells you | Evidence | Free source | Role for the agent |
|---|---|---|---|---|
| VIX (prior close) and its 252-day percentile | How nervous the market is; expected size of daily moves | Strong for volatility, none for direction (F1) | Cboe file, free | Risk and size scaling; reporting |
| VIX1D (prior close) | Expected size of the current day's move | Mixed; one forecasting study (F3) | Cboe file, free, daily only | Yardstick (if H1 passes); never a raw intraday threshold |
| VIX9D/VIX, VIX/VIX3M | Stress (near-term above long-term) | Mixed for volatility-selling payoffs (F4) | Cboe files, free | Stress flag; log |
| SKEW, VVIX | Crash-insurance price; volatility of volatility | Weak (F6) | Cboe files, free | Log only |
| Put/call | Sentiment | Weak (F7) | Snapshot only; no free history | Log forward only |
| Open-interest gamma proxy | Whether dealers are likely to calm or amplify moves | Mixed for volatility (F12); unstable for direction (F13) | Alpaca contracts endpoint or Cboe delayed chain (terms of the latter UNVERIFIED) | Size or veto only; forward test first (H4) |
| Option spreads and IV from Alpaca "indicative" | (unreliable) | Alpaca-affiliated forum reply says not for testing strategies | Free | Do not use before H0 passes |
| Signed option flow, unusual activity | Possible informed trading | Single stocks only, next day to week (F8, F10) | None (needs paid OPRA trades) | Not recommended |

Real-time quality: everything in the first rows is daily and available before 09:00, so the IEX-only live feed (MT-G35) is not an obstacle.

**Plain-English points for the owner**

- An option is a **price for movement**. Buying one means paying today for a big move later. On average the price is a little higher than the movement delivered, and you also pay the spread.
- **Time decay is not a hidden fee.** It is how the price falls as the window for movement closes. Your real costs are the spread, the small "extra" built into option prices, and having no edge on direction.
- A 0DTE option looks cheap because each contract is small. That is leverage, not value. In SPX 0DTE, retail traders as a group lost about $241,000 a day (Feb 2021 to Sep 2023).
- **"Gamma flip" and "walls" are estimates built on a guess** about who holds which options. The sign of the guess changes the story. There is real economics behind the idea, but the tests so far are weak, so treat the levels as hypotheses, not facts.
- The VIX is worth a glance each morning: it tells you whether a normal day is quiet or jumpy. It does not tell you which way.
- "I made money on paper" is weak proof for options too. For stocks, Alpaca paper fills ignore queue position and price impact (per the repo's earlier report on Alpaca's paper-trading page); I could not find how Alpaca fills paper option orders; and its free options prices are only indicative.
- If no test passes, doing nothing is a correct result.

**Mini-glossary:** *implied volatility (IV)* = how big a swing the option price assumes, as a yearly percent. *VIX* = IV of S&P 500 options over the next 30 days; *VIX1D* = over today only. *IV rank* = today's IV against the last year's range. *Skew* = crash-insurance puts cost more than equally distant calls. *Term structure* = short-term IV against long-term IV. *Put/call ratio* = puts traded divided by calls traded. *Open interest* = contracts still open. *Gamma* = how fast an option's exposure changes as price moves; largest for at-the-money options about to expire. *Market maker or dealer* = firm that quotes both sides and hedges. *GEX* = a vendor's estimate of dealers' total gamma. *0DTE* = expires today. *Theta* = value lost per day to time.

---

## 5. Open questions and things I could not verify

**Access and budget limits**

1. SSRN blocked all downloads, so for these I read abstracts only: Brogaard, Han and Won; Adams, Fontaine and Ornthanalai (and the merged Adams-Dim-Eraker-Fontaine-Ornthanalai-Vilkov draft); Vilkov's SSRN paper (I read the repo's annotated text and issue files instead); the 2026 preprints (Ardia and Vaudescal, Popovici, Chilingarian, Maurer, Maurer and Muller, Lin et al., Singh, Paz).
2. **Adams et al. numbers are UNVERIFIED.** A secondary summary says 0DTE options "dampen volatility by approximately 60 annualized basis points" ([QuantPedia](https://quantpedia.com/do-sp500-0dtes-options-increase-market-volatility/)). What I can support is Amaya et al.'s description of that paper: volatility is lower on days when 0DTE options are available, and related to the sign and size of dealer gamma.
3. **Brogaard et al. versions differ.** The abstract I read says a one-standard-deviation increase in 0DTE trading raises volatility by "9.10% relative to the mean value of volatility". An earlier search summary said "almost 14%". I trust the abstract text; the versions differ.
4. My web-search allowance ran out mid-project. Not searched, so treat as unknown rather than absent: Cboe SKEW predictive tests; independent post-publication replications of Pan and Poteshman or Johnson and So; academic evidence on "sweep" orders; recent evidence on index put/call ratios; SPY or QQQ option-volume predictability; the "max pain" academic paper mentioned in a search summary; any Fed or BIS note specifically on 0DTE; IV-rank timing tests.
5. Pages I could not read: SpotGamma's support pages (403), ThetaData and Databento pricing (dynamic), OCC statistics (403), FRED VIXCLS (fetch error), Wiley and ScienceDirect PDFs.
6. Titles seen but abstracts not read, so not relied on: Da, Goyenko and Zhang (2024) "Intraday Option Return: A Tale of Two Momentum"; Perz "Profitability of Selected 0DTE Index Options Strategies"; O'Donovan "0DTE Options and the Price of Tail Protection"; Dorion, Orlowski and Song "The Factor Structure of 0DTE Option Returns". They may bear directly on this topic.
7. The claim that 0DTE reached 65% of SPX volume in Q2 2026 is from an Investing.com summary of Cboe slides ([link](https://www.investing.com/news/company-news/cboe-q2-2026-slides-record-revenue-0dte-options-surge-to-65-of-spx-93CH-4828641)); the Cboe page I read does not state it. UNVERIFIED.

**Substantive open questions**

8. **Real SPY and QQQ option spreads** by time of day and expiry: no free real quotes. All my cost illustrations assume 1-cent half-spreads.
9. **Whether the Cboe delayed chain is the national best bid and offer or Cboe-only quotes**, and whether scheduled downloads are allowed.
10. **How Alpaca paper fills options** (from the indicative feed? OPRA?) I did not find this in the docs I read. It matters for any paper "options" result.
11. **Why the proxy loss is so large** (F18, H3). I did not read the lab code.
12. **Do the 1996 to 2020 gamma results survive in the 0DTE era?** Evidence is split: Singh's effect reverses in 2025, Paz's replication weakens, Ardia and Vaudescal's variance link holds on public data. All three are preprints.
13. **Transfer from Korea:** the market-maker inventory evidence is from KOSPI 200 options; US behaviour may differ (Hu et al. also show S&P 500 market makers turn positions over 32 times faster than net position changes).
14. **Selection in the retail data:** Bogousslavsky and Muravyev use traders who keep a trading journal (likely more sophisticated), which may explain their milder loss numbers.
15. **Sample periods not checked** for Pan and Poteshman, Xing et al., An et al. and Muravyev et al. (I read abstracts only), so the dates behind those effects are unknown to me; the 40-basis-point and 50-basis-point style effects may be concentrated in older years.
16. **Interested parties.** Cboe (earns on volume; wrote "0DTEs Decoded", supplied data for and hosts Amaya et al.); SqueezeMetrics, SpotGamma and gex.live (sell GEX data; Baltussen et al. thank SqueezeMetrics for data; gex.live found the Vilkov bug); tastylive (brokerage and education); Alpaca and Massive (sell data plans). Academic papers I found carry no course-selling conflicts; Bryzgalova et al. state they have none to disclose. Many 2026 preprint authors are unknown to me.

---

## 6. Sources

Status key: **PDF** = full text read; **abstract** = abstract only; **page** = official page read; **file** = downloaded and read; **snippet** = search snippet only (UNVERIFIED). "Preprint" = not peer reviewed.

**0DTE and retail**

1. Beckmeyer, Branger, Gayda, "Retail Traders Love 0DTE Options... But Should They?", 15 Dec 2023 version. PDF. https://wp.lancs.ac.uk/fofi2024/files/2024/04/FoFI-2024-146-Leander-Gayda.pdf (SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4404704)
2. Fu, Li, Musto, Pearson, "Hope at a Reasonable Price: Customer Use of Limit Orders in the 0DTE Market", SEC DERA working paper, 14-16 Mar 2025. PDF. https://www.sec.gov/files/dera-hope-reasonable-prc-2503.pdf (views are the authors', not the Commission's)
3. Bogousslavsky, Muravyev, "An Anatomy of Retail Option Trading", 8 Feb 2025. PDF. https://www.brettonwoodsskiconference.com/uploads/b/f9bfc8b0-0251-11ed-a646-3dea17112d2f/An%20Anatomy%20of%20Retail%20Option%20Trading.pdf
4. Bryzgalova, Pavlova, Sikorskaya, "Retail Trading in Options and the Rise of the Big Three Wholesalers", J. Finance 78(6), 2023. PDF. https://lbsresearch.london.edu/id/eprint/2827/ (doi 10.1111/jofi.13285)
5. Bauer, Cosemans, Eichholtz, "Option trading and individual investor performance", J. Banking and Finance 33(4), 2009. Abstract. https://ideas.repec.org/a/eee/jbfina/v33y2009i4p731-746.html
6. Hu, Kirilova, Park, Ryu, "Who Profits from Trading Options?", Management Science, 2024. Abstract. https://doi.org/10.1287/mnsc.2023.4916
7. Lipson, Tomio, Zhang, "A Real Cost of Free Trades: Retail Option Trading Increases the Volatility of Underlying Securities", 2023 preprint. Abstract. https://doi.org/10.2139/ssrn.4383463
8. Muravyev, Pearson, "Options Trading Costs Are Lower than You Think", Rev. Financial Studies, 2020. Abstract. https://doi.org/10.1093/rfs/hhaa010

**0DTE and market impact**

9. Amaya, Garcia-Ares, Pearson, Vasquez, "0DTE Index Options and Market Volatility: How Large is Their Impact?", 25 Jan 2025. PDF. https://cdn.cboe.com/resources/education/research_publications/gammasqueezes.pdf (Cboe supplied data and hosts the file)
10. Dim, Eraker, Vilkov, "0DTEs: Trading, Gamma Risk and Volatility Propagation", 14 May 2024. PDF. https://westernfinance-portal.org/viewpaper?n=950096 (SSRN: https://ssrn.com/abstract=4692190)
11. Brogaard, Han, Won, "Does 0DTE Options Trading Increase Volatility?", 2023 preprint. Abstract (via Crossref). https://doi.org/10.2139/ssrn.4426358
12. Adams, Fontaine, Ornthanalai, "The Market for 0DTE: The Role of Liquidity Providers in Volatility Attenuation", 2024 (SSRN 4881008; merged draft SSRN 5641974). Snippet/description via source 9. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4881008
13. Almeida, Freire, Hizmeri, "0DTE Asset Pricing", 23 May 2025. PDF. https://www.fma.org/assets/docs/Derivatives2025/Almeida.pdf
14. Bandi, Fusari, Reno, "0DTE option pricing", 19 Feb 2024 (forthcoming J. Finance per a search summary). PDF. https://westernfinance-portal.org/viewpaper?n=915376
15. Vilkov, "0DTE Trading Rules: Tail Risk, Implementation, and Tactical Timing", SSRN 4641356; replication package with README, KNOWN-ISSUES and annotated paper. Files. https://github.com/vilkovgr/0dte-strategies
16. Cboe (Mandy Xu), "0DTEs Decoded: Positioning, Trends, and Market Impact", 2 May 2025. Page. https://www.cboe.com/insights/posts/0-dt-es-decoded-positioning-trends-and-market-impact/
17. Cboe (Henry Schwartz), "The State of the Options Industry: 2025", 22 Jan 2026. Page. https://www.cboe.com/insights/posts/the-state-of-the-options-industry-2025
18. Cboe (Henry Schwartz), Q2 2026 options review, 21 Jul 2026. Page. https://www.cboe.com/insights/posts/state-of-the-options-industry-options-market-continued-to-break-records-in-q-2-2026
19. ECB, Financial Stability Review Nov 2023, box on 0DTE. Page. https://www.ecb.europa.eu/press/financial-stability-publications/fsr/focus/2023/html/ecb.fsrbox202311_02~0cf2c71d00.en.html
20. QuantPedia summary of Adams et al. (secondary; numbers UNVERIFIED). https://quantpedia.com/do-sp500-0dtes-options-increase-market-volatility/

**Informed options trading and price discovery**

21. Pan, Poteshman, "The Information in Option Volume for Future Stock Prices", Rev. Financial Studies 19(3), 2006. Abstract. https://econpapers.repec.org/article/ouprfinst/v_3a19_3ay_3a2006_3ai_3a3_3ap_3a871-908.htm
22. Cremers, Weinbaum, "Deviations from Put-Call Parity and Stock Return Predictability", JFQA 45(2), 2010. Abstract. https://ideas.repec.org/a/cup/jfinqa/v45y2010i02p335-367_00.html
23. Xing, Zhang, Zhao, "What Does the Individual Option Volatility Smirk Tell Us About Future Equity Returns?", JFQA 45(3), 2010. Abstract (via Crossref). https://doi.org/10.1017/s0022109010000220
24. An, Ang, Bali, Cakici, "The Joint Cross Section of Stocks and Options", J. Finance 69(5), 2014. Abstract (NBER/SSRN versions via Crossref). https://www.nber.org/papers/w19590
25. Johnson, So, "The option to stock volume ratio and future returns", J. Financial Economics 106(2), 2012. PDF. https://www.travislakejohnson.com/pdfs/Johnson%20So%20OS%202012%20(JFE).pdf
26. Muravyev, Pearson, Broussard, "Is there price discovery in equity options?", J. Financial Economics 107(2), 2013. Abstract. https://econpapers.repec.org/article/eeejfinec/v_3a107_3ay_3a2013_3ai_3a2_3ap_3a259-283.htm
27. Goncalves-Pinto, Grundy, Hameed, van der Heijden, Zhu, "Why Do Option Prices Predict Stock Returns?", Management Science, 2020. Abstract. https://doi.org/10.1287/mnsc.2019.3398
28. Lin, Luo, Shao, "When Does Intraday Options Trading Predict Stock Returns?", 2026 preprint. Abstract. https://doi.org/10.2139/ssrn.7318198
29. Simon, Wiggins, "S&P futures returns and contrary sentiment indicators", J. Futures Markets, 2001. Abstract (via Crossref). https://doi.org/10.1002/fut.4

**Dealer hedging, gamma and pinning**

30. Baltussen, Da, Lammers, Martens, "Hedging demand and market intraday momentum", J. Financial Economics 142, 2021. PDF. https://www3.nd.edu/~zda/intramom.pdf (thanks SqueezeMetrics for data; two authors at Robeco)
31. Ni, Pearson, Poteshman, White, "Does Option Trading Have a Pervasive Impact on Underlying Stock Prices?", Rev. Financial Studies 34(4), 2021. Abstract; 2006 draft read. https://econpapers.repec.org/article/ouprfinst/v_3a34_3ay_3a2021_3ai_3a4_3ap_3a1952-1986..htm ; https://www.ou.edu/dam/price/Finance/CFS/paper/pdf/pearsonPoteshmanWhite.pdf
32. Barbon, Buraschi, "Gamma Fragility", working paper, 5 Nov 2020. PDF. https://alexandria.unisg.ch/bitstreams/25fec636-90a2-4735-a3a4-dfc0b68d3feb/download (not peer reviewed as far as I found)
33. Ni, Pearson, Poteshman, "Stock price clustering on option expiration dates", J. Financial Economics 78(1), 2005. Abstract (SSRN version). https://doi.org/10.2139/ssrn.519044
34. Golez, Jackwerth, "Pinning in the S&P 500 futures", J. Financial Economics 106(3), 2012. PDF. https://d-nb.info/1112655492/34
35. Hu, Kirilova, Muravyev, Ryu, "Options Market Makers", 10 Feb 2025. PDF. https://www.fma.org/assets/docs/Derivatives2025/Muravyev.pdf
36. SqueezeMetrics, "The Implied Order Book" (GEX), 6 Jul 2020. PDF (vendor document). https://squeezemetrics.com/download/The_Implied_Order_Book.pdf
37. 2026 SSRN preprints (abstracts via Crossref): Ardia and Vaudescal https://doi.org/10.2139/ssrn.7202999 ; Popovici https://doi.org/10.2139/ssrn.7082418 ; Chilingarian https://doi.org/10.2139/ssrn.7131778 ; Maurer https://doi.org/10.2139/ssrn.6650858 ; Maurer and Muller https://doi.org/10.2139/ssrn.7339718 ; Singh https://doi.org/10.2139/ssrn.7350465 ; Paz https://doi.org/10.2139/ssrn.7290621
38. Regan, Xie, "Inferring Latent Market Forces: Evaluating LLM Detection of Gamma Exposure Patterns via Obfuscation Testing", arXiv 2512.17923. Abstract page. https://arxiv.org/abs/2512.17923

**Volatility, VIX1D, skew and term structure**

39. Carr, Wu, "Variance Risk Premiums", Rev. Financial Studies, 2009. SSRN abstract via Crossref. https://doi.org/10.2139/ssrn.577222
40. Coval, Shumway, "Expected Option Returns", J. Finance 56(3), 2001. PDF. https://backend.production.deepblue-documents.lib.umich.edu/server/api/core/bitstreams/3b55995a-7728-41ce-af29-a0ed1354ea76/content
41. Bakshi, Kapadia, "Delta-Hedged Gains and the Negative Market Volatility Risk Premium", Rev. Financial Studies, 2003. Abstract (SSRN version via Crossref). https://doi.org/10.2139/ssrn.267106
42. Augustin, Cheng, Van den Bergen, "Volmageddon and the Failure of Short Volatility Products", Financial Analysts Journal 77(3), 2021. Accepted manuscript read. https://utoronto.scholaris.ca/server/api/core/bitstreams/7f0a59c4-4070-4d48-ac2c-c42e7bb6ecbc/content
43. Johnson, "Risk Premia and the VIX Term Structure", JFQA 52(6), 2017. Abstract. https://ideas.repec.org/a/cup/jfinqa/v52y2017i06p2461-2490_00.html
44. Albers, "A New Star Is Born: Does the VIX1D Render Common Volatility Forecasting Models Obsolete?", J. Futures Markets 45(11), 2025. Abstract. https://ideas.repec.org/a/wly/jfutmk/v45y2025i11p2092-2108.html
45. Albers, Kestner, "The daily rise and fall of the VIX1D: Causes and solutions of its overnight bias", Finance Research Letters 62, 2024. Abstract. https://ideas.repec.org/a/eee/finlet/v62y2024ipas1544612324002162.html
46. Cboe, "Cboe 1-Day Volatility Index Methodology". PDF. https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_1-Day_Volatility_Index.pdf
47. Kozhan, Neuberger, Schneider, "The Skew Risk Premium in the Equity Index Market", Rev. Financial Studies, 2013. Abstract (SSRN version via Crossref). https://doi.org/10.2139/ssrn.2565731
48. Goyal, Saretto, "Cross-section of option returns and volatility", J. Financial Economics 94(2), 2009. SSRN abstract via Crossref. https://doi.org/10.2139/ssrn.889947
49. Christensen, Nielsen, "The Implied-Realized Volatility Relation with Jumps in Underlying Asset Prices", 2005 preprint. Abstract (via Crossref). https://doi.org/10.2139/ssrn.686021
50. tastylive, "Implied Volatility Rank and Percentile" (broker and educator; commercial interest). Page. https://www.tastylive.com/concepts-strategies/implied-volatility-rank-percentile

**Data, costs and venues**

51. Alpaca, About Market Data API (plans and prices). Page. https://docs.alpaca.markets/us/docs/about-market-data-api
52. Alpaca, Historical Option Data (indicative versus OPRA; since Feb 2024). Page. https://docs.alpaca.markets/us/docs/historical-option-data
53. Alpaca, Options Trading (contracts endpoint, open_interest field). Page. https://docs.alpaca.markets/us/docs/options-trading
54. Alpaca community forum, "What is the Indicative Pricing Feed for options?". Page (reply by Dan_Whitnable_Alpaca, an Alpaca-affiliated account, 3 Jul 2024). https://forum.alpaca.markets/t/what-is-the-indicative-pricing-feed-for-options/14595
55. Cboe daily index files (VIX, VIX1D, VIX9D, VIX3M, VVIX, SKEW) at https://cdn.cboe.com/api/global/us_indices/daily_prices/ ; VIX history page https://www.cboe.com/tradable_products/vix/vix_historical_data/ ; put/call files https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv ; daily statistics https://www.cboe.com/us/options/market_statistics/daily/ ; historical options page https://www.cboe.com/us/options/market_statistics/historical_data/ ; delayed chain https://cdn.cboe.com/api/global/delayed_quotes/options/SPY.json . Files and pages.
56. SEC filing SR-CBOE-2020-054, Exhibit 5 (penny pricing for SPY and QQQ options). PDF. https://www.sec.gov/files/rules/sro/cboe/2020/34-89075-ex5.pdf
57. Massive options documentation (plan names and prices). Page. https://massive.com/docs/rest/options/overview

**My own calculations (saved in this folder):** `calc_bs_illustration.py` (Black-Scholes premium, gamma and spread-cost illustration for S = 766, IV 15%, 1-cent half-spreads) and `calc_vix_csv.py` (VIX1D open-to-close drift, VIX1D/VIX ratios and VIX percentile, from the Cboe files downloaded 29 Sep 2026).
