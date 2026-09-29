"""Offline tests for the runtime of the live paper minute trader (market, runner, watchdog, report, CLI).

Every test uses fakes: no network, no keys, no trading/state. Names say which rule each test proves."""
from __future__ import annotations

import ast
import dataclasses
import json
import re
from argparse import Namespace
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from lab.scalp import backtest as bt
from lab.scalp import data as dt
from lab.scalp.live import __main__ as cli
from lab.scalp.live import config as C
from lab.scalp.live import journal as J
from lab.scalp.live import market as M
from lab.scalp.live import orders as O
from lab.scalp.live import report as REP
from lab.scalp.live import risk as R
from lab.scalp.live import runner as RUN
from lab.scalp.live import state as S
from lab.scalp.live import watchdog as W
from lab.scalp.live.clock import SessionTimes
from lab.scalp.live.events import DayEvents
from lab.scalp.live.model import (NY, AccountView, Bar, Candidate, DayCounters, Feed, Kind, Lane, LastTrade,
                                  MarketSnapshot, Mode, OrderView, PositionView, Quote, Reason, SlotState)

LIVE = Path(C.__file__).resolve().parent
D = date(2026, 10, 1)          # a Thursday inside the event calendar


def ts(hhmmss: str, d: date = D) -> pd.Timestamp:
    return pd.Timestamp(f"{d} {hhmmss}", tz=NY)


def session(d: date = D) -> SessionTimes:
    return SessionTimes.from_calendar(d, ts("09:30", d), ts("16:00", d))


class Clock:
    def __init__(self, t):
        self.t = pd.Timestamp(t)

    def __call__(self):
        return self.t

    def set(self, t):
        self.t = pd.Timestamp(t)


# ============================================================================================ LiveMarket
class FakeIEX:
    """Latest quote/trade and minute bars as the IEX REST endpoints would give them at `clock()`: the bar request
    also returns the minute still in progress (which must never be delivered), and a bar shows up `lag_s` seconds
    after its minute ends. `px[start]` can be changed later to simulate a correction."""

    def __init__(self, clock, symbols=("SPY", "QQQ"), lag_s=0.0):
        self.clock, self.symbols, self.lag = clock, symbols, pd.Timedelta(seconds=lag_s)
        self.px: dict[pd.Timestamp, float] = {}
        self.fail_quotes = False
        self.calls = {"quote": 0, "trade": 0, "bars": 0}

    def price(self, t):
        return self.px.get(t, 650.0 + (t - ts("09:30")).total_seconds() / 6000)

    def get_stock_latest_quote(self, req):
        self.calls["quote"] += 1
        if self.fail_quotes:
            raise ConnectionError("feed down")
        now = self.clock()
        return {s: SimpleNamespace(bid_price=650.0, ask_price=650.01, bid_size=1, ask_size=2,
                                   timestamp=(now - pd.Timedelta(milliseconds=300)).tz_convert("UTC").to_pydatetime())
                for s in req.symbol_or_symbols}

    def get_stock_latest_trade(self, req):
        self.calls["trade"] += 1
        now = self.clock()
        return {s: SimpleNamespace(price=650.005, size=10, timestamp=now.tz_convert("UTC").to_pydatetime())
                for s in req.symbol_or_symbols}

    def get_stock_bars(self, req):
        self.calls["bars"] += 1
        assert req.feed.value == "iex"
        now = self.clock()
        start = pd.Timestamp(req.start)
        start = (start.tz_localize("UTC") if start.tzinfo is None else start).tz_convert(NY)
        rows = []
        t = start.floor("min")
        while t <= now.floor("min"):
            done = t + pd.Timedelta(minutes=1) + self.lag <= now
            if done or t == now.floor("min"):           # the in-progress minute comes back too
                for s in req.symbol_or_symbols:
                    p = self.price(t)
                    rows.append((s, t.tz_convert("UTC"), p, p + 0.05, p - 0.05, p, 1000.0))
            t += pd.Timedelta(minutes=1)
        idx = pd.MultiIndex.from_arrays([[r[0] for r in rows], [r[1] for r in rows]], names=["symbol", "timestamp"])
        df = pd.DataFrame([r[2:] for r in rows], columns=["open", "high", "low", "close", "volume"], index=idx)
        return SimpleNamespace(df=df)


def _live(clock, fake, **kw):
    return M.LiveMarket(fake, ["SPY", "QQQ"], clock, session_open=ts("09:30"), session_close=ts("16:00"), **kw)


def test_mt_g22_live_market_delivers_each_completed_bar_once_and_never_an_in_progress_bar():
    clock = Clock(ts("09:30:00.5"))
    fake = FakeIEX(clock)
    j = J.MemoryJournal(Mode.DRY, clock)
    lm = _live(clock, fake, journal=j)
    seen = []

    def poll(t):
        clock.set(ts(t))
        s = lm.poll()
        for sym, bars in s.new_bars.items():
            for b in bars:
                assert b.start + pd.Timedelta(minutes=1) <= s.now       # complete when delivered
                assert b.feed is Feed.IEX
                seen.append((sym, b.start.strftime("%H:%M")))
        return s

    s = poll("09:30:00.5")
    assert s.new_bars == {} and fake.calls["bars"] == 0               # nothing due yet: no bar request at all
    s = poll("09:31:00.5")
    assert {k: [b.start.strftime("%H:%M") for b in v] for k, v in s.new_bars.items()} == \
        {"SPY": ["09:30"], "QQQ": ["09:30"]}                           # the 09:31 bar in progress is NOT delivered
    n = fake.calls["bars"]
    s = poll("09:31:30")
    assert s.new_bars == {} and fake.calls["bars"] == n                # next bar not due: no request
    fake.px[ts("09:30")] = 999.0                                       # a later correction of a delivered bar...
    poll("09:32:00.2")
    poll("09:33:00.2")
    assert seen.count(("SPY", "09:30")) == 1                           # ...is never delivered again
    assert sorted(set(seen)) == sorted(seen)                           # every bar exactly once
    assert s.halted == {"SPY": None, "QQQ": None}                      # halt status unknown, never "not halted"
    assert j.kinds().count("HALT_STATUS_UNAVAILABLE") == 1


def test_mt_g22_live_market_backfills_missed_minutes_in_order():
    clock = Clock(ts("09:31:00.5"))
    fake = FakeIEX(clock)
    lm = _live(clock, fake)
    lm.poll()
    clock.set(ts("09:36:00.4"))                                        # the process was busy for 5 minutes
    s = lm.poll()
    assert [b.start.strftime("%H:%M") for b in s.new_bars["SPY"]] == ["09:31", "09:32", "09:33", "09:34", "09:35"]
    assert [b.start.strftime("%H:%M") for b in s.new_bars["QQQ"]] == ["09:31", "09:32", "09:33", "09:34", "09:35"]


def test_mt_g22_live_market_waits_for_a_late_bar_and_delivers_it_once():
    clock = Clock(ts("09:31:00.3"))
    fake = FakeIEX(clock, lag_s=2.0)
    lm = _live(clock, fake)
    assert lm.poll().new_bars == {}                                    # due but not published yet
    clock.set(ts("09:31:01.3"))
    assert lm.poll().new_bars == {}
    clock.set(ts("09:31:02.3"))
    assert [b.start.strftime("%H:%M") for b in lm.poll().new_bars["SPY"]] == ["09:30"]
    clock.set(ts("09:31:03.3"))
    assert lm.poll().new_bars == {}


def test_mt_g22_failed_polls_leave_the_data_stale_and_the_entry_gate_says_data_stale():
    clock = Clock(ts("11:00:00"))
    fake = FakeIEX(clock)
    lm = _live(clock, fake)
    s = lm.poll()
    assert s.last_data_ok == ts("11:00:00")
    fake.fail_quotes = True
    clock.set(ts("11:00:03"))
    s = lm.poll()
    assert s.last_data_ok == ts("11:00:00") and any("quote" in e for e in lm.errors)
    assert s.quotes["SPY"].ts < ts("11:00:00")                          # the old quote is kept, and it is old
    reg = C.load_registry().get("NOISE_MOM_SPY", "SPY")
    ec = R.EntryContext(now=s.now, candidate=Candidate(reg.setup_id, 1, "SPY", "enter", 1, ts("10:59")), reg=reg,
                        counters=DayCounters(D, 100_000.0, cash_prev_close=100_000.0), session=session(),
                        events=DayEvents(known=True), quote=s.quotes["SPY"], last_trade=s.trades["SPY"],
                        recent_bars=[], last_data_ok=s.last_data_ok, clock_offset_ms=None, halted=None,
                        prior_close=648.0, slot_state=SlotState.FLAT, open_parents=0, open_position=False)
    why = R.entry_reasons(ec)
    assert Reason.DATA_STALE in why and Reason.QUOTE_STALE in why and Reason.CLOCK_UNVERIFIED in why


def test_live_market_records_every_poll_and_the_recording_plays_back(tmp_path):
    clock = Clock(ts("09:31:00.5"))
    rec = M.Recorder(tmp_path / "rec.jsonl")
    lm = _live(clock, FakeIEX(clock), recorder=rec)
    snaps = []
    for t in ("09:31:00.5", "09:31:01.5", "09:32:00.5"):
        clock.set(ts(t))
        snaps.append(lm.poll())
    rec.close()
    back = M.RecordingMarket(tmp_path / "rec.jsonl")
    out = []
    while (s := back.poll()) is not None:
        out.append(s)
        assert back.clock() == s.now
    assert out == snaps


# ============================================================================================ clock offset
def test_mt_g22_clock_offset_is_distance_to_the_server_plus_half_the_round_trip():
    assert M.offset_from_samples([(100.0, 100.05, 100.02)]) == pytest.approx(40.0 + 10.0)
    # best of 3 by round trip: the 4 ms sample wins even though another sample looks closer
    samples = [(0.0, 0.0, 0.3), (10.0, 10.010, 10.004), (20.0, 20.0, 20.2)]
    assert M.offset_from_samples(samples) == pytest.approx(8.0 + 2.0)
    assert M.offset_from_samples([]) is None
    assert M.offset_from_samples([(1.0, None, 1.1)]) is None


def test_mt_g22_clock_offset_measured_once_a_minute_and_none_when_the_clock_call_fails():
    class Trading:
        def __init__(self, fail=False):
            self.calls, self.fail = 0, fail

        def get_clock(self):
            self.calls += 1
            if self.fail:
                raise TimeoutError("no answer")
            return SimpleNamespace(timestamp=pd.Timestamp(1_000.030, unit="s", tz="UTC").to_pydatetime())

    walls = iter([1000.00, 1000.02, 1000.00, 1000.02, 1000.00, 1000.02] * 4)
    clock = Clock(ts("11:00:00"))
    tr = Trading()
    lm = _live(clock, FakeIEX(clock), trading_client=tr, wall=lambda: next(walls))
    s = lm.poll()
    assert s.clock_offset_ms == pytest.approx(20.0 + 10.0) and tr.calls == 3
    clock.set(ts("11:00:30"))
    lm.poll()
    assert tr.calls == 3                                               # not again within the minute
    clock.set(ts("11:01:00"))
    lm.poll()
    assert tr.calls == 6
    assert M.measure_offset(Trading(fail=True)) is None                # unverified, never "fine"


# ============================================================================================ ReplayMarket
def _bars(starts, sym="SPY", px=650.0):
    return [Bar(sym, ts(s), px, px + 0.1, px - 0.1, px + 0.02, 1000.0, Feed.SIP) for s in starts]


def test_mt_g27_replay_market_ticks_one_three_and_six_seconds_after_each_minute():
    bars = {"SPY": _bars(["09:30", "09:31", "09:33"]), "QQQ": _bars(["09:30", "09:32"], "QQQ", 560.0)}
    asked = []

    def qf(sym, t):
        asked.append((sym, t))
        return Quote(sym, 650.0, 650.01, 1, 1, t - pd.Timedelta(milliseconds=100), t, Feed.SIP)

    rm = M.ReplayMarket(D, bars, qf, open_ts=ts("09:30"), close_ts=ts("09:35"))
    sched = [(t.strftime("%H:%M:%S"), m.strftime("%H:%M") if m is not None else None) for t, m in rm.ticks()]
    assert sched[:6] == [("09:31:01", "09:30"), ("09:31:03", None), ("09:31:06", None),
                         ("09:32:01", "09:31"), ("09:32:03", None), ("09:32:06", None)]
    assert len(sched) == 5 * 3
    got = []
    while (s := rm.poll()) is not None:
        assert rm.clock() == s.now and s.last_data_ok == s.now and s.clock_offset_ms == 0.0
        got.append((s.now.strftime("%H:%M:%S"), {k: [b.start.strftime("%H:%M") for b in v]
                                                 for k, v in s.new_bars.items()}))
    assert got[0] == ("09:31:01", {"SPY": ["09:30"], "QQQ": ["09:30"]})
    assert got[3] == ("09:32:01", {"SPY": ["09:31"]})
    assert got[6] == ("09:33:01", {"QQQ": ["09:32"]})                  # SPY 09:32 missing: nothing invented
    assert got[1][1] == {} and got[2][1] == {}                          # +3 s and +6 s: order handling only
    assert ("SPY", ts("09:31:06")) in asked                             # a real quote at every tick
    last = s if s is not None else None
    assert last is None and rm.done


def test_sip_quote_source_caches_on_disk_and_refuses_the_last_16_minutes(tmp_path):
    class Data:
        def __init__(self):
            self.n = 0

        def get_stock_quotes(self, req):
            self.n += 1
            assert req.feed.value == "sip" and req.limit == 1
            t = pd.Timestamp(req.end)
            return SimpleNamespace(data={"SPY": [SimpleNamespace(bid_price=650.0, ask_price=650.02, bid_size=3,
                                                                 ask_size=4, timestamp=t.to_pydatetime())]})

    data = Data()
    src = M.SipQuoteSource(data, tmp_path, now_fn=lambda: ts("20:00"))
    q = src("SPY", ts("10:00:01"))
    assert (q.bid, q.ask, q.feed) == (650.0, 650.02, Feed.SIP) and data.n == 1
    src.flush()
    again = M.SipQuoteSource(data, tmp_path, now_fn=lambda: ts("20:00"))
    assert again("SPY", ts("10:00:01")) == q and data.n == 1           # from the disk cache
    late = M.SipQuoteSource(data, tmp_path, now_fn=lambda: ts("10:10"))
    assert late("SPY", ts("10:00:02")) is None and data.n == 1         # younger than 16 minutes: not asked


# ============================================================================================ build_context
def _px(idx: pd.DatetimeIndex) -> np.ndarray:
    t = idx.asi8 / 6e10
    return 600.0 + 8.0 * np.sin(t / 3000.0) + 1.5 * np.sin(t / 97.0) + 0.3 * np.sin(t / 7.0)


class FakeSIP:
    """Deterministic SIP minute and daily bars (weekdays, extended hours 04:00-19:59)."""

    def __init__(self):
        self.requests = []

    def get_stock_bars(self, req):
        self.requests.append(req)
        start, end = pd.Timestamp(req.start), pd.Timestamp(req.end)
        start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
        end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
        if req.timeframe.value == "1Day":
            days = pd.bdate_range(start.tz_convert(NY).date(), end.tz_convert(NY).date())
            idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize(NY) for d in days]).tz_convert("UTC")
            idx = idx[(idx >= start) & (idx < end)]
            px = _px(idx + pd.Timedelta(hours=16)) + 0.07
        else:
            idx = pd.date_range(start.floor("min"), end, freq="min", inclusive="left")
            ny = idx.tz_convert(NY)
            idx = idx[(ny.dayofweek < 5) & (ny.hour >= 4) & (ny.hour < 20)]
            px = _px(idx)
        df = pd.DataFrame({"open": px - 0.02, "high": px + 0.11, "low": px - 0.13, "close": px, "volume": 500.0,
                           "trade_count": 5.0, "vwap": px},
                          index=pd.MultiIndex.from_arrays([[req.symbol_or_symbols[0]] * len(idx), idx],
                                                          names=["symbol", "timestamp"]))
        return SimpleNamespace(df=df)


class FakeCalendar:
    def get_calendar(self, req):
        return [SimpleNamespace(date=d.date(), open=pd.Timestamp(f"{d.date()} 09:30").to_pydatetime(),
                                close=pd.Timestamp(f"{d.date()} 16:00").to_pydatetime())
                for d in pd.bdate_range(req.start, req.end)]


def _same_ctx(a, b):
    for f in dataclasses.fields(a):
        x, y = getattr(a, f.name), getattr(b, f.name)
        if isinstance(x, np.ndarray) or isinstance(y, np.ndarray):
            np.testing.assert_allclose(x, y, equal_nan=True)
        elif isinstance(x, float) or isinstance(y, float):
            assert x == pytest.approx(y), f.name
        else:
            assert x == y, f.name


def test_live_context_equals_the_backtest_context_on_the_same_bars(tmp_path, monkeypatch):
    def no_keys(*a, **k):
        raise AssertionError("build_context must use the clients it is given, never data.keys()")

    monkeypatch.setattr(dt, "keys", no_keys)
    monkeypatch.setattr(dt, "clients", no_keys)
    d = date(2026, 9, 15)
    live_dir, bt_dir = tmp_path / "live", tmp_path / "bt"
    ctx, row, prior = M.build_context("SPY", d, live_dir, FakeSIP(), FakeCalendar(),
                                      now=ts("09:00", d), log=lambda s: None)
    assert row.date == d and row.open == ts("09:30", d) and row.close == ts("16:00", d)
    assert prior and prior[-1].date == date(2026, 9, 14) and all(p.date < d for p in prior)
    # the backtest's way: cache through today's close, split into days, contexts over all of them
    dt.download(["SPY"], d, d, bt_dir, client=FakeSIP(), trading_client=FakeCalendar(),
                now=ts("20:00", d).tz_convert("UTC"), log=lambda s: None)
    cal = dt.load_calendar(bt_dir)
    s0 = d - timedelta(days=dt.WARMUP_DAYS)
    days = bt.to_days(dt.load_bars("SPY", s0, d, bt_dir), cal, dt.load_official_closes("SPY", s0, d, bt_dir))
    assert days[-1].date == d and days[-1].complete
    expected = bt.contexts(days, cal)[-1]
    _same_ctx(ctx, expected)
    assert ctx.prev_close is not None and ctx.sigma is not None and ctx.daily_vol is not None


def test_build_context_refuses_without_explicit_clients_and_on_a_holiday(tmp_path):
    with pytest.raises(ValueError):
        M.build_context("SPY", D, tmp_path, None, None)
    with pytest.raises(ValueError, match="not a trading day"):
        M.build_context("SPY", date(2026, 10, 3), tmp_path, FakeSIP(), FakeCalendar(), log=lambda s: None)


# ============================================================================================ startup guards
def test_mt_g27_deploy_in_market_hours_with_changed_code_blocks_entries():
    first = {"package_hash": "a" * 64}
    assert RUN.deploy_reasons(ts("10:00"), first, "b" * 64) == [Reason.DEPLOY_IN_MARKET_HOURS]
    assert RUN.deploy_reasons(ts("09:00"), first, "b" * 64) == [Reason.DEPLOY_IN_MARKET_HOURS]
    assert RUN.deploy_reasons(ts("10:00"), first, "a" * 64) == []       # a plain restart of the same code
    assert RUN.deploy_reasons(ts("08:59"), first, "b" * 64) == []       # before 09:00: deploys allowed
    assert RUN.deploy_reasons(ts("16:15"), first, "b" * 64) == []
    assert RUN.deploy_reasons(ts("10:00"), None, "b" * 64) == []        # the session's first start pins the hash


def test_mt_g40_e0_is_read_once_per_session_and_kept_on_restart(tmp_path):
    acct = AccountView("PA123GWRL", "ACTIVE", 10_100.0, 10_000.0, 9_000.0, 20_000.0, 9_000.0, False, False, "x")
    info, created = RUN.session_info(tmp_path, D, session(), "h1", ts("09:10"), Mode.DRY, lambda: acct)
    assert created and info["e0"] == 10_000.0 and info["cash_prev_close"] == 9_000.0
    assert info["package_hash"] == "h1" and info["open"] == ts("09:30").isoformat()
    moved = dataclasses.replace(acct, last_equity=12_345.0)
    info2, created2 = RUN.session_info(tmp_path, D, session(), "h1", ts("11:00"), Mode.DRY, lambda: moved)
    assert not created2 and info2["e0"] == 10_000.0 and len(info2["starts"]) == 2
    assert RUN.deploy_reasons(ts("11:00"), info2, "h2") == [Reason.DEPLOY_IN_MARKET_HOURS]


def test_mt_g18_weekly_stop_base_is_the_weeks_first_session_e0(tmp_path):
    thu = D                                                            # 2026-10-01 is a Thursday
    assert RUN.week_e0(tmp_path, thu, 9_000.0) == 9_000.0             # no earlier session this week
    S.write_session(tmp_path, date(2026, 9, 29), {"e0": 10_000.0})     # Tuesday (Monday did not run)
    S.write_session(tmp_path, date(2026, 9, 30), {"e0": 9_500.0})
    S.write_session(tmp_path, date(2026, 9, 25), {"e0": 12_000.0})     # last week: ignored
    assert RUN.week_e0(tmp_path, thu, 9_000.0) == 10_000.0


def test_mt_g41_risk_hash_mismatch_disables_entries(tmp_path):
    j = J.MemoryJournal(Mode.DRY, lambda: ts("09:00"))
    assert RUN.risk_hash_reasons(tmp_path, {"SCALP_RISK_HASH": C.risk_hash()}, j) == []
    flags = RUN.risk_hash_reasons(tmp_path, {"SCALP_RISK_HASH": "0" * 64}, j)
    assert flags == [Reason.RISK_HASH_MISMATCH] and j.of("risk_hash_mismatch")
    reg = C.load_registry().get("NOISE_MOM_SPY", "SPY")
    t = ts("11:00:01")
    ec = R.EntryContext(now=t, candidate=Candidate(reg.setup_id, 1, "SPY", "enter", 1, ts("10:59")), reg=reg,
                        counters=DayCounters(D, 100_000.0, cash_prev_close=100_000.0), session=session(),
                        events=DayEvents(known=True), quote=Quote("SPY", 650.0, 650.01, 1, 1, t, t, Feed.IEX),
                        last_trade=LastTrade("SPY", 650.0, 1, t, Feed.IEX),
                        recent_bars=_bars(["10:55", "10:56", "10:57", "10:58", "10:59"]), last_data_ok=t,
                        clock_offset_ms=10.0, halted=False, prior_close=648.0, slot_state=SlotState.FLAT,
                        open_parents=0, open_position=False, settled_cash=100_000.0,
                        broker_nonmarginable_bp=100_000.0, planned_notional=650.03)
    assert R.entry_reasons(ec) == []
    assert Reason.RISK_HASH_MISMATCH in R.entry_reasons(dataclasses.replace(ec, flags=frozenset(flags)))


def test_mt_g41_unset_risk_hash_is_pinned_and_a_later_change_is_caught(tmp_path):
    j = J.MemoryJournal(Mode.DRY, lambda: ts("09:00"))
    assert RUN.risk_hash_reasons(tmp_path, {}, j) == []
    assert (tmp_path / "risk_hash.pin").read_text().strip() == C.risk_hash() and j.of("RISK_HASH_UNPINNED")
    (tmp_path / "risk_hash.pin").write_text("f" * 64)
    assert RUN.risk_hash_reasons(tmp_path, {}, j) == [Reason.RISK_HASH_MISMATCH]


def test_mt_g10_a_changed_setup_runs_shadow_only(monkeypatch):
    reg = C.load_registry()
    bad = dataclasses.replace(reg.setups[0], code_hash="0" * 64)
    reg = C.Registry((bad,) + reg.setups[1:], reg.account_last4, reg.test_start, reg.path)
    j = J.MemoryJournal(Mode.DRY, lambda: ts("09:00"))
    out, mism = RUN.registry_for_run(reg, j)
    assert mism == [f"{bad.setup_id}/{bad.symbol}"]
    assert out.get(bad.setup_id, bad.symbol).lane is Lane.SHADOW
    assert all(r.lane is Lane.EXPLORATORY for r in out.setups[1:])
    assert j.of("code_hash_mismatch")[0]["reason"] == "CODE_HASH_MISMATCH"


class FlagEngine:
    def __init__(self, *a, flags=None, **k):
        self.args, self.kw, self.flags = a, k, set(flags or ())


class NoFlagEngine:
    def __init__(self, *a, **k):
        self.flags = set()                       # takes the keyword but drops the flags


def test_startup_flags_reach_the_engine_or_the_run_is_refused():
    args = (None, None, None, None, session(), DayEvents(True), {}, Mode.DRY, lambda: ts("09:00"))
    eng = RUN.make_engine(*args, flags=[Reason.RISK_HASH_MISMATCH], engine_cls=FlagEngine)
    assert eng.flags == {Reason.RISK_HASH_MISMATCH}
    with pytest.raises(RuntimeError):
        RUN.make_engine(*args, flags=[Reason.SELFTEST_FAILED], engine_cls=NoFlagEngine)


# ============================================================================================ self-test (MT-G27)
class KillEngine:
    """Minimal kill switch: cancel everything, then sell each position at the bid once the cancels are done."""

    def __init__(self, broker, journal, registry, counters, session, events, ctx, mode, clock, state_dir=None,
                 works=True, **_):
        self.b, self.clock, self.kill, self.works, self.state_dir = broker, clock, None, works, state_dir
        self.flags = set()

    def request_kill(self, reason):
        self.kill = reason

    def tick(self, snap):
        if not (self.kill and self.works):
            return []
        opened = self.b.open_orders()
        for o in opened:
            if o.side == "buy" or o.order_type != "limit" or o.client_order_id.startswith("SCALP-") is False:
                self.b.cancel(o.id)
        if not self.b.open_orders():
            for p in self.b.positions():
                if p.qty > 0:
                    self.b.submit(O.exit_limit(p.symbol, int(p.qty), snap.quotes.get(p.symbol), None, 0.002,
                                               Kind.EXIT, setup_id=None, version=0, session_date=snap.now.date(),
                                               bar_start=snap.now, leg="K", attempt=0, reason="KILLED"))
        return []

    def status(self):
        return {"position": bool(self.b.positions()), "open_orders": [o.id for o in self.b.open_orders()]}


def test_mt_g27_pre_open_self_test_passes_with_a_working_kill_switch_and_fails_without(tmp_path):
    from lab.scalp.live.broker import SimBroker
    reg = C.load_registry()
    ok, detail = RUN.self_test(ts("09:10"), reg, tmp_path, engine_cls=KillEngine, sim_broker_cls=SimBroker)
    assert ok, detail

    class Broken(KillEngine):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.works = False

    ok, detail = RUN.self_test(ts("09:10"), reg, tmp_path, engine_cls=Broken, sim_broker_cls=SimBroker)
    assert not ok and "10 simulated seconds" in detail
    assert not (tmp_path / "HALT").exists()                          # never the real state directory


# ============================================================================================ runner loop
class TickEngine(KillEngine):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.snaps, self.flatten = [], None

    def tick(self, snap):
        self.snaps.append(snap)
        return super().tick(snap)

    def request_flatten(self, why):
        self.flatten = why
        self.kill = why


def test_runner_ticks_heartbeats_and_feeds_the_sim_broker_before_the_engine(tmp_path):
    from lab.scalp.live.broker import SimBroker
    bars = {"SPY": _bars(["09:30", "09:31", "09:32"])}
    clock = M.SimClock(ts("09:30"))
    market = M.ReplayMarket(D, bars, M.bar_quote_fn(bars), clock, open_ts=ts("09:30"), close_ts=ts("09:33"))
    sim = SimBroker(clock, fill_mode="bar")
    eng = TickEngine(sim, None, None, None, None, None, {}, Mode.REPLAY, clock)
    rec = M.Recorder(tmp_path / "r.jsonl")
    run = RUN.Runner(eng, market, J.MemoryJournal(Mode.REPLAY, clock), Mode.REPLAY, clock, tmp_path,
                     SessionTimes.from_calendar(D, ts("09:30"), ts("09:33")), sim_broker=sim, recorder=rec,
                     live=False)
    out = run.loop()
    rec.close()
    assert out["ticks"] == 9 and len(eng.snaps) == 9
    assert sim.last_bar["SPY"] == ts("09:32")                          # bars reached the sim broker
    hb = S.read_heartbeat(tmp_path)
    assert hb["mode"] == "replay" and hb["ts"] == eng.snaps[-1].now.isoformat() and "open_orders" in hb["status"]
    assert len(list(M.read_recording(tmp_path / "r.jsonl"))) == 9


def test_sigterm_asks_the_engine_to_exit_everything_then_stops(tmp_path):
    from lab.scalp.live.broker import SimBroker
    bars = {"SPY": _bars([f"10:{m:02d}" for m in range(0, 30)])}
    clock = M.SimClock(ts("10:00"))
    market = M.ReplayMarket(D, bars, M.bar_quote_fn(bars), clock, open_ts=ts("10:00"), close_ts=ts("10:30"))
    sim = SimBroker(clock, fill_mode="quote", positions=(PositionView("SPY", 1, 650.0),))
    eng = TickEngine(sim, None, None, None, None, None, {}, Mode.REPLAY, clock)
    j = J.MemoryJournal(Mode.REPLAY, clock)
    run = RUN.Runner(eng, market, j, Mode.REPLAY, clock, tmp_path, session(), sim_broker=sim, live=False)
    run.step()
    run.request_stop("SIGTERM")
    out = run.loop()
    assert eng.flatten == "SIGTERM" and out["stop"] == "SIGTERM"
    assert sim.positions() == [] and out["ticks"] < 10                 # flat, then stopped (not at the close)
    assert j.of("stop_requested")


def test_replay_runs_the_engine_on_a_simulated_clock_and_sends_nothing(tmp_path):
    bars = {"SPY": _bars(["09:30", "09:31"]), "QQQ": _bars(["09:30", "09:31"], "QQQ", 560.0)}
    st = SessionTimes.from_calendar(D, ts("09:30"), ts("09:32"))
    clock = M.SimClock(ts("09:30"))
    market = M.ReplayMarket(D, bars, M.bar_quote_fn(bars), clock, open_ts=st.open, close_ts=st.close)
    j = J.MemoryJournal(Mode.REPLAY, clock)
    out = RUN.replay(D, e0=10_000.0, market=market, journal=j, engine_cls=TickEngine, ctx_by_symbol={},
                     session=st, state_dir=tmp_path, out=lambda s: None)
    assert out["ticks"] == 6 and j.of("replay_start")[0]["e0"] == 10_000.0
    assert "EXPLORATORY" in out["summary"]
    assert not (tmp_path / "heartbeat.json").exists()                # a replay is not a running bot


# ============================================================================================ watchdog (MT-G39)
class FakeBroker:
    """Order book look-alike: sells fill at once at their limit; cancels are immediate."""

    def __init__(self, positions=(), orders=()):
        self.pos = {p.symbol: p for p in positions}
        self.orders = {o.id: o for o in orders}
        self.submitted, self.cancelled = [], []

    def positions(self):
        return [p for p in self.pos.values() if p.qty != 0]

    def open_orders(self):
        return [o for o in self.orders.values() if o.open]

    def cancel(self, oid):
        self.cancelled.append(oid)
        self.orders[oid] = dataclasses.replace(self.orders[oid], status="canceled")

    def submit(self, spec):
        assert spec.order_class == "simple" and spec.limit_price > 0 and spec.side == "sell"
        self.submitted.append(spec)
        p = self.pos[spec.symbol]
        self.pos[spec.symbol] = dataclasses.replace(p, qty=p.qty - spec.qty)
        v = OrderView(f"o{len(self.orders)}", spec.client_order_id, spec.symbol, "sell", spec.qty, spec.qty,
                      spec.limit_price, "filled", "limit", spec.limit_price)
        self.orders[v.id] = v
        return v

    def get_order(self, oid):
        return self.orders[oid]


def _book():
    stop = OrderView("leg-stop", "x-stop", "SPY", "sell", 1, 0, None, "held", "stop_limit", 645.0, 646.0)
    tp = OrderView("leg-tp", "x-tp", "SPY", "sell", 1, 0, None, "new", "limit", 660.0)
    return FakeBroker([PositionView("SPY", 1, 650.0)], [stop, tp])


def _quote(sym):
    t = ts("11:00")
    return Quote(sym, 649.0, 649.01, 1, 1, t, t, Feed.IEX)


def _wd(tmp_path, now, broker, mode=Mode.PAPER):
    clock = Clock(ts(now))
    j = J.MemoryJournal(mode, clock)
    return W.Watchdog(mode, tmp_path, clock, j, broker=broker, quote_fn=_quote, sleep=lambda s: None,
                      session=session()), j


def test_mt_g39_watchdog_flattens_when_the_heartbeat_is_31_seconds_old(tmp_path):
    S.write_heartbeat(tmp_path, ts("10:59:29"), "paper", {"position": True})
    b = _book()
    wd, j = _wd(tmp_path, "11:00:00", b)
    out = wd.check()
    assert out["action"] == "flatten" and out["reasons"] == ["HEARTBEAT_STALE"] and out["flat"]
    assert set(b.cancelled) == {"leg-stop", "leg-tp"} and b.positions() == []
    spec = b.submitted[0]
    assert spec.kind is Kind.EXIT and spec.limit_price == O.round_up_cent(649.0 * (1 - C.KILL_COLLARS[0]))
    assert O.parse_client_id(spec.client_order_id)["leg"] == "W"
    assert S.read_flag(tmp_path, S.HALT)["by"] == "watchdog"
    assert j.of("watchdog_flatten") and (tmp_path / "alerts.log").exists()


def test_mt_g39_watchdog_flattens_an_open_position_at_1557_even_with_a_fresh_heartbeat(tmp_path):
    S.write_heartbeat(tmp_path, ts("15:56:58"), "paper", {"position": True})
    b = _book()
    wd, _ = _wd(tmp_path, "15:57:00", b)
    out = wd.check()
    assert out["action"] == "flatten" and out["reasons"] == ["OPEN_AT_KILL_TIME"] and b.positions() == []


def test_mt_g39_watchdog_does_nothing_while_the_heartbeat_is_fresh(tmp_path):
    S.write_heartbeat(tmp_path, ts("10:59:45"), "paper", {"position": True})
    b = _book()
    wd, _ = _wd(tmp_path, "11:00:00", b)
    assert wd.check()["action"] == "none"
    wd.clock.set(ts("15:56:59"))
    S.write_heartbeat(tmp_path, ts("15:56:50"), "paper", {"position": True})
    assert wd.check()["action"] == "none"
    wd.clock.set(ts("17:00:00"))
    assert wd.check()["action"] == "idle"                                # outside market hours
    assert b.submitted == [] and b.cancelled == [] and not (tmp_path / "HALT").exists()


def test_mt_g39_a_clean_stop_with_a_flat_account_is_left_alone_but_a_position_is_not(tmp_path):
    S.write_heartbeat(tmp_path, ts("10:00:00"), "paper", {"position": False, "stopped": "SIGTERM"})
    flat = FakeBroker()
    wd, _ = _wd(tmp_path, "11:00:00", flat)
    assert wd.check()["action"] == "none" and not (tmp_path / "HALT").exists()
    b = _book()
    wd, _ = _wd(tmp_path, "11:00:00", b)
    assert wd.check()["action"] == "flatten" and b.positions() == []


def test_mt_g39_dry_watchdog_only_journals_would_flatten(tmp_path):
    S.write_heartbeat(tmp_path, ts("10:59:00"), "dry", {"position": True})
    wd, j = _wd(tmp_path, "11:00:00", None, Mode.DRY)
    assert wd.check()["action"] == "would_flatten"
    assert j.of("would_flatten") and not (tmp_path / "HALT").exists()
    with pytest.raises(ValueError):
        W.Watchdog(Mode.PAPER, tmp_path, Clock(ts("11:00")), j, broker=None)


# ============================================================================================ kill / reset-halt (MT-G27, G41)
def test_mt_g27_kill_writes_kill_and_flattens_itself_when_no_bot_is_running(tmp_path):
    b = _book()
    msgs = []
    rc = cli.cmd_kill(Namespace(reason="owner test"), state_dir=tmp_path, broker_factory=lambda: b,
                      quote_fn=_quote, clock=lambda: ts("11:00"), journal=J.MemoryJournal(Mode.PAPER),
                      out=msgs.append)
    assert rc == 0
    assert S.read_flag(tmp_path, S.KILL)["reason"] == "owner test"
    assert b.positions() == [] and not b.open_orders()
    assert O.parse_client_id(b.submitted[0].client_order_id)["leg"] == "K"
    assert S.read_flag(tmp_path, S.HALT)["reason"] == "kill: owner test"


def test_mt_g27_kill_leaves_the_work_to_a_running_bot(tmp_path):
    S.write_heartbeat(tmp_path, ts("10:59:55"), "paper", {"position": True})
    b = _book()
    made = []
    rc = cli.cmd_kill(Namespace(reason="stop now"), state_dir=tmp_path,
                      broker_factory=lambda: made.append(1) or b, quote_fn=_quote, clock=lambda: ts("11:00"),
                      journal=J.MemoryJournal(Mode.PAPER), out=lambda s: None)
    assert rc == 0 and S.read_flag(tmp_path, S.KILL) is not None
    assert made == [] and b.submitted == [] and not (tmp_path / "HALT").exists()


def test_mt_g41_reset_halt_appends_to_the_changes_log(tmp_path):
    S.write_flag(tmp_path, S.HALT, "watchdog: HEARTBEAT_STALE", ts("11:00"), "watchdog")
    S.write_flag(tmp_path, S.KILL, "owner", ts("11:00"), "kill command")
    cli.cmd_reset_halt(Namespace(reason="checked the account, all flat"), state_dir=tmp_path,
                       clock=lambda: ts("11:30"), out=lambda s: None)
    assert not (tmp_path / "HALT").exists() and not (tmp_path / "KILL").exists()
    cli.cmd_reset_halt(Namespace(reason="second"), state_dir=tmp_path, clock=lambda: ts("11:31"),
                       out=lambda s: None)
    log = S.read_changes(tmp_path)
    assert [x["reason"] for x in log] == ["checked the account, all flat", "second"]
    assert log[0]["action"] == "reset-halt" and log[0]["cleared"]["halt"]["reason"] == "watchdog: HEARTBEAT_STALE"
    with pytest.raises(ValueError):
        S.reset_halt(tmp_path, "  ", ts("11:32"))


# ============================================================================================ CLI
def test_mt_g36_run_paper_without_confirm_paper_refuses_before_touching_anything(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("no client may be built")

    monkeypatch.setattr(RUN, "scalp_clients", boom)
    assert cli.main(["run", "--mode", "paper"]) == 2
    assert "--confirm-paper" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(["run", "--mode", "live"])


class FakeTC:
    def __init__(self, number, base="https://paper-api.alpaca.markets"):
        self._base_url, self.number = base, number

    def get_account(self):
        return SimpleNamespace(account_number=self.number, status=SimpleNamespace(value="ACTIVE"), equity="10000",
                               last_equity="10000", cash="10000", buying_power="20000",
                               non_marginable_buying_power="10000", options_trading_level=0,
                               trading_blocked=False, shorting_enabled=False, pattern_day_trader=False)


def test_mt_g36_check_account_proves_paper_and_not_rules_printing_only_last_4(tmp_path):
    env = {"ALPACA_SCALP_KEY": "sk", "ALPACA_SCALP_SECRET": "ss", "ALPACA_RULES_KEY": "rk",
           "ALPACA_RULES_SECRET": "rs"}
    nums = {"sk": "PA3SCALPGWRL", "rk": "PA9RULESXXXX"}
    msgs = []
    rc = cli.check_account(env, lambda k, s: FakeTC(nums[k]), tmp_path, msgs.append)
    text = "\n".join(msgs)
    assert rc == 0, text
    assert "...GWRL" in text and "PA3SCALPGWRL" not in text and "PA9RULESXXXX" not in text
    assert "sk" not in re.findall(r"\b\w+\b", text) and "ss" not in re.findall(r"\b\w+\b", text)
    assert (tmp_path / "account.pin").read_text().strip() == "PA3SCALPGWRL"
    assert "below about $6,600" not in text


@pytest.mark.parametrize("case", ["same_as_rules", "live_url", "no_keys", "url_override"])
def test_mt_g36_check_account_fails_loudly(tmp_path, case):
    env = {"ALPACA_SCALP_KEY": "sk", "ALPACA_SCALP_SECRET": "ss", "ALPACA_RULES_KEY": "rk",
           "ALPACA_RULES_SECRET": "rs"}
    base = "https://paper-api.alpaca.markets"
    nums = {"sk": "PA3SCALPGWRL", "rk": "PA9RULESXXXX"}
    if case == "same_as_rules":
        nums["rk"] = nums["sk"]
    if case == "live_url":
        base = "https://api.alpaca.markets"
    if case == "no_keys":
        env.pop("ALPACA_SCALP_SECRET")
    if case == "url_override":
        env["APCA_API_BASE_URL"] = "https://api.alpaca.markets"
    msgs = []
    assert cli.check_account(env, lambda k, s: FakeTC(nums[k], base), tmp_path, msgs.append) == 1
    assert any("FAIL" in m for m in msgs) and not (tmp_path / "account.pin").exists()


# ============================================================================================ report
def _closed(i, honest, how="target", qty=1, day="2026-10-01"):
    """Journal lines in the engine's format: a buy fill, then the trade_closed line."""
    labels = {"setup_id": "ORB5_QQQ", "version": 1, "lane": "EXPLORATORY", "feed": "IEX"}
    return [{"kind": "fill", "ts": f"{day}T09:35:0{i}-04:00", "symbol": "QQQ", "side": "buy", "qty": qty,
             "price": 560.0, "slippage": {"cents": 1.0, "bps": 0.18, "decision_mid": 559.995}, **labels},
            {"kind": "trade_closed", "ts": f"{day}T10:0{i}:00-04:00", "symbol": "QQQ", "how": how, "qty": qty,
             "paper_pnl": honest + 0.03, "honest_pnl": honest, "risk_usd": 1.2, "r": honest / 1.2, **labels}]


def _submit(qty, e0=100_000.0):
    return {"kind": "would_submit", "ts": "2026-10-01T09:35:01-04:00", "cid": "SCALP-ORB5Q-261001-0934-E0-abcdef",
            "symbol": "QQQ", "qty": qty, "limit": 560.3, "stop": 559.5, "stop_limit": 559.1, "target": 568.3,
            "numbers": {"e0": e0, "limit": 560.3, "stop": 559.5, "stop_limit": 559.1, "lane": "EXPLORATORY"},
            "setup_id": "ORB5_QQQ", "version": 1, "lane": "EXPLORATORY", "feed": "IEX"}


def test_mt_g11_report_labels_insufficient_sample_and_exploratory_on_every_setup_line():
    lines = (_closed(1, 2.0) + _closed(2, -1.0, "stop") + _closed(3, 0.5, "MANUAL")
             + [{"kind": "decision", "ts": "2026-10-01T10:00:01-04:00", "setup_id": "NOISE_MOM_SPY",
                 "lane": "EXPLORATORY", "accepted": False, "reasons": ["SPREAD_TOO_WIDE", "DATA_STALE"]},
                _submit(1), _submit(2)])
    changes = [{"ts": "2026-10-01T08:00:00-04:00", "action": "reset-halt", "reason": "checked"}]
    text = REP.build_report(lines, C.load_registry(), changes=changes)
    assert "INSUFFICIENT SAMPLE" in text and "EXPLORATORY" in text.splitlines()[1]
    orb = [x for x in text.splitlines() if "ORB5_QQQ" in x and not x.startswith("    ")]
    assert len(orb) >= 6 and all(x.startswith("[EXPLORATORY] ORB5_QQQ") for x in orb)
    assert "3 closed trades over 1 sessions -> INSUFFICIENT SAMPLE" in text
    assert "median slippage 1.00 cents / 0.18 bps over 3 fills [FEED=IEX]" in text
    assert text.index("Changes log") < text.index("ORB5_QQQ")          # MT-G41: changes first
    assert "inactive (no backtest baseline" in text and "FEED_MISMATCH" in text
    assert "exits that were not stop/target/time/flatten/daily stop/kill: 1 (must be 0)  <- BUG" in text
    assert "qty differs from the sizing function: 1 (must be 0)  <- BUG" in text and "qty 2 but sizing gives 1" in text
    assert "SPREAD_TOO_WIDE: 1" in text and "Would have sent (dry run / replay): 2 orders" in text
    assert "09:30    3 trades" in text                                  # the 15-minute entry bucket


def test_mt_g4_remark_flags_a_fill_better_than_the_sip_quote():
    lines = [{"kind": "fill", "ts": "2026-10-01T10:00:00-04:00", "symbol": "SPY", "side": "buy", "price": 649.99}]
    qf = lambda s, t: Quote(s, 650.0, 650.01, 1, 1, t, t, Feed.SIP)   # noqa: E731
    out = REP.remark(lines, qf, ts("12:00"))
    assert "optimistic" not in out[1]
    lines[0]["price"] = 650.05
    assert "optimistic paper fill" in REP.remark(lines, qf, ts("12:00"))[1]
    assert "too recent" in REP.remark(lines, qf, ts("10:10"))[1]


# ============================================================================================ package hygiene
RUNTIME = ("market.py", "runner.py", "watchdog.py", "report.py", "__main__.py", "state.py")


def test_package_never_imports_anthropic_trader_or_the_options_lab():
    for py in LIVE.glob("*.py"):
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [("." * node.level) + (node.module or "")]
            for n in names:
                assert not re.match(r"^(anthropic|trader|lab\.options_lab|\.\.options_lab|\.\.\.trader)", n), \
                    (py.name, n)
                assert "options_lab" not in n and not n.lstrip(".").startswith("trader"), (py.name, n)


def _docstrings(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                out.add(id(first.value))
    return out


def test_mt_g36_rules_keys_are_read_only_inside_check_account():
    found = []
    for py in LIVE.glob("*.py"):
        tree = ast.parse(py.read_text())
        docs = _docstrings(tree)
        parents = {}
        for node in ast.walk(tree):
            for ch in ast.iter_child_nodes(node):
                parents[ch] = node
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "ALPACA_RULES" in node.value \
                    and id(node) not in docs:
                p = node
                while p in parents and not isinstance(p, ast.FunctionDef):
                    p = parents[p]
                found.append((py.name, getattr(p, "name", "<module>")))
    assert found and set(found) == {("__main__.py", "check_account")}


def test_runtime_modules_build_orders_only_through_the_order_builder():
    for name in RUNTIME:
        src = (LIVE / name).read_text()
        assert "OrderSpec(" not in src, name
        assert not re.search(r"Market(Order)?Request|StopOrderRequest|StopLimitOrderRequest|LimitOrderRequest",
                             src), name
        assert ".submit_order(" not in src and "cancel_order" not in src, name


# ============================================================================================ with the real engine
def test_mt_g27_pre_open_self_test_with_the_real_engine_and_sim_broker(tmp_path):
    ok, detail = RUN.self_test(ts("09:10"), C.load_registry(), tmp_path)
    assert ok, detail
    assert not (tmp_path / "HALT").exists() and (tmp_path / "selftest" / "HALT-dry").exists()   # DRY names


QUIET = date(2026, 10, 6)       # a Tuesday with no scheduled release in the event calendar


def _session_bars(sym, prices, d=QUIET):
    out, prev = [], prices[0]
    for k, px in enumerate(prices):
        t = ts("09:30", d) + pd.Timedelta(minutes=k)
        out.append(Bar(sym, t, prev, max(prev, px) + 0.02, min(prev, px) - 0.02, px, 5_000.0, Feed.SIP))
        prev = px
    return out


def test_replay_with_the_real_engine_shows_what_it_would_have_done_and_why(tmp_path):
    from lab.scalp.signals import Ctx
    n = 390
    qqq = [560.0 + 0.1 * min(k, 5) for k in range(n)]                   # up in the first 5 minutes, then flat
    spy = [650.0 + 0.05 * min(k, 30) for k in range(n)]                 # up in the first half hour
    bars = {"QQQ": _session_bars("QQQ", qqq), "SPY": _session_bars("SPY", spy)}
    st = SessionTimes.from_calendar(QUIET, ts("09:30", QUIET), ts("16:00", QUIET))
    clock = M.SimClock(st.open)
    market = M.ReplayMarket(QUIET, bars, M.bar_quote_fn(bars), clock, open_ts=st.open, close_ts=st.close)
    j = J.MemoryJournal(Mode.REPLAY, clock)
    ctx = {"QQQ": Ctx(prev_close=559.0), "SPY": Ctx(prev_close=649.0)}
    out = RUN.replay(QUIET, e0=100_000.0, market=market, journal=j, ctx_by_symbol=ctx, session=st,
                     state_dir=tmp_path, out=lambda s: None)
    dec = {(x["setup_id"], x["ts"][11:19]): x for x in j.of("decision")}
    orb = dec[("ORB5_QQQ", "09:35:01")]
    assert orb["accepted"] and orb["lane"] == "EXPLORATORY"
    ws = j.of("would_submit")
    assert len(ws) == 1 and ws[0]["symbol"] == "QQQ" and ws[0]["qty"] == 1
    l30 = dec[("LAST30_MOM_SPY", "15:30:01")]
    assert not l30["accepted"] and "POSITION_OPEN" in l30["reasons"]   # one slot for the whole bot (MT-G2)
    closed = j.of("trade_closed")
    assert len(closed) == 1 and closed[0]["how"] == "TIME_EXIT" and closed[0]["ts"][11:16] == "15:50"
    assert not j.of("submit")                                           # nothing sent anywhere
    assert "would buy" not in out["summary"] and "ORB5_QQQ" in out["summary"]
    assert "refused LAST30_MOM_SPY SPY buy at 15:30:01: " in out["summary"]
    text = REP.build_report(j.lines, C.load_registry())
    assert "exits that were not stop/target/time/flatten/daily stop/kill: 0 (must be 0)\n" in text
    assert "qty differs from the sizing function: 0 (must be 0)\n" in text
    assert "1 closed trades over 1 sessions -> INSUFFICIENT SAMPLE" in text


class FakeTime:
    """Stands in for the runner's `time` module: sleeping moves the fake clock."""

    def __init__(self, clock):
        self.clock = clock

    def sleep(self, s):
        self.clock.set(self.clock() + pd.Timedelta(seconds=max(s, 0.25)))

    def monotonic(self):
        return self.clock().timestamp()


def test_run_dry_wires_market_engine_sim_broker_and_heartbeat_offline(tmp_path, monkeypatch):
    from lab.scalp.live import broker as B
    from lab.scalp.signals import Ctx
    clock = Clock(ts("15:58:30", QUIET))
    ft = FakeTime(clock)
    data = FakeIEX(clock)

    class Trading:
        def get_clock(self):
            return SimpleNamespace(timestamp=clock().tz_convert("UTC").to_pydatetime())

    class Reader:
        def __init__(self, mode=Mode.DRY, **k):
            assert Mode(mode) is Mode.DRY                        # dry mode never builds a writable broker

        def account(self):
            return AccountView("PA0TESTGWRL", "ACTIVE", 100_050.0, 100_000.0, 100_000.0, 200_000.0, 100_000.0,
                               False, False, "https://paper-api.alpaca.markets")

    monkeypatch.setattr(RUN, "scalp_clients", lambda env=None: (data, Trading()))
    monkeypatch.setattr(B, "AlpacaBroker", Reader)
    monkeypatch.setattr(M, "build_context", lambda sym, d, *a, **k: (
        Ctx(prev_close=649.0), M.CalendarRow(d, ts("09:30", d), ts("16:00", d)), []))
    monkeypatch.setattr(RUN, "now_ny", clock)
    monkeypatch.setattr(RUN, "time", ft)
    msgs = []
    rc = RUN.run("dry", no_watchdog=True, state_dir=tmp_path, env={}, out=msgs.append)
    assert rc == 0, msgs
    lines = J.read_journal(J.journal_path(tmp_path, QUIET, Mode.DRY))
    kinds = [x["kind"] for x in lines]
    assert kinds[0] == "start" and "startup" in kinds and "end" in kinds
    assert next(x for x in lines if x["kind"] == "self_test")["passed"]
    assert next(x for x in lines if x["kind"] == "startup")["e0"] == 100_000.0
    assert S.read_session(tmp_path, QUIET)["e0"] == 100_000.0
    hb = S.read_heartbeat(tmp_path)
    assert hb["mode"] == "dry" and hb["status"]["stopped"] == "session over"
    assert (tmp_path / "recordings" / f"{QUIET}-dry.jsonl").exists()
    assert "DRY run" in msgs[0] and "Summary (dry)" in msgs[-1]
    assert (tmp_path / "risk_hash.pin").exists()
    assert {x["setup_id"] for x in lines if x["kind"] == "mt_g13_cusum_off"} == {r.setup_id for r in C.load_registry()}
    start = next(x for x in lines if x["kind"] == "startup")
    assert start["lanes"]["NOISE_MOM_SPY/SPY"] == "SHADOW" and start["test_start"] is None      # dry pins nothing
    assert "NOISE_MOM_SPY/SPY" in start["shadow_only"] and not (tmp_path / S.TEST_START_PIN).exists()


def test_sigterm_with_nothing_open_just_stops_without_a_kill(tmp_path):
    from lab.scalp.live.broker import SimBroker
    bars = {"SPY": _bars([f"10:{m:02d}" for m in range(0, 30)])}
    clock = M.SimClock(ts("10:00"))
    market = M.ReplayMarket(D, bars, M.bar_quote_fn(bars), clock, open_ts=ts("10:00"), close_ts=ts("10:30"))
    sim = SimBroker(clock, fill_mode="quote")
    eng = TickEngine(sim, None, None, None, None, None, {}, Mode.REPLAY, clock)
    run = RUN.Runner(eng, market, J.MemoryJournal(Mode.REPLAY, clock), Mode.REPLAY, clock, tmp_path, session(),
                     sim_broker=sim, live=False)
    run.step()
    run.request_stop("SIGTERM")
    assert eng.flatten is None and eng.kill is None
    assert run.loop()["ticks"] == 2


def test_mt_g27_kill_says_plainly_when_it_cannot_reach_the_account(tmp_path):
    from lab.scalp.live.model import PaperLockError

    def no_broker():
        raise PaperLockError("ALPACA_SCALP_KEY / ALPACA_SCALP_SECRET are not set")

    msgs = []
    rc = cli.cmd_kill(Namespace(reason="test"), state_dir=tmp_path, broker_factory=no_broker, quote_fn=None,
                      clock=lambda: ts("11:00"), journal=J.MemoryJournal(Mode.PAPER), out=msgs.append)
    assert rc == 1 and S.read_flag(tmp_path, S.KILL) is not None
    assert "could not be flattened" in msgs[-1]


def test_mt_g26_report_compares_the_broker_history_with_the_journal():
    cid = O.client_id("ORB5_QQQ", 1, D, ts("09:34"), "E", 0)
    xid = O.client_id("ORB5_QQQ", 1, D, ts("09:34"), "X", 0)
    orders = [OrderView("1", cid, "QQQ", "buy", 1, 1, 560.0, "filled", "limit"),
              OrderView("2", xid, "QQQ", "sell", 1, 1, 561.0, "filled", "limit"),
              OrderView("3", "manual-7", "SPY", "buy", 1, 0, None, "new", "limit")]
    out = "\n".join(REP.broker_block(orders, [{"kind": "submit"}]))
    assert "SCALP entry orders at the broker: 1 (1 with a fill); journal 'submit' lines: 1\n" in out
    assert "orders without a SCALP- id: 1" in out
    assert "DIFFERENT" in "\n".join(REP.broker_block(orders, []))
