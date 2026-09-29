"""Fixed position sizing (MT-G14). One pure function with a fixed signature.

Size never depends on how the day, the week or anyone's mood is going: the only inputs are the day's starting
equity E0 (Alpaca `last_equity`), the entry limit, the stop, the stop-limit's limit price and the lane. Any other
argument (a `confidence`, a `pnl_today`) is a TypeError because the function simply has no such parameter.

    qty = floor(RISK_PCT x E0 / (entry_limit - stop_limit))   risk sized on the WORST stop fill (MT-G21)
    qty = min(qty, floor(NOTIONAL_CAP_PCT x E0 / entry_limit))
    qty = min(qty, EXPLORATORY_MAX_QTY)                        exploratory lane (1 share)
    qty = 0                                                    shadow or retired lane, or any bad input

Never rounded up; 0 means no trade. The floors are checked back with multiplication so float division can never
round a quantity above either budget.
"""
from __future__ import annotations

import math
from numbers import Real

from . import config as C
from .model import Lane


def _floor_within(budget: float, per_unit: float) -> int:
    q = math.floor(budget / per_unit)
    while q > 0 and q * per_unit > budget:
        q -= 1
    return max(q, 0)


def qty(e0: float, entry_limit: float, stop: float, stop_limit: float, lane: Lane) -> int:
    """Shares to buy for a long entry; 0 = no trade."""
    lane = Lane(lane)
    vals = (e0, entry_limit, stop, stop_limit)
    if lane in (Lane.SHADOW, Lane.RETIRED):
        return 0
    if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) or v <= 0 for v in vals):
        return 0
    if entry_limit <= stop_limit or stop >= entry_limit or stop_limit > stop:
        return 0
    q = min(_floor_within(C.RISK_PCT * e0, entry_limit - stop_limit),
            _floor_within(C.NOTIONAL_CAP_PCT * e0, entry_limit))
    if lane is Lane.EXPLORATORY:
        q = min(q, C.EXPLORATORY_MAX_QTY)
    return int(q)
