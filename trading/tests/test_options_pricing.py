"""Tests for trader/options/pricing.py: Black-Scholes, the VIX x skew model (OPT-37, RPL), calibration,
Cboe index history and the OPT-20 VIX/VIX3M inputs. Synthetic data and fake clients only; no network."""
import copy
import io
import math
import os
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from trader.options import pricing as P
from trader.options.models import parse_occ


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(url, timeout=0):
        raise AssertionError(f"network call in a test: {url}")

    monkeypatch.setattr(P, "fetch_url", boom)


@pytest.fixture
def table():
    return P.load_skew_table()


# --- Black-Scholes ---------------------------------------------------------------------------------------


def test_bs_textbook_values():
    # Hull: S=K=100, T=1, r=5%, vol=20% -> call 10.4506, put 5.5735
    assert P.bs_price(100, 100, 1.0, 0.2, "call", 0.05) == pytest.approx(10.4506, abs=1e-4)
    assert P.bs_price(100, 100, 1.0, 0.2, "put", 0.05) == pytest.approx(5.5735, abs=1e-4)


@pytest.mark.parametrize("k", [80, 95, 100, 110, 130])
def test_put_call_parity_with_dividend_yield(k):
    s, t, r, q, v = 100.0, 0.4, 0.03, 0.013, 0.25
    c, p = P.bs_price(s, k, t, v, "call", r, q), P.bs_price(s, k, t, v, "put", r, q)
    assert c - p == pytest.approx(s * math.exp(-q * t) - k * math.exp(-r * t), abs=1e-9)


def test_kind_aliases_and_bad_kind():
    assert P.bs_price(100, 95, 0.1, 0.2, "P") == P.bs_price(100, 95, 0.1, 0.2, "put")
    assert P.bs_price(100, 95, 0.1, 0.2, "c") == P.bs_price(100, 95, 0.1, 0.2, "call")
    with pytest.raises(ValueError):
        P.bs_price(100, 95, 0.1, 0.2, "straddle")


def test_expired_and_zero_vol_give_intrinsic():
    assert P.bs_price(90, 100, 0.0, 0.2, "put") == 10.0
    assert P.bs_price(110, 100, -1.0, 0.2, "put") == 0.0
    assert P.bs_price(110, 100, 0.0, 0.2, "call") == 10.0
    # zero vol: discounted forward intrinsic
    assert P.bs_price(90, 100, 1.0, 0.0, "put", 0.05) == pytest.approx(100 * math.exp(-0.05) - 90)
    assert P.bs_price(110, 100, 1.0, 0.0, "put", 0.0) == 0.0


@pytest.mark.parametrize("bad", [dict(spot=0), dict(spot=float("nan")), dict(strike=-5), dict(strike=None),
                                 dict(vol=-0.1), dict(vol=float("inf")), dict(t_years=float("nan"))])
def test_bs_refuses_garbage(bad):
    args = dict(spot=100, strike=100, t_years=0.1, vol=0.2)
    args.update(bad)
    with pytest.raises(ValueError):
        P.bs_price(args["spot"], args["strike"], args["t_years"], args["vol"])


def test_delta_signs_parity_and_finite_difference():
    s, k, t, v, r, q = 650.0, 620.0, 35 / 365, 0.18, 0.04, 0.013
    dp = P.bs_delta(s, k, t, v, "put", r, q)
    dc = P.bs_delta(s, k, t, v, "call", r, q)
    assert -1 < dp < 0 < dc < 1
    assert dc - dp == pytest.approx(math.exp(-q * t))
    h = 0.01
    fd = (P.bs_price(s + h, k, t, v, "put", r, q) - P.bs_price(s - h, k, t, v, "put", r, q)) / (2 * h)
    assert dp == pytest.approx(fd, abs=1e-6)


def test_delta_at_expiry_is_a_step():
    assert P.bs_delta(90, 100, 0, 0.2, "put") == -1.0
    assert P.bs_delta(110, 100, 0, 0.2, "put") == 0.0
    assert P.bs_delta(100, 100, 0, 0.2, "put") == -0.5
    assert P.bs_delta(110, 100, 0, 0.2, "call") == 1.0


def test_vega_matches_finite_difference_and_is_zero_at_expiry():
    s, k, t, v, r, q = 650.0, 600.0, 30 / 365, 0.2, 0.04, 0.013
    h = 1e-4
    fd = (P.bs_price(s, k, t, v + h, "put", r, q) - P.bs_price(s, k, t, v - h, "put", r, q)) / (2 * h)
    assert P.bs_vega(s, k, t, v, r, q) == pytest.approx(fd, rel=1e-5)
    assert P.bs_vega(s, k, 0, v) == 0.0
    assert P.bs_vega(s, k, t, 0.0) == 0.0


def test_years_uses_calendar_days():
    assert P.years(365) == 1.0
    assert P.years(-3) == 0.0


# --- implied vol ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("k,kind", [(500, "put"), (600, "put"), (650, "put"), (700, "call"), (620, "call")])
@pytest.mark.parametrize("vol", [0.08, 0.2, 0.6])
def test_implied_vol_round_trip(k, kind, vol):
    s, t, r, q = 650.0, 35 / 365, 0.04, 0.013
    price = P.bs_price(s, k, t, vol, kind, r, q)
    if price < 1e-6:
        pytest.skip("price too small to invert")
    assert P.implied_vol(price, s, k, t, kind, r, q) == pytest.approx(vol, abs=1e-4)


@pytest.mark.parametrize("price", [None, float("nan"), 0.0, -1.0, "abc"])
def test_implied_vol_none_for_missing_price(price):
    assert P.implied_vol(price, 650, 620, 0.1, "put") is None


def test_implied_vol_none_outside_no_arbitrage_range():
    # a deep ITM put below its intrinsic value, and a price above anything a 500% vol gives
    assert P.implied_vol(5.0, 600, 650, 0.1, "put") is None
    assert P.implied_vol(640.0, 650, 620, 0.1, "put") is None
    assert P.implied_vol(3.0, 650, 620, 0.0, "put") is None  # expired
    assert P.implied_vol(3.0, 0, 620, 0.1, "put") is None  # bad spot


# --- skew model (OPT-37 RPL) ------------------------------------------------------------------------------

M_RPL = np.array([0.85, 0.90, 0.92, 0.95, 0.97, 1.00])
LO_RPL = np.array([1.82, 1.44, 1.31, 1.12, 1.00, 0.85])
HI_RPL = np.array([1.48, 1.25, 1.16, 1.03, 0.96, 0.82])


def rpl_iv(idx, m):
    """The research prototype's formula (options/work/proto.py iv_model, mode 'skew'), copied as the oracle."""
    w = min(1.0, max(0.0, (idx - 0.15) / 0.10))
    tab = LO_RPL * (1 - w) + HI_RPL * w
    if m >= 1.0:
        return idx * max(0.70, 0.85 - 0.8 * (m - 1.0))
    return idx * float(np.interp(m, M_RPL, tab, left=tab[0] + (m - 0.85) * -6))


@pytest.mark.parametrize("vix", [0.10, 0.15, 0.18, 0.22, 0.25, 0.40])
@pytest.mark.parametrize("m", [0.70, 0.80, 0.85, 0.88, 0.93, 0.96, 0.99, 1.0, 1.05, 1.3])
def test_default_table_reproduces_the_rpl_model(table, vix, m):
    assert P.model_iv(600.0, 600.0 * m, 35, vix, table) == pytest.approx(rpl_iv(vix, m), rel=1e-9)


def test_committed_table_has_provenance(table):
    assert "alpaca" in table["source"] and "cboe" in table["source"].lower()
    cal = table["calibrated"]
    assert cal["first_entry"] >= "2024-02-01" and cal["contracts"] > 0 and cal["dte"] == 35
    assert table["dividend_yield"]["SPY"] == pytest.approx(0.013)
    assert table["vol_index"]["SPY"] == "VIX"


def test_default_table_loaded_when_none_given(table):
    assert P.model_iv(650, 620, 35, 0.18) == P.model_iv(650, 620, 35, 0.18, table)
    a = P.default_skew_table()
    a["buckets"][0]["ratio_low"][0] = 99.0  # a caller mutating its copy never changes the cache
    assert P.default_skew_table()["buckets"][0]["ratio_low"][0] == 1.82


def test_vix_in_points_or_fraction(table):
    assert P.model_iv(650, 620, 35, 18.0, table) == P.model_iv(650, 620, 35, 0.18, table)
    assert P.vol_fraction(82.69) == pytest.approx(0.8269)
    assert P.vol_fraction(0.9) == 0.9


def test_skew_makes_otm_puts_richer_than_flat(table):
    flat = P.model_iv(650, 610, 35, 0.16, table, mode="flat")
    assert flat == 0.16
    assert P.model_iv(650, 610, 35, 0.16, table) > flat
    assert P.model_iv(650, 650, 35, 0.16, table) < flat  # at the money trades below VIX


def test_skew_flattens_when_vix_is_high(table):
    lo = P.model_iv(600, 540, 35, 0.12, table) / 0.12
    hi = P.model_iv(600, 540, 35, 0.35, table) / 0.35
    assert lo == pytest.approx(1.44) and hi == pytest.approx(1.25)


def test_iv_is_clipped_to_bounds(table):
    t = copy.deepcopy(table)
    t["iv_bounds"] = [0.05, 0.5]
    assert P.model_iv(600, 300, 35, 0.6, t) == 0.5
    assert P.model_iv(600, 900, 35, 0.04, t) == 0.05


@pytest.mark.parametrize("bad", [dict(spot=0), dict(strike=float("nan")), dict(vix=None), dict(vix=0),
                                 dict(vix=float("nan")), dict(dte=-1), dict(dte=float("nan"))])
def test_model_iv_refuses_bad_inputs(table, bad):
    args = dict(spot=650, strike=620, dte=35, vix=0.18)
    args.update(bad)
    with pytest.raises(ValueError):
        P.model_iv(args["spot"], args["strike"], args["dte"], args["vix"], table)


def test_model_iv_unknown_mode(table):
    with pytest.raises(ValueError):
        P.model_iv(650, 620, 35, 0.18, table, mode="realised")


def two_bucket_table(table):
    t = copy.deepcopy(table)
    short = copy.deepcopy(t["buckets"][0])
    short.update(name="short", dte_min=0, dte_max=14, ratio_low=[2.5, 2.0, 1.8, 1.4, 1.1, 0.9],
                 ratio_high=[2.0, 1.6, 1.5, 1.2, 1.0, 0.85])
    t["buckets"][0].update(name="mid", dte_min=21, dte_max=49)
    t["buckets"].insert(0, short)
    return t


def test_dte_bucket_is_used_and_nearest_bucket_outside_ranges(table):
    t = two_bucket_table(table)
    assert P.pick_bucket(7, t)["name"] == "short"
    assert P.pick_bucket(35, t)["name"] == "mid"
    assert P.pick_bucket(16, t)["name"] == "short"   # between buckets: the nearer one
    assert P.pick_bucket(20, t)["name"] == "mid"
    assert P.pick_bucket(90, t)["name"] == "mid"     # beyond the last bucket
    assert P.model_iv(600, 540, 7, 0.12, t) == pytest.approx(0.12 * 2.0)
    assert P.model_iv(600, 540, 35, 0.12, t) == pytest.approx(0.12 * 1.44)
    assert P.model_iv(600, 540, 0, 0.12, t) == pytest.approx(0.12 * 2.0)  # expiry day is allowed


@pytest.mark.parametrize("mutate", [
    lambda t: t.update(buckets=[]),
    lambda t: t["buckets"][0].update(ratio_low=[1.0]),
    lambda t: t["buckets"][0].update(moneyness=[0.85, 0.80, 0.92, 0.95, 0.97, 1.0]),
    lambda t: t["buckets"][0].update(ratio_high=[1.48, 1.25, 0.0, 1.03, 0.96, 0.82]),
    lambda t: t["buckets"][0].update(dte_min=50, dte_max=10),
    lambda t: t.update(vix_low=0.3, vix_high=0.2),
])
def test_broken_tables_are_refused(table, mutate):
    t = copy.deepcopy(table)
    mutate(t)
    with pytest.raises(ValueError):
        P.model_iv(650, 620, 35, 0.18, t)


def test_model_quote_is_consistent(table):
    q = P.model_quote(650, 620, 35, 0.165, "put", table, rate=0.04, div_yield=0.013)
    assert q["iv"] == P.model_iv(650, 620, 35, 0.165, table)
    assert q["price"] == pytest.approx(P.bs_price(650, 620, 35 / 365, q["iv"], "put", 0.04, 0.013))
    assert -0.25 < q["delta"] < -0.10 and q["vega"] > 0
    # rate defaults to the table's default_rate
    q2 = P.model_quote(650, 620, 35, 0.165, "put", table, div_yield=0.013)
    assert q2["price"] == pytest.approx(q["price"])
    flat = P.model_quote(650, 620, 35, 0.165, "put", table, mode="flat")
    assert flat["iv"] == 0.165 and flat["price"] < q2["price"]


def test_dividend_yield_lookup(table):
    assert P.dividend_yield("spy", table) == pytest.approx(0.013)
    assert P.dividend_yield("XYZ", table) == 0.0


def test_put_spread_credit_is_lower_with_skew(table):
    """RPL: ignoring skew overstates a bull put spread's credit relative to its risk."""
    s, dte, vix = 650.0, 35, 0.16

    def credit(mode):
        a = P.model_quote(s, 620, dte, vix, "put", table, mode=mode)["price"]
        b = P.model_quote(s, 607, dte, vix, "put", table, mode=mode)["price"]
        return a - b

    # with skew the long (lower) put is priced at a higher vol than the short one, so the credit is smaller than
    # pricing both legs at the short leg's own vol would give
    k1_iv = P.model_iv(s, 620, dte, vix, table)
    naive = (P.bs_price(s, 620, dte / 365, k1_iv, "put", 0.04, 0) - P.bs_price(s, 607, dte / 365, k1_iv, "put", 0.04, 0))
    assert P.model_iv(s, 607, dte, vix, table) > k1_iv
    assert credit("skew") < naive
    assert credit("skew") > 0 and credit("flat") > 0


# --- calibration --------------------------------------------------------------------------------------


def synthetic_obs(table, vixes=(0.12, 0.14, 0.16, 0.19, 0.22, 0.26, 0.30), spot=600.0, dte=35, r=0.04, q=0.013,
                  ms=(0.85, 0.90, 0.92, 0.95, 0.97)):
    """Option closes priced by the model itself, so calibration must give the table back."""
    out = []
    for i, v in enumerate(vixes):
        d = pd.Timestamp("2024-03-01") + pd.Timedelta(days=30 * i)
        for m in ms:
            k = spot * m
            iv = P.model_iv(spot, k, dte, v, table)
            out.append({"date": d.date().isoformat(), "expiry": (d + pd.Timedelta(days=dte)).date().isoformat(),
                        "spot": spot, "strike": k, "price": P.bs_price(spot, k, dte / 365, iv, "put", r, q),
                        "vix": v * 100, "rate": r, "div_yield": q})
    return out


def test_calibration_recovers_a_known_table(table):
    # a VIX range inside [vix_low, vix_high] keeps the synthetic ratio exactly linear in VIX
    obs = synthetic_obs(table, vixes=(0.15, 0.17, 0.19, 0.21, 0.23, 0.25))
    base = copy.deepcopy(table)
    base["buckets"][0]["ratio_low"] = [1.0] * 6
    base["buckets"][0]["ratio_high"] = [1.0] * 6
    out = P.calibrate_skew(obs, base, min_obs_per_node=3)
    b = out["buckets"][0]
    assert b["ratio_low"][:5] == pytest.approx([1.82, 1.44, 1.31, 1.12, 1.00], abs=2e-3)
    assert b["ratio_high"][:5] == pytest.approx([1.48, 1.25, 1.16, 1.03, 0.96], abs=2e-3)
    # the 1.00 node had no observations: kept from the base and reported
    assert b["ratio_low"][5] == 1.0 and "all:1" in out["calibrated"]["kept_default"]
    assert out["calibrated"]["entry_dates"] == 6 and out["calibrated"]["contracts"] == 30
    assert base["buckets"][0]["ratio_low"] == [1.0] * 6  # base not modified


def test_calibration_with_flat_vix_uses_the_mean(table):
    obs = synthetic_obs(table, vixes=(0.14, 0.14, 0.14))
    out = P.calibrate_skew(obs, table, min_obs_per_node=3)
    b = out["buckets"][0]
    assert b["ratio_low"][1] == b["ratio_high"][1] == pytest.approx(1.44, abs=2e-3)


def test_calibration_drops_bad_observations_and_handles_empty(table):
    bad = [{"date": "2024-03-01", "expiry": "2024-04-05", "spot": 600, "strike": 510, "price": float("nan"), "vix": 15},
           {"date": "2024-03-01", "expiry": "2024-02-05", "spot": 600, "strike": 510, "price": 2.0, "vix": 15},
           {"date": "2024-03-01", "spot": 600, "strike": 510, "price": 2.0, "vix": 15},
           {"date": "2024-03-01", "expiry": "2024-04-05", "spot": 600, "strike": 510, "price": 2.0, "vix": None},
           {"date": "2024-03-01", "expiry": "2024-04-05", "spot": 600, "strike": 300, "price": 2.0, "vix": 15}]
    out = P.calibrate_skew(bad, table)
    assert out["buckets"][0]["ratio_low"] == table["buckets"][0]["ratio_low"]
    assert out["calibrated"]["contracts"] == 0 and out["calibrated"]["first_entry"] is None
    empty = P.calibrate_skew([], table)
    assert empty["buckets"] == table["buckets"]


def test_calibration_respects_dte_buckets(table):
    t = two_bucket_table(table)
    obs = synthetic_obs(table, vixes=(0.15, 0.2, 0.25), dte=7)  # priced with the 35-DTE ratios, but 7 DTE
    out = P.calibrate_skew(obs, t, min_obs_per_node=3)
    short, mid = out["buckets"]
    assert short["ratio_low"][1] == pytest.approx(1.44, abs=2e-3)   # short bucket refitted
    assert mid["ratio_low"] == t["buckets"][1]["ratio_low"]          # 35-DTE bucket untouched


def test_write_and_load_round_trip(table, tmp_path):
    out = P.calibrate_skew(synthetic_obs(table), table, min_obs_per_node=3)
    path = P.write_skew_table(out, tmp_path / "skew.yaml")
    back = P.load_skew_table(path)
    assert back["buckets"] == out["buckets"] and back["calibrated"]["contracts"] == out["calibrated"]["contracts"]
    assert P.model_iv(650, 620, 35, 0.18, back) == pytest.approx(P.model_iv(650, 620, 35, 0.18, out))


def test_monthly_expiries_are_third_fridays():
    got = [d.date().isoformat() for d in P.monthly_expiries("2024-02-01", "2024-06-30")]
    assert got == ["2024-02-16", "2024-03-15", "2024-04-19", "2024-05-17", "2024-06-21"]
    assert P.monthly_expiries("2024-02-17", "2024-03-14") == []


class FakeOptionClient:
    """Answers get_option_bars like alpaca-py: `.df` indexed by (symbol, timestamp)."""

    def __init__(self, table, fail_on=()):
        self.table, self.fail_on, self.requests = table, set(fail_on), []

    def get_option_bars(self, req):
        syms = list(req.symbol_or_symbols)
        self.requests.append(syms)
        exp = parse_occ(syms[0])["expiry"]
        if exp in self.fail_on:
            raise RuntimeError("HTTP 500")
        day = pd.Timestamp(req.start) + pd.Timedelta(days=1)
        rows, idx = [], []
        for s in syms[:-1]:  # the last requested contract never traded
            o = parse_occ(s)
            dte = (pd.Timestamp(o["expiry"]) - day).days
            iv = P.model_iv(600.0, o["strike"], dte, 0.16, self.table)
            px = P.bs_price(600.0, o["strike"], dte / 365, iv, "put", 0.04, 0.013)
            idx.append((s, pd.Timestamp(day.date()).tz_localize("America/New_York").tz_convert("UTC")))
            rows.append({"open": px, "high": px, "low": px, "close": px, "volume": 10})
        return type("BarSet", (), {"df": pd.DataFrame(rows, index=pd.MultiIndex.from_tuples(idx, names=["symbol", "timestamp"]))})()


def test_collect_observations_from_fake_alpaca(table):
    days = pd.bdate_range("2024-01-02", "2024-06-28")
    spot = pd.Series(600.0, index=days)
    vix = pd.Series(16.0, index=days)
    problems = []
    client = FakeOptionClient(table, fail_on={"2024-04-19"})
    obs = P.collect_skew_observations(client, spot, vix, start="2024-02-01", end="2024-06-30", rate=0.04,
                                      problems=problems)
    expiries = sorted({o["expiry"] for o in obs})
    assert expiries == ["2024-03-15", "2024-05-17", "2024-06-21"]  # Feb entry is before start, Apr fails
    assert any("2024-04-19" in p and "HTTP 500" in p for p in problems)
    assert all(o["kind"] == "put" and o["div_yield"] == pytest.approx(0.013) for o in obs)
    assert {o["strike"] for o in obs} >= {540.0, 550.0, 570.0, 582.0, 600.0}  # $5 below 97%, $1 above
    assert 510.0 not in {o["strike"] for o in obs}  # a contract with no bar is simply absent
    for o in obs:  # entry is the last session at least 35 days before expiry
        assert (pd.Timestamp(o["expiry"]) - pd.Timestamp(o["date"])).days >= 35
    out = P.calibrate_skew(obs, table, min_obs_per_node=3)
    assert out["buckets"][0]["ratio_low"][1] == pytest.approx(table["buckets"][0]["ratio_low"][1], abs=0.02)


def test_collect_with_no_history_returns_nothing(table):
    problems = []
    assert P.collect_skew_observations(FakeOptionClient(table), pd.Series(dtype=float), pd.Series(dtype=float),
                                       problems=problems) == []
    assert problems == ["no spot or index history"]


# --- Cboe index history (OPT-20, OPT-37) --------------------------------------------------------------

VIX_CSV = "DATE,OPEN,HIGH,LOW,CLOSE\n09/23/2026,16.1,16.5,15.9,16.20\n09/24/2026,16.2,17.0,16.0,bad\n" \
          "09/25/2026,16.9,18.0,16.5,17.50\n"
VIX3M_CSV = "DATE,OPEN,HIGH,LOW,CLOSE\n09/23/2026,19,19,19,19.00\n09/25/2026,17,17,17,17.00\n"
SKEW_CSV = "DATE,SKEW\n09/24/2026,141.2\n09/25/2026,139.8\n"


class FakeFetch:
    def __init__(self, text=None, error=None):
        self.text, self.error, self.urls = text, error, []

    def __call__(self, url):
        self.urls.append(url)
        if self.error:
            raise self.error
        return self.text


def test_fetch_cboe_index_downloads_parses_and_caches(tmp_path):
    f = FakeFetch(VIX_CSV)
    s = P.fetch_cboe_index("vix", state_dir=tmp_path, fetch=f)
    assert f.urls == ["https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"]
    assert list(s.index.strftime("%Y-%m-%d")) == ["2026-09-23", "2026-09-25"]  # the bad row is dropped
    assert s.iloc[-1] == pytest.approx(0.175) and s.name == "VIX"
    assert s.attrs["stale"] is False and s.attrs["source"].endswith("VIX_History.csv")
    assert (tmp_path / "cache" / "cboe" / "VIX_History.csv").exists()
    # a fresh cache is used without a download
    f2 = FakeFetch(error=OSError("offline"))
    s2 = P.fetch_cboe_index("VIX", state_dir=tmp_path, fetch=f2)
    assert f2.urls == [] and s2.equals(s)


def test_old_cache_is_refreshed_and_used_when_offline(tmp_path):
    P.fetch_cboe_index("VIX3M", state_dir=tmp_path, fetch=FakeFetch(VIX3M_CSV))
    cache = tmp_path / "cache" / "cboe" / "VIX3M_History.csv"
    old = datetime(2026, 9, 1).timestamp()
    os.utime(cache, (old, old))
    now = datetime(2026, 9, 28, 17, 0)
    s = P.fetch_cboe_index("VIX3M", state_dir=tmp_path, fetch=FakeFetch(error=OSError("offline")), now=now)
    assert s.attrs["stale"] is True and "offline" in s.attrs["error"] and s.iloc[-1] == pytest.approx(0.17)
    newer = VIX3M_CSV + "09/28/2026,18,18,18,18.00\n"
    s = P.fetch_cboe_index("VIX3M", state_dir=tmp_path, fetch=FakeFetch(newer), now=now)
    assert s.attrs["stale"] is False and s.iloc[-1] == pytest.approx(0.18)


def test_offline_without_cache_raises_a_clear_error(tmp_path):
    with pytest.raises(P.CboeDataError) as e:
        P.fetch_cboe_index("VIX", state_dir=tmp_path, fetch=FakeFetch(error=OSError("no route")))
    msg = str(e.value)
    assert "VIX_History.csv" in msg and "no route" in msg and str(tmp_path) in msg


def test_a_broken_download_is_not_cached(tmp_path):
    with pytest.raises(P.CboeDataError):
        P.fetch_cboe_index("VIX", state_dir=tmp_path, fetch=FakeFetch("<html>maintenance</html>"))
    assert not (tmp_path / "cache" / "cboe" / "VIX_History.csv").exists()


def test_units_and_skew_is_never_divided(tmp_path):
    pts = P.fetch_cboe_index("VIX", state_dir=tmp_path, fetch=FakeFetch(VIX_CSV), units="points")
    assert pts.iloc[-1] == 17.5
    sk = P.fetch_cboe_index("SKEW", state_dir=tmp_path, fetch=FakeFetch(SKEW_CSV))
    assert sk.iloc[-1] == pytest.approx(139.8)
    with pytest.raises(ValueError):
        P.fetch_cboe_index("VIX", state_dir=tmp_path, fetch=FakeFetch(VIX_CSV), units="percent")


@pytest.mark.parametrize("name", ["", "../etc", "VIX/../x", None])
def test_bad_index_names_are_refused(tmp_path, name):
    with pytest.raises(ValueError):
        P.fetch_cboe_index(name, state_dir=tmp_path, fetch=FakeFetch(VIX_CSV))


def test_parse_cboe_history_edge_cases():
    with pytest.raises(ValueError):
        P.parse_cboe_history("")
    with pytest.raises(ValueError):
        P.parse_cboe_history("DATE,CLOSE\n")
    with pytest.raises(ValueError):
        P.parse_cboe_history("DATE,CLOSE\n01/02/2024,nan\n01/03/2024,-1\n")
    with pytest.raises(ValueError):
        P.parse_cboe_history("DAY,CLOSE\n01/02/2024,12\n")
    s = P.parse_cboe_history("DATE,CLOSE\n2024-01-03,13\n01/02/2024,12\n01/02/2024,12.5\n")
    assert list(s.values) == [12.5, 13.0]  # ISO accepted, sorted, duplicate date keeps the last


def test_the_default_fetch_is_never_the_network_in_tests(tmp_path):
    with pytest.raises(P.CboeDataError):
        P.fetch_cboe_index("VIX", state_dir=tmp_path)


# --- OPT-20 inputs --------------------------------------------------------------------------------------


def test_vix_term_ratio():
    assert P.vix_term_ratio(20, 18) == pytest.approx(20 / 18)
    assert P.vix_term_ratio(0.2, 0.25) == pytest.approx(0.8)
    for a, b in [(None, 18), (20, 0), (float("nan"), 18), (20, "x"), (-1, 18)]:
        assert P.vix_term_ratio(a, b) is None


def test_opt20_term_structure_flags_inversion_and_missing_data(tmp_path):
    vix = P.fetch_cboe_index("VIX", state_dir=tmp_path, fetch=FakeFetch(VIX_CSV))
    v3 = P.fetch_cboe_index("VIX3M", state_dir=tmp_path, fetch=FakeFetch(VIX3M_CSV))
    inv = P.opt20_term_structure("2026-09-25", vix, v3)
    assert inv["ratio"] == pytest.approx(17.5 / 17.0, abs=1e-4) and inv["blocks_entry"] is True
    assert inv["source"] == "cboe"
    calm = P.opt20_term_structure("2026-09-23", vix, v3)
    assert calm["blocks_entry"] is False and calm["vix"] == pytest.approx(0.162)
    # 24 Sep has a bad VIX row: the previous close is used (asof), within the staleness limit
    assert P.opt20_term_structure("2026-09-24", vix, v3)["vix"] == pytest.approx(0.162)
    for day, a, b in [("2026-10-30", vix, v3), ("2026-09-22", vix, v3), ("2026-09-25", None, v3),
                      ("2026-09-25", vix, pd.Series(dtype=float))]:
        out = P.opt20_term_structure(day, a, b)
        assert out["ratio"] is None and out["blocks_entry"] is None


def test_index_on_staleness():
    s = pd.Series([0.2, 0.3], index=pd.to_datetime(["2026-09-01", "2026-09-10"]))
    assert P.index_on(s, "2026-09-12") == 0.3
    assert P.index_on(s, "2026-09-20") is None
    assert P.index_on(s, "2026-09-20", max_stale_days=10) == 0.3
    assert P.index_on(None, "2026-09-12") is None


# --- review fixes ---------------------------------------------------------------------------------------


def test_model_quote_defaults_to_the_calibration_inputs(table):
    """RPL prices SPY with q = 1.3% (table) and the day's T-bill rate; defaults must not silently use q = 0."""
    q = P.model_quote(650, 620, 35, 0.16, "put", table, rate=0.005)
    iv = P.model_iv(650, 620, 35, 0.16, table)
    assert q["div_yield"] == pytest.approx(0.013) and q["rate_source"] == "caller" and q["rate"] == 0.005
    assert q["price"] == pytest.approx(P.bs_price(650, 620, 35 / 365, iv, "put", 0.005, 0.013))
    assert q["delta"] == pytest.approx(P.bs_delta(650, 620, 35 / 365, iv, "put", 0.005, 0.013))
    d = P.model_quote(650, 620, 35, 0.16, "put", table)
    assert d["rate_source"] == "default_rate" and d["rate"] == pytest.approx(table["default_rate"])
    assert P.model_quote(650, 620, 35, 0.16, "put", table, underlying="qqq")["div_yield"] == pytest.approx(0.006)
    assert P.model_quote(650, 620, 35, 0.16, "put", table, div_yield=0.0)["div_yield"] == 0.0
    with pytest.raises(ValueError):
        P.model_quote(650, 620, 35, 0.16, "put", table, rate=float("nan"))


DTB3_CSV = "observation_date,DTB3\n2026-09-22,4.01\n2026-09-23,.\n2026-09-24,4.08\n"


def test_fetch_tbill_rates_parses_caches_and_converts(tmp_path):
    f = FakeFetch(DTB3_CSV)
    r = P.fetch_tbill_rates(state_dir=tmp_path, fetch=f)
    assert f.urls == ["https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3"]
    assert list(r.index.strftime("%Y-%m-%d")) == ["2026-09-22", "2026-09-24"]  # '.' is missing, not zero
    assert r.iloc[-1] == pytest.approx(0.0408) and r.attrs["units"] == "fraction" and r.attrs["stale"] is False
    assert (tmp_path / "cache" / "fred" / "DTB3.csv").exists()
    assert P.rate_on(r, "2026-09-23") == pytest.approx(0.0401)   # previous value
    assert P.rate_on(r, "2026-10-20") is None                    # too old
    with pytest.raises(P.CboeDataError):
        P.fetch_tbill_rates(state_dir=tmp_path / "x", fetch=FakeFetch("<html>down</html>"))
    assert not (tmp_path / "x" / "cache" / "fred" / "DTB3.csv").exists()


def test_skew_series_is_labelled_points(tmp_path):
    sk = P.fetch_cboe_index("SKEW", state_dir=tmp_path, fetch=FakeFetch(SKEW_CSV))
    assert sk.attrs["units"] == "points"
    assert P.fetch_cboe_index("VIX", state_dir=tmp_path, fetch=FakeFetch(VIX_CSV)).attrs["units"] == "fraction"


@pytest.mark.parametrize("mutate", [
    lambda t: t.update(iv_bounds=[3.0, 0.01]),
    lambda t: t.update(iv_bounds=[0.0, 3.0]),
    lambda t: t.update(iv_bounds=["a", 3.0]),
    lambda t: t.update(put_wing_slope=-6),
    lambda t: t.update(put_wing_slope=None),
    lambda t: t["buckets"][0].update(moneyness=[float("nan"), 0.90, 0.92, 0.95, 0.97, 1.0]),
    lambda t: t["buckets"][0].update(moneyness=["x", 0.90, 0.92, 0.95, 0.97, 1.0]),
    lambda t: t["buckets"][0].update(ratio_low=[1.8, None, 1.3, 1.1, 1.0, 0.85]),
    lambda t: t["buckets"][0]["call"].update(floor=-1),
    lambda t: t["buckets"][0]["call"].update(floor=0.9),          # floor above atm
    lambda t: t["buckets"][0]["call"].update(slope=-0.8),
    lambda t: t["buckets"][0]["call"].update(atm=0),
    lambda t: t["buckets"][0].update(call=[1, 2]),
    lambda t: t.update(vix_low=15, vix_high=25),                    # Cboe points, not fractions
    lambda t: t.update(buckets=[1]),
    lambda t: t.update(buckets="all"),
    lambda t: t["buckets"][0].update(dte_min="soon"),
])
def test_more_broken_tables_are_refused_with_value_error(table, mutate):
    t = copy.deepcopy(table)
    mutate(t)
    with pytest.raises(ValueError):
        P.validate_skew_table(t)
    with pytest.raises(ValueError):
        P.model_quote(650, 620, 35, 0.18, "put", t)


def test_collect_skips_expiries_when_the_index_is_stale(table):
    days = pd.bdate_range("2024-01-02", "2024-06-28")
    spot = pd.Series(600.0, index=days)
    vix = pd.Series(16.0, index=days[days <= "2024-03-29"])  # truncated / stale cache
    problems = []
    obs = P.collect_skew_observations(FakeOptionClient(table), spot, vix, start="2024-02-01", end="2024-06-30",
                                      rate=0.04, problems=problems)
    # entries 2024-04-12 and 2024-05-17 would carry March's VIX forward: skipped
    assert {o["expiry"] for o in obs} == {"2024-03-15", "2024-04-19"}
    assert sum("no index value" in p for p in problems) == 2


def test_collect_uses_a_daily_rate_series(table):
    days = pd.bdate_range("2024-01-02", "2024-06-28")
    spot, vix = pd.Series(600.0, index=days), pd.Series(16.0, index=days)
    rates = pd.Series(0.052, index=days[days <= "2024-04-30"])
    problems = []
    obs = P.collect_skew_observations(FakeOptionClient(table), spot, vix, start="2024-02-01", end="2024-06-30",
                                      rate=rates, problems=problems)
    assert obs and all(o["rate"] == pytest.approx(0.052) for o in obs)
    assert {o["expiry"] for o in obs} == {"2024-03-15", "2024-04-19", "2024-05-17"}
    assert sum("no rate" in p for p in problems) == 1  # the June expiry's entry (17 May) has no rate


def test_tz_aware_day_and_series_never_crash_opt20(tmp_path):
    vix = P.fetch_cboe_index("VIX", state_dir=tmp_path, fetch=FakeFetch(VIX_CSV))
    v3 = P.fetch_cboe_index("VIX3M", state_dir=tmp_path, fetch=FakeFetch(VIX3M_CSV))
    now = pd.Timestamp("2026-09-25 16:10", tz="America/New_York")
    out = P.opt20_term_structure(now, vix, v3)
    assert out["date"] == "2026-09-25" and out["blocks_entry"] is True
    # 2026-09-26 01:00 UTC is still 25 Sep in New York
    assert P.opt20_term_structure(pd.Timestamp("2026-09-26 01:00", tz="UTC"), vix, v3)["date"] == "2026-09-25"
    utc = vix.copy()
    utc.index = utc.index.tz_localize("America/New_York").tz_convert("UTC")
    assert P.index_on(utc, "2026-09-25") == pytest.approx(0.175)
    assert P.index_on(utc, now) == pytest.approx(0.175)


def test_opt20_record_logs_value_dates_and_staleness(tmp_path):
    vix = P.fetch_cboe_index("VIX", state_dir=tmp_path, fetch=FakeFetch(VIX_CSV))
    v3 = P.fetch_cboe_index("VIX3M", state_dir=tmp_path, fetch=FakeFetch(VIX3M_CSV))
    out = P.opt20_term_structure("2026-09-24", vix, v3)  # neither index has a usable 24 Sep row
    assert out["vix_date"] == "2026-09-23" and out["vix3m_date"] == "2026-09-23"
    assert out["stale"] is False and out["errors"] == []
    assert out["source_url"][0].endswith("VIX_History.csv") and out["source_url"][1].endswith("VIX3M_History.csv")
    cache = tmp_path / "cache" / "cboe" / "VIX_History.csv"
    old = datetime(2026, 9, 1).timestamp()
    os.utime(cache, (old, old))
    st = P.fetch_cboe_index("VIX", state_dir=tmp_path, fetch=FakeFetch(error=OSError("offline")),
                            now=datetime(2026, 9, 28))
    rec = P.opt20_term_structure("2026-09-28", st, v3)
    assert rec["stale"] is True and "offline" in rec["errors"][0] and rec["vix_date"] == "2026-09-25"
    missing = P.opt20_term_structure("2026-10-30", vix, v3)
    assert missing["vix_date"] is None and missing["vix3m_date"] is None


def test_opt20_flag_matches_the_logged_ratio():
    s1 = pd.Series([0.200008], index=pd.to_datetime(["2026-09-25"]))
    s2 = pd.Series([0.2], index=pd.to_datetime(["2026-09-25"]))
    out = P.opt20_term_structure("2026-09-25", s1, s2)
    assert out["ratio"] == 1.0 and out["blocks_entry"] is False


def test_calibration_records_dte_underlying_rate_and_keeps_provenance(table, tmp_path):
    obs = synthetic_obs(table)
    for o in obs[:5]:
        del o["rate"]
    out = P.calibrate_skew(obs, table, min_obs_per_node=3, dte=35, underlying="spy", rate_source="FRED DTB3")
    cal = out["calibrated"]
    assert cal["dte"] == 35 and cal["underlying"] == "SPY" and out["buckets"][0]["calibrated_dte"] == 35
    assert "30 observations with their own rate (FRED DTB3)" in cal["rate"] and "5 at flat 0.04" in cal["rate"]
    path = P.write_skew_table(out, tmp_path / "skew.yaml")
    text = path.read_text()
    assert "FRED DTB3" in text and "35 DTE" in text and "underlying SPY" in text and "call.atm" in text
    assert P.load_skew_table(path)["calibrated"]["dte"] == 35


def test_calibration_shares_nothing_with_the_base(table):
    base = copy.deepcopy(table)
    out = P.calibrate_skew([], base)
    out["dividend_yield"]["SPY"] = 9.9
    out["buckets"][0]["call"]["atm"] = 5
    out["iv_bounds"][0] = 0.5
    assert base == table


@pytest.mark.parametrize("field,value", [("rate", None), ("div_yield", None), ("rate", "x"), ("div_yield", "x"),
                                         ("rate", float("nan"))])
def test_bad_rate_or_yield_in_one_observation_never_crashes(table, field, value):
    obs = synthetic_obs(table)
    obs[0][field] = value
    out = P.calibrate_skew(obs, table, min_obs_per_node=3)
    n = out["calibrated"]["contracts"]
    assert n == (len(obs) if value is None else len(obs) - 1)  # None = default; garbage = dropped


def test_options_key_pair_is_never_mixed(monkeypatch):
    for k in ("ALPACA_OPTIONS_KEY", "ALPACA_OPTIONS_SECRET", "ALPACA_DATA_KEY", "ALPACA_DATA_SECRET",
              "ALPACA_RULES_KEY", "ALPACA_RULES_SECRET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ALPACA_OPTIONS_KEY", "okey")         # half a pair
    monkeypatch.setenv("ALPACA_RULES_KEY", "rkey")
    monkeypatch.setenv("ALPACA_RULES_SECRET", "rsecret")
    assert P._options_key_pair() == ("rkey", "rsecret")
    monkeypatch.setenv("ALPACA_OPTIONS_SECRET", "osecret")
    assert P._options_key_pair() == ("okey", "osecret")
    for k in ("ALPACA_OPTIONS_KEY", "ALPACA_RULES_KEY"):
        monkeypatch.delenv(k)
    with pytest.raises(RuntimeError):
        P._options_key_pair()


def test_load_dotenv_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# c\nPRICING_T_A=1\nPRICING_T_B=\nPRICING_T_C=file\n")
    monkeypatch.delenv("PRICING_T_A", raising=False)
    monkeypatch.delenv("PRICING_T_B", raising=False)
    monkeypatch.setenv("PRICING_T_C", "env")
    P._load_dotenv(env)
    assert os.environ["PRICING_T_A"] == "1" and "PRICING_T_B" not in os.environ
    assert os.environ["PRICING_T_C"] == "env"


def _main_inputs():
    days = pd.bdate_range("2024-01-02", "2024-06-28")
    return pd.Series(600.0, index=days), pd.Series(0.16, index=days, name="VIX"), pd.Series(0.04, index=days)


def test_main_calibrates_with_rates_and_writes(table, tmp_path, monkeypatch):
    monkeypatch.setattr(P, "_load_dotenv", lambda path=None: None)
    spot, vix, rates = _main_inputs()
    path = tmp_path / "skew.yaml"
    out, err = io.StringIO(), io.StringIO()
    rc = P.main(["calibrate", "--write", "--path", str(path)], option_client=FakeOptionClient(table),
                spot=spot, vix=vix, rates=rates, out=out, err=err)
    assert rc == 0 and path.exists()
    back = P.load_skew_table(path)
    cal = back["calibrated"]
    assert cal["dte"] == 35 and cal["underlying"] == "SPY" and "FRED DTB3" in cal["rate"]
    assert "0 at flat" in cal["rate"] and cal["contracts"] > 0
    assert "FRED DTB3" in path.read_text().splitlines()[6]


def test_main_refuses_to_write_from_a_stale_cache(table, tmp_path, monkeypatch):
    monkeypatch.setattr(P, "_load_dotenv", lambda path=None: None)
    spot, vix, rates = _main_inputs()
    vix.attrs.update(stale=True, error="OSError: offline")
    path = tmp_path / "skew.yaml"
    err = io.StringIO()
    rc = P.main(["calibrate", "--write", "--path", str(path)], option_client=FakeOptionClient(table),
                spot=spot, vix=vix, rates=rates, out=io.StringIO(), err=err)
    assert rc == 2 and not path.exists()
    assert "stale cache" in err.getvalue() and "not written" in err.getvalue()
    # no observations at all: also refused
    rc = P.main(["calibrate", "--write", "--path", str(path)], option_client=FakeOptionClient(table),
                spot=spot, vix=vix.iloc[:0], rates=rates, out=io.StringIO(), err=io.StringIO())
    assert rc == 2 and not path.exists()
