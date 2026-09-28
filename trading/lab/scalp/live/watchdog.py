"""Outside heartbeat watchdog and the stand-alone kill switch (MT-G39, MT-G27).

The watchdog is a SEPARATE OS process (the runner starts it with start_new_session=True, or run it yourself:
`python -m lab.scalp.live watchdog --mode paper`). Every WATCHDOG_EVERY_S (15 s) during market hours it checks:
- the bot's heartbeat (state/scalp/heartbeat-<mode>.json, its own mode's only) is more than HEARTBEAT_STALE_S (30 s)
  old or missing, or
- it is at or after watchdog_flat_at (15:57 on a normal day) and a position is open.
Either one -> cancel every open order (and wait for the cancels to be confirmed), flatten every long position with
sell limits at KILL_COLLARS (0.2%, 0.5%, 1% under the bid, escalating), write HALT, journal and alert. In PAPER mode
it uses its own read/write broker on the ALPACA_SCALP paper account (never any other keys). In DRY mode the
simulated position lives inside the bot, so it only journals `would_flatten`.

`kill_command` is what `python -m lab.scalp.live kill --reason ...` runs: it writes the KILL flag (the running engine
acts on it at its next tick), and if no fresh PAPER heartbeat shows a running paper bot, it performs the kill itself
with the same flatten routine. Both take the broker lock with a deadline (LOCK_WAIT_S): a bot hung inside an order
call must not hang its own backstop, so after the deadline they go on without the lock and journal it. Exits go
out whatever the data or the entry caps say (MT-G38); only limit orders are used (MT-G21), priced off the latest
quote, or off the position's average price with a wider collar when there is none.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from . import config as C
from . import orders as O
from . import state as S
from .clock import SessionTimes
from .model import NY, BrokerReject, BrokerUnavailable, Kind, Mode, Quote, Reason, as_ny

POLL_S = 0.5


def now_ny() -> pd.Timestamp:
    return pd.Timestamp.now(tz=NY)


# ------------------------------------------------------------------------------------------ session times
def session_times(state_dir: str | Path | None, d: date) -> SessionTimes:
    """Today's session from the runner's session file, else the cached exchange calendar, else 09:30-16:00.
    (With no calendar a half day would be treated as a full day: the bot itself refuses half days.)"""
    info = S.read_session(state_dir, d) or {}
    if info.get("open") and info.get("close"):
        return SessionTimes.from_calendar(d, as_ny(info["open"]), as_ny(info["close"]))
    try:
        from .. import data as dt
        cal = dt.load_calendar()
        row = cal[cal["date"] == d]
        if not row.empty:
            return SessionTimes.from_calendar(d, row["open"].iloc[0], row["close"].iloc[0])
    except (OSError, ValueError, KeyError):
        pass
    return SessionTimes.from_calendar(d, as_ny(pd.Timestamp(f"{d} 09:30")), as_ny(pd.Timestamp(f"{d} 16:00")))


def watchdog_reasons(now: pd.Timestamp, st: SessionTimes, hb_age_s: float | None, position_open: bool
                     ) -> list[Reason]:
    """Why the watchdog must flatten now ([] = all good). Only during the session."""
    now = as_ny(now)
    if not st.is_open(now):
        return []
    out = []
    if hb_age_s is None or hb_age_s > C.HEARTBEAT_STALE_S:
        out.append(Reason.HEARTBEAT_STALE)
    if now >= st.watchdog_flat_at and position_open:
        out.append(Reason.OPEN_AT_KILL_TIME)
    return out


# ------------------------------------------------------------------------------------------ flatten
def _open_ids(broker: Any) -> list[str]:
    ids = []
    for o in broker.open_orders():
        for x in (o, *o.legs):
            if x.open and x.id not in ids:
                ids.append(x.id)
    return ids


def cancel_all(broker: Any, clock: Callable[[], pd.Timestamp], sleep: Callable[[float], None]) -> bool:
    """Cancel every open order and wait (up to CANCEL_CONFIRM_S) until the broker shows none. A cancel request is
    not a cancel: True only once the broker confirms."""
    ids = _open_ids(broker)
    for oid in ids:
        try:
            broker.cancel(oid)
        except (BrokerReject, BrokerUnavailable):
            pass           # already done, or unknown: the confirmation below decides
    t0 = as_ny(clock())
    while True:
        if not _open_ids(broker):
            return True
        if (as_ny(clock()) - t0).total_seconds() >= C.CANCEL_CONFIRM_S:
            return False
        sleep(POLL_S)


def _wait_fill(broker: Any, order_id: str, clock: Callable[[], pd.Timestamp], sleep: Callable[[float], None]):
    t0 = as_ny(clock())
    while True:
        o = broker.get_order(order_id)
        if o.status == "filled" or not o.open:
            return o
        if (as_ny(clock()) - t0).total_seconds() >= C.EXIT_ACK_S:
            return o
        sleep(POLL_S)


@dataclass
class FlattenResult:
    cancelled: bool = True
    orders: list[str] = field(default_factory=list)
    flat: bool = False
    problems: list[str] = field(default_factory=list)


def flatten_all(broker: Any, clock: Callable[[], pd.Timestamp], session_date: date, reason: str, leg: str = "W",
                quote_fn: Callable[[str], Quote | None] | None = None,
                sleep: Callable[[float], None] = time.sleep) -> FlattenResult:
    """Kill-switch flatten: cancel all open orders (confirmed), then sell every long position with limit orders at
    KILL_COLLARS, escalating after EXIT_ACK_S without a fill. Leg W (watchdog) or K (kill switch)."""
    res = FlattenResult(cancelled=cancel_all(broker, clock, sleep))
    now0 = as_ny(clock())
    base = int(now0.second) * len(C.KILL_COLLARS)      # unique attempt numbers within this minute
    for p in broker.positions():
        if p.qty == 0:
            continue
        if p.qty < 0:
            res.problems.append(f"{p.symbol}: short {p.qty} found; the bot has no buy-to-cover path, close by hand")
            continue
        remaining = int(p.qty)
        for i, collar in enumerate(C.KILL_COLLARS):
            if remaining < 1:
                break
            q = None
            if quote_fn is not None:
                try:
                    q = quote_fn(p.symbol)
                except Exception:  # noqa: BLE001 - no quote: price off the position with a wider collar
                    q = None
            spec = O.exit_limit(p.symbol, remaining, q, p.avg_entry_price, collar, Kind.EXIT, setup_id=None,
                                version=0, session_date=session_date, bar_start=now0.floor("min"), leg=leg,
                                attempt=base + i, reason=reason)
            try:
                view = broker.submit(spec)
            except (BrokerReject, BrokerUnavailable) as e:
                res.problems.append(f"{p.symbol}: {type(e).__name__} {e}")
                continue
            res.orders.append(spec.client_order_id)
            o = _wait_fill(broker, view.id, clock, sleep)
            if o.open:
                cancel_all(broker, clock, sleep)
                o = broker.get_order(view.id)
            remaining -= int(o.filled_qty or 0)
    left = [p for p in broker.positions() if p.qty != 0]
    res.flat = not left and not _open_ids(broker)
    if left:
        res.problems.append("still open: " + ", ".join(f"{p.symbol} {p.qty:g}" for p in left))
    return res


def order_lock(broker: Any, state_dir: str | Path | None, wait_s: float | None = C.LOCK_WAIT_S) -> Any:
    """The broker's own lock when it has one (AlpacaBroker.lock() is re-entrant, so its submits inside do not
    deadlock), else the shared state/scalp/broker.lock. Yields True when held, False when `wait_s` passed first."""
    fn = getattr(broker, "lock", None)
    return fn(wait_s=wait_s) if callable(fn) else S.broker_lock(state_dir, wait_s=wait_s)


# ------------------------------------------------------------------------------------------ the watchdog
class Watchdog:
    """One `check()` per WATCHDOG_EVERY_S. `broker` is the SCALP paper broker in PAPER mode (None in DRY mode, where
    positions are read from the bot's heartbeat)."""

    def __init__(self, mode: Mode | str, state_dir: str | Path | None, clock: Callable[[], pd.Timestamp],
                 journal: Any, broker: Any = None, quote_fn: Callable[[str], Quote | None] | None = None,
                 sleep: Callable[[float], None] = time.sleep, session: SessionTimes | None = None,
                 lock_wait_s: float = C.LOCK_WAIT_S):
        self.mode, self.state_dir, self.clock, self.journal = Mode(mode), state_dir, clock, journal
        self.broker, self.quote_fn, self.sleep, self.session = broker, quote_fn, sleep, session
        self.lock_wait_s = lock_wait_s
        if self.mode is Mode.PAPER and broker is None:
            raise ValueError("the PAPER watchdog needs its own SCALP paper broker")
        self.acted = False

    def _session(self, now: pd.Timestamp) -> SessionTimes:
        if self.session is None or self.session.date != now.date():
            self.session = session_times(self.state_dir, now.date())
        return self.session

    def _positions_open(self) -> bool:
        if self.broker is not None:
            return any(p.qty != 0 for p in self.broker.positions())
        st = (S.read_heartbeat(self.state_dir, self.mode) or {}).get("status") or {}
        return bool(st.get("position") or st.get("positions"))

    def check(self) -> dict[str, Any]:
        now = as_ny(self.clock())
        st = self._session(now)
        if not st.is_open(now):
            return {"action": "idle", "reasons": []}
        age = S.heartbeat_age_s(self.state_dir, now, self.mode)
        pos = self._positions_open()
        reasons = watchdog_reasons(now, st, age, pos)
        if not reasons:
            return {"action": "none", "reasons": [], "heartbeat_age_s": age}
        orders_open = bool(self.broker is not None and _open_ids(self.broker))
        if self.acted and not pos and not orders_open:
            return {"action": "none", "reasons": [r.value for r in reasons], "note": "already flat"}
        stopped = ((S.read_heartbeat(self.state_dir, self.mode) or {}).get("status") or {}).get("stopped")
        if stopped and reasons == [Reason.HEARTBEAT_STALE] and not pos and not orders_open:
            return {"action": "none", "reasons": [], "note": f"bot stopped ({stopped}); account flat"}
        why = "+".join(r.value for r in reasons)
        if self.mode is not Mode.PAPER:
            self.journal.write("would_flatten", reasons=reasons, heartbeat_age_s=age, position_open=pos,
                               note="DRY: the simulated position lives in the bot; nothing sent")
            self.acted = True
            return {"action": "would_flatten", "reasons": [r.value for r in reasons]}
        with order_lock(self.broker, self.state_dir, self.lock_wait_s) as locked:
            if not locked:
                self.journal.write("lock_not_acquired", waited_s=self.lock_wait_s,
                                   note="the bot holds the broker lock (hung?): flattening without it")
            res = flatten_all(self.broker, self.clock, now.date(), why, "W", self.quote_fn, self.sleep)
        S.write_flag(self.state_dir, S.HALT, f"watchdog: {why}", now, "watchdog")
        self.journal.write("watchdog_flatten", reasons=reasons, heartbeat_age_s=age, orders=res.orders,
                           flat=res.flat, cancelled=res.cancelled, problems=res.problems)
        S.alert(self.state_dir, now, f"watchdog flattened the SCALP paper account ({why}); flat={res.flat}. "
                                     f"HALT is set: run `reset-halt --reason ...` after checking.",
                problems=res.problems)
        self.acted = True
        return {"action": "flatten", "reasons": [r.value for r in reasons], "flat": res.flat}


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def run_watchdog(wd: Watchdog, parent_pid: int | None = None, max_checks: int | None = None) -> int:
    """Check every WATCHDOG_EVERY_S until the session is over (close + 5 min) or `max_checks` is reached. It keeps
    running if the bot dies (that is its job) and stops early only when the bot is gone and the day is over."""
    n = 0
    while max_checks is None or n < max_checks:
        n += 1
        try:
            wd.check()
        except Exception as e:  # noqa: BLE001 - the watchdog must not die of one bad check
            now = as_ny(wd.clock())
            wd.journal.write("watchdog_error", error=f"{type(e).__name__}: {e}")
            S.alert(wd.state_dir, now, f"watchdog check failed: {type(e).__name__}: {e}")
        now = as_ny(wd.clock())
        st = wd._session(now)
        if now > st.close + pd.Timedelta(minutes=5) and not _pid_alive(parent_pid):
            break
        if now > st.close + pd.Timedelta(minutes=30):
            break
        wd.sleep(C.WATCHDOG_EVERY_S)
    return 0


# ------------------------------------------------------------------------------------------ kill command
def kill_command(reason: str, state_dir: str | Path | None, clock: Callable[[], pd.Timestamp],
                 broker_factory: Callable[[], Any], journal: Any,
                 quote_fn: Callable[[str], Quote | None] | None = None,
                 sleep: Callable[[float], None] = time.sleep, out: Callable[[str], None] = print,
                 lock_wait_s: float = C.LOCK_WAIT_S) -> dict[str, Any]:
    """Write KILL; if no PAPER bot heartbeat is fresh, cancel and flatten the SCALP paper account here and write
    HALT. (A running dry bot does not count: it holds no paper position.)"""
    if not str(reason or "").strip():
        raise ValueError("kill needs a reason")
    now = as_ny(clock())
    S.write_flag(state_dir, S.KILL, reason, now, "kill command")
    age = S.heartbeat_age_s(state_dir, now, Mode.PAPER)
    fresh = age is not None and age <= C.HEARTBEAT_STALE_S
    journal.write("kill_command", reason=reason, heartbeat_age_s=age, bot_running=fresh)
    if fresh:
        out(f"KILL written. The bot's heartbeat is {age:.0f} s old, so the bot will cancel and flatten at its next "
            f"tick and set HALT.")
        return {"acted": False, "heartbeat_age_s": age}
    out("KILL written. No running bot (no fresh heartbeat): cancelling and flattening the SCALP paper account now.")
    broker = broker_factory()
    with order_lock(broker, state_dir, lock_wait_s) as locked:
        if not locked:
            journal.write("lock_not_acquired", waited_s=lock_wait_s, note="flattening without the broker lock")
            out(f"The broker lock was busy for {lock_wait_s:g} s (a hung bot?): flattening without it.")
        res = flatten_all(broker, clock, now.date(), f"KILL: {reason}", "K", quote_fn, sleep)
    S.write_flag(state_dir, S.HALT, f"kill: {reason}", now, "kill command")
    journal.write("kill_flatten", reason=reason, orders=res.orders, flat=res.flat, cancelled=res.cancelled,
                  problems=res.problems)
    S.alert(state_dir, now, f"kill switch ran ({reason}); flat={res.flat}", problems=res.problems)
    out(f"Done: flat={res.flat}, orders sent={len(res.orders)}." + (f" Problems: {res.problems}" if res.problems
                                                                      else ""))
    return {"acted": True, "flat": res.flat, "orders": res.orders, "problems": res.problems}
