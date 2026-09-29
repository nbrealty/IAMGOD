"""Scalp lab data (lab/scalp/data.py) with fake Alpaca clients: no network, no keys."""
import json
import warnings
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from lab.scalp import data as dt

NY = "America/New_York"


def _utc(t):
    """alpaca-py stores request times as naive UTC."""
    t = pd.Timestamp(t)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


class FakeTrading:
    def __init__(self, half_days=()):
        self.half_days = set(half_days)

    def get_calendar(self, req):
        out = []
        for d in pd.bdate_range(req.start, req.end):
            close = "13:00" if d.date() in self.half_days else "16:00"
            out.append(SimpleNamespace(date=d.date(), open=pd.Timestamp(f"{d.date()} 09:30").to_pydatetime(),
                                       close=pd.Timestamp(f"{d.date()} {close}").to_pydatetime()))
        return out


BASE = pd.Timestamp("2026-01-01", tz="UTC")


def _px(idx):
    """A price that depends only on the bar time, so two requests for one minute agree."""
    return 100 + (idx - BASE).total_seconds().to_numpy() / 60 * 1e-5


class FakeData:
    """Extended-hours minute bars (04:00-19:59 New York) on weekdays in [start, end), or daily bars (official
    close = the 16:00 price + 0.05). With `ex_date`, prices drop by `factor` on that date, and a request made on
    or after it (`today`) sees every earlier bar scaled by `factor` too, like Alpaca's back-adjustment."""

    def __init__(self, fail_first=0, ex_date=None, factor=0.995):
        self.requests, self.fail_first = [], fail_first
        self.ex_date, self.factor, self.today = ex_date, factor, None

    def _scale(self, idx):
        """Raw prices drop by the dividend on the ex-date; once it has passed, earlier bars are scaled to match."""
        if self.ex_date is None:
            return np.ones(len(idx))
        after = idx.tz_convert(NY).date >= self.ex_date
        adjusted = self.today is not None and self.today >= self.ex_date
        return np.where(after | adjusted, self.factor, 1.0)

    def get_stock_bars(self, req):
        self.requests.append(req)
        if self.fail_first:
            self.fail_first -= 1
            raise ConnectionError("read timed out")
        start, end = _utc(req.start), _utc(req.end)
        if getattr(getattr(req, "timeframe", None), "value", "1Min") == "1Day":
            days = pd.bdate_range(start.tz_convert(NY).date(), end.tz_convert(NY).date())
            idx = pd.DatetimeIndex([pd.Timestamp(d).tz_localize(NY) for d in days]).tz_convert("UTC")
            idx = idx[(idx >= start) & (idx < end)]
            px = (_px(idx + pd.Timedelta(hours=16)) + 0.05) * self._scale(idx)
        else:
            idx = pd.date_range(start.floor("min"), end, freq="min", inclusive="left")
            ny = idx.tz_convert(NY)
            keep = (ny.dayofweek < 5) & (ny.hour >= 4) & (ny.hour < 20)
            idx = idx[keep]
            px = _px(idx) * self._scale(idx)
        df = pd.DataFrame({"open": px, "high": px + 0.01, "low": px - 0.01, "close": px, "volume": 100.0,
                           "trade_count": 5.0, "vwap": px},
                          index=pd.MultiIndex.from_arrays([[req.symbol_or_symbols[0]] * len(idx), idx],
                                                          names=["symbol", "timestamp"]))
        return SimpleNamespace(df=df)


def _minute_months(reqs):
    """Months of the full-month minute requests (not daily bars, not 1-minute basis probes)."""
    return [_utc(r.start).tz_convert(NY).strftime("%Y-%m") for r in reqs
            if r.timeframe.value == "1Min" and _utc(r.end) - _utc(r.start) > pd.Timedelta(minutes=1)]


def test_cap_end_never_asks_for_the_last_16_minutes():
    now = pd.Timestamp("2026-09-28 14:35", tz="UTC")
    assert dt.cap_end(now, now) == now - pd.Timedelta(minutes=16)
    early = pd.Timestamp("2026-09-01", tz="UTC")
    assert dt.cap_end(early, now) == early


def test_keep_rth_uses_the_calendar_including_half_days(tmp_path):
    cal = dt.fetch_calendar(FakeTrading(half_days={date(2026, 11, 27)}), date(2026, 11, 26), date(2026, 11, 30))
    cal = dt.save_calendar(cal, tmp_path)
    idx = pd.date_range("2026-11-27 04:00", "2026-11-27 19:59", freq="min", tz=NY).tz_convert("UTC")
    df = pd.DataFrame({"close": 1.0}, index=idx)
    rth = dt.keep_rth(df, cal)
    assert len(rth) == 210 and rth.index[0].strftime("%H:%M") == "09:30" and rth.index[-1].strftime("%H:%M") == "12:59"


def test_download_caches_by_month_and_caps_the_end(tmp_path):
    now = pd.Timestamp("2026-09-04 15:00", tz=NY).tz_convert("UTC")
    fake = FakeData()
    counts = dt.download(["spy"], date(2026, 9, 1), date(2026, 9, 4), tmp_path, client=fake,
                         trading_client=FakeTrading(half_days={date(2026, 9, 3)}), now=now, log=lambda s: None)
    assert _minute_months(fake.requests) == ["2026-07", "2026-08", "2026-09"]
    assert all(_utc(r.end) <= now - pd.Timedelta(minutes=16) for r in fake.requests)
    assert all(r.feed.value == "sip" and r.adjustment.value == "all" for r in fake.requests)
    assert (tmp_path / "SPY_202609.csv.gz").exists() and (tmp_path / "calendar.csv").exists()
    bars = dt.load_bars("SPY", date(2026, 9, 1), date(2026, 9, 4), tmp_path)
    per_day = bars.groupby(bars.index.date).size()
    assert per_day[date(2026, 9, 1)] == 390 and per_day[date(2026, 9, 3)] == 210   # half day
    assert per_day[date(2026, 9, 4)] == (14 * 60 + 44) - (9 * 60 + 30)            # stops at 14:44 (now - 16 min)
    assert bars.index.min().strftime("%H:%M") == "09:30" and counts["SPY"] > 0

    n = len(fake.requests)
    dt.download(["SPY"], date(2026, 9, 1), date(2026, 9, 4), tmp_path, client=fake, trading_client=FakeTrading(),
                now=now, log=lambda s: None)
    assert len(fake.requests) == n                    # everything cached through `now - 16 min`
    later = now + pd.Timedelta(hours=1)
    dt.download(["SPY"], date(2026, 9, 1), date(2026, 9, 4), tmp_path, client=fake, trading_client=FakeTrading(),
                now=later, log=lambda s: None)
    assert _minute_months(fake.requests[n:]) == ["2026-09"]      # only the open month is re-fetched in full


def test_prior_day_levels_and_missing_sessions(tmp_path):
    now = pd.Timestamp("2026-09-10 20:00", tz=NY).tz_convert("UTC")
    dt.download(["SPY"], date(2026, 9, 1), date(2026, 9, 9), tmp_path, client=FakeData(),
                trading_client=FakeTrading(), now=now, log=lambda s: None)
    bars = dt.load_bars("SPY", date(2026, 9, 1), date(2026, 9, 9), tmp_path)
    cal = dt.load_calendar(tmp_path)
    lv = dt.prior_day_levels(bars, cal)
    d1, d2 = date(2026, 9, 1), date(2026, 9, 2)
    assert lv.loc[d2, "prev_close"] == lv.loc[d1, "close"] and lv.loc[d2, "prev_high"] == lv.loc[d1, "high"]
    assert np.isnan(lv.loc[d1, "prev_close"])
    gap = bars[bars.index.date != date(2026, 9, 3)]                       # a session missing from the data
    lv2 = dt.prior_day_levels(gap, cal)
    assert np.isnan(lv2.loc[date(2026, 9, 4), "prev_close"])


def test_retry_transient_errors_but_not_permanent_ones():
    slept = []
    fake = FakeData(fail_first=2)
    out = dt.with_retry(lambda: fake.get_stock_bars(SimpleNamespace(
        symbol_or_symbols=["SPY"], start=pd.Timestamp("2026-09-01 13:30", tz="UTC"),
        end=pd.Timestamp("2026-09-01 13:35", tz="UTC"))), sleep=slept.append)
    assert len(out.df) == 5 and slept == [2.0, 4.0]

    calls = []

    def denied():
        calls.append(1)
        raise RuntimeError('{"message":"subscription does not permit querying recent SIP data"}')

    with pytest.raises(RuntimeError):
        dt.with_retry(denied, sleep=slept.append)
    assert len(calls) == 1


def test_keys_prefer_the_scalp_account(monkeypatch):
    monkeypatch.setenv("ALPACA_RULES_KEY", "r")
    monkeypatch.setenv("ALPACA_RULES_SECRET", "rs")
    monkeypatch.delenv("ALPACA_SCALP_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SCALP_SECRET", raising=False)
    assert dt.keys() == ("r", "rs")
    monkeypatch.setenv("ALPACA_SCALP_KEY", "s")
    monkeypatch.setenv("ALPACA_SCALP_SECRET", "ss")
    assert dt.keys() == ("s", "ss")


# ------------------------------------------------------------------------------------ review regressions
def test_later_download_keeps_one_price_basis_after_an_ex_dividend_date(tmp_path):
    """Months cached before an ex-date must not keep the old adjustment next to months fetched after it."""
    fake, trading = FakeData(ex_date=date(2026, 9, 18)), FakeTrading()
    now1 = pd.Timestamp("2026-09-05 12:00", tz=NY).tz_convert("UTC")
    fake.today = now1.tz_convert(NY).date()
    dt.download(["SPY"], date(2026, 8, 3), date(2026, 9, 4), tmp_path, client=fake, trading_client=trading,
                now=now1, log=lambda s: None)
    now2 = pd.Timestamp("2026-10-06 12:00", tz=NY).tz_convert("UTC")
    fake.today = now2.tz_convert(NY).date()
    logs = []
    dt.download(["SPY"], date(2026, 9, 1), date(2026, 10, 5), tmp_path, client=fake, trading_client=trading,
                now=now2, log=logs.append)
    assert "2026-08" in _minute_months(fake.requests) and any("re-adjusted" in m for m in logs)
    with warnings.catch_warnings():
        warnings.simplefilter("error")                    # one basis: no mixed-basis warning
        bars = dt.load_bars("SPY", date(2026, 6, 15), date(2026, 10, 5), tmp_path)
    lv = dt.prior_day_levels(bars, dt.load_calendar(tmp_path))
    gap = (lv["open"] / lv["prev_close"] - 1).abs()
    assert gap.max() < 0.001                              # no fake -0.5% overnight gap at 2026-09-01
    # months fetched again with no corporate action in between are only probed, not re-fetched
    n = len(fake.requests)
    later = now2 + pd.Timedelta(days=1)
    fake.today = later.tz_convert(NY).date()
    dt.download(["SPY"], date(2026, 10, 1), date(2026, 10, 6), tmp_path, client=fake, trading_client=trading,
                now=later, log=lambda s: None)
    assert _minute_months(fake.requests[n:]) == ["2026-10"]


def test_load_bars_warns_on_mixed_price_basis(tmp_path):
    now = pd.Timestamp("2026-09-10 20:00", tz=NY).tz_convert("UTC")
    dt.download(["SPY"], date(2026, 9, 1), date(2026, 9, 9), tmp_path, client=FakeData(),
                trading_client=FakeTrading(), now=now, log=lambda s: None)
    mp = tmp_path / "SPY_202608.json"
    meta = json.loads(mp.read_text())
    mp.write_text(json.dumps({**meta, "basis_as_of": "2026-06-01T00:00:00+00:00"}))
    with pytest.warns(UserWarning, match="price-adjustment"):
        dt.load_bars("SPY", date(2026, 8, 1), date(2026, 9, 9), tmp_path)


def test_official_closes_are_cached_for_closed_sessions_only(tmp_path):
    now = pd.Timestamp("2026-09-04 11:00", tz=NY).tz_convert("UTC")      # 2026-09-04 still in progress
    dt.download(["SPY"], date(2026, 9, 1), date(2026, 9, 4), tmp_path, client=FakeData(),
                trading_client=FakeTrading(), now=now, log=lambda s: None)
    closes = dt.load_official_closes("SPY", date(2026, 9, 1), date(2026, 9, 4), tmp_path)
    assert sorted(closes) == [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]
    t16 = pd.DatetimeIndex([pd.Timestamp("2026-09-02 16:00", tz=NY)]).tz_convert("UTC")
    assert closes[date(2026, 9, 2)] == pytest.approx(_px(t16)[0] + 0.05)


def test_transient_errors_are_classified_by_type_not_by_words():
    import requests
    chunk = requests.exceptions.ChunkedEncodingError(
        "('Connection broken: InvalidChunkLength(got length b\'\', 0 bytes read)', ...)")
    assert dt._transient(chunk)
    assert dt._transient(ConnectionError("proxy 4403 reset"))
    assert dt._transient(requests.exceptions.ReadTimeout("read timed out"))
    http = SimpleNamespace(response=SimpleNamespace(status_code=403))
    from alpaca.common.exceptions import APIError
    assert not dt._transient(APIError('{"message": "forbidden"}', http))
    assert dt._transient(APIError('{"message": "busy"}', SimpleNamespace(response=SimpleNamespace(status_code=503))))
    assert dt._transient(APIError('{"message": "rate"}', SimpleNamespace(response=SimpleNamespace(status_code=429))))
    assert not dt._transient(RuntimeError("subscription does not permit querying recent SIP data"))
    assert not dt._transient(ValueError("bad request field"))
