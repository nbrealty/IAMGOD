"""Session clock rules for entries (MT-G20). Pure: `now` is always a parameter, nothing reads the system clock.

Times come from the exchange calendar (Alpaca's open and close for the day), so half days shift everything:
on a 13:00 close the entry cutoff is 12:31, the flatten 12:50 and the kill check 12:55. The backtest skipped
half days, so a half day is also rejected outright (HALF_DAY: untested).

Windows (a normal day):
- 09:30:00-09:44:59 OPENING_BLOCK, unless the setup registered the opening window (ORB5_QQQ decides at 9:35).
  On an 08:30 release day (CPI, payrolls ...) the setup also needs `tested_on_release_days`.
- from 15:31:00 AFTER_ENTRY_CUTOFF (a 15:30:xx decision still goes: LAST30 decides on the 15:29 bar's close).
- from 15:50:00 FLATTEN_WINDOW (the engine exits everything); 15:55 kill check; 15:57 outside watchdog.
- a scheduled 10:00 release at t: RELEASE_BLACKOUT from t-2m through t+5m inclusive.
- FOMC statement day: FOMC_BLACKOUT from 13:58:00 through 15:30:59.
- an event calendar that does not cover the day: EVENT_CALENDAR_UNKNOWN (never read as "no events").

Notes 1 Patch C (owner-approved 2026-09-28), checked by risk.py through `event_horizon_hits`: the whole intended
hold must stay clear of every scheduled event window, not only the decision time. The interval is
[d, e_latest + H + B_exit] with d the decision time, e_latest = d + ENTRY_TIMEOUT_S (the entry parent is cancelled
after that), H the setup's registered `max_hold` ("until_flatten": the hold ends at flatten_at; N minutes: at
e_latest + N min, never past flatten_at) and B_exit = EVENT_EXIT_ALLOWANCE_S. Event windows are [t - 5 min,
t + 10 min] around every release in the calendar (08:30 and 10:00 alike) and the FOMC statement and press
conference; inclusive endpoints overlap. H is never shortened to squeeze a trade through.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from . import config as C
from .model import Reason, as_ny

NORMAL_SESSION_MIN = 390


@dataclass(frozen=True)
class SessionTimes:
    """One regular session's clock, all tz-aware New York Timestamps."""
    date: date
    open: pd.Timestamp
    close: pd.Timestamp
    half_day: bool
    open_block_end: pd.Timestamp      # open + 15 min: entries allowed from here
    entry_cutoff: pd.Timestamp        # close - 29 min: entries allowed while now < this
    flatten_at: pd.Timestamp          # close - 10 min
    kill_at: pd.Timestamp             # close - 5 min
    watchdog_flat_at: pd.Timestamp    # close - 3 min

    @classmethod
    def from_calendar(cls, d: date, open_ts: pd.Timestamp, close_ts: pd.Timestamp) -> "SessionTimes":
        o, c = as_ny(open_ts), as_ny(close_ts)
        if c <= o or o.date() != d:
            raise ValueError(f"bad session {d}: open {o}, close {c}")
        m = pd.Timedelta(minutes=1)
        return cls(date=d, open=o, close=c,
                   half_day=(c - o) < NORMAL_SESSION_MIN * m,
                   open_block_end=o + C.OPEN_BLOCK_MIN * m,
                   entry_cutoff=c - C.ENTRY_CUTOFF_MIN_BEFORE_CLOSE * m,
                   flatten_at=c - C.FLATTEN_MIN_BEFORE_CLOSE * m,
                   kill_at=c - C.KILL_MIN_BEFORE_CLOSE * m,
                   watchdog_flat_at=c - C.WATCHDOG_FLAT_MIN_BEFORE_CLOSE * m)

    def is_open(self, now: pd.Timestamp) -> bool:
        return self.open <= as_ny(now) < self.close


def at(d: date, hhmmss: str) -> pd.Timestamp:
    """New York wall-clock time on date d ("13:58" or "15:30:59")."""
    return as_ny(pd.Timestamp(f"{d.isoformat()} {hhmmss}"))


def fomc_window(d: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    """[start, end] inclusive, to the second."""
    return at(d, C.FOMC_BLOCK[0]), at(d, C.FOMC_BLOCK[1])


def clock_reasons(now: pd.Timestamp, st: SessionTimes, reg, ev) -> list[Reason]:
    """Every clock rule that blocks a NEW entry right now (empty list = the clock allows it). `reg` is the
    setup's Registration (None = treated as not registered on the opening window); `ev` is events.DayEvents.
    Exits never go through this function (MT-G38)."""
    now = as_ny(now)
    out: list[Reason] = []
    if not (st.open <= now < st.close):
        out.append(Reason.MARKET_CLOSED)
    if st.half_day:
        out.append(Reason.HALF_DAY)
    if now < st.open_block_end:
        allowed = bool(reg is not None and reg.opening_window)
        if allowed and ev is not None and ev.release_0830:
            allowed = bool(reg.tested_on_release_days)
        if not allowed:
            out.append(Reason.OPENING_BLOCK)
    if now >= st.entry_cutoff:
        out.append(Reason.AFTER_ENTRY_CUTOFF)
    if now >= st.flatten_at:
        out.append(Reason.FLATTEN_WINDOW)
    if ev is None or not ev.known:
        out.append(Reason.EVENT_CALENDAR_UNKNOWN)
    if ev is not None:
        before = pd.Timedelta(minutes=C.RELEASE_BLOCK_BEFORE_MIN)
        after = pd.Timedelta(minutes=C.RELEASE_BLOCK_AFTER_MIN)
        if any(as_ny(t) - before <= now <= as_ny(t) + after for t in ev.releases_1000):
            out.append(Reason.RELEASE_BLACKOUT)
        if ev.fomc:
            a, b = fomc_window(st.date)
            if a <= now <= b + pd.Timedelta(microseconds=999_999):   # through 15:30:59.999
                out.append(Reason.FOMC_BLACKOUT)
    return out


# ------------------------------------------------------------------------------------------ Notes 1 Patch C
def event_windows(st: SessionTimes, ev) -> list[tuple[pd.Timestamp, pd.Timestamp, str]]:
    """[(start, end, name)] of every scheduled event window on the day: [t - 5 min, t + 10 min] around each release
    (release_times, plus releases_1000 given without a name) and, on an FOMC day, the statement and press conference
    (the calendar's times, else the standard 14:00 / 14:30: a missing time can never clear the day)."""
    if ev is None:
        return []
    times: dict[pd.Timestamp, list[str]] = {}

    def put(t: pd.Timestamp, name: str) -> None:
        names = times.setdefault(as_ny(t), [])
        if name not in names:
            names.append(name)

    for t, name in getattr(ev, "release_times", None) or []:
        put(t, str(name))
    for t in getattr(ev, "releases_1000", None) or []:
        if as_ny(t) not in times:
            put(t, "release")
    if getattr(ev, "fomc", False):
        fomc = list(getattr(ev, "fomc_times", None) or [])
        if not fomc:
            fomc = [(at(st.date, hhmm), what) for hhmm, what in C.FOMC_EVENT_TIMES]
        for t, what in fomc:
            put(t, str(what))
    before = pd.Timedelta(minutes=C.EVENT_WINDOW_BEFORE_MIN)
    after = pd.Timedelta(minutes=C.EVENT_WINDOW_AFTER_MIN)
    return [(t - before, t + after, f"{' + '.join(names)} {t:%H:%M}") for t, names in sorted(times.items())]


def hold_horizon(now: pd.Timestamp, st: SessionTimes, reg) -> tuple[pd.Timestamp, pd.Timestamp]:
    """[d, e_latest + H + B_exit] for an entry decided at `now` (see the module docstring). A missing registration
    counts as held until the flatten (the longest hold)."""
    d = as_ny(now)
    e_latest = d + pd.Timedelta(seconds=C.ENTRY_TIMEOUT_S)
    mh = getattr(reg, "max_hold", C.MAX_HOLD_UNTIL_FLATTEN) if reg is not None else C.MAX_HOLD_UNTIL_FLATTEN
    if mh == C.MAX_HOLD_UNTIL_FLATTEN:
        hold_end = max(st.flatten_at, e_latest)
    else:
        hold_end = max(min(e_latest + pd.Timedelta(minutes=int(mh)), st.flatten_at), e_latest)
    return d, hold_end + pd.Timedelta(seconds=C.EVENT_EXIT_ALLOWANCE_S)


def event_horizon_hits(now: pd.Timestamp, st: SessionTimes, reg, ev) -> list[str]:
    """Names of the event windows the entry's whole hold would meet (inclusive endpoints); [] = clear. Entries only
    (MT-G38): exits never go through this."""
    a, b = hold_horizon(now, st, reg)
    return [name for w0, w1, name in event_windows(st, ev) if a <= w1 and w0 <= b]
