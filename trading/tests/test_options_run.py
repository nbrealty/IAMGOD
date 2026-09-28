"""Book O daily run, shadow book, skip menu, gates and the broker's options additions (W2-A).

Synthetic chains and fake brokers only: no network, no orders (owner decision 10). Rule IDs refer to
reports/Options rulebook.md.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from trader.broker import AlpacaPaperBroker, SimBroker, clean_prefixes, mleg_problems, single_problems
from trader.models import Lot
from trader.options import book as ob
from trader.options import chain, pricing
from trader.options import run
from trader.options import shadow as osh
from trader.options.ledger import OptionsBook
from trader.options.models import OptionQuote, SpreadLot, OptionLeg, occ_symbol
from trader.state import BookState

DAY = "2026-10-16"  # Friday; the Nov 20 monthly expiry is 35 days away (OPT-18 window)
EXPS = ["2026-10-23", "2026-11-20", "2026-12-18"]
SPOTS = {"SPY": 660.0, "QQQ": 580.0, "IWM": 240.0}


# --- synthetic chains -----------------------------------------------------------------------------------


def close_utc(day: str) -> datetime:
    """20:30 UTC = 16:30 New York (EDT): the after-close run."""
    return datetime.fromisoformat(day + "T20:30:00+00:00")


def run_1545_utc(day: str) -> datetime:
    return datetime.fromisoformat(day + "T19:46:00+00:00")


def make_chain(und, spot, day, expiries=EXPS, leg_spread=0.01, vol=0.18, oi=1000, volume=100, qtime=None,
               drop_greeks=False):
    qt = qtime or (day + "T19:59:00+00:00")
    out = []
    for exp in expiries:
        dte = (pd.Timestamp(exp) - pd.Timestamp(day)).days
        k = int(spot * 0.80)
        while k <= spot * 1.05:
            m = pricing.model_quote(spot, k, max(dte, 0), vol, "put")
            mid = max(0.02, m["price"])
            out.append(OptionQuote(occ_symbol(und, exp, "put", k), und, exp, "put", float(k),
                                   round(mid - leg_spread / 2, 3), round(mid + leg_spread / 2, 3), qt,
                                   iv=None if drop_greeks else m["iv"], delta=None if drop_greeks else m["delta"],
                                   gamma=0.01, theta=-0.05, vega=None if drop_greeks else m["vega"] / 100,
                                   open_interest=oi, open_interest_date=day, volume=volume))
            k += 1
    return out


def fake_fetch(chains, seen=None):
    def fetch(underlying, *, extra_symbols=(), spot=None, now=None):
        if seen is not None:
            seen[underlying] = tuple(extra_symbols)
        q, s = chains.get(underlying, (None, None))
        if q is None:
            raise RuntimeError("no data")
        return chain.ChainQuotes(q, [], {"spot": s, "fatal": []})
    return fetch


def cboe(vix=18.0, vix3m=19.0):
    def f(url):
        name = url.split("/")[-1].split("_")[0]
        v = {"VIX": vix, "VIX3M": vix3m, "VIX9D": 17.0, "SKEW": 140.0}[name]
        return f"DATE,OPEN,HIGH,LOW,CLOSE\n10/15/2026,{v},{v},{v},{v}\n"
    return f


def log_day(cfg, sd, day, spots=None, *, expiries=EXPS, when="close", vix=18.0, vix3m=19.0, seen=None, **kw):
    spots = spots or SPOTS
    chains = {u: (make_chain(u, s, day, expiries, **kw), s) for u, s in spots.items()}
    now = close_utc(day) if when == "close" else run_1545_utc(day)
    return run.log_chains(cfg, sd, when, now=now, fetch=fake_fetch(chains, seen), cboe_fetch=cboe(vix, vix3m))


ACCT = {"regime_label": "bull_calm", "equity": 100_000, "uncommitted_cash": 90_000}


def run_day(cfg, sd, day, **kw):
    args = {**ACCT, **kw}
    return run.run_options(cfg, sd, now=close_utc(day), **args)


@pytest.fixture
def sd(tmp_path):
    return tmp_path


def write_skip(sd, day, k, **fields):
    folder = run.pending_dir(day, sd)
    folder.mkdir(parents=True, exist_ok=True)
    body = {"date": day, "choice": "skip", "reason_code": "DATA_SUSPECT", "evidence": ["candidate.short.bid"],
            "prediction": {"probability": 0.5}, **fields}
    p = folder / f"skip_{k}.json"
    p.write_text(json.dumps(body))
    return p


# --- broker: prefix-scoped cancel (owner decision 6) ------------------------------------------------------


class FakeTradingClient:
    def __init__(self, orders=(), base="https://paper-api.alpaca.markets"):
        self._base_url = base
        self.orders = list(orders)
        self.cancelled_ids, self.cancel_all = [], 0
        self.submitted = []
        self.account = SimpleNamespace(equity="100000", cash="80000", maintenance_margin="200",
                                       options_trading_level=3, options_approved_level=3, status="ACTIVE")
        self.config = SimpleNamespace(max_options_trading_level=3)
        self.positions = []
        self.by_cid = {}
        self.fail_cancel = set()

    def get_orders(self, req):
        assert req.status.value == "open"
        return self.orders

    def cancel_order_by_id(self, oid):
        if oid in self.fail_cancel:
            raise RuntimeError("order is not cancelable")
        self.cancelled_ids.append(oid)

    def cancel_orders(self):
        self.cancel_all += 1

    def get_account(self):
        return self.account

    def get_account_configurations(self):
        return self.config

    def get_all_positions(self):
        return self.positions

    def submit_order(self, req):
        self.submitted.append(req)
        return SimpleNamespace(status="accepted", id="b-1", client_order_id=req.client_order_id)

    def get_order_by_client_id(self, cid):
        if cid in self.by_cid:
            return self.by_cid[cid]
        raise RuntimeError("order not found 40410000")

    def get(self, path, params):
        self.last_get = (path, params)
        return [{"id": "a1", "activity_type": "OPASN", "symbol": "SPY261120P00631000", "qty": "1",
                 "date": "2026-11-02", "price": None, "side": "buy"}]


def order(cid, oid):
    return SimpleNamespace(client_order_id=cid, id=oid)


def test_cancel_without_prefixes_keeps_old_behaviour():
    c = FakeTradingClient()
    assert AlpacaPaperBroker("k", "s", [], client=c).cancel_open_orders() is None
    assert c.cancel_all == 1 and c.cancelled_ids == []


def test_cancel_with_prefixes_only_touches_own_orders():
    c = FakeTradingClient([order("OPT-20261016-open-a", "1"), order("rules-SPY-buy-1", "2"),
                           order("claude-QQQ-sell-1", "3"), order(None, "4")])
    b = AlpacaPaperBroker("k", "s", [], client=c)
    assert b.cancel_open_orders(prefixes=["rules"]) == ["rules-SPY-buy-1"]
    assert c.cancelled_ids == ["2"] and c.cancel_all == 0
    assert b.cancel_open_orders(prefixes="OPT-") == ["OPT-20261016-open-a"]  # a bare string is one prefix


def test_cancel_with_empty_or_blank_prefixes_cancels_nothing():
    c = FakeTradingClient([order("rules-SPY-buy-1", "2")])
    b = AlpacaPaperBroker("k", "s", [], client=c)
    assert b.cancel_open_orders(prefixes=[]) == []
    assert b.cancel_open_orders(prefixes=["", "  "]) == []
    assert c.cancelled_ids == [] and c.cancel_all == 0
    assert clean_prefixes(None) == () and clean_prefixes("OPT-") == ("OPT-",)


def test_cancel_failure_is_recorded_not_raised():
    c = FakeTradingClient([order("OPT-a", "1"), order("OPT-b", "2")])
    c.fail_cancel = {"1"}
    b = AlpacaPaperBroker("k", "s", [], client=c)
    assert b.cancel_open_orders(prefixes=["OPT-"]) == ["OPT-b"]
    assert "OPT-a" in b.last_cancel_errors[0]


def test_sim_cancel_with_prefixes_keeps_other_books_orders(cfg):
    st = {"cash": 1000.0, "positions": {}, "open_orders": [
        {"client_order_id": "rules-SPY-buy-1", "symbol": "SPY", "side": "buy", "qty": 1, "date": "2026-10-16"},
        {"client_order_id": "OPT-x", "symbol": "SPY", "side": "buy", "qty": 1, "date": "2026-10-16"}]}
    b = SimBroker(st, {"SPY": 100.0}, {"etf": 5}, cfg.asset_class, bars={"SPY": pd.DataFrame()},
                  fill_mode="next_open")
    assert b.cancel_open_orders(prefixes=["rules"]) == ["rules-SPY-buy-1"]
    assert [o["client_order_id"] for o in st["open_orders"]] == ["OPT-x"]
    assert st["closed_orders"]["rules-SPY-buy-1"]["status"] == "canceled"
    assert b.cancel_open_orders() is None and st["open_orders"] == []


# --- broker: options reads and the gated mleg submit ----------------------------------------------------------


def mleg_order(limit=-0.25, prefix="OPT-", intent="open", qty=1):
    open_ = intent == "open"
    return {"legs": [{"symbol": "SPY261120P00631000", "side": "sell" if open_ else "buy",
                      "position_intent": "sell_to_open" if open_ else "buy_to_close", "ratio_qty": 1},
                     {"symbol": "SPY261120P00629000", "side": "buy" if open_ else "sell",
                      "position_intent": "buy_to_open" if open_ else "sell_to_close", "ratio_qty": 1}],
            "qty": qty, "limit_price": limit, "intent": intent, "order_class": "mleg", "type": "limit",
            "time_in_force": "day", "extended_hours": False, "client_order_id": f"{prefix}20261016-open-abc"}


@pytest.mark.parametrize("kw,why", [({"enabled": False, "gate_ok": True}, "OPT-1"),
                                    ({"enabled": True, "gate_ok": False}, "OPT-41")])
def test_submit_mleg_refuses_without_enable_and_gate(kw, why):
    c = FakeTradingClient()
    res = AlpacaPaperBroker("k", "s", [], client=c).submit_mleg(mleg_order(), **kw)
    assert res["status"] == "refused" and why in res["error"] and c.submitted == []


def test_submit_mleg_refuses_live_or_unknown_host():
    for base in ("https://api.alpaca.markets", None):
        c = FakeTradingClient(base=base)
        b = AlpacaPaperBroker("k", "s", [], client=c)
        assert not b.is_paper()
        assert b.submit_mleg(mleg_order(), enabled=True, gate_ok=True)["status"] == "refused"
        assert c.submitted == []


@pytest.mark.parametrize("o,why", [
    (mleg_order(limit=0.25), "negative limit"),  # OPT-14 sign: credit entry must be negative
    (mleg_order(limit=-0.25, intent="close"), "positive limit"),
    (mleg_order(prefix="rules-"), "owner decision 6"),
    ({**mleg_order(), "type": "market"}, "LIMIT"),
    ({**mleg_order(), "qty": 1.5}, "whole number"),
    ({**mleg_order(), "legs": mleg_order()["legs"][:1]}, "exactly 2 legs"),
    ({**mleg_order(), "extended_hours": True}, "extended"),
])
def test_mleg_problems_catch_bad_orders(o, why):
    assert any(why in p for p in mleg_problems(o, enabled=True, gate_ok=True, paper=True))


def test_submit_mleg_sends_one_limit_day_mleg_order():
    c = FakeTradingClient()
    res = AlpacaPaperBroker("k", "s", [], client=c).submit_mleg(mleg_order(), enabled=True, gate_ok=True)
    assert res["status"] == "accepted" and len(c.submitted) == 1
    req = c.submitted[0].to_request_fields()
    assert req["order_class"].value == "mleg" and req["type"].value == "limit" and req["time_in_force"].value == "day"
    assert req["limit_price"] == -0.25 and len(req["legs"]) == 2 and req["client_order_id"].startswith("OPT-")
    assert {l["position_intent"].value for l in req["legs"]} == {"sell_to_open", "buy_to_open"}


def single_order(**kw):
    return {"client_order_id": "OPT-20261019-asn-abc", "symbol": "SPY", "qty": 100, "side": "sell", "type": "limit",
            "time_in_force": "day", "limit_price": 650.0, **kw}


@pytest.mark.parametrize("o,why", [
    (single_order(side="buy"), "only sell"),
    (single_order(client_order_id="rules-x"), "owner decision 6"),
    (single_order(type="market"), "LIMIT"),
    (single_order(qty=10.5), "whole number"),
    (single_order(limit_price=0), "positive"),
    (single_order(symbol="SPY261120P00629000"), "SELL_TO_CLOSE"),
    (single_order(position_intent="sell_to_close"), "no position intent"),
])
def test_single_problems_catch_bad_cleanup_orders(o, why):
    assert any(why in p for p in single_problems(o, enabled=True, gate_ok=True, paper=True))


def test_submit_single_is_gated_and_sends_one_limit_day_sell():
    c = FakeTradingClient()
    b = AlpacaPaperBroker("k", "s", [], client=c)
    assert b.submit_single(single_order(), enabled=False, gate_ok=True)["status"] == "refused"
    assert b.submit_single(single_order(), enabled=True, gate_ok=False)["status"] == "refused"
    assert AlpacaPaperBroker("k", "s", [], client=FakeTradingClient(base=None)).submit_single(
        single_order(), enabled=True, gate_ok=True)["status"] == "refused"
    assert c.submitted == []
    assert b.submit_single(single_order(), enabled=True, gate_ok=True)["status"] == "accepted"
    opt = single_order(symbol="SPY261120P00629000", qty=1, limit_price=0.4, position_intent="sell_to_close")
    assert b.submit_single(opt, enabled=True, gate_ok=True)["status"] == "accepted"
    stock, option = (r.to_request_fields() for r in c.submitted)
    assert stock["side"].value == "sell" and stock["type"].value == "limit" and stock["time_in_force"].value == "day"
    assert "position_intent" not in stock and option["position_intent"].value == "sell_to_close"


def test_options_account_positions_activities_and_fills():
    c = FakeTradingClient()
    c.positions = [SimpleNamespace(symbol="SPY261120P00631000", qty="-1", side="short", asset_class="us_option",
                                   avg_entry_price="2.0", market_value="-150"),
                   SimpleNamespace(symbol="SPY", qty="10", side="long", asset_class="us_equity",
                                   avg_entry_price="600", market_value="6600")]
    b = AlpacaPaperBroker("k", "s", [], client=c)
    a = b.options_account()
    assert a["paper"] and a["options_trading_level"] == 3 and a["max_options_trading_level"] == 3
    assert a["maintenance_margin"] == 200.0 and a["problems"] == []
    pos = b.positions_detail()
    assert pos[0]["qty"] == -1.0 and pos[0]["side"] == "short" and pos[1]["qty"] == 10.0
    acts = b.option_activities()
    assert acts[0]["activity_type"] == "OPASN" and c.last_get[1]["activity_types"] == "OPASN,OPEXC,OPEXP"
    leg = SimpleNamespace(symbol="SPY261120P00631000", side="sell", position_intent="sell_to_open",
                          filled_qty="1", filled_avg_price="2.10")
    c.by_cid["OPT-a"] = SimpleNamespace(status="filled", filled_qty="1", filled_avg_price="0.3",
                                        filled_at="2026-10-19T19:50:00Z", id="b1", client_order_id="OPT-a",
                                        symbol=None, side=None, legs=[leg])
    rows = b.mleg_fills([{"client_order_id": "OPT-a"}, {"client_order_id": "OPT-missing"}])
    assert rows[0]["filled_qty"] == 1.0 and rows[0]["legs"][0]["filled_avg_price"] == 2.10
    assert rows[1]["status"] == "unknown" and rows[1]["legs"] == []


def test_options_account_read_failure_is_a_problem_not_a_crash():
    c = FakeTradingClient()
    c.get_account = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    a = AlpacaPaperBroker("k", "s", [], client=c).options_account()
    assert a["equity"] is None and "account read failed" in a["problems"][0]
    assert any("account read failed" in p for p in run.startup_checks(a, [], {}, {}))


# --- OPT-6 start-up checks ---------------------------------------------------------------------------------------


GOOD_ACCT = {"paper": True, "options_trading_level": 3, "max_options_trading_level": 3, "problems": []}


def test_opt6_all_good_passes():
    assert run.startup_checks(GOOD_ACCT, [{"symbol": "SPY", "qty": 5}], {"SPY": 5}, {}) == []


@pytest.mark.parametrize("change,why", [({"paper": False}, "not a paper"),
                                        ({"options_trading_level": 2}, "options_trading_level"),
                                        ({"options_trading_level": None}, "options_trading_level"),
                                        ({"max_options_trading_level": None}, "max_options_trading_level"),
                                        ({"max_options_trading_level": 2}, "max_options_trading_level")])
def test_opt6_each_failure(change, why):
    assert any(why in p for p in run.startup_checks({**GOOD_ACCT, **change}, [], {}, {}))


def test_opt6_unowned_stock_fails_but_o_stock_and_options_are_fine():
    assert run.startup_checks(GOOD_ACCT, [{"symbol": "SPY", "qty": 105}], {"SPY": 5}, {"SPY": 100}) == []
    assert run.startup_checks(GOOD_ACCT, [{"symbol": "SPY261120P00631000", "qty": -1}], {}, {}) == []
    bad = run.startup_checks(GOOD_ACCT, [{"symbol": "XOM", "qty": 3}], {"SPY": 5}, {})
    assert bad and "XOM" in bad[0]


def test_rules_fill_pending_booking_is_not_unowned_stock(sd):
    """A rules-book order that filled before the rules run booked it must not freeze book O's entries."""
    st = BookState(book="rules")
    st.lots = {"A": {"SPY": Lot(qty=4, entry_price=600, entry_date="2026-10-01", stop=0)}}
    st.pending_orders = [{"client_order_id": "R2026-SPY-buy-1", "symbol": "SPY", "side": "buy", "qty": 10.0,
                          "settled_qty": 0.0, "signal_close": 660.0}]
    st.save(sd)
    assert run.rules_pending_stock(sd) == {"SPY": 10.0}
    pos = [{"symbol": "SPY", "qty": 14.0}]
    other, notes = run.explain_pending(pos, run.other_books_stock(sd), run.rules_pending_stock(sd), {})
    assert other == {"SPY": 14.0} and "pending booking" in notes[0]
    assert run.startup_checks(GOOD_ACCT, pos, other, {}) == []
    # more than the pending order explains is still unowned
    other, _ = run.explain_pending([{"symbol": "SPY", "qty": 30.0}], {"SPY": 4.0}, {"SPY": 10.0}, {})
    assert run.startup_checks(GOOD_ACCT, [{"symbol": "SPY", "qty": 30.0}], other, {})


def test_other_books_stock_reads_the_rules_ledger(sd):
    st = BookState(book="rules")
    st.lots = {"A": {"SPY": Lot(qty=4, entry_price=600, entry_date="2026-10-01", stop=0)},
               "C": {"NVDA": Lot(qty=2, entry_price=100, entry_date="2026-10-01", stop=90)}}
    st.save(sd)
    assert run.other_books_stock(sd) == {"SPY": 4, "NVDA": 2}
    assert run.other_books_stock(sd / "nothing") == {}


# --- OPT-35 wiring ----------------------------------------------------------------------------------------------


def test_log_chains_logs_every_held_and_shadow_leg(cfg, sd):
    log_day(cfg, sd, DAY)
    run_day(cfg, sd, DAY)
    held = run.held_symbols(sd)
    assert held and all(s.startswith(("SPY", "QQQ", "IWM")) for s in held)
    seen = {}
    rec = log_day(cfg, sd, "2026-10-19", seen=seen)
    assert rec["complete"]
    spy_legs = [s for s in held if s.startswith("SPY")]
    assert set(spy_legs) <= set(seen["SPY"])


def test_load_chain_falls_back_and_spots_from_bars(cfg, sd):
    assert run.load_chain(DAY, sd) == (None, None)
    log_day(cfg, sd, DAY, when="1545")
    snap, when = run.load_chain(DAY, sd)
    assert when == "1545" and run.spots_of(snap)["SPY"] == 660.0
    bars = {"SPY": pd.DataFrame({"close": [650.0, float("nan"), 655.0]},
                                index=pd.to_datetime(["2026-10-14", "2026-10-15", "2026-10-17"]))}
    assert run.spots_of(None, bars, DAY) == {"SPY": 650.0}  # never a later close (no look-ahead), NaN skipped


def test_regime_from_bars_needs_history():
    assert run.regime_label_from_bars(None) == (None, "no SPY bars")
    short = {"SPY": pd.DataFrame({"close": [1.0] * 10}, index=pd.bdate_range("2026-01-01", periods=10))}
    assert run.regime_label_from_bars(short)[0] is None
    idx = pd.bdate_range(end=DAY, periods=400)
    up = {"SPY": pd.DataFrame({"close": [100 + i * 0.1 for i in range(400)]}, index=idx)}
    assert run.regime_label_from_bars(up, DAY)[0] in ("bull_calm", "bull_volatile", "choppy")


# --- OPT-33 menu ---------------------------------------------------------------------------------------------


def test_prepare_writes_a_one_spread_menu_and_touches_nothing_else(cfg, sd):
    log_day(cfg, sd, DAY)
    out = run.prepare_options(cfg, sd, date=DAY, **ACCT)
    c = out["candidate"]
    assert c and c["underlying"] == "SPY" and c["contracts"] >= 1 and c["limit_price"] < 0
    folder = run.pending_dir(DAY, sd)
    ctx = json.loads((folder / "context.json").read_text())
    assert ctx["menu"] == {"kind": "one spread", "choices": ["follow", "skip"]}
    assert ctx["prediction_rule"]["direction"] == "below" and ctx["prediction_rule"]["horizon"] == 20
    assert ctx["prediction_rule"]["threshold_pct"] == pytest.approx((c["short"]["strike"] / 660.0 - 1) * 100, abs=1e-3)
    assert ctx["order_session"] == "2026-10-19"
    assert "headline" not in json.dumps(ctx).lower()
    schema = json.loads((folder / "schema.json").read_text())
    assert schema["additionalProperties"] is False and "choice" in schema["properties"]
    assert "never choose strikes" in (folder / "instructions.md").read_text()
    assert not osh.ShadowO.path(sd).exists() and not OptionsBook.path(sd).exists()


def test_prepare_without_regime_or_cash_gives_no_spread(cfg, sd):
    log_day(cfg, sd, DAY)
    out = run.prepare_options(cfg, sd, date=DAY, equity=100_000, uncommitted_cash=90_000)
    assert out["candidate"] is None and any("OPT-19" in r for r in out["reasons"])
    out = run.prepare_options(cfg, sd, date=DAY, regime_label="bull_calm", equity=100_000)
    assert out["candidate"] is None and any("assignment cover" in r for r in out["reasons"])
    ctx = json.loads((run.pending_dir(DAY, sd) / "context.json").read_text())
    assert ctx["menu"]["kind"] == "none" and "candidate" not in ctx


def test_prepare_bear_regime_and_missing_chain(cfg, sd):
    assert any("OPT-27" in r for r in run.prepare_options(cfg, sd, date=DAY, **ACCT)["reasons"])
    log_day(cfg, sd, DAY)
    out = run.prepare_options(cfg, sd, date=DAY, **{**ACCT, "regime_label": "bear"})
    assert out["candidate"] is None and any("permission 0" in r for r in out["reasons"])


def test_prepare_moves_stale_skip_files(cfg, sd):
    log_day(cfg, sd, DAY)
    write_skip(sd, DAY, 1)
    run.prepare_options(cfg, sd, date=DAY, **ACCT)
    assert run.find_decision_files(DAY, sd) == []
    assert (run.pending_dir(DAY, sd) / "stale" / "skip_1.json").exists()


# --- OPT-34 skips ------------------------------------------------------------------------------------------------


def prepared(cfg, sd, day=DAY, samples=3):
    log_day(cfg, sd, day)
    return run.prepare_options(cfg, sd, date=day, samples=samples, **ACCT)["candidate"]


def test_majority_skip_opens_skip_shadow_with_code_built_prediction(cfg, sd):
    c = prepared(cfg, sd)
    write_skip(sd, DAY, 1, prediction={"probability": 0.5, "threshold_pct": -50, "horizon": 60})
    write_skip(sd, DAY, 2)
    write_skip(sd, DAY, 3, choice="follow", reason_code="NONE", evidence=[], prediction=None)
    e = run_day(cfg, sd, DAY)
    assert e["skip"]["skip"]["reason_code"] == "DATA_SUSPECT" and e["skip"]["samples"] == 3
    assert any("replaced by code" in p for p in e["skip"]["problems"])
    sh = osh.ShadowO.load(sd)
    assert len(sh.skips.open_lots()) == 1 and sh.skips.open_lots()[0].lot_id.startswith("K-")
    pred = sh.predictions[0]
    assert pred["horizon"] == 20 and pred["direction"] == "below" and pred["symbol"] == "SPY"
    assert pred["threshold_pct"] == pytest.approx((c["short"]["strike"] / c["spot"] - 1) * 100, abs=1e-3)
    # the rules' shadow book still books its spread (OPT-36 follows the rules, not Claude)
    assert len(sh.book.open_lots()) == 1 and sh.book.open_lots()[0].tags["skipped"] is True


def test_skip_probability_not_above_delta_is_dropped(cfg, sd):
    c = prepared(cfg, sd)
    write_skip(sd, DAY, 1, prediction={"probability": abs(c["short"]["delta"])})
    e = run_day(cfg, sd, DAY)
    assert e["skip"]["skip"] is None and any("argues for the trade" in p for p in e["skip"]["problems"])
    assert osh.ShadowO.load(sd).skips.open_lots() == []


def test_claude_strike_choice_is_dropped_but_logged(cfg, sd):
    prepared(cfg, sd)
    write_skip(sd, DAY, 1, choice="follow", reason_code="NONE", evidence=[], prediction=None,
               short_strike=600, contracts=5, width=10)
    e = run_day(cfg, sd, DAY)
    assert any("OPT-33 dropped keys" in p and "short_strike" in p for p in e["skip"]["problems"])
    lot = osh.ShadowO.load(sd).book.open_lots()[0]
    assert lot.width in (2.0, 3.0, 4.0, 5.0) and lot.contracts == e["shadow_entry"]["contracts"]


@pytest.mark.parametrize("fields,why", [
    ({"reason_code": "NONE"}, "reason code"),
    ({"reason_code": "EARNINGS_IN_WINDOW"}, "invalid"),  # not an O code: the file is invalid
    ({"evidence": []}, "evidence"),
    ({"evidence": ["candidate.nothing_here"]}, "not in today's context"),
    ({"evidence": ["date"]}, "not market data"),
    ({"prediction": None}, "prediction"),
    ({"date": "2026-10-15"}, "is not"),
    ({"reason_code": "SCHEDULED_EVENT", "event_date": "2026-10-30"}, "order session"),
])
def test_bad_skips_are_dropped(cfg, sd, fields, why):
    prepared(cfg, sd)
    write_skip(sd, DAY, 1, **fields)
    e = run_day(cfg, sd, DAY)
    assert e["skip"]["skip"] is None
    assert any(why in p for p in e["skip"]["problems"]), e["skip"]["problems"]


def test_scheduled_event_on_the_order_session_is_allowed(cfg, sd):
    prepared(cfg, sd, samples=1)
    write_skip(sd, DAY, 1, reason_code="SCHEDULED_EVENT", event_date="2026-10-19")
    assert run_day(cfg, sd, DAY)["skip"]["skip"]["reason_code"] == "SCHEDULED_EVENT"


def test_minority_skip_is_not_applied(cfg, sd):
    prepared(cfg, sd)
    write_skip(sd, DAY, 1)
    for k in (2, 3):
        write_skip(sd, DAY, k, choice="follow", reason_code="NONE", evidence=[], prediction=None)
    e = run_day(cfg, sd, DAY)
    assert e["skip"]["skip"] is None and any("strict majority" in p for p in e["skip"]["problems"])


def test_one_skip_of_three_requested_is_not_a_majority(cfg, sd):
    """Guide rule 8: missing or unreadable samples count as "no skip"; the denominator is the samples requested."""
    prepared(cfg, sd, samples=3)
    write_skip(sd, DAY, 1)
    (run.pending_dir(DAY, sd) / "skip_2.json").write_text("{broken")
    e = run_day(cfg, sd, DAY)
    assert e["skip"]["skip"] is None and e["skip"]["requested"] == 3 and e["skip"]["skips"] == 1
    assert osh.ShadowO.load(sd).skips.open_lots() == []
    # two valid skips of three requested is a strict majority
    write_skip(sd, DAY, 2)
    assert run_day(cfg, sd, DAY)["skip"]["skip"] is not None


def test_skip_prediction_carries_a_base_rate_from_bars(cfg, sd):
    prepared(cfg, sd, samples=1)
    write_skip(sd, DAY, 1)
    idx = pd.bdate_range(end=DAY, periods=400)
    closes = [600.0 + 60.0 * ((i % 40) / 40.0) for i in range(len(idx))]
    run_day(cfg, sd, DAY, bars={"SPY": pd.DataFrame({"close": closes}, index=idx)})
    pred = osh.ShadowO.load(sd).predictions[0]
    assert pred["base_rate"] is not None and 0.0 <= pred["base_rate"] <= 1.0


def test_skip_without_a_prepared_menu_is_ignored(cfg, sd):
    log_day(cfg, sd, DAY)
    p = write_skip(sd, DAY, 1)
    e = run_day(cfg, sd, DAY, decision_files=[p])
    assert e["skip"]["skip"] is None and "no menu prepared" in e["skip"]["problems"][0]


def test_rerun_same_day_is_idempotent(cfg, sd):
    prepared(cfg, sd, samples=1)
    write_skip(sd, DAY, 1)
    run_day(cfg, sd, DAY)
    run_day(cfg, sd, DAY)
    sh = osh.ShadowO.load(sd)
    assert len(sh.book.open_lots()) == 1 and len(sh.skips.open_lots()) == 1
    assert len(sh.predictions) == 1 and len(sh.skip_log) == 1 and len(sh.trackers) == 1
    assert len([r for r in sh.evaluations if r["date"] == DAY]) == 1


# --- OPT-36 shadow book ---------------------------------------------------------------------------------------------


def test_shadow_entry_at_mid_minus_half_cost_and_opt22_exit(cfg, sd):
    c = prepared(cfg, sd)
    e = run_day(cfg, sd, DAY)
    assert e["shadow_entry"]["credit"] == pytest.approx(c["mid_credit"] - 0.5 * c["quoted_cost"])
    lot = osh.ShadowO.load(sd).book.open_lots()[0]
    assert lot.shadow and lot.lot_id.startswith("S-") and lot.max_loss == pytest.approx(
        (lot.width - lot.entry_credit_per_share) * 100 * lot.contracts)
    log_day(cfg, sd, "2026-11-13", expiries=EXPS[1:], spots={"SPY": 670.0, "QQQ": 590.0, "IWM": 245.0})
    e2 = run_day(cfg, sd, "2026-11-13")
    ex = [x for x in e2["shadow_exits"] if x["underlying"] == "SPY"][0]
    assert ex["reason"] == ob.EXIT_EXPIRY and ex["R"] > 0
    rec = osh.ShadowO.load(sd).book.closed[0]
    assert rec["R"] == pytest.approx(rec["pnl"] / rec["max_loss"])
    assert rec["R_paper"] >= rec["R"]  # the model view pays model fees on top


def test_shadow_short_strike_exit_and_missing_quotes_close_at_width(cfg, sd):
    c = prepared(cfg, sd)
    run_day(cfg, sd, DAY)
    crash = {"SPY": c["short"]["strike"] - 5, "QQQ": 580.0, "IWM": 240.0}
    log_day(cfg, sd, "2026-10-19", spots=crash)
    e = run_day(cfg, sd, "2026-10-19")
    assert [x["reason"] for x in e["shadow_exits"] if x["underlying"] == "SPY"] == [ob.EXIT_SHORT_STRIKE]
    # a second spread cannot open in the same cycle (OPT-18/OPT-24)
    assert "shadow_entry" not in e


def test_exit_fires_without_a_chain(cfg, sd):
    prepared(cfg, sd)
    run_day(cfg, sd, DAY)
    e = run_day(cfg, sd, "2026-11-13")  # no snapshot logged that day: exits still run, entries do not
    ex = [x for x in e["shadow_exits"] if x["underlying"] == "SPY"][0]
    rec = osh.ShadowO.load(sd).book.closed[0]
    assert ex["reason"] == ob.EXIT_EXPIRY and rec["exit_debit"] == pytest.approx(rec["width"])
    assert rec["tags"]["exit_model"]["unmarked"] is True
    assert any("OPT-27" in r for r in e["menu"]["reasons"])


def test_expiry_settlement_at_intrinsic():
    lot = SpreadLot("S-1", "SPY", "2026-11-20", "put", OptionLeg("SPY261120P00631000", "put", 631, "2026-11-20",
                                                                  "short", 1),
                    OptionLeg("SPY261120P00629000", "put", 629, "2026-11-20", "long", 1), 1, 2.0, 0.3, 170, 172,
                    "2026-10-16")
    assert osh.expiry_value(lot, 640) == 0 and osh.expiry_value(lot, 630) == 1.0
    assert osh.expiry_value(lot, 600) == 2.0 and osh.expiry_value(lot, None) == 2.0
    book = OptionsBook(lots={"S-1": lot})
    lot.tags = {"entry_contracts": 1, "fees_actual": 0.0, "model_pnl_adj": 0.0}
    recs = osh.update_exits(book, [], {"SPY": 630.0}, "2026-11-20")
    assert recs[0]["exit_debit"] == 1.0 and "settled at expiry" in recs[0]["reason"]


def test_opt31_drawdown_closes_every_shadow_spread(cfg, sd):
    prepared(cfg, sd)
    run_day(cfg, sd, DAY)
    sh = osh.ShadowO.load(sd)
    sh.book.peak_pnl = 3000.0  # a high-water mark far above: drawdown >= 2% of E
    sh.save(sd)
    log_day(cfg, sd, "2026-10-19")
    e = run_day(cfg, sd, "2026-10-19")
    assert e["shadow_breakers"]["close_all"] and e["shadow_breakers"]["halt"]
    assert osh.ShadowO.load(sd).book.open_lots() == [] and osh.ShadowO.load(sd).book.halted
    assert [x["reason"] for x in e["shadow_exits"] if x["underlying"] == "SPY"] == ["OPT-31 drawdown halt"]


def test_opt13_wide_quotes_block_and_count_in_no_trade_rate(cfg, sd):
    log_day(cfg, sd, DAY, leg_spread=0.05)
    e = run_day(cfg, sd, DAY)
    assert "shadow_entry" not in e and any("OPT-13" in r for r in e["menu"]["reasons"])
    assert e["evaluation"]["opt13_blocked"] and e["evaluation"]["eligible"]
    ntr = osh.no_trade_rate(osh.ShadowO.load(sd).evaluations)
    assert ntr == {"eligible_cycles": 1, "blocked_by_opt13": 1, "rate": 1.0}


def test_missing_greeks_block_entries(cfg, sd):
    log_day(cfg, sd, DAY, drop_greeks=True)
    e = run_day(cfg, sd, DAY)
    assert "shadow_entry" not in e


# --- OPT-20, OPT-25, OPT-39 variants --------------------------------------------------------------------------------


def test_opt20_record_is_logged_only(cfg, sd):
    log_day(cfg, sd, DAY, vix=25.0, vix3m=20.0)
    e = run_day(cfg, sd, DAY)
    assert "shadow_entry" in e  # variant (i) never blocks the real rule
    lot = osh.ShadowO.load(sd).book.open_lots()[0]
    assert lot.tags["opt20"]["blocks_entry"] is True and lot.tags["opt20"]["ratio"] == 1.25
    assert osh.opt20_record(None)["blocks_entry"] is None
    report = run.report_options(cfg, sd)
    assert report["variants"]["OPT-20_i"]["n"] == 0


def tracker(credit=0.5, width=2.0):
    return {"lot_id": "S-1", "underlying": "SPY", "expiry": "2026-11-20", "short_symbol": "S", "long_symbol": "L",
            "short_strike": 631.0, "width": width, "credit": credit, "max_loss_pc": (width - credit) * 100,
            "entry_date": DAY, "fee": 0.04, "variants": {v: None for v in osh.EXIT_VARIANTS}}


def q(sym, bid, ask):
    return OptionQuote(sym, "SPY", "2026-11-20", "put", 631.0, bid, ask, None)


def test_opt25_take_profit_and_stops():
    t = tracker()
    osh.update_trackers([t], [q("S", 0.30, 0.30), q("L", 0.10, 0.10)], {"SPY": 660.0}, "2026-10-20")
    assert t["variants"]["tp50"]["debit"] == pytest.approx(0.20) and t["variants"]["tp50"]["R"] > 0
    assert t["variants"]["stop1x"] is None and t["variants"]["hold7"] is None
    t = tracker()
    osh.update_trackers([t], [q("S", 1.20, 1.20), q("L", 0.10, 0.10)], {"SPY": 660.0}, "2026-10-20")
    assert t["variants"]["stop1x"]["debit"] == pytest.approx(1.1)  # loss 0.6 >= 1x the 0.5 credit
    assert t["variants"]["stop2x"] is None  # but not 2x
    osh.update_trackers([t], [q("S", 1.80, 1.80), q("L", 0.20, 0.20)], {"SPY": 660.0}, "2026-10-21")
    assert t["variants"]["stop2x"]["debit"] == pytest.approx(1.6) and t["variants"]["stop2x"]["R"] < 0


def test_opt25_stop2x_needs_twice_the_credit_and_hold7_waits():
    t = tracker()
    osh.update_trackers([t], [q("S", 1.10, 1.10), q("L", 0.20, 0.20)], {"SPY": 660.0}, "2026-10-20")
    assert t["variants"]["stop1x"] is None and t["variants"]["stop2x"] is None  # loss 0.4 < 1x the credit
    osh.update_trackers([t], [], {"SPY": 600.0}, "2026-10-21")  # below the short strike, quotes missing
    assert t["variants"]["time21"]["unmarked"] and t["variants"]["hold7"] is None
    osh.update_trackers([t], [], {"SPY": 600.0}, "2026-11-13")
    assert t["variants"]["hold7"]["debit"] == 2.0 and osh.variant_summary([t])["hold7"]["n"] == 1


def test_opt39_variants_on_qqq_and_iwm(cfg, sd):
    prepared(cfg, sd)
    e = run_day(cfg, sd, DAY)
    assert e["opt39"]["QQQ"]["lot_id"].startswith("VQQQ-") and e["opt39"]["IWM"]["lot_id"].startswith("VIWM-")
    e = run_day(cfg, sd, DAY)
    assert e["opt39"]["QQQ"]["lot_id"] is None  # one spread per cycle per underlying
    und = sorted(l.underlying for l in osh.ShadowO.load(sd).variants.open_lots())
    assert und == ["IWM", "QQQ"]


# --- OPT-26 / OPT-27 with a broker --------------------------------------------------------------------------------


class FakeBroker:
    def __init__(self, positions=(), acct=None, fills=()):
        self.acct = {**GOOD_ACCT, "equity": 100_000.0, "cash": 90_000.0, "maintenance_margin": 0.0,
                     **(acct or {})}
        self._positions = list(positions)
        self.submitted = []
        self.singles = []
        self._fills = list(fills)

    def options_account(self):
        return dict(self.acct)

    def positions_detail(self):
        return list(self._positions)

    def option_activities(self):
        return []

    def submit_mleg(self, order, *, enabled, gate_ok, prefix="OPT-"):
        why = mleg_problems(order, enabled=enabled, gate_ok=gate_ok, paper=True, prefix=prefix)
        if why:
            return {"status": "refused", "error": "; ".join(why)}
        self.submitted.append(order)
        return {"status": "accepted", "id": f"b{len(self.submitted)}", "client_order_id": order["client_order_id"]}

    def submit_single(self, order, *, enabled, gate_ok, prefix="OPT-"):
        why = single_problems(order, enabled=enabled, gate_ok=gate_ok, paper=True, prefix=prefix)
        if why:
            return {"status": "refused", "error": "; ".join(why)}
        self.singles.append(order)
        return {"status": "accepted", "id": f"s{len(self.singles)}", "client_order_id": order["client_order_id"]}

    def mleg_fills(self, pending):
        return [self._fills.pop(0)(p) if self._fills else {"client_order_id": p["client_order_id"],
                                                             "status": "accepted", "final": False, "filled_qty": 0}
                for p in pending]


def test_broker_account_feeds_the_shadow_sizing(cfg, sd):
    log_day(cfg, sd, DAY)
    e = run.run_options(cfg, sd, now=close_utc(DAY), regime_label="bull_calm", broker=FakeBroker())
    assert e["account"]["equity"] == 100_000.0 and e["account"]["uncommitted_cash"] == 90_000.0
    assert "shadow_entry" in e and e["broker_blocks"] == []
    # a later run without a broker reuses the stored read (<= 5 days old)
    e2 = run.run_options(cfg, sd, now=close_utc("2026-10-19"), regime_label="bull_calm")
    assert e2["account"]["equity"] == 100_000.0


def test_assigned_stock_freezes_entries_and_plans_cleanup(cfg, sd):
    log_day(cfg, sd, DAY)
    b = FakeBroker(positions=[{"symbol": "SPY", "qty": 100.0, "side": "long"}])
    e = run.run_options(cfg, sd, now=close_utc(DAY), regime_label="bull_calm", broker=b)
    assert "shadow_entry" not in e and any("OPT-26" in x for x in e["broker_blocks"])
    assert e["incidents"]["stock_excess"] == {"SPY": 100.0}
    assert e["cleanup_plan"][0]["action"] == "owner_review_stock"  # not O's stock: O never trades it
    assert b.submitted == []


def test_orphan_option_leg_is_an_incident(cfg, sd):
    log_day(cfg, sd, DAY)
    b = FakeBroker(positions=[{"symbol": "SPY261120P00631000", "qty": -1.0, "side": "short"}])
    e = run.run_options(cfg, sd, now=close_utc(DAY), regime_label="bull_calm", broker=b)
    assert any("naked short" in x for x in e["broker_blocks"]) and "shadow_entry" not in e


def test_opt6_failure_blocks_entries_but_not_exits(cfg, sd):
    prepared(cfg, sd)
    run_day(cfg, sd, DAY)
    b = FakeBroker(acct={"options_trading_level": 1})
    e = run.run_options(cfg, sd, now=close_utc("2026-11-13"), regime_label="bull_calm", broker=b)
    assert any("OPT-6" in x for x in e["broker_blocks"])
    assert [x["reason"] for x in e["shadow_exits"] if x["underlying"] == "SPY"] == [ob.EXIT_EXPIRY]


# --- gates (OPT-40, OPT-41, OPT-42) -----------------------------------------------------------------------------------


def test_gates_fail_closed_on_a_fresh_install(cfg, sd):
    g = run.gate_status(cfg, sd)
    assert g["paper_start_ok"] is False and g["orders_allowed"] is False and g["enabled"] is False
    assert g["opt42"]["live_ok"] is False and g["opt40"]["promotion_ok"] is False
    assert g["opt41"]["items"]["complete_chain_sessions"]["ok"] is False


def fake_index(sd, n):
    rows = []
    for i, d in enumerate(pd.bdate_range("2026-06-01", periods=n)):
        f = Path("options") / "chains" / d.date().isoformat() / "close.json.gz"
        (sd / f).parent.mkdir(parents=True, exist_ok=True)
        (sd / f).write_bytes(b"x")
        rows.append({"date": d.date().isoformat(), "when": "close", "complete": True, "file": str(f),
                     "per_underlying": {u: {"complete": True} for u in ("SPY", "QQQ", "IWM")}})
    (sd / "options" / "chains" / "chain_log_index.json").write_text(json.dumps(rows))


def passing_shadow():
    sh = osh.ShadowO()
    for exp, days in (("2026-07-17", pd.bdate_range("2026-06-11", "2026-06-17")),
                      ("2026-08-21", pd.bdate_range("2026-07-16", "2026-07-22"))):
        for d in days:
            osh.add_evaluation(sh, {"date": d.date().isoformat(), "when": "close", "underlying": "SPY",
                                    "in_window": True, "expiry": exp, "eligible": True, "opt13_blocked": True,
                                    "candidate": False, "ratio": 1.05})
    osh.add_evaluation(sh, {"date": "2026-09-01", "when": "close", "underlying": "SPY", "in_window": False})
    return sh


def approve(sd, key, **rec):
    p = sd / "options" / run.APPROVAL_FILE
    d = json.loads(p.read_text()) if p.exists() else {}
    d[key] = rec
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d))


def test_opt41_passes_only_with_every_item(cfg, sd):
    fake_index(sd, 40)
    sh = passing_shadow()
    g = run.gate_status(cfg, sd, shadow=sh)
    assert {k for k, v in g["opt41"]["items"].items() if not v["ok"]} == {"owner_yes"}
    approve(sd, "paper_start", approved="yes", date="2026-10-01", note="ok")  # not a literal true
    assert run.gate_status(cfg, sd, shadow=sh)["paper_start_ok"] is False
    approve(sd, "paper_start", approved=True, date="2026-10-01", note="")  # no written note
    assert run.gate_status(cfg, sd, shadow=sh)["paper_start_ok"] is False
    approve(sd, "paper_start", approved=True, date="2026-10-01", note="Owner: yes, start paper orders")
    g = run.gate_status(cfg, sd, shadow=sh)
    assert g["paper_start_ok"] is True
    assert g["orders_allowed"] is False  # options_book.enabled is still false (owner decision 10)


def test_opt41_counts_and_ratios(cfg, sd):
    fake_index(sd, 39)
    assert not run.gate_status(cfg, sd, shadow=passing_shadow())["opt41"]["items"]["complete_chain_sessions"]["ok"]
    sh = passing_shadow()
    for r in sh.evaluations:
        if r.get("ratio"):
            r["ratio"] = 1.4
    assert not run.opt41_status(cfg, sd, sh)["items"]["model_credit_ratio"]["ok"]
    few = osh.ShadowO(evaluations=passing_shadow().evaluations[:6] + passing_shadow().evaluations[-1:])
    assert osh.credit_ratio_check(few.evaluations, osh.completed_cycles(few.evaluations))["n"] < 10


def test_opt40_needs_backtest_shadow_and_owner(cfg, sd):
    bt = {"width_usd": 2.0, "base": {"E": 0.05}, "doubled_costs": {"E": 0.01}, "bil_E": 0.003,
          "sensitivity": {"a": {"E": 0.02}, "b": {"E": 0.01}}}
    (sd / "options" / "backtest").mkdir(parents=True)
    (sd / "options" / "backtest" / "latest.json").write_text(json.dumps(bt))
    sh = osh.ShadowO()
    lot_rec = {"lot": SpreadLot("S-1", "SPY", "2026-11-20", "put",
                                OptionLeg("A", "put", 631, "2026-11-20", "short", 0),
                                OptionLeg("B", "put", 629, "2026-11-20", "long", 0), 0, 2.0, 0.3, 170, 172,
                                "2026-10-16", status="closed").to_dict()}
    sh.book.closed = [{"R": 0.1, "R_paper": 0.1, "max_loss": 170, "width": 2.0, "contracts": 1, "lot_id": f"S-{i}",
                       "date": "2026-11-13", "entry_date": "2026-10-16", "tags": {"bil_rate": 0.04}, **lot_rec}
                      for i in range(30)]
    items = run.opt40_status(cfg, sd, sh, OptionsBook())["items"]
    # OPT-40 (i): the run on real Alpaca option bars is not built, so the item fails closed
    assert {k for k, v in items.items() if not v["ok"]} == {"owner_sign_off", "alpaca_option_bars_run"}
    bt["alpaca_option_bars"] = {"E": 0.03, "n": 25}
    (sd / "options" / "backtest" / "latest.json").write_text(json.dumps(bt))
    items = run.opt40_status(cfg, sd, sh, OptionsBook())["items"]
    assert {k for k, v in items.items() if not v["ok"]} == {"owner_sign_off"}
    # at most one promotion per quarter
    approve(sd, "promotion_history", date="x")
    d = json.loads((sd / "options" / run.APPROVAL_FILE).read_text())
    d["promotion_history"] = [{"date": "2026-08-03"}]
    (sd / "options" / run.APPROVAL_FILE).write_text(json.dumps(d))
    assert not run.opt40_status(cfg, sd, sh, OptionsBook(), now=close_utc("2026-09-15"))["items"][
        "one_promotion_per_quarter"]["ok"]
    assert run.opt40_status(cfg, sd, sh, OptionsBook(), now=close_utc("2026-10-15"))["items"][
        "one_promotion_per_quarter"]["ok"]
    bt["doubled_costs"]["E"] = -0.01
    (sd / "options" / "backtest" / "latest.json").write_text(json.dumps(bt))
    assert not run.opt40_status(cfg, sd, sh, OptionsBook())["items"]["doubled_costs_positive"]["ok"]


# --- the paper path (fake brokers only; enabled is false in the committed policy) --------------------------------------


def enabled_cfg(cfg):
    pol = json.loads(json.dumps(cfg.policy))
    pol["options_book"]["enabled"] = True
    return SimpleNamespace(policy=pol, playbook=cfg.playbook)


@pytest.fixture
def gate_open(monkeypatch):
    real = run.gate_status

    def fake(cfg, state_dir=None, **kw):
        g = real(cfg, state_dir, **kw)
        g["paper_start_ok"] = True
        g["orders_allowed"] = g["enabled"]
        return g
    monkeypatch.setattr(run, "gate_status", fake)


def test_no_order_while_disabled_even_with_gate_and_broker(cfg, sd, gate_open):
    log_day(cfg, sd, DAY)
    b = FakeBroker()
    e = run.run_options(cfg, sd, now=close_utc(DAY), regime_label="bull_calm", broker=b, dry_run=False)
    log_day(cfg, sd, "2026-10-19", when="1545")
    e2 = run.run_options(cfg, sd, now=run_1545_utc("2026-10-19"), when="1545", regime_label="bull_calm", broker=b,
                         dry_run=False)
    assert b.submitted == [] and e["orders_allowed"] is False and e2["orders_allowed"] is False
    assert run._load_paper(sd)["intents"] == []


def test_no_order_in_a_dry_run(cfg, sd, gate_open):
    ecfg = enabled_cfg(cfg)
    log_day(cfg, sd, DAY)
    b = FakeBroker()
    e = run.run_options(ecfg, sd, now=close_utc(DAY), regime_label="bull_calm", broker=b, dry_run=True)
    assert e["orders_allowed"] is False and b.submitted == []


def paper_flow(cfg, sd, spot_1545=660.0, fills=()):
    ecfg = enabled_cfg(cfg)
    log_day(cfg, sd, DAY)
    b = FakeBroker(acct={"equity": 400_000.0, "cash": 360_000.0}, fills=list(fills))
    run.run_options(ecfg, sd, now=close_utc(DAY), regime_label="bull_calm", broker=b, dry_run=False)
    log_day(cfg, sd, "2026-10-19", when="1545", spots={**SPOTS, "SPY": spot_1545})
    e = run.run_options(ecfg, sd, now=run_1545_utc("2026-10-19"), when="1545", regime_label="bull_calm",
                        broker=b, dry_run=False)
    return ecfg, b, e


def test_paper_entry_is_queued_then_sent_at_1545(cfg, sd, gate_open):
    _, b, e = paper_flow(cfg, sd)
    assert len(b.submitted) == 1
    o = b.submitted[0]
    assert o["limit_price"] < 0 and o["client_order_id"].startswith("OPT-") and o["qty"] >= 1
    assert o["type"] == "limit" and o["time_in_force"] == "day"
    assert run._load_paper(sd)["pending"][0]["intent"] == "open"
    assert run._load_paper(sd)["intents"] == []


def test_opt17_cancels_after_a_1pct_move(cfg, sd, gate_open):
    _, b, e = paper_flow(cfg, sd, spot_1545=660.0 * 1.02)
    assert b.submitted == [] and "OPT-17" in e["paper_orders"][0]["reasons"][0]


def test_partial_fill_books_only_filled_contracts_and_unfilled_is_retried_once(cfg, sd, gate_open):
    ecfg, b, _ = paper_flow(cfg, sd)
    pend = run._load_paper(sd)["pending"][0]
    assert pend["qty"] == 2
    short, long = pend["legs"]

    def partial(p):
        return {"client_order_id": p["client_order_id"], "status": "canceled", "final": True, "filled_qty": 1.0,
                "filled_avg_price": 0.3, "legs": [{"symbol": short, "filled_avg_price": 2.0},
                                                  {"symbol": long, "filled_avg_price": 1.7}]}
    b._fills = [partial]
    log_day(cfg, sd, "2026-10-19")
    run.run_options(ecfg, sd, now=close_utc("2026-10-19"), regime_label="bull_calm", broker=b, dry_run=False)
    lot = OptionsBook.load(sd).open_lots()[0]
    assert lot.contracts == 1 and lot.entry_credit_per_share == pytest.approx(0.3) and not lot.shadow
    assert run._load_paper(sd)["pending"] == []
    assert run.o_owned(sd)["symbols"] == {short, long}


def test_unfilled_entry_is_repriced_once_then_dropped(cfg, sd, gate_open):
    ecfg, b, _ = paper_flow(cfg, sd)

    def expired(p):
        return {"client_order_id": p["client_order_id"], "status": "expired", "final": True, "filled_qty": 0.0}
    b._fills = [expired]
    log_day(cfg, sd, "2026-10-19")
    run.run_options(ecfg, sd, now=close_utc("2026-10-19"), regime_label="bull_calm", broker=b, dry_run=False)
    intents = run._load_paper(sd)["intents"]
    assert len(intents) == 1 and intents[0]["tries"] == 1 and intents[0]["session"] == "2026-10-20"
    log_day(cfg, sd, "2026-10-20", when="1545")
    run.run_options(ecfg, sd, now=run_1545_utc("2026-10-20"), when="1545", regime_label="bull_calm", broker=b,
                    dry_run=False)
    first, retry = b.submitted
    assert -retry["limit_price"] < -first["limit_price"]  # OPT-14: mid - 25% of the quoted cost on the retry
    b._fills = [expired]
    log_day(cfg, sd, "2026-10-20")
    run.run_options(ecfg, sd, now=close_utc("2026-10-20"), regime_label="bull_calm", broker=b, dry_run=False)
    assert run._load_paper(sd)["intents"] == []


def test_paper_exit_uses_the_ladder_and_never_pays_above_width(cfg, sd, gate_open):
    ecfg = enabled_cfg(cfg)
    led = OptionsBook()
    cand = {"underlying": "SPY", "expiry": "2026-11-20", "type": "put", "spot": 660.0, "quoted_cost": 0.02,
            "mid_credit": 0.3, "short": {"symbol": "SPY261120P00631000", "strike": 631.0},
            "long": {"symbol": "SPY261120P00629000", "strike": 629.0}}
    led.open_spread(cand, {"contracts": 1, "credit_per_share": 0.3, "order_id": "OPT-x"}, "2026-10-19", shadow=False)
    led.save(sd)
    log_day(cfg, sd, "2026-11-13", expiries=EXPS[1:], spots={**SPOTS, "SPY": 625.0})
    pos = [{"symbol": "SPY261120P00631000", "qty": -1.0}, {"symbol": "SPY261120P00629000", "qty": 1.0}]
    b = FakeBroker(positions=pos, acct={"maintenance_margin": 200.0})
    e = run.run_options(ecfg, sd, now=close_utc("2026-11-13"), regime_label="bull_calm", broker=b, dry_run=False)
    # OPT-17: the after-close run only records the exit; nothing is queued overnight
    assert b.submitted == [] and e["exits_due"][0]["reason"] == ob.EXIT_EXPIRY_ITM
    assert run._load_paper(sd)["exit_tries"] == {}
    log_day(cfg, sd, "2026-11-16", when="1545", expiries=EXPS[1:], spots={**SPOTS, "SPY": 625.0})
    e = run.run_options(ecfg, sd, now=run_1545_utc("2026-11-16"), when="1545", regime_label="bull_calm",
                        broker=b, dry_run=False)
    assert len(b.submitted) == 1
    o = b.submitted[0]
    assert o["intent"] == "close" and 0 < o["limit_price"] <= 2.0
    po = [x for x in e["paper_orders"] if x.get("ladder")][0]
    assert po["reason"] == ob.EXIT_EXPIRY_ITM and po["ladder"]["basis"].startswith("natural")
    assert run.o_owned(sd)["symbols"] == {"SPY261120P00631000", "SPY261120P00629000"}


def test_paper_exit_due_while_disabled_is_only_logged(cfg, sd):
    led = OptionsBook()
    cand = {"underlying": "SPY", "expiry": "2026-11-20", "type": "put", "spot": 660.0,
            "short": {"symbol": "SPY261120P00631000", "strike": 631.0},
            "long": {"symbol": "SPY261120P00629000", "strike": 629.0}}
    led.open_spread(cand, {"contracts": 1, "credit_per_share": 0.3}, "2026-10-19", shadow=False)
    led.save(sd)
    b = FakeBroker()
    e = run.run_options(cfg, sd, now=close_utc("2026-11-13"), regime_label="bull_calm", broker=b, dry_run=False)
    assert b.submitted == [] and any("paper exit(s) due" in n for n in e["notes"])


def test_recheck_entry_rejects_moved_delta_and_wide_quotes(cfg, sd):
    c = prepared(cfg, sd)
    quotes = run.all_quotes(run.load_chain(DAY, sd)[0])
    fresh, why = run.recheck_entry(c, quotes, 660.0, DAY, cfg.policy)
    assert fresh and why == [] and fresh["limit_price"] < 0 and fresh["contracts"] <= c["contracts"]
    moved = [OptionQuote(**{**x.to_dict(), "delta": -0.40}) if x.symbol == c["short"]["symbol"] else x
             for x in quotes]
    assert "band" in run.recheck_entry(c, moved, 660.0, DAY, cfg.policy)[1][0]
    wide = [OptionQuote(**{**x.to_dict(), "ask": x.ask + 0.3}) if x.symbol == c["long"]["symbol"] else x
            for x in quotes]
    assert run.recheck_entry(c, wide, 660.0, DAY, cfg.policy)[0] is None
    assert "missing" in run.recheck_entry(c, quotes, None, DAY, cfg.policy)[1][0]


# --- report and separation ---------------------------------------------------------------------------------------------


def test_report_has_opt38_invested_gates_and_feed_note(cfg, sd):
    prepared(cfg, sd)
    run_day(cfg, sd, DAY)
    log_day(cfg, sd, "2026-11-13", expiries=EXPS[1:], spots={"SPY": 670.0, "QQQ": 590.0, "IWM": 245.0})
    run_day(cfg, sd, "2026-11-13")
    r = run.report_options(cfg, sd)
    s = r["shadow"]
    for k in ("n", "win_rate", "avg_win_R", "avg_loss_R", "E", "sqn", "worst_R", "slippage_pct_of_E",
              "max_drawdown_R", "no_trade_rate", "benchmarks"):
        assert k in s
    assert s["n"] == 1 and s["benchmarks"]["zero"] == 0.0 and s["benchmarks"]["bil_rate_assumed"] is True
    assert r["invested_per_trade"]["shadow"][0]["invested"] > 0
    assert "indicative" in r["feed_note"] and r["gates"]["opt42"]["live_ok"] is False
    assert r["variants"]["OPT-39"]["QQQ"]["n"] == 1 and r["variants"]["OPT-25"]["hold7"]["n"] == 1
    assert (sd / "options" / "report.json").exists()


def test_opt38_stats_edge_cases():
    assert osh.opt38_stats([])["n"] == 0 and osh.opt38_stats([])["E"] is None
    recs = [{"R": 0.1, "max_loss": 0}, {"R": float("nan")}, {"R": -0.5, "max_loss": 100, "width": 2,
                                                              "contracts": 1, "date": "2026-11-13",
                                                              "entry_date": "2026-10-16", "tags": {}}]
    s = osh.opt38_stats(recs)
    assert s["n"] == 2 and s["worst_R"] == -0.5 and s["max_drawdown_R"] == pytest.approx(0.5)
    assert osh.sqn([0.1]) is None and osh.sqn([0.1, 0.1]) is None
    r, assumed = osh.bil_r({"max_loss": 100, "width": 2, "contracts": 1, "date": "2026-11-13",
                            "entry_date": "2026-10-14", "tags": {"bil_rate": 0.0365}})
    assert r == pytest.approx(200 * 0.0365 * 30 / 365 / 100) and not assumed


def test_o_owned_empty_and_with_assigned_stock(sd):
    assert run.o_owned(sd) == {"symbols": set(), "stock": {}, "value": 0.0, "order_prefix": "OPT-"}
    led = OptionsBook(o_stock={"SPY": 100.0})
    led.save(sd)
    assert run.o_owned(sd)["stock"] == {"SPY": 100.0}


def test_run_with_only_the_interface_arguments(cfg, sd):
    e = run.run_options(cfg, sd, now=close_utc(DAY))
    assert e["snapshot"] is None and "shadow_entry" not in e
    assert (sd / "options" / "journal.jsonl").exists()
    out = run.prepare_options(cfg, sd, date=DAY, samples=1)
    assert out["candidate"] is None and out["samples"] == 1


def test_corrupt_shadow_file_is_set_aside(sd):
    p = osh.ShadowO.path(sd)
    p.parent.mkdir(parents=True)
    p.write_text("{not json")
    assert osh.ShadowO.load(sd).book.lots == {}
    assert p.with_suffix(".corrupt.json").exists()


def test_skip_predictions_resolve_after_20_sessions(sd):
    sh = osh.ShadowO(predictions=[{"id": "O-skip-2026-10-16", "date": "2026-10-16", "symbol": "SPY", "horizon": 20,
                                   "direction": "below", "threshold_pct": -4.0, "probability": 0.4,
                                   "base_close": 660.0, "base_rate": None, "outcome": None}])
    idx = pd.bdate_range("2026-10-16", periods=25)
    bars = {"SPY": pd.DataFrame({"close": [660.0] * 20 + [600.0] * 5}, index=idx)}
    done = osh.resolve_predictions(sh, bars, idx[-1])
    assert done and sh.predictions[0]["outcome"] == 1 and sh.predictions[0]["brier"] == pytest.approx(0.36)
    assert osh.resolve_predictions(sh, None, idx[-1]) == []


def open_paper_lot(sd, expiry="2026-11-20"):
    led = OptionsBook()
    cand = {"underlying": "SPY", "expiry": expiry, "type": "put", "spot": 660.0, "quoted_cost": 0.02,
            "mid_credit": 0.3, "short": {"symbol": occ_symbol("SPY", expiry, "put", 631), "strike": 631.0},
            "long": {"symbol": occ_symbol("SPY", expiry, "put", 629), "strike": 629.0}}
    led.open_spread(cand, {"contracts": 1, "credit_per_share": 0.3, "order_id": "OPT-x"}, "2026-10-19", shadow=False)
    return led


def test_opt15_alert_when_a_spread_is_open_at_dte_2(cfg, sd):
    led = open_paper_lot(sd)
    led.save(sd)
    e = run.run_options(cfg, sd, now=close_utc("2026-11-18"))
    assert e["alerts"]["paper"] and "DTE 2" in e["alerts"]["paper"][0]


def test_paper_ledger_marks_and_drawdown_halt_force_a_close(cfg, sd, gate_open):
    led = open_paper_lot(sd)
    led.peak_pnl = 5000.0  # far above: drawdown >= 2% of E
    led.save(sd)
    log_day(cfg, sd, "2026-10-19")
    pos = [{"symbol": "SPY261120P00631000", "qty": -1.0}, {"symbol": "SPY261120P00629000", "qty": 1.0}]
    b = FakeBroker(positions=pos, acct={"maintenance_margin": 200.0})
    e = run.run_options(enabled_cfg(cfg), sd, now=close_utc("2026-10-19"), regime_label="bull_calm", broker=b,
                        dry_run=False)
    assert e["paper_breakers"]["halt"] and OptionsBook.load(sd).halted
    assert OptionsBook.load(sd).marks[-1]["date"] == "2026-10-19"
    assert b.submitted == [] and e["exits_due"][0]["reason"] == "OPT-31 drawdown halt"
    log_day(cfg, sd, "2026-10-20", when="1545")
    e = run.run_options(enabled_cfg(cfg), sd, now=run_1545_utc("2026-10-20"), when="1545", regime_label="bull_calm",
                        broker=b, dry_run=False)
    assert len(b.submitted) == 1
    po = [x for x in e["paper_orders"] if x.get("reason")][0]
    assert po["reason"] == "OPT-31 drawdown halt" and po["ladder"]["basis"].startswith("natural")


def test_paper_marks_skip_when_a_leg_has_no_quote(cfg, sd):
    open_paper_lot(sd).save(sd)
    e = run.run_options(cfg, sd, now=close_utc("2026-10-19"))
    assert any("paper marks skipped" in n for n in e["notes"]) and OptionsBook.load(sd).marks == []


# --- review fixes: OPT-15 freeze, OPT-30 next session, OPT-26 clean-up, settle while disabled -----------------------


def queue_intent_on_day(cfg, sd, b):
    ecfg = enabled_cfg(cfg)
    log_day(cfg, sd, DAY)
    run.run_options(ecfg, sd, now=close_utc(DAY), regime_label="bull_calm", broker=b, dry_run=False)
    assert len(run._load_paper(sd)["intents"]) == 1
    return ecfg


def test_paper_spread_open_at_dte_2_freezes_paper_entries(cfg, sd, gate_open):
    """OPT-15: the entry candidate comes from the shadow book, but a PAPER spread open at DTE <= 2 still freezes."""
    b = FakeBroker(acct={"equity": 400_000.0, "cash": 360_000.0, "maintenance_margin": 200.0})
    ecfg = queue_intent_on_day(cfg, sd, b)
    led = open_paper_lot(sd, expiry="2026-10-20")  # DTE 1 at the 2026-10-19 order run
    led.save(sd)
    b._positions = [{"symbol": occ_symbol("SPY", "2026-10-20", "put", 631), "qty": -1.0},
                    {"symbol": occ_symbol("SPY", "2026-10-20", "put", 629), "qty": 1.0}]
    log_day(cfg, sd, "2026-10-19", when="1545")
    e = run.run_options(ecfg, sd, now=run_1545_utc("2026-10-19"), when="1545", regime_label="bull_calm",
                        broker=b, dry_run=False)
    assert [o["intent"] for o in b.submitted] == ["close"]  # the exit goes, the entry does not
    entry = [x for x in e["paper_orders"] if x.get("status") == "rejected"][0]
    assert any("OPT-15" in r for r in entry["reasons"])


def test_paper_spread_at_dte_2_stops_the_after_close_queue(cfg, sd, gate_open):
    led = open_paper_lot(sd, expiry="2026-10-16")  # DTE 0 at the 2026-10-16 close run
    led.save(sd)
    b = FakeBroker(positions=[{"symbol": occ_symbol("SPY", "2026-10-16", "put", 631), "qty": -1.0},
                              {"symbol": occ_symbol("SPY", "2026-10-16", "put", 629), "qty": 1.0}],
                   acct={"equity": 400_000.0, "cash": 360_000.0, "maintenance_margin": 200.0})
    log_day(cfg, sd, DAY, expiries=[DAY] + EXPS)
    e = run.run_options(enabled_cfg(cfg), sd, now=close_utc(DAY), regime_label="bull_calm", broker=b, dry_run=False)
    assert e["menu"]["candidate"] is True  # the shadow book would enter; the paper ledger's own freeze stops it
    assert run._load_paper(sd)["intents"] == [] and any("not queued" in n and "OPT-15" in n for n in e["notes"])


def test_paper_loss_blocks_the_next_sessions_entry(cfg, sd, gate_open):
    """OPT-30: a loss >= 0.5% of E on the paper ledger on day D means no paper entry at D+1 15:45, even though the
    15:45 run's own intraday change is small."""
    b = FakeBroker(acct={"equity": 400_000.0, "cash": 360_000.0, "maintenance_margin": 200.0})
    ecfg = queue_intent_on_day(cfg, sd, b)
    led = OptionsBook.load(sd)
    led.marks = [{"date": "2026-10-15", "o_pnl": 2500.0, "day_pnl": 0.0},
                 {"date": DAY, "o_pnl": 0.0, "day_pnl": -2500.0}]
    led.peak_pnl = 2500.0
    led.save(sd)
    log_day(cfg, sd, "2026-10-19", when="1545")
    e = run.run_options(ecfg, sd, now=run_1545_utc("2026-10-19"), when="1545", regime_label="bull_calm",
                        broker=b, dry_run=False)
    assert b.submitted == []
    assert any("OPT-30" in r for r in e["paper_orders"][0]["reasons"])
    assert run._prior_session_pnl(OptionsBook.load(sd), "2026-10-19") == -2500.0


def test_paper_loss_at_the_close_stops_queuing(cfg, sd, gate_open):
    led = open_paper_lot(sd, expiry="2026-12-18")
    led.marks = [{"date": "2026-10-15", "o_pnl": 2500.0, "day_pnl": 0.0}]
    led.peak_pnl = 2500.0
    led.save(sd)
    pos = [{"symbol": occ_symbol("SPY", "2026-12-18", "put", 631), "qty": -1.0},
           {"symbol": occ_symbol("SPY", "2026-12-18", "put", 629), "qty": 1.0}]
    b = FakeBroker(positions=pos, acct={"equity": 400_000.0, "cash": 360_000.0, "maintenance_margin": 200.0})
    log_day(cfg, sd, DAY)
    e = run.run_options(enabled_cfg(cfg), sd, now=close_utc(DAY), regime_label="bull_calm", broker=b, dry_run=False)
    assert e["paper_breakers"]["no_new_entries"] and run._load_paper(sd)["intents"] == []
    assert any("not queued" in n and "OPT-30" in n for n in e["notes"])


def filled(qty, price):
    def f(p):
        return {"client_order_id": p["client_order_id"], "status": "filled", "final": True, "filled_qty": qty,
                "filled_avg_price": price, "legs": []}
    return f


def test_assignment_is_booked_and_cleaned_up_stock_first(cfg, sd, gate_open):
    """OPT-26: assignment -> O's ledger owns the stock; at 15:45 the stock is sold first (marketable limit), and
    only once it is flat the orphan long put is sold to close; the lot then closes with the settlement."""
    ecfg = enabled_cfg(cfg)
    open_paper_lot(sd).save(sd)
    short, long = occ_symbol("SPY", "2026-11-20", "put", 631), occ_symbol("SPY", "2026-11-20", "put", 629)
    b = FakeBroker(positions=[{"symbol": long, "qty": 1.0}, {"symbol": "SPY", "qty": 100.0}],
                   acct={"equity": 400_000.0, "cash": 360_000.0, "maintenance_margin": 200.0})
    log_day(cfg, sd, DAY)
    e = run.run_options(ecfg, sd, now=close_utc(DAY), regime_label="bull_calm", broker=b, dry_run=False)
    led = OptionsBook.load(sd)
    assert e["assignments"][0]["contracts"] == 1 and led.o_stock == {"SPY": 100.0}
    assert led.open_lots()[0].status == "incident" and run.o_owned(sd)["stock"] == {"SPY": 100.0}
    assert [s_["action"] for s_ in e["cleanup_plan"]] == ["sell_stock", "wait_stock_flat"]
    assert b.submitted == [] and b.singles == [] and "shadow_entry" not in e
    # a rerun books nothing twice
    run.run_options(ecfg, sd, now=close_utc(DAY), regime_label="bull_calm", broker=b, dry_run=False)
    assert OptionsBook.load(sd).o_stock == {"SPY": 100.0}
    # 15:45: sell the stock first; no spread exit and no long-put sale yet
    log_day(cfg, sd, "2026-10-19", when="1545")
    run.run_options(ecfg, sd, now=run_1545_utc("2026-10-19"), when="1545", regime_label="bull_calm", broker=b,
                    dry_run=False)
    assert b.submitted == [] and len(b.singles) == 1
    sale = b.singles[0]
    assert sale["symbol"] == "SPY" and sale["qty"] == 100 and sale["side"] == "sell"
    assert sale["limit_price"] == pytest.approx(660.0 * 0.99) and sale["client_order_id"].startswith("OPT-")
    # the sale fills; the broker now holds only the long put
    b._fills = [filled(100.0, 655.0)]
    b._positions = [{"symbol": long, "qty": 1.0}]
    log_day(cfg, sd, "2026-10-19")
    e = run.run_options(ecfg, sd, now=close_utc("2026-10-19"), regime_label="bull_calm", broker=b, dry_run=False)
    assert OptionsBook.load(sd).o_stock == {} and [s_["action"] for s_ in e["cleanup_plan"]] == ["sell_to_close_long"]
    log_day(cfg, sd, "2026-10-20", when="1545")
    run.run_options(ecfg, sd, now=run_1545_utc("2026-10-20"), when="1545", regime_label="bull_calm", broker=b,
                    dry_run=False)
    orph = b.singles[1]
    assert orph["symbol"] == long and orph["position_intent"] == "sell_to_close" and orph["qty"] == 1
    assert orph["limit_price"] > 0
    b._fills = [filled(1.0, 0.5)]
    b._positions = []
    log_day(cfg, sd, "2026-10-20")
    run.run_options(ecfg, sd, now=close_utc("2026-10-20"), regime_label="bull_calm", broker=b, dry_run=False)
    led = OptionsBook.load(sd)
    assert led.open_lots() == [] and led.closed[-1]["reason"] == "OPT-26 assignment clean-up"
    # credit 0.30 x 100 + the stock sold 24 above the strike + the long put's 50, less the model fees
    assert led.closed[-1]["pnl"] == pytest.approx(30.0 + (655.0 - 631.0) * 100 + 50.0, abs=2.0)
    assert b.submitted == []  # never a 2-leg close for a spread whose short leg is gone


def test_exit_fill_is_not_mistaken_for_an_assignment(sd):
    led = open_paper_lot(sd)
    short, long = led.open_lots()[0].short_leg.symbol, led.open_lots()[0].long_leg.symbol
    # both legs gone (an exit filled) and rules-book stock: no assignment
    assert run.book_assignments([{"symbol": "SPY", "qty": 100.0}], led, {"SPY": 100.0}, DAY) == []
    assert run.book_assignments([{"symbol": "SPY", "qty": 100.0}], led, {}, DAY) == []
    # short gone, long there, but no unexplained stock: no assignment
    assert run.book_assignments([{"symbol": long, "qty": 1.0}], led, {}, DAY) == []
    assert led.o_stock == {}


def test_fills_are_booked_while_orders_are_disabled(cfg, sd, gate_open):
    """A paper order working when the owner turns O off (or a dry run) is still booked when it fills."""
    ecfg, b, _ = paper_flow(cfg, sd)
    pend = run._load_paper(sd)["pending"][0]
    short, long = pend["legs"]
    b._fills = [lambda p: {"client_order_id": p["client_order_id"], "status": "filled", "final": True,
                           "filled_qty": 2.0, "legs": [{"symbol": short, "filled_avg_price": 2.0},
                                                       {"symbol": long, "filled_avg_price": 1.7}]}]
    log_day(cfg, sd, "2026-10-19")
    e = run.run_options(cfg, sd, now=close_utc("2026-10-19"), regime_label="bull_calm", broker=b, dry_run=True)
    assert e["orders_allowed"] is False and e["paper_settled"] == 1
    assert OptionsBook.load(sd).open_lots()[0].contracts == 2 and run._load_paper(sd)["pending"] == []


def test_next_session_skips_exchange_holidays():
    assert run.next_session("2026-10-16") == "2026-10-19"
    assert run.next_session("2026-11-25") == "2026-11-27"  # Thanksgiving
    assert run.next_session("2026-12-24") == "2026-12-28"  # Christmas (Friday)
    assert run.next_session("2027-01-15") == "2027-01-19"  # MLK day


def test_opt13_1545_rows_see_the_cycle_the_shadow_entered(cfg, sd):
    prepared(cfg, sd)
    run_day(cfg, sd, DAY)
    log_day(cfg, sd, "2026-10-19", when="1545", leg_spread=0.6)  # wide quotes at 15:45
    run.run_options(cfg, sd, now=run_1545_utc("2026-10-19"), when="1545", **ACCT)
    sh = osh.ShadowO.load(sd)
    row = [r for r in sh.evaluations if r["when"] == "1545"][0]
    assert row["candidate"] is True
    assert osh.no_trade_rate(sh.evaluations, when="1545")["blocked_by_opt13"] == 0


def test_corrupt_shadow_shapes_are_set_aside(sd):
    p = osh.ShadowO.path(sd)
    p.parent.mkdir(parents=True)
    for bad in ('{"book": {"lots": [1]}}', '{"evaluations": 5}', '[1, 2]'):
        p.write_text(bad)
        assert osh.ShadowO.load(sd).evaluations == []
        assert p.with_suffix(".corrupt.json").exists() and not p.exists()


def test_credit_ratio_counts_sessions_not_runs():
    """OPT-41: 5 sessions with a close and a 15:45 row each are n = 5, and the gate stays closed."""
    ev = []
    for d in pd.bdate_range("2026-06-11", periods=5):
        for w in ("close", "1545"):
            ev.append({"date": d.date().isoformat(), "when": w, "underlying": "SPY", "in_window": True,
                       "expiry": "2026-07-17", "ratio": 1.0 if w == "close" else 3.0})
    r = osh.credit_ratio_check(ev, ["2026-07-17"])
    assert r["n"] == 5 and r["ok"] is False and r["median"] == 1.0


def test_sqn_follows_m2():
    assert osh.sqn([0.1, -0.1] * 14) is None  # n = 28 < 30
    xs = [0.2, -0.1, 0.05] * 50  # n = 150
    import statistics
    m, sd_ = statistics.mean(xs), statistics.stdev(xs)
    assert osh.sqn(xs) == pytest.approx(10 * m / sd_)


def test_slippage_is_reported_in_percent_of_equity():
    rec = {"R": 0.1, "max_loss": 100, "width": 2, "contracts": 1, "date": "2026-11-13", "entry_date": "2026-10-16",
           "tags": {}, "lot": {"events": [{"slippage_dollars": 40.0}]}}
    assert osh.opt38_stats([rec], equity=100_000)["slippage_pct_of_E"] == pytest.approx(0.04)


def test_opt41_items_are_checked_not_asserted(cfg, sd, monkeypatch):
    assert run.built_check()["ok"] and run.separation_check(sd)["ok"]
    monkeypatch.setattr(run, "BUILT_TESTS", ("test_missing_file.py",))
    assert not run.built_check()["ok"]
    from trader import engine
    monkeypatch.setattr(engine, "_own_prefixes", lambda book, date: ("OPT-",))
    assert not run.separation_check(sd)["ok"]
