"""Scalp lab setups (lab/scalp/signals.py): no look-ahead, and each setup fires on a day built for it."""
from dataclasses import replace

import numpy as np
import pytest

from lab.scalp import signals as sg
from lab.scalp.synth import flat_day, make_day, random_day


def _ctx(p0=100.0, **kw):
    base = dict(prev_close=p0 * 0.99, prev_high=p0 * 1.001, prev_low=p0 * 0.995, sigma=np.full(391, 0.001),
                daily_vol=0.01, ema=(p0, p0 * 0.999))
    base.update(kw)
    return sg.Ctx(**base)


def _perturb_after(day, k, seed):
    """Replace every bar after index k with an unrelated path (prices and volumes)."""
    other = random_day(seed, n=day.n, p0=float(day.c[k]) * 1.01, bps=20.0)
    cut = lambda a, b: np.r_[a[:k + 1], b[k + 1:]]  # noqa: E731
    return replace(day, o=cut(day.o, other.o), h=cut(day.h, other.h), l=cut(day.l, other.l),
                   c=cut(day.c, other.c), v=cut(day.v, other.v * 7))


@pytest.mark.parametrize("setup_id", sorted(sg.SETUPS))
def test_no_look_ahead(setup_id):
    """Intents decided at or before bar k do not change when later bars change, or when the day is cut at k."""
    fn = sg.SETUPS[setup_id].fn
    fired = 0
    for seed in range(8):
        day, ctx = random_day(seed, bps=5.0), _ctx()
        full = fn(day, ctx)
        fired += len(full)
        for k in (0, 3, 4, 5, 20, 29, 30, 44, 61, 200, 329, 359, 360, 384):
            upto = [it for it in full if it.m <= day.m[k]]
            assert [it for it in fn(_perturb_after(day, k, seed + 50), ctx) if it.m <= day.m[k]] == upto
            assert fn(day.upto(k), ctx) == upto
    assert fired > 0, f"{setup_id} never fired on random days, so the look-ahead check proved nothing"


def test_intents_are_decided_at_bar_closes_inside_the_session():
    for st in sg.SETUPS.values():
        for seed in range(3):
            day = random_day(seed, bps=5.0)
            for it in st.fn(day, _ctx()):
                assert it.m in set(day.m.tolist()) and it.action in ("enter", "exit")


# --------------------------------------------------------------------------------------- hand-built days
def _up_first_5():
    return make_day([100.1, 100.2, 100.3, 100.4, 100.5] + [100.5] * 385)


def test_orb5_fires_long_on_an_up_first_candle_and_not_on_a_doji():
    it = sg.orb5(_up_first_5(), sg.Ctx())
    assert len(it) == 1 and it[0].m == 4 and it[0].side == 1 and it[0].target_r == 10.0
    assert it[0].stop == pytest.approx(100.09)   # low of the first 5-minute candle
    assert sg.orb5(flat_day(), sg.Ctx()) == []


def test_noise_mom_fires_above_the_band_and_not_inside_it():
    closes = np.r_[np.linspace(100.03, 101.0, 30), np.full(360, 101.0)]
    ctx = sg.Ctx(prev_close=100.0, sigma=np.full(391, 0.001), daily_vol=0.01)
    it = sg.noise_mom(make_day(closes, opens=np.r_[100.0, closes[:-1]]), ctx)
    assert it[0].m == 29 and it[0].action == "enter" and it[0].side == 1
    assert it[0].size == pytest.approx(2.0)   # min(4, 2% / 1% daily vol)
    assert sg.noise_mom(flat_day(), ctx) == []


def test_vwap_trend_is_always_in_and_flips_only_on_a_cross():
    closes = np.linspace(100, 101, 390)
    rising = make_day(closes, opens=np.r_[99.9, closes[:-1]])
    it = sg.vwap_trend(rising, sg.Ctx())
    assert it[0].m == 0 and it[0].side == 1 and all(i.action == "enter" for i in it) and len(it) == 1
    flat = sg.vwap_trend(flat_day(), sg.Ctx())   # close == VWAP -> 'else SHORT' by the rule; then no flips
    assert len(flat) == 1 and flat[0].side == -1


def test_last30_variants():
    closes = np.r_[np.linspace(100.1, 101, 30), np.full(360, 101.0)]
    day, ctx = make_day(closes), sg.Ctx(prev_close=100.0)
    for fn in (sg.last30_mom, sg.last30_rod, sg.last30_mom_close):
        it = fn(day, ctx)
        assert len(it) == 1 and it[0].m == 359 and it[0].side == 1
    assert sg.last30_eta(day, ctx) == []          # 15:00 -> 15:30 was flat, so the two signals do not agree
    flat, fctx = flat_day(), sg.Ctx(prev_close=100.0)
    assert sg.last30_eta(flat, fctx) == []
    it = sg.last30_mom(flat, fctx)                 # Gao eq. 4: r1 <= 0 is a short, so it is always in
    assert len(it) == 1 and it[0].side == -1


@pytest.mark.parametrize("fn,minutes", [(sg.orb30, 30), (sg.orb15, 15)])
def test_orb_range_breakout(fn, minutes):
    closes = np.r_[np.tile([99.9, 100.1], minutes // 2 + 1)[:minutes], np.full(40 - minutes, 100.0),
                   np.full(350, 101.0)]
    it = fn(make_day(closes), sg.Ctx())
    assert len(it) == 1 and it[0].m == 40 and it[0].side == 1
    assert it[0].stop == pytest.approx(99.89) and it[0].target_dist == pytest.approx(100.11 - 99.89)
    assert fn(flat_day(), sg.Ctx()) == []


def test_ema_pullback_fires_on_a_dip_to_ema9_in_an_uptrend():
    closes = np.r_[np.full(25, 100.0), [99.95, 99.92, 99.98, 100.05, 100.10], np.full(360, 100.10)]
    it = sg.ema_pullback(make_day(closes, wick=0.0), sg.Ctx(ema=(100.0, 99.0)))
    assert it and it[0].m == 29 and it[0].side == 1 and it[0].target_r == 2.0
    assert sg.ema_pullback(flat_day(), sg.Ctx(ema=(100.0, 100.0))) == []
    assert sg.ema_pullback(flat_day(), sg.Ctx()) == []


def test_pdh_break_fires_once_and_not_inside_yesterdays_range():
    closes = np.r_[np.full(15, 100.0), np.full(375, 101.5)]
    ctx = sg.Ctx(prev_close=100.0, prev_high=101.0, prev_low=99.0)
    it = sg.pdh_pdl(make_day(closes), ctx)
    assert len(it) == 1 and it[0].m == 19 and it[0].side == 1 and it[0].stop == pytest.approx(99.99)
    assert sg.pdh_pdl(flat_day(), ctx) == []
    gap_up = make_day(np.full(390, 101.5))        # opened above PDH: a gap day, no long from this setup
    assert [i for i in sg.pdh_pdl(gap_up, ctx) if i.side == 1] == []


def test_vwap_fade_buys_a_stretched_drop():
    closes = np.r_[np.tile([99.9, 100.1], 20), [99.7, 99.5, 99.3], np.full(347, 99.3)]
    it = sg.vwap_fade(make_day(closes), sg.Ctx())
    assert it and it[0].action == "enter" and it[0].side == 1 and it[0].max_hold == 30 and it[0].m >= 40
    assert sg.vwap_fade(flat_day(), sg.Ctx()) == []


def test_gap_fade_and_gap_go():
    day, ctx = make_day(np.full(390, 101.0)), sg.Ctx(prev_close=100.0)
    f = sg.gap_fade(day, ctx)
    assert len(f) == 1 and f[0].m == 4 and f[0].side == -1 and f[0].target == 100.0
    assert f[0].stop_dist == pytest.approx(1.0)
    g = sg.gap_go(day, ctx)
    assert len(g) == 1 and g[0].side == 1 and g[0].stop == 100.0 and g[0].target_dist == pytest.approx(1.0)
    assert sg.gap_fade(flat_day(), ctx) == [] and sg.gap_go(flat_day(), ctx) == []
    small = make_day(np.full(390, 100.4))         # a 0.4% gap is below the 0.5% trigger
    assert sg.gap_fade(small, ctx) == []


def test_every_setup_is_quiet_on_a_flat_day_except_the_always_in_rules():
    always_in = {"VWAP_TREND_QQQ", "LAST30_MOM_SPY", "LAST30_ROD_SPY", "LAST30_MOM_SPY_CLOSE"}
    ctx = sg.Ctx(prev_close=100.0, prev_high=101.0, prev_low=99.0, sigma=np.full(391, 0.001), daily_vol=0.01,
                 ema=(100.0, 100.0))
    for sid, st in sg.SETUPS.items():
        it = st.fn(flat_day(), ctx)
        assert (len(it) == 1) if sid in always_in else (it == []), sid


# ------------------------------------------------------------------------------------------- indicators
def test_vwap_and_rsi_are_running_values():
    day = random_day(3)
    vw, sd = sg.vwap_sd(day)
    x = (day.h + day.l + day.c) / 3
    k = 100
    assert vw[k] == pytest.approx(np.sum(day.v[:k + 1] * x[:k + 1]) / np.sum(day.v[:k + 1]))
    assert sd[k] == pytest.approx(np.sqrt(np.sum(day.v[:k + 1] * (x[:k + 1] - vw[k]) ** 2) / np.sum(day.v[:k + 1])))
    r = sg.rsi(np.array([10.0, 9.0, 8.0, 7.0, 8.0]), 2)
    assert np.isnan(r[:2]).all() and r[2] == 0.0 and r[3] == 0.0 and r[4] == pytest.approx(50.0)  # Wilder: gain avg (0+1)/2, loss avg (1+0)/2


def test_five_minute_buckets_close_on_their_last_minute_or_the_next_bar():
    day = make_day(np.arange(1.0, 13.0), minutes=[0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 14])
    bk = sg.buckets5(day)
    assert bk.start.tolist() == [0, 5, 10]
    assert bk.c.tolist() == [5.0, 9.0, 12.0]
    assert bk.close_at == ((), (), (), (), (0,), (), (), (), (), (1,), (), (2,))   # minute 9 missing


def test_noise_moves_carry_missing_minutes():
    day = make_day([101.0, 102.0], opens=[100.0, 101.0], minutes=[0, 2])
    mv = sg.noise_moves(day)
    assert mv[1] == pytest.approx(0.01) and mv[2] == pytest.approx(0.01) and mv[3] == pytest.approx(0.02)
    assert sg.noise_sigma([mv] * 13) is None and sg.noise_sigma([mv] * 14)[3] == pytest.approx(0.02)


# ------------------------------------------------------------------------------------ review regressions
def test_two_buckets_completing_on_one_bar_are_both_evaluated_oldest_first():
    day = make_day(np.arange(1.0, 8.0), minutes=[20, 21, 22, 23, 29, 30, 31])
    bk = sg.buckets5(day)
    assert bk.start.tolist() == [20, 25, 30] and bk.close_at[4] == (0, 1)


def test_pdh_break_in_a_bucket_whose_last_minute_is_missing_is_not_lost():
    minutes = list(range(0, 19)) + [20, 21, 22, 23] + list(range(29, 390))
    closes = [100.0] * 19 + [101.5] * 4 + [100.5] * (390 - 29)
    ctx = sg.Ctx(prev_close=100.0, prev_high=101.0, prev_low=99.0)
    it = sg.pdh_pdl(make_day(closes, minutes=minutes), ctx)
    assert len(it) == 1 and it[0].m == 29 and it[0].side == 1
    assert it[0].stop == pytest.approx(min(100.0, 101.5) - 0.01)   # low of the 9:50-9:54 bucket (its first open is 100)


def test_live_position_overrides_the_modelled_one_at_the_latest_bar():
    closes = np.linspace(100, 101, 390)
    day = make_day(closes, opens=np.r_[99.9, closes[:-1]]).upto(120)   # modelled: long since 9:30, no flips
    k = int(day.m[-1])
    assert [i for i in sg.vwap_trend(day, sg.Ctx()) if i.m == k] == []
    live_short = sg.vwap_trend(day, sg.Ctx(), live=sg.Live(side=-1, entries=1))
    assert [(i.m, i.action, i.side) for i in live_short if i.m == k] == [(k, "exit", 0), (k, "enter", 1)]
    live_flat = sg.vwap_trend(day, sg.Ctx(), live=sg.Live(side=0))   # e.g. the first order never filled
    assert [(i.m, i.action, i.side) for i in live_flat if i.m == k] == [(k, "enter", 1)]
    assert [i for i in live_flat if i.m < k] == [i for i in sg.vwap_trend(day, sg.Ctx()) if i.m < k]


def test_live_flat_blocks_a_modelled_exit():
    closes = np.r_[np.tile([99.9, 100.1], 20), [99.7, 99.5, 99.3], np.full(5, 99.3), [100.2]]
    day = make_day(closes)
    modelled = sg.vwap_fade(day, sg.Ctx())
    k = int(day.m[-1])
    assert [(i.m, i.action) for i in modelled if i.m == k] == [(k, "exit")]   # the model is long, back at VWAP
    live = sg.vwap_fade(day, sg.Ctx(), live=sg.Live(side=0, entries=1))
    assert not any(i.m == k and i.action == "exit" for i in live)   # no exit for a position that does not exist


def test_last30_and_gap_use_the_official_close_when_known():
    closes = np.r_[np.full(30, 100.05), np.full(360, 100.05)]
    day = make_day(closes)
    assert sg.last30_mom(day, sg.Ctx(prev_close=100.0))[0].side == 1
    assert sg.last30_mom(day, sg.Ctx(prev_close=100.0, prev_close_auction=100.10))[0].side == -1
    gap = make_day(np.full(390, 100.52))
    assert sg.gap_fade(gap, sg.Ctx(prev_close=100.0)) != []                        # +0.52% from the 15:59 close
    assert sg.gap_fade(gap, sg.Ctx(prev_close=100.0, prev_close_auction=100.05)) == []   # +0.47% officially
