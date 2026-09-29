"""Scalp lab backtest mechanics (lab/scalp/backtest.py, report.py): fills, exits, costs, baselines. Offline."""
import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from lab.scalp import backtest as bt
from lab.scalp import report as rp
from lab.scalp import signals as sg
from lab.scalp.synth import make_day, random_day, random_frame


def _enter(m, side=1, **kw):
    return sg.Intent(m=m, action="enter", side=side, **kw)


def test_fill_is_the_next_bar_open():
    day = random_day(1)
    t = bt.execute(day, [_enter(4)])
    assert t[0].entry_m == 5 and t[0].entry == day.o[5]
    gap = make_day(np.full(6, 100.0), opens=[100, 100, 100, 100, 100, 100.7], minutes=[0, 1, 2, 3, 4, 9])
    t = bt.execute(gap, [_enter(4)])
    assert t[0].entry_m == 9 and t[0].entry == 100.7   # missing minutes: the next bar that exists


def test_stop_is_assumed_before_target_in_the_same_bar():
    n = 10
    c = np.full(n, 100.0)
    h, lo = c + 0.1, c - 0.1
    h[5], lo[5] = 101.5, 98.5          # this bar touches both the stop (99) and the target (101)
    day = make_day(c, highs=h, lows=lo)
    t = bt.execute(day, [_enter(0, stop=99.0, target=101.0)])[0]
    assert (t.reason, t.exit, t.exit_m) == ("stop", 99.0, 6)
    s = bt.execute(day, [_enter(0, side=-1, stop=101.0, target=99.0)])[0]
    assert (s.reason, s.exit) == ("stop", 101.0)


def test_open_beyond_the_stop_fills_at_the_open_and_target_fills_at_the_target():
    c = np.full(10, 100.0)
    o = c.copy()
    o[4] = 98.0
    day = make_day(c, opens=o, highs=np.maximum(o, c) + 0.05, lows=np.minimum(o, c) - 0.05)
    t = bt.execute(day, [_enter(0, stop=99.0, target=102.0)])[0]
    assert (t.reason, t.exit) == ("stop", 98.0)
    h = c + 0.05
    h[3] = 100.6
    day = make_day(c, highs=h, lows=c - 0.05)
    t = bt.execute(day, [_enter(0, stop=99.0, target_r=0.5)])[0]   # R = 1.0 -> target 100.5
    assert (t.reason, t.exit, t.risk) == ("target", 100.5, 1.0)


def test_entry_already_past_its_stop_is_skipped():
    day = make_day(np.full(10, 100.0))
    assert bt.execute(day, [_enter(0, stop=100.5, target_r=10)]) == []
    assert bt.execute(day, [_enter(0, side=-1, target=100.2, stop_dist=1.0)]) == []   # target already passed


@pytest.mark.parametrize("close_min", [390, 210])
def test_flat_by_five_minutes_before_the_close(close_min):
    day = random_day(2, n=close_min, close_min=close_min)
    for st in sg.SETUPS.values():
        if st.exit_mode != "open":
            continue
        trades = bt.execute(day, st.fn(day, sg.Ctx(prev_close=100.0, prev_high=100.1, prev_low=99.9,
                                                   sigma=np.full(391, 0.0005), daily_vol=0.01)), st.exit_mode)
        assert all(t.exit_m <= close_min - 5 for t in trades), st.id
    trades = bt.execute(day, sg.vwap_trend(day, sg.Ctx()))
    last = trades[-1]
    assert last.reason == "time" and last.exit_m == close_min - 5 and last.exit == day.o[close_min - 5]


def test_close_mode_exits_at_the_last_close():
    day = random_day(4)
    t = bt.execute(day, [_enter(359)], exit_mode="close")[0]
    assert t.reason == "close" and t.exit == day.c[-1] and t.exit_m == 390


def test_max_hold_exits_at_the_open_30_minutes_after_the_fill():
    day = make_day(np.full(100, 100.0))
    t = bt.execute(day, [_enter(10, stop_dist=5.0, max_hold=30)])[0]
    assert (t.entry_m, t.exit_m, t.reason) == (11, 41, "max_hold")


def test_one_position_at_a_time_and_every_fill_follows_an_intent():
    ctx = sg.Ctx(prev_close=99.0, prev_high=100.1, prev_low=99.5, sigma=np.full(391, 0.001), daily_vol=0.01,
                 ema=(100.0, 99.9))
    for st in sg.SETUPS.values():
        for seed in range(4):
            day = random_day(seed, bps=5.0)
            intents = st.fn(day, ctx)
            trades = bt.execute(day, intents, st.exit_mode)
            for a, b in zip(trades, trades[1:]):
                assert a.exit_m <= b.entry_m, st.id
            enter_bars = {int(np.searchsorted(day.m, it.m, side="right")) for it in intents if it.action == "enter"}
            assert all(int(np.searchsorted(day.m, t.entry_m)) in enter_bars for t in trades), st.id


def test_cost_math():
    assert bt.net_bps(10.0, 0.5) == 9.0
    assert bt.usd_per_1000(9.0) == pytest.approx(0.9)
    sc = {name: cost for name, _, cost in bt.scenarios(bt.COSTS)}
    assert sc["gross"] == 0 and (sc["low"], sc["realistic"], sc["pessimistic"]) == (0.5, 1.5, 4.0)   # spec defaults
    assert sc["opt_bach"] == (2.0, 0.01)
    # options: the larger of a fixed half-spread and a % of premium, in bps of premium per side
    assert bt.option_cost_bps(1.00, 2.0, 0.01) == pytest.approx(200.0)      # 2% > $0.01 on a $1 premium
    assert bt.option_cost_bps(0.25, 2.0, 0.01) == pytest.approx(400.0)      # $0.01 is 4% of a $0.25 premium
    trades = pd.DataFrame([
        {"kind": "setup", "setup": "ORB5_QQQ", "symbol": "QQQ", "date": "2026-01-02", "year": 2026, "entry_m": 5,
         "hold_min": 10, "gross_bps": 10.0, "r_mult": 0.5, "pub_mult": 2.0, "opt_delta_bps": 100.0,
         "opt_bach_bps": 50.0, "opt_premium": 1.0},
        {"kind": "setup", "setup": "ORB5_QQQ", "symbol": "QQQ", "date": "2026-01-05", "year": 2026, "entry_m": 5,
         "hold_min": 20, "gross_bps": -4.0, "r_mult": -1.0, "pub_mult": 1.0, "opt_delta_bps": -100.0,
         "opt_bach_bps": -150.0, "opt_premium": 0.25},
    ])
    m = bt.metrics(trades, "2026-01-02", boot=200)
    r = m[(m["split"] == "all") & (m["scenario"] == "low")].iloc[0]           # 0.5 bps per side
    assert r["trades"] == 2 and r["expectancy_bps"] == pytest.approx(2.0)    # (9 + -5) / 2
    assert r["usd_per_trade"] == pytest.approx(0.2) and r["total_usd"] == pytest.approx(0.4)
    assert r["win_rate"] == 0.5 and r["profit_factor"] == pytest.approx(9 / 5)
    assert r["max_dd_usd"] == pytest.approx(0.5) and r["avg_hold_min"] == 15
    assert r["pub_sizing_pct"] == pytest.approx((2 * 9 - 5) / 100)
    r = m[(m["split"] == "all") & (m["scenario"] == "realistic")].iloc[0]     # 1.5 bps per side
    assert r["expectancy_bps"] == pytest.approx((7 + -7) / 2)
    o = m[(m["split"] == "all") & (m["scenario"] == "opt_bach")].iloc[0]
    assert o["expectancy_bps"] == pytest.approx(((50 - 400) + (-150 - 800)) / 2)   # 2% vs $0.01 on $0.25
    assert set(m["split"]) == {"all", "IS", "OOS", "Y2026"}


def test_option_proxy_sign_and_time_decay():
    d, b, p = bt.option_proxy(1, 100.0, 100.0, 0, 30, 390, 0.01)
    assert d == 0.0 and b < 0                       # no move: the Bachelier proxy loses to time decay
    d, b, p = bt.option_proxy(-1, 100.0, 99.0, 0, 30, 390, 0.01)
    assert d > 0 and b > 0                          # a short signal is a long put
    assert np.isnan(bt.option_proxy(1, 100.0, 101.0, 0, 30, 390, None)[1])


def test_option_proxy_prices_with_marked_up_vol_and_a_floor():
    _, _, p = bt.option_proxy(1, 100.0, 100.0, 0, 30, 390, 0.01)
    assert p == pytest.approx(100.0 * 0.012 * np.sqrt(1.0) * bt.PHI0)       # 1.2 x realised vol
    _, _, p_low = bt.option_proxy(1, 100.0, 100.0, 0, 30, 390, 0.0001)
    assert p_low == pytest.approx(100.0 * bt.IV_FLOOR * bt.PHI0)            # 10%/yr floor
    _, late, _ = bt.option_proxy(1, 700.0, 700.0, 360, 385, 390, 0.005)
    assert late < -5000                             # a late 0DTE option loses most of its premium with no move


def _frames():
    days = [d.date() for d in pd.bdate_range("2026-06-01", "2026-07-31")]
    cal = pd.DataFrame({"date": days,
                        "open": [pd.Timestamp(d).tz_localize("America/New_York") + pd.Timedelta(hours=9.5)
                                 for d in days],
                        "close": [pd.Timestamp(d).tz_localize("America/New_York") + pd.Timedelta(hours=16)
                                  for d in days]})
    return {"SPY": random_frame(10, days), "QQQ": random_frame(20, days, p0=300.0)}, cal, days


def test_baselines_are_seeded_and_match_the_setup():
    bars, cal, days = _frames()
    setups = [sg.SETUPS["ORB5_QQQ"], sg.SETUPS["VWAP_2SD_FADE_1M"]]
    a = bt.run(bars, cal, days[20], days[-1], setups, seed=7)
    b = bt.run(bars, cal, days[20], days[-1], setups, seed=7)
    c = bt.run(bars, cal, days[20], days[-1], setups, seed=8)
    pd.testing.assert_frame_equal(a, b)
    ra, rc = a[a["kind"] == "random"], c[c["kind"] == "random"]
    assert not ra[["entry_m"]].reset_index(drop=True).equals(rc[["entry_m"]].reset_index(drop=True))
    key = ["setup", "symbol", "date"]
    s = a[a["kind"] == "setup"]
    k = a[a["kind"] == "random"]
    assert (k.groupby(key).size() == s.groupby(key).size()).all()
    assert set(k["side"]) == {-1, 1}  # weak on its own; the look-ahead guard is test_random_baseline_does_not_borrow_...
    coin = a[a["kind"] == "coin"]
    assert (coin.groupby(key).size().reindex(s.groupby(key).size().index, fill_value=0)
            <= s.groupby(key).size()).all()                   # a flipped position can block a later entry
    setup_entries = set(zip(s["setup"], s["symbol"], s["date"], s["entry_m"]))
    coin_all = set(zip(coin["setup"], coin["symbol"], coin["date"], coin["entry_m"]))
    assert coin_all <= setup_entries                          # coin trades only at the setup's own entries


def test_end_to_end_run_metrics_and_report(tmp_path):
    bars, cal, days = _frames()
    start, end = days[20], days[-1]
    trades = bt.run(bars, cal, start, end, seed=0)
    assert set(trades["kind"]) == {"setup", "random", "coin"}
    assert (trades["exit_m"] <= 390).all() and trades["date"].min() >= start.isoformat()
    ctxs = bt.contexts(bt.to_days(bars["SPY"], cal), cal)
    assert ctxs[0].prev_close is None and ctxs[1].prev_close is not None
    assert ctxs[13].sigma is None and ctxs[14].sigma is not None and ctxs[15].daily_vol is not None
    mid = bt.split_date([d.isoformat() for d in days[20:]])
    m = bt.metrics(trades, mid, boot=100)
    meta = {"symbols": ["SPY", "QQQ"], "start": str(start), "end": str(end), "split_mid": mid, "seed": 0,
            "costs": bt.COSTS, "boot": 100}
    rp.save_trades(trades, meta, tmp_path)
    t2, meta2 = rp.load_trades(tmp_path)
    assert len(t2) == len(trades) and meta2["split_mid"] == mid
    paths = rp.write(m, meta, tmp_path)
    js = json.loads(paths["json"].read_text())
    verdicts = {v["verdict"] for v in js["verdicts"]}
    assert js["metrics"] and verdicts <= {"undecidable (--boot too small)", "too few days"}   # boot=100 < 561
    assert js["meta"]["alpha"] == pytest.approx(0.05 / (len(sg.SETUPS) * 2))
    md = paths["md"].read_text()
    assert "Out-of-sample" in md and "ORB5_QQQ" in md
    assert {"IS", "OOS", "all"} <= set(pd.read_csv(paths["csv"])["split"])


def test_split_date_is_the_middle_session():
    assert bt.split_date(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]) == "2026-01-02"
    assert bt.split_date([date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]) == "2026-01-02"


# ------------------------------------------------------------------------------------ review regressions
def test_coin_flip_mirrors_stop_and_target_and_follows_its_own_exits():
    c = np.r_[np.full(5, 100.0), np.linspace(100.0, 101.5, 20), np.full(365, 101.5)]
    day = make_day(c, wick=0.0)
    it = [_enter(0, stop=99.0, target=102.0)]
    orig = bt.execute(day, it)[0]
    assert (orig.side, orig.reason) == (1, "time") and orig.exit == pytest.approx(101.5)
    flip = bt.execute(day, it, flip=lambda _: True)[0]
    assert flip.side == -1 and flip.stop == pytest.approx(101.0) and flip.target == pytest.approx(98.0)
    assert flip.reason == "stop" and flip.exit == pytest.approx(101.0)   # not the sign-flipped +1.5 time exit
    same = bt.execute(day, it, flip=lambda _: False)[0]
    assert (same.side, same.exit, same.reason) == (orig.side, orig.exit, orig.reason)


def test_session_in_progress_is_skipped_not_closed_at_a_fake_eod():
    bars, cal, days = _frames()
    today = pd.Timestamp(days[-1]).tz_localize("America/New_York")
    cut = {s: df[df.index < today + pd.Timedelta(hours=10, minutes=44)] for s, df in bars.items()}
    d_last = bt.to_days(cut["SPY"], cal)[-1]
    assert d_last.date == days[-1] and not d_last.complete and not d_last.half_day
    trades = bt.run(cut, cal, days[20], days[-1], seed=0)
    assert days[-1].isoformat() not in set(trades["date"]) and not (trades["reason"] == "eod").any()
    assert days[-2].isoformat() in set(trades["date"])


def test_no_trades_still_writes_a_report(tmp_path, capsys):
    from lab.scalp import __main__ as cli
    m = bt.metrics(pd.DataFrame(columns=bt.ROW_COLS), "2026-01-01")
    assert m.empty and "split" in m.columns
    paths = rp.write(m, {"symbols": ["SPY"], "boot": 2000}, tmp_path)
    assert "_no trades_" in paths["md"].read_text() and json.loads(paths["json"].read_text())["verdicts"] == []
    cli._print_table(m)
    assert "no trades" in capsys.readouterr().out


def _metric_rows(setup, sym, lo_real, p_real, lo_pess):
    base = {"setup": setup, "symbol": sym, "primary": True, "split": "OOS", "trades": 50, "days": 40}
    return [{**base, "scenario": "realistic", "ci_lo_bps": lo_real, "p_vs_random": p_real},
            {**base, "scenario": "pessimistic", "ci_lo_bps": lo_pess, "p_vs_random": p_real}]


def test_verdict_bar_is_fixed_by_the_preregistered_family_and_boot_size():
    one = pd.DataFrame(_metric_rows("GAP_FADE_SPY", "QQQ", 1.0, 0.01, 0.5))
    assert rp.alpha_for(one) == pytest.approx(0.05 / (len(sg.SETUPS) * 2))   # not 0.05 for a one-pair run
    assert rp.verdicts(one, boot=2000)["verdict"].iloc[0] == "no edge shown"   # p 0.01 is above the bar
    good = pd.DataFrame(_metric_rows("GAP_FADE_SPY", "QQQ", 1.0, 0.0005, 0.5))
    assert rp.verdicts(good, boot=2000)["verdict"].iloc[0] == "candidate"
    assert rp.verdicts(good, boot=500)["verdict"].iloc[0] == "undecidable (--boot too small)"
    assert "WARNING" in rp.summary_md(good, {"boot": 500}) and "WARNING" not in rp.summary_md(good, {"boot": 2000})
    weak = pd.DataFrame(_metric_rows("GAP_FADE_SPY", "QQQ", 1.0, 0.0005, -0.5))
    v = rp.verdicts(weak, boot=2000).iloc[0]
    assert v["verdict"] == "candidate (fails at pessimistic cost)" and not v["pessimistic_ok"]
    wide = pd.DataFrame(_metric_rows("GAP_FADE_SPY", "AAPL", 1.0, 0.0005, 0.5))
    assert rp.alpha_for(wide) == pytest.approx(0.05 / (len(sg.SETUPS) * 3))


def test_summary_labels_the_no_decay_option_proxy_and_leads_with_bachelier(tmp_path):
    bars, cal, days = _frames()
    trades = bt.run(bars, cal, days[20], days[-1], [sg.SETUPS["LAST30_MOM_SPY"]], seed=0)
    m = bt.metrics(trades, bt.split_date(trades["date"]), boot=100)
    assert "opt_delta" not in set(m["scenario"]) and {"opt_bach", "opt_delta_no_decay"} <= set(m["scenario"])
    md = rp.summary_md(m, {"boot": 100, "costs": bt.COSTS})
    assert "IGNORES DECAY" in md and md.index("Bachelier") < md.index("IGNORES DECAY")
    assert "indicative" in md


def test_official_close_is_used_for_close_exits_and_yesterdays_close():
    bars, cal, days = _frames()
    closes = {d: 555.0 + k for k, d in enumerate(days)}
    ds = bt.to_days(bars["SPY"], cal, closes)
    assert ds[3].auction_close == closes[days[3]]
    ctx = bt.contexts(ds, cal)
    assert ctx[4].prev_close_auction == closes[days[3]] and ctx[4].prev_close == ds[3].c[-1]
    t = bt.execute(ds[4], [_enter(359)], exit_mode="close")[0]
    assert (t.exit, t.exit_m, t.reason) == (closes[days[4]], 390, "close")
    no_auction = bt.execute(bt.to_days(bars["SPY"], cal)[4], [_enter(359)], exit_mode="close")[0]
    assert no_auction.exit == ds[4].c[-1]


def test_random_baseline_does_not_borrow_the_setups_side_from_the_future():
    # The price runs up for 200 minutes, then goes flat. A momentum setup that goes long at minute 200 learned
    # its side from that run-up; a baseline copying that side to earlier random minutes would 'earn' the run-up.
    c = np.r_[np.linspace(100.0, 110.0, 200), np.full(190, 110.0)]
    day = make_day(c, wick=0.0)
    late_long = [sg.Trade(side=1, entry_m=200, entry=110.0, exit_m=300, exit=110.0, reason="time")]
    gross, sides = [], []
    for seed in range(400):
        for s, em, ep, xm, xp in bt.random_baseline(day, late_long, "open", np.random.default_rng(seed)):
            gross.append(s * (xp / ep - 1.0) * 1e4)
            sides.append(s)
    assert 0.4 < np.mean(np.array(sides) > 0) < 0.6
    assert abs(np.mean(gross)) < 25.0      # copying the long side gives about +225 bps on this path
