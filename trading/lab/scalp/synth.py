"""Synthetic sessions for offline tests and demos (no network)."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .signals import Day

NY = "America/New_York"


def make_day(closes, opens=None, highs=None, lows=None, volume=1000.0, d: date = date(2026, 9, 21),
             close_min: int = 390, minutes=None, wick: float = 0.01) -> Day:
    """A session from a close path. Each open is the previous close unless given; wicks are +/- `wick`."""
    c = np.asarray(closes, dtype=float)
    o = np.asarray(opens, dtype=float) if opens is not None else np.r_[c[0], c[:-1]]
    h = np.asarray(highs, dtype=float) if highs is not None else np.maximum(o, c) + wick
    lo = np.asarray(lows, dtype=float) if lows is not None else np.minimum(o, c) - wick
    m = np.asarray(minutes, dtype=int) if minutes is not None else np.arange(len(c))
    v = np.broadcast_to(np.asarray(volume, dtype=float), c.shape).copy()
    return Day(d, pd.Timestamp(d).tz_localize(NY) + pd.Timedelta(hours=9, minutes=30), close_min, m, o, h, lo, c, v)


def flat_day(price: float = 100.0, n: int = 390, **kw) -> Day:
    return make_day(np.full(n, price), wick=0.0, **kw)


def random_day(seed: int = 0, n: int = 390, p0: float = 100.0, bps: float = 4.0, **kw) -> Day:
    rng = np.random.default_rng(seed)
    c = p0 * np.exp(np.cumsum(rng.normal(0, bps / 1e4, n)))
    vol = rng.integers(500, 5000, n).astype(float)
    return make_day(c, volume=vol, wick=0.02, **kw)


def random_frame(seed: int, days: list[date], p0: float = 100.0, bps: float = 4.0) -> pd.DataFrame:
    """Several sessions as a bar DataFrame indexed by New York bar-start time (like data.load_bars)."""
    frames, price = [], p0
    for k, d in enumerate(days):
        day = random_day(seed + k, p0=price, bps=bps, d=d)
        idx = pd.DatetimeIndex([day.ts(int(x)) for x in day.m], name="ts")
        frames.append(pd.DataFrame({"open": day.o, "high": day.h, "low": day.l, "close": day.c,
                                    "volume": day.v}, index=idx))
        price = float(day.c[-1])
    return pd.concat(frames)
