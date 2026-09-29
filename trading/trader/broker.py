"""Brokers: Alpaca paper trading, or a local simulator for dry runs and tests.

EX-1: stock and ETF orders are DAY market orders (sent after the close, they fill at the next open);
crypto orders are GTC. EX-2: every order is a market order, so exits always go out as market orders.
EX-4: `order_fills` reports what really filled (quantity, average price, date) so the ledger books lots at
fill prices, not at the signal close. It replaces the rulebook's `fills_since()` (Implementation plan phase 1,
item 4): looking up each pending order by its client id also catches partial fills on orders still open.

Book O (reports/Options rulebook.md, phase O4) shares the rules book's paper account (owner decision 6), so
`cancel_open_orders(prefixes=...)` cancels only one book's orders. The options additions (`submit_mleg`,
`mleg_fills`, `positions_detail`, `option_activities`, `options_account`, and `submit_single` for the OPT-26
clean-up sells) are used only by `trader/options/run.py`; `submit_mleg` and `submit_single` refuse unless O is
enabled, the OPT-41 gate passed and the host is paper.
"""
from __future__ import annotations

import math
import os
import secrets
from typing import Any, Protocol

import pandas as pd

from .models import Order
from .options.models import is_occ, parse_occ

NY = "America/New_York"
# Statuses after which an order can no longer fill (a partial fill stays filled).
FINAL_STATUSES = frozenset({"filled", "canceled", "expired", "rejected", "done_for_day", "replaced"})
MAX_CLIENT_ID = 48
SIM_CLOSED_KEEP = 500  # closed simulator orders kept in state, newest last


class Broker(Protocol):
    name: str

    def account(self) -> tuple[float, float]:
        """(equity, cash)"""

    def positions(self) -> dict[str, float]: ...

    def cancel_open_orders(self, prefixes: Any = None) -> list[str] | None:
        """Prefixes cancel only this book's orders (owner decision 6). None cancels every open order in the
        simulator; the Alpaca broker refuses None unless `all_orders=True` (its account is shared with O)."""

    def submit(self, orders: list[Order], client_prefix: str, *, date: Any = None,
               suffix: str | None = None) -> list[dict]:
        """`date` is the signal date (the simulator needs it; Alpaca ignores it)."""

    def order_fills(self, pending: list[dict]) -> list[dict]: ...


# --- shared helpers -------------------------------------------------------------------------------


def time_in_force(symbol: str) -> str:
    """EX-1: crypto trades around the clock (GTC); fractional stock orders must be DAY."""
    return "gtc" if "/" in symbol else "day"


def new_suffix() -> str:
    """Short random tag so a --force rerun on the same date never reuses a client order id."""
    return secrets.token_hex(3)


def make_client_order_id(prefix: str, symbol: str, side: str, n: int, suffix: str = "") -> str:
    """`{prefix}-{SYM}-{side}-{n}-{suffix}`, at most 48 characters; only the prefix is shortened.

    Symbol, side and suffix are capped so the tail (which holds the unique `n`) always fits whole.
    """
    sym = _alnum(symbol)[:12].upper()
    tail = f"-{sym}-{_alnum(side)[:4]}-{n}" + (f"-{_alnum(suffix)[:8]}" if _alnum(suffix) else "")
    head = str(prefix or "")[: max(0, MAX_CLIENT_ID - len(tail))]
    return (head + tail)[-MAX_CLIENT_ID:].lstrip("-")


def _alnum(x: Any) -> str:
    return "".join(ch for ch in str(x or "") if ch.isalnum())


def assign_client_ids(orders: list[Order], prefix: str, suffix: str) -> list[str]:
    """One id per order, unique within the call. An order's own client_order_id is used when set and unused."""
    used: set[str] = set()
    ids = []
    for n, o in enumerate(orders, start=1):
        cid = o.client_order_id
        if not cid or cid in used:
            cid, k = make_client_order_id(prefix, o.symbol, o.side, n, suffix), n
            while cid in used:
                k += len(orders)
                cid = make_client_order_id(prefix, o.symbol, o.side, k, suffix)
        used.add(cid)
        ids.append(cid)
    return ids


def order_problem(o: Order) -> str | None:
    """Why an order must not be sent (checked before any broker call), or None."""
    if not o.symbol:
        return "missing symbol"
    if is_occ(o.symbol):
        return "OPT-2: the stock path never sends option (OCC) symbols"
    if o.side not in ("buy", "sell"):
        return f"unknown side {o.side!r}"
    if not _finite(o.qty) or float(o.qty) <= 0:
        return f"quantity must be positive, got {o.qty}"
    return None


def status_str(status: Any) -> str:
    """Broker status (enum or text) -> lowercase text such as 'filled'."""
    if status is None:
        return ""
    text = str(getattr(status, "value", status)).lower()
    return text.split(".", 1)[1] if text.startswith("orderstatus.") else text


def fill_row(client_order_id: str, status: str, *, filled_qty: float = 0.0, filled_avg_price: float | None = None,
             filled_at: str | None = None, **extra) -> dict:
    """The one fill shape both brokers return (EX-4)."""
    qty = float(filled_qty) if _finite(filled_qty) and float(filled_qty) > 0 else 0.0
    price = float(filled_avg_price) if qty > 0 and _finite(filled_avg_price) and float(filled_avg_price) > 0 else None
    row = {"client_order_id": client_order_id, "status": status,
           "final": status in FINAL_STATUSES or status == "unknown",
           "filled_qty": qty, "filled_avg_price": price, "filled_at": filled_at if qty > 0 else None}
    row.update(extra)
    return row


def ny_date(ts: Any) -> str | None:
    """Timestamp -> 'YYYY-MM-DD' in New York time.

    A naive timestamp with a time of day is taken as UTC (the broker's clock); a bare date is already a day
    and is returned unchanged.
    """
    if ts is None:
        return None
    try:
        t = pd.Timestamp(ts)
    except (TypeError, ValueError):
        return None
    if pd.isna(t):
        return None
    if t.tzinfo is None:
        if t == t.normalize():
            return t.date().isoformat()
        t = t.tz_localize("UTC")
    return t.tz_convert(NY).date().isoformat()


def _ny_naive(ts: Any) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    return t.tz_convert(NY).tz_localize(None) if t.tzinfo is not None else t


def _finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _num(x: Any) -> float | None:
    return float(x) if _finite(x) else None


def _get(obj: Any, attr: str) -> Any:
    return obj.get(attr) if isinstance(obj, dict) else getattr(obj, attr, None)


def _int_or_none(x: Any) -> int | None:
    v = _num(x)
    return int(v) if v is not None else None


def clean_prefixes(prefixes: Any) -> tuple[str, ...]:
    """Owner decision 6: the client-id prefixes a book owns. A bare string is one prefix; blanks are dropped
    (an empty prefix would match every order in the shared account)."""
    if isinstance(prefixes, str):
        prefixes = [prefixes]
    return tuple(str(p) for p in (prefixes or []) if str(p or "").strip())


# --- book O (options) order checks ------------------------------------------------------------------

PAPER_HOST = "paper-api.alpaca.markets"
OPTION_ACTIVITY_TYPES = ("OPASN", "OPEXC", "OPEXP")
_OPEN_INTENTS = ("buy_to_open", "sell_to_open")
_CLOSE_INTENTS = ("buy_to_close", "sell_to_close")
MLEG_MIN_OPEN_DTE = 1  # the broker lock never opens a 0DTE or expired spread; options.risk applies OPT-5's 25


def mleg_problems(order: dict, *, enabled: bool, gate_ok: bool, paper: bool, prefix: str = "OPT-",
                  today: Any = None, min_open_dte: int = MLEG_MIN_OPEN_DTE) -> list[str]:
    """Why this mleg order must not be sent (a second lock after options.risk): OPT-1 enabled and paper host,
    OPT-41 gate, OPT-42 no live, OPT-3 two OCC legs 1:1 on one root, expiry and type (a vertical) with different
    strikes and matching intents, OPT-14 LIMIT/DAY/whole contracts and the sign (open a credit spread = negative
    limit, close it = positive limit), owner decision 6 prefix. With `today`, an open whose expiry is fewer than
    `min_open_dte` calendar days away (0DTE, expired) is refused too (OPT-5 floor; options.risk holds the full
    policy floor, this lock only stops the worst case if a caller ever skips it)."""
    out = []
    if not enabled:
        out.append("OPT-1: options_book.enabled is false; no orders")
    if not gate_ok:
        out.append("OPT-41: paper-start gate has not passed")
    if not paper:
        out.append("OPT-1/OPT-42: refusing a non-paper base URL")
    if not str(order.get("client_order_id") or "").startswith(prefix or "OPT-"):
        out.append(f"owner decision 6: client_order_id must start with {prefix!r}")
    if str(order.get("type", "limit")).lower() != "limit" or str(order.get("time_in_force", "day")).lower() != "day":
        out.append("OPT-14: LIMIT and DAY only")
    if order.get("extended_hours"):
        out.append("OPT-14: no extended hours")
    q = _num(order.get("qty"))
    if q is None or q <= 0 or q != math.floor(q):
        out.append("OPT-14: qty must be a whole number of contracts > 0")
    return out + _mleg_leg_problems(order, today=today, min_open_dte=min_open_dte)


def _mleg_shape_problems(legs: list, *, opening: bool, today: Any, min_open_dte: int) -> list[str]:
    """OPT-3: both legs are OCC option symbols on the same root, expiry and type, at different strikes;
    OPT-5: an open is not 0DTE or expired (when `today` is known)."""
    syms = [str(l.get("symbol") or "") for l in legs]
    bad = [s for s in syms if not is_occ(s)]
    if bad:
        return [f"OPT-3: leg symbol {bad[0]!r} is not an OCC option symbol"]
    a, b = (parse_occ(s) for s in syms)
    out = []
    if a["underlying"] != b["underlying"]:
        out.append("OPT-3: legs must share one underlying")
    if a["expiry"] != b["expiry"]:
        out.append("OPT-3: legs must share one expiry")
    if a["type"] != b["type"]:
        out.append("OPT-3: legs must be the same type (put/put or call/call)")
    if a["strike"] == b["strike"]:
        out.append("OPT-3: legs must have different strikes")
    if opening and today is not None:
        try:
            days = (pd.Timestamp(a["expiry"]).date() - pd.Timestamp(today).date()).days
        except (TypeError, ValueError):
            days = None
        if days is None or days < max(1, int(min_open_dte)):
            out.append(f"OPT-5: opening a spread {days} days before expiry (floor {max(1, int(min_open_dte))})")
    return out


def _mleg_leg_problems(order: dict, *, today: Any = None, min_open_dte: int = MLEG_MIN_OPEN_DTE) -> list[str]:
    legs = order.get("legs") or []
    if len(legs) != 2:
        return ["OPT-3: exactly 2 legs"]
    intents0 = {str(l.get("position_intent", "")).lower() for l in legs}
    shape = _mleg_shape_problems(legs, opening=intents0 == set(_OPEN_INTENTS), today=today,
                                 min_open_dte=min_open_dte)
    if shape:
        return shape
    for l in legs:  # the side sent must agree with the intent both locks judged (buy_to_* = buy, sell_to_* = sell)
        s, i = str(l.get("side") or "").lower(), str(l.get("position_intent") or "").lower()
        if s not in ("buy", "sell") or not i.startswith(s + "_"):
            return [f"OPT-3: leg side {s!r} does not match position_intent {i!r}"]
    intents = {str(l.get("position_intent", "")).lower() for l in legs}
    if any(_num(l.get("ratio_qty", 1)) != 1 for l in legs):
        return ["OPT-3: ratio must be 1:1"]
    lp = _num(order.get("limit_price"))
    if lp is None or lp == 0:
        return ["OPT-14: limit_price missing or zero"]
    intent = str(order.get("intent") or "").lower()
    # Paper orders are bull put credit spreads only (options.risk), so an open is a credit and a close a debit.
    if intents == set(_OPEN_INTENTS):
        if intent not in ("", "open"):
            return ["order intent does not match its *_TO_OPEN legs"]
        return [] if lp < 0 else ["OPT-14: opening a credit spread needs a negative limit_price"]
    if intents == set(_CLOSE_INTENTS):
        if intent not in ("", "close"):
            return ["order intent does not match its *_TO_CLOSE legs"]
        return [] if lp > 0 else ["OPT-14: closing a credit spread needs a positive limit_price"]
    return ["OPT-3: leg intents must be one *_TO_OPEN pair or one *_TO_CLOSE pair"]


def single_problems(order: dict, *, enabled: bool, gate_ok: bool, paper: bool, prefix: str = "OPT-") -> list[str]:
    """Why an OPT-26 clean-up order must not be sent. Only two kinds exist: SELL O's assigned stock (whole shares)
    or SELL_TO_CLOSE an orphan long option. Both are LIMIT DAY, paper only, enabled + gate, `OPT-` prefix.
    Nothing here can open a position or create short stock."""
    out = []
    if not enabled:
        out.append("OPT-1: options_book.enabled is false; no orders")
    if not gate_ok:
        out.append("OPT-41: paper-start gate has not passed")
    if not paper:
        out.append("OPT-1/OPT-42: refusing a non-paper base URL")
    if not str(order.get("client_order_id") or "").startswith(prefix or "OPT-"):
        out.append(f"owner decision 6: client_order_id must start with {prefix!r}")
    if str(order.get("type", "limit")).lower() != "limit" or str(order.get("time_in_force", "day")).lower() != "day":
        out.append("OPT-14: LIMIT and DAY only")
    if order.get("extended_hours"):
        out.append("OPT-14: no extended hours")
    q = _num(order.get("qty"))
    if q is None or q <= 0 or q != math.floor(q):
        out.append("OPT-26: qty must be a whole number > 0")
    lp = _num(order.get("limit_price"))
    if lp is None or lp <= 0:
        out.append("OPT-26: limit_price must be positive")
    if str(order.get("side", "")).lower() != "sell":
        out.append("OPT-26: clean-up orders only sell (O's stock, or an orphan long option)")
    sym = str(order.get("symbol") or "")
    if not sym:
        out.append("OPT-26: symbol missing")
    occ = len(sym) > 15 and sym[-9] in "CP" and sym[-8:].isdigit()
    if occ and str(order.get("position_intent", "")).lower() != "sell_to_close":
        out.append("OPT-26: an option clean-up order must be SELL_TO_CLOSE")
    if not occ and order.get("position_intent"):
        out.append("OPT-26: a stock clean-up order carries no position intent")
    return out


def _single_request(order: dict):
    """alpaca-py LimitOrderRequest for one OPT-26 clean-up order (stock sale or SELL_TO_CLOSE option)."""
    from alpaca.trading.enums import OrderSide, PositionIntent, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest

    kw = {}
    if order.get("position_intent"):
        kw["position_intent"] = PositionIntent(str(order["position_intent"]).lower())
    return LimitOrderRequest(symbol=str(order["symbol"]), qty=int(order["qty"]), side=OrderSide.SELL,
                             time_in_force=TimeInForce.DAY, limit_price=round(float(order["limit_price"]), 2),
                             client_order_id=str(order["client_order_id"]), extended_hours=False, **kw)


def _mleg_request(order: dict):
    """alpaca-py LimitOrderRequest with OrderClass.MLEG and one OptionLegRequest per leg (ratio 1)."""
    from alpaca.trading.enums import OrderClass, OrderSide, PositionIntent, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

    legs = []
    for l in order["legs"]:
        pi = PositionIntent(str(l["position_intent"]).lower())
        # The side comes from the intent (never a missing/mismatched 'side' field defaulting to SELL).
        side = OrderSide.BUY if pi.value.startswith("buy_") else OrderSide.SELL
        legs.append(OptionLegRequest(symbol=l["symbol"], ratio_qty=1, side=side, position_intent=pi))
    return LimitOrderRequest(qty=int(order["qty"]), order_class=OrderClass.MLEG, time_in_force=TimeInForce.DAY,
                             limit_price=round(float(order["limit_price"]), 2), legs=legs,
                             client_order_id=str(order["client_order_id"]), extended_hours=False)


def _is_not_found(e: Exception) -> bool:
    """Alpaca's own "order not found" answer (code 40410000). Any other 404 (a wrong URL, a proxy error page)
    proves nothing about the order, so it must not end a pending order."""
    try:
        if str(getattr(e, "code", "")) == "40410000":
            return True
    except Exception:  # APIError.code parses the body as JSON and raises on anything else
        pass
    text = str(e).lower()
    return "40410000" in text or "order not found" in text


# --- Alpaca ---------------------------------------------------------------------------------------


class AlpacaPaperBroker:
    """Alpaca paper account (the client is always created with paper=True)."""

    name = "alpaca-paper"

    def __init__(self, key: str, secret: str, crypto_symbols: list[str], *, client: Any = None):
        if client is None:
            from alpaca.trading.client import TradingClient

            client = TradingClient(key, secret, paper=True)
        self._client = client
        # Alpaca reports crypto positions as "BTCUSD"; orders use "BTC/USD".
        self._crypto = {s.replace("/", ""): s for s in crypto_symbols}

    @classmethod
    def for_book(cls, book: str, crypto_symbols: list[str]) -> "AlpacaPaperBroker":
        key = os.environ.get(f"ALPACA_{book.upper()}_KEY")
        secret = os.environ.get(f"ALPACA_{book.upper()}_SECRET")
        if not key or not secret:
            raise RuntimeError(f"Set ALPACA_{book.upper()}_KEY and ALPACA_{book.upper()}_SECRET, or use --sim.")
        return cls(key, secret, crypto_symbols)

    def account(self) -> tuple[float, float]:
        a = self._client.get_account()
        return float(a.equity), float(a.cash)

    def positions(self) -> dict[str, float]:
        out = {}
        for p in self._client.get_all_positions():
            sym = self._crypto.get(p.symbol, p.symbol)
            out[sym] = float(p.qty)
        return out

    def cancel_open_orders(self, prefixes: Any = None, *, all_orders: bool = False) -> list[str] | None:
        """Cancel open orders.

        With prefixes (owner decision 6, shared account) only orders whose client_order_id starts with one of
        them are cancelled, one by one, so a book never cancels another book's orders. An empty list cancels
        nothing. Returns the cancelled client ids; failures are kept in `last_cancel_errors` (the next
        `order_fills` shows what really happened to those orders).

        Cancelling every order in the account (O's `OPT-` orders included) needs an explicit `all_orders=True`;
        a call with no prefixes and no flag raises instead of silently breaching decision 6.
        """
        if prefixes is None:
            if not all_orders:
                raise ValueError("cancel_open_orders needs prefixes (owner decision 6: the paper account is "
                                 "shared with book O); pass all_orders=True to cancel every open order")
            self._client.cancel_orders()
            return None
        wanted = clean_prefixes(prefixes)
        self.last_cancel_errors: list[str] = []
        if not wanted:
            return []
        done = []
        for o in self._open_orders():
            cid = str(_get(o, "client_order_id") or "")
            if not cid.startswith(wanted):
                continue
            try:
                self._client.cancel_order_by_id(str(_get(o, "id")))
                done.append(cid)
            except Exception as e:  # already filled or cancelled: settle it next run
                self.last_cancel_errors.append(f"{cid}: {e}")
        return done

    def _open_orders(self) -> list:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        return list(self._client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, limit=500)) or [])

    # --- book O (options) additions: read-only views, and an mleg submit gated by OPT-1/OPT-41 -----------

    def is_paper(self) -> bool:
        """OPT-1: True only when the client talks to Alpaca's paper host. Unknown hosts count as not paper."""
        base = getattr(self._client, "_base_url", None)
        return PAPER_HOST in str(getattr(base, "value", base) or "")

    def options_account(self) -> dict:
        """OPT-6/OPT-27 inputs: equity, cash, maintenance margin, option levels and the account configuration.

        Never raises: a failed read leaves the field None and adds a line to `problems` (the checks then fail).
        """
        out = {"paper": self.is_paper(), "equity": None, "cash": None, "maintenance_margin": None,
               "options_trading_level": None, "options_approved_level": None, "max_options_trading_level": None,
               "status": None, "problems": []}
        try:
            a = self._client.get_account()
            for k in ("equity", "cash", "maintenance_margin"):
                out[k] = _num(_get(a, k))
            for k in ("options_trading_level", "options_approved_level"):
                out[k] = _int_or_none(_get(a, k))
            out["status"] = status_str(_get(a, "status"))
        except Exception as e:
            out["problems"].append(f"account read failed: {e}")
        try:
            c = self._client.get_account_configurations()
            out["max_options_trading_level"] = _int_or_none(_get(c, "max_options_trading_level"))
        except Exception as e:
            out["problems"].append(f"account configuration read failed: {e}")
        return out

    def positions_detail(self) -> list[dict]:
        """Every position in the shared account, OCC option symbols included, with a signed quantity
        (short < 0): [{symbol, qty, side, asset_class, avg_entry_price, market_value}]. Raises on a failed read."""
        out = []
        for p in self._client.get_all_positions():
            sym = self._crypto.get(_get(p, "symbol"), _get(p, "symbol"))
            side = status_str(_get(p, "side"))
            side = side.split(".", 1)[1] if side.startswith("positionside.") else side
            q = _num(_get(p, "qty")) or 0.0
            q = -abs(q) if side == "short" else q
            out.append({"symbol": sym, "qty": q, "side": side or ("short" if q < 0 else "long"),
                        "asset_class": status_str(_get(p, "asset_class")),
                        "avg_entry_price": _num(_get(p, "avg_entry_price")),
                        "market_value": _num(_get(p, "market_value"))})
        return out

    def option_activities(self, after: Any = None, types=OPTION_ACTIVITY_TYPES) -> list[dict]:
        """OPT-26: assignment/exercise/expiry activities (OPASN, OPEXC, OPEXP). Paper posts them the next day.

        alpaca-py 0.44 has no typed call for activities, so this uses the client's raw GET. Raises on failure.
        """
        params = {"activity_types": ",".join(types)}
        if after is not None:
            params["after"] = str(after)
        rows = self._client.get("/account/activities", params) or []
        return [{"id": _get(r, "id"), "activity_type": str(_get(r, "activity_type") or ""),
                 "symbol": _get(r, "symbol"), "qty": _num(_get(r, "qty")), "date": _get(r, "date"),
                 "price": _num(_get(r, "price")), "side": _get(r, "side")} for r in rows]

    def submit_mleg(self, order: dict, *, enabled: bool, gate_ok: bool, prefix: str = "OPT-",
                    today: Any = None) -> dict:
        """Send ONE multi-leg LIMIT DAY option order (OPT-3, OPT-14). Refuses (status "refused", nothing sent)
        unless options_book.enabled, the OPT-41 gate and a paper host (OPT-1) all hold, and the order passes the
        basic OPT-3/OPT-14 shape and sign check (one vertical on OCC legs) and, for an open, the 0DTE floor.
        `today` defaults to the New York date now (the order goes out now). The caller must run
        options.risk.validate_spread_order first.
        """
        cid = str(order.get("client_order_id") or "")
        base = {"client_order_id": cid, "qty": order.get("qty"), "limit_price": order.get("limit_price"),
                "legs": [l.get("symbol") for l in order.get("legs") or []]}
        if today is None:
            today = pd.Timestamp.now(tz=NY).date()
        why = mleg_problems(order, enabled=enabled, gate_ok=gate_ok, paper=self.is_paper(), prefix=prefix,
                            today=today)
        if why:
            return {**base, "status": "refused", "id": None, "error": "; ".join(why)}
        try:
            req = _mleg_request(order)
        except Exception as e:  # never sent
            return {**base, "status": "error", "id": None, "error": str(e)}
        try:
            r = self._client.submit_order(req)
        except Exception as e:
            return self._after_submit_error(base, cid, e)
        return {**base, "status": status_str(_get(r, "status")), "id": str(_get(r, "id") or ""),
                "client_order_id": str(_get(r, "client_order_id") or cid)}

    def submit_single(self, order: dict, *, enabled: bool, gate_ok: bool, prefix: str = "OPT-") -> dict:
        """OPT-26 clean-up: send ONE single-leg LIMIT DAY sell (O's assigned stock, or an orphan long put with
        SELL_TO_CLOSE). Refuses (status "refused", nothing sent) under the same locks as `submit_mleg`."""
        cid = str(order.get("client_order_id") or "")
        base = {"client_order_id": cid, "symbol": order.get("symbol"), "qty": order.get("qty"),
                "limit_price": order.get("limit_price")}
        why = single_problems(order, enabled=enabled, gate_ok=gate_ok, paper=self.is_paper(), prefix=prefix)
        if why:
            return {**base, "status": "refused", "id": None, "error": "; ".join(why)}
        try:
            req = _single_request(order)
        except Exception as e:  # never sent
            return {**base, "status": "error", "id": None, "error": str(e)}
        try:
            r = self._client.submit_order(req)
        except Exception as e:
            return self._after_submit_error(base, cid, e)
        return {**base, "status": status_str(_get(r, "status")), "id": str(_get(r, "id") or ""),
                "client_order_id": str(_get(r, "client_order_id") or cid)}

    def mleg_fills(self, pending: list[dict]) -> list[dict]:
        """EX-4 for mleg orders: the parent fill row plus each leg's filled quantity and average price.
        Never raises for one bad order (same rules as order_fills)."""
        rows = []
        for p in pending or []:
            row = self._fill_one(p)
            try:
                order = self._lookup(row["client_order_id"], p.get("broker_order_id")) if row["status"] not in (
                    "error", "unknown") else None
            except Exception:
                order = None
            row["legs"] = [{"symbol": _get(l, "symbol"), "side": status_str(_get(l, "side")),
                            "position_intent": status_str(_get(l, "position_intent")),
                            "filled_qty": _num(_get(l, "filled_qty")) or 0.0,
                            "filled_avg_price": _num(_get(l, "filled_avg_price"))}
                           for l in (_get(order, "legs") or [])] if order is not None else []
            rows.append(row)
        return rows

    def submit(self, orders: list[Order], client_prefix: str, *, date: Any = None,
               suffix: str | None = None) -> list[dict]:
        """EX-1/EX-2 market orders. Results: {symbol, side, qty, status, id, client_order_id} (+ error).

        `date` is accepted so both brokers take the same call; Alpaca dates the orders itself.
        """
        suffix = new_suffix() if suffix is None else suffix
        return [self._submit_one(o, cid) for o, cid in zip(orders, assign_client_ids(orders, client_prefix, suffix))]

    def _submit_one(self, o: Order, cid: str) -> dict:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        base = {"symbol": o.symbol, "side": o.side, "qty": o.qty, "client_order_id": cid}
        problem = order_problem(o)
        if problem:
            return {**base, "status": "error", "id": None, "error": problem}
        try:
            req = MarketOrderRequest(symbol=o.symbol, qty=o.qty,
                                     side=OrderSide.BUY if o.side == "buy" else OrderSide.SELL,
                                     time_in_force=TimeInForce(time_in_force(o.symbol)), client_order_id=cid)
        except Exception as e:  # never sent
            return {**base, "status": "error", "id": None, "error": str(e)}
        try:
            r = self._client.submit_order(req)
        except Exception as e:  # one bad order must not stop the others
            return self._after_submit_error(base, cid, e)
        return {**base, "status": status_str(_get(r, "status")), "id": str(_get(r, "id") or ""),
                "client_order_id": str(_get(r, "client_order_id") or cid)}

    def _after_submit_error(self, base: dict, cid: str, error: Exception) -> dict:
        """The order may have reached Alpaca before the error (a timeout, or the client's automatic retry
        hitting "client_order_id must be unique"). Booking it as "not placed" would leave a position with no
        lot and no stop, so look the id up once:
        found -> its real status; "order not found" -> error (not placed); lookup failed too -> "unconfirmed",
        which the ledger keeps as pending so the next run's `order_fills` settles or drops it.
        """
        try:
            r = self._client.get_order_by_client_id(cid)
        except Exception as e2:
            if _is_not_found(e2):
                return {**base, "status": "error", "id": None, "error": str(error)}
            return {**base, "status": "unconfirmed", "id": None,
                    "error": f"{error}; could not check whether the broker has the order: {e2}"}
        return {**base, "status": status_str(_get(r, "status")), "id": str(_get(r, "id") or ""),
                "client_order_id": str(_get(r, "client_order_id") or cid),
                "note": f"the submit call raised ({error}) but the broker has the order"}

    def order_fills(self, pending: list[dict]) -> list[dict]:
        """EX-4: one fill row per pending order. Never raises for one bad order.

        Unknown id -> status "unknown" (final, nothing filled). Any other lookup error -> status "error",
        not final, so the pending order is kept and checked again next run.
        """
        return [self._fill_one(p) for p in pending or []]

    def _fill_one(self, p: dict) -> dict:
        cid = str(p.get("client_order_id") or "")
        try:
            order = self._lookup(cid, p.get("broker_order_id"))
        except Exception as e:
            return {**fill_row(cid, "error"), "final": False, "error": str(e)}
        if order is None:
            return fill_row(cid, "unknown")
        qty = _num(_get(order, "filled_qty")) or 0.0
        # A partial fill that was then cancelled may have no filled_at; its last update is the fill day.
        when = _get(order, "filled_at") or (_get(order, "updated_at") if qty > 0 else None)
        return fill_row(cid or str(_get(order, "client_order_id") or ""), status_str(_get(order, "status")),
                        filled_qty=qty, filled_avg_price=_num(_get(order, "filled_avg_price")),
                        filled_at=ny_date(when), id=str(_get(order, "id") or ""),
                        symbol=_get(order, "symbol"), side=status_str(_get(order, "side")))

    def _lookup(self, cid: str, broker_id: Any):
        """The order by client id, else by broker id; None when the broker does not know it."""
        attempts = []
        if cid:
            attempts.append((self._client.get_order_by_client_id, cid))
        if broker_id:
            attempts.append((self._client.get_order_by_id, str(broker_id)))
        for fetch, key in attempts:
            try:
                return fetch(key)
            except Exception as e:
                if not _is_not_found(e):
                    raise
        return None


# --- simulator ------------------------------------------------------------------------------------


class SimBroker:
    """Local broker whose cash, positions and orders live in the book's state file (`state.sim`).

    fill_mode "close": every order fills at once at its reference price (the signal close) +/- cost.
    fill_mode "next_open" (EX-4, "in the simulator, fill at the next bar's open"): orders wait in
    `sim_state["open_orders"]` and fill at the open of the first bar after their signal date +/- cost.
    Default: "close" without bars (the old behaviour), "next_open" with bars.

    cost_in_price True (default): the reported fill price includes the cost. False: the fill price is the raw
    close/open and the cost is taken from cash separately, so a ledger that charges its own model cost on
    top of fill prices (as it must for real broker fills) does not count the cost twice.
    Buys never spend more than the cash on hand (a shortfall fills the affordable part); sells never go short.
    """

    name = "sim"

    def __init__(self, sim_state: dict, prices: dict[str, float], cost_bps: dict[str, int], asset_class,
                 bars: dict[str, pd.DataFrame] | None = None, fill_mode: str | None = None, *,
                 cost_in_price: bool = True):
        mode = fill_mode or ("close" if bars is None else "next_open")
        if mode not in ("close", "next_open"):
            raise ValueError(f"fill_mode must be 'close' or 'next_open', got {fill_mode!r}")
        self.state = sim_state
        self.prices = prices
        self.cost_bps = cost_bps
        self.asset_class = asset_class
        self.bars = bars
        self.fill_mode = mode
        self.cost_in_price = cost_in_price

    def account(self) -> tuple[float, float]:
        """Cash plus every position at today's price. A held symbol with no usable price today (missing or
        NaN close, not fetched) keeps its last known mark: valuing it at $0 would fake a drawdown and latch
        the halt and loss breakers."""
        cash = self.state["cash"]
        marks = self.state.setdefault("marks", {})
        equity = cash
        for s, q in self.state["positions"].items():
            p = self.prices.get(s)
            if _finite(p) and float(p) > 0:
                marks[s] = float(p)
            else:
                p = marks.get(s, 0.0)
            equity += q * float(p)
        return equity, cash

    def positions(self) -> dict[str, float]:
        return {s: q for s, q in self.state["positions"].items() if q > 1e-12}

    # --- orders --------------------------------------------------------------------------------

    def submit(self, orders: list[Order], client_prefix: str, *, date: Any = None,
               suffix: str | None = None) -> list[dict]:
        """Close mode fills now; next-open mode queues each order with its signal date (`date` or the last bar)."""
        signal_date = self._signal_date(date)
        if self.fill_mode == "next_open" and signal_date is None:
            raise ValueError("next_open fills need bars or a date= for the signal date")
        suffix = new_suffix() if suffix is None else suffix
        known = self._known_ids()
        results = []
        for o, cid in zip(orders, assign_client_ids(orders, client_prefix, suffix)):
            base = {"symbol": o.symbol, "side": o.side, "qty": o.qty, "client_order_id": cid}
            problem = order_problem(o) or ("duplicate client_order_id" if cid in known else None)
            if problem is None and self.fill_mode == "close" and not (_finite(o.price) and o.price > 0):
                problem = f"no reference price for {o.symbol}"
            if problem:
                results.append({**base, "status": "error", "id": None, "error": problem})
                continue
            known.add(cid)
            if self.fill_mode == "close":
                results.append(self._fill_now(o, cid, signal_date, base))
            else:
                self.state.setdefault("open_orders", []).append(
                    {"client_order_id": cid, "id": cid, "symbol": o.symbol, "side": o.side, "qty": float(o.qty),
                     "date": signal_date, "ref_price": float(o.price) if _finite(o.price) else None,
                     "status": "accepted"})
                results.append({**base, "status": "accepted", "id": cid})
        return results

    def order_fills(self, pending: list[dict]) -> list[dict]:
        """Fill every order that is due, then report each pending order in the Alpaca fill shape."""
        self._fill_due()
        open_ids = {od["client_order_id"] for od in self.state.get("open_orders", [])}
        closed = self.state.get("closed_orders", {})
        rows = []
        for p in pending or []:
            cid = str(p.get("client_order_id") or "")
            if cid in open_ids:
                rows.append(fill_row(cid, "accepted", id=cid))
            elif cid in closed:
                rec = closed[cid]
                rows.append(fill_row(cid, rec["status"], filled_qty=rec["filled_qty"],
                                     filled_avg_price=rec["filled_avg_price"], filled_at=rec["filled_at"],
                                     id=cid, symbol=rec["symbol"], side=rec["side"]))
            else:
                rows.append(fill_row(cid, "unknown"))
        return rows

    def cancel_open_orders(self, prefixes: Any = None, *, all_orders: bool = False) -> list[str] | None:
        """Fill what is due first (those fills already happened), then cancel the rest.

        `prefixes` works as in AlpacaPaperBroker, except that None cancels every open order here without
        `all_orders` (the simulator's state belongs to one book; `all_orders` is accepted for parity). Otherwise
        only orders whose client_order_id starts with one of the prefixes (an empty list cancels nothing) and the
        ids are returned.
        """
        self._fill_due()
        wanted = None if prefixes is None else clean_prefixes(prefixes)
        keep, done = [], []
        for od in self.state.get("open_orders", []):
            if wanted is None or (wanted and str(od["client_order_id"]).startswith(wanted)):
                self._close(od, "canceled")
                done.append(od["client_order_id"])
            else:
                keep.append(od)
        if "open_orders" in self.state:
            self.state["open_orders"] = keep
        return None if prefixes is None else done

    # --- internals -----------------------------------------------------------------------------

    def _fill_now(self, o: Order, cid: str, date: str | None, base: dict) -> dict:
        od = {"client_order_id": cid, "id": cid, "symbol": o.symbol, "side": o.side, "qty": float(o.qty),
              "date": date}
        rec = self._execute(od, float(o.price), date)
        out = {**base, "status": rec["status"], "id": cid, "filled_qty": rec["filled_qty"],
               "filled_avg_price": rec["filled_avg_price"]}
        if rec["filled_avg_price"] is not None:
            out["fill_price"] = round(rec["filled_avg_price"], 4)
        if rec.get("note"):
            out["note"] = rec["note"]
        return out

    def _fill_due(self) -> None:
        """Next-open fills: each open order whose symbol has a bar after its signal date. Sells before buys."""
        if not self.bars or not self.state.get("open_orders"):
            return
        waiting, due = [], []
        for od in self.state["open_orders"]:
            bar = self._next_open(od["symbol"], od["date"])
            (due if bar else waiting).append((od, bar))
        due.sort(key=lambda x: (x[1][0], 0 if x[0]["side"] == "sell" else 1))
        for od, (day, open_px) in due:
            self._execute(od, open_px, day)
        self.state["open_orders"] = [od for od, _ in waiting]

    def _next_open(self, symbol: str, date: str) -> tuple[str, float] | None:
        """(date, open) of the first bar after `date` with a usable open, or None."""
        df = (self.bars or {}).get(symbol)
        if df is None or len(df) == 0 or "open" not in df:
            return None
        idx = pd.DatetimeIndex(df.index)
        if idx.tz is not None:
            idx = idx.tz_convert(NY).tz_localize(None)
        opens = pd.Series(pd.to_numeric(df["open"], errors="coerce").to_numpy(), index=idx.normalize()).sort_index()
        later = opens[(opens.index > pd.Timestamp(date)) & (opens > 0)]
        if later.empty:
            return None
        return later.index[0].date().isoformat(), float(later.iloc[0])

    def _execute(self, od: dict, ref_price: float, day: str | None) -> dict:
        """Fill one order at ref_price +/- cost. Long only: a sell never exceeds the position.

        A buy never takes cash below zero (a real account would refuse the excess), so a gap-up open or an
        oversized order fills only the affordable part and the record says so.
        """
        buy = od["side"] == "buy"
        held = self.state["positions"].get(od["symbol"], 0.0)
        rate = self._cost_rate(od["symbol"])
        gross = ref_price * (1 + rate if buy else 1 - rate)  # cash per share, cost included
        note = None
        if buy:
            affordable = math.floor(max(float(self.state["cash"]), 0.0) / gross * 1e6) / 1e6
            qty = min(od["qty"], affordable)
            if qty < od["qty"] - 1e-12:
                note = f"buy cut to {qty:.6g} of {od['qty']:.6g}: not enough cash at {ref_price:.4f}"
        else:
            qty = min(od["qty"], max(held, 0.0))
        if qty <= 1e-12:
            return self._close(od, "rejected", note=note or "nothing to sell")
        signed = qty if buy else -qty
        self.state["cash"] -= signed * gross
        self.state["positions"][od["symbol"]] = held + signed
        self.state.setdefault("marks", {})[od["symbol"]] = float(ref_price)  # a held symbol always has a mark
        fill = gross if self.cost_in_price else ref_price
        return self._close(od, "filled", qty=qty, price=fill, day=day, cost=qty * ref_price * rate, note=note)

    def _close(self, od: dict, status: str, *, qty: float = 0.0, price: float | None = None,
               day: str | None = None, cost: float = 0.0, note: str | None = None) -> dict:
        rec = {"client_order_id": od["client_order_id"], "id": od.get("id"), "symbol": od["symbol"],
               "side": od["side"], "qty": od["qty"], "date": od.get("date"), "status": status,
               "filled_qty": float(qty), "filled_avg_price": price, "filled_at": day if qty > 0 else None,
               "cost": float(cost)}
        if note:
            rec["note"] = note
        closed = self.state.setdefault("closed_orders", {})
        closed[rec["client_order_id"]] = rec
        for old in list(closed)[: max(0, len(closed) - SIM_CLOSED_KEEP)]:
            del closed[old]
        return rec

    def _cost_rate(self, symbol: str) -> float:
        """Per-side cost as a fraction; an unknown asset class pays the highest configured cost."""
        bps = self.cost_bps.get(self.asset_class(symbol))
        if bps is None:
            bps = max(self.cost_bps.values(), default=0)
        return float(bps) / 10_000

    def _signal_date(self, date: Any) -> str | None:
        """The New York calendar day of `date` (bars are dated in New York time), else the last bar's day."""
        if date is not None:
            return _ny_naive(date).date().isoformat()
        last = [_ny_naive(df.index.max()) for df in (self.bars or {}).values() if df is not None and len(df)]
        return max(last).date().isoformat() if last else None

    def _known_ids(self) -> set[str]:
        ids = {od["client_order_id"] for od in self.state.get("open_orders", [])}
        return ids | set(self.state.get("closed_orders", {}))
