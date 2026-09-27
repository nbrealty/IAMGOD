"""decisions.py: evidence paths (CL-2), weight caps and moves (RISK-7/8/10, M-11, CL-10/12), the rules-book review
(CL-7/8) and the Claude book's menu resolution (CL-11/13/14, CL-5), all on synthetic data."""
import copy
import math
from types import SimpleNamespace

import pytest

from conftest import make_bars
from trader import decisions as d
from trader import indicators as ind
from trader import strategies as strat
from trader.config import Config, load_config
from trader.models import Lot, Target
from trader.schemas import (RESTRICTED_SKIP_CODES, Action, ClaudeDecision, Halve, LikelyError, Prediction,
                            ResolvedDecision, ResolvedTarget, RulesReview, Skip, SleeveWeightChoices, WeightChoice)

EQ = 100_000.0
DATE = "2026-09-25"  # a Friday; the next session is Monday 2026-09-28
PERM_ALL = {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0}
DRIFT = {"SPY": 0.001, "IWM": -0.001, "NVDA": 0.003, "AVGO": 0.0025, "AAPL": -0.002}


def _cfg_copy(cfg: Config) -> Config:
    return Config(playbook=copy.deepcopy(cfg.playbook), policy=copy.deepcopy(cfg.policy))


def _d_enabled(cfg: Config) -> Config:
    c = _cfg_copy(cfg)
    c.playbook["sleeves"]["D"]["enabled"] = True
    return c


@pytest.fixture(scope="module")
def mcfg():
    return load_config()


@pytest.fixture(scope="module")
def market(mcfg):
    symbols = _d_enabled(mcfg).allowlist()  # crypto bars too, for the D tests
    return {s: make_bars(seed=i + 1, drift=DRIFT.get(s, 0.0), crypto="/" in s) for i, s in enumerate(symbols)}


@pytest.fixture(scope="module")
def prices(market):
    return {s: float(df["close"].iloc[-1]) for s, df in market.items()}


def _ctx(prices):
    return {
        "date": DATE,
        "account": {"equity": EQ, "drawdown": 0.01},
        "regime": {"label": "bull_calm", "temperature": 0.85, "breadth_above_50d": 0.0, "permissions": PERM_ALL},
        "rule_signals": {
            "A": {"indicators": [{"symbol": "SPY", "above_10m_sma": True}], "notes": []},
            "B": {"indicators": [{"symbol": "SPY", "close": prices["SPY"], "rsi2": 8.0},
                                 {"symbol": "IWM", "close": prices["IWM"], "rsi2": 50.0}], "notes": []},
            "C": {"indicators": [{"symbol": "NVDA", "close": prices["NVDA"], "volume_ratio": 1.8, "rs_pct": 99.0},
                                 {"symbol": "AVGO", "close": prices["AVGO"], "volume_ratio": 1.6},
                                 {"symbol": "AAPL", "close": prices["AAPL"], "rs_pct": None}],
                  "notes": ["one breakout"]},
        },
        "signal_count": {"B": 1, "C": 2},
        "data_problems": ["MSFT: zero volume on the last bar"],
        "allowlist": sorted(prices),
    }


@pytest.fixture
def book(mcfg, market, prices):
    """Rule targets and lots for the Claude-book tests."""
    p = prices
    b_spy_stop = d.stop_menu("B", market["SPY"], mcfg.policy)["rule"]
    lots = {
        "C": {"NVDA": Lot(0.02 * EQ / p["NVDA"], 0.7 * p["NVDA"], "2026-08-01", 0.8 * p["NVDA"], 0.6 * p["NVDA"]),
              "MSFT": Lot(0.03 * EQ / p["MSFT"], 0.9 * p["MSFT"], "2026-08-01", 0.85 * p["MSFT"], 0.8 * p["MSFT"])},
        "B": {"IWM": Lot(0.04 * EQ / p["IWM"], 1.02 * p["IWM"], "2026-09-20", 0.9 * p["IWM"], 0.9 * p["IWM"])},
        "A": {"EFA": Lot(0.05 * EQ / p["EFA"], p["EFA"], "2026-01-02")},
    }
    rules = [
        Target("SPY", "A", 0.11 * EQ / p["SPY"], None, "faber weight 0.20 of sleeve"),
        Target("BIL", "A", 0.20 * EQ / p["BIL"], None, "faber weight 0.36 of sleeve"),
        Target("SPY", "B", 0.05 * EQ / p["SPY"], b_spy_stop, "RSI2 entry"),
        Target("NVDA", "C", lots["C"]["NVDA"].qty, lots["C"]["NVDA"].stop, "hold"),
        Target("MSFT", "C", lots["C"]["MSFT"].qty, lots["C"]["MSFT"].stop, "hold"),
        Target("IWM", "B", lots["B"]["IWM"].qty, lots["B"]["IWM"].stop, "hold"),
    ]  # A:EFA is held with no rule target
    return {"rules": rules, "lots": lots, "prices": dict(p), "ctx": _ctx(p)}


def pred(pid="p1", symbol="NVDA", prob=0.6, thr=2.0):
    return Prediction(id=pid, symbol=symbol, horizon=20, direction="above", threshold_pct=thr, probability=prob,
                      linked_decision=f"action:{symbol}")


def act(symbol, sleeve, size="rule", **kw):
    kw.setdefault("reason_code", "FOLLOW_RULE")
    kw.setdefault("evidence", ["regime.label"])
    return Action(symbol=symbol, sleeve=sleeve, size=size, **kw)


def decision(actions=(), predictions=(), **kw):
    kw.setdefault("market_view", "calm")
    kw.setdefault("journal_note", "Followed the rules.")
    return ClaudeDecision(actions=list(actions), predictions=list(predictions), **kw)


def resolve(cfg, market, book, dec, **kw):
    kw.setdefault("permissions", PERM_ALL)
    kw.setdefault("ctx", book["ctx"])
    return d.resolve_actions(dec, cfg=cfg, rule_targets=book["rules"], lots=book["lots"], bars=market,
                             prices=book["prices"], equity=kw.pop("equity", EQ), **kw)


def dropped(res, key):
    return any(p.startswith(f"action {key}: dropped") for p in res.problems)


# --- CL-2: evidence paths ---------------------------------------------------------------------------------


def test_path_exists_walks_dicts_lists_and_symbol_selectors(prices):
    ctx = _ctx(prices)
    assert d.path_exists(ctx, "rule_signals.C.indicators[NVDA].volume_ratio")
    assert d.path_exists(ctx, "rule_signals.C.indicators[nvda].volume_ratio")  # symbols are case-insensitive
    assert d.path_exists(ctx, "rule_signals.C.indicators[0].rs_pct")
    assert d.path_exists(ctx, "rule_signals.C.indicators[-1].symbol")
    assert d.path_exists(ctx, "rule_signals[C].notes[0]")  # [X] on a dict is the key X
    assert d.path_exists(ctx, "rule_signals.C.indicators['AVGO'].close")  # quotes tolerated
    assert d.path_exists(ctx, "data_problems[MSFT]")  # "SYM: problem" strings
    assert d.path_exists(ctx, "regime.label")
    assert d.path_exists(ctx, "account.drawdown")
    assert d.path_exists(ctx, "regime.breadth_above_50d")  # 0.0 is a value


def test_path_exists_rejects_missing_none_nan_empty_and_malformed(prices):
    ctx = _ctx(prices)
    ctx["regime"]["nan_value"] = float("nan")
    for bad in ["rule_signals.C.indicators[AAPL].rs_pct",  # None
                "regime.nan_value",
                "rule_signals.B.notes",  # empty list
                "rule_signals.C.indicators[TSLA].close",  # not in the list
                "rule_signals.C.indicators[7].close",  # out of range
                "rule_signals.Z", "nope", "", "  ", "a..b", "a[", "a[]", ".a", "a.", "data_problems[NVDA]",
                None, 3, ["regime.label"]]:
        assert not d.path_exists(ctx, bad), bad
    assert not d.path_exists(None, "regime.label")
    assert not d.path_exists("text", "regime.label")


def test_evidence_ok_needs_every_path(prices):
    ctx = _ctx(prices)
    assert d.evidence_ok(ctx, ["regime.label", "account.drawdown"]) == (True, "")
    ok, why = d.evidence_ok(ctx, ["regime.label", "news.headline"])
    assert not ok and "news.headline" in why and "CL-2" in why
    assert not d.evidence_ok(ctx, [])[0]
    assert not d.evidence_ok(ctx, None)[0]
    assert not d.evidence_ok(ctx, "regime.label")[0]  # a bare string is not a list
    assert not d.evidence_ok(None, ["regime.label"])[0]


# --- RISK-7 / RISK-8 / M-11: cap_weights --------------------------------------------------------------------


def test_cap_weights_clips_to_band_and_probation_cap(mcfg):
    w = d.cap_weights(mcfg, {"A": 0.9, "B": 0.3, "C": 0.3, "D": 0.1})
    assert w == pytest.approx({"A": 0.60, "B": 0.20, "C": 0.15, "D": 0.0})  # RISK-8: B, C at default; D off
    w = d.cap_weights(mcfg, {"A": 0.1, "B": 0.0, "C": -1.0, "D": 0.0})
    assert w == pytest.approx({"A": 0.50, "B": 0.15, "C": 0.10, "D": 0.0})  # mins


def test_cap_weights_promoted_sleeves_reach_max_then_cash_buffer_scales(mcfg):
    w = d.cap_weights(mcfg, {"A": 0.6, "B": 0.3, "C": 0.3}, promoted=["B", "C"])
    raw = {"A": 0.60, "B": 0.25, "C": 0.20, "D": 0.0}
    scale = 0.95 / sum(raw.values())
    assert w == pytest.approx({s: v * scale for s, v in raw.items()})
    assert sum(w.values()) == pytest.approx(0.95)


def test_cap_weights_speculative_cap_cuts_d_first(mcfg):
    cfg = _d_enabled(mcfg)
    w = d.cap_weights(cfg, {"A": 0.5, "B": 0.15, "C": 0.2, "D": 0.05}, promoted=("C", "D"))
    assert w["C"] == pytest.approx(0.20) and w["D"] == pytest.approx(0.0)
    w = d.cap_weights(cfg, {"A": 0.5, "B": 0.15, "C": 0.15, "D": 0.05})  # not promoted: D capped at 0.03
    assert w["C"] == pytest.approx(0.15) and w["D"] == pytest.approx(0.03)


def test_cap_weights_speculative_cap_wins_over_mins(mcfg):
    cfg = _d_enabled(mcfg)
    cfg.playbook["sleeves"]["C"]["min"] = 0.15
    cfg.playbook["sleeves"]["D"]["min"] = 0.10
    cfg.playbook["sleeves"]["D"]["max"] = 0.10
    w = d.cap_weights(cfg, {"A": 0.5, "B": 0.15, "C": 0.2, "D": 0.1}, promoted=("C", "D"))
    assert w["C"] + w["D"] == pytest.approx(0.20)
    assert w["C"] == pytest.approx(0.15) and w["D"] == pytest.approx(0.05)


def test_cap_weights_demotion_goes_to_min(mcfg):
    w = d.cap_weights(mcfg, {"A": 0.55, "B": 0.2, "C": 0.15}, demoted={"B": "half", "C": "stop", "A": "ok"})
    assert w["B"] == pytest.approx(0.15) and w["C"] == pytest.approx(0.10) and w["A"] == pytest.approx(0.55)


def test_cap_weights_missing_or_bad_values_count_as_min(mcfg):
    w = d.cap_weights(mcfg, {"A": float("nan"), "B": "x", "C": None})
    assert w == pytest.approx({"A": 0.50, "B": 0.15, "C": 0.10, "D": 0.0})
    assert set(d.cap_weights(mcfg, None)) == {"A", "B", "C", "D"}


def test_cap_weights_honours_a_larger_cash_buffer(mcfg):
    cfg = _cfg_copy(mcfg)
    cfg.policy["portfolio"]["min_cash_buffer"] = 0.30
    w = d.cap_weights(cfg, {"A": 0.6, "B": 0.2, "C": 0.15})
    assert sum(w.values()) == pytest.approx(0.70)


# --- CL-10 / CL-12 / RISK-10: resolve_weights -------------------------------------------------------------------

PREV = {"A": 0.55, "B": 0.15, "C": 0.10, "D": 0.0}
RULE = {"A": 0.60, "B": 0.20, "C": 0.15, "D": 0.0}
CALM = SimpleNamespace(drawdown=0.01, watch=False, halted=False)
WCTX = {"date": DATE, "signal_count": {"B": 1, "C": 2}, "regime": {"label": "bull_calm"}}


def rw(cfg, choices, *, prev=PREV, since=None, breakers=CALM, ctx=WCTX, **kw):
    return d.resolve_weights(choices, cfg=cfg, prev=prev, rule=RULE, sessions_since_change=since or {},
                             breakers=breakers, ctx=ctx, **kw)


def up(code="SIGNAL_COUNT_CHANGE", evidence=("signal_count.B",), choice="up"):
    return {"choice": choice, "reason_code": code, "evidence": list(evidence)}


def test_resolve_weights_keep_is_prev(mcfg):
    w, reasons, problems = rw(mcfg, SleeveWeightChoices())
    assert w == pytest.approx(PREV) and problems == []
    assert not any(r["changed"] for r in reasons.values())
    w, _, _ = rw(mcfg, None)
    assert w == pytest.approx(PREV)


def test_resolve_weights_first_run_uses_rule_weights(mcfg):
    w, _, _ = rw(mcfg, None, prev=None)
    assert w == pytest.approx(d.cap_weights(mcfg, RULE))


def test_resolve_weights_b_up_with_code_and_evidence(mcfg, prices):
    w, reasons, problems = rw(mcfg, {"B": up()}, ctx=_ctx(prices))
    assert w["B"] == pytest.approx(0.20) and problems == []
    assert reasons["B"]["changed"] and reasons["B"]["reason_code"] == "SIGNAL_COUNT_CHANGE"


def test_resolve_weights_b_up_without_code_or_evidence_is_refused(mcfg, prices):
    w, reasons, problems = rw(mcfg, {"B": {"choice": "up"}}, ctx=_ctx(prices))
    assert w["B"] == pytest.approx(0.15) and "CL-12" in problems[0] and not reasons["B"]["changed"]
    w, _, problems = rw(mcfg, {"B": up(evidence=["news.fed"])}, ctx=_ctx(prices))
    assert w["B"] == pytest.approx(0.15) and "CL-2" in problems[0]
    w, _, _ = rw(mcfg, {"B": up(evidence=[])}, ctx=None)
    assert w["B"] == pytest.approx(0.15)
    for ev in (["signal_count.B"], ["news.fed_pivot"]):  # no context: nothing can be verified, so no increase
        w, reasons, problems = rw(mcfg, {"B": up(evidence=ev), "C": up(evidence=ev)}, ctx=None)
        assert w["B"] == pytest.approx(0.15) and w["C"] == pytest.approx(0.10), ev
        assert "CL-2" in problems[0] and not reasons["B"]["changed"]


def test_resolve_weights_a_and_decreases_need_no_code(mcfg):
    w, _, problems = rw(mcfg, {"A": "up", "C": "down"}, ctx=None)  # nothing to verify, so no context needed
    assert w["A"] == pytest.approx(0.60) and w["C"] == pytest.approx(0.10) and problems == []
    w, _, _ = rw(mcfg, {"B": "down"})
    assert w["B"] == pytest.approx(0.15)  # the band min holds


def test_resolve_weights_moves_are_clamped_to_one_step(mcfg):
    w, reasons, _ = rw(mcfg, {"A": "rule"}, prev={**PREV, "A": 0.50})
    assert w["A"] == pytest.approx(0.55) and reasons["A"]["requested"] == pytest.approx(0.55)
    w, _, _ = rw(mcfg, {"C": up(code="RETURN_TO_DEFAULT", choice="default")}, prev={**PREV, "C": 0.10})
    assert w["C"] == pytest.approx(0.15)


def test_resolve_weights_rate_limit(mcfg):
    w, _, problems = rw(mcfg, {"B": up()}, since={"B": 3})
    assert w["B"] == pytest.approx(0.15) and "CL-12" in problems[0]
    w, _, problems = rw(mcfg, {"A": "down"}, since={"A": 4})  # every change is rate limited, decreases too
    assert w["A"] == pytest.approx(0.55) and problems
    w, _, _ = rw(mcfg, {"B": up()}, since={"B": 5})
    assert w["B"] == pytest.approx(0.20)


def test_resolve_weights_watch_tier_blocks_bcd_increases(mcfg):
    watch = SimpleNamespace(drawdown=0.06, watch=True, halted=False)
    w, _, problems = rw(mcfg, {"B": up(), "A": "up", "C": "down"}, breakers=watch)
    assert w["B"] == pytest.approx(0.15) and "RISK-10" in " ".join(problems)
    assert w["A"] == pytest.approx(0.60)  # A may still rise
    w, _, _ = rw(mcfg, {"B": up()}, breakers=SimpleNamespace(drawdown=0.05))  # no watch attribute: drawdown decides
    assert w["B"] == pytest.approx(0.15)
    w, _, _ = rw(mcfg, {"B": up()}, breakers={"drawdown": 0.0, "watch": True})  # dict form
    assert w["B"] == pytest.approx(0.15)
    w, _, _ = rw(mcfg, {"B": up()}, breakers=None)
    assert w["B"] == pytest.approx(0.20)


def test_resolve_weights_other_breakers_block_increases(mcfg):
    for b in (SimpleNamespace(drawdown=0.0, halted=True), SimpleNamespace(drawdown=0.0, monthly_block=True),
              SimpleNamespace(drawdown=0.0, sleeve_risk_mult={"B": 0.5})):
        w, _, _ = rw(mcfg, {"B": up()}, breakers=b)
        assert w["B"] == pytest.approx(0.15), b


def test_resolve_weights_probation_cap_and_promotion(mcfg):
    w, reasons, _ = rw(mcfg, {"B": up()}, prev={**PREV, "B": 0.20})
    assert w["B"] == pytest.approx(0.20) and not reasons["B"]["changed"]  # RISK-8
    w, reasons, _ = rw(mcfg, {"B": up()}, prev={**PREV, "B": 0.20}, promoted=("B",))
    assert w["B"] == pytest.approx(0.25) and reasons["B"]["changed"]


def test_resolve_weights_return_to_default_stops_at_default(mcfg):
    w, _, _ = rw(mcfg, {"C": up(code="RETURN_TO_DEFAULT")}, prev={**PREV, "C": 0.12})
    assert w["C"] == pytest.approx(0.15)  # 0.17 requested, trimmed to the default
    w, _, problems = rw(mcfg, {"B": up(code="RETURN_TO_DEFAULT")}, prev={**PREV, "B": 0.20}, promoted=("B",))
    assert w["B"] == pytest.approx(0.20) and "default" in problems[0]


def test_resolve_weights_demotion_and_disabled_d(mcfg):
    w, _, _ = rw(mcfg, {"B": up(), "D": up()}, demoted={"B": "half"})
    assert w["B"] == pytest.approx(0.15) and w["D"] == 0.0


def test_resolve_weights_speculative_cap(mcfg):
    cfg = _d_enabled(mcfg)
    prev = {"A": 0.55, "B": 0.15, "C": 0.20, "D": 0.0}
    w, _, _ = rw(cfg, {"D": up()}, prev=prev, promoted=("C", "D"))
    assert w["C"] + w["D"] <= 0.20 + 1e-12


def test_resolve_weights_bad_choices_become_keep(mcfg):
    w, _, problems = rw(mcfg, {"B": {"choice": "double"}, "A": WeightChoice(choice="up")})
    assert w["B"] == pytest.approx(0.15) and w["A"] == pytest.approx(0.60)
    assert any("weight B: invalid" in p for p in problems)


def test_sessions_since(market):
    idx = market["SPY"].index
    today = idx[-1].date().isoformat()
    assert d.sessions_since([], idx, today) == d.NEVER
    assert d.sessions_since([None, "junk"], idx, today) == d.NEVER
    assert d.sessions_since([idx[-4].date().isoformat()], idx, today) == 3
    assert d.sessions_since([idx[-10].date().isoformat(), idx[-2].date().isoformat()], idx, today) == 1
    assert d.sessions_since([today], idx, today) == 0
    assert d.sessions_since(["2030-01-01"], idx, today) == 0  # a future date counts as just changed
    assert d.sessions_since(["2026-09-18"], [], "2026-09-25") == 5  # no bars: business days
    assert d.sessions_since(["2026-09-18"], idx.tz_localize("UTC"), "2026-09-25") == 5


def test_sessions_since_change_reads_weight_history(market):
    idx = market["SPY"].index
    hist = [{"date": idx[-7].date().isoformat(), "changed": ["B"]},
            {"date": idx[-3].date().isoformat(), "changed": ["A", "C"]}, {"date": "x"}]
    out = d.sessions_since_change(hist, idx, idx[-1].date().isoformat())
    assert out == {"A": 2, "B": 6, "C": 2, "D": d.NEVER}


# --- CL-7 / CL-8 / CL-2 / CL-5: apply_review -------------------------------------------------------------------


@pytest.fixture
def review_setup(prices):
    lots = {"C": {"MSFT": Lot(10, 100.0, "2026-09-01", 90.0, 90.0)}, "B": {"QQQ": Lot(5, 100.0, "2026-09-20", 90.0)}}
    targets = [
        Target("SPY", "A", 30.0, None, "faber"),  # A increase: never touched
        Target("SPY", "B", 20.0, 95.0, "RSI2 entry"),
        Target("NVDA", "C", 8.0, 180.0, "breakout entry"),
        Target("AVGO", "C", 4.0, 300.0, "breakout entry"),
        Target("MSFT", "C", 0.0, 90.0, "closed below 50-day SMA"),  # exit
        Target("QQQ", "B", 5.0, 90.0, "hold"),
    ]
    return targets, lots, _ctx(prices)


def skip(symbol, sleeve, code="HALT_OR_ILLIQUID", evidence=("regime.label",), pid=None, **kw):
    """By default the skip is backed by a prediction "p-<SYMBOL>" about its own symbol (see `review`)."""
    return Skip(symbol=symbol, sleeve=sleeve, reason_code=code, evidence=list(evidence),
                prediction_id=f"p-{symbol}" if pid is None else pid, **kw)


def review(skips=(), halves=(), preds=None):
    """Default predictions: one "p-<SYMBOL>" per skipped symbol, plus "p1" (NVDA) for the halves."""
    if preds is None:
        preds = [pred(f"p-{s}", s) for s in dict.fromkeys(k.symbol for k in skips)] + [pred()]
    return RulesReview(journal_note="ok", skip_entries=list(skips), halve_sleeves=list(halves),
                       predictions=list(preds))


def by_key(targets):
    return {(t.sleeve, t.symbol): t for t in targets}


def test_review_cannot_skip_sleeve_a(review_setup):
    targets, lots, ctx = review_setup
    log = []
    out, vetoes = d.apply_review(targets, review([skip("SPY", "A")]), lots, log, ctx=ctx, date=DATE)
    assert by_key(out)[("A", "SPY")].qty == 30.0 and vetoes == []
    assert any("CL-7" in line for line in log)
    halve_a = Halve(sleeve="A", reason_code="HALT_OR_ILLIQUID", evidence=["regime.label"], prediction_id="p1")
    out, vetoes = d.apply_review(targets, review(halves=[halve_a]), lots, log, ctx=ctx, date=DATE)
    assert by_key(out)[("A", "SPY")].qty == 30.0 and vetoes == []


def test_review_skip_is_per_sleeve(review_setup):
    targets, lots, ctx = review_setup
    log = []
    out, vetoes = d.apply_review(targets, review([skip("SPY", "B")]), lots, log, ctx=ctx, date=DATE)
    k = by_key(out)
    assert k[("B", "SPY")].qty == 0.0 and k[("A", "SPY")].qty == 30.0
    assert vetoes == [{"date": DATE, "sleeve": "B", "symbol": "SPY", "fraction": 1.0, "rule_qty": 20.0,
                       "current_qty": 0.0, "stop": 95.0, "reason_code": "HALT_OR_ILLIQUID", "prediction_id": "p-SPY",
                       "event_date": "", "verified": False}]
    assert "skipped by review" in k[("B", "SPY")].reason
    assert targets[1].qty == 20.0  # inputs are not mutated


def test_review_never_touches_exits_holds_or_stops(review_setup):
    targets, lots, ctx = review_setup
    log = []
    out, vetoes = d.apply_review(targets, review([skip("MSFT", "C"), skip("QQQ", "B")]), lots, log, ctx=ctx,
                                 date=DATE)
    k = by_key(out)
    assert k[("C", "MSFT")] == targets[4] and k[("B", "QQQ")] == targets[5] and vetoes == []
    assert any("no increase to skip" in line for line in log)


def test_review_halve_and_skip_precedence(review_setup):
    targets, lots, ctx = review_setup
    halve_c = Halve(sleeve="C", reason_code="HALT_OR_ILLIQUID", evidence=["regime.label"], prediction_id="p1")
    out, vetoes = d.apply_review(targets, review([skip("NVDA", "C")], [halve_c]), lots, [], ctx=ctx, date=DATE)
    k = by_key(out)
    assert k[("C", "NVDA")].qty == 0.0 and k[("C", "AVGO")].qty == pytest.approx(2.0)
    assert k[("C", "AVGO")].stop == 300.0  # stop untouched
    assert sorted((v["symbol"], v["fraction"]) for v in vetoes) == [("AVGO", 0.5), ("NVDA", 1.0)]


def test_review_halve_of_an_add_halves_only_the_increase(prices):
    lots = {"D": {"BTC/USD": Lot(1.0, 100.0, "2026-09-01", 80.0)}}
    t = [Target("BTC/USD", "D", 3.0, 80.0, "donchian")]
    h = Halve(sleeve="D", reason_code="CORPORATE_ACTION", evidence=["regime.label"], prediction_id="p1")
    out, vetoes = d.apply_review(t, review(halves=[h]), lots, [], ctx=_ctx(prices), date=DATE)
    assert out[0].qty == pytest.approx(2.0) and vetoes[0]["current_qty"] == 1.0 and vetoes[0]["rule_qty"] == 3.0


def test_review_earnings_rules(review_setup):
    targets, lots, ctx = review_setup
    ok = skip("NVDA", "C", code="EARNINGS_IN_WINDOW", event_date="2026-09-29", verified=True)
    out, vetoes = d.apply_review(targets, review([ok]), lots, [], ctx=ctx, date=DATE)
    assert by_key(out)[("C", "NVDA")].qty == 0.0 and vetoes[0]["event_date"] == "2026-09-29"
    for bad in (skip("SPY", "B", code="EARNINGS_IN_WINDOW", event_date="2026-09-29"),  # C only
                skip("NVDA", "C", code="EARNINGS_IN_WINDOW"),  # no date
                skip("NVDA", "C", code="EARNINGS_IN_WINDOW", event_date="soon"),
                skip("NVDA", "C", code="EARNINGS_IN_WINDOW", event_date="2026-09-24"),  # already past
                skip("NVDA", "C", code="EARNINGS_IN_WINDOW", event_date="2026-10-20")):  # outside 5 sessions
        log = []
        out, vetoes = d.apply_review(targets, review([bad]), lots, log, ctx=ctx, date=DATE)
        assert vetoes == [] and by_key(out)[(bad.sleeve, bad.symbol)].qty > 0, bad
        assert any("ignored" in line for line in log)


def test_review_earnings_verified_is_forced_false():
    targets = [Target("NVDA", "C", 5.0, 90.0, "entry")]
    item = skip("NVDA", "C", code="EARNINGS_IN_WINDOW", event_date="2026-09-29", verified=True)
    out, vetoes = d.apply_review(targets, review([item]), {}, [], date=DATE)
    assert out[0].qty == 0.0 and vetoes[0]["verified"] is False  # no earnings calendar yet (C-18)
    assert item.verified is True  # the input is not mutated


def test_review_scheduled_event_rules(review_setup):
    targets, lots, ctx = review_setup
    good = skip("SPY", "B", code="SCHEDULED_EVENT", event_date="2026-09-28")
    _, vetoes = d.apply_review(targets, review([good]), lots, [], ctx=ctx, date=DATE)
    assert len(vetoes) == 1
    for bad in (skip("SPY", "B", code="SCHEDULED_EVENT", event_date=DATE),  # today is not the next session
                skip("SPY", "B", code="SCHEDULED_EVENT", event_date="2026-10-09"),
                skip("SPY", "B", code="SCHEDULED_EVENT")):
        _, vetoes = d.apply_review(targets, review([bad]), lots, [], ctx=ctx, date=DATE)
        assert vetoes == [], bad
    t = [Target("BTC/USD", "D", 1.0, 80.0, "entry")]
    _, vetoes = d.apply_review(t, review([skip("BTC/USD", "D", code="SCHEDULED_EVENT", event_date="2026-09-28")]),
                               {}, [], ctx=ctx, date=DATE)
    assert vetoes == []  # B and C only


def test_review_data_suspect_needs_data_problems_or_price_field(prices):
    ctx = _ctx(prices)
    targets = [Target("MSFT", "C", 5.0, 90.0, "entry"), Target("NVDA", "C", 5.0, 90.0, "entry")]
    cases = {
        ("MSFT", ("data_problems[MSFT]",)): True,
        ("MSFT", ("data_problems[0]",)): True,  # the string names MSFT
        ("NVDA", ("rule_signals.C.indicators[NVDA].close",)): True,
        ("NVDA", ("regime.label",)): False,
        ("NVDA", ("rule_signals.C.indicators[NVDA].volume_ratio",)): False,  # not a price field
        ("NVDA", ("rule_signals.C.indicators[AVGO].close",)): False,  # another symbol's price
        ("NVDA", ("data_problems[0]",)): False,  # that problem is about MSFT
    }
    for (sym, ev), want in cases.items():
        _, vetoes = d.apply_review(targets, review([skip(sym, "C", code="DATA_SUSPECT", evidence=ev)]), {}, [],
                                   ctx=ctx, date=DATE)
        assert bool(vetoes) is want, (sym, ev)
    h = Halve(sleeve="C", reason_code="DATA_SUSPECT", evidence=["rule_signals.C.indicators[AVGO].close"],
              prediction_id="p1")
    _, vetoes = d.apply_review(targets, review(halves=[h]), {}, [], ctx=ctx, date=DATE)
    assert len(vetoes) == 2  # a sleeve-wide halve only needs the field shape


def test_review_restricted_codes_after_cl9(review_setup):
    targets, lots, ctx = review_setup
    _, vetoes = d.apply_review(targets, review([skip("SPY", "B", code="CORPORATE_ACTION")]), lots, [], ctx=ctx,
                               allowed_codes=RESTRICTED_SKIP_CODES, date=DATE)
    assert vetoes == []
    _, vetoes = d.apply_review(targets, review([skip("SPY", "B")]), lots, [], ctx=ctx,
                               allowed_codes=RESTRICTED_SKIP_CODES, date=DATE)
    assert len(vetoes) == 1


def test_review_evidence_and_prediction_required(review_setup):
    targets, lots, ctx = review_setup
    for bad in (skip("SPY", "B", evidence=["news.cnbc"]), skip("SPY", "B", evidence=[]),
                skip("SPY", "B", pid="nope"), skip("SPY", "B", pid="")):
        _, vetoes = d.apply_review(targets, review([bad]), lots, [], ctx=ctx, date=DATE)
        assert vetoes == [], bad
    _, vetoes = d.apply_review(targets, review([skip("SPY", "B")], preds=()), lots, [], ctx=ctx, date=DATE)
    assert vetoes == []


def test_review_with_cfg_cleans_predictions_first(mcfg, review_setup):
    targets, lots, ctx = review_setup
    log = []
    r = review([skip("SPY", "B", pid="bad")], preds=[pred("bad", symbol="GME")])
    _, vetoes = d.apply_review(targets, r, lots, log, ctx=ctx, date=DATE, cfg=mcfg)
    assert vetoes == [] and any("allowlist" in line for line in log)


def test_review_old_call_signature_still_works(review_setup):
    targets, lots, _ = review_setup
    log = []
    out, vetoes = d.apply_review(targets, review([skip("SPY", "B")]), lots, log)  # no ctx: shape checks only
    assert by_key(out)[("B", "SPY")].qty == 0.0 and vetoes[0]["date"] == ""
    old = SimpleNamespace(skip_entries=["SPY", "NVDA"], halve_sleeves=["C", "A"], journal_note="old")
    log = []
    out, vetoes = d.apply_review(targets, old, lots, log)
    assert out == targets and vetoes == []  # old string skips have no reason code (CL-8)
    assert sum("ignored" in line for line in log) == 4
    assert d.apply_review(targets, None, lots, []) == (targets, [])


def test_review_accepts_a_dict_and_survives_garbage(review_setup):
    targets, lots, ctx = review_setup
    raw = review([skip("SPY", "B")]).model_dump()
    raw["skip_entries"].append({"symbol": "NVDA"})  # invalid item: dropped by the parser
    log = []
    out, vetoes = d.apply_review(targets, raw, lots, log, ctx=ctx)
    assert len(vetoes) == 1 and vetoes[0]["date"] == DATE  # date taken from the context
    assert any("dropped" in line for line in log)
    out, vetoes = d.apply_review(targets, "not json", lots, log)
    assert out == targets and vetoes == []


def test_review_empty_targets():
    assert d.apply_review([], review([skip("SPY", "B")]), {}, []) == ([], [])


# --- CL-11 / CL-14: eligibility and stop menu -----------------------------------------------------------------


def test_eligibility_follows_cl11(mcfg, market):
    el = d.eligibility(mcfg, market, PERM_ALL)
    spy, iwm = market["SPY"]["close"], market["IWM"]["close"]
    assert spy.iloc[-1] > ind.sma(spy, 200).iloc[-1] and iwm.iloc[-1] < ind.sma(iwm, 200).iloc[-1]
    assert "SPY" in el["B"] and "IWM" not in el["B"]
    assert {"NVDA", "AVGO"} <= el["C"] and "AAPL" not in el["C"]
    assert el["A"] == {"SPY", "EFA", "IEF", "DBC", "VNQ", "BIL"}
    assert el["D"] == set()  # D is off
    none = d.eligibility(mcfg, market, {"A": 1.0, "B": 0.0, "C": 0.0, "D": 1.0})
    assert none["B"] == set() and none["C"] == set()
    assert d.eligibility(_d_enabled(mcfg), market, PERM_ALL)["D"] == {"BTC/USD", "ETH/USD"}
    assert d.eligibility(mcfg, market, {})["B"] == set()  # a missing permission counts as 0


def test_eligibility_short_history_is_not_eligible(mcfg, market):
    bars = dict(market)
    bars["SPY"] = market["SPY"].iloc[-50:]
    bars["NVDA"] = market["NVDA"].iloc[-100:]
    el = d.eligibility(mcfg, bars, PERM_ALL)
    assert "SPY" not in el["B"] and "NVDA" not in el["C"]


def test_stop_menu_numbers(mcfg, market):
    df = market["NVDA"]
    price = float(df["close"].iloc[-1])
    menu = d.stop_menu("C", df, mcfg.policy)
    assert menu["rule"] == pytest.approx(strat.rule_stop("C", df, mcfg.policy))
    assert menu["tight"] == pytest.approx(price - 0.5 * (price - menu["rule"]))
    assert menu["keep"] == menu["rule"]
    lot = Lot(1, 100, "2026-01-01", 42.0)
    assert d.stop_menu("C", df, mcfg.policy, lot)["keep"] == 42.0
    assert d.stop_menu("A", market["SPY"], mcfg.policy, lot) == {"rule": None, "tight": None, "keep": None}
    flat = df.copy()
    flat[["open", "high", "low", "close"]] = 50.0
    assert d.stop_menu("B", flat, mcfg.policy)["rule"] is None  # zero ATR: no usable stop
    assert d.stop_menu("B", df.iloc[:5], mcfg.policy)["rule"] is None  # too short for ATR20
    assert d.stop_menu("B", None, mcfg.policy, lot)["keep"] == 42.0


def test_is_deviation():
    assert not d.is_deviation(0.10, 0.10, 0.0, 0.2)
    assert not d.is_deviation(0.09, 0.10, 0.0, 0.2)  # 10% apart, same direction
    assert d.is_deviation(0.07, 0.10, 0.0, 0.2)
    assert d.is_deviation(0.05, 0.05, 0.05, 0.2) is False  # both hold
    assert d.is_deviation(0.049, 0.05, 0.05, 0.2)  # small trim against a hold: different direction
    assert d.is_deviation(0.0, 0.05, 0.05, 0.2)
    assert not d.is_deviation(0.0, 0.0, 0.0, 0.2)


# --- the Claude book: resolve_actions ------------------------------------------------------------------------


def test_no_actions_every_key_follows_the_rule(mcfg, market, book):
    res = resolve(mcfg, market, book, decision())
    assert isinstance(res, ResolvedDecision)
    expected = {"A:SPY", "A:BIL", "B:SPY", "C:NVDA", "C:MSFT", "B:IWM", "A:EFA"}
    assert set(res.targets) == expected
    for rt in res.targets.values():
        assert rt.source == "rule" and rt.pct == pytest.approx(rt.rule_pct) and not rt.is_deviation
    efa = res.targets["A:EFA"]
    assert efa.pct == pytest.approx(0.05) and efa.current_pct == pytest.approx(0.05)  # held, no rule target
    assert res.targets["B:SPY"].stop == book["rules"][2].stop
    assert res.targets["A:SPY"].stop is None
    assert res.journal_note == "Followed the rules."


def test_unmentioned_keys_follow_the_rule(mcfg, market, book):
    dec = decision([act("SPY", "B", stop="tight")])
    res = resolve(mcfg, market, book, dec)
    b = res.targets["B:SPY"]
    menu = d.stop_menu("B", market["SPY"], mcfg.policy)
    assert b.source == "action" and not b.is_deviation and b.stop == pytest.approx(menu["tight"])
    assert all(rt.source == "rule" for k, rt in res.targets.items() if k != "B:SPY")


def test_deviation_without_a_record_is_dropped(mcfg, market, book):
    a = act("AVGO", "C", "pct", target_pct_equity=0.03, reason_code="TREND_STRENGTHENING",
            evidence=["rule_signals.C.indicators[AVGO].volume_ratio"])
    res = resolve(mcfg, market, book, decision([a]))
    assert dropped(res, "C:AVGO") and "CL-13" in " ".join(res.problems)
    assert res.targets["C:AVGO"].source == "rule" and res.targets["C:AVGO"].pct == 0.0
    res = resolve(mcfg, market, book, decision([a.model_copy(update={"prediction_id": "p1"})],
                                               [pred("p1", "AVGO")]))
    t = res.targets["C:AVGO"]
    assert t.source == "action" and t.is_deviation and t.pct == pytest.approx(0.03) and t.prediction_id == "p1"
    assert t.stop == pytest.approx(d.stop_menu("C", market["AVGO"], mcfg.policy)["rule"])


def test_deviation_needs_a_deviation_code(mcfg, market, book):
    a = act("MSFT", "C", "exit", reason_code="FOLLOW_RULE", prediction_id="p1")
    res = resolve(mcfg, market, book, decision([a], [pred("p1", "MSFT")]))
    assert dropped(res, "C:MSFT") and res.targets["C:MSFT"].pct == pytest.approx(0.03)


def test_pct_size_is_always_a_deviation_and_is_clipped(mcfg, market, book):
    rule_pct = res_pct = resolve(mcfg, market, book, decision()).targets["A:SPY"].rule_pct
    same = act("SPY", "A", "pct", target_pct_equity=res_pct)
    res = resolve(mcfg, market, book, decision([same]))
    assert dropped(res, "A:SPY")  # FOLLOW_RULE cannot carry a pct size
    same = same.model_copy(update={"reason_code": "REGIME_RISK", "prediction_id": "p1"})
    res = resolve(mcfg, market, book, decision([same], [pred("p1", "SPY")]))
    assert res.targets["A:SPY"].is_deviation and res.targets["A:SPY"].pct == pytest.approx(rule_pct)
    big = act("NVDA", "C", "pct", target_pct_equity=0.5, reason_code="TREND_STRENGTHENING", prediction_id="p1")
    res = resolve(mcfg, market, book, decision([big], [pred()]))
    assert res.targets["C:NVDA"].pct == pytest.approx(0.10)  # 10% single-stock cap
    assert any("clipped" in p for p in res.problems)
    neg = big.model_copy(update={"target_pct_equity": -0.2})
    assert resolve(mcfg, market, book, decision([neg], [pred()])).targets["C:NVDA"].pct == 0.0
    nan = big.model_copy(update={"target_pct_equity": float("nan")})
    res = resolve(mcfg, market, book, decision([nan], [pred()]))
    assert dropped(res, "C:NVDA") and res.targets["C:NVDA"].source == "rule"


def test_half_rule_and_hold_sizes(mcfg, market, book):
    half = act("SPY", "B", "half_rule")
    res = resolve(mcfg, market, book, decision([half]))
    assert dropped(res, "B:SPY")  # half the rule is a deviation
    half = half.model_copy(update={"reason_code": "REGIME_RISK", "prediction_id": "p1"})
    res = resolve(mcfg, market, book, decision([half], [pred("p1", "SPY")]))
    b = res.targets["B:SPY"]
    assert b.pct == pytest.approx(0.5 * b.rule_pct) and b.is_deviation
    hold = act("NVDA", "C", "hold", stop="keep")
    res = resolve(mcfg, market, book, decision([hold]))
    n = res.targets["C:NVDA"]
    assert n.source == "action" and not n.is_deviation and n.pct == pytest.approx(0.02)
    assert n.stop == pytest.approx(book["lots"]["C"]["NVDA"].stop)  # keep = the lot's stop


def test_unknown_symbol_or_missing_price_is_dropped(mcfg, market, book):
    res = resolve(mcfg, market, book, decision([act("ZZZZ", "C")]))
    assert dropped(res, "C:ZZZZ") and "C:ZZZZ" not in res.targets
    book["prices"].pop("AVGO")
    res = resolve(mcfg, market, book, decision([act("AVGO", "C")]))
    assert dropped(res, "C:AVGO") and "no price" in " ".join(res.problems)


def test_held_key_without_price_is_left_alone(mcfg, market, book):
    book["prices"].pop("MSFT")
    res = resolve(mcfg, market, book, decision([act("MSFT", "C", "exit", reason_code="TREND_WEAKENING")]))
    assert "C:MSFT" not in res.targets and any(p.startswith("C:MSFT: no price") for p in res.problems)


def test_b_eligibility(mcfg, market, book):
    up_iwm = act("IWM", "B", "pct", target_pct_equity=0.06, reason_code="MEAN_REVERSION_SETUP",
                 evidence=["rule_signals.B.indicators[IWM].rsi2"], prediction_id="p1")
    res = resolve(mcfg, market, book, decision([up_iwm], [pred("p1", "IWM")]))
    assert dropped(res, "B:IWM") and "CL-11" in " ".join(res.problems)
    res = resolve(mcfg, market, book, decision([act("SPY", "B")]))
    assert res.targets["B:SPY"].source == "action"
    res = resolve(mcfg, market, book, decision([act("SPY", "B")]), permissions={**PERM_ALL, "B": 0.0})
    assert dropped(res, "B:SPY")


def test_c_eligibility(mcfg, market, book):
    new = dict(size="pct", target_pct_equity=0.02, reason_code="TREND_STRENGTHENING", prediction_id="p1")
    res = resolve(mcfg, market, book, decision([act("AAPL", "C", **new)], [pred("p1", "AAPL")]))
    assert dropped(res, "C:AAPL")  # fails the trend template
    res = resolve(mcfg, market, book, decision([act("AVGO", "C", **new)], [pred("p1", "AVGO")]))
    assert res.targets["C:AVGO"].source == "action"
    res = resolve(mcfg, market, book, decision([act("AVGO", "C", **new)], [pred("p1", "AVGO")]),
                  permissions={**PERM_ALL, "C": 0.0})
    assert dropped(res, "C:AVGO")
    res = resolve(mcfg, market, book, decision([act("AVGO", "C", **new)], [pred("p1", "AVGO")]),
                  eligible={"A": set(), "B": set(), "C": set(), "D": set()})
    assert dropped(res, "C:AVGO")  # a precomputed eligibility map is honoured


def test_a_and_d_eligibility(mcfg, market, book):
    res = resolve(mcfg, market, book, decision([act("NVDA", "A", "pct", target_pct_equity=0.02,
                                                    reason_code="REGIME_RISK", prediction_id="p1")], [pred()]))
    assert dropped(res, "A:NVDA")
    res = resolve(mcfg, market, book, decision([act("BIL", "A", "pct", target_pct_equity=0.25,
                                                    reason_code="REGIME_RISK", prediction_id="p1")],
                                               [pred("p1", "BIL")]))
    assert res.targets["A:BIL"].pct == pytest.approx(0.25) and res.targets["A:BIL"].stop is None
    crypto = act("BTC/USD", "D", "pct", target_pct_equity=0.02, reason_code="TREND_STRENGTHENING",
                 prediction_id="p1")
    res = resolve(mcfg, market, book, decision([crypto], [pred("p1", "SPY")]))
    assert dropped(res, "D:BTC/USD")  # D is off (and BTC/USD is not on the allowlist while it is off)
    cfg = _d_enabled(mcfg)
    res = resolve(cfg, market, book, decision([crypto], [pred("p1", "BTC/USD")]))
    assert res.targets["D:BTC/USD"].source == "action"
    res = resolve(cfg, market, book, decision([crypto], [pred("p1", "BTC/USD")]),
                  permissions={**PERM_ALL, "D": 0.0})
    assert dropped(res, "D:BTC/USD")


def test_reductions_are_allowed_in_ineligible_names(mcfg, market, book):
    a = act("IWM", "B", "exit", reason_code="TREND_WEAKENING", evidence=["rule_signals.B.indicators[IWM].close"],
            prediction_id="p1")
    res = resolve(mcfg, market, book, decision([a], [pred("p1", "IWM")]))
    t = res.targets["B:IWM"]
    assert t.pct == 0.0 and t.is_deviation and t.source == "action"


def test_action_on_nothing_is_dropped(mcfg, market, book):
    res = resolve(mcfg, market, book, decision([act("AAPL", "C", "exit", reason_code="TREND_WEAKENING")]))
    assert dropped(res, "C:AAPL") and "nothing held" in " ".join(res.problems)


def test_reason_codes_are_sleeve_specific(mcfg, market, book):
    ev = ["rule_signals.C.indicators[NVDA].close"]
    res = resolve(mcfg, market, book, decision([act("NVDA", "C", "hold", reason_code="MEAN_REVERSION_SETUP",
                                                    evidence=ev)]))
    assert dropped(res, "C:NVDA")
    res = resolve(mcfg, market, book, decision([act("SPY", "B", reason_code="EARNINGS_IN_WINDOW")]))
    assert dropped(res, "B:SPY")
    res = resolve(mcfg, market, book, decision([act("SPY", "A", reason_code="SCHEDULED_EVENT")]))
    assert dropped(res, "A:SPY")
    res = resolve(mcfg, market, book, decision([act("SPY", "B", reason_code="MEAN_REVERSION_SETUP")]))
    assert res.targets["B:SPY"].source == "action"


def test_evidence_is_checked_for_every_action(mcfg, market, book):
    for ev in ([], ["news.cnbc"], ["regime.label", "rule_signals.C.indicators[AAPL].rs_pct"]):
        res = resolve(mcfg, market, book, decision([act("SPY", "B", evidence=ev)]))
        assert dropped(res, "B:SPY") and res.targets["B:SPY"].source == "rule", ev
    res = resolve(mcfg, market, book, decision([act("SPY", "B")]), ctx=None)
    assert dropped(res, "B:SPY")  # no context: nothing can be verified


def test_data_suspect_in_the_claude_book(mcfg, market, book):
    exit_msft = dict(size="exit", reason_code="DATA_SUSPECT", prediction_id="p1")
    res = resolve(mcfg, market, book, decision([act("MSFT", "C", **exit_msft, evidence=["regime.label"])],
                                               [pred("p1", "MSFT")]))
    assert dropped(res, "C:MSFT")
    res = resolve(mcfg, market, book, decision([act("MSFT", "C", **exit_msft, evidence=["data_problems[MSFT]"])],
                                               [pred("p1", "MSFT")]))
    assert res.targets["C:MSFT"].pct == 0.0 and res.targets["C:MSFT"].source == "action"


def test_duplicate_key_first_wins(mcfg, market, book):
    first = act("SPY", "B", stop="tight")
    second = act("SPY", "B", "exit", reason_code="REGIME_RISK", prediction_id="p1")
    res = resolve(mcfg, market, book, decision([first, second], [pred("p1", "SPY")]))
    b = res.targets["B:SPY"]
    assert b.pct == pytest.approx(b.rule_pct) and "duplicate" in " ".join(res.problems)
    bad_first = act("SPY", "B", evidence=[])
    res = resolve(mcfg, market, book, decision([bad_first, first]))
    assert res.targets["B:SPY"].source == "rule"  # the first counts even when it is dropped


def test_stop_floor_on_increases(mcfg, market, book):
    lot = book["lots"]["C"]["NVDA"]
    fresh = d.stop_menu("C", market["NVDA"], mcfg.policy)["rule"]
    assert lot.stop < fresh
    add = act("NVDA", "C", "pct", target_pct_equity=0.04, stop="keep", reason_code="TREND_STRENGTHENING",
              prediction_id="p1")
    res = resolve(mcfg, market, book, decision([add], [pred()]))
    assert res.targets["C:NVDA"].stop == pytest.approx(fresh)  # CL-14: raised to the rule stop
    none = add.model_copy(update={"stop": "none"})
    res = resolve(mcfg, market, book, decision([none], [pred()]))
    assert res.targets["C:NVDA"].stop == pytest.approx(fresh) and any("'none'" in p for p in res.problems)
    tight = add.model_copy(update={"stop": "tight"})
    res = resolve(mcfg, market, book, decision([tight], [pred()]))
    assert res.targets["C:NVDA"].stop > fresh  # tighter is allowed


def test_stops_never_widen_below_the_lot(mcfg, market, book):
    price = book["prices"]["NVDA"]
    book["lots"]["C"]["NVDA"].stop = 0.99 * price  # above the fresh rule stop
    res = resolve(mcfg, market, book, decision([act("NVDA", "C", "hold", stop="rule",
                                                    evidence=["rule_signals.C.indicators[NVDA].close"])]))
    assert res.targets["C:NVDA"].stop == pytest.approx(0.99 * price)
    res = resolve(mcfg, market, book, decision([act("SPY", "A", stop="rule")]))
    assert res.targets["A:SPY"].stop is None  # A has no stops


def test_increase_without_a_computable_stop_is_dropped(mcfg, market, book):
    cfg = _d_enabled(mcfg)
    bars = dict(market)
    bars["BTC/USD"] = market["BTC/USD"].iloc[-5:]
    crypto = act("BTC/USD", "D", "pct", target_pct_equity=0.02, reason_code="TREND_STRENGTHENING",
                 prediction_id="p1")
    res = d.resolve_actions(decision([crypto], [pred("p1", "BTC/USD")]), cfg=cfg, ctx=book["ctx"],
                            rule_targets=book["rules"], lots=book["lots"], bars=bars,
                            prices={**book["prices"], "BTC/USD": float(bars["BTC/USD"]["close"].iloc[-1])},
                            equity=EQ, permissions=PERM_ALL)
    assert dropped(res, "D:BTC/USD") and "CL-14" in " ".join(res.problems)


def test_predictions_are_cleaned(mcfg, market, book):
    preds = [pred("p1", prob=0.99, thr=80), pred("p2", symbol="GME"), pred("p1"), pred("p3", prob=0.01),
             pred("p4"), pred("p5")]
    dev = act("SPY", "B", "exit", reason_code="REGIME_RISK", prediction_id="p5")
    res = resolve(mcfg, market, book, decision([dev], preds))
    kept = {p.id: p for p in res.predictions}
    assert list(kept) == ["p1", "p3", "p4"]  # at most 3; GME and the duplicate id dropped
    assert kept["p1"].probability == 0.95 and kept["p1"].threshold_pct == 50.0
    assert kept["p3"].probability == 0.05
    assert dropped(res, "B:SPY")  # its prediction p5 was the 4th valid one, so it was not kept


def test_clean_predictions_directly(mcfg):
    log = []
    out = d.clean_predictions([{"id": "x", "symbol": "spy", "horizon": 5, "direction": "below",
                                "threshold_pct": -2, "probability": 0.4, "linked_decision": "weight:B"},
                               {"id": "bad"}, pred("n", prob=float("nan"))],
                              max_n=3, allowlist=mcfg.allowlist(), log=log)
    assert [p.symbol for p in out] == ["SPY"] and len(log) == 2
    assert d.clean_predictions(None, max_n=3, allowlist=[]) == []


def test_journal_and_likely_error_are_trimmed(mcfg, market, book):
    note = "One. Two! Three? Four. Five. Six. Seven."
    dec = decision(journal_note=note, likely_error=LikelyError(kind="omission", note="First. Second."))
    res = resolve(mcfg, market, book, dec)
    assert res.journal_note == "One. Two! Three? Four. Five."
    assert res.likely_error.note == "First." and res.likely_error.kind == "omission"
    assert d.trim_sentences("", 5) == "" and d.trim_sentences("No stop at all", 1) == "No stop at all"


def test_non_positive_equity_gives_no_targets(mcfg, market, book):
    for eq in (0.0, -5.0, float("nan"), None):
        res = resolve(mcfg, market, book, decision([act("SPY", "B")]), equity=eq)
        assert res.targets == {} and "equity" in res.problems[-1]


def test_decision_as_dict_and_sample_tag(mcfg, market, book):
    raw = decision([act("SPY", "B", stop="tight")]).model_dump()
    raw["actions"].append({"symbol": "NVDA"})  # invalid: dropped by the parser, the rest is kept
    res = resolve(mcfg, market, book, raw, sample=2, weights={"A": 0.55}, weight_reasons={"A": {"choice": "keep"}})
    assert res.sample == 2 and res.weights == {"A": 0.55} and res.weight_reasons == {"A": {"choice": "keep"}}
    assert res.targets["B:SPY"].sample == 2 and res.targets["A:SPY"].sample is None
    assert any("actions[NVDA]" in p for p in res.problems)


def test_rule_targets_can_be_plans_or_a_dict(mcfg, market, book):
    from trader.models import SleevePlan
    plan = SleevePlan("B", 1.0, targets={t.symbol: t for t in book["rules"] if t.sleeve == "B"})
    res = d.resolve_actions(decision(), cfg=mcfg, ctx=book["ctx"], rule_targets={"B": plan}, lots={},
                            bars=market, prices=book["prices"], equity=EQ, permissions=PERM_ALL)
    assert set(res.targets) == {"B:SPY", "B:IWM"}
    res = d.resolve_actions(decision(), cfg=mcfg, ctx=book["ctx"], rule_targets=None, lots=None, bars=market,
                            prices=None, equity=EQ, permissions=None)
    assert res.targets == {}


# --- resolved_to_targets ---------------------------------------------------------------------------------------


def _rt(sleeve, symbol, pct, cur=0.0, rule=None, **kw):
    return ResolvedTarget(sleeve=sleeve, symbol=symbol, pct=pct, stop=kw.pop("stop", None),
                          rule_pct=pct if rule is None else rule, current_pct=cur, **kw)


def test_resolved_to_targets_converts_and_labels():
    prices = {"SPY": 500.0, "NVDA": 100.0}
    res = ResolvedDecision(weights={}, targets={
        "A:SPY": _rt("A", "SPY", 0.10, rationale="faber weight"),
        "C:NVDA": _rt("C", "NVDA", 0.03, rule=0.0, stop=90.0, source="action", reason_code="TREND_STRENGTHENING",
                      rationale="breakout volume", evidence=["x.y"], prediction_id="p1", is_deviation=True),
    })
    log = []
    targets, devs = d.resolved_to_targets(res, lots={}, prices=prices, equity=EQ, weights={"A": 0.55, "C": 0.15},
                                          date=DATE, log=log)
    k = by_key(targets)
    assert k[("A", "SPY")].qty == pytest.approx(20.0) and k[("A", "SPY")].reason == "rule: faber weight"
    assert k[("C", "NVDA")].qty == pytest.approx(30.0) and k[("C", "NVDA")].stop == 90.0
    assert k[("C", "NVDA")].reason == "claude TREND_STRENGTHENING: breakout volume"
    assert devs == [{"date": DATE, "symbol": "NVDA", "sleeve": "C", "rule_pct": 0.0, "claude_pct": 0.03,
                     "reason_code": "TREND_STRENGTHENING", "evidence": ["x.y"], "prediction_id": "p1"}]
    assert log == []


def test_resolved_to_targets_scales_only_increases_to_the_sleeve_weight():
    prices = {"NVDA": 100.0, "AVGO": 100.0, "MSFT": 100.0}
    lots = {"C": {"MSFT": Lot(100.0, 90.0, "2026-09-01", 85.0)}}  # 10% of equity held
    res = ResolvedDecision(weights={}, targets={
        "C:MSFT": _rt("C", "MSFT", 0.10, cur=0.10),
        "C:NVDA": _rt("C", "NVDA", 0.04, stop=90.0, source="action", is_deviation=True, reason_code="REGIME_RISK"),
        "C:AVGO": _rt("C", "AVGO", 0.04, stop=90.0),
    })
    log = []
    targets, devs = d.resolved_to_targets(res, lots=lots, prices=prices, equity=EQ, weights={"C": 0.15},
                                          date=DATE, log=log)
    k = by_key(targets)
    assert k[("C", "MSFT")].qty == 100.0  # the hold is untouched
    # Claude's deviation gives way first; the rule's own entry keeps its full size and its label
    assert k[("C", "AVGO")].qty == pytest.approx(40.0) and "cut" not in k[("C", "AVGO")].reason
    assert k[("C", "NVDA")].qty == pytest.approx(10.0)
    assert sum(t.qty * 100.0 for t in targets) == pytest.approx(0.15 * EQ)
    assert "deviating increases scaled by 0.25" in log[0]
    assert len(devs) == 1 and devs[0]["symbol"] == "NVDA"
    assert devs[0]["claude_pct"] == pytest.approx(0.01)  # the deviation records what was actually targeted


def test_resolved_to_targets_zero_weight_blocks_increases_but_keeps_holds_and_exits():
    prices = {"BTC/USD": 100.0, "ETH/USD": 50.0}
    lots = {"D": {"ETH/USD": Lot(10.0, 40.0, "2026-09-01", 30.0)}}
    res = ResolvedDecision(weights={}, targets={
        "D:BTC/USD": _rt("D", "BTC/USD", 0.02, stop=80.0),
        "D:ETH/USD": _rt("D", "ETH/USD", 0.0, cur=0.005),
    })
    targets, _ = d.resolved_to_targets(res, lots=lots, prices=prices, equity=EQ, weights={}, date=DATE, log=[])
    k = by_key(targets)
    assert k[("D", "BTC/USD")].qty == 0.0 and k[("D", "ETH/USD")].qty == 0.0


def test_resolved_to_targets_hold_snaps_to_lot_and_skips_missing_prices():
    prices = {"SPY": 3.0}
    lots = {"A": {"SPY": Lot(1 / 3, 3.0, "2026-09-01")}}
    res = ResolvedDecision(weights={}, targets={"A:SPY": _rt("A", "SPY", (1 / 3) * 3.0 / EQ, cur=(1 / 3) * 3.0 / EQ),
                                                "A:EFA": _rt("A", "EFA", 0.1)})
    log = []
    targets, _ = d.resolved_to_targets(res, lots=lots, prices=prices, equity=EQ, weights={"A": 0.6}, date=DATE,
                                       log=log)
    assert len(targets) == 1 and targets[0].qty == lots["A"]["SPY"].qty
    assert "A/EFA: no price" in log[0]
    assert d.resolved_to_targets(res, lots=lots, prices=prices, equity=0.0, weights={}, date=DATE, log=log) == ([], [])


# --- round trip with the real sleeves ------------------------------------------------------------------------


def test_round_trip_with_rule_plans_follows_the_rules(mcfg, market, prices):
    as_of = market["SPY"].index[-1]
    weights = {"A": 0.55, "B": 0.20, "C": 0.15, "D": 0.0}
    sl, pol = mcfg.sleeves, mcfg.policy
    plans = {"A": strat.sleeve_a(market, sl["A"], EQ * weights["A"], {}, pol, as_of),
             "B": strat.sleeve_b(market, sl["B"], EQ * weights["B"], {}, pol, EQ, 1.0),
             "C": strat.sleeve_c(market, sl["C"], EQ * weights["C"], {}, pol, EQ, 1.0)}
    ctx = _ctx(prices)
    res = d.resolve_actions(decision(), cfg=mcfg, ctx=ctx, rule_targets=plans, lots={}, bars=market, prices=prices,
                            equity=EQ, permissions=PERM_ALL)
    targets, devs = d.resolved_to_targets(res, lots={}, prices=prices, equity=EQ, weights=weights, date=DATE, log=[])
    rule = {(t.sleeve, t.symbol): t for p in plans.values() for t in p.targets.values()}
    got = by_key(targets)
    assert set(got) == set(rule) and devs == []
    for key, t in rule.items():
        assert got[key].qty == pytest.approx(t.qty, rel=1e-9) and got[key].stop == t.stop
        assert got[key].reason.startswith("rule: ")
    assert all(math.isfinite(t.qty) for t in targets)


def test_resolved_decision_round_trip_with_weights_and_actions(mcfg, market, book):
    """resolve_weights -> resolve_actions -> resolved_to_targets on one decision."""
    dec = decision([act("SPY", "B", stop="tight")],
                   sleeve_weights=SleeveWeightChoices(B=WeightChoice(choice="up", reason_code="SIGNAL_COUNT_CHANGE",
                                                                     evidence=["signal_count.B"])))
    w, reasons, problems = d.resolve_weights(dec.sleeve_weights, cfg=mcfg, prev=PREV, rule=RULE,
                                             sessions_since_change={}, breakers=CALM, ctx=book["ctx"])
    res = resolve(mcfg, market, book, dec, weights=w)
    targets, devs = d.resolved_to_targets(res, lots=book["lots"], prices=book["prices"], equity=EQ, weights=w,
                                          date=DATE, log=[])
    assert w["B"] == pytest.approx(0.20) and reasons["B"]["changed"] and problems == []
    assert by_key(targets)[("B", "SPY")].reason.startswith("claude FOLLOW_RULE")
    assert devs == []
    for s in ("A", "B", "C", "D"):
        notional = sum(t.qty * book["prices"][t.symbol] for t in targets if t.sleeve == s)
        held = sum(l.qty * book["prices"][sym] for sym, l in book["lots"].get(s, {}).items())
        assert notional <= max(w[s] * EQ, held) + 1e-6


# --- robustness ----------------------------------------------------------------------------------------------


def test_nan_rule_stop_and_qty_do_not_leak(mcfg, market, book):
    book["rules"][2] = Target("SPY", "B", float("nan"), float("nan"), "RSI2 entry")
    res = resolve(mcfg, market, book, decision())
    b = res.targets["B:SPY"]
    assert b.stop is None and b.pct == 0.0 and b.rule_pct == 0.0  # the risk engine sets its own stop


def test_rate_limit_value_none_counts_as_never_changed(mcfg):
    w, _, problems = rw(mcfg, {"B": up()}, since={"B": None})
    assert w["B"] == pytest.approx(0.20) and problems == []


def test_review_with_a_bad_run_date_checks_only_the_date_format(review_setup):
    targets, lots, ctx = review_setup
    ok = skip("NVDA", "C", code="EARNINGS_IN_WINDOW", event_date="2030-01-02")
    _, vetoes = d.apply_review(targets, review([ok]), lots, [], ctx=ctx, date="not a date")
    assert len(vetoes) == 1 and vetoes[0]["date"] == "not a date"
    bad = skip("NVDA", "C", code="EARNINGS_IN_WINDOW", event_date="next week")
    _, vetoes = d.apply_review(targets, review([bad]), lots, [], ctx=ctx, date="not a date")
    assert vetoes == []


def test_review_halve_with_nothing_to_halve_is_logged(prices):
    h = Halve(sleeve="B", reason_code="HALT_OR_ILLIQUID", evidence=["regime.label"], prediction_id="p1")
    log = []
    out, vetoes = d.apply_review([Target("SPY", "A", 3.0, None, "faber")], review(halves=[h]), {}, log,
                                 ctx=_ctx(prices), date=DATE)
    assert vetoes == [] and any("no increase to halve" in line for line in log)


# --- review fixes: fail-closed defaults, windows, predictions, position limits, bad numbers --------------------


def _vetoed(item, date, targets=None, **kw):
    targets = targets or [Target(item.symbol, item.sleeve, 5.0, 90.0, "entry")]
    _, vetoes = d.apply_review(targets, review([item]), {}, [], date=date, **kw)
    return bool(vetoes)


def test_session_after_skips_weekends_and_nyse_holidays():
    from datetime import date as Date
    assert d.session_after(Date(2026, 9, 22)) == Date(2026, 9, 23)
    assert d.session_after(Date(2026, 9, 25)) == Date(2026, 9, 28)  # Friday -> Monday
    assert d.session_after(Date(2026, 9, 4)) == Date(2026, 9, 8)  # Labor Day Monday is closed
    assert d.session_after(Date(2026, 11, 25)) == Date(2026, 11, 27)  # Thanksgiving Thursday is closed
    assert d.session_after(Date(2026, 9, 25), 5) == Date(2026, 10, 2)


def test_scheduled_event_must_be_exactly_the_next_session():
    ev = lambda date, when: _vetoed(skip("SPY", "B", code="SCHEDULED_EVENT", event_date=when), date)  # noqa: E731
    assert ev("2026-09-22", "2026-09-23")  # Tuesday -> Wednesday
    assert not ev("2026-09-22", "2026-09-24")  # two sessions ahead
    assert ev("2026-09-25", "2026-09-28")  # Friday -> Monday
    assert not ev("2026-09-25", "2026-09-26")  # a Saturday is not a session
    assert not ev("2026-09-25", "2026-09-29")
    assert not ev("2026-09-04", "2026-09-07")  # Labor Day
    assert ev("2026-09-04", "2026-09-08")
    assert ev("2026-11-25", "2026-11-27") and not ev("2026-11-25", "2026-11-26")  # Thanksgiving


def test_earnings_window_is_today_to_the_fifth_session():
    ev = lambda date, when: _vetoed(skip("NVDA", "C", code="EARNINGS_IN_WINDOW", event_date=when), date)  # noqa: E731
    assert ev("2026-09-25", "2026-09-25")  # after today's close, before the fill
    assert ev("2026-09-25", "2026-10-02")  # the 5th session
    assert not ev("2026-09-25", "2026-10-05")  # the 6th session (C-18)
    assert not ev("2026-09-25", "2026-09-24")
    assert ev("2026-11-20", "2026-11-30") and not ev("2026-11-20", "2026-12-01")  # Thanksgiving is not a session


def test_skip_prediction_must_be_about_the_skipped_symbol(review_setup):
    targets, lots, ctx = review_setup
    r = review([skip("SPY", "B", pid="p1")])  # p1 is about NVDA and linked to an NVDA action
    log = []
    _, vetoes = d.apply_review(targets, r, lots, log, ctx=ctx, date=DATE)
    assert vetoes == [] and any("about NVDA, not SPY" in line for line in log)
    linked = pred("p1").model_copy(update={"linked_decision": "skip:SPY"})
    _, vetoes = d.apply_review(targets, review([skip("SPY", "B", pid="p1")], preds=[linked]), lots, [], ctx=ctx,
                               date=DATE)
    assert len(vetoes) == 1  # a prediction about another symbol may back the skip it names
    halve_b = Halve(sleeve="B", reason_code="HALT_OR_ILLIQUID", evidence=["regime.label"], prediction_id="p1")
    _, vetoes = d.apply_review(targets, review(halves=[halve_b]), lots, [], ctx=ctx, date=DATE)
    assert len(vetoes) == 1  # a sleeve-wide halve has no symbol: any kept prediction backs it


def test_review_cleans_predictions_without_cfg(review_setup):
    targets, lots, ctx = review_setup
    four = [pred("a"), pred("b"), pred("c"), pred("d", "SPY")]
    for kw in ({"ctx": ctx}, {}):  # the context's limit, or CL-5's 3 for the old call
        log = []
        _, vetoes = d.apply_review(targets, review([skip("SPY", "B", pid="d")], preds=four), lots, log,
                                   date=DATE, **kw)
        assert vetoes == [] and any("at most 3" in line for line in log), kw
    small = {**ctx, "allowlist": ["NVDA"]}  # SPY is not on the context's allowlist
    _, vetoes = d.apply_review(targets, review([skip("SPY", "B")]), lots, [], ctx=small, date=DATE)
    assert vetoes == []
    one = {**ctx, "limits": {"max_predictions_per_day": 1}}
    two = [pred("a"), pred("b", "SPY")]
    _, vetoes = d.apply_review(targets, review([skip("SPY", "B", pid="b")], preds=two), lots, [], ctx=one, date=DATE)
    assert vetoes == []
    _, vetoes = d.apply_review(targets, review([skip("SPY", "B", pid="b")], preds=two[::-1]), lots, [], ctx=one,
                               date=DATE)
    assert len(vetoes) == 1


def test_review_leaves_a_nan_target_to_the_risk_engine(prices):
    t = [Target("SPY", "B", float("nan"), 95.0, "RSI2 entry"), Target("NVDA", "C", 5.0, 90.0, "entry")]
    halve_b = Halve(sleeve="B", reason_code="HALT_OR_ILLIQUID", evidence=["regime.label"], prediction_id="p1")
    out, vetoes = d.apply_review(t, review([skip("SPY", "B")], [halve_b]), {}, [], ctx=_ctx(prices), date=DATE)
    assert out[0] is t[0] and vetoes == []
    assert all(math.isfinite(v["rule_qty"]) for v in vetoes)


def test_data_suspect_accepts_context_menu_keys(mcfg, market, book, prices):
    ctx = _ctx(prices)
    ctx["menus"] = {"C:NVDA": {"sleeve": "C", "symbol": "NVDA", "price": prices["NVDA"]},
                    "C:AVGO": {"sleeve": "C", "symbol": "AVGO", "price": prices["AVGO"]}}
    targets = [Target("NVDA", "C", 5.0, 90.0, "entry")]
    for ev, want in ((["menus[C:NVDA].price"], True), (["menus[C:AVGO].price"], False)):
        _, vetoes = d.apply_review(targets, review([skip("NVDA", "C", code="DATA_SUSPECT", evidence=ev)]), {}, [],
                                   ctx=ctx, date=DATE)
        assert bool(vetoes) is want, ev
    book["ctx"] = ctx
    a = act("NVDA", "C", "exit", reason_code="DATA_SUSPECT", evidence=["menus[C:NVDA].price"], prediction_id="p1")
    res = resolve(mcfg, market, book, decision([a], [pred()]))
    assert res.targets["C:NVDA"].source == "action" and res.targets["C:NVDA"].pct == 0.0


def test_is_deviation_exact_boundary():
    assert not d.is_deviation(0.08, 0.10, 0.0, 0.2)  # exactly 20% of the larger: not more than 20%
    assert d.is_deviation(0.0799, 0.10, 0.0, 0.2)


def test_watch_tier_blocks_rule_and_default_moves_too(mcfg):
    watch = SimpleNamespace(drawdown=0.06, watch=True, halted=False)
    for choice in ("rule", "default"):
        w, _, problems = rw(mcfg, {"C": up(choice=choice)}, breakers=watch)
        assert w["C"] == pytest.approx(0.10) and "RISK-10" in problems[0], choice
        w, _, _ = rw(mcfg, {"C": up(choice=choice)})
        assert w["C"] == pytest.approx(0.15), choice  # the same move is allowed off the watch tier


def test_bad_rule_quantity_on_a_held_lot_holds(mcfg, market, book):
    iwm = book["lots"]["B"]["IWM"]
    for bad in (float("nan"), None, float("inf")):
        book["rules"][5] = Target("IWM", "B", bad, iwm.stop, "hold")
        res = resolve(mcfg, market, book, decision())
        t = res.targets["B:IWM"]
        assert t.pct == pytest.approx(t.current_pct) and t.rule_pct == pytest.approx(t.current_pct), bad
        assert any("B:IWM: the rule's target quantity is not a number" in p for p in res.problems)
        targets, _ = d.resolved_to_targets(res, lots=book["lots"], prices=book["prices"], equity=EQ,
                                           weights={"A": 0.6, "B": 0.2, "C": 0.15}, date=DATE, log=[])
        assert by_key(targets)[("B", "IWM")].qty == iwm.qty
    book["rules"][5] = Target("IWM", "B", -5.0, iwm.stop, "hold")
    res = resolve(mcfg, market, book, decision())
    assert res.targets["B:IWM"].pct == 0.0 and any("negative" in p for p in res.problems)  # as risk.py: long only


def test_non_numeric_resolved_share_holds():
    lots = {"B": {"IWM": Lot(10.0, 100.0, "2026-09-01", 90.0)}}
    res = ResolvedDecision(weights={}, targets={"B:IWM": _rt("B", "IWM", float("nan"), cur=0.01)})
    log = []
    targets, _ = d.resolved_to_targets(res, lots=lots, prices={"IWM": 100.0}, equity=EQ, weights={"B": 0.2},
                                       date=DATE, log=log)
    assert targets[0].qty == 10.0 and "not a number" in log[0]


def test_rule_targets_in_other_shapes_are_read_or_reported(mcfg, market, book):
    exit_iwm = Target("IWM", "B", 0.0, 90.0, "exit signal")
    for shape in ([exit_iwm], {"B": {"IWM": exit_iwm}}, {"B": [exit_iwm]}):
        res = d.resolve_actions(decision(), cfg=mcfg, ctx=book["ctx"], rule_targets=shape, lots=book["lots"],
                                bars=market, prices=book["prices"], equity=EQ, permissions=PERM_ALL)
        assert res.targets["B:IWM"].pct == 0.0 and res.targets["B:IWM"].rationale == "exit signal", shape
    res = d.resolve_actions(decision(), cfg=mcfg, ctx=book["ctx"], rule_targets={"B": "IWM"}, lots=book["lots"],
                            bars=market, prices=book["prices"], equity=EQ, permissions=PERM_ALL)
    assert any("is not a Target" in p for p in res.problems)


def test_nan_lot_stop_does_not_bypass_the_stop_floor(mcfg, market, book):
    book["lots"]["C"]["NVDA"].stop = float("nan")
    fresh = d.stop_menu("C", market["NVDA"], mcfg.policy)["rule"]
    assert d.stop_menu("C", market["NVDA"], mcfg.policy, book["lots"]["C"]["NVDA"])["keep"] == pytest.approx(fresh)
    for stop in ("keep", "rule", "tight"):
        add = act("NVDA", "C", "pct", target_pct_equity=0.04, stop=stop, reason_code="TREND_STRENGTHENING",
                  prediction_id="p1")
        res = resolve(mcfg, market, book, decision([add], [pred()]))
        t = res.targets["C:NVDA"]
        assert t.source == "action" and math.isfinite(t.stop) and t.stop >= fresh - 1e-9, stop
    hold = act("NVDA", "C", "hold", stop="keep", evidence=["rule_signals.C.indicators[NVDA].close"])
    assert resolve(mcfg, market, book, decision([hold])).targets["C:NVDA"].stop == pytest.approx(fresh)
    short = {**market, "NVDA": market["NVDA"].iloc[-5:]}  # no rule stop can be computed
    res = d.resolve_actions(decision([hold.model_copy(update={"stop": "rule"})]), cfg=mcfg, ctx=book["ctx"],
                            rule_targets=book["rules"], lots=book["lots"], bars=short, prices=book["prices"],
                            equity=EQ, permissions=PERM_ALL)
    assert res.targets["C:NVDA"].source == "action" and res.targets["C:NVDA"].stop is None  # not NaN


def test_deviation_prediction_must_be_about_the_symbol_or_linked(mcfg, market, book):
    a = act("AVGO", "C", "pct", target_pct_equity=0.03, reason_code="TREND_STRENGTHENING", prediction_id="p1")
    res = resolve(mcfg, market, book, decision([a], [pred("p1", "NVDA")]))
    assert dropped(res, "C:AVGO") and "about NVDA, not AVGO" in " ".join(res.problems)
    for link in ("action:C:AVGO", "action:AVGO", " Action : C : avgo "):
        linked = pred("p1", "NVDA").model_copy(update={"linked_decision": link})
        res = resolve(mcfg, market, book, decision([a], [linked]))
        assert res.targets["C:AVGO"].source == "action", link


def _limited(cfg, **limits):
    c = _cfg_copy(cfg)
    for s, n in limits.items():
        c.playbook["sleeves"][s]["max_positions"] = n
    return c


def test_claude_new_positions_respect_max_positions(mcfg, market, book):
    cfg = _limited(mcfg, C=3)  # NVDA and MSFT are held: one slot left
    new = dict(size="pct", target_pct_equity=0.02, reason_code="TREND_STRENGTHENING")
    elig = {"A": set(), "B": {"SPY", "DIA"}, "C": {"AVGO", "HD", "JPM"}, "D": set()}
    acts = [act("AVGO", "C", prediction_id="pa", **new), act("HD", "C", prediction_id="ph", **new)]
    res = resolve(cfg, market, book, decision(acts, [pred("pa", "AVGO"), pred("ph", "HD")]), eligible=elig)
    assert res.targets["C:AVGO"].source == "action"
    assert dropped(res, "C:HD") and "C-5" in " ".join(res.problems) and res.targets["C:HD"].pct == 0.0
    out_msft = act("MSFT", "C", "exit", reason_code="TREND_WEAKENING", prediction_id="pm")
    res = resolve(cfg, market, book, decision(acts + [out_msft], [pred("pa", "AVGO"), pred("ph", "HD"),
                                                                  pred("pm", "MSFT")]), eligible=elig)
    assert {k for k in ("C:AVGO", "C:HD", "C:MSFT") if res.targets[k].source == "action"} == {"C:AVGO", "C:HD",
                                                                                          "C:MSFT"}
    assert sum(1 for rt in res.targets.values() if rt.sleeve == "C" and rt.pct > 0) == 3  # an exit frees a slot
    dia = act("DIA", "B", prediction_id="pd", **new)  # B holds IWM and the rule enters SPY: B-1 allows 2
    res = resolve(mcfg, market, book, decision([dia], [pred("pd", "DIA")]), eligible=elig)
    assert dropped(res, "B:DIA") and "B-1" in " ".join(res.problems)
    assert res.targets["B:SPY"].pct > 0 and res.targets["B:IWM"].pct > 0  # the rule's own entry is never undone


def test_resolved_to_targets_undoes_new_positions_over_the_limit():
    prices = {"IWM": 100.0, "SPY": 100.0, "DIA": 100.0, "QQQ": 100.0}
    lots = {"B": {"IWM": Lot(40.0, 100.0, "2026-09-01", 90.0)}}
    claude = dict(rule=0.0, stop=90.0, source="action", reason_code="TREND_STRENGTHENING", is_deviation=True,
                  prediction_id="p1")
    res = ResolvedDecision(weights={}, targets={
        "B:IWM": _rt("B", "IWM", 0.04, cur=0.04), "B:SPY": _rt("B", "SPY", 0.05, stop=90.0),
        "B:DIA": _rt("B", "DIA", 0.03, **claude), "B:QQQ": _rt("B", "QQQ", 0.03, **claude)})
    for limit, undone in ((2, {"DIA", "QQQ"}), (3, {"QQQ"}), (None, set())):
        log = []
        targets, devs = d.resolved_to_targets(res, lots=lots, prices=prices, equity=EQ, weights={"B": 0.25},
                                              date=DATE, log=log, position_limits=None if limit is None else {"B": limit})
        k = by_key(targets)
        assert {s for s in ("DIA", "QQQ") if k[("B", s)].qty == 0.0} == undone, limit
        assert {r["symbol"] for r in devs} == {"DIA", "QQQ"} - undone
        assert sum("new position undone" in line for line in log) == len(undone)
        assert k[("B", "SPY")].qty == pytest.approx(50.0) and k[("B", "IWM")].qty == 40.0
    assert d.max_positions(load_config()) == {"B": 2, "C": 5}


def test_rule_increase_cut_by_the_weight_is_labelled_and_recorded():
    prices = {"MSFT": 100.0, "NVDA": 100.0}
    for held, want_qty, recorded in ((80.0, 20.0, True), (55.0, 45.0, False)):
        lots = {"C": {"MSFT": Lot(held, 90.0, "2026-09-01", 85.0)}}
        res = ResolvedDecision(weights={}, targets={
            "C:MSFT": _rt("C", "MSFT", held * 100 / EQ, cur=held * 100 / EQ),
            "C:NVDA": _rt("C", "NVDA", 0.05, stop=90.0, rationale="breakout")})
        log = []
        targets, devs = d.resolved_to_targets(res, lots=lots, prices=prices, equity=EQ, weights={"C": 0.10},
                                              date=DATE, log=log)
        k = by_key(targets)
        assert k[("C", "NVDA")].qty == pytest.approx(want_qty) and k[("C", "MSFT")].qty == held
        assert k[("C", "NVDA")].reason == "rule: breakout (cut to fit the sleeve weight)"
        assert "follow the rule scaled" in log[0]
        if recorded:  # 0.05 -> 0.02 is more than 20% below the rule
            assert devs == [{"date": DATE, "symbol": "NVDA", "sleeve": "C", "rule_pct": 0.05, "claude_pct": 0.02,
                             "reason_code": "WEIGHT_CAP", "evidence": [], "prediction_id": ""}]
        else:
            assert devs == []


def test_holdings_above_the_weight_are_logged_not_sold():
    lots = {"A": {"SPY": Lot(200.0, 100.0, "2026-09-01")}}
    res = ResolvedDecision(weights={}, targets={"A:SPY": _rt("A", "SPY", 0.20, cur=0.20),
                                                "A:EFA": _rt("A", "EFA", 0.05)})
    log = []
    targets, _ = d.resolved_to_targets(res, lots=lots, prices={"SPY": 100.0, "EFA": 100.0}, equity=EQ,
                                       weights={"A": 0.10}, date=DATE, log=log)
    k = by_key(targets)
    assert k[("A", "SPY")].qty == 200.0 and k[("A", "EFA")].qty == 0.0
    assert "holds are not sold" in log[0]


def test_sessions_since_reads_odd_dates_and_rows():
    from datetime import date as Date
    import pandas as pd
    for when in ("2026-09-18", "2026-09-18T00:00:00+00:00", 20260918, Date(2026, 9, 18),
                 pd.Timestamp("2026-09-18", tz="UTC")):
        assert d.sessions_since([when], [], "2026-09-25") == 5, when
    assert d.sessions_since(["2026-09-04"], [], "2026-09-08") == 1  # Labor Day is not a session
    assert d.sessions_since([123, True, None, ""], [], "2026-09-25") == d.NEVER
    for bad_run_date in ("", None, "junk"):
        assert d.sessions_since(["2026-09-18"], [], bad_run_date) == 0  # no change today
    problems = []
    hist = ["junk", None, {"date": "not a date", "changed": ["B"]}, {"date": "2026-09-21", "changed": "B"},
            {"date": "2026-09-18T00:00:00+00:00", "changed": ["C"]}]
    out = d.sessions_since_change(hist, [], "2026-09-25", problems)
    assert out == {"A": d.NEVER, "B": d.NEVER, "C": 5, "D": d.NEVER}
    assert len(problems) == 4 and any("not YYYY-MM-DD" in p for p in problems)
    assert any("not a list of sleeves" in p for p in problems)
