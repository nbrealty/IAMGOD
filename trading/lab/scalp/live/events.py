"""Scheduled market events for the clock rules (MT-G20): FOMC statement days and economic releases.

`events_<year>.json` (committed) holds:
    {"covers_from": "2026-01-01", "covers_through": "2026-12-31" | null,
     "fomc":     [{"date": "2026-01-28", "verified": true, "source": "..."}],
     "releases": [{"date": "2026-10-02", "time": "08:30", "name": "Employment Situation", "verified": true,
                   "source": "..."}]}

Rules (ChatGPT spec section 2: a missing calendar is UNKNOWN, never "no events"):
- a date outside [covers_from, covers_through] is unknown (`DayEvents.known = False`), and so is every date
  when either bound is null;
- only entries marked `verified: true` count as known events; an unverified entry makes its date unknown;
- a release before the 09:30 open (08:30 CPI, payrolls ...) makes the day an "08:30 release day"
  (`release_0830`, names); a release during the session (10:00 ISM, JOLTS ...) goes to `releases_1000` as a
  New York timestamp and gets the t-2m..t+5m entry blackout. The field keeps its design name for any in-session
  time, so a 09:45 or 14:00 release is blacked out the same way (stricter).
- Notes 1 Patch C: every release (pre-open ones included) is also kept with its time and name in `release_times`,
  and an FOMC day's `statement` and `press_conference` times in `fomc_times` (the standard 14:00 / 14:30 when the
  file gives none: clock.event_windows), for the whole-hold event check (EVENT_HORIZON_OVERLAP).
Unknown dates block every entry; exits are never affected.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path
from typing import Any

import pandas as pd

from .config import EVENTS_PATH
from .model import as_ny

SESSION_OPEN = time(9, 30)


@dataclass(frozen=True)
class DayEvents:
    known: bool
    release_0830: list[str] = field(default_factory=list)          # names of pre-open releases (08:30 and similar)
    releases_1000: list[pd.Timestamp] = field(default_factory=list)  # in-session release times (NY)
    fomc: bool = False
    release_times: list[tuple[pd.Timestamp, str]] = field(default_factory=list)  # every release (NY time, name)
    fomc_times: list[tuple[pd.Timestamp, str]] = field(default_factory=list)     # statement / press conference


@dataclass(frozen=True)
class EventCalendar:
    covers_from: date | None
    covers_through: date | None
    fomc: dict[date, bool]                                   # date -> verified
    releases: dict[date, list[tuple[time, str, bool]]]       # date -> [(time, name, verified)]
    path: str = ""
    fomc_times: dict[date, list[tuple[time, str]]] = field(default_factory=dict)   # date -> [(time, what)]

    def covers(self, d: date) -> bool:
        return (self.covers_from is not None and self.covers_through is not None
                and self.covers_from <= d <= self.covers_through)

    def day(self, d: date) -> DayEvents:
        rel = self.releases.get(d, [])
        fomc_entry = self.fomc.get(d)
        verified = (fomc_entry is None or fomc_entry) and all(v for _, _, v in rel)
        # Unverified entries still show up (stricter), but they make the date unknown, which blocks entries.
        return DayEvents(
            known=bool(self.covers(d) and verified),
            release_0830=[n for t, n, _ in rel if t < SESSION_OPEN],
            releases_1000=[as_ny(pd.Timestamp.combine(d, t)) for t, _, _ in rel if t >= SESSION_OPEN],
            fomc=fomc_entry is not None,
            release_times=[(as_ny(pd.Timestamp.combine(d, t)), n) for t, n, _ in rel],
            fomc_times=[(as_ny(pd.Timestamp.combine(d, t)), n) for t, n in self.fomc_times.get(d, [])])


def _date(v: Any, what: str) -> date | None:
    if v is None:
        return None
    try:
        return date.fromisoformat(str(v))
    except ValueError as e:
        raise ValueError(f"events: bad date for {what}: {v!r}") from e


def _time(v: Any, what: str) -> time:
    try:
        return time.fromisoformat(str(v))
    except ValueError as e:
        raise ValueError(f"events: bad time for {what}: {v!r}") from e


def load_events(path: str | Path = EVENTS_PATH) -> EventCalendar:
    """Read the calendar. A malformed file raises (the runner then treats every date as unknown)."""
    raw = json.loads(Path(path).read_text())
    fomc: dict[date, bool] = {}
    fomc_times: dict[date, list[tuple[time, str]]] = {}
    for e in raw.get("fomc", []):
        d = _date(e.get("date"), "fomc")
        fomc[d] = bool(fomc.get(d, True) and e.get("verified") is True)
        for key, what in (("statement", "FOMC statement"), ("press_conference", "FOMC press conference")):
            if e.get(key) is not None:
                fomc_times.setdefault(d, []).append((_time(e.get(key), f"{what} {d}"), what))
    releases: dict[date, list[tuple[time, str, bool]]] = {}
    for e in raw.get("releases", []):
        d = _date(e.get("date"), "release")
        name = str(e.get("name") or "").strip()
        if not name:
            raise ValueError(f"events: release on {d} has no name")
        releases.setdefault(d, []).append((_time(e.get("time"), name), name, e.get("verified") is True))
    return EventCalendar(_date(raw.get("covers_from"), "covers_from"), _date(raw.get("covers_through"),
                         "covers_through"), fomc, releases, str(path), fomc_times)


def load_events_or_unknown(path: str | Path = EVENTS_PATH) -> EventCalendar:
    """Like load_events, but a missing or broken file gives a calendar that knows no date (all UNKNOWN)."""
    try:
        return load_events(path)
    except (OSError, ValueError):
        return EventCalendar(None, None, {}, {}, str(path))
