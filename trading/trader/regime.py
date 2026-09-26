"""Deterministic market regime classifier (playbook: "A four-sleeve playbook...").

Precedence, most restrictive first: panic > bear > choppy > bull_volatile > bull_calm.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from . import indicators as ind
from .data import Bars

# Size multiplier per sleeve for each regime. Sleeve A always follows its own
# rules (they move to cash on their own); sleeve D follows its own BTC trend.
PERMISSIONS: dict[str, dict[str, float]] = {
    "bull_calm": {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0},
    "bull_volatile": {"A": 1.0, "B": 0.5, "C": 0.5, "D": 0.5},
    "bear": {"A": 1.0, "B": 0.0, "C": 0.0, "D": 1.0},
    "panic": {"A": 1.0, "B": 0.0, "C": 0.0, "D": 0.5},
    "choppy": {"A": 1.0, "B": 0.5, "C": 0.0, "D": 1.0},
}


@dataclass
class Regime:
    label: str
    spy_close: float
    spy_sma200: float
    vol20: float
    vol20_median_1y: float
    crossings_60d: int
    return_24m: float
    vol_top_quintile: bool
    breadth_above_200d: float
    canary_ok: bool | None
    permissions: dict[str, float]

    def to_dict(self) -> dict:
        return asdict(self)


def classify(bars: Bars, benchmark: str, universe: list[str], canaries: list[str]) -> Regime:
    spy = bars[benchmark]["close"].dropna()
    sma200 = ind.sma(spy, 200)
    vol20 = ind.realized_vol(spy, 20)

    above = (spy > sma200).dropna()
    last60 = above.iloc[-60:]
    crossings = int((last60.astype(int).diff().abs() == 1).sum())

    vol_now = float(vol20.iloc[-1])
    vol_median = float(vol20.iloc[-252:].median())
    vol_hist = vol20.iloc[-756:].dropna()
    vol_top_quintile = bool(vol_now >= np.nanpercentile(vol_hist, 80)) if len(vol_hist) > 20 else False
    ret24 = ind.total_return(spy, 504)

    breadth_members = [s for s in universe if s in bars and len(bars[s]) >= 200]
    if breadth_members:
        breadth = float(
            np.mean([bars[s]["close"].iloc[-1] > ind.sma(bars[s]["close"], 200).iloc[-1] for s in breadth_members])
        )
    else:
        breadth = float("nan")

    canary_ok: bool | None = None
    if all(c in bars for c in canaries):
        scores = [ind.momentum_13612w(ind.completed_month_closes(bars[c]["close"])) for c in canaries]
        if not any(np.isnan(scores)):
            canary_ok = all(s > 0 for s in scores)

    spy_above = bool(spy.iloc[-1] > sma200.iloc[-1])
    if not np.isnan(ret24) and ret24 < 0 and vol_top_quintile:
        label = "panic"
    elif not spy_above:
        label = "bear"
    elif crossings >= 3:
        label = "choppy"
    elif vol_now > vol_median:
        label = "bull_volatile"
    else:
        label = "bull_calm"

    return Regime(
        label=label,
        spy_close=float(spy.iloc[-1]),
        spy_sma200=float(sma200.iloc[-1]),
        vol20=vol_now,
        vol20_median_1y=vol_median,
        crossings_60d=crossings,
        return_24m=float(ret24),
        vol_top_quintile=vol_top_quintile,
        breadth_above_200d=breadth,
        canary_ok=canary_ok,
        permissions=dict(PERMISSIONS[label]),
    )
