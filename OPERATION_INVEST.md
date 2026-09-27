# Operation Invest: handoff for the next session

Read this first. It records where the project stands, the decisions the owner has made, and
exactly what to build next. Work on the `operation-invest` branch, and push to it (the owner
also keeps `claude/investment-agents-question-hrkk10` in sync).

## Where things stand

| Piece | Location | Status |
|---|---|---|
| Research: Claude as a trading agent | `reports/Claude autonomous trading agents.md` | Done |
| Research: strategy playbook | `reports/Trading strategy playbook.md` | Done |
| Book list | `reports/Trading book list.md` | Done |
| Study notes on 11 books the owner bought | `research_notes/Book study notes/` | Done |
| Current market and professional practice (Sept 2026) | `research_notes/Current market practice/` | Done (mostly snippet-sourced) |
| **Rulebook: 114 rules with IDs, sources, status** | `reports/Agent rulebook.md` | Done, **approved to build** |
| **Agent building guide** | `reports/Agent building guide.md` | Done, **approved to build** |
| Trading system v1 (two books, four sleeves, risk engine, tests) | `trading/` (see `trading/README.md`) | Superseded by the rulebook build below |
| **Rulebook build: BUILD NOW rules, ledger, menus, consensus, measurement, shadow rules** | `trading/trader/` | Built; full test suite passes (765 tests) |
| Session flow (Option B): `prepare`, decision files, `run --session` | `trading/trader/session.py`, `engine.py`, `__main__.py` | Built; prepare and dry runs checked against the real Alpaca data and rules paper account (no orders placed) |
| **Daily session runbook** | `trading/SESSION_RUNBOOK.md` | Written; every non-order command rehearsed on the simulator |
| State on the `trading-state` branch | `trading/scripts/state.sh pull\|push` | Built and tested against a local repository; the branch does not exist on GitHub yet (the first push creates it) |
| Rules-only backtester | `trading/trader/backtest.py` | Built (2017–2026 run done; see the progress note under "What to build") |
| Frozen test days for the Claude side | `trading/evals/` | In progress |
| Scheduled weekday routine | (not created) | **Waiting for the owner's OK** after a dry run |
| GitHub Actions daily workflow | `.github/workflows/paper-trading.yml` | Old API-key path, **stays switched off** (Option B below) |
| Book PDFs | `docs/*.pdf` | Uploaded by the owner. Do not commit extracted book text. |

## Decisions the owner has made

1. **Option B: no Anthropic API key.** The Claude book's decisions (and the rules book's veto
   review) are made by a scheduled Claude Code session on the owner's subscription, not by API
   calls. Keep the API path in `trader/llm.py` working as an alternative, but the default flow is
   session-driven.
2. **Alpaca paper, $100,000 balance.** Only one paper account exists so far, for the rules book:
   environment variables `ALPACA_RULES_KEY` and `ALPACA_RULES_SECRET`. The Claude book's account
   (`ALPACA_CLAUDE_KEY` / `ALPACA_CLAUDE_SECRET`) may not exist yet. Until it does, run the Claude
   book on the local simulator (`--sim`), and say so in every report.
3. **Market data** uses the rules account's keys (`AlpacaData.from_env` already falls back to them).
4. **Later, a $100 live account.** At that size the per-trade risk and the $25 minimum order
   make most sleeves impossible, and Claude costs would dominate. Plan for a rules-only live book;
   never go live without the owner's explicit say-so and the rulebook's going-live gate (G-1 to G-7).
5. **Crypto sleeve D stays off.** The model default stays `claude-opus-5` (only relevant to the API path).

## What to build (the owner said: build the BUILD NOW rules)

**Progress (2026-09-27):** items 1–5 and 7 are built. Connectivity works: the rules paper account answers
(equity $100,000) and daily bars come from the `sip` feed. The Claude book still runs on the
simulator (no `ALPACA_CLAUDE_*` account yet). Item 6 is ready but not switched on: the steps are in
`trading/SESSION_RUNBOOK.md`, including a suggested schedule and trigger prompt. What is left:
(a) the owner's OK for a first real run and the scheduled routine; (b) confirming the first
`scripts/state.sh push` is allowed to create the `trading-state` branch from a scheduled session;
(c) the owner's call on the backtest findings (sleeve A's BIL cash leg is often cut by the 30% single-ETF cap;
sleeve B lost money 2017–2026); (d) finishing `trading/evals/`.


Use ultracode: run the build as workflows (understand → implement → adversarial review → tests).

1. **Check connectivity first.** With the env vars above, confirm the Alpaca paper account and data API respond
   (account equity, one daily bar for SPY). If they fail, stop and tell the owner exactly which
   host or variable is the problem.
2. **All BUILD NOW rules in `reports/Agent rulebook.md`**, following its "Implementation plan" section,
   including the six bookkeeping bugs it lists (stop kept on add, partial reductions not recorded,
   signal-close used instead of fill prices, silent `reconcile()` rescale, review able to skip sleeve A,
   sleeve C trailing stop not enforced in `risk.py`).
3. **TEST FIRST rules as logged shadow signals only.** They must not change orders.
4. **The agent building guide's rules** (`reports/Agent building guide.md`), adapted to Option B:
   code computes every number, Claude picks from menus, per-action validation instead of all-or-nothing,
   reason codes and falsifiable predictions with Brier scoring, override tracking, prompt/schema
   version tags, and a frozen test set in `trading/evals/`. For run-to-run consistency in session mode,
   have three independent subagents produce the decision and act on the majority (median sizes).
5. **The session-driven flow (Option B):**
   - `python -m trader prepare --book claude` writes the day's context (the same dict `build_context`
     makes) to `state/claude/pending/<date>/context.json`, plus the JSON schema the decision must match.
   - The session (Claude) reads the context, the rulebook and `config/playbook_brief.md`, and writes
     `decision.json`. The same goes for the rules book's review (`review.json`).
   - `python -m trader run --book claude --decision-file <path>` validates the file with the same
     pydantic models and runs the risk engine and orders exactly as the API path does. A missing or
     invalid file means hold (stops still enforced).
   - State lives on a `trading-state` branch (the workflow file shows the pattern). Load it at the
     start of every run and push it at the end.
6. **A daily routine:** after a successful dry run, and only with the owner's OK, create a scheduled
   trigger that starts a fresh session each weekday after the US close. It runs the flow above and
   ends with a short plain-English summary: equity, drawdown, trades, Claude's note, anything that
   failed. Write its prompt as a standalone instruction that points to this file.
7. **A backtester**, which the rulebook requires before any TEST FIRST rule can be promoted. It runs
   the sleeves over historical bars with the cost model, and never uses Claude.

## Rules for working in this repo

- Never raise risk above `trading/config/risk_policy.yaml` without the owner asking. Every rule
  change must keep or tighten limits.
- Nothing Claude outputs may bypass `trading/trader/risk.py`.
- Run `cd trading && python -m pytest -q` before every push, and add tests for every new rule.
- Never commit API keys, `.env`, extracted book text or anything under `trading/state/`.
- Explain things to the owner in plain, short English; they are new to trading and to code.
- Commit messages end with the session's attribution lines; don't put model names in commits.

## Useful facts

- Alpaca reports crypto positions as `BTCUSD`, while orders use `BTC/USD` (handled in `broker.py`).
- The free Alpaca data plan uses the IEX feed, so volume is IEX-only and noisy.
- Claude Code web sessions only reach Alpaca when the environment's network access allows it
  (it is set to Full).
- The owner's earlier cloud session could not reach `*.alpaca.markets`; new sessions can.
