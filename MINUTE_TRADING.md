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
| Live paper minute trader | not built | **Your first job** (below) |

Headline results (out of sample, realistic cost, per $1,000 traded): every setup lost between about $0.03 and $0.45 a
trade. The 5-minute opening range breakout replicated before costs in year one and faded to about zero in 2026. Buying
same-day options on these signals lost 4% to 47% of the premium per trade. Details are in the backtest report.

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
