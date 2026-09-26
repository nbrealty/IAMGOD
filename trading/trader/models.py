"""Small shared data types."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Target:
    """Desired holding of one symbol inside one sleeve. qty 0 means exit."""

    symbol: str
    sleeve: str
    qty: float
    stop: float | None = None
    reason: str = ""


@dataclass
class SleevePlan:
    sleeve: str
    capital: float
    targets: dict[str, Target] = field(default_factory=dict)
    candidates: list[dict] = field(default_factory=list)  # indicator snapshots shown to Claude
    notes: list[str] = field(default_factory=list)


@dataclass
class Order:
    symbol: str
    side: str  # "buy" or "sell"
    qty: float
    price: float  # reference price (last close) used for checks and the simulator
    reason: str = ""


@dataclass
class Lot:
    qty: float
    entry_price: float
    entry_date: str
    stop: float | None = None
    initial_stop: float | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "Lot":
        return cls(**d)
