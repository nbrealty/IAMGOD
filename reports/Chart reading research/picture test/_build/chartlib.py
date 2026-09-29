"""Shared code for the blind chart-reading test: data access, truth rules, synthetic sessions, chart drawing.

Read-only on the repo: the lab modules are imported from /home/user/IAMGOD/trading (no bytecode is written there)
and only the cached bars / frozen daily bars are read. Everything is written next to this file's parent folder.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True                     # never write __pycache__ into the repo
sys.path.insert(0, "/home/user/IAMGOD/trading")

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt                                    # noqa: E402
from matplotlib.colors import to_rgb                               # noqa: E402
from matplotlib.patches import Rectangle                           # noqa: E402
from matplotlib.text import Text                                   # noqa: E402
from matplotlib.ticker import FixedLocator, FuncFormatter, MaxNLocator   # noqa: E402

TRADING = Path("/home/user/IAMGOD/trading")
SYMS = ("SPY", "QQQ")
CUTOFF = date(2026, 7, 1)
NBARS = 390
CTX = 110                    # daily sessions before the session (60 shown + 50 for the 50-day average)
SHOW = 60
A_BLOCKS = ["09:30-09:39", "09:40-09:49", "09:50-09:59", "10:00-10:09", "10:10-10:19", "10:20-10:29"]

# ------------------------------------------------------------------------------------------------ style
GREEN, RED = "#2e9e44", "#d62728"
BLUE, ORANGE, PURPLE = "#1f5fbf", "#f28e2b", "#8b3fbf"
VOL_ALPHA = 0.70
W_PX, H_PX = 1000, 700


# ------------------------------------------------------------------------------------------------ data
def load_minute():
    """{symbol: {'bars': minute frame, 'days': [Day...]}} via the lab loaders (cache dir = state/scalp_cache)."""
    from lab.scalp import data as dt
    from lab.scalp.backtest import to_days
    cal = dt.load_calendar()
    out = {}
    for sym in SYMS:
        bars = dt.load_bars(sym, date(2024, 1, 1), date(2026, 12, 31))
        closes = dt.load_official_closes(sym, date(2024, 1, 1), date(2026, 12, 31))
        out[sym] = {"bars": bars, "days": to_days(bars, cal, closes)}
    return out


def is_full_day(day) -> bool:
    from lab.scalp.backtest import tradable
    return bool(tradable(day) and day.n == NBARS and np.array_equal(day.m, np.arange(NBARS)))


def daily_from_minutes(bars: pd.DataFrame) -> pd.DataFrame:
    """Daily bars from the minute bars: first open, max high, min low, last close, sum volume."""
    g = bars.groupby(bars.index.date)
    d = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                      "close": g["close"].last(), "volume": g["volume"].sum()})
    d.index.name = "date"
    return d


def load_evals_daily(sym: str) -> pd.DataFrame:
    """The repo's frozen official daily bars (trading/evals/bars.csv.gz), one symbol, indexed by date."""
    df = pd.read_csv(TRADING / "evals" / "bars.csv.gz")
    df = df[df["symbol"] == sym].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.sort_values("date").set_index("date")[["open", "high", "low", "close", "volume"]]


# ------------------------------------------------------------------------------------------------ sessions
@dataclass
class Session:
    sid: str
    kind: str                      # 'real' | 'synthetic'
    symbol: str                    # synthetic: the symbol of the matched real session
    date: date                     # synthetic: the date of the matched real session
    o: np.ndarray                  # 390 one-minute bars
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    d_o: np.ndarray                # CTX daily bars before the session, oldest first
    d_h: np.ndarray
    d_l: np.ndarray
    d_c: np.ndarray
    d_v: np.ndarray
    matched: str | None = None     # synthetic: sid of the real session it is matched to
    post_cutoff: bool = True
    daily_source: str = ""
    info: dict | None = None


# ------------------------------------------------------------------------------------------------ helpers
def hhmm(minute_from_open: int) -> str:
    h, m = divmod(9 * 60 + 30 + int(minute_from_open), 60)
    return f"{h:02d}:{m:02d}"


def vwap_series(h, l, c, v):
    tp = (np.asarray(h, float) + np.asarray(l, float) + np.asarray(c, float)) / 3.0
    return np.cumsum(tp * v) / np.cumsum(v)


def agg5(o, h, l, c, v, nb=30):
    m = nb * 5
    return (np.asarray(o[0:m:5], float), np.asarray(h[:m], float).reshape(nb, 5).max(axis=1),
            np.asarray(l[:m], float).reshape(nb, 5).min(axis=1), np.asarray(c[4:m:5], float),
            np.asarray(v[:m], float).reshape(nb, 5).sum(axis=1))


def ema20(x):
    return pd.Series(np.asarray(x, float)).ewm(span=20, adjust=False).mean().to_numpy()


def sma(x, n):
    return pd.Series(np.asarray(x, float)).rolling(n).mean().to_numpy()


# ------------------------------------------------------------------------------------------------ truth rules
def truth_A(o, h, l, c, v):
    """Chart A: 1-minute candles 09:30-10:29 (first 60 bars). Returns (answers, metrics, flags)."""
    o, h, l, c, v = (np.asarray(x[:60], float) for x in (o, h, l, c, v))
    vw = vwap_series(h, l, c, v)
    ans, met, flags = {}, {}, []
    chg = (c[-1] / o[0] - 1.0) * 100.0
    ans["A1"] = "up" if chg >= 0.10 else "down" if chg <= -0.10 else "flat"
    met["A1"] = {"chg_pct": chg}
    ans["A2"] = "above" if c[-1] > vw[-1] else "below"
    met["A2"] = {"close_vs_vwap_pct": (c[-1] / vw[-1] - 1.0) * 100.0}
    if c[-1] == vw[-1]:
        flags.append("A2_tie")
    side, crosses = 0, 0
    for ci, vi in zip(c, vw):
        s = 1 if ci > vi else -1 if ci < vi else 0
        if s == 0:
            continue
        if side != 0 and s != side:
            crosses += 1
        side = s
    ans["A3"] = "0-1" if crosses <= 1 else "2-4" if crosses <= 4 else "5+"
    met["A3"] = {"crosses": crosses}
    hi = h.max()
    idx = np.flatnonzero(h == hi)
    ans["A4"] = "first" if idx[0] < 30 else "second"
    met["A4"] = {"highest_high_bar": int(idx[0]), "bars_at_that_high": int(len(idx)),
                 "first_half_high_minus_second_half_high_pct": (h[:30].max() - h[30:].max()) / o[0] * 100.0}
    if len({int(i) // 30 for i in idx}) > 1:
        flags.append("A4_tie_across_halves")
    rng_pct = (h.max() - l.min()) / o[0] * 100.0
    ans["A5"] = "<0.25%" if rng_pct < 0.25 else ">0.50%" if rng_pct > 0.50 else "0.25-0.50%"
    met["A5"] = {"range_pct": rng_pct}
    ref, mx = h[:15].max(), c[15:].max()
    ans["A6"] = "yes" if mx > ref else "no"
    met["A6"] = {"first15_high": ref, "max_close_after_0945": mx, "margin_pct": (mx / ref - 1.0) * 100.0}
    if mx == ref:
        flags.append("A6_touch")
    vm = v.max()
    idx = np.flatnonzero(v == vm)
    ans["A7"] = A_BLOCKS[int(idx[0]) // 10]
    other = np.delete(v, np.arange((int(idx[0]) // 10) * 10, (int(idx[0]) // 10) * 10 + 10))
    met["A7"] = {"peak_bar": int(idx[0]), "bars_at_peak": int(len(idx)),
                 "peak_over_best_bar_in_other_blocks": float(vm / other.max())}
    if len({int(i) // 10 for i in idx}) > 1:
        flags.append("A7_tie_across_blocks")
    ans["A8"] = None
    return ans, met, flags


def truth_B(o, h, l, c, v):
    """Chart B: 5-minute candles 09:30-11:59 (first 150 one-minute bars); B7 uses bars up to 12:29."""
    o1, h1, l1, c1, v1 = (np.asarray(x[:150], float) for x in (o, h, l, c, v))
    O, H, L, C, V = agg5(o1, h1, l1, c1, v1)
    vw = vwap_series(h1, l1, c1, v1)[4::5]
    em = ema20(C)
    ans, met, flags = {}, {}, []
    chg = (C[-1] / O[0] - 1.0) * 100.0
    ans["B1"] = "up" if chg >= 0.15 else "down" if chg <= -0.15 else "flat"
    met["B1"] = {"chg_pct": chg}
    ratio = abs(C[-1] - O[0]) / (H.max() - L.min())
    ans["B2"] = "trend" if ratio >= 0.6 else "range"
    met["B2"] = {"net_over_range": ratio}
    ans["B3"] = "up" if em[-1] > em[-6] else "down"
    met["B3"] = {"ema_last_minus_5_earlier_pct": (em[-1] / em[-6] - 1.0) * 100.0}
    if em[-1] == em[-6]:
        flags.append("B3_tie")
    ans["B4"] = "above" if C[-1] > vw[-1] else "below"
    met["B4"] = {"close_vs_vwap_pct": (C[-1] / vw[-1] - 1.0) * 100.0}
    r1 = H[:12].max() - L[:12].min()
    r2 = H[18:].max() - L[18:].min()
    ans["B5"] = "yes" if r2 < r1 else "no"
    met["B5"] = {"range_0930_1029_pct": r1 / O[0] * 100.0, "range_1100_1159_pct": r2 / O[0] * 100.0}
    ans["B6"] = None
    p0, p1 = float(np.asarray(c, float)[149]), float(np.asarray(c, float)[179])
    ans["B7"] = "up" if p1 > p0 else "down"
    met["B7"] = {"close_1159": p0, "close_1229": p1, "move_pct": (p1 / p0 - 1.0) * 100.0}
    if p1 == p0:
        flags.append("B7_tie")
    return ans, met, flags


def truth_C(d_o, d_h, d_l, d_c):
    """Chart C: last 60 of the CTX daily bars are drawn, the 20/50-day averages use all CTX bars."""
    d_o, d_h, d_l, d_c = (np.asarray(x, float) for x in (d_o, d_h, d_l, d_c))
    s20, s50 = sma(d_c, 20), sma(d_c, 50)
    ans, met, flags = {}, {}, []
    ans["C1"] = "yes" if d_c[-1] > s50[-1] else "no"
    met["C1"] = {"close_vs_sma50_pct": (d_c[-1] / s50[-1] - 1.0) * 100.0}
    ans["C2"] = "yes" if s20[-1] > s50[-1] else "no"
    met["C2"] = {"sma20_vs_sma50_pct": (s20[-1] / s50[-1] - 1.0) * 100.0}
    f0 = CTX - SHOW                                        # index of the first shown candle
    chg = (d_c[-1] / d_o[f0] - 1.0) * 100.0
    ans["C3"] = "up" if chg > 3.0 else "down" if chg < -3.0 else "flat"
    met["C3"] = {"net60_pct": chg}
    gaps = d_o[f0 + 1:] / d_c[f0:-1] - 1.0                # 59 gaps between two visible candles
    a = np.abs(gaps)
    k = int(np.argmax(a))
    pos = k + 1                                            # zero-based position of the candle that opens with the gap
    third = ["first third", "middle third", "last third"][pos // 20]
    ans["C4"] = {"direction": "up" if gaps[k] > 0 else "down", "third": third}
    srt = np.sort(a)[::-1]
    met["C4"] = {"gap_pct": gaps[k] * 100.0, "candle_number": pos + 1,
                 "second_largest_abs_pct": srt[1] * 100.0, "ratio_largest_to_second": float(srt[0] / srt[1])}
    if np.sum(a == a.max()) > 1:
        flags.append("C4_tie")
    ans["C5"] = None
    return ans, met, flags


def all_truth(s: Session):
    a = truth_A(s.o, s.h, s.l, s.c, s.v)
    b = truth_B(s.o, s.h, s.l, s.c, s.v)
    c = truth_C(s.d_o, s.d_h, s.d_l, s.d_c)
    return {"A": a, "B": b, "C": c}


# ------------------------------------------------------------------------------------------------ soft flags
def soft_flags(ch, met):
    """Borderline items a careful human reader could not settle by eye. Informational only (nothing is dropped).
    Tolerances are judgment calls, listed in build_report.md."""
    f = []
    if ch == "A":
        if abs(abs(met["A1"]["chg_pct"]) - 0.10) < 0.02:
            f.append("A1_within_0.02pp_of_threshold")
        if abs(met["A2"]["close_vs_vwap_pct"]) < 0.01:
            f.append("A2_close_within_0.01pct_of_vwap")
        if met["A3"]["crosses"] in (1, 2, 4, 5):
            f.append("A3_count_next_to_a_class_boundary")
        if abs(met["A4"]["first_half_high_minus_second_half_high_pct"]) < 0.01:
            f.append("A4_two_halves_within_0.01pct")
        r = met["A5"]["range_pct"]
        if min(abs(r - 0.25), abs(r - 0.50)) < 0.03:
            f.append("A5_within_0.03pp_of_threshold")
        if abs(met["A6"]["margin_pct"]) < 0.01:
            f.append("A6_close_within_0.01pct_of_level")
        if met["A7"]["peak_over_best_bar_in_other_blocks"] < 1.05:
            f.append("A7_runner_up_block_within_5pct")
    elif ch == "B":
        if abs(abs(met["B1"]["chg_pct"]) - 0.15) < 0.03:
            f.append("B1_within_0.03pp_of_threshold")
        if abs(met["B2"]["net_over_range"] - 0.6) < 0.05:
            f.append("B2_within_0.05_of_threshold")
        if abs(met["B3"]["ema_last_minus_5_earlier_pct"]) < 0.005:
            f.append("B3_ema_change_below_0.005pct")
        if abs(met["B4"]["close_vs_vwap_pct"]) < 0.01:
            f.append("B4_close_within_0.01pct_of_vwap")
        a, b = met["B5"]["range_0930_1029_pct"], met["B5"]["range_1100_1159_pct"]
        if abs(b / a - 1.0) < 0.05:
            f.append("B5_ranges_within_5pct")
    else:
        if abs(met["C1"]["close_vs_sma50_pct"]) < 0.2:
            f.append("C1_close_within_0.2pct_of_sma50")
        if abs(met["C2"]["sma20_vs_sma50_pct"]) < 0.2:
            f.append("C2_averages_within_0.2pct")
        if abs(abs(met["C3"]["net60_pct"]) - 3.0) < 0.5:
            f.append("C3_within_0.5pp_of_threshold")
        if met["C4"]["ratio_largest_to_second"] < 1.15:
            f.append("C4_runner_up_gap_within_15pct")
        if met["C4"]["candle_number"] in (21, 41):
            f.append("C4_gap_straddles_a_thirds_line")
    return f


# ------------------------------------------------------------------------------------------------ synthetic
def _units(o, h, l, c, pc):
    """Bars as log-ratios to the previous close: columns open, high, low, close."""
    return np.log(np.column_stack([o, h, l, c]) / np.asarray(pc, float)[:, None])


def _mirror(u):
    """Flip a bar up<->down around its previous close (high and low swap)."""
    return -u[:, [0, 2, 1, 3]]


def _chain(u, p0):
    out = np.empty((len(u), 4))
    pc = p0
    for i in range(len(u)):
        out[i] = pc * np.exp(u[i])
        pc = out[i, 3]
    return out[:, 0], out[:, 1], out[:, 2], out[:, 3]


def synth_intraday(o, h, l, c, v, rng, block=10):
    """Random-walk day matched to a real one. Each real bar (its shape relative to the previous close, plus its
    volume) is a unit. Units are shuffled inside each 10-minute block (the 09:30 and the last bar stay put, so
    the opening spike and the closing minute keep their slots) and each unit is flipped up/down by a coin toss.
    Sizes of the moves, the volume profile and the number of bars are the real day's; direction is random.
    Prices are rounded to whole cents at the end (real bars sit on the cent grid)."""
    o, h, l, c, v = (np.asarray(x, float) for x in (o, h, l, c, v))
    n = len(o)
    pc = np.concatenate(([o[0]], c[:-1]))
    u = _units(o, h, l, c, pc)
    src = np.arange(n)
    for b0 in range(0, n, block):
        seg = np.arange(b0, min(b0 + block, n))
        mov = seg[(seg != 0) & (seg != n - 1)]
        src[mov] = rng.permutation(mov)
    flip = rng.random(n) < 0.5
    u2 = u[src]
    u2 = np.where(flip[:, None], _mirror(u2), u2)
    so, sh, sl, sc = (np.round(x, 2) for x in _chain(u2, o[0]))          # prices on the 1-cent grid, like real bars
    return so, sh, sl, sc, v[src], src, flip


def synth_daily(o111, h111, l111, c111, v111, rng):
    """Random-walk daily context: the 110 real daily bars (relative to the previous close, with volume) are shuffled
    over the whole span and flipped up/down by a coin toss."""
    o, h, l, c, v = (np.asarray(x, float) for x in (o111, h111, l111, c111, v111))
    u = _units(o[1:], h[1:], l[1:], c[1:], c[:-1])
    perm = rng.permutation(len(u))
    flip = rng.random(len(u)) < 0.5
    u2 = u[perm]
    u2 = np.where(flip[:, None], _mirror(u2), u2)
    so, sh, sl, sc = (np.round(x, 2) for x in _chain(u2, c[0]))          # the frozen daily bars are rounded to cents
    return so, sh, sl, sc, v[1:][perm]


# ------------------------------------------------------------------------------------------------ drawing
def _decimals(step):
    d = 0
    while abs(step * 10 ** d - round(step * 10 ** d)) > 1e-6 and d < 4:
        d += 1
    return d


def _blend(color, alpha):
    r = np.array(to_rgb(color))
    return tuple(alpha * r + (1 - alpha) * np.ones(3))


def render_chart(path, title, o, h, l, c, v, x_major, x_major_labels, x_minor, lines, xlabel, thirds=False,
                 grid_major=True):
    """Draw one 1000x700 chart and return QA numbers measured on the rendered pixels.

    o,h,l,c,v: candle arrays (prices). lines: list of (label, color, y_prices). x positions are candle slots
    (candle i occupies [i, i+1), centre i+0.5). Price axis = % change from the first open drawn."""
    n = len(o)
    o, h, l, c, v = (np.asarray(x, float) for x in (o, h, l, c, v))
    base = o[0]
    pc = lambda x: (np.asarray(x, float) / base - 1.0) * 100.0            # noqa: E731
    op, hp, lp, cp = pc(o), pc(h), pc(l), pc(c)
    line_pct = [(lab, col, pc(y)) for lab, col, y in lines]
    ymin = min([lp.min()] + [np.nanmin(y) for _, _, y in line_pct])
    ymax = max([hp.max()] + [np.nanmax(y) for _, _, y in line_pct])
    pad = 0.06 * (ymax - ymin)
    ymin, ymax = ymin - pad, ymax + pad
    mult = v / np.median(v)

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.unicode_minus": False})
    fig = plt.figure(figsize=(W_PX / 100, H_PX / 100), dpi=100, facecolor="white")
    left, width = 0.035, 0.850
    axp = fig.add_axes([left, 0.290, width, 0.595], facecolor="white")
    axv = fig.add_axes([left, 0.095, width, 0.165], facecolor="white", sharex=axp)

    # ---- price panel
    axp.set_xlim(0, n)
    axp.set_ylim(ymin, ymax)
    loc = MaxNLocator(nbins=8, steps=[1, 2, 5, 10], min_n_ticks=5)
    ticks = [t for t in loc.tick_values(ymin, ymax) if ymin <= t <= ymax]
    step = ticks[1] - ticks[0]
    dec = _decimals(step)
    axp.yaxis.set_major_locator(FixedLocator(ticks))
    axp.yaxis.set_major_formatter(FuncFormatter(
        lambda val, pos, dec=dec: f"{0:.{dec}f}%" if abs(val) < 10 ** (-dec - 1) else f"{val:+.{dec}f}%"))
    axp.yaxis.tick_right()
    axp.yaxis.set_label_position("right")
    pass
    axp.grid(axis="y", color="#e4e4e4", lw=0.8, zorder=0)
    axp.set_axisbelow(True)
    for x in (x_major if grid_major else []):
        axp.axvline(x, color="#e4e4e4", lw=0.8, zorder=0)
    for x in x_minor:
        axp.axvline(x, color="#f1f1f1", lw=0.7, zorder=0)
    if thirds:
        for x in (20, 40):
            axp.axvline(x, color="#b5b5b5", lw=1.0, ls=(0, (5, 4)), zorder=1)
    axp.axhline(0.0, color="#8a8a8a", lw=1.0, ls=(0, (2, 3)), zorder=1)
    axp.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
    axp.tick_params(axis="y", length=4, color="#999999", labelsize=11)

    span = ymax - ymin
    min_body = 0.004 * span
    bw = 0.72
    up = cp >= op
    for i in range(n):
        col = GREEN if up[i] else RED
        x = i + 0.5
        axp.plot([x, x], [lp[i], hp[i]], color=col, lw=1.3, solid_capstyle="butt", zorder=3)
        lo_b, hi_b = min(op[i], cp[i]), max(op[i], cp[i])
        hgt = max(hi_b - lo_b, min_body)
        y0 = lo_b - (hgt - (hi_b - lo_b)) / 2.0
        axp.add_patch(Rectangle((x - bw / 2, y0), bw, hgt, facecolor=col, edgecolor=col, lw=0.6, zorder=4))
    handles = []
    for lab, col, y in line_pct:
        hd, = axp.plot(np.arange(n) + 0.5, y, color=col, lw=1.9, zorder=6, label=lab)
        handles.append(hd)
    if handles:
        axp.legend(handles=handles, loc="lower right", bbox_to_anchor=(1.0, 1.012), ncol=len(handles),
                   frameon=False, fontsize=11, handlelength=2.4, columnspacing=1.6, borderaxespad=0.0)
    for sp in ("top", "left"):
        axp.spines[sp].set_visible(False)
    for sp in ("right", "bottom"):
        axp.spines[sp].set_color("#999999")

    # ---- volume panel
    vcol = [GREEN if u_ else RED for u_ in up]
    axv.bar(np.arange(n) + 0.5, mult, width=bw, color=vcol, alpha=VOL_ALPHA, linewidth=0, zorder=3)
    axv.axhline(1.0, color="#7a7a7a", lw=1.0, ls=(0, (4, 3)), zorder=4)
    vmax = mult.max() * 1.10
    axv.set_ylim(0, vmax)
    axv.yaxis.tick_right()
    axv.yaxis.set_label_position("right")
    ppu = axv.get_position().height * H_PX / vmax                    # pixels per 1x of volume
    cand = [t for t in MaxNLocator(nbins=5, integer=True).tick_values(0, vmax) if 1 < t <= vmax]
    vt = ([0.0] if ppu >= 20 else []) + [1.0]                        # the dashed line is the median: always label 1x
    for t in cand:
        if (t - vt[-1]) * ppu >= 22:
            vt.append(float(t))
    axv.yaxis.set_major_locator(FixedLocator(vt))
    axv.yaxis.set_major_formatter(FuncFormatter(lambda val, pos: "0" if val == 0 else f"{val:g}x"))
    pass
    axv.grid(axis="y", color="#e4e4e4", lw=0.8, zorder=0)
    axv.set_axisbelow(True)
    for x in (x_major if grid_major else []):
        axv.axvline(x, color="#e4e4e4", lw=0.8, zorder=0)
    for x in x_minor:
        axv.axvline(x, color="#f1f1f1", lw=0.7, zorder=0)
    if thirds:
        for x in (20, 40):
            axv.axvline(x, color="#b5b5b5", lw=1.0, ls=(0, (5, 4)), zorder=1)
    axv.set_xlim(0, n)
    axv.xaxis.set_major_locator(FixedLocator(list(x_major)))
    axv.xaxis.set_major_formatter(FuncFormatter(lambda val, pos, m=list(x_major), lab=list(x_major_labels):
                                                lab[m.index(val)] if val in m else ""))
    axv.set_xlabel(xlabel, fontsize=11, labelpad=6)
    axv.tick_params(axis="x", length=4, color="#999999", labelsize=11)
    axv.tick_params(axis="y", length=4, color="#999999", labelsize=11)
    for sp in ("top", "left"):
        axv.spines[sp].set_visible(False)
    for sp in ("right", "bottom"):
        axv.spines[sp].set_color("#999999")

    ttl = fig.text(left, 0.952, title, fontsize=15, fontweight="bold", ha="left", va="center", color="#222222")
    ylab_p = fig.text(0.988, 0.5875, "% change from first open", fontsize=11, rotation=90, ha="center", va="center")
    ylab_v = fig.text(0.972, 0.1775, "Volume\n(x median)", fontsize=11, rotation=90, ha="center", va="center",
                      linespacing=1.15)

    fig.canvas.draw()
    qa = _qa(fig, axp, axv, [ttl, ylab_p, ylab_v], n, op, cp, hp, lp, mult, up, line_pct, ymin, ymax)
    fig.savefig(path, format="png", dpi=100, facecolor="white", metadata={"Software": None})
    plt.close(fig)
    return qa


def _qa(fig, axp, axv, fixed_texts, n, op, cp, hp, lp, mult, up, line_pct, ymin, ymax):
    """Measure the rendered pixels: candle colours, volume bars, indicator lines, and text placement."""
    buf = np.asarray(fig.canvas.buffer_rgba())[..., :3].astype(float) / 255.0
    H, W = buf.shape[:2]
    assert (W, H) == (W_PX, H_PX), (W, H)

    def px(ax, x, y):
        X, Y = ax.transData.transform((x, y))
        return int(round(X)), H - 1 - int(round(Y))

    def near(col, r, cc, tol=0.10):
        if 0 <= r < H and 0 <= cc < W:
            return float(np.max(np.abs(buf[r, cc] - np.array(col)))) <= tol
        return False

    line_rgb = [np.array(to_rgb(col)) for _, col, _ in line_pct]
    g, r_ = np.array(to_rgb(GREEN)), np.array(to_rgb(RED))
    checked = ok = wrong = occluded = 0
    for i in range(n):
        col, other = (g, r_) if up[i] else (r_, g)
        ylo, yhi = min(op[i], cp[i]), max(op[i], cp[i])
        _, r_hi = px(axp, i + 0.5, yhi)
        _, r_lo = px(axp, i + 0.5, ylo)
        if r_lo - r_hi < 6:
            continue                                                    # body too thin to sample reliably
        checked += 1
        hit = bad = under_line = False
        for fy in (0.25, 0.75):
            for dx in (-0.22, 0.0, 0.22):
                cc, rr = px(axp, i + 0.5 + dx, ylo + fy * (yhi - ylo))
                hit = hit or near(col, rr, cc)
                bad = bad or near(other, rr, cc)
                under_line = under_line or any(near(lc, rr, cc, tol=0.16) for lc in line_rgb)
        if hit:
            ok += 1
        elif under_line:
            occluded += 1                                               # an indicator line covers every sample
        wrong += bad
    candles = (checked, ok + occluded, wrong)
    vchecked = vok = 0
    for i in range(n):
        col = np.array(_blend(GREEN if up[i] else RED, VOL_ALPHA))
        _, r_top = px(axv, i + 0.5, mult[i])
        _, r_bot = px(axv, i + 0.5, 0.0)
        if r_bot - r_top < 6:
            continue
        vchecked += 1
        hit = False
        for fy in (0.25, 0.6):
            for d in (-2, 0, 2):
                cc, rr = px(axv, i + 0.5, mult[i] * fy)
                hit = hit or near(col, rr, cc + d, tol=0.10)
        vok += hit
    volume = (vchecked, vok)
    lines_qa = {}
    for k, (lab, col, y) in enumerate(line_pct):
        rgb = line_rgb[k]
        chk = good = 0
        for i in range(0, n, 3):
            cc, rr = px(axp, i + 0.5, y[i])
            # skip points where another line (drawn later) passes within 4 px: it may cover this one
            if any(j != k and abs(px(axp, i + 0.5, line_pct[j][2][i])[1] - rr) <= 4 for j in range(len(line_pct))):
                continue
            chk += 1
            found = False
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    if near(rgb, rr + dr, cc + dc, tol=0.16):
                        found = True
            good += found
        lines_qa[lab] = (chk, good)

    # ---- text placement
    rend = fig.canvas.get_renderer()
    texts = list(fixed_texts) + [axv.xaxis.label]
    leg = axp.get_legend()
    if leg is not None:
        texts += list(leg.get_texts())
    for ax, axis in ((axp, axp.yaxis), (axv, axv.yaxis), (axv, axv.xaxis)):
        lim = ax.get_ylim() if axis is ax.yaxis else ax.get_xlim()
        for tk in axis.get_major_ticks():
            if lim[0] - 1e-9 <= tk.get_loc() <= lim[1] + 1e-9:
                for lab in (tk.label1, tk.label2):
                    if lab.get_visible() and lab.get_text():
                        texts.append(lab)
    boxes = [(t.get_text(), t.get_window_extent(rend)) for t in texts if t.get_text()]
    outside = [s for s, b in boxes if b.x0 < 0 or b.y0 < 0 or b.x1 > W or b.y1 > H]
    overlaps = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i][1].overlaps(boxes[j][1]):
                bi, bj = boxes[i][1], boxes[j][1]
                w = min(bi.x1, bj.x1) - max(bi.x0, bj.x0)
                hh = min(bi.y1, bj.y1) - max(bi.y0, bj.y0)
                if w > 1 and hh > 1:
                    overlaps.append((boxes[i][0], boxes[j][0]))
    # legend box must not sit on top of the price axes
    leg_over_axes = False
    if leg is not None:
        lb = leg.get_window_extent(rend)
        ab = axp.get_window_extent(rend)
        leg_over_axes = bool(lb.y0 < ab.y1 - 1)
    return {"candles": candles, "volume": volume, "lines": lines_qa, "text_outside": outside,
            "text_overlaps": overlaps, "legend_over_axes": leg_over_axes, "ylim": (ymin, ymax)}


# ------------------------------------------------------------------------------------------------ chart specs
def draw_A(s: Session, path):
    o, h, l, c, v = (x[:60] for x in (s.o, s.h, s.l, s.c, s.v))
    vw = vwap_series(h, l, c, v)
    major = list(range(0, 60, 10))
    return render_chart(path, "1-minute candles", o, h, l, c, v, major, [hhmm(x) for x in major],
                        [x for x in range(5, 60, 10)], [("VWAP", BLUE, vw)], "Time of day (candle start time)")


def draw_B(s: Session, path):
    O, H, L, C, V = agg5(s.o[:150], s.h[:150], s.l[:150], s.c[:150], s.v[:150])
    vw = vwap_series(s.h[:150], s.l[:150], s.c[:150], s.v[:150])[4::5]
    em = ema20(C)
    major = list(range(0, 30, 6))
    return render_chart(path, "5-minute candles", O, H, L, C, V, major, [hhmm(5 * x) for x in major],
                        [x for x in range(3, 30, 6)],
                        [("VWAP", BLUE, vw), ("EMA 20 of 5-min closes", ORANGE, em)],
                        "Time of day (candle start time)")


def draw_C(s: Session, path):
    f0 = CTX - SHOW
    s20, s50 = sma(s.d_c, 20), sma(s.d_c, 50)
    sl = slice(f0, CTX)
    major_c = [0, 9, 19, 29, 39, 49, 59]
    return render_chart(path, "Daily candles", s.d_o[sl], s.d_h[sl], s.d_l[sl], s.d_c[sl], s.d_v[sl],
                        [x + 0.5 for x in major_c], [str(x + 1) for x in major_c], [],
                        [("20-day average", ORANGE, s20[sl]), ("50-day average", PURPLE, s50[sl])],
                        "Trading days, oldest to newest (candle number)", thirds=True, grid_major=False)


DRAW = {"A": draw_A, "B": draw_B, "C": draw_C}
