"""Report-only measurement: rulebook section (f) (M-1 to M-11), the going-live gate (G-1, G-2, G-4, G-5) and
the RISK-14 stress line.

Pure functions: state lists and numbers in, JSON-safe dicts out (floats or None, never NaN). Nothing here
changes a target, an order or a limit. `demotion` feeds RISK-13-style sleeve cuts in `risk.breaker_status`,
which can only lower risk.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import shadow

SLEEVES_R = ("B", "C", "D")  # A is not measured in R (A-5)
TRADING_DAYS = 252
SQN_LABEL = "t-stat of mean R"
STRESS_SHOCKS = {"equity_like": 0.20, "DBC": 0.10, "crypto": 0.30}  # RISK-14
API_COST_CEILING = 0.005  # M-9: Malkiel's 0.50% a year
GTAA5 = ("SPY", "EFA", "IEF", "DBC", "VNQ")
PRICE_ONLY_NOTE = ("benchmarks chain the stored daily closes, so they are price returns (no dividends or coupons), "
                   "and Sharpe is over the cash ETF's price return, which is close to 0%")


# --- small helpers ----------------------------------------------------------------------------------


def _f(x, nd: int = 4) -> float | None:
    """A finite rounded float, else None (keeps reports JSON-safe)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if math.isfinite(v) else None


def _policy(policy) -> dict:
    return policy.policy if hasattr(policy, "policy") else policy


def _day(x) -> str:
    return x.date().isoformat() if hasattr(x, "date") else str(x)


def _finite(values) -> np.ndarray:
    items = [] if values is None else list(values)
    return np.asarray([v for v in items if _f(v, 12) is not None], dtype=float)


# --- M-2: per-sleeve statistics -------------------------------------------------------------------------


def max_losing_streak(rs) -> int:
    """Longest run of consecutive losing trades (R < 0), in the order given."""
    best = run = 0
    for r in rs:
        run = run + 1 if r < 0 else 0
        best = max(best, run)
    return best


def top_share(rs, frac: float = 0.05) -> float | None:
    """Share of the total R that came from the best `frac` of lots (at least one). None when total R ≤ 0."""
    a = np.sort(_finite(rs))[::-1]
    total = a.sum() if len(a) else 0.0
    if len(a) == 0 or total <= 0:
        return None
    k = max(1, math.ceil(frac * len(a)))
    return float(a[:k].sum() / total)


def sqn(rs) -> float | None:
    """M-2: √min(n, 100) · mean / sd, shown only from n ≥ 30 (it is the t-stat of the mean R)."""
    a = _finite(rs)
    if len(a) < 30:
        return None
    sd = a.std(ddof=1)
    return float(math.sqrt(min(len(a), 100)) * a.mean() / sd) if sd > 0 else None


def bootstrap_upper(rs, q: float = 0.90, n_boot: int = 2000, seed: int = 0) -> float | None:
    """M-11: one-sided `q` bootstrap upper bound of the mean R (resampling lots with replacement).

    Seeded, so the same trades always give the same answer.
    """
    a = _finite(rs)
    if len(a) == 0:
        return None
    if len(a) == 1:
        return float(a[0])
    rng = np.random.default_rng(seed)
    means = []
    chunk = max(1, 200_000 // len(a))  # bounded memory for long backtests
    left = n_boot
    while left > 0:
        k = min(chunk, left)
        means.append(a[rng.integers(0, len(a), size=(k, len(a)))].mean(axis=1))
        left -= k
    return float(np.quantile(np.concatenate(means), q))


def _one_sleeve(trades: list[dict], boot_q: float, n_boot: int, seed: int) -> dict:
    trades = sorted(trades, key=lambda t: str(t.get("date", "")))  # stable: same-day order kept
    with_r = [t for t in trades if _f(t.get("R"), 12) is not None]
    rs = [float(t["R"]) for t in with_r]
    a = np.asarray(rs, dtype=float)
    n = len(a)
    wins, losses = a[a > 0], a[a < 0]
    mae = _finite([t.get("mae_R") for t in with_r])
    mfe = _finite([t.get("mfe_R") for t in with_r])
    held = _finite([t.get("sessions_held") for t in trades])
    return {
        "n": n,
        "n_without_R": len(trades) - n,
        "win_rate": _f(len(wins) / n) if n else None,
        "avg_win_R": _f(wins.mean()) if len(wins) else None,
        "avg_loss_R": _f(losses.mean()) if len(losses) else None,
        "E": _f(a.mean()) if n else None,
        "sd": _f(a.std(ddof=1)) if n >= 2 else None,
        "SQN": _f(sqn(rs)),
        "SQN_label": SQN_LABEL,
        "max_losing_streak": max_losing_streak(rs),
        "best_R": _f(a.max()) if n else None,
        "worst_R": _f(a.min()) if n else None,
        "top5pct_share": _f(top_share(rs)),
        "mean_MAE_R": _f(mae.mean()) if len(mae) else None,
        "mean_MFE_R": _f(mfe.mean()) if len(mfe) else None,
        "median_hold": _f(float(np.median(held)), 1) if len(held) else None,
        "total_pnl": _f(sum(_f(t.get("pnl"), 6) or 0.0 for t in trades), 2),
        "boot_upper": _f(bootstrap_upper(rs, boot_q, n_boot, seed)),
        "boot_q": boot_q,
    }


def _boot_q_of(policy) -> float | None:
    if policy is None:
        return None
    return _f(_policy(policy).get("measurement", {}).get("demotion", {}).get("bootstrap_upper_q"), 6)


def sleeve_stats(closed_trades: list[dict], *, boot_q: float | None = None, n_boot: int = 2000, seed: int = 0,
                 sleeves: tuple = SLEEVES_R, since: str | None = None, policy=None) -> dict[str, dict]:
    """M-2: per-sleeve statistics from closed lots, net of costs. Sleeve A is excluded (A-5).

    Lots without an R (no initial risk) count in `n_without_R` only. SQN is None below 30 lots.
    `boot_upper` is the M-11 bootstrap bound at `boot_q`; by default the policy's `bootstrap_upper_q` when
    `policy` is given, else 0.90. `since` (ISO date) keeps only lots entered on or after it (M-10 counts lots
    after the phase 1 fixes).
    """
    q = boot_q if boot_q is not None else (_boot_q_of(policy) or 0.90)
    out = {}
    for s in sleeves:
        trades = [t for t in closed_trades or [] if t.get("sleeve") == s
                  and (not since or str(t.get("entry_date") or t.get("date") or "") >= since)]
        out[s] = _one_sleeve(trades, q, n_boot, seed)
    return out


# --- M-11: demotion and M-10: promotion -------------------------------------------------------------------


def demotion(stats_by_sleeve: dict, policy) -> dict[str, str]:
    """M-11: {sleeve: "half"} when n ≥ 30 and the bootstrap upper bound of mean R < 0 (min weight, half risk);
    {sleeve: "stop"} when n ≥ 50 and SQN ≤ −1.0 (new entries stop pending review). Sleeves not listed are fine.

    The bound counts only when it was computed at the policy's quantile or a higher one (a higher bound below
    0 means the policy's bound is below 0 too); compute stats with `sleeve_stats(..., policy=policy)`."""
    dem = _policy(policy)["measurement"]["demotion"]
    q_pol = float(dem.get("bootstrap_upper_q", 0.90))
    out = {}
    for s, st in (stats_by_sleeve or {}).items():
        if s not in SLEEVES_R or not st:
            continue
        n = int(st.get("n") or 0)
        q = _f(st.get("SQN"), 6)
        ub = _f(st.get("boot_upper"), 12)
        bq = _f(st.get("boot_q"), 6)
        if bq is not None and bq < q_pol - 1e-9:
            ub = None  # a bound at a lower quantile than the policy's proves nothing: recompute with the policy
        if n >= dem["sqn_min_n"] and q is not None and q <= dem["sqn_floor"]:
            out[s] = "stop"
        elif n >= dem["bootstrap_min_n"] and ub is not None and ub < 0:
            out[s] = "half"
    return out


def demotion_reasons(stats_by_sleeve: dict, policy) -> dict[str, str]:
    """Plain-English reason for each M-11 demotion, for the journal and the owner."""
    out = {}
    for s, level in demotion(stats_by_sleeve, policy).items():
        st = stats_by_sleeve[s]
        if level == "stop":
            out[s] = f"sleeve {s}: SQN {st['SQN']} over {st['n']} lots is at or below the floor; new entries stop"
        else:
            out[s] = (f"sleeve {s}: even the optimistic estimate of its average R ({st['boot_upper']}) is below 0 "
                      f"over {st['n']} lots; minimum weight at half risk")
    return out


def _halt_recent(state, sessions: int, halt_dd: float) -> bool:
    """True when the book is halted now or was halted in any of the last `sessions` runs.

    A row that stores `halted` is taken at its word (so an owner reset of the peak counts). Older rows without
    it fall back to the drawdown from the running peak of the history, which can only err towards "halted".
    """
    if getattr(state, "halted", False):
        return True
    hist = getattr(state, "equity_history", []) or []
    peak = 0.0
    flags = []
    for h in hist:
        eq = _f(h.get("equity"), 6) or 0.0
        peak = max(peak, eq)
        if "halted" in h:
            flags.append(bool(h.get("halted")))
        else:
            flags.append(peak > 0 and 1 - eq / peak >= halt_dd)
    return any(flags[-sessions:]) if sessions > 0 else False


def promotion_gate(stats: dict, state, policy, backtest_E=None) -> dict[str, dict]:
    """M-10 (report only; the owner edits `risk_pct_by_sleeve` by hand): all of ≥ 100 closed lots, E > 0,
    SQN ≥ 2.0, live E ≥ 0.5 × backtest E where a backtest exists, and no halt in the last 63 sessions. A sleeve
    latched off (RISK-13 / M-11, `state.sleeve_blocked`) does not pass while the latch holds.

    `stats` should come from `sleeve_stats(..., since=<date of the phase 1 fixes>)`.
    `backtest_E` is {sleeve: E}, one number for every sleeve, or None. A check that does not apply is None.
    """
    pol = _policy(policy)
    p = pol["measurement"]["promotion"]
    halted = _halt_recent(state, int(p["no_halt_sessions"]), float(pol["breakers"]["drawdown_halt"]))
    promoted = set(getattr(state, "promoted_sleeves", []) or [])
    blocked = dict(getattr(state, "sleeve_blocked", {}) or {})
    out = {}
    for s, st in (stats or {}).items():
        if s not in SLEEVES_R:
            continue
        n, e, q = int(st.get("n") or 0), _f(st.get("E"), 12), _f(st.get("SQN"), 12)
        bt = backtest_E.get(s) if isinstance(backtest_E, dict) else backtest_E
        bt = _f(bt, 12)
        checks = {
            "closed_lots": n >= p["min_closed_lots"],
            "positive_E": e is not None and e > 0,
            "sqn": q is not None and q >= p["min_sqn"],
            "vs_backtest": None if bt is None else (e is not None and e >= p["min_backtest_ratio"] * bt),
            "no_recent_halt": not halted,
            "not_blocked": s not in blocked,
        }
        out[s] = {
            "passed": all(v is not False for v in checks.values()),
            "checks": checks,
            "detail": {"n": n, "need_n": p["min_closed_lots"], "E": e, "SQN": q, "need_sqn": p["min_sqn"],
                       "backtest_E": bt, "blocked": blocked.get(s)},
            "already_promoted": s in promoted,
        }
    return out


# --- equity history frames -------------------------------------------------------------------------------


def history_frame(equity_history: list[dict]) -> pd.DataFrame:
    """Equity history as a frame indexed by date: `equity`, one `c_<SYM>` column per stored close and one
    `x_<KEY>` column per exposure. SPY falls back to the old `benchmark` field."""
    rows = []
    for h in equity_history or []:
        if not h.get("date"):
            continue
        closes = dict(h.get("closes") or {})
        if "SPY" not in closes and _f(h.get("benchmark"), 6):
            closes["SPY"] = h["benchmark"]
        row = {"date": pd.Timestamp(h["date"]), "equity": _f(h.get("equity"), 6)}
        row.update({f"c_{k}": _f(v, 6) for k, v in closes.items()})
        row.update({f"x_{k}": _f(v, 6) for k, v in (h.get("exposure") or {}).items()})
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["equity"])
    df = pd.DataFrame(rows).set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df.apply(pd.to_numeric, errors="coerce")


def _prices(frame: pd.DataFrame, symbols) -> pd.DataFrame | None:
    """Closes of `symbols` from the first row where all are present, gaps forward-filled; None if missing."""
    cols = [f"c_{s}" for s in symbols]
    if frame.empty or any(c not in frame for c in cols):
        return None
    p = frame[cols].where(frame[cols] > 0)
    ok = p.notna().all(axis=1)
    if not ok.any():
        return None
    p = p.loc[ok.idxmax():].ffill()
    p.columns = list(symbols)
    return p if len(p) >= 2 else None


def rebalanced_path(prices: pd.DataFrame, weights: dict[str, float], every: str, capital: float = 1.0) -> pd.Series:
    """Value of a fixed-weight mix bought on the first row and rebalanced at the last row of each month
    (`every="month"`) or year (`every="year"`)."""
    syms = list(weights)
    px = prices[syms].to_numpy(dtype=float)
    w = np.array([weights[s] for s in syms], dtype=float)
    idx = prices.index
    key = idx.year * 100 + idx.month if every == "month" else idx.year
    units = w * capital / px[0]
    values = np.empty(len(px))
    for i in range(len(px)):
        values[i] = float(units @ px[i])
        if i + 1 < len(px) and key[i + 1] != key[i]:
            units = w * values[i] / px[i]
    return pd.Series(values, index=idx)


def perf_stats(values: pd.Series, rf: pd.Series | None = None) -> dict | None:
    """Total return, annualised volatility, Sharpe (excess over the cash ETF when given) and max drawdown."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    v = v[v > 0]
    if len(v) < 2:
        return None
    rets = v.pct_change().dropna()
    ex = rets - rf.reindex(rets.index).fillna(0.0) if rf is not None else rets
    sd, sd_ex = rets.std(ddof=1), ex.std(ddof=1)
    return {
        "return": _f(v.iloc[-1] / v.iloc[0] - 1),
        "vol": _f(sd * math.sqrt(TRADING_DAYS)) if len(rets) >= 2 else None,
        "sharpe": _f(ex.mean() / sd_ex * math.sqrt(TRADING_DAYS), 3) if len(rets) >= 2 and sd_ex > 0 else None,
        "max_drawdown": _f(float((1 - v / v.cummax()).max())),
        "start": _day(v.index[0]),
        "end": _day(v.index[-1]),
        "days": int(len(v)),
    }


def _cash_returns(frame: pd.DataFrame) -> pd.Series | None:
    if "c_BIL" not in frame:
        return None
    return frame["c_BIL"].where(frame["c_BIL"] > 0).ffill().pct_change()


def benchmark_paths(frame: pd.DataFrame) -> dict[str, pd.Series | None]:
    """M-1 value paths on the book's starting capital: SPY buy-and-hold, 60/40 SPY/IEF rebalanced monthly,
    GTAA-5 20% each rebalanced yearly. A benchmark whose closes are missing is None."""
    out: dict[str, pd.Series | None] = {}
    for name, weights, every in (("spy", {"SPY": 1.0}, "month"),
                                 ("sixty_forty", {"SPY": 0.6, "IEF": 0.4}, "month"),
                                 ("gtaa5", {s: 0.2 for s in GTAA5}, "year")):
        px = _prices(frame, list(weights))
        if px is None:
            out[name] = None
            continue
        cap = frame["equity"].reindex(px.index).dropna()
        capital = float(cap.iloc[0]) if len(cap) and cap.iloc[0] > 0 else 1.0
        out[name] = rebalanced_path(px, weights, every, capital)
    return out


def benchmarks(equity_history: list[dict]) -> dict:
    """M-1: {book, spy, sixty_forty, gtaa5: {return, vol, sharpe, max_drawdown, start, end, days} | None}.

    `book` covers every row; `book_same_dates[name]` is the book over exactly that benchmark's dates (M-1
    "same capital and dates"), since a benchmark starts only where all its closes are stored.
    """
    names = ("spy", "sixty_forty", "gtaa5")
    frame = history_frame(equity_history)
    if frame.empty:
        return {"book": None, "spy": None, "sixty_forty": None, "gtaa5": None,
                "book_same_dates": {n: None for n in names}, "note": PRICE_ONLY_NOTE}
    rf = _cash_returns(frame)
    out = {"book": perf_stats(frame["equity"], rf)}
    same = {}
    for name, path in benchmark_paths(frame).items():
        out[name] = perf_stats(path, rf) if path is not None else None
        same[name] = perf_stats(frame["equity"].reindex(path.index), rf) if path is not None else None
    out["book_same_dates"] = same
    out["note"] = PRICE_ONLY_NOTE
    return out


def g2_inputs(frame: pd.DataFrame) -> dict | None:
    """G-2 on one window: the dates where both SPY and IEF closes are stored. Returns the book's, 60/40's and
    SPY's stats over exactly those dates, or None when 60/40 cannot be built."""
    px = _prices(frame, ["SPY", "IEF"])
    if px is None:
        return None
    rf = _cash_returns(frame)
    return {
        "book": perf_stats(frame["equity"].reindex(px.index), rf),
        "sixty_forty": perf_stats(rebalanced_path(px, {"SPY": 0.6, "IEF": 0.4}, "month"), rf),
        "spy": perf_stats(px["SPY"], rf),
        "start": px.index[0].date().isoformat(), "end": px.index[-1].date().isoformat(), "days": int(len(px)),
    }


# --- M-4: sleeve A ------------------------------------------------------------------------------------------


def _a_weights(frame: pd.DataFrame) -> tuple[pd.DataFrame | None, str]:
    """Share of sleeve A in each asset per row, from exposure keys A_<SYM> (A_cash is BIL)."""
    parts: dict[str, pd.Series] = {}
    for col in frame.columns:
        if col.startswith("x_A_") and len(col) > 4:
            sym = "BIL" if col[4:] == "cash" else col[4:]
            parts[sym] = parts.get(sym, 0.0) + frame[col].fillna(0.0)
    if "x_A" not in frame or not parts:
        return None, "no sleeve A exposure recorded"
    a = frame["x_A"]
    known = pd.DataFrame(parts).sum(axis=1)
    used = a > 0
    if not used.any():
        return None, "sleeve A held nothing"
    if ((known[used] - a[used]).abs() > 0.02 * a[used]).any():
        return None, "A return needs exposure A_<SYMBOL> for every A asset (only some are recorded)"
    missing = [s for s in parts if f"c_{s}" not in frame]
    if missing:
        return None, f"no closes stored for {', '.join(missing)}"
    return pd.DataFrame(parts).div(a.where(used), axis=0), ""


def sleeve_a_report(equity_history: list[dict], *, top_n: int = 20) -> dict:
    """M-4: sleeve A's time in BIL, the share of SPY's 20 best and 20 worst days each year that A spent out of
    SPY, and (when every A asset's exposure is stored) its return and max drawdown against GTAA-5 (benchmark 3).

    A day's position is the one held at the previous close (start-of-day holdings).
    """
    frame = history_frame(equity_history)
    out: dict = {"days": 0, "avg_cash_share": None, "days_mostly_cash": None, "best_days_in_cash": None,
                 "worst_days_in_cash": None, "by_year": {}, "return": None, "max_drawdown": None,
                 "gtaa5": None, "notes": []}
    if frame.empty or "x_A" not in frame:
        out["notes"].append("no sleeve A exposure recorded yet")
        return out
    a = frame["x_A"]
    held = a > 0
    out["days"] = int(held.sum())
    if "x_A_cash" in frame and held.any():
        share = (frame["x_A_cash"].fillna(0.0) / a.where(held)).dropna()
        out["avg_cash_share"] = _f(share.mean())
        out["days_mostly_cash"] = _f((share >= 0.5).mean())
    _best_worst_days(frame, top_n, out)
    start = _a_return(frame, out)
    if start is None and held.any():
        start = held.idxmax()  # A's own return is unknown: compare over the days A held something
    if start is not None:
        g = benchmark_paths(frame.loc[start:]).get("gtaa5")
        gs = perf_stats(g) if g is not None else None
        out["gtaa5"] = {"return": gs["return"], "max_drawdown": gs["max_drawdown"], "start": gs["start"],
                        "in_cash": 0.0} if gs else None
        if gs is None:
            out["notes"].append("GTAA-5 needs stored closes of SPY, EFA, IEF, DBC and VNQ")
    return out


def _best_worst_days(frame: pd.DataFrame, top_n: int, out: dict) -> None:
    if "c_SPY" not in frame or "x_A_SPY" not in frame:
        out["notes"].append("SPY closes or A's SPY exposure missing: best/worst days not measured")
        return
    spy = frame["c_SPY"].where(frame["c_SPY"] > 0)
    rets = spy.pct_change()
    expo = frame["x_A_SPY"]
    out_of_spy = (expo <= 0).where(expo.notna()).shift(1)  # start-of-day holdings; unknown rows dropped
    df = pd.DataFrame({"ret": rets, "cash": out_of_spy}).dropna()
    if df.empty:
        return
    best_hits = worst_hits = best_n = worst_n = 0
    for year, g in df.groupby(df.index.year):
        k = min(top_n, len(g) // 2)
        if k == 0:
            continue
        b = g.nlargest(k, "ret")["cash"].astype(bool)
        w = g.nsmallest(k, "ret")["cash"].astype(bool)
        out["by_year"][str(year)] = {"days": k, "best_in_cash": _f(b.mean()), "worst_in_cash": _f(w.mean())}
        best_hits, best_n = best_hits + int(b.sum()), best_n + k
        worst_hits, worst_n = worst_hits + int(w.sum()), worst_n + k
    if best_n:
        out["best_days_in_cash"] = _f(best_hits / best_n)
        out["worst_days_in_cash"] = _f(worst_hits / worst_n)


def _a_return(frame: pd.DataFrame, out: dict):
    """Sleeve A's return and max drawdown into `out`; returns the date its value path starts, or None."""
    weights, why = _a_weights(frame)
    if weights is None:
        out["notes"].append(why)
        return None
    rets = pd.DataFrame({s: frame[f"c_{s}"].where(frame[f"c_{s}"] > 0).ffill().pct_change() for s in weights})
    daily = (weights.shift(1) * rets).sum(axis=1, min_count=1).dropna()
    if daily.empty:
        return None
    base = frame.index[frame.index.get_loc(daily.index[0]) - 1]  # the close the first return starts from
    path = pd.concat([pd.Series([1.0], index=[base]), (1 + daily).cumprod()])
    st = perf_stats(path)
    if st:
        out["return"], out["max_drawdown"] = st["return"], st["max_drawdown"]
    return path.index[0]


# --- M-5, M-6, M-7: deviations, vetoes, predictions ---------------------------------------------------------


def _group(records: list[dict], key: str, value: str) -> dict:
    out: dict[str, dict] = {}
    for r in records:
        g = out.setdefault(str(r.get(key) or "UNKNOWN"), {"n": 0, "sum": 0.0, "hits": 0})
        g["n"] += 1
        g["sum"] += float(r[value])
        g["hits"] += int(float(r[value]) > 0)
    return {k: {"n": g["n"], "sum": _f(g["sum"], 6), "hit_rate": _f(g["hits"] / g["n"])} for k, g in out.items()}


def monthly_sleeve_returns(state) -> tuple[dict[str, dict[str, float]], str]:
    """Each sleeve's P&L per month as a share of the book's equity at the start of that month.

    Uses `sleeve_cum` ({sleeve: cumulative P&L}) stored in equity_history rows when present; otherwise the
    realized P&L of lots closed that month (basis says which).
    """
    hist = [h for h in getattr(state, "equity_history", []) or [] if h.get("date")]
    if not hist:
        return {}, "none"
    starts: dict[str, float] = {}
    prev_eq = None
    for h in hist:
        m = h["date"][:7]
        if m not in starts:
            starts[m] = float(prev_eq if prev_eq is not None else h["equity"])
        prev_eq = h["equity"]
    out: dict[str, dict[str, float]] = {}
    if any("sleeve_cum" in h for h in hist):
        prev: dict[str, float] = {}  # a sleeve's first stored value is its baseline
        for h in hist:
            m = h["date"][:7]
            for s, cum in (h.get("sleeve_cum") or {}).items():
                cum = _f(cum, 6)
                if cum is None:
                    continue
                if s in prev and starts[m]:
                    out.setdefault(m, {}).setdefault(s, 0.0)
                    out[m][s] += (cum - prev[s]) / starts[m]
                prev[s] = cum
        return {m: {s: _f(v, 6) for s, v in d.items()} for m, d in out.items()}, "sleeve_cum"
    for t in getattr(state, "closed_trades", []) or []:
        m = str(t.get("date", ""))[:7]
        if m in starts and starts[m]:
            out.setdefault(m, {}).setdefault(t.get("sleeve", "?"), 0.0)
            out[m][t.get("sleeve", "?")] += float(_f(t.get("pnl"), 6) or 0.0) / starts[m]
    return {m: {s: _f(v, 6) for s, v in d.items()} for m, d in out.items()}, "realized closed lots only"


def deviation_attribution(state, rules_state=None) -> dict:
    """M-5: n, hit rate and Σ value_20d (share of equity) of the Claude book's deviations, by sleeve and reason
    code, plus the monthly Claude-minus-rules return by sleeve when the rules book's state is given."""
    devs = list(getattr(state, "deviations", []) or [])
    done = [d for d in devs if _f(d.get("value_20d"), 12) is not None]
    vals = [float(d["value_20d"]) for d in done]
    out = {
        "n": len(devs), "n_resolved": len(done),
        "sum_value_20d": _f(sum(vals), 6) if vals else 0.0,
        "hit_rate": _f(sum(v > 0 for v in vals) / len(vals)) if vals else None,
        "mean_value_20d": _f(np.mean(vals), 6) if vals else None,
        "by_sleeve": _group(done, "sleeve", "value_20d"),
        "by_code": _group(done, "reason_code", "value_20d"),
        "monthly_vs_rules": None, "basis": None,
    }
    if rules_state is not None:
        claude_m, basis = monthly_sleeve_returns(state)
        rules_m, basis_r = monthly_sleeve_returns(rules_state)
        diff: dict[str, dict] = {}
        for m in sorted(set(claude_m) | set(rules_m)):
            sleeves = set(claude_m.get(m, {})) | set(rules_m.get(m, {}))
            diff[m] = {s: _f((claude_m.get(m, {}).get(s) or 0.0) - (rules_m.get(m, {}).get(s) or 0.0), 6)
                       for s in sorted(sleeves)}
        out["monthly_vs_rules"] = diff
        out["basis"] = basis if basis == basis_r else f"claude: {basis}; rules: {basis_r}"
        if basis != "sleeve_cum" or basis_r != "sleeve_cum":
            out["note"] = ("monthly Claude-minus-rules uses realized P&L of closed lots only (no daily sleeve P&L "
                           "stored): open positions are missing and a lot counts in the month it closed")
    return out


def override_report(state) -> dict:
    """M-6: vetoes (shadow lots) by reason code and sleeve: how many, how many scored, Σ veto_value."""
    lots = list(getattr(state, "shadow_lots", []) or [])
    summary = shadow.veto_summary(state)
    scored = [lt for lt in lots if lt.get("status") == "closed" and _f(lt.get("veto_value"), 12) is not None]
    by_code = _group(scored, "reason_code", "veto_value")
    for lot in lots:
        by_code.setdefault(lot.get("reason_code") or "UNKNOWN", {"n": 0, "sum": 0.0, "hit_rate": None})
    for code, g in by_code.items():
        g["n_vetoes"] = sum(1 for lt in lots if (lt.get("reason_code") or "UNKNOWN") == code)
    vals = [float(lt["veto_value"]) for lt in scored]
    return {
        "n_vetoes": len(lots), "n_scored": summary["n_scored"], "n_open": summary["n_open"],
        "n_pending_entry": sum(1 for lt in lots if lt.get("status") == "pending_entry"),
        "n_expired": summary["n_expired"],
        "sum_value": summary["sum_value"], "sum_value_usd": summary["sum_value_usd"],
        "hit_rate": _f(sum(v > 0 for v in vals) / len(vals)) if vals else None,
        "by_code": by_code, "by_sleeve": _group(scored, "sleeve", "veto_value"),
        "restricted": bool(getattr(state, "veto_codes_restricted", False)),
    }


def prediction_scores(predictions: list[dict], min_resolved: int = 50) -> dict:
    """M-7: Brier score, skill = 1 − Brier / Brier_ref and calibration in 10% bins, shown only once
    `min_resolved` predictions have resolved (before that the numbers are None)."""
    res = [p for p in predictions or [] if p.get("outcome") in (0, 1) and _f(p.get("brier"), 12) is not None]
    n = len(res)
    out = {"n": len(predictions or []), "n_resolved": n, "min_resolved": min_resolved,
           "shown": n >= min_resolved, "brier": None, "brier_ref": None, "skill": None, "n_with_ref": 0,
           "base_rate_full_window_share": None, "calibration": None}
    if not out["shown"] or not res:
        out["note"] = f"scores are shown after {min_resolved} resolved predictions ({n} so far)"
        return out
    out["brier"] = _f(np.mean([p["brier"] for p in res]))
    ref = [p for p in res if _f(p.get("brier_ref"), 12) is not None]
    out["n_with_ref"] = len(ref)
    counted = [p for p in ref if p.get("base_rate_n") is not None]
    if counted:
        full = sum(1 for p in counted if int(p["base_rate_n"]) >= shadow.BASE_RATE_LOOKBACK)
        out["base_rate_full_window_share"] = _f(full / len(counted))
        if full < len(counted):
            out["base_rate_note"] = (f"{len(counted) - full} of {len(counted)} base rates used fewer than "
                                     f"{shadow.BASE_RATE_LOOKBACK} sessions of history")
    if ref:
        b, r = np.mean([p["brier"] for p in ref]), np.mean([p["brier_ref"] for p in ref])
        out["brier_ref"] = _f(r)
        out["skill"] = _f(1 - b / r) if r > 0 else None
    bins: dict[str, dict] = {}
    for p in res:
        i = min(int(float(p["probability"]) * 10), 9)
        g = bins.setdefault(f"{i / 10:.1f}-{(i + 1) / 10:.1f}", {"n": 0, "p": 0.0, "o": 0})
        g["n"] += 1
        g["p"] += float(p["probability"])
        g["o"] += int(p["outcome"])
    out["calibration"] = {k: {"n": g["n"], "mean_prob": _f(g["p"] / g["n"]), "hit_rate": _f(g["o"] / g["n"])}
                          for k, g in sorted(bins.items())}
    return out


# --- M-8: capture ratios ------------------------------------------------------------------------------------


def _monthly_returns(series: pd.Series) -> pd.Series:
    s = series.dropna()
    s = s[s > 0]
    if len(s) < 2:
        return pd.Series(dtype=float)
    month_end = s.groupby(s.index.year * 100 + s.index.month).last()
    base = pd.concat([pd.Series([s.iloc[0]]), month_end.iloc[:-1]], ignore_index=True)
    return pd.Series(month_end.to_numpy() / base.to_numpy() - 1.0, index=month_end.index)


def capture_ratios(equity_history: list[dict]) -> dict:
    """M-8: monthly up- and down-capture against SPY (mean book return in SPY's up or down months ÷ SPY's),
    and the share of rolling 6- and 12-month windows with a positive book return."""
    frame = history_frame(equity_history)
    out = {"months": 0, "up_capture": None, "down_capture": None, "positive_6m": None, "positive_12m": None}
    if frame.empty or "c_SPY" not in frame:
        return out
    both = frame[["equity", "c_SPY"]].dropna()
    book, spy = _monthly_returns(both["equity"]), _monthly_returns(both["c_SPY"])
    if book.empty:
        return out
    out["months"] = int(len(book))
    up, down = spy > 0, spy < 0
    if up.any() and spy[up].mean() != 0:
        out["up_capture"] = _f(book[up].mean() / spy[up].mean(), 3)
    if down.any() and spy[down].mean() != 0:
        out["down_capture"] = _f(book[down].mean() / spy[down].mean(), 3)
    growth = 1 + book
    for n, key in ((6, "positive_6m"), (12, "positive_12m")):
        if len(book) >= n:
            windows = growth.rolling(n).apply(np.prod, raw=True).dropna() - 1
            out[key] = _f((windows > 0).mean())
    return out


# --- M-9: API cost -------------------------------------------------------------------------------------------


def api_cost_report(state, equity: float) -> dict:
    """M-9: total API cost, the cost as an annualised share of equity (Malkiel's ceiling is 0.50%) and the
    book's return net of that cost. Session mode (Option B) runs on the subscription and logs $0 per call."""
    rows = list(getattr(state, "api_cost", []) or [])
    hist = list(getattr(state, "equity_history", []) or [])
    total = sum(_f(r.get("usd"), 6) or 0.0 for r in rows)
    sessions = len(hist) or len({r.get("date") for r in rows})
    annual = total / sessions * TRADING_DAYS if sessions else None
    pct = annual / equity if annual is not None and equity and equity > 0 else None
    by_role: dict[str, float] = {}
    for r in rows:
        role = str(r.get("role") or "?")
        by_role[role] = by_role.get(role, 0.0) + (_f(r.get("usd"), 6) or 0.0)
    ret = ret_net = None
    if len(hist) >= 2 and hist[0].get("equity"):
        e0, e1 = float(hist[0]["equity"]), float(hist[-1]["equity"])
        ret, ret_net = _f(e1 / e0 - 1), _f((e1 - total) / e0 - 1)
    modes = sorted({str(r.get("mode") or "api") for r in rows})
    out = {
        "calls": len(rows), "total_usd": _f(total, 2), "by_role": {k: _f(v, 2) for k, v in by_role.items()},
        "input_tokens": int(sum(_f(r.get("input_tokens"), 0) or 0 for r in rows)),
        "output_tokens": int(sum(_f(r.get("output_tokens"), 0) or 0 for r in rows)),
        "annual_usd": _f(annual, 2), "annual_pct_equity": _f(pct, 6), "ceiling_pct": API_COST_CEILING,
        "above_ceiling": bool(pct is not None and pct > API_COST_CEILING),
        "return": ret, "return_net_of_api": ret_net, "modes": modes,
    }
    if "session" in modes:
        out["note"] = "session mode runs on the Claude subscription, so per-call cost is logged as $0"
    return out


# --- G-1, G-2, G-4, G-5: going-live gate (report only) ---------------------------------------------------------


def block_bootstrap_p(diffs, block: int = 10, n_boot: int = 2000, seed: int = 0) -> float | None:
    """G-4: one-sided p-value that the mean daily difference is > 0, by a circular block bootstrap of the
    centred differences (blocks keep the day-to-day dependence). Small p = the difference is unlikely luck."""
    d = _finite(diffs)
    n = len(d)
    if n < 2:
        return None
    obs = d.mean()
    centred = d - obs
    block = max(1, min(block, n))
    n_blocks = math.ceil(n / block)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(n_boot, n_blocks))
    idx = ((starts[:, :, None] + np.arange(block)) % n).reshape(n_boot, -1)[:, :n]
    means = centred[idx].mean(axis=1)
    return float((np.sum(means >= obs) + 1) / (n_boot + 1))


def _api_rows(state, since: str | None, role: str | None = None) -> list[dict]:
    """API cost rows dated on or after `since` (all rows when `since` is None), optionally of one role."""
    rows = []
    for r in getattr(state, "api_cost", []) or []:
        if since and str(r.get("date") or "") < since:
            continue
        if role is not None and r.get("role") != role:
            continue
        rows.append(r)
    return rows


def _usd(rows: list[dict]) -> float:
    return float(sum(_f(r.get("usd"), 6) or 0.0 for r in rows))


def _net_equity(state, since: str | None) -> pd.Series:
    """Daily equity net of cumulative API cost (G-2, G-4), from `since` on."""
    hist = [h for h in getattr(state, "equity_history", []) or []
            if h.get("date") and (not since or h["date"] >= since)]
    if not hist:
        return pd.Series(dtype=float)
    eq = pd.Series({pd.Timestamp(h["date"]): _f(h.get("equity"), 6) for h in hist}, dtype=float).sort_index()
    cost = pd.Series(0.0, index=eq.index)
    for r in _api_rows(state, since):
        usd = _f(r.get("usd"), 6) or 0.0
        if usd and r.get("date"):
            cost[cost.index >= pd.Timestamp(r["date"])] += usd
    return eq - cost


def _event_hit(e: dict, start: str) -> bool:
    return str(e.get("reason", "")).startswith("reconcile") and str(e.get("date", "")) >= start \
        and not e.get("explained")


def _reconcile_events(state, sessions: int = 60) -> list[dict]:
    """G-5: reconcile events (reason starting with "reconcile") in the last `sessions` runs, unless marked
    explained. Looks at open lots' events, the events kept inside closed trades (a lot rescaled by reconcile
    that later closed on its own rule) and closed trades whose own reason is a reconcile. The ledger writes
    an event only for differences over 1%."""
    hist = [h["date"] for h in getattr(state, "equity_history", []) or [] if h.get("date")]
    start = hist[-sessions] if len(hist) >= sessions else (hist[0] if hist else "")
    found = []
    for sleeve, held in (getattr(state, "lots", {}) or {}).items():
        for sym, lot in held.items():
            for e in getattr(lot, "events", None) or (lot.get("events", []) if isinstance(lot, dict) else []):
                if _event_hit(e, start):
                    found.append({"sleeve": sleeve, "symbol": sym, **e})
    for t in getattr(state, "closed_trades", []) or []:
        hits = [e for e in t.get("events") or [] if isinstance(e, dict) and _event_hit(e, start)]
        found += [{"sleeve": t.get("sleeve"), "symbol": t.get("symbol"), **e} for e in hits]
        if not hits and _event_hit({"reason": t.get("reason"), "date": t.get("date"),
                                    "explained": t.get("explained")}, start):
            found.append({"sleeve": t.get("sleeve"), "symbol": t.get("symbol"), "date": t.get("date"),
                          "reason": t.get("reason")})
    return found


def g7_slippage(state, pol: dict, since: str | None = None) -> dict:
    """G-7: per asset class, the median measured slippage (bps, positive = worse for us) of settled fills
    against the policy cost model. Measured once a class has `slippage_min_fills` fills (an order split
    over several sleeves counts once). ok is False when any measured class's median is more than twice
    the model (G-7: go back to paper); a class with too few fills is reported but does not fail."""
    turnover = pol["turnover"]
    model = {cls: float(b) for cls, b in turnover["cost_model_per_side_bps"].items()}
    min_fills = int(turnover.get("slippage_min_fills", 30))
    by_class: dict[str, list[float]] = {}
    seen: set = set()
    for i, row in enumerate(state.fills):
        if since and str(row.get("date") or "") < since:
            continue
        slip = _f(row.get("slippage_bps"), 12)
        if slip is None:
            continue
        key = (row.get("client_order_id"), row.get("date"), row.get("fill")) if row.get("client_order_id") else i
        if key in seen:
            continue
        seen.add(key)
        by_class.setdefault(row.get("asset_class"), []).append(slip)
    classes, breached = {}, []
    for cls, bps in model.items():
        slips = by_class.get(cls, [])
        med = float(np.median(slips)) if len(slips) >= min_fills else None
        if med is not None and med > 2 * bps:
            breached.append(cls)
        classes[cls] = {"fills": len(slips), "need": min_fills, "median_bps": _f(med, 2), "model_bps": bps,
                        "ok": None if med is None else med <= 2 * bps}
    return {"ok": not breached, "breached": breached, "classes": classes}


def _book_checks(state, pol: dict, since: str | None) -> dict:
    min_s = int(pol["measurement"]["going_live_min_sessions"])
    net = _net_equity(state, since)
    hist = [h for h in state.equity_history if h.get("date") and (not since or h["date"] >= since)]
    net_hist = [{**h, "equity": float(net.get(pd.Timestamp(h["date"]), float("nan")))} for h in hist]
    g = g2_inputs(history_frame(net_hist)) if net_hist else None
    book, sf, spy = (g["book"], g["sixty_forty"], g["spy"]) if g else (None, None, None)
    g2 = None
    if book and sf and spy and book["sharpe"] is not None and sf["sharpe"] is not None \
            and book["max_drawdown"] is not None and spy["max_drawdown"] is not None:
        g2 = bool(book["sharpe"] > sf["sharpe"] and book["max_drawdown"] <= 0.7 * spy["max_drawdown"])
    recon = _reconcile_events(state)
    return {
        "G-1_sessions": {"ok": len(hist) >= min_s, "sessions": len(hist), "need": min_s},
        "G-2_beats_60_40": {"ok": g2, "book_sharpe": book and book["sharpe"], "sixty_forty_sharpe": sf and sf["sharpe"],
                            "book_max_dd": book and book["max_drawdown"], "spy_max_dd": spy and spy["max_drawdown"],
                            "window": {k: g[k] for k in ("start", "end", "days")} if g else None},
        "G-5_reconcile": {"ok": not recon, "n_events": len(recon), "events": recon[:10]},
        "G-7_slippage": g7_slippage(state, pol, since),
        "api_cost_usd": _f(_usd(_api_rows(state, since)), 2),
    }


def _value_20d_usd(state, since: str | None = None) -> float:
    eq = {h["date"]: float(h["equity"]) for h in state.equity_history if h.get("date")}
    last = float(state.equity_history[-1]["equity"]) if state.equity_history else 0.0
    return sum(float(d["value_20d"]) * eq.get(d.get("date"), last)
               for d in state.deviations if _f(d.get("value_20d"), 12) is not None
               and (not since or str(d.get("date") or "") >= since))


def going_live_report(rules_state, claude_state, policy, *, since: str | None = None,
                      data_problems: list[str] | None = None, rehearsed: bool | None = None) -> dict:
    """G-1, G-2, G-4, G-5 and G-7's slippage test as a report; nothing here moves money. A check that cannot be known yet is None and
    counts as not passed. `since` = the date the phase 1 fixes went live: G-1, G-2 and every G-4 sum count
    from there. `data_problems` = today's unresolved data-check messages; `rehearsed` = owner confirms the
    kill-switch and halt-reset rehearsal (G-5)."""
    pol = _policy(policy)
    min_s = int(pol["measurement"]["going_live_min_sessions"])
    books = {"rules": _book_checks(rules_state, pol, since), "claude": _book_checks(claude_state, pol, since)}
    for b in books.values():
        b["G-5_data_clean"] = {"ok": None if data_problems is None else not data_problems,
                               "problems": list(data_problems or [])[:10]}
        b["G-5_rehearsed"] = {"ok": rehearsed}

    rules_net, claude_net = _net_equity(rules_state, since), _net_equity(claude_state, since)
    common = rules_net.index.intersection(claude_net.index)
    diffs = (claude_net[common].pct_change() - rules_net[common].pct_change()).dropna()
    p = block_bootstrap_p(diffs.to_numpy()) if len(diffs) >= min_s else None
    value_usd = _value_20d_usd(claude_state, since)
    claude_cost = books["claude"]["api_cost_usd"] or 0.0
    review_cost = _usd(_api_rows(rules_state, since, role="review"))
    veto_usd = shadow.veto_summary(rules_state, since=since)["sum_value_usd"]
    g4_claude = None if p is None else bool(p < 0.10 and value_usd > claude_cost)
    g4 = {"ok": g4_claude, "p_value": _f(p), "days": int(len(diffs)), "need_days": min_s,
          "value_20d_usd": _f(value_usd, 2), "claude_api_usd": _f(claude_cost, 2),
          "rules_review_keeps_claude": bool(veto_usd > review_cost), "veto_value_usd": _f(veto_usd, 2),
          "review_api_usd": _f(review_cost, 2)}

    def passed(checks: dict) -> bool:
        return all(v.get("ok") is True for k, v in checks.items() if k.startswith("G-"))

    rules_ok, claude_ok = passed(books["rules"]), passed(books["claude"]) and g4_claude is True
    return {
        "books": books, "G-4_claude_vs_rules": g4,
        "rules_passed": rules_ok, "claude_passed": claude_ok,
        "live_candidate": "claude" if claude_ok else ("rules" if rules_ok else None),
        "since": since, "note": "report only: going live always needs the owner's explicit decision "
                                "(G-3, G-6 and G-7's capital limits are policy). " + PRICE_ONLY_NOTE,
    }


# --- RISK-14: stress line (display only) ----------------------------------------------------------------------


def _iter_lots(lots):
    """Yield (symbol, qty, entry_price) from {sleeve: {symbol: Lot}} or {symbol: Lot}, Lot objects or dicts."""
    for k, v in (lots or {}).items():
        if isinstance(v, dict) and "qty" not in v:  # a sleeve: {symbol: lot}
            for sym, lot in v.items():
                yield from _one_lot(sym, lot)
        else:
            yield from _one_lot(k, v)


def _one_lot(sym, lot):
    qty = lot.get("qty") if isinstance(lot, dict) else getattr(lot, "qty", None)
    entry = lot.get("entry_price") if isinstance(lot, dict) else getattr(lot, "entry_price", None)
    if _f(qty, 12):
        yield sym, float(qty), _f(entry, 12)


def stress_line(lots, prices: dict, equity: float, cfg) -> dict:
    """RISK-14 (display only): loss if equity-like holdings fell 20%, DBC 10% and crypto 30% at once,
    in dollars and as a share of equity. Shown next to heat; never used to size or block anything."""
    parts = {"equity_like": 0.0, "DBC": 0.0, "crypto": 0.0}
    for sym, qty, entry in _iter_lots(lots):
        price = _f((prices or {}).get(sym), 12) or entry or 0.0
        notional = qty * price
        if cfg.asset_class(sym) == "crypto":
            parts["crypto"] += notional
        elif sym == "DBC":
            parts["DBC"] += notional
        elif cfg.is_equity_like(sym):
            parts["equity_like"] += notional
    loss = sum(parts[k] * STRESS_SHOCKS[k] for k in parts)
    pct = loss / equity if equity and equity > 0 else None
    text = (f"If stocks fell 20%, commodities 10% and crypto 30% together, the book would lose about "
            f"${loss:,.0f}" + (f" ({pct:.1%} of equity)." if pct is not None else "."))
    return {"notional": {k: _f(v, 2) for k, v in parts.items()}, "shocks": dict(STRESS_SHOCKS),
            "loss_usd": _f(loss, 2), "loss_pct": _f(pct), "text": text}


# --- M-2 brief: losing streaks ----------------------------------------------------------------------------------


def _p_no_run(n: int, k: int, q: float) -> float:
    """Probability that `n` independent trades with loss chance `q` contain no run of `k` losses."""
    state = np.zeros(k)
    state[0] = 1.0
    for _ in range(n):
        new = np.zeros(k)
        new[0] = state.sum() * (1 - q)
        new[1:] = state[:-1] * q
        state = new
    return float(state.sum())


def streak_quantiles(win_rate: float, n_trades: int = 100, qs=(0.25, 0.5, 0.75, 0.95)) -> dict[float, int]:
    """Exact quantiles of the longest losing streak in `n_trades` independent trades."""
    q = 1 - win_rate
    out, k = {}, 0
    for target in sorted(qs):
        while _p_no_run(n_trades, k + 1, q) < target:
            k += 1
        out[target] = k
    return out


def losing_streak_table(win_rates=(0.35, 0.40, 0.45), n_trades: int = 100) -> str:
    """M-2 brief for the prompt: how long losing streaks get by pure chance, computed exactly."""
    lines = [f"Longest losing streak in {n_trades} independent trades (exact odds):",
             "win rate | typical (middle half) | worst 5% of cases"]
    for w in win_rates:
        s = streak_quantiles(w, n_trades)
        lines.append(f"{w:.0%}      | {s[0.25]}-{s[0.75]}                   | {s[0.95]} or more")
    lines.append("A streak this long is normal for a working rule; it is not evidence the rule broke.")
    return "\n".join(lines)
