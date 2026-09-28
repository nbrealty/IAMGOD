"""Model option prices for book O: Black-Scholes, a VIX x skew table, and Cboe index history.

This is the pricing half of the RPL method (reports/Options rulebook.md) that the OPT-37 backtester uses:
Black-Scholes on raw closes, with implied vol = Cboe volatility index x a skew ratio by moneyness and DTE bucket,
calibrated on Alpaca option bars since Feb 2024 (`calibrate_skew`, stored in `config/options_skew.yaml`).
`fetch_cboe_index` gives the VIX / VIX3M history for the backtester and for OPT-20 (VIX/VIX3M, logged only).

Units: volatilities, rates and dividend yields are fractions (0.185 = 18.5%). Cboe publishes index points (18.5);
`fetch_cboe_index` converts to fractions by default and `model_iv` accepts either. Prices are per share.
Nothing here places orders; the only network calls are read-only public data (Cboe CSV, Alpaca option bars).
"""
from __future__ import annotations

import io
import math
import re
import copy
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd
import yaml

from ..config import CONFIG_DIR, STATE_DIR
from .models import occ_symbol

SKEW_PATH = CONFIG_DIR / "options_skew.yaml"
CBOE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{name}_History.csv"
POINT_INDEXES = ("SKEW",)  # Cboe indexes that are not volatilities: never divided by 100
DAYS_PER_YEAR = 365.0
IV_LO, IV_HI = 1e-4, 5.0


class CboeDataError(RuntimeError):
    """Cboe history could not be fetched and there is no cached copy."""


# --- Black-Scholes (European, continuous dividend yield) -------------------------------------------------


def _ncdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _npdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _kind(kind: str) -> str:
    k = str(kind or "").strip().lower()
    if k in ("put", "p"):
        return "put"
    if k in ("call", "c"):
        return "call"
    raise ValueError(f"option kind must be 'put' or 'call', got {kind!r}")


def _positive(name: str, x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number, got {x!r}") from None
    if not math.isfinite(v) or v <= 0:
        raise ValueError(f"{name} must be a positive finite number, got {x!r}")
    return v


def _finite(name: str, x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number, got {x!r}") from None
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite, got {x!r}")
    return v


def years(dte: float) -> float:
    """Calendar days to expiry -> years (the rulebook's DTE is calendar days)."""
    return max(0.0, float(dte)) / DAYS_PER_YEAR


def _d1_d2(spot, strike, t, vol, rate, div_yield):
    sq = vol * math.sqrt(t)
    d1 = (math.log(spot / strike) + (rate - div_yield + 0.5 * vol * vol) * t) / sq
    return d1, d1 - sq


def _checked(spot, strike, t, vol, rate, div_yield):
    spot, strike = _positive("spot", spot), _positive("strike", strike)
    t = _finite("t_years", t)
    vol = _finite("vol", vol)
    if vol < 0:
        raise ValueError(f"vol must be >= 0, got {vol!r}")
    return spot, strike, t, vol, _finite("rate", rate), _finite("div_yield", div_yield)


def bs_price(spot, strike, t_years, vol, kind="put", rate=0.0, div_yield=0.0) -> float:
    """OPT-37 (RPL): Black-Scholes price per share of a European put or call with a continuous dividend yield.

    At or after expiry (t <= 0) it returns the intrinsic value; with zero vol, the discounted forward intrinsic.
    """
    spot, strike, t, vol, rate, div_yield = _checked(spot, strike, t_years, vol, rate, div_yield)
    kind = _kind(kind)
    if t <= 0:
        return max(strike - spot, 0.0) if kind == "put" else max(spot - strike, 0.0)
    fwd_s, pv_k = spot * math.exp(-div_yield * t), strike * math.exp(-rate * t)
    if vol == 0:
        return max(pv_k - fwd_s, 0.0) if kind == "put" else max(fwd_s - pv_k, 0.0)
    d1, d2 = _d1_d2(spot, strike, t, vol, rate, div_yield)
    if kind == "put":
        return pv_k * _ncdf(-d2) - fwd_s * _ncdf(-d1)
    return fwd_s * _ncdf(d1) - pv_k * _ncdf(d2)


def bs_delta(spot, strike, t_years, vol, kind="put", rate=0.0, div_yield=0.0) -> float:
    """OPT-37: Black-Scholes delta per share (a put's delta is negative, -0.20 means '20 delta').

    At expiry or with zero vol: the in/out-of-the-money step (-1/0 for puts, 1/0 for calls; half at the strike).
    """
    spot, strike, t, vol, rate, div_yield = _checked(spot, strike, t_years, vol, rate, div_yield)
    kind = _kind(kind)
    if t <= 0 or vol == 0:
        fwd_s = spot * math.exp(-div_yield * max(t, 0.0))
        pv_k = strike * math.exp(-rate * max(t, 0.0))
        itm_call = 1.0 if fwd_s > pv_k else 0.0 if fwd_s < pv_k else 0.5
        disc = math.exp(-div_yield * max(t, 0.0))
        return disc * (itm_call - 1.0) if kind == "put" else disc * itm_call
    d1, _ = _d1_d2(spot, strike, t, vol, rate, div_yield)
    disc = math.exp(-div_yield * t)
    return disc * (_ncdf(d1) - 1.0) if kind == "put" else disc * _ncdf(d1)


def bs_vega(spot, strike, t_years, vol, rate=0.0, div_yield=0.0) -> float:
    """OPT-37: Black-Scholes vega per share per 1.00 of vol (divide by 100 for one vol point). Same for puts and calls."""
    spot, strike, t, vol, rate, div_yield = _checked(spot, strike, t_years, vol, rate, div_yield)
    if t <= 0 or vol == 0:
        return 0.0
    d1, _ = _d1_d2(spot, strike, t, vol, rate, div_yield)
    return spot * math.exp(-div_yield * t) * _npdf(d1) * math.sqrt(t)


def implied_vol(price, spot, strike, t_years, kind="put", rate=0.0, div_yield=0.0,
                lo: float = IV_LO, hi: float = IV_HI, tol: float = 1e-7) -> float | None:
    """OPT-37 calibration input: the vol that makes `bs_price` equal `price`, or None when there is none.

    None (never a guess) for a missing/non-positive price, expired contracts, or a price outside the no-arbitrage
    range [intrinsic at vol lo, price at vol hi]. Bisection, so it always converges.
    """
    try:
        p = float(price)
        spot, strike, t, _, rate, div_yield = _checked(spot, strike, t_years, 0.0, rate, div_yield)
        kind = _kind(kind)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(p) or p <= 0 or t <= 0:
        return None
    f = lambda v: bs_price(spot, strike, t, v, kind, rate, div_yield) - p  # noqa: E731
    f_lo, f_hi = f(lo), f(hi)
    if f_lo > 0 or f_hi < 0:
        return None
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if abs(f_mid) < tol or hi - lo < tol:
            return mid
        if f_mid < 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --- skew table ----------------------------------------------------------------------------------------


def load_skew_table(path: str | Path | None = None) -> dict:
    """Read `config/options_skew.yaml` (or `path`) and check it (OPT-37). Raises ValueError on a broken table."""
    with open(path or SKEW_PATH) as f:
        table = yaml.safe_load(f) or {}
    validate_skew_table(table)
    return table


def _num(where: str, x) -> float:
    """A finite number from a table field, or ValueError naming the field (never TypeError/AttributeError)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        raise ValueError(f"skew table: {where} must be a number, got {x!r}") from None
    if not math.isfinite(v):
        raise ValueError(f"skew table: {where} must be finite, got {x!r}")
    return v


def _nums(where: str, xs) -> list[float]:
    if not isinstance(xs, (list, tuple)):
        raise ValueError(f"skew table: {where} must be a list, got {xs!r}")
    return [_num(f"{where}[{i}]", x) for i, x in enumerate(xs)]


def validate_skew_table(table: dict) -> None:
    """Refuse a table the model cannot use (OPT-37): every check raises ValueError instead of pricing garbage.

    Checks: buckets are dicts with equal-length, finite, strictly increasing moneyness nodes and positive finite
    ratios; dte_min <= dte_max; 0 < vix_low < vix_high <= 3 (fractions, not Cboe points); 0 < iv_bounds[0] <
    iv_bounds[1]; put_wing_slope >= 0; call block with atm > 0, 0 < floor <= atm, slope >= 0.
    """
    if not isinstance(table, dict) or not table.get("buckets"):
        raise ValueError("skew table has no buckets")
    if not isinstance(table["buckets"], (list, tuple)):
        raise ValueError("skew table: buckets must be a list")
    lo, hi = _num("vix_low", table.get("vix_low", 0.15)), _num("vix_high", table.get("vix_high", 0.25))
    if not (0 < lo < hi <= 3.0):
        raise ValueError(f"skew table needs 0 < vix_low < vix_high <= 3 (fractions: 0.15, not 15), got {lo}, {hi}")
    bounds = _nums("iv_bounds", table.get("iv_bounds", [0.01, 3.0]))
    if len(bounds) < 2 or not (0 < bounds[0] < bounds[1]):
        raise ValueError(f"skew table needs iv_bounds [low, high] with 0 < low < high, got {bounds}")
    if _num("put_wing_slope", table.get("put_wing_slope", 6.0)) < 0:
        raise ValueError("skew table: put_wing_slope must be >= 0 (IV rises further out of the money)")
    for b in table["buckets"]:
        if not isinstance(b, dict):
            raise ValueError(f"skew table: each bucket must be a mapping, got {b!r}")
        name = b.get("name")
        m = _nums(f"bucket {name!r} moneyness", b.get("moneyness") or [])
        rl = _nums(f"bucket {name!r} ratio_low", b.get("ratio_low") or [])
        rh = _nums(f"bucket {name!r} ratio_high", b.get("ratio_high") or [])
        if not m or len(m) != len(rl) or len(m) != len(rh):
            raise ValueError(f"bucket {name!r}: moneyness, ratio_low and ratio_high need equal, non-zero length")
        if any(x <= 0 for x in m) or any(y <= x for x, y in zip(m, m[1:])):
            raise ValueError(f"bucket {name!r}: moneyness nodes must be positive and strictly increasing")
        if any(v <= 0 for v in rl + rh):
            raise ValueError(f"bucket {name!r}: ratios must be positive numbers")
        if _num(f"bucket {name!r} dte_min", b.get("dte_min", 0)) > _num(f"bucket {name!r} dte_max",
                                                                         b.get("dte_max", 10**6)):
            raise ValueError(f"bucket {name!r}: dte_min > dte_max")
        call = b.get("call") or {}
        if not isinstance(call, dict):
            raise ValueError(f"bucket {name!r}: call must be a mapping")
        _num(f"bucket {name!r} call.start", call.get("start", 1.0))
        atm = _num(f"bucket {name!r} call.atm", call.get("atm", 0.85))
        floor = _num(f"bucket {name!r} call.floor", call.get("floor", 0.70))
        slope = _num(f"bucket {name!r} call.slope", call.get("slope", 0.8))
        if not (atm > 0 and 0 < floor <= atm and slope >= 0):
            raise ValueError(f"bucket {name!r}: call needs atm > 0, 0 < floor <= atm and slope >= 0")


_DEFAULT: dict = {}


def default_skew_table() -> dict:
    """A copy of the committed table, read once per file change (the backtester prices thousands of options)."""
    mtime = SKEW_PATH.stat().st_mtime
    if _DEFAULT.get("mtime") != mtime:
        _DEFAULT.update(mtime=mtime, table=load_skew_table(SKEW_PATH))
    return copy.deepcopy(_DEFAULT["table"])


def _table(skew_table: dict | None) -> dict:
    if skew_table is None:
        return default_skew_table()
    validate_skew_table(skew_table)
    return skew_table


def pick_bucket(dte: float, table: dict) -> dict:
    """The DTE bucket holding `dte`; outside every bucket, the nearest one (OPT-37)."""
    buckets = table["buckets"]
    for b in buckets:
        if float(b.get("dte_min", 0)) <= dte <= float(b.get("dte_max", 10**6)):
            return b

    def gap(b):
        return max(float(b.get("dte_min", 0)) - dte, dte - float(b.get("dte_max", 10**6)), 0.0)

    return min(buckets, key=gap)


def vol_fraction(x) -> float:
    """A volatility index as a fraction: 18.5 (Cboe points) -> 0.185; 0.185 stays. Values above 3 are points."""
    v = _positive("volatility index", x)
    return v / 100.0 if v > 3.0 else v


def skew_ratio(moneyness: float, vix: float, bucket: dict, table: dict) -> float:
    """OPT-37 (RPL): IV / index ratio at `moneyness` = strike / spot for one DTE bucket and index level."""
    call = bucket.get("call") or {}
    start = float(call.get("start", 1.0))
    if moneyness >= start:
        return max(float(call.get("floor", 0.70)),
                   float(call.get("atm", 0.85)) - float(call.get("slope", 0.8)) * (moneyness - start))
    lo, hi = float(table.get("vix_low", 0.15)), float(table.get("vix_high", 0.25))
    w = min(1.0, max(0.0, (vix - lo) / (hi - lo)))
    nodes = np.asarray(bucket["moneyness"], float)
    tab = np.asarray(bucket["ratio_low"], float) * (1 - w) + np.asarray(bucket["ratio_high"], float) * w
    if moneyness < nodes[0]:
        return float(tab[0] + (nodes[0] - moneyness) * float(table.get("put_wing_slope", 6.0)))
    return float(np.interp(moneyness, nodes, tab))


def model_iv(spot, strike, dte, vix, skew_table: dict | None = None, *, mode: str = "skew") -> float:
    """OPT-37 (RPL): model implied vol = index x skew ratio(moneyness, DTE bucket, index level).

    `vix` is the volatility index for the underlying (VIX for SPY), as a fraction or in Cboe points.
    `skew_table=None` loads `config/options_skew.yaml`. `mode="flat"` returns the index itself: the biased
    flat-volatility run OPT-37 must print next to the base (pass realised vol as `vix` for the realised run).
    Raises ValueError for missing/invalid inputs rather than pricing garbage.
    """
    spot, strike = _positive("spot", spot), _positive("strike", strike)
    dte = _finite("dte", dte)
    if dte < 0:
        raise ValueError(f"dte must be >= 0, got {dte!r}")
    v = vol_fraction(vix)
    if mode == "flat":
        return v
    if mode != "skew":
        raise ValueError(f"mode must be 'skew' or 'flat', got {mode!r}")
    table = _table(skew_table)
    ratio = skew_ratio(strike / spot, v, pick_bucket(dte, table), table)
    lo_b, hi_b = (table.get("iv_bounds") or [0.01, 3.0])[:2]
    return float(min(float(hi_b), max(float(lo_b), v * ratio)))


def dividend_yield(underlying: str, skew_table: dict | None = None) -> float:
    """Continuous dividend yield used for `underlying` (0.0 when the table does not list it)."""
    return float((_table(skew_table).get("dividend_yield") or {}).get(str(underlying).upper(), 0.0))


def model_quote(spot, strike, dte, vix, kind="put", skew_table: dict | None = None, *,
                rate: float | None = None, div_yield: float | None = None, underlying: str = "SPY",
                mode: str = "skew") -> dict:
    """OPT-37 (RPL): one modelled option {iv, price, delta, vega} per share, from `model_iv` and Black-Scholes.

    The inputs default to the ones the table was calibrated with: `div_yield=None` uses the table's yield for
    `underlying` (SPY 1.3%). RPL priced with the 3-month T-bill rate of each date: pass it as `rate`
    (`rate_on(fetch_tbill_rates(), day)`). With `rate=None` the table's flat `default_rate` is used and the
    result says so in `rate_source` ("default_rate" rather than "caller"), so a log can tell the two apart.
    The returned dict also carries the `rate` and `div_yield` actually used.
    """
    table = _table(skew_table)
    if rate is None:
        r, r_src = float(table.get("default_rate", 0.04)), "default_rate"
    else:
        r, r_src = _finite("rate", rate), "caller"
    q = dividend_yield(underlying, table) if div_yield is None else _finite("div_yield", div_yield)
    iv = model_iv(spot, strike, dte, vix, table, mode=mode)
    t = years(dte)
    return {"iv": iv, "price": bs_price(spot, strike, t, iv, kind, r, q),
            "delta": bs_delta(spot, strike, t, iv, kind, r, q),
            "vega": bs_vega(spot, strike, t, iv, r, q),
            "rate": r, "rate_source": r_src, "div_yield": q}


# --- calibration (Alpaca option bars since Feb 2024) ---------------------------------------------------


def calibrate_skew(observations: Iterable[dict], base_table: dict | None = None, *,
                   min_obs_per_node: int = 5, max_node_distance: float = 0.015, rate: float | None = None,
                   source: str = "alpaca option bars / cboe index", dte: int | None = None,
                   underlying: str | None = None, rate_source: str | None = None) -> dict:
    """OPT-37 (RPL): fit a skew table from observed option closes. Pure: no network.

    Each observation: {date, expiry (ISO), spot (raw close), strike, price (option close), vix (fraction or points),
    optional kind ("put"), rate, div_yield}. IV comes from `implied_vol`; ratio = IV / index. Each observation goes
    to the nearest moneyness node of its DTE bucket (dropped if more than `max_node_distance` away). Per node the
    ratio is regressed on the index and read at vix_low and vix_high; with too little spread in the index the
    mean is used for both. Nodes or buckets with fewer than `min_obs_per_node` observations keep the base table's
    values and are listed under `calibrated.kept_default`. Returns a new table (the base is not modified, and the
    result shares no nested objects with it).

    Provenance: `calibrated` records the collection `dte` and `underlying` when given, and `rate`: how many
    observations carried their own rate (`rate_source` names it, e.g. "FRED DTB3") and how many fell back to the
    flat default. An observation's missing `div_yield` uses the table's yield for `underlying` (0 if not given).
    """
    base = copy.deepcopy(_table(base_table))
    r_default = float(base.get("default_rate", 0.04)) if rate is None else float(rate)
    q_default = dividend_yield(underlying, base) if underlying else 0.0
    rows = [_obs_row(o, r_default, q_default) for o in observations]
    rows = [r for r in rows if r is not None]
    out = {k: v for k, v in base.items() if k != "buckets"}
    out["buckets"], kept, used = [], [], []
    for b in base["buckets"]:
        nb, u, k = _fit_bucket(b, rows, base, min_obs_per_node, max_node_distance)
        if u and dte is not None:
            nb["calibrated_dte"] = int(dte)
        out["buckets"].append(nb)
        kept += k
        used += u
    dates = sorted({r["date"] for r in used})
    own = sum(1 for r in used if r["rate_from"] == "observation")
    rate_text = (f"{own} observations with their own rate ({rate_source or 'given per observation'}), "
                 f"{len(used) - own} at flat {r_default:g} ({'caller' if rate is not None else 'default_rate'})")
    out["source"] = source
    cal = {"first_entry": dates[0] if dates else None, "last_entry": dates[-1] if dates else None,
           "entry_dates": len(dates), "contracts": len(used)}
    if underlying:
        cal["underlying"] = str(underlying).upper()
    if dte is not None:
        cal["dte"] = int(dte)
    cal.update({"method": "linear fit of IV/index on index per moneyness node, read at vix_low and vix_high",
                "rate": rate_text, "kept_default": kept, "run_date": date.today().isoformat()})
    out["calibrated"] = cal
    validate_skew_table(out)
    return out


def _obs_row(o: dict, r_default: float, q_default: float = 0.0) -> dict | None:
    """One observation -> {date, dte, m, vix, ratio, rate_from}, or None when it is unusable (bad data, no IV).

    A missing or None rate/div_yield uses the default; a non-numeric one drops the observation.
    """
    try:
        d, exp = pd.Timestamp(o["date"]), pd.Timestamp(o["expiry"])
        dte = (exp.normalize() - d.normalize()).days
        spot, strike, vix = float(o["spot"]), float(o["strike"]), vol_fraction(o["vix"])
        own_rate = o.get("rate") is not None
        r = _finite("rate", o["rate"]) if own_rate else r_default
        q = _finite("div_yield", o["div_yield"]) if o.get("div_yield") is not None else q_default
    except (KeyError, TypeError, ValueError):
        return None
    iv = implied_vol(o.get("price"), spot, strike, years(dte), o.get("kind", "put"), r, q)
    if iv is None or dte <= 0:
        return None
    return {"date": d.date().isoformat(), "dte": dte, "m": strike / spot, "vix": vix, "ratio": iv / vix,
            "rate_from": "observation" if own_rate else "default"}


def _fit_bucket(bucket: dict, rows: list[dict], table: dict, min_obs: int, max_dist: float):
    """Refit one DTE bucket's nodes -> (new bucket, observations used, nodes kept from the base)."""
    lo, hi = float(table.get("vix_low", 0.15)), float(table.get("vix_high", 0.25))
    nodes = np.asarray(bucket["moneyness"], float)
    mine = [r for r in rows if pick_bucket(r["dte"], table) is bucket]
    groups: dict[int, list[dict]] = {i: [] for i in range(len(nodes))}
    for r in mine:
        i = int(np.argmin(np.abs(nodes - r["m"])))
        if abs(nodes[i] - r["m"]) <= max_dist:
            groups[i].append(r)
    new = dict(bucket)
    rl, rh = list(map(float, bucket["ratio_low"])), list(map(float, bucket["ratio_high"]))
    kept, used = [], []
    for i, g in groups.items():
        if len(g) < min_obs:
            kept.append(f"{bucket.get('name')}:{nodes[i]:g}")
            continue
        rl[i], rh[i] = _fit_node(g, lo, hi)
        used += g
    new["ratio_low"], new["ratio_high"] = [round(x, 3) for x in rl], [round(x, 3) for x in rh]
    return new, used, kept


def _fit_node(g: list[dict], lo: float, hi: float) -> tuple[float, float]:
    """Linear fit ratio ~ a + b x index, read at lo and hi; flat mean if the index barely moved. Ratios stay > 0."""
    x = np.array([r["vix"] for r in g])
    y = np.array([r["ratio"] for r in g])
    if np.ptp(x) < 0.02:
        a = float(np.mean(y))
        return a, a
    b, a = np.polyfit(x, y, 1)
    floor = 0.05
    return max(floor, float(a + b * lo)), max(floor, float(a + b * hi))


def monthly_expiries(start, end) -> list[pd.Timestamp]:
    """Standard monthly expiries (third Fridays) from `start` to `end` inclusive."""
    out = []
    for first in pd.date_range(pd.Timestamp(start).replace(day=1), pd.Timestamp(end), freq="MS"):
        fridays = pd.date_range(first, first + pd.offsets.MonthEnd(0), freq="W-FRI")
        if len(fridays) >= 3 and pd.Timestamp(start) <= fridays[2] <= pd.Timestamp(end):
            out.append(fridays[2])
    return out


def _series(s: pd.Series) -> pd.Series:
    s = pd.Series(s).dropna().astype(float)
    idx = pd.to_datetime(s.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    s.index = idx.normalize()
    return s.sort_index()


def collect_skew_observations(client, spot: pd.Series, vix: pd.Series, *, underlying: str = "SPY",
                              start="2024-02-01", end=None, dte: int = 35,
                              moneyness: Iterable[float] = (1.0, 0.97, 0.95, 0.92, 0.90, 0.85),
                              div_yield: float | None = None, rate: float | pd.Series | None = None,
                              max_stale_days: int = 5, problems: list | None = None) -> list[dict]:
    """OPT-37: observations for `calibrate_skew` from Alpaca daily option bars (read-only market data).

    For each monthly expiry since `start`, on the last session at least `dte` days before it, it asks
    `client.get_option_bars` (an alpaca-py OptionHistoricalDataClient or a fake) for puts near each moneyness
    ($5 strikes below 0.97, $1 strikes above) and keeps the day's close. `spot` must be RAW (unadjusted) closes.
    One failing expiry never stops the run; the reason is appended to `problems`.
    The index value must be from `ent` or at most `max_stale_days` calendar days before it (a stale or truncated
    Cboe cache is never carried forward); otherwise the expiry is skipped as a problem. `rate` is a fraction, or a
    daily rate Series such as `fetch_tbill_rates()` (RPL: the 3-month T-bill of each entry date); an entry with no
    rate within 7 days is skipped as a problem.
    """
    from alpaca.data.requests import OptionBarsRequest
    from alpaca.data.timeframe import TimeFrame

    problems = problems if problems is not None else []
    spot, vix = _series(spot), _series(vix)
    if spot.empty or vix.empty:
        problems.append("no spot or index history")
        return []
    q = dividend_yield(underlying) if div_yield is None else float(div_yield)
    end = pd.Timestamp(end) if end is not None else spot.index[-1] + pd.Timedelta(days=dte + 31)
    out: list[dict] = []
    for exp in monthly_expiries(pd.Timestamp(start) + pd.Timedelta(days=dte), end):
        days = spot.index[spot.index <= exp - pd.Timedelta(days=dte)]
        if len(days) == 0 or days[-1] < pd.Timestamp(start):
            continue
        ent = days[-1]
        vix_now = index_on(vix, ent, max_stale_days)
        if vix_now is None:
            problems.append(f"{exp.date()}: no index value on {ent.date()} or in the {max_stale_days} days before")
            continue
        r_now = None
        if isinstance(rate, pd.Series):
            r_now = index_on(rate, ent, 7)
            if r_now is None:
                problems.append(f"{exp.date()}: no rate on {ent.date()} or in the 7 days before")
                continue
        elif rate is not None:
            r_now = float(rate)
        syms = _strikes(underlying, exp, float(spot[ent]), moneyness)
        try:
            req = OptionBarsRequest(symbol_or_symbols=list(syms), timeframe=TimeFrame.Day,
                                    start=ent - pd.Timedelta(days=1), end=ent + pd.Timedelta(days=1))
            closes = _bar_closes(client.get_option_bars(req).df, ent)
        except Exception as e:  # one bad expiry never stops the calibration
            problems.append(f"{exp.date()}: {type(e).__name__}: {str(e)[:120]}")
            continue
        for sym, strike in syms.items():
            if sym in closes:
                obs = {"date": ent.date().isoformat(), "expiry": exp.date().isoformat(), "spot": float(spot[ent]),
                       "strike": strike, "price": closes[sym], "vix": float(vix_now), "kind": "put",
                       "div_yield": q, "symbol": sym}
                if r_now is not None:
                    obs["rate"] = r_now
                out.append(obs)
    return out


def _strikes(underlying: str, exp: pd.Timestamp, s: float, moneyness: Iterable[float]) -> dict[str, float]:
    syms = {}
    for m in moneyness:
        k = float(round(s * m / 5) * 5 if m < 0.97 else round(s * m))
        syms[occ_symbol(underlying, exp.date().isoformat(), "put", k)] = k
    return syms


def _bar_closes(df: pd.DataFrame, day: pd.Timestamp) -> dict[str, float]:
    """{symbol: close} on `day` from an alpaca-py bars DataFrame indexed by (symbol, timestamp)."""
    out: dict[str, float] = {}
    if df is None or len(df) == 0:
        return out
    for (sym, ts), row in df.iterrows():
        t = pd.Timestamp(ts)
        t = t.tz_convert("America/New_York").tz_localize(None) if t.tzinfo else t
        c = float(row.get("close", float("nan")))
        if t.normalize() == day.normalize() and math.isfinite(c) and c > 0:
            out[str(sym)] = c
    return out


def write_skew_table(table: dict, path: str | Path | None = None) -> Path:
    """Save a checked table as YAML (the default path is config/options_skew.yaml)."""
    validate_skew_table(table)
    p = Path(path or SKEW_PATH)
    p.write_text(provenance_header(table) + yaml.safe_dump(table, sort_keys=False))
    return p


def provenance_header(table: dict) -> str:
    """YAML comment block saying how the table was made (OPT-37 provenance), regenerated on every write."""
    cal = table.get("calibrated") or {}
    lines = [
        "Skew table for book O's model prices (OPT-37, RPL method). Read by trader/options/pricing.py.",
        "Code reads this; Claude never changes it. Re-run the calibration with:",
        "  python -m trader.options.pricing calibrate --write",
        "Model: IV = volatility index (fraction) x ratio(moneyness = strike/spot, DTE bucket, index level); see",
        "pricing.skew_ratio. Note: at moneyness >= call.start the ratio is call.atm whatever the index level (as in",
        "RPL), so at high VIX it steps up from the blended 1.00 node to call.atm at the money.",
        f"Provenance: source = {table.get('source')}",
        f"  underlying {cal.get('underlying', '?')}, entries {cal.get('first_entry')} .. {cal.get('last_entry')},"
        f" {cal.get('entry_dates')} entry dates, {cal.get('contracts')} contracts, {cal.get('dte', '?')} DTE",
        f"  rate: {cal.get('rate', '?')}",
        f"  nodes kept from the previous table: {', '.join(cal.get('kept_default') or []) or 'none'}",
        f"  run date {cal.get('run_date', '?')}",
    ]
    return "".join(f"# {x}\n" for x in lines)


# --- Cboe index history (VIX, VIX3M, ...) --------------------------------------------------------------


def fetch_url(url: str, timeout: float = 20.0) -> str:
    """Plain HTTPS GET of a public CSV (read-only; never used by tests)."""
    from urllib.request import Request, urlopen

    with urlopen(Request(url, headers={"User-Agent": "trader-options-pricing"}), timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_cboe_index(name: str, *, state_dir: str | Path | None = None,
                     fetch: Callable[[str], str] | None = None, now: datetime | None = None,
                     max_age_hours: float = 12.0, units: str = "fraction") -> pd.Series:
    """OPT-37 / OPT-20: daily close history of a Cboe index (VIX, VIX3M, VIX9D, VXN, RVX, SKEW, ...).

    Source: Cboe's public CSV. Cached as `state_dir/cache/cboe/<NAME>_History.csv`; a cache younger than
    `max_age_hours` is used without a download. If the download fails an older cache is used (`attrs["stale"]`);
    with no cache it raises CboeDataError saying where to put a manual download. `units="fraction"` gives
    volatility indexes as fractions (18.5 -> 0.185); "points" keeps Cboe's numbers. SKEW is never divided.
    """
    name = str(name or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,12}", name):
        raise ValueError(f"not a Cboe index name: {name!r}")
    if units not in ("fraction", "points"):
        raise ValueError(f"units must be 'fraction' or 'points', got {units!r}")
    cache = Path(state_dir or STATE_DIR) / "cache" / "cboe" / f"{name}_History.csv"
    url = CBOE_URL.format(name=name)
    text, stale, error = _cboe_text(cache, url, fetch or fetch_url, now, max_age_hours)
    s = parse_cboe_history(text, name)
    if units == "fraction" and name not in POINT_INDEXES:
        s = s / 100.0
    s.name = name
    s.attrs.update({"source": url, "cache": str(cache), "stale": stale, "error": error,
                    "units": "points" if name in POINT_INDEXES else units})
    return s


def _cboe_text(cache: Path, url: str, fetch, now: datetime | None, max_age_hours: float,
               parse: Callable[[str, str], pd.Series] | None = None):
    """(csv text, stale?, fetch error) using the cache when fresh, the network otherwise, the old cache last."""
    now_ts = (now or datetime.now()).timestamp()
    if cache.exists() and now_ts - cache.stat().st_mtime < max_age_hours * 3600:
        return cache.read_text(), False, None
    try:
        text = fetch(url)
        (parse or parse_cboe_history)(text, cache.stem.replace("_History", ""))  # never cache a broken download
    except Exception as e:  # offline, blocked or a bad file
        err = f"{type(e).__name__}: {str(e)[:160]}"
        if cache.exists():
            return cache.read_text(), True, err
        raise CboeDataError(f"History {url} is not reachable ({err}) and there is no cache at {cache}. "
                            f"Connect to the internet, or download that CSV by hand and save it there.") from e
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp")
    tmp.write_text(text)
    tmp.replace(cache)
    return text, False, None


def parse_cboe_history(text: str, name: str = "") -> pd.Series:
    """Cboe CSV -> close Series indexed by date (oldest first). Bad rows are dropped; no valid rows raises."""
    df = pd.read_csv(io.StringIO(text or ""), dtype=str) if (text or "").strip() else pd.DataFrame()
    if df.empty:
        raise ValueError(f"empty Cboe CSV {name}".strip())
    cols = {c.strip().upper(): c for c in df.columns}
    if "DATE" not in cols:
        raise ValueError(f"Cboe CSV {name} has no DATE column")
    col = cols.get("CLOSE") or cols.get(name.upper()) or df.columns[-1]
    dates = pd.to_datetime(df[cols["DATE"]].str.strip(), format="%m/%d/%Y", errors="coerce")
    iso = pd.to_datetime(df[cols["DATE"]].str.strip(), format="%Y-%m-%d", errors="coerce")
    dates = dates.fillna(iso)
    vals = pd.to_numeric(df[col], errors="coerce")
    s = pd.Series(vals.to_numpy(float), index=pd.DatetimeIndex(dates))
    s = s[s.index.notna() & np.isfinite(s.to_numpy()) & (s.to_numpy() > 0)]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if s.empty:
        raise ValueError(f"no valid rows in Cboe CSV {name}".strip())
    return s


def _ny_naive(day) -> pd.Timestamp:
    """A day or timestamp as naive New York time (tz-aware inputs are converted, naive ones kept)."""
    t = pd.Timestamp(day)
    return t.tz_convert("America/New_York").tz_localize(None) if t.tzinfo is not None else t


def index_point(series: pd.Series | None, day, max_stale_days: int = 5) -> tuple[float | None, str | None]:
    """(close, its date) on `day` or the last one before it within `max_stale_days` calendar days; else (None, None).

    Time zones never crash it: a tz-aware `day` or series index is compared as New York dates.
    """
    if series is None or len(series) == 0:
        return None, None
    s = _series(series)
    s = s[np.isfinite(s.to_numpy())]
    d = _ny_naive(day)
    s = s[s.index <= d]
    if s.empty or (d.normalize() - s.index[-1]).days > max_stale_days:
        return None, None
    return float(s.iloc[-1]), s.index[-1].date().isoformat()


def index_on(series: pd.Series | None, day, max_stale_days: int = 5) -> float | None:
    """The index close on `day`, or the last one before it within `max_stale_days` calendar days; else None."""
    return index_point(series, day, max_stale_days)[0]


FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={name}"


def parse_fred_series(text: str, name: str = "DTB3") -> pd.Series:
    """FRED fredgraph CSV (observation_date/DATE, value; '.' = missing) -> Series in the file's units, oldest first."""
    df = pd.read_csv(io.StringIO(text or ""), dtype=str) if (text or "").strip() else pd.DataFrame()
    if df.empty or len(df.columns) < 2:
        raise ValueError(f"empty FRED CSV {name}".strip())
    cols = {c.strip().upper(): c for c in df.columns}
    dcol = cols.get("OBSERVATION_DATE") or cols.get("DATE")
    if dcol is None:
        raise ValueError(f"FRED CSV {name} has no date column")
    vcol = cols.get(name.upper()) or [c for c in df.columns if c != dcol][-1]
    dates = pd.to_datetime(df[dcol].str.strip(), format="%Y-%m-%d", errors="coerce")
    vals = pd.to_numeric(df[vcol], errors="coerce")
    s = pd.Series(vals.to_numpy(float), index=pd.DatetimeIndex(dates))
    s = s[s.index.notna() & np.isfinite(s.to_numpy())]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if s.empty:
        raise ValueError(f"no valid rows in FRED CSV {name}".strip())
    return s


def fetch_tbill_rates(*, state_dir: str | Path | None = None, fetch: Callable[[str], str] | None = None,
                      now: datetime | None = None, max_age_hours: float = 24.0, name: str = "DTB3") -> pd.Series:
    """OPT-37 (RPL): daily 3-month T-bill rate (FRED DTB3) as a fraction (4.01 -> 0.0401), public CSV.

    Cached as `state_dir/cache/fred/DTB3.csv` with the same rules as `fetch_cboe_index` (fresh cache used, old
    cache when offline with `attrs["stale"]`, CboeDataError with no cache). Use `rate_on(series, day)`.
    """
    name = str(name or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{1,20}", name):
        raise ValueError(f"not a FRED series id: {name!r}")
    cache = Path(state_dir or STATE_DIR) / "cache" / "fred" / f"{name}.csv"
    url = FRED_URL.format(name=name)
    text, stale, error = _cboe_text(cache, url, fetch or fetch_url, now, max_age_hours,
                                    parse=lambda t, _n: parse_fred_series(t, name))
    s = parse_fred_series(text, name) / 100.0
    s.name = name
    s.attrs.update({"source": url, "cache": str(cache), "stale": stale, "units": "fraction", "error": error})
    return s


def rate_on(rates: pd.Series | None, day, max_stale_days: int = 7) -> float | None:
    """The T-bill rate (fraction) on `day` or the last one within `max_stale_days`; None when there is none."""
    return index_on(rates, day, max_stale_days)


def vix_term_ratio(vix, vix3m) -> float | None:
    """OPT-20 input: VIX / VIX3M (above 1 = inverted term structure). None when either value is missing."""
    try:
        a, b = float(vix), float(vix3m)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(a) and math.isfinite(b)) or a <= 0 or b <= 0:
        return None
    return a / b


def opt20_term_structure(day, vix: pd.Series | None, vix3m: pd.Series | None, max_stale_days: int = 5) -> dict:
    """OPT-20 (TEST FIRST, logged only): VIX, VIX3M and the variant (i) flag 'no entry when VIX/VIX3M > 1'.

    It never blocks anything itself. With missing data `ratio` is None and `blocks_entry` is None (unknown),
    so the shadow log can tell 'not inverted' from 'no data'.
    """
    (v, v_day), (v3, v3_day) = index_point(vix, day, max_stale_days), index_point(vix3m, day, max_stale_days)
    ratio = vix_term_ratio(v, v3)
    ratio = None if ratio is None else round(ratio, 4)

    def attr(s, key):
        return (getattr(s, "attrs", None) or {}).get(key)

    return {"date": _ny_naive(day).date().isoformat(), "vix": v, "vix3m": v3, "vix_date": v_day,
            "vix3m_date": v3_day, "ratio": ratio,
            # decided on the logged (rounded) ratio, so the record never shows ratio 1.0 next to True
            "blocks_entry": None if ratio is None else bool(ratio > 1.0),
            "stale": bool(attr(vix, "stale") or attr(vix3m, "stale")),
            "errors": [e for e in (attr(vix, "error"), attr(vix3m, "error")) if e],
            "source": "cboe", "source_url": [attr(vix, "source"), attr(vix3m, "source")]}


# --- script entry point -------------------------------------------------------------------------------


def _load_dotenv(path: Path | None = None) -> None:
    """Keys from trading/.env, the same way `python -m trader` loads them (existing environment wins)."""
    import os

    from ..config import ROOT

    path = Path(path or ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip())


def _options_key_pair() -> tuple[str, str]:
    """Alpaca key and secret for option bars, always taken as a pair (never a key from one pair with another's
    secret): ALPACA_OPTIONS_*, then ALPACA_DATA_*, then ALPACA_RULES_*."""
    import os

    for prefix in ("ALPACA_OPTIONS", "ALPACA_DATA", "ALPACA_RULES"):
        key, secret = os.environ.get(f"{prefix}_KEY"), os.environ.get(f"{prefix}_SECRET")
        if key and secret:
            return key, secret
    raise RuntimeError("Set ALPACA_OPTIONS_KEY and ALPACA_OPTIONS_SECRET (or the ALPACA_DATA_* / ALPACA_RULES_* "
                       "pair) in the environment or trading/.env.")


def main(argv: list[str] | None = None, *, option_client=None, spot: pd.Series | None = None,
         vix: pd.Series | None = None, rates: pd.Series | None = None, out=None, err=None) -> int:
    """`python -m trader.options.pricing calibrate [--start 2024-02-01] [--dte 35] [--write] [--path P]`:
    re-fit the skew table from Alpaca option bars (read-only), priced with the daily FRED DTB3 rate like RPL,
    and print it; `--write` saves it with a regenerated provenance header. `--write` is refused (exit 2) when
    the VIX or rate history came from a stale cache, or no observation was usable. Keyword arguments let
    tests pass fake clients and series instead of the network."""
    import argparse

    out, err = out or sys.stdout, err or sys.stderr
    ap = argparse.ArgumentParser(prog="python -m trader.options.pricing")
    ap.add_argument("command", choices=["calibrate"])
    ap.add_argument("--start", default="2024-02-01")
    ap.add_argument("--dte", type=int, default=35)
    ap.add_argument("--underlying", default="SPY")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--path", default=None, help="where --write saves (default config/options_skew.yaml)")
    args = ap.parse_args(argv)
    _load_dotenv()
    und = args.underlying.upper()
    if spot is None:
        from ..data import AlpacaData

        spot = AlpacaData.from_env().history([und], pd.Timestamp(args.start) - pd.Timedelta(days=10),
                                             adjustment="raw")[und]["close"]
    if vix is None:
        base = default_skew_table()
        vix = fetch_cboe_index((base.get("vol_index") or {}).get(und, "VIX"))
    if rates is None:
        rates = fetch_tbill_rates()
    if option_client is None:
        from alpaca.data.historical.option import OptionHistoricalDataClient

        option_client = OptionHistoricalDataClient(*_options_key_pair())
    problems: list[str] = []
    for label, series in (("index", vix), ("rate", rates)):
        if (getattr(series, "attrs", None) or {}).get("stale"):
            problems.append(f"{label} history is a stale cache ({series.attrs.get('error')}); "
                            f"last value {series.index[-1].date() if len(series) else 'none'}")
    obs = collect_skew_observations(option_client, spot, vix, underlying=und, start=args.start,
                                    end=pd.Timestamp.today(), dte=args.dte, rate=rates, problems=problems)
    table = calibrate_skew(obs, underlying=und, dte=args.dte, rate_source="FRED DTB3",
                          source=f"alpaca option bars ({und}, trade closes) / cboe "
                                 f"{getattr(vix, 'name', None) or 'VIX'} / FRED DTB3; RPL calibration")
    print(yaml.safe_dump(table, sort_keys=False), file=out)
    for p in problems:
        print("problem:", p, file=err)
    if args.write:
        stale = any((getattr(x, "attrs", None) or {}).get("stale") for x in (vix, rates))
        if stale or not obs:
            print("not written: " + ("stale input history" if stale else "no usable observations"), file=err)
            return 2
        print("written:", write_skew_table(table, args.path), file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
