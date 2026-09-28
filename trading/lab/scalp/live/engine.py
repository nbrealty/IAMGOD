"""The tick engine of the live paper minute trader: one position slot, brackets, exits, kill switch, reconcile.

`Engine.tick(snapshot)` runs about once a second (DESIGN.md section 2B). It never sleeps: everything that must
wait (a cancel to be confirmed, an exit to fill, a kill to finish) is a small state machine that moves a step on
each tick, so the heartbeat keeps beating while it waits. Order of work in one tick:

 1. Kill / halt flags: `state/scalp/KILL` or `request_kill(reason)` -> cancel ALL open orders, wait for confirmed
    cancels, sell every long position with KILL_COLLARS escalating, then write `state/scalp/HALT`. Only a person
    clears HALT (`reset-halt`). A HALT file blocks entries (HALTED_MANUAL). `request_kill` writes the KILL file
    first, so a restart in the middle of a kill resumes it and still ends in HALT (MT-G40). A leg that will not
    cancel is alerted once (a person must close the position in the dashboard); nothing is ever oversold. The
    plain KILL / HALT / daily_stop-DATE files are the PAPER bot's; a dry run uses KILL-dry, HALT-dry and
    daily_stop-DATE-dry (state.flag_name) and only reads the paper HALT, so a simulation never touches paper.
 2. Tracked orders are re-read from the broker and the slot moves: FLAT -> ENTRY_PENDING -> (PARTIALLY_FILLED) ->
    OPEN -> EXIT_PENDING -> FLAT / COOLDOWN; DISABLED after a kill, a halt or the daily stop. Nothing counts as
    filled without a fill, and a cancel REQUEST is not a cancel: the slot stays taken until the broker says
    "canceled" (a fill that arrives meanwhile is a position). Unfilled entry after ENTRY_TIMEOUT_S -> cancel. A
    partial fill -> cancel the rest, then the filled shares are sold (PARTIAL_FILL_PROTECT): after a partial fill
    no leg counts as protection (Alpaca keeps children "held" and may never activate them, ChatGPT spec 8). After a full fill the stop leg must be live with exactly the
    registered prices within STOP_CONFIRM_S or the position is sold (STOP_UNCONFIRMED). No code path ever
    changes a leg's stop price (MT-G16).
 3. Reconcile (MT-G26) against the broker-mirror (expected shares per symbol, expected open order ids) every
    RECONCILE_EVERY_S while anything is open (RECONCILE_IDLE_EVERY_S when flat) and before every entry. A
    mismatch not explained by an order in flight that holds on 2 checks at least 3 s apart -> kill.
 4. Clock (MT-G20): from flatten_at (15:50) cancel entries and exit everything (TIME_EXIT); anything still open
    at kill_at (15:55) -> kill (OPEN_AT_KILL_TIME). `request_flatten` (SIGTERM) exits the same way (SHUTDOWN)
    and blocks new entries, without a HALT.
 5. Daily stop (MT-G18): realized + unrealized HONEST P&L <= -daily_limit(E0) -> cancel, exit, no entries today.
    The 5% drawdown from the test's high-water mark writes HALT.
 6. Stop watchdog (MT-G21): long, stop leg unfilled, price below the stop-limit's limit for STOP_WATCHDOG_S ->
    cancel the legs, then PROTECT sells escalating through EXIT_COLLARS, then kill. Paused while halted.
 7. New bars -> the setups in lab/scalp/signals.py, UNCHANGED, with `Live` from the REAL slot; only intents at
    the latest bar count (an intent on a bar that arrived late with a newer one is journalled BAR_STALE, or, for
    an exit, still sent). Exits first (SETUP_EXIT, never gated), then entries: orders.entry_bracket, then
    risk.entry_check, then a reconcile, then the guarded broker. Every candidate becomes a `Decision` in the
    journal with ALL its reasons (a rejected one is a shadow trade). DRY / REPLAY send to the SimBroker only and
    journal `would_submit`.
 8. The exit path (one path, MT-G16): cancel the bracket legs, wait for confirmed cancels (a leg that filled
    meanwhile closed the position), then a sell limit at EXIT_COLLARS[0], re-priced one collar further each
    EXIT_ACK_S without a fill; after the last collar -> kill. Cancels unconfirmed for CANCEL_GIVE_UP_X x
    CANCEL_CONFIRM_S -> alert and kill. A stray open sell in the symbol (an exit sent before a restart) is waited
    for and its fills are booked to the trade. Exits have their own rate budget (guard.py).
 9. Cost ledger (MT-G3, G4): quotes at decision, submission and fill; slippage against the decision mid; fees;
    paper and honest P&L; +1 / +5 minute marks after each fill. Counters for restarts (MT-G40). A trade closed by
    the take-profit (a resting limit) is PENDING_VERIFY: the P&L gates count it as at most 0, it does not reset
    the loss streak, and it is left out of the resolved R series of the switch-offs (gates.lane_check_pending counts it at
    its gate value, at most 0R, only when that is stricter) until a print through its limit verifies it (a live bar
    here, or the MT-G4 SIP re-mark at the next start / `report --remark`, which also books a missed fill at 0R). After every closed trade (and at startup, from `history`) the automatic switch-offs run:
    MT-G12 losers, MT-G13 drift, MT-G3 / G13 slippage against the model -> SHADOW or RETIRED for this run.
10. `status()` is the heartbeat the runner writes every tick.
A broker rejection of an ENTRY is never retried and blocks the symbol's entries for the day (MT-G25), also after a
restart (state/scalp/blocked-DATE-MODE); a rejected EXIT is retried at the next collar. A timeout on submit -> look the order up by client id before anything else.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .. import signals as sg
from . import config as C
from . import costs
from . import gates
from . import orders as O
from . import risk
from . import state as S
from .broker import is_done, remaining
from .guard import ExitDelayed, GuardedBroker
from .model import (Bar, BrokerReject, BrokerUnavailable, Candidate, DayCounters, Decision, Journal, Kind, Lane,
                    LastTrade, MarketSnapshot, Mode, OrderSpec, OrderView, Quote, Reason, RunawayOrders, SlotState,
                    as_ny)

LIVE_STOP = frozenset({"new", "accepted", "held", "pending_new"})
PX_TOL = 0.005                       # prices are cents: equal within half a cent
MAX_DT_S = 5.0                       # a gap between ticks never counts as more than this (stop watchdog)
UNCERTAIN_GIVE_UP_S = 10.0           # an entry whose submit timed out and never shows up is dropped after this
TP_VERIFY_BARS = 2                   # MT-G4: a take-profit fill is verified by a live bar of its minute or the next


def _sec(x: float) -> pd.Timedelta:
    return pd.Timedelta(seconds=x)


def _q(q: Quote | None) -> dict[str, Any] | None:
    if q is None:
        return None
    return {"bid": q.bid, "ask": q.ask, "mid": q.mid, "bid_size": q.bid_size, "ask_size": q.ask_size, "ts": q.ts,
            "feed": q.feed}


# ------------------------------------------------------------------------------------------------ slot records
@dataclass
class ExitJob:
    """The one exit path for the slot's position (MT-G16)."""
    reason: Reason
    kind: Kind
    leg: str                                      # "X" exit, "P" protect
    collars: tuple[float, ...]
    started: pd.Timestamp
    decision_quote: dict[str, Any] | None = None
    phase: str = "cancel"                         # cancel -> sell
    cancel_req: dict[str, pd.Timestamp] = field(default_factory=dict)
    cancel_since: pd.Timestamp | None = None      # first cancel request still unconfirmed (MT-G16 give-up clock)
    idx: int = 0                                  # collar in use
    order_id: str | None = None
    order_at: pd.Timestamp | None = None
    order_cancel_at: pd.Timestamp | None = None
    uncertain_cid: str | None = None              # a submit timed out: find it by client id first


@dataclass
class Trade:
    """The single slot (MT-G2): one entry parent, its legs, and whatever sells it."""
    setup_id: str | None
    version: int
    symbol: str
    reg: Any
    bar_start: pd.Timestamp
    state: SlotState
    spec: OrderSpec | None = None
    candidate: Candidate | None = None
    parent_id: str | None = None
    parent_cid: str | None = None
    parent_view: OrderView | None = None
    submitted_at: pd.Timestamp | None = None
    cancel_requested_at: pd.Timestamp | None = None
    uncertain_since: pd.Timestamp | None = None   # entry submit timed out and the order was not found yet
    stop: float | None = None
    stop_limit: float | None = None
    target: float | None = None
    entry_qty: float = 0.0
    sold_qty: float = 0.0
    buys: list[tuple[float, float]] = field(default_factory=list)
    sells: list[tuple[float, float]] = field(default_factory=list)
    legs: dict[str, OrderView] = field(default_factory=dict)       # "tp" / "sl"
    sell_ids: set[str] = field(default_factory=set)
    first_fill_at: pd.Timestamp | None = None
    confirm_deadline: pd.Timestamp | None = None
    stop_confirmed: bool = False
    counted: bool = False                          # the round trip was counted (first fill)
    stop_out: bool = False
    pending_verify: bool = False                   # MT-G4: a resting take-profit filled; kept out of the gates
    tp_fill: tuple[str, float, pd.Timestamp] | None = None    # (leg id, limit, fill time) of that take-profit
    below_since: pd.Timestamp | None = None
    decision_quote: dict[str, Any] | None = None
    submit_quote: dict[str, Any] | None = None
    info: dict[str, Any] = field(default_factory=dict)
    next_attempt: dict[str, int] = field(default_factory=dict)
    exit: ExitJob | None = None
    closed_by: str = ""

    @property
    def qty(self) -> float:
        return self.entry_qty - self.sold_qty

    def avg_buy(self) -> float | None:
        n = sum(q for q, _ in self.buys)
        return sum(q * p for q, p in self.buys) / n if n > 0 else None


@dataclass
class KillJob:
    reason: str
    started: pd.Timestamp
    cancel_req: dict[str, pd.Timestamp] = field(default_factory=dict)
    orders: dict[str, dict[str, Any]] = field(default_factory=dict)   # symbol -> working kill order
    idx: dict[str, int] = field(default_factory=dict)
    alerted: set[str] = field(default_factory=set)
    retry_at: dict[str, pd.Timestamp] = field(default_factory=dict)   # symbol -> no new kill order before this
    blocked_since: dict[str, pd.Timestamp] = field(default_factory=dict)  # symbol -> waiting on sells that stay open
    unbooked_since: pd.Timestamp | None = None    # broker flat, but our books still hold shares (see _kill_settle)


# ------------------------------------------------------------------------------------------------ engine
class Engine:
    def __init__(self, broker: Any, journal: Journal, registry: Any, counters: DayCounters, session: Any,
                 events: Any, ctx_by_symbol: dict[str, Any], mode: Mode, clock: Callable[[], pd.Timestamp], *,
                 adopted: Any = None, state_dir: str | Path | None = None, flags: set[Reason] | None = None,
                 alert: Callable[[str, dict[str, Any]], None] | None = None,
                 history: dict[tuple[str, str], dict[str, list[float]]] | None = None):
        self.mode = Mode(mode)
        self.raw = broker.broker if isinstance(broker, GuardedBroker) else broker
        if self.mode is not Mode.PAPER and not hasattr(self.raw, "update"):
            raise ValueError("dry run and replay trade on a SimBroker only (no orders anywhere)")
        self.broker = broker if isinstance(broker, GuardedBroker) else GuardedBroker(broker, clock, journal)
        self.broker.e0 = counters.e0
        self.journal, self.registry, self.counters, self.session, self.events = journal, registry, counters, \
            session, events
        self.ctx = {s: (c[0] if isinstance(c, tuple) else c) for s, c in (ctx_by_symbol or {}).items()}
        self.clock, self.alert_fn = clock, alert
        self.state_dir = None if state_dir is None else Path(state_dir)
        self.flags: set[Reason] = set(flags or ())
        self.date = session.date
        self.now: pd.Timestamp = as_ny(clock())
        self.entries_by_setup: dict[str, int] = dict(counters.round_trips_by_setup)
        # MT-G25 + G40: a broker rejection blocks the symbol for the day and uses up an entry submission, even after
        # a restart (a synchronous 4xx leaves no order at Alpaca to rebuild it from)
        self.blocked_name = f"blocked-{self.date.isoformat()}-{self.mode.value}"
        self._load_blocked()
        self.broker.seed(counters.entry_submit_times, counters.entry_submits, counters.notional_traded)
        # MT-G3, G12, G13: each setup's closed-trade R and fill slippage (history from restore / journals, then
        # every new close and fill), checked at startup and after each closed trade
        # "r": the resolved R series; "pend": MT-G4 take-profits still PENDING_VERIFY (key -> gate R, min(R, 0)),
        # which gates.lane_check_pending counts only when that makes the decision more conservative
        self.hist: dict[tuple[str, str], dict[str, Any]] = {
            k: {"r": list(v.get("r") or []), "slip": list(v.get("slip") or []), "pend": dict(v.get("pend") or {})}
            for k, v in (history or {}).items()}
        self.bars: dict[str, list[Bar]] = {}
        self.quotes: dict[str, Quote] = {}
        self.last_trades: dict[str, LastTrade] = {}
        self.halted: dict[str, bool | None] = {}
        self.last_data_ok: pd.Timestamp | None = None
        self.clock_offset_ms: float | None = None
        self.trade: Trade | None = None
        self.lingering: dict[str, pd.Timestamp] = {}          # stray open orders we cancel and watch
        self.linger_req: dict[str, pd.Timestamp] = {}
        self.kill: KillJob | None = None
        self.killed = False
        self.kill_attempt = 0
        self.mm: dict[str, list[Any]] = {}                     # mismatch key -> [first seen, checks, detail]
        self.next_reconcile: pd.Timestamp | None = None
        self.marks: list[tuple[pd.Timestamp, dict[str, Any]]] = []
        self.seen: dict[str, tuple[float, float]] = {}        # order id -> (filled qty, filled value) booked
        self.last_tick: pd.Timestamp | None = None
        self.dd_halted = False
        self.new_bar_syms: list[str] = []
        self.prev_last_bar: dict[str, pd.Timestamp | None] = {}   # newest bar per symbol before this tick
        self.linger_view: dict[str, OrderView] = {}
        self._kill_read_done: set[str] = set()                # exit orders the kill has read as done (booked)
        self.tp_checks: list[dict[str, Any]] = []             # MT-G4 take-profit fills waiting for a print through
        # MT-G27: the PAPER bot owns the plain KILL / HALT / daily_stop-DATE files (the `kill` command, the watchdog
        # and `reset-halt` use them). Any other mode has its own names, so a dry run's simulated kill can never
        # flatten the paper account and a dry bot never swallows the owner's KILL meant for the paper bot.
        self.kill_name = S.flag_name(S.KILL, self.mode)
        self.halt_name = S.flag_name(S.HALT, self.mode)
        self.daily_stop_name = S.flag_name(f"daily_stop-{self.date.isoformat()}", self.mode)
        ds = self._file(self.daily_stop_name)
        if ds is not None and ds.exists():
            self.counters.daily_stopped = True          # stricter only: a restart cannot undo today's stop
        self._adopt(adopted)
        for reg in list(getattr(registry, "setups", ()) or ()):
            self._lane_gate(reg.setup_id, reg.symbol)

    # ================================================================================== public
    def tick(self, snap: MarketSnapshot) -> list[Decision]:
        now = as_ny(snap.now)
        self.now = now
        dt = min(max((now - self.last_tick).total_seconds(), 0.0), MAX_DT_S) if self.last_tick is not None else 0.0
        self._ingest(snap)
        if self.mode is not Mode.PAPER:
            self.raw.update(now, snap.quotes, snap.new_bars)    # idempotent: the runner may call it too
        self._flag_files(now)
        self._safe(self._refresh, now)
        if self.kill is not None:
            self._safe(self._kill_step, now)
        else:
            self._safe(self._reconcile, now)
            if self.kill is None:
                self._safe(self._clock_rules, now)
            if self.kill is None:
                self._safe(self._shutdown, now)
            if self.kill is None:
                self._safe(self._daily_stop, now)
            if self.kill is None:
                self._safe(self._stop_watchdog, now, dt)
            if self.kill is None and self.trade is not None and self.trade.exit is not None:
                self._safe(self._exit_step, now)
            if self.kill is not None:
                self._safe(self._kill_step, now)
        decisions = self._signals(now)
        self._verify_tps(now)
        self._marks(now)
        self.last_tick = now
        return decisions

    def request_kill(self, reason: str | Reason) -> None:
        """Kill switch (MT-G27): cancel everything, flatten everything, then HALT. Runs on the next tick (or at
        once when called from inside a tick)."""
        why = reason.value if isinstance(reason, Reason) else str(reason)
        if self.kill is not None:
            return
        self.kill = KillJob(why, self.now)
        self.flags.add(Reason.KILLED)
        # MT-G27 + G40: persist the kill BEFORE anything else, so a restart mid-kill resumes it and ends in HALT
        kf = self._file(self.kill_name)
        if kf is not None and not kf.exists():
            self._write_flag(self.kill_name, {"reason": why, "ts": self.now.isoformat(), "by": "engine kill switch"})
        self.journal.write("kill_start", reason=why, slot=self.slot_state.value)
        self._alert(f"KILL SWITCH: {why}", {"reason": why})

    def request_flatten(self, reason: str | Reason) -> None:
        """Orderly shutdown (SIGTERM, DESIGN 2C): no new entries from now on, a pending entry is cancelled and the
        position leaves through the normal exit path (SHUTDOWN). No HALT is written, unlike the kill switch; an
        exit that does not fill still escalates to the kill switch as usual."""
        why = reason.value if isinstance(reason, Reason) else str(reason)
        if Reason.SHUTDOWN in self.flags:
            return
        self.flags.add(Reason.SHUTDOWN)
        self.journal.write("flatten_requested", reason=why, slot=self.slot_state.value)

    def _shutdown(self, now: pd.Timestamp) -> None:
        t = self.trade
        if Reason.SHUTDOWN not in self.flags or t is None:
            return
        if t.state is SlotState.ENTRY_PENDING and t.cancel_requested_at is None:
            self._cancel_entry(now, Reason.SHUTDOWN)
        t = self.trade
        if t is not None and t.qty > 1e-9 and t.exit is None:
            self._start_exit(Reason.SHUTDOWN, Kind.EXIT, now)

    @property
    def slot_state(self) -> SlotState:
        t = self.trade
        if t is not None:
            return SlotState.EXIT_PENDING if t.exit is not None or self.kill is not None else t.state
        if self.kill is not None or self.killed or Reason.KILLED in self.flags or \
                Reason.HALTED_MANUAL in self.flags or self.counters.daily_stopped:
            return SlotState.DISABLED
        if self._cooling(self.now):
            return SlotState.COOLDOWN
        return SlotState.FLAT

    def status(self) -> dict[str, Any]:
        """Heartbeat (written by the runner every tick)."""
        t, c = self.trade, self.counters
        pos = None
        if t is not None:
            pos = {"symbol": t.symbol, "setup_id": t.setup_id, "qty": t.qty, "avg_entry": t.avg_buy(),
                   "stop": t.stop, "stop_limit": t.stop_limit, "target": t.target, "stop_confirmed": t.stop_confirmed,
                   "exit_reason": t.exit.reason.value if t.exit else None,
                   "lane": getattr(getattr(t.reg, "lane", None), "value", None)}
        opened = [x for x in ([t.parent_id] if t and t.parent_id else []) +
                  [v.id for v in (t.legs.values() if t else []) if not is_done(v)] +
                  ([t.exit.order_id] if t and t.exit and t.exit.order_id else []) + list(self.lingering)]
        return {"ts": self.now.isoformat(), "mode": self.mode.value, "slot": self.slot_state.value, "position": pos,
                "open_orders": opened, "killing": self.kill is not None, "killed": self.killed,
                "flags": sorted(f.value for f in self.flags),
                "counters": {"entry_submits": c.entry_submits, "round_trips": c.round_trips,
                             "round_trips_by_setup": dict(c.round_trips_by_setup), "loss_streak": c.loss_streak,
                             "realized_pnl": round(c.realized_pnl, 4), "realized_honest": round(c.realized_honest, 4),
                             "unrealized_honest": round(self._unrealized(), 4),
                             "daily_limit": risk.daily_limit(c.e0), "daily_stopped": c.daily_stopped,
                             "blocked_symbols": sorted(c.blocked_symbols), "e0": c.e0,
                             "day_trades_5_sessions": c.day_trades_5d},
                "reconcile_mismatches": sorted(self.mm), "last_data_ok": self.last_data_ok}

    # ================================================================================== inputs
    def _ingest(self, snap: MarketSnapshot) -> None:
        for s, q in (snap.quotes or {}).items():
            if q is not None and q.valid:
                self.quotes[s] = q
        for s, lt in (snap.trades or {}).items():
            if lt is not None and lt.price > 0:
                self.last_trades[s] = lt
        self.halted.update(snap.halted or {})
        if snap.last_data_ok is not None:
            self.last_data_ok = as_ny(snap.last_data_ok)
        self.clock_offset_ms = snap.clock_offset_ms
        self.new_bar_syms = []
        st = self.session
        self.prev_last_bar = {}
        for s, bl in (snap.new_bars or {}).items():
            have = self.bars.setdefault(s, [])
            self.prev_last_bar[s] = as_ny(have[-1].start) if have else None
            added = False
            for b in sorted(bl, key=lambda x: x.start):
                t = as_ny(b.start)
                if not (st.open <= t < st.close) or (have and t <= as_ny(have[-1].start)):
                    continue      # outside the session, or already delivered (a bar is never updated later)
                have.append(b)
                added = True
            if added:
                self.new_bar_syms.append(s)

    def _fresh_quote(self, sym: str) -> Quote | None:
        q = self.quotes.get(sym)
        if q is None or not q.valid or self.now - as_ny(q.ts) > _sec(C.QUOTE_MAX_AGE_S):
            return None
        return q

    def _last_price(self, sym: str, fallback: float | None = None) -> float | None:
        lt = self.last_trades.get(sym)
        q = self.quotes.get(sym)
        bars = self.bars.get(sym)
        t = self.trade if self.trade is not None and self.trade.symbol == sym else None
        for v in (lt.price if lt else None, q.bid if q is not None and q.valid else None,
                  bars[-1].close if bars else None, t.avg_buy() if t else None, fallback):
            if v is not None and math.isfinite(v) and v > 0:
                return float(v)
        return None

    def _mark(self, sym: str) -> float | None:
        q = self._fresh_quote(sym)
        return q.bid if q is not None else self._last_price(sym)

    # ================================================================================== helpers
    def _safe(self, fn: Callable[..., Any], *a: Any) -> Any:
        try:
            return fn(*a)
        except (BrokerUnavailable, BrokerReject) as e:
            self.journal.write("broker_error", step=fn.__name__, error=type(e).__name__, detail=str(e)[:300])
            return None

    def _cancel_quiet(self, oid: str, why: str, **fields: Any) -> bool:
        """A cancel REQUEST that never stops the tick: a refusal (422 'not cancelable') or a timeout is journalled
        and the caller's confirmation clock decides what happens next."""
        try:
            self.broker.cancel(oid)
        except (BrokerReject, BrokerUnavailable) as e:
            self.journal.write("cancel_failed", order_id=oid, reason=why, error=type(e).__name__,
                               status=getattr(e, "status", None), detail=str(e)[:200], **fields)
            return False
        self.journal.write("cancel_request", order_id=oid, reason=why, **fields)
        return True

    def _alert(self, msg: str, fields: dict[str, Any]) -> None:
        self.journal.write("alert", message=msg, **fields)
        if self.alert_fn is not None:
            try:
                self.alert_fn(msg, fields)
            except Exception as e:  # noqa: BLE001 - an alert channel failing must not stop the engine
                self.journal.write("alert_failed", error=str(e)[:200])

    def _labels(self, t: Trade | None = None, reg: Any = None) -> dict[str, Any]:
        reg = reg if reg is not None else (t.reg if t is not None else None)
        if reg is not None:
            return reg.labels()
        if t is not None and t.setup_id:
            return {"setup_id": t.setup_id, "version": t.version, "lane": None, "feed": None}
        return {}

    def _file(self, name: str) -> Path | None:
        return None if self.state_dir is None else self.state_dir / name

    def _write_flag(self, name: str, payload: dict[str, Any]) -> None:
        p = self._file(name)
        if p is None:
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, default=str) + "\n")

    def _read_flag(self, name: str) -> dict[str, Any] | None:
        p = self._file(name)
        if p is None or not p.exists():
            return None
        try:
            v = json.loads(p.read_text())
        except (OSError, ValueError):
            return None
        return v if isinstance(v, dict) else None

    # ---------------------------------------------------------------- broker rejections survive a restart (G25, G40)
    def _load_blocked(self) -> None:
        """Today's blocked symbols and rejected entry submissions from state/scalp/blocked-DATE (stricter only). A
        rejected submit the broker kept (an asynchronous reject) was already counted by restore.py: skipped."""
        data = self._read_flag(self.blocked_name)
        if not data:
            return
        c = self.counters
        c.blocked_symbols.update(str(x) for x in data.get("symbols") or [])
        for x in data.get("rejected") or []:
            cid = str(x.get("cid") or "")
            try:
                known = bool(cid) and self.raw.get_by_client_id(cid) is not None
            except (BrokerUnavailable, BrokerReject):
                known = False                             # cannot tell: count it (the stricter choice)
            if known:
                continue
            c.entry_submits += 1
            c.entry_submit_times.append(as_ny(x.get("ts") or self.now))
            sid = str(x.get("setup_id") or "")
            if sid:
                self.entries_by_setup[sid] = self.entries_by_setup.get(sid, 0) + 1
        self.journal.write("blocked_restored", symbols=sorted(c.blocked_symbols),
                           rejected=len(data.get("rejected") or []))

    def _save_blocked(self, now: pd.Timestamp, spec: OrderSpec, c: Candidate, status: int | None) -> None:
        data = self._read_flag(self.blocked_name) or {"symbols": [], "rejected": []}
        data["symbols"] = sorted(set(data.get("symbols") or []) | self.counters.blocked_symbols)
        data.setdefault("rejected", []).append({"cid": spec.client_order_id, "ts": now.isoformat(),
                                                "setup_id": c.setup_id, "symbol": c.symbol, "status": status})
        self._write_flag(self.blocked_name, data)

    # ---------------------------------------------------------------- automatic switch-offs (MT-G3, G12, G13)
    def _lane_gate(self, setup_id: str | None, symbol: str) -> None:
        """Demote a setup to SHADOW or RETIRED for the rest of this run when its history trips a switch-off. The
        committed registry is never rewritten; the next start recomputes the same answer from the history."""
        reg = self.registry.get(setup_id, symbol) if setup_id else None
        if reg is None or reg.lane in (Lane.SHADOW, Lane.RETIRED):
            return
        h = self.hist.get((reg.setup_id, reg.symbol)) or {}
        lane, why = gates.lane_check_pending(h.get("r") or [], list((h.get("pend") or {}).values()),
                                             h.get("slip") or [], reg.backtest_mean_r, reg.model_slip_bps)
        if lane is None:
            return
        self.registry = C.with_registration(self.registry, C.with_lane(reg, lane))
        self.journal.write("lane_demoted", from_lane=reg.lane.value, to_lane=lane.value, why=why,
                           **{**reg.labels(), "lane": lane.value})
        self._alert(f"{reg.setup_id} {reg.symbol} switched to {lane.value}: {'; '.join(why)}",
                    {"setup_id": reg.setup_id, "lane": lane.value})

    def _hist(self, t: Trade | None) -> dict[str, Any] | None:
        if t is None or not t.setup_id:
            return None
        return self._hist_for(t.setup_id, t.symbol)

    def _hist_for(self, setup_id: str, symbol: str) -> dict[str, Any]:
        h = self.hist.setdefault((setup_id, symbol), {"r": [], "slip": [], "pend": {}})
        h.setdefault("pend", {})
        return h

    def _fee_gap(self, e: Exception) -> None:
        if not getattr(self, "_fee_gap_noted", False):
            self._fee_gap_noted = True
            self._alert(f"no fee row covers {self.date} (a replay of an old date?): fees counted as 0 and "
                        "flagged FEE_TABLE_GAP", {"detail": str(e)[:200]})

    def _fees(self, side: str, q: float, px: float) -> float | None:
        try:
            return costs.fees(side, q, px, self.date)
        except ValueError as e:
            self._fee_gap(e)
            return None

    def _pnl(self, buys: list[tuple[float, float]], sells: list[tuple[float, float]]) -> dict[str, float]:
        """costs.pnl_breakdown on today's fee rows. A date no row covers (only a replay of a pre-2026 day) is
        flagged loudly and counted with the honest slippage but no fees, so the engine keeps protecting."""
        try:
            return costs.pnl_breakdown(buys, sells, self.date)
        except ValueError as e:
            self._fee_gap(e)
            paper = sum(q * p for q, p in sells) - sum(q * p for q, p in buys)
            slip = C.HONEST_SLIP_PER_SHARE * (sum(q for q, _ in buys) + sum(q for q, _ in sells))
            return {"paper_pnl": paper, "fees": 0.0, "honest_slip": slip, "honest_pnl": paper - slip,
                    "buy_qty": sum(q for q, _ in buys), "sell_qty": sum(q for q, _ in sells), "fee_table_gap": True}

    def _cooling(self, now: pd.Timestamp) -> bool:
        c = self.counters
        times = [c.loss_pause_until, *c.stopout_until.values(), *c.wild_pause_until.values()]
        return any(t is not None and now < as_ny(t) for t in times)

    def _book(self, v: OrderView) -> tuple[float, float]:
        """New fill quantity and its price on this order since we last looked ((0, 0) if none)."""
        old_q, old_v = self.seen.get(v.id, (0.0, 0.0))
        q = float(v.filled_qty or 0.0)
        val = q * float(v.filled_avg_price or 0.0)
        if q <= old_q + 1e-9 or not v.filled_avg_price:
            return 0.0, 0.0
        self.seen[v.id] = (q, val)
        dq = q - old_q
        return dq, (val - old_v) / dq

    # ================================================================================== adoption (restore.py)
    def _adopt(self, st: Any) -> None:
        if st is None:
            return
        self.kill_attempt = max(self.kill_attempt, int(getattr(st, "kill_attempt_next", 0) or 0))
        now = self.now
        for oid in getattr(st, "cancel_ids", []) or []:
            self.lingering[oid] = now - _sec(60)                 # cancel on the first tick
        for v in getattr(st, "cancel_views", []) or []:
            # fills before the restart are already in the restored position and counters: book only later ones
            self.seen[v.id] = (float(v.filled_qty), float(v.filled_qty) * float(v.filled_avg_price or 0.0))
        a = getattr(st, "trade", None)
        if a is not None:
            reg = self.registry.get(a.setup_id, a.symbol) if a.setup_id else None
            t = Trade(a.setup_id, int(a.version or 0), a.symbol, reg, a.bar_start or now.floor("min"), SlotState.OPEN,
                      parent_id=a.parent.id if a.parent is not None else None,
                      parent_cid=a.parent.client_order_id if a.parent is not None else None,
                      parent_view=a.parent, entry_qty=float(a.qty), buys=[(float(a.qty), float(a.avg_entry))],
                      next_attempt=dict(a.next_attempt or {}), counted=True)
            if a.parent is not None:
                self.seen[a.parent.id] = (float(a.parent.filled_qty), float(a.parent.filled_qty) *
                                          float(a.parent.filled_avg_price or 0.0))
                for g in a.parent.legs:
                    role = "sl" if g.order_type == "stop_limit" else "tp"
                    t.legs[role] = g
                    t.sell_ids.add(g.id)
                    self.seen[g.id] = (float(g.filled_qty), float(g.filled_qty) * float(g.filled_avg_price or 0.0))
                sl = t.legs.get("sl")
                t.stop = sl.stop_price if sl is not None else None
                t.stop_limit = sl.limit_price if sl is not None else None
                tp = t.legs.get("tp")
                t.target = tp.limit_price if tp is not None else None
            self.trade = t
            self.journal.write("adopt", symbol=a.symbol, qty=a.qty, protected=a.protected, why=a.why,
                               **self._labels(t))
            if a.protected:
                t.stop_confirmed = True
            else:
                self._start_exit(Reason.UNPROTECTED_POSITION, Kind.PROTECT, now, run=False)
        p = getattr(st, "pending_entry", None)
        if p is not None:
            parsed = O.parse_client_id(p.client_order_id) or {}
            sid = parsed.get("setup_id")
            if self.trade is None:
                reg = self.registry.get(sid, p.symbol) if sid else None
                bs = as_ny(pd.Timestamp(f"{parsed['session_date'].isoformat()} {parsed['hhmm'][:2]}:"
                                        f"{parsed['hhmm'][2:]}")) if parsed else now.floor("min")
                self.trade = Trade(sid, int(getattr(reg, "version", 0) or 0), p.symbol, reg, bs,
                                   SlotState.ENTRY_PENDING, parent_id=p.id, parent_cid=p.client_order_id,
                                   parent_view=p, submitted_at=p.submitted_at or now)
                self.journal.write("adopt_pending_entry", cid=p.client_order_id, symbol=p.symbol,
                                   reason=Reason.ORDER_STATE_UNCERTAIN.value, **self._labels(self.trade))
                self._cancel_entry(now, Reason.ORDER_STATE_UNCERTAIN)
            else:
                self.lingering[p.id] = now - _sec(60)

    # ================================================================================== flags
    def _flag_files(self, now: pd.Timestamp) -> None:
        if self.state_dir is None:
            return
        kill = self._file(self.kill_name)
        if kill.exists() and self.kill is None:
            data = self._read_flag(self.kill_name)
            if data is not None:
                why = str(data.get("reason") or "KILL file")[:200]
            else:
                try:
                    why = kill.read_text().strip()[:200] or "KILL file"
                except OSError:
                    why = "KILL file"
            self.request_kill(why if why.startswith("KILL file") else f"KILL file: {why}")
        # our own HALT, and (a dry run) the paper HALT too, read-only: the stricter choice
        halts = [p for p in {self._file(self.halt_name), self._file(S.HALT)} if p.exists()]
        if halts:
            if Reason.HALTED_MANUAL not in self.flags:
                self.journal.write("halt_seen", path=str(halts[0]))
            self.flags.add(Reason.HALTED_MANUAL)
        elif not self.dd_halted:
            self.flags.discard(Reason.HALTED_MANUAL)

    # ================================================================================== order tracking
    def _refresh(self, now: pd.Timestamp) -> None:
        for oid in list(self.lingering):
            v = self.broker.get_order(oid)
            self.linger_view[oid] = v
            t = self.trade
            if v.side == "sell" and t is not None and v.symbol == t.symbol:
                # a stray sell (an exit sent before a restart, a leg of an older bracket) that fills sells the slot's
                # shares: book it to the trade so its P&L is never lost (MT-G40)
                dq, px = self._book(v)
                if dq > 0:
                    t.sell_ids.add(v.id)
                    leg = (O.parse_client_id(v.client_order_id) or {}).get("leg")
                    self._on_fill(now, v, dq, px, "protect" if leg == "P" else "exit")
                    if t.qty <= 1e-9:
                        t.closed_by = t.closed_by or "EXIT_BEFORE_RESTART"
            if is_done(v):
                self.lingering.pop(oid, None)
                self.linger_req.pop(oid, None)
                self.linger_view.pop(oid, None)
                continue
            if now - self.lingering[oid] >= _sec(2) and (oid not in self.linger_req or
                                                          now - self.linger_req[oid] >= _sec(C.CANCEL_CONFIRM_S)):
                self._cancel_quiet(oid, "stray open order")
                self.linger_req[oid] = now
        t = self.trade
        if t is None:
            return
        if t.parent_id is None and t.uncertain_since is not None:
            found = self.broker.get_by_client_id(t.parent_cid)
            if found is None:
                if now - t.uncertain_since >= _sec(UNCERTAIN_GIVE_UP_S):
                    self.journal.write("entry_not_found", cid=t.parent_cid, reason=Reason.ORDER_STATE_UNCERTAIN.value,
                                       **self._labels(t))
                    self.trade = None
                return
            t.parent_id, t.uncertain_since = found.id, None
        self._poll_trade(now)
        if self.trade is not None and self.kill is None:
            self._advance(now)

    def _poll_trade(self, now: pd.Timestamp) -> None:
        t = self.trade
        if t is None or t.parent_id is None:
            return
        v = self.broker.get_order(t.parent_id)
        self._take_parent(now, v)

    def _take_parent(self, now: pd.Timestamp, v: OrderView) -> None:
        t = self.trade
        t.parent_view = v
        for g in v.legs:
            role = "sl" if g.order_type == "stop_limit" else "tp"
            t.legs[role] = g
            t.sell_ids.add(g.id)
        dq, px = self._book(v)
        if dq > 0:
            self._on_fill(now, v, dq, px, "entry")
        for role, g in list(t.legs.items()):
            dq, px = self._book(g)
            if dq > 0:
                if role == "sl":
                    t.stop_out = True
                else:
                    t.pending_verify = True             # MT-G4: a resting limit's paper fill needs a SIP check
                    t.tp_fill = (g.id, float(g.limit_price or px), as_ny(g.filled_at or now))
                self._on_fill(now, g, dq, px, "stop" if role == "sl" else "target")

    def _advance(self, now: pd.Timestamp) -> None:
        """Slot state machine after the broker's latest view (see the module docstring, step 2)."""
        t = self.trade
        v = t.parent_view
        if v is None:
            return
        if t.qty <= 1e-9 and t.entry_qty > 0 and is_done(v):
            self._close_trade(now, t.closed_by or ("target" if t.legs.get("tp") and t.legs["tp"].status == "filled"
                                                   else "stop"))
            return
        if t.exit is not None:
            return
        full = t.entry_qty >= float(v.qty) - 1e-9 and t.entry_qty > 0
        if t.state is SlotState.ENTRY_PENDING:
            if full:
                t.state = SlotState.OPEN
                t.first_fill_at = t.first_fill_at or now
                t.confirm_deadline = t.first_fill_at + _sec(C.STOP_CONFIRM_S)
            elif t.entry_qty > 0:
                t.state = SlotState.PARTIALLY_FILLED
                t.first_fill_at = t.first_fill_at or now
                t.confirm_deadline = t.first_fill_at + _sec(C.STOP_CONFIRM_S)
                if not is_done(v) and t.cancel_requested_at is None:
                    self._cancel_entry(now, Reason.PARTIAL_FILL_PROTECT)
            elif is_done(v):
                self.journal.write("entry_done", cid=v.client_order_id, status=v.status, filled=0,
                                   symbol=t.symbol, **self._labels(t))
                for g in t.legs.values():
                    if not is_done(g):
                        self.lingering.setdefault(g.id, now)
                self.trade = None
                return
            elif t.cancel_requested_at is None:
                if t.submitted_at is not None and now - as_ny(t.submitted_at) >= _sec(C.ENTRY_TIMEOUT_S):
                    self._cancel_entry(now, Reason.ENTRY_TIMEOUT)
            elif now - t.cancel_requested_at >= _sec(C.CANCEL_CONFIRM_S):
                self._cancel_entry(now, Reason.ORDER_STATE_UNCERTAIN)
            return
        if t.state is SlotState.PARTIALLY_FILLED:
            if not is_done(v):
                if t.cancel_requested_at is None or now - t.cancel_requested_at >= _sec(C.CANCEL_CONFIRM_S):
                    self._cancel_entry(now, Reason.PARTIAL_FILL_PROTECT)
                    v = t.parent_view
                    full = t.entry_qty >= float(v.qty) - 1e-9
            if full:
                t.state = SlotState.OPEN
                return
            # ChatGPT spec 8: after a PARTIAL fill no leg counts as protection (Alpaca keeps children "held" and
            # may never activate them), so once the rest is cancelled the filled shares are sold at once
            if is_done(v) or (t.confirm_deadline is not None and now >= t.confirm_deadline):
                self._start_exit(Reason.PARTIAL_FILL_PROTECT, Kind.PROTECT, now)
            return
        if t.state is SlotState.OPEN:
            sl = t.legs.get("sl")
            if not t.stop_confirmed:
                if self._stop_ok(t, sl):
                    t.stop_confirmed = True
                    self.journal.write("stop_confirmed", cid=t.parent_cid, qty=t.qty, stop=t.stop,
                                       stop_limit=t.stop_limit, status=sl.status, **self._labels(t))
                elif t.confirm_deadline is None or now >= t.confirm_deadline:
                    self.journal.write("stop_unconfirmed", cid=t.parent_cid, leg=sl, **self._labels(t))
                    self._start_exit(Reason.STOP_UNCONFIRMED, Kind.PROTECT, now)
                return
            if t.qty > 1e-9 and all(is_done(g) for g in t.legs.values()):
                self._start_exit(Reason.UNPROTECTED_POSITION, Kind.PROTECT, now)

    def _stop_ok(self, t: Trade, sl: OrderView | None) -> bool:
        """MT-G16 stop confirmation: the stop leg is live, covers the position and has the registered prices."""
        return (sl is not None and sl.status in LIVE_STOP and t.stop is not None and t.stop_limit is not None
                and sl.stop_price is not None and sl.limit_price is not None
                and abs(sl.stop_price - t.stop) < PX_TOL and abs(sl.limit_price - t.stop_limit) < PX_TOL
                and abs(remaining(sl) - t.qty) <= 1e-9)

    def _cancel_entry(self, now: pd.Timestamp, why: Reason) -> None:
        t = self.trade
        if t is None or t.parent_id is None:
            return
        if t.parent_view is not None and is_done(t.parent_view):
            return
        again = t.cancel_requested_at is not None
        # a refused request (422 'not cancelable', a timeout) is journalled and never stops the tick: the clock starts
        # anyway, so the CANCEL_CONFIRM_S re-request (ORDER_STATE_UNCERTAIN), the 15:50 / 15:55 rules and the kill
        # switch still run (MT-G20, MT-G40)
        self._cancel_quiet(t.parent_id, why.value, cid=t.parent_cid, repeat=again, **self._labels(t))
        t.cancel_requested_at = now
        try:
            v = self.broker.get_order(t.parent_id)               # a cancel REQUEST: look again, do not assume
        except (BrokerUnavailable, BrokerReject) as e:
            self.journal.write("broker_error", step="_cancel_entry", error=type(e).__name__, detail=str(e)[:300])
            return
        self._take_parent(now, v)

    # ================================================================================== fills and the ledger
    def _on_fill(self, now: pd.Timestamp, v: OrderView, dq: float, px: float, role: str, t: Trade | None = None
                 ) -> None:
        t = t if t is not None else self.trade
        side = v.side
        c = self.counters
        c.notional_traded += dq * px
        q = self.quotes.get(v.symbol)
        fee = self._fees(side, dq, px)
        dec = None
        if t is not None and t.symbol == v.symbol:
            if side == "buy":
                t.buys.append((dq, px))
                t.entry_qty += dq
                c.buy_notional += dq * px
                dec = t.decision_quote
                if not t.counted:
                    t.counted = True
                    c.round_trips += 1
                    if t.setup_id:
                        c.round_trips_by_setup[t.setup_id] = c.round_trips_by_setup.get(t.setup_id, 0) + 1
            else:
                t.sells.append((dq, px))
                t.sold_qty += dq
                dec = t.exit.decision_quote if t.exit is not None else _q(self.quotes.get(v.symbol))
                if role in ("stop", "protect"):
                    t.stop_out = True
        elif side == "buy":
            c.buy_notional += dq * px
        slip = None
        if dec and dec.get("mid"):
            cents, bps = costs.slippage(side, px, float(dec["mid"]))
            slip = {"cents": cents, "bps": bps, "decision_mid": dec["mid"]}
            h = self._hist(t) if t is not None and t.symbol == v.symbol else None
            if h is not None:
                h["slip"].append(float(bps))                 # MT-G3 / G13 slippage history
        self.journal.write("fill", order_id=v.id, cid=v.client_order_id, symbol=v.symbol, side=side, qty=dq,
                           price=px, role=role, fees=fee, quote_at_fill=_q(q), slippage=slip,
                           quote_at_decision=dec, quote_at_submit=t.submit_quote if t and side == "buy" else None,
                           feed=q.feed.value if q is not None else None,
                           **{k: w for k, w in self._labels(t).items() if k != "feed"})
        for m in (1, 5):
            self.marks.append((now + pd.Timedelta(minutes=m), {"symbol": v.symbol, "side": side, "fill": px,
                                                               "minutes": m, "order_id": v.id}))

    def _close_trade(self, now: pd.Timestamp, how: str) -> None:
        t = self.trade
        c = self.counters
        br = self._pnl(t.buys, t.sells)
        # MT-G4: a take-profit (resting limit) fill is PENDING_VERIFY until a SIP trade printed through the limit;
        # until then the gates count it as at most 0 and it does not reset the loss streak
        gate = min(br["honest_pnl"], 0.0) if t.pending_verify else br["honest_pnl"]
        c.realized_pnl += br["paper_pnl"]
        c.realized_honest += gate
        c.week_honest += gate
        c.test_honest += gate
        c.test_peak = max(c.test_peak, c.test_honest)
        if gate < 0:
            c.loss_streak += 1
            if c.loss_streak >= C.LOSS_STREAK_N:
                c.loss_pause_until = now + pd.Timedelta(minutes=C.LOSS_STREAK_PAUSE_MIN)
        elif not t.pending_verify:
            c.loss_streak = 0
        if t.stop_out and t.setup_id:
            c.stopout_until[(t.setup_id, t.symbol)] = now + pd.Timedelta(minutes=C.STOPOUT_REENTRY_MIN)
        risk_usd = None
        if t.spec is not None and t.spec.stop_limit_price is not None:
            risk_usd = t.entry_qty * (t.spec.limit_price - t.spec.stop_limit_price)
        # R is the trade's honest R (reports). The MT-G12 / G13 switch-offs get it only for a VERIFIED close: an
        # unverified take-profit (PENDING_VERIFY) is kept OUT of the R series (MT-G4), not counted as 0R, or every
        # winning setup would look like a loser. min(honest, 0) stays for the P&L gates above.
        r = (br["honest_pnl"] / risk_usd) if risk_usd else None
        gate_r = (gate / risk_usd) if risk_usd else None
        # parent_cid (deterministic, unique per trade) is how MT-G4 resolutions find this trade again, in any
        # process; tp_limit / tp_filled_at are what the evening SIP re-mark checks
        self.journal.write("trade_closed", symbol=t.symbol, how=how, qty=t.entry_qty, buys=t.buys, sells=t.sells,
                           paper_pnl=br["paper_pnl"], honest_pnl=br["honest_pnl"], gate_honest_pnl=gate,
                           pending_verify=t.pending_verify, fees=br["fees"], honest_slip=br["honest_slip"],
                           risk_usd=risk_usd, r=r, gate_r=gate_r, parent_cid=t.parent_cid,
                           tp_order_id=t.tp_fill[0] if t.tp_fill else None,
                           tp_limit=t.tp_fill[1] if t.tp_fill else None,
                           tp_filled_at=t.tp_fill[2] if t.tp_fill else None,
                           stop_out=t.stop_out, loss_streak=c.loss_streak,
                           realized_honest_today=c.realized_honest, **self._labels(t))
        for g in t.legs.values():
            if not is_done(g):
                self.lingering.setdefault(g.id, now)
        h = self._hist(t)
        self.trade = None
        self.next_reconcile = now                        # the book changed: check it on the next tick
        if h is not None:
            if t.pending_verify:
                self.journal.write("lane_gate_excluded", reason="PENDING_VERIFY", symbol=t.symbol, r=r,
                                   tp_order_id=t.tp_fill[0] if t.tp_fill else None,
                                   parent_cid=t.parent_cid,
                                   note="MT-G4: an unverified take-profit fill stays out of the resolved MT-G12 / G13 R "
                                        "series until a trade prints through its limit (live bar or the SIP re-mark); "
                                        "meanwhile the switch-offs also count it at its gate value (at most 0R) when "
                                        "that is stricter", **self._labels(t))
                if t.tp_fill is not None and r is not None:
                    oid, lim, at_ = t.tp_fill
                    key = t.parent_cid or oid
                    h["pend"][key] = float(min(gate_r if gate_r is not None else r, 0.0))
                    self.tp_checks.append({"setup_id": t.setup_id, "symbol": t.symbol, "order_id": oid, "limit": lim,
                                           "minute": at_.floor("min"), "r": float(r), "labels": self._labels(t),
                                           "parent_cid": t.parent_cid, "key": key})
            elif r is not None:
                h["r"].append(float(r))
            self._lane_gate(t.setup_id, t.symbol)       # MT-G12: "after every closed trade"

    def _verify_tps(self, now: pd.Timestamp) -> None:
        """MT-G4: a resting take-profit counts as filled only if a trade printed strictly through its limit. Every
        IEX trade is a SIP trade, so a completed live bar of the fill minute (or the next) with a high above the limit
        proves it; that trade's R then joins the MT-G12 / G13 series (journal `tp_verified`, which the next start
        reads back). No such bar by then: it stays out (`tp_unverified`), for the evening SIP re-mark to judge."""
        if not self.tp_checks:
            return
        keep = []
        for chk in self.tp_checks:
            last = chk["minute"] + pd.Timedelta(minutes=TP_VERIFY_BARS - 1)
            bars = [b for b in self.bars.get(chk["symbol"]) or [] if chk["minute"] <= as_ny(b.start) <= last]
            hit = next((b for b in bars if b.high > chk["limit"] + 1e-9), None)
            if hit is not None:
                self.journal.write("tp_verified", order_id=chk["order_id"], parent_cid=chk.get("parent_cid"),
                                   limit=chk["limit"], bar_start=hit.start, bar_high=hit.high, bar_feed=hit.feed,
                                   r=chk["r"], symbol=chk["symbol"], source="LIVE_BAR", **chk["labels"])
                h = self._hist_for(chk["setup_id"], chk["symbol"])
                h["pend"].pop(chk.get("key") or chk["order_id"], None)
                h["r"].append(chk["r"])
                self._lane_gate(chk["setup_id"], chk["symbol"])
            elif now >= last + pd.Timedelta(minutes=1) + _sec(C.BAR_MAX_AGE_S):
                self.journal.write("tp_unverified", order_id=chk["order_id"], parent_cid=chk.get("parent_cid"),
                                   limit=chk["limit"], symbol=chk["symbol"],
                                   bars_seen=len(bars), note="no live print through the limit: stays PENDING_VERIFY",
                                   **chk["labels"])
            else:
                keep.append(chk)
        self.tp_checks = keep

    def _marks(self, now: pd.Timestamp) -> None:
        due = [m for m in self.marks if m[0] <= now]
        if not due:
            return
        self.marks = [m for m in self.marks if m[0] > now]
        for _, m in due:
            q = self._fresh_quote(m["symbol"])
            mid = q.mid if q is not None else None
            sign = 1.0 if m["side"] == "buy" else -1.0
            move = None if mid is None else round(sign * (mid - m["fill"]) / m["fill"] * 1e4, 4)
            self.journal.write("post_fill_mark", mid=mid, move_bps_in_our_favor=move,
                               feed=q.feed.value if q is not None else None, **m)

    # ================================================================================== exit path (MT-G16)
    def _start_exit(self, reason: Reason, kind: Kind, now: pd.Timestamp, run: bool = True) -> None:
        t = self.trade
        if t is None or t.exit is not None:
            return
        # MT-G21: the stop watchdog resends at bid - 0.2% first (STOP_ESCALATION_COLLARS), every other exit starts at
        # the tighter EXIT_COLLARS
        collars = C.STOP_ESCALATION_COLLARS[:C.STOP_ESCALATION_TRIES] if reason is Reason.STOP_ESCALATION \
            else C.EXIT_COLLARS
        t.exit = ExitJob(reason, kind, "P" if kind is Kind.PROTECT else "X", tuple(collars), now,
                         _q(self.quotes.get(t.symbol)))
        t.state = SlotState.EXIT_PENDING
        self.journal.write("exit_start", reason=reason.value, order_kind=kind.value, symbol=t.symbol, qty=t.qty,
                           **self._labels(t))
        if run and self.kill is None:
            self._exit_step(now)

    def _exit_step(self, now: pd.Timestamp) -> None:
        t = self.trade
        if t is None or t.exit is None or self.kill is not None:
            return
        j = t.exit
        halted = self.halted.get(t.symbol) is True
        if j.phase == "cancel":
            live = self._exit_blockers(t)
            for x in live:
                if x.id not in j.cancel_req or now - j.cancel_req[x.id] >= _sec(C.CANCEL_CONFIRM_S):
                    again = x.id in j.cancel_req
                    j.cancel_req[x.id] = now
                    self._cancel_quiet(x.id, j.reason.value, repeat=again,
                                       note=Reason.ORDER_STATE_UNCERTAIN.value if again else None, **self._labels(t))
            if live:
                self._poll_trade(now)
                if self.trade is None:
                    return
                live = self._exit_blockers(t)
            if live:
                # a cancel request is not a cancel: wait, but not forever (MT-G16: the one exit path must get out)
                j.cancel_since = j.cancel_since or now
                if now - j.cancel_since >= _sec(C.CANCEL_GIVE_UP_X * C.CANCEL_CONFIRM_S):
                    ids = [x.id for x in live]
                    self._alert(f"{t.symbol}: cancels of {ids} not confirmed after "
                                f"{(now - j.cancel_since).total_seconds():.0f} s: kill switch. If it cannot finish, "
                                "close the position by hand in the Alpaca paper dashboard", {"orders": ids})
                    self.request_kill(f"{j.reason.value}: cancels not confirmed ({', '.join(ids)})")
                return
            if t.qty <= 1e-9:
                self._close_trade(now, t.closed_by or "leg_during_exit")
                return
            j.phase, j.cancel_since = "sell", None
        if j.order_id is not None:
            v = self.broker.get_order(j.order_id)
            dq, px = self._book(v)
            if dq > 0:
                self._on_fill(now, v, dq, px, "protect" if j.kind is Kind.PROTECT else "exit")
            if t.qty <= 1e-9:
                t.closed_by = j.reason.value
                self._close_trade(now, j.reason.value)
                return
            if not is_done(v):
                if halted:
                    return                               # MT-G21: a halt pauses the escalation
                if j.order_cancel_at is None and now - j.order_at >= _sec(C.EXIT_ACK_S):
                    j.order_cancel_at = now
                    j.cancel_since = now
                    self._cancel_quiet(v.id, "exit not filled", **self._labels(t))
                    v = self.broker.get_order(v.id)
                    dq, px = self._book(v)
                    if dq > 0:
                        self._on_fill(now, v, dq, px, "protect" if j.kind is Kind.PROTECT else "exit")
                elif j.order_cancel_at is not None and now - j.order_cancel_at >= _sec(C.CANCEL_CONFIRM_S):
                    j.order_cancel_at = now
                    self._cancel_quiet(v.id, "exit not filled", repeat=True, **self._labels(t))
                if not is_done(v):
                    if j.cancel_since is not None and \
                            now - j.cancel_since >= _sec(C.CANCEL_GIVE_UP_X * C.CANCEL_CONFIRM_S):
                        self._alert(f"{t.symbol}: the exit order {v.id} will not cancel: kill switch",
                                    {"order_id": v.id})
                        self.request_kill(f"{j.reason.value}: exit order cancel not confirmed")
                    return
                j.cancel_since = None
                if t.qty <= 1e-9:
                    self._close_trade(now, j.reason.value)
                    return
            j.order_id, j.order_cancel_at = None, None
            j.idx += 1
            if j.idx >= len(j.collars):
                self.request_kill(f"{j.reason.value}: exit not filled after {len(j.collars)} collars")
                return
        if j.uncertain_cid is not None:
            found = self.broker.get_by_client_id(j.uncertain_cid)
            if found is not None:
                j.order_id, j.order_at, j.uncertain_cid = found.id, now, None
                t.sell_ids.add(found.id)
                return
            j.uncertain_cid = None                       # never arrived: send the same attempt again (same id)
            t.next_attempt[j.leg] = max(t.next_attempt.get(j.leg, 1) - 1, 0)
        self._send_exit(now)

    def _exit_blockers(self, t: Trade) -> list[OrderView]:
        """Orders that must be gone before our own sell may go out (never oversell): the entry parent, its legs, and
        any stray open SCALP sell in the symbol (an exit sent before a restart, the leg of an older bracket)."""
        own = [x for x in ([t.parent_view] if t.parent_view is not None else []) + list(t.legs.values())
               if not is_done(x)]
        ids = {x.id for x in own}
        stray = [v for oid, v in self.linger_view.items() if oid in self.lingering and oid not in ids
                 and v.side == "sell" and v.symbol == t.symbol and not is_done(v)]
        return own + stray

    def _send_exit(self, now: pd.Timestamp) -> None:
        t = self.trade
        j = t.exit
        qty = int(math.floor(t.qty + 1e-9))
        if qty < 1:
            return
        attempt = t.next_attempt.get(j.leg, 0)
        q = self._fresh_quote(t.symbol)
        try:
            spec = O.exit_limit(t.symbol, qty, q, self._last_price(t.symbol), j.collars[j.idx], j.kind,
                                setup_id=t.setup_id, version=t.version, session_date=self.date,
                                bar_start=t.bar_start, leg=j.leg, attempt=attempt, reason=j.reason.value)
        except ValueError as e:
            self.request_kill(f"no price for the exit: {e}")
            return
        t.next_attempt[j.leg] = attempt + 1
        try:
            v = self.broker.submit(spec)
        except ExitDelayed:
            t.next_attempt[j.leg] = attempt
            return
        except BrokerReject as e:
            self.journal.write("exit_rejected", cid=spec.client_order_id, status=e.status, detail=str(e)[:200],
                               collar=j.collars[j.idx], **self._labels(t))
            j.idx += 1                                   # exits must get out: next collar on the next tick
            if j.idx >= len(j.collars):
                self.request_kill(f"{j.reason.value}: exit rejected at every collar")
            return
        except BrokerUnavailable:
            j.uncertain_cid, j.order_at = spec.client_order_id, now
            self.journal.write("exit_uncertain", cid=spec.client_order_id, **self._labels(t))
            return
        j.order_id, j.order_at, j.order_cancel_at = v.id, now, None
        t.sell_ids.add(v.id)
        self.journal.write("exit_order", cid=spec.client_order_id, qty=qty, limit=spec.limit_price,
                           collar=j.collars[j.idx], order_kind=j.kind.value, reason=j.reason.value, tags=spec.reason,
                           quote=_q(q), **self._labels(t))
        dq, px = self._book(v)
        if dq > 0:
            self._on_fill(now, v, dq, px, "protect" if j.kind is Kind.PROTECT else "exit")
            if t.qty <= 1e-9:
                self._close_trade(now, j.reason.value)

    # ================================================================================== kill switch (MT-G27)
    def _kill_step(self, now: pd.Timestamp) -> None:
        k = self.kill
        if k is None:
            return
        opens = self.broker.open_orders()
        kill_ids = {i["id"] for i in k.orders.values() if i.get("id")}
        asked = False
        for o in opens:
            if o.id in kill_ids or is_done(o):
                continue
            if o.id not in k.cancel_req or now - k.cancel_req[o.id] >= _sec(C.CANCEL_CONFIRM_S):
                k.cancel_req[o.id] = now
                self._cancel_quiet(o.id, f"KILL {k.reason}"[:80])
                asked = True
        if asked:
            opens = self.broker.open_orders()
        t = self.trade
        if t is not None and t.parent_id is not None:
            self._poll_trade(now)                     # book any fill that raced the cancels
            t = self.trade
        if t is not None:
            self._kill_book_sells(now, t, kill_ids)   # the trade's own exit orders may fill while being cancelled
        for sym, info in k.orders.items():
            if info.get("id") is None:
                continue
            v = self.broker.get_order(info["id"])
            info["view"] = v
            dq, px = self._book(v)
            if dq > 0:
                owner = t if t is not None and t.symbol == sym else None
                self._on_fill(now, v, dq, px, "kill", owner)
        positions = self.broker.positions()
        for p in positions:
            sym = p.symbol
            if p.qty < 0:
                if sym not in k.alerted:
                    k.alerted.add(sym)
                    self._alert(f"SHORT position {sym} {p.qty:g}: this bot only sells, a person must close it",
                                {"symbol": sym, "qty": p.qty})
                continue
            info = k.orders.get(sym)
            if info and info.get("id") and not is_done(info["view"]):
                if info.get("cancel_at") is None and now - info["at"] >= _sec(C.EXIT_ACK_S):
                    info["cancel_at"] = now
                    self._cancel_quiet(info["id"], "kill order not filled")
                elif info.get("cancel_at") is not None and now - info["cancel_at"] >= _sec(C.CANCEL_CONFIRM_S):
                    info["cancel_at"] = now
                    self._cancel_quiet(info["id"], "kill order not filled", repeat=True)
                continue
            if info and info.get("id"):
                v = info["view"]
                if v.filled_qty > 0 and now - as_ny(v.updated_at or info["at"]) < _sec(C.MISMATCH_MIN_GAP_S):
                    continue                           # it just filled: let the position catch up, never oversell
                if v.filled_qty < v.qty - 1e-9:
                    k.idx[sym] = k.idx.get(sym, 0) + 1   # the last kill order ended unfilled: one collar further
                info["id"] = None
            if info and info.get("cid") and info.get("id") is None and info.get("uncertain"):
                found = self.broker.get_by_client_id(info["cid"])
                info["uncertain"] = False
                if found is not None:
                    info.update(id=found.id, at=now, view=found, cancel_at=None)
                    continue
            others = [o for o in opens if o.symbol == sym and o.side == "sell" and o.id not in kill_ids
                      and not is_done(o)]
            if others:
                # wait for the legs' cancels: never oversell. If they never go, say so loudly (once): only a person
                # can close the position then (Alpaca dashboard)
                k.blocked_since.setdefault(sym, now)
                if now - k.blocked_since[sym] >= _sec(C.CANCEL_GIVE_UP_X * C.CANCEL_CONFIRM_S) and \
                        f"stuck:{sym}" not in k.alerted:
                    k.alerted.add(f"stuck:{sym}")
                    ids = [o.id for o in others]
                    self._alert(f"kill switch cannot sell {sym}: open sell order(s) {ids} will not cancel. Close the "
                                "position and those orders by hand in the Alpaca paper dashboard", {"orders": ids})
                continue
            k.blocked_since.pop(sym, None)
            if now < k.retry_at.get(sym, now):
                continue                               # the last kill order was rejected: wait EXIT_ACK_S
            qty = int(math.floor(p.qty + 1e-9))
            if qty < 1:
                continue
            i = min(k.idx.get(sym, 0), len(C.KILL_COLLARS) - 1)
            if k.idx.get(sym, 0) >= len(C.KILL_COLLARS) and f"collars:{sym}" not in k.alerted:
                k.alerted.add(f"collars:{sym}")
                self._alert(f"kill switch: {sym} not flat after every collar, still trying at the widest",
                            {"symbol": sym})
            try:
                spec = O.exit_limit(sym, qty, self._fresh_quote(sym), self._last_price(sym, p.avg_entry_price),
                                    C.KILL_COLLARS[i], Kind.EXIT, setup_id=None, version=0, session_date=self.date,
                                    bar_start=now.floor("min"), leg="K", attempt=self.kill_attempt % 1000,
                                    reason=f"KILL {k.reason}"[:80])
            except ValueError as e:
                self._alert(f"kill switch cannot price {sym}: {e}", {"symbol": sym})
                continue
            # the id carries the minute (HHMM), so the attempt number wraps at 1000 without ever repeating an id
            self.kill_attempt += 1
            try:
                v = self.broker.submit(spec)
            except ExitDelayed:
                self.kill_attempt -= 1                 # nothing reached the broker
                continue
            except BrokerReject as e:
                k.idx[sym] = k.idx.get(sym, 0) + 1
                k.retry_at[sym] = now + _sec(C.EXIT_ACK_S)
                self.journal.write("kill_order_rejected", cid=spec.client_order_id, status=e.status,
                                   detail=str(e)[:200])
                continue
            except BrokerUnavailable:
                k.orders[sym] = {"id": None, "cid": spec.client_order_id, "at": now, "uncertain": True}
                continue
            k.orders[sym] = {"id": v.id, "cid": spec.client_order_id, "at": now, "view": v, "cancel_at": None}
            self.journal.write("kill_order", cid=spec.client_order_id, symbol=sym, qty=qty, limit=spec.limit_price,
                               collar=C.KILL_COLLARS[i], tags=spec.reason)
            owner = t if t is not None and t.symbol == sym else None
            if owner is not None:
                owner.sell_ids.add(v.id)
            dq, px = self._book(v)
            if dq > 0:
                self._on_fill(now, v, dq, px, "kill", owner)
        t = self.trade
        if t is not None and t.qty <= 1e-9 and (t.parent_view is None or is_done(t.parent_view)):
            if t.entry_qty > 0:
                self._close_trade(now, f"kill: {k.reason}")
            else:
                self.trade = None
        if self.broker.positions() or self.broker.open_orders():
            return
        # Flat at the broker with nothing open. Every fill that got us here is booked BEFORE the trade is let go:
        # Alpaca acknowledges a marketable limit unfilled (pending_new) and fills it ~0.6 s later, so a kill (or
        # exit) order sent on THIS tick is filled by now without having been read. The broker was read as flat
        # first, so the fill is already visible on the orders read below.
        if self.trade is not None and not self._kill_settle(now, k):
            return                                     # our books still hold shares: look again next tick
        self.lingering.clear()
        self.kill, self.killed = None, True
        self._write_flag(self.halt_name, {"reason": k.reason, "ts": now.isoformat(), "by": "engine kill switch"})
        kf = self._file(self.kill_name)
        if kf is not None and kf.exists():
            try:
                kf.unlink()
            except OSError:
                pass
        self.journal.write("kill_done", reason=k.reason, seconds=(now - k.started).total_seconds())
        self._alert(f"kill switch done: flat, no open orders, HALT set ({k.reason})", {"reason": k.reason})

    def _kill_settle(self, now: pd.Timestamp, k: KillJob) -> bool:
        """The broker is flat: re-read every order that can have sold the trade's shares (the kill orders, the
        trade's own exit / protect orders, stray sells being cancelled, the parent and its legs), book each new fill
        (fill line, cost ledger, counters) and close the trade (`how = kill: ...`, trade_closed, realized and test
        honest P&L). True when the trade is settled. If our books still show shares that no order explains, wait
        MISMATCH_MIN_GAP_S for the views to catch up, then alert and let the trade go (the broker is flat; the next
        start rebuilds the P&L from the broker's history, MT-G40)."""
        t = self.trade
        if t is None:
            return True
        if t.parent_id is not None:
            self._safe(self._poll_trade, now)        # legs (take-profit / stop) keep their own roles
            t = self.trade
            if t is None:
                return True
        legs = {g.id for g in t.legs.values()}
        kill_ids = {i["id"] for i in k.orders.values() if i.get("id")}
        ids = (kill_ids | set(t.sell_ids) | {oid for oid, v in self.linger_view.items() if v.side == "sell"
                                             and v.symbol == t.symbol}) - legs
        for oid in sorted(ids):
            try:
                v = self.broker.get_order(oid)
            except (BrokerUnavailable, BrokerReject) as e:
                self.journal.write("broker_error", step="_kill_settle", order_id=oid, error=type(e).__name__,
                                   detail=str(e)[:200])
                continue
            if v.symbol != t.symbol or v.side != "sell":
                continue
            dq, px = self._book(v)
            if dq > 0:
                t.sell_ids.add(v.id)
                leg = (O.parse_client_id(v.client_order_id) or {}).get("leg")
                role = "kill" if oid in kill_ids or leg in ("K", "W") else "protect" if leg == "P" else "exit"
                self._on_fill(now, v, dq, px, role, t)
        if t.entry_qty <= 0:
            self.trade = None                           # never filled: nothing to book
            return True
        if t.qty <= 1e-9:
            self._close_trade(now, f"kill: {k.reason}")
            return True
        k.unbooked_since = k.unbooked_since or now
        if now - k.unbooked_since < _sec(C.MISMATCH_MIN_GAP_S):
            return False
        self.journal.write("trade_unbooked", symbol=t.symbol, qty=t.qty, sells_seen=sorted(t.sell_ids),
                           reason=k.reason, **self._labels(t))
        self._alert(f"kill switch: the broker is flat but {t.qty:g} {t.symbol} share(s) of the trade were sold by an "
                    "order the bot could not read: that exit is missing from today's journal (the next start "
                    "rebuilds the P&L from the broker's history)", {"symbol": t.symbol, "qty": t.qty})
        self.trade = None
        return True

    def _kill_book_sells(self, now: pd.Timestamp, t: Trade, kill_ids: set[str]) -> None:
        """MT-G16 / G40: every fill is booked. During a kill the exit path is paused, so the trade's own exit and
        protect orders (and a submit that timed out) are read here; a fill on one is booked to the trade, and the
        trade closes (how='kill: ...') once no shares are left. Legs are booked by _poll_trade, stray sells by
        _refresh, kill orders below."""
        j = t.exit
        if j is not None and j.uncertain_cid is not None:
            try:
                found = self.broker.get_by_client_id(j.uncertain_cid)
            except (BrokerUnavailable, BrokerReject):
                found = None                              # look again on the next tick
            if found is not None:
                j.order_id, j.order_at, j.uncertain_cid = found.id, now, None
                t.sell_ids.add(found.id)
        legs = {g.id for g in t.legs.values()}
        for oid in sorted(t.sell_ids - legs - kill_ids - set(self.lingering)):
            if oid in self._kill_read_done:
                continue
            try:
                v = self.broker.get_order(oid)
            except (BrokerUnavailable, BrokerReject) as e:   # one unreadable order must not stall the kill
                self.journal.write("broker_error", step="_kill_book_sells", order_id=oid, error=type(e).__name__,
                                   detail=str(e)[:200])
                continue
            dq, px = self._book(v)
            if dq > 0:
                leg = (O.parse_client_id(v.client_order_id) or {}).get("leg")
                self._on_fill(now, v, dq, px, "protect" if leg == "P" else "exit", t)
            if is_done(v):
                self._kill_read_done.add(oid)

    # ================================================================================== reconcile (MT-G26)
    def _expected(self) -> tuple[dict[str, float], set[str]]:
        t = self.trade
        pos: dict[str, float] = {}
        ids: set[str] = set(self.lingering)
        if t is not None:
            if t.qty > 1e-9:
                pos[t.symbol] = t.qty
            if t.parent_id:
                ids.add(t.parent_id)
            ids.update(g.id for g in t.legs.values())
            ids.update(t.sell_ids)
            if t.exit is not None and t.exit.order_id:
                ids.add(t.exit.order_id)
        if self.kill is not None:
            ids.update(i["id"] for i in self.kill.orders.values() if i.get("id"))
        return pos, ids

    def _reconcile(self, now: pd.Timestamp, force: bool = False) -> list[str]:
        """Unexplained mismatches right now (and trip the kill when one holds on 2 checks >= 3 s apart)."""
        if not force and self.next_reconcile is not None and now < self.next_reconcile:
            return sorted(self.mm)
        try:
            positions = self.broker.positions()
            opens = self.broker.open_orders()
        except (BrokerUnavailable, BrokerReject) as e:
            self.journal.write("reconcile_unavailable", detail=str(e)[:200])
            self.next_reconcile = now + _sec(C.RECONCILE_EVERY_S)
            return ["UNAVAILABLE"] if force else sorted(self.mm)
        exp_pos, exp_ids = self._expected()
        have = {p.symbol: float(p.qty) for p in positions if abs(p.qty) > 1e-9}
        buy_left: dict[str, float] = {}
        sell_left: dict[str, float] = {}
        for o in opens:
            if o.id in exp_ids and not is_done(o):
                d = buy_left if o.side == "buy" else sell_left
                d[o.symbol] = d.get(o.symbol, 0.0) + remaining(o)
        found: dict[str, str] = {}
        for sym in sorted(set(have) | set(exp_pos)):
            diff = have.get(sym, 0.0) - exp_pos.get(sym, 0.0)
            if abs(diff) <= 1e-9:
                continue
            if (diff > 0 and buy_left.get(sym, 0.0) >= diff - 1e-9) or \
                    (diff < 0 and sell_left.get(sym, 0.0) >= -diff - 1e-9):
                continue                                # explained by an order in flight
            found[f"position:{sym}"] = f"broker {have.get(sym, 0.0):g} vs expected {exp_pos.get(sym, 0.0):g}"
        for o in opens:
            if o.id not in exp_ids and not is_done(o):
                found[f"order:{o.id}"] = f"{o.client_order_id} {o.symbol} {o.side} {o.qty:g} {o.status}"
        for key in list(self.mm):
            if key not in found:
                self.journal.write("reconcile_cleared", key=key)
                del self.mm[key]
        trip = []
        for key, detail in found.items():
            if key not in self.mm:
                self.mm[key] = [now, 1, detail]
                self.journal.write("reconcile_mismatch", key=key, detail=detail, check=1)
            else:
                rec = self.mm[key]
                rec[1] += 1
                rec[2] = detail
                if rec[1] >= C.MISMATCH_CONFIRM_CHECKS and now - rec[0] >= _sec(C.MISMATCH_MIN_GAP_S):
                    trip.append(key)
        busy = self.trade is not None or bool(self.lingering) or bool(have) or bool(opens)
        nxt = now + _sec(C.RECONCILE_EVERY_S if busy else C.RECONCILE_IDLE_EVERY_S)
        for rec in self.mm.values():
            nxt = min(nxt, max(rec[0] + _sec(C.MISMATCH_MIN_GAP_S), now + _sec(1)))
        self.next_reconcile = nxt
        if trip:
            self.flags.add(Reason.RECONCILE_MISMATCH)
            self.journal.write("reconcile_halt", keys=trip, details=[self.mm[k][2] for k in trip])
            self.request_kill(Reason.RECONCILE_MISMATCH)
        return sorted(found)

    # ================================================================================== clock, daily stop, stops
    def _clock_rules(self, now: pd.Timestamp) -> None:
        st, t = self.session, self.trade
        # the 15:55 kill first and on its own: nothing in the flatten step below may keep it from firing (MT-G20)
        if now >= st.kill_at and (self.trade is not None or self.lingering):
            self.request_kill(Reason.OPEN_AT_KILL_TIME)
            return
        if now >= st.flatten_at and t is not None:
            if t.state is SlotState.ENTRY_PENDING and t.cancel_requested_at is None:
                self._cancel_entry(now, Reason.TIME_EXIT)
            t = self.trade
            if t is not None and t.qty > 1e-9 and t.exit is None:
                self._start_exit(Reason.TIME_EXIT, Kind.EXIT, now)

    def _unrealized(self) -> float:
        """Honest P&L of the open trade (sold part + the rest marked at the bid, MT-G4). 0 when flat."""
        t = self.trade
        if t is None or t.qty <= 1e-9:
            return 0.0
        mark = self._mark(t.symbol)
        if mark is None:
            return 0.0
        return self._pnl(t.buys, t.sells + [(t.qty, mark)])["honest_pnl"]

    def _daily_stop(self, now: pd.Timestamp) -> None:
        c = self.counters
        unreal = self._unrealized()
        limit = risk.daily_limit(c.e0)
        if not c.daily_stopped and c.realized_honest + unreal <= -limit + 1e-9:
            c.daily_stopped = True
            self._write_flag(self.daily_stop_name, {"ts": now.isoformat(), "realized_honest": c.realized_honest,
                                            "unrealized_honest": unreal, "limit": limit})
            self.journal.write("daily_stop", realized_honest=c.realized_honest, unrealized_honest=unreal,
                               limit=limit, e0=c.e0)
            self._alert(f"daily stop: honest P&L {c.realized_honest + unreal:.2f} <= -{limit:.2f}", {"limit": limit})
        if c.daily_stopped and self.trade is not None:
            t = self.trade
            if t.state is SlotState.ENTRY_PENDING and t.cancel_requested_at is None:
                self._cancel_entry(now, Reason.DAILY_STOP)
            t = self.trade
            if t is not None and t.qty > 1e-9 and t.exit is None:
                self._start_exit(Reason.DAILY_STOP, Kind.EXIT, now)
        test_now = c.test_honest + unreal
        if not self.dd_halted and max(c.test_peak, 0.0) - test_now >= C.DRAWDOWN_HALT_PCT * c.e0 - 1e-9:
            self.dd_halted = True
            self.flags.add(Reason.HALTED_MANUAL)
            self._write_flag(self.halt_name, {"reason": Reason.DRAWDOWN_HALT.value, "ts": now.isoformat(),
                                      "by": "engine drawdown"})
            self._alert("5% drawdown from the test's high-water mark: HALT (a person must reset it)",
                        {"test_honest": test_now, "peak": c.test_peak})

    def _stop_watchdog(self, now: pd.Timestamp, dt: float) -> None:
        t = self.trade
        if t is None or t.state is not SlotState.OPEN or t.exit is not None or t.qty <= 1e-9 or t.stop_limit is None:
            return
        sl = t.legs.get("sl")
        if sl is not None and sl.status == "filled":
            return
        if self.halted.get(t.symbol) is True:
            if t.below_since is not None:
                t.below_since += _sec(dt)                # a halt pauses the count (MT-G21)
            return
        px = self._mark(t.symbol)
        if px is None or px >= t.stop_limit:
            t.below_since = None
            return
        if t.below_since is None:
            t.below_since = now
            self.journal.write("stop_watchdog", phase="below_stop_limit", price=px, stop_limit=t.stop_limit,
                               **self._labels(t))
        if now - t.below_since >= _sec(C.STOP_WATCHDOG_S):
            self._start_exit(Reason.STOP_ESCALATION, Kind.PROTECT, now)

    # ================================================================================== signals and entries
    def _day(self, sym: str) -> sg.Day | None:
        bars = self.bars.get(sym) or []
        if not bars:
            return None
        o = self.session.open
        close_min = int((self.session.close - o).total_seconds() // 60)
        m = np.array([int((as_ny(b.start) - o).total_seconds() // 60) for b in bars], dtype=int)
        f = lambda a: np.array([getattr(b, a) for b in bars], dtype=float)  # noqa: E731
        return sg.Day(self.date, o, close_min, m, f("open"), f("high"), f("low"), f("close"), f("volume"))

    def _signals(self, now: pd.Timestamp) -> list[Decision]:
        out: list[Decision] = []
        for sym in [s for s in C.ALLOWED_SYMBOLS if s in self.new_bar_syms]:
            regs = self.registry.for_symbol(sym)
            day = self._day(sym) if regs else None
            if day is None:
                continue
            latest = int(day.m[-1])
            # bars that arrived late, together with a newer one (a backfill, IEX publishing late): their intents are
            # not dropped silently. A late exit still goes out (never gated); a late entry is refused BAR_STALE. On
            # the first delivery (a start or restart backfill) only bars that ended in the last 2 x BAR_MAX_AGE_S
            # count as late; older ones are history the previous process decided on.
            prev = self.prev_last_bar.get(sym)
            prev_m = None if prev is None else int((prev - self.session.open).total_seconds() // 60)
            recent = now - _sec(2 * C.BAR_MAX_AGE_S)
            ctx = self.ctx.get(sym) or sg.Ctx()
            exits, entries, stale = [], [], []
            for reg in regs:
                t = self.trade
                owns = t is not None and t.setup_id == reg.setup_id and t.symbol == sym and t.qty > 1e-9
                live = sg.Live(side=1 if owns else 0, entries=self.entries_by_setup.get(reg.setup_id, 0),
                               exiting=bool(owns and t.exit is not None))
                try:
                    intents = sg.SETUPS[reg.setup_id].fn(day, ctx, live=live)
                except Exception as e:  # noqa: BLE001 - a setup bug must not stop exits or the kill switch
                    self.journal.write("signal_error", error=f"{type(e).__name__}: {str(e)[:200]}", symbol=sym,
                                       **reg.labels())
                    continue
                for it in intents:
                    m = int(it.m)
                    late = m < latest and ((prev_m is not None and m > prev_m) or
                                           (prev_m is None and day.ts(m) + pd.Timedelta(minutes=1) >= recent))
                    if m != latest and not late:
                        continue
                    c = Candidate(reg.setup_id, reg.version, sym, it.action, int(it.side), day.ts(m),
                                  stop=it.stop, stop_dist=it.stop_dist, target=it.target, target_r=it.target_r,
                                  target_dist=it.target_dist, reason=it.reason)
                    if it.action == "exit":
                        exits.append((c, reg))
                    elif late:
                        stale.append((c, reg, latest - m))
                    else:
                        entries.append((c, reg))
            for c, reg in exits:
                d = self._safe(self._exit_candidate, now, c, reg)
                out.append(d if d is not None else Decision(c, True, (Reason.SETUP_EXIT,), None,
                                                            {"broker_error": True}))
            for c, reg, n in stale:
                d = Decision(c, False, (Reason.BAR_STALE,), None, {"shadow": True, "missed": True,
                                                                   "late_by_bars": n})
                self._journal_decision(d, reg)
                out.append(d)
            for c, reg in entries:
                d = self._safe(self._entry_candidate, now, c, reg)
                out.append(d if d is not None else Decision(c, False, (Reason.ORDER_STATE_UNCERTAIN,), None,
                                                            {"broker_error": True}))
        return out

    def _exit_candidate(self, now: pd.Timestamp, c: Candidate, reg: Any) -> Decision:
        t = self.trade
        if t is not None and t.setup_id == c.setup_id and t.symbol == c.symbol and t.qty > 1e-9:
            d = Decision(c, True, (Reason.SETUP_EXIT,), None, {"setup_reason": c.reason})
            self._journal_decision(d, reg)
            if t.exit is None and self.kill is None:
                self._start_exit(Reason.SETUP_EXIT, Kind.EXIT, now)
            return d
        d = Decision(c, False, (), None, {"ignored": "this setup holds no position"})
        self._journal_decision(d, reg)
        return d

    def _buying_power(self) -> tuple[float, dict[str, Any]]:
        try:
            a = self.broker.account()
            return float(a.non_marginable_buying_power), {}
        except (BrokerUnavailable, BrokerReject) as e:
            return 0.0, {"account": f"unavailable: {str(e)[:100]}"}

    def _entry_candidate(self, now: pd.Timestamp, c: Candidate, reg: Any) -> Decision:
        cnt, t = self.counters, self.trade
        q = self.quotes.get(c.symbol)
        spec, reasons, info = O.entry_bracket(c, reg, q, cnt.e0, self.date, 0)
        notes: dict[str, Any] = {"numbers": info}
        planned = spec.qty * spec.limit_price if spec is not None else float(info.get("notional") or 0.0)
        bp, extra = self._buying_power()
        notes.update(extra)
        ctx = self.ctx.get(c.symbol)
        spy_ctx = self.ctx.get("SPY")
        spy_lt = self.last_trades.get("SPY")
        spy_q = self.quotes.get("SPY")
        flags = set(self.flags) | ({Reason.KILLED} if self.killed or self.kill is not None else set())
        ec = risk.EntryContext(
            now=now, candidate=c, reg=reg, counters=cnt, session=self.session, events=self.events, quote=q,
            last_trade=self.last_trades.get(c.symbol), recent_bars=list(self.bars.get(c.symbol) or []),
            last_data_ok=self.last_data_ok, clock_offset_ms=self.clock_offset_ms, halted=self.halted.get(c.symbol),
            prior_close=self._prior_close(ctx), slot_state=self.slot_state,
            open_parents=1 if t is not None and t.parent_view is not None and not is_done(t.parent_view) else 0,
            open_position=t is not None and t.qty > 1e-9, flags=frozenset(flags),
            unrealized_honest=self._unrealized(), settled_cash=risk.settled_cash(cnt), broker_nonmarginable_bp=bp,
            gross_notional_open=(t.qty * (self._mark(t.symbol) or 0.0)) if t is not None else 0.0,
            planned_notional=planned, open_symbol=t.symbol if t is not None and t.qty > 1e-9 else None,
            spy_price=spy_lt.price if spy_lt else (spy_q.bid if spy_q is not None else None),
            spy_prior_close=self._prior_close(spy_ctx))
        rr, rnotes = risk.entry_check(ec)
        notes.update(rnotes)
        for r in rr:
            if r not in reasons:
                reasons.append(r)
        if t is not None and Reason.POSITION_OPEN not in reasons:
            reasons.append(Reason.POSITION_OPEN)          # one slot, whatever the gate says (MT-G2)
        if not reasons and spec is not None:
            keys = self._reconcile(now, force=True)
            if keys:
                reasons.append(Reason.RECONCILE_MISMATCH if keys != ["UNAVAILABLE"] else Reason.ORDER_STATE_UNCERTAIN)
                notes["reconcile"] = keys
        if reasons or spec is None:
            d = Decision(c, False, tuple(reasons), None, {**notes, "shadow": True})
            self._journal_decision(d, reg)
            return d
        return self._submit_entry(now, c, reg, spec, info, notes)

    def _prior_close(self, ctx: Any) -> float | None:
        if ctx is None:
            return None
        v = ctx.prev_close_auction if getattr(ctx, "prev_close_auction", None) is not None else ctx.prev_close
        return None if v is None else float(v)

    def _submit_entry(self, now: pd.Timestamp, c: Candidate, reg: Any, spec: OrderSpec, info: dict[str, Any],
                      notes: dict[str, Any]) -> Decision:
        cnt = self.counters
        q = self.quotes.get(c.symbol)
        d = Decision(c, True, (), spec, notes)
        self._journal_decision(d, reg)
        try:
            v = self.broker.submit(spec)
        except RunawayOrders as e:
            self.journal.write("runaway_orders", cid=spec.client_order_id, detail=str(e)[:300], **reg.labels())
            self.request_kill(f"RUNAWAY_ORDERS: {e}")
            self._safe(self._kill_step, now)
            return Decision(c, False, (Reason.KILLED,), spec, {**notes, "runaway": str(e)})
        except BrokerReject as e:
            self._count_submit(now, c)
            cnt.blocked_symbols.add(c.symbol)            # never retried; entries in this symbol stop today
            self._save_blocked(now, spec, c, e.status)   # ... even after a restart (MT-G40)
            self.journal.write("broker_reject", cid=spec.client_order_id, status=e.status, code=e.code,
                               detail=str(e)[:300], symbol=c.symbol, **reg.labels())
            self._alert(f"broker rejected the {c.symbol} entry ({e.status}): {c.symbol} entries blocked today",
                        {"status": e.status})
            return Decision(c, False, (Reason.SYMBOL_BLOCKED_BROKER_REJECT,), spec, {**notes, "reject": str(e)[:200]})
        except BrokerUnavailable as e:
            self._count_submit(now, c)
            self.journal.write("submit_uncertain", cid=spec.client_order_id, detail=str(e)[:200], **reg.labels())
            try:
                v = self.broker.get_by_client_id(spec.client_order_id)
            except (BrokerUnavailable, BrokerReject):
                v = None
            self.trade = Trade(c.setup_id, reg.version, c.symbol, reg, c.bar_start, SlotState.ENTRY_PENDING,
                               spec=spec, candidate=c, parent_cid=spec.client_order_id, submitted_at=now,
                               stop=spec.stop_price, stop_limit=spec.stop_limit_price, target=spec.take_profit,
                               decision_quote=_q(q), submit_quote=_q(q), info=info,
                               uncertain_since=None if v is not None else now)
            if v is None:
                return Decision(c, True, (Reason.ORDER_STATE_UNCERTAIN,), spec, notes)
        else:
            self._count_submit(now, c)
            self.trade = Trade(c.setup_id, reg.version, c.symbol, reg, c.bar_start, SlotState.ENTRY_PENDING,
                               spec=spec, candidate=c, parent_cid=spec.client_order_id, submitted_at=now,
                               stop=spec.stop_price, stop_limit=spec.stop_limit_price, target=spec.take_profit,
                               decision_quote=_q(q), submit_quote=_q(q), info=info)
        t = self.trade
        t.parent_id = v.id
        self.next_reconcile = now                        # busy now: reconcile on the next tick, then every 5 s
        self.journal.write("submit" if self.mode is Mode.PAPER else "would_submit", cid=spec.client_order_id,
                           symbol=c.symbol, qty=spec.qty, limit=spec.limit_price, stop=spec.stop_price,
                           stop_limit=spec.stop_limit_price, target=spec.take_profit, quote=_q(q), numbers=info,
                           **reg.labels())
        self._take_parent(now, v)
        self._safe(self._advance, now)
        return d

    def _count_submit(self, now: pd.Timestamp, c: Candidate) -> None:
        cnt = self.counters
        cnt.entry_submits += 1
        cnt.entry_submit_times.append(now)
        self.entries_by_setup[c.setup_id] = self.entries_by_setup.get(c.setup_id, 0) + 1

    def _journal_decision(self, d: Decision, reg: Any) -> None:
        c = d.candidate
        self.journal.write("decision", symbol=c.symbol, action=c.action, side=c.side, bar_start=c.bar_start,
                           setup_reason=c.reason, accepted=d.accepted, reasons=[r.value for r in d.reasons],
                           order=d.order, notes=d.notes, shadow=bool(d.notes.get("shadow")) if d.notes else False,
                           slot=self.slot_state.value, **(reg.labels() if reg is not None else
                                                          {"setup_id": c.setup_id, "version": c.version}))
