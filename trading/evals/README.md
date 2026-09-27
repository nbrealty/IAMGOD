# evals: frozen test days for the Claude side

Agent building guide rules 14 and 15: a fixed set of historical days, scored by code, rerun whenever the
prompt, the instructions, the model or the config changes.

## Files

- `bars.csv.gz`: daily bars for every data symbol (`cfg.data_symbols()`), 2016 to the last frozen date.
  Split and dividend adjusted, prices rounded to 2 decimals, gzip. It is fetched once and never refreshed, so every
  rerun sees the same numbers.
- `manifest.json`: the chosen days, `{dates: [{date, regime, control, why, ...}]}`, plus how they were chosen.
- `build.py`, `prepare.py`, `check.py`: the three steps below. `__init__.py` holds the shared helpers (loading the
  frozen bars, the fixed starting state, rebuilding a day through the engine).

## The days

`python -m evals.build` (network, market data only) replays every 5th session from 2018 through the engine's
steps 1-10 (rules book, flat starting book) and picks 30 days:

- every regime label (bull_calm, bull_volatile, bear, panic, choppy), at least 2 days each;
- at least 8 **control** days: no planned B, C or D entries and no data problems. The flat starting book always buys
  its sleeve A allocation, so "no rule trades" means nothing in the sleeves Claude may review or change. On a
  control day the right answer is an empty decision (Claude book: no actions, weights kept) or an empty review;
- at least 5 days with B entries and 5 with C breakouts;
- the rest spread over time (each pick is the candidate farthest from the days already chosen; deterministic).

`--offline` re-picks from the existing `bars.csv.gz` without the network.

## Running an eval

Run from `trading/`. Use a scratch folder, never the live `state/` folder.

```
python -m evals.prepare --out /tmp/evals-run --book both --samples 3
# answer every folder /tmp/evals-run/<book>/pending/<date>/ exactly like a live session:
#   decision_<k>.json (Claude book) or review_<k>.json (rules book), each sample written independently
python -m evals.check /tmp/evals-run
```

Every day starts from the same state: a flat book on the simulator with the playbook's starting cash, and only
the bars a live run on that day would have fetched (the last `data.history_sessions` sessions up to that close).
The context goes through `engine.prepare_book`, the same code as a live `prepare`.

## What `check` scores (code only)

Each file is read by the same `SessionAdvisor` as a live run, then replayed through the engine's step 11 and the
risk engine on the rebuilt day.

| check | passes when |
|---|---|
| `parses_clean` | the file parsed with no dropped item and no problem line |
| `allowlist` | every symbol in actions, skips and predictions is on the allowlist |
| `stops_below_price` | every stop Claude's actions produced sits below today's price (Claude book) |
| `no_risk_clip` | the risk engine clipped nothing beyond what it clips on the plain rule plan |
| `actions_accepted` | no action, weight move, skip or halve was refused by code |
| `control_quiet` | control days only: no actions, weight changes, deviations, skips or halves |
| `predictions_valid` | predictions on the allowlist, inside the ranges and the daily limit; every deviation, skip or halve names one |

A check that does not apply counts as n/a, never as a pass. Missing files (the session or API never answered) and
files the reader rejects (format failures, including a wrong date) are counted separately and kept out of the
scores. With several samples per day, the report gives the consensus module's agreement rate across samples.
If the context rebuilt at check time differs from the one written by `prepare` (code, config or prompt changed in
between), the report names those days: prepare and answer them again.

Each book in the report carries `versions`: the prompt, instructions, schema and context versions the code uses
now, the prompt version(s) the days were prepared with, and the model(s) that answered. A new prompt or model is a
new system (guide rules 7 and 15): before switching on the routine or relying on an old `eval_report.json`, check
that its `prompt_version` matches the current one (`prompt_changed_since_prepare` is false); if not, run the set
again.

The report is printed and written to `<DIR>/eval_report.json`. Only the journal text would need a model grader
against a fixed rubric; that is not built.
