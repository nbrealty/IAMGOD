"""Backtester (rulebook phase 7, M-12): next-open fills, costs, no look-ahead, determinism, overrides."""
import copy
import json

import numpy as np
import pandas as pd
import pytest

from conftest import make_bars
from trader import backtest as bt
from trader.config import Config, load_config

START, END = "2026-07-20", "2026-09-25"
WINDOW = 320


def small_cfg() -> Config:
    """The real config with a 6-name C universe, so each replay stays fast."""
    base = load_config()
    pb = copy.deepcopy(base.playbook)
    uni = ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "KO"]
    pb["sleeves"]["C"]["universe"] = uni
    pb["sleeves"]["C"]["sectors"] = {g: [s for s in m if s in uni] for g, m in pb["sleeves"]["C"]["sectors"].items()}
    return Config(playbook=pb, policy=copy.deepcopy(base.policy))


def synth_bars(cfg: Config, n: int = 420) -> dict:
    """Synthetic daily bars; SPY dips hard in the last weeks so sleeve B gets RSI(2) entries."""
    out = {}
    for i, sym in enumerate(cfg.data_symbols()):
        out[sym] = make_bars(n=n, seed=i + 1, drift=0.0006, vol=0.012)
        # opens that differ from the prior close, so a close fill and an open fill can be told apart
        df = out[sym]
        df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0]) * (1 + 0.002 * np.sin(np.arange(n)))
        df["high"] = np.maximum(df["high"], df["open"])
        df["low"] = np.minimum(df["low"], df["open"])
    for sym in ("SPY", "QQQ"):
        df = out[sym]
        for k in (-30, -29, -28, -12, -11):
            df.iloc[k:, :4] = df.iloc[k:, :4] * 0.985
    return out


@pytest.fixture(scope="module")
def cfg_small():
    return small_cfg()


@pytest.fixture(scope="module")
def data(cfg_small):
    return synth_bars(cfg_small)


@pytest.fixture(scope="module")
def result(cfg_small, data):
    return bt.run_backtest(cfg_small, data, START, END, window=WINDOW)


def test_replay_trades_and_reports(result):
    assert result.fills and result.orders
    assert len(result.equity) == len(pd.bdate_range(START, END))
    s = result.summary
    for k in ("cagr", "vol", "sharpe", "max_drawdown", "final_equity", "total_return"):
        assert k in s
    assert result.benchmarks["spy"] and result.benchmarks["sixty_forty"]
    assert set(result.sleeve_stats) >= {"B", "C"}
    assert result.exposure["A"] > 0.3
    assert result.reconcile_events == 0  # the simulator and the ledger never disagree
    json.dumps(result.to_dict())  # JSON-safe
    assert "CAGR" in result.headline()


def test_fills_are_at_the_next_open(result, data):
    for f in result.fills:
        df = data[f["symbol"]]
        after = df.index[df.index > pd.Timestamp(f["signal_date"])]
        assert f["date"] == after[0].date().isoformat()  # the first session after the signal
        assert f["fill"] == pytest.approx(float(df.loc[after[0], "open"]), abs=1e-5)
        assert f["signal_close"] == pytest.approx(float(df.loc[pd.Timestamp(f["signal_date"]), "close"]))


def test_costs_are_charged_once(cfg_small, result):
    bps = cfg_small.policy["turnover"]["cost_model_per_side_bps"]
    for f in result.fills:
        assert f["cost"] == pytest.approx(f["qty"] * f["fill"] * bps[f["asset_class"]] / 1e4, abs=1e-5)
    assert result.turnover["costs"] == pytest.approx(sum(f["cost"] for f in result.fills), abs=0.01)
    assert result.turnover["costs"] > 0


def test_higher_costs_lower_the_result(cfg_small, data, result):
    dear = bt.run_backtest(cfg_small, data, START, END, window=WINDOW,
                           overrides=["turnover.cost_model_per_side_bps.etf=50",
                                      "turnover.cost_model_per_side_bps.stock=60"])
    assert dear.turnover["costs"] > result.turnover["costs"] * 3
    assert dear.summary["final_equity"] < result.summary["final_equity"]


def test_deterministic(cfg_small, data, result):
    again = bt.run_backtest(cfg_small, data, START, END, window=WINDOW)
    assert again.to_dict() == result.to_dict()


def test_no_look_ahead(cfg_small, data, result):
    """Changing every bar after day X changes nothing decided on or before X."""
    cut = pd.Timestamp("2026-08-28")
    moved = {}
    rng = np.random.default_rng(7)
    for s, df in data.items():
        df = df.copy()
        later = df.index > cut
        df.loc[later, ["open", "high", "low", "close"]] *= rng.uniform(0.7, 1.3, (int(later.sum()), 1))
        moved[s] = df
    other = bt.run_backtest(cfg_small, moved, START, END, window=WINDOW)
    upto = lambda res: res.equity[res.equity.index <= cut]  # noqa: E731
    pd.testing.assert_series_equal(upto(result), upto(other))
    day = lambda rows: [r for r in rows if r["date"] <= cut.date().isoformat()]  # noqa: E731
    assert day(result.orders) == day(other.orders)  # orders decided on X use bars <= X only
    assert day(result.fills) == day(other.fills)
    assert other.equity.iloc[-1] != result.equity.iloc[-1]


def test_window_only_slices_history(cfg_small, data):
    """Each day sees at most `window` bars, all dated on or before it."""
    dates = pd.DatetimeIndex(data["SPY"].index[-3:])
    for d, view in bt._day_views(data, dates, 50):
        assert all(len(df) <= 50 and df.index.max() <= d for df in view.values())


# --- overrides --------------------------------------------------------------------------------------------


def test_overrides_reach_playbook_and_policy(cfg_small):
    new = bt.apply_overrides(cfg_small, ["sleeves.B.rsi_entry=5", "per_trade.stop_atr_multiple.B=2.25"])
    assert new.sleeves["B"]["rsi_entry"] == 5
    assert new.policy["per_trade"]["stop_atr_multiple"]["B"] == 2.25
    assert cfg_small.sleeves["B"]["rsi_entry"] == 10  # the original is untouched
    assert cfg_small.policy["per_trade"]["stop_atr_multiple"]["B"] == 3.0
    assert bt.params_version(new) != bt.params_version(cfg_small)
    assert bt.apply_overrides(cfg_small, {"policy.breakers.drawdown_halt": 0.15}).policy["breakers"][
        "drawdown_halt"] == 0.15


@pytest.mark.parametrize("item", [
    "per_trade.risk_pct_default=0.01",
    "per_trade.risk_pct_by_sleeve.C=0.02",
    "per_trade.stop_atr_multiple.B=3.75",
    "breakers.drawdown_halt=0.3",
    "breakers.daily_loss_pct=0.05",
    "portfolio.min_cash_buffer=0.0",
    "portfolio.max_equity_like=0.9",
    "turnover.cost_model_per_side_bps.stock=2",
    "turnover.max_orders_per_day=50",
    "account.long_only=false",
    "per_trade.no_averaging_down=false",
    "sleeves.D.enabled=true",
    "sleeves.C.max=0.3",
])
def test_loosening_risk_is_refused(cfg_small, item):
    with pytest.raises(bt.OverrideError):
        bt.apply_overrides(cfg_small, [item])
    assert bt.apply_overrides(cfg_small, [item], allow_risk_changes=True) is not cfg_small


@pytest.mark.parametrize("item", [
    "per_trade.risk_pct_default=0.0025", "breakers.drawdown_halt=0.15", "portfolio.min_cash_buffer=0.10",
    "turnover.cost_model_per_side_bps.etf=8", "per_trade.time_stop_days.B=7", "turnover.rebalance_band=0.1",
    "sleeves.C.pivot_lookback=40",
])
def test_tightening_or_neutral_is_allowed(cfg_small, item):
    bt.apply_overrides(cfg_small, [item])


def test_unknown_or_malformed_overrides_are_refused(cfg_small):
    for item in (["sleeves.B.rsi_entyr=5"], ["nope=1"], ["sleeves.B.rsi_entry"]):
        with pytest.raises(bt.OverrideError):
            bt.apply_overrides(cfg_small, item)


def test_run_backtest_refuses_loosening(cfg_small, data):
    with pytest.raises(bt.OverrideError):
        bt.run_backtest(cfg_small, data, START, END, overrides=["per_trade.risk_pct_default=0.02"])


# --- CLI and cache ------------------------------------------------------------------------------------------


class FakeData:
    def __init__(self, bars):
        self.bars, self.calls, self.notes, self.feed_used = bars, 0, [], "sip"

    def history(self, symbols, start, end=None):
        self.calls += 1
        return {s: self.bars[s] for s in symbols if s in self.bars}


def test_history_is_cached(cfg_small, data, tmp_path):
    fake = FakeData(data)
    a = bt.load_history(cfg_small, "2025-01-01", END, cache_dir=tmp_path, data=fake, say=lambda *_: None)
    b = bt.load_history(cfg_small, "2025-01-01", END, cache_dir=tmp_path, data=fake, say=lambda *_: None)
    assert fake.calls == 1 and set(a) == set(b)
    assert list(tmp_path.glob("bars_*.pkl"))


def test_cli_runs_and_writes_json(cfg_small, data, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bt, "load_config", lambda: cfg_small)
    monkeypatch.setattr(bt, "STATE_DIR", tmp_path)
    out = tmp_path / "res.json"
    rc = bt.main(["--start", "2026-09-01", "--end", END, "--window", "300", "--out", str(out)], data=FakeData(data))
    assert rc == 0
    got = json.loads(out.read_text())
    assert got["start"] == "2026-09-01" and got["summary"]["final_equity"] > 0
    assert "CAGR" in capsys.readouterr().out
    assert (tmp_path / "cache").is_dir()


def test_cli_refuses_loosening(cfg_small, monkeypatch, capsys):
    monkeypatch.setattr(bt, "load_config", lambda: cfg_small)
    assert bt.main(["--set", "breakers.drawdown_halt=0.5"], data=FakeData({})) == 2
    assert "Refused" in capsys.readouterr().out
