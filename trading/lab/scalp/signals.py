"""Minute-trading setups as pure functions (scalp lab).

Each setup takes ONE regular session of 1-minute bars (a `Day`) plus facts known before that session opened
(a `Ctx`: yesterday's high/low/close, the noise band, the carried EMAs) and returns trade intents.

- An intent is decided at the close of the bar it names (`Intent.m`) and is filled at the NEXT bar's open.
- A setup walks the day bar by bar and at bar i looks only at bars 0..i. Indicators are running (prefix) sums,
  so a value at bar i never depends on a later bar. `tests/test_scalp_signals.py` checks this by changing
  later bars and by cutting the day short.
- A setup knows whether it is flat by replaying its own position with `Tracker`, the same fill model the
  backtester uses (next-bar-open fills, intrabar stop/target with the stop first, flat at the 15:55 open).

Live reuse: call the setup with the bars received so far and `live=Live(...)` holding the REAL position and
the entries made today; act only on intents whose `m` is the latest bar. At that bar the setup decides from
the real position instead of the modelled one (an unfilled order or a stop filled elsewhere cannot make it
exit a position that does not exist). Earlier bars are still replayed with the model, which only matters for
once-a-day flags such as "the first breakout was already seen".

Times are minutes from the session open (`m`): the 9:30 bar is m=0, the 9:59 bar is m=29 (its close is the
10:00 price), the 15:55 bar is m=385. A bar exists only for a minute with trades, so missing minutes are
allowed: an event due at minute T is taken at the first bar with m >= T.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, replace
from datetime import date
from types import SimpleNamespace
from typing import Any, Callable

import numpy as np
import pandas as pd

NORMAL_MIN = 390          # minutes in a full regular session
EXIT_BEFORE_CLOSE = 5     # flat at the open of the bar 5 minutes before the close (15:55 on a normal day)
MAX_LEVERAGE = 4.0        # cap used by the papers' own sizing (reported only; the lab trades $1,000 per trade)


# ----------------------------------------------------------------------------------------------- data shapes
@dataclass(frozen=True)
class Day:
    """One regular session of 1-minute bars for one symbol. `m` = bar START in minutes from the open."""
    date: date
    open_ts: pd.Timestamp
    close_min: int
    m: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    v: np.ndarray
    auction_close: float | None = None   # official close (closing auction), when known; used by "close" exits

    @classmethod
    def from_frame(cls, df: pd.DataFrame, open_ts: pd.Timestamp, close_ts: pd.Timestamp) -> "Day":
        """Build from bars indexed by tz-aware bar-start time with open/high/low/close/volume columns."""
        df = df.sort_index()
        m = ((df.index - open_ts).total_seconds() // 60).astype(int).to_numpy()
        f = lambda col: df[col].to_numpy(dtype=float)  # noqa: E731
        return cls(open_ts.date(), open_ts, int((close_ts - open_ts).total_seconds() // 60), m,
                   f("open"), f("high"), f("low"), f("close"), f("volume"))

    @property
    def n(self) -> int:
        return len(self.m)

    @property
    def half_day(self) -> bool:
        return self.close_min < NORMAL_MIN

    @property
    def exit_m(self) -> int:
        return self.close_min - EXIT_BEFORE_CLOSE

    @property
    def complete(self) -> bool:
        """The data reach the time exit (False for a session still in progress or cut short by missing bars)."""
        return self.n > 0 and int(self.m[-1]) >= self.exit_m

    def ts(self, m: int) -> pd.Timestamp:
        return self.open_ts + pd.Timedelta(minutes=int(m))

    def upto(self, i: int) -> "Day":
        """The day as a live runner would see it after bar i closed."""
        k = i + 1
        return replace(self, m=self.m[:k], o=self.o[:k], h=self.h[:k], l=self.l[:k], c=self.c[:k], v=self.v[:k])


@dataclass(frozen=True)
class Ctx:
    """Facts known before the session opens. None means 'not enough history': setups that need it skip."""
    prev_close: float | None = None        # close of yesterday's last regular-session 1-minute bar (15:59)
    prev_close_auction: float | None = None  # yesterday's official close incl. the 16:00 auction, when known
    prev_high: float | None = None
    prev_low: float | None = None
    sigma: np.ndarray | None = None        # noise band: mean |close/open - 1| at minute k over the last 14 days
    daily_vol: float | None = None         # sample std of the last 14 daily close-to-close returns
    ema: tuple[float, float] | None = None  # (EMA9, EMA21) of 5-min closes after the previous session


@dataclass(frozen=True)
class Intent:
    """A decision taken at the close of bar `m`, to be filled at the next bar's open."""
    m: int
    action: str                      # "enter" or "exit"
    side: int = 0                    # +1 long, -1 short (enter only)
    stop: float | None = None        # absolute stop price
    stop_dist: float | None = None   # or stop = fill -/+ stop_dist
    target: float | None = None      # absolute target price
    target_r: float | None = None    # or target = fill +/- target_r * |fill - stop|
    target_dist: float | None = None  # or target = fill +/- target_dist
    max_hold: int | None = None      # exit at the open of the first bar >= fill minute + max_hold
    risk_pct: float | None = None    # published sizing: risk this share of equity (reported, not traded)
    size: float | None = None        # published sizing multiplier on 1x notional (reported, not traded)
    reason: str = ""


@dataclass
class Trade:
    """A filled position. exit_m is the bar start for open fills, bar start + 1 for intrabar stop/target fills."""
    side: int
    entry_m: int
    entry: float
    stop: float | None = None
    target: float | None = None
    risk: float | None = None
    max_hold: int | None = None
    pub_mult: float | None = None
    tag: str = ""
    exit_m: int = -1
    exit: float = float("nan")
    reason: str = ""


# ------------------------------------------------------------------------------------------ fill mechanics
def resolve(it: Intent, fill: float) -> tuple[float | None, float | None, float | None] | None:
    """Stop, target and risk per share once the fill price is known; None = skip (fill already past a level)."""
    s = it.side
    stop = it.stop if it.stop is not None else (fill - s * it.stop_dist if it.stop_dist is not None else None)
    if stop is not None and s * (fill - stop) <= 0:
        return None
    risk = abs(fill - stop) if stop is not None else None
    if it.target is not None:
        target = it.target
    elif it.target_r is not None and risk is not None:
        target = fill + s * it.target_r * risk
    elif it.target_dist is not None:
        target = fill + s * it.target_dist
    else:
        target = None
    if target is not None and s * (target - fill) <= 0:
        return None
    return stop, target, risk


def bar_exit(side: int, stop: float | None, target: float | None, o: float, h: float, l: float
             ) -> tuple[float, str] | None:
    """Did this bar hit the stop or target? An open beyond a level fills at the open. If the stop and the target
    are both inside the bar's range, the STOP is assumed first (conservative)."""
    if side > 0:
        if target is not None and o >= target:
            return o, "target"
        if stop is not None and o <= stop:
            return o, "stop"
        if stop is not None and l <= stop:
            return stop, "stop"
        if target is not None and h >= target:
            return target, "target"
    else:
        if target is not None and o <= target:
            return o, "target"
        if stop is not None and o >= stop:
            return o, "stop"
        if stop is not None and h >= stop:
            return stop, "stop"
        if target is not None and l <= target:
            return target, "target"
    return None


@dataclass(frozen=True)
class Live:
    """What a live runner really holds after the latest bar closed (overrides the modelled position there)."""
    side: int = 0            # +1 long, -1 short, 0 flat
    entries: int = 0         # entries already made today by this setup on this symbol
    exiting: bool = False    # an exit order is working


def _live_view(live: Live) -> Any:
    """The attributes setups read from a Tracker, taken from the real position."""
    return SimpleNamespace(side=live.side, entries=live.entries, exiting=live.exiting,
                           pos=SimpleNamespace(side=live.side) if live.side else None)


class Tracker:
    """One position at a time for one setup on one day. `step(i)` processes bar i: the time exit at its open,
    the max-hold exit, pending intents filled at its open, then the intrabar stop/target check.
    exit_mode "open": flat at the open of the first bar at or after close - 5 min; "close": flat at the
    official close when known (`day.auction_close`), else the last bar's close.
    `flip(intent)` -> True trades that entry the other way with the stop and target mirrored around the fill
    (used only by the coin-flip baseline)."""

    def __init__(self, day: Day, exit_mode: str = "open", flip: Callable[[Intent], bool] | None = None):
        self.day, self.exit_mode, self.flip = day, exit_mode, flip
        self.pos: Trade | None = None
        self.pending: list[Intent] = []
        self.trades: list[Trade] = []
        self.entries = 0
        self.done = False

    @property
    def side(self) -> int:
        """Side after pending intents fill (what the setup is committed to)."""
        side = self.pos.side if self.pos else 0
        for it in self.pending:
            side = 0 if it.action == "exit" else (it.side if side == 0 else side)
        return side

    @property
    def exiting(self) -> bool:
        return any(it.action == "exit" for it in self.pending)

    def submit(self, it: Intent) -> None:
        if self.done:
            return
        self.pending.append(it)
        if it.action == "enter":
            self.entries += 1

    def _close(self, price: float, m: int, reason: str) -> None:
        t = self.pos
        t.exit, t.exit_m, t.reason = float(price), int(m), reason
        self.trades.append(t)
        self.pos = None

    def step(self, i: int) -> None:
        if self.done:
            return
        d = self.day
        m, o, h, l = int(d.m[i]), d.o[i], d.h[i], d.l[i]
        if self.exit_mode == "open" and m >= d.exit_m:
            self.pending.clear()
            if self.pos:
                self._close(o, m, "time")
            self.done = True
            return
        if self.pos and self.pos.max_hold is not None and m >= self.pos.entry_m + self.pos.max_hold:
            self._close(o, m, "max_hold")
        if self.pending:
            for it in self.pending:
                if it.action == "exit":
                    if self.pos:
                        self._close(o, m, it.reason or "exit")
                elif self.pos is None:
                    lv = resolve(it, o)
                    if lv is None:
                        continue
                    stop, target, risk = lv
                    side, pub = it.side, it.size
                    if it.risk_pct is not None and risk:
                        pub = min(it.risk_pct * o / risk, MAX_LEVERAGE)
                    if self.flip is not None and self.flip(it):
                        side, pub = -side, None
                        stop = None if stop is None else 2.0 * o - stop
                        target = None if target is None else 2.0 * o - target
                    self.pos = Trade(side, m, float(o), stop, target, risk, it.max_hold, pub, it.reason)
            self.pending = []
        if self.pos:
            hit = bar_exit(self.pos.side, self.pos.stop, self.pos.target, o, h, l)
            if hit:
                self._close(hit[0], m + 1, hit[1])

    def finish(self) -> list[Trade]:
        """End of data: anything still open is closed at the last bar's close (the official close in "close"
        mode when it is known)."""
        d = self.day
        if self.pos and d.n:
            if self.exit_mode == "close" and d.auction_close is not None and d.complete:
                self._close(d.auction_close, d.close_min, "close")
            else:
                self._close(d.c[-1], int(d.m[-1]) + 1, "close" if self.exit_mode == "close" else "eod")
        self.pending.clear()
        self.done = True
        return self.trades


Decide = Callable[[int, Tracker], "tuple[Intent, ...] | list[Intent]"]


def replay(day: Day, decide: Decide, exit_mode: str = "open", live: Live | None = None
           ) -> tuple[list[Intent], list[Trade]]:
    """Walk the day: bar i is processed by the tracker, then the setup decides at bar i's close. With `live`,
    the decision at the latest bar sees the real position instead of the modelled one."""
    tr = Tracker(day, exit_mode)
    out: list[Intent] = []
    for i in range(day.n):
        tr.step(i)
        if tr.done:
            break
        view = _live_view(live) if live is not None and i == day.n - 1 else tr
        for it in decide(i, view) or ():
            tr.submit(it)
            out.append(it)
    return out, tr.finish()


def _enter(day: Day, i: int, side: int, **kw) -> Intent:
    return Intent(m=int(day.m[i]), action="enter", side=int(side), **kw)


def _exit(day: Day, i: int, reason: str) -> Intent:
    return Intent(m=int(day.m[i]), action="exit", reason=reason)


def _first_at(day: Day, minute: int) -> int:
    """Index of the first bar starting at or after `minute` (day.n if none yet)."""
    return int(np.searchsorted(day.m, minute, side="left"))


def _last_before(day: Day, minute: int) -> int:
    """Index of the last bar starting before `minute` (-1 if none)."""
    return int(np.searchsorted(day.m, minute, side="left")) - 1


# ---------------------------------------------------------------------------------------------- indicators
def vwap_sd(day: Day) -> tuple[np.ndarray, np.ndarray]:
    """Session VWAP of HLC3 from the open and its volume-weighted standard deviation, both running."""
    x = (day.h + day.l + day.c) / 3.0
    cv = np.cumsum(day.v)
    cvx = np.cumsum(day.v * x)
    cvx2 = np.cumsum(day.v * x * x)
    with np.errstate(invalid="ignore", divide="ignore"):
        vw = np.where(cv > 0, cvx / np.where(cv > 0, cv, 1.0), x)
        var = np.where(cv > 0, cvx2 / np.where(cv > 0, cv, 1.0) - vw * vw, 0.0)
    return vw, np.sqrt(np.clip(var, 0.0, None))


def rsi(c: np.ndarray, n: int = 2) -> np.ndarray:
    """Wilder RSI; the first average is the simple mean of the first n changes. NaN until defined."""
    out = np.full(len(c), np.nan)
    if len(c) <= n:
        return out
    d = np.diff(c)
    g, ls = np.clip(d, 0, None), np.clip(-d, 0, None)
    ag, al = g[:n].mean(), ls[:n].mean()
    for j in range(n, len(c)):
        if j > n:
            ag = (ag * (n - 1) + g[j - 1]) / n
            al = (al * (n - 1) + ls[j - 1]) / n
        out[j] = 50.0 if ag == 0 and al == 0 else (100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al))
    return out


def ema_run(seed: float | None, x: np.ndarray, n: int) -> np.ndarray:
    """EMA with alpha 2/(n+1), continuing from `seed` (or starting at the first value)."""
    a = 2.0 / (n + 1.0)
    out = np.empty(len(x))
    prev = seed
    for j, val in enumerate(x):
        prev = val if prev is None else prev + a * (val - prev)
        out[j] = prev
    return out


@dataclass(frozen=True)
class Buckets:
    """5-minute bars built from 1-minute bars. Bucket j spans minutes start[j]..start[j]+4. `close_at[i]` lists
    the buckets completed at bar i (the first bar at or after their last minute), oldest first; usually none or
    one, two when a bucket's last minute is missing and the next bar already ends the following bucket."""
    start: np.ndarray
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    close_at: tuple[tuple[int, ...], ...]


def buckets5(day: Day) -> Buckets:
    if day.n == 0:
        e = np.array([])
        return Buckets(e.astype(int), e, e, e, e, ())
    b = day.m // 5
    firsts = np.flatnonzero(np.r_[True, b[1:] != b[:-1]])
    lasts = np.r_[firsts[1:] - 1, day.n - 1]
    start = b[firsts] * 5
    closing: list[list[int]] = [[] for _ in range(day.n)]
    for j, s in enumerate(start):
        i = _first_at(day, int(s) + 4)
        if i < day.n:
            closing[i].append(j)
    return Buckets(start, day.o[firsts], np.maximum.reduceat(day.h, firsts), np.minimum.reduceat(day.l, firsts),
                   day.c[lasts], tuple(tuple(x) for x in closing))


def ema_after_day(seed: tuple[float, float] | None, day: Day) -> tuple[float, float] | None:
    """(EMA9, EMA21) of 5-min closes after this session, carried from `seed`."""
    bk = buckets5(day)
    if len(bk.c) == 0:
        return seed
    e9 = ema_run(seed[0] if seed else None, bk.c, 9)
    e21 = ema_run(seed[1] if seed else None, bk.c, 21)
    return float(e9[-1]), float(e21[-1])


def noise_moves(day: Day) -> np.ndarray:
    """|price / open - 1| at k minutes after the open (k = 1..390; price = close of the bar starting at k-1).
    Missing minutes carry the last price; minutes after an early close are NaN."""
    out = np.full(NORMAL_MIN + 1, np.nan)
    if day.n == 0:
        return out
    o0 = day.o[0]
    k = np.clip(day.m + 1, 0, NORMAL_MIN)
    out[k] = np.abs(day.c / o0 - 1.0)
    last = np.nan
    for j in range(1, min(day.close_min, NORMAL_MIN) + 1):
        if np.isnan(out[j]):
            out[j] = last
        last = out[j]
    return out


def noise_sigma(prior_moves: list[np.ndarray], days: int = 14) -> np.ndarray | None:
    """Mean move by minute over the previous `days` sessions (needs that many)."""
    if len(prior_moves) < days:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN minutes (after early closes) stay NaN
        return np.nanmean(np.vstack(prior_moves[-days:]), axis=0)


# -------------------------------------------------------------------------------------------------- setups
def orb5(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """ORB5_QQQ: direction of the first 5-min candle; stop at its other end; target 10R; else the time exit."""
    dec, last = _first_at(day, 4), _last_before(day, 5)
    if dec >= day.n or last < 0:
        return []

    def decide(i: int, tr: Tracker):
        if i != dec:
            return ()
        bo, bc = day.o[0], day.c[last]
        if bc == bo:
            return ()
        s = 1 if bc > bo else -1
        stop = day.l[:last + 1].min() if s > 0 else day.h[:last + 1].max()
        return (_enter(day, i, s, stop=float(stop), target_r=10.0, risk_pct=0.01, reason="orb5"),)

    return replay(day, decide, live=live)[0]


NOISE_TIMES = tuple(range(29, 360, 30))  # bars 9:59, 10:29, ..., 15:29 (prices at 10:00 ... 15:30)


def noise_mom(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """NOISE_MOM_SPY: trade breaks of the 14-day noise band, checked on the hour and half hour."""
    if ctx.sigma is None or ctx.prev_close is None or day.n == 0:
        return []
    vw, _ = vwap_sd(day)
    o0, pc = day.o[0], ctx.prev_close
    up_ref, dn_ref = max(o0, pc), min(o0, pc)
    dec: dict[int, int] = {}
    for t in NOISE_TIMES:
        i = _first_at(day, t)
        if i < day.n:
            dec[i] = t
    mult = min(MAX_LEVERAGE, 0.02 / ctx.daily_vol) if ctx.daily_vol else None

    def decide(i: int, tr: Tracker):
        t = dec.get(i)
        if t is None:
            return ()
        sig = ctx.sigma[t + 1]
        if not np.isfinite(sig):
            return ()
        ub, lb, p, s = up_ref * (1 + sig), dn_ref * (1 - sig), day.c[i], tr.side
        if s == 0:
            if p > ub:
                return (_enter(day, i, 1, size=mult, reason="above_band"),)
            if p < lb:
                return (_enter(day, i, -1, size=mult, reason="below_band"),)
        elif s > 0:
            if p < lb:
                return (_exit(day, i, "reverse"), _enter(day, i, -1, size=mult, reason="below_band"))
            if p < max(ub, vw[i]):
                return (_exit(day, i, "band_or_vwap"),)
        else:
            if p > ub:
                return (_exit(day, i, "reverse"), _enter(day, i, 1, size=mult, reason="above_band"))
            if p > min(lb, vw[i]):
                return (_exit(day, i, "band_or_vwap"),)
        return ()

    return replay(day, decide, live=live)[0]


def vwap_trend(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """VWAP_TREND_QQQ: always in; long above VWAP, short below, flip on a 1-min close across it."""
    vw, _ = vwap_sd(day)

    def decide(i: int, tr: Tracker):
        p, s = day.c[i], tr.side
        if s == 0:   # the first bar; live, also after an entry that did not fill
            return (_enter(day, i, 1 if p > vw[i] else -1, reason="first_bar" if i == 0 else "reenter"),)
        if s > 0 and p < vw[i]:
            return (_exit(day, i, "flip"), _enter(day, i, -1, reason="flip"))
        if s < 0 and p > vw[i]:
            return (_exit(day, i, "flip"), _enter(day, i, 1, reason="flip"))
        return ()

    return replay(day, decide, live=live)[0]


def _last30(day: Day, ctx: Ctx, variant: str, exit_mode: str = "open", live: Live | None = None) -> list[Intent]:
    pc = ctx.prev_close_auction if ctx.prev_close_auction is not None else ctx.prev_close
    dec, i10, i15 = _first_at(day, 359), _last_before(day, 30), _last_before(day, 330)
    if pc is None or dec >= day.n or i10 < 0:
        return []

    def decide(i: int, tr: Tracker):
        if i != dec:
            return ()
        r1 = day.c[i10] / pc - 1
        if variant == "mom":
            s = 1 if r1 > 0 else -1
        elif variant == "rod":
            s = 1 if day.c[i] / pc - 1 > 0 else -1
        else:  # "eta": first half-hour and 15:00-15:30 must agree
            r12 = day.c[i] / day.c[i15] - 1
            s = 1 if (r1 > 0 and r12 > 0) else (-1 if (r1 < 0 and r12 < 0) else 0)
        return (_enter(day, i, s, reason=variant),) if s else ()

    return replay(day, decide, exit_mode, live)[0]


def last30_mom(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """LAST30_MOM_SPY: sign of the first half-hour return (vs yesterday's close) decides the 15:30 trade."""
    return _last30(day, ctx, "mom", live=live)


def last30_rod(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """Variant B (Baltussen r_ROD): sign of yesterday's close -> 15:30."""
    return _last30(day, ctx, "rod", live=live)


def last30_eta(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """Variant C (Gao eta(r1, r12)): trade only when the first half-hour and 15:00-15:30 agree."""
    return _last30(day, ctx, "eta", live=live)


def last30_mom_close(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """LAST30_MOM_SPY held to the last bar's close (the papers' 16:00 exit, approximated)."""
    return _last30(day, ctx, "mom", exit_mode="close", live=live)


def _orb_range(day: Day, ctx: Ctx, minutes: int, live: Live | None = None) -> list[Intent]:
    k = _first_at(day, minutes)
    if k == 0 or k >= day.n:
        return []
    orh, orl = float(day.h[:k].max()), float(day.l[:k].min())
    st = {"taken": False}

    def decide(i: int, tr: Tracker):
        if st["taken"] or i < k or day.m[i] > 329:   # triggers from the end of the range through the 14:59 bar
            return ()
        if day.c[i] > orh:
            st["taken"] = True
            return (_enter(day, i, 1, stop=orl, target_dist=orh - orl, reason=f"orb{minutes}_up"),)
        if day.c[i] < orl:
            st["taken"] = True
            return (_enter(day, i, -1, stop=orh, target_dist=orh - orl, reason=f"orb{minutes}_down"),)
        return ()

    return replay(day, decide, live=live)[0]


def orb30(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """ORB30_CLASSIC: first 1-min close outside the 9:30-9:59 range; stop other side; target one range."""
    return _orb_range(day, ctx, 30, live)


def orb15(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """Pre-registered secondary: the same with a 9:30-9:44 range."""
    return _orb_range(day, ctx, 15, live)


def ema_pullback(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """EMA9_21_PULLBACK_5M: in a 9/21 EMA trend, buy a 5-min candle that dips to EMA9 and closes back above."""
    bk = buckets5(day)
    if len(bk.c) == 0:
        return []
    e9 = ema_run(ctx.ema[0] if ctx.ema else None, bk.c, 9)
    e21 = ema_run(ctx.ema[1] if ctx.ema else None, bk.c, 21)

    def decide(i: int, tr: Tracker):
        for j in bk.close_at[i]:          # oldest first
            if not 25 <= bk.start[j] <= 325 or tr.side != 0 or tr.entries >= 3:
                continue
            a9, a21, bo, bh, bl, bc = e9[j], e21[j], bk.o[j], bk.h[j], bk.l[j], bk.c[j]
            if a9 > a21 and bl <= a9 and bc > a9 and bc > bo:
                return (_enter(day, i, 1, stop=float(min(bl, a21) - 0.01), target_r=2.0, reason="pullback_long"),)
            if a9 < a21 and bh >= a9 and bc < a9 and bc < bo:
                return (_enter(day, i, -1, stop=float(max(bh, a21) + 0.01), target_r=2.0,
                                reason="pullback_short"),)
        return ()

    return replay(day, decide, live=live)[0]


def pdh_pdl(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """PDH_PDL_BREAK_5M: first 5-min close through yesterday's high (or low), from inside the range."""
    if ctx.prev_high is None or ctx.prev_low is None or day.n == 0:
        return []
    bk = buckets5(day)
    pdh, pdl = ctx.prev_high, ctx.prev_low
    long_ok, short_ok = day.o[0] < pdh, day.o[0] > pdl
    st = {"long": False, "short": False}

    def decide(i: int, tr: Tracker):
        for j in bk.close_at[i]:          # oldest first
            if not 10 <= bk.start[j] <= 325:     # 5-min bars closing 9:45 through 15:00
                continue
            if long_ok and not st["long"] and bk.c[j] > pdh:
                st["long"] = True
                if tr.side == 0:
                    return (_enter(day, i, 1, stop=float(bk.l[j]), target_r=2.0, reason="pdh_break"),)
            elif short_ok and not st["short"] and bk.c[j] < pdl:
                st["short"] = True
                if tr.side == 0:
                    return (_enter(day, i, -1, stop=float(bk.h[j]), target_r=2.0, reason="pdl_break"),)
        return ()

    return replay(day, decide, live=live)[0]


def vwap_fade(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """VWAP_2SD_FADE_1M: fade a close 2 volume-weighted SDs from VWAP with RSI(2) extreme; exit at VWAP."""
    vw, sd = vwap_sd(day)
    r2 = rsi(day.c, 2)

    def decide(i: int, tr: Tracker):
        p = day.c[i]
        if tr.pos is not None:
            if not tr.exiting and ((tr.pos.side > 0 and p >= vw[i]) or (tr.pos.side < 0 and p <= vw[i])):
                return (_exit(day, i, "vwap"),)
            return ()
        if tr.side != 0 or tr.entries >= 3 or not 29 <= day.m[i] <= 359 or not np.isfinite(r2[i]):
            return ()
        if p < vw[i] - 2 * sd[i] and r2[i] < 10:
            return (_enter(day, i, 1, stop_dist=float(sd[i]), max_hold=30, reason="fade_low"),)
        if p > vw[i] + 2 * sd[i] and r2[i] > 90:
            return (_enter(day, i, -1, stop_dist=float(sd[i]), max_hold=30, reason="fade_high"),)
        return ()

    return replay(day, decide, live=live)[0]


def _gap(day: Day, ctx: Ctx, fade: bool, live: Live | None = None) -> list[Intent]:
    pc = ctx.prev_close_auction if ctx.prev_close_auction is not None else ctx.prev_close
    dec, last = _first_at(day, 4), _last_before(day, 5)
    if pc is None or dec >= day.n or last < 0:
        return []

    def decide(i: int, tr: Tracker):
        if i != dec:
            return ()
        g = day.o[0] / pc - 1
        if abs(g) < 0.005 - 1e-12:
            return ()
        size = abs(day.o[0] - pc)
        lo5, hi5 = day.l[:last + 1].min(), day.h[:last + 1].max()
        if g > 0 and lo5 > pc:
            it = (_enter(day, i, -1, target=pc, stop_dist=size, reason="fade_gap_up") if fade else
                  _enter(day, i, 1, stop=pc, target_dist=size, reason="go_gap_up"))
            return (it,)
        if g < 0 and hi5 < pc:
            it = (_enter(day, i, 1, target=pc, stop_dist=size, reason="fade_gap_down") if fade else
                  _enter(day, i, -1, stop=pc, target_dist=size, reason="go_gap_down"))
            return (it,)
        return ()

    return replay(day, decide, live=live)[0]


def gap_fade(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """GAP_FADE_SPY: a >= 0.5% opening gap not filled by 9:34 is faded toward yesterday's close."""
    return _gap(day, ctx, fade=True, live=live)


def gap_go(day: Day, ctx: Ctx, live: Live | None = None) -> list[Intent]:
    """Pre-registered secondary 'gap-and-go': the same trigger traded with the gap."""
    return _gap(day, ctx, fade=False, live=live)


# ------------------------------------------------------------------------------------------------ registry
@dataclass(frozen=True)
class Setup:
    id: str
    fn: Callable[..., list[Intent]]   # fn(day, ctx, live=None)
    primary: tuple[str, ...] = ("SPY", "QQQ")
    exit_mode: str = "open"
    note: str = ""


SETUPS: dict[str, Setup] = {s.id: s for s in (
    Setup("ORB5_QQQ", orb5, ("QQQ",), note="Zarattini & Aziz 2023; SPY is a robustness check"),
    Setup("NOISE_MOM_SPY", noise_mom, ("SPY",), note="Zarattini, Aziz & Barbon 2024; 1x sizing primary"),
    Setup("VWAP_TREND_QQQ", vwap_trend, ("QQQ",), note="Zarattini & Aziz 2023; SPY is a robustness check"),
    Setup("LAST30_MOM_SPY", last30_mom, ("SPY",), note="Gao et al. 2018 eq. 4; exit 15:55 open"),
    Setup("LAST30_ROD_SPY", last30_rod, ("SPY",), note="variant B (Baltussen r_ROD)"),
    Setup("LAST30_ETA_SPY", last30_eta, ("SPY",), note="variant C (Gao eta)"),
    Setup("LAST30_MOM_SPY_CLOSE", last30_mom_close, ("SPY",), "close",
          note="sensitivity: exit at the official 16:00 close (the 15:59 bar close when it is unknown)"),
    Setup("ORB30_CLASSIC", orb30, note="retail convention"),
    Setup("ORB15_CLASSIC", orb15, note="pre-registered secondary of ORB30_CLASSIC"),
    Setup("EMA9_21_PULLBACK_5M", ema_pullback, note="retail convention"),
    Setup("PDH_PDL_BREAK_5M", pdh_pdl, note="retail convention"),
    Setup("VWAP_2SD_FADE_1M", vwap_fade, note="retail convention"),
    Setup("GAP_FADE_SPY", gap_fade, note="Grant, Wolf & Yu 2005 context"),
    Setup("GAP_GO_SPY", gap_go, note="pre-registered secondary of GAP_FADE_SPY"),
)}
