"""End-to-end tests of the live paper minute trader (lab/scalp/live), with every real module wired together.

The pieces are tested apart in test_scalp_live_rules/engine/broker/runtime.py; here the REAL runner, market,
engine, guard and SimBroker run whole sessions together. All offline: synthetic bars, fake data clients, simulated
clocks, temporary state folders. No network, no keys, no order sent anywhere. Names say which rule each test proves.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from lab.scalp.live import config as C
from lab.scalp.live import journal as J
from lab.scalp.live import market as M
from lab.scalp.live import report as REP
from lab.scalp.live import runner as RUN
from lab.scalp.live import state as S
from lab.scalp.live import watchdog as W
from lab.scalp.live.broker import SimBroker
from lab.scalp.live.clock import SessionTimes
from lab.scalp.live.events import load_events_or_unknown
from lab.scalp.live.model import NY, Bar, DayCounters, Feed, Mode, PositionView, Reason
from lab.scalp.signals import Ctx

TRADING = Path(__file__).resolve().parents[1]
D = date(2026, 10, 8)          # a Thursday inside the committed event calendar with no scheduled event (Notes 1
                               # Patch C: on 1 Oct the 10:00 ISM release now refuses ORB5's 9:35 entry)
E0 = 100_000.0


def ts(hms: str, d: date = D) -> pd.Timestamp:
    return pd.Timestamp(f"{d} {hms}", tz=NY)


def session() -> SessionTimes:
    return SessionTimes.from_calendar(D, ts("09:30"), ts("16:00"))


def path_bars(sym: str, legs: list[tuple[str, str, float, float]], wick: float = 0.02) -> list[Bar]:
    """1-minute SIP bars moving in a straight line from p0 to p1 over each (start, end) leg, both minutes included."""
    out = []
    for a, b, p0, p1 in legs:
        s, e = ts(a), ts(b)
        n = int((e - s).total_seconds() // 60) + 1
        closes = np.linspace(p0, p1, n)
        opens = np.r_[p0, closes[:-1]]
        for k, (o, c) in enumerate(zip(opens, closes)):
            out.append(Bar(sym, s + pd.Timedelta(minutes=k), float(o), float(max(o, c) + wick),
                           float(min(o, c) - wick), float(c), 5_000.0, Feed.SIP))
    return out


def synthetic_day() -> dict[str, list[Bar]]:
    """QQQ: up in the first 5 minutes (ORB5 long at 9:35, stop 559.98 = the first candle's low), flat through the
    9:35 bar, then the 9:36 bar trades through the stop. SPY: up in the first half hour (LAST30 long at 15:30),
    inside the noise band at 10:00, below it at 10:30 (NOISE short: refused, no shorts), back inside the band from
    11:00, flat after 15:30 (far from the overlay stop and target, so LAST30 leaves at the 15:50 flatten)."""
    qqq = path_bars("QQQ", [("09:30", "09:34", 560.0, 561.0), ("09:35", "09:35", 561.0, 561.0)])
    qqq.append(Bar("QQQ", ts("09:36"), 560.9, 560.95, 559.6, 559.7, 9_000.0, Feed.SIP))
    qqq += path_bars("QQQ", [("09:37", "15:59", 559.7, 559.8)])
    spy = path_bars("SPY", [("09:30", "09:59", 650.0, 650.3), ("10:00", "10:29", 650.3, 649.2),
                            ("10:30", "10:59", 649.2, 649.9), ("11:00", "15:29", 649.9, 650.1),
                            ("15:30", "15:59", 650.1, 650.15)])
    return {"QQQ": qqq, "SPY": spy}


def ctxs() -> dict[str, Ctx]:
    """Yesterday's facts: SPY closed at 650.00 (noise band 649.35 - 650.65 with sigma 0.1%), QQQ at 559.00."""
    band = np.full(391, 0.001)
    return {"QQQ": Ctx(prev_close=559.0, sigma=band, daily_vol=0.01),
            "SPY": Ctx(prev_close=650.0, sigma=band, daily_vol=0.01)}


class RecordingSim(SimBroker):
    """The real SimBroker; remembers its instances so a test can look at every spec the replay sent to it."""
    made: list["RecordingSim"] = []

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        RecordingSim.made.append(self)


def _decisions(lines: list[dict]) -> list[tuple]:
    return [(x["setup_id"], x["bar_start"], x["action"], x["side"], x["accepted"], tuple(x["reasons"]))
            for x in lines if x["kind"] == "decision"]


# ============================================================================================ 1. full session replay
def test_mt_g20_g16_g2_full_synthetic_session_replay_through_the_runner(tmp_path):
    bars = synthetic_day()
    st = session()
    market = M.ReplayMarket(D, bars, M.bar_quote_fn(bars), M.SimClock(st.open), open_ts=st.open, close_ts=st.close)
    RecordingSim.made = []
    out = RUN.replay(D, e0=E0, market=market, ctx_by_symbol=ctxs(), session=st, state_dir=tmp_path,
                     sim_broker_cls=RecordingSim, out=lambda s: None)
    lines = J.read_journal(J.journal_path(tmp_path, D, Mode.REPLAY))
    assert lines[0]["kind"] == "replay_start" and lines[0]["events_known"] and lines[0]["fill_mode"] == "bar"

    # every candidate the engine returned is in the journal, with its lane, version and ALL its reasons
    dec = [x for x in lines if x["kind"] == "decision"]
    assert len(dec) == len(out["decisions_list"]) == 3
    for x, d in zip(dec, out["decisions_list"]):
        assert (x["setup_id"], x["accepted"], x["reasons"]) == (d.candidate.setup_id, d.accepted,
                                                                [r.value for r in d.reasons])
        assert x["lane"] == "EXPLORATORY" and x["version"] == 1 and x["bar_start"]
        assert x["accepted"] or x["reasons"]                                  # a refusal always says why
    orb, noise, l30 = dec
    assert (orb["setup_id"], orb["ts"][11:19], orb["accepted"]) == ("ORB5_QQQ", "09:35:01", True)
    assert (noise["setup_id"], noise["ts"][11:19], noise["side"]) == ("NOISE_MOM_SPY", "10:30:01", -1)
    assert not noise["accepted"] and noise["reasons"] == ["SHORT_DISABLED"] and noise["shadow"]
    assert (l30["setup_id"], l30["ts"][11:19], l30["accepted"]) == ("LAST30_MOM_SPY", "15:30:01", True)

    # ORB5: bracket with the first candle's low as the stop, out on the stop leg at the stop price (bar replay)
    closed = [x for x in lines if x["kind"] == "trade_closed"]
    assert [(x["setup_id"], x["how"]) for x in closed] == [("ORB5_QQQ", "stop"), ("LAST30_MOM_SPY", "TIME_EXIT")]
    ws = {x["setup_id"]: x for x in lines if x["kind"] == "would_submit"}
    assert ws["ORB5_QQQ"]["stop"] == 559.98 and ws["ORB5_QQQ"]["qty"] == 1
    stop_fill = next(x for x in lines if x["kind"] == "fill" and x["role"] == "stop")
    assert stop_fill["price"] == 559.98 and stop_fill["ts"][11:19] == "09:37:01"
    assert closed[0]["stop_out"] and closed[0]["honest_pnl"] < closed[0]["paper_pnl"] < 0

    # LAST30: flattened at 15:50 by the clock rule, flat well before 15:52 (MT-G20), nothing open at the end
    assert ws["LAST30_MOM_SPY"]["symbol"] == "SPY" and ws["LAST30_MOM_SPY"]["qty"] == 1
    assert closed[1]["ts"][11:16] == "15:50" and closed[1]["ts"] < f"{D}T15:52"
    assert not any(x["kind"] in ("kill_start", "reconcile_mismatch", "broker_error", "signal_error") for x in lines)
    (sim,) = RecordingSim.made
    assert not sim.positions() and not sim.open_orders()

    # MT-G21 / MT-G16: only limit orders, entries only as complete long brackets, never a real order anywhere
    assert [(s.symbol, s.order_class) for s in sim.submits] == [("QQQ", "bracket"), ("SPY", "bracket"),
                                                                 ("SPY", "simple")]
    assert all(s.limit_price > 0 and s.client_order_id.startswith("SCALP-") for s in sim.submits)
    assert not any(x["kind"] == "submit" for x in lines)

    # the plain-English summary and the report agree with the journal
    assert "refused NOISE_MOM_SPY SPY short at 10:30:01: SHORT_DISABLED" in out["summary"]
    assert "Closed trades: 2" in out["summary"]
    text = REP.build_report(lines, C.load_registry())
    assert "exits that were not stop/target/time/flatten/daily stop/kill: 0 (must be 0)" in text
    assert "qty differs from the sizing function: 0 (must be 0)" in text
    assert "SHORT_DISABLED: 1" in text


def test_mt_g27_an_earlier_replays_halt_never_blocks_the_next_replay(tmp_path):
    (tmp_path / "replay").mkdir()
    S.write_flag(tmp_path / "replay", S.HALT, "left over from an older replay", ts("09:00"), "test")
    bars = synthetic_day()
    st = session()
    market = M.ReplayMarket(D, bars, M.bar_quote_fn(bars), M.SimClock(st.open), open_ts=st.open, close_ts=st.close)
    j = J.MemoryJournal(Mode.REPLAY, market.clock)
    RUN.replay(D, e0=E0, market=market, ctx_by_symbol=ctxs(), session=st, state_dir=tmp_path, journal=j,
               out=lambda s: None)
    assert [x["accepted"] for x in j.of("decision")] == [True, False, True]
    assert not S.halted(tmp_path)                                   # the real state folder was never touched


# ============================================================================================ runner harness
def _runner(tmp_path, flags=()):
    """The real Runner + Engine + SimBroker (bar mode) on the synthetic day, in simulated time."""
    bars = synthetic_day()
    st = session()
    clock = M.SimClock(st.open)
    market = M.ReplayMarket(D, bars, M.bar_quote_fn(bars), clock, open_ts=st.open, close_ts=st.close)
    sim = SimBroker(clock, fill_mode="bar")
    j = J.MemoryJournal(Mode.REPLAY, clock)
    eng = RUN.make_engine(sim, j, C.load_registry(), DayCounters(D, E0, cash_prev_close=E0), st,
                          load_events_or_unknown().day(D), ctxs(), Mode.REPLAY, clock, state_dir=tmp_path / "st",
                          flags=flags)
    run = RUN.Runner(eng, market, j, Mode.REPLAY, clock, tmp_path / "st", st, sim_broker=sim, live=False)
    return run, sim, j, clock


def _until(run, clock, hms):
    while clock() < ts(hms):
        assert run.step() is not None


def test_startup_flags_reach_the_real_engine_and_block_every_entry(tmp_path):
    run, sim, j, clock = _runner(tmp_path, flags=[Reason.SELFTEST_FAILED])
    assert Reason.SELFTEST_FAILED in run.engine.flags
    run.loop()
    decs = j.of("decision")
    assert decs and all(not x["accepted"] and "SELFTEST_FAILED" in x["reasons"] for x in decs)
    assert not sim.submits


def test_mt_g21_bracket_take_profit_is_not_cancelled_at_60_seconds(tmp_path):
    run, sim, j, clock = _runner(tmp_path)
    _until(run, clock, "09:36:06")               # 65 s after the 09:35:01 entry (the next tick brings the drop)
    tp = next(o for o in sim.open_orders() if o.order_type == "limit" and o.side == "sell")
    assert tp.status == "new" and not sim.cancels                   # no timer ever cancels a working leg
    assert run.engine.status()["position"]["stop_confirmed"]


def test_sigterm_exits_the_position_through_the_normal_path_without_a_halt(tmp_path):
    run, sim, j, clock = _runner(tmp_path)
    _until(run, clock, "09:35:04")
    assert sim.positions() and run.engine.slot_state.value == "OPEN"
    run.request_stop("SIGTERM")
    out = run.loop()
    assert out["stop"] == "SIGTERM" and not sim.positions() and not sim.open_orders()
    assert [x["how"] for x in j.of("trade_closed")] == ["SHUTDOWN"]
    assert j.of("flatten_requested") and not j.of("kill_start")
    assert not (tmp_path / "st" / "HALT").exists()                  # an orderly stop needs no manual reset
    assert Reason.SHUTDOWN in run.engine.flags                      # and nothing new is bought meanwhile


# ============================================================================================ 2. dry run, live market
class FakeIEX:
    """The IEX REST endpoints LiveMarket polls, served from a list of synthetic bars at the simulated time: a bar is
    returned once its minute has ended, the quote is the last finished bar's close +/- half a cent (SIM feed), the
    last trade is that close. Also Alpaca's /v2/clock for the clock-offset check."""

    def __init__(self, clock, bars: dict[str, list[Bar]]):
        self.clock, self.bars = clock, bars
        self.calls = 0

    def _last(self, sym):
        done = [b for b in self.bars[sym] if b.start + pd.Timedelta(minutes=1) <= self.clock()]
        return done[-1].close if done else self.bars[sym][0].open

    def get_stock_latest_quote(self, req):
        self.calls += 1
        t = (self.clock() - pd.Timedelta(milliseconds=200)).tz_convert("UTC").to_pydatetime()
        return {s: SimpleNamespace(bid_price=self._last(s) - 0.005, ask_price=self._last(s) + 0.005, bid_size=3,
                                   ask_size=3, timestamp=t) for s in req.symbol_or_symbols}

    def get_stock_latest_trade(self, req):
        t = (self.clock() - pd.Timedelta(milliseconds=500)).tz_convert("UTC").to_pydatetime()
        return {s: SimpleNamespace(price=self._last(s), size=100, timestamp=t) for s in req.symbol_or_symbols}

    def get_stock_bars(self, req):
        assert req.feed.value == "iex"
        start = pd.Timestamp(req.start)
        start = (start.tz_localize("UTC") if start.tzinfo is None else start).tz_convert(NY)
        rows = [(s, b) for s in req.symbol_or_symbols for b in self.bars[s]
                if b.start >= start and b.start <= self.clock()]              # the minute in progress comes too
        idx = pd.MultiIndex.from_arrays([[s for s, _ in rows], [b.start.tz_convert("UTC") for _, b in rows]],
                                        names=["symbol", "timestamp"])
        df = pd.DataFrame([(b.open, b.high, b.low, b.close, b.volume) for _, b in rows],
                          columns=["open", "high", "low", "close", "volume"], index=idx)
        return SimpleNamespace(df=df)

    def get_clock(self):
        return SimpleNamespace(timestamp=self.clock().tz_convert("UTC").to_pydatetime())


def _dry_session(tmp_path, start="09:33:00", end="09:38:30"):
    """A dry run as `run --mode dry` wires it: LiveMarket (IEX, recorded) -> SimBroker (quote fills) -> Engine,
    heartbeat every tick, on a simulated clock that the loop's 1-second sleep moves forward."""
    st = session()
    clock = M.SimClock(ts(start))
    data = FakeIEX(clock, synthetic_day())
    rec_path = M.recording_path(tmp_path, D, "dry")
    rec = M.Recorder(rec_path)
    j = J.MemoryJournal(Mode.DRY, clock)
    market = M.LiveMarket(data, ["SPY", "QQQ"], clock, trading_client=data, recorder=rec, journal=j,
                          session_open=st.open, session_close=st.close, wall=lambda: clock().timestamp())
    sim = SimBroker(clock, fill_mode="quote")
    eng = RUN.make_engine(sim, j, C.load_registry(), DayCounters(D, E0, cash_prev_close=E0), st,
                          load_events_or_unknown().day(D), ctxs(), Mode.DRY, clock, state_dir=tmp_path)
    run = RUN.Runner(eng, market, j, Mode.DRY, clock, tmp_path, st, sim_broker=sim,
                     sleep=lambda s: clock.advance(1))
    n = int((ts(end) - ts(start)).total_seconds())
    out = run.loop(max_ticks=n)
    rec.close()
    return out, j, sim, data, rec_path


def test_mt_g22_dry_run_loop_with_a_live_market_for_five_simulated_minutes(tmp_path):
    out, j, sim, data, rec_path = _dry_session(tmp_path)
    assert out["ticks"] == 330 and data.calls == 330                 # one poll per simulated second
    assert j.of("HALT_STATUS_UNAVAILABLE")                           # halt status unknown, never "not halted"
    (orb,) = j.of("decision")
    assert orb["setup_id"] == "ORB5_QQQ" and orb["accepted"] and orb["ts"][11:19] == "09:35:00"
    (ws,) = j.of("would_submit")
    assert ws["symbol"] == "QQQ" and ws["qty"] == 1 and ws["quote"]["feed"] == "IEX"      # MT-G35 feed tag
    assert not j.of("submit") and [s.order_class for s in sim.submits] == ["bracket"]
    # the 9:36 drop reaches the quote at 09:37:00: the stop leg sells at the bid, inside the stop-limit
    (closed,) = j.of("trade_closed")
    assert closed["how"] == "stop" and closed["ts"][11:16] == "09:37"
    assert not sim.positions() and not sim.open_orders()
    hb = S.read_heartbeat(tmp_path)
    assert hb["mode"] == "dry" and hb["ts"] == ts("09:38:29").isoformat() and hb["status"]["slot"] == "COOLDOWN"
    assert rec_path.exists() and len(list(M.read_recording(rec_path))) == 330


# ============================================================================================ 3. replay a recording
def test_mt_g27_g37_replaying_a_recorded_session_gives_the_same_decisions(tmp_path):
    _, j, sim, _, rec_path = _dry_session(tmp_path / "live")
    out = RUN.replay(D, recording=rec_path, e0=E0, ctx_by_symbol=ctxs(), session=session(),
                     state_dir=tmp_path / "replay", out=lambda s: None)
    lines = J.read_journal(J.journal_path(tmp_path / "replay", D, Mode.REPLAY))
    assert lines[0]["fill_mode"] == "quote" and out["ticks"] == 330
    assert _decisions(lines) == _decisions(j.lines) and _decisions(lines)          # same signals, same reasons
    key = lambda xs: [(x["cid"], x["qty"], x["limit"], x["stop"], x["stop_limit"], x["target"])  # noqa: E731
                      for x in xs if x["kind"] == "would_submit"]
    assert key(lines) == key(j.lines)                                               # same orders, same ids
    fills = lambda xs: [(x["ts"], x["side"], x["price"]) for x in xs if x["kind"] == "fill"]  # noqa: E731
    assert fills(lines) == fills(j.lines)
    assert [x["how"] for x in lines if x["kind"] == "trade_closed"] == ["stop"]


# ============================================================================================ watchdog (MT-G39)
@pytest.mark.parametrize("first_check_s", [0, 7, 14])
def test_mt_g39_bot_dies_with_a_position_open_and_the_watchdog_flattens_within_45_seconds(tmp_path, first_check_s):
    died = ts("11:00:00")
    S.write_heartbeat(tmp_path, died, "paper", {"position": {"symbol": "SPY", "qty": 1}})    # the last beat
    clock = M.SimClock(died + pd.Timedelta(seconds=first_check_s))
    sim = SimBroker(clock, positions=(PositionView("SPY", 1, 650.0),), mode=Mode.PAPER)
    sim.set_quote("SPY", 650.00, 650.01)
    j = J.MemoryJournal(Mode.PAPER, clock)
    wd = W.Watchdog(Mode.PAPER, tmp_path, clock, j, broker=sim, sleep=lambda s: clock.advance(s), session=session(),
                    quote_fn=lambda sym: sim.quotes.get(sym))
    W.run_watchdog(wd, max_checks=4)
    (done,) = j.of("watchdog_flatten")
    assert done["flat"] and done["reasons"] == ["HEARTBEAT_STALE"]
    assert (as_ts(done["ts"]) - died).total_seconds() <= 45
    assert not sim.positions() and S.halted(tmp_path)


def as_ts(x: str) -> pd.Timestamp:
    return pd.Timestamp(x).tz_convert(NY)


# ============================================================================================ MT-G4 fills in replay
@pytest.mark.parametrize("low,filled", [(500.00, False), (499.99, True)])
def test_mt_g4_buy_limit_500_fills_in_bar_replay_only_when_the_low_trades_through_it(low, filled):
    from lab.scalp.live import orders as O
    from lab.scalp.live.model import Candidate, Quote
    reg = C.load_registry().get("ORB5_QQQ", "QQQ")
    clock = M.SimClock(ts("10:00:01"))
    q = Quote("QQQ", 499.97, 499.98, 100, 100, clock(), clock(), Feed.SIM)       # limit = ask + 2 cents = 500.00
    cand = Candidate("ORB5_QQQ", 1, "QQQ", "enter", 1, ts("09:59"), stop=498.0, target_r=10.0)
    spec, why, _ = O.entry_bracket(cand, reg, q, E0, D, 0)
    assert spec is not None and spec.limit_price == 500.00, why
    sim = SimBroker(clock, fill_mode="bar")                     # no quote in the simulator: only bars can fill it
    v = sim.submit(spec)
    assert v.status == "new"
    clock.advance(60)
    sim.update(clock(), None, {"QQQ": [Bar("QQQ", ts("10:00"), 500.5, 500.6, low, 500.5, 1e4, Feed.SIP)]})
    o = sim.get_order(v.id)
    assert (o.status == "filled") is filled
    if filled:
        assert o.filled_avg_price == 500.00                     # at the limit, never better than it


# ============================================================================================ 4. command line
def _cli(*args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ALPACA_", "APCA_"))}   # no keys at all
    return subprocess.run([sys.executable, "-m", "lab.scalp.live", *args], cwd=TRADING, env=env,
                          capture_output=True, text=True, timeout=120)


def test_cli_help_lists_every_command():
    r = _cli("--help")
    assert r.returncode == 0, r.stderr
    for cmd in ("check-account", "run", "replay", "kill", "reset-halt", "watchdog", "report", "hash"):
        assert cmd in r.stdout


def test_mt_g10_g41_cli_hash_prints_the_risk_and_code_hashes_offline():
    r = _cli("hash")
    assert r.returncode == 0, r.stderr
    assert f"risk hash    {C.risk_hash()}" in r.stdout
    assert f"package hash {RUN.package_hash()}" in r.stdout
    reg = C.load_registry()
    assert len(reg.setups) == 3
    for x in reg.setups:
        assert f"{x.setup_id}/{x.symbol} v{x.version} [EXPLORATORY]" in r.stdout
    assert "CODE_HASH_MISMATCH" not in r.stdout


def test_mt_g36_cli_run_paper_without_confirm_exits_2_before_building_any_client():
    r = _cli("run", "--mode", "paper")
    assert r.returncode == 2 and "--confirm-paper" in r.stdout
