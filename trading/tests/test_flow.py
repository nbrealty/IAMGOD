"""End-to-end daily flow over consecutive dates on the simulator with next-open fills (INTEGRATION_SPEC I1).

Each test slices one synthetic history to successive dates and runs the book once per date, the way the
scheduled session does: prepare -> decision files -> run, then the next day settles yesterday's orders.
"""
import json

import numpy as np
import pandas as pd
import pytest

from conftest import make_bars
from trader import decisions, ledger, risk, session
from trader.broker import SimBroker
from trader.engine import prepare_book, run_book
from trader.models import Lot
from trader.regime import classify, classify_kwargs
from trader.schemas import Action, ClaudeDecision, Prediction, RulesReview, Skip
from trader.session import SessionAdvisor
from trader.state import BookState

CASH = 100_000.0


@pytest.fixture(scope="module")
def world():
    from trader.config import load_config

    cfg = load_config()
    bars = {s: make_bars(n=900, seed=i + 1, drift=0.0005, crypto="/" in s) for i, s in enumerate(cfg.data_symbols())}
    return cfg, bars


def upto(bars, d):
    return {s: df[df.index <= d] for s, df in bars.items()}


class Book:
    """Runs one book day after day on a fresh SimBroker built from the saved state, like the CLI does."""

    def __init__(self, cfg, bars, book, tmp_path):
        self.cfg, self.bars, self.book, self.dir = cfg, bars, book, tmp_path

    def state(self):
        return BookState.load(self.book, self.dir)

    def broker(self, state, b):
        if not state.sim:
            state.sim = {"cash": CASH, "positions": {}}
        return SimBroker(state.sim, risk.last_valid_closes(b), ledger.cost_model(self.cfg, state), self.cfg.asset_class,
                         bars=b, fill_mode="next_open", cost_in_price=False)

    def run(self, d, advisor=None, state=None, **kw):
        state = state or self.state()
        b = upto(self.bars, d)
        return run_book(self.book, self.cfg, b, self.broker(state, b), advisor, d, self.dir, state=state, **kw)

    def prepare(self, d, samples=None):
        state = self.state()
        b = upto(self.bars, d)
        return prepare_book(self.book, self.cfg, b, self.broker(state, b), d, self.dir, state=state, samples=samples)


class Fake:
    def __init__(self, *items):
        self.items, self.contexts = list(items), []

    def _meta(self, role):
        return {"mode": "session", "role": role, "model": "fake", "samples_requested": len(self.items),
                "samples_valid": len(self.items), "prompt_version": f"pv-{role}", "usd": 0.0}

    def decide(self, ctx):
        self.contexts.append(ctx)
        return [f(ctx) if callable(f) else f for f in self.items], self._meta("decide")

    def review_rules_plan(self, ctx):
        self.contexts.append(ctx)
        return [f(ctx) if callable(f) else f for f in self.items], self._meta("review")


def pred(sym, pid="p1", link=None, horizon=5):
    return Prediction(id=pid, symbol=sym, horizon=horizon, direction="above", threshold_pct=1.0, probability=0.6,
                      linked_decision=link or f"action:B:{sym}")


def b_action(sym, size, pct=0.0, with_pred=True):
    return Action(symbol=sym, sleeve="B", size=size, target_pct_equity=pct, reason_code="MEAN_REVERSION_SETUP",
                  evidence=[f"rule_signals.B.indicators[{sym}].rsi2"], prediction_id="p1" if with_pred else "",
                  rationale="test")


def decision(ctx, actions=(), predictions=()):
    return ClaudeDecision(date=ctx["date"], market_view="test", journal_note="note", actions=list(actions),
                          predictions=list(predictions))


def eligible_b(cfg, bars, d):
    return sorted(decisions.eligibility(cfg, upto(bars, d), {"A": 1, "B": 1, "C": 1, "D": 1})["B"])[0]


def trades(state, sleeve, sym):
    return [t for t in state.closed_trades if t["sleeve"] == sleeve and t["symbol"] == sym]


# --- money bookkeeping ------------------------------------------------------------------------------


def test_add_partial_sell_close_gives_one_trade_with_the_right_r(world, tmp_path):
    cfg, bars = world
    d = list(bars["SPY"].index[-5:])
    sym = eligible_b(cfg, bars, d[0])
    book = Book(cfg, bars, "claude", tmp_path)
    buy = Fake(lambda c: decision(c, [b_action(sym, "pct", 0.05)], [pred(sym)]))
    book.run(d[0], buy)
    s = book.state()
    assert s.lots.get("B", {}).get(sym) is None and any(p["symbol"] == sym for p in s.pending_orders)

    trim = Fake(lambda c: decision(c, [b_action(sym, "pct", 0.025)], [pred(sym)]))
    e1 = book.run(d[1], trim)
    s = book.state()
    lot = s.lots["B"][sym]
    open1 = float(bars[sym].loc[d[1], "open"])
    close0 = float(bars[sym].loc[d[0], "close"])
    assert lot.entry_price == pytest.approx(open1)  # EX-4: the next open, not the signal close
    assert lot.entry_date == d[0].date().isoformat() and lot.fill_date == d[1].date().isoformat()
    q1, stop = lot.qty, lot.initial_stop
    assert lot.initial_risk_dollars == pytest.approx(q1 * max(open1 - stop, close0 - stop))
    [row] = [f for f in s.fills if f["symbol"] == sym]
    assert row["slippage_bps"] == pytest.approx((open1 / close0 - 1) * 1e4, abs=0.01)
    assert row["gap_R"] == pytest.approx((open1 - close0) / (close0 - stop), abs=1e-4)
    assert [o for o in e1["orders"] if o["symbol"] == sym][0]["side"] == "sell"

    out = Fake(lambda c: decision(c, [b_action(sym, "exit")], [pred(sym)]))
    book.run(d[2], out)
    s = book.state()
    lot = s.lots["B"][sym]
    open2 = float(bars[sym].loc[d[2], "open"])
    sold1 = q1 - lot.qty
    assert 0 < sold1 < q1
    assert lot.realized_pnl == pytest.approx(sold1 * (open2 - open1))  # partial sale realizes P&L (M-3)
    assert not trades(s, "B", sym)

    book.run(d[3])
    s = book.state()
    assert "B" not in s.lots or sym not in s.lots["B"]
    [t] = trades(s, "B", sym)  # exactly one record for the whole lot
    open3 = float(bars[sym].loc[d[3], "open"])
    bps = cfg.policy["turnover"]["cost_model_per_side_bps"]["etf"] / 1e4
    realized = sold1 * (open2 - open1) + (q1 - sold1) * (open3 - open1)
    costs = bps * (q1 * open1 + sold1 * open2 + (q1 - sold1) * open3)
    risk0 = q1 * max(open1 - stop, close0 - stop)
    assert t["pnl"] == pytest.approx(realized - costs, abs=0.01)
    assert t["R"] == pytest.approx((realized - costs) / risk0, abs=1e-3)
    assert t["tags"]["mode"] == "session" and t["tags"]["prompt_version"] == "pv-decide"  # CL-3
    # The simulator's cash moved by exactly the same fills and costs.
    assert s.sim["positions"].get(sym, 0.0) == pytest.approx(0.0, abs=1e-6)


def test_rules_book_lots_match_the_simulator_every_day(world, tmp_path):
    cfg, bars = world
    book = Book(cfg, bars, "rules", tmp_path)
    for d in bars["SPY"].index[-4:]:
        book.run(d)
        s = book.state()
        held = {}
        for lots in s.lots.values():
            for sym, lot in lots.items():
                held[sym] = held.get(sym, 0.0) + lot.qty
        for sym, q in s.sim["positions"].items():
            assert held.get(sym, 0.0) == pytest.approx(q, abs=1e-6), sym
        # The simulator's cash moved by exactly the booked fills and their costs (each cost counted once).
        flow = sum((-1 if f["side"] == "buy" else 1) * f["qty"] * f["fill"] - f["cost"] for f in s.fills)
        assert s.sim["cash"] == pytest.approx(CASH + flow, abs=0.01)
        assert not [ln for ln in json.loads((tmp_path / "rules" / "journal.jsonl").read_text().splitlines()[-1])
                    ["risk_log"] if "reconcile:" in ln]


# --- stops without Claude ------------------------------------------------------------------------------


def test_claude_book_without_advisor_enforces_c_ratchet_and_b_time_stop(world, tmp_path):
    cfg, bars = world
    idx = bars["SPY"].index
    d = idx[-1]
    b = upto(bars, d)
    c_sym = next(s for s in cfg.sleeves["C"]["universe"]
                 if float(b[s]["close"].iloc[-1]) > float(b[s]["low"].iloc[-11:-1].min()))
    b_sym = cfg.sleeves["B"]["symbols"][0]
    c_px, b_px = float(b[c_sym]["close"].iloc[-1]), float(b[b_sym]["close"].iloc[-1])
    state = BookState(book="claude")
    state.lots = {"C": {c_sym: Lot(10.0, c_px, idx[-30].date().isoformat(), c_px * 0.5, c_px * 0.5)},
                  "B": {b_sym: Lot(5.0, b_px, idx[-13].date().isoformat(), b_px * 0.5, b_px * 0.5)}}
    state.sim = {"cash": CASH - 10 * c_px - 5 * b_px, "positions": {c_sym: 10.0, b_sym: 5.0}}
    state.save(tmp_path)
    e = Book(cfg, bars, "claude", tmp_path).run(d, None)
    sells = {o["symbol"]: o for o in e["orders"] if o["side"] == "sell"}
    assert b_sym in sells and "time stop" in sells[b_sym]["reason"]  # B-4 in the Claude book too
    assert c_sym not in sells
    trail = float(b[c_sym]["low"].iloc[-11:-1].min())
    assert BookState.load("claude", tmp_path).lots["C"][c_sym].stop == pytest.approx(trail)  # C-7 persisted


# --- the rules book review ------------------------------------------------------------------------------


def test_review_cannot_skip_sleeve_a(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    plain = Book(cfg, bars, "rules", tmp_path / "plain").run(d, None, dry_run=True)
    a_buys = sorted(o["symbol"] for o in plain["orders"] if o["side"] == "buy" and "A:" in o["reason"])
    assert a_buys

    def review(ctx):
        return RulesReview(date=ctx["date"], journal_note="skip A",
                           skip_entries=[Skip(symbol=s, sleeve="A", reason_code="HALT_OR_ILLIQUID",
                                              evidence=["regime.label"], prediction_id=f"p{i}")
                                         for i, s in enumerate(a_buys)],
                           predictions=[pred(s, f"p{i}", f"skip:{s}") for i, s in enumerate(a_buys)])

    e = Book(cfg, bars, "rules", tmp_path / "reviewed").run(d, Fake(review), dry_run=True)
    assert sorted(o["symbol"] for o in e["orders"] if o["side"] == "buy" and "A:" in o["reason"]) == a_buys
    assert e["vetoes"] == []


def _dip_then_rally(df, at, down=3, drop=0.015, rise=0.01):
    """RSI(2) dip ending on bar `at` (a B entry signal), then a rally (the B exit: close above SMA5)."""
    close = df["close"].to_numpy().copy()
    n = len(close)
    for i in range(n + at - down + 1, n + at + 1):
        close[i] = close[i - 1] * (1 - drop)
    for i in range(n + at + 1, n):
        close[i] = close[i - 1] * (1 + rise)
    open_ = np.r_[close[0], close[:-1] * 1.002]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) * 1.003,
                         "low": np.minimum(open_, close) * 0.997, "close": close, "volume": df["volume"].to_numpy()},
                        index=df.index)


def test_veto_becomes_a_shadow_lot_that_closes_and_is_scored(world, tmp_path):
    cfg, base = world
    bars = dict(base)
    bars["QQQ"] = _dip_then_rally(base["SPY"] * 1.5, at=-6)  # an uptrend (above its SMA200) with a dip
    d = list(bars["SPY"].index[-6:])
    b0 = upto(bars, d[0])
    reg = classify(b0, "SPY", cfg.stock_universe(), cfg.playbook["regime"]["canaries"],
                   **classify_kwargs(cfg.playbook["regime"]))
    assert reg.permissions["B"] > 0  # the synthetic market lets sleeve B trade

    def review(ctx):
        assert any(p["symbol"] == "QQQ" for p in ctx["planned_increases"])
        return RulesReview(date=ctx["date"], journal_note="skip QQQ",
                           skip_entries=[Skip(symbol="QQQ", sleeve="B", reason_code="HALT_OR_ILLIQUID",
                                              evidence=["rule_signals.B.indicators[QQQ].close"],
                                              prediction_id="p1")],
                           predictions=[pred("QQQ", "p1", "skip:QQQ")])

    book = Book(cfg, bars, "rules", tmp_path)
    e = book.run(d[0], Fake(review))
    assert [v["symbol"] for v in e["vetoes"]] == ["QQQ"]
    assert "QQQ" not in {o["symbol"] for o in e["orders"]}
    s = book.state()
    [lot] = s.shadow_lots
    assert lot["status"] == "pending_entry" and lot["qty"] > 0
    assert [p["symbol"] for p in s.predictions] == ["QQQ"]  # the skip's prediction is stored (CL-5)
    for day in d[1:]:
        book.run(day)
    s = book.state()
    [lot] = s.shadow_lots
    assert lot["status"] == "closed", lot
    assert lot["entry_price"] == pytest.approx(float(bars["QQQ"].loc[d[1], "open"]), rel=1e-3)
    assert lot["veto_value"] is not None and lot["veto_value"] < 0  # the rally made the veto cost money
    assert s.predictions[0]["outcome"] in (0, 1) and s.predictions[0]["brier"] is not None


# --- decision files (Option B) ---------------------------------------------------------------------------


def _write(folder, name, obj):
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj))
    return p


def _file(date, **over):
    d = ClaudeDecision(date=date, market_view="m", journal_note="j").model_dump()
    d.update(over)
    return d


def test_decision_file_with_wrong_date_holds(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    date = d.date().isoformat()
    book = Book(cfg, bars, "claude", tmp_path)
    good = _write(tmp_path / "files", "decision_1.json", _file(date))
    e = book.run(d, SessionAdvisor([good], date, cfg), dry_run=True)
    assert e["orders"] and e["claude_error"] is None  # a valid empty decision follows the rules
    wrong = _write(tmp_path / "files", "decision_2.json", _file("2020-01-02"))
    e = book.run(d, SessionAdvisor([wrong], date, cfg), dry_run=True)
    assert e["orders"] == [] and e["claude_error"]  # the book holds


def test_invalid_file_holds_but_stops_are_enforced(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    sym = cfg.sleeves["B"]["symbols"][1]
    px = float(bars[sym].loc[d, "close"])
    state = BookState(book="claude")
    state.lots = {"B": {sym: Lot(4.0, px * 1.05, bars["SPY"].index[-3].date().isoformat(), px * 1.01, px * 1.01)}}
    state.sim = {"cash": CASH - 4 * px, "positions": {sym: 4.0}}
    state.save(tmp_path)
    bad = _write(tmp_path / "files", "decision_1.json", "{not json")
    e = Book(cfg, bars, "claude", tmp_path).run(d, SessionAdvisor([bad], d.date().isoformat(), cfg))
    assert e["claude_error"]
    [o] = e["orders"]
    assert o["symbol"] == sym and o["side"] == "sell" and "stop" in o["reason"]


def test_session_files_from_the_pending_folder(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    date = d.date().isoformat()
    book = Book(cfg, bars, "claude", tmp_path)
    out = book.prepare(d, samples=2)
    folder = session.pending_dir("claude", date, tmp_path)
    assert out["dir"] == str(folder) and out["samples"] == 2
    _write(folder, "decision_1.json", _file(date, journal_note="first"))
    _write(folder, "decision_2.json", _file(date, journal_note="second"))
    adv = SessionAdvisor.from_pending("claude", date, cfg, tmp_path)
    e = book.run(d, adv)
    assert e["claude_meta"]["samples_valid"] == 2 and e["claude_error"] is None
    assert e["tags"]["model_source"] == "self-reported"  # guide 17: session files name their own model
    s = book.state()
    assert s.api_cost[-1]["mode"] == "session" and s.api_cost[-1]["usd"] == 0.0  # M-9
    assert s.weight_history[-1]["date"] == date and s.weight_history[-1]["changed"] == []


def test_prepare_writes_the_same_context_run_book_uses(world, tmp_path):
    cfg, bars = world
    for name in ("rules", "claude"):
        d = bars["SPY"].index[-2]
        book = Book(cfg, bars, name, tmp_path / name)
        book.run(bars["SPY"].index[-3])  # some history and pending orders first
        out = book.prepare(d)
        written = json.loads((session.pending_dir(name, d.date().isoformat(), tmp_path / name)
                              / "context.json").read_text())
        adv = Fake(lambda c: decision(c)) if name == "claude" else Fake(
            lambda c: RulesReview(date=c["date"], journal_note="ok"))
        book.run(d, adv)
        assert json.loads(json.dumps(adv.contexts[0])) == written
        assert out["summary"] and out["files"]["schema"].endswith("schema.json")


def test_dry_run_saves_nothing_and_places_nothing(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    book = Book(cfg, bars, "rules", tmp_path)
    state = book.state()
    e = book.run(d, None, state=state, dry_run=True)
    assert e["orders"] and e["fills"] == [] and e["dry_run"]
    assert not BookState.path("rules", tmp_path).exists()
    assert state.sim["positions"] == {} and not state.sim.get("open_orders") and state.pending_orders == []


# --- consensus and deviations ---------------------------------------------------------------------------


def test_deviation_without_a_prediction_is_dropped(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    sym = eligible_b(cfg, bars, d)
    e = Book(cfg, bars, "claude", tmp_path).run(
        d, Fake(lambda c: decision(c, [b_action(sym, "pct", 0.05, with_pred=False)])))
    assert sym not in {o["symbol"] for o in e["orders"]}
    assert e["deviations"] == []
    assert any("needs a prediction_id" in p for p in e["samples"][0]["problems"])


def test_three_samples_one_deviates_the_rule_wins(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    sym = eligible_b(cfg, bars, d)
    lone = Fake(lambda c: decision(c, [b_action(sym, "pct", 0.05)], [pred(sym)]),
                lambda c: decision(c), lambda c: decision(c))
    e = Book(cfg, bars, "claude", tmp_path).run(d, lone)
    assert sym not in {o["symbol"] for o in e["orders"]}
    assert e["deviations"] == [] and e["agreement"]["n"] == 3
    assert e["cl15_shadow"]["rule"] == "CL-15"
    both = Fake(lambda c: decision(c, [b_action(sym, "pct", 0.05)], [pred(sym)]),
                lambda c: decision(c, [b_action(sym, "pct", 0.05)], [pred(sym)]), lambda c: decision(c))
    e = Book(cfg, bars, "claude", tmp_path / "majority").run(d, both)
    assert sym in {o["symbol"] for o in e["orders"]} and [x["symbol"] for x in e["deviations"]] == [sym]


def test_predictions_are_stored_and_later_resolved(world, tmp_path):
    cfg, bars = world
    days = list(bars["SPY"].index[-7:])
    sym = eligible_b(cfg, bars, days[0])
    book = Book(cfg, bars, "claude", tmp_path)
    book.run(days[0], Fake(lambda c: decision(c, [b_action(sym, "pct", 0.05)], [pred(sym)])))
    s = book.state()
    [p] = s.predictions
    assert p["symbol"] == sym and p["outcome"] is None and p["base_close"] is not None
    assert p["tags"]["book"] == "claude"
    [dv] = s.deviations
    assert dv["symbol"] == sym and dv["prediction_id"] == "p1"
    for d in days[1:]:
        book.run(d)
    [p] = book.state().predictions
    base = float(bars[sym].loc[days[0], "close"])
    later = float(bars[sym].loc[days[5], "close"])
    assert p["outcome"] == int(later > base * 1.01)
    assert p["brier"] == pytest.approx((0.6 - p["outcome"]) ** 2)


def test_rerun_with_force_replaces_the_days_records(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    sym = eligible_b(cfg, bars, d)
    book = Book(cfg, bars, "claude", tmp_path)
    book.run(d, Fake(lambda c: decision(c, [b_action(sym, "pct", 0.05)], [pred(sym)])))
    assert "skipped" in book.run(d, Fake(lambda c: decision(c)))
    book.run(d, Fake(lambda c: decision(c)), force=True)
    s = book.state()
    assert s.predictions == [] and s.deviations == []  # the discarded attempt left nothing to score
    assert not [p for p in s.pending_orders if p["symbol"] == sym]  # its order was cancelled
    ids = [p["client_order_id"] for p in s.pending_orders]
    assert len(ids) == len(set(ids)) and all(i.startswith("c" + d.strftime("%Y%m%d")) for i in ids)


def test_force_rerun_drops_the_discarded_attempts_weight_row_and_note(world, tmp_path):
    from trader.schemas import SleeveWeightChoices, WeightChoice

    cfg, bars = world
    d0, d = bars["SPY"].index[-2], bars["SPY"].index[-1]
    date = d.date().isoformat()
    book = Book(cfg, bars, "claude", tmp_path)
    book.run(d0, Fake(lambda c: decision(c)))
    before = book.state().weight_history[-1]["weights"]["C"]

    def down(c):
        return ClaudeDecision(date=c["date"], market_view="m", journal_note="went down",
                              sleeve_weights=SleeveWeightChoices(C=WeightChoice(choice="down")))

    book.run(d, Fake(down))
    s = book.state()
    assert s.weight_history[-1]["weights"]["C"] < before and s.weight_history[-1]["changed"] == ["C"]
    book.run(d, Fake(lambda c: ClaudeDecision(date=c["date"], market_view="m", journal_note="kept")), force=True)
    s = book.state()
    rows = [r for r in s.weight_history if r["date"] == date]
    assert len(rows) == 1 and rows[0]["weights"]["C"] == pytest.approx(before) and rows[0]["changed"] == []
    assert [n["note"] for n in s.notes if n["date"] == date] == ["kept"]
    costs = [r for r in s.api_cost if r["date"] == date]
    assert len(costs) == 2 and costs[0].get("superseded") and not costs[1].get("superseded")


def test_empty_broker_positions_never_rebuy_the_book(world, tmp_path):
    cfg, bars = world
    days = list(bars["SPY"].index[-3:])
    book = Book(cfg, bars, "rules", tmp_path)
    book.run(days[0])
    book.run(days[1])
    s = book.state()
    assert s.lots

    class EmptyPositions(SimBroker):
        def positions(self):
            return {}

    b = upto(bars, days[2])
    held = {sym for lots in s.lots.values() for sym in lots}
    for dry in (True, False):
        st = book.state()
        real = book.broker(st, b)
        broker = EmptyPositions(st.sim, real.prices, real.cost_bps, real.asset_class, bars=b, fill_mode="next_open",
                                cost_in_price=False)
        e = run_book("rules", cfg, b, broker, None, days[2], tmp_path, state=st, dry_run=dry)
        assert not [o for o in e["orders"] if o["symbol"] in held], e["orders"]
        assert any(ln.startswith("STOP:") and "--confirm-empty-account" in ln for ln in e["risk_log"])


def test_run_output_names_invalid_files_and_dropped_items(world, tmp_path, capsys):
    from trader.__main__ import print_entry

    cfg, bars = world
    d = bars["SPY"].index[-1]
    date = d.date().isoformat()
    sym = eligible_b(cfg, bars, d)
    folder = session.pending_dir("claude", date, tmp_path)
    no_pred = _file(date, journal_note="no pred", actions=[b_action(sym, "pct", 0.05, with_pred=False).model_dump()])
    _write(folder, "decision_1.json", _file(date, journal_note="first"))
    _write(folder, "decision_2.json", no_pred)
    _write(folder, "decision_3.json", "{not json")
    e = Book(cfg, bars, "claude", tmp_path).run(d, SessionAdvisor.from_pending("claude", date, cfg, tmp_path),
                                                 dry_run=True)
    print_entry(e)
    out = capsys.readouterr().out
    assert "samples: 2 of 3 valid" in out
    assert "claude problem: decision_3.json: not valid JSON" in out
    assert "needs a prediction_id" in out


def test_context_shows_no_test_first_shadow_signals(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    adv = Fake(lambda c: decision(c))
    e = Book(cfg, bars, "claude", tmp_path).run(d, adv, dry_run=True)
    ctx = adv.contexts[0]
    assert all("shadow" not in sig for sig in ctx["rule_signals"].values())
    assert "credit_canary" not in ctx["regime"]
    assert "shadow" not in json.dumps(ctx["rule_signals"])
    assert "shadow_signals" in e  # the journal still logs them


def test_deviation_citing_a_shadow_signal_is_dropped(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    sym = eligible_b(cfg, bars, d)
    act = Action(symbol=sym, sleeve="B", size="pct", target_pct_equity=0.05, reason_code="MEAN_REVERSION_SETUP",
                 evidence=["regime.credit_canary"], prediction_id="p1", rationale="test")
    e = Book(cfg, bars, "claude", tmp_path).run(d, Fake(lambda c: decision(c, [act], [pred(sym)])), dry_run=True)
    assert sym not in {o["symbol"] for o in e["orders"]} and e["deviations"] == []


def test_deviation_the_risk_engine_blocked_is_not_stored(world, tmp_path):
    from trader.state import set_kill_switch

    cfg, bars = world
    d = bars["SPY"].index[-1]
    sym = eligible_b(cfg, bars, d)
    set_kill_switch(True, tmp_path)
    book = Book(cfg, bars, "claude", tmp_path)
    e = book.run(d, Fake(lambda c: decision(c, [b_action(sym, "pct", 0.05)], [pred(sym)])))
    assert sym not in {o["symbol"] for o in e["orders"]}
    assert e["deviations"] == [] and book.state().deviations == []
    assert any("deviation not traded" in ln for ln in e["risk_log"])


def test_api_path_through_run_book_with_a_fallback_sample(world, tmp_path):
    """OPERATION_INVEST item 1: the API path (ClaudeAdvisor + a fake client) runs the whole day."""
    from test_llm_session import FakeClient, decision_json, response
    from trader.llm import ClaudeAdvisor

    cfg, bars = world
    d = bars["SPY"].index[-1]
    date = d.date().isoformat()
    items = [response(decision_json("a", date=date)), response(decision_json("b", date=date)),
             response(decision_json("c", date=date), model="claude-sonnet-5")]
    book = Book(cfg, bars, "claude", tmp_path)
    e = book.run(d, ClaudeAdvisor(cfg, FakeClient(items)))
    assert e["claude_error"] is None and e["orders"]  # three valid "follow the rules" answers
    assert e["tags"]["mode"] == "api" and e["tags"]["fallback_used"] is True
    [row] = book.state().api_cost
    assert row["mode"] == "api" and row["usd"] > 0 and row["samples"] == 3
    low = [ln for ln in e["risk_log"] if ln.startswith("low confidence")]
    assert low and "fallback model" in low[0] and "missing samples" not in low[0]  # guide 17: say the cause


def test_prepare_leaves_a_day_that_already_ran_alone(world, tmp_path):
    cfg, bars = world
    d = bars["SPY"].index[-1]
    date = d.date().isoformat()
    book = Book(cfg, bars, "claude", tmp_path)
    book.prepare(d, samples=1)
    folder = session.pending_dir("claude", date, tmp_path)
    _write(folder, "decision_1.json", _file(date))
    book.run(d, SessionAdvisor.from_pending("claude", date, cfg, tmp_path))
    before = sorted(p.name for p in folder.iterdir())
    out = book.prepare(d, samples=1)  # e.g. the next day is a holiday: the data still ends on `d`
    assert out["skipped"] and "already ran" in out["summary"][0]
    assert sorted(p.name for p in folder.iterdir()) == before


# --- the journal ------------------------------------------------------------------------------------------


def test_journal_entries_are_json_serialisable(world, tmp_path):
    cfg, bars = world
    book = Book(cfg, bars, "claude", tmp_path)
    days = bars["SPY"].index[-2:]
    sym = eligible_b(cfg, bars, days[0])
    book.run(days[0], Fake(lambda c: decision(c, [b_action(sym, "pct", 0.05)], [pred(sym)]),
                           lambda c: decision(c, [b_action(sym, "pct", 0.05)], [pred(sym)])))
    book.run(days[1], None, dry_run=True)

    def no_nan(token):
        raise ValueError(token)

    lines = (tmp_path / "claude" / "journal.jsonl").read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        e = json.loads(line, parse_constant=no_nan)
        for key in ("broker", "simulated", "breakers", "temperature", "samples", "agreement", "vetoes",
                    "deviations", "predictions", "shadow_signals", "cl15_shadow", "settled_fills",
                    "prompt_version", "data_feed"):
            assert key in e, key
        assert e["broker"] == "sim" and e["simulated"] is True


# --- a missing close never values a holding at $0 (finding #1) --------------------------------------------


def test_nan_close_on_a_held_etf_does_not_fake_a_drawdown(world, tmp_path):
    cfg, base = world
    days = list(base["SPY"].index[-5:])
    book = Book(cfg, base, "rules", tmp_path)
    for d in days[:-1]:
        book.run(d)
    s = book.state()
    held = max(s.sim["positions"], key=lambda k: s.sim["positions"][k] * float(base[k]["close"].iloc[-2]))
    eq_before = s.equity_history[-1]["equity"]
    bars = dict(base)
    df = base[held].copy()
    df.loc[days[-1], "close"] = float("nan")
    bars[held] = df
    e = Book(cfg, bars, "rules", tmp_path).run(days[-1])
    assert abs(e["equity"] / eq_before - 1) < 0.01, (held, e["equity"], eq_before)
    s = book.state()
    assert not s.halted
    b = e["breakers"]
    assert not b.get("halted") and not b.get("monthly_block")
    assert not any("drawdown" in r or "week" in r for r in b.get("reasons", [])), b


def test_sim_account_keeps_the_last_mark_for_a_symbol_without_a_price(world):
    cfg, _ = world
    sim = {"cash": 1_000.0, "positions": {"SPY": 10.0}}
    SimBroker(sim, {"SPY": 50.0}, {}, cfg.asset_class).account()
    equity, cash = SimBroker(sim, {}, {}, cfg.asset_class).account()  # SPY not fetched today
    assert equity == pytest.approx(1_500.0) and cash == 1_000.0
    equity, _ = SimBroker(sim, {"SPY": float("nan")}, {}, cfg.asset_class).account()
    assert equity == pytest.approx(1_500.0)
