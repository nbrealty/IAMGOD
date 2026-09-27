# Claude paper trading: two books side by side

Two paper-trading books run the same strategy playbook every weekday after the US close:

| Book | Who decides | What Claude can do | Where it trades now |
|---|---|---|---|
| `rules` | Fixed rules from the playbook | Only skip or halve a new B/C/D entry for a listed reason, and write the daily note | Alpaca paper account (`ALPACA_RULES_*`) |
| `claude` | Claude, picking from menus that code builds | Choose sleeve weights (one small step at a time) and positions, follow or deviate from the rules with a reason and a prediction, pick a stop from a menu | **Local simulator** until its own paper account exists |

Until the Claude book has its own Alpaca paper account (`ALPACA_CLAUDE_KEY` / `ALPACA_CLAUDE_SECRET`), it runs on
the simulator (`--sim claude`, $100,000 starting cash, fills at the next day's open plus costs). Every output
and report labels it **SIMULATED**.

## How a day works (Option B: no Anthropic API key)

Claude's decisions come from a scheduled **Claude Code session**, not from API calls. The exact steps are in
[`SESSION_RUNBOOK.md`](SESSION_RUNBOOK.md). In short:

1. `scripts/state.sh pull` loads the saved state from the `trading-state` branch.
2. `python -m trader prepare --book both --sim claude` computes everything with code and writes, per book,
   `state/<book>/pending/<date>/context.json` (today's numbers and menus), `schema.json` (the exact answer
   format) and `instructions.md`.
3. Three independent subagents per book each write one answer: `decision_1.json` ... `decision_3.json`
   (Claude book) or `review_1.json` ... `review_3.json` (rules book). Code acts only on what a majority
   agrees on, using the median size.
4. `python -m trader run --book both --sim claude --session` checks every file against the same rules, then
   sends everything through the risk engine and places the orders. A bad item is dropped on its own. With no
   valid file, the Claude book holds its positions (stops still enforced) and the rules book runs unreviewed.
5. `python -m trader status` and `python -m trader report`, then `scripts/state.sh push` saves the state.

The API path still works as an alternative: set `claude.mode: api` in `config/playbook.yaml` and
`ANTHROPIC_API_KEY`, then `python -m trader run` calls Claude directly.

## The hard limits

The limits live in `config/risk_policy.yaml` and are enforced in plain Python (`trader/risk.py`). Nothing
Claude writes can get past them; its choices only ever become targets that go through the risk engine.

- long only: no shorts, no leverage, no options, allowlisted symbols only;
- 0.5% of equity at risk per new trade (1R), sized from the stop, 2% hard cap; the stop can never be wider than
  the rule's stop, and stops only move up (sleeve C trails the 10-day low, sleeve B exits after 10 sessions);
- position caps (30% per ETF, 10% per stock or coin), at most 75% in stock-like assets, 6% total open risk,
  a 5% cash buffer, at most 10 orders a day;
- drawdown breakers from the peak: a warning at −5% (Claude may not raise B/C/D weights), risk halves at −10%,
  no new entries at −15%, exits only at −20% until the owner re-enables;
- loss limits: −1% today or −2.5% this week stops new entries; −4% this month stops new B/C/D entries;
  a sleeve 5% of equity below its own peak stops that sleeve until the owner resets it;
- a kill switch (`python -m trader kill on`).

## The four sleeves

| Sleeve | Strategy | Share of equity |
|---|---|---|
| A | Faber GTAA-5 trend core: SPY, EFA, IEF, DBC, VNQ above their 10-month SMA, else T-bills (BIL) | 50–60% |
| B | Connors RSI(2) dip-buying on SPY, QQQ, IWM, DIA | 15–25% |
| C | Minervini trend-template breakouts on 40 large caps (probation, max 2 per sector) | 10–20% |
| D | BTC/ETH Donchian trend, **off** (`enabled: false` in `config/playbook.yaml`) | 0–5% |

A code-computed regime (bull calm, bull volatile, bear, panic, choppy) switches B and C on, to half size, or
off, and a "temperature" (hot / neutral / cold) is shown to Claude. Rules marked TEST FIRST in the rulebook are
computed every day and logged as "shadow" signals only; they never change orders.

## Setup

```bash
cd trading
pip install -r requirements.txt
cp .env.example .env    # fill in the keys; .env is git-ignored. Environment variables work too.
```

Market data uses the rules account's keys unless `ALPACA_DATA_KEY` / `ALPACA_DATA_SECRET` are set. Data comes
from the consolidated `sip` feed (free for bars older than 15 minutes) with `iex` as the automatic fallback.

Try it without any risk:

```bash
python -m trader prepare --book both --sim claude       # write today's context files (no orders, no save)
python -m trader run --book both --sim claude --dry-run # compute everything, place nothing, save nothing
TRADER_STATE_DIR=/tmp/trader-test python -m trader run --sim   # both books on the simulator, test state folder
```

`TRADER_STATE_DIR` keeps a test's state away from `trading/state/`. Always use it with `run --sim` for the
rules book: the real rules book's state is tied to Alpaca, and a book cannot switch brokers.

## Commands

| Command | What it does |
|---|---|
| `run [--book rules\|claude\|both] [--sim [BOOK ...]] [--session] [--decision-file PATH ...] [--dry-run] [--no-claude]` | Today's run. `--sim` alone = every book on the simulator. `--session` uses today's decision files. A book that already ran for the latest trading day is skipped. |
| `prepare [--book ...] [--sim [BOOK ...]] [--samples N]` | Writes the pending folder for the session (no orders, no save). |
| `status` | Equity, drawdown, flags, blocked sleeves, pending orders, positions, last note. |
| `report [--json] [--since DATE]` | Books vs SPY, 60/40 and GTAA-5; per-sleeve results in R; Claude's deviations and the review's vetoes scored; prediction Brier scores; promotion, demotion and going-live gates (report only). |
| `kill on\|off [--reset-halt [--reset-peak]]` | Owner: kill switch; clear a drawdown halt. |
| `sleeve-reset S --book B` | Owner: allow a blocked sleeve's entries again. |
| `veto-reset` / `deviation-reset` | Owner: lift the automatic limits on the review's skips / the Claude book's deviations after they scored badly. |
| `promote S --book B --i-am-the-owner` / `demote ...` | Owner: raise or lower a sleeve's weight cap; shows the promotion gate first. |
| `python -m trader.backtest --start 2017-01-01 [--set KEY=VALUE] [--out FILE]` | Rules-only backtest with costs and next-open fills; never calls Claude; refuses settings that loosen risk. |

## Saving state

`scripts/state.sh pull` and `scripts/state.sh push` keep the state folder (`$TRADER_STATE_DIR`, default
`trading/state/`) as its own small git repository on the `trading-state` branch. The script never touches the
code branch. Never commit `trading/state/` to the code branch.

When the Claude book's paper account exists: add its keys, rename `state/claude` to `state/claude-sim` (the
simulated history stays for reference), and drop `--sim claude` from the runbook commands. A book cannot switch
between the simulator and Alpaca with the same state; the code refuses.

## What changed in this build (the rulebook's BUILD NOW rules)

- Lot bookkeeping fixed (`trader/ledger.py`): real fill prices, partial sells recorded, correct R after adds,
  one closed-trade record per lot, no silent rescaling when the broker disagrees, slippage measured per fill.
- Orders fill at the next open (the simulator too), are settled the next day, and costs are counted once.
- Risk engine: the rule's stop is a floor for every entry, the sleeve C trailing stop and sleeve B time stop are
  enforced for both books, plus the stock-like, speculative, sector, cluster and loss limits above.
- Claude picks from menus that code builds, with reason codes, evidence paths and falsifiable predictions.
  Deviations from the rules, the review's vetoes and predictions are all scored later.
- Three independent samples per book; majority and median decide (`trader/consensus.py`).
- Measurement (`trader/metrics.py`): benchmarks, per-sleeve R statistics, capture ratios, promotion and
  demotion gates, going-live checks.
- A rules-only backtester (`trader/backtest.py`) and a frozen test set of past days for the Claude side (`evals/`).

## Files

```
SESSION_RUNBOOK.md          the daily steps for the scheduled Claude Code session
scripts/state.sh            load/save state on the trading-state branch
config/playbook.yaml        sleeves, universes, data feed, Claude settings
config/risk_policy.yaml     hard limits (Claude can read, never change)
config/playbook_brief.md    strategy summary Claude reads every day
trader/engine.py            one daily run of one book, and `prepare`
trader/risk.py              risk engine
trader/ledger.py            lots, fills, R, costs
trader/decisions.py         turns Claude's menu choices into targets (with every check)
trader/session.py           pending folder and decision files (Option B)
trader/consensus.py         majority / median over samples
trader/llm.py               API path (alternative) and the role texts
trader/schemas.py           decision and review formats
trader/metrics.py, shadow.py, shadow_rules.py   measurement and TEST FIRST shadow signals
trader/regime.py, strategies.py, indicators.py   regime, sleeves, indicators
trader/data.py, broker.py   Alpaca data and paper broker, local simulator
trader/backtest.py          rules-only backtester
state/<book>/journal.jsonl  every run: regime, Claude's answers, risk decisions, orders
```

## Not built yet

- Sleeve C has no earnings-growth filter and no earnings calendar; the review can skip an entry before
  earnings only with a stated date.
- Stops are checked on daily closes, not intraday, and orders are market orders at the next open.
- Moving a sleeve from 0.5% to 1% risk stays a manual edit of the policy file after its gate passes.
- Only one data source, so "two price sources disagree" cannot be checked.
- The daily routine is not scheduled yet: it needs a successful dry run and the owner's OK.
- The GitHub Actions workflow (`.github/workflows/paper-trading.yml`) is the old API-key path and stays off.

## Tests

```bash
cd trading && python -m pytest -q
```
