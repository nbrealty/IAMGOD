"""Brokers for the live paper minute trader: the real Alpaca PAPER account and an in-memory look-alike.

`AlpacaBroker` (MT-G36, MT-G26, MT-G15, MT-G21, MT-G25)
- Paper lock, checked in the constructor BEFORE any network call: the key names must be exactly
  ALPACA_SCALP_KEY / ALPACA_SCALP_SECRET (the stock books' keys can never be passed in), both must be set, no
  base-URL override may point anywhere but https://paper-api.alpaca.markets, and the built client's own base URL
  must be that paper host. Anything else raises PaperLockError. There is no live-money path.
- `account()` proves it is the SCALP paper account: the number starts with "PA", ends with the registry's
  `account_last4` and, once pinned (`state/scalp/account.pin`), equals the pinned number. Orders are refused until
  this check has passed once.
- `submit()` builds limit orders only (a bracket = limit parent + take-profit limit + stop-LIMIT); there is no
  market or stop-market request anywhere. A SELL is refused unless it fits inside the long position minus shares
  already promised to other open sells, so it can never open a short (MT-G15). Submits and cancels run under an
  exclusive fcntl lock on `state/scalp/broker.lock`, shared with the watchdog and the kill command.
- Errors: HTTP 4xx -> BrokerReject (never retried for entries); timeouts, 429 and 5xx -> BrokerUnavailable
  (query by client id before trying again). A duplicate client id is looked up and the existing order returned.
- `Mode.DRY` gives a read-only instance: `submit` and `cancel` raise.

`SimBroker`: the same interface in memory, for dry runs, replays, the pre-open self-test and tests. `update(now,
quotes, bars)` moves it forward (idempotent for the same inputs). Quote mode: a buy limit fills at the ask when
limit >= ask (a sell at the bid when limit <= bid); bracket legs wake up only after the parent is FULLY filled
(take-profit "new", stop-loss "held", like Alpaca); the stop triggers when the bid <= stop and then works as a
limit at the stop-limit price. Bar mode (replay): legs are checked on each new bar after the fill bar: an open
beyond the target fills the target at the open, then the stop first when both levels are inside one bar (the
backtest's bar_exit order); a limit fills on a bar only if the bar traded THROUGH
its price, a touch is not a fill (MT-G4). Test knobs: `partial_fill_qty`, `reject_next`,
`cancel_delay_s` (a cancel request is not a cancel), `unavailable_next`, `fill_delay_s`.

Open orders come back FLAT from both brokers: every open order once, bracket legs as their own items (Alpaca
gives legs their own ids and non-SCALP client ids), so reconcile and cancel-all never miss a live leg.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

import pandas as pd

from . import config as C
from . import orders as O
from .model import (DONE_STATUSES, AccountView, Bar, BrokerReject, BrokerUnavailable, Feed, Mode, OrderSpec, OrderView,
                    PaperLockError, PositionView, Quote, as_ny)

PAPER_URL = "https://paper-api.alpaca.markets"
SCALP_KEYS = ("ALPACA_SCALP_KEY", "ALPACA_SCALP_SECRET")
# Environment variables that alpaca tools read as a trading base-URL override. Any of them set to a non-paper
# host refuses the broker (MT-G36). Names starting with ALPACA_SCALP_ that mention a URL are checked too.
URL_ENV = ("APCA_API_BASE_URL", "APCA_BASE_URL", "ALPACA_BASE_URL", "ALPACA_API_BASE_URL", "ALPACA_TRADING_URL",
           "ALPACA_ENDPOINT", "ALPACA_URL")
LOCK_PATH = C.STATE_DIR / "broker.lock"
PIN_PATH = C.STATE_DIR / "account.pin"
PAGE = 500


def _norm_url(u: Any) -> str:
    u = getattr(u, "value", u)
    s = str(u or "").strip().rstrip("/")
    return s[:-3] if s.endswith("/v2") else s


def is_done(v: OrderView) -> bool:
    """Terminal status. Anything else (including statuses we do not know) counts as still live."""
    return v.status in DONE_STATUSES


def remaining(v: OrderView) -> float:
    return 0.0 if is_done(v) else max(float(v.qty) - float(v.filled_qty), 0.0)


def reserved_sell_qty(open_flat: list[OrderView], symbol: str) -> float:
    """Shares of `symbol` already promised to open SELL orders. The legs of one bracket are one-cancels-other,
    so they count once (the largest); every other open sell counts in full. With one slot there is at most one
    bracket per symbol, so the non-SCALP sells (Alpaca-named legs, or anything foreign) count as their largest."""
    ours, legs = 0.0, 0.0
    for o in open_flat:
        if o.symbol != symbol or o.side != "sell" or is_done(o):
            continue
        r = remaining(o)
        if O.parse_client_id(o.client_order_id) is not None:
            ours += r
        else:
            legs = max(legs, r)
    return ours + legs


# ============================================================================================ Alpaca (paper)
def _status_code(e: Exception) -> int | None:
    for get in (lambda: getattr(e, "status_code", None), lambda: e.response.status_code):  # type: ignore[attr-defined]
        try:
            v = get()
        except Exception:  # noqa: BLE001 - APIError.status_code can itself raise without an http_error
            v = None
        if isinstance(v, int):
            return v
    return None


def _error_code(e: Exception) -> str | None:
    try:
        return str(json.loads(str(e)).get("code"))
    except Exception:  # noqa: BLE001 - not a JSON error body
        return None


def _transient_types() -> tuple[type, ...]:
    out: list[type] = [ConnectionError, TimeoutError]
    try:
        import requests
        out += [requests.exceptions.ConnectionError, requests.exceptions.Timeout]
    except ImportError:  # pragma: no cover - requests comes with alpaca-py
        pass
    return tuple(out)


def classify(e: Exception) -> Exception:
    """Map any client error to BrokerReject (4xx: the broker said no) or BrokerUnavailable (it may or may not
    have arrived: timeouts, network, 429, 5xx, anything unknown)."""
    if isinstance(e, (BrokerReject, BrokerUnavailable, PaperLockError)):
        return e
    status = _status_code(e)
    if status is not None and 400 <= status < 500 and status != 429:
        return BrokerReject(str(e)[:300], status, _error_code(e))
    return BrokerUnavailable(f"{type(e).__name__}: {str(e)[:300]}")


def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def _opt_f(x: Any) -> float | None:
    if x is None or x == "":
        return None
    v = _f(x, float("nan"))
    return v if math.isfinite(v) else None


def _ev(x: Any) -> str:
    """An alpaca enum or plain value as a lower-case string."""
    return str(getattr(x, "value", x) or "").lower()


def _ts(x: Any) -> pd.Timestamp | None:
    if x is None:
        return None
    t = pd.Timestamp(x)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return as_ny(t)


def order_view(o: Any) -> OrderView:
    """alpaca-py Order -> OrderView (legs nested when the order came back nested)."""
    return OrderView(
        id=str(o.id), client_order_id=str(o.client_order_id or ""), symbol=str(o.symbol or ""), side=_ev(o.side),
        qty=_f(o.qty), filled_qty=_f(o.filled_qty), filled_avg_price=_opt_f(o.filled_avg_price),
        status=_ev(o.status), order_type=_ev(getattr(o, "type", None) or getattr(o, "order_type", None)),
        limit_price=_opt_f(o.limit_price), stop_price=_opt_f(o.stop_price),
        order_class=_ev(getattr(o, "order_class", None)) or "simple",
        legs=tuple(order_view(x) for x in (getattr(o, "legs", None) or ())),
        submitted_at=_ts(getattr(o, "submitted_at", None)), filled_at=_ts(getattr(o, "filled_at", None)),
        updated_at=_ts(getattr(o, "updated_at", None)))


def position_view(p: Any) -> PositionView:
    q = _f(p.qty)
    if _ev(getattr(p, "side", "")) == "short" and q > 0:
        q = -q
    return PositionView(symbol=str(p.symbol), qty=q, avg_entry_price=_f(p.avg_entry_price))


def with_timeout(client: Any, seconds: float = C.HTTP_TIMEOUT_S) -> Any:
    """Give every HTTP call of an alpaca-py client a timeout. alpaca-py sets none (`session.request(method, url,
    **opts)`), so one stalled connection would hang the tick, the heartbeat and anything waiting on the broker lock;
    with this a hang becomes requests.Timeout -> BrokerUnavailable (query by client id before trying again)."""
    sess = getattr(client, "_session", None)
    if sess is None or getattr(sess, "_scalp_timeout", None) is not None:
        return client
    orig = sess.request

    def request(method: str, url: str, **kw: Any) -> Any:
        if kw.get("timeout") is None:
            kw["timeout"] = seconds
        return orig(method, url, **kw)

    sess.request = request
    sess._scalp_timeout = seconds
    return client


def _default_client(key: str, secret: str) -> Any:
    from alpaca.trading.client import TradingClient
    return with_timeout(TradingClient(key, secret, paper=True))


class AlpacaBroker:
    """The ALPACA_SCALP paper account. See the module docstring for the paper lock."""

    def __init__(self, mode: Mode = Mode.PAPER, keys: tuple[str, str] = SCALP_KEYS,
                 lock_path: str | Path | None = LOCK_PATH, *, account_last4: str | None = None,
                 pin_path: str | Path | None = PIN_PATH, url_override: str | None = None,
                 client_factory: Callable[[str, str], Any] | None = None, env: Mapping[str, str] | None = None):
        mode = Mode(mode)
        if mode not in (Mode.PAPER, Mode.DRY):
            raise PaperLockError(f"AlpacaBroker runs in paper or dry mode only, not {mode.value}")
        if tuple(keys) != SCALP_KEYS:
            raise PaperLockError("only the ALPACA_SCALP_KEY / ALPACA_SCALP_SECRET pair may be used (decision 1)")
        env = os.environ if env is None else env
        k, s = env.get(SCALP_KEYS[0]), env.get(SCALP_KEYS[1])
        if not k or not s:
            raise PaperLockError("ALPACA_SCALP_KEY / ALPACA_SCALP_SECRET are not set: add them to the environment "
                                 "settings and start a new session")
        names = set(URL_ENV) | {n for n in env if n.startswith("ALPACA_SCALP_") and ("URL" in n or "ENDPOINT" in n)}
        for n in sorted(names):
            v = env.get(n)
            if v and _norm_url(v) != PAPER_URL:
                raise PaperLockError(f"{n} points at a non-paper URL: refusing (MT-G36)")
        if url_override is not None and _norm_url(url_override) != PAPER_URL:
            raise PaperLockError("url_override must be the paper host (MT-G36)")
        client = (client_factory or _default_client)(k, s)
        base = _norm_url(getattr(client, "_base_url", None) or getattr(client, "base_url", None))
        if base != PAPER_URL:
            raise PaperLockError(f"trading client base URL is {base or 'unknown'!r}, not the paper host (MT-G36)")
        if hasattr(client, "_retry"):
            client._retry = 0     # no silent resend inside alpaca-py: a timeout surfaces and we query by client id
        with_timeout(client)      # every call is bounded (C.HTTP_TIMEOUT_S), whoever built the client
        self.mode, self.client, self.base_url = mode, client, PAPER_URL
        self.lock_path = None if lock_path is None else Path(lock_path)
        self.pin_path = None if pin_path is None else Path(pin_path)
        self._last4 = account_last4
        self._verified: str | None = None
        self._lock_depth = 0

    # ------------------------------------------------------------------ lock (shared with watchdog and kill)
    @contextmanager
    def lock(self, wait_s: float | None = None) -> Iterator[bool]:
        """Exclusive cross-process lock around order actions. Re-entrant within this instance. With `wait_s` (the
        watchdog and the kill command) it gives up after that many seconds and yields False: the caller goes on
        without the lock (nested submits do not ask again), which is safe because it cancels first and every
        sell re-reads the position and the open orders."""
        if self._lock_depth or self.lock_path is None:
            self._lock_depth += 1
            try:
                yield True
            finally:
                self._lock_depth -= 1
            return
        from .state import flock_wait
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "a+") as fh:
            got = flock_wait(fh, wait_s)
            self._lock_depth += 1
            try:
                yield got
            finally:
                self._lock_depth -= 1
                if got:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _call(self, fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - mapped to the two broker errors
            raise classify(e) from e

    # ------------------------------------------------------------------ reads
    def account(self) -> AccountView:
        a = self._call(self.client.get_account)
        number = str(getattr(a, "account_number", "") or "")
        last4 = self._last4 if self._last4 is not None else C.load_registry().account_last4
        if not number.startswith("PA"):
            raise PaperLockError("account number does not start with PA: not a paper account (MT-G36)")
        if not number.endswith(last4):
            raise PaperLockError(f"account number does not end with the registered ...{last4} (MT-G26)")
        if self.pin_path is not None and self.pin_path.exists():
            if self.pin_path.read_text().strip() != number:
                raise PaperLockError("account number differs from the pinned SCALP account (MT-G26)")
        self._verified = number
        return AccountView(
            account_number=number, status=_ev(getattr(a, "status", "")), equity=_f(a.equity),
            last_equity=_f(a.last_equity), cash=_f(a.cash), buying_power=_f(a.buying_power),
            non_marginable_buying_power=_f(getattr(a, "non_marginable_buying_power", 0.0)),
            trading_blocked=bool(getattr(a, "trading_blocked", False)),
            shorting_enabled=bool(getattr(a, "shorting_enabled", False)), base_url=self.base_url)

    def positions(self) -> list[PositionView]:
        return [position_view(p) for p in self._call(self.client.get_all_positions)]

    def open_orders(self) -> list[OrderView]:
        """Every open order FLAT (legs as their own items)."""
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN, nested=False, limit=PAGE)
        return [order_view(o) for o in self._call(lambda: self.client.get_orders(filter=req))]

    def orders_since(self, since: pd.Timestamp) -> list[OrderView]:
        """All statuses, nested, oldest first, paged by submission time."""
        from alpaca.common.enums import Sort
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest
        after = as_ny(since).tz_convert("UTC").to_pydatetime()
        out: dict[str, OrderView] = {}
        for _ in range(100):                                   # at most 50,000 orders: far above any real day
            req = GetOrdersRequest(status=QueryOrderStatus.ALL, after=after, nested=True, limit=PAGE,
                                   direction=Sort.ASC)
            page = [order_view(o) for o in self._call(lambda: self.client.get_orders(filter=req))]
            new = [v for v in page if v.id not in out]
            out.update((v.id, v) for v in new)
            if len(page) < PAGE or not new:
                break
            last = max(v.submitted_at for v in page if v.submitted_at is not None)
            after = last.tz_convert("UTC").to_pydatetime()
        return sorted(out.values(), key=lambda v: (v.submitted_at or pd.Timestamp(0, tz="UTC"), v.id))

    def get_order(self, order_id: str) -> OrderView:
        from alpaca.trading.requests import GetOrderByIdRequest
        return order_view(self._call(lambda: self.client.get_order_by_id(order_id, GetOrderByIdRequest(nested=True))))

    def get_by_client_id(self, client_order_id: str) -> OrderView | None:
        try:
            return order_view(self._call(lambda: self.client.get_order_by_client_id(client_order_id)))
        except BrokerReject as e:
            if e.status == 404:
                return None
            raise

    # ------------------------------------------------------------------ orders
    def _writable(self) -> None:
        if self.mode is not Mode.PAPER:
            raise PaperLockError("this AlpacaBroker is read-only (dry mode): no orders")
        if self._verified is None:
            self.account()                      # right account before the first order (MT-G26)

    def request_for(self, spec: OrderSpec) -> Any:
        """The alpaca-py request for a spec: LimitOrderRequest only (MT-G21)."""
        from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, StopLossRequest, TakeProfitRequest
        common = dict(symbol=spec.symbol, qty=int(spec.qty), limit_price=float(spec.limit_price),
                      side=OrderSide.BUY if spec.side == "buy" else OrderSide.SELL, time_in_force=TimeInForce.DAY,
                      client_order_id=spec.client_order_id, extended_hours=False)
        if spec.order_class == "bracket":
            return LimitOrderRequest(**common, order_class=OrderClass.BRACKET,
                                     take_profit=TakeProfitRequest(limit_price=float(spec.take_profit)),
                                     stop_loss=StopLossRequest(stop_price=float(spec.stop_price),
                                                               limit_price=float(spec.stop_limit_price)))
        return LimitOrderRequest(**common, order_class=OrderClass.SIMPLE)

    def submit(self, spec: OrderSpec) -> OrderView:
        self._writable()
        check_spec(spec)
        with self.lock():
            if spec.side == "sell":
                have = sum(p.qty for p in self.positions() if p.symbol == spec.symbol)
                free = have - reserved_sell_qty(self.open_orders(), spec.symbol)
                if spec.qty > free + 1e-9:
                    raise BrokerReject(f"sell {spec.qty} {spec.symbol} > free long qty {free:g}: refused so it "
                                       "can never open a short (MT-G15)", None, "SELL_EXCEEDS_POSITION")
            req = self.request_for(spec)
            try:
                return order_view(self.client.submit_order(req))
            except Exception as e:  # noqa: BLE001 - classified below
                err = classify(e)
                if isinstance(err, BrokerReject) and err.status in (409, 422) and "client_order_id" in str(e).lower():
                    found = self.get_by_client_id(spec.client_order_id)
                    if found is not None:
                        return found
                raise err from e

    def cancel(self, order_id: str) -> None:
        """A cancel REQUEST. Alpaca answers 422 both for an order that is already done (fine) and for one it will not
        cancel: the order is read back, and only a done order counts as fine; otherwise BrokerReject
        NOT_CANCELABLE (the engine journals it and its give-up clock escalates to the kill switch)."""
        if self.mode is not Mode.PAPER:
            raise PaperLockError("this AlpacaBroker is read-only (dry mode): no cancels")
        with self.lock():
            try:
                self._call(lambda: self.client.cancel_order_by_id(order_id))
            except BrokerReject as e:
                if e.status != 422:
                    raise
                v = self.get_order(order_id)
                if is_done(v):
                    return
                raise BrokerReject(f"order {order_id} not cancelable (status {v.status}): {e}", 422,
                                   "NOT_CANCELABLE") from e


def check_spec(spec: OrderSpec) -> None:
    """The last check before anything is sent (both brokers): a SCALP- id, a whole qty >= 1, a positive limit,
    and a spec the order builder would accept."""
    problems = O.validate(spec)
    if not spec.client_order_id.startswith(C.ORDER_PREFIX):
        problems.append("client id must start with SCALP-")
    if isinstance(spec.qty, bool) or not isinstance(spec.qty, int) or spec.qty < 1:
        problems.append("qty must be an int >= 1")
    if not spec.limit_price > 0:
        problems.append("limit must be positive")
    if problems:
        raise BrokerReject(f"refused before sending: {sorted(set(problems))}", None, "LOCAL_VALIDATION")


# ============================================================================================ simulator
@dataclass
class _Order:
    id: str
    client_order_id: str
    symbol: str
    side: str
    qty: float
    limit_price: float
    order_type: str = "limit"                  # "limit" | "stop_limit"
    stop_price: float | None = None
    order_class: str = "simple"
    role: str = "simple"                       # simple | parent | tp | sl
    parent: str | None = None
    legs: list[str] = field(default_factory=list)
    status: str = "new"
    filled_qty: float = 0.0
    fill_value: float = 0.0
    submitted_at: pd.Timestamp | None = None
    filled_at: pd.Timestamp | None = None
    updated_at: pd.Timestamp | None = None
    cancel_at: pd.Timestamp | None = None
    active: bool = True                        # legs: False until the parent is fully filled
    triggered: bool = False                    # stop leg: the stop price was touched
    fill_bar: pd.Timestamp | None = None       # bar mode: legs only look at bars after this one

    @property
    def done(self) -> bool:
        return self.status in DONE_STATUSES

    @property
    def left(self) -> float:
        return max(self.qty - self.filled_qty, 0.0)


class SimBroker:
    """In-memory Alpaca paper look-alike (see the module docstring). Never sends anything anywhere."""

    def __init__(self, clock: Callable[[], pd.Timestamp], account: AccountView | None = None,
                 positions: tuple[PositionView, ...] | list[PositionView] = (), fill_mode: str = "quote", *,
                 partial_fill_qty: float | None = None, reject_next: int | None = None, cancel_delay_s: float = 0.0,
                 unavailable_next: str | bool | None = None, fill_delay_s: float = 0.0, mode: Mode = Mode.DRY):
        if fill_mode not in ("quote", "bar"):
            raise ValueError("fill_mode is 'quote' or 'bar'")
        self.clock, self.fill_mode, self.mode = clock, fill_mode, Mode(mode)
        self._acct = account or AccountView("PASIM00GWRL", "active", 100_000.0, 100_000.0, 100_000.0, 100_000.0,
                                            100_000.0, False, False, "sim://paper")
        self.cash = float(self._acct.cash)
        self.pos: dict[str, list[float]] = {p.symbol: [float(p.qty), float(p.avg_entry_price)] for p in positions}
        self.partial_fill_qty, self.reject_next = partial_fill_qty, reject_next
        self.cancel_delay_s, self.unavailable_next, self.fill_delay_s = cancel_delay_s, unavailable_next, fill_delay_s
        self.orders: dict[str, _Order] = {}
        self.by_cid: dict[str, str] = {}
        self.quotes: dict[str, Quote] = {}
        self.last_bar: dict[str, pd.Timestamp] = {}
        self.fills: list[dict[str, Any]] = []          # every fill, for tests and the self-test
        self.submits: list[OrderSpec] = []             # every spec that reached the "broker"
        self.cancels: list[str] = []
        self._n = 0

    # ------------------------------------------------------------------ driving
    def now(self) -> pd.Timestamp:
        return as_ny(self.clock())

    def set_quote(self, symbol: str, bid: float, ask: float, size: float = 100.0) -> None:
        t = self.now()
        self.update(t, {symbol: Quote(symbol, bid, ask, size, size, t, t, Feed.SIM)})

    def update(self, now: pd.Timestamp, quotes: Mapping[str, Quote] | None = None,
               bars: Mapping[str, list[Bar]] | None = None) -> None:
        """Advance to `now`: take the quotes and any NEW bars (a bar already seen is ignored), finish due cancels,
        then match every live order. Calling it twice with the same inputs changes nothing."""
        now = as_ny(now)
        for sym, q in (quotes or {}).items():
            if q is not None and q.valid:
                self.quotes[sym] = q
        self._due_cancels(now)
        for o in list(self.orders.values()):
            self._match_quote(o, now)
        if self.fill_mode == "bar":
            for sym, bl in (bars or {}).items():
                for b in sorted(bl, key=lambda x: x.start):
                    st = as_ny(b.start)
                    if sym in self.last_bar and st <= self.last_bar[sym]:
                        continue
                    self.last_bar[sym] = st
                    for o in list(self.orders.values()):
                        self._match_bar(o, b, now)
        else:
            for sym, bl in (bars or {}).items():
                for b in bl:
                    self.last_bar[sym] = max(self.last_bar.get(sym, as_ny(b.start)), as_ny(b.start))

    def inject_position(self, symbol: str, qty: float, avg: float) -> None:
        """A position the bot did not make (tests: a phantom fill at the broker)."""
        cur = self.pos.get(symbol, [0.0, 0.0])
        n = cur[0] + qty
        self.pos[symbol] = [n, avg if cur[0] == 0 else (cur[0] * cur[1] + qty * avg) / n if n else 0.0]

    def add_foreign_order(self, symbol: str, side: str, qty: float, limit: float, cid: str = "manual-1") -> str:
        """An open order the bot did not send (tests: reconcile must flag it)."""
        o = self._new(cid, symbol, side, qty, limit)
        return o.id

    # ------------------------------------------------------------------ Broker protocol
    def account(self) -> AccountView:
        mark = 0.0
        for sym, (q, avg) in self.pos.items():
            quote = self.quotes.get(sym)
            mark += q * (quote.bid if quote is not None and q > 0 else quote.ask if quote is not None else avg)
        return replace(self._acct, equity=self.cash + mark, cash=self.cash)

    def positions(self) -> list[PositionView]:
        return [PositionView(s, q, avg) for s, (q, avg) in sorted(self.pos.items()) if abs(q) > 1e-9]

    def open_orders(self) -> list[OrderView]:
        self._due_cancels(self.now())
        return [self._view(o, nested=False) for o in self.orders.values() if not o.done]

    def orders_since(self, since: pd.Timestamp) -> list[OrderView]:
        s = as_ny(since)
        top = [o for o in self.orders.values() if o.parent is None and o.submitted_at is not None
               and o.submitted_at >= s]
        return [self._view(o) for o in sorted(top, key=lambda o: (o.submitted_at, o.id))]

    def get_order(self, order_id: str) -> OrderView:
        self._due_cancels(self.now())
        if order_id not in self.orders:
            raise BrokerReject(f"order {order_id} not found", 404)
        return self._view(self.orders[order_id])

    def get_by_client_id(self, client_order_id: str) -> OrderView | None:
        oid = self.by_cid.get(client_order_id)
        return None if oid is None else self.get_order(oid)

    def submit(self, spec: OrderSpec) -> OrderView:
        now = self.now()
        if self.unavailable_next in (True, "before"):
            self.unavailable_next = None
            raise BrokerUnavailable("simulated timeout (the order never arrived)")
        if self.reject_next is not None:
            status, self.reject_next = self.reject_next, None
            raise BrokerReject(f"simulated rejection {status} (e.g. account restricted)", status)
        if spec.client_order_id in self.by_cid:                 # duplicate id: the broker returns the original
            return self.get_order(self.by_cid[spec.client_order_id])
        check_spec(spec)
        if spec.side == "sell":
            have = self.pos.get(spec.symbol, [0.0, 0.0])[0]
            free = have - reserved_sell_qty(self.open_orders(), spec.symbol)
            if spec.qty > free + 1e-9:
                raise BrokerReject(f"insufficient qty available for order (have {have:g}, free {free:g})", 403)
        self.submits.append(spec)
        o = self._new(spec.client_order_id, spec.symbol, spec.side, spec.qty, spec.limit_price,
                      order_class=spec.order_class, role="parent" if spec.order_class == "bracket" else "simple")
        if spec.order_class == "bracket":
            tp = self._new(f"leg-{self._n + 1:05d}", spec.symbol, "sell", spec.qty, float(spec.take_profit),
                           order_class="bracket", role="tp", parent=o.id, status="held", active=False)
            sl = self._new(f"leg-{self._n + 1:05d}", spec.symbol, "sell", spec.qty, float(spec.stop_limit_price),
                           order_type="stop_limit", stop_price=float(spec.stop_price), order_class="bracket",
                           role="sl", parent=o.id, status="held", active=False)
            o.legs = [tp.id, sl.id]
        self._match_quote(o, now)
        if self.unavailable_next == "after":
            self.unavailable_next = None
            raise BrokerUnavailable("simulated timeout (the order DID arrive)")
        return self._view(o)

    def cancel(self, order_id: str) -> None:
        now = self.now()
        o = self.orders.get(order_id)
        if o is None:
            raise BrokerReject(f"order {order_id} not found", 404)
        self.cancels.append(order_id)
        if o.done:
            return
        targets = [o] + [self.orders[x] for x in o.legs if not self.orders[x].done and not self.orders[x].active]
        for t in targets:
            if self.cancel_delay_s > 0:
                if t.cancel_at is None:
                    t.cancel_at = now + pd.Timedelta(seconds=self.cancel_delay_s)
                    t.status, t.updated_at = "pending_cancel", now
            else:
                self._set_canceled(t, now)

    # ------------------------------------------------------------------ internals
    def _new(self, cid: str, symbol: str, side: str, qty: float, limit: float, *, order_type: str = "limit",
             stop_price: float | None = None, order_class: str = "simple", role: str = "simple",
             parent: str | None = None, status: str = "new", active: bool = True) -> _Order:
        self._n += 1
        now = self.now()
        o = _Order(id=f"sim-{self._n:05d}", client_order_id=cid, symbol=symbol, side=side, qty=float(qty),
                   limit_price=float(limit), order_type=order_type, stop_price=stop_price, order_class=order_class,
                   role=role, parent=parent, status=status, submitted_at=now, updated_at=now, active=active)
        self.orders[o.id] = o
        self.by_cid[cid] = o.id
        return o

    def _view(self, o: _Order, nested: bool = True) -> OrderView:
        avg = o.fill_value / o.filled_qty if o.filled_qty > 0 else None
        legs = tuple(self._view(self.orders[x]) for x in o.legs) if nested else ()
        return OrderView(id=o.id, client_order_id=o.client_order_id, symbol=o.symbol, side=o.side, qty=o.qty,
                         filled_qty=o.filled_qty, filled_avg_price=avg, status=o.status, order_type=o.order_type,
                         limit_price=o.limit_price, stop_price=o.stop_price, order_class=o.order_class, legs=legs,
                         submitted_at=o.submitted_at, filled_at=o.filled_at, updated_at=o.updated_at)

    def _set_canceled(self, o: _Order, now: pd.Timestamp) -> None:
        if o.done:
            return
        o.status, o.updated_at, o.cancel_at = "canceled", now, None
        if o.role == "parent":
            # A parent cancelled after a PARTIAL fill: whether Alpaca keeps legs for the filled part is
            # UNVERIFIED (MT-G16), so the simulator drops them and the engine must protect the position itself.
            for x in o.legs:
                self._set_canceled(self.orders[x], now)

    def _due_cancels(self, now: pd.Timestamp) -> None:
        for o in self.orders.values():
            if o.cancel_at is not None and not o.done and now >= o.cancel_at:
                self._set_canceled(o, now)

    def _fillable(self, o: _Order, now: pd.Timestamp) -> bool:
        if o.done or not o.active or o.left <= 0:
            return False
        if o.status == "held" and o.role == "tp":
            return False
        if self.fill_delay_s and o.role in ("simple", "parent") and o.submitted_at is not None:
            return now >= o.submitted_at + pd.Timedelta(seconds=self.fill_delay_s)
        return True

    def _fill(self, o: _Order, qty: float, price: float, now: pd.Timestamp,
              bar_start: pd.Timestamp | None = None) -> None:
        if o.role in ("simple", "parent") and self.partial_fill_qty:
            qty = min(qty, float(self.partial_fill_qty))
        qty = min(qty, o.left)
        if o.side == "sell":
            have = self.pos.get(o.symbol, [0.0, 0.0])[0]
            qty = min(qty, max(have, 0.0))                     # shorting is off: never below zero
        if qty <= 0:
            return
        price = O.round_cent(price)
        o.filled_qty += qty
        o.fill_value += qty * price
        o.updated_at = now
        o.status = "filled" if o.left <= 1e-9 else "partially_filled"
        if o.status == "filled":
            o.filled_at = now
        cur = self.pos.get(o.symbol, [0.0, 0.0])
        if o.side == "buy":
            n = cur[0] + qty
            self.pos[o.symbol] = [n, (cur[0] * cur[1] + qty * price) / n]
            self.cash -= qty * price
        else:
            self.pos[o.symbol] = [cur[0] - qty, cur[1] if cur[0] - qty > 1e-9 else 0.0]
            self.cash += qty * price
            if abs(self.pos[o.symbol][0]) <= 1e-9:
                del self.pos[o.symbol]
        self.fills.append({"ts": now, "id": o.id, "cid": o.client_order_id, "symbol": o.symbol, "side": o.side,
                           "qty": qty, "price": price, "role": o.role})
        if o.role == "parent" and o.status == "filled":
            # the fill bar: the bar that filled it (bar mode), else the minute in progress at a quote fill. Legs
            # look only at bars after it.
            fill_bar = as_ny(bar_start) if bar_start is not None else now.floor("min")
            for x in o.legs:                                   # legs wake up only after a FULL fill
                leg = self.orders[x]
                if not leg.done:
                    leg.active, leg.fill_bar, leg.updated_at = True, fill_bar, now
                    leg.status = "new" if leg.role == "tp" else "held"
        if o.role in ("tp", "sl") and o.status == "filled" and o.parent:
            for x in self.orders[o.parent].legs:               # one-cancels-other
                if x != o.id:
                    self._set_canceled(self.orders[x], now)

    def _match_quote(self, o: _Order, now: pd.Timestamp) -> None:
        q = self.quotes.get(o.symbol)
        if q is None or not self._fillable(o, now):
            return
        if o.role in ("tp", "sl") and self.fill_mode == "bar":
            return                                             # replay: legs are checked on bars only
        if o.role == "sl":
            if not o.triggered and q.bid <= float(o.stop_price):
                o.triggered = True
            if o.triggered and q.bid >= o.limit_price:
                self._fill(o, o.left, q.bid, now)
            return
        if o.side == "buy" and o.limit_price >= q.ask:
            self._fill(o, o.left, q.ask, now)
        elif o.side == "sell" and o.limit_price <= q.bid:
            self._fill(o, o.left, q.bid, now)

    def _match_bar(self, o: _Order, b: Bar, now: pd.Timestamp) -> None:
        if o.symbol != b.symbol or not self._fillable(o, now):
            return
        st = as_ny(b.start)
        if o.role in ("tp", "sl"):
            if o.fill_bar is None or st <= o.fill_bar:
                return
            parent = self.orders[o.parent] if o.parent else None
            sl = next((self.orders[x] for x in parent.legs if self.orders[x].role == "sl"), None) if parent else None
            tp = next((self.orders[x] for x in parent.legs if self.orders[x].role == "tp"), None) if parent else None
            # an open beyond the target fills the target at the open, before any stop check (signals.bar_exit's
            # order); MT-G4: strictly through the limit, not just touching it
            if tp is not None and self._fillable(tp, now) and b.open > tp.limit_price:
                self._fill(tp, tp.left, b.open, now)
                return
            # the stop first when both levels are inside one bar (the backtest's rule)
            if sl is not None and self._fillable(sl, now):
                stop = float(sl.stop_price)
                if b.open <= stop:
                    sl.triggered = True
                    if b.open >= sl.limit_price:
                        self._fill(sl, sl.left, b.open, now)
                        return
                    if b.high >= sl.limit_price:
                        self._fill(sl, sl.left, sl.limit_price, now)
                        return
                elif b.low <= stop:
                    sl.triggered = True
                    self._fill(sl, sl.left, stop, now)
                    return
                elif sl.triggered and b.high >= sl.limit_price:
                    self._fill(sl, sl.left, max(sl.limit_price, b.open if b.open >= sl.limit_price else 0.0), now)
                    return
            if tp is not None and self._fillable(tp, now):
                if b.open > tp.limit_price:                    # MT-G4: through the limit, not just touching it
                    self._fill(tp, tp.left, b.open, now)
                elif b.high > tp.limit_price:
                    self._fill(tp, tp.left, tp.limit_price, now)
            return
        if o.submitted_at is not None and st < o.submitted_at.floor("min"):
            return
        # MT-G4: a limit fills on a bar only when the bar TRADED THROUGH it (a low exactly at a buy limit is not a
        # fill: the queue ahead of us may have taken every share at that price)
        if o.side == "buy":
            if b.open < o.limit_price:
                self._fill(o, o.left, b.open, now, st)
            elif b.low < o.limit_price:
                self._fill(o, o.left, o.limit_price, now, st)
        else:
            if b.open > o.limit_price:
                self._fill(o, o.left, b.open, now, st)
            elif b.high > o.limit_price:
                self._fill(o, o.left, o.limit_price, now, st)


def sim_positions(pos: Mapping[str, float], price: float = 650.0) -> list[PositionView]:
    """Convenience for tests and the self-test: {"SPY": 1} -> [PositionView("SPY", 1, price)]."""
    return [PositionView(s, float(q), float(price)) for s, q in pos.items()]


__all__ = ["AlpacaBroker", "SimBroker", "PAPER_URL", "SCALP_KEYS", "check_spec", "classify", "is_done",
           "order_view", "position_view", "remaining", "reserved_sell_qty", "sim_positions"]
