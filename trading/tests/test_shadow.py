"""Shadow veto lots (CL-9), predictions (CL-5, M-7) and deviations (CL-13, M-5). Synthetic bars only."""
import json
import math

import numpy as np
import pandas as pd
import pytest

from conftest import make_bars
from trader import metrics, shadow, strategies
from trader.schemas import Prediction
from trader.state import BookState


def frame(closes, opens=None, lows=None, highs=None, start="2026-01-05", freq="B"):
    c = np.asarray(closes, dtype=float)
    o = np.asarray(opens, dtype=float) if opens is not None else np.r_[c[0], c[:-1]]
    lo = np.asarray(lows, dtype=float) if lows is not None else np.minimum(o, c) - 0.5
    hi = np.asarray(highs, dtype=float) if highs is not None else np.maximum(o, c) + 0.5
    idx = pd.date_range(start=start, periods=len(c), freq=freq)
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c, "volume": 1e6}, index=idx)


def day(df, i):
    return df.index[i].date().isoformat()


def veto(date, sleeve="B", symbol="SPY", fraction=1.0, rule_qty=10.0, current_qty=0.0, stop=90.0,
         code="SCHEDULED_EVENT"):
    return {"date": date, "sleeve": sleeve, "symbol": symbol, "fraction": fraction, "rule_qty": rule_qty,
            "current_qty": current_qty, "stop": stop, "reason_code": code, "prediction_id": "p1"}


# --- B case: RSI(2) dip that recovers ------------------------------------------------------------------

def b_bars():
    """Flat at 100, dip to 95 (signal, idx 25), then 97 (open 96), 101 (open 97, exit signal), 103 (open 102)."""
    closes = [100.0] * 25 + [95.0, 97.0, 101.0, 103.0]
    opens = [100.0] * 25 + [100.0, 96.0, 97.0, 102.0]
    return frame(closes, opens)


def test_open_veto_lots_sizes_and_filters():
    st = BookState(book="rules")
    added = shadow.open_veto_lots(st, [
        veto("2026-02-09"),                                               # skip: full vetoed increase
        veto("2026-02-09", symbol="QQQ", fraction=0.5, rule_qty=10, current_qty=2),  # halve an add
        veto("2026-02-09", sleeve="A", symbol="EFA"),                     # CL-7: A is never vetoed
        veto("2026-02-09", symbol="IWM", rule_qty=5, current_qty=5),      # no increase
        veto("2026-02-09", symbol="DIA", fraction=0.0),                   # nothing vetoed
    ], "2026-02-09")
    assert [lt["symbol"] for lt in added] == ["SPY", "QQQ"]
    assert added[0]["qty"] == 10 and added[0]["status"] == "pending_entry"
    assert added[1]["qty"] == pytest.approx(0.5 * 8)
    assert added[0]["reason_code"] == "SCHEDULED_EVENT" and added[0]["prediction_id"] == "p1"
    assert added[0]["id"] == "veto:rules:2026-02-09:B:SPY"


def test_open_veto_lots_rerun_replaces_only_pending_entry():
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto("2026-02-09", rule_qty=10)], "2026-02-09")
    shadow.open_veto_lots(st, [veto("2026-02-09", rule_qty=12)], "2026-02-09")
    assert len(st.shadow_lots) == 1 and st.shadow_lots[0]["qty"] == 12
    st.shadow_lots[0]["status"] = "open"
    assert shadow.open_veto_lots(st, [veto("2026-02-09", rule_qty=20)], "2026-02-09") == []
    assert st.shadow_lots[0]["qty"] == 12


def test_b_veto_lot_closes_under_sleeve_rules(cfg):
    """A shadow veto lot enters at the next open and closes on B-4(a) at the next open; R is hand-checked."""
    df = b_bars()
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 25))], day(df, 25))
    events = shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 28))
    lot = st.shadow_lots[0]
    assert [e["event"] for e in events] == ["entered", "exit_signal", "closed"]
    assert lot["entry_date"] == day(df, 26) and lot["entry_price"] == 96.0
    assert lot["exit_signal_date"] == day(df, 27) and "5-day SMA" in lot["exit_reason"]
    assert lot["exit_date"] == day(df, 28) and lot["exit_price"] == 102.0
    costs = 10 * 96 * 5 / 1e4 + 10 * 102 * 5 / 1e4  # EX-5: 5 bps per side for ETFs
    assert lot["costs"] == pytest.approx(costs)
    assert lot["initial_risk"] == pytest.approx(10 * (96 - 90))
    r = ((102 - 96) * 10 - costs) / 60
    assert lot["R_net"] == pytest.approx(r)
    assert lot["veto_value"] == pytest.approx(-r)  # the veto missed a winner: negative value
    assert lot["value_usd"] == pytest.approx(-((102 - 96) * 10 - costs))
    assert lot["sessions_held"] == 3 and lot["status"] == "closed"


def test_day_by_day_equals_catch_up(cfg):
    df = b_bars()
    a, b = BookState(book="rules"), BookState(book="rules")
    for st in (a, b):
        shadow.open_veto_lots(st, [veto(day(df, 25))], day(df, 25))
    for i in range(25, 29):
        shadow.update_veto_lots(a, {"SPY": df}, cfg, day(df, i))
    shadow.update_veto_lots(b, {"SPY": df}, cfg, day(df, 28))
    assert a.shadow_lots == b.shadow_lots


def test_no_look_ahead_and_waits_for_bars(cfg):
    df = b_bars()
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 25))], day(df, 25))
    assert shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 25)) == []  # no bar after the signal yet
    assert st.shadow_lots[0]["status"] == "pending_entry"
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 26))
    assert st.shadow_lots[0]["status"] == "open"
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 27))
    assert st.shadow_lots[0]["status"] == "pending_exit"  # exit fills at the next open, not known yet
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 28))
    assert st.shadow_lots[0]["status"] == "closed"


def test_cost_bps_number_dict_state_override(cfg):
    df = b_bars()
    results = {}
    for label, arg, override in (("zero", 0.0, {}), ("dict", {"etf": 10}, {}), ("state", None, {"etf": 20})):
        st = BookState(book="rules", cost_model_bps=override)
        shadow.open_veto_lots(st, [veto(day(df, 25))], day(df, 25))
        shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 28), arg)
        results[label] = st.shadow_lots[0]
    assert results["zero"]["R_net"] == pytest.approx(1.0)  # (102 - 96) * 10 / 60 with no costs
    assert results["dict"]["costs"] == pytest.approx((96 + 102) * 10 * 10 / 1e4)
    assert results["state"]["costs"] == pytest.approx((96 + 102) * 10 * 20 / 1e4)


# --- C case: breakout that fails; the C-7 ratchet sets the exit ---------------------------------------------

def c_bars():
    closes = [100.0 + i for i in range(60)] + [161.0, 162.0, 152.0, 150.5, 149.0]
    opens = [100.0] + [100.0 + i - 1 for i in range(1, 60)] + [160.0, 161.0, 161.0, 152.0, 150.0]
    lows = [c - 1 for c in closes[:60]] + [160.0, 161.0, 151.0, 150.0, 148.0]
    highs = [max(o, c) + 0.5 for o, c in zip(opens, closes)]
    return frame(closes, opens, lows, highs)


def test_c_veto_lot_closes_on_ratcheted_stop(cfg):
    df = c_bars()
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 59), sleeve="C", symbol="NVDA", rule_qty=5, stop=150.0,
                                    code="EARNINGS_IN_WINDOW")], day(df, 59))
    shadow.update_veto_lots(st, {"NVDA": df}, cfg, day(df, 64))
    lot = st.shadow_lots[0]
    assert lot["initial_stop"] == 150.0
    assert lot["stop"] == 151.0  # C-7: raised to the lowest low of the prior 10 sessions
    assert lot["exit_signal_date"] == day(df, 63) and lot["exit_reason"] == "breakout stop hit"
    assert lot["entry_price"] == 160.0 and lot["exit_price"] == 150.0
    costs = 5 * 160 * 10 / 1e4 + 5 * 150 * 10 / 1e4  # stocks: 10 bps per side
    r = ((150 - 160) * 5 - costs) / (5 * 10)
    assert lot["R_net"] == pytest.approx(r)
    assert lot["veto_value"] == pytest.approx(-r) and lot["veto_value"] > 0  # the veto avoided a loser


def test_halved_veto_scales_value_by_fraction(cfg):
    df = c_bars()
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 59), sleeve="C", symbol="NVDA", rule_qty=10, stop=150.0,
                                    fraction=0.5)], day(df, 59))
    shadow.update_veto_lots(st, {"NVDA": df}, cfg, day(df, 64))
    lot = st.shadow_lots[0]
    assert lot["qty"] == 5
    assert lot["veto_value"] == pytest.approx(-0.5 * lot["R_net"])


def test_b_time_stop_closes_shadow_lot(cfg):
    closes = [100.0] * 30 + [100.0 - 0.1 * k for k in range(1, 16)]
    df = frame(closes)
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 29), stop=50.0)], day(df, 29))
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 44))
    lot = st.shadow_lots[0]
    assert "time stop" in lot["exit_reason"]
    assert lot["exit_signal_date"] == day(df, 39)  # 10 sessions held (B-4b)
    assert lot["exit_date"] == day(df, 40)


def test_d_veto_lot_uses_crypto_rules(cfg):
    closes = [100.0] * 30 + [101.0, 70.0, 69.0]
    df = frame(closes, start="2026-01-01", freq="D")
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 29), sleeve="D", symbol="BTC/USD", rule_qty=1, stop=80.0)],
                          day(df, 29))
    shadow.update_veto_lots(st, {"BTC/USD": df}, cfg, day(df, 32))
    lot = st.shadow_lots[0]
    assert lot["exit_reason"] == "crypto stop hit" and lot["status"] == "closed"
    assert lot["costs"] == pytest.approx((100 + 70) * 25 / 1e4)  # crypto: 25 bps per side


def test_gap_below_stop_uses_planned_risk(cfg):
    closes = [100.0] * 25 + [95.0, 92.0, 92.0]
    opens = [100.0] * 25 + [100.0, 93.0, 92.0]
    df = frame(closes, opens)
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 25), stop=94.0)], day(df, 25))
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 27), 0.0)
    lot = st.shadow_lots[0]
    assert lot["initial_risk"] == pytest.approx(10 * (95 - 94))  # signal close − stop, not a near-zero gap
    assert lot["exit_reason"] == "RSI2 disaster stop" and lot["R_net"] == pytest.approx(-1.0)


def test_missing_stop_uses_rule_stop(cfg):
    df = make_bars(n=120, seed=3)
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 100), stop=None)], day(df, 100))
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 101))
    expected = strategies.rule_stop("B", df.iloc[:101], cfg.policy)
    assert st.shadow_lots[0]["initial_stop"] == pytest.approx(expected)


def test_missing_symbol_and_bad_lot_never_raise(cfg):
    df = b_bars()
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 25), symbol="QQQ")], day(df, 25))
    st.shadow_lots.append({"id": "broken", "symbol": "SPY", "sleeve": "B", "status": "open", "date": day(df, 25)})
    assert shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 28)) == []
    assert st.shadow_lots[0]["status"] == "pending_entry"  # no QQQ bars: waits
    assert "problem" in st.shadow_lots[1]
    assert shadow.update_veto_lots(st, {}, cfg, day(df, 28)) == []


def test_nan_open_waits_for_clean_bar(cfg):
    df = b_bars()
    df.loc[df.index[26], "open"] = float("nan")
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 25))], day(df, 25))
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 26))
    assert st.shadow_lots[0]["status"] == "pending_entry"


# --- CL-9 summary and restriction -------------------------------------------------------------------------

def closed_lot(value, code="SCHEDULED_EVENT", date="2026-03-02", usd=None):
    return {"id": f"v{value}{date}", "status": "closed", "veto_value": value, "reason_code": code, "date": date,
            "value_usd": usd if usd is not None else value * 100}


def test_veto_summary_and_should_restrict():
    st = BookState(book="rules")
    st.shadow_lots = [closed_lot(-0.5), closed_lot(0.2, "DATA_SUSPECT"), closed_lot(-0.1),
                      {"id": "open", "status": "open", "reason_code": "HALT_OR_ILLIQUID", "date": "2026-03-02"}]
    s = shadow.veto_summary(st)
    assert s["n_scored"] == 3 and s["sum_value"] == pytest.approx(-0.4) and s["n_open"] == 1
    assert s["by_code"]["SCHEDULED_EVENT"] == {"n": 2, "sum": pytest.approx(-0.6)}
    assert s["by_code"]["DATA_SUSPECT"]["n"] == 1
    assert s["sum_value_usd"] == pytest.approx(-40.0)
    assert shadow.should_restrict(st, 3) is True
    assert shadow.should_restrict(st, 4) is False  # not enough scored vetoes yet
    st.shadow_lots.append(closed_lot(1.0))
    assert shadow.should_restrict(st, 3) is False  # vetoes are net positive


def test_veto_summary_since_and_empty():
    st = BookState(book="rules")
    assert shadow.veto_summary(st) == {"n_scored": 0, "sum_value": 0, "sum_value_usd": 0, "by_code": {},
                                       "n_open": 0, "n_expired": 0}
    assert shadow.should_restrict(st, 0) is False
    st.shadow_lots = [closed_lot(-1.0, date="2026-01-05"), closed_lot(0.3, date="2026-04-01")]
    assert shadow.veto_summary(st, since="2026-03-01")["n_scored"] == 1
    assert shadow.should_restrict(st, 1, since="2026-03-01") is False
    assert shadow.should_restrict(st, 1) is True


# --- CL-5 / M-7: predictions ---------------------------------------------------------------------------------

def geometric(n=400, growth=0.01, start="2024-01-01"):
    return frame(100 * (1 + growth) ** np.arange(n), start=start)


def test_base_rate_hand_checked():
    close = geometric()["close"]
    five_day = 1.01 ** 5 - 1  # 5.101% every time
    assert five_day * 100 > 5
    assert shadow.base_rate(close, 5, "above", 5.0) == 1.0
    assert shadow.base_rate(close, 5, "above", 6.0) == 0.0
    assert shadow.base_rate(close, 5, "below", 0.0) == 0.0
    assert shadow.base_rate(close.iloc[:30], 5, "above", 0.0) is None  # too little history


def test_base_rate_uses_only_the_lookback():
    c = np.r_[100 * 0.99 ** np.arange(200), 100 * 0.99 ** 199 * 1.01 ** np.arange(1, 101)]
    close = frame(c)["close"]
    assert shadow.base_rate(close, 5, "above", 0.0, lookback=60) == 1.0
    assert shadow.base_rate(close, 5, "above", 0.0) < 0.5


def test_base_rate_matches_a_plain_loop():
    close = make_bars(n=1500, seed=7)["close"]
    c = close.iloc[-(1260 + 20):].to_numpy()
    hits = [c[i + 20] < c[i] * (1 - 0.03) for i in range(len(c) - 20)]
    assert shadow.base_rate(close, 20, "below", -3.0) == pytest.approx(np.mean(hits))


def test_add_predictions_clips_drops_and_dedupes():
    df = geometric()
    st = BookState(book="claude")
    d = day(df, 300)
    preds = [Prediction(id="p1", symbol="SPY", horizon=5, direction="above", threshold_pct=80.0, probability=0.99,
                        linked_decision="action:B:SPY"),
             {"id": "p2", "symbol": "SPY", "horizon": 7, "direction": "above", "threshold_pct": 1, "probability": 0.5},
             {"id": "p3", "symbol": "SPY", "horizon": 20, "direction": "sideways", "threshold_pct": 1,
              "probability": 0.5},
             {"id": "p4", "symbol": "NOPE", "horizon": 20, "direction": "below", "threshold_pct": -1,
              "probability": 0.01}]
    stored = shadow.add_predictions(st, preds, date=d, bars={"SPY": df}, tags={"prompt_version": "abc"})
    assert [p["id"] for p in stored] == ["p1", "p4"]
    p1, p4 = stored
    assert p1["probability"] == 0.95 and p1["threshold_pct"] == 50.0  # CL-5 clipping
    assert p1["base_close"] == pytest.approx(df["close"].iloc[300]) and p1["base_date"] == d
    assert p1["base_rate"] == 0.0 and p1["resolve_after"] == 5 and p1["book"] == "claude"
    assert p1["tags"] == {"prompt_version": "abc"} and p1["uid"] == f"claude:{d}:p1"
    assert p4["probability"] == 0.05 and p4["base_close"] is None  # unknown symbol: kept, not scorable yet
    shadow.add_predictions(st, preds[:1], date=d, bars={"SPY": df})
    assert len(st.predictions) == 2  # rerun replaces, no duplicate


def test_prediction_resolves_and_is_scored():
    """Rulebook test: a prediction resolves and is scored (Brier and Brier_ref, M-7)."""
    df = make_bars(n=1400, seed=11)
    st = BookState(book="claude")
    i0 = 1300
    d = day(df, i0)
    preds = [{"id": "up", "symbol": "SPY", "horizon": 5, "direction": "above", "threshold_pct": 1.0,
              "probability": 0.7, "linked_decision": "action:B:SPY"},
             {"id": "down", "symbol": "SPY", "horizon": 20, "direction": "below", "threshold_pct": -2.0,
              "probability": 0.2, "linked_decision": "skip:SPY"}]
    shadow.add_predictions(st, preds, date=d, bars={"SPY": df.iloc[: i0 + 1]})
    assert shadow.resolve_predictions(st, {"SPY": df}, day(df, i0 + 4)) == []  # 4 bars: not yet
    done = shadow.resolve_predictions(st, {"SPY": df}, day(df, i0 + 5))
    assert [p["id"] for p in done] == ["up"]
    base = df["close"].iloc[i0]
    o_up = int(df["close"].iloc[i0 + 5] > base * 1.01)
    up = st.predictions[0]
    assert up["outcome"] == o_up and up["resolve_after_date"] == day(df, i0 + 5)
    assert up["brier"] == pytest.approx((0.7 - o_up) ** 2)
    assert up["brier_ref"] == pytest.approx((up["base_rate"] - o_up) ** 2)
    done = shadow.resolve_predictions(st, {"SPY": df}, day(df, i0 + 25))
    assert [p["id"] for p in done] == ["down"]
    o_dn = int(df["close"].iloc[i0 + 20] < base * 0.98)
    assert st.predictions[1]["outcome"] == o_dn
    assert shadow.resolve_predictions(st, {"SPY": df}, day(df, i0 + 30)) == []  # never resolved twice
    scores = metrics.prediction_scores(st.predictions, min_resolved=2)
    briers = [(0.7 - o_up) ** 2, (0.2 - o_dn) ** 2]
    refs = [p["brier_ref"] for p in st.predictions]
    assert scores["shown"] and scores["brier"] == pytest.approx(np.mean(briers), abs=1e-4)
    assert scores["skill"] == pytest.approx(1 - np.mean(briers) / np.mean(refs), abs=1e-3)


def test_prediction_base_filled_later_when_bars_arrive():
    df = geometric()
    st = BookState(book="claude")
    shadow.add_predictions(st, [{"id": "p", "symbol": "SPY", "horizon": 5, "direction": "above",
                                 "threshold_pct": 2.0, "probability": 0.6}], date=day(df, 300), bars=None)
    assert st.predictions[0]["base_close"] is None
    shadow.resolve_predictions(st, {"SPY": df}, day(df, 310))
    p = st.predictions[0]
    assert p["base_close"] == pytest.approx(df["close"].iloc[300]) and p["outcome"] == 1
    assert p["brier"] == pytest.approx(0.16) and p["brier_ref"] == pytest.approx(0.0)


# --- CL-13 / M-5: deviations ----------------------------------------------------------------------------------

def test_deviation_value_20d_hand_checked():
    closes = [50.0] * 40
    opens = [50.0] * 40
    closes[31] = 55.0  # close at t+20, where t = idx 11 is the fill bar after the decision (idx 10)
    df = frame(closes, opens)
    st = BookState(book="claude")
    rec = {"date": day(df, 10), "symbol": "NVDA", "sleeve": "C", "rule_pct": 0.01, "claude_pct": 0.03,
           "reason_code": "TREND_STRENGTHENING", "evidence": ["rule_signals.C.indicators[NVDA].rs_pct"],
           "prediction_id": "p1"}
    shadow.add_deviations(st, [rec, {"date": day(df, 10), "symbol": "X", "claude_pct": None}], {"model": "m"})
    assert len(st.deviations) == 1 and st.deviations[0]["tags"] == {"model": "m"}
    assert shadow.resolve_deviations(st, {"NVDA": df}, day(df, 30)) == []
    d = st.deviations[0]
    assert d["fill_ref"] == 50.0 and d["fill_date"] == day(df, 11) and d["value_20d"] is None
    done = shadow.resolve_deviations(st, {"NVDA": df}, day(df, 31))
    assert len(done) == 1
    assert d["value_20d"] == pytest.approx((0.03 - 0.01) * (55 / 50 - 1))
    assert d["resolved_date"] == day(df, 31)
    shadow.add_deviations(st, [rec])
    assert len(st.deviations) == 1 and st.deviations[0]["value_20d"] is not None  # resolved one kept


def test_deviation_missing_symbol_stays_open():
    st = BookState(book="claude")
    shadow.add_deviations(st, [{"date": "2026-03-02", "symbol": "ZZZ", "sleeve": "C", "rule_pct": 0.0,
                                "claude_pct": 0.02}])
    assert shadow.resolve_deviations(st, {}, "2026-06-01") == []
    assert st.deviations[0]["value_20d"] is None


def test_state_round_trip_keeps_shadow_records(tmp_path, cfg):
    df = b_bars()
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 25))], day(df, 25))
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 28))
    st.save(tmp_path)
    back = BookState.load("rules", tmp_path)
    assert back.shadow_lots[0]["R_net"] == pytest.approx(st.shadow_lots[0]["R_net"])
    assert not any(isinstance(v, float) and math.isnan(v) for v in back.shadow_lots[0].values())


def test_short_history_rule_stop_is_not_stored_as_nan(cfg):
    df = frame([100.0] * 8)  # fewer bars than ATR20 needs
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 5), stop=None)], day(df, 5))
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 7))
    lot = st.shadow_lots[0]
    assert lot["status"] == "pending_entry" and lot["stop"] is None and "too little history" in lot["problem"]
    json.dumps(st.shadow_lots, allow_nan=False)


# --- review fixes: more exits, gaps, expiry, bad opens --------------------------------------------------------

def test_c_veto_lot_exits_on_sma50(cfg):
    """C-8: the close drops under the 50-day SMA while above the stop and the prior 10-day low."""
    closes = [120.0] * 60 + [101.0, 100.0, 100.0, 100.0]
    opens = [120.0] * 60 + [120.0, 101.0, 100.5, 100.0]
    lows = [119.5] * 60 + [90.0, 99.5, 99.5, 99.5]
    df = frame(closes, opens, lows)
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 60), sleeve="C", symbol="NVDA", rule_qty=5, stop=85.0)], day(df, 60))
    shadow.update_veto_lots(st, {"NVDA": df}, cfg, day(df, 63), 0.0)
    lot = st.shadow_lots[0]
    assert lot["exit_reason"] == "closed below 50-day SMA" and lot["exit_signal_date"] == day(df, 61)
    assert lot["stop"] == 90.0  # C-7 ratchet to the prior 10-day low, still under the close
    assert lot["entry_price"] == 101.0 and lot["exit_price"] == 100.5
    assert lot["R_net"] == pytest.approx((100.5 - 101.0) * 5 / (5 * (101 - 85)))


def test_d_veto_lot_exits_on_donchian_zero(cfg):
    closes = list(np.linspace(100, 129, 30)) + [130.0, 110.0, 108.0]
    df = frame(closes, start="2026-01-01", freq="D")
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 29), sleeve="D", symbol="BTC/USD", rule_qty=1, stop=80.0)],
                          day(df, 29))
    shadow.update_veto_lots(st, {"BTC/USD": df}, cfg, day(df, 32), 0.0)
    lot = st.shadow_lots[0]
    assert lot["exit_reason"] == "donchian score 0" and lot["exit_signal_date"] == day(df, 31)
    assert lot["entry_price"] == 129.0 and lot["exit_price"] == 110.0
    assert lot["R_net"] == pytest.approx((110 - 129) / (129 - 80))


def test_risk_per_share_is_floored_at_planned_risk():
    assert shadow._risk_per_share(96.0, 90.0, 95.0) == pytest.approx(6.0)  # gap up: entry − stop
    assert shadow._risk_per_share(146.29, 146.28, 159.0) == pytest.approx(12.72)  # gap to just above the stop
    assert shadow._risk_per_share(93.0, 94.0, 95.0) == pytest.approx(1.0)  # gap below the stop
    assert shadow._risk_per_share(100.0, 101.0, 99.0) == pytest.approx(1.0)  # neither above: 1% of entry


def test_gap_to_just_above_stop_does_not_explode_r(cfg):
    """Safety: an entry 1 cent above the stop must not turn a 2-point loss into hundreds of R."""
    closes = [159.0] * 60 + [145.0, 144.0]
    opens = [159.0] * 60 + [146.29, 144.29]
    lows = [158.5] * 60 + [144.5, 143.5]
    df = frame(closes, opens, lows)
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 59), sleeve="C", symbol="NVDA", rule_qty=10, stop=146.28,
                                    code="EARNINGS_IN_WINDOW")], day(df, 59))
    shadow.update_veto_lots(st, {"NVDA": df}, cfg, day(df, 61), 0.0)
    lot = st.shadow_lots[0]
    assert lot["initial_risk"] == pytest.approx(10 * (159.0 - 146.28))
    assert lot["R_net"] == pytest.approx(-2.0 * 10 / (10 * 12.72))
    assert abs(lot["veto_value"]) < 0.2


def test_entry_expires_when_the_next_bar_is_days_late(cfg):
    """A halted name: the first bar after the signal comes a week later, so the DAY order would have lapsed."""
    df = b_bars().iloc[:26]
    resume = (pd.Timestamp(day(df, 25)) + pd.offsets.BDay(6)).date().isoformat()  # five sessions with no bar
    halted = pd.concat([df, frame([103.0] * 3, start=resume)])
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 25), code="HALT_OR_ILLIQUID")], day(df, 25))
    events = shadow.update_veto_lots(st, {"SPY": halted}, cfg, halted.index[-1].date().isoformat())
    lot = st.shadow_lots[0]
    assert lot["status"] == "expired" and "business days" in lot["expired_reason"]
    assert events[0]["event"] == "expired" and lot["entry_price"] is None
    s = shadow.veto_summary(st)
    assert s["n_scored"] == 0 and s["n_open"] == 0 and s["n_expired"] == 1
    assert shadow.update_veto_lots(st, {"SPY": halted}, cfg, halted.index[-1].date().isoformat()) == []


def test_entry_after_a_one_day_holiday_still_fills(cfg):
    df = b_bars().drop(b_bars().index[26])  # one missing session (a holiday)
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 25))], day(df, 25))
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 26))
    assert st.shadow_lots[0]["status"] in ("open", "pending_exit")


def test_bad_open_enters_and_exits_at_the_next_clean_open(cfg):
    """A NaN open that the feed never corrects must not park a lot forever."""
    df = b_bars()
    df = pd.concat([df, frame([103.0] * 3, start="2026-02-13")])
    df.loc[df.index[26], "open"] = float("nan")
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 25))], day(df, 25))
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 26), 0.0)
    assert st.shadow_lots[0]["status"] == "pending_entry"  # nothing clean yet: wait
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 27), 0.0)
    lot = st.shadow_lots[0]
    assert lot["entry_date"] == day(df, 27) and lot["entry_price"] == 97.0 and "next clean open" in lot["note"]
    assert lot["status"] == "pending_exit" and lot["exit_signal_date"] == day(df, 27)  # close 101 > SMA5
    df.loc[df.index[28], "open"] = 0.0  # the exit bar's open is bad too
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 28), 0.0)
    assert lot["status"] == "pending_exit"
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, 29), 0.0)
    assert lot["status"] == "closed" and lot["exit_date"] == day(df, 29) and lot["exit_price"] == 103.0
    assert lot["R_net"] == pytest.approx((103.0 - 97.0) / (97.0 - 90.0))  # entry − stop (above the planned 5)


def test_no_clean_open_in_the_window_expires(cfg):
    df = b_bars()
    df = pd.concat([df, frame([103.0] * 5, start="2026-02-13")])
    df.loc[df.index[26:30], "open"] = float("nan")
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(day(df, 25))], day(df, 25))
    shadow.update_veto_lots(st, {"SPY": df}, cfg, day(df, len(df) - 1))
    assert st.shadow_lots[0]["status"] == "expired"


def test_numpy_cost_bps_is_honoured(cfg):
    st = BookState(book="rules")
    assert shadow._cost_bps(np.int64(0), cfg, st, "SPY") == 0.0
    assert shadow._cost_bps(np.float32(7), cfg, st, "SPY") == 7.0
    assert shadow._cost_bps(None, cfg, st, "SPY") == 5.0


# --- CL-9 latch: policy minimum and owner reset --------------------------------------------------------------

def test_should_restrict_reads_policy_minimum_and_reset_date(cfg):
    assert cfg.policy["claude_limits"]["veto_min_scored"] == 30
    st = BookState(book="rules")
    st.shadow_lots = [closed_lot(-0.1, date=f"2026-03-{d:02d}") for d in range(1, 30)]
    assert shadow.should_restrict(st, policy=cfg) is False  # 29 scored
    st.shadow_lots.append(closed_lot(-0.1, date="2026-03-30"))
    assert shadow.should_restrict(st, policy=cfg) is True
    assert shadow.should_restrict(st, policy=cfg.policy) is True
    assert shadow.should_restrict(st) is True  # 30 without a policy too
    st.veto_reset_date = "2026-04-01"  # the owner reset the latch: a fresh count starts
    assert shadow.should_restrict(st, policy=cfg) is False
    st.shadow_lots += [closed_lot(-0.1, date="2026-04-02") for _ in range(30)]
    for i, lot in enumerate(st.shadow_lots[-30:]):
        lot["id"] = f"new{i}"
    assert shadow.should_restrict(st, policy=cfg) is True


# --- guide rule 6: deviations that lose cut Claude's freedom --------------------------------------------------

def test_deviation_summary_and_should_restrict_deviations(cfg):
    st = BookState(book="claude")
    st.deviations = [{"date": f"2026-03-{d:02d}", "symbol": "SPY", "sleeve": "B", "reason_code": "REGIME_RISK",
                      "value_20d": -0.001} for d in range(1, 30)]
    st.deviations.append({"date": "2026-03-30", "symbol": "SPY", "sleeve": "B", "value_20d": None})
    s = shadow.deviation_summary(st)
    assert s["n"] == 30 and s["n_resolved"] == 29 and s["sum_value_20d"] == pytest.approx(-0.029)
    assert s["by_code"]["REGIME_RISK"]["n"] == 29
    assert shadow.should_restrict_deviations(st, policy=cfg) is False  # 29 resolved
    st.deviations[-1]["value_20d"] = -0.001
    assert shadow.should_restrict_deviations(st, policy=cfg) is True
    st.deviations.append({"date": "2026-03-31", "symbol": "QQQ", "sleeve": "B", "value_20d": 0.05})
    assert shadow.should_restrict_deviations(st, policy=cfg) is False  # net positive
    st.deviations[-1]["value_20d"] = 0.0
    st.deviations_reset_date = "2026-03-15"
    assert shadow.should_restrict_deviations(st, policy=cfg) is False  # only 17 since the reset
    assert shadow.should_restrict_deviations(st, 10, policy=cfg) is True


# --- reruns and malformed records -----------------------------------------------------------------------------

def test_clear_pending_drops_a_discarded_attempt(cfg):
    df = b_bars()
    d, older = day(df, 25), day(df, 20)
    st = BookState(book="rules")
    shadow.open_veto_lots(st, [veto(d), veto(older, symbol="QQQ")], d)
    st.shadow_lots.append({**st.shadow_lots[0], "id": "entered", "status": "open"})
    st.predictions = [{"date": d, "outcome": None}, {"date": d, "outcome": 1}, {"date": older, "outcome": None}]
    st.deviations = [{"date": d, "value_20d": None}, {"date": older, "value_20d": None}]
    counts = shadow.clear_pending(st, d)
    assert counts == {"shadow_lots": 1, "predictions": 1, "deviations": 1}
    assert [lt["id"] for lt in st.shadow_lots] == [veto_id := shadow.veto_lot_id("rules", older, "B", "QQQ"),
                                                 "entered"] and veto_id
    assert len(st.predictions) == 2 and len(st.deviations) == 1
    shadow.open_veto_lots(st, [], d)  # the rerun had no veto: nothing from the first attempt is scored
    assert not any(lt["date"] == d and lt["status"] == "pending_entry" for lt in st.shadow_lots)


def test_resolvers_skip_malformed_records():
    df = geometric()
    st = BookState(book="claude")
    good = {"id": "g", "date": day(df, 300), "symbol": "SPY", "horizon": 5, "direction": "above",
            "threshold_pct": 2.0, "probability": 0.6, "base_close": float(df["close"].iloc[300]), "base_rate": 0.5,
            "outcome": None}
    st.predictions = [{"id": "no_date", "symbol": "SPY", "horizon": 5, "direction": "above", "outcome": None},
                      {**good, "id": "no_horizon", "horizon": None}, dict(good)]
    done = shadow.resolve_predictions(st, {"SPY": df}, day(df, 310))
    assert [p["id"] for p in done] == ["g"]
    assert "problem" in st.predictions[0] and "problem" in st.predictions[1]
    st.deviations = [{"symbol": "SPY", "claude_pct": 0.02, "rule_pct": 0.0},
                     {"date": day(df, 300), "symbol": "SPY", "claude_pct": None, "rule_pct": 0.0},
                     {"date": day(df, 300), "symbol": "SPY", "sleeve": "B", "claude_pct": 0.02, "rule_pct": 0.0}]
    done = shadow.resolve_deviations(st, {"SPY": df}, day(df, 340))
    assert len(done) == 1 and done[0]["value_20d"] > 0
    assert "problem" in st.deviations[0] and "problem" in st.deviations[1]


def test_deviation_bad_fill_open_uses_next_clean_open():
    closes = [50.0] * 40
    opens = [50.0] * 11 + [float("nan")] + [51.0] * 28
    closes[32] = 56.1  # 20 sessions after the fill bar (idx 12)
    df = frame(closes, opens)
    st = BookState(book="claude")
    shadow.add_deviations(st, [{"date": day(df, 10), "symbol": "NVDA", "sleeve": "C", "rule_pct": 0.0,
                                "claude_pct": 0.02}])
    shadow.resolve_deviations(st, {"NVDA": df}, day(df, 39))
    d = st.deviations[0]
    assert d["fill_date"] == day(df, 12) and d["fill_ref"] == 51.0 and d["resolved_date"] == day(df, 32)
    assert d["value_20d"] == pytest.approx(0.02 * (56.1 / 51 - 1))


def test_base_rate_observation_count_is_stored():
    df = geometric()
    st = BookState(book="claude")
    shadow.add_predictions(st, [{"id": "p", "symbol": "SPY", "horizon": 5, "direction": "above",
                                 "threshold_pct": 2.0, "probability": 0.6}], date=day(df, 300), bars={"SPY": df})
    assert st.predictions[0]["base_rate_n"] == 301 - 5  # 301 closes, 296 complete 5-day windows
    assert shadow.base_rate_stats(df["close"], 5, "above", 2.0, lookback=100) == (1.0, 100)
    shadow.resolve_predictions(st, {"SPY": df}, day(df, 310))
    scores = metrics.prediction_scores(st.predictions, min_resolved=1)
    assert scores["base_rate_full_window_share"] == 0.0 and "fewer than 1260" in scores["base_rate_note"]
