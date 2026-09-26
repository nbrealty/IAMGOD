import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trader.config import load_config  # noqa: E402


def make_bars(n=900, drift=0.0004, vol=0.01, seed=0, start_price=100.0, end=None, crypto=False):
    rng = np.random.default_rng(seed)
    freq = "D" if crypto else "B"
    end = pd.Timestamp(end or "2026-09-25")
    idx = pd.date_range(end=end, periods=n, freq=freq)
    rets = rng.normal(drift, vol, n)
    close = start_price * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, vol / 2, n)))
    low = close * (1 - np.abs(rng.normal(0, vol / 2, n)))
    open_ = np.r_[close[0], close[:-1]]
    volume = rng.integers(1_000_000, 2_000_000, n).astype(float)
    return pd.DataFrame({"open": open_, "high": np.maximum(high, np.maximum(open_, close)),
                         "low": np.minimum(low, np.minimum(open_, close)), "close": close, "volume": volume},
                        index=idx)


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def bars(cfg):
    out = {}
    for i, sym in enumerate(cfg.allowlist()):
        out[sym] = make_bars(seed=i + 1, drift=0.0005, crypto="/" in sym)
    return out
