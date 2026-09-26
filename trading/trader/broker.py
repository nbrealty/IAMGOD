"""Brokers: Alpaca paper trading, or a local simulator for dry runs and tests."""
from __future__ import annotations

import os
from typing import Protocol

from .models import Order


class Broker(Protocol):
    name: str

    def account(self) -> tuple[float, float]:
        """(equity, cash)"""

    def positions(self) -> dict[str, float]: ...

    def cancel_open_orders(self) -> None: ...

    def submit(self, orders: list[Order], client_prefix: str) -> list[dict]: ...


class AlpacaPaperBroker:
    """Alpaca paper account. Refuses to run against a live account."""

    name = "alpaca-paper"

    def __init__(self, key: str, secret: str, crypto_symbols: list[str]):
        from alpaca.trading.client import TradingClient

        self._client = TradingClient(key, secret, paper=True)
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

    def cancel_open_orders(self) -> None:
        self._client.cancel_orders()

    def submit(self, orders: list[Order], client_prefix: str) -> list[dict]:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        results = []
        for o in orders:
            req = MarketOrderRequest(
                symbol=o.symbol,
                qty=o.qty,
                side=OrderSide.BUY if o.side == "buy" else OrderSide.SELL,
                # Fractional stock orders must be DAY; after the close they queue for the next open.
                time_in_force=TimeInForce.GTC if "/" in o.symbol else TimeInForce.DAY,
                client_order_id=f"{client_prefix}-{o.symbol.replace('/', '')}-{o.side}"[:48],
            )
            try:
                r = self._client.submit_order(req)
                results.append({"symbol": o.symbol, "side": o.side, "qty": o.qty, "status": str(r.status),
                                "id": str(r.id)})
            except Exception as e:  # one bad order must not stop the others
                results.append({"symbol": o.symbol, "side": o.side, "qty": o.qty, "status": "error",
                                "error": str(e)})
        return results


class SimBroker:
    """Fills every order at the reference price plus a per-side cost. State lives in the book's state file."""

    name = "sim"

    def __init__(self, sim_state: dict, prices: dict[str, float], cost_bps: dict[str, int], asset_class):
        self.state = sim_state
        self.prices = prices
        self.cost_bps = cost_bps
        self.asset_class = asset_class

    def account(self) -> tuple[float, float]:
        cash = self.state["cash"]
        equity = cash + sum(q * self.prices.get(s, 0.0) for s, q in self.state["positions"].items())
        return equity, cash

    def positions(self) -> dict[str, float]:
        return {s: q for s, q in self.state["positions"].items() if q > 1e-12}

    def cancel_open_orders(self) -> None:
        pass

    def submit(self, orders: list[Order], client_prefix: str) -> list[dict]:
        results = []
        for o in orders:
            bps = self.cost_bps[self.asset_class(o.symbol)] / 10_000
            fill = o.price * (1 + bps if o.side == "buy" else 1 - bps)
            signed = o.qty if o.side == "buy" else -o.qty
            self.state["cash"] -= signed * fill
            self.state["positions"][o.symbol] = self.state["positions"].get(o.symbol, 0.0) + signed
            results.append({"symbol": o.symbol, "side": o.side, "qty": o.qty, "status": "filled",
                            "fill_price": round(fill, 4)})
        return results
