# Claude paper trading: two books side by side

Two paper-trading accounts run the same strategy playbook every weekday after the US close:

| Book | Who decides | What Claude can do |
|---|---|---|
| `rules` | Fixed rules from the playbook | Only skip or halve a new entry for a concrete reason, and write the daily journal note |
| `claude` | Claude | Pick sleeve weights and positions, follow or ignore the rules' suggestions, set stops |

The same hard risk limits (`config/risk_policy.yaml`) apply to both books. They live in plain
Python (`trader/risk.py`) and nothing Claude outputs can get past them:

- long only: no shorts, no leverage, no options, allowlisted symbols only;
- 0.5% of equity at risk per new trade, sized from the stop, with a 2% hard cap;
- stops are checked on every run and can only move up;
- per-position caps (30% per ETF, 10% per stock or coin), 6% total open risk, a 5% cash buffer, max 10 orders a day;
- drawdown breakers: risk halves at −10%, no new entries at −15%, exits only at −20% until a human re-enables;
- daily (−2R) and weekly (−5R) loss limits;
- a kill switch (`python -m trader kill on`).

The strategy background is in `../reports/Trading strategy playbook.md` and
`../reports/Claude autonomous trading agents.md`.

## The four sleeves

| Sleeve | Strategy | Share of equity |
|---|---|---|
| A | Faber GTAA-5 trend core: SPY, EFA, IEF, DBC, VNQ above their 10-month SMA, else T-bills (BIL) | 50–60% |
| B | Connors RSI(2) dip-buying on SPY, QQQ, IWM, DIA | 15–25% |
| C | Minervini trend-template breakouts on 40 large caps (probation) | 10–20% |
| D | BTC/ETH Donchian trend, **off until you set `enabled: true`** in `config/playbook.yaml` | 0–10% |

A code-computed regime (bull calm, bull volatile, bear, panic, choppy) switches sleeves B and C
on, to half size, or off. The rules book always follows it; the Claude book sees it and decides.

## Setup

1. **Alpaca paper accounts** (free, at alpaca.markets). Create two paper accounts, one per book,
   so their results stay separate, and copy each one's API key and secret.
2. **Anthropic API key** from console.anthropic.com.
3. Install and configure:

   ```bash
   cd trading
   pip install -r requirements.txt
   cp .env.example .env    # fill in the keys; .env is git-ignored
   ```

4. Try it without placing orders:

   ```bash
   python -m trader run --dry-run          # both books, Alpaca data, no orders, nothing saved
   python -m trader run --sim              # local simulator with $10,000 (still uses the Alpaca data key)
   ```

5. Run for real (paper money):

   ```bash
   python -m trader run                    # both books
   python -m trader status                 # positions, drawdown, Claude's last note
   python -m trader report                 # rules vs Claude vs SPY buy-and-hold
   ```

Each run is safe to repeat: a book that already ran for the latest trading day is skipped.

### Running it every day automatically

`.github/workflows/paper-trading.yml` runs both books at 21:35 UTC on weekdays and saves state
to a `trading-state` branch. To turn it on:

1. Merge this code into the default branch (GitHub only runs scheduled workflows from there).
2. In the repository settings, add secrets `ANTHROPIC_API_KEY`, `ALPACA_RULES_KEY`,
   `ALPACA_RULES_SECRET`, `ALPACA_CLAUDE_KEY`, `ALPACA_CLAUDE_SECRET`.
3. Add the repository variable `PAPER_TRADING_ENABLED` = `true`.
   Optionally set `CLAUDE_MODEL` (default `claude-opus-5`; the research suggested
   `claude-opus-5-5` as a cheaper option, and Sonnet 5 also works; Haiku does not support the settings used here).

You can also start a run by hand from the Actions tab, including a dry run.

## Files

```
config/playbook.yaml        sleeves, universes, Claude model
config/risk_policy.yaml     hard limits (Claude can read, never change)
config/playbook_brief.md    strategy summary Claude reads every day
trader/indicators.py        SMA, RSI, ATR, volatility, momentum
trader/regime.py            regime classifier
trader/strategies.py        the four sleeves
trader/risk.py              risk engine
trader/llm.py               Claude calls (structured JSON output, validated)
trader/engine.py            one daily run of one book
trader/broker.py            Alpaca paper broker and a local simulator
trader/state.py             state files, kill switch, audit journal
state/<book>/journal.jsonl  every run: regime, Claude's full output, risk decisions, orders
```

## Costs

About two Claude calls per trading day (one per book). With the default model that is roughly
$5–20 a month depending on how much Claude thinks; check `claude_meta` token counts in the journal
after the first week. Alpaca paper trading and its IEX data are free.

## Not built yet

These parts of the playbook are not implemented, so treat the results with that in mind:

- Sleeve C has no earnings-growth filter and no earnings-date check (no fundamentals data source
  yet). In the rules book, Claude's review can skip entries before earnings.
- No sector concentration cap, no automatic "sleeve kill" from bootstrapped backtests, no wash-sale tracking.
- Stops are checked on daily closes, not intraday, and orders are market orders at the next open.
- The move from 0.5% to 1% risk for proven sleeves is manual (edit the policy file).
- Only one data source, so the "two price sources disagree" check is not possible yet.
- The live Claude and Alpaca calls have not been tested against the real services; the tests use
  synthetic data, a simulator and a fake Claude.

## Tests

```bash
cd trading && python -m pytest -q
```
