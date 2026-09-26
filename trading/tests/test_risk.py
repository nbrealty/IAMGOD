from trader.models import Lot, Target
from trader.risk import RiskEngine, breaker_status


def _breakers(cfg, equity=10000, peak=10000, day=0.0, week=0.0, halted=False, kill=False):
    return breaker_status(cfg, equity, peak, day, week, halted, kill)


def test_kill_switch_allows_exits_only(cfg, bars):
    price = bars["AAPL"]["close"].iloc[-1]
    lots = {"C": {"AAPL": Lot(2, price, "2026-09-01", price * 0.9, price * 0.9)}}
    proposed = [Target("AAPL", "C", 0, None, "exit"), Target("MSFT", "C", 3, bars["MSFT"]["close"].iloc[-1] * 0.95)]
    res = RiskEngine(cfg).apply(proposed, lots, {"AAPL": 2}, bars, 10000, _breakers(cfg, kill=True))
    sides = {(o.symbol, o.side) for o in res.orders}
    assert ("AAPL", "sell") in sides
    assert not any(o.side == "buy" for o in res.orders)


def test_allowlist_and_no_shorts(cfg, bars):
    proposed = [Target("GME", "C", 5, 1.0), Target("AAPL", "C", -5, None)]
    res = RiskEngine(cfg).apply(proposed, {}, {}, bars, 10000, _breakers(cfg))
    assert res.orders == []
    assert any("allowlist" in line for line in res.log)


def test_per_trade_risk_clip(cfg, bars):
    price = bars["MSFT"]["close"].iloc[-1]
    stop = price * 0.95
    res = RiskEngine(cfg).apply([Target("MSFT", "C", 1000, stop)], {}, {}, bars, 10000, _breakers(cfg))
    [t] = [t for t in res.targets if t.symbol == "MSFT"]
    assert (price - t.stop) * t.qty <= 0.005 * 10000 + 1e-6


def test_drawdown_halves_risk_and_blocks(cfg, bars):
    price = bars["MSFT"]["close"].iloc[-1]
    stop = price * 0.95
    res = RiskEngine(cfg).apply([Target("MSFT", "C", 1000, stop)], {}, {}, bars, 8900, _breakers(cfg, 8900, 10000))
    [t] = [t for t in res.targets if t.symbol == "MSFT"]
    assert (price - stop) * t.qty <= 0.0025 * 8900 + 1e-6
    res = RiskEngine(cfg).apply([Target("MSFT", "C", 1000, stop)], {}, {}, bars, 8400, _breakers(cfg, 8400, 10000))
    assert res.orders == []


def test_stop_enforced_even_if_decider_holds(cfg, bars):
    price = bars["AAPL"]["close"].iloc[-1]
    lots = {"C": {"AAPL": Lot(2, price * 1.2, "2026-09-01", price * 1.05, price * 1.05)}}
    res = RiskEngine(cfg).apply([Target("AAPL", "C", 2, price * 1.05, "hold")], lots, {"AAPL": 2}, bars, 10000,
                                _breakers(cfg))
    assert [(o.symbol, o.side) for o in res.orders] == [("AAPL", "sell")]


def test_stop_never_widens(cfg, bars):
    price = bars["AAPL"]["close"].iloc[-1]
    lots = {"C": {"AAPL": Lot(1, price * 0.9, "2026-09-01", price * 0.93, price * 0.85)}}
    res = RiskEngine(cfg).apply([Target("AAPL", "C", 1, price * 0.5, "hold")], lots, {"AAPL": 1}, bars, 10000,
                                _breakers(cfg))
    [t] = res.targets
    assert t.stop == price * 0.93


def test_etf_notional_cap_and_cash_buffer(cfg, bars):
    price = bars["SPY"]["close"].iloc[-1]
    res = RiskEngine(cfg).apply([Target("SPY", "A", 10_000 / price, None)], {}, {}, bars, 10000, _breakers(cfg))
    [t] = res.targets
    assert t.qty * price <= 0.30 * 10000 + 1e-6


def test_untracked_positions_left_alone(cfg, bars):
    res = RiskEngine(cfg).apply([], {}, {"TSLA": 3}, bars, 10000, _breakers(cfg))
    assert res.orders == []
    assert any("left untouched" in line for line in res.log)


def test_daily_loss_blocks_entries(cfg, bars):
    b = _breakers(cfg, day=-120)  # 1R = $50, so -2.4R
    assert b.no_new_entries
