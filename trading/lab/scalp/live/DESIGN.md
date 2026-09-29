# Live paper minute trader: design (v1)

Package `trading/lab/scalp/live/`. Paper only, shares only, SPY and QQQ only, long only, 1 share per trade.
The law is `reports/Why day traders lose.md` section 4 (MT-G rules) plus `MINUTE_TRADING.md` (owner decisions,
paper caps). Where two sources differ, the stricter number wins. Shared types are in `model.py`.

Run from `trading/`: `python -m lab.scalp.live <command>`. Nothing in this package imports `trader/` or
`lab/options_lab.py`. Nothing reads `ALPACA_RULES_*` except `check-account`, which reads the RULES account
number (read-only) to prove the SCALP account is a different one. No LLM is called anywhere (MT-G29..G32 are
satisfied by having no LLM in v1; a test asserts the package never imports `anthropic`).

## 1. What runs

| Setup (registered v1) | Symbol | Decides at | Entry | Exit | Lane |
|---|---|---|---|---|---|
| ORB5_QQQ | QQQ | close of the 9:34 bar | ~9:35:0x | stop = other end of first 5-min candle, target 10R (bracket), else 15:50 flatten | EXPLORATORY |
| LAST30_MOM_SPY | SPY | close of the 15:29 bar | ~15:30:0x | overlay bracket: stop 0.5%, target 1.0% below/above the entry limit; 15:50 flatten | EXPLORATORY |
| NOISE_MOM_SPY | SPY | :00 and :30 from 10:00 to 15:30 | same minute | setup's own band/VWAP exits (EXIT orders) + overlay bracket 0.5% / 1.0%; 15:50 flatten | EXPLORATORY |

- Signals come from `lab/scalp/signals.py` UNCHANGED: `SETUPS[id].fn(day, ctx, live=Live(...))`; act only on
  intents whose `m` equals the latest completed bar's `m`.
- Short signals are rejected with `SHORT_DISABLED` (logged as shadow). Shorts need the owner's OK.
- One position slot for the whole bot (MT-G2); a signal while it is taken is rejected `POSITION_OPEN`.
- Differences from the backtest (each is written in `registry.json` and every report): exits by 15:50 not 15:55
  (MT-G20); overlay stop/target for the two setups that had none (MT-G16 needs a bracket); long only; today's
  bars are IEX (real time) while history and the backtest are SIP (`FEED_MISMATCH`, MT-G35).

## 2. Modules (who builds what)

### A. Pure rules (no network, no clock reads: `now` is always a parameter)

**`config.py`**: every guardrail constant as a module-level constant (MT-G41 locks them in a test), the allowlist,
setup codes, registry loading and code hashes.
- Constants (exact names and values; tests assert them):
  `ALLOWED_SYMBOLS=("SPY","QQQ")`, `SHORTS_ENABLED=False`,
  `MAX_ROUND_TRIPS_DAY=4`, `MAX_ROUND_TRIPS_SETUP=2`, `MAX_OPEN_POSITIONS=1`, `MAX_ENTRY_SUBMITS_DAY=8`,
  `MAX_ENTRY_SUBMITS_PER_MIN=6`, `MAX_OPEN_PARENTS=1`, `MAX_NOTIONAL_DAY_X_E0=4.0`, `MAX_EXIT_ORDERS_PER_MIN=30`,
  `RISK_PCT=0.001` (ChatGPT 0.10% is stricter than MT-G14's 0.25%), `NOTIONAL_CAP_PCT=0.10` (spec 10% < 25%),
  `EXPLORATORY_MAX_QTY=1`, `GROSS_NOTIONAL_MAX_X_E0=1.0`,
  `DAILY_STOP_USD=25.0`, `DAILY_STOP_PCTS=(0.005, 0.01)` (limit = min of $25 and those x E0),
  `WEEKLY_STOP_PCT=0.02`, `DRAWDOWN_HALT_PCT=0.05`, `TEST_STOP_USD=150.0`, `TEST_MAX_SESSIONS=60`,
  `LOSS_STREAK_N=3`, `LOSS_STREAK_PAUSE_MIN=30`, `STOPOUT_REENTRY_MIN=15`,
  `ENTRY_COLLAR_USD=0.02`, `ENTRY_COLLAR_PCT=0.0005`, `STOP_LIMIT_MIN_USD=0.05`, `STOP_LIMIT_FRAC=0.5`,
  `EXIT_COLLARS=(0.0005, 0.002, 0.005)`, `KILL_COLLARS=(0.002, 0.005, 0.01)`, `STOP_WATCHDOG_S=10`,
  `STOP_ESCALATION_TRIES=3`, `ENTRY_TIMEOUT_S=2`, `STOP_CONFIRM_S=5`, `EXIT_ACK_S=5`, `CANCEL_CONFIRM_S=5`,
  `OPEN_BLOCK_MIN=15`, `ENTRY_CUTOFF_MIN_BEFORE_CLOSE=29` (entries allowed while now < close - 29 min, i.e. through
  15:30:59), `FLATTEN_MIN_BEFORE_CLOSE=10`, `KILL_MIN_BEFORE_CLOSE=5`, `WATCHDOG_FLAT_MIN_BEFORE_CLOSE=3`,
  `RELEASE_BLOCK_BEFORE_MIN=2`, `RELEASE_BLOCK_AFTER_MIN=5`, `FOMC_BLOCK=("13:58","15:30:59")`,
  `CLOCK_OFFSET_MS=100`, `DATA_SILENCE_S=2`, `QUOTE_MAX_AGE_S=2`, `BAR_MAX_AGE_S=65`, `MAX_SPREAD_USD=0.02`,
  `MAX_SPREAD_BPS=5.0`, `MAX_PRICE_VS_LAST_TRADE=0.005`, `WILD_MINUTE_RANGE=0.01`, `WILD_MINUTE_PAUSE_MIN=10`,
  `LULD_PCT=0.05` (reject if decision price is more than 5% from the mean close of the last 5 bars),
  `MWCB_DROP=0.07` (SPY down 7% from prior close: no entries),
  `RECONCILE_EVERY_S=5`, `RECONCILE_IDLE_EVERY_S=30`, `MISMATCH_CONFIRM_CHECKS=2`, `MISMATCH_MIN_GAP_S=3`,
  `HONEST_SLIP_PER_SHARE=0.01`, `HEARTBEAT_STALE_S=30`, `WATCHDOG_EVERY_S=15`,
  `MIN_SAMPLE_TRADES=100`, `MIN_SAMPLE_SESSIONS=40`, `SWITCH_OFF_N=30`, `RETIRE_N=100`,
  `ORDER_PREFIX="SCALP-"`, `SETUP_CODES={"ORB5_QQQ":"ORB5Q","LAST30_MOM_SPY":"L30S","NOISE_MOM_SPY":"NOISES"}`.
- `registry.json` (committed): list of `{setup_id, symbol, version, lane, source, registered, params, code_hash,
  code_files, opening_window, tested_on_release_days, feed_live, feed_backtest, backtest_mean_r, deviations}`.
  `params` holds `overlay_stop_pct` / `overlay_target_pct` (0.005 / 0.01 for LAST30 and NOISE; null for ORB5).
  Also `{"account_last4": "GWRL", "test_start": null}`.
- `load_registry(path) -> Registry`; `Registry.get(setup_id, symbol) -> Registration | None`; refuses (raises)
  an entry with empty `source` (MT-G24), a symbol outside the allowlist (MT-G23), lane VALIDATED without
  `validated_report` whose `passed` is true (the MT-G5..G7 machinery is not built in v1, so VALIDATED is
  impossible), and any setup id not in `signals.SETUPS`.
- `code_hash(files: list[str], params: dict) -> str` (sha256 over file bytes in order + canonical JSON of params)
  (MT-G10); `risk_hash() -> str` over `config.py, risk.py, sizing.py, orders.py` (MT-G41).

**`clock.py`** (MT-G20): `SessionTimes.from_calendar(date, open_ts, close_ts)` with fields `open, close,
half_day, open_block_end (open+15m), entry_cutoff (close-29m), flatten_at (close-10m), kill_at (close-5m),
watchdog_flat_at (close-3m)`. `clock_reasons(now, st, reg, ev: DayEvents) -> list[Reason]`:
MARKET_CLOSED outside [open, close); HALF_DAY on half days (the backtest skipped them: untested); OPENING_BLOCK for
now < open_block_end unless `reg.opening_window` (and, on an 08:30 release day, also `reg.tested_on_release_days`);
AFTER_ENTRY_CUTOFF for now >= entry_cutoff; FLATTEN_WINDOW for now >= flatten_at; EVENT_CALENDAR_UNKNOWN if the
event calendar does not cover the date; RELEASE_BLACKOUT within [t-2m, t+5m] of a 10:00 release;
FOMC_BLACKOUT from 13:58:00 through 15:30:59 on FOMC statement days.

**`events.py`** + `events_2026.json` (MT-G20): `load_events(path) -> EventCalendar`;
`EventCalendar.day(date) -> DayEvents(known: bool, release_0830: list[str], releases_1000: list[pd.Timestamp],
fomc: bool)`. `known=False` outside `[covers_from, covers_through]` (missing calendar = UNKNOWN, never "no
events"). Only entries marked `verified: true` count as known events; an unverified entry makes that date
unknown.

**`sizing.py`** (MT-G14): `qty(e0: float, entry_limit: float, stop: float, stop_limit: float, lane: Lane) -> int`.
Exactly these parameters (a `confidence` or `pnl_today` keyword must raise TypeError). qty = floor(RISK_PCT*e0 /
(entry_limit - stop_limit)), capped by floor(NOTIONAL_CAP_PCT*e0/entry_limit), capped by EXPLORATORY_MAX_QTY in the
EXPLORATORY lane, 0 for SHADOW/RETIRED, never rounded up, 0 if entry_limit <= stop_limit or any input <= 0.

**`orders.py`** (MT-G21, G16, G25): the ONLY way to make an `OrderSpec`. There is no function that can make a
market, stop or stop-market order, and `OrderSpec` values it returns always have a positive limit price.
- `client_id(setup_id, version, session_date, bar_start, leg, attempt) -> str`: `SCALP-{CODE}-{YYMMDD}-{HHMM}-
  {leg}{attempt}-{h6}` with h6 = first 6 hex of sha256 of all inputs; deterministic (same attempt, same id).
  Legs: E entry parent, X exit, P protect, K kill switch, W watchdog. `parse_client_id(cid) -> dict | None`.
- `entry_bracket(candidate, reg, quote, e0, session_date, attempt) -> tuple[OrderSpec | None, list[Reason], dict]`:
  long only (short -> SHORT_DISABLED). limit = round_down_cent(ask + min(ENTRY_COLLAR_USD, ENTRY_COLLAR_PCT*ask)).
  stop = candidate.stop, or limit - stop_dist, or (overlay) limit*(1-overlay_stop_pct); round DOWN to the cent.
  stop_limit = round_down_cent(stop - max(STOP_LIMIT_MIN_USD, STOP_LIMIT_FRAC*(limit-stop))).
  target = candidate.target, or limit + target_r*(limit-stop), or limit + target_dist, or (overlay)
  limit*(1+overlay_target_pct); round to the cent. INVALID_STOP if stop >= bid or stop >= limit;
  TARGET_TOO_CLOSE if target <= limit + 0.01. qty = sizing.qty(e0, limit, stop, stop_limit, reg.lane);
  SIZE_ZERO if 0. The dict holds every number used (for the journal and MT-G33's size check).
- `exit_limit(symbol, qty, quote_or_none, last_price, collar, kind, ids...) -> OrderSpec`: sell limit =
  round_up_cent(bid*(1-collar)); with no quote use last_price*(1-max(collar, 0.005)) and note NO_QUOTE.
- Rounding helpers `round_down_cent`, `round_up_cent` (Decimal based, no float drift).

**`costs.py`** (MT-G3, G4): fee table with effective dates (SEC Section 31 $20.60 per $1M of sales from
2026-04-04; FINRA TAF $0.000195/share sold, cap per trade from the research file; CAT per share from the research
file or 0 flagged UNVERIFIED); `fees(side, qty, price, on: date) -> float` raises for a date no row covers;
`honest_pnl(buys, sells, on) = paper_pnl - HONEST_SLIP_PER_SHARE*shares*2 - fees`;
`slippage(side, fill, decision_mid) -> (cents, bps)` positive = worse. Two cost conventions (ChatGPT spec section
1): fills already contain the spread, so the spread is never subtracted again.

**`risk.py`** (MT-G2, G14, G15, G17, G18, G19, G22, G23, G25, G26, G27, G35, G41, G10 enforcement point):
`entry_reasons(ec: EntryContext) -> list[Reason]` returns EVERY failing reason (empty list = allowed).
`EntryContext` (frozen dataclass): `now, candidate, reg (Registration|None), counters (DayCounters), session
(SessionTimes), events (DayEvents), quote, last_trade, recent_bars (list[Bar] for the symbol, today),
last_data_ok, clock_offset_ms, halted (bool|None), prior_close (float|None), slot_state, open_parents (int),
open_position (bool), flags (set[Reason]: KILLED, HALTED_MANUAL, SELFTEST_FAILED, DEPLOY_IN_MARKET_HOURS,
RISK_HASH_MISMATCH, RECONCILE_MISMATCH, CODE_HASH_MISMATCH that apply now), unrealized_honest (float),
settled_cash (float), broker_nonmarginable_bp (float), gross_notional_open (float), planned_notional (float)`.
Checks (each its own reason): allowlist; registration and lane; shorts; flags; clock_reasons; caps (round trips
day/setup, POSITION_OPEN, OPEN_PARENT, submits day, submits in the rolling 60 s, notional day); cooldowns
(stop-out 15 min for (setup, symbol), loss streak 30 min, wild-minute pause); loss limits (DAILY_STOP when
realized_honest + unrealized_honest <= -daily_limit(e0) or counters.daily_stopped, WEEKLY_STOP, DRAWDOWN_HALT,
TEST_STOP incl. sessions >= 60); data (DATA_STALE if now - last_data_ok > 2 s, NO_QUOTE, QUOTE_STALE if quote age
> 2 s, BAR_STALE if the latest bar ended more than 65 s ago, SPREAD_TOO_WIDE if spread > $0.02 or > 5 bps,
CLOCK_OFFSET / CLOCK_UNVERIFIED, PRICE_AWAY_FROM_LAST_TRADE if |ask/last-1| > 0.5%, LULD_BAND, HALTED when
halted is True, MWCB); money (INSUFFICIENT_SETTLED_CASH if planned_notional > min(settled_cash,
broker_nonmarginable_bp, e0); GROSS_NOTIONAL if gross_notional_open + planned > e0). `daily_limit(e0) =
min(DAILY_STOP_USD, 0.005*e0, 0.01*e0)`. `halted is None` (status unavailable) is NOT a rejection but is
recorded as a note. EXIT/PROTECT orders never go through this function (MT-G38).

**`gates.py`** (MT-G11, G12, G13): `sample_label(n_trades, n_sessions) -> "INSUFFICIENT SAMPLE" | "OK"`;
`switch_off(r_values, seed=0) -> Lane | None` (n >= 30 and one-sided 90% bootstrap upper bound of mean < 0 ->
SHADOW; n >= 100 and mean <= 0 -> RETIRED); `cusum_trip(r_values, baseline_mean, ...) -> bool` (inactive below
30 trades or when baseline_mean is None; one-sided CUSUM with k=0.5*|shift| style parameters documented in code;
tests: a -0.2R setup trips within 90 trades in >= 90% of seeded runs, a +0.2R setup false-trips <= 10%).

**`journal.py`**: `FileJournal(path, mode, clock)` appends one JSON line per event with `ts, mode, kind` and the
fields given (numbers as floats, enums as their values, Timestamps ISO); `MemoryJournal` for tests.
Every line about a setup carries `setup_id, version, lane, feed`.

### B. Execution (depends on A and model.py)

**`broker.py`**:
- `AlpacaBroker(mode=Mode.PAPER, keys=("ALPACA_SCALP_KEY","ALPACA_SCALP_SECRET"), lock_path=...)`. MT-G36: the
  constructor refuses (raises `PaperLockError` BEFORE any network call) if the key names are not exactly the SCALP
  pair, if either env var is missing, if `APCA_API_BASE_URL` (or any url override) is set to a non-paper URL, or
  if the built client's base URL is not `https://paper-api.alpaca.markets`. `account()` also checks the account
  number starts with "PA" and ends with the registry's `account_last4`, and (if the state pin exists) equals the
  pinned full number; mismatch raises. Maps alpaca-py objects to `OrderView`/`PositionView`/`AccountView`
  (statuses lower-case strings, legs nested). `submit()` builds only `LimitOrderRequest` (with
  `order_class=BRACKET`, `take_profit=TakeProfitRequest`, `stop_loss=StopLossRequest(stop_price, limit_price)` for
  brackets); it asserts the spec's client id starts with "SCALP-", qty is an int >= 1, limit > 0, and for a SELL
  that qty <= the current long position (fetched inside the lock) so a sell can never open a short (MT-G15).
  Every submit/cancel runs under an exclusive `fcntl` file lock on `state/scalp/broker.lock` shared with the
  watchdog and the kill command. HTTP 4xx -> `BrokerReject` (with status); timeouts/5xx -> `BrokerUnavailable`.
  A 422 for a duplicate client id -> look the order up by client id and return it.
  `mode=Mode.DRY` builds a READ-ONLY instance: `submit`/`cancel` raise.
- `SimBroker(clock, account=AccountView(...), positions=(), fill_mode="quote"|"bar")`: in-memory Alpaca look-alike
  used by dry run, replay, the pre-open self-test and tests. `update(now, quotes, bars)` advances it. Quote mode:
  a buy limit fills at the ask when limit >= ask (sell: at the bid when limit <= bid), else it rests; bracket legs
  activate only after the parent is FULLY filled (take-profit "new", stop-loss "held", like Alpaca); the stop
  triggers when the bid <= stop, then acts as a limit at stop_limit. Bar mode (replay): a leg's stop/target is
  checked on each new bar after the fill bar, stop first when both are inside one bar (the backtest's rule).
  Options: `partial_fill_qty` (to test partial fills), `reject_next` (to test rejections), `cancel_delay_s`
  (a cancel request is not a cancel), `unavailable_next`. It never lets a sell exceed the long position
  (raises BrokerReject like a broker with shorting off).

**`guard.py`** (MT-G25, a separate module outside the decision code): `GuardedBroker(broker, clock, journal)`
wraps every broker the engine uses. ENTRY specs: at most MAX_ENTRY_SUBMITS_PER_MIN in any rolling 60 s,
MAX_ENTRY_SUBMITS_DAY per session, MAX_OPEN_PARENTS open parents, qty <= sizing maximum (EXPLORATORY_MAX_QTY),
notional today <= MAX_NOTIONAL_DAY_X_E0*e0, symbol in the allowlist, client id prefix SCALP-. A breach does not
send the order and raises `RunawayOrders`; the engine answers with the kill switch. EXIT/PROTECT specs have their
own budget (MAX_EXIT_ORDERS_PER_MIN); exceeding it delays (journals) but never kills. risk.py rejects these cases
earlier in normal operation; the guard is the backstop if that logic has a bug (Knight Capital).

**`engine.py`**: `Engine(broker, journal, registry, counters, session, events, ctx_by_symbol, mode, clock)` with
`tick(snap: MarketSnapshot) -> list[Decision]`. Order of work in one tick:
1. Kill/halt flags (`state/scalp/KILL` file or `engine.request_kill(reason)`): kill = cancel ALL open orders,
   wait for confirmed cancels (poll <= CANCEL_CONFIRM_S), flatten every position with `KILL_COLLARS` escalating,
   write `state/scalp/HALT` (json: reason, ts), journal, alert. Only `reset-halt` clears HALT.
2. Update tracked orders from the broker (get_order), advance the slot state machine
   (FLAT/ENTRY_PENDING/PARTIALLY_FILLED/OPEN/EXIT_PENDING/COOLDOWN/DISABLED). Never mark filled without a fill;
   a cancel request is not a cancel. Entry parent unfilled after ENTRY_TIMEOUT_S -> cancel request; a fill that
   arrives meanwhile is a position. Partial fill -> cancel the rest; if the legs are not live for the filled qty
   within STOP_CONFIRM_S -> PROTECT flatten (PARTIAL_FILL_PROTECT). After a full fill, stop confirmation: the
   stop leg must be in {new, accepted, held, pending_new} with stop and limit equal to the registered values within
   STOP_CONFIRM_S, else PROTECT flatten (STOP_UNCONFIRMED). Stops are never widened; no code path modifies a leg's
   stop price.
3. Reconcile (MT-G26) every RECONCILE_EVERY_S while anything is open or pending (RECONCILE_IDLE_EVERY_S when flat)
   and before any entry: broker positions and open orders vs the broker-mirror (expected qty per symbol, expected
   open order ids). Any non-SCALP order or position is a mismatch. Halt only if the mismatch holds on 2 checks at
   least 3 s apart and is not explained by an order in flight: then kill (RECONCILE_MISMATCH).
4. Clock: at flatten_at cancel pending entries and EXIT every position (TIME_EXIT); at kill_at with anything still
   open -> kill (OPEN_AT_KILL_TIME).
5. Daily stop (MT-G18): realized_honest + unrealized honest (bid-marked, minus honest slippage and fees) <=
   -daily_limit(e0) -> cancel all, EXIT all, `counters.daily_stopped = True` (no entries until next session).
   Weekly stop / drawdown / test stop only block entries (risk.py); the drawdown sets HALT (manual reset).
6. Stop watchdog (MT-G21): long position, stop leg not filled, bid below the stop-limit price for >= 10 s ->
   cancel legs (confirmed), then PROTECT sell at EXIT_COLLARS escalation, up to STOP_ESCALATION_TRIES, then kill.
   Pause the count while `halted` is True.
7. New bars: append to today's bars; for each registered setup on that symbol call the signal with
   `Live(side, entries, exiting)` from the REAL slot (side is 0 if another setup owns the slot); keep intents at
   the latest bar. Exits first (SETUP_EXIT via the exit path, never gated), then entries: build the bracket with
   orders.entry_bracket, run risk.entry_reasons, and on success submit (or, in DRY/REPLAY mode, submit to the
   SimBroker and journal `would_submit`). Every candidate produces a `Decision` in the journal with all reasons.
   Exploratory lane label on every line.
8. Exit path (one path, MT-G16): cancel the bracket legs, wait for confirmed cancels (if a leg filled meanwhile,
   the position is closed), then a sell limit at EXIT_COLLARS[0], re-priced to the next collar each EXIT_ACK_S
   without a fill, after the last collar -> kill. Exit order ids use leg X/P/K and an attempt number; exits have
   their own rate budget (MAX_EXIT_ORDERS_PER_MIN) that never triggers the kill switch.
9. Record each fill in the cost ledger (MT-G3): quote at decision, at submission and at fill; slippage vs the
   decision mid; fees; honest P&L; schedule the +1 min and +5 min mid marks (journal `post_fill_mark`).
   Counters update: submits, round trips (on any fill), per setup, loss streak and pause, stop-out cooldown when
   the stop leg filled, realized paper and honest P&L, notional, buy notional.
10. Heartbeat: `engine.status()` returns a dict (slot state, position, open orders, counters summary) the runner
    writes to `state/scalp/heartbeat.json` every tick.
Broker rejection of an ENTRY: never retried; the symbol is blocked for entries today (MT-G25). A rejection of an
EXIT is retried at the next collar (exits must get out). `BrokerUnavailable` on submit: query by client id
before any new attempt.

**`restore.py`** (MT-G40): `rebuild(broker, session_date, e0, cash_prev_close, week_start, test_start, registry,
now) -> tuple[DayCounters, AdoptedState]`. From `orders_since(week_start or test_start)` with the SCALP- prefix:
today's entry submits and their times, round trips per setup, closed trades paired FIFO per symbol (entry parent
fill vs leg/exit fills), realized paper/honest P&L today, week and test totals, loss streak, pause and stop-out
timers (a stop-leg fill = stop-out), notional and buy notional; test sessions = distinct session dates with any
SCALP order since test_start. `AdoptedState`: an open SCALP position with its live legs is adopted (slot OPEN); a
position without a live stop leg -> PROTECT flatten on the first tick (UNPROTECTED_POSITION); an unfilled SCALP
entry parent -> cancel (ORDER_STATE_UNCERTAIN).

### C. Runtime (depends on A, B)

**`market.py`**:
- `LiveMarket(data_client, symbols, clock)`: polls IEX every second: `get_stock_latest_quote` and
  `get_stock_latest_trade` for both symbols (one request each), and new minute bars (`get_stock_bars`, feed IEX,
  from the last known bar) so that a bar is delivered once, when complete (start + 60 s <= now). Missing bars are
  backfilled; a bar is never updated after delivery (no later corrections). Tracks `last_data_ok`. Measures the
  clock offset once a minute from Alpaca `/v2/clock` (best of 3 by round-trip time; offset_ms = |server -
  local_mid| + rtt/2; None if the call fails). Halt status: None (unavailable on the free IEX REST feed, noted once
  in the journal as HALT_STATUS_UNAVAILABLE). Returns `MarketSnapshot`. Records every poll result to the recorder.
- `ReplayMarket(date, bars (SIP 1-min for the day), quote_fn, clock)`: steps a simulated clock through the session:
  for each bar, ticks at bar end + 1 s (bar delivered, quote = real historical SIP quote at that instant from
  `quote_fn`, cached on disk), + 3 s and + 6 s (order handling). `last_data_ok = now`, clock offset 0.
- `RecordingMarket(path)`: replays a recording made by the runner (MT-G27).
- `build_context(symbol, session_date, cache_dir, data_client, trading_client) -> (Ctx, calendar_row, prior_days)`:
  SIP history of the previous ~45 days via `lab.scalp.data.download` (read-only data calls, cache in
  `state/scalp_cache`), then `lab.scalp.backtest.contexts` so live uses exactly the backtest's Ctx.

**`runner.py`**: `run(mode, ...)` the main loop at 1 Hz: build context; E0 from the account's `last_equity`
(stored once per session in `state/scalp/session-YYYY-MM-DD.json`, with the code hash of the package); pre-open
self-test (MT-G27: a SimBroker with a 1-share position and a bracket is killed by `Engine` in simulated time; must
be flat with no open orders within 10 simulated seconds, else SELFTEST_FAILED for the day); deploy guard
(a start between 09:00 and 16:15 ET whose package hash differs from the hash stored at the session's first start
-> DEPLOY_IN_MARKET_HOURS); MT-G41 risk hash (env `SCALP_RISK_HASH` if set must equal `config.risk_hash()`, else
RISK_HASH_MISMATCH; if unset, pin it in `state/scalp/risk_hash.pin` and journal RISK_HASH_UNPINNED); MT-G10
registry hashes (a mismatch makes that setup shadow-only: CODE_HASH_MISMATCH); restore; then loop: market snapshot
-> engine.tick -> heartbeat -> recorder. Starts the watchdog as a separate OS process (`start_new_session=True`)
unless `--no-watchdog`. Stops after the session close with a short end-of-day summary. Handles SIGTERM by
requesting a flatten (EXIT all) before exiting.

**`watchdog.py`** (MT-G39): separate process. Every WATCHDOG_EVERY_S in market hours: if the heartbeat is older
than HEARTBEAT_STALE_S, or it is >= watchdog_flat_at (15:57) and any position is open, it takes the broker lock,
cancels all open orders, flattens with KILL_COLLARS via its own `AlpacaBroker` (SCALP keys only), writes HALT,
journals and alerts. In DRY mode it only journals `would_flatten` (the simulated position lives in the bot).

**`report.py`**: `python -m lab.scalp.live report [--date D | --since D]` reads the journals and (paper mode) the
broker history: per setup and lane (EXPLORATORY label on every line): trades, win rate, paper P&L next to honest
P&L, slippage (median cents and bps, FEED tag), cost/gross over the last 50 trades, MT-G11 label, MT-G12 lane
check, MT-G13 CUSUM (inactive without a baseline), MT-G33 bias checks (non-standard exits must be 0; qty equals
sizing(inputs); trades after red vs green days), MT-G34 P&L by 15-minute entry bucket next to SPY buy-and-hold,
SPY open-to-close and cash, every rejected candidate counted by reason, and the dry-run "would have" list.
`--remark` (MT-G4): re-marks each fill against the historical SIP quote at the fill time (once > 15 min old).

**`__main__.py`** commands: `check-account` (read-only: SCALP account number last 4, status, equity, buying power,
options level, paper URL proof, differs from RULES; pins the full number in `state/scalp/account.pin`),
`run --mode dry|paper [--no-watchdog]`, `replay --date YYYY-MM-DD [--recording PATH]`, `kill --reason TEXT`
(writes the KILL flag; if no bot heartbeat is fresh it performs the kill itself under the lock), `reset-halt
--reason TEXT` (appends to `state/scalp/changes.log`, MT-G41), `watchdog --mode dry|paper`, `report ...`, `hash`
(prints code and risk hashes). `run --mode paper` refuses unless `--confirm-paper` is also given.

State lives in `trading/state/scalp/` (gitignored): journal/YYYY-MM-DD-<mode>.jsonl, recordings/, heartbeat.json,
HALT, KILL, session-*.json, account.pin, risk_hash.pin, changes.log, alerts.log, quote_cache/.

## 3. Tests (all offline, fake clients; files `trading/tests/test_scalp_live_*.py`)
Each MT-G rule's "Test" column from the report has a test, named after the rule (e.g.
`test_mt_g2_fifth_round_trip_rejected`). Required at least: constants locked (MT-G41); sizing property test over
10,000 random inputs and the forbidden-keyword TypeError (MT-G14); order builder cannot make a market order
(MT-G21); client ids deterministic and parseable (MT-G25); every clock rule incl. half day and FOMC 14:45
(MT-G20); unknown event calendar blocks entries; every data gate with its own reason (MT-G22); caps, cooldowns,
daily stop at 11:02 flattened within 10 s (MT-G18); restart after 3 trades and 0.9% loss keeps the counts
(MT-G40); a phantom 10 SPY shares halts within 10 s but a 2 s late fill does not (MT-G26); kill switch flattens a
mock book with the quote feed down and the entry cap used up (MT-G38, G27); a 7th entry submission in 60 s triggers
the kill switch while 8 exit resends do not (MT-G25); a broker 403 on an entry is not retried and blocks the symbol
but an exit still goes out; partial fill protection; a cancel request that is slow does not free the slot early;
stop unconfirmed -> flat; the paper lock refuses a live URL before any network call (MT-G36) and never reads
ALPACA_RULES_* keys; the package never imports anthropic, trader or options_lab; the live decision for each of the
three setups equals the backtest's intent on the same bars (live = backtest).

## 4. Changes after the first independent review (v1 build)
- Whole-test stop: `registry.json` keeps `test_start: null`; the first PAPER run pins its date in
  `state/scalp/test_start.pin` (logged in changes.log) and restore counts every session since (runner
  `resolve_test_start`). Paper refuses to run without one.
- `run --mode paper` always starts the watchdog (`--no-watchdog` is dry only). SIGTERM keeps ticking until flat, hands
  over to the kill switch after 20 s and stops after 90 s with an alert.
- Heartbeats are per mode (`heartbeat-paper.json`, `heartbeat-dry.json`): the paper watchdog and `kill` read the
  paper one only. Every alpaca-py HTTP call has a 5 s timeout (`broker.with_timeout`); the watchdog and `kill` wait at
  most 10 s for the broker lock, then act without it.
- Deploy guard: a session's first start between 09:00 and 16:15 is compared with the previous session's last start;
  a PAPER first start there with no earlier session at all is blocked.
- Registry: `uses_volume` (required; MT-G35: a volume setup is shadow-only on a non-SIP live feed, so NOISE_MOM_SPY
  is SHADOW in dry and paper runs), `model_slip_bps` (the backtest's realistic 1.5 bps per side; MT-G3 / G13 slippage
  switch-offs), `prior_registered` / `safety_fix` (MT-G10 20-session cadence). `labels()` carries `code_hash`.
- MT-G37 note: `lab/scalp/backtest.py` does not call risk.py. The 20- and 60-session paper reviews must use
  `python -m lab.scalp.live replay` (the real engine and risk gate on SIP bars) as their backtest.

## 5. Changes after the second verification round
- Whole-test start and HALT do not trust the local state folder alone (a fresh container has none): PAPER reads
  ~400 days of the broker's order history (read-only) at startup and refuses to start without it. The test start is
  the earlier of the pin and the first SCALP- order's session; a kill (K) or watchdog (W) order after the last
  `reset-halt` in changes.log with no HALT file here writes HALT again (`runner.resolve_test_start`,
  `runner.broker_halt_reason`).
- The plain KILL / HALT / daily_stop-DATE files are the PAPER bot's. A dry run's engine uses KILL-dry, HALT-dry and
  daily_stop-DATE-dry (`state.flag_name`), obeys the paper HALT read-only, and never writes or removes a paper
  flag. `reset-halt` clears both.
- Deploy guard: a start in 09:00-16:15 must match the code that ran before 09:00 (today's last pre-window start,
  else the previous session's last start) and every start already made in the window; a flagged start writes
  `deploy_block-DATE.json` and the block holds for the rest of the day (`runner.deploy_check`).
- A cancel the broker refuses (422 NOT_CANCELABLE) never stops a tick or the engine's construction; the 15:55 kill is
  checked before the 15:50 flatten step.
- MT-G4 / G12: a take-profit fill stays out of the switch-off R series (never counted as 0R) until a completed live
  bar of its minute or the next printed above its limit (journal `tp_verified`, read back at the next start). The
  P&L gates still count it as at most 0. `trade_closed.r` is the honest R; `gate_r` is what the P&L gates used.
- During a kill the trade's own exit orders are still read, so an exit that fills while being cancelled is booked
  and the trade is closed (`how = kill: ...`).

## 6. Changes after the third verification round
- Kill fills are booked (V3-1): Alpaca acknowledges a marketable limit unfilled and fills it ~0.6 s later, so the kill
  order sent on the tick that finds the account flat is filled but unread. Before the kill completes, the engine
  re-reads the kill orders, the trade's own sells and the parent and legs, books every fill (fill line, ledger,
  counters) and closes the trade (`how = kill: ...`). Shares no order explains -> wait 3 s, then `trade_unbooked` and
  an alert (the next start rebuilds the P&L from the broker). The exit, protect and SIGTERM paths already read the
  order before letting the trade go.
- MT-G4 resolution (V3-2, V3-1a, V3-2a): `trade_closed` carries `parent_cid`, `tp_limit`, `tp_filled_at`;
  resolutions (`tp_verified` from a live bar or the SIP re-mark, `tp_missed` from the re-mark) are matched by the
  entry's client id (the SimBroker's order ids repeat across processes; an old line's order id counts only inside
  its own journal file). The evening re-mark (`report --remark`, and best effort at every start) resolves each
  pending take-profit older than 16 minutes against historical SIP trades of its fill minute and the next: strictly
  through the limit -> its R; otherwise a missed fill at 0R. While any is still pending, `gates.lane_check_pending`
  demotes when the resolved series trips OR the series with every pending take-profit at its gate value (min(R, 0))
  trips: an unverified win never counts at its paper R, and counting it at 0R is used only when stricter. This may
  hold a winning setup in shadow for the rest of a run; the re-mark makes the series exact within a day. The report's
  MT-G12 / G13 lines use the same series and print how many take-profits were verified, missed or left out.
- Durable state (V3-3): `state-save` / `state-restore` copy a whitelist (journal/*.jsonl, *.pin, changes.log,
  session-*.json, deploy_block-*.json; never keys, flags, heartbeats or recordings) to and from the branch
  `scalp-state` through a temporary git worktree (the owner's checkout is never touched; the push is never forced;
  append-only files merge as the union of their lines; test_start.pin keeps the earlier date; other differences
  are reported, never overwritten). In PAPER, a setup whose broker fills no local journal covers runs shadow-only
  with a startup message to run `state-restore` (fail closed: the MT-G3 / G13 slippage history would restart).
- Feed labels (R1): each run's registrations carry the feed the run actually uses (IEX live, SIP for a historical
  replay, SIM in the self-test); the report prints FEED_MISMATCH only when that feed differs from the backtest's.

## 7. Changes after the fourth verification round
- Journal gaps (V4-1-1, V4-2-1): a session counts as covered only when the entry's client id is on a `decision`
  (its order), `submit`, `submit_uncertain` or `fill` line of the engine's own `journal/<date>-paper.jsonl`. The
  -remark / -kill / -watchdog files and lines built from the broker's history (`tp_remark`, `tp_verified`, ...) name
  the same id but prove nothing about the local record, so the startup re-mark no longer lifts the shadow on the
  next start. An unreadable line is skipped.
- A logged exit from the gap rule (V4-2-2): a journal lost for good (the container went before `state-save`) would
  otherwise hold the setup in shadow for as long as the broker's history shows the session. `accept-journal-gap
  --session D [--setup SETUP/SYM] --reason ...` writes the owner's acceptance to changes.log (MT-G41); from the next
  start that session no longer shadows the setup (journal `journal_gap_accepted`), and its fills stay missing from
  the MT-G3 / G13 slippage history. `state-restore` stays the first thing to try; the startup message names both.
- New tests pin the V3-1 kill settle (a take-profit or a stray sell that fills while the kill cancels it is booked on
  the tick that finds the account flat; unexplained shares wait MISMATCH_MIN_GAP_S before `trade_unbooked` and an
  alert), the V3-2 startup re-mark from the broker's history, and the engine's in-process pending view (`pend`).

## 8. Owner notes 1 (Notes 1 addendum v2, owner-approved 28 Sept 2026)
Source: `reports/Owner notes 1 - intraday addendum v2 and v3 (2026-09-28).md` (verdict table). Where it is stricter
it wins; nothing here loosens an MT-G rule, and every rule below applies to ENTRIES only (MT-G38: exits, protects,
the flatten, the kill switch and the watchdog are never blocked by it). Tests: `tests/test_scalp_live_notes1.py`.
- **Patch C, event check over the whole hold (`EVENT_HORIZON_OVERLAP`).** risk.py refuses a new entry when
  [d, d + ENTRY_TIMEOUT_S + H + EVENT_EXIT_ALLOWANCE_S (60 s)] meets [t - 5 min, t + 10 min]
  (`EVENT_WINDOW_BEFORE_MIN` / `_AFTER_MIN`) of any scheduled event t, endpoints included (`clock.hold_horizon`,
  `clock.event_windows`, `clock.event_horizon_hits`). Events: every release in the calendar (08:30 and 10:00 alike,
  `DayEvents.release_times`) and the FOMC statement and press conference (`DayEvents.fomc_times` from the calendar's
  `statement` / `press_conference`, else the standard 14:00 / 14:30, `FOMC_EVENT_TIMES`). H is the registry's new
  required `max_hold`: `"until_flatten"` (all three v1 setups: the hold ends at the 15:50 flatten) or whole minutes
  (then never past the flatten); a missing registration counts as `until_flatten`. The MT-G20 blocks
  (RELEASE_BLACKOUT, FOMC_BLACKOUT, OPENING_BLOCK) stay as they were; an unknown calendar is still
  EVENT_CALENDAR_UNKNOWN. Effect: ORB5's 9:35 entry is skipped on days with a 10:00 release (the owner accepted this),
  NOISE's checks are refused until 10:10 on those days, every entry before 14:40 is refused on FOMC days, and LAST30
  at 15:30 is refused only when a window reaches 15:30-15:51. A guardrail change: exempt from the MT-G10 20-session
  rule, and no v1 trade existed, so every version stays 1 (written in each registration's `deviations`; the code
  hashes did not change: signals.py, sizing.py and orders.py are untouched).
- **Patch G, halts (`HALTED`, `HALT_SUSPECTED`).** engine `_halt_watch`, every tick: a symbol whose snapshot status is
  halted, or whose latest trade is older than `HALT_SUSPECT_S` (60 s) while our data polls are fresh (last poll <=
  DATA_SILENCE_S and the symbol's quote received) from `HALT_SUSPECT_FROM_MIN` (5) after the open to the close, gets
  `DayCounters.halt_blocks[symbol]` for the rest of the session. It is written to `blocked-DATE-MODE` (key `halts`)
  before anything else, like a broker rejection, so a restart keeps it; journal `halt_block` and an alert. risk.py
  refuses that symbol's entries with the recorded reason. A halt never marks a position flat, never assumes a
  reopening, never forces an exit; the stop watchdog still pauses while the status says halted (MT-G21). On the free
  IEX feed the status is unavailable (None), so the suspicion rule is the one that acts; a data glitch that leaves the
  last trade old blocks that symbol for the day (fail closed).
- **Patch G, margin framework (record only).** `config.margin_framework(date, base_url)`:
  MARGIN_INTRADAY_FRAMEWORK (Alpaca applies FINRA Notice 26-10's intraday margin standard from 4 June 2026; source
  https://docs.alpaca.markets/us/docs/the-intraday-margin-rule, checked 2026-09-28) on the Alpaca paper host on or
  after the effective date, else UNKNOWN; with the check date and its age in days. `check-account` prints it and
  every run's `startup` journal line carries it. It gates nothing: entries are sized from settled cash (MT-G15).
- **Patch E, excursions (measurement only).** For the open trade, each tick, from the quotes the engine sees
  (`engine._diag_observe`): E = the average entry fill, D = entry limit - stop-limit per share (the same R as
  `trade_closed.r`); MFE_R = max(0, max(bid - E) / D), MAE_R = max(0, max(E - bid) / D); seconds from the first fill
  to +0.25R, +0.5R and +1R (null = not reached while observed); seconds without a fresh quote (or between ticks
  further apart than DATA_SILENCE_S) are counted as unobserved (`no_quote_s`, `gaps`), so "never reached" and "not
  seen" stay apart. Written as `diag` on the `trade_closed` line; never added to P&L, never used by an exit, never an
  R value. The report prints them per setup under strategy performance.
- **Patch F, execution health apart from strategy performance.** The engine journals `quote_age_s` in every entry
  decision's notes, `ack_ms` / `ack_status` (submit -> the broker's answer) on `submit` / `would_submit`,
  `exit_order` and `kill_order`, `latency` (seen after submit, broker submitted -> filled), `order_qty`,
  `filled_total` and `cancel_race` (a fill after a cancel request) on fills, and `data_gap_start` / `data_gap` (no
  successful poll for more than DATA_SILENCE_S in the session). The report's EXECUTION HEALTH section shows those,
  partial fills, refused cancels, broker rejections, halt blocks and the per-setup slippage against the registered
  model; every other line says "uncalibrated: no registered baseline" (a missing baseline is not "healthy"). The
  STRATEGY PERFORMANCE section holds the honest outcomes and the MT-G11 / G12 / G13 lines. Incidents are never R
  values: the MT-G12 / G13 series (engine, `runner.lane_history`, report) read closed trades only. A trade closed by
  an execution-driven exit (kill switch, protect sell) keeps its honest R in the series: the money is real, and
  dropping it would be looser.
- **Patch H, operating result.** `operating_costs.json` (committed): {name, usd_per_month, source, note} per running
  cost (Alpaca market data $0 on the free plan, LLM / API $0 because none is used, hosting `null` = not recorded). The
  report prints the honest trading P&L, each cost pro-rated over the report's calendar days (first to last journal
  date, 365.25 / 12 days a month), and the operating result = trading P&L - recorded costs, marked "incomplete" while
  any cost is not recorded (null prints "not recorded", never $0). Only report.py reads the file: nothing sizes or
  places a trade from it (a test scans the package).
- **Deploy note.** config.py and risk.py changed, so `risk_hash()` changed: the owner updates `SCALP_RISK_HASH` (print
  it with `python -m lab.scalp.live hash`) and removes a stale `state/scalp/risk_hash.pin` before the next paper start,
  or every entry is refused RISK_HASH_MISMATCH. Start before 09:00 ET (MT-G27 deploy guard).
