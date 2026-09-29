"""Option data types for book O (reports/Options rulebook.md, implementation plan phase O1).

Money is in dollars per spread position (not per share) unless a name says `_per_share`.
One contract controls 100 shares. A spread is always 2 legs: same underlying, expiry and type,
1:1, one long and one short (OPT-3).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from datetime import date

MULTIPLIER = 100
OCC_RE = re.compile(r"^(?P<root>[A-Z]{1,6})(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})(?P<cp>[CP])(?P<strike>\d{8})$")


def is_occ(symbol: str) -> bool:
    """True for an OCC option symbol such as SPY261023P00700000 (OPT-2: the stock path must reject these)."""
    return bool(OCC_RE.match(str(symbol or "")))


def parse_occ(symbol: str) -> dict:
    m = OCC_RE.match(symbol)
    if not m:
        raise ValueError(f"not an OCC option symbol: {symbol!r}")
    return {
        "underlying": m["root"],
        "expiry": date(2000 + int(m["yy"]), int(m["mm"]), int(m["dd"])).isoformat(),
        "type": "call" if m["cp"] == "C" else "put",
        "strike": int(m["strike"]) / 1000.0,
    }


def occ_symbol(underlying: str, expiry: str, opt_type: str, strike: float) -> str:
    y, mth, d = expiry.split("-")
    return f"{underlying}{y[2:]}{mth}{d}{'C' if opt_type == 'call' else 'P'}{int(round(strike * 1000)):08d}"


@dataclass
class OptionQuote:
    """One contract from a chain snapshot (OPT-35 logger row)."""

    symbol: str
    underlying: str
    expiry: str
    type: str  # "put" | "call"
    strike: float
    bid: float | None
    ask: float | None
    quote_time: str | None  # ISO timestamp
    iv: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    open_interest: int | None = None
    open_interest_date: str | None = None
    volume: int | None = None
    tradable: bool = True
    feed: str = "indicative"

    @property
    def mid(self) -> float | None:
        if self.bid is None or self.ask is None or self.bid < 0 or self.ask <= 0 or self.ask < self.bid:
            return None
        return (self.bid + self.ask) / 2

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, d: dict) -> "OptionQuote":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class OptionLeg:
    symbol: str  # OCC
    type: str  # "put" | "call"
    strike: float
    expiry: str
    side: str  # "long" | "short"
    qty: int  # contracts, always > 0


@dataclass
class SpreadLot:
    """One open vertical spread in book O (OPT-3, OPT-7). R_net = (P&L - costs) / max_loss."""

    lot_id: str
    underlying: str
    expiry: str
    type: str  # "put" (bull put credit spread, OPT-18)
    short_leg: OptionLeg
    long_leg: OptionLeg
    contracts: int
    width: float  # strike distance in $ per share
    entry_credit_per_share: float  # positive = credit received
    max_loss: float  # (width - credit) * 100 * contracts: initial_risk_dollars
    budgeted_loss: float  # max_loss + quoted cost at entry (OPT-8)
    entry_date: str
    status: str = "open"  # "pending_entry" | "open" | "pending_exit" | "closed"
    shadow: bool = True  # True until OPT-41 passes and the owner turns paper orders on
    exit_debit_per_share: float | None = None
    realized_pnl: float = 0.0
    costs: float = 0.0
    events: list[dict] = field(default_factory=list)
    tags: dict = field(default_factory=dict)

    @property
    def r_net(self) -> float | None:
        if self.status != "closed" or self.max_loss <= 0:
            return None
        return (self.realized_pnl - self.costs) / self.max_loss

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["short_leg"] = dict(self.short_leg.__dict__)
        d["long_leg"] = dict(self.long_leg.__dict__)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SpreadLot":
        known = {f.name for f in fields(cls)}
        d = {k: v for k, v in d.items() if k in known}
        d["short_leg"] = OptionLeg(**d["short_leg"])
        d["long_leg"] = OptionLeg(**d["long_leg"])
        return cls(**d)
