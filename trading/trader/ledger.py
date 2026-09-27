"""Lot bookkeeping: every change to a sleeve's holdings goes through this module (M-3, EX-4, EX-5, B-6, RISK-13).

The flow each day:
- `record_orders` stores the orders sent today as pending, crosses shares between sleeves when no order is
  needed, and persists raised stops.
- Next run, `settle_fills` reads what the broker actually filled and moves the lots at the real fill prices.
- `reconcile` compares the lots with the broker and writes an event for every difference (never silent).
- `update_marks` keeps the highest high / lowest low of each open lot and each sleeve's P&L curve
  (every open lot priced, with its last known close when today's is missing).

`apply_fill` is the single place a lot changes. Pure functions on `BookState`; no broker calls.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import pandas as pd
from pandas.tseries.holiday import (AbstractHolidayCalendar, GoodFriday, Holiday, USLaborDay,
                                    USMartinLutherKingJr, USMemorialDay, USPresidentsDay, USThanksgivingDay,
                                    nearest_workday, sunday_to_monday)

from .models import Lot, Target
from .state import BookState

EPS = 1e-9  # quantities at or below this are zero
FINAL_STATUSES = {"filled", "canceled", "cancelled", "expired", "rejected", "done_for_day", "replaced", "unknown"}


# --- small helpers ------------------------------------------------------------------------------


def _num(x) -> float | None:
    """A finite float, or None for None / NaN / text that is not a number."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _stop(x) -> float | None:
    """A usable stop price: finite and above zero."""
    v = _num(x)
    return v if v is not None and v > 0 else None


def _higher_stop(a: float | None, b: float | None) -> float | None:
    """Stops never widen (RISK-3): the higher of two stops, ignoring missing ones."""
    a, b = _stop(a), _stop(b)
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def _field(obj, name: str, default=None):
    """Read a field from a dataclass (Order, Target) or a plain dict."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _day(value) -> str | None:
    """ISO date (YYYY-MM-DD) from a date string or timestamp, or None (also for NaN / NaT)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(ts) else ts.date().isoformat()


def _class_of(asset_class, symbol: str) -> str:
    """Asset class from a callable, a {symbol: class} dict or one class name (EX-5).

    Pair symbols ("BTC/USD") are always crypto. Anything unknown is "unknown", which `_bps_for` charges
    at the most expensive rate, so a missing class never under-charges costs.
    """
    if "/" in str(symbol):
        return "crypto"
    if callable(asset_class):
        cls = asset_class(symbol)
    elif isinstance(asset_class, dict):
        cls = asset_class.get(symbol)
    else:
        cls = asset_class
    return str(cls) if cls else "unknown"


def _policy(cfg_or_policy) -> dict:
    return cfg_or_policy.policy if hasattr(cfg_or_policy, "policy") else cfg_or_policy


def _sleeve_pnl(state: BookState, sleeve: str) -> dict:
    """RISK-13 input: the running P&L record of one sleeve. `marks` ({symbol: {close, date}}) keeps each
    open lot's last known close, so a day without a price never drops its open P&L."""
    rec = state.sleeve_pnl.setdefault(sleeve, {})
    for k in ("realized", "cum", "peak"):
        rec.setdefault(k, 0.0)
    rec.setdefault("date", None)
    return rec


# --- trading sessions -----------------------------------------------------------------------------


class _NyseHolidays(AbstractHolidayCalendar):
    """Regular NYSE full-day holidays, so 'sessions held' counts trading days, not weekdays."""

    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=sunday_to_monday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


@lru_cache(maxsize=64)
def _holidays(first_year: int, last_year: int) -> tuple:
    days = _NyseHolidays().holidays(f"{first_year}-01-01", f"{last_year}-12-31")
    return tuple(d.date() for d in days)


def sessions_between(start: str, end: str, crypto: bool = False) -> int:
    """Sessions after `start` up to and including `end`: bars with start < date <= end.

    Crypto trades every day, so it counts calendar days. Special one-off market closures are not known here.
    """
    s, e = _day(start), _day(end)
    if s is None or e is None or e <= s:
        return 0
    s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
    if crypto:
        return int((e_ts - s_ts).days)
    begin = (s_ts + pd.Timedelta(days=1)).date()
    stop = (e_ts + pd.Timedelta(days=1)).date()
    return int(np.busday_count(begin, stop, holidays=list(_holidays(s_ts.year, e_ts.year))))


# --- costs (EX-5) -------------------------------------------------------------------------------


def cost_model(cfg_or_policy, state: BookState | None = None) -> dict[str, float]:
    """EX-5: per-side cost in bps per asset class. Measured overrides can only raise the policy value."""
    base = _policy(cfg_or_policy)["turnover"]["cost_model_per_side_bps"]
    out = {cls: float(bps) for cls, bps in base.items()}
    for cls, bps in (state.cost_model_bps if state is not None else {}).items():
        v = _num(bps)
        if v is not None and cls in out:
            out[cls] = max(out[cls], v)
    return out


def _bps_for(model: dict | None, state: BookState | None, asset_class: str) -> float:
    """bps for one class from a model dict; unknown class -> the most expensive one (safer)."""
    model = {k: float(v) for k, v in (model or {}).items() if _num(v) is not None}
    bps = model.get(asset_class, max(model.values()) if model else 0.0)
    override = _num((state.cost_model_bps if state is not None else {}).get(asset_class))
    return max(bps, override) if override is not None else bps


def cost_for(cfg_or_policy, state: BookState | None, asset_class: str, notional: float) -> float:
    """EX-5: dollar cost of one side of a trade of `notional` dollars."""
    model = _policy(cfg_or_policy)["turnover"]["cost_model_per_side_bps"]
    return abs(float(notional)) * _bps_for(model, state, asset_class) / 1e4


def measured_cost_model(state: BookState, policy) -> dict[str, float]:
    """EX-5: raise a class's cost to its median measured slippage when that is more than twice the model.

    Needs at least `slippage_min_fills` fills in the class. An order split over several sleeves counts once.
    Only raised classes are stored in `state.cost_model_bps`; a class is never set below the policy.
    """
    turnover = _policy(policy)["turnover"]
    model = {cls: float(b) for cls, b in turnover["cost_model_per_side_bps"].items()}
    min_fills = int(turnover.get("slippage_min_fills", 30))
    by_class: dict[str, list[float]] = {}
    seen: set = set()
    for i, row in enumerate(state.fills):
        slip = _num(row.get("slippage_bps"))
        if slip is None:
            continue
        key = (row.get("client_order_id"), row.get("date"), row.get("fill")) if row.get("client_order_id") else i
        if key in seen:
            continue
        seen.add(key)
        by_class.setdefault(row.get("asset_class"), []).append(slip)
    out, raised = dict(model), {}
    for cls, bps in model.items():
        slips = by_class.get(cls, [])
        if len(slips) >= min_fills:
            med = float(np.median(slips))
            if med > 2 * bps:
                out[cls] = raised[cls] = round(med, 2)
    state.cost_model_bps = raised
    return out


# --- the single place lots change (M-3) --------------------------------------------------------------


def _new_lot_id(state: BookState, sleeve: str, symbol: str, entry_date: str) -> str:
    base = f"{state.book}:{sleeve}:{symbol}:{entry_date}"
    used = {t.get("lot_id") for t in state.closed_trades}
    if base not in used:
        return base
    n = 2
    while f"{base}#{n}" in used:
        n += 1
    return f"{base}#{n}"


def _touch_marks(lot: Lot, price: float) -> None:
    """A traded price is inside the holding window, so it bounds the MAE / MFE marks."""
    lot.max_high = price if lot.max_high is None else max(lot.max_high, price)
    lot.min_low = price if lot.min_low is None else min(lot.min_low, price)


def _event(lot: Lot, date: str, kind: str, qty: float, price: float, signal_close, cost: float,
           realized: float, reason: str, note: str = "") -> None:
    ev = {
        "date": date, "kind": kind, "qty": round(qty, 9), "price": round(price, 6),
        "signal_close": _num(signal_close), "cost": round(cost, 6), "stop": lot.stop,
        "realized": round(realized, 6), "reason": reason, "qty_after": round(max(lot.qty, 0.0), 9),
    }
    if note:
        ev["note"] = note
    lot.events.append(ev)


def apply_fill(state: BookState, sleeve: str, symbol: str, delta_qty: float, price: float, date: str, *,
               signal_close: float | None = None, stop: float | None = None, reason: str = "", cost: float = 0.0,
               tags: dict | None = None, entry_date: str | None = None, note: str = "") -> None:
    """Move one sleeve's lot by `delta_qty` shares at `price` (M-3). Buys open or add; sells reduce or close.

    Raises ValueError for a missing / non-positive price or a non-finite quantity, so bad data never
    reaches the lots. A sell with no lot does nothing. `note` is extra detail kept on the event.
    """
    dq, px = _num(delta_qty), _num(price)
    if dq is None:
        raise ValueError(f"{sleeve}/{symbol}: quantity {delta_qty!r} is not a number")
    if abs(dq) <= EPS:
        return
    if px is None or px <= 0:
        raise ValueError(f"{sleeve}/{symbol}: fill price {price!r} is not a positive number")
    cost = abs(_num(cost) or 0.0)
    if dq > 0:
        _buy(state, sleeve, symbol, dq, px, date, signal_close, _stop(stop), reason, cost, tags, entry_date, note)
    else:
        _sell(state, sleeve, symbol, -dq, px, date, signal_close, reason, cost, note)


def _buy(state, sleeve, symbol, qty, price, date, signal_close, stop, reason, cost, tags, entry_date,
         note="") -> None:
    held = state.lots.setdefault(sleeve, {})
    lot = held.get(symbol)
    if lot is None:
        start = _day(entry_date) or date
        lot = Lot(qty=qty, entry_price=price, entry_date=start, stop=stop, initial_stop=stop,
                  lot_id=_new_lot_id(state, sleeve, symbol, start),
                  initial_risk_dollars=qty * max(0.0, price - stop) if stop is not None else 0.0,
                  bought_qty=qty, costs=cost, fill_date=date, tags=dict(tags or {}))
        held[symbol] = lot
        kind = "open"
    else:
        if not lot.lot_id:  # lot from an old state file
            lot.lot_id = _new_lot_id(state, sleeve, symbol, lot.entry_date)
        # M-3: the added shares' risk uses the stop in force after the add, not the first stop. Stops never
        # go down (RISK-3), so that is the higher of the lot's stop and the one sent with the add.
        stop_at_add = _higher_stop(lot.stop, stop)
        new_qty = lot.qty + qty
        lot.entry_price = (lot.entry_price * lot.qty + price * qty) / new_qty
        lot.qty = new_qty
        lot.bought_qty += qty
        if stop_at_add is not None:
            lot.initial_risk_dollars += qty * max(0.0, price - stop_at_add)
        lot.stop = stop_at_add
        lot.costs += cost
        for k, v in (tags or {}).items():
            lot.tags.setdefault(k, v)
        kind = "add"
    _touch_marks(lot, price)
    _sleeve_pnl(state, sleeve)["realized"] -= cost
    _event(lot, date, kind, qty, price, signal_close, cost, 0.0, reason, note)


def _sell(state, sleeve, symbol, qty, price, date, signal_close, reason, cost, note="") -> None:
    lot = state.lots.get(sleeve, {}).get(symbol)
    if lot is None:
        return
    if not lot.lot_id:
        lot.lot_id = _new_lot_id(state, sleeve, symbol, lot.entry_date)
    sold = min(qty, lot.qty)
    realized = sold * (price - lot.entry_price)
    lot.realized_pnl += realized
    lot.costs += cost
    lot.qty -= sold
    _touch_marks(lot, price)
    rec = _sleeve_pnl(state, sleeve)
    rec["realized"] += realized - cost
    _event(lot, date, "reduce", sold, price, signal_close, cost, realized, reason, note)
    if lot.qty <= EPS:
        state.closed_trades.append(_closed_trade(lot, sleeve, symbol, date, price, reason))
        (rec.get("marks") or {}).pop(symbol, None)  # a later lot in this symbol never uses this lot's mark
        del state.lots[sleeve][symbol]
        if not state.lots[sleeve]:
            del state.lots[sleeve]


def _closed_trade(lot: Lot, sleeve: str, symbol: str, date: str, last_price: float, reason: str) -> dict:
    """M-3: one record per lot, written when it reaches zero. R is net of costs (EX-5)."""
    sells = [e for e in lot.events if e.get("kind") == "reduce" and e.get("qty")]
    sold = sum(e["qty"] for e in sells)
    exit_price = sum(e["qty"] * e["price"] for e in sells) / sold if sold > 0 else last_price
    net = lot.realized_pnl - lot.costs
    risk = lot.initial_risk_dollars
    rps = lot.risk_per_share
    return {
        "date": date, "sleeve": sleeve, "symbol": symbol, "lot_id": lot.lot_id,
        "entry_date": lot.entry_date, "fill_date": lot.fill_date,
        "entry_price": round(lot.entry_price, 4), "exit_price": round(exit_price, 4),
        "qty": round(lot.bought_qty, 9), "pnl": round(net, 2), "realized_pnl": round(lot.realized_pnl, 2),
        "costs": round(lot.costs, 2), "initial_stop": lot.initial_stop,
        "initial_risk_dollars": round(risk, 2), "R": round(net / risk, 3) if risk > 0 else None,
        "mae_R": round((lot.min_low - lot.entry_price) / rps, 3) if rps and lot.min_low is not None else None,
        "mfe_R": round((lot.max_high - lot.entry_price) / rps, 3) if rps and lot.max_high is not None else None,
        "sessions_held": sessions_between(lot.entry_date, date, crypto="/" in symbol),
        "reason": reason, "tags": dict(lot.tags), "events": list(lot.events),
    }


# --- today's orders (EX-4) ----------------------------------------------------------------------


def _deltas(state: BookState, targets: list[Target]) -> dict[str, list[tuple]]:
    """symbol -> [(target, delta)] where delta = target qty - the sleeve's lot qty (non-zero only)."""
    last: dict[tuple, Target] = {}
    for t in targets:
        last[(_field(t, "sleeve"), _field(t, "symbol"))] = t  # a repeated (sleeve, symbol): the last one wins
    out: dict[str, list[tuple]] = {}
    for (sleeve, sym), t in last.items():
        want = _num(_field(t, "qty"))
        if want is None:  # a broken target never means "exit"
            continue
        lot = state.lots.get(sleeve, {}).get(sym)
        d = max(0.0, want) - (lot.qty if lot else 0.0)
        if abs(d) > EPS:
            out.setdefault(sym, []).append((t, d))
    return out


def _pair_results(orders: list, results: list[dict]) -> list[tuple]:
    """Match each order to its submit result: by client_order_id, then list position, then symbol and side."""
    used: set[int] = set()
    pairs = []
    for i, o in enumerate(orders):
        sym, side, coid = _field(o, "symbol"), _field(o, "side"), _field(o, "client_order_id") or ""
        free = [j for j, r in enumerate(results)
                if j not in used and r.get("symbol", sym) == sym and r.get("side", side) == side]
        by_id = [j for j in free if coid and results[j].get("client_order_id") == coid]
        j = by_id[0] if by_id else (i if i in free else (free[0] if free else None))
        if j is not None:
            used.add(j)
        pairs.append((o, results[j] if j is not None else None))
    return pairs


def _alloc(entries: list[tuple], tags: dict | None) -> list[dict]:
    return [{"sleeve": _field(t, "sleeve"), "delta_qty": d, "stop": _stop(_field(t, "stop")),
             "reason": _field(t, "reason", "") or "", "tags": dict(tags or {}),
             "target_qty": max(0.0, _num(_field(t, "qty")) or 0.0)} for t, d in entries]


def record_orders(state: BookState, targets: list[Target], orders: list, submit_results: list[dict],
                  prices: dict[str, float], date: str, *, asset_class, cost_bps: dict | None,
                  tags: dict | None = None, log: list[str] | None = None,
                  min_notional: float = 25.0) -> list[dict]:
    """EX-4: store today's submitted orders as pending; cross between sleeves when no order is needed.

    - Each submitted order (status not "error") becomes a pending order holding every sleeve's delta for
      that symbol. Its lots change only when `settle_fills` sees the real fill.
    - A symbol with no order: if some sleeves increase and others decrease, `min(sum up, sum down)` shares
      move between them at the signal close with zero cost. When a sleeve exits to zero and the shares the
      others buy fall short of its lot by at most `min_notional` dollars (policy
      `turnover.min_order_notional`, which is why no order was sent), it sells its whole lot so its trade
      record is written, and the leftover goes to the buying sleeves pro rata. The broker total never
      changes without an order. One-sided changes with no order change nothing; an unfinished exit is logged.
    - Every target whose lot exists: `lot.stop = max(lot.stop, target.stop)` (persists the C-7 ratchet).
    `asset_class` (callable, {symbol: class} dict or one class name) is stored on each pending order; an
    unknown class is charged the most expensive rate at settlement. `cost_bps` is part of the engine's call;
    crosses are free, and costs are charged in `settle_fills`. A result without a client_order_id gets one
    here (written into the result dict too), so an immediate fill can be settled with `immediate_fills`.
    Returns the pending orders added.
    """
    log = log if log is not None else []
    deltas = _deltas(state, targets)
    added, ordered = [], set()
    for n, (o, res) in enumerate(_pair_results(orders, submit_results or [])):
        sym = _field(o, "symbol")
        ordered.add(sym)
        if res is None or str(res.get("status", "")).lower() == "error":
            why = res.get("error", "") if res else "no submit result"
            log.append(f"{sym}: {_field(o, 'side')} order not placed ({why}); lots unchanged")
            continue
        added.append(_pending(state, o, res, n, deltas.get(sym, []), prices, date, asset_class, tags))
    state.pending_orders.extend(added)
    for sym, entries in deltas.items():
        if sym in ordered:
            continue
        alloc = _alloc(entries, tags)
        _cross(state, sym, alloc, _num(prices.get(sym)), date, tags, log, order_id=None,
               min_notional=min_notional)
        for a in alloc:
            left = _lot_qty(state, a["sleeve"], sym) if a["target_qty"] <= EPS else None
            if left:
                log.append(f"{a['sleeve']}/{sym}: exit not finished, {left:.6g} shares stay in the book "
                           "(no order was sent for this symbol); the trade record waits for the last share")
    _raise_stops(state, targets)
    return added


def _pending(state, o, res, n, entries, prices, date, asset_class, tags) -> dict:
    sym, side = _field(o, "symbol"), _field(o, "side")
    coid = res.get("client_order_id") or _field(o, "client_order_id") or f"{state.book}-{date}-{sym}-{side}-{n}"
    res.setdefault("client_order_id", coid)
    signal_close = _num(prices.get(sym)) or _num(_field(o, "price"))
    return {"client_order_id": coid, "broker_order_id": res.get("id"), "date": date, "symbol": sym,
            "side": side, "qty": _num(res.get("qty")) or _num(_field(o, "qty")) or 0.0,
            "signal_close": signal_close, "asset_class": _class_of(asset_class, sym), "alloc": _alloc(entries, tags),
            "status": str(res.get("status", "")), "settled_qty": 0.0, "settled_value": 0.0, "crossed": False}


def _lot_qty(state: BookState, sleeve: str, sym: str) -> float | None:
    lot = state.lots.get(sleeve, {}).get(sym)
    return lot.qty if lot else None


def _cross(state: BookState, sym: str, alloc: list[dict], price: float | None, date: str,
           tags: dict | None, log: list[str], *, order_id: str | None, min_notional: float = 0.0) -> None:
    """Move shares between sleeves at the signal close with zero cost: min(sum up, sum down), pro rata.

    `order_id` None means no order was sent for the symbol (record_orders): then the broker total cannot
    change. If the exits' leftover beyond what the other sleeves buy is worth at most `min_notional`, a
    sleeve exiting to zero sells its whole lot first, the leftover goes to the buying sleeves pro rata and
    trims take what is left. Otherwise (or inside an order, at settlement) the split is pro rata.
    """
    ups = [a for a in alloc if a["delta_qty"] > EPS]
    downs = [a for a in alloc if a["delta_qty"] < -EPS]
    tot_up, tot_down = sum(a["delta_qty"] for a in ups), -sum(a["delta_qty"] for a in downs)
    size = min(tot_up, tot_down)
    where = "no order" if order_id is None else f"inside order {order_id}, at the signal close"
    if size <= EPS:
        return
    if price is None or price <= 0:
        log.append(f"{sym}: internal cross between sleeves ({where}) skipped, no price")
        return
    exits = [a for a in downs if a.get("target_qty", 1.0) <= EPS]
    exit_q = {id(a): _lot_qty(state, a["sleeve"], sym) or -a["delta_qty"] for a in exits}
    tot_exit = sum(exit_q.values())
    if order_id is None and exits and tot_up < tot_down - EPS \
            and (tot_exit - tot_up) * price <= max(0.0, _num(min_notional) or 0.0) + 1e-9:
        # M-3: finish the exits so their trades are recorded, instead of leaving a stub no order will clear.
        # Only for a leftover below the order minimum, so the other sleeves never get more than that.
        rest = max(0.0, tot_up - tot_exit)  # what the trims still sell once the exits are done
        tot_trim = -sum(a["delta_qty"] for a in downs if id(a) not in exit_q)
        sells = []
        for a in downs:
            if id(a) in exit_q:
                sells.append((a, exit_q[id(a)]))
            else:
                sells.append((a, rest * -a["delta_qty"] / tot_trim if tot_trim > EPS else 0.0))
        moved = max(tot_up, tot_exit)
    else:
        sells = []
        for a in downs:
            q = size * -a["delta_qty"] / tot_down
            if a.get("target_qty", 1.0) <= EPS and size >= tot_down - EPS:
                q = _lot_qty(state, a["sleeve"], sym) or q  # a full exit leaves no rounding dust
            sells.append((a, q))
        moved = size
    for a, q in sells:  # sells first
        apply_fill(state, a["sleeve"], sym, -q, price, date, signal_close=price,
                   reason=f"internal cross: {a['reason']}", tags=a.get("tags") or tags, entry_date=date)
    for a in ups:
        apply_fill(state, a["sleeve"], sym, moved * a["delta_qty"] / tot_up, price, date, signal_close=price,
                   stop=a.get("stop"), reason=f"internal cross: {a['reason']}", tags=a.get("tags") or tags,
                   entry_date=date)
    log.append(f"{sym}: {moved:.6g} shares crossed between sleeves at {price:.2f} ({where}, no cost)")
    if moved > tot_up + EPS:
        names = ", ".join(a["sleeve"] for a in ups)
        log.append(f"{sym}: exit left {moved - tot_up:.6g} shares that no order sells (below the order "
                   f"minimum); they move to {names}, so the book still matches the broker")


def _raise_stops(state: BookState, targets: list[Target]) -> None:
    """Persist ratcheted stops (C-7, RISK-4). Stops only ever rise."""
    for t in targets:
        lot = state.lots.get(_field(t, "sleeve"), {}).get(_field(t, "symbol"))
        if lot is not None:
            lot.stop = _higher_stop(lot.stop, _field(t, "stop"))


def immediate_fills(submit_results: list[dict], date: str) -> list[dict]:
    """Fill rows (the `order_fills` shape) for orders a broker filled at submit time (simulator close mode)."""
    rows = []
    for r in submit_results or []:
        price = _num(r.get("filled_avg_price", r.get("fill_price")))
        if str(r.get("status", "")).lower() != "filled" or price is None or not r.get("client_order_id"):
            continue
        rows.append({"client_order_id": r["client_order_id"], "status": "filled", "final": True,
                     "filled_qty": _num(r.get("filled_qty", r.get("qty"))) or 0.0, "filled_avg_price": price,
                     "filled_at": _day(r.get("filled_at")) or date})
    return rows


def pending_symbols(state: BookState) -> set[str]:
    """Symbols with an order still open at the broker; `reconcile` leaves these alone."""
    return {o.get("symbol") for o in state.pending_orders if o.get("symbol")}


# --- settle last run's orders (EX-4, B-6) --------------------------------------------------------------


def _is_final(fill: dict) -> bool:
    if "final" in fill and fill["final"] is not None:
        return bool(fill["final"])
    return str(fill.get("status", "")).lower() in FINAL_STATUSES


def settle_fills(state: BookState, fills: list[dict], *, date: str, asset_class, cost_bps: dict | None,
                 log: list[str] | None = None) -> list[dict]:
    """EX-4: move the lots to what the broker really filled, at the real fill prices.

    Fills are matched to `state.pending_orders` by client_order_id. Finished orders are removed; orders still
    open stay pending (a partial fill is applied now and the rest later). Returns the fill rows added to
    `state.fills`. Costs use `cost_bps` (per asset class), never below a measured override (EX-5); an
    unknown class pays the most expensive rate. `cost_bps=None` charges no policy costs and says so in the
    log. The simulator already fills at price +/- cost, so its caller passes zero bps to avoid charging twice.
    """
    log = log if log is not None else []
    by_id = {f.get("client_order_id"): f for f in fills or [] if f.get("client_order_id")}
    known = {o.get("client_order_id") for o in state.pending_orders}
    for coid in by_id:
        if coid not in known:
            log.append(f"fill for unknown order {coid} ignored")
    rows, keep = [], []
    for order in state.pending_orders:
        fill = by_id.get(order.get("client_order_id"))
        if fill is None:
            keep.append(order)
            continue
        rows += _settle_one(state, order, fill, date, asset_class, cost_bps, log)
        if _is_final(fill):
            _log_final(order, fill, log)
        else:
            keep.append(order)
    state.pending_orders = keep
    state.fills.extend(rows)
    if cost_bps is None and rows:
        log.append("settle_fills: no cost model given, fills booked without policy costs (EX-5)")
    return rows


def _settle_one(state, order, fill, date, asset_class, cost_bps, log) -> list[dict]:
    sym, side = order["symbol"], order["side"]
    sign = 1 if side == "buy" else -1
    order["status"] = str(fill.get("status", order.get("status", "")))
    if not order.get("crossed"):  # sleeves netted inside this symbol trade with each other first
        _cross(state, sym, order.get("alloc", []), _num(order.get("signal_close")), order["date"], None, log,
               order_id=order.get("client_order_id") or "?")
        order["crossed"] = True
    filled = _num(fill.get("filled_qty")) or 0.0
    new = filled - (order.get("settled_qty") or 0.0)
    if new <= EPS:
        return []
    avg = _num(fill.get("filled_avg_price"))
    if avg is None or avg <= 0:
        log.append(f"{sym}: {new:.6g} filled but no fill price; not applied (reconcile will check)")
        return []
    value = filled * avg - (order.get("settled_value") or 0.0)
    price = value / new if value > 0 else avg  # price of this increment when an order fills in pieces
    order["settled_qty"], order["settled_value"] = filled, filled * avg
    same = [a for a in order.get("alloc", []) if a["delta_qty"] * sign > EPS]
    total = sum(abs(a["delta_qty"]) for a in same)
    if total <= EPS:
        log.append(f"{sym}: {side} fill of {new:.6g} matches no sleeve; reconcile will check")
        return []
    cls = order.get("asset_class") or _class_of(asset_class, sym)
    bps = _bps_for(cost_bps, state, cls)
    full = _is_final(fill) and filled >= (_num(order.get("qty")) or 0.0) - 1e-6
    fill_date = _day(fill.get("filled_at")) or date
    rows = []
    for a in same:
        q = new * abs(a["delta_qty"]) / total
        lot = state.lots.get(a["sleeve"], {}).get(sym)
        if sign < 0 and full and a.get("target_qty", 1.0) <= EPS and lot is not None:
            q = lot.qty  # a full exit leaves no rounding dust
        rps = lot.risk_per_share if lot is not None else None  # read before the fill can close the lot
        apply_fill(state, a["sleeve"], sym, sign * q, price, fill_date, signal_close=order.get("signal_close"),
                   stop=a.get("stop"), reason=a.get("reason", ""), cost=q * price * bps / 1e4,
                   tags=a.get("tags"), entry_date=order["date"])
        rows.append(_fill_row(order, a, q, price, fill_date, cls, q * price * bps / 1e4, rps))
    return rows


def _fill_row(order: dict, a: dict, qty: float, price: float, date: str, cls: str, cost: float,
              lot_risk_per_share: float | None = None) -> dict:
    """EX-4 slippage (positive = worse for us) and B-6 gap_R for every sleeve B fill.

    B-6, positive = worse: buys (fill - signal_close) / (signal_close - stop); sells
    (signal_close - fill) / the lot's 1R per share (entry - stop).
    """
    side, sc = order["side"], _num(order.get("signal_close"))
    sign = 1 if side == "buy" else -1
    slip = round(sign * (price / sc - 1) * 1e4, 2) if sc and sc > 0 else None
    gap_r = None
    stop, rps = _stop(a.get("stop")), _num(lot_risk_per_share)
    if a["sleeve"] == "B" and sc and sc > 0:
        if side == "buy" and stop is not None and sc - stop > 0:
            gap_r = round((price - sc) / (sc - stop), 4)
        elif side == "sell" and rps is not None and rps > 0:
            gap_r = round((sc - price) / rps, 4)
    return {"date": date, "symbol": order["symbol"], "side": side, "sleeve": a["sleeve"], "asset_class": cls,
            "qty": round(qty, 9), "signal_close": sc, "fill": round(price, 6), "slippage_bps": slip, "gap_R": gap_r,
            "cost": round(cost, 6), "client_order_id": order.get("client_order_id"), "signal_date": order.get("date")}


def _log_final(order: dict, fill: dict, log: list[str]) -> None:
    filled, qty = _num(fill.get("filled_qty")) or 0.0, _num(order.get("qty")) or 0.0
    status = str(fill.get("status", ""))
    if status.lower() == "unknown":
        log.append(f"{order['symbol']}: broker does not know order {order.get('client_order_id')}; "
                   "removed, reconcile will check the position")
    elif filled < qty - 1e-6:
        log.append(f"{order['symbol']}: {order['side']} order {status}, filled {filled:.6g} of {qty:.6g}")


# --- broker vs book (phase 1 item 2: no silent rescale) ---------------------------------------------------


RECONCILE = "reconcile"  # the exact event / trade reason (metrics G-5 counts these)


def _compact(sym) -> str:
    return str(sym).replace("/", "").replace("-", "").upper()


def reconcile(lots: dict[str, dict[str, Lot]], positions: dict[str, float], log: list[str], *,
              state: BookState | None = None, prices: dict[str, float] | None = None, date: str | None = None,
              skip_symbols=(), allow_all_zero: bool = False) -> set[str]:
    """Make the sleeve lots agree with what the broker holds. Every change is logged and written as an event
    with reason "reconcile" (the numbers are in the event's `note`).

    Differences within 1% are left alone. Symbols with orders still pending are skipped. With `state`,
    reductions realize P&L at today's close (a lot that reaches zero writes its closed trade) and increases
    are adds at today's close with the lot's stop. Without `state` (old call) the lots are scaled and each
    change is still logged and written as an event, but no P&L is booked, and the log says so.

    Broker data that looks wrong changes nothing: a position that is not a number, a symbol the broker
    spells differently (BTCUSD for BTC/USD), or a broker that reports none of the symbols the book tracks
    (an empty or failed positions call would otherwise close every lot and leave the real shares with no
    sleeve and no stop). Pass `allow_all_zero=True` once the owner has checked the account really is empty.
    Returns the symbols skipped for suspect broker data, so the caller can treat them as data problems.
    """
    date = date or pd.Timestamp.today().date().isoformat()
    positions = positions or {}
    if state is not None:
        lots = state.lots
    skip = set(skip_symbols) | (pending_symbols(state) if state is not None else set())
    totals: dict[str, float] = {}
    for held in lots.values():
        for sym, lot in held.items():
            totals[sym] = totals.get(sym, 0.0) + lot.qty
    suspect = _suspect_positions(totals, positions, skip, allow_all_zero, log)
    changed = False
    for sym, total in totals.items():
        if sym in suspect:
            continue
        have = max(0.0, _num(positions.get(sym, 0.0)))
        if total <= 0 or abs(have - total) <= 0.01 * total:
            continue
        if sym in skip:
            log.append(f"{sym}: broker holds {have:.6g}, book expects {total:.6g}; order pending, checked next run")
            continue
        factor = have / total
        note = f"broker holds {have:.6g}, book expected {total:.6g}"
        log.append(f"{sym}: reconcile: {note}; lots moved by factor {factor:.3f}")
        changed = True
        if state is not None:
            _reconcile_state(state, sym, factor, _num((prices or {}).get(sym)), date, note, log)
        else:
            _reconcile_lots_only(lots, sym, factor, date, note, log)
    if changed and state is None:
        log.append("reconcile was called without state: lots were rescaled but no P&L or trade record was "
                   "booked (M-3); the engine should pass state=, prices= and date=")
    _log_untracked(totals, positions, log)
    return suspect


def _suspect_positions(totals: dict[str, float], positions: dict, skip: set, allow_all_zero: bool,
                       log: list[str]) -> set[str]:
    """Tracked symbols whose broker numbers should not be trusted today (see `reconcile`)."""
    suspect = set()
    for sym in totals:
        raw = positions.get(sym, 0.0)
        if _num(raw) is None:
            log.append(f"{sym}: broker position {raw!r} is not a number; reconcile skipped")
            suspect.add(sym)
        elif sym not in positions:
            alias = [p for p in positions if p not in totals and _compact(p) == _compact(sym)]
            if alias:
                log.append(f"{sym}: the broker reports it as {alias[0]}; symbol names do not match, "
                           "reconcile skipped (fix the symbol mapping)")
                suspect.add(sym)
    live = [s for s, t in totals.items() if t > EPS and s not in skip and s not in suspect]
    if live and not allow_all_zero and all((_num(positions.get(s, 0.0)) or 0.0) <= EPS for s in live):
        log.append(f"WARNING: the broker reports none of the {len(live)} symbol(s) this book holds "
                   f"({', '.join(sorted(live))}); reconcile changed nothing. If the account really is empty, "
                   "rerun reconcile with allow_all_zero=True.")
        suspect.update(live)
    return suspect


def _reconcile_state(state: BookState, sym: str, factor: float, price: float | None, date: str, note: str,
                     log: list[str]) -> None:
    for sleeve in list(state.lots):
        lot = state.lots.get(sleeve, {}).get(sym)
        if lot is None:
            continue
        px = price if price is not None and price > 0 else lot.entry_price
        if px != price:
            log.append(f"{sleeve}/{sym}: no close today, reconcile uses the entry price (zero P&L)")
        delta = -lot.qty if factor <= 0 else lot.qty * (factor - 1)
        apply_fill(state, sleeve, sym, delta, px, date, signal_close=px, stop=lot.stop, reason=RECONCILE,
                   note=note)


def _reconcile_lots_only(lots: dict, sym: str, factor: float, date: str, note: str, log: list[str]) -> None:
    for sleeve in list(lots):
        lot = lots[sleeve].get(sym)
        if lot is None:
            continue
        before = lot.qty
        lot.qty = before * factor
        # No prices here, so no P&L can be realized: the event is a plain rescale, still on the record.
        _event(lot, date, "rescale", abs(lot.qty - before), lot.entry_price, None, 0.0, 0.0, RECONCILE, note)
        if factor <= 0:
            log.append(f"{sleeve}/{sym}: lot removed by reconcile without a trade record (no state given)")
            del lots[sleeve][sym]


def _log_untracked(totals: dict[str, float], positions: dict[str, float], log: list[str]) -> None:
    for sym, q in positions.items():
        v = _num(q)
        if v is not None and v > 1e-6 and totals.get(sym, 0.0) <= 0:
            log.append(f"{sym}: broker holds {v:.6g} that no sleeve tracks (left alone)")


# --- old immediate-fill path ------------------------------------------------------------------------------


def update_lots(state: BookState, targets: list[Target], prices: dict[str, float], date: str, *,
                asset_class=None, cost_bps: dict | None = None, tags: dict | None = None,
                log: list[str] | None = None) -> None:
    """Old path: every target fills immediately at `prices` (kept for old callers; M-3 bookkeeping applies).

    Stops never go down. Costs are charged only when `asset_class` and `cost_bps` are given.
    """
    for t in targets:
        sleeve, sym = _field(t, "sleeve"), _field(t, "symbol")
        lot = state.lots.get(sleeve, {}).get(sym)
        cur = lot.qty if lot else 0.0
        want, price = _num(_field(t, "qty")), _num(prices.get(sym))
        delta = 0.0 if want is None else (-cur if want <= EPS else want - cur)
        if want is None or (abs(delta) > EPS and (price is None or price <= 0)):
            if log is not None:
                log.append(f"{sleeve}/{sym}: no valid quantity or price, lot unchanged")
            continue
        if abs(delta) > EPS:
            cls = _class_of(asset_class, sym) if asset_class is not None else None
            cost = abs(delta) * price * _bps_for(cost_bps, state, cls) / 1e4 if cls and cost_bps else 0.0
            apply_fill(state, sleeve, sym, delta, price, date, signal_close=price, stop=_field(t, "stop"),
                       reason=_field(t, "reason", "") or "", cost=cost, tags=tags, entry_date=date)
        lot = state.lots.get(sleeve, {}).get(sym)
        if lot is not None:
            lot.stop = _higher_stop(lot.stop, _field(t, "stop"))
    state.lots = {s: h for s, h in state.lots.items() if h}


# --- daily marks (M-2 MAE/MFE inputs, RISK-13 inputs) ------------------------------------------------------


def _upto(df: pd.DataFrame, date: str | None) -> pd.DataFrame:
    if date is None or df.empty:
        return df
    ts = pd.Timestamp(date)
    if getattr(df.index, "tz", None) is not None and ts.tz is None:
        ts = ts.tz_localize(df.index.tz)
    return df[df.index <= ts]


def _after(df: pd.DataFrame, date: str) -> pd.DataFrame:
    ts = pd.Timestamp(date)
    if getattr(df.index, "tz", None) is not None and ts.tz is None:
        ts = ts.tz_localize(df.index.tz)
    return df[df.index > ts]


def _last_close(df: pd.DataFrame | None, date: str | None) -> tuple[float | None, str | None]:
    """The last usable close up to `date` and its bar date, or (None, None)."""
    if df is None or not isinstance(df, pd.DataFrame) or "close" not in df:
        return None, None
    try:
        closes = pd.to_numeric(_upto(df, date)["close"], errors="coerce")
    except (TypeError, ValueError):
        return None, None
    closes = closes[closes > 0].dropna()
    if not len(closes):
        return None, None
    return _num(closes.iloc[-1]), _day(closes.index[-1])


def update_marks(state: BookState, bars: dict[str, pd.DataFrame], date: str, *,
                 log: list[str] | None = None) -> None:
    """Update each open lot's highest high / lowest low since entry, then each sleeve's P&L curve.

    Sleeve P&L (RISK-13): cum = realized (net of costs) + sum of qty * (close - entry_price) over open lots;
    peak = the highest cum so far (starts at 0). Every open lot is always priced: a lot with no close today
    uses its last known close (kept in `sleeve_pnl[sleeve]["marks"]`), else its entry price, and the log says
    so. Counting it as zero would hide a loss (loosening RISK-13) or lift the peak and fake a drawdown later.
    """
    log = log if log is not None else []
    unrealized: dict[str, float] = {}
    for sleeve, held in state.lots.items():
        marks = _sleeve_pnl(state, sleeve).setdefault("marks", {})
        for sym, lot in held.items():
            df = bars.get(sym)
            if isinstance(df, pd.DataFrame) and len(df) and {"high", "low"} <= set(df.columns):
                _mark_lot(lot, df, date)
            close, bar_date = _last_close(df, date)
            if close is not None:
                marks[sym] = {"close": close, "date": bar_date or date}
            else:
                old = marks.get(sym) if isinstance(marks.get(sym), dict) else {}
                close = _num(old.get("close"))
                if close is not None and close > 0:
                    log.append(f"{sleeve}/{sym}: no close today; sleeve P&L uses the last close "
                               f"{close:.2f} from {old.get('date')}")
                else:
                    close = lot.entry_price
                    log.append(f"{sleeve}/{sym}: no close yet; sleeve P&L values it at its entry price")
            unrealized[sleeve] = unrealized.get(sleeve, 0.0) + lot.qty * (close - lot.entry_price)
        for sym in [s for s in marks if s not in held]:
            del marks[sym]
    for sleeve in set(state.lots) | set(state.sleeve_pnl):
        rec = _sleeve_pnl(state, sleeve)
        if sleeve not in state.lots:
            rec.pop("marks", None)
        rec["cum"] = round(rec["realized"] + unrealized.get(sleeve, 0.0), 6)
        rec["peak"] = round(max(rec["peak"], rec["cum"]), 6)
        rec["date"] = date


def _mark_lot(lot: Lot, df: pd.DataFrame, date: str) -> None:
    try:
        window = _upto(_after(df, lot.entry_date), date)
    except (TypeError, ValueError):
        return
    hi, lo = _num(window["high"].max()), _num(window["low"].min())
    if hi is not None:
        lot.max_high = hi if lot.max_high is None else max(lot.max_high, hi)
    if lo is not None:
        lot.min_low = lo if lot.min_low is None else min(lot.min_low, lo)
