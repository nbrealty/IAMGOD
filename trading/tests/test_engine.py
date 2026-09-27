"""Engine unit tests: the old intents (end-to-end rules run, Claude book inside limits, failure holds, dry run,
scaling to the sleeve weight, crypto sleeve) rewritten for the v2 schema and next-open fills, plus the
context layout (ctx-2) and the CLI."""
import copy
import json

import pandas as pd
import pytest

from conftest import make_bars
from trader import decisions, ledger, risk
from trader import __main__ as cli
from trader.broker import SimBroker
from trader.config import Config
from trader.engine import decision_to_targets, normalize_weights, rules_sleeve_weights, run_book
from trader.llm import ClaudeError
from trader.models import Lot
from trader.schemas import Action, ClaudeDecision, Prediction, RulesReview, SleeveWeightChoices, WeightChoice
from trader.state import BookState


class FakeAdvisor:
    """Returns lists of samples, as both real advisors do."""

    def __init__(self, decisions=None, reviews=None, fail=False):
        self.decisions, self.reviews, self.fail, self.contexts = decisions or [], reviews, fail, []

    def _meta(self, n, role):
        return {"mode": "session", "role": role, "model": "fake", "samples_requested": n, "samples_valid": n,
                "prompt_version": "pv-test", "usd": 0.0}

    def review_rules_plan(self, ctx):
        self.contexts.append(ctx)
        if self.fail:
            raise ClaudeError("boom", meta=self._meta(0, "review"))
        reviews = self.reviews or [RulesReview(journal_note="rules ok", date=ctx["date"])]
        return reviews, self._meta(len(reviews), "review")

    def decide(self, ctx):
        self.contexts.append(ctx)
        if self.fail:
            raise ClaudeError("boom")
        ds = [d(ctx) if callable(d) else d for d in self.decisions]
        return ds, self._meta(len(ds), "decide")


def _sim(cfg, state, bars, cash=100_000.0):
    state.sim = state.sim or {"cash": cash, "positions": {}}
    return SimBroker(state.sim, risk.last_valid_closes(bars), ledger.cost_model(cfg, state), cfg.asset_class,
                     bars=bars, cost_in_price=False)


def _upto(bars, d):
    return {s: df[df.index <= d] for s, df in bars.items()}


def _held(state):
    out = {}
    for lots in state.lots.values():
        for s, lot in lots.items():
            out[s] = out.get(s, 0.0) + lot.qty
    return out


def test_rules_book_end_to_end(cfg, bars, tmp_path):
    d1, d2 = bars["SPY"].index[-2], bars["SPY"].index[-1]
    state = BookState.load("rules", tmp_path)
    advisor = FakeAdvisor()
    b1 = _upto(bars, d1)
    e = run_book("rules", cfg, b1, _sim(cfg, state, b1), advisor, d1, tmp_path, state=state)
    assert e["orders"], e["risk_log"]
    assert advisor.contexts and "rule_signals" in advisor.contexts[0]
    saved = BookState.load("rules", tmp_path)
    assert saved.lots == {} and len(saved.pending_orders) == len(e["orders"])  # EX-4: nothing until filled

    # Next run: the orders fill at d2's open and the lots match the simulator exactly.
    e2 = run_book("rules", cfg, bars, _sim(cfg, saved, bars), advisor, d2, tmp_path, state=saved)
    assert len(e2["settled_fills"]) >= len(e["orders"])
    saved = BookState.load("rules", tmp_path)
    held = _held(saved)
    for s, q in saved.sim["positions"].items():
        if q > 1e-9 and not any(p["symbol"] == s for p in saved.pending_orders):
            assert held.get(s, 0) == pytest.approx(q, abs=1e-6)
    for f in saved.fills[: len(e["orders"])]:
        assert f["fill"] == pytest.approx(float(bars[f["symbol"]].loc[d2, "open"]))
    equity = saved.sim["cash"] + sum(q * bars[s]["close"].iloc[-1] for s, q in saved.sim["positions"].items())
    assert saved.sim["cash"] >= 0.04 * equity  # cash buffer respected
    # Same date again is skipped.
    again = run_book("rules", cfg, bars, _sim(cfg, saved, bars), advisor, d2, tmp_path, state=saved)
    assert "skipped" in again


def _eligible_b(cfg, bars):
    elig = decisions.eligibility(cfg, bars, {"A": 1, "B": 1, "C": 1, "D": 1})["B"]
    return sorted(elig)[0]


def test_claude_book_follows_decision_within_limits(cfg, bars, tmp_path):
    """Menus in, numbers out: weights move one step, D stays off, ineligible or unknown actions are dropped,
    stops respect the rule floor and the per-trade cap."""
    sym = _eligible_b(cfg, bars)

    def decide(ctx):
        return ClaudeDecision(
            date=ctx["date"], market_view="test", journal_note="note",
            sleeve_weights=SleeveWeightChoices(A=WeightChoice(choice="up"), D=WeightChoice(choice="up")),
            actions=[
                Action(symbol="AAPL", sleeve="A", size="pct", target_pct_equity=0.05, reason_code="REGIME_RISK",
                       evidence=["regime.label"], prediction_id="p1"),
                Action(symbol="BTC/USD", sleeve="D", size="pct", target_pct_equity=0.05,
                       reason_code="TREND_STRENGTHENING", evidence=["regime.label"], prediction_id="p1"),
                Action(symbol=sym, sleeve="B", size="pct", target_pct_equity=0.9, stop="tight",
                       reason_code="MEAN_REVERSION_SETUP", evidence=[f"rule_signals.B.indicators[{sym}].rsi2"],
                       prediction_id="p1", rationale="dip"),
            ],
            predictions=[Prediction(id="p1", symbol=sym, horizon=5, direction="above", threshold_pct=1.0,
                                    probability=0.6, linked_decision=f"action:B:{sym}")])

    as_of = bars["SPY"].index[-1]
    state = BookState.load("claude", tmp_path)
    e = run_book("claude", cfg, bars, _sim(cfg, state, bars), FakeAdvisor([decide]), as_of, tmp_path, state=state)
    prev = e["rule_weights"]
    assert e["sleeve_weights"]["A"] == pytest.approx(min(prev["A"] + 0.05, 0.60), abs=1e-9)  # one step, max 0.60
    assert e["sleeve_weights"]["D"] == 0
    problems = " ".join(p for s in e["samples"] for p in s["problems"])
    assert "action A:AAPL: dropped (sleeve A may only buy its assets and BIL" in problems  # CL-11
    assert "action D:BTC/USD: dropped" in problems and "weight D: 'up' refused" in problems
    assert "AAPL" not in {o["symbol"] for o in e["orders"]}
    assert "BTC/USD" not in {o["symbol"] for o in e["orders"]}
    order = [o for o in e["orders"] if o["symbol"] == sym]
    assert order, e["risk_log"]
    assert order[0]["qty"] * order[0]["price"] <= 0.30 * e["equity"] + 1  # ETF notional cap
    pending = BookState.load("claude", tmp_path).pending_orders
    alloc = [a for p in pending if p["symbol"] == sym for a in p["alloc"] if a["sleeve"] == "B"][0]
    rule = decisions.stop_menu("B", bars[sym], cfg.policy)["rule"]
    assert alloc["stop"] >= rule - 1e-9  # CL-14: tight is above the rule floor
    assert (order[0]["price"] - alloc["stop"]) * alloc["delta_qty"] <= 0.005 * e["equity"] + 1e-6  # RISK-2
    assert e["deviations"] and e["deviations"][0]["symbol"] == sym
    assert BookState.load("claude", tmp_path).notes[-1]["note"] == "note"


def test_claude_failure_holds_positions(cfg, bars, tmp_path):
    as_of = bars["SPY"].index[-1]
    state = BookState.load("claude", tmp_path)
    e = run_book("claude", cfg, bars, _sim(cfg, state, bars), FakeAdvisor(fail=True), as_of, tmp_path, state=state)
    assert e["orders"] == []
    assert e["claude_error"] == "boom"


def test_dry_run_saves_nothing(cfg, bars, tmp_path):
    as_of = bars["SPY"].index[-1]
    state = BookState.load("rules", tmp_path)
    broker = _sim(cfg, state, bars)
    e = run_book("rules", cfg, bars, broker, None, as_of, tmp_path, dry_run=True, state=state)
    assert e["orders"] and e["fills"] == []
    assert not BookState.path("rules", tmp_path).exists()
    assert state.sim["positions"] == {} and not state.sim.get("open_orders")


def test_decision_scaled_to_sleeve_weight(cfg, bars):
    sym = _eligible_b(cfg, bars)
    d = ClaudeDecision(market_view="", journal_note="",
                       actions=[Action(symbol=sym, sleeve="B", size="pct", target_pct_equity=0.3,
                                       reason_code="MEAN_REVERSION_SETUP", evidence=["rule_signals.B.x"],
                                       prediction_id="p1")],
                       predictions=[Prediction(id="p1", symbol=sym, horizon=5, direction="above",
                                               threshold_pct=1.0, probability=0.6,
                                               linked_decision=f"action:B:{sym}")])
    log = []
    ctx = {"rule_signals": {"B": {"x": 1}}}
    targets, weights = decision_to_targets(cfg, d, {}, bars, 10000, log, ctx=ctx, weights={"B": 0.15},
                                           permissions={"A": 1, "B": 1, "C": 1, "D": 1})
    [t] = [t for t in targets if t.symbol == sym]
    assert t.qty * bars[sym]["close"].iloc[-1] == pytest.approx(weights["B"] * 10000)
    # Without a context nothing can be checked: the action is dropped and the key follows the rule (nothing).
    targets, _ = decision_to_targets(cfg, d, {}, bars, 10000, [], weights={"B": 0.15},
                                     permissions={"A": 1, "B": 1, "C": 1, "D": 1})
    assert all(t.qty == 0 for t in targets if t.symbol == sym)


def test_crypto_sleeve_when_enabled(cfg, tmp_path):
    pb = copy.deepcopy(cfg.playbook)
    pb["sleeves"]["D"]["enabled"] = True
    cfg_d = Config(playbook=pb, policy=cfg.policy)
    bars = {s: make_bars(seed=i + 1, drift=0.002 if "/" in s else 0.0005, vol=0.01, crypto="/" in s)
            for i, s in enumerate(cfg_d.allowlist())}
    as_of = bars["SPY"].index[-1]
    state = BookState.load("rules", tmp_path)
    e = run_book("rules", cfg_d, bars, _sim(cfg_d, state, bars), None, as_of, tmp_path, state=state)
    crypto = [o for o in e["orders"] if "/" in o["symbol"]]
    assert crypto, e["risk_log"]
    for o in crypto:
        assert o["qty"] * o["price"] <= 0.05 * 100000 + 1
    pending = BookState.load("rules", tmp_path).pending_orders
    alloc = [a for p in pending if p["symbol"] == crypto[0]["symbol"] for a in p["alloc"]][0]
    assert alloc["sleeve"] == "D" and alloc["stop"] is not None and alloc["stop"] < crypto[0]["price"]


# --- weights --------------------------------------------------------------------------------------


def test_weights_go_through_cap_weights(cfg, bars):
    w = normalize_weights(cfg, {"A": 0.9, "B": 0.5, "C": 0.5, "D": 0.5})
    assert w == decisions.cap_weights(cfg, {"A": 0.9, "B": 0.5, "C": 0.5, "D": 0.5})
    assert w["D"] == 0 and w["C"] + w["D"] <= 0.20 + 1e-12 and sum(w.values()) <= 0.95 + 1e-12
    r = rules_sleeve_weights(cfg, bars, demoted={"C": "half"})
    assert r["C"] <= cfg.sleeves["C"]["min"] + 1e-12  # M-11: demoted to its min
    assert r["B"] <= cfg.sleeve_weight_cap("B") + 1e-12  # RISK-8 probation cap


# --- context ctx-2 --------------------------------------------------------------------------------


def _ctx(cfg, bars, tmp_path, book):
    state = BookState.load(book, tmp_path)
    as_of = bars["SPY"].index[-1]
    adv = FakeAdvisor(reviews=None, decisions=[lambda c: ClaudeDecision(date=c["date"], market_view="",
                                                                        journal_note="")])
    run_book(book, cfg, bars, _sim(cfg, state, bars), adv, as_of, tmp_path, dry_run=True, state=state)
    return adv.contexts[0]


def test_context_layout_claude(cfg, bars, tmp_path):
    ctx = _ctx(cfg, bars, tmp_path, "claude")
    json.dumps(ctx, allow_nan=False)  # JSON-safe, no NaN
    for key in ("context_schema", "prompt_version", "date", "book", "broker", "simulated", "account", "regime",
                "sleeve_bounds", "weights", "positions", "rule_signals", "menus", "allowlist", "reason_codes",
                "limits", "data_problems", "data_feed", "performance", "scorecard", "recent_notes"):
        assert key in ctx, key
    assert ctx["context_schema"] == "ctx-3" and ctx["broker"] == "sim" and ctx["simulated"] is True
    for key in ("day_pnl_pct", "week_pnl_pct", "month_pnl_pct", "watch", "monthly_block", "sleeve_risk_mult",
                "open_risk_heat_pct", "stress", "one_R_by_sleeve"):
        assert key in ctx["account"], key
    assert "one_R_dollars" not in ctx["account"]  # the default-rate 1R was wrong for a promoted sleeve
    assert set(ctx["weights"]["menu"]["B"]) == {"keep", "up", "down", "rule", "default"}
    assert ctx["weights"]["change_allowed"] == {s: True for s in "ABCD"}
    assert "temperature" in ctx["regime"] and "permissions" in ctx["regime"]
    assert len(ctx["rule_signals"]["C"]["indicators"]) <= 15
    some = next(iter(ctx["menus"].values()))
    assert {"price", "current_pct", "rule_pct", "half_rule_pct", "eligible_increase", "stops"} <= set(some)
    assert ctx["menus"]["D:BTC/USD"]["eligible_increase"] is False if "D:BTC/USD" in ctx["menus"] else True
    assert "per_sleeve" in ctx["performance"] and "B" in ctx["performance"]["per_sleeve"]
    assert "Longest losing streak" in ctx["performance"]["losing_streak_brief"]
    assert set(ctx["scorecard"]) == {"predictions", "deviations", "vetoes"}
    assert "planned_increases" not in ctx


def test_context_layout_rules(cfg, bars, tmp_path):
    ctx = _ctx(cfg, bars, tmp_path, "rules")
    json.dumps(ctx, allow_nan=False)
    assert "planned_increases" in ctx and "menus" not in ctx and "weights" not in ctx
    assert all(p["sleeve"] in ("B", "C", "D") for p in ctx["planned_increases"])
    assert ctx["reason_codes"]["skip"] == list(decisions.SKIP_CODES)


def test_restricted_veto_codes_show_in_context(cfg, bars, tmp_path):
    state = BookState.load("rules", tmp_path)
    state.veto_codes_restricted = True
    state.save(tmp_path)
    ctx = _ctx(cfg, bars, tmp_path, "rules")
    assert ctx["reason_codes"]["skip"] == ["DATA_SUSPECT", "HALT_OR_ILLIQUID"]


def test_positions_failure_sends_no_orders(cfg, bars, tmp_path):
    state = BookState.load("rules", tmp_path)
    broker = _sim(cfg, state, bars)

    def boom():
        raise RuntimeError("positions endpoint down")

    broker.positions = boom
    e = run_book("rules", cfg, bars, broker, None, bars["SPY"].index[-1], tmp_path, state=state)
    assert e["orders"] == [] and any("positions unavailable" in line for line in e["risk_log"])


def test_lots_reconcile_against_broker_with_state(cfg, bars, tmp_path):
    """A broker short of what the book expects books a reconcile reduction with P&L (no silent rescale)."""
    as_of = bars["SPY"].index[-1]
    state = BookState.load("rules", tmp_path)
    px = float(bars["IEF"]["close"].iloc[-1])
    state.lots = {"A": {"IEF": Lot(10.0, px * 0.9, "2026-01-02")}}
    state.sim = {"cash": 100_000.0, "positions": {"IEF": 5.0}}
    run_book("rules", cfg, bars, _sim(cfg, state, bars), None, as_of, tmp_path, dry_run=True, state=state)
    ev = [e for e in state.lots["A"]["IEF"].events if e["reason"] == "reconcile"]
    assert ev and state.lots["A"]["IEF"].qty == pytest.approx(5.0)
    assert state.lots["A"]["IEF"].realized_pnl == pytest.approx(5 * (px - px * 0.9))


class _NoTouchSim(SimBroker):
    """A simulator that fails the test if anything sends or cancels an order."""

    def submit(self, *a, **k):
        raise AssertionError("submit called")

    def cancel_open_orders(self):
        raise AssertionError("cancel_open_orders called")


def test_dry_run_and_prepare_never_touch_broker_orders(cfg, bars, tmp_path):
    from trader.engine import prepare_book

    d1, d2 = bars["SPY"].index[-2], bars["SPY"].index[-1]
    b1 = _upto(bars, d1)
    for book in ("rules", "claude"):
        adv = FakeAdvisor([lambda c: ClaudeDecision(date=c["date"], market_view="m", journal_note="j")])
        state = BookState.load(book, tmp_path)
        run_book(book, cfg, b1, _sim(cfg, state, b1), adv, d1, tmp_path, state=state)
        saved = BookState.load(book, tmp_path)
        assert saved.pending_orders, book  # so the cancel branch in step 1 is reachable
        before = BookState.path(book, tmp_path).read_text()
        for call in ("prepare", "dry"):
            st = BookState.load(book, tmp_path)
            st.sim = st.sim or {"cash": 100_000.0, "positions": {}}
            broker = _NoTouchSim(st.sim, risk.last_valid_closes(bars), ledger.cost_model(cfg, st), cfg.asset_class,
                                 bars=bars, cost_in_price=False)
            if call == "prepare":
                prepare_book(book, cfg, bars, broker, d2, tmp_path, state=st)
            else:
                e = run_book(book, cfg, bars, broker, adv, d2, tmp_path, state=st, dry_run=True)
                assert e["dry_run"] and e["fills"] == []
        assert BookState.path(book, tmp_path).read_text() == before  # nothing saved


def test_kill_file_blocks_entries_in_run_book(cfg, bars, tmp_path):
    from trader.state import set_kill_switch

    as_of = bars["SPY"].index[-1]
    plain = BookState.load("rules", tmp_path / "plain")
    e = run_book("rules", cfg, bars, _sim(cfg, plain, bars), None, as_of, tmp_path / "plain", state=plain,
                 dry_run=True)
    assert any(o["side"] == "buy" for o in e["orders"])  # without the kill switch the rules would buy

    set_kill_switch(True, tmp_path)
    state = BookState.load("rules", tmp_path)
    sym = cfg.sleeves["B"]["symbols"][0]
    px = float(bars[sym]["close"].iloc[-1])
    state.lots = {"B": {sym: Lot(4.0, px * 1.05, bars["SPY"].index[-3].date().isoformat(), px * 1.01, px * 1.01)}}
    state.sim = {"cash": 100_000.0 - 4 * px, "positions": {sym: 4.0}}
    e = run_book("rules", cfg, bars, _sim(cfg, state, bars), None, as_of, tmp_path, state=state)
    assert e["orders"] and all(o["side"] == "sell" and o["symbol"] == sym for o in e["orders"]), e["orders"]
    assert "kill switch is on" in e["breakers"]["reasons"]


# --- CLI ---------------------------------------------------------------------------------------------


def test_sim_books_parsing():
    assert cli.sim_books(None, ("rules", "claude")) == set()
    assert cli.sim_books([], ("rules", "claude")) == {"rules", "claude"}
    assert cli.sim_books(["claude"], ("rules", "claude")) == {"claude"}


def test_partial_bar_is_dropped_before_the_close():
    idx = pd.to_datetime(["2026-09-24", "2026-09-25"])
    bars = {"SPY": pd.DataFrame({"close": [1.0, 2.0]}, index=idx)}
    out, note = cli.drop_partial_bar(bars, pd.Timestamp("2026-09-25 11:00", tz="America/New_York"))
    assert len(out["SPY"]) == 1 and note
    out, note = cli.drop_partial_bar(bars, pd.Timestamp("2026-09-25 16:30", tz="America/New_York"))
    assert len(out["SPY"]) == 2 and note is None
    # the SIP feed lags 16 minutes: at 16:15 today's bar does not have the closing auction yet
    out, note = cli.drop_partial_bar(bars, pd.Timestamp("2026-09-25 16:15", tz="America/New_York"))
    assert len(out["SPY"]) == 1 and note
    from trader.data import SIP_DELAY

    settled = pd.Timestamp("2026-09-25").replace(hour=cli.CLOSE_SETTLED[0], minute=cli.CLOSE_SETTLED[1])
    assert settled >= pd.Timestamp("2026-09-25 16:00") + SIP_DELAY + pd.Timedelta(minutes=5)
    out, note = cli.drop_partial_bar(bars, pd.Timestamp("2026-09-26 09:00", tz="America/New_York"))
    assert len(out["SPY"]) == 2 and note is None


def test_cli_run_prepare_status_report_with_sim(cfg, bars, tmp_path, monkeypatch, capsys):
    """The whole CLI on the simulator with synthetic bars (no network, no Alpaca)."""
    monkeypatch.setattr(cli, "STATE_DIR", tmp_path)
    d1 = bars["SPY"].index[-2]
    monkeypatch.setattr(cli, "fetch_bars", lambda c: (_upto(bars, d1), {"feed_used": "test", "notes": []}))
    assert cli.main(["prepare", "--book", "claude", "--sim"]) == 0
    assert (tmp_path / "claude" / "pending" / d1.date().isoformat() / "context.json").exists()
    assert cli.main(["run", "--sim", "--session"]) == 0
    out = capsys.readouterr().out
    assert "SIMULATED" in out and "none found" in out
    monkeypatch.setattr(cli, "fetch_bars", lambda c: (bars, {"feed_used": "test", "notes": []}))
    assert cli.main(["run", "--sim", "--no-claude"]) == 0
    assert cli.main(["status"]) == 0
    assert cli.main(["report"]) == 0
    assert cli.main(["report", "--json"]) == 0
    out = capsys.readouterr().out
    assert "rules" in out and BookState.load("rules", tmp_path).fills


def test_cli_owner_commands(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "STATE_DIR", tmp_path)
    s = BookState(book="rules", sleeve_blocked={"C": "drawdown"}, veto_codes_restricted=True,
                  sleeve_pnl={"C": {"realized": -6000.0, "cum": -6000.0, "peak": 0.0}})
    s.save(tmp_path)
    assert cli.main(["sleeve-reset", "C", "--book", "rules"]) == 0
    assert cli.main(["veto-reset", "--book", "rules"]) == 0
    s = BookState.load("rules", tmp_path)
    assert s.sleeve_blocked == {} and s.sleeve_pnl["C"]["peak"] == -6000.0
    assert s.veto_codes_restricted is False and s.veto_reset_date
    assert cli.main(["promote", "C", "--book", "rules"]) == 1  # refused without the owner flag
    assert BookState.load("rules", tmp_path).promoted_sleeves == []
    assert cli.main(["promote", "C", "--book", "rules", "--i-am-the-owner"]) == 0
    assert BookState.load("rules", tmp_path).promoted_sleeves == ["C"]
    assert cli.main(["demote", "C", "--book", "rules", "--i-am-the-owner"]) == 0
    assert BookState.load("rules", tmp_path).promoted_sleeves == []
    # M-12: at most one promotion per sleeve per quarter; a demotion is always allowed.
    assert cli.main(["promote", "C", "--book", "rules", "--i-am-the-owner"]) == 1
    assert "at most one promotion" in capsys.readouterr().out
    s = BookState.load("rules", tmp_path)
    assert s.promoted_sleeves == [] and [p["sleeve"] for p in s.promotions] == ["C"]
    assert cli.main(["promote", "D", "--book", "rules", "--i-am-the-owner"]) == 0  # another sleeve is fine
    s = BookState.load("rules", tmp_path)
    s.promotions = [{"date": "2000-01-03", "sleeve": "C"}]  # last quarter's promotion does not count
    s.save(tmp_path)
    assert cli.main(["promote", "C", "--book", "rules", "--i-am-the-owner"]) == 0
    assert BookState.load("rules", tmp_path).promoted_sleeves == ["D", "C"]
    c = BookState(book="claude", deviations_restricted=True)
    c.save(tmp_path)
    assert cli.main(["deviation-reset"]) == 0
    assert BookState.load("claude", tmp_path).deviations_restricted is False
    assert "NOT passed" in capsys.readouterr().out


def test_decision_file_needs_a_single_book(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STATE_DIR", tmp_path)
    with pytest.raises(SystemExit):
        cli.main(["run", "--sim", "--decision-file", "x.json"])


def test_unexpected_advisor_failure_falls_back_safely(cfg, bars, tmp_path):
    """Anything but a clean answer: the Claude book holds, the rules book runs unreviewed."""

    class Broken:
        def decide(self, ctx):
            raise RuntimeError("network down")

        def review_rules_plan(self, ctx):
            raise RuntimeError("network down")

    as_of = bars["SPY"].index[-1]
    s = BookState.load("claude", tmp_path)
    e = run_book("claude", cfg, bars, _sim(cfg, s, bars), Broken(), as_of, tmp_path, dry_run=True, state=s)
    assert e["orders"] == [] and "network down" in e["claude_error"]
    s = BookState.load("rules", tmp_path)
    plain = run_book("rules", cfg, bars, _sim(cfg, s, bars), None, as_of, tmp_path, dry_run=True, state=s)
    s = BookState.load("rules", tmp_path)
    e = run_book("rules", cfg, bars, _sim(cfg, s, bars), Broken(), as_of, tmp_path, dry_run=True, state=s)
    assert [o["symbol"] for o in e["orders"]] == [o["symbol"] for o in plain["orders"]]


def test_new_state_fields_survive_save_and_load(tmp_path):
    s = BookState(book="claude", veto_reset_date="2026-09-01", deviations_restricted=True,
                  deviations_reset_date="2026-09-02")
    s.save(tmp_path)
    t = BookState.load("claude", tmp_path)
    assert (t.veto_reset_date, t.deviations_restricted, t.deviations_reset_date) == ("2026-09-01", True,
                                                                                      "2026-09-02")


def test_a_book_never_switches_between_simulator_and_alpaca(cfg, bars, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "STATE_DIR", tmp_path)
    sim_state = BookState(book="claude", sim={"cash": 1.0, "positions": {}})
    with pytest.raises(SystemExit, match="simulator"):
        cli.make_broker("claude", cfg, sim_state, bars, simulate=False)
    live_state = BookState(book="rules", lots={"A": {"SPY": Lot(1.0, 100.0, "2026-09-01")}})
    with pytest.raises(SystemExit, match="Alpaca"):
        cli.make_broker("rules", cfg, live_state, bars, simulate=True)
    fresh = BookState(book="claude")
    broker = cli.make_broker("claude", cfg, fresh, bars, simulate=True)
    assert broker.name == "sim" and broker.fill_mode == "next_open" and broker.cost_in_price is False
    assert fresh.sim["cash"] == cfg.playbook["simulation"]["starting_cash"]


def test_guide_rule_6_latch_makes_the_claude_book_follow_the_rules(cfg, bars, tmp_path):
    sym = _eligible_b(cfg, bars)
    s = BookState.load("claude", tmp_path)
    s.deviations_restricted = True
    decide = lambda c: ClaudeDecision(  # noqa: E731
        date=c["date"], market_view="", journal_note="",
        actions=[Action(symbol=sym, sleeve="B", size="pct", target_pct_equity=0.05, reason_code="MEAN_REVERSION_SETUP",
                        evidence=[f"rule_signals.B.indicators[{sym}].rsi2"], prediction_id="p1")],
        predictions=[Prediction(id="p1", symbol=sym, horizon=5, direction="above", threshold_pct=1.0,
                                probability=0.6, linked_decision=f"action:B:{sym}")])
    e = run_book("claude", cfg, bars, _sim(cfg, s, bars), FakeAdvisor([decide]), bars["SPY"].index[-1], tmp_path,
                 dry_run=True, state=s)
    assert sym not in {o["symbol"] for o in e["orders"]} and e["orders"]  # rule targets only
    assert any("deviations are restricted" in line for line in e["risk_log"])


# --- M-13 experiment log (finding #10) -------------------------------------------------------------------


def test_log_experiment_dedups_by_kind_and_version(tmp_path):
    from trader.state import log_experiment

    assert log_experiment({"kind": "params", "version": "a"}, tmp_path)
    assert not log_experiment({"kind": "params", "version": "a"}, tmp_path)
    assert log_experiment({"kind": "prompt:decide", "version": "a"}, tmp_path)
    assert log_experiment({"kind": "params", "version": "b"}, tmp_path)
    assert len((tmp_path / "experiments.jsonl").read_text().splitlines()) == 3


def test_run_logs_prompt_and_params_once(cfg, bars, tmp_path):
    d1, d2 = bars["SPY"].index[-2], bars["SPY"].index[-1]
    adv = FakeAdvisor()
    for d in (d1, d2):
        state = BookState.load("rules", tmp_path)
        b = _upto(bars, d)
        run_book("rules", cfg, b, _sim(cfg, state, b), adv, d, tmp_path, state=state)
    rows = [json.loads(x) for x in (tmp_path / "experiments.jsonl").read_text().splitlines()]
    assert sorted(r["kind"] for r in rows) == ["params", "prompt:review"]


def test_one_failed_book_does_not_stop_the_other(cfg, bars, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "STATE_DIR", tmp_path)
    monkeypatch.setattr(cli, "fetch_bars", lambda c: (bars, {"feed_used": "test", "notes": []}))
    real = cli.run_book

    def flaky(book, *a, **k):
        if book == "rules":
            raise RuntimeError("rules book broke")
        return real(book, *a, **k)

    monkeypatch.setattr(cli, "run_book", flaky)
    assert cli.main(["run", "--sim", "--no-claude", "--dry-run"]) == 1
    out = capsys.readouterr().out
    assert "[rules] FAILED: RuntimeError: rules book broke" in out and "=== claude book" in out
    with pytest.raises(RuntimeError):  # a single book still fails loudly
        cli.main(["run", "--book", "rules", "--sim", "--no-claude", "--dry-run"])
