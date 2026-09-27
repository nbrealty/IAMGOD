"""Stock splits in held names (finding #0). The bars are split-adjusted (Adjustment.ALL), so a split shows only as
restated history: the book must rescale its lots, never book the change as a trade or hit a pre-split stop."""
import pandas as pd
import pytest

from conftest import make_bars
from trader import ledger, risk
from trader.broker import SimBroker
from trader.engine import run_book
from trader.models import Lot, Target
from trader.state import BookState

CASH = 100_000.0


@pytest.mark.parametrize("ratio,want", [(4.0, 4.0), (4.03, 4.0), (0.1, 0.1), (1.5, 1.5), (2 / 3, 2 / 3),
                                        (0.99, None), (1.1, None), (4.2, None), (None, None), (-2, None)])
def test_split_ratio(ratio, want):
    got = ledger.split_ratio(ratio)
    assert (got is None and want is None) or got == pytest.approx(want)


def _split(bars, sym, r):
    out = dict(bars)
    df = bars[sym].copy()
    for c in ("open", "high", "low", "close"):
        df[c] = df[c] / r
    df["volume"] = df["volume"] * r
    out[sym] = df
    return out


@pytest.fixture(scope="module")
def world():
    from trader.config import load_config

    cfg = load_config()
    bars = {s: make_bars(n=900, seed=i + 21, drift=0.001, crypto="/" in s)
            for i, s in enumerate(cfg.data_symbols())}
    return cfg, bars


def _run(cfg, bars, d, sd, state=None):
    state = state or BookState.load("rules", sd)
    b = {s: df[df.index <= d] for s, df in bars.items()}
    broker = SimBroker(state.sim, risk.last_valid_closes(b), ledger.cost_model(cfg, state), cfg.asset_class,
                       bars=b, fill_mode="next_open", cost_in_price=False)
    return run_book("rules", cfg, b, broker, None, d, sd, state=state)


def _seed(bars, sd):
    idx = bars["SPY"].index
    nv = float(bars["NVDA"].loc[idx[-4], "close"])
    st = BookState(book="rules")
    st.lots = {"C": {"NVDA": Lot(10.0, nv * 0.97, idx[-12].date().isoformat(), nv * 0.9, nv * 0.9)}}
    st.sim = {"cash": CASH - 10 * nv * 0.97, "positions": {"NVDA": 10.0}}
    st.save(sd)
    return idx


def test_split_in_held_name_rescales_lots_end_to_end(world, tmp_path):
    """Modelled on the s12 probe: a 4-for-1 split in a held C lot. Before the fix the pre-split stop forced an
    exit and the sleeve booked about -1,100 of fake loss. Compared with the same days without a split, every
    share count is 4x, every price 1/4, and the P&L is the same."""
    cfg, bars = world
    ctrl, spl = tmp_path / "ctrl", tmp_path / "split"
    idx = _seed(bars, ctrl)
    _seed(bars, spl)
    day0, day1, day2 = idx[-3], idx[-2], idx[-1]
    adj = _split(bars, "NVDA", 4)
    _run(cfg, bars, day0, ctrl)  # both books see the same pre-split day and keep a mark
    _run(cfg, bars, day0, spl)
    out_c = [_run(cfg, bars, d, ctrl) for d in (day1, day2)]
    out_s = [_run(cfg, adj, d, spl) for d in (day1, day2)]

    for oc, os_ in zip(out_c, out_s):
        assert not any("NVDA" in x and "exit enforced" in x for x in os_["risk_log"])
        nv_c = {(o["side"], round(o["qty"] * 4, 6)) for o in oc["orders"] if o["symbol"] == "NVDA"}
        nv_s = {(o["side"], round(o["qty"], 6)) for o in os_["orders"] if o["symbol"] == "NVDA"}
        assert nv_s == nv_c
    sc, ss = BookState.load("rules", ctrl), BookState.load("rules", spl)
    assert [t for t in ss.closed_trades if t["symbol"] == "NVDA"] == [] or \
        [t["pnl"] for t in ss.closed_trades] == pytest.approx([t["pnl"] for t in sc.closed_trades], abs=0.05)
    lc, ls = sc.lots["C"]["NVDA"], ss.lots["C"]["NVDA"]
    assert ls.qty == pytest.approx(4 * lc.qty)
    assert ls.entry_price == pytest.approx(lc.entry_price / 4)
    assert ls.stop == pytest.approx(lc.stop / 4)
    assert ls.risk_per_share == pytest.approx(lc.risk_per_share / 4)
    assert ss.sim["positions"]["NVDA"] == pytest.approx(4 * sc.sim["positions"]["NVDA"])
    assert ss.sleeve_pnl["C"]["cum"] == pytest.approx(sc.sleeve_pnl["C"]["cum"], abs=0.05)
    assert "C" not in ss.sleeve_blocked
    assert any(e["kind"] == "split" for e in ls.events)


def test_broker_split_without_mark_is_not_a_trade():
    """Reconcile backstop (no mark yet, the s12 case): broker 4x the shares, close near entry / 4."""
    st = BookState(book="rules")
    st.lots = {"C": {"NVDA": Lot(10.0, 150.8, "2026-09-10", 140.0, 140.0)}}
    log = []
    ledger.reconcile(st.lots, {"NVDA": 40.0}, log, state=st, prices={"NVDA": 38.87}, date="2026-09-24")
    lot = st.lots["C"]["NVDA"]
    assert lot.qty == pytest.approx(40) and lot.entry_price == pytest.approx(37.7) and lot.stop == pytest.approx(35)
    assert st.closed_trades == [] and lot.realized_pnl == 0
    assert any("treated as a split" in x for x in log)


def test_broker_doubling_at_same_price_is_still_an_add():
    st = BookState(book="rules")
    st.lots = {"C": {"NVDA": Lot(10.0, 100.0, "2026-09-10", 90.0, 90.0)}}
    ledger.reconcile(st.lots, {"NVDA": 20.0}, [], state=st, prices={"NVDA": 101.0}, date="2026-09-24")
    lot = st.lots["C"]["NVDA"]
    assert lot.qty == pytest.approx(20) and lot.entry_price == pytest.approx(100.5)


def test_live_broker_not_split_yet_is_skipped():
    st = BookState(book="rules")
    st.lots = {"C": {"NVDA": Lot(40.0, 25.0, "2026-09-10", 22.5, 22.5)}}
    log = []
    lag = ledger.split_lagging(st, {"NVDA": 4.0}, {"NVDA": 10.0}, log)
    assert lag == {"NVDA"} and "split" in log[0]


def test_stop_far_above_close_on_calm_day_is_not_enforced(cfg):
    """Backstop in risk: a stop more than 2x the close after an ordinary day is a price-scale mismatch."""
    from trader.risk import Breakers, RiskEngine

    df = make_bars(n=300, seed=3)
    bars = {"NVDA": df, "SPY": make_bars(n=300, seed=4)}
    close = float(df["close"].iloc[-1])
    lots = {"C": {"NVDA": Lot(10.0, close * 4, "2026-09-01", close * 3.6, close * 3.6)}}
    b = Breakers(0.0, False, False, 1.0, 0.0, 0.0, [])
    res = RiskEngine(cfg).apply([Target("NVDA", "C", 20, None, "add")], lots, {"NVDA": 10.0}, bars, CASH, b)
    assert not [o for o in res.orders if o.symbol == "NVDA"]
    assert any("stop not enforced" in x for x in res.log)
    # a real crash through the stop (a big one-day move) is still enforced
    crash = df.copy()
    crash.iloc[-1, crash.columns.get_loc("close")] = float(df["close"].iloc[-2]) * 0.3
    res = RiskEngine(cfg).apply([], {"C": {"NVDA": Lot(10.0, 100.0, "2026-09-01", 90.0, 90.0)}},
                                {"NVDA": 10.0}, {"NVDA": crash, "SPY": bars["SPY"]}, CASH, b)
    assert any(o.symbol == "NVDA" and o.side == "sell" for o in res.orders)
