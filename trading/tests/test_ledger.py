"""Ledger tests (M-3, EX-4, EX-5, B-6, RISK-13 inputs, phase 1 items 1, 2, 4 and the reconcile fix)."""
import json
import math

import numpy as np
import pandas as pd
import pytest

from conftest import make_bars
from trader import ledger
from trader.models import Lot, Order, Target
from trader.state import BookState


def _state(book="rules"):
    return BookState(book=book)


def _lot(state, sleeve, sym):
    return state.lots.get(sleeve, {}).get(sym)


def _classes(sym):
    return "crypto" if "/" in sym else ("etf" if sym in {"SPY", "QQQ", "IWM", "DIA", "IEF", "BIL"} else "stock")


BPS = {"etf": 5, "stock": 10, "crypto": 25}


# --- apply_fill: M-3 bookkeeping -------------------------------------------------------------------


def test_add_partial_sell_close_gives_one_trade_with_right_r():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 100.0, "2026-09-01", stop=95.0, cost=1.0, entry_date="2026-08-31")
    ledger.apply_fill(s, "B", "SPY", 10, 104.0, "2026-09-02", stop=100.0, cost=1.0)
    lot = _lot(s, "B", "SPY")
    assert lot.qty == 20 and lot.entry_price == pytest.approx(102.0)
    assert lot.initial_risk_dollars == pytest.approx(50 + 40)  # add uses the stop at the add, not 95
    assert lot.stop == 100.0 and lot.initial_stop == 95.0
    ledger.apply_fill(s, "B", "SPY", -5, 106.0, "2026-09-03", cost=0.5)
    assert s.closed_trades == []  # a partial sell never makes a trade record
    assert lot.realized_pnl == pytest.approx(20.0) and lot.qty == 15
    ledger.apply_fill(s, "B", "SPY", -15, 101.0, "2026-09-04", cost=1.5, reason="exit")
    assert _lot(s, "B", "SPY") is None and "B" not in s.lots
    [t] = s.closed_trades
    assert t["realized_pnl"] == pytest.approx(5.0) and t["costs"] == pytest.approx(4.0)
    assert t["pnl"] == pytest.approx(1.0)
    assert t["initial_risk_dollars"] == pytest.approx(90.0)
    assert t["R"] == pytest.approx(round(1 / 90, 3))
    assert t["qty"] == pytest.approx(20) and t["entry_date"] == "2026-08-31" and t["fill_date"] == "2026-09-01"
    assert t["exit_price"] == pytest.approx((5 * 106 + 15 * 101) / 20)
    assert t["sessions_held"] == 4
    assert t["mae_R"] == pytest.approx(round((100 - 102) / 4.5, 3))
    assert t["mfe_R"] == pytest.approx(round((106 - 102) / 4.5, 3))
    assert t["lot_id"] == "rules:B:SPY:2026-08-31" and t["reason"] == "exit"
    assert [e["kind"] for e in t["events"]] == ["open", "add", "reduce", "reduce"]
    assert s.sleeve_pnl["B"]["realized"] == pytest.approx(t["pnl"])  # RISK-13 input matches the trade


def test_partial_reductions_realize_pnl_into_lot_and_sleeve():
    s = _state()
    ledger.apply_fill(s, "C", "NVDA", 10, 50.0, "2026-09-01", stop=45.0)
    ledger.apply_fill(s, "C", "NVDA", -4, 55.0, "2026-09-02", cost=0.2, reason="trim")
    lot = _lot(s, "C", "NVDA")
    assert lot.qty == 6 and lot.realized_pnl == pytest.approx(20.0) and lot.costs == pytest.approx(0.2)
    ev = lot.events[-1]
    assert ev["kind"] == "reduce" and ev["qty"] == 4 and ev["realized"] == pytest.approx(20.0)
    assert ev["reason"] == "trim" and ev["qty_after"] == 6
    assert set(ev) >= {"date", "kind", "qty", "price", "signal_close", "cost", "stop", "realized", "reason"}
    assert s.sleeve_pnl["C"]["realized"] == pytest.approx(19.8)
    assert s.closed_trades == []


def test_add_never_lowers_stop_and_risk_uses_the_stop_in_force():
    s = _state()
    ledger.apply_fill(s, "B", "QQQ", 10, 100.0, "2026-09-01", stop=95.0)
    ledger.apply_fill(s, "B", "QQQ", 10, 100.0, "2026-09-02", stop=90.0)
    lot = _lot(s, "B", "QQQ")
    assert lot.stop == 95.0  # never widened
    # M-3: the added shares are protected by the 95 stop that stays in force, not the 90 that was sent
    assert lot.initial_risk_dollars == pytest.approx(50 + 50)
    ledger.apply_fill(s, "B", "QQQ", 5, 100.0, "2026-09-03")  # no stop given: the lot's stop is the stop at add
    assert lot.initial_risk_dollars == pytest.approx(100 + 25)
    ledger.apply_fill(s, "B", "QQQ", 5, 100.0, "2026-09-04", stop=98.0)  # a higher stop is used and kept
    assert lot.initial_risk_dollars == pytest.approx(125 + 10) and lot.stop == 98.0


def test_sleeve_a_without_stop_has_no_r():
    s = _state()
    ledger.apply_fill(s, "A", "IEF", 10, 100.0, "2026-09-01")
    assert _lot(s, "A", "IEF").initial_risk_dollars == 0.0 and _lot(s, "A", "IEF").risk_per_share is None
    ledger.apply_fill(s, "A", "IEF", -10, 110.0, "2026-09-02")
    [t] = s.closed_trades
    assert t["R"] is None and t["mae_R"] is None and t["mfe_R"] is None and t["pnl"] == pytest.approx(100.0)


def test_stop_at_or_above_fill_gives_zero_risk_and_no_r():
    s = _state()
    ledger.apply_fill(s, "C", "AMD", 10, 100.0, "2026-09-01", stop=101.0)
    assert _lot(s, "C", "AMD").initial_risk_dollars == 0.0
    ledger.apply_fill(s, "C", "AMD", -10, 90.0, "2026-09-02")
    assert s.closed_trades[0]["R"] is None


@pytest.mark.parametrize("price", [float("nan"), 0.0, -1.0, None, "abc"])
def test_bad_price_raises_and_leaves_lots_alone(price):
    s = _state()
    with pytest.raises(ValueError):
        ledger.apply_fill(s, "B", "SPY", 5, price, "2026-09-01")
    assert s.lots == {}


def test_nan_quantity_raises_zero_quantity_is_a_no_op():
    s = _state()
    with pytest.raises(ValueError):
        ledger.apply_fill(s, "B", "SPY", float("nan"), 100.0, "2026-09-01")
    ledger.apply_fill(s, "B", "SPY", 0.0, 100.0, "2026-09-01")
    ledger.apply_fill(s, "B", "SPY", 1e-12, float("nan"), "2026-09-01")  # zero quantity: price never used
    assert s.lots == {} and s.sleeve_pnl == {}


def test_sell_without_lot_does_nothing_and_oversell_is_capped():
    s = _state()
    ledger.apply_fill(s, "C", "MSFT", -5, 100.0, "2026-09-01")
    assert s.lots == {} and s.closed_trades == []
    ledger.apply_fill(s, "C", "MSFT", 3, 100.0, "2026-09-01", stop=90.0)
    ledger.apply_fill(s, "C", "MSFT", -10, 110.0, "2026-09-02")
    [t] = s.closed_trades
    assert t["realized_pnl"] == pytest.approx(30.0)


def test_nan_stop_is_treated_as_missing():
    s = _state()
    ledger.apply_fill(s, "A", "SPY", 5, 100.0, "2026-09-01", stop=float("nan"))
    lot = _lot(s, "A", "SPY")
    assert lot.stop is None and lot.initial_risk_dollars == 0.0


def test_lot_id_stays_unique_when_reopened_on_same_date():
    s = _state()
    for _ in range(3):
        ledger.apply_fill(s, "B", "IWM", 1, 100.0, "2026-09-01", stop=95.0)
        ledger.apply_fill(s, "B", "IWM", -1, 101.0, "2026-09-01")
    ids = [t["lot_id"] for t in s.closed_trades]
    assert ids == ["rules:B:IWM:2026-09-01", "rules:B:IWM:2026-09-01#2", "rules:B:IWM:2026-09-01#3"]


def test_tags_stamped_at_open_and_kept_on_add():
    s = _state("claude")
    ledger.apply_fill(s, "C", "META", 2, 100.0, "2026-09-01", stop=92.0, tags={"prompt_version": "v1"})
    ledger.apply_fill(s, "C", "META", 2, 100.0, "2026-09-02", stop=92.0, tags={"prompt_version": "v2", "model": "m"})
    assert _lot(s, "C", "META").tags == {"prompt_version": "v1", "model": "m"}
    ledger.apply_fill(s, "C", "META", -4, 110.0, "2026-09-03")
    assert s.closed_trades[0]["tags"]["prompt_version"] == "v1"


# --- old state files ----------------------------------------------------------------------------------


def test_old_state_lots_load_and_close_with_r(tmp_path):
    path = BookState.path("rules", tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "book": "rules", "peak_equity": 1000.0, "some_old_field": 1,
        "lots": {"C": {"AAPL": {"qty": 10, "entry_price": 50.0, "entry_date": "2026-01-02",
                                "stop": 47.0, "initial_stop": 45.0}}},
    }))
    s = BookState.load("rules", tmp_path)
    lot = _lot(s, "C", "AAPL")
    assert lot.initial_risk_dollars == pytest.approx(50.0) and lot.bought_qty == 10 and lot.events == []
    ledger.apply_fill(s, "C", "AAPL", -10, 60.0, "2026-01-09", reason="exit")
    [t] = s.closed_trades
    assert t["R"] == pytest.approx(2.0) and t["lot_id"] == "rules:C:AAPL:2026-01-02"
    s.save(tmp_path)
    again = BookState.load("rules", tmp_path)
    assert again.closed_trades[0]["R"] == pytest.approx(2.0) and again.lots == {}


def test_state_round_trip_keeps_pending_orders_fills_and_events(tmp_path):
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 3, 100.0, "2026-09-01", stop=95.0)
    targets = [Target("NVDA", "C", 5, 90.0, "breakout")]
    ledger.record_orders(s, targets, [Order("NVDA", "buy", 5, 100.0)], [{"symbol": "NVDA", "side": "buy", "qty": 5,
                         "status": "accepted", "id": "b1", "client_order_id": "c1"}], {"NVDA": 100.0},
                         "2026-09-25", asset_class=_classes, cost_bps=BPS)
    s.save(tmp_path)
    again = BookState.load("rules", tmp_path)
    assert again.pending_orders == s.pending_orders
    assert _lot(again, "B", "SPY").events == _lot(s, "B", "SPY").events
    assert again.sleeve_pnl == s.sleeve_pnl


# --- costs (EX-5) -------------------------------------------------------------------------------------


def test_cost_for_uses_policy_and_only_raising_overrides(cfg):
    s = _state()
    assert ledger.cost_for(cfg, s, "etf", 10_000) == pytest.approx(5.0)
    assert ledger.cost_for(cfg.policy, None, "stock", -10_000) == pytest.approx(10.0)
    s.cost_model_bps = {"etf": 12.0}
    assert ledger.cost_for(cfg, s, "etf", 10_000) == pytest.approx(12.0)
    s.cost_model_bps = {"etf": 2.0}  # an override can never lower the policy
    assert ledger.cost_for(cfg, s, "etf", 10_000) == pytest.approx(5.0)
    assert ledger.cost_for(cfg, s, "mystery", 10_000) == pytest.approx(25.0)  # unknown class: most expensive
    assert ledger.cost_model(cfg, s) == {"etf": 5.0, "stock": 10.0, "crypto": 25.0}


def _fill_rows(n, cls, slip, split=False):
    rows = []
    for i in range(n):
        base = {"date": "2026-09-01", "asset_class": cls, "slippage_bps": slip, "fill": 100.0,
                "client_order_id": f"o{i}"}
        rows.append(dict(base, sleeve="A"))
        if split:
            rows.append(dict(base, sleeve="B"))
    return rows


def test_measured_cost_model_raises_only_after_enough_fills(cfg):
    s = _state()
    s.fills = _fill_rows(29, "etf", 12.0)
    assert ledger.measured_cost_model(s, cfg.policy)["etf"] == 5.0 and s.cost_model_bps == {}
    s.fills = _fill_rows(30, "etf", 12.0)
    out = ledger.measured_cost_model(s, cfg)
    assert out["etf"] == 12.0 and out["stock"] == 10.0 and s.cost_model_bps == {"etf": 12.0}
    assert ledger.cost_for(cfg, s, "etf", 10_000) == pytest.approx(12.0)


def test_measured_cost_model_needs_more_than_twice_the_model(cfg):
    s = _state()
    s.cost_model_bps = {"etf": 20.0}
    s.fills = _fill_rows(40, "etf", 9.0) + _fill_rows(40, "stock", -3.0)
    out = ledger.measured_cost_model(s, cfg.policy)
    assert out == {"etf": 5.0, "stock": 10.0, "crypto": 25.0}
    assert s.cost_model_bps == {}  # never below the policy: back to the model


def test_measured_cost_model_counts_split_orders_once_and_skips_missing(cfg):
    s = _state()
    s.fills = _fill_rows(15, "etf", 50.0, split=True) + [{"asset_class": "etf", "slippage_bps": None}] * 20
    assert ledger.measured_cost_model(s, cfg.policy)["etf"] == 5.0
    s.fills = [{"asset_class": "stock", "slippage_bps": v} for v in [25.0] * 20 + [float("nan")] * 5 + [30.0] * 10]
    assert ledger.measured_cost_model(s, cfg.policy)["stock"] == 25.0


# --- record_orders / settle_fills (EX-4, B-6) ---------------------------------------------------------------


def _submit(state, targets, orders, results, prices, date="2026-09-25", log=None, tags=None, **kw):
    return ledger.record_orders(state, targets, orders, results, prices, date, asset_class=_classes, cost_bps=BPS,
                                tags=tags, log=log, **kw)


def _fill(coid, qty, price, final=True, status="filled", filled_at="2026-09-28"):
    return {"client_order_id": coid, "status": status, "final": final, "filled_qty": qty,
            "filled_avg_price": price, "filled_at": filled_at}


def _settle(state, fills, date="2026-09-28", log=None, cost_bps=BPS):
    return ledger.settle_fills(state, fills, date=date, asset_class=_classes, cost_bps=cost_bps,
                               log=log if log is not None else [])


def test_fills_use_fill_prices_not_closes():
    s = _state()
    added = _submit(s, [Target("NVDA", "C", 10, 90.0, "breakout")], [Order("NVDA", "buy", 10, 100.0)],
                    [{"symbol": "NVDA", "side": "buy", "qty": 10, "status": "accepted", "id": "b1",
                      "client_order_id": "c1"}], {"NVDA": 100.0}, tags={"prompt_version": "p1"})
    assert s.lots == {}  # nothing changes until the broker says it filled
    [p] = added
    assert p["client_order_id"] == "c1" and p["broker_order_id"] == "b1" and p["signal_close"] == 100.0
    assert p["symbol"] == "NVDA" and p["side"] == "buy" and p["qty"] == 10 and p["date"] == "2026-09-25"
    assert p["alloc"][0]["sleeve"] == "C" and p["alloc"][0]["reason"] == "breakout"
    assert p["alloc"][0]["tags"] == {"prompt_version": "p1"}
    assert p["asset_class"] == "stock" and p["alloc"][0]["delta_qty"] == 10 and p["alloc"][0]["stop"] == 90.0
    rows = _settle(s, [_fill("c1", 10, 101.0)])
    lot = _lot(s, "C", "NVDA")
    assert lot.entry_price == 101.0 and lot.entry_date == "2026-09-25" and lot.fill_date == "2026-09-28"
    assert lot.initial_risk_dollars == pytest.approx(10 * 11)
    assert lot.costs == pytest.approx(10 * 101 * 10 / 1e4)
    assert lot.tags == {"prompt_version": "p1"} and lot.lot_id == "rules:C:NVDA:2026-09-25"
    [r] = rows
    assert r["slippage_bps"] == pytest.approx(100.0) and r["gap_R"] is None and r["sleeve"] == "C"
    assert s.fills == rows and s.pending_orders == []


def test_slippage_sign_positive_means_worse():
    s = _state()
    ledger.apply_fill(s, "C", "AAPL", 10, 90.0, "2026-09-01", stop=80.0)
    ledger.apply_fill(s, "C", "MSFT", 10, 90.0, "2026-09-01", stop=80.0)
    targets = [Target("AAPL", "C", 0, None, "exit"), Target("MSFT", "C", 0, None, "exit")]
    orders = [Order("AAPL", "sell", 10, 100.0), Order("MSFT", "sell", 10, 100.0)]
    results = [{"symbol": o.symbol, "side": "sell", "qty": 10, "status": "accepted", "client_order_id": o.symbol}
               for o in orders]
    _submit(s, targets, orders, results, {"AAPL": 100.0, "MSFT": 100.0})
    rows = _settle(s, [_fill("AAPL", 10, 99.0), _fill("MSFT", 10, 101.0)])
    slip = {r["symbol"]: r["slippage_bps"] for r in rows}
    assert slip["AAPL"] == pytest.approx(100.0)  # sold below the close: worse
    assert slip["MSFT"] == pytest.approx(-100.0)  # sold above the close: better
    buy = _state()
    _submit(buy, [Target("SPY", "A", 10, None, "trend")], [Order("SPY", "buy", 10, 100.0)],
            [{"symbol": "SPY", "side": "buy", "qty": 10, "status": "accepted", "client_order_id": "x"}],
            {"SPY": 100.0})
    [r] = _settle(buy, [_fill("x", 10, 99.5)])
    assert r["slippage_bps"] == pytest.approx(-50.0)  # bought below the close: better


def test_gap_r_logged_for_sleeve_b_buys_only():
    s = _state()
    targets = [Target("SPY", "B", 6, 95.0, "rsi2 dip"), Target("SPY", "A", 4, None, "trend")]
    _submit(s, targets, [Order("SPY", "buy", 10, 100.0)],
            [{"symbol": "SPY", "side": "buy", "qty": 10, "status": "accepted", "client_order_id": "g"}],
            {"SPY": 100.0})
    rows = _settle(s, [_fill("g", 10, 101.0)])
    by = {r["sleeve"]: r for r in rows}
    assert by["B"]["gap_R"] == pytest.approx(0.2)  # (101 - 100) / (100 - 95)
    assert by["A"]["gap_R"] is None
    assert by["B"]["qty"] == pytest.approx(6) and by["A"]["qty"] == pytest.approx(4)  # pro rata to the deltas
    assert _lot(s, "B", "SPY").qty == pytest.approx(6) and _lot(s, "A", "SPY").qty == pytest.approx(4)


def test_gap_r_none_without_usable_stop():
    s = _state()
    _submit(s, [Target("QQQ", "B", 5, None, "dip")], [Order("QQQ", "buy", 5, 100.0)],
            [{"symbol": "QQQ", "side": "buy", "qty": 5, "status": "accepted", "client_order_id": "q"}],
            {"QQQ": 100.0})
    [r] = _settle(s, [_fill("q", 5, 100.5)])
    assert r["gap_R"] is None


def test_pending_order_survives_non_final_status_and_settles_in_pieces():
    s = _state()
    _submit(s, [Target("DIA", "B", 10, 90.0, "dip")], [Order("DIA", "buy", 10, 100.0)],
            [{"symbol": "DIA", "side": "buy", "qty": 10, "status": "accepted", "client_order_id": "p"}],
            {"DIA": 100.0})
    _settle(s, [], date="2026-09-26", log=[])
    assert len(s.pending_orders) == 1 and s.lots == {}  # no news: still pending
    _settle(s, [_fill("p", 4, 100.0, final=False, status="partially_filled")])
    assert len(s.pending_orders) == 1 and _lot(s, "B", "DIA").qty == pytest.approx(4)
    _settle(s, [_fill("p", 4, 100.0, final=False, status="partially_filled")])
    assert _lot(s, "B", "DIA").qty == pytest.approx(4)  # the same news twice is not applied twice
    rows = _settle(s, [_fill("p", 10, 101.2)], date="2026-09-29", log=[])
    lot = _lot(s, "B", "DIA")
    assert s.pending_orders == [] and lot.qty == pytest.approx(10)
    assert rows[0]["fill"] == pytest.approx(102.0)  # (10 * 101.2 - 4 * 100) / 6
    assert lot.entry_price == pytest.approx(101.2)
    assert [e["kind"] for e in lot.events] == ["open", "add"]


def test_final_status_derived_from_status_when_flag_missing():
    s = _state()
    _submit(s, [Target("IWM", "B", 5, 90.0, "dip")], [Order("IWM", "buy", 5, 100.0)],
            [{"symbol": "IWM", "side": "buy", "qty": 5, "status": "accepted", "client_order_id": "f"}],
            {"IWM": 100.0})
    fill = {"client_order_id": "f", "status": "filled", "filled_qty": "5", "filled_avg_price": "100.1"}
    _settle(s, [fill])
    assert s.pending_orders == [] and _lot(s, "B", "IWM").entry_price == pytest.approx(100.1)


def test_canceled_partial_unknown_and_priceless_fills_are_logged():
    s = _state()
    targets = [Target("IWM", "B", 10, 90.0, "dip"), Target("QQQ", "B", 5, 90.0, "dip"),
               Target("DIA", "B", 5, 90.0, "dip")]
    orders = [Order("IWM", "buy", 10, 100.0), Order("QQQ", "buy", 5, 100.0), Order("DIA", "buy", 5, 100.0)]
    results = [{"symbol": o.symbol, "side": "buy", "qty": o.qty, "status": "accepted", "client_order_id": o.symbol}
               for o in orders]
    _submit(s, targets, orders, results, {"IWM": 100.0, "QQQ": 100.0, "DIA": 100.0})
    log = []
    _settle(s, [_fill("IWM", 4, 100.0, status="canceled"),
                {"client_order_id": "QQQ", "status": "unknown", "final": True, "filled_qty": 0,
                 "filled_avg_price": None, "filled_at": None},
                _fill("DIA", 5, None), _fill("ghost", 1, 1.0)], log=log)
    text = "\n".join(log)
    assert s.pending_orders == []
    assert _lot(s, "B", "IWM").qty == pytest.approx(4) and "filled 4 of 10" in text
    assert _lot(s, "B", "QQQ") is None and "does not know" in text
    assert _lot(s, "B", "DIA") is None and "no fill price" in text
    assert "unknown order ghost" in text


def test_partial_sell_order_realizes_pnl_without_trade():
    s = _state()
    ledger.apply_fill(s, "C", "AMZN", 10, 100.0, "2026-09-01", stop=90.0)
    _submit(s, [Target("AMZN", "C", 6, 95.0, "trim")], [Order("AMZN", "sell", 4, 110.0)],
            [{"symbol": "AMZN", "side": "sell", "qty": 4, "status": "accepted", "client_order_id": "t"}],
            {"AMZN": 110.0})
    assert _lot(s, "C", "AMZN").stop == 95.0  # ratchet persisted while the sell is pending
    _settle(s, [_fill("t", 4, 109.0)])
    lot = _lot(s, "C", "AMZN")
    assert lot.qty == pytest.approx(6) and lot.realized_pnl == pytest.approx(36.0)
    assert s.closed_trades == []


def test_full_exit_leaves_no_rounding_dust():
    s = _state()
    ledger.apply_fill(s, "C", "TSLA", 10 / 3, 90.0, "2026-09-01", stop=80.0)
    q = round(10 / 3, 6)  # the broker order is rounded to 6 decimals
    _submit(s, [Target("TSLA", "C", 0, None, "stop hit")], [Order("TSLA", "sell", q, 100.0)],
            [{"symbol": "TSLA", "side": "sell", "qty": q, "status": "accepted", "client_order_id": "d"}],
            {"TSLA": 100.0})
    _settle(s, [_fill("d", q, 99.0)])
    assert _lot(s, "C", "TSLA") is None and len(s.closed_trades) == 1


def test_internal_cross_without_order():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 90.0, "2026-09-01", stop=85.0)
    log = []
    targets = [Target("SPY", "B", 0, None, "exit: close > SMA5"), Target("SPY", "A", 10, None, "trend")]
    added = _submit(s, targets, [], [], {"SPY": 100.0}, log=log)
    assert added == [] and s.pending_orders == []
    [t] = s.closed_trades
    assert t["sleeve"] == "B" and t["pnl"] == pytest.approx(100.0) and t["costs"] == 0.0
    assert t["R"] == pytest.approx(2.0) and t["reason"].startswith("internal cross")
    a = _lot(s, "A", "SPY")
    assert a.qty == pytest.approx(10) and a.entry_price == 100.0 and a.costs == 0.0
    assert "crossed" in "\n".join(log)
    assert s.fills == []  # crosses are not broker fills, so they never enter the slippage stats


def test_internal_cross_partial_and_one_sided_no_order():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 90.0, "2026-09-01", stop=85.0)
    log = []
    # the 6 shares A does not take are worth $600, far above the order minimum: plain pro rata, and said so
    _submit(s, [Target("SPY", "B", 0, None, "exit"), Target("SPY", "A", 4, None, "trend")], [], [],
            {"SPY": 100.0}, log=log)
    assert _lot(s, "B", "SPY").qty == pytest.approx(6) and _lot(s, "A", "SPY").qty == pytest.approx(4)
    assert any("B/SPY: exit not finished, 6 shares" in line for line in log)
    before = _lot(s, "B", "SPY").qty
    log.clear()
    _submit(s, [Target("SPY", "B", 2, None, "trim")], [], [], {"SPY": 100.0}, log=log)  # no order: nothing moves
    assert _lot(s, "B", "SPY").qty == before and log == []  # one-sided trim and no order: quantities stay
    _submit(s, [Target("SPY", "B", 0, None, "exit")], [], [], {"SPY": 100.0}, log=log)
    assert _lot(s, "B", "SPY").qty == before and "exit not finished" in log[-1]  # one-sided exit: logged


def test_cross_inside_an_order_happens_first_at_settle():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 90.0, "2026-09-01", stop=85.0)
    targets = [Target("SPY", "B", 0, None, "exit"), Target("SPY", "A", 4, None, "trend")]
    _submit(s, targets, [Order("SPY", "sell", 6, 100.0)],
            [{"symbol": "SPY", "side": "sell", "qty": 6, "status": "accepted", "client_order_id": "n"}],
            {"SPY": 100.0})
    assert _lot(s, "B", "SPY").qty == 10 and _lot(s, "A", "SPY") is None  # nothing moves before settlement
    log = []
    rows = _settle(s, [_fill("n", 6, 99.0)], log=log)
    text = "\n".join(log)
    assert "crossed between sleeves" in text and "inside order n" in text and "no order" not in text
    [t] = s.closed_trades
    assert t["realized_pnl"] == pytest.approx(4 * 10 + 6 * 9)
    assert t["costs"] == pytest.approx(6 * 99 * 5 / 1e4, abs=0.005)  # rounded to cents
    a = _lot(s, "A", "SPY")
    assert a.qty == pytest.approx(4) and a.entry_price == 100.0 and a.entry_date == "2026-09-25"
    [r] = rows
    assert r["sleeve"] == "B" and r["qty"] == pytest.approx(6) and r["slippage_bps"] == pytest.approx(100.0)


def test_error_results_are_not_pending_and_change_nothing():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 90.0, "2026-09-01", stop=85.0)
    log = []
    targets = [Target("SPY", "B", 0, None, "exit"), Target("SPY", "A", 4, None, "trend"),
               Target("QQQ", "B", 5, 90.0, "dip")]
    orders = [Order("SPY", "sell", 6, 100.0), Order("QQQ", "buy", 5, 100.0)]
    results = [{"symbol": "SPY", "side": "sell", "qty": 6, "status": "error", "error": "market closed"}]
    _submit(s, targets, orders, results, {"SPY": 100.0, "QQQ": 100.0}, log=log)
    assert s.pending_orders == [] and _lot(s, "B", "SPY").qty == 10 and _lot(s, "A", "SPY") is None
    text = "\n".join(log)
    assert "market closed" in text and "no submit result" in text


def test_stops_persist_for_all_targets_and_never_lower():
    s = _state()
    ledger.apply_fill(s, "C", "NVDA", 10, 100.0, "2026-09-01", stop=90.0)
    _submit(s, [Target("NVDA", "C", 10, 95.0, "hold (C-7 ratchet)")], [], [], {"NVDA": 110.0})
    assert _lot(s, "C", "NVDA").stop == 95.0
    _submit(s, [Target("NVDA", "C", 10, 80.0, "hold")], [], [], {"NVDA": 110.0})
    _submit(s, [Target("NVDA", "C", 10, None, "hold")], [], [], {"NVDA": 110.0})
    assert _lot(s, "C", "NVDA").stop == 95.0


def test_results_paired_by_client_id_then_position():
    s = _state()
    orders = [Order("QQQ", "buy", 5, 100.0, client_order_id="id-q"), Order("IWM", "buy", 5, 100.0)]
    results = [{"symbol": "IWM", "side": "buy", "qty": 5, "status": "accepted", "id": "b-i"},
               {"symbol": "QQQ", "side": "buy", "qty": 5, "status": "accepted", "id": "b-q",
                "client_order_id": "id-q"}]
    added = _submit(s, [Target("QQQ", "B", 5, 90.0, "dip"), Target("IWM", "B", 5, 90.0, "dip")], orders, results,
                    {"QQQ": 100.0, "IWM": 100.0})
    by = {p["symbol"]: p for p in added}
    assert by["QQQ"]["broker_order_id"] == "b-q" and by["IWM"]["broker_order_id"] == "b-i"
    assert by["IWM"]["client_order_id"] == "rules-2026-09-25-IWM-buy-1"


def test_immediate_fills_round_trip_for_simulator_close_mode():
    s = _state()
    results = [{"symbol": "SPY", "side": "buy", "qty": 10, "status": "filled", "fill_price": 100.05}]
    _submit(s, [Target("SPY", "A", 10, None, "trend")], [Order("SPY", "buy", 10, 100.0)], results,
            {"SPY": 100.0})
    assert results[0]["client_order_id"]
    fills = ledger.immediate_fills(results, "2026-09-25")
    assert fills[0]["final"] and fills[0]["filled_at"] == "2026-09-25"
    _settle(s, fills, date="2026-09-25", log=[])
    lot = _lot(s, "A", "SPY")
    assert lot.entry_price == pytest.approx(100.05) and s.pending_orders == []
    assert ledger.immediate_fills([{"status": "accepted", "client_order_id": "z"}], "2026-09-25") == []


def test_settle_with_no_pending_or_no_fills_is_harmless():
    s = _state()
    assert _settle(s, []) == []
    assert _settle(s, None) == []
    assert s.fills == [] and s.lots == {}


def test_measured_costs_apply_to_settled_fills():
    s = _state()
    s.cost_model_bps = {"etf": 20.0}
    _submit(s, [Target("SPY", "A", 10, None, "trend")], [Order("SPY", "buy", 10, 100.0)],
            [{"symbol": "SPY", "side": "buy", "qty": 10, "status": "accepted", "client_order_id": "m"}],
            {"SPY": 100.0})
    _settle(s, [_fill("m", 10, 100.0)])
    assert _lot(s, "A", "SPY").costs == pytest.approx(10 * 100 * 20 / 1e4)


# --- reconcile: no silent rescale --------------------------------------------------------------------------


def _two_sleeves():
    s = _state()
    ledger.apply_fill(s, "A", "SPY", 10, 95.0, "2026-09-01")
    ledger.apply_fill(s, "B", "SPY", 10, 90.0, "2026-09-01", stop=85.0)
    return s


def test_reconcile_reduction_realizes_pnl_and_writes_events():
    s = _two_sleeves()
    log = []
    ledger.reconcile(s.lots, {"SPY": 15.0}, log, state=s, prices={"SPY": 100.0}, date="2026-09-28")
    a, b = _lot(s, "A", "SPY"), _lot(s, "B", "SPY")
    assert a.qty == pytest.approx(7.5) and b.qty == pytest.approx(7.5)
    assert a.realized_pnl == pytest.approx(12.5) and b.realized_pnl == pytest.approx(25.0)
    ev = b.events[-1]
    assert ev["reason"] == "reconcile" and ev["kind"] == "reduce" and ev["date"] == "2026-09-28"
    assert ev["note"] == "broker holds 15, book expected 20"
    assert "SPY" in log[0] and "reconcile" in log[0] and "broker holds 15" in log[0]
    assert s.sleeve_pnl["B"]["realized"] == pytest.approx(25.0)


def test_reconcile_to_zero_writes_closed_trades():
    s = _two_sleeves()
    ledger.apply_fill(s, "C", "NVDA", 5, 100.0, "2026-09-01", stop=90.0)
    log = []
    ledger.reconcile(s.lots, {"NVDA": 5.0}, log, state=s, prices={"SPY": 100.0}, date="2026-09-28")
    assert "C" in s.lots and "A" not in s.lots and "B" not in s.lots
    assert len(s.closed_trades) == 2 and all(t["reason"] == "reconcile" for t in s.closed_trades)
    b = [t for t in s.closed_trades if t["sleeve"] == "B"][0]
    assert b["R"] == pytest.approx(2.0)


def test_reconcile_all_zero_changes_nothing_unless_allowed():
    # an empty or failed positions call must not close every lot and leave the real shares untracked
    for positions in ({}, None, {"SPY": 0.0}, {"XYZ": 4.0}):
        s = _two_sleeves()
        log = []
        bad = ledger.reconcile(s.lots, positions, log, state=s, prices={"SPY": 100.0}, date="2026-09-28")
        assert bad == {"SPY"} and _lot(s, "A", "SPY").qty == 10 and s.closed_trades == []
        assert any(line.startswith("WARNING") and "allow_all_zero" in line for line in log)
    s = _two_sleeves()
    ledger.reconcile(s.lots, {}, [], state=s, prices={"SPY": 100.0}, date="2026-09-28", allow_all_zero=True)
    assert s.lots == {} and len(s.closed_trades) == 2
    log = []
    ledger.reconcile({"A": {"SPY": Lot(10, 95.0, "2026-09-01")}}, {}, log)  # the old call is guarded too
    assert "WARNING" in log[0]


def test_reconcile_skips_a_symbol_the_broker_spells_differently():
    s = _state()
    ledger.apply_fill(s, "D", "BTC/USD", 0.5, 60000.0, "2026-09-01", stop=50000.0)
    ledger.apply_fill(s, "C", "NVDA", 10, 100.0, "2026-09-01", stop=90.0)
    log = []
    bad = ledger.reconcile(s.lots, {"BTCUSD": 0.5, "NVDA": 10.0}, log, state=s, prices={"BTC/USD": 61000.0},
                           date="2026-09-28")
    assert bad == {"BTC/USD"} and _lot(s, "D", "BTC/USD").qty == 0.5 and s.closed_trades == []
    assert any("BTCUSD" in line and "do not match" in line for line in log)


@pytest.mark.parametrize("have,changed", [(19.8, False), (19.79, True), (20.2, False), (20.21, True)])
def test_reconcile_threshold_is_one_percent(have, changed):
    s = _two_sleeves()
    log = []
    ledger.reconcile(s.lots, {"SPY": have}, log, state=s, prices={"SPY": 100.0}, date="2026-09-28")
    total = _lot(s, "A", "SPY").qty + _lot(s, "B", "SPY").qty
    assert (total == pytest.approx(have)) is changed and (total == 20) is not changed and bool(log) is changed


def test_reconcile_increase_is_an_add_with_the_lot_stop():
    s = _two_sleeves()
    ledger.reconcile(s.lots, {"SPY": 22.0}, [], state=s, prices={"SPY": 100.0}, date="2026-09-28")
    b = _lot(s, "B", "SPY")
    assert b.qty == pytest.approx(11) and b.initial_risk_dollars == pytest.approx(50 + 15)
    assert b.events[-1]["kind"] == "add" and b.events[-1]["reason"] == "reconcile"
    assert _lot(s, "A", "SPY").initial_risk_dollars == 0.0


def test_reconcile_small_differences_and_pending_symbols_are_left_alone():
    s = _two_sleeves()
    log = []
    ledger.reconcile(s.lots, {"SPY": 20.1}, log, state=s, prices={"SPY": 100.0}, date="2026-09-28")
    assert log == [] and _lot(s, "A", "SPY").qty == 10
    s.pending_orders = [{"client_order_id": "x", "symbol": "SPY", "side": "sell", "qty": 5, "alloc": []}]
    ledger.reconcile(s.lots, {"SPY": 15.0}, log, state=s, prices={"SPY": 100.0}, date="2026-09-28")
    assert _lot(s, "A", "SPY").qty == 10 and "pending" in log[0]
    s.pending_orders = []
    log.clear()
    ledger.reconcile(s.lots, {"SPY": 15.0}, log, state=s, prices={"SPY": 100.0}, date="2026-09-28",
                     skip_symbols={"SPY"})
    assert _lot(s, "A", "SPY").qty == 10 and log


def test_reconcile_without_price_uses_entry_price_and_says_so():
    s = _two_sleeves()
    log = []
    ledger.reconcile(s.lots, {"SPY": 10.0}, log, state=s, prices={}, date="2026-09-28")
    assert _lot(s, "A", "SPY").realized_pnl == pytest.approx(0.0)
    assert any("no close today" in line for line in log)


def test_reconcile_nan_position_is_skipped_not_zeroed():
    s = _two_sleeves()
    log = []
    ledger.reconcile(s.lots, {"SPY": float("nan")}, log, state=s, prices={"SPY": 100.0}, date="2026-09-28")
    assert _lot(s, "A", "SPY").qty == 10 and "not a number" in log[0]


def test_reconcile_old_call_still_works_but_is_not_silent():
    lots = {"A": {"SPY": Lot(10, 95.0, "2026-09-01")}, "B": {"SPY": Lot(10, 90.0, "2026-09-01", 85.0, 85.0),
                                                               "QQQ": Lot(5, 100.0, "2026-09-01", 95.0, 95.0)}}
    log = []
    ledger.reconcile(lots, {"SPY": 10.0, "QQQ": 0.0, "IWM": 3.0}, log)
    assert lots["A"]["SPY"].qty == pytest.approx(5) and lots["B"]["SPY"].qty == pytest.approx(5)
    ev = lots["A"]["SPY"].events[-1]
    assert ev["reason"] == "reconcile" and ev["note"] == "broker holds 10, book expected 20"
    assert ev["kind"] == "rescale" and ev["qty"] == pytest.approx(5)
    assert "QQQ" not in lots["B"]
    text = "\n".join(log)
    assert "without a trade record" in text and "IWM" in text and "no sleeve tracks" in text
    assert "called without state" in text and "pass state=" in text  # the lossy old call is flagged


# --- old immediate-fill wrapper ---------------------------------------------------------------------------


def test_update_lots_wrapper_keeps_old_behaviour_with_new_bookkeeping():
    s = _state()
    ledger.update_lots(s, [Target("SPY", "A", 10, None, "trend")], {"SPY": 100.0}, "2026-09-01")
    ledger.update_lots(s, [Target("SPY", "A", 15, None, "trend")], {"SPY": 110.0}, "2026-09-02")
    lot = _lot(s, "A", "SPY")
    assert lot.qty == 15 and lot.entry_price == pytest.approx(1550 / 15)
    ledger.update_lots(s, [Target("SPY", "A", 0, None, "exit")], {"SPY": 120.0}, "2026-09-03")
    [t] = s.closed_trades
    assert t["pnl"] == pytest.approx(15 * 120 - 1550) and s.lots == {}


def test_update_lots_never_lowers_stop_and_charges_costs_when_asked():
    s = _state()
    ledger.update_lots(s, [Target("NVDA", "C", 10, 90.0, "breakout")], {"NVDA": 100.0}, "2026-09-01",
                       asset_class=_classes, cost_bps=BPS)
    ledger.update_lots(s, [Target("NVDA", "C", 10, 80.0, "hold")], {"NVDA": 100.0}, "2026-09-02")
    lot = _lot(s, "C", "NVDA")
    assert lot.stop == 90.0 and lot.costs == pytest.approx(1.0)
    log = []
    ledger.update_lots(s, [Target("NVDA", "C", 0, None, "exit")], {"NVDA": float("nan")}, "2026-09-03", log=log)
    assert _lot(s, "C", "NVDA").qty == 10 and "no valid quantity or price" in log[0]


# --- marks: MAE / MFE inputs and sleeve P&L (RISK-13) ----------------------------------------------------------


def test_update_marks_tracks_high_low_since_entry_and_sleeve_pnl():
    df = make_bars(n=60, seed=3)
    entry = df.index[40].date().isoformat()
    today = df.index[-1].date().isoformat()
    s = _state()
    ledger.apply_fill(s, "C", "AAPL", 10, float(df["close"].iloc[40]), entry, stop=float(df["close"].iloc[40]) * 0.9)
    ledger.update_marks(s, {"AAPL": df}, today)
    lot = _lot(s, "C", "AAPL")
    after = df[df.index > df.index[40]]
    assert lot.max_high == pytest.approx(max(after["high"].max(), lot.entry_price))
    assert lot.min_low == pytest.approx(min(after["low"].min(), lot.entry_price))
    rec = s.sleeve_pnl["C"]
    expected = 10 * (df["close"].iloc[-1] - lot.entry_price)
    assert rec["cum"] == pytest.approx(expected, abs=1e-5) and rec["date"] == today
    assert rec["peak"] == pytest.approx(max(0.0, expected), abs=1e-5)


def test_sleeve_peak_holds_after_a_drop_and_counts_realized():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 100.0, "2026-09-01", stop=95.0, cost=1.0)
    idx = pd.to_datetime(["2026-09-01", "2026-09-02", "2026-09-03"])
    up = pd.DataFrame({"open": [100, 105, 110], "high": [101, 106, 111], "low": [99, 104, 109],
                       "close": [100, 105, 110], "volume": [1, 1, 1]}, index=idx, dtype=float)
    ledger.update_marks(s, {"SPY": up}, "2026-09-03")
    assert s.sleeve_pnl["B"]["cum"] == pytest.approx(99.0) and s.sleeve_pnl["B"]["peak"] == pytest.approx(99.0)
    down = up.copy()
    down.loc[idx[-1], ["close", "low"]] = [96.0, 95.5]
    ledger.update_marks(s, {"SPY": down}, "2026-09-03")
    assert s.sleeve_pnl["B"]["cum"] == pytest.approx(-41.0) and s.sleeve_pnl["B"]["peak"] == pytest.approx(99.0)
    assert _lot(s, "B", "SPY").min_low == pytest.approx(95.5)
    ledger.apply_fill(s, "B", "SPY", -10, 96.0, "2026-09-04")
    ledger.update_marks(s, {}, "2026-09-04")  # no lots left: cum is the realized P&L
    assert s.sleeve_pnl["B"]["cum"] == pytest.approx(-41.0) and s.sleeve_pnl["B"]["peak"] == pytest.approx(99.0)


def test_update_marks_uses_bars_up_to_date_and_survives_bad_data():
    s = _state()
    ledger.apply_fill(s, "C", "AMD", 10, 100.0, "2026-09-01", stop=90.0)
    ledger.apply_fill(s, "C", "ORCL", 10, 100.0, "2026-09-01", stop=90.0)
    idx = pd.to_datetime(["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"])
    df = pd.DataFrame({"open": 100.0, "high": [101, 103, np.nan, 150], "low": [99, 97, np.nan, 50],
                       "close": [100, 102, np.nan, 140], "volume": 1.0}, index=idx)
    log = []
    ledger.update_marks(s, {"AMD": df, "ORCL": pd.DataFrame()}, "2026-09-03", log=log)
    lot = _lot(s, "C", "AMD")
    assert lot.max_high == pytest.approx(103) and lot.min_low == pytest.approx(97)  # the 09-04 bar is later
    # AMD: last good close 102. ORCL has never had a price: valued at its entry price, and the log says so
    assert s.sleeve_pnl["C"]["cum"] == pytest.approx(10 * 2)
    assert s.sleeve_pnl["C"]["marks"]["AMD"] == {"close": 102.0, "date": "2026-09-02"}
    assert log == ["C/ORCL: no close yet; sleeve P&L values it at its entry price"]
    assert _lot(s, "C", "ORCL").max_high == 100.0  # only its fill price so far


def test_update_marks_with_tz_aware_index():
    s = _state()
    ledger.apply_fill(s, "C", "GE", 1, 100.0, "2026-09-01", stop=90.0)
    df = make_bars(n=10, end="2026-09-10")
    df.index = df.index.tz_localize("America/New_York")
    ledger.update_marks(s, {"GE": df}, "2026-09-10")
    assert _lot(s, "C", "GE").max_high >= 100.0 and not math.isnan(s.sleeve_pnl["C"]["cum"])


def test_closed_trade_mae_mfe_use_marks():
    s = _state()
    ledger.apply_fill(s, "C", "LLY", 10, 100.0, "2026-09-01", stop=90.0)
    idx = pd.to_datetime(["2026-09-02", "2026-09-03"])
    df = pd.DataFrame({"open": 100.0, "high": [120.0, 110.0], "low": [95.0, 100.0], "close": [110.0, 105.0],
                       "volume": 1.0}, index=idx)
    ledger.update_marks(s, {"LLY": df}, "2026-09-03")
    ledger.apply_fill(s, "C", "LLY", -10, 105.0, "2026-09-04")
    t = s.closed_trades[0]
    assert t["mae_R"] == pytest.approx(-0.5) and t["mfe_R"] == pytest.approx(2.0) and t["R"] == pytest.approx(0.5)


# --- sessions held ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("start,end,crypto,expected", [
    ("2026-08-31", "2026-09-04", False, 4),
    ("2026-07-02", "2026-07-07", False, 2),   # July 3 is the observed Independence Day
    ("2026-04-02", "2026-04-06", False, 1),   # Good Friday
    ("2026-07-02", "2026-07-07", True, 5),    # crypto counts calendar days
    ("2026-09-01", "2026-09-01", False, 0),
    ("2026-09-05", "2026-09-01", False, 0),
    (None, "2026-09-01", False, 0),
])
def test_sessions_between(start, end, crypto, expected):
    assert ledger.sessions_between(start, end, crypto) == expected


def test_nan_target_quantity_never_means_exit():
    s = _state()
    ledger.apply_fill(s, "C", "NVDA", 10, 100.0, "2026-09-01", stop=90.0)
    log = []
    _submit(s, [Target("NVDA", "C", float("nan"), 95.0, "broken")], [], [], {"NVDA": 110.0}, log=log)
    assert _lot(s, "C", "NVDA").qty == 10 and s.closed_trades == []
    ledger.update_lots(s, [Target("NVDA", "C", float("nan"), None, "broken")], {"NVDA": 110.0}, "2026-09-02",
                       log=log)
    assert _lot(s, "C", "NVDA").qty == 10 and "no valid quantity" in log[-1]


def test_update_lots_raises_stop_even_without_a_price():
    s = _state()
    ledger.apply_fill(s, "C", "NVDA", 10, 100.0, "2026-09-01", stop=90.0)
    ledger.update_lots(s, [Target("NVDA", "C", 10, 96.0, "hold")], {}, "2026-09-02")
    assert _lot(s, "C", "NVDA").stop == 96.0


# --- review fixes: RISK-13 marks when a price is missing -------------------------------------------------------


def _bar(close, day):
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": 1.0},
                        index=pd.to_datetime([day]))


def _drawdown(s, sleeve):
    rec = s.sleeve_pnl[sleeve]
    return max(0.0, rec["peak"], rec["cum"]) - rec["cum"]


def test_missing_price_keeps_the_last_mark_so_a_loss_stays_visible():
    s = _state()
    ledger.apply_fill(s, "C", "NVDA", 100, 100.0, "2026-09-01", stop=90.0)
    ledger.update_marks(s, {"NVDA": _bar(40.0, "2026-09-02")}, "2026-09-02")
    assert s.sleeve_pnl["C"]["cum"] == pytest.approx(-6000) and _drawdown(s, "C") == pytest.approx(6000)
    log = []
    ledger.update_marks(s, {}, "2026-09-03", log=log)  # NVDA's data fetch failed today
    assert s.sleeve_pnl["C"]["cum"] == pytest.approx(-6000) and _drawdown(s, "C") == pytest.approx(6000)
    assert s.sleeve_pnl["C"]["date"] == "2026-09-03"
    assert log == ["C/NVDA: no close today; sleeve P&L uses the last close 40.00 from 2026-09-02"]


def test_missing_price_never_fakes_a_drawdown_or_lifts_the_peak():
    s = _state()
    ledger.apply_fill(s, "C", "NVDA", 100, 100.0, "2026-09-01", stop=90.0)
    ledger.update_marks(s, {"NVDA": _bar(160.0, "2026-09-02")}, "2026-09-02")
    assert s.sleeve_pnl["C"]["peak"] == pytest.approx(6000)
    ledger.update_marks(s, {"NVDA": pd.DataFrame()}, "2026-09-03")  # a winner with no price is still a winner
    assert s.sleeve_pnl["C"]["cum"] == pytest.approx(6000) and _drawdown(s, "C") == 0.0
    # realized +2000, and a loser marked at 75: missing it for a day must not raise the peak to +2000,
    # which would show up as a false $2,500 drawdown once its price is back
    s = _state()
    ledger.apply_fill(s, "C", "NVDA", 100, 100.0, "2026-09-01", stop=90.0)
    ledger.apply_fill(s, "C", "NVDA", -100, 120.0, "2026-09-04")
    ledger.apply_fill(s, "C", "BBB", 100, 100.0, "2026-09-04", stop=90.0)
    ledger.update_marks(s, {"BBB": _bar(75.0, "2026-09-05")}, "2026-09-05")
    assert s.sleeve_pnl["C"]["cum"] == pytest.approx(-500) and s.sleeve_pnl["C"]["peak"] == 0.0
    ledger.update_marks(s, {}, "2026-09-06")
    assert s.sleeve_pnl["C"]["peak"] == 0.0 and s.sleeve_pnl["C"]["cum"] == pytest.approx(-500)
    ledger.update_marks(s, {"BBB": _bar(75.0, "2026-09-07")}, "2026-09-07")
    assert s.sleeve_pnl["C"]["peak"] == 0.0 and _drawdown(s, "C") == pytest.approx(500)


def test_marks_are_dropped_with_the_lot_and_never_reused_by_a_new_lot(tmp_path):
    s = _state()
    ledger.apply_fill(s, "C", "AMD", 10, 100.0, "2026-09-01", stop=90.0)
    ledger.update_marks(s, {"AMD": _bar(50.0, "2026-09-02")}, "2026-09-02")
    s.save(tmp_path)
    s = BookState.load("rules", tmp_path)  # marks survive a save
    assert s.sleeve_pnl["C"]["marks"]["AMD"]["close"] == 50.0
    ledger.apply_fill(s, "C", "AMD", -10, 50.0, "2026-09-03")
    assert "AMD" not in s.sleeve_pnl["C"]["marks"]
    ledger.apply_fill(s, "C", "AMD", 10, 120.0, "2026-09-04", stop=110.0)
    log = []
    ledger.update_marks(s, {}, "2026-09-04", log=log)
    assert s.sleeve_pnl["C"]["cum"] == pytest.approx(-500)  # the new lot is at its entry price, not at 50
    assert "entry price" in log[0]
    ledger.apply_fill(s, "C", "AMD", -10, 120.0, "2026-09-05")
    ledger.update_marks(s, {}, "2026-09-05")
    assert "marks" not in s.sleeve_pnl["C"]  # no lots left in the sleeve: no marks kept


# --- review fixes: costs must be given (EX-5) ---------------------------------------------------------------


def test_cost_model_and_asset_class_are_required():
    s = _state()
    with pytest.raises(TypeError):
        ledger.settle_fills(s, [], date="2026-09-28")
    with pytest.raises(TypeError):
        ledger.record_orders(s, [], [], [], {}, "2026-09-25")


def test_unknown_class_pays_the_most_expensive_rate_and_pairs_are_crypto():
    assert ledger._class_of(lambda sym: "stock", "BTC/USD") == "crypto"
    assert ledger._class_of(None, "ETH/USD") == "crypto"
    assert ledger._class_of(None, "NVDA") == "unknown" and ledger._class_of({"SPY": "etf"}, "SPY") == "etf"
    assert ledger._class_of("etf", "SPY") == "etf"
    s = _state()
    ledger.record_orders(s, [Target("NVDA", "C", 10, 90.0, "breakout")], [Order("NVDA", "buy", 10, 100.0)],
                         [{"symbol": "NVDA", "side": "buy", "qty": 10, "status": "accepted", "client_order_id": "u"}],
                         {"NVDA": 100.0}, "2026-09-25", asset_class=None, cost_bps=BPS)
    assert s.pending_orders[0]["asset_class"] == "unknown"
    ledger.settle_fills(s, [_fill("u", 10, 100.0)], date="2026-09-28", asset_class=None, cost_bps=BPS, log=[])
    assert _lot(s, "C", "NVDA").costs == pytest.approx(10 * 100 * 25 / 1e4)  # never under-charged


def test_no_cost_model_is_logged():
    s = _state()
    _submit(s, [Target("SPY", "A", 10, None, "trend")], [Order("SPY", "buy", 10, 100.0)],
            [{"symbol": "SPY", "side": "buy", "qty": 10, "status": "accepted", "client_order_id": "z"}],
            {"SPY": 100.0})
    log = []
    _settle(s, [_fill("z", 10, 100.0)], log=log, cost_bps=None)
    assert _lot(s, "A", "SPY").costs == 0.0 and any("no cost model given" in line for line in log)
    s2 = _state()  # the simulator's call: zero bps on purpose, nothing logged
    _submit(s2, [Target("SPY", "A", 10, None, "trend")], [Order("SPY", "buy", 10, 100.0)],
            [{"symbol": "SPY", "side": "buy", "qty": 10, "status": "accepted", "client_order_id": "z"}],
            {"SPY": 100.0})
    log = []
    _settle(s2, [_fill("z", 10, 100.05)], log=log, cost_bps={"etf": 0, "stock": 0, "crypto": 0})
    assert _lot(s2, "A", "SPY").costs == 0.0 and log == []


def test_crypto_fill_rows_costs_and_calendar_sessions():
    s = _state()
    _submit(s, [Target("BTC/USD", "D", 0.1, 50000.0, "trend")], [Order("BTC/USD", "buy", 0.1, 60000.0)],
            [{"symbol": "BTC/USD", "side": "buy", "qty": 0.1, "status": "accepted", "client_order_id": "k"}],
            {"BTC/USD": 60000.0})
    [r] = _settle(s, [_fill("k", 0.1, 60300.0, filled_at="2026-09-26")])
    assert r["asset_class"] == "crypto" and r["cost"] == pytest.approx(0.1 * 60300 * 25 / 1e4)
    assert r["slippage_bps"] == pytest.approx(50.0) and r["gap_R"] is None and r["date"] == "2026-09-26"
    assert _lot(s, "D", "BTC/USD").costs == pytest.approx(15.075)
    _submit(s, [Target("BTC/USD", "D", 0, None, "exit")], [Order("BTC/USD", "sell", 0.1, 61000.0)],
            [{"symbol": "BTC/USD", "side": "sell", "qty": 0.1, "status": "accepted", "client_order_id": "k2"}],
            {"BTC/USD": 61000.0}, date="2026-09-30")
    _settle(s, [_fill("k2", 0.1, 61000.0, filled_at="2026-10-01")], date="2026-10-01")
    [t] = s.closed_trades
    assert t["sessions_held"] == 6  # 2026-09-25 -> 2026-10-01, every calendar day counts for crypto
    assert t["costs"] == pytest.approx(15.075 + 15.25, abs=0.005)


# --- review fixes: fill times, lookups and split orders -------------------------------------------------------


@pytest.mark.parametrize("value", [float("nan"), np.nan, pd.NaT, "NaT", "", "  ", None, "garbage",
                                   np.datetime64("NaT")])
def test_day_of_a_missing_value_is_none(value):
    assert ledger._day(value) is None


def test_nan_fill_time_uses_the_run_date_and_closes_cleanly():
    s = _state()
    ledger.apply_fill(s, "C", "NVDA", 10, 90.0, "2026-09-01", stop=80.0)
    _submit(s, [Target("NVDA", "C", 0, None, "exit")], [Order("NVDA", "sell", 10, 100.0)],
            [{"symbol": "NVDA", "side": "sell", "qty": 10, "status": "accepted", "client_order_id": "t"}],
            {"NVDA": 100.0})
    [r] = _settle(s, [_fill("t", 10, 100.0, filled_at=np.nan)])
    assert r["date"] == "2026-09-28" and s.lots == {} and s.pending_orders == []
    [t] = s.closed_trades
    assert t["date"] == "2026-09-28" and t["sessions_held"] == ledger.sessions_between("2026-09-01", "2026-09-28")


def test_lookup_error_row_keeps_the_order_and_crosses_only_once():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 90.0, "2026-09-01", stop=85.0)
    _submit(s, [Target("SPY", "B", 0, None, "exit"), Target("SPY", "A", 4, None, "trend")],
            [Order("SPY", "sell", 6, 100.0)],
            [{"symbol": "SPY", "side": "sell", "qty": 6, "status": "accepted", "client_order_id": "n"}],
            {"SPY": 100.0})
    err = {"client_order_id": "n", "status": "error", "final": False, "filled_qty": 0.0,
           "filled_avg_price": None, "filled_at": None, "error": "timeout"}
    log = []
    assert _settle(s, [err], log=log) == []
    assert len(s.pending_orders) == 1 and _lot(s, "A", "SPY").qty == pytest.approx(4)
    assert _lot(s, "B", "SPY").qty == pytest.approx(6) and "inside order n" in "\n".join(log)
    _settle(s, [err])
    assert _lot(s, "A", "SPY").qty == pytest.approx(4) and _lot(s, "B", "SPY").qty == pytest.approx(6)
    _settle(s, [_fill("n", 6, 99.0)])
    assert _lot(s, "B", "SPY") is None and s.pending_orders == [] and len(s.closed_trades) == 1


def test_sell_split_over_an_exit_and_a_trim_filled_in_pieces():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 90.0, "2026-09-01", stop=85.0)
    ledger.apply_fill(s, "D", "SPY", 10, 90.0, "2026-09-01", stop=80.0)
    _submit(s, [Target("SPY", "B", 0, None, "exit"), Target("SPY", "D", 7, 85.0, "trim")],
            [Order("SPY", "sell", 13, 100.0)],
            [{"symbol": "SPY", "side": "sell", "qty": 13, "status": "accepted", "client_order_id": "m"}],
            {"SPY": 100.0})
    rows = _settle(s, [_fill("m", 6, 100.0, final=False, status="partially_filled")])
    assert {r["sleeve"]: r["qty"] for r in rows} == {"B": pytest.approx(60 / 13), "D": pytest.approx(18 / 13)}
    assert s.closed_trades == [] and len(s.pending_orders) == 1
    _settle(s, [_fill("m", 13, 100.0)])
    assert _lot(s, "B", "SPY") is None and len(s.closed_trades) == 1  # the exit leaves no fraction behind
    assert _lot(s, "D", "SPY").qty == pytest.approx(7) and s.pending_orders == []


# --- review fixes: exits with no order (M-3) -------------------------------------------------------------------


def test_no_order_exit_finishes_the_lot_when_the_leftover_is_below_the_order_minimum():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 580.0, "2026-09-01", stop=560.0)
    log = []
    targets = [Target("SPY", "B", 0, None, "stop hit"), Target("SPY", "A", 9.97, None, "trend")]
    _submit(s, targets, [], [], {"SPY": 575.0}, log=log)  # net 0.03 x 575 = $17 < $25: no order
    assert _lot(s, "B", "SPY") is None
    [t] = s.closed_trades
    assert t["sleeve"] == "B" and t["realized_pnl"] == pytest.approx(-50.0) and t["R"] == pytest.approx(-0.25)
    assert _lot(s, "A", "SPY").qty == pytest.approx(10)  # the book still holds the broker's 10 shares
    text = "\n".join(log)
    assert "0.03 shares" in text and "move to A" in text and "exit not finished" not in text
    _submit(s, [Target("SPY", "A", 9.97, None, "trend")], [], [], {"SPY": 575.0})  # next run: nothing stuck
    assert len(s.closed_trades) == 1 and _lot(s, "A", "SPY").qty == pytest.approx(10)


def test_no_order_exit_goes_first_and_trims_take_the_rest():
    s = _state()
    ledger.apply_fill(s, "B", "XYZ", 10, 5.0, "2026-09-01", stop=4.5)
    ledger.apply_fill(s, "C", "XYZ", 10, 5.0, "2026-09-01", stop=4.0)
    targets = [Target("XYZ", "B", 0, None, "exit"), Target("XYZ", "C", 6, 4.0, "trim"),
               Target("XYZ", "A", 12, None, "trend")]
    _submit(s, targets, [], [], {"XYZ": 5.0})  # net -2 x $5 = $10 < $25: no order
    assert _lot(s, "B", "XYZ") is None and len(s.closed_trades) == 1
    assert _lot(s, "C", "XYZ").qty == pytest.approx(8) and _lot(s, "A", "XYZ").qty == pytest.approx(12)


def test_no_order_exit_leftover_uses_the_given_order_minimum():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 90.0, "2026-09-01", stop=85.0)
    targets = [Target("SPY", "B", 0, None, "exit"), Target("SPY", "A", 4, None, "trend")]
    _submit(s, targets, [], [], {"SPY": 100.0}, min_notional=1000.0)  # $600 leftover is below $1000
    assert _lot(s, "B", "SPY") is None and _lot(s, "A", "SPY").qty == pytest.approx(10)


# --- review fixes: B-6 for every B fill, EX-5 boundary ----------------------------------------------------------


def test_gap_r_for_sleeve_b_sells_uses_the_lot_risk_and_positive_is_worse():
    s = _state()
    ledger.apply_fill(s, "B", "SPY", 10, 100.0, "2026-09-01", stop=95.0)  # 1R = 5 per share
    ledger.apply_fill(s, "C", "SPY", 10, 100.0, "2026-09-01", stop=90.0)
    targets = [Target("SPY", "B", 0, None, "exit: close > SMA5"), Target("SPY", "C", 0, None, "exit")]
    _submit(s, targets, [Order("SPY", "sell", 20, 104.0)],
            [{"symbol": "SPY", "side": "sell", "qty": 20, "status": "accepted", "client_order_id": "e"}],
            {"SPY": 104.0})
    by = {r["sleeve"]: r for r in _settle(s, [_fill("e", 20, 103.0)])}
    assert by["B"]["gap_R"] == pytest.approx(0.2)  # (104 - 103) / 5: sold below the signal close
    assert by["C"]["gap_R"] is None  # B-6 is for sleeve B only
    s2 = _state()
    ledger.apply_fill(s2, "B", "QQQ", 10, 100.0, "2026-09-01")  # no stop: no 1R, so no gap_R
    _submit(s2, [Target("QQQ", "B", 0, None, "exit")], [Order("QQQ", "sell", 10, 104.0)],
            [{"symbol": "QQQ", "side": "sell", "qty": 10, "status": "accepted", "client_order_id": "f"}],
            {"QQQ": 104.0})
    [r] = _settle(s2, [_fill("f", 10, 105.0)])
    assert r["gap_R"] is None and r["slippage_bps"] == pytest.approx(-96.15, abs=0.01)


def test_measured_cost_model_exactly_twice_the_model_is_not_raised(cfg):
    s = _state()
    s.fills = _fill_rows(30, "etf", 10.0)
    assert ledger.measured_cost_model(s, cfg.policy)["etf"] == 5.0 and s.cost_model_bps == {}
    s.fills = _fill_rows(30, "etf", 10.01)
    assert ledger.measured_cost_model(s, cfg.policy)["etf"] == 10.01
