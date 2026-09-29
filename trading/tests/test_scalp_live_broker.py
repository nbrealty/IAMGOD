"""Live paper minute trader, brokers (lab/scalp/live/broker.py): the AlpacaBroker paper lock and order mapping with
fake alpaca clients, and the SimBroker's fill semantics. All offline: no network, no keys, no real state dir."""
import json
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest
from alpaca.common.exceptions import APIError
from alpaca.trading.enums import OrderClass, OrderSide, OrderStatus, OrderType, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import LimitOrderRequest

from lab.scalp.live import broker as B
from lab.scalp.live import config as C
from lab.scalp.live import orders as O
from lab.scalp.live.broker import AlpacaBroker, SimBroker
from lab.scalp.live.model import (Bar, BrokerReject, BrokerUnavailable, Candidate, Feed, Kind, Mode, PaperLockError,
                                  Quote, as_ny)

D = date(2026, 10, 1)
REG = C.load_registry()
NOISE = REG.get("NOISE_MOM_SPY", "SPY")
ENV = {"ALPACA_SCALP_KEY": "k-scalp", "ALPACA_SCALP_SECRET": "s-scalp"}


def ts(hms):
    return as_ny(f"{D.isoformat()} {hms}")


class NoRules(dict):
    """An environment that fails the test if anything reads an ALPACA_RULES_* value."""

    def __getitem__(self, k):
        if str(k).startswith("ALPACA_RULES_"):
            raise AssertionError(f"{k} was read")
        return super().__getitem__(k)

    def get(self, k, default=None):
        if str(k).startswith("ALPACA_RULES_"):
            raise AssertionError(f"{k} was read")
        return super().get(k, default)


def fake_order(**kw):
    base = dict(id="o-1", client_order_id="SCALP-X", symbol="SPY", side=OrderSide.BUY, qty="1", filled_qty="0",
                filled_avg_price=None, status=OrderStatus.NEW, type=OrderType.LIMIT, order_type=OrderType.LIMIT,
                limit_price="650.33", stop_price=None, order_class=OrderClass.SIMPLE, legs=None,
                submitted_at=pd.Timestamp("2026-10-01T14:00:01Z"), filled_at=None,
                updated_at=pd.Timestamp("2026-10-01T14:00:01Z"))
    base.update(kw)
    return SimpleNamespace(**base)


def api_error(status, message):
    http = SimpleNamespace(response=SimpleNamespace(status_code=status), request=None)
    return APIError(json.dumps({"code": status * 100, "message": message}), http)


class FakeClient:
    def __init__(self, base="https://paper-api.alpaca.markets", number="PA3XYZ9GWRL", positions=(), opens=()):
        self._base_url = base
        self._retry = 3
        self.number = number
        self.calls: list[tuple] = []
        self.pos = list(positions)
        self.opens = list(opens)
        self.submit_error = None
        self.by_cid = {}

    def get_account(self):
        self.calls.append(("get_account",))
        return SimpleNamespace(account_number=self.number, status=SimpleNamespace(value="ACTIVE"), equity="10000",
                               last_equity="9990", cash="10000", buying_power="40000",
                               non_marginable_buying_power="10000", trading_blocked=False, shorting_enabled=True)

    def get_all_positions(self):
        self.calls.append(("positions",))
        return self.pos

    def get_orders(self, filter=None):
        self.calls.append(("get_orders", filter))
        return self.opens if filter is not None and filter.status == QueryOrderStatus.OPEN else []

    def submit_order(self, req):
        self.calls.append(("submit", req))
        if self.submit_error is not None:
            raise self.submit_error
        return fake_order(client_order_id=req.client_order_id, symbol=req.symbol, side=req.side, qty=str(req.qty),
                          limit_price=str(req.limit_price), order_class=req.order_class)

    def get_order_by_client_id(self, cid):
        self.calls.append(("by_cid", cid))
        if cid in self.by_cid:
            return self.by_cid[cid]
        raise api_error(404, "order not found")

    def cancel_order_by_id(self, oid):
        self.calls.append(("cancel", oid))


def make(tmp_path, client=None, env=None, **kw):
    made = []

    def factory(k, s):
        made.append((k, s))
        return client if client is not None else FakeClient()
    kw.setdefault("lock_path", tmp_path / "broker.lock")
    kw.setdefault("pin_path", tmp_path / "account.pin")
    kw.setdefault("account_last4", "GWRL")
    b = AlpacaBroker(env=NoRules(ENV if env is None else env), client_factory=factory, **kw)
    return b, made


def spec_entry(q=None):
    q = q or Quote("SPY", 650.00, 650.01, 100, 100, ts("10:00:01"), ts("10:00:01"), Feed.IEX)
    spec, reasons, _ = O.entry_bracket(Candidate("NOISE_MOM_SPY", 1, "SPY", "enter", 1, ts("09:59")), NOISE, q,
                                       100_000.0, D, 0)
    assert spec is not None, reasons
    return spec


def spec_exit(qty=1, attempt=0, bid=650.0):
    q = Quote("SPY", bid, bid + 0.01, 100, 100, ts("10:00:01"), ts("10:00:01"), Feed.IEX)
    return O.exit_limit("SPY", qty, q, None, 0.0005, Kind.EXIT, setup_id="NOISE_MOM_SPY", version=1, session_date=D,
                        bar_start=ts("09:59"), leg="X", attempt=attempt)


# ============================================================================================ MT-G36 paper lock
def test_mt_g36_paper_lock_refuses_the_rules_keys_before_any_network_call(tmp_path):
    with pytest.raises(PaperLockError):
        make(tmp_path, keys=("ALPACA_RULES_KEY", "ALPACA_RULES_SECRET"))
    with pytest.raises(PaperLockError):
        make(tmp_path, keys=("ALPACA_SCALP_KEY", "ALPACA_RULES_SECRET"))


def test_mt_g36_missing_keys_refused_before_any_client_is_built(tmp_path):
    for env in ({}, {"ALPACA_SCALP_KEY": "k"}, {"ALPACA_SCALP_KEY": "", "ALPACA_SCALP_SECRET": "s"}):
        made = []
        with pytest.raises(PaperLockError, match="not set"):
            AlpacaBroker(env=NoRules(env), client_factory=lambda k, s: made.append(1),
                         lock_path=tmp_path / "l", pin_path=None, account_last4="GWRL")
        assert made == []


@pytest.mark.parametrize("name", ["APCA_API_BASE_URL", "ALPACA_BASE_URL", "ALPACA_SCALP_BASE_URL"])
def test_mt_g36_a_live_url_override_is_refused_before_any_network_call(tmp_path, name):
    made = []
    env = {**ENV, name: "https://api.alpaca.markets"}
    with pytest.raises(PaperLockError, match="non-paper"):
        AlpacaBroker(env=NoRules(env), client_factory=lambda k, s: made.append(1), lock_path=tmp_path / "l",
                     pin_path=None, account_last4="GWRL")
    assert made == []
    b, _ = make(tmp_path, env={**ENV, name: "https://paper-api.alpaca.markets/v2"})   # the paper host is fine
    assert b.base_url == B.PAPER_URL
    with pytest.raises(PaperLockError):
        make(tmp_path, url_override="https://api.alpaca.markets")


def test_mt_g36_a_client_pointing_at_the_live_host_is_refused(tmp_path):
    client = FakeClient(base="https://api.alpaca.markets")
    with pytest.raises(PaperLockError, match="not the paper host"):
        make(tmp_path, client=client)
    assert client.calls == []


def test_the_default_client_is_the_real_alpaca_paper_client(tmp_path):
    b = AlpacaBroker(env=NoRules(ENV), lock_path=tmp_path / "l", pin_path=None, account_last4="GWRL")
    assert B._norm_url(b.client._base_url) == B.PAPER_URL and b.client._retry == 0


# ============================================================================================ MT-G26 right account
def test_mt_g26_account_must_be_the_scalp_paper_account(tmp_path):
    b, _ = make(tmp_path)
    a = b.account()
    assert a.account_number.endswith("GWRL") and a.last_equity == 9990 and a.base_url == B.PAPER_URL
    for number in ("PA3XYZ9ABCD", "XX3XYZ9GWRL"):
        b, _ = make(tmp_path, client=FakeClient(number=number))
        with pytest.raises(PaperLockError):
            b.account()
    (tmp_path / "account.pin").write_text("PA000000GWRL\n")
    b, _ = make(tmp_path)
    with pytest.raises(PaperLockError, match="pinned"):
        b.account()


def test_orders_are_refused_until_the_account_check_passed(tmp_path):
    client = FakeClient(number="PA3XYZ9ABCD")
    b, _ = make(tmp_path, client=client)
    with pytest.raises(PaperLockError):
        b.submit(spec_entry())
    assert not [c for c in client.calls if c[0] == "submit"]


def test_dry_alpaca_broker_is_read_only(tmp_path):
    b, _ = make(tmp_path, mode=Mode.DRY)
    b.account()
    with pytest.raises(PaperLockError):
        b.submit(spec_entry())
    with pytest.raises(PaperLockError):
        b.cancel("o-1")
    with pytest.raises(PaperLockError):
        make(tmp_path, mode=Mode.REPLAY)


# ============================================================================================ MT-G21 request mapping
def test_mt_g21_entry_maps_to_a_limit_bracket_with_a_stop_limit(tmp_path):
    client = FakeClient()
    b, _ = make(tmp_path, client=client)
    s = spec_entry()
    b.submit(s)
    req = [c[1] for c in client.calls if c[0] == "submit"][0]
    assert type(req) is LimitOrderRequest and req.type == OrderType.LIMIT and req.order_class == OrderClass.BRACKET
    assert req.limit_price == s.limit_price and req.qty == 1 and req.side == OrderSide.BUY
    assert req.time_in_force == TimeInForce.DAY and req.extended_hours is False
    assert req.take_profit.limit_price == s.take_profit
    assert req.stop_loss.stop_price == s.stop_price and req.stop_loss.limit_price == s.stop_limit_price
    assert req.client_order_id == s.client_order_id and s.client_order_id.startswith("SCALP-")
    assert (tmp_path / "broker.lock").exists()


def test_mt_g21_exit_maps_to_a_simple_limit_sell(tmp_path):
    client = FakeClient(positions=[SimpleNamespace(symbol="SPY", qty="1", avg_entry_price="650", side="long")])
    b, _ = make(tmp_path, client=client)
    b.submit(spec_exit())
    req = [c[1] for c in client.calls if c[0] == "submit"][0]
    assert type(req) is LimitOrderRequest and req.order_class == OrderClass.SIMPLE and req.side == OrderSide.SELL
    assert req.take_profit is None and req.stop_loss is None and req.limit_price > 0


def test_mt_g15_a_sell_larger_than_the_free_long_position_is_refused(tmp_path):
    client = FakeClient(positions=[SimpleNamespace(symbol="SPY", qty="1", avg_entry_price="650", side="long")])
    b, _ = make(tmp_path, client=client)
    with pytest.raises(BrokerReject) as e:
        b.submit(spec_exit(qty=2))
    assert e.value.code == "SELL_EXCEEDS_POSITION"
    # the bracket legs still promise the one share: a plain sell of it would oversell once a leg fills
    leg = fake_order(id="leg-1", client_order_id="4b1e-uuid", side=OrderSide.SELL, type=OrderType.STOP_LIMIT,
                     order_class=OrderClass.BRACKET, status=OrderStatus.HELD)
    client.opens = [leg]
    with pytest.raises(BrokerReject):
        b.submit(spec_exit(qty=1))
    client.opens, client.pos = [], []
    with pytest.raises(BrokerReject):                   # no position at all: a sell would be a short
        b.submit(spec_exit(qty=1))
    assert not [c for c in client.calls if c[0] == "submit"]


def test_local_validation_refuses_a_non_scalp_id_before_sending(tmp_path):
    from dataclasses import replace
    client = FakeClient()
    b, _ = make(tmp_path, client=client)
    with pytest.raises(BrokerReject, match="SCALP"):
        b.submit(replace(spec_entry(), client_order_id="manual-1"))
    with pytest.raises(BrokerReject):
        b.submit(replace(spec_entry(), limit_price=0.0))
    assert not [c for c in client.calls if c[0] == "submit"]


# ============================================================================================ MT-G25 errors
def test_mt_g25_duplicate_client_id_is_looked_up_and_returned(tmp_path):
    client = FakeClient()
    b, _ = make(tmp_path, client=client)
    s = spec_entry()
    client.submit_error = api_error(422, "client_order_id must be unique")
    client.by_cid[s.client_order_id] = fake_order(id="orig", client_order_id=s.client_order_id,
                                                  status=OrderStatus.FILLED, filled_qty="1",
                                                  filled_avg_price="650.01")
    v = b.submit(s)
    assert v.id == "orig" and v.status == "filled" and v.filled_avg_price == 650.01


def test_mt_g25_4xx_is_a_reject_and_timeouts_are_unavailable(tmp_path):
    client = FakeClient()
    b, _ = make(tmp_path, client=client)
    client.submit_error = api_error(403, "account is restricted")
    with pytest.raises(BrokerReject) as e:
        b.submit(spec_entry())
    assert e.value.status == 403
    for err in (TimeoutError("read timed out"), api_error(504, "gateway"), api_error(429, "slow down")):
        client.submit_error = err
        with pytest.raises(BrokerUnavailable):
            b.submit(spec_entry())
    assert b.get_by_client_id("SCALP-nothing") is None


def test_orders_since_asks_for_all_statuses_nested_500_at_a_time(tmp_path):
    client = FakeClient()
    b, _ = make(tmp_path, client=client)
    b.orders_since(ts("00:00"))
    req = [c[1] for c in client.calls if c[0] == "get_orders"][0]
    assert req.status == QueryOrderStatus.ALL and req.nested is True and req.limit == 500 and req.after is not None
    b.open_orders()
    req = [c[1] for c in client.calls if c[0] == "get_orders"][-1]
    assert req.status == QueryOrderStatus.OPEN and req.nested is False      # flat: legs as their own items


def test_order_view_maps_alpaca_objects_to_plain_views():
    leg = fake_order(id="l1", client_order_id="uuid", side=OrderSide.SELL, type=OrderType.STOP_LIMIT,
                     stop_price="646.5", limit_price="645.0", status=OrderStatus.HELD, order_class=OrderClass.BRACKET)
    v = B.order_view(fake_order(legs=[leg], order_class=OrderClass.BRACKET, status=OrderStatus.PARTIALLY_FILLED,
                                filled_qty="1", filled_avg_price="650.01", qty="2"))
    assert v.status == "partially_filled" and v.side == "buy" and v.order_class == "bracket"
    assert v.qty == 2 and v.filled_qty == 1 and v.filled_avg_price == 650.01
    assert v.legs[0].order_type == "stop_limit" and v.legs[0].status == "held" and v.legs[0].stop_price == 646.5
    assert v.submitted_at.tz is not None and str(v.submitted_at.tz) == "America/New_York"
    p = B.position_view(SimpleNamespace(symbol="SPY", qty="3", avg_entry_price="650", side=SimpleNamespace(value="short")))
    assert p.qty == -3


def test_the_broker_lock_is_reentrant(tmp_path):
    b, _ = make(tmp_path)
    with b.lock():
        with b.lock():
            pass
    assert (tmp_path / "broker.lock").exists()


def test_broker_module_never_names_the_rules_keys():
    src = (C.LIVE_DIR / "broker.py").read_text()
    assert "ALPACA_RULES" not in src and "anthropic" not in src


# ============================================================================================ SimBroker
@pytest.fixture
def sim():
    clk = {"t": ts("10:00:01")}
    s = SimBroker(lambda: clk["t"])
    s.clk = clk
    s.set_quote("SPY", 650.00, 650.01)
    return s


def test_sim_buy_limit_fills_at_the_ask_and_legs_wake_after_a_full_fill(sim):
    s = spec_entry()
    v = sim.submit(s)
    assert v.status == "filled" and v.filled_avg_price == 650.01
    tp = [x for x in v.legs if x.order_type == "limit"][0]
    sl = [x for x in v.legs if x.order_type == "stop_limit"][0]
    assert tp.status == "new" and sl.status == "held"
    assert sl.stop_price == s.stop_price and sl.limit_price == s.stop_limit_price
    assert not tp.client_order_id.startswith("SCALP-")                  # like Alpaca: legs get their own ids
    assert {o.id for o in sim.open_orders()} == {tp.id, sl.id}          # flat list of open orders


def test_sim_legs_stay_held_while_the_parent_is_only_partly_filled(sim):
    sim.partial_fill_qty = 1
    from dataclasses import replace
    v = sim.submit(replace(spec_entry(), qty=2))
    assert v.status == "partially_filled" and all(x.status == "held" for x in v.legs)
    sim.cancel(v.id)
    sim.set_quote("SPY", 600.0, 600.01)                                  # far below the stop: nothing fires
    v = sim.get_order(v.id)
    assert v.status == "canceled" and all(x.status == "canceled" for x in v.legs) and v.filled_qty == 1
    assert sim.positions()[0].qty == 1                                   # unprotected: the engine must sell it


def test_sim_stop_triggers_at_the_bid_and_fills_only_inside_the_stop_limit(sim):
    s = spec_entry()
    v = sim.submit(s)
    sim.set_quote("SPY", s.stop_limit_price - 0.50, s.stop_limit_price - 0.49)   # gap through the limit
    sl = [x for x in sim.get_order(v.id).legs if x.order_type == "stop_limit"][0]
    assert sl.status == "held" and sim.positions()[0].qty == 1
    sim.set_quote("SPY", s.stop_limit_price + 0.01, s.stop_limit_price + 0.02)   # back inside: it fills
    legs = sim.get_order(v.id).legs
    assert [x.status for x in legs if x.order_type == "stop_limit"] == ["filled"]
    assert [x.status for x in legs if x.order_type == "limit"] == ["canceled"]    # one-cancels-other
    assert not sim.positions()


def test_sim_take_profit_fills_at_the_bid(sim):
    s = spec_entry()
    v = sim.submit(s)
    sim.set_quote("SPY", s.take_profit + 0.05, s.take_profit + 0.06)
    legs = {x.order_type: x for x in sim.get_order(v.id).legs}
    assert legs["limit"].status == "filled" and legs["limit"].filled_avg_price == pytest.approx(s.take_profit + 0.05)
    assert legs["stop_limit"].status == "canceled" and not sim.positions()


def test_sim_never_lets_a_sell_open_a_short(sim):
    with pytest.raises(BrokerReject) as e:
        sim.submit(spec_exit())
    assert e.value.status == 403
    sim.submit(spec_entry())
    with pytest.raises(BrokerReject):                   # the legs still promise the share
        sim.submit(spec_exit())
    assert sim.positions()[0].qty == 1


def test_sim_reject_unavailable_and_duplicate_ids(sim):
    sim.reject_next = 403
    with pytest.raises(BrokerReject):
        sim.submit(spec_entry())
    assert sim.submits == []
    sim.unavailable_next = "before"
    with pytest.raises(BrokerUnavailable):
        sim.submit(spec_entry())
    assert sim.get_by_client_id(spec_entry().client_order_id) is None
    sim.unavailable_next = "after"
    with pytest.raises(BrokerUnavailable):
        sim.submit(spec_entry())
    found = sim.get_by_client_id(spec_entry().client_order_id)
    assert found is not None and found.status == "filled"
    again = sim.submit(spec_entry())                    # same client id: the original comes back, no new order
    assert again.id == found.id and len(sim.submits) == 1


def test_sim_a_cancel_request_is_not_a_cancel(sim):
    sim.cancel_delay_s = 3
    sim.fill_delay_s = 100
    v = sim.submit(spec_entry())
    sim.cancel(v.id)
    assert sim.get_order(v.id).status == "pending_cancel"
    sim.clk["t"] = ts("10:00:03")
    assert sim.get_order(v.id).status == "pending_cancel"
    sim.clk["t"] = ts("10:00:04")
    assert sim.get_order(v.id).status == "canceled" and not sim.open_orders()


def test_sim_update_is_idempotent(sim):
    s = spec_entry()
    sim.submit(s)
    q = {"SPY": Quote("SPY", 650.2, 650.21, 100, 100, ts("10:00:02"), ts("10:00:02"), Feed.SIM)}
    sim.update(ts("10:00:02"), q)
    before = (sim.positions(), len(sim.fills))
    sim.update(ts("10:00:02"), q)
    assert (sim.positions(), len(sim.fills)) == before


def test_sim_bar_mode_checks_legs_on_later_bars_with_the_stop_first():
    clk = {"t": ts("10:00:01")}
    sim = SimBroker(lambda: clk["t"], fill_mode="bar")
    sim.set_quote("SPY", 650.00, 650.01)
    s = spec_entry()
    v = sim.submit(s)
    assert v.status == "filled"
    fill_bar = Bar("SPY", ts("10:00"), 650.0, 700.0, 600.0, 650.0, 1000, Feed.SIP)   # same minute: ignored
    clk["t"] = ts("10:01:01")
    sim.update(clk["t"], None, {"SPY": [fill_bar]})
    assert sim.positions()[0].qty == 1
    both = Bar("SPY", ts("10:01"), 650.0, s.take_profit + 1, s.stop_price - 0.01, 650.0, 1000, Feed.SIP)
    clk["t"] = ts("10:02:01")
    sim.update(clk["t"], None, {"SPY": [both]})
    legs = {x.order_type: x for x in sim.get_order(v.id).legs}
    assert legs["stop_limit"].status == "filled" and legs["stop_limit"].filled_avg_price == s.stop_price
    assert legs["limit"].status == "canceled" and not sim.positions()


def test_sim_positions_and_foreign_orders_for_reconcile_tests(sim):
    sim.inject_position("SPY", 10, 650.0)
    oid = sim.add_foreign_order("SPY", "buy", 1, 600.0)
    assert sim.positions()[0].qty == 10 and [o.id for o in sim.open_orders()] == [oid]
    a = sim.account()
    assert a.account_number.startswith("PA") and a.equity == pytest.approx(100_000 + 10 * 650.0)
