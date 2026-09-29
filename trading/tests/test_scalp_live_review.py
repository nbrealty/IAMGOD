"""Live paper minute trader: fixes from the independent review of lab/scalp/live (restarts, the whole-test stop, the
watchdog backstop, switch-offs, honest P&L, broker timeouts). All offline: SimBroker or fake clients, fake clocks,
memory journals and tmp_path state. No network, no keys."""
import dataclasses
import fcntl
import json
from argparse import Namespace
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from lab.scalp.live import __main__ as cli
from lab.scalp.live import broker as B
from lab.scalp.live import config as C
from lab.scalp.live import gates as G
from lab.scalp.live import journal as J
from lab.scalp.live import market as M
from lab.scalp.live import orders as O
from lab.scalp.live import report as REP
from lab.scalp.live import restore as RS
from lab.scalp.live import risk as R
from lab.scalp.live import runner as RUN
from lab.scalp.live import state as S
from lab.scalp.live import watchdog as W
from lab.scalp.live.broker import AlpacaBroker, SimBroker
from lab.scalp.live.engine import Engine
from lab.scalp.live.model import (Bar, BrokerReject, DayCounters, Feed, Lane, Mode, OrderView, PositionView, Reason,
                                  SlotState, as_ny)

from test_scalp_live_engine import D, KNOWN, REG, H, ctxs, enter_noise, mkbars, session, ts

NOISE = REG.get("NOISE_MOM_SPY", "SPY")
ENV = {"ALPACA_SCALP_KEY": "k-scalp", "ALPACA_SCALP_SECRET": "s-scalp"}


def restart(h, tmp_path, now=None, test_start=None, history=None):
    """Kill the process, start a new one: counters and adoption rebuilt from the broker, same state directory."""
    now = now or h.t
    c, adopted = RS.rebuild(h.sim, h.d, h.c.e0, h.c.cash_prev_close, h.d - timedelta(days=h.d.weekday()),
                            test_start, REG, now)
    h.c = c
    h.eng = Engine(h.sim, h.j, REG, c, session(h.d), KNOWN, ctxs(), Mode.DRY, h.clock, adopted=adopted,
                   state_dir=h.state, history=history)
    return c, adopted


# =================================================================================== whole-test stop (paper caps)
def _trade(day, n, buy, sell, setup="NOISE_MOM_SPY", sym="SPY", leg="X", tp_filled=False):
    """One closed SCALP round trip on `day` as the broker's history shows it (an entry parent and our sell)."""
    t0 = as_ny(f"{day} 10:00:01")
    cid = O.client_id(setup, 1, day, t0.floor("min") - pd.Timedelta(minutes=1), "E", n)
    legs = ()
    if tp_filled:
        legs = (OrderView(f"tp{day}{n}", f"leg-tp{n}", sym, "sell", 1, 1, sell, "filled", "limit", sell,
                          filled_at=t0 + pd.Timedelta(minutes=5)),
                OrderView(f"sl{day}{n}", f"leg-sl{n}", sym, "sell", 1, 0, None, "canceled", "stop_limit", buy - 4,
                          buy - 3))
    entry = OrderView(f"e{day}{n}", cid, sym, "buy", 1, 1, buy, "filled", "limit", buy + 0.02,
                      order_class="bracket" if legs else "simple", legs=legs, submitted_at=t0, filled_at=t0)
    if tp_filled:
        return [entry]
    xid = O.client_id(setup, 1, day, t0.floor("min") - pd.Timedelta(minutes=1), leg, n)
    ex = OrderView(f"x{day}{n}", xid, sym, "sell", 1, 1, sell, "filled", "limit", sell,
                   submitted_at=t0 + pd.Timedelta(minutes=5), filled_at=t0 + pd.Timedelta(minutes=5))
    return [entry, ex]


class HistBroker:
    """The broker's order history and positions, nothing else (restore.py only reads)."""

    def __init__(self, orders, positions=()):
        self.orders, self.pos = list(orders), list(positions)

    def orders_since(self, since):
        return [o for o in self.orders if o.submitted_at >= as_ny(since)]

    def positions(self):
        return self.pos


def _entry_reasons(c, now=ts("11:00:01")):
    t = now
    from lab.scalp.live.model import Candidate, LastTrade, Quote
    bars = [Bar("SPY", ts("10:55") + pd.Timedelta(minutes=k), 650.0, 650.1, 649.9, 650.0, 1e4, Feed.IEX)
            for k in range(5)]
    ec = R.EntryContext(now=t, candidate=Candidate(NOISE.setup_id, 1, "SPY", "enter", 1, ts("10:59")), reg=NOISE,
                        counters=c, session=session(), events=KNOWN,
                        quote=Quote("SPY", 650.0, 650.01, 1, 1, t, t, Feed.IEX),
                        last_trade=LastTrade("SPY", 650.0, 1, t, Feed.IEX), recent_bars=bars, last_data_ok=t,
                        clock_offset_ms=10.0, halted=False, prior_close=648.0, slot_state=SlotState.FLAT,
                        open_parents=0, open_position=False, settled_cash=100_000.0,
                        broker_nonmarginable_bp=100_000.0, planned_notional=650.03)
    return R.entry_reasons(ec)


def test_whole_test_stop_counts_losses_from_earlier_sessions_after_a_restart():
    days = [date(2026, 9, 21) + timedelta(days=k) for k in (0, 1, 2, 3, 4, 7)]     # 6 sessions, -$30 each
    hist = HistBroker([o for i, d in enumerate(days) for o in _trade(d, i, 650.0, 620.0)])
    today = date(2026, 9, 29)
    c, _ = RS.rebuild(hist, today, 100_000.0, 100_000.0, date(2026, 9, 28), days[0], REG, ts("09:00", today))
    assert c.test_sessions == 6 and c.test_honest == pytest.approx(-180.0 - 6 * 0.02 - 6 * X_fees(620.0), abs=0.05)
    assert Reason.TEST_STOP in _entry_reasons(dataclasses.replace(c, session_date=D))
    # the committed registry's null test_start used to hide all of it
    c0, _ = RS.rebuild(hist, today, 100_000.0, 100_000.0, date(2026, 9, 28), None, REG, ts("09:00", today))
    assert c0.test_honest == 0.0 and c0.test_sessions == 0


def X_fees(px):
    from lab.scalp.live import costs
    return costs.fees("sell", 1, px, date(2026, 9, 28))


def test_whole_test_stop_after_60_sessions_even_without_losses():
    days = list(pd.bdate_range("2026-07-01", periods=60).date)
    hist = HistBroker([o for i, d in enumerate(days) for o in _trade(d, i, 650.0, 650.10)])
    today = days[-1] + timedelta(days=1)
    c, _ = RS.rebuild(hist, today, 100_000.0, 100_000.0, today - timedelta(days=today.weekday()), days[0], REG,
                      ts("09:00", today))
    assert c.test_sessions == 60
    assert Reason.TEST_STOP in _entry_reasons(dataclasses.replace(c, session_date=D))


def test_first_paper_run_pins_the_test_start_and_logs_it(tmp_path):
    reg = C.load_registry()
    assert reg.test_start is None                                      # the committed file stays null
    assert RUN.resolve_test_start(reg, tmp_path, Mode.DRY, ts("09:10")) is None     # a dry run pins nothing
    with pytest.raises(RuntimeError):                                  # PAPER needs the broker history (fail closed)
        RUN.resolve_test_start(reg, tmp_path, Mode.PAPER, ts("09:10"))
    assert RUN.resolve_test_start(reg, tmp_path, Mode.PAPER, ts("09:10"), []) == D    # no SCALP history: today
    later = ts("09:10", date(2026, 10, 8))
    assert RUN.resolve_test_start(reg, tmp_path, Mode.PAPER, later, []) == D      # never moved later
    assert [x["action"] for x in S.read_changes(tmp_path)] == ["test-start"]
    fixed = dataclasses.replace(reg, test_start=date(2026, 9, 30))
    assert RUN.resolve_test_start(fixed, tmp_path, Mode.PAPER, later, []) == date(2026, 9, 30)
    (tmp_path / S.TEST_START_PIN).write_text("garbage")
    with pytest.raises(RuntimeError):
        S.pin_test_start(tmp_path, D, ts("09:10"), "x")


# =================================================================================== MT-G39 watchdog
def test_mt_g39_paper_run_refuses_no_watchdog_before_touching_anything(monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("no client may be built")

    monkeypatch.setattr(RUN, "scalp_clients", boom)
    msgs = []
    assert RUN.run("paper", confirm_paper=True, no_watchdog=True, env={}, out=msgs.append) == 2
    assert "MT-G39" in msgs[0]
    assert cli.main(["run", "--mode", "paper", "--confirm-paper", "--no-watchdog"]) == 2


def test_mt_g39_a_dry_heartbeat_never_counts_as_the_paper_bot(tmp_path):
    from test_scalp_live_runtime import _book, _quote, _wd
    S.write_heartbeat(tmp_path, ts("10:59:55"), "dry", {"position": None})     # a dry bot is running ...
    b = _book()
    wd, _ = _wd(tmp_path, "11:00:00", b)
    out = wd.check()                                                       # ... the paper bot is dead
    assert out["action"] == "flatten" and out["reasons"] == ["HEARTBEAT_STALE"] and b.positions() == []
    b2 = _book()
    res = W.kill_command("owner", tmp_path, lambda: ts("11:00"), lambda: b2, J.MemoryJournal(Mode.PAPER),
                         quote_fn=_quote, sleep=lambda s: None, out=lambda s: None)
    assert res["acted"] and b2.positions() == []
    assert S.read_heartbeat(tmp_path, "dry")["mode"] == "dry" and S.read_heartbeat(tmp_path, "paper") is None


def test_mt_g39_watchdog_flattens_even_when_a_hung_bot_holds_the_broker_lock(tmp_path):
    from test_scalp_live_runtime import _book, _quote
    from test_scalp_live_runtime import Clock
    S.write_heartbeat(tmp_path, ts("10:59:00"), "paper", {"position": True})
    b = _book()
    j = J.MemoryJournal(Mode.PAPER)
    wd = W.Watchdog(Mode.PAPER, tmp_path, Clock(ts("11:00:00")), j, broker=b, quote_fn=_quote,
                    sleep=lambda s: None, session=session(), lock_wait_s=0.2)
    with open(tmp_path / S.LOCK, "a+") as held:                         # the bot hangs inside an order call
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        out = wd.check()
    assert out["action"] == "flatten" and b.positions() == []
    assert j.of("lock_not_acquired")


def test_mt_g39_alpaca_broker_lock_gives_up_after_its_deadline(tmp_path):
    from test_scalp_live_broker import FakeClient
    br = AlpacaBroker(Mode.PAPER, lock_path=tmp_path / "broker.lock", pin_path=None, account_last4="GWRL",
                      client_factory=lambda k, s: FakeClient(), env=ENV)
    with open(tmp_path / "broker.lock", "a+") as held:
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        with br.lock(wait_s=0.1) as got:
            assert got is False
            with br.lock() as inner:                                   # nested submits do not wait again
                assert inner is True
    with br.lock(wait_s=0.1) as got:
        assert got is True


# =================================================================================== HTTP timeouts (MT-G25)
def test_every_alpaca_http_call_gets_a_timeout(monkeypatch):
    from alpaca.trading.client import TradingClient
    seen = []
    client = TradingClient("k", "s", paper=True)
    monkeypatch.setattr(client._session, "request", lambda method, url, **kw: seen.append(kw) or "ok")
    B.with_timeout(client)
    assert client._session.request("GET", "https://paper-api.alpaca.markets/v2/account") == "ok"
    client._session.request("GET", "x", timeout=2.0)
    assert [x["timeout"] for x in seen] == [C.HTTP_TIMEOUT_S, 2.0]
    B.with_timeout(client)                                            # idempotent: not wrapped twice
    client._session.request("GET", "y")
    assert len(seen) == 3

    class Sess:
        def request(self, method, url, **kw):
            return kw

    fake = SimpleNamespace(_base_url="https://paper-api.alpaca.markets", _session=Sess(), _retry=3)
    br = AlpacaBroker(Mode.DRY, lock_path=None, pin_path=None, account_last4="GWRL", client_factory=lambda k, s: fake,
                      env=ENV)
    assert br.client._session.request("GET", "z")["timeout"] == C.HTTP_TIMEOUT_S and br.client._retry == 0


def test_a_request_timeout_is_broker_unavailable_not_a_reject():
    import requests
    from lab.scalp.live.model import BrokerUnavailable
    assert isinstance(B.classify(requests.exceptions.ReadTimeout("stalled")), BrokerUnavailable)


# =================================================================================== check-account (step 1)
def test_check_account_accepts_the_real_alpaca_paper_client_without_any_network(tmp_path):
    from alpaca.trading.client import TradingClient
    from test_scalp_live_runtime import FakeTC

    def make(k, s):
        c = B.with_timeout(TradingClient(k, s, paper=True))            # _base_url is the BaseURL enum here
        c.get_account = FakeTC("PA3SCALPGWRL" if k == "sk" else "PA9RULESXXXX").get_account
        return c

    env = {"ALPACA_SCALP_KEY": "sk", "ALPACA_SCALP_SECRET": "ss", "ALPACA_RULES_KEY": "rk",
           "ALPACA_RULES_SECRET": "rs"}
    msgs = []
    assert cli.check_account(env, make, tmp_path, msgs.append) == 0, msgs
    assert "  base URL https://paper-api.alpaca.markets" in msgs


# =================================================================================== MT-G27 deploys
def test_mt_g27_first_start_at_1000_with_changed_code_blocks_entries(tmp_path):
    assert RUN.deploy_reasons(ts("10:00"), None, "b" * 64, baseline_hash="a" * 64) == [
        Reason.DEPLOY_IN_MARKET_HOURS]
    assert RUN.deploy_reasons(ts("10:00"), None, "a" * 64, baseline_hash="a" * 64) == []
    assert RUN.deploy_reasons(ts("10:00"), None, "b" * 64, require_baseline=True) == [Reason.DEPLOY_IN_MARKET_HOURS]
    assert RUN.deploy_reasons(ts("08:59"), None, "b" * 64, baseline_hash="a" * 64, require_baseline=True) == []
    S.write_session(tmp_path, date(2026, 9, 29), {"package_hash": "old", "starts": [{"package_hash": "p1"}]})
    S.write_session(tmp_path, date(2026, 9, 30), {"package_hash": "x", "starts": [{"package_hash": "a"},
                                                                                  {"package_hash": "p2"}]})
    S.write_session(tmp_path, D, {"package_hash": "today"})
    assert S.last_package_hash(tmp_path, D) == "p2"                    # yesterday's last start, not today's
    assert S.last_package_hash(tmp_path, date(2026, 9, 29)) is None


# =================================================================================== MT-G27 / G40 kill
def test_mt_g27_restart_mid_kill_keeps_entries_blocked_and_ends_in_halt(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.step(1)
    h.sim.cancel_delay_s = 1e9                                        # the kill cannot finish before the restart
    h.eng.request_kill("RUNAWAY_ORDERS: test")
    for _ in range(5):
        h.step(1)
    assert h.flag("KILL").exists() and not h.flag("HALT").exists()
    h.sim.cancel_delay_s = 0.0
    for o in h.sim.orders.values():
        o.cancel_at = None if o.status != "pending_cancel" else h.t   # the broker catches up after the restart
    restart(h, tmp_path)
    h.step(1)
    assert Reason.KILLED in h.eng.flags
    h.until("10:00:30")
    assert h.flat() and h.flag("HALT").exists() and not h.flag("KILL").exists()
    h.t = ts("10:30:00")
    h.px["SPY"] = 652.0
    decs = h.step(1, {"SPY": mkbars("SPY", "10:00", "10:29", 651.0, 652.0)})
    noise = [x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY" and x.candidate.action == "enter"]
    assert all(not x.accepted for x in noise) and h.sim.submits.count is not None
    assert len([s for s in h.sim.submits if s.kind.value == "ENTRY"]) == 1


# =================================================================================== MT-G25 / G40 rejects
def test_mt_g25_restart_after_a_403_keeps_the_symbol_blocked_and_the_submit_counted(tmp_path):
    h = H(tmp_path, sim_kw={"reject_next": 403})
    h.px["SPY"] = 651.0
    decs = h.step(1, {"SPY": mkbars("SPY", "09:30", "09:59", 650.0, 651.0)})
    noise = [x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY"]
    assert noise[0].reasons == (Reason.SYMBOL_BLOCKED_BROKER_REJECT,) and h.c.blocked_symbols == {"SPY"}
    h.t = ts("10:05:00")
    c, _ = restart(h, tmp_path)
    assert c.blocked_symbols == {"SPY"} and c.entry_submits == 1 and h.eng.broker.entry_count == 1
    assert h.eng.entries_by_setup.get("NOISE_MOM_SPY") == 1
    h.t = ts("10:30:00")
    h.px["SPY"] = 652.0
    decs = h.step(1, {"SPY": mkbars("SPY", "09:30", "10:29", 650.0, 652.0)})
    assert not h.sim.submits
    assert all(Reason.SYMBOL_BLOCKED_BROKER_REJECT in x.reasons for x in decs if x.candidate.action == "enter")


# =================================================================================== MT-G40 exit across a restart
def _rest_exit_then_restart(h, tmp_path, cancel_delay):
    enter_noise(h)
    h.step(1)
    h.sim.fill_delay_s = 1e9                                          # the time exit's sell rests unfilled
    h.t = ts("15:49:59")
    h.step(1)
    assert h.j.of("exit_order")
    h.sim.fill_delay_s = 0.0
    h.sim.cancel_delay_s = cancel_delay
    restart(h, tmp_path)


def test_mt_g40_restart_while_an_exit_sell_rests_waits_for_its_cancel_and_never_oversells(tmp_path):
    h = H(tmp_path)
    _rest_exit_then_restart(h, tmp_path, cancel_delay=3.0)
    h.px["SPY"] = 650.0                                               # the resting sell is no longer marketable
    h.until("15:50:30")
    assert h.flat() and not h.j.of("exit_rejected") and not h.j.of("kill_start")
    assert h.j.of("trade_closed")


def test_mt_g40_an_exit_that_fills_right_after_a_restart_is_booked_to_the_trade(tmp_path):
    h = H(tmp_path)
    _rest_exit_then_restart(h, tmp_path, cancel_delay=0.0)
    h.until("15:50:10")                                               # the stray exit fills at once
    assert h.flat() and not h.j.of("exit_rejected") and not h.j.of("kill_start")
    closed = h.j.of("trade_closed")[-1]
    assert closed["how"] == "EXIT_BEFORE_RESTART" and closed["sells"] and closed["paper_pnl"] is not None
    assert h.c.realized_pnl == pytest.approx(closed["paper_pnl"])


# =================================================================================== MT-G12 / G13 / G3 switch-offs
def test_mt_g12_a_losing_history_starts_the_setup_in_shadow(tmp_path):
    rs = list(np.random.default_rng(1).normal(-0.5, 0.3, 30))
    h = H(tmp_path)
    h.eng = Engine(h.sim, h.j, REG, h.c, session(), KNOWN, ctxs(), Mode.DRY, h.clock, state_dir=h.state,
                   history={("NOISE_MOM_SPY", "SPY"): {"r": rs, "slip": []}})
    assert h.eng.registry.get("NOISE_MOM_SPY", "SPY").lane is Lane.SHADOW
    assert h.j.of("lane_demoted")[0]["to_lane"] == "SHADOW"
    h.px["SPY"] = 651.0
    decs = h.step(1, {"SPY": mkbars("SPY", "09:30", "09:59", 650.0, 651.0)})
    noise = [x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY"][0]
    assert not noise.accepted and Reason.LANE_SHADOW in noise.reasons and not h.sim.submits


def test_mt_g12_switch_off_runs_after_every_closed_trade(tmp_path):
    h = H(tmp_path)
    h.eng.hist[("NOISE_MOM_SPY", "SPY")] = {"r": [-0.6] * 29, "slip": []}
    enter_noise(h)
    h.step(1)
    h.px["SPY"] = 649.0                                               # a loser, closed at the 15:50 time exit
    h.t = ts("15:49:59")
    h.until("15:50:05")
    assert h.j.of("trade_closed") and h.j.of("trade_closed")[-1]["r"] < 0
    assert h.eng.registry.get("NOISE_MOM_SPY", "SPY").lane is Lane.SHADOW
    assert h.eng.registry.get("LAST30_MOM_SPY", "SPY").lane is Lane.EXPLORATORY


def test_mt_g3_median_slippage_over_30_fills_above_1_5x_model_holds_the_setup_in_shadow():
    assert G.lane_check([], [3.0] * 29, None, 1.5) == (None, [])      # 29 fills: not yet
    lane, why = G.lane_check([], [3.0] * 30, None, 1.5)               # 3 bps > 1.5 x 1.5 bps
    assert lane is Lane.SHADOW and why[0].startswith("MT-G3")
    assert G.lane_check([], [2.2] * 30, None, 1.5)[0] is None         # under 1.5 x model
    lane, why = G.lane_check([], [3.5] * 30, None, 1.5)               # over 2 x model too (MT-G13 backstop)
    assert lane is Lane.SHADOW and any(w.startswith("MT-G13") for w in why)
    assert G.lane_check([], [9.0] * 50, None, None) == (None, [])     # no model: the check says off, never trips


def test_mt_g13_cusum_needs_a_baseline_and_then_trips_a_drifting_setup():
    bad = list(np.random.default_rng(3).normal(-0.2, 1.0, 90))
    assert not any(w.startswith("MT-G13") for w in G.lane_check(bad, [], None, None)[1])
    trips = sum(any(w.startswith("MT-G13") for w in G.lane_check(
        list(np.random.default_rng(s).normal(-0.2, 1.0, 90)), [], 0.2, None)[1]) for s in range(40))
    assert trips >= 32


def test_mt_g3_slippage_history_from_the_journal_starts_the_setup_in_shadow(tmp_path):
    lines = [{"kind": "fill", "ts": f"2026-09-30T10:{i:02d}:01-04:00", "setup_id": "LAST30_MOM_SPY",
              "symbol": "SPY", "side": "buy", "slippage": {"bps": 4.0, "cents": 0.26}} for i in range(30)]
    p = J.journal_path(tmp_path, date(2026, 9, 30), Mode.PAPER)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    hist = RUN.lane_history(REG, RS.AdoptedState(), tmp_path, Mode.PAPER)
    assert hist[("LAST30_MOM_SPY", "SPY")]["slip"] == [4.0] * 30 and hist[("ORB5_QQQ", "QQQ")]["slip"] == []
    h = H(tmp_path)
    eng = Engine(h.sim, h.j, REG, h.c, session(), KNOWN, ctxs(), Mode.DRY, h.clock, history=hist)
    assert eng.registry.get("LAST30_MOM_SPY", "SPY").lane is Lane.SHADOW


# =================================================================================== MT-G4 pending verify
def test_mt_g4_a_take_profit_fill_is_pending_verify_and_kept_out_of_the_gates(tmp_path):
    h = H(tmp_path)
    h.c.loss_streak = 2
    enter_noise(h)
    h.step(1)
    target = h.eng.trade.target
    h.px["SPY"] = target + 0.05                                       # the resting take-profit fills on paper
    h.step(1)
    closed = h.j.of("trade_closed")[-1]
    assert closed["how"] == "target" and closed["pending_verify"] and closed["honest_pnl"] > 0
    assert closed["gate_honest_pnl"] == 0.0
    assert h.c.realized_honest == 0.0 and h.c.test_honest == 0.0 and h.c.loss_streak == 2
    assert h.c.realized_pnl == pytest.approx(closed["paper_pnl"])


def test_mt_g4_restore_keeps_a_take_profit_win_out_of_the_gates():
    today = D
    hist = HistBroker(_trade(today, 0, 650.0, 656.5, tp_filled=True) + _trade(today, 1, 650.0, 649.0))
    c, st = RS.rebuild(hist, today, 100_000.0, 100_000.0, today - timedelta(days=today.weekday()), today, REG,
                       ts("12:00"))
    tp = next(t for t in st.trades if t.pending_verify)
    assert tp.honest_pnl > 0 and tp.gate_honest == 0.0
    loss = next(t for t in st.trades if not t.pending_verify)
    assert c.realized_honest == pytest.approx(loss.honest_pnl) and c.test_honest == pytest.approx(loss.honest_pnl)


# =================================================================================== MT-G35 volume setups
def test_mt_g35_volume_setup_with_feed_iex_is_shadow_only_and_with_sip_allowed():
    j = J.MemoryJournal(Mode.DRY)
    iex, shadow = RUN.registry_for_run(REG, j, feed="IEX")
    assert iex.get("NOISE_MOM_SPY", "SPY").lane is Lane.SHADOW and shadow == ["NOISE_MOM_SPY/SPY"]
    assert iex.get("ORB5_QQQ", "QQQ").lane is Lane.EXPLORATORY and iex.get("LAST30_MOM_SPY", "SPY").lane is \
        Lane.EXPLORATORY
    assert j.of("volume_setup_on_iex")[0]["setup_id"] == "NOISE_MOM_SPY"
    sip, shadow = RUN.registry_for_run(REG, J.MemoryJournal(Mode.DRY), feed="SIP")
    assert sip.get("NOISE_MOM_SPY", "SPY").lane is Lane.EXPLORATORY and shadow == []


def _reg_file(tmp_path, idx=0, **change):
    raw = json.loads(C.REGISTRY_PATH.read_text())
    raw["setups"][idx].update(change)
    for k, v in list(change.items()):
        if v is KeyError:
            del raw["setups"][idx][k]
    p = tmp_path / "reg.json"
    p.write_text(json.dumps(raw))
    return p


def test_mt_g35_every_registration_must_say_whether_it_uses_volume(tmp_path):
    with pytest.raises(C.RegistryError):
        C.load_registry(_reg_file(tmp_path, uses_volume=KeyError))
    with pytest.raises(C.RegistryError, match="MT-G35"):
        C.load_registry(_reg_file(tmp_path, uses_volume="yes"))


# =================================================================================== MT-G10 cadence
def test_mt_g10_v3_twenty_sessions_later_allowed_nineteen_refused_safety_fix_exempt(tmp_path):
    base = dict(version=3, registered="2026-11-03", prior_registered="2026-10-06")      # s + 20 sessions
    assert C.load_registry(_reg_file(tmp_path, **base)).setups[0].version == 3
    with pytest.raises(C.RegistryError, match="MT-G10"):
        C.load_registry(_reg_file(tmp_path, **{**base, "registered": "2026-11-02"}))  # s + 19
    reg = C.load_registry(_reg_file(tmp_path, **{**base, "registered": "2026-10-13", "safety_fix": True}))
    assert reg.setups[0].safety_fix
    with pytest.raises(C.RegistryError, match="prior_registered"):
        C.load_registry(_reg_file(tmp_path, version=2))


# =================================================================================== MT-G21 stop watchdog
def test_mt_g21_stop_watchdog_first_resend_is_bid_minus_0_2_percent(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.step(1)
    h.px["SPY"] = h.eng.trade.stop_limit - 1.0                        # gapped through the stop-limit
    t0 = h.t
    while not h.j.of("exit_order") and h.t < t0 + pd.Timedelta(seconds=15):
        h.step(1)
    first = h.j.of("exit_order")[0]
    assert first["reason"] == "STOP_ESCALATION" and first["collar"] == 0.002
    assert first["limit"] == O.round_up_cent(h.px["SPY"] * (1 - 0.002))
    assert C.STOP_ESCALATION_COLLARS == (0.002, 0.005, 0.01)


# =================================================================================== MT-G25 / G27 kill attempts
def test_mt_g27_kill_switch_keeps_working_past_attempt_999(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.step(1)
    h.eng.kill_attempt = 1000
    h.eng.request_kill("test")
    h.until("10:00:30")
    assert h.flat() and h.j.of("kill_done")
    assert not any("cannot price" in a["message"] for a in h.j.of("alert"))
    assert O.parse_client_id(h.j.of("kill_order")[0]["cid"])["attempt"] == 0


def test_mt_g27_a_rejected_kill_order_waits_before_the_next_try(tmp_path):
    h = H(tmp_path)
    enter_noise(h)
    h.step(1)
    h.eng.request_kill("test")
    h.sim.reject_next = 403                                           # the first kill sell is refused
    h.step(1)
    rej = h.j.of("kill_order_rejected")
    assert len(rej) == 1
    t_rej = h.t
    while not h.j.of("kill_order") and h.t < t_rej + pd.Timedelta(seconds=10):
        h.step(1)
    assert h.t - t_rej >= pd.Timedelta(seconds=C.EXIT_ACK_S) and h.j.of("kill_order")


# =================================================================================== MT-G16 cancels
def test_alpaca_cancel_422_counts_only_when_the_order_is_really_done(tmp_path):
    from test_scalp_live_broker import FakeClient, api_error, fake_order

    class C422(FakeClient):
        def __init__(self, status):
            super().__init__()
            self.status = status

        def cancel_order_by_id(self, oid):
            raise api_error(422, "order is not cancelable")

        def get_order_by_id(self, oid, req=None):
            from alpaca.trading.enums import OrderStatus
            return fake_order(id=oid, status=OrderStatus(self.status))

    ok = AlpacaBroker(Mode.PAPER, lock_path=tmp_path / "l", pin_path=None, account_last4="GWRL",
                      client_factory=lambda k, s: C422("filled"), env=ENV)
    assert ok.cancel("o-1") is None
    stuck = AlpacaBroker(Mode.PAPER, lock_path=tmp_path / "l", pin_path=None, account_last4="GWRL",
                         client_factory=lambda k, s: C422("held"), env=ENV)
    with pytest.raises(BrokerReject) as e:
        stuck.cancel("o-1")
    assert e.value.code == "NOT_CANCELABLE"


# =================================================================================== SIGTERM (DESIGN 2C)
class StuckEngine:
    """Never flat: the exit path cannot get out."""

    def __init__(self):
        self.flatten = self.kill = None
        self.flags = set()

    def tick(self, snap):
        return []

    def request_flatten(self, why):
        self.flatten = why

    def request_kill(self, why):
        self.kill = why

    def status(self):
        return {"position": {"symbol": "SPY", "qty": 1}, "open_orders": ["x"]}


def test_sigterm_keeps_going_until_flat_escalates_to_the_kill_then_stops_loudly(tmp_path):
    from test_scalp_live_runtime import _bars
    bars = {"SPY": _bars([f"10:{m:02d}" for m in range(0, 10)])}
    clock = M.SimClock(ts("10:00"))
    market = M.ReplayMarket(D, bars, M.bar_quote_fn(bars), clock, open_ts=ts("10:00"), close_ts=ts("10:10"))
    eng = StuckEngine()
    j = J.MemoryJournal(Mode.DRY, clock)
    run = RUN.Runner(eng, market, j, Mode.DRY, clock, tmp_path, session(), live=False, heartbeat=False)
    run.step()
    t0 = as_ny(clock())
    run.request_stop("SIGTERM")
    run.loop()
    assert eng.flatten == "SIGTERM" and "SHUTDOWN" in eng.kill
    stop = j.of("stop_not_flat")
    assert stop and as_ny(stop[0]["ts"]) - t0 >= pd.Timedelta(seconds=RUN.SIGTERM_HARD_S)
    assert "watchdog must flatten" in (tmp_path / "alerts.log").read_text()


# =================================================================================== MT-G15 day trades
def test_mt_g15_the_bot_counts_its_own_day_trades_over_5_business_days():
    days = [date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 28), date(2026, 9, 30), D]
    hist = HistBroker([o for i, d in enumerate(days) for o in _trade(d, i, 650.0, 650.5)])
    c, _ = RS.rebuild(hist, D, 1e5, 1e5, date(2026, 9, 28), days[0], REG, ts("12:00"))
    assert c.day_trades_5d == 4                                       # 9/24 is 6 business days back


# =================================================================================== partial fills (spec 8)
class HeldLegsAfterPartial(SimBroker):
    """After a partial fill and a cancel of the rest, the legs stay 'held' with the filled qty (never active)."""

    def _set_canceled(self, o, now):
        if o.role == "parent" and o.filled_qty > 0:
            o.status, o.updated_at, o.cancel_at = "canceled", now, None
            for x in o.legs:
                self.orders[x].qty = o.filled_qty
                self.orders[x].status = "held"
            return
        super()._set_canceled(o, now)


def test_partial_fill_never_counts_a_held_leg_as_protection(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "EXPLORATORY_MAX_QTY", 2)
    h = H(tmp_path, sim=HeldLegsAfterPartial(lambda: ts("10:00:00"), partial_fill_qty=1))
    enter_noise(h)
    t0 = h.t
    while not h.flat() and h.t < t0 + pd.Timedelta(seconds=C.STOP_CONFIRM_S + 3):
        h.step(1)
    assert h.flat() and not h.j.of("stop_confirmed")
    assert h.j.of("exit_start")[0]["reason"] == "PARTIAL_FILL_PROTECT"


# =================================================================================== late bars (spec 8)
def test_a_decision_bar_that_arrives_with_the_next_bar_is_journalled_bar_stale(tmp_path):
    h = H(tmp_path, start="09:59:30")
    h.px["SPY"] = 650.9
    h.step(1, {"SPY": mkbars("SPY", "09:30", "09:58", 650.0, 650.9)})
    h.t = ts("10:01:08")
    h.px["SPY"] = 651.0
    late = [b for b in mkbars("SPY", "09:30", "10:00", 650.0, 651.0)][-2:]       # 9:59 and 10:00 together
    decs = h.step(1, {"SPY": late})
    noise = [x for x in decs if x.candidate.setup_id == "NOISE_MOM_SPY"]
    assert noise and noise[0].reasons == (Reason.BAR_STALE,) and noise[0].notes["missed"]
    assert [x for x in h.j.of("decision") if x["reasons"] == ["BAR_STALE"]] and not h.sim.submits


# =================================================================================== dry restart (MT-G40)
def test_mt_g40_dry_restart_rebuilds_todays_counters_from_the_dry_journal():
    day = "2026-10-01"
    lines = [{"kind": "would_submit", "ts": f"{day}T10:00:01-04:00", "setup_id": "NOISE_MOM_SPY"},
             {"kind": "fill", "ts": f"{day}T10:00:01-04:00", "cid": "SCALP-A", "side": "buy", "role": "entry",
              "qty": 1, "price": 651.0, "setup_id": "NOISE_MOM_SPY", "symbol": "SPY"},
             {"kind": "fill", "ts": f"{day}T10:30:01-04:00", "cid": "SCALP-B", "side": "sell", "role": "stop",
              "qty": 1, "price": 647.0, "setup_id": "NOISE_MOM_SPY", "symbol": "SPY"},
             {"kind": "trade_closed", "ts": f"{day}T10:30:01-04:00", "setup_id": "NOISE_MOM_SPY", "symbol": "SPY",
              "paper_pnl": -4.0, "honest_pnl": -4.03, "gate_honest_pnl": -4.03, "stop_out": True},
             {"kind": "would_submit", "ts": f"{day}T11:00:01-04:00", "setup_id": "LAST30_MOM_SPY"},
             {"kind": "fill", "ts": f"{day}T11:00:01-04:00", "cid": "SCALP-C", "side": "buy", "role": "entry",
              "qty": 1, "price": 650.0, "setup_id": "LAST30_MOM_SPY", "symbol": "SPY"}]
    c = DayCounters(D, 1e5, cash_prev_close=1e5)
    note = RS.from_journal(lines, c)
    assert c.entry_submits == 2 and c.round_trips == 2 and c.round_trips_by_setup == {"NOISE_MOM_SPY": 1,
                                                                                      "LAST30_MOM_SPY": 1}
    assert c.realized_honest == pytest.approx(-4.03) and c.loss_streak == 1
    assert c.stopout_until[("NOISE_MOM_SPY", "SPY")] == ts("10:45:01")
    assert "position of 1 share(s) open at the restart is gone" in note
    assert RS.from_journal([], DayCounters(D, 1e5)) is None


# =================================================================================== replay fills (MT-G37)
def test_replay_bar_gapping_above_the_target_fills_the_target_at_the_open_like_the_backtest(tmp_path):
    from lab.scalp import signals as sg
    h = H(tmp_path, sim_kw={"fill_mode": "bar"}, mode=Mode.REPLAY)
    enter_noise(h)
    t = h.eng.trade
    h.t = ts("10:02:00")
    gap = Bar("SPY", ts("10:01"), t.target + 0.50, t.target + 0.60, t.stop - 0.10, t.stop + 0.05, 5e3, Feed.SIP)
    h.step(1, {"SPY": [gap]})
    assert h.flat() and h.j.of("trade_closed")[0]["how"] == "target"
    assert sg.bar_exit(1, t.stop, t.target, gap.open, gap.high, gap.low) == (gap.open, "target")
    assert [f["price"] for f in h.j.of("fill") if f["side"] == "sell"] == [round(gap.open, 2)]


# =================================================================================== MT-G33 / G34 report
def _closed(i, honest, how, day="2026-10-01", buy=650.0):
    return [{"kind": "fill", "ts": f"{day}T10:{i:02d}:01-04:00", "setup_id": "NOISE_MOM_SPY", "symbol": "SPY",
             "side": "buy", "qty": 1, "price": buy},
            {"kind": "trade_closed", "ts": f"{day}T11:{i:02d}:01-04:00", "setup_id": "NOISE_MOM_SPY",
             "symbol": "SPY", "lane": "EXPLORATORY", "how": how, "paper_pnl": honest + 0.03, "honest_pnl": honest,
             "buys": [[1, buy]], "qty": 1}]


def test_mt_g33_sigterm_exit_is_not_standard_and_disposition_is_reported():
    lines = _closed(1, 2.0, "target") + _closed(2, 1.5, "SHUTDOWN") + _closed(3, -1.0, "DAILY_STOP")
    text = REP.build_report(lines, REG)
    assert "exits that were not stop/target/time/flatten/daily stop/kill: 1 (must be 0)  <- 1 manual stop" in text
    assert "disposition of exits that were not a pre-set stop/target/time exit: 2 exits, 1 at a profit (50%), " \
           "1 at a loss (50%)" in text
    assert "top-decile volume minute" in text and "n/a" in text


def test_mt_g33_top_decile_volume_entries_are_counted_and_flagged():
    idx = [as_ny(f"{d.date()} 10:01") for d in pd.bdate_range("2026-09-02", "2026-10-01")]
    vol = [100.0] * (len(idx) - 1) + [1_000.0]
    df = pd.DataFrame({"open": 650.0, "high": 650.1, "low": 649.9, "close": 650.0, "volume": vol},
                      index=pd.DatetimeIndex(idx))
    trades = REP._trades(_closed(1, 1.0, "target"))
    assert REP.volume_share(trades, {"SPY": df}) == (1, 1)
    text = "\n".join(REP.bias_block(trades, [], {"SPY": df}))
    assert "1 of 1 (100%)  <- FLAG" in text


def test_mt_g34_exposure_matched_spy_uses_the_same_dollars_and_minutes():
    idx = pd.DatetimeIndex([ts("10:01"), ts("11:01")])
    spy = pd.DataFrame({"open": [650.0, 651.0], "high": 652.0, "low": 649.0, "close": [650.5, 656.5],
                        "volume": 1.0}, index=idx)
    trades = REP._trades(_closed(1, 1.0, "target"))
    total, n = REP.exposure_matched_spy(trades, spy)
    assert n == 1 and total == pytest.approx(650.0 * (656.5 / 650.0 - 1))
    assert "exposure-matched SPY (same dollars, same minutes held): $6.50 over 1 trades" in "\n".join(
        REP.buckets_block(trades, spy))
