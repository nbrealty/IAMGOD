"""Small shared data types."""
from __future__ import annotations

from dataclasses import dataclass, field, fields


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
    shadow: list[dict] = field(default_factory=list)  # TEST FIRST shadow signals: logged, never traded


@dataclass
class Order:
    symbol: str
    side: str  # "buy" or "sell"
    qty: float
    price: float  # reference price (last close) used for checks and the simulator
    reason: str = ""
    priority: int = 99  # EX-3: lower is kept first when the daily order cap drops buys
    client_order_id: str = ""


@dataclass
class Lot:
    """One sleeve's position in one symbol, from its first fill until it is back to zero (M-3).

    entry_price is the average cost of the shares still held, from real fill prices.
    initial_risk_dollars grows on every add by add_qty * (fill - stop_at_add), so R stays right after adds.
    realized_pnl is gross: sold_qty * (fill - entry_price) summed over reductions. costs holds the
    cost-model charge for every buy and sell. R_net = (realized_pnl - costs) / initial_risk_dollars.
    """

    qty: float
    entry_price: float
    entry_date: str  # signal date of the first entry (sessions held count bars after this date)
    stop: float | None = None
    initial_stop: float | None = None
    lot_id: str = ""
    initial_risk_dollars: float = 0.0
    bought_qty: float = 0.0  # total quantity ever added (for risk per share)
    realized_pnl: float = 0.0
    costs: float = 0.0
    events: list[dict] = field(default_factory=list)
    fill_date: str | None = None  # date of the first fill
    max_high: float | None = None  # highest high since entry, for MFE
    min_low: float | None = None  # lowest low since entry, for MAE
    tags: dict = field(default_factory=dict)  # CL-3: prompt_version, model, effort, context_schema, book

    def __post_init__(self) -> None:
        # Old state files: derive the new bookkeeping fields from what was stored.
        if not self.bought_qty and self.qty > 0:
            self.bought_qty = self.qty
        if not self.initial_risk_dollars and self.initial_stop is not None and self.qty > 0:
            self.initial_risk_dollars = max(0.0, (self.entry_price - self.initial_stop) * self.qty)

    @property
    def risk_per_share(self) -> float | None:
        if self.bought_qty > 0 and self.initial_risk_dollars > 0:
            return self.initial_risk_dollars / self.bought_qty
        return None

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["events"] = list(self.events)
        d["tags"] = dict(self.tags)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Lot":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})
