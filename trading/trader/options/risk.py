"""Book O's own order check (OPT-2, OPT-3, OPT-5, OPT-8, OPT-9, OPT-14, OPT-15, OPT-24, OPT-42).

This is the ONLY place that accepts OCC option symbols. The stock path in `trader/risk.py` is not touched and
keeps rejecting them (OPT-2). Every order book O could send passes `validate_spread_order` first; shadow orders
pass it too, so the shadow book follows the same rules.

Order shape (a plain dict, the same one the broker's mleg submit takes):
    {"legs": [{"symbol": OCC, "side": "buy"|"sell", "position_intent": "buy_to_open"|"sell_to_open"|
               "buy_to_close"|"sell_to_close", "ratio_qty": 1}, ...],
     "qty": int contracts, "limit_price": float (negative = credit, positive = debit; alpaca-py mleg sign),
     "intent": "open"|"close", "order_class": "mleg", "type": "limit", "time_in_force": "day",
     "extended_hours": False, "client_order_id": "OPT-...",
     optional: "budgeted_loss_per_contract", "quoted_cost", "lot_id" (for closes)}

Numbers in the order never loosen a check (OPT-7): the budgeted loss per contract is computed here from the
strikes and the limit price; a supplied value can only raise it. Breaker inputs (OPT-31 `cap_mult`, halts,
freezes) are keyword arguments of the validator, never order fields.
"""
from __future__ import annotations

import math

from .book import (_cap_greeks, assignment_need, cycle_blocked, dte, floor_int, new_this_week, num, ob_policy,
                   open_budgeted_loss, to_date)
from .models import MULTIPLIER, is_occ, parse_occ

MODES = ("shadow", "paper", "live")
OPEN_INTENTS = {"buy_to_open", "sell_to_open"}
CLOSE_INTENTS = {"buy_to_close", "sell_to_close"}


def _lots(ledger) -> list:
    """Open lots from an OptionsBook, a list of SpreadLots, or None."""
    if ledger is None:
        return []
    if hasattr(ledger, "open_lots"):
        return ledger.open_lots()
    return [l for l in ledger if getattr(l, "status", "open") != "closed"]


def _closed(ledger) -> list[dict]:
    return list(getattr(ledger, "closed", []) or [])


def _every_lot(ledger) -> list:
    """Open and closed lots (for the OPT-18 cycle and OPT-9 weekly checks)."""
    if ledger is None:
        return []
    if hasattr(ledger, "all_lots"):
        return ledger.all_lots()
    if hasattr(ledger, "open_lots"):
        return ledger.open_lots()
    return list(ledger)


def _leg_side(leg: dict) -> str | None:
    """'long' or 'short' from the leg's position intent (or its side when no intent is given)."""
    intent = str(leg.get("position_intent", "")).lower()
    if intent in ("buy_to_open", "sell_to_close"):
        return "long"
    if intent in ("sell_to_open", "buy_to_close"):
        return "short"
    side = str(leg.get("side", "")).lower()
    return {"buy": "long", "sell": "short"}.get(side)


def _order_basics(order: dict, p: dict) -> list[str]:
    """OPT-14: mleg, LIMIT, DAY, whole contracts, no extended hours; owner decision 6: `OPT-` client id."""
    out = []
    if str(order.get("order_class", "mleg")).lower() != "mleg":
        out.append("OPT-3: must be one mleg order")
    if str(order.get("type", "limit")).lower() != "limit":
        out.append("OPT-14: limit orders only, never market")
    if str(order.get("time_in_force", "day")).lower() != "day":
        out.append("OPT-14: time in force must be DAY (never queued overnight)")
    if order.get("extended_hours"):
        out.append("OPT-14: no extended hours")
    q = num(order.get("qty"))
    if q is None or q <= 0 or q != math.floor(q):
        out.append(f"OPT-14: qty must be a whole number of contracts > 0 (got {order.get('qty')!r})")
    prefix = str(p.get("order_prefix", "OPT-"))
    if not str(order.get("client_order_id", "")).startswith(prefix):
        out.append(f"owner decision 6: client_order_id must start with {prefix!r}")
    return out


def _leg_shape(order: dict) -> tuple[list[str], list[dict]]:
    """OPT-3 / OPT-5: exactly 2 option legs, same underlying/expiry/type, ratio 1:1, one long and one short."""
    legs = order.get("legs") or []
    if len(legs) != 2:
        kind = "single-leg options are banned (OPT-5)" if len(legs) < 2 else f"{len(legs)} legs"
        return [f"OPT-3: a spread has exactly 2 legs ({kind})"], []
    out, parsed = [], []
    for leg in legs:
        sym = str(leg.get("symbol", ""))
        if not is_occ(sym):
            return [f"OPT-5: leg {sym!r} is not an OCC option (no equity legs)"], []
        parsed.append({**parse_occ(sym), "symbol": sym, "side": _leg_side(leg),
                       "intent": str(leg.get("position_intent", "")).lower(), "ratio": leg.get("ratio_qty", 1)})
    a, b = parsed
    for key, name in (("underlying", "underlying"), ("expiry", "expiry"), ("type", "type")):
        if a[key] != b[key]:
            out.append(f"OPT-3/OPT-5: mixed {name} ({a[key]} vs {b[key]})")
    if any(num(x["ratio"]) != 1 for x in parsed):
        out.append("OPT-3: ratio must be 1:1")
    if {a["side"], b["side"]} != {"long", "short"}:
        out.append("OPT-3: needs one long and one short leg (naked short or same-side legs)")
    if a["strike"] == b["strike"]:
        out.append("OPT-3: legs have the same strike")
    return out, parsed


def _intent_check(order: dict, parsed: list[dict]) -> tuple[list[str], str | None]:
    """Open orders use *_TO_OPEN on both legs, closes *_TO_CLOSE on both (OPT-3, OPT-15)."""
    intents = {x["intent"] for x in parsed}
    want = str(order.get("intent", "")).lower()
    if intents <= OPEN_INTENTS and len(intents) == 2:
        kind = "open"
    elif intents <= CLOSE_INTENTS and len(intents) == 2:
        kind = "close"
    else:
        return [f"OPT-3/OPT-15: leg intents {sorted(intents)} do not form one open or one close"], None
    if want and want != kind:
        return [f"order intent {want!r} does not match leg intents ({kind})"], None
    return [], kind


def _is_credit(parsed: list[dict]) -> bool:
    """A vertical is a credit spread when the short leg is nearer the money (OPT-3)."""
    short = next(x for x in parsed if x["side"] == "short")
    long = next(x for x in parsed if x["side"] == "long")
    return short["strike"] > long["strike"] if short["type"] == "put" else short["strike"] < long["strike"]


def _sign_check(order: dict, kind: str, credit: bool, width: float) -> list[str]:
    """OPT-14 sign: a credit entry sends a negative limit, a debit close a positive one; OPT-15 width cap."""
    lp = num(order.get("limit_price"))
    if lp is None or lp == 0:
        return ["OPT-14: limit_price missing or zero"]
    out = []
    if kind == "open":
        if credit and lp > 0:
            out.append("OPT-14: credit entry must have a negative limit_price")
        if not credit and lp < 0:
            out.append("OPT-14: debit entry must have a positive limit_price")
        if credit and -lp >= width:
            out.append("OPT-3: credit at or above the width is not a real spread price")
        if not credit and lp >= width:
            out.append("OPT-3: debit at or above the width is not a real spread price")
    elif credit:
        if lp < 0:
            out.append("OPT-14: debit close must have a positive limit_price")
        if lp > width + 1e-9:
            out.append(f"OPT-15: never pay more than the width ({width:g}) to close")
    else:  # closing a debit spread sells it: a credit, negative limit, never more than the width
        if lp > 0:
            out.append("OPT-14: closing a debit spread is a credit: limit_price must be negative")
        if -lp > width + 1e-9:
            out.append(f"OPT-3: a credit above the width ({width:g}) is not a real spread price")
    return out


def _mode_check(mode: str, underlying: str, credit: bool, typ: str, p: dict, gate_ok: bool) -> list[str]:
    """OPT-42 no live; OPT-1/OPT-41 paper needs enabled + gate; OPT-4/OPT-18 paper = SPY bull put credit only."""
    if mode not in MODES:
        return [f"unknown mode {mode!r}"]
    if mode == "live":
        return ["OPT-42: no live options under this rulebook"]
    if mode == "shadow":
        return []
    out = []
    if not p.get("enabled", False):
        out.append("OPT-1: options_book.enabled is false; shadow only")
    if not gate_ok:
        out.append("OPT-41: paper-start gate has not passed")
    if underlying not in p["underlyings"]:
        out.append(f"OPT-4: {underlying} is shadow-only; paper orders are {p['underlyings']} only")
    if typ != "put" or not credit:
        out.append("OPT-18: paper orders are bull put credit spreads only")
    return out


def _entry_checks(order, parsed, date, ledger, p, equity, cash, width, credit, *, cap_mult, blocks, quotes,
                  spot, mode) -> list[str]:
    """Book gates (OPT-31 halt, breaker/incident/freeze `blocks`), OPT-5 DTE floor, OPT-9 weekly cap,
    OPT-18 one spread per cycle, OPT-24 no add or second spread after a loss exit, OPT-8/OPT-9/OPT-10 caps."""
    lots, closed = _lots(ledger), _closed(ledger)
    out = [f"blocked: {b}" for b in (blocks or [])]
    if getattr(ledger, "halted", False):
        out.append("OPT-31: O is halted until the owner resets it")
    expiry, und = parsed[0]["expiry"], parsed[0]["underlying"]
    if date is None:
        out.append("OPT-5: date needed to check DTE")
    else:
        if dte(expiry, date) < int(p["min_dte_entry"]):
            out.append(f"OPT-5: DTE {dte(expiry, date)} below {p['min_dte_entry']}")
        wk = new_this_week(_every_lot(ledger), date, closed)
        if wk >= int(p["max_new_per_week"]):
            out.append(f"OPT-9: {wk} new spread(s) this week (max {p['max_new_per_week']})")
    syms = {x["symbol"] for x in parsed}
    for lot in lots:
        if {lot.short_leg.symbol, lot.long_leg.symbol} & syms:
            out.append(f"OPT-24: no adding to or rolling open spread {lot.lot_id}")
    why = cycle_blocked(expiry, _every_lot(ledger), closed, und)
    if why:
        out.append(why)
    return out + _size_checks(order, parsed, lots, p, equity, cash, width, credit, cap_mult=cap_mult,
                              quotes=quotes, spot=spot, mode=mode)


def _budget_per_contract(order, width, credit, p) -> float:
    """OPT-7/OPT-8 budgeted loss per contract from the strikes and the limit price (never below MaxLoss).

    Credit spread: MaxLoss = (width - credit) x 100; debit spread: MaxLoss = debit x 100. Plus the quoted cost
    and fees. A supplied `budgeted_loss_per_contract` can only raise it.
    """
    lp = num(order.get("limit_price"), 0.0)
    max_loss = (width + lp) * MULTIPLIER if credit else lp * MULTIPLIER  # credit: lp = -credit
    computed = max_loss + max(0.0, num(order.get("quoted_cost"), 0.0)) * MULTIPLIER \
        + 4 * max(0.0, float(p["fees_per_contract"]))
    supplied = num(order.get("budgeted_loss_per_contract"))
    return max(computed, supplied) if supplied is not None else computed


def _size_checks(order, parsed, lots, p, equity, cash, width, credit, *, cap_mult, quotes, spot, mode) -> list[str]:
    """OPT-8 per-trade cap (x OPT-31 cap_mult, clamped to 0..1), OPT-9 book budget, open count and assignment
    cover, OPT-10 greek caps, all from code-computed numbers."""
    eq = num(equity)
    if eq is None or eq <= 0:
        return ["OPT-8: equity unknown; cannot check size caps"]
    qty = int(num(order.get("qty"), 0) or 0)
    budget_pc = _budget_per_contract(order, width, credit, p)
    out = []
    mult = min(1.0, max(0.0, num(cap_mult, 0.0)))
    cap = float(p["max_budgeted_loss_per_trade_pct"]) * eq * mult
    if budget_pc <= 0 or qty > floor_int(cap / budget_pc):
        out.append(f"OPT-8: {qty} x budgeted loss {budget_pc:.2f} exceeds the per-trade cap {cap:.2f}")
    if open_budgeted_loss(lots) + qty * budget_pc > float(p["max_open_budgeted_loss_pct"]) * eq + 1e-9:
        out.append("OPT-9: open budgeted loss would exceed the book cap")
    if len(lots) + 1 > int(p["max_open_spreads"]):
        out.append(f"OPT-9: already {len(lots)} open spreads")
    if p.get("require_assignment_cover", True):
        short = next(x for x in parsed if x["side"] == "short")
        need = assignment_need(lots) + short["strike"] * MULTIPLIER * qty
        c = num(cash)
        if c is None or c < need - 1e-9:
            out.append(f"OPT-9: uncommitted cash {cash} does not cover assignment of {need:,.0f}")
    return out + _greek_checks(parsed, qty, lots, p, eq, quotes, spot, mode)


def _greek_checks(parsed, qty, lots, p, eq, quotes, spot, mode) -> list[str]:
    """OPT-10 delta-notional and short-vega caps with the new spread. Needs the legs' quotes and the spot;
    without them a paper order is rejected (a shadow order is not checked here: build_candidate checks it)."""
    s = num(spot)
    if quotes is None or s is None or s <= 0:
        return ["OPT-10: quotes and spot needed to check the greek caps"] if mode == "paper" else []
    qmap = {getattr(x, "symbol", None): x for x in quotes}
    short = next(x for x in parsed if x["side"] == "short")
    long = next(x for x in parsed if x["side"] == "long")
    sq, lq = qmap.get(short["symbol"]), qmap.get(long["symbol"])
    g = [num(getattr(x, a, None)) for x in (sq, lq) for a in ("delta", "vega")]
    if None in g:
        return ["OPT-10/OPT-27: a leg's delta or vega is missing"]
    greeks = {"delta": g[2] - g[0], "vega": g[3] - g[1]}
    notes: list[str] = []
    k = _cap_greeks(qty, greeks, lots, qmap, s, eq, p, notes)
    return [] if k >= qty else (notes or [f"OPT-10: greek caps allow {k} contracts, order has {qty}"])


def _close_checks(order, parsed, lots) -> list[str]:
    """A close must match an open lot's two legs and never exceed its contracts (that would open a new position)."""
    syms = {x["symbol"] for x in parsed}
    lot = next((l for l in lots if {l.short_leg.symbol, l.long_leg.symbol} == syms), None)
    if lot is None:
        return ["OPT-15: close does not match an open spread in O's ledger"]
    out = []
    for x in parsed:
        leg = lot.short_leg if x["symbol"] == lot.short_leg.symbol else lot.long_leg
        if x["side"] != leg.side:
            out.append(f"OPT-3: close would flip {x['symbol']} instead of closing it")
    if int(num(order.get("qty"), 0) or 0) > int(lot.contracts):
        out.append(f"OPT-3: close qty {order.get('qty')} exceeds the lot's {lot.contracts} contracts")
    return out


def validate_spread_order(order: dict, ledger, policy: dict | None, *, mode: str = "shadow", date=None,
                          equity=None, uncommitted_cash=None, gate_ok: bool = False, cap_mult: float = 1.0,
                          blocks=(), quotes=None, spot=None) -> tuple[bool, list[str]]:
    """Check one book O order against every order rule. Returns (ok, reasons); ok is True only with no reasons.

    mode: "shadow" (any underlying and vertical type allowed, OPT-39 variants), "paper" (needs
    `options_book.enabled`, `gate_ok` from OPT-41, SPY, bull put credit spread) or "live" (always rejected, OPT-42).
    Paper closes need `enabled` and `gate_ok` too (non-negotiable 2: no order while O is disabled).
    `date`, `equity` and `uncommitted_cash` are needed for entries (DTE and size caps); missing ones reject.
    Entry-only inputs: `cap_mult` (OPT-31, from breaker_status; clamped to 0..1), `blocks` (breaker, incident
    or OPT-15 freeze reasons; any reject), `quotes` and `spot` (OPT-10 greek caps; required in paper mode).
    An OptionsBook ledger also brings the OPT-31 halt latch, closed records (OPT-18/OPT-24) and the week count.
    """
    p = ob_policy(policy)
    if not isinstance(order, dict):
        return False, ["order is not a dict"]
    reasons = _order_basics(order, p)
    shape, parsed = _leg_shape(order)
    reasons += shape
    if shape:
        return False, reasons
    why, kind = _intent_check(order, parsed)
    reasons += why
    if kind is None:
        return False, reasons
    credit = _is_credit(parsed)
    width = abs(parsed[0]["strike"] - parsed[1]["strike"])
    reasons += _sign_check(order, kind, credit, width)
    lots = _lots(ledger)
    if kind == "open":
        reasons += _mode_check(mode, parsed[0]["underlying"], credit, parsed[0]["type"], p, gate_ok)
        reasons += _entry_checks(order, parsed, date if date is None else to_date(date), ledger, p, equity,
                                 uncommitted_cash, width, credit, cap_mult=cap_mult, blocks=blocks, quotes=quotes,
                                 spot=spot, mode=mode)
    else:
        if mode not in MODES:
            reasons.append(f"unknown mode {mode!r}")
        if mode == "live":
            reasons.append("OPT-42: no live options under this rulebook")
        if mode == "paper":
            if not p.get("enabled", False):
                reasons.append("OPT-1: options_book.enabled is false; no paper orders (closes included)")
            if not gate_ok:
                reasons.append("OPT-41: paper-start gate has not passed")
        reasons += _close_checks(order, parsed, lots)
    return not reasons, reasons


def spread_order(candidate: dict, *, intent: str = "open", qty: int | None = None, limit_price: float | None = None,
                 client_order_id: str = "OPT-") -> dict:
    """Build the order dict for a candidate (open) or a lot-like candidate (close) in the shape above.

    Opening a bull put spread: sell_to_open the short, buy_to_open the long, negative limit (credit).
    Closing: buy_to_close the short, sell_to_close the long, positive limit (debit).
    """
    s, lg = candidate["short"], candidate["long"]
    opening = intent == "open"
    legs = [{"symbol": s["symbol"], "side": "sell" if opening else "buy",
             "position_intent": "sell_to_open" if opening else "buy_to_close", "ratio_qty": 1},
            {"symbol": lg["symbol"], "side": "buy" if opening else "sell",
             "position_intent": "buy_to_open" if opening else "sell_to_close", "ratio_qty": 1}]
    lp = candidate.get("limit_price") if limit_price is None else limit_price
    return {"legs": legs, "qty": int(qty if qty is not None else candidate.get("contracts", 0)),
            "limit_price": lp, "intent": intent, "order_class": "mleg", "type": "limit",
            "time_in_force": "day", "extended_hours": False, "client_order_id": client_order_id,
            "budgeted_loss_per_contract": candidate.get("budgeted_loss_per_contract"),
            "quoted_cost": candidate.get("quoted_cost")}
