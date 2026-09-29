# Minute trading: handoff for the minute-trading session

Read this first. It is the standing brief for the session that works on **minute trading** (scalping and day
trading on 1- and 5-minute charts). A separate session runs the stock books, book O and the options lab; its brief is
`OPERATION_INVEST.md`. Written 28 Sept 2026 by the operations session.

The owner is new to trading and to code. Explain things in plain, short English, and ask before anything that places
orders for the first time or changes a limit.

## Where things stand

| Piece | Location | Status |
|---|---|---|
| Research: what minute traders do, costs, paper vs live fills, the PDT rule, account safety, guru red flags | `reports/Minute trading research.md` | Done |
| **2-year backtest of 14 setups on SPY and QQQ** (Sep 2024 to Sep 2026, SIP 1-minute bars) | `reports/Minute trading backtest results.md` | Done. **No setup beat costs out of sample; none passed.** |
| Why day traders (and trading bots and AIs) lose, and **42 guardrail rules MT-G1 to MT-G42** | `reports/Why day traders lose.md` | Done. The guardrails are the law for this bot |
| An outside spec from ChatGPT, with the operations session's verdict | `reports/External intraday spec (ChatGPT, 2026-09-28).md` | Input only. Adopt its execution and test rules; test its two strategies; skip OFI |
| The backtest lab (data download and cache, 14 setups as pure functions, fills, costs, baselines, statistics) | `trading/lab/scalp/` (`python -m lab.scalp ...`), tests `trading/tests/test_scalp_*.py` | Built, reviewed twice, tested (49+ offline tests) |
| Live paper minute trader | `trading/lab/scalp/live/` (`python -m lab.scalp.live ...`), design in its `DESIGN.md`, tests `trading/tests/test_scalp_live_*.py` | Built 28 Sept 2026, 4 review rounds (3 reviewers, then verifier pairs). Dry replay of 28 Sept done. **No bot paper order yet: ask the owner first** (see "Live trader status") |
| Chart-reading research (7 reports, a blind picture test, 4 fact-checks) | `reports/Chart reading research/` (start with `00 Fact-check corrections (read first).md`, then `01 Synthesis and plan.md`) | Done 29 Sept 2026. **Wave 1 of tests awaits the owner's OK**; the cousin's journal is requested |

Headline results (out of sample, realistic cost, per $1,000 traded): every setup lost between about $0.03 and $0.45 a
trade, except GAP_FADE on SPY (+$0.39 on 74 trades, 95% range -8.7 to +16.7 bps, not significant) and NOISE_MOM on QQQ
(a check run, $0.00). The 5-minute opening range breakout replicated before costs in year one and faded to about zero in 2026. Buying
same-day options on these signals lost about 4% to 38% of the premium per trade at realistic option costs (up to 44% at pessimistic costs). Details are in the backtest report.

## Live trader status (28 Sept 2026, minute-trading session)

- **Account check passed (read-only):** SCALP account ...GWRL, ACTIVE, paper host, different from RULES (...KA87),
  equity $1,000,000 (Alpaca's default; the caps are in dollars so this is fine; the size caps need at least about
  $6,600). The bot is long-only and refuses any sell above the position. **Owner approved and I set
  `no_shorting=true` on the SCALP account at Alpaca (evening of 28 Sept 2026); shorting_enabled now False.**
- **One manual mechanics test (owner approved, 15:13 ET):** 1 SPY share bracket, bought $766.13, closed $766.06,
  paper -$0.07, honest -$0.11, account flat. Proved on the real paper API: legs show take-profit `new` and stop
  `held` after a full fill; a duplicate client_order_id gets 422; a second sell while legs are live gets 403
  "insufficient qty available" (legs reserve shares, so an exit must cancel legs first); cancels confirm in about
  50 ms; paper fills were at the NBBO, 2-3 cents better than the IEX quote the bot sees.
- **Dry replay of 28 Sept (SIP bars and quotes, simulated broker, no orders):** 5 signals, all short, all refused
  (SHORT_DISABLED; 2 also SPREAD_TOO_WIDE at 3-4 cents). Live decisions matched the backtest's intents. Shadow outcome
  if shorts had been allowed: ORB5 +$3.65, NOISE -$4.55, LAST30 +$1.14 per share gross (one day proves nothing).
- **What runs:** ORB5_QQQ and LAST30_MOM_SPY place orders (EXPLORATORY, 1 share, long only). NOISE_MOM_SPY is
  shadow-only (MT-G35: its VWAP exit uses volume, and the live free feed is IEX while the backtest was SIP).
- **Event calendar** `lab/scalp/live/events_2026.json` covers 29 Sept to 31 Dec 2026 from official sources; dates
  outside it, and dates with an unverified release, block all entries (UNKNOWN is not "no events"). Refresh it before
  1 Jan 2027. Fees (`costs.py`): SEC $20.60/M; FINRA TAF paused 1 Oct-31 Dec 2026 but still charged (Alpaca
  pass-through unverified); CAT $0.000003/share per side.
- **State across containers:** run `python -m lab.scalp.live state-save` after each session and `state-restore` at
  the start of a new container (branch `scalp-state`). A paper start whose journals do not cover the broker's SCALP
  fills keeps those setups shadow-only until restored (or `accept-journal-gap`, logged).
- **Before the first bot paper session:** owner OK; store `SCALP_RISK_HASH` (printed by `hash`) in the environment
  settings (the whole-test start date is taken automatically from the first SCALP order); start before 09:00 ET
  (a start at 09:00-16:15 with changed code blocks entries for the day, MT-G27).
- **Owner decisions of 28 Sept 2026:** first bot paper session approved for Tue 29 Sept (scheduled start 08:30 ET, before
  09:00; a wrap-up report at 16:20 ET); shorting off at Alpaca; the Notes_1 items approved. Those were built, reviewed
  by two independent reviewers and pushed: event check over the whole holding period
  (EVENT_HORIZON_OVERLAP, so ORB5 skips days with a 10:00 release or an FOMC afternoon), no new entries in a symbol after
  a seen or suspected halt, per-trade MFE/MAE diagnostics (measurement only), execution health kept apart from strategy
  performance in the report, operating costs (`operating_costs.json`, hosting "not recorded"), margin framework recorded.
- **Handoff v4 (owner file, 29 Sept):** verdict and two independent capability reports in `reports/Owner notes 2 - ...`. No
  blocker. Two gaps fixed and reviewed by two independent reviewers (full suite 2065 passed): a single-instance runner lock
  (a second `run` of the same mode refuses to start) and engine alerts also written to `state/scalp/alerts.log`. Known and not
  fixed: a full or unwritable state disk stops the bot at its first journal write (the outside watchdog then flattens); the
  watchdog shares the bot's machine; no cash reservation for pending orders (safe with one slot). Owner decisions raised:
  repository is public, key handling (G-1), data-rights conflict to clear with Alpaca.
- **Open items:** MT-G5/G6/G7/G42 (validated lane) not built, so the validated lane is impossible; `backtest_mean_r` is null
  so the MT-G13 drift check is inactive until the 20-session review fills it; the lab backtester does not yet run the
  guard code (use `replay` for the 20/60-session reviews, MT-G37). **Corrections from the fact-checks:** the SEC
  half-penny tick and lower access-fee cap were moved to the first business day of Nov 2027 (SEC Release 34-105656), not
  Nov 2026; do not plan a cost re-check for Nov 2026.

## Chart-reading research (29 Sept 2026)

Folder `reports/Chart reading research/`: seven research reports (R1 to R7), a blind picture-reading test (R8) and four
independent fact-checks. Read `00 Fact-check corrections (read first).md`, then `01 Synthesis and plan.md`. In short:
no chart technique has strong after-cost proof at minute level on SPY/QQQ; the agent's chart reading should be code (a
59-feature "Reader", spec in `R1_features.json`) with the AI limited to veto and explain (MT-G29); by eye the AI reads
clean charts 97.8% right but showed no skill predicting (small sample) and extended the trend; "10X" is a fair description of the design (not yet
measured) for coverage, consistency, records and research speed, undefined for profit. **Wave 1** is at least 114 new pre-registered tests, mostly on 2016-2024 data (old data can drop ideas, not confirm them:
MT-G6; they add to the trials already counted under MT-G7) and awaits the owner's OK. Requested from the owner: the cousin's screens, rules and a
journal including skipped trades. Cboe VIX-family files are for private use only: never commit them (scheduled downloads await the owner's decision).
**Data rights (29 Sept):** `Data rights register.md` in that folder found that this GitHub repository is public and holds
market-data files from earlier work; Alpaca's terms are silent on sending market data to an AI model (no AI layer until it
answers in writing). Owner action: check the repository's visibility.

## The owner's decisions for minute trading

1. **Own paper account.** Minute trading uses only the second Alpaca paper account, with the environment variables
   `ALPACA_SCALP_KEY` and `ALPACA_SCALP_SECRET` (the owner added them on 28 Sept 2026). **Never** use the `ALPACA_RULES_*`
   keys to place a minute-trading order. That account belongs to the stock books, book O and the options lab. Minute
   trades there would be adopted into the stock book's holdings and would corrupt its equity and breakers.
   The lab's data download falls back to the RULES keys for read-only market data; that is fine.
2. **Paper only, small amounts.** There is no live-money path (MT-G36). Going live would need a separate written owner
   decision and the rulebook's going-live gate.
3. **Untested setups may run on paper, in an "exploratory" lane (owner, 28 Sept 2026).** The owner wants to learn by
   testing on paper, including setups that have not passed. This amends MT-G5 ("shadow only until it passes") for the
   paper account only:
   - **Exploratory lane:** any registered setup (the lab's 14, the ChatGPT spec's ORB_MOMENTUM_V1 and VWAP_REVERSION_V1,
     and the owner's cousin's method once written down as exact rules). Minimum size (1 share, see caps). Every other
     guardrail still applies. Results are labelled EXPLORATORY and never count as proof of an edge.
   - **Validated lane:** only a setup version that passes MT-G5 to MT-G7 on forward data, with MT-G11's sample
     (100 closed trades over 40 sessions). Only this lane may ever size up, and only with the owner's written OK.
   - A setup's lane is shown in every report and journal line.
4. **Nothing illegal, public data only; distrust promotion.** No tips from courses, Discords or social media; no
   "top gainer" lists; SPY and QQQ only (MT-G23, MT-G24). The owner's cousin's method is welcome as an idea to test,
   the same way as everything else.
5. **Shares first; options later and shadow-first (MT-G28).** The backtest says same-day options on these signals lose
   heavily. No 0DTE.
6. **Keep all reviewers.** Build with workflows: implement, then at least two independent reviewers, then fix. Run the
   full test suite (`cd trading && python -m pytest -q`) before every push.

## Your first job

1. **Check the account (read-only), and stop if it fails.** With `ALPACA_SCALP_KEY`/`ALPACA_SCALP_SECRET`, create the
   client with `paper=True`, and confirm the base URL is the paper host. Show the owner: account number (last 4 digits
   only), status, equity, buying power, options level, and that it is **not** the RULES account (compare account
   numbers without printing keys). If the variables are missing, tell the owner to check the environment settings;
   a new session is needed after adding them.
2. **Build the live paper minute trader** in `trading/lab/scalp/live/` (or similar), reusing the setup functions in
   `trading/lab/scalp/signals.py` unchanged so live and backtest decide the same way. Build every BUILD NOW guardrail in
   `reports/Why day traders lose.md` section 4. The ones that matter most on day one:
   - MT-G36 paper-only lock; MT-G26 right account and constant position reconcile; MT-G27 kill switch.
   - MT-G21 limit orders with price collars only (no plain market orders); MT-G16 bracket with stop and target set
     before entry, never widened; MT-G38 exits are never blocked by entry filters; MT-G39 a separate watchdog that
     flattens if the bot dies; MT-G40 restart-safe counters; MT-G25 order-rate caps and unique `SCALP-` order ids.
   - MT-G2 trade caps (at most 4 round trips a day, 2 per setup, **1 open position in total**); MT-G14 fixed sizing;
     MT-G17 no averaging down; MT-G19 30-minute pause after 3 losses in a row.
   - MT-G18 daily stop, and MT-G20 clock rules (no entries after 15:30, flatten from 15:50, kill switch if anything is
     open at 15:55; the opening block applies except to setups registered and tested on the opening window, like ORB5).
   - MT-G3/MT-G4 record the bid, ask and fill of every order and compute "honest" P&L; MT-G35 tag each price's feed.
   - From the ChatGPT spec (section 8): explicit order states, protect partial fills at once, Alpaca bracket children
     activate only after the parent fills completely, a cancel request is not a cancel, log every rejected candidate
     with an enumerated reason.
3. **Dry run first.** Run a full session with no orders (decisions and would-be orders logged), show the owner what it
   would have done and why, and **ask before the first paper order.**

### Paper caps for version 1 (where two sources differ, the stricter number wins)

| Cap | Value | Source |
|---|---|---|
| Account | `ALPACA_SCALP_*` paper account only | decision 1 |
| Instruments | SPY and QQQ shares; no options, no shorts until the owner OKs shorting | MT-G23, MT-G28, ChatGPT spec |
| Size | 1 share per trade in the exploratory lane | backtest report section 8 |
| Open positions | 1 in total | MT-G2 |
| Round trips | 4 a day in total, 2 per setup; 8 entry submissions a day | MT-G2 |
| Daily loss stop | the smallest of $25, 0.5% and 1% of the day's starting equity: flatten and stop for the day | backtest report, ChatGPT spec, MT-G18 |
| Whole-test stop | $150 total loss or 60 trading days, then report to the owner | backtest report |
| Orders | marketable limits with collars; stop-limits; ids start with `SCALP-` | MT-G21, MT-G25 |
| Clock | no entries after 15:30; flatten from 15:50; nothing overnight | MT-G20 |
| Reviews | after 20 and 60 sessions: compare paper fills with a backtest replay of the same days | backtest report |

### Which setups first

The backtest report suggests ORB5_QQQ, LAST30_MOM_SPY and NOISE_MOM_SPY for the first exploratory paper test (one trade
a day each, the strongest published evidence, and they measure real fill costs). With MT-G2's single open position,
they share one slot: a later signal is skipped (and logged) while a position is open. Skip VWAP_TREND (about 16 trades a
day), VWAP_2SD_FADE, EMA 9/21, PDH/PDL and ORB30 until the three above have run, unless the owner asks.

### Known follow-ups in the backtest lab (from the last independent review)

- **The random baseline is noisy.** It draws one random trade per setup trade, which adds noise to "p vs random" at the
  strict 0.0018 bar. Draw about 20 random trades per setup trade instead (only `run()` changes; the metrics already work
  per trade).
- **Market drift is not matched.** The random side is 50/50, but some setups lean long (about 55 to 57%). Draw the
  random side with the setup's long share measured on earlier days only, so it stays free of look-ahead.
- Neither changes today's verdict (nothing beat costs), but fix both before any setup is judged a "candidate".

Before adding the ChatGPT strategies to paper, add them to the backtester as new registered versions (every threshold
counts toward the MT-G7 trial count) and note the IEX-live versus SIP-history volume mismatch for RVOL5.

## Keeping out of the other session's way

- Work only in `trading/lab/scalp/`, `trading/tests/test_scalp_*.py`, `MINUTE_TRADING.md` and new `reports/` files.
  Do not edit `trading/trader/`, `trading/lab/options_lab.py`, `trading/config/` or `OPERATION_INVEST.md` without the
  owner's OK. Those belong to the operations session.
- Keep runtime state under `trading/state/scalp/` (gitignored). If it needs saving across sessions, push it to its own
  branch, `scalp-state`, never `trading-state`.
- Work on the branch this session was given, merge `operation-invest` in when needed, and push to the branches the
  owner names. Never force-push a shared branch.

## Rules for working in this repo

- Never commit API keys, `.env`, extracted book text or anything under `trading/state/`.
- Nothing Claude outputs may bypass the guardrail code. Claude may only veto trades (MT-G29), never add risk or invent
  numbers; code computes every number.
- Add tests for every new rule; run the full test suite before every push.
- Commit messages end with the session's attribution lines; no model names in commits or files.
- Report honestly: say when something failed, when a test was skipped, and when a result is too small a sample
  (MT-G11: "INSUFFICIENT SAMPLE" below 100 trades and 40 sessions).
