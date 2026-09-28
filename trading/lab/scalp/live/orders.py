"""The order builder: the ONLY place an OrderSpec is made (MT-G21, MT-G16, MT-G25).

- Every order is a LIMIT order with a positive limit price. There is no function here (or anywhere in the
  package) that can make a market, stop or stop-market order; the stop-loss of a bracket is a stop-LIMIT.
- Entries are long-only brackets: a marketable buy limit at ask + min($0.02, 0.05% x ask) (rounded DOWN to the
  cent, so the collar is never exceeded), a take-profit limit and a stop-limit, all fixed before submission from
  the candidate and the frozen registration (MT-G16). Short entries are refused (SHORT_DISABLED).
- Exits are plain sell limits at bid x (1 - collar), rounded UP to the cent (never more aggressive than the
  collar). With no usable quote the last trade is used with a collar of at least 0.5% and the order says
  NO_QUOTE: exits always go out (MT-G38).
- Client order ids are deterministic (MT-G25): the same setup, version, date, signal bar, leg and attempt always
  give the same id, so a retry of one attempt can never become a second order; a resend uses attempt + 1.
Money is rounded with Decimal so no float drift ever turns $651.23 into $651.2299999.
"""
from __future__ import annotations

import hashlib
import math
import re
from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any

import pandas as pd

from . import config as C
from . import sizing
from .model import Candidate, Kind, Lane, OrderSpec, Quote, Reason, as_ny

LEGS = {"E": "entry parent", "X": "exit", "P": "protect", "K": "kill switch", "W": "watchdog"}
BOT_CODE = "BOT"          # orders not owned by one setup (kill switch or watchdog flattening the whole book)
MAX_ATTEMPT = 999
CENT = Decimal("0.01")
_CID = re.compile(r"^SCALP-([A-Z0-9]{2,8})-(\d{6})-(\d{4})-([EXPKW])(\d{1,3})-([0-9a-f]{6})$")


# ------------------------------------------------------------------------------------------------ rounding
def _cents(x: float, mode: str) -> float:
    if not math.isfinite(x):
        raise ValueError(f"not a price: {x}")
    # repr() gives the shortest decimal that round-trips, so 651.23 stays 651.23 before rounding
    return float(Decimal(repr(float(x))).quantize(CENT, rounding=mode))


def round_down_cent(x: float) -> float:
    return _cents(x, ROUND_FLOOR)


def round_up_cent(x: float) -> float:
    return _cents(x, ROUND_CEILING)


def round_cent(x: float) -> float:
    return _cents(x, ROUND_HALF_UP)


# ------------------------------------------------------------------------------------------------ client ids
def _code(setup_id: str | None) -> str:
    if not setup_id:
        return BOT_CODE
    if setup_id not in C.SETUP_CODES:
        raise ValueError(f"no order-id code for setup {setup_id!r}")
    return C.SETUP_CODES[setup_id]


def client_id(setup_id: str | None, version: int, session_date: date, bar_start: pd.Timestamp, leg: str,
              attempt: int) -> str:
    """SCALP-{CODE}-{YYMMDD}-{HHMM}-{leg}{attempt}-{h6}; h6 = first 6 hex of sha256 of all the inputs.
    setup_id None/"" = a bot-level order (kill switch, watchdog) with code BOT."""
    if leg not in LEGS:
        raise ValueError(f"unknown leg {leg!r}")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or not 0 <= attempt <= MAX_ATTEMPT:
        raise ValueError(f"attempt must be an int 0..{MAX_ATTEMPT}")
    code = _code(setup_id)
    bs = as_ny(bar_start)
    key = "|".join([setup_id or "", str(int(version)), session_date.isoformat(), bs.isoformat(), leg, str(attempt)])
    h6 = hashlib.sha256(key.encode()).hexdigest()[:6]
    return f"{C.ORDER_PREFIX}{code}-{session_date:%y%m%d}-{bs:%H%M}-{leg}{attempt}-{h6}"


def parse_client_id(cid: str) -> dict[str, Any] | None:
    """Fields of a SCALP- id, or None for anything else (a non-SCALP order is a reconcile mismatch)."""
    m = _CID.match(cid or "")
    if not m:
        return None
    code, ymd, hhmm, leg, attempt, h6 = m.groups()
    by_code = {v: k for k, v in C.SETUP_CODES.items()}
    if code != BOT_CODE and code not in by_code:
        return None
    try:
        d = pd.Timestamp(f"20{ymd}").date()
    except ValueError:
        return None
    return {"code": code, "setup_id": by_code.get(code), "session_date": d, "hhmm": hhmm, "leg": leg,
            "attempt": int(attempt), "h6": h6}


# ------------------------------------------------------------------------------------------------ entries
def entry_bracket(candidate: Candidate, reg, quote: Quote | None, e0: float, session_date: date, attempt: int
                  ) -> tuple[OrderSpec | None, list[Reason], dict[str, Any]]:
    """Build the long entry bracket for a candidate, or say why not. Returns (spec or None, reasons, numbers):
    every reason that applies is listed; `numbers` holds every value used (journal and MT-G33 size check)."""
    if candidate.action != "enter":
        raise ValueError("entry_bracket takes entry candidates only (exits use exit_limit)")
    reasons: list[Reason] = []
    info: dict[str, Any] = {"e0": e0, "attempt": attempt, "side": candidate.side}
    if candidate.side != 1:
        reasons.append(Reason.SHORT_DISABLED)
        return None, reasons, info
    if candidate.symbol not in C.ALLOWED_SYMBOLS:
        reasons.append(Reason.SYMBOL_NOT_ALLOWED)
    if reg is None or reg.setup_id != candidate.setup_id or reg.symbol != candidate.symbol:
        reasons.append(Reason.SETUP_NOT_REGISTERED)
        return None, reasons, info
    if quote is None or not quote.valid:
        reasons.append(Reason.NO_QUOTE)
        return None, reasons, info
    bid, ask = float(quote.bid), float(quote.ask)
    info.update(bid=bid, ask=ask, mid=quote.mid, spread=quote.spread, bid_size=quote.bid_size,
                ask_size=quote.ask_size, quote_ts=quote.ts, quote_feed=quote.feed)
    collar = min(C.ENTRY_COLLAR_USD, C.ENTRY_COLLAR_PCT * ask)
    limit = round_down_cent(ask + collar)
    info.update(collar=collar, limit=limit)

    # stop: the setup's own level, else its distance from the limit, else the registered overlay (MT-G16)
    stop, stop_src = None, None
    if candidate.stop is not None:
        stop, stop_src = float(candidate.stop), "setup"
    elif candidate.stop_dist is not None:
        stop, stop_src = limit - float(candidate.stop_dist), "setup_dist"
    elif reg.overlay_stop_pct is not None:
        stop, stop_src = limit * (1.0 - reg.overlay_stop_pct), "overlay"
    if stop is None or not math.isfinite(stop) or stop <= 0:
        info["stop_source"] = stop_src or "missing"
        reasons.append(Reason.INVALID_STOP)
        return None, reasons, info
    stop = round_down_cent(stop)
    dist = limit - stop
    stop_limit = round_down_cent(stop - max(C.STOP_LIMIT_MIN_USD, C.STOP_LIMIT_FRAC * dist))
    info.update(stop=stop, stop_source=stop_src, stop_limit=stop_limit)
    if stop >= bid or stop >= limit or stop_limit <= 0:
        reasons.append(Reason.INVALID_STOP)

    # target: absolute, else R multiple of the limit-to-stop distance, else a distance, else the overlay
    target, tgt_src = None, None
    if candidate.target is not None:
        target, tgt_src = float(candidate.target), "setup"
    elif candidate.target_r is not None:
        target, tgt_src = limit + float(candidate.target_r) * dist, "setup_r"
    elif candidate.target_dist is not None:
        target, tgt_src = limit + float(candidate.target_dist), "setup_dist"
    elif reg.overlay_target_pct is not None:
        target, tgt_src = limit * (1.0 + reg.overlay_target_pct), "overlay"
    info["target_source"] = tgt_src or "missing"
    if target is None or not math.isfinite(target):
        reasons.append(Reason.TARGET_TOO_CLOSE)       # no target = no bracket = no entry (MT-G16)
        return None, reasons, info
    target = round_cent(target)
    info["target"] = target
    if target <= limit + 0.01 + 1e-9:
        reasons.append(Reason.TARGET_TOO_CLOSE)

    q = sizing.qty(e0, limit, stop, stop_limit, reg.lane)
    info.update(qty=q, risk_per_share=round(limit - stop_limit, 6), risk_usd=round(q * (limit - stop_limit), 6),
                notional=round(q * limit, 6), lane=Lane(reg.lane).value)
    if q < 1:
        reasons.append(Reason.SIZE_ZERO)
    if reasons:
        return None, reasons, info
    cid = client_id(candidate.setup_id, reg.version, session_date, candidate.bar_start, "E", attempt)
    spec = OrderSpec(client_order_id=cid, symbol=candidate.symbol, side="buy", qty=int(q), kind=Kind.ENTRY,
                     limit_price=limit, order_class="bracket", take_profit=target, stop_price=stop,
                     stop_limit_price=stop_limit, setup_id=candidate.setup_id, version=reg.version,
                     reason=candidate.reason, tif="day", extended_hours=False)
    _checked(spec)
    return spec, [], info


# ------------------------------------------------------------------------------------------------ exits
def exit_limit(symbol: str, qty: int, quote: Quote | None, last_price: float | None, collar: float, kind: Kind,
               *, setup_id: str | None, version: int, session_date: date, bar_start: pd.Timestamp, leg: str,
               attempt: int, reason: str = "") -> OrderSpec:
    """A closing SELL limit for a long position (EXIT or PROTECT; never gated, MT-G38). Price =
    round_up_cent(bid x (1 - collar)); with no valid quote, last_price x (1 - max(collar, 0.5%)) and the reason
    carries NO_QUOTE. Raises ValueError only when there is no price at all (the caller escalates to the kill
    switch, which uses the position's own mark)."""
    kind = Kind(kind)
    if kind is Kind.ENTRY:
        raise ValueError("exit_limit makes EXIT or PROTECT orders only")
    if leg == "E":
        raise ValueError("leg E is for entry parents")
    if isinstance(qty, bool) or int(qty) != qty or qty < 1:
        raise ValueError(f"qty must be a whole number >= 1, got {qty!r}")
    if not 0 <= collar < 0.5:
        raise ValueError(f"collar out of range: {collar}")
    tags = [reason] if reason else []
    if quote is not None and quote.valid:
        px = round_up_cent(float(quote.bid) * (1.0 - collar))
    else:
        if last_price is None or not math.isfinite(last_price) or last_price <= 0:
            raise ValueError("no quote and no last price: cannot price an exit limit")
        px = round_up_cent(float(last_price) * (1.0 - max(collar, 0.005)))
        tags.append(Reason.NO_QUOTE.value)
    px = max(px, 0.01)
    cid = client_id(setup_id, version, session_date, bar_start, leg, attempt)
    spec = OrderSpec(client_order_id=cid, symbol=symbol, side="sell", qty=int(qty), kind=kind, limit_price=px,
                     order_class="simple", setup_id=setup_id or "", version=int(version), reason="|".join(tags),
                     tif="day", extended_hours=False)
    return _checked(spec)


# ------------------------------------------------------------------------------------------------ checks
def _checked(spec: OrderSpec) -> OrderSpec:
    problems = validate(spec)
    if problems:
        raise ValueError(f"order builder produced a bad spec: {problems}")
    return spec


def validate(spec: OrderSpec) -> list[str]:
    """Problems with a spec (empty = fine). The broker and the guard call this again before sending."""
    p: list[str] = []
    if not spec.client_order_id.startswith(C.ORDER_PREFIX) or parse_client_id(spec.client_order_id) is None:
        p.append("client id is not a SCALP- id")
    if spec.kind is Kind.ENTRY and spec.symbol not in C.ALLOWED_SYMBOLS:
        p.append("symbol not allowed")          # exits may close anything found in the account (kill switch)
    if spec.side not in ("buy", "sell"):
        p.append("bad side")
    if isinstance(spec.qty, bool) or not isinstance(spec.qty, int) or spec.qty < 1:
        p.append("qty must be an int >= 1")
    if not (isinstance(spec.limit_price, (int, float)) and math.isfinite(spec.limit_price) and spec.limit_price > 0):
        p.append("limit price must be positive")
    if spec.tif != "day" or spec.extended_hours:
        p.append("day orders in regular hours only")
    if spec.order_class == "bracket":
        if spec.kind is not Kind.ENTRY or spec.side != "buy":
            p.append("brackets are long entries only")
        tp, sp, sl = spec.take_profit, spec.stop_price, spec.stop_limit_price
        if tp is None or sp is None or sl is None:
            p.append("bracket needs take-profit, stop and stop-limit")
        elif not (0 < sl <= sp < spec.limit_price < tp):
            p.append("bracket prices out of order")
    elif spec.order_class == "simple":
        if spec.kind is Kind.ENTRY:
            p.append("entries are brackets only (MT-G16)")
        if spec.take_profit is not None or spec.stop_price is not None or spec.stop_limit_price is not None:
            p.append("simple orders carry no legs")
    else:
        p.append("unknown order class")
    return p
