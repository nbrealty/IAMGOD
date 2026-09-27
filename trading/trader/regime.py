"""Deterministic market regime classifier (playbook: "A four-sleeve playbook...").

Precedence, most restrictive first: panic > bear > choppy > bull_volatile > bull_calm (REG-1, REG-2).
The label sets the sleeve permissions (REG-3). Everything else here is for display or shadow logging
only and never changes the label: temperature (REG-4), credit canary (REG-6), stock-bond monitor
(REG-7) and the DAA canary (REG-8).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from . import indicators as ind

if TYPE_CHECKING:
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

# REG-4 components, in the rulebook's order.
TEMPERATURE_COMPONENTS = (
    "spy_return_504d",      # (1) SPY 504-session return
    "spy_vol20_inverted",   # (2) 1 - percentile of SPY vol20
    "breadth_above_200d",   # (3) share of the C universe above its SMA200
    "spy_vs_sma200",        # (4) SPY close / SMA200 - 1
    "credit_hyg_ief_126d",  # (5) 126-session change of the HYG/IEF close ratio
)
MIN_COMPONENT_VALUES = 252  # REG-4: a component with less history than this is left out
STOCK_BOND_SESSIONS = 60    # REG-7
FILL_GAP_SESSIONS = 5       # a missing bar or two is bridged; a longer gap leaves the symbol out


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
    # Display and shadow fields (defaults keep the old positional construction working).
    temperature: float | None = None
    temperature_label: str = "unknown"
    temperature_components: dict = field(default_factory=dict)
    temperature_inputs: dict = field(default_factory=dict)
    temperature_note: str = ""
    breadth_above_50d: float = float("nan")
    stock_bond_corr: float | None = None
    bonds_not_hedging: bool = False
    credit_canary: dict | None = None

    def to_dict(self) -> dict:
        """JSON-safe copy for the context and journal: NaN and infinity become None."""
        return _json_safe(asdict(self))


def classify(bars: Bars, benchmark: str, universe: list[str], canaries: list[str], *,
             credit: tuple[str, str] | list[str] | None = ("HYG", "IEF"), bond: str = "IEF",
             lookback: int = 1260, hot: float = 0.80, cold: float = 0.20, corr_flag: float = 0.30) -> Regime:
    """Label today's market (REG-1..3) and attach the display-only readings (REG-4, 6, 7, 8)."""
    spy = _benchmark_closes(bars, benchmark)
    trend = _trend_fields(spy)
    closes = _aligned_closes(bars, universe, spy.index)
    temp, temp_label, components, inputs, note = compute_temperature(
        bars, spy, universe, credit=credit, lookback=lookback, hot=hot, cold=cold, universe_closes=closes)
    corr, not_hedging = stock_bond(bars, spy, bond, corr_flag)
    return Regime(
        **trend,
        breadth_above_200d=_breadth_now(closes, 200),
        canary_ok=_daa_canary(bars, canaries),
        permissions=dict(PERMISSIONS[trend["label"]]),
        temperature=temp,
        temperature_label=temp_label,
        temperature_components=components,
        temperature_inputs=inputs,
        temperature_note=note,
        breadth_above_50d=_breadth_now(closes, 50),
        stock_bond_corr=corr,
        bonds_not_hedging=not_hedging,
        credit_canary=credit_canary(bars, credit, trend["label"], spy.index),
    )


def classify_kwargs(regime_cfg: dict | None) -> dict:
    """Keyword arguments for `classify` from `playbook["regime"]` (REG-4, REG-7 settings).

    A missing or null number falls back to its default; `credit: null` (or anything that is not a
    list of symbols) turns the credit pair off instead of crashing.
    """
    rc = regime_cfg or {}

    def num(key: str, default: float) -> float:
        v = rc.get(key)
        return default if v is None else v

    credit = rc.get("credit", ("HYG", "IEF"))
    return {
        "credit": tuple(credit) if isinstance(credit, (list, tuple)) else None,
        "lookback": int(num("temperature_lookback", 1260)),
        "hot": float(num("hot", 0.80)),
        "cold": float(num("cold", 0.20)),
        "corr_flag": float(num("stock_bond_corr_flag", 0.30)),
    }


# --- REG-1 / REG-2: the label (unchanged logic) ---------------------------------------------------


def _benchmark_closes(bars: Bars, benchmark: str) -> pd.Series:
    df = bars.get(benchmark)
    spy = df["close"].dropna() if df is not None and "close" in df else pd.Series(dtype=float)
    if spy.empty:
        raise ValueError(f"no {benchmark} closes: the regime cannot be classified without the benchmark")
    return spy


def _trend_fields(spy: pd.Series) -> dict:
    """REG-1 trend and the REG-2 label, most restrictive first."""
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

    return {
        "label": label,
        "spy_close": float(spy.iloc[-1]),
        "spy_sma200": float(sma200.iloc[-1]),
        "vol20": vol_now,
        "vol20_median_1y": vol_median,
        "crossings_60d": crossings,
        "return_24m": float(ret24),
        "vol_top_quintile": vol_top_quintile,
    }


def _breadth_now(closes: pd.DataFrame, n: int) -> float:
    """Share of the universe above its n-day SMA today (REG-4 display; NaN if too few qualify).

    Uses the same benchmark-aligned closes as the temperature, so the 50- and 200-day shares are
    measured the same way and a stale symbol is left out instead of being read on old data.
    """
    if closes.empty:
        return float("nan")
    return float(ind.share_above_sma(closes, n).iloc[-1])


def _daa_canary(bars: Bars, canaries: list[str]) -> bool | None:
    """REG-8: VWO and BND 13612W both > 0. Displayed only."""
    if not all(c in bars for c in canaries):
        return None
    scores = [ind.momentum_13612w(ind.completed_month_closes(bars[c]["close"])) for c in canaries]
    if any(np.isnan(scores)):
        return None
    return all(s > 0 for s in scores)


# --- REG-4: temperature (display only) ------------------------------------------------------------


def compute_temperature(bars: Bars, spy: pd.Series, universe: list[str], *, credit=("HYG", "IEF"),
                        lookback: int = 1260, hot: float = 0.80, cold: float = 0.20,
                        universe_closes: pd.DataFrame | None = None):
    """REG-4 temperature T = mean of the available component percentiles; never traded.

    Returns (T or None, label, components, inputs, note). `components` maps each component to its
    percentile (or None when it has fewer than 252 values) plus `n_sessions`, `n_used` and
    `n_values` (how many sessions each percentile was ranked on; fewer than `lookback` means a short
    window, which the note says). `inputs` holds today's raw value of each component (for vol20,
    the volatility itself, before inverting). The label is decided on unrounded values; rounding
    is for display only.
    """
    series = _component_series(bars, spy, universe, credit, universe_closes)
    raw: dict[str, float] = {}
    n_values: dict[str, int] = {}
    inputs: dict = {}
    for name in TEMPERATURE_COMPONENTS:
        s = series.get(name)
        n_values[name] = _window_count(s, lookback)
        pct = ind.percentile_rank(s, lookback, MIN_COMPONENT_VALUES) if s is not None else float("nan")
        if name == "spy_vol20_inverted":
            pct = 1.0 - pct  # calm (low volatility) reads hot
        if not math.isnan(pct):
            raw[name] = pct
        inputs[name] = _last_value(s)

    t_raw = float(np.mean(list(raw.values()))) if raw else None
    label = _temperature_label(t_raw, hot, cold)
    components: dict = {k: round(raw[k], 4) if k in raw else None for k in TEMPERATURE_COMPONENTS}
    components["n_sessions"] = int(len(spy))
    components["n_used"] = len(raw)
    components["n_values"] = n_values
    temp = round(t_raw, 4) if t_raw is not None else None
    return temp, label, components, inputs, _temperature_note(temp, label, components, lookback)


def _component_series(bars: Bars, spy: pd.Series, universe: list[str], credit,
                      universe_closes: pd.DataFrame | None = None) -> dict[str, pd.Series]:
    """Each REG-4 component as a daily series on the benchmark's calendar (vectorized)."""
    if universe_closes is None:
        universe_closes = _aligned_closes(bars, universe, spy.index)
    sma200 = ind.sma(spy, 200)
    out = {
        "spy_return_504d": spy / spy.shift(504) - 1.0,
        "spy_vol20_inverted": ind.realized_vol(spy, 20),
        "breadth_above_200d": ind.share_above_sma(universe_closes, 200),
        "spy_vs_sma200": spy / sma200 - 1.0,
    }
    pair = _credit_pair(bars, credit)
    if pair is not None:
        frame = _aligned_closes(bars, list(pair), spy.index)
        if frame.shape[1] == 2:
            ratio = frame.iloc[:, 0] / frame.iloc[:, 1]  # prices <= 0 are already NaN
            out["credit_hyg_ief_126d"] = ratio / ratio.shift(126) - 1.0
    return out


def _aligned_closes(bars: Bars, symbols: list[str], index: pd.Index) -> pd.DataFrame:
    """Closes of `symbols` side by side on `index`; short gaps are bridged, missing symbols left out."""
    cols = {}
    for s in dict.fromkeys(symbols):
        df = bars.get(s)
        if df is None or "close" not in df or df.empty:
            continue
        close = df["close"].astype(float)
        cols[s] = close[~close.index.duplicated(keep="last")]
    if not cols:
        return pd.DataFrame(index=index, dtype=float)
    frame = pd.DataFrame(cols).reindex(index).ffill(limit=FILL_GAP_SESSIONS)
    return frame.where(frame > 0)


def _temperature_label(temp: float | None, hot: float, cold: float) -> str:
    if temp is None:
        return "unknown"
    if temp >= hot:
        return "hot"
    if temp <= cold:
        return "cold"
    return "neutral"


def _temperature_note(temp: float | None, label: str, components: dict, lookback: int) -> str:
    """Plain-English line saying how many components the reading used and which windows were short."""
    missing = [k for k in TEMPERATURE_COMPONENTS if components.get(k) is None]
    total = len(TEMPERATURE_COMPONENTS)
    if temp is None:
        return f"unknown: no component has {MIN_COMPONENT_VALUES} sessions of history yet (display only)"
    text = f"{label}: T {temp:.4f} from {total - len(missing)} of {total} components (display only)"
    if missing:
        text += "; left out for lack of data: " + ", ".join(missing)
    n_values = components.get("n_values", {})
    short = [f"{k} ranked on {n_values[k]} of {lookback} sessions" for k in TEMPERATURE_COMPONENTS
             if components.get(k) is not None and n_values.get(k, lookback) < lookback]
    if short:
        text += "; short history: " + ", ".join(short)
    return text


def _window_count(series: pd.Series | None, lookback: int) -> int:
    """Usable (finite) values in the series' last `lookback` sessions: what the percentile ranks against."""
    if series is None or lookback < 1:
        return 0
    return int(np.isfinite(series.iloc[-lookback:].to_numpy(dtype=float, na_value=np.nan)).sum())


def _last_value(series: pd.Series | None) -> float | None:
    if series is None or len(series) == 0:
        return None
    v = float(series.iloc[-1])
    return round(v, 6) if math.isfinite(v) else None


# --- REG-6 credit canary (shadow value only) and REG-7 stock-bond monitor --------------------------


def credit_canary(bars: Bars, credit, label: str, sessions: pd.Index) -> dict | None:
    """REG-6 (TEST FIRST): would 13612W(HYG) - 13612W(IEF) < 0 downgrade bull_calm? Never changes the label.

    `sessions` is the benchmark calendar; month-ends are taken as of its last date. None when either
    symbol is missing, stale (its feed stopped more than FILL_GAP_SESSIONS sessions ago) or short.
    """
    pair = _credit_pair(bars, credit)
    if pair is None or not all(_is_fresh(bars, s, sessions) for s in pair):
        return None
    as_of = sessions[-1]
    hyg, ief = (ind.momentum_13612w(ind.completed_month_closes(_positive_closes(bars[s]), as_of)) for s in pair)
    if not (math.isfinite(hyg) and math.isfinite(ief)):
        return None
    negative = bool(hyg - ief < 0)
    would = negative and label == "bull_calm"
    return {
        "hyg_13612w": round(float(hyg), 4),
        "ief_13612w": round(float(ief), 4),
        "spread": round(float(hyg - ief), 4),
        "signal_negative": negative,
        "would_downgrade": would,
        "label_if_applied": "bull_volatile" if would else label,
    }


def stock_bond(bars: Bars, spy: pd.Series, bond: str = "IEF", flag: float = 0.30) -> tuple[float | None, bool]:
    """REG-7: 60-session correlation of SPY and bond daily returns; above `flag` = "bonds not hedging".

    Display only: it never changes the label, permissions or any order. None when the bond is
    missing or its feed stopped more than FILL_GAP_SESSIONS sessions ago (an old reading is not today's).
    """
    if not _is_fresh(bars, bond, spy.index):
        return None, False
    corr = ind.return_correlation(spy, bars[bond]["close"].astype(float), STOCK_BOND_SESSIONS)
    if not math.isfinite(corr):
        return None, False
    return round(corr, 4), bool(corr > flag)  # the flag uses the unrounded value; rounding is display


def _positive_closes(df: pd.DataFrame) -> pd.Series:
    """Closes with zero or negative prints removed (bad data, not a -100% day)."""
    close = df["close"].astype(float)
    return close[close > 0]


def _is_fresh(bars: Bars, symbol: str, sessions: pd.Index) -> bool:
    """True when the symbol's last usable close is at most FILL_GAP_SESSIONS benchmark sessions old.

    Same tolerance as `_aligned_closes`, so a feed outage drops every reading of that symbol together.
    """
    df = bars.get(symbol)
    if df is None or "close" not in df or len(sessions) == 0:
        return False
    close = _positive_closes(df)
    if close.empty:
        return False
    return int((sessions > close.index.max()).sum()) <= FILL_GAP_SESSIONS


def _credit_pair(bars: Bars, credit) -> tuple[str, str] | None:
    """The (high-yield, treasury) symbols when both have closes, else None."""
    if not credit or len(credit) != 2:
        return None
    pair = (str(credit[0]), str(credit[1]))
    if pair[0] == pair[1]:
        return None
    for s in pair:
        df = bars.get(s)
        if df is None or "close" not in df or df["close"].dropna().empty:
            return None
    return pair


def _json_safe(x):
    """Plain Python types with NaN/inf as None, so `json.dumps(..., allow_nan=False)` works."""
    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_safe(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if math.isfinite(x) else None
    return x
