import pandas as pd

from trader.broker import SimBroker
from trader.engine import decision_to_targets, run_book
from trader.llm import Action, ClaudeDecision, ClaudeError, RulesReview, SleeveWeights
from trader.state import BookState


class FakeAdvisor:
    def __init__(self, decision=None, fail=False):
        self.decision, self.fail, self.contexts = decision, fail, []

    def review_rules_plan(self, ctx):
        self.contexts.append(ctx)
        if self.fail:
            raise ClaudeError("boom")
        return RulesReview(journal_note="rules ok", skip_entries=[], halve_sleeves=[]), {"model": "fake"}

    def decide(self, ctx):
        self.contexts.append(ctx)
        if self.fail:
            raise ClaudeError("boom")
        return self.decision, {"model": "fake"}


def _sim(cfg, state, bars):
    state.sim = state.sim or {"cash": 10000.0, "positions": {}}
    prices = {s: float(df["close"].iloc[-1]) for s, df in bars.items()}
    return SimBroker(state.sim, prices, cfg.policy["turnover"]["cost_model_per_side_bps"], cfg.asset_class)


def test_rules_book_end_to_end(cfg, bars, tmp_path):
    as_of = bars["SPY"].index[-1]
    state = BookState.load("rules", tmp_path)
    advisor = FakeAdvisor()
    e = run_book("rules", cfg, bars, _sim(cfg, state, bars), advisor, as_of, tmp_path, state=state)
    assert e["orders"], e["risk_log"]
    assert advisor.contexts and "rule_signals" in advisor.contexts[0]
    saved = BookState.load("rules", tmp_path)
    held = {}
    for lots in saved.lots.values():
        for s, l in lots.items():
            held[s] = held.get(s, 0) + l.qty
    for s, q in saved.sim["positions"].items():
        if q > 1e-9:
            assert abs(held.get(s, 0) - q) < 1e-6
    equity = saved.sim["cash"] + sum(q * bars[s]["close"].iloc[-1] for s, q in saved.sim["positions"].items())
    assert saved.sim["cash"] >= 0.04 * equity  # cash buffer respected
    # Same date again is skipped.
    again = run_book("rules", cfg, bars, _sim(cfg, saved, bars), advisor, as_of, tmp_path, state=saved)
    assert "skipped" in again


def test_claude_book_follows_decision_within_limits(cfg, bars, tmp_path):
    decision = ClaudeDecision(
        market_view="test",
        sleeve_weights=SleeveWeights(A=0.9, B=0.2, C=0.1, D=0.1),  # A above max, D disabled
        actions=[
            Action(symbol="SPY", sleeve="A", target_pct_equity=0.5, stop_price=0, rationale="core"),
            Action(symbol="AAPL", sleeve="A", target_pct_equity=0.1, stop_price=0, rationale="stock in A"),
            Action(symbol="MSFT", sleeve="C", target_pct_equity=0.5, stop_price=0, rationale="no stop"),
            Action(symbol="BTC/USD", sleeve="D", target_pct_equity=0.05, stop_price=0, rationale="crypto"),
        ],
        journal_note="note",
    )
    as_of = bars["SPY"].index[-1]
    state = BookState.load("claude", tmp_path)
    e = run_book("claude", cfg, bars, _sim(cfg, state, bars), FakeAdvisor(decision), as_of, tmp_path, state=state)
    assert e["sleeve_weights"]["A"] == 0.6  # clipped to the sleeve maximum
    assert e["sleeve_weights"]["D"] == 0
    log = "\n".join(e["risk_log"])
    assert "AAPL" in log and "not allowed in sleeve A" in log
    assert "BTC/USD" not in {o["symbol"] for o in e["orders"]}
    spy = [o for o in e["orders"] if o["symbol"] == "SPY"][0]
    assert spy["qty"] * spy["price"] <= 0.30 * 10000 + 1  # ETF cap
    msft = [o for o in e["orders"] if o["symbol"] == "MSFT"][0]
    saved = BookState.load("claude", tmp_path)
    lot = saved.lots["C"]["MSFT"]
    assert lot.stop is not None and (msft["price"] - lot.stop) * lot.qty <= 50 + 1e-6
    assert saved.notes[-1]["note"] == "note"


def test_claude_failure_holds_positions(cfg, bars, tmp_path):
    as_of = bars["SPY"].index[-1]
    state = BookState.load("claude", tmp_path)
    e = run_book("claude", cfg, bars, _sim(cfg, state, bars), FakeAdvisor(fail=True), as_of, tmp_path, state=state)
    assert e["orders"] == []
    assert e["claude_error"] == "boom"


def test_dry_run_saves_nothing(cfg, bars, tmp_path):
    as_of = bars["SPY"].index[-1]
    state = BookState.load("rules", tmp_path)
    e = run_book("rules", cfg, bars, _sim(cfg, state, bars), None, as_of, tmp_path, dry_run=True, state=state)
    assert e["orders"] and e["fills"] == []
    assert not BookState.path("rules", tmp_path).exists()


def test_decision_scaled_to_sleeve_weight(cfg, bars):
    d = ClaudeDecision(market_view="", sleeve_weights=SleeveWeights(A=0.5, B=0.15, C=0.1, D=0),
                       actions=[Action(symbol="QQQ", sleeve="B", target_pct_equity=0.3, stop_price=1.0,
                                       rationale="x")], journal_note="")
    log = []
    targets, weights = decision_to_targets(cfg, d, {}, bars, 10000, log)
    [t] = targets
    assert abs(t.qty * bars["QQQ"]["close"].iloc[-1] - weights["B"] * 10000) < 1e-6


def test_crypto_sleeve_when_enabled(cfg, tmp_path):
    import copy

    from conftest import make_bars
    from trader.config import Config

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
        assert o["qty"] * o["price"] <= 0.10 * 10000 + 1
    lot = BookState.load("rules", tmp_path).lots["D"][crypto[0]["symbol"]]
    assert lot.stop is not None and lot.stop < crypto[0]["price"]
