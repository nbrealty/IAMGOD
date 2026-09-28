"""Runaway-order guard (MT-G25): a separate backstop between the engine and any broker.

The decision code (risk.py) already refuses entries that break a cap. This module does not trust it: every order
the engine sends goes through `GuardedBroker.submit`, which counts on its own.

- ENTRY specs: at most MAX_ENTRY_SUBMITS_PER_MIN in any rolling 60 s, MAX_ENTRY_SUBMITS_DAY per session,
  MAX_OPEN_PARENTS open parent orders at the broker, qty <= the sizing maximum (EXPLORATORY_MAX_QTY), today's
  notional (the planned round trip counts twice) <= MAX_NOTIONAL_DAY_X_E0 x E0, symbol on the allowlist, a
  SCALP- client id and a spec the order builder accepts. A breach sends NOTHING and raises RunawayOrders; the
  engine answers with the kill switch (the Knight Capital lesson: a bug upstream must not become 4 million
  orders). An attempt is counted before it is sent, so a timeout still uses up budget.
- EXIT / PROTECT specs have their own budget (MAX_EXIT_ORDERS_PER_MIN). Going over it only DELAYS the order
  (ExitDelayed, journalled; the engine tries again on the next tick). It never kills: the way out stays open.
- Cancels always pass (they only reduce risk).
Reads (positions, orders, account) are passed straight through.
"""
from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from . import config as C
from . import orders as O
from .model import Journal, Kind, OrderSpec, OrderView, RunawayOrders, as_ny

WINDOW = pd.Timedelta(seconds=60)


class ExitDelayed(Exception):
    """The exit budget for this minute is used up: try the exit again on the next tick (never a kill)."""


class GuardedBroker:
    def __init__(self, broker: Any, clock: Callable[[], pd.Timestamp], journal: Journal, e0: float | None = None):
        if isinstance(broker, GuardedBroker):
            raise TypeError("the broker is already guarded")
        self.broker, self.clock, self.journal, self.e0 = broker, clock, journal, e0
        self.mode = getattr(broker, "mode", None)
        self.entry_times: list[pd.Timestamp] = []
        self.entry_count = 0
        self.entry_notional = 0.0
        self.exit_times: list[pd.Timestamp] = []
        self.day = None

    # ------------------------------------------------------------------ state
    def seed(self, entry_times: list[pd.Timestamp], entry_count: int, notional: float) -> None:
        """Restart (MT-G40): carry today's counts over from the rebuilt counters."""
        self.entry_times = [as_ny(t) for t in entry_times]
        self.entry_count = int(entry_count)
        self.entry_notional = float(notional)
        self.day = as_ny(self.clock()).date()

    def _roll(self, now: pd.Timestamp) -> None:
        if self.day != now.date():
            self.day, self.entry_times, self.entry_count, self.entry_notional = now.date(), [], 0, 0.0
            self.exit_times = []
        self.entry_times = [t for t in self.entry_times if now - t < WINDOW]
        self.exit_times = [t for t in self.exit_times if now - t < WINDOW]

    def _open_parents(self) -> int:
        n = 0
        for o in self.broker.open_orders():
            p = O.parse_client_id(o.client_order_id)
            if p is not None and p["leg"] == "E" and o.side == "buy":
                n += 1
        return n

    def entry_breaches(self, spec: OrderSpec, now: pd.Timestamp) -> list[str]:
        """Every cap this ENTRY would break (empty = it may go)."""
        b: list[str] = []
        if len(self.entry_times) >= C.MAX_ENTRY_SUBMITS_PER_MIN:
            b.append(f"{len(self.entry_times)} entry submissions in the last 60 s (max {C.MAX_ENTRY_SUBMITS_PER_MIN})")
        if self.entry_count >= C.MAX_ENTRY_SUBMITS_DAY:
            b.append(f"{self.entry_count} entry submissions today (max {C.MAX_ENTRY_SUBMITS_DAY})")
        if spec.qty > C.EXPLORATORY_MAX_QTY:
            b.append(f"qty {spec.qty} above the sizing maximum {C.EXPLORATORY_MAX_QTY}")
        if spec.symbol not in C.ALLOWED_SYMBOLS:
            b.append(f"symbol {spec.symbol} not on the allowlist")
        if not spec.client_order_id.startswith(C.ORDER_PREFIX):
            b.append("client id without the SCALP- prefix")
        b += [f"spec: {p}" for p in O.validate(spec)]
        if self.e0 is None or not self.e0 > 0:
            b.append("no E0: the notional cap cannot be checked")
        elif self.entry_notional + 2.0 * spec.qty * spec.limit_price > C.MAX_NOTIONAL_DAY_X_E0 * self.e0 + 1e-9:
            b.append(f"today's notional would pass {C.MAX_NOTIONAL_DAY_X_E0} x E0")
        if not b and self._open_parents() >= C.MAX_OPEN_PARENTS:
            b.append(f"an entry parent is already open (max {C.MAX_OPEN_PARENTS})")
        return b

    # ------------------------------------------------------------------ orders
    def submit(self, spec: OrderSpec) -> OrderView:
        now = as_ny(self.clock())
        self._roll(now)
        kind = Kind(spec.kind)
        if kind is Kind.ENTRY:
            breaches = self.entry_breaches(spec, now)
            if breaches:
                self.journal.write("runaway_blocked", cid=spec.client_order_id, symbol=spec.symbol, qty=spec.qty,
                                   limit=spec.limit_price, breaches=breaches)
                raise RunawayOrders("; ".join(breaches))
            self.entry_times.append(now)
            self.entry_count += 1
            self.entry_notional += 2.0 * spec.qty * spec.limit_price
            return self.broker.submit(spec)
        if spec.side != "sell" or spec.order_class != "simple":
            raise RunawayOrders(f"{kind.value} orders are simple sells only")
        if len(self.exit_times) >= C.MAX_EXIT_ORDERS_PER_MIN:
            self.journal.write("exit_delayed", cid=spec.client_order_id, symbol=spec.symbol, order_kind=kind.value,
                               sent_last_60s=len(self.exit_times))
            raise ExitDelayed(f"{len(self.exit_times)} exit orders in the last 60 s")
        self.exit_times.append(now)
        return self.broker.submit(spec)

    def cancel(self, order_id: str) -> None:
        self.broker.cancel(order_id)

    # ------------------------------------------------------------------ reads pass through
    def __getattr__(self, name: str) -> Any:
        return getattr(self.broker, name)
