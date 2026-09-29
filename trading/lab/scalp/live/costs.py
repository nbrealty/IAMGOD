"""Trading costs: regulatory fee table with effective dates, honest P&L and slippage (MT-G3, MT-G4, MT-G1).

Alpaca charges no commission, and its paper account simulates NO regulatory fees (Alpaca paper-trading doc), so
the bot models them itself. Fees are a table of rows (component, rate, unit, start, end, source, verified);
`fees()` uses the rows in force on the trade date and raises for a date that a component has no row for (a
missing fee is never read as "free").

- SEC Section 31: on sales, per $1M of proceeds; Alpaca rounds it UP to the cent per trade.
- FINRA TAF: on sales, per share, capped per trade; Alpaca rounds it UP to the cent per trade.
  FINRA paused TAF for trades from 1 Oct to 31 Dec 2026 (SR-FINRA-2026-021, verified), but whether Alpaca stops
  passing it through is NOT verified, so the table keeps charging it (stricter; at most $0.01 per sell).
- CAT: both sides, per share (CAT Fee 2026-1 + Historical CAT Assessment 1A from May 2026); how Alpaca rounds it
  is not documented, so it is not rounded (about $0.000003 a share).
Values come from the build session's source check of 28 Sept 2026 (official SEC, FINRA, CAT NMS and Alpaca pages).

Two cost conventions (ChatGPT spec section 1): filled P&L already contains the spread (we paid the ask and sold
at the bid), so the spread is NEVER subtracted again. honest_pnl = paper P&L - $0.01/share per side - fees.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, Decimal
from typing import Iterable, Sequence

from .config import HONEST_SLIP_PER_SHARE

COMPONENTS = ("SEC", "TAF", "CAT")


@dataclass(frozen=True)
class FeeRow:
    component: str            # SEC | TAF | CAT (rows of one component in force on the same day add up)
    name: str
    rate: float
    unit: str                 # "per_million_sold" | "per_share_sold" | "per_share"
    start: date
    end: date | None          # inclusive; None = open-ended
    source: str
    verified: bool
    cap_per_trade: float | None = None
    round_up_cent: bool = False
    note: str = ""

    def covers(self, d: date) -> bool:
        return self.start <= d and (self.end is None or d <= self.end)


_SEC_ADV = "https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2"
_TAF_2026 = "https://www.finra.org/rules-guidance/rule-filings/sr-finra-2024-019/fee-adjustment-schedule"
_TAF_PAUSE = "https://www.sec.gov/files/rules/sro/finra/2026/34-106409.pdf"
FEE_TABLE: tuple[FeeRow, ...] = (
    FeeRow("SEC", "SEC Section 31 (zero rate)", 0.0, "per_million_sold", date(2026, 1, 1), date(2026, 4, 3),
           _SEC_ADV, True, round_up_cent=True, note="$0.00 per $1M through 3 Apr 2026"),
    FeeRow("SEC", "SEC Section 31", 20.60, "per_million_sold", date(2026, 4, 4), None, _SEC_ADV, True,
           round_up_cent=True, note="in effect until 60 days after the FY2027 appropriation is enacted"),
    FeeRow("TAF", "FINRA TAF", 0.000195, "per_share_sold", date(2026, 1, 1), date(2026, 9, 30), _TAF_2026, True,
           cap_per_trade=9.79, round_up_cent=True),
    FeeRow("TAF", "FINRA TAF (Q4 2026 FINRA fee holiday: still charged)", 0.000195, "per_share_sold",
           date(2026, 10, 1), date(2026, 12, 31), _TAF_PAUSE, False, cap_per_trade=9.79, round_up_cent=True,
           note="FINRA paused TAF 1 Oct-31 Dec 2026 (verified); Alpaca pass-through during the pause UNVERIFIED, "
                "so the normal rate is kept (stricter)"),
    FeeRow("TAF", "FINRA TAF", 0.000195, "per_share_sold", date(2027, 1, 1), None, _TAF_PAUSE, True,
           cap_per_trade=9.79, round_up_cent=True, note="rates held through 31 Dec 2028 (SR-FINRA-2026-020)"),
    FeeRow("CAT", "no industry-member CAT invoices", 0.0, "per_share", date(2025, 12, 1), date(2026, 4, 30),
           "https://www.catnmsplan.com/cat-fee-alerts", True),
    FeeRow("CAT", "CAT Fee 2026-1", 0.000001, "per_share", date(2026, 5, 1), None,
           "https://www.catnmsplan.com/sites/default/files/2026-04/04.01.26-CAT-Fee-Alert-2026-1.pdf", True,
           note="Alpaca rounding of CAT fees UNVERIFIED: not rounded here"),
    FeeRow("CAT", "Historical CAT Assessment 1A", 0.000002, "per_share", date(2026, 5, 1), None,
           "https://www.catnmsplan.com/sites/default/files/2026-04/04.01.26-CAT-Fee-Alert-2026-2.pdf", True,
           note="until about $39M is collected (about 2 years)"),
)


def _up_cent(x: float) -> float:
    return float(Decimal(repr(float(x))).quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def fee_breakdown(side: str, qty: float, price: float, on: date, table: Sequence[FeeRow] = FEE_TABLE
                  ) -> dict[str, float]:
    """Fees in dollars per component for one fill. Raises ValueError for a date some component does not cover."""
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be buy or sell, got {side!r}")
    if not (math.isfinite(qty) and math.isfinite(price)) or qty < 0 or price < 0:
        raise ValueError("qty and price must be finite and >= 0")
    out: dict[str, float] = {}
    for comp in COMPONENTS:
        rows = [r for r in table if r.component == comp and r.covers(on)]
        if not rows:
            raise ValueError(f"no {comp} fee row covers {on}: add one to costs.FEE_TABLE")
        total = 0.0
        for r in rows:
            if r.unit == "per_million_sold":
                v = qty * price * r.rate / 1e6 if side == "sell" else 0.0
            elif r.unit == "per_share_sold":
                v = qty * r.rate if side == "sell" else 0.0
            elif r.unit == "per_share":
                v = qty * r.rate
            else:
                raise ValueError(f"unknown fee unit {r.unit!r}")
            if r.cap_per_trade is not None:
                v = min(v, r.cap_per_trade)
            if r.round_up_cent and v > 0:
                v = _up_cent(v)
            total += v
        out[comp] = total
    return out


def fees(side: str, qty: float, price: float, on: date) -> float:
    """Total modelled regulatory fees for one fill (dollars)."""
    return sum(fee_breakdown(side, qty, price, on).values())


Fill = tuple[float, float]   # (qty, price)


def pnl_breakdown(buys: Iterable[Fill], sells: Iterable[Fill], on: date) -> dict[str, float]:
    """Paper P&L of a (long) round trip and its honest version (MT-G4). `buys` and `sells` are the fills as
    (qty, price). Honest = paper - HONEST_SLIP_PER_SHARE per share per side - modelled fees on every fill."""
    buys, sells = list(buys), list(sells)
    bq, sq = sum(q for q, _ in buys), sum(q for q, _ in sells)
    paper = sum(q * p for q, p in sells) - sum(q * p for q, p in buys)
    fee = sum(fees("buy", q, p, on) for q, p in buys) + sum(fees("sell", q, p, on) for q, p in sells)
    slip = HONEST_SLIP_PER_SHARE * (bq + sq)       # = $0.01 x shares x 2 for a closed round trip
    return {"paper_pnl": paper, "fees": fee, "honest_slip": slip, "honest_pnl": paper - slip - fee,
            "buy_qty": bq, "sell_qty": sq}


def honest_pnl(buys: Iterable[Fill], sells: Iterable[Fill], on: date) -> float:
    return pnl_breakdown(buys, sells, on)["honest_pnl"]


def slippage(side: str, fill: float, decision_mid: float) -> tuple[float, float]:
    """(cents per share, bps) against the mid at decision time; positive = worse for us (MT-G3)."""
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be buy or sell, got {side!r}")
    if not decision_mid > 0:
        raise ValueError("decision mid must be positive")
    diff = (fill - decision_mid) if side == "buy" else (decision_mid - fill)
    return round(diff * 100.0, 6), round(diff / decision_mid * 1e4, 6)
