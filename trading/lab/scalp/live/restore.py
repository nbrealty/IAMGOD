"""Restart-safe state (MT-G40): rebuild today's counters and the open slot from the broker's own history.

A crash or restart must not reset the limits. Nothing here trusts a local file: `rebuild()` reads every SCALP-
order since the week (or the test) started and recomputes
- today's entry submissions and their times (MT-G2 8 a day, MT-G25 6 a minute), round trips (an entry with any
  fill) in total and per setup;
- closed trades, paired first-in-first-out per symbol (entry parent fills against take-profit / stop-loss leg
  fills and our own exit, protect, kill and watchdog sells), each with paper and honest P&L (MT-G4, fees by date);
- today's realized paper / honest P&L, the week's and the whole test's honest P&L and the test's high-water mark
  (MT-G18), the loss streak and its 30-minute pause (MT-G19), the 15-minute stop-out timers (MT-G17: a stop-leg
  fill or a protect sell is a stop-out), today's notional and buy notional (MT-G25, MT-G15);
- test sessions = distinct session dates with any SCALP order since `test_start`;
- MT-G4: a trade closed by a take-profit leg (a resting limit) is PENDING_VERIFY: the gates count it as at most 0
  and it does not reset the loss streak, exactly as the engine does;
- MT-G15: our own day trades (a lot bought and sold on the same session) over the last 5 sessions.
Each closed trade carries its R (honest P&L / (qty x (entry limit - stop-limit))) for the MT-G12 switch-off, which
keeps PENDING_VERIFY trades out of its resolved R series until the MT-G4 re-mark resolves them (runner.lane_history,
gates.lane_check_pending), and its entry's client id (parent_cid) to find those resolutions.
E0 is passed in (Alpaca `last_equity`, stored once per session by the runner), never recomputed here.

`AdoptedState` tells the engine what is live right now: an open SCALP position with a live stop leg is adopted
(slot OPEN); a position without one is flattened on the first tick (UNPROTECTED_POSITION); an unfilled SCALP entry
parent is cancelled (ORDER_STATE_UNCERTAIN); stray open SCALP orders (old exits, legs of closed trades) are
cancelled. A position no SCALP order explains is left to reconcile (MT-G26), which halts on it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from . import config as C
from . import costs
from . import orders as O
from .broker import is_done, remaining
from .model import NY, DayCounters, OrderView, PositionView, as_ny

LIVE_STOP = frozenset({"new", "accepted", "held", "pending_new"})


@dataclass
class ClosedTrade:
    setup_id: str | None
    symbol: str
    opened: pd.Timestamp
    closed: pd.Timestamp
    buys: list[tuple[float, float]]
    sells: list[tuple[float, float]]
    stop_out: bool
    paper_pnl: float
    honest_pnl: float
    fees: float
    pending_verify: bool = False                # closed by a take-profit (resting limit) fill (MT-G4)
    gate_honest: float = 0.0                    # what the gates count: min(honest, 0) while PENDING_VERIFY
    r: float | None = None                      # honest P&L / planned risk in dollars (MT-G12 uses it only when
                                                # not pending_verify: an unverified win is left out, never 0R)
    tp_order_id: str | None = None              # the take-profit leg that closed it (matches a `tp_verified` line)
    parent_cid: str | None = None               # the entry's client id: how MT-G4 resolutions find the trade again
    gate_r: float | None = None                 # gate_honest / planned risk (what a pending take-profit counts at)
    tp_limit: float | None = None               # the take-profit leg's limit (the MT-G4 SIP re-mark checks it)
    tp_filled_at: pd.Timestamp | None = None


@dataclass
class AdoptedTrade:
    symbol: str
    qty: float                                  # shares held at the broker now
    avg_entry: float
    setup_id: str | None
    version: int
    bar_start: pd.Timestamp | None              # the signal bar (rebuilds the client ids of later exits)
    parent: OrderView | None                    # the entry parent, nested with its legs
    protected: bool                             # a live stop leg covers exactly the position
    buys: list[tuple[float, float]] = field(default_factory=list)
    sells: list[tuple[float, float]] = field(default_factory=list)
    next_attempt: dict[str, int] = field(default_factory=dict)   # leg letter -> next free attempt number
    why: str = ""


@dataclass
class AdoptedState:
    trade: AdoptedTrade | None = None
    pending_entry: OrderView | None = None      # unfilled SCALP entry parent still open: cancel it
    cancel_ids: list[str] = field(default_factory=list)          # other open SCALP orders to cancel
    cancel_views: list[OrderView] = field(default_factory=list)  # the same orders as read (fills already booked)
    extra_positions: list[PositionView] = field(default_factory=list)   # not explained by SCALP orders
    kill_attempt_next: int = 0
    trades: list[ClosedTrade] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _midnight(d: date) -> pd.Timestamp:
    return pd.Timestamp(d).tz_localize(NY)


def _when(v: OrderView) -> pd.Timestamp:
    for t in (v.filled_at, v.updated_at, v.submitted_at):
        if t is not None:
            return as_ny(t)
    return pd.Timestamp(0, tz=NY)


def _bar_start(p: dict[str, Any]) -> pd.Timestamp:
    hh, mm = p["hhmm"][:2], p["hhmm"][2:]
    return as_ny(pd.Timestamp(f"{p['session_date'].isoformat()} {hh}:{mm}"))


@dataclass
class _Lot:
    symbol: str
    setup_id: str | None
    version: int
    parent: OrderView
    bar_start: pd.Timestamp
    opened: pd.Timestamp
    qty: float
    price: float
    left: float = 0.0
    sells: list[tuple[float, float]] = field(default_factory=list)
    stop_out: bool = False
    pending_verify: bool = False
    tp_order_id: str | None = None
    tp_limit: float | None = None
    tp_filled_at: pd.Timestamp | None = None
    closed: pd.Timestamp | None = None


def rebuild(broker: Any, session_date: date, e0: float, cash_prev_close: float | None, week_start: date | None,
            test_start: date | None, registry: Any, now: pd.Timestamp) -> tuple[DayCounters, AdoptedState]:
    """(today's counters, what is live) from the broker's SCALP- order history. See the module docstring."""
    now = as_ny(now)
    # the day-trade count (MT-G15) looks back 5 sessions, which can start in the week before
    starts = [d for d in (week_start, test_start, session_date, session_date - timedelta(days=7)) if d is not None]
    since = _midnight(min(starts))
    history = broker.orders_since(since)
    st = AdoptedState()
    cnt = DayCounters(session_date=session_date, e0=float(e0), cash_prev_close=cash_prev_close)

    events: list[tuple[pd.Timestamp, int, str, Any]] = []   # (time, 0 buy / 1 sell, kind, payload)
    tp_legs: dict[str, OrderView] = {}
    sessions: set[date] = set()
    kill_max = -1
    for o in history:
        p = O.parse_client_id(o.client_order_id)
        if p is None:
            st.notes.append(f"non-SCALP order {o.client_order_id} ({o.symbol} {o.side} {o.status})")
            continue
        sd = p["session_date"]
        if test_start is not None and sd >= test_start:
            sessions.add(sd)
        if p["leg"] == "K" and sd == session_date:
            kill_max = max(kill_max, p["attempt"])
        if p["leg"] == "E":
            if sd == session_date:
                cnt.entry_submits += 1
                cnt.entry_submit_times.append(as_ny(o.submitted_at) if o.submitted_at is not None else now)
                if o.filled_qty > 0:
                    cnt.round_trips += 1
                    sid = p["setup_id"] or ""
                    cnt.round_trips_by_setup[sid] = cnt.round_trips_by_setup.get(sid, 0) + 1
            if o.filled_qty > 0 and o.filled_avg_price:
                reg_v = int(getattr(registry.get(p["setup_id"], o.symbol), "version", 0) or 0) \
                    if registry is not None and p["setup_id"] else 0
                lot = _Lot(o.symbol, p["setup_id"], reg_v, o, _bar_start(p), _when(o), float(o.filled_qty),
                           float(o.filled_avg_price))
                lot.left = lot.qty
                events.append((_when(o), 0, "buy", lot))
                for leg in o.legs:
                    if leg.filled_qty > 0 and leg.filled_avg_price:
                        events.append((_when(leg), 1, "stop" if leg.order_type == "stop_limit" else "target",
                                       (o.symbol, float(leg.filled_qty), float(leg.filled_avg_price), leg.id)))
                        tp_legs[leg.id] = leg
        elif o.side == "sell" and o.filled_qty > 0 and o.filled_avg_price:
            events.append((_when(o), 1, "protect" if p["leg"] == "P" else p["leg"],
                           (o.symbol, float(o.filled_qty), float(o.filled_avg_price), o.id)))
    st.kill_attempt_next = kill_max + 1
    cnt.test_sessions = len(sessions)

    # ---- FIFO pairing per symbol
    lots: dict[str, list[_Lot]] = {}
    closed: list[_Lot] = []
    for t, _, kind, payload in sorted(events, key=lambda e: (e[0], e[1])):
        if kind == "buy":
            lots.setdefault(payload.symbol, []).append(payload)
            if t.date() == session_date:
                cnt.notional_traded += payload.qty * payload.price
                cnt.buy_notional += payload.qty * payload.price
            continue
        sym, q, px, oid = payload
        if t.date() == session_date:
            cnt.notional_traded += q * px
        queue = lots.get(sym, [])
        while q > 1e-9 and queue:
            lot = queue[0]
            take = min(q, lot.left)
            lot.sells.append((take, px))
            lot.left -= take
            q -= take
            if kind in ("stop", "protect"):
                lot.stop_out = True
            if kind == "target":
                lot.pending_verify = True
                lot.tp_order_id = oid
                leg = tp_legs.get(oid)
                lot.tp_limit = leg.limit_price if leg is not None else None
                lot.tp_filled_at = _when(leg) if leg is not None else t
            if lot.left <= 1e-9:
                lot.closed = t
                closed.append(queue.pop(0))
        if q > 1e-9:
            st.notes.append(f"{sym}: {q:g} shares sold at {t} that no SCALP entry explains")

    # ---- closed trades -> P&L, streaks, timers
    running, peak = 0.0, 0.0
    for lot in sorted(closed, key=lambda x: x.closed):
        d = lot.closed.date()
        try:
            br = costs.pnl_breakdown([(lot.qty, lot.price)], lot.sells, d)
        except ValueError as e:                        # a date no fee row covers: no fees, loudly noted
            st.notes.append(f"FEE_TABLE_GAP {d}: {e}")
            paper = sum(q * p for q, p in lot.sells) - lot.qty * lot.price
            slip = C.HONEST_SLIP_PER_SHARE * (lot.qty + sum(q for q, _ in lot.sells))
            br = {"paper_pnl": paper, "honest_pnl": paper - slip, "fees": 0.0}
        gate = min(br["honest_pnl"], 0.0) if lot.pending_verify else br["honest_pnl"]
        sl = next((g for g in lot.parent.legs if g.order_type == "stop_limit"), None)
        lim, sl_lim = lot.parent.limit_price, (sl.limit_price if sl is not None else None)
        risk_usd = lot.qty * (lim - sl_lim) if lim is not None and sl_lim is not None and lim > sl_lim else None
        tr = ClosedTrade(lot.setup_id, lot.symbol, lot.opened, lot.closed, [(lot.qty, lot.price)], lot.sells,
                         lot.stop_out, br["paper_pnl"], br["honest_pnl"], br["fees"], lot.pending_verify, gate,
                         br["honest_pnl"] / risk_usd if risk_usd else None, lot.tp_order_id,
                         lot.parent.client_order_id, gate / risk_usd if risk_usd else None, lot.tp_limit,
                         lot.tp_filled_at)
        st.trades.append(tr)
        if week_start is not None and week_start <= d <= session_date or d == session_date:
            cnt.week_honest += gate
        if test_start is not None and test_start <= d <= session_date:
            running += gate
            peak = max(peak, running)
        if d != session_date:
            continue
        cnt.realized_pnl += tr.paper_pnl
        cnt.realized_honest += gate
        if gate < 0:
            cnt.loss_streak += 1
            if cnt.loss_streak >= C.LOSS_STREAK_N:
                cnt.loss_pause_until = lot.closed + pd.Timedelta(minutes=C.LOSS_STREAK_PAUSE_MIN)
        elif not lot.pending_verify:
            cnt.loss_streak = 0
        if tr.stop_out and lot.setup_id:
            cnt.stopout_until[(lot.setup_id, lot.symbol)] = lot.closed + pd.Timedelta(minutes=C.STOPOUT_REENTRY_MIN)
    cnt.test_honest, cnt.test_peak = running, peak
    # MT-G15: our own day trades (bought and sold on the same session) over the last 5 business days incl. today
    last5 = {x.date() for x in pd.bdate_range(end=pd.Timestamp(session_date), periods=5)}
    cnt.day_trades_5d = sum(1 for t in st.trades if t.opened.date() == t.closed.date() and t.closed.date() in last5)

    # ---- what is live now
    positions = [p for p in broker.positions() if abs(p.qty) > 1e-9]
    open_lots = {s: [x for x in q if x.left > 1e-9] for s, q in lots.items()}
    keep_ids: set[str] = set()
    for pos in positions:
        mine = open_lots.get(pos.symbol) or []
        if not mine or st.trade is not None or pos.qty <= 0:
            st.extra_positions.append(pos)
            continue
        lot = mine[-1]
        lot_qty = sum(x.left for x in mine)
        stop = next((g for g in lot.parent.legs if g.order_type == "stop_limit"), None)
        tp = next((g for g in lot.parent.legs if g.order_type != "stop_limit"), None)
        protected = (len(mine) == 1 and abs(lot_qty - pos.qty) <= 1e-9 and stop is not None
                     and stop.status in LIVE_STOP and abs(remaining(stop) - pos.qty) <= 1e-9)
        why = "" if protected else ("no live stop leg covering the position" if abs(lot_qty - pos.qty) <= 1e-9
                                    else f"broker holds {pos.qty:g}, SCALP history explains {lot_qty:g}")
        nxt: dict[str, int] = {}
        pfx = O.parse_client_id(lot.parent.client_order_id)
        for o in history:
            q = O.parse_client_id(o.client_order_id)
            if q and pfx and q["code"] == pfx["code"] and q["session_date"] == pfx["session_date"] \
                    and q["hhmm"] == pfx["hhmm"] and q["leg"] in ("X", "P"):
                nxt[q["leg"]] = max(nxt.get(q["leg"], 0), q["attempt"] + 1)
        st.trade = AdoptedTrade(pos.symbol, float(pos.qty), float(pos.avg_entry_price), lot.setup_id, lot.version,
                                lot.bar_start, lot.parent, protected, [(lot.qty, lot.price)], list(lot.sells), nxt,
                                why)
        if protected:
            keep_ids.add(lot.parent.id)
            keep_ids.update(g.id for g in (stop, tp) if g is not None and not is_done(g))
        elif not is_done(lot.parent):
            keep_ids.add(lot.parent.id)                    # the engine's protect path cancels it with the legs
            keep_ids.update(g.id for g in lot.parent.legs if not is_done(g))

    for o in history:
        p = O.parse_client_id(o.client_order_id)
        if p is None:
            continue
        live = [o] + list(o.legs)
        if p["leg"] == "E" and not is_done(o) and o.filled_qty <= 0 and o.id not in keep_ids:
            if st.pending_entry is None and st.trade is None:
                st.pending_entry = o
                continue
        for x in live:
            if not is_done(x) and x.id not in keep_ids:
                st.cancel_ids.append(x.id)
                st.cancel_views.append(x)
    return cnt, st


def _num(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return v if v == v else 0.0


def from_journal(lines: list[dict], cnt: DayCounters) -> str | None:
    """DRY restart (MT-G40): a dry run's broker is a fresh SimBroker, so the broker history is empty. Today's
    counters come back from today's dry journal instead (submits, round trips, fills' notional, closed trades'
    honest P&L, loss streak and pause, stop-out timers, the daily stop, broker-rejected symbols), added to `cnt`.
    A simulated position that was open when the process stopped is gone; the note says so. Returns a plain-English
    note, or None when the journal holds nothing from an earlier run today."""
    day = cnt.session_date.isoformat()
    todays = [x for x in lines if str(x.get("ts") or "")[:10] == day]
    subs = [x for x in todays if x.get("kind") in ("would_submit", "submit", "broker_reject")]
    fills = [x for x in todays if x.get("kind") == "fill"]
    closes = [x for x in todays if x.get("kind") == "trade_closed"]
    if not (subs or fills or closes):
        return None
    for x in subs:
        if x.get("kind") == "broker_reject":
            # the rejected submission is counted once, by the engine from blocked-DATE-dry (Engine._load_blocked,
            # which also counts it per setup); counting it here too would count it twice
            if x.get("symbol"):
                cnt.blocked_symbols.add(str(x["symbol"]))
            continue
        cnt.entry_submits += 1
        cnt.entry_submit_times.append(as_ny(x["ts"]))
    counted: set[str] = set()
    held = 0.0
    for f in fills:
        q, px = _num(f.get("qty")), _num(f.get("price"))
        cnt.notional_traded += q * px
        if f.get("side") == "buy":
            cnt.buy_notional += q * px
            held += q
            cid = str(f.get("cid") or f.get("order_id") or "")
            if f.get("role") == "entry" and cid not in counted:
                counted.add(cid)
                cnt.round_trips += 1
                sid = str(f.get("setup_id") or "")
                cnt.round_trips_by_setup[sid] = cnt.round_trips_by_setup.get(sid, 0) + 1
        else:
            held -= q
    for x in closes:
        t = as_ny(x["ts"])
        honest = _num(x.get("honest_pnl"))
        gate = _num(x.get("gate_honest_pnl")) if x.get("gate_honest_pnl") is not None else honest
        cnt.realized_pnl += _num(x.get("paper_pnl"))
        cnt.realized_honest += gate
        if gate < 0:
            cnt.loss_streak += 1
            if cnt.loss_streak >= C.LOSS_STREAK_N:
                cnt.loss_pause_until = t + pd.Timedelta(minutes=C.LOSS_STREAK_PAUSE_MIN)
        elif not x.get("pending_verify"):
            cnt.loss_streak = 0
        if x.get("stop_out") and x.get("setup_id"):
            cnt.stopout_until[(str(x["setup_id"]), str(x.get("symbol")))] = t + pd.Timedelta(
                minutes=C.STOPOUT_REENTRY_MIN)
    if any(x.get("kind") == "daily_stop" for x in todays):
        cnt.daily_stopped = True
    note = (f"DRY restart: today's dry counters rebuilt from the dry journal ({cnt.entry_submits} entry submits, "
            f"{cnt.round_trips} round trips, honest P&L ${cnt.realized_honest:,.2f}).")
    if held > 1e-9:
        note += (f" The simulated position of {held:g} share(s) open at the restart is gone (no trade_closed line "
                 "for it); the dry results miss that trade.")
    return note
