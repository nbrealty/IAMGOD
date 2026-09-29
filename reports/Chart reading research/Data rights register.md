# Data Rights Register: AI paper-trading project

**Prepared:** 29 Sep 2026 (documents fetched and read on 28-29 Sep 2026)
**Type:** research only. Nothing in the project was edited, no orders were placed, no broker or trading API was called.
**This is not legal advice.** It records what the published terms say, quotes them word for word with the address, and says what is unclear. When a document is silent, this register does **not** treat silence as permission.

---

## 0. Read this first (six points)

1. **GitHub reports this repository as PUBLIC, not private.** The brief says "private". GitHub says otherwise (evidence in R4). Several data files are sitting in it, downloadable by anyone with no login: a 2.5 MB file of daily bars for 56 symbols (`trading/evals/bars.csv.gz`), a snapshot of 11,822 Alpaca option quotes that also carries four Cboe index values (branch `trading-state`), and about ten copyrighted book PDFs (`docs/`). Alpaca's own words forbid publishing its data. **This is the most urgent item. Check the repository's visibility in GitHub today** (Settings, then General, then Danger Zone, then Change visibility).
2. **The AI chart-reading test is UNCLEAR.** No current Alpaca or exchange document says yes or no to feeding market data (or pictures made from it) to an AI model. The new consolidated-tape rules that start on **1 April 2027** do speak about AI directly. Until Alpaca answers in writing, do not repeat or extend the test with Alpaca-derived data, and do not build any "AI veto" or "AI explain" step that sends market numbers to an AI model.
3. **Cboe and Yahoo are RESTRICTED.** Cboe allows one personal, non-commercial copy and asks for written consent for storing or copying beyond that. Yahoo bans scripted collection of its data "for any purpose" without its prior permission. Both were used by script.
4. **The core of the project is fine with conditions.** Using Alpaca's free data for your own automated paper trading, and keeping downloaded bars privately for your own backtests, is what the free plan is for. The conditions: personal, non-commercial, you stay a "non-professional", nothing is shared or published.
5. **One document conflict to clear with Alpaca.** Alpaca's paper-trading page says a Paper Only account holder "is only entitled to receive and make use of IEX market data", while its Market Data FAQ says free users can query SIP data that is 15 minutes old or more. Your SIP downloads rely on the second statement.
6. **Dates:** 1 Oct 2026 (IEX raises its real-time TOPS fee), 1 Mar 2027 (deadline for new consolidated-tape licences), 1 Apr 2027 (new rules take over, including AI rules). See section 7.

---

## 1. Scoreboard (11 uses checked)

| Status | Count | Entries |
|---|---|---|
| VERIFIED_OK | 1 | R9 SEC fee pages |
| OK_WITH_CONDITIONS | 5 | R1 real-time IEX for the bot, R2 SIP history cached locally, R3 aggregated results in reports, R6 indicative option quotes (private reading), R10 FINRA/CAT fee pages |
| UNCLEAR | 2 | R5 AI chart-reading test, R8 Kenneth French library |
| RESTRICTED | 3 | R4 raw data files in the (public) repository, R7 Cboe VIX files, R11 Yahoo Finance |

What the labels mean here:

- **VERIFIED_OK:** the publisher says in words that this use is allowed.
- **OK_WITH_CONDITIONS:** the documents allow the use if you keep to stated limits (mostly: personal, private, non-commercial).
- **UNCLEAR:** no document clearly covers it. Unknown permission is **not** approval. It does not mean unsafe. It means nothing in writing says yes.
- **RESTRICTED:** the written terms limit or forbid this use, and no consent has been obtained.

---

## 2. Plain-English words used below

- **IEX:** one stock exchange. Alpaca's free real-time stock feed shows only IEX trades and quotes.
- **SIP:** the official combined price tape of all US exchanges. Two plans run it: **CTA** (NYSE-listed shares, Tapes A and B) and **UTP** (Nasdaq-listed shares, Tape C). Alpaca's free plan gives SIP data only when it is at least 15 minutes old.
- **Delayed data:** at least 15 minutes old. The tape rules treat it more lightly than live data.
- **Non-professional:** a private person using the data for personal, non-business purposes, who is not registered or working in the securities business.
- **Non-display use:** a computer using the data with no person looking at a screen. A trading bot is the standard example.
- **Derived data:** numbers made from market data that cannot be turned back into that data (a win rate, an average, a Sharpe ratio). The exchanges treat it as the friendliest category.
- **Redistribution:** giving the data to anyone else, or showing it to them. Posting it in a public repository counts.

---

## 3. How the documents fit together

Your right to use the data comes through several layers. When they disagree, the strictest one wins (Alpaca Customer Agreement, section 24, quoted below).

| Layer | Document | Who it binds |
|---|---|---|
| 1 | Alpaca Terms and Conditions | You, when you use Alpaca's API and content |
| 2 | Alpaca Customer Agreement (version V26.2026.07), section 30, plus the two exchange agreements it pulls in (Nasdaq OMX Global Subscriber Agreement, NYSE Market Data Display Services Agreement, both dated 2013) | You, if you accepted the full account agreement |
| 3 | Plan and exchange policies: CTA and UTP tape policies, IEX Market Data Policies | Mostly Alpaca (the "vendor"); they reach you through layer 2 |
| 4 | Alpaca staff comments on the forum and support pages | Nobody (helpful, not a contract) |
| 5 | New Consolidated Tape (CT) Plan policies, effective 1 Apr 2027 | Alpaca first, then you through new customer terms |

> "In the event that this Agreement or any Third Party Documentation is silent with respect to Prohibited Activity, or in the event of any conflict with respect to this Agreement and any Third Party Documentation regarding Prohibited Activity, the document or agreement containing the most restrictive terms shall prevail for purposes of this Agreement."
> Alpaca Customer Agreement V26.2026.07, section 24 "Conflicts", page 14. https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf

**Which agreement did you sign?** Alpaca's Terms and Conditions cover every user, including a paper-only sign-up. The Customer Agreement (with section 30) is signed when you open a full brokerage account. Please check which sign-up you completed (Paper Only, or a live brokerage account that also has paper accounts). Both documents limit the data to personal, non-commercial use, so most answers below do not change, but question Q1 in section 8 depends on it.

---

## 4. The register

### R1. Alpaca real-time IEX data, used by the live paper bot

**Status: OK_WITH_CONDITIONS**

**(a) Use in question.** The bot reads live IEX quotes and one-minute bars through Alpaca's API on the free Basic plan and uses them to decide paper orders on your own account. The journal records bid, ask and mid at each decision (small amounts). Second-by-second recordings stay in the local state folder and are not pushed anywhere.

**(b) What the documents say (exact words).**

> "The Basic plan serves as the default option for both Paper and Live trading accounts, ensuring all users can access essential data with zero cost. However, this plan only includes limited real-time data: for equities only the IEX exchange, for options only the indicative feed."
> "If you signed up for an Alpaca account to trade or build a personal trading app, you're using the Trading API. If you're a business integrating Alpaca as your backend brokerage provider, you're using the Broker API."
> Alpaca docs, About Market Data API (page updated 2026-07-16). https://docs.alpaca.markets/docs/about-market-data-api

> Plan page text (line breaks removed): "Free For developers and researchers $0/mo" and "Algo Trader Plus For algo traders and quants $99/mo".
> https://alpaca.markets/data

> "Other than as set forth herein, you agree to use the Services and Content solely for your own personal and non-commercial purposes. Should you wish to use the Services and Content for any other purposes, including without limitation commercial usage, or making the Services and Content available to others through your own application (a "User Application"), you shall provide Alpaca with 30 days advance written notice prior to making such User Application available to others."
> Alpaca Terms and Conditions, "Personal and Non-Commercial Usage". https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf

> "I further understand that AlpacaDB, Inc. provides market data to non-professional Alpaca customers. The terms "non-professional" and "nonprofessional" are defined within both the NASDAQ OMX Global Subscriber Agreement as well as the NYSE Market Data Display Services Agreement, and are incorporated by reference."
> Alpaca Customer Agreement V26.2026.07, section 30 "Use of Market Data and Waiver or Limitation of Liability", page 16. https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf

On where the "IEX" data comes from:

> "The Free plan consists of data from IEX (Investors Exchange LLC). IEX data is sourced from the SIP feed, and not the exchange itself."
> Alpaca support, "What data provider does Alpaca use?" (May 2025). https://alpaca.markets/support/data-provider-alpaca

IEX's own rules for "non-display use" (a bot):

> "'Non-Display' use refers to accessing, processing, or consuming Real-Time IEX Market Data for a purpose other than (i) solely facilitating Data Subscriber's display of the Real-Time IEX Market Data or (ii) solely internally or externally distributing the Real-Time IEX Market Data."
> "Non-Display use may include, but is not limited to: [...] Automated trading [...]"
> "All Data Subscribers to Real-Time IEX Market Data are required to indicate whether they are engaging in Non-Display use on an annual basis by completing the IEX Non-Display Use Declaration"
> IEX Market Data Policies, September 2026, section 13. https://www.iex.io/documents/iex-market-data-policies

> "'Data Subscriber' means any natural person or entity that receives Real-Time IEX market data either directly from the Exchange or from another non-affiliated Data Subscriber via uncontrolled distribution where such non-affiliated Data Subscriber does not control both the entitlement to and display of the Real-Time IEX Market Data by the Data Subscriber. A Data Subscriber must enter into a Data Subscriber Agreement with IEX in order to receive Real-Time IEX market data."
> IEX Fee Schedule, effective 1 Sep 2026, Market Data Fees, Definitions. https://www.iex.io/resources/trading/fee-schedule

> "'Non-Professional Data User' means a natural person or qualifying trust that uses IEX Market Data only for personal purposes and not for any commercial purposes, and for a natural person who works in the United States, is not (i) registered or qualified in any capacity with the Securities and Exchange Commission, the Commodities Futures Trading Commission, any state securities agency, any securities exchange or association, or any commodities or futures contract market or association; [...]"
> IEX Market Data Policies, September 2026, section 8. https://www.iex.io/documents/iex-market-data-policies

On quality (not rights), Alpaca staff say:

> "IEX data is really intended for testing and debug and typically should not be used to make live trading decisions."
> Dan_Whitnable_Alpaca (Alpaca staff), March 2024. https://forum.alpaca.markets/t/paper-account-data-query-denied/13822

**(c) Status:** OK_WITH_CONDITIONS.

**(d) In plain English.** The free plan is offered to private individuals, including for paper and live algorithmic trading, and the only limits Alpaca gives you are: personal use, non-commercial use, no sharing. Exchange policies call "automated trading" non-display use and attach declarations and fees to it, but those apply to firms that sign data agreements with the exchange. Nothing Alpaca hands a retail user (Terms, Customer Agreement, the two non-professional agreements) mentions non-display use or asks you to declare it. Two things are not visible in writing: who counts as the "Data Subscriber" on the IEX side of Alpaca's free feed (IEX's fee schedule reads as if any person receiving real-time IEX data through an API must sign IEX's own agreement, while Alpaca says its IEX data comes from the SIP), and whether automated use by a non-professional needs any declaration. That is Alpaca's chain to sort out, but it is worth asking (Q5 and Q6). Small quote fields stored in your journals are covered by the same terms, and become a problem only if published (R4).

**(e) What to do.**
- Keep as is.
- Keep the Alpaca account in your own name, trade only your own money, and never share the keys or the live feed with anyone (this includes your cousin).
- Do not publish live quotes (R4).
- Ask Alpaca Q5 and Q6 in writing.
- Watch: IEX raises its real-time TOPS fee from $500 to $1,000 a month on 1 Oct 2026 (paid by data subscribers, not by you). Alpaca could change or withdraw the free IEX stream. The bot already tags the feed on every line and fails safe when the feed is missing. Keep that.

**(f) Verified:** 29 Sep 2026.

---

### R2. Alpaca SIP historical minute and daily bars, cached locally, used for backtests and research

**Status: OK_WITH_CONDITIONS** (one written conflict to clear with Alpaca: Q1)

**(a) Use in question.** The lab downloads SIP 1-minute and daily bars (and, for the 28 Sept replay, historical SIP quotes) through the API. It never asks for data newer than 16 minutes (`DELAY = 16 min` in `lab/scalp/data.py`). Files are cached as `state/scalp_cache/<SYMBOL>_<YYYYMM>.csv.gz` on the disk of a cloud container. The cache is not copied to GitHub (the state-sync whitelist excludes caches). The data feeds backtests, the replay, research and the picture test.

**(b) What the documents say (exact words).**

> "For historical queries, the `end` parameter must be at least 15 minutes old to query SIP data without a subscription."
> Alpaca docs, Market Data FAQ (updated 2026-09-21). https://docs.alpaca.markets/docs/market-data-faq

> Basic plan column of the plan table: "Historical data timeframe | Since 2016"; "Historical data limitation* | latest 15 minutes". Algo Trader Plus: "no restriction".
> Alpaca docs, About Market Data API (updated 2026-07-16). https://docs.alpaca.markets/docs/about-market-data-api

> "However, if one is using the free market data then only historical SIP data can be fetched and only IEX 'real time' data is available. 'Real time' in this case is anything more current than the past 15 minutes."
> Dan_Whitnable_Alpaca (Alpaca staff), March 2024. https://forum.alpaca.markets/t/paper-account-data-query-denied/13822

The conflicting sentence:

> "As an Alpaca Paper Only Account holder, you are only entitled to receive and make use of IEX market data."
> Alpaca docs, Paper Trading (updated 2026-07-07). https://docs.alpaca.markets/us/docs/paper-trading

The limits that apply to any copy:

> "Content is provided exclusively for personal and noncommercial access and use. No part of the Service or Content may be copied, reproduced, republished, uploaded, posted, publicly displayed, encoded, translated, transmitted or distributed in any way (including "mirroring") to any other computer, server, web site or other medium for publication or distribution or for any commercial enterprise, without Alpaca's express prior written consent."
> Alpaca Terms and Conditions, "Content". https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf

> "I agree not to reproduce, distribute, sell or commercially exploit the market data in any manner without written consent from Alpaca."
> Alpaca Customer Agreement V26.2026.07, section 30, page 16.

> "Subscriber may not sell, lease, furnish or otherwise permit or provide access to the Information to any other Person or to any other office or place."
> "For Non-Professional or Private Subscriber, the Information is licensed only for personal use."
> Nasdaq OMX Global Subscriber Agreement, Version 2013.1, section 1 and 1(a). https://files.alpaca.markets/disclosures/library/NASDAQ+OMX+Global+Subscriber+Agreement.pdf

> "Subscriber shall not furnish Market Data to any other person or entity." and "If Subscriber is a Nonprofessional Subscriber, he or she shall receive Market Data solely for his or her personal, non-business use."
> NYSE Agreement for Market Data Display Services, last update 4 March 2013, paragraphs 5 and 11. https://files.alpaca.markets/disclosures/library/NYSE+Market+Data+Display+Services+Agreement.pdf

Tape rules for delayed data:

> "For UTP Information, the Delay Interval is 15 minutes."
> "Vendors are currently not required to obtain Subscriber Agreements from Subscribers of Delayed and/or End-of-Day Information on Controlled Products."
> "Non-Display Use fees apply only to Vendors that receive a Data Feed containing Real-Time UTP Information."
> UTP Data Policies, published September 2023. https://www.utpplan.com/DOC/datapolicies.pdf

> "Non-Display Use of real-time CTA Market Data means accessing, processing or consuming CTA Market Data, whether delivered via direct and/or redistributor data feeds, for a purpose other than in support of data recipient's display or further internal or external redistribution." (Examples listed include "Any trading in any asset class" and "Price referencing for algorithmic trading".)
> CTA Market Data Non-Display Use Policy, Nov 2015. https://www.ctaplan.com/publicdocs/ctaplan/Policy_CTA_Non_Display_with_FAQ.pdf

Supporting, but not a licence: Alpaca's own learning article says "it's best to keep a local cache of data to work with" (June 2018). https://alpaca.markets/learn/collecting-market-data

I found no sentence in the Alpaca, Nasdaq, NYSE, CTA or UTP documents that says anything either way about a subscriber **storing** downloaded data for personal use.

**(c) Status:** OK_WITH_CONDITIONS.

**(d) In plain English.**
- Free-plan users are told they can pull SIP history that is at least 15 minutes old, and Alpaca staff repeat it. The tape rules treat data that old as "delayed", the lightest category: the non-display rules in both tape policies apply to **real-time** data, so your delayed-only SIP use falls outside them.
- The "no copying" wording in Alpaca's Terms is aimed at copies made "for publication or distribution or for any commercial enterprise". A private cache for your own tests is not that.
- Three soft spots. (1) The Paper Only sentence above conflicts with the FAQ. (2) The "local disk" is a rented cloud container. The old Nasdaq agreement bans furnishing data "to any other office or place". No document says whether your own cloud server counts. (3) The tape rules change on 1 Apr 2027 (section 7).
- The cache must stay private (R4).

**(e) What to do.**
- Keep as is for private use.
- Never copy the cache anywhere shared: not GitHub, not a drive link, not email or chat.
- Keep the 16-minute guard in the code.
- Ask Alpaca Q1 (Paper Only entitlement), Q2 (keeping copies), Q7 (2027 changes).

**(f) Verified:** 29 Sep 2026.

---

### R3. Aggregated statistics and per-trade results written into reports

**Status: OK_WITH_CONDITIONS**

**(a) Use in question.** Backtest and research reports hold summary numbers (win rates, average profit per trade, drawdowns, significance tests) and per-trade results of the bot's own paper trades. Raw bars are not in the reports. The reports go into the GitHub repository (which is public, see R4).

**(b) What the documents say (exact words).**

> "'Derived Data' means any information generated in whole or in part from IEX Market Data if and only if the information generated cannot be reverse engineered to recreate all or a portion of any IEX Market Data or be used to create other data or information that is recognizable as a reasonable substitute for IEX Market Data."
> IEX Market Data Policies, September 2026, section 11. https://www.iex.io/documents/iex-market-data-policies

> "To be considered Derived Data: 1) The Derived Data cannot be reverse engineered to recreate the Information, and 2) The Derived Data cannot be used to create other data that is recognized to be a reasonable facsimile for the UTP Information."
> "DERIVED DATA: MULTIPLE SECURITY [NOT FEE LIABLE]: Derived Data that contains price and/or volume data is based upon multiple UTP security symbols is currently not fee liable."
> UTP Data Policies, September 2023, Derived Data Policy. https://www.utpplan.com/DOC/datapolicies.pdf

The wide legacy wording (Nasdaq and NYSE agreements):

> "Information also includes any element of Information as used or processed in such a way that the Information can be identified, recalculated or re-engineered from the processed Information or that the processed Information can be used as a substitute for Information."
> Nasdaq OMX Global Subscriber Agreement, section 12 "Information".

> "'Market Data' means (a) last sale information and quotation information [...] and (c) all information that derives from any such information."
> NYSE Agreement for Market Data Display Services, paragraph 1.

**(c) Status:** OK_WITH_CONDITIONS.

**(d) In plain English.** Totals, averages, win rates and the bot's own fill prices cannot be turned back into the price tape, and every plan document calls that kind of output "derived data", the friendliest category. The NYSE wording ("all information that derives from") is very wide if read literally, but the plan-level derived-data policies are what people rely on. The risk is not in summary numbers. It is in tables from which a reader could rebuild prices: long lists of bars, quotes or prints for one symbol. Because the repository is public today, anything in a report is public.

**(e) What to do.**
- Keep publishing summary numbers only.
- Do not paste price tables, bar lists, or quote and print series into reports.
- For per-trade rows, keep your own fill price, time and profit or loss, not the surrounding quotes.
- The public `Options lab day 1 post-mortem` shows a handful of individual option prints and quotes. That is small, but avoid adding more.
- Ask Alpaca Q3(b).

**(f) Verified:** 29 Sep 2026.

---

### R4. Raw or near-raw data files that ARE in the repository (found while checking)

**Status: RESTRICTED** while the repository is public. If it were truly private with only you inside, the storage part would drop to UNCLEAR (no document mentions git hosting).

**(a) Use in question.** Not on your list of facts; found by reading the project and the public GitHub pages. Your brief says raw bars are not committed and the repository is private. Both statements are contradicted:

| # | What | Where | Size and content |
|---|---|---|---|
| 1 | `trading/evals/bars.csv.gz` | committed (commit 3ba9cff); downloadable without login on branches `operation-invest` and `claude/investment-agents-question-hrkk10` | 2,580,403 bytes, 149,532 rows, **56 symbols, daily open/high/low/close/volume, 2016-01-04 to 2026-09-25**, adjusted, built by `python -m evals.build` from Alpaca (SIP first, IEX fallback) |
| 2 | `options/chains/2026-09-28/close.json.gz` | public branch `trading-state` | 410 KB. **11,822 option quotes** (SPY 4,920; QQQ 4,799; IWM 2,103) with bid, ask, quote time, IV, delta, gamma, theta, vega, open interest, volume, from Alpaca's indicative feed. Also a `cboe` block: VIX 14.87, VIX3M 17.93, VIX9D 12.76, SKEW 144.91 for 25 Sep 2026, with the Cboe file addresses |
| 3 | `claude/pending/<date>/context.json` | public branch `trading-state` | About 43 KB per day of market-derived scores and signals for 51 allowed symbols, prepared as input for the AI-assisted stock book. Derived numbers, not raw bars, but they are AI inputs (R5) and they are public |
| 4 | Journals with IEX bid, ask and mid at each decision | **not yet public.** `state-save` will copy them to a new branch `scalp-state` (the whitelist excludes caches and recordings) | Small, but would be public while the repository is public |
| 5 | Book PDFs under `docs/` | public branches `operation-invest` and `claude/investment-agents-question-hrkk10` | Outside market data, see section 10 |

**Visibility evidence (checked 29 Sep 2026):**
- The repository page https://github.com/nbrealty/IAMGOD shows the label "Public" and the description "A god-game set in fictionalized 2026 America. You read the three-layer souls of a living city [...]".
- GitHub's API https://api.github.com/repos/nbrealty/IAMGOD returns `"private": false` and `"visibility": "public"`.
- Public branches: `main`, `operation-invest`, `claude/investment-agents-question-hrkk10`, `trading-state`, and two game branches. There is no `scalp-state` branch yet.

**(b) What the documents say (exact words).**

> "No part of the Service or Content may be copied, reproduced, republished, uploaded, posted, publicly displayed, encoded, translated, transmitted or distributed in any way (including "mirroring") to any other computer, server, web site or other medium for publication or distribution or for any commercial enterprise, without Alpaca's express prior written consent."
> Alpaca Terms and Conditions, "Content".

> "I agree not to reproduce, distribute, sell or commercially exploit the market data in any manner without written consent from Alpaca."
> Alpaca Customer Agreement V26.2026.07, section 30.

> "Unfortunately, you cannot redistribute Alpaca API data." (answer to "Can I redistribute Alpaca API data via my platform?", November 2022)
> https://alpaca.markets/support/redistribute-alpaca-api

> "Subscriber may not sell, lease, furnish or otherwise permit or provide access to the Information to any other Person or to any other office or place."
> Nasdaq OMX Global Subscriber Agreement, section 1. And, in its summary: "Subscriber indemnifies NASDAQ OMX and holds NASDAQ OMX harmless for any Claims or Losses (as described in Section 9) resulting from Subscriber's breach of the Agreement, from Subscriber's infringement of a third-party's intellectual property rights or from any third-party lawsuit related to Subscriber's use or receipt of Information."

> "Real-Time or Delayed IEX Market Data that is databased or stored beyond the current trading day will not be considered IEX Historical Data and subject to the IEX Historical Data Terms of Use."
> IEX Market Data Policies, September 2026, section 1.

> "Alpaca may also terminate or suspend your access to the Service or the Content if Alpaca finds that your usage violates these Terms and Conditions, or if your usage puts an undue strain on Alpaca's information technology infrastructure."
> Alpaca Terms and Conditions, "Termination; Modification".

Cboe's terms on the four index values are in R7.

**(c) Status:** RESTRICTED (while public).

**(d) In plain English.** A public repository hands Alpaca's data to the whole internet. That is "publication or distribution" in Alpaca's own words. A daily-bar file for 56 symbols and a snapshot of nearly 12,000 option quotes are real copies of market data, not summary statistics. The likely consequence is not a lawsuit against a hobby project. It is that Alpaca can suspend the keys under its Terms, which would stop the whole project. The exchange agreements you accepted through Alpaca also carry indemnities. Deleting a file from the latest version does not remove it from history or from copies others already made.

**(e) What to do.**
1. **Today:** confirm the repository's visibility on GitHub. Either make the repository private, or move the trading work to a separate private repository. Only you can do this.
2. **Before the first `state-save`:** do not run `python -m lab.scalp.live state-save` while the repository is public, because it would publish quote fields in the journals. Or drop the quote fields from what it copies.
3. **Stop adding data files.** Freeze `trading/evals/bars.csv.gz` (no refresh commits). Stop the `trading-state` job from writing `options/chains/*` snapshots, and from putting Cboe values into them. These belong to the operations session; the decision is yours.
4. **After step 1,** decide with Alpaca's answer to Q3 whether to keep or remove the files. If remove: delete them from every branch and from history (needs a history rewrite, which the operations session can do). Copies made while public cannot be recalled.
5. **Rebuild instead of storing:** `python -m evals.build` fetches the bars again from Alpaca on demand.

**(f) Verified:** 29 Sep 2026.

---

### R5. AI chart-reading test: pictures made from SIP-derived bars shown to an AI model

**Status: UNCLEAR**

**(a) Use in question.** 108 pictures (36 market days x 3 charts) were built from cached SIP minute and daily bars: 24 real days of SPY and QQQ (3 Aug to 25 Sep 2026) plus 12 reshuffled "twins". Price is shown as percent change from the first open, volume as a multiple of the median bar, and there is no ticker and no date. Six AI agents (two passes) read them in a blind test. The pictures were not committed. The bot's order path never sends market data to an AI model. The answer key (`truth.json`, 100 KB) holds derived measures and a few price levels per picture and is due to be committed with the report.

**(b) What the documents say (exact words).**

Today's Alpaca and exchange documents do not mention AI. The nearest general wording is the "no copying, no furnishing to others" text quoted in R2, which is aimed at publication, distribution and giving data to other persons or places.

Alpaca's own documentation encourages connecting AI assistants to its market-data tools:

> "Market data: Query historical and live data: bars, quotes, trades, snapshots, option chains with Greeks"
> "Alpaca API keys: a free paper trading account is enough to start"
> "MCP client: [...] or any MCP-compatible tool"
> "Control which tools are available to your AI assistant using `ALPACA_TOOLSETS`. This is useful for limiting scope (e.g. read-only market data) [...]"
> Alpaca docs, Trading MCP Server (updated 2026-09-09). https://docs.alpaca.markets/us/docs/alpaca-mcp-server

That page is not a licence. It says nothing about what the AI provider may keep, or about exchange-owned data.

What changes on 1 April 2027 (Consolidated Tape Plan Policies, version 1.1, 19 Aug 2026; Data Usage Agreement, version 1.0, published 18 Aug 2026). https://cdn.databp.com/tenants/datact/CT-Plan-Policies.pdf and https://consolidatedtape.com/agreements/data-agreement.html

> "Access to, or Usage of, CT Data by an artificial intelligence or machine-learning model, application, or service (collectively, "AI Services") is licensed under existing CT Plan Access and Usage policies and is subject to all applicable fees, including Access fees, Non-Display Use fees, and Derived Data fees. All outputs of AI Services are treated as CT Data and remain subject to the same policies and fees as the CT Data inputs unless qualified as Derived Data under Section 4.6 (Derived Data Creation)." (Policies, section 4.10)

> "AI Service Usage by a Non-Professional Authorized User, including automated or standing instructions, must remain within that Authorized User's personal, non-business Usage." (section 4.10)

> "Each Non-Professional Authorized User must access the AI Service through the Authorized User's own individual account with the AI Service provider and must take reasonable steps to use only an AI Service that provides assurances that the Authorized User's CT Data is not shared or made accessible to any other person." (section 4.10)

> "Legally binding terms with each individual user that prohibit redistribution, ingestion into third-party services, scraping, and - except as permitted under Section 4.10 - use of the US Consolidated Tape to train, fine-tune, retrieve into, or otherwise serve third-party artificial intelligence models or other systems that present the data outside the user's personal interaction with the Licensee's application." (section 4.7, what Alpaca must put in its customer terms)

> "Apply a 15-minute delay and redistribute the delayed data to any users or applications." (section 4.4, the "Delayed Data Redistribution" licence; obligations listed: a verifiable delay system, clear attribution, and attribution terms in the customer terms)

The real-time rules in the new Data Usage Agreement also say "Subscriber must not extract, export, copy, scrape, capture, retransmit, or otherwise remove CT Plan Information from a Controlled Display or Controlled Service except as expressly permitted under an applicable Data License" (section 2(e)). Whether Alpaca will treat 15-minute-delayed API data under the delayed licence (looser) or under this subscriber regime (tighter) is not stated anywhere I could find.

**(c) Status:** UNCLEAR.

**(d) In plain English.** Nothing in writing says yes or no today. A private one-off test, on pictures with no ticker or date that were not kept, sits at the low-risk end, and Alpaca itself documents hooking AI assistants to its data. But a chart can be re-measured back into approximate prices (the test's own answer key was checked against pixel readings), so pictures are not clearly "derived data", and the AI provider's own rules on keeping and training on uploads also matter (not researched here). From April 2027 the tape rules speak to AI directly: your own account with the AI provider, no sharing, outputs count as market data unless they qualify as derived data. So the safe assumption is that AI use of Alpaca-derived data will be **more** regulated, not less.

**(e) What to do (disable the dependent path until Alpaca answers).**
- Treat the test as finished. Do not repeat or extend it with Alpaca-derived data.
- Pause these planned steps while they use Alpaca-derived numbers or pictures: R8 follow-ups (a) messy-screenshot test scored against data, (b) same test on other models, (c) picture-versus-table forward test, (d) scoring an AI veto on every candidate trade (MT-G29, MT-G32).
- Do not build any AI "veto" or "explain" step that sends quotes, bars or charts to an AI model.
- Keep the order path AI-free (it is today). The code-only "Reader" design does not depend on this.
- If you need AI experiments meanwhile, use synthetic data (like the twins), your own trade records, or data whose terms allow it.
- Keep `truth.json` to derived measures. Do not add raw series. Do not store the pictures.
- Ask Alpaca Q4 (section 8).
- **Adjacent path, same question:** the stock-book side of the repository already gives an AI model a daily context file of market-derived numbers (`claude/pending/*/context.json`, and an AI key in the GitHub workflow). That is the operations session's area, but Q4 covers it too.
- Screenshots of your cousin's screens carry that platform's own data terms and the cousin's private information. Not assessed here.

**(f) Verified:** 29 Sep 2026.

---

### R6. Alpaca "indicative" option quotes, read for research

**Status: OK_WITH_CONDITIONS** for private reading. The public snapshot file is covered in R4.

**(a) Use in question.** The options lab and research read Alpaca's free indicative option chains (quotes, implied volatility, greeks) for research and for paper option trades.

**(b) What the documents say (exact words).**

> "Indicative Pricing Feed is a free derivative of the original OPRA feed: the quotes are not actual OPRA quotes, they're just indicative derivatives. The trades are also derivatives and they're delayed by 15 minutes."
> Alpaca docs, Historical Option Data (updated 2025-09-24). https://docs.alpaca.markets/docs/historical-option-data

> "The use case for indicative pricing is to debug ones code and not generally to be used for live trading or to test the efficacy of ones strategy. This is provided free as an alternative to paid OPRA data to reduce the cost burden during algo design."
> Dan_Whitnable_Alpaca (Alpaca staff), 3 July 2024. https://forum.alpaca.markets/t/what-is-the-indicative-pricing-feed-for-options/14595

The general Alpaca limits (personal, non-commercial, no publishing) are the same as in R1 and R2. Alpaca's disclosure library lists only the Nasdaq and NYSE market-data agreements, not an OPRA agreement (https://alpaca.markets/disclosures). For real OPRA data, OPRA's own form of subscriber agreement says:

> "You shall receive the Service and the OPRA Data included therein solely for your own business or personal use, and you shall not retransmit or otherwise furnish the OPRA Data to any person [...]"
> OPRA Electronic Form of Subscriber Agreement. https://cdn.opraplan.com/documents/OPRA_Electronic_Subscriber_Agreement.pdf

**(c) Status:** OK_WITH_CONDITIONS.

**(d) In plain English.** No document treats the indicative feed differently from other Alpaca content: private, personal use is fine, publishing is not. Alpaca staff say the feed exists to debug code and is not real quotes, so results built on it prove little about real trading. That is a quality point, but it also means there is no written encouragement to use it for research.

**(e) What to do.** Keep private. Do not commit chain snapshots (R4). Keep labelling reports "indicative". Ask Q3(c).

**(f) Verified:** 29 Sep 2026.

---

### R7. Cboe VIX-family history files (VIX, VIX1D, VIX9D, VIX3M, VVIX, SKEW)

**Status: RESTRICTED**

**(a) Use in question.** Scripts download six free CSV files from `cdn-api.cboe.com`, cache them under `state/cache/cboe/`, and use them for research (volatility yardsticks in the Wave 1 tests, and a volatility-times-skew model in the options lab). Four current index values were also written into a committed options snapshot (R4).

**(b) What the documents say (exact words).**

> "You may view, print and download one copy of the Materials for your personal non-commercial use in connection with products and services offered by Cboe, provided that you maintain all copyright, trademark and other notices contained on the Materials. You may not otherwise copy, reproduce, alter, store either in hard copy or in an electronic retrieval system, license, transmit, display, broadcast, create a derivative work (for example, a financial product, service or index) from, use to verify or correct other data or information, publish, rent, sublicense, distribute, or otherwise use in whole or in part in any other manner the Materials without Cboe's prior written consent except to the extent that such use constitutes "fair use" under the "Copyright Act of 1976", as amended from time to time. To formally request such consent you must submit a Request to Use Cboe Content."
> Cboe, Terms and Conditions for Use of Cboe Websites, section 2, "Last Updated: November 16, 2022" (still the current version on 29 Sep 2026). https://www.cboe.com/terms

> "In order to use any Cboe logo, data, photo/image or other content contained in Cboe websites (collectively "Cboe Content"), you must receive approval in advance from Cboe."
> "If Cboe approves your request, such approval will be contingent upon your execution of a license agreement. You are not approved to use Cboe Content until a license agreement has been signed by both you and Cboe."
> "In order to use any Cboe Content, you must receive approval in advance from Cboe. To request approval, send an e-mail to permissions@cboe.com [...]"
> "Submitting a Request to Use Cboe Content in no way grants or implies permission to use Cboe Content in any form."
> Cboe, Use of Cboe Content. https://www.cboe.com/use-of-content

> "Cboe Volatility Index data is compiled for the convenience of site visitors and is furnished without responsibility for accuracy and is accepted by the site visitor on the condition that transmission or omissions shall not be made the basis for any claim, demand or cause for action. The information and data was obtained from sources believed to be reliable, but accuracy is not guaranteed."
> Cboe, VIX Historical Data page. https://www.cboe.com/tradable-products/vix/vix-historical-data

The CSV files themselves carry no licence text (checked on VIX_History.csv, last row 09/28/2026). The Terms contain no words about robots, scraping or automation (searched: none).

**(c) Status:** RESTRICTED. (This confirms the earlier fact-check: restrictive, personal, non-commercial.)

**(d) In plain English.** The written permission is narrow: **one** personal, non-commercial copy, and "in connection with products and services offered by Cboe". Storing more copies, keeping the files in a cache, or building anything from them needs Cboe's written consent unless it counts as "fair use" (a legal judgment this register does not make). Read literally, Cboe's "Use of Cboe Content" page asks for approval **and a licence** for any use of its data. The earlier fact-checkers judged private research low-risk. That may be right in practice, but no consent exists, and publishing any of it is clearly outside the terms.

**(e) What to do.**
- Keep the rule "never commit or share Cboe files". Remove the four Cboe values from the public snapshot (R4).
- In reports, use only aggregated statements (for example "VIX1D closed above its open on 471 of 519 days"), not series.
- Until Cboe replies, hold the dependent paths: no new automated daily Cboe fetches, and no new place where Cboe values feed a live decision. The options lab already has a scripted fetch (`trader/options/pricing.py`); running it privately is your call, but consent is the clean fix.
- Email permissions@cboe.com (draft in section 8).
- If Cboe says no or asks for a licence: stop using the files and compute your own volatility measure from Alpaca bars.

**(f) Verified:** 29 Sep 2026.

---

### R8. Kenneth French Data Library (monthly and daily factor files)

**Status: UNCLEAR** (low risk). No use conditions are published.

**(a) Use in question.** Monthly and daily Fama/French factor files are downloaded for research and used in private analysis (for example momentum and trend tests).

**(b) What the documents say (exact words).**

> Library page footer: "Copyright Eugene F. Fama and Kenneth R. French"
> https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html

> File trailer in `F-F_Research_Data_Factors_CSV.zip` (downloaded 29 Sep 2026): "Copyright 2026 Eugene F. Fama and Kenneth R. French"
> File header: "This file was created using the 202608 CRSP database. The 1-month TBill rate data until 202405 are from Ibbotson Associates. Starting from 202406, the 1-month TBill rate is from ICE BofA US 1-Month Treasury Bill Index."
> https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip

The library page, the "Details" page for the factors, and the files contain no terms of use, no licence, no citation rule and no redistribution statement (I searched the page text for licence, permission, terms, cite and redistribute). The contact page lists **kfrench@dartmouth.edu**. https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/contact_Information.html

**(c) Status:** UNCLEAR.

**(d) In plain English.** The authors publish the data for download and it is used everywhere in research, but they keep the copyright and state no rules. The series is built from CRSP data, and the risk-free rate comes from Ibbotson and ICE BofA, whose owners may have their own terms (not researched). Private analysis is the natural reading. Republishing the files or long series is not covered by anything in writing.

**(e) What to do.**
- On hold: putting French files or series into the repository or into a report.
- May continue (my judgment, not a permission): private analysis on your own machine, with the results reported and the papers cited.
- Ask kfrench@dartmouth.edu only if you want to publish the data or series (draft in section 8).

**(f) Verified:** 29 Sep 2026.

---

### R9. SEC fee pages (Section 31 fee rate advisories and related filings)

**Status: VERIFIED_OK**

**(a) Use in question.** SEC fee rates and dates are recorded in the fee table (`lab/scalp/live/costs.py`) with links to the SEC pages.

**(b) What the documents say (exact words).**

> "Information presented on www.sec.gov is considered public information and may be copied or further distributed by users of the web site without the SEC's permission."
> SEC, Privacy Information page ("Last Reviewed or Updated: Nov. 29, 2023"). https://www.sec.gov/about/privacy-information

Checking note: SEC.gov refused my automated page download (HTTP 403). The sentence was confirmed by an exact-phrase search that returned that page and by one page-fetch summary; a second summary run did not reproduce it. **Please glance at the page once.**

**(c) Status:** VERIFIED_OK.

**(d) In plain English.** SEC pages are public information you may copy and share. The fee table holds numbers and links anyway.

**(e) What to do.** Keep as is. Keep the source link and the date next to each rate.

**(f) Verified:** 29 Sep 2026.

---

### R10. FINRA and CAT fee pages (Trading Activity Fee, CAT fee alerts)

**Status: OK_WITH_CONDITIONS**

**(a) Use in question.** FINRA's Trading Activity Fee (including the pause from 1 Oct to 31 Dec 2026) and the CAT fee rates are recorded as numbers, dates and source links in the fee table. The fee-alert PDFs were read but are not in the repository.

**(b) What the documents say (exact words).**

> "The works of authorship contained in the FINRA Website, including, but not limited to, all design, text, sound recordings, and images-are owned, except as otherwise expressly stated, by FINRA and may not be copied, reproduced, transmitted, displayed, performed, distributed, rented, sublicensed, uploaded, posted, framed, altered, stored for subsequent use, or otherwise used in whole or in part in any manner without FINRA's prior written consent, except to the extent that such use constitutes "fair use" under the Copyright Act of 1976 (17 U.S.C. § 107), as amended, and then, only with notices of FINRA's proprietary rights."
> FINRA Terms of Use (last modified November 9, 2023), "Copyright, Trademark, and Proprietary", paragraph b. https://www.finra.org/terms-of-use
> Permission requests: https://www.finra.org/contact-finra/permission-use-finra-copyrighted-material

The CAT site's Legal Notice uses the same wording for its web site ("may not be copied, reproduced [...] stored for subsequent use [...] without Participants' prior written consent, except to the extent that such use constitutes "fair use""). https://www.catnmsplan.com/legal-notice

**(c) Status:** OK_WITH_CONDITIONS.

**(d) In plain English.** These terms protect the pages' text and design. A fee rate is a fact. Writing "0.000195 dollars per share, from this date, source: link" into your own table is not copying the page. Pasting the page text, or committing the PDFs, would be.

**(e) What to do.** Keep the table as numbers, dates and links. Do not paste FINRA or CAT text into reports. Keep the fee-alert PDFs out of the repository. If you ever want to quote their text, use FINRA's permission page.

**(f) Verified:** 29 Sep 2026.

---

### R11. Yahoo Finance

**Status: RESTRICTED** (scripted collection is banned without Yahoo's prior permission)

**(a) Use in question.** You described one rough comparison flagged UNVERIFIED. What I found is wider: report R6 ("Long-horizon trends") pulled daily price history for 16 tickers (SPY, QQQ, ^GSPC, ^IXIC, EFA, IEF, VNQ, DBC, SHY, MTUM, SPMO, QMOM, FFTY, DBMF, KMLM, CTA) by script from `https://query1.finance.yahoo.com/v8/finance/chart/...` on 28 Sep 2026, and built several tables on it (rule tests on SPY and QQQ from 1993, ETF track records). R6 marks them "UNVERIFIED" and calls the endpoint "Unofficial endpoint, no published service terms". That last phrase is not right: Yahoo publishes terms, and they address exactly this.

**(b) What the documents say (exact words).**

> "access or collect data, or attempt to access or collect data, from our Services using any automated means, devices, programs, algorithms or methodologies, including but not limited to robots, spiders, scrapers, data mining tools, or data gathering or extraction tools, for any purpose without our express, prior permission."
> "Unless otherwise expressly stated, you may not access or reuse the Services, or any portion thereof, for any commercial purpose."
> "use any material or content from, including without limitation any data, (a) to create any database, archive, mobile application, data feed, widget or any other aggregated data source that competes with or constitutes a material substitute for the Services, in whole or in part, [...]"
> Yahoo Terms of Service, "Last updated: 4 August 2026". https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html

**(c) Status:** RESTRICTED.

**(d) In plain English.** A script is "automated means". Yahoo's terms ban that "for any purpose" without its permission. The main risk to you is not a claim. It is building conclusions on data that was obtained against the terms and that nobody has verified.

**(e) What to do.**
- Stop scripted Yahoo pulls now. Do not commit any Yahoo data.
- Keep the Yahoo-based tables in R6 flagged UNVERIFIED, or remove them. Correct the "no published service terms" line.
- Replace the data: Alpaca daily bars for 2016 onward (subject to R2), the French files for factor history (R8), or a licensed source for longer history.
- Asking Yahoo for permission is not worth the trouble.

**(f) Verified:** 29 Sep 2026.

---

## 5. Your data status: professional or non-professional

**What it means for a person running an algorithm on their own account.** In every document, the label depends on **who you are and what you use the data for**, not on whether a computer does the trading. Automated trading with your own money, in your own name, for yourself, is still non-professional. The label flips if any of these become true.

| Trigger | Where it is written |
|---|---|
| You are registered or qualified with the SEC, CFTC, a state securities agency, an exchange or association, or a commodities body; or work as an investment adviser; or are employed by a bank or other exempt organisation doing work that would need registration | Nasdaq agreement section 12 ("Non-Professional Subscriber" is a natural person who is NOT any of these); IEX Policies section 8 |
| Data is used for a business, or for another person or entity | NYSE paragraphs 9 and 11 ("solely for his/her personal, non-business use") |
| The account is held by a company or other entity | Alpaca support (Dec 2022): "business accounts are considered professional data subscribers" (https://alpaca.markets/support/alpaca-business-accounts); CT Plan policy 5.3 from 2027 |
| You use other people's capital, trade for the benefit of another party, share profits, or get paid for trading | NYSE paragraph 12 questions H, I and J (quoted below) |
| You give advice or sell signals or services | NYSE question F; CT Plan definition of Professional Usage |

> "H. Do you use the capital of any other individual or entity in the conduct of your trading?" "I. Do you conduct trading for the benefit of a corporation, partnership, or other entity?" "J. Have you entered into any agreement to share the profit of your trading activities or receive compensation for your trading activities?"
> "Subscriber shall notify Vendor promptly in writing of any change in his or her circumstances that may cause him or her to cease to qualify as a Nonprofessional Subscriber or that may change his or her response to any of the preceding questions."
> NYSE Agreement for Market Data Display Services, paragraph 12. https://files.alpaca.markets/disclosures/library/NYSE+Market+Data+Display+Services+Agreement.pdf

> "All users are considered "professional" until the vendor properly qualifies him/her as a nonprofessional."
> CTA Vendor Guide, section 5 (undated). https://www.ctaplan.com/publicdocs/ctaplan/notifications/trader-update/Vendor_Guide.pdf

From 1 April 2027 the new tape rules say it in plain words:

> "Day traders - An individual trading their own capital from a personal-name account may qualify for Non-Professional Usage, provided the individual does not receive compensation for trading on behalf of any third party and has not entered into a profit-sharing arrangement that would trigger a disqualifying response."
> CT Plan Policies v1.1, section 5.5. https://cdn.databp.com/tenants/datact/CT-Plan-Policies.pdf

**Status of your position: OK_WITH_CONDITIONS.** These facts must stay true: the Alpaca account is in your own personal name (please confirm; the GitHub owner is a personal user account named `nbrealty`), the money is yours, the project is not sold or offered as a service, and no one else uses the feed. **Your cousin:** if the cousin's money, a profit share, or a paid service ever enters the picture, tell Alpaca first. The NYSE questions above ask about exactly that.

---

## 6. Are the two big questions addressed anywhere?

**A. Feeding market data, or charts made from it, into a third-party AI model.**
- Today's documents (Alpaca Terms, Customer Agreement, Nasdaq and NYSE agreements, IEX policies, CTA and UTP policies): **not addressed by name.** Only the general no-copying and no-furnishing words apply (R2, R5).
- Alpaca's own docs show AI assistants using its market-data tools (R5). Helpful, not a licence.
- From **1 April 2027**: addressed in detail (R5): own account with the AI provider, no sharing, outputs treated as market data unless they qualify as derived data, and no training or fine-tuning use outside the personal interaction.
- The AI provider's own terms on keeping and training on uploads are a separate layer, not researched here.

**B. Committing derived data (or raw data) to a private repository.**
- **Not addressed anywhere I found.** No document mentions git or code hosting.
- Derived data (non-reversible summaries) is expressly the friendliest category in the IEX, UTP and CT Plan definitions (R3).
- Raw copies: the nearest words are "uploaded [...] to any other computer, server [...] for publication or distribution" (Alpaca Terms) and "furnish [...] to any other office or place" (Nasdaq). A private repository with only you inside is a grey area. A **public** one is publication (R4).

---

## 7. Dates to watch

| Date | What | Why it matters |
|---|---|---|
| 1 Oct 2026 | IEX raises Real-Time TOPS from $500 to $1,000 per month (IEX Fee Schedule; delayed data stays free). CT Plan licensing portal opens | The free real-time IEX stream is Alpaca's to fund. Watch for a change to the Basic plan |
| 1 Mar 2027 | Deadline for new consolidated-tape licences. "firms that have not executed them by March 1, 2027 will not be authorized to receive US Consolidated Tape data after April 1, 2027" (https://consolidatedtape.com/) | Alpaca will very likely change its customer terms before then. Read them, especially AI, copying and non-display wording |
| 1 Apr 2027 | CTA and UTP plans replaced by the CT Plan (administrator DataCT). New Data Usage Agreement and Policies take effect | Answers to Q1 to Q4 may change |

---

## 8. Who to ask, and what to ask

Ask in writing. Ask Alpaca to name the document and section behind each answer. Keep the replies (outside the repository).

### 8.1 Alpaca (first)

- **Where:** Alpaca support request form https://alpaca.markets/support/request, copying **compliance@alpaca.markets** (the Customer Agreement, page 1, says: "IF I HAVE ANY QUESTIONS ABOUT ANY OF THE PROVISIONS IN THIS AGREEMENT, I WILL EMAIL compliance@alpaca.markets OR CALL ALPACA AT +1 (941) 231-4093"). The Terms also require "30 days advance written notice" before making Content available to others through your own application (Q3 covers that).
- **Draft:**

> Subject: Written confirmation needed: personal use of Basic-plan market data for private backtesting and AI analysis
>
> I am an individual on the Basic (free) market data plan. My account type is [Paper Only / live brokerage with paper accounts: fill in]. I use the data only for my own private, non-commercial research and my own automated paper trading. Please answer each question in writing and name the document and section for each answer.
>
> 1. Your Paper Trading page says a Paper Only account holder "is only entitled to receive and make use of IEX market data". Your Market Data FAQ says SIP data can be queried without a subscription if the end time is at least 15 minutes old. May I download and use SIP historical bars, quotes and trades that are at least 15 minutes old?
> 2. May I keep a copy of downloaded historical data on a computer or cloud server I control, for my own backtests, with no time limit?
> 3. May I put any of the following in a git repository, and does the answer differ for a private repository only I can see and a public one? (a) raw daily or minute bars, (b) summary statistics and per-trade results, (c) option-chain snapshots from the indicative feed, (d) IEX bid and ask values stored with my bot's order records.
> 4. May I show charts, tables or numbers made from this data to a third-party AI model for my own private analysis, and what conditions apply (my own account with the AI provider, no retention, no training)? I note your MCP server page describes connecting AI assistants to your market-data tools.
> 5. My bot uses the free real-time IEX stream for automated trading on my own account. Please confirm I am a non-professional data user and that I need no non-display declaration or fee.
> 6. Your support page says "IEX data is sourced from the SIP feed, and not the exchange itself". Is that right for the real-time Basic feed, and which exchange or tape rules apply to me as a user?
> 7. The Consolidated Tape Plan replaces the CTA and UTP plans on 1 April 2027 and requires new licences by 1 March 2027. Will you change your customer terms for Basic-plan users, and will any answer above change?

### 8.2 Cboe (before any further use)

- **Where:** **permissions@cboe.com** (per https://www.cboe.com/use-of-content). Cboe's page asks for these items:
  - your exact name, title, organisation and contact details (individual, no organisation);
  - a detailed explanation of how you will use and display the content: private, non-commercial research; scripted download of the daily history CSV files for VIX, VIX1D, VIX9D, VIX3M, VVIX and SKEW from cdn-api.cboe.com; stored on my own computer or cloud server; results reported only as summary statistics;
  - screenshots, samples or links: none, since nothing is displayed;
  - distribution plans: none, no one else sees the files;
  - how long: ongoing;
  - anything else: I am asking whether this needs a licence agreement or falls within the Terms.
- **Ask:** "Please confirm in writing whether this private, non-commercial use, including automated download and local storage, is permitted, or which licence is needed."

### 8.3 Kenneth French (only if you want to publish)

- **Where:** **kfrench@dartmouth.edu**.
- **Ask:** "May I keep the daily and monthly Fama/French factor files in a private research project and publish summary results that cite the Data Library? I do not plan to republish the factor series."

### 8.4 Others

- **FINRA:** only to quote page text, at https://www.finra.org/contact-finra/permission-use-finra-copyrighted-material.
- **SEC:** nothing to ask.
- **Yahoo:** nothing to ask. Stop instead.
- **IEX, DataCT (licensing@datact.com, support@datact.com):** ask Alpaca first. They license Alpaca, not you. IEX's market operations address is marketops@iextrading.com if Alpaca cannot answer.

---

## 9. Actions for the owner

| # | Action | Who | When | Entry |
|---|---|---|---|---|
| 1 | Check the repository's visibility on GitHub. Make it private, or move the trading work into a separate private repository | You | Today, before the first `state-save` | R4 |
| 2 | Do not run `state-save` while the repository is public. Stop adding data files. Freeze `trading/evals/bars.csv.gz`. Stop `options/chains/*` snapshots and the Cboe values inside them | You decide; operations session executes | Today | R4, R7 |
| 3 | After step 1, decide (with Alpaca's Q3 answer) whether to keep or delete the published files; if delete, remove from all branches and history | You and the operations session | This week | R4 |
| 4 | Send the Alpaca questions Q1 to Q7 in writing. Fill in your account type first | You | This week | R1 to R6 |
| 5 | Pause every AI use of Alpaca-derived numbers or pictures: no repeat of the chart test, no AI veto or explain step, no picture-versus-table forward test | Minute-trading session | Now, until Alpaca replies | R5 |
| 6 | Email permissions@cboe.com. Hold new Cboe dependencies. Keep the rule "never commit Cboe files" | You; sessions | This week | R7 |
| 7 | Stop scripted Yahoo pulls. Keep or remove the Yahoo tables in R6 and fix the "no published service terms" line | Research session | Now | R11 |
| 8 | Keep French files private and cite them. Email only if you want to publish | Sessions | Ongoing | R8 |
| 9 | Keep the Alpaca account in your own name, your own money only, feed and keys unshared. Tell Alpaca first if your cousin's money, a profit share or a paid service ever appears | You | Ongoing | Section 5 |
| 10 | Diary dates: 1 Oct 2026, 1 Mar 2027, 1 Apr 2027. Read Alpaca's new customer terms when they arrive | You | Calendar | Section 7 |
| 11 | Remove the book PDFs from public branches (section 10) | You | This week | Section 10 |
| 12 | Keep a private copy of the Alpaca Terms and Customer Agreement versions you accepted (V26.2026.07 at 29 Sep 2026), outside the repository | You | This week | Section 3 |

---

## 10. Seen while checking, not on your list

- **Book PDFs in the public repository.** `docs/` on branches `operation-invest` and `claude/investment-agents-question-hrkk10` holds about ten full-text books (for example `The_Intelligent_Investor.pdf`, 5.8 MB, and `41775536-Market-Wizards.pdf`, 1.2 MB). I confirmed two of them download without login. That is a copyright problem unrelated to market data. Remove them from public branches (and history). The brief's rule "never commit extracted book text" does not cover whole PDFs.
- **Economic-release calendars** (Fed, BLS, BEA, Census: US government sources; University of Michigan and ISM: private organisations). Only release dates are recorded, which are facts. Not assessed in depth. Check the publisher's terms if you ever republish ISM or Michigan values.
- **Alpaca news data** used by the stock books (`news_signals`) has its own content terms. Not assessed.
- **The pictures test files** (`truth.json`, reader answers) hold derived measures and a few price levels per picture. Low risk. Do not add raw series.
- **Screenshots of your cousin's screens** carry the cousin's platform terms and personal information. Not assessed.

---

## 11. How this was checked, limits, and one disclosure

**Method.** I read the brief (`MINUTE_TRADING.md`), the staged research reports and the fact-check reports. I read the code that touches data (`lab/scalp/data.py`, `live/statesync.py`, `live/journal.py`, `trader/data.py`, `trader/options/pricing.py`, `evals/`). I fetched every governing document listed below and read it in full or searched it for the relevant clauses. Quotes are copied from the text of the fetched PDFs and pages, not from summaries, with two exceptions noted in R9 and in the plan-page text in R1. Fetches and downloads were held in memory only; the only file written is this register.

**Limits.**
- Legal effect is not assessed. "Fair use" is not decided.
- I could not see which sign-up you completed with Alpaca, or which agreement versions your account accepted.
- The Nasdaq and NYSE agreements Alpaca links date from 2013, and the UTP and CTA policies I found date from 2023 and 2015. Alpaca or the plans may use newer versions that are not published.
- Alpaca staff forum posts are helpful evidence, not contract terms.
- The AI provider's terms, GitHub's terms, ICE, CRSP and Ibbotson terms were not researched.
- The SEC page could not be downloaded by script (see R9).
- OPRA rules were read only as context, since Alpaca does not link them.

**Disclosure.** Early on, before I applied the "no git" rule strictly, I ran a few **read-only git listing commands** (`log`, `ls-files`, `branch`, `remote`, `ls-tree`) in `/home/user/IAMGOD`. They changed nothing. After that I used only public GitHub web pages and the GitHub API for repository facts. I edited nothing under `/home/user/IAMGOD`, made no commit, called no broker or trading API, and placed no order. An automatic safety check also blocked one attempt to read a proxy help file; I did not retry it.

---

## Appendix A. Documents relied on

| Document | Version or date | Address |
|---|---|---|
| Alpaca Terms and Conditions | undated PDF, fetched 29 Sep 2026 | https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf |
| Alpaca Customer Agreement | V26.2026.07 | https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf |
| Nasdaq OMX Global Subscriber Agreement | Version 2013.1 | https://files.alpaca.markets/disclosures/library/NASDAQ+OMX+Global+Subscriber+Agreement.pdf |
| NYSE Agreement for Market Data Display Services | last update 4 Mar 2013 | https://files.alpaca.markets/disclosures/library/NYSE+Market+Data+Display+Services+Agreement.pdf |
| Alpaca disclosures library | fetched 29 Sep 2026 | https://alpaca.markets/disclosures |
| Alpaca docs: About Market Data API | updated 2026-07-16 | https://docs.alpaca.markets/docs/about-market-data-api |
| Alpaca docs: Market Data FAQ | updated 2026-09-21 | https://docs.alpaca.markets/docs/market-data-faq |
| Alpaca docs: Paper Trading | updated 2026-07-07 | https://docs.alpaca.markets/us/docs/paper-trading |
| Alpaca docs: Historical Option Data | updated 2025-09-24 | https://docs.alpaca.markets/docs/historical-option-data |
| Alpaca docs: Trading MCP Server | updated 2026-09-09 | https://docs.alpaca.markets/us/docs/alpaca-mcp-server |
| Alpaca plan page | fetched 29 Sep 2026 | https://alpaca.markets/data |
| Alpaca support: data provider | May 2025 | https://alpaca.markets/support/data-provider-alpaca |
| Alpaca support: redistribute | November 2022 | https://alpaca.markets/support/redistribute-alpaca-api |
| Alpaca support: business accounts | December 2022 | https://alpaca.markets/support/alpaca-business-accounts |
| Alpaca forum, paper account data (staff post) | March 2024 | https://forum.alpaca.markets/t/paper-account-data-query-denied/13822 |
| Alpaca forum, indicative feed (staff post) | July 2024 | https://forum.alpaca.markets/t/what-is-the-indicative-pricing-feed-for-options/14595 |
| Alpaca learning article, storing data | June 2018 | https://alpaca.markets/learn/collecting-market-data |
| IEX Market Data Policies | September 2026 | https://www.iex.io/documents/iex-market-data-policies |
| IEX Data Subscriber Agreement | September 2026 | https://www.iex.io/documents/iex-data-subscriber-agreement |
| IEX Fee Schedule | effective 1 Sep 2026, and pending 1 Oct 2026 | https://www.iex.io/resources/trading/fee-schedule |
| UTP Data Policies | published September 2023 | https://www.utpplan.com/DOC/datapolicies.pdf |
| CTA Market Data Non-Display Use Policy | Nov 2015 | https://www.ctaplan.com/publicdocs/ctaplan/Policy_CTA_Non_Display_with_FAQ.pdf |
| CTA Vendor Guide | undated | https://www.ctaplan.com/publicdocs/ctaplan/notifications/trader-update/Vendor_Guide.pdf |
| CT Plan Policies | version 1.1, 19 Aug 2026, effective 1 Apr 2027 | https://cdn.databp.com/tenants/datact/CT-Plan-Policies.pdf |
| CT Plan Data Usage Agreement | version 1.0, published 18 Aug 2026, effective 1 Apr 2027 | https://consolidatedtape.com/agreements/data-agreement.html |
| CT Plan transition page | fetched 29 Sep 2026 | https://consolidatedtape.com/ |
| OPRA Electronic Form of Subscriber Agreement | undated | https://cdn.opraplan.com/documents/OPRA_Electronic_Subscriber_Agreement.pdf |
| Cboe Terms and Conditions for Use of Cboe Websites | last updated 16 Nov 2022 | https://www.cboe.com/terms |
| Cboe Use of Cboe Content | fetched 29 Sep 2026 | https://www.cboe.com/use-of-content |
| Cboe VIX Historical Data page | fetched 29 Sep 2026 | https://www.cboe.com/tradable-products/vix/vix-historical-data |
| Kenneth French Data Library | files built from the 202608 CRSP database | https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html |
| SEC Privacy Information | last reviewed or updated 29 Nov 2023 | https://www.sec.gov/about/privacy-information |
| FINRA Terms of Use | last modified 9 Nov 2023 | https://www.finra.org/terms-of-use |
| CAT NMS Plan Legal Notice | fetched 29 Sep 2026 | https://www.catnmsplan.com/legal-notice |
| Yahoo Terms of Service | last updated 4 Aug 2026 | https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html |
| GitHub repository page and API | checked 29 Sep 2026 | https://github.com/nbrealty/IAMGOD and https://api.github.com/repos/nbrealty/IAMGOD |
