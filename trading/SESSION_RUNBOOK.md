# Session runbook: the weekday run after the US close

This is what a scheduled Claude Code session does every weekday after the US market close
(Option B in `OPERATION_INVEST.md`: no Anthropic API key, decisions come from this session).
Follow the steps in order. Every command below has been run and works. Do not improvise other commands.

Two books run:

- **rules** book: the rules decide; Claude can only skip or halve new B/C/D entries. It trades on the
  owner's Alpaca **paper** account (`ALPACA_RULES_KEY` / `ALPACA_RULES_SECRET`).
- **claude** book: Claude picks from menus inside the hard risk limits. It has no paper account yet, so it
  runs on the local **simulator** (`--sim claude`). Say "simulated" whenever you report on it.

## Hard rules for this session

1. Never edit, commit or push anything in the code repository. The only thing you push is the state,
   and only with `scripts/state.sh push`.
2. Never print API keys or copy them anywhere.
3. Use only the commands in this file. Never use these (they are for the owner only): `--force`,
   `--confirm-empty-account`, `kill`, `sleeve-reset`, `veto-reset`, `deviation-reset`, `promote`, `demote`.
4. Never drop `--sim claude` from a command. The Claude book has no paper account, and a book cannot switch
   between the simulator and Alpaca.
5. If a step says **stop**, skip to step 9 (the summary) and say clearly what failed.

## Step 0. Go to the trading folder and install

Run every command from the `trading/` folder of the repository. If your shell forgets the folder between
commands, start each command with `cd "$(git rev-parse --show-toplevel)/trading" && `.

```bash
cd "$(git rev-parse --show-toplevel)/trading"
pip install -q -r requirements.txt
test -n "$ALPACA_RULES_KEY" && test -n "$ALPACA_RULES_SECRET" && echo "rules keys: set" || echo "rules keys: MISSING"
```

If the keys are missing: **stop** ("ALPACA_RULES_KEY / ALPACA_RULES_SECRET are not set in this environment").
Leave `TRADER_STATE_DIR` unset, so the state lives in `trading/state/`.

## Step 1. Load the saved state

```bash
scripts/state.sh pull
```

It prints `state: loaded trading-state ...` (or, the very first time only, `trading-state does not exist
on the remote yet`). If it prints `state.sh: ...` with an error: **stop**. Do not run the books without their
saved state: the rules book would not know which lots it owns.

## Step 2. Look at where the books stand

```bash
python -m trader status
```

Note each book's `last run` date, any `HALTED`, `BLOCKED`, `WATCH` or `MONTHLY LOSS BLOCK` flags, and the
kill switch line. (The first time it prints `no runs yet`.)

## Step 3. Prepare today's context

```bash
python -m trader prepare --book both --sim claude
```

It fetches market data (`market data: 56 symbols, feed sip`) and prints, per book, the date, equity,
drawdown, regime and the **pending folder**, for example
`trading/state/claude/pending/2026-09-25` and `trading/state/rules/pending/2026-09-25`.

- If it fails with "Market data is not set up" or "Could not fetch daily bars": **stop** and quote the message
  (it names the variable or host to fix).
- If the date it prints is the same as both books' `last run` date from step 2, the market was closed today
  (holiday) or today's run already happened; `prepare` then says `already ran for <date> ... nothing
  prepared` and leaves the pending folder alone. Do nothing more: go to step 9 and say so.

## Step 4. Write the decision files with independent subagents

Each pending folder has `context.json`, `schema.json` and `instructions.md`. `instructions.md` says how
many files are wanted (normally 3): `decision_1.json` ... in the claude folder and `review_1.json` ... in
the rules folder.

Start **one fresh subagent per file** (normally 6: 3 per book), all in parallel. Do not write the files
yourself and do not let one subagent write two files: the point is independent answers, and identical files
are thrown away. Give each subagent this prompt, with the folder, file name and k filled in:

> You are writing one independent sample for a paper-trading book.
> Folder: `<absolute path of the pending folder>`.
> Read exactly three files in that folder: `instructions.md`, `context.json` and `schema.json`. Read nothing
> else: no other files in the repository, no web, no other `decision_*.json` or `review_*.json` files, and no
> remembered prices or news.
> Follow `instructions.md` exactly. Copy the full shapes it shows: every key in `schema.json` is required and
> no other key is allowed. Use `"date"` exactly as given there.
> Write one file, `<folder>/<decision_k.json or review_k.json>`, containing a single valid JSON object, with
> `"meta": {"model": "<the model you are>", "sample": <k>}`.
> Most days the right answer is to follow the rules (no actions, no skips). Do not run any command that
> trades, and do not edit any other file. Reply with one line: the file you wrote.

When they finish, check the files are there:

```bash
ls state/claude/pending/<date>/ state/rules/pending/<date>/
```

If some files are missing, carry on anyway: a missing sample counts as "follow the rules", and with no
valid file at all the Claude book holds its positions (stops still enforced) and the rules book runs
unreviewed. Mention it in the summary.

If this session has no way to start subagents, do not write the files yourself. Carry on with no files:
the Claude book holds and the rules book runs unreviewed. Say so in the summary.

## Step 5. Dry run (places no orders, saves no state; it only adds a journal line)

```bash
python -m trader run --book both --sim claude --session --dry-run
```

It prints, per book, `advisor: session files in ...: decision_1.json, ...`, the equity, the sleeve weights,
Claude's note (`claude: ...`), a `samples: X of Y valid` line, risk log lines and `planned (not sent): buy ...`
lines. Read it. `claude error: ...` means the files were not usable (the book then follows the fallback
above); note the message for the summary. Each `claude problem: ...` line names a file that was dropped, or an
action, skip or weight change inside a file that was ignored; note them for the summary. If the command itself crashes (a Python traceback): **stop**.

## Step 6. The real run

```bash
python -m trader run --book both --sim claude --session
```

This sends the rules book's orders to the Alpaca paper account (market orders for the next open) and
books the Claude book's orders in the simulator. Before it sends anything, it cancels **every** open order in
that paper account, so the owner must not place manual orders in the rules book's paper account. It prints the same as step 5 with `order:` lines, plus
`filled:` lines for yesterday's orders that filled at today's open.

- `ORDER PROBLEM: ...` lines: note every one for the summary. Do not retry.
- `skipped: already ran for <date>`: that book already ran today. Do not rerun it (never use `--force`).
- A `log: STOP: broker positions look wrong ...` line means the broker reported positions that do not match
  the book (for example an empty account); the orders in those symbols were not sent. Quote the line in the
  summary. Only the owner may decide what to do (never use `--confirm-empty-account`).
- If it stops with a message about the state belonging to another broker: **stop** and quote the message.
  Only the owner may decide what to do.
- If the command crashes (a Python traceback) during one book, the other book may not have run. Check with
  `python -m trader status`: if the other book's `last run` is not today, run that book alone: the same
  command with `--book both` replaced by `--book rules` or `--book claude` (always keep `--sim claude`).

## Step 7. Status and report

```bash
python -m trader status
python -m trader report
```

`status` shows equity, drawdown, flags, pending orders and positions per book. `report` compares each
book with SPY, 60/40 and GTAA-5 and shows per-sleeve results (it needs at least two daily runs).

## Step 8. Save the state

```bash
scripts/state.sh push
```

It prints `state: pushed trading-state (...)` or `nothing changed`. If it fails, say in the summary, in
capitals, that **the state was not saved**, and quote the error. Tomorrow's run would then start from
older state, so the owner must fix it before the next weekday.

## Step 9. Plain-English summary

End the session with a short summary for the owner, who is new to trading. Plain, short sentences, no jargon
without a few words of explanation. Include:

1. The date the run was for, and whether anything was skipped (holiday, already ran) or failed.
2. For each book: equity, drawdown from the peak, and orders sent (symbol, buy/sell, reason in a few words).
   Always call the Claude book **simulated**.
3. Fills of yesterday's orders, if any.
4. Claude's journal note for each book (the `claude:` line), and whether the decision files were used
   (quote the `samples: X of Y valid` line and every `claude problem:` line) or the book fell back to
   holding / running unreviewed.
5. Anything that needs the owner: breakers, blocked sleeves, `ORDER PROBLEM` lines, data notes (for example
   the IEX fallback), a failed state save, or a stop from this runbook.

Keep it under about 15 lines.

## For the owner: the scheduled trigger

Only after a successful dry run and with the owner's OK, create a routine that starts a fresh session each
weekday after the close, in this repository on the `operation-invest` branch. Suggested time: 17:05 New York
time (`CRON_TZ=America/New_York 5 17 * * 1-5`), which leaves time for the closing prices to settle. Never
schedule it before 16:30 New York time: the free data feed lags 16 minutes, so before 16:30 the run drops
today's bar and trades on yesterday's close.
Suggested prompt:

> Run today's paper-trading session. Open `trading/SESSION_RUNBOOK.md` in this repository and follow it step
> by step, exactly as written. Never place orders any other way, never commit or push code, and end with the
> plain-English summary it describes. Background: `OPERATION_INVEST.md`.
