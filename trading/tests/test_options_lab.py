"""Options lab (lab/options_lab.py): offline checks that need no Alpaca connection."""
import importlib.util
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

_spec = importlib.util.spec_from_file_location("options_lab", Path(__file__).resolve().parent.parent / "lab" / "options_lab.py")
options_lab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(options_lab)

TODAY = date(2026, 9, 29)


def _bare_lab(tmp_path, mode="0dte"):
    lab = options_lab.Lab.__new__(options_lab.Lab)  # skip __init__: no network clients
    lab.dir, lab.trades, lab.done_checkpoints, lab.dry = tmp_path, [], set(), True
    lab.book_path = tmp_path / "trades.json"
    lab.mode, lab.today, lab.full_day, lab.cutoff_alerted = mode, TODAY, True, False
    lab.state_dir = tmp_path
    return lab


def _at(monkeypatch, hm):
    h, m = map(int, hm.split(":"))
    monkeypatch.setattr(options_lab, "ny_now", lambda: datetime(2026, 9, 29, h, m, tzinfo=options_lab.NY))


def _rows(tmp_path):
    return [json.loads(ln) for ln in (tmp_path / "journal.jsonl").read_text().splitlines()]


def _contracts(*exps):
    return lambda req: NS(option_contracts=[NS(expiration_date=e) for e in exps])


def _paper_trading():
    return NS(get_account=lambda: NS(), _base_url="https://paper-api.alpaca.markets")


def _chain(spot=700.0, typ="put", delta=True):
    """A put chain around `spot`, 1-dollar strikes, 0.05-wide quotes; delta falls away from the money."""
    rows = []
    for k in range(int(spot) - 20, int(spot) + 21):
        dist = (spot - k) if typ == "put" else (k - spot)  # >0 out of the money
        d = max(0.02, min(0.98, 0.5 - dist * 0.04))
        px = max(0.10, round(0.9 - dist * 0.08, 2))
        sym = f"SPY260929{'P' if typ == 'put' else 'C'}{k * 1000:08d}"
        rows.append({"symbol": sym, "type": typ, "strike": float(k), "bid": px, "ask": round(px + 0.05, 2),
                     "delta": (-d if typ == "put" else d) if delta else None, "iv": 0.2})
    return rows


def _fresh_quotes(lab, rows=None, snaps=None, age_sec=0):
    """Stub lab.quotes (the pre-send re-read) with each leg's current bid/ask, stamped `age_sec` before now."""
    def q(syms):
        now = options_lab.ny_now() - timedelta(seconds=age_sec)
        if snaps is not None:
            return {s: NS(bid_price=snaps[s].latest_quote.bid_price, ask_price=snaps[s].latest_quote.ask_price,
                          timestamp=now) for s in syms}
        by = {r["symbol"]: r for r in rows}
        return {s: NS(bid_price=by[s]["bid"], ask_price=by[s]["ask"], timestamp=now) for s in syms}
    lab.quotes = q


def test_entry_logging_accepts_a_signal_kind(tmp_path, monkeypatch):
    """28 Sept 2026: log(kind, ..., kind=...) raised TypeError and lost the 10:15 checkpoint."""
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.signal = lambda sym: ("put_credit", {"spot": 500.0, "move_60m": 0.1})
    lab.build = lambda sym, kind, spot: (None, "no strike passed the quote filter")
    lab.try_entry("10:15")
    rows = _rows(tmp_path)
    assert [r["event"] for r in rows] == ["signal", "no_trade", "signal", "no_trade"]
    assert rows[0]["kind"] == "put_credit" and rows[1]["why"] == "no strike passed the quote filter"
    assert lab.trades == []


# --- expiry selection ----------------------------------------------------------------------------------------------
def test_0dte_picks_today():
    assert options_lab.pick_expiry([TODAY + timedelta(days=2), TODAY, TODAY + timedelta(days=1)], TODAY, "0dte") \
        == (TODAY, "ok")


def test_0dte_refuses_a_later_expiry():
    e, why = options_lab.pick_expiry([TODAY + timedelta(days=1), TODAY + timedelta(days=3)], TODAY, "0dte")
    assert e is None and "no contract expires today" in why and "never falls back" in why


def test_short_mode_keeps_v1_expiry_rule():
    e, _ = options_lab.pick_expiry([TODAY, TODAY + timedelta(days=1), TODAY + timedelta(days=2)], TODAY, "short")
    assert e == TODAY + timedelta(days=2)
    assert options_lab.pick_expiry([TODAY], TODAY, "short")[0] is None


def test_expiry_for_0dte_asks_for_today_and_refuses_tomorrow(tmp_path):
    lab = _bare_lab(tmp_path)
    seen = []
    lab.trading = NS(get_option_contracts=lambda req: seen.append(req) or _contracts(TODAY + timedelta(days=1))(req))
    e, why = lab.expiry_for("SPY")
    assert e is None and "no contract expires today" in why
    assert seen[0].expiration_date == TODAY
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    assert lab.expiry_for("QQQ") == (TODAY, "ok")


def test_no_same_day_expiry_logs_no_trade(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY + timedelta(days=1)))
    lab.signal = lambda sym: ("put_credit", {"spot": 700.0})
    lab.chain = lambda *a: pytest.fail("chain must not be read without a same-day expiry")
    lab.try_entry("10:15")
    rows = [r for r in _rows(tmp_path) if r["event"] == "no_trade"]
    assert len(rows) == 2 and all("no contract expires today" in r["why"] for r in rows)
    assert lab.trades == []


# --- timing --------------------------------------------------------------------------------------------------------
def test_0dte_timing_is_well_before_the_broker_cutoff():
    tm = options_lab.TIMING["0dte"]
    m = options_lab.minutes
    cutoff = min([options_lab.PLANNING_CUTOFF] + list(options_lab.BROKER_0DTE_CUTOFF.values()))
    assert cutoff <= "15:15"  # planned against the stricter published cutoff
    for key in ("last_entry", "open_cancel", "time_exit", "hard_close", "last_resort", "close_by"):
        assert m(tm[key], cutoff) >= 5, key
    assert tm["time_exit"] < tm["hard_close"] < tm["last_resort"] < tm["close_by"]
    assert m(tm["time_exit"], tm["close_by"]) >= 15  # the stepped ladder has time to converge
    assert m(tm["time_exit"], tm["last_resort"]) >= 15
    assert tm["last_entry"] <= "14:15" and max(tm["entry_times"]) <= tm["last_entry"]
    assert tm["open_cancel"] <= tm["time_exit"]
    assert m(tm["close_by"], options_lab.BROKER_0DTE_LIQUIDATION) >= 30
    assert options_lab.EXPIRY_MODE == "0dte"


def test_entries_refused_after_the_last_entry_time(tmp_path, monkeypatch):
    _at(monkeypatch, "14:20")
    lab = _bare_lab(tmp_path)
    lab.signal = lambda sym: pytest.fail("no signal is read after the last entry time")
    lab.try_entry("14:00")
    rows = _rows(tmp_path)
    assert rows[-1]["event"] == "no_trade" and "after the last entry time" in rows[-1]["why"]
    # the order-level lock refuses too
    lab.trading = _paper_trading()
    t = {"long": "SPY260929P00698000", "short": "SPY260929P00700000", "width": 2.0, "max_loss": 100.0, "qty": 1}
    assert "after the last entry time" in lab.check_order(t, "open")
    _at(monkeypatch, "11:30")
    assert lab.check_order(t, "open") == []


def test_0dte_order_lock_refuses_a_later_expiry(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = _paper_trading()
    t = {"long": "SPY260930P00698000", "short": "SPY260930P00700000", "width": 2.0, "max_loss": 100.0, "qty": 1}
    assert any("not today" in w for w in lab.check_order(t, "open"))


def test_half_day_blocks_0dte_entries(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.full_day = None
    lab.trading = NS(get_calendar=lambda req: [NS(date=TODAY, close=datetime(2026, 9, 29, 13, 0))])
    lab.signal = lambda sym: pytest.fail("no signal on a half day")
    lab.try_entry("10:15")
    assert _rows(tmp_path)[-1]["event"] == "no_trade" and lab.full_day is False


# --- journal / trade records ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("mode,tag", [("0dte", "v2-0dte"), ("short", "v1-short")])
def test_version_tag_on_every_journal_row(tmp_path, monkeypatch, mode, tag):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path, mode)
    lab.log("start", dry=True)
    lab.log("signal", kind="put_credit")
    assert [r["lab_version"] for r in _rows(tmp_path)] == [tag, tag]


def test_entry_records_prices_version_and_expectation(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY), **vars(_paper_trading()))
    lab.chain = lambda sym, expiry, spot: _chain(700.0)
    _fresh_quotes(lab, _chain(700.0))
    lab.signal = lambda sym: ("put_credit", {"spot": 700.0})
    lab.try_entry("11:30")
    t = lab.trades[0]
    assert t["id"] == "0929Z1" and t["lab_version"] == "v2-0dte" and t["expiry"] == TODAY.isoformat()
    assert t["open_order"]["status"] == "dry-run" and t["open_order"]["client_order_id"] == "LAB-0929Z1-open-0"
    assert "section 5" in t["backtest_expectation"]
    assert t["minutes_to_broker_cutoff"] == 240 and t["underlying_price"] == 700.0
    entry = next(r for r in _rows(tmp_path) if r["event"] == "entry")
    assert entry["net"] == t["net"] and entry["long"][1:] == [t["long_bid"], t["long_ask"]]
    assert entry["short"][1:] == [t["short_bid"], t["short_ask"]] and entry["minutes_to_broker_cutoff"] == 240
    assert abs(abs(t["short_delta"]) - 0.30) < 0.03  # the ~0.30 delta target is kept
    assert t["max_loss"] <= options_lab.MAX_LOSS_PER_TRADE


# --- greeks --------------------------------------------------------------------------------------------------------
def test_missing_greeks_everywhere_skips_with_reason(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    lab.chain = lambda sym, expiry, spot: _chain(700.0, delta=False)
    t, why = lab.build("SPY", "put_credit", 700.0)
    assert t is None and "has greeks" in why
    skip = [r for r in _rows(tmp_path) if r["event"] == "legs_skipped"]
    assert skip and skip[0]["count"] == 41 and "never guessed" in skip[0]["why"]


def test_missing_greeks_on_some_legs_never_picks_them(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    rows = _chain(700.0)
    best = min(rows, key=lambda r: abs(abs(r["delta"]) - 0.30))
    best["delta"] = None  # the ideal short strike has no greeks: it must be skipped, not treated as delta 0
    lab.chain = lambda sym, expiry, spot: rows
    t, why = lab.build("SPY", "put_credit", 700.0)
    assert why == "ok" and t["short"] != best["symbol"] and t["short_delta"] is not None
    assert any(r["event"] == "legs_skipped" and r["count"] == 1 for r in _rows(tmp_path))


def test_chain_keeps_uncomputable_missing_greeks_as_none(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.underlying_price = lambda sym: 700.0
    q_empty = NS(bid_price=0.0, ask_price=0.05)  # bid 0: no mid to invert
    q_crossed = NS(bid_price=1.1, ask_price=1.1)  # ask not above bid
    q = NS(bid_price=1.0, ask_price=1.1)
    snaps = {"SPY260929P00690000": NS(latest_quote=q_empty, greeks=None, implied_volatility=None),
             "SPY260929C00700000": NS(latest_quote=q_crossed, greeks=NS(delta=None), implied_volatility=None),
             "SPY260929C00701000": NS(latest_quote=q, greeks=NS(delta=0.45), implied_volatility=0.2)}
    lab.options = NS(get_option_chain=lambda req: snaps)
    out = {r["symbol"]: r for r in lab.chain("SPY", TODAY, 700.0)}
    assert {s: r["delta"] for s, r in out.items()} == \
        {"SPY260929P00690000": None, "SPY260929C00700000": None, "SPY260929C00701000": 0.45}
    assert out["SPY260929P00690000"]["delta_why"] == "bid is 0 or missing"
    assert out["SPY260929C00700000"]["delta_why"] == "ask is not above bid"
    assert out["SPY260929C00701000"]["delta_source"] == "alpaca"
    row = next(r for r in _rows(tmp_path) if r["event"] == "delta_computed")
    assert row["alpaca"] == 1 and row["computed"] == 0 and row["none"] == 2 and row["spot_source"] == "latest_trade"


# --- computed delta (Black-Scholes on the mid when the snapshot has no greeks) ------------------------------------
def test_bs_matches_the_textbook_example():
    # Hull, Options Futures and Other Derivatives, example 15.6: S=42, K=40, r=10%, sigma=20%, T=0.5
    # -> call 4.76, put 0.81; d1 = 0.7693 -> call delta N(d1) = 0.7791, put delta = -0.2209.
    kw = dict(r=0.10, q=0.0)
    assert abs(options_lab.bs_price(42, 40, 0.5, 0.2, "call", **kw) - 4.76) < 0.005
    assert abs(options_lab.bs_price(42, 40, 0.5, 0.2, "put", **kw) - 0.81) < 0.005
    assert abs(options_lab.bs_delta(42, 40, 0.5, 0.2, "call", **kw) - 0.7791) < 0.0005
    assert abs(options_lab.bs_delta(42, 40, 0.5, 0.2, "put", **kw) - (-0.2209)) < 0.0005


@pytest.mark.parametrize("typ,price,delta", [("call", 4.76, 0.7791), ("put", 0.81, -0.2209)])
def test_iv_and_delta_recovered_from_a_textbook_price(typ, price, delta):
    iv, why = options_lab.implied_vol(price, 42, 40, 0.5, typ, r=0.10, q=0.0)
    assert why == "ok" and abs(iv - 0.20) < 0.003
    d, iv2, why = options_lab.computed_delta(price - 0.01, price + 0.01, 42, 40, 0.5, typ, r=0.10, q=0.0)
    assert why == "ok" and abs(iv2 - iv) < 1e-6 and abs(d - delta) < 0.003


def test_same_day_put_and_call_round_trip():
    t = options_lab.years_to_expiry(TODAY, datetime(2026, 9, 29, 11, 30, tzinfo=options_lab.NY))
    assert abs(t - 4.5 / (24 * 365)) < 1e-9
    for typ, k in (("put", 698.0), ("call", 702.0)):
        p = options_lab.bs_price(700.0, k, t, 0.15, typ)
        iv, why = options_lab.implied_vol(p, 700.0, k, t, typ)
        assert why == "ok" and abs(iv - 0.15) < 1e-3
        d = options_lab.bs_delta(700.0, k, t, iv, typ)
        assert (d < 0) == (typ == "put") and abs(d - options_lab.bs_delta(700.0, k, t, 0.15, typ)) < 1e-3


def test_time_to_expiry_has_a_floor():
    late = datetime(2026, 9, 29, 16, 30, tzinfo=options_lab.NY)
    assert options_lab.years_to_expiry(TODAY, late) == options_lab.MIN_T_YEARS


def test_iv_solve_gives_up_cleanly():
    # above the price at the 5.0 cap: no IV in range
    iv, why = options_lab.implied_vol(30.0, 700.0, 700.0, 0.0001, "call")
    assert iv is None and "IV above 5.0" in why
    # below the price at the 0.01 floor
    t = 0.5
    floor_px = options_lab.bs_price(700.0, 600.0, t, 0.01, "call")
    iv, why = options_lab.implied_vol(floor_px - 1.0, 700.0, 600.0, t, "call")
    assert iv is None and "IV below 0.01" in why
    # bracketed but not converged within the step limit
    iv, why = options_lab.implied_vol(4.76, 42, 40, 0.5, "call", r=0.10, q=0.0, max_iter=3)
    assert iv is None and "did not converge" in why
    d, iv, why = options_lab.computed_delta(29.9, 30.1, 700.0, 700.0, 0.0001, "call")
    assert d is None and iv is None and "IV above" in why


@pytest.mark.parametrize("typ,k,bid,ask", [("call", 690.0, 9.95, 10.03),   # mid 9.99 < intrinsic 10
                                           ("put", 710.0, 9.99, 10.01)])   # mid 10.00: not a tick above
def test_mid_not_above_intrinsic_gives_no_delta(typ, k, bid, ask):
    d, iv, why = options_lab.computed_delta(bid, ask, 700.0, k, 0.001, typ)
    assert d is None and iv is None and "not a tick above intrinsic" in why


def _snaps_without_greeks(spot=700.0, sigma=0.15, hm=(10, 15), exp="260929"):
    """A same-day SPY chain priced by Black-Scholes at `sigma`, quoted mid +/- 0.02, with NO greeks."""
    t = options_lab.years_to_expiry(TODAY, datetime(2026, 9, 29, *hm, tzinfo=options_lab.NY))
    snaps, true = {}, {}
    for typ in ("put", "call"):
        for k in range(int(spot) - 15, int(spot) + 16):
            p = options_lab.bs_price(spot, float(k), t, sigma, typ)
            mid = round(p, 2)
            sym = f"SPY{exp}{'P' if typ == 'put' else 'C'}{k * 1000:08d}"
            snaps[sym] = NS(latest_quote=NS(bid_price=round(max(0.0, mid - 0.02), 2), ask_price=round(mid + 0.02, 2)),
                            greeks=None, implied_volatility=None)
            true[sym] = options_lab.bs_delta(spot, float(k), t, sigma, typ)
    return snaps, true


@pytest.mark.parametrize("kind,target", [("put_credit", 0.30), ("call_debit", 0.50)])
def test_chain_without_greeks_trades_on_computed_delta(tmp_path, monkeypatch, kind, target):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    lab.underlying_price = lambda sym: 700.0
    snaps, true = _snaps_without_greeks()
    lab.options = NS(get_option_chain=lambda req: snaps)
    t, why = lab.build("SPY", kind, 700.0)
    assert why == "ok" and t["delta_source"] == "computed"
    assert t["short_delta_source"] == "computed" and t["long_delta_source"] == "computed"
    picked = t["short"] if kind.endswith("credit") else t["long"]
    typ = "put" if kind.startswith("put") else "call"
    # the pick is the strike whose TRUE delta is nearest the target (quotes rounded to the cent do not move it)
    best = min((s for s in true if s[9] == typ[0].upper()), key=lambda s: abs(abs(true[s]) - target))
    assert picked == best
    got = t["short_delta"] if kind.endswith("credit") else t["long_delta"]
    assert abs(got - true[picked]) < 0.02 and abs(abs(got) - target) < 0.12
    assert 0.05 < t["short_delta_iv"] < 0.40
    assert t["max_loss"] <= options_lab.MAX_LOSS_PER_TRADE
    row = next(r for r in _rows(tmp_path) if r["event"] == "delta_computed")
    assert row["computed"] > 0 and row["alpaca"] == 0 and row["r"] == options_lab.RISK_FREE_RATE


def test_entry_row_carries_the_delta_source(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY), **vars(_paper_trading()))
    lab.underlying_price = lambda sym: 700.0
    snaps, _ = _snaps_without_greeks()
    lab.options = NS(get_option_chain=lambda req: snaps)
    _fresh_quotes(lab, snaps=snaps)
    lab.signal = lambda sym: ("put_credit", {"spot": 700.0})
    lab.try_entry("10:15")
    entry = next(r for r in _rows(tmp_path) if r["event"] == "entry")
    assert entry["delta_source"] == "computed" and entry["short_delta_source"] == "computed"
    assert lab.trades[0]["delta_source"] == "computed"


def test_alpaca_delta_preferred_when_present(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    lab.underlying_price = lambda sym: 700.0
    snaps, true = _snaps_without_greeks()
    # Alpaca greeks on every put, deliberately different from what the quotes imply: they must win.
    for sym, s in snaps.items():
        if sym[9] == "P":
            s.greeks = NS(delta=round(true[sym] * 0.5, 4))
    lab.options = NS(get_option_chain=lambda req: snaps)
    rows = {r["symbol"]: r for r in lab.chain("SPY", TODAY, 700.0)}
    puts = [r for s, r in rows.items() if s[9] == "P"]
    usable = [r for r in puts if round(true[r["symbol"]] * 0.5, 4) != 0]
    assert usable and all(r["delta_source"] == "alpaca" and r["delta"] == round(true[r["symbol"]] * 0.5, 4)
                          for r in usable)
    # a 0.0 Alpaca delta (deep OTM, rounded) is not usable: it is never taken as-is (round 2 finding 7)
    assert all(r.get("alpaca_delta_rejected") and r["delta_source"] != "alpaca" for r in puts if r not in usable)
    assert any(r["delta_source"] == "computed" for s, r in rows.items() if s[9] == "C")
    lab.chain = lambda sym, expiry, spot: list(rows.values())
    t, why = lab.build("SPY", "put_credit", 700.0)
    assert why == "ok" and t["delta_source"] == "alpaca" and t["short_delta"] == rows[t["short"]]["delta"]


def test_chain_falls_back_to_the_bar_spot_when_the_trade_read_fails(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.underlying_price = lambda sym: None
    snaps, _ = _snaps_without_greeks()
    lab.options = NS(get_option_chain=lambda req: snaps)
    out = lab.chain("SPY", TODAY, 700.0)
    assert any(r["delta_source"] == "computed" for r in out)
    row = next(r for r in _rows(tmp_path) if r["event"] == "delta_computed")
    assert row["spot_source"] == "minute_bar_close" and row["spot"] == 700.0


def test_computed_delta_keeps_the_quote_filter(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    lab.underlying_price = lambda sym: 700.0
    snaps, _ = _snaps_without_greeks()
    for s in snaps.values():  # every quote 0.30 wide: deltas compute, but no leg may be traded
        q = s.latest_quote
        q.ask_price = round(q.bid_price + 0.30, 2) if q.bid_price > 0 else q.ask_price
    lab.options = NS(get_option_chain=lambda req: snaps)
    t, why = lab.build("SPY", "put_credit", 700.0)
    assert t is None and "quote too wide" in why


# --- caps ----------------------------------------------------------------------------------------------------------
def test_caps_and_locks_unchanged():
    assert options_lab.MAX_LOSS_PER_TRADE == 250.0 and options_lab.MAX_LOSS_TOTAL == 750.0
    assert options_lab.MAX_OPENS == 4 and options_lab.MAX_QUOTE_SPREAD == 0.20
    assert options_lab.UNDERLYINGS == ("SPY", "QQQ") and options_lab.PREFIX == "LAB-"
    assert options_lab.TIMING["short"]["close_by"] == "15:50" and options_lab.TIMING["short"]["time_exit"] == "15:35"


def test_wide_quote_leg_is_not_traded(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    rows = _chain(700.0)
    for r in rows:
        r["ask"] = round(r["bid"] + 0.30, 2)
    lab.chain = lambda sym, expiry, spot: rows
    t, why = lab.build("SPY", "put_credit", 700.0)
    assert t is None and "quote too wide" in why


def test_total_cap_room_limits_size(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    lab.chain = lambda sym, expiry, spot: _chain(700.0)
    lab.trades = [{"status": "open", "max_loss": 740.0}]
    t, why = lab.build("SPY", "put_credit", 700.0)
    assert t is None and "remaining room" in why


# =================================================================================================================
# Review fixes (v2-0dte review, 28 Sept 2026)
# =================================================================================================================
import subprocess
import sys
import time as _time

LONG, SHORT = "SPY260929P00698000", "SPY260929P00700000"


class FakeTrading:
    """A paper TradingClient stand-in: records every order request; order states and positions are scripted."""

    _base_url = "https://paper-api.alpaca.markets"

    def __init__(self, positions=None, states=None, submit_error=None, lookup=None):
        self.sent, self.cancelled, self.positions = [], [], positions
        self.states = list(states or [])
        self.submit_error, self.lookup = submit_error, lookup

    def submit_order(self, req):
        self.sent.append(req)
        if self.submit_error:
            raise self.submit_error
        return NS(id=f"o{len(self.sent)}", status=NS(value="new"), qty=req.qty, legs=None)

    def get_order_by_client_id(self, cid):
        if isinstance(self.lookup, Exception):
            raise self.lookup
        if self.lookup is None:
            raise ConnectionError("lookup down")
        return self.lookup

    def get_order_by_id(self, oid):
        st, filled, px = self.states.pop(0) if self.states else ("new", 0, None)
        return NS(status=NS(value=st), filled_qty=filled, filled_avg_price=px)

    def cancel_order_by_id(self, oid):
        self.cancelled.append(oid)

    def get_all_positions(self):
        if isinstance(self.positions, Exception):
            raise self.positions
        return [NS(symbol=s, qty=str(q), side=NS(value="long" if q > 0 else "short"))
                for s, q in (self.positions or {}).items()]


def _open_trade(credit=True, qty=2, entry=0.60, **kw):
    t = {"id": "0929Z1", "underlying": "SPY", "kind": "put_credit" if credit else "put_debit", "type": "put",
         "credit": credit, "long": LONG, "short": SHORT, "long_strike": 698.0, "short_strike": 700.0,
         "width": 2.0, "qty": qty, "net": entry, "entry_net": entry, "status": "open", "opened": True,
         "exit_cost_pc": 0.10, "max_loss": round(((2.0 - entry) if credit else entry) * 100 * qty + 10 * qty, 2)}
    t.update(kw)
    return t


def _live_lab(tmp_path, monkeypatch, hm, trading, mode="0dte", quote=None, spot=705.0):
    _at(monkeypatch, hm)
    lab = _bare_lab(tmp_path, mode)
    lab.dry, lab.trading = False, trading
    lab.spread_mid = (lambda t: quote) if not callable(quote) else quote
    lab.underlying_price = lambda sym: spot
    return lab


def _limit(req):
    return abs(float(req.limit_price))


# --- finding 1: flat before Alpaca's 15:00 sell-out window, positions checked, leg-by-leg fallback ---------------
def test_0dte_timing_pinned_and_flat_before_the_sellout_window():
    assert options_lab.TIMING["0dte"] == {
        "entry_times": ("10:15", "11:30", "12:15", "13:15"), "last_entry": "13:30", "open_cancel": "13:45",
        "time_exit": "14:00", "hard_close": "14:20", "last_resort": "14:30", "close_by": "14:40"}
    assert options_lab.BROKER_0DTE_SELLOUT == "15:00" and options_lab.PLANNING_CUTOFF == "15:00"
    assert options_lab.minutes(options_lab.TIMING["0dte"]["close_by"], options_lab.BROKER_0DTE_SELLOUT) >= 20


def test_short_timing_pinned_to_v1():
    assert options_lab.TIMING["short"] == {
        "entry_times": ("10:15", "11:30", "13:00", "14:15"), "last_entry": "14:30", "open_cancel": "14:45",
        "time_exit": "15:35", "hard_close": "15:45", "last_resort": "15:48", "close_by": "15:50"}


def test_one_leg_sold_out_by_broker_legs_out_short_first(tmp_path, monkeypatch):
    fake = FakeTrading(positions={SHORT: -2})  # the long leg is gone (sold out by the broker)
    lab = _live_lab(tmp_path, monkeypatch, "14:05", fake, quote=(1.5, 1.6))
    t = _open_trade()
    lab.trades = [t]
    lab.manage()  # 1st read: mismatch noted, no two-leg close sent
    assert t["status"] == "open" and fake.sent == [] and t["leg_mismatch_hits"] == 1
    lab.manage()  # 2nd read agrees: switch to leg-by-leg
    assert t["status"] == "legging_out" and t["legs_left"] == {"short": 2, "long": 0} and fake.sent == []
    lab.quotes = lambda syms: {syms[0]: NS(bid_price=1.9, ask_price=2.0)}
    lab.manage()  # buy back the naked short leg
    req = fake.sent[-1]
    assert req.symbol == SHORT and req.side.value == "buy" and req.position_intent.value == "buy_to_close"
    assert req.qty == 2 and _limit(req) == 2.05 and req.client_order_id == "LAB-0929Z1-legshort-0"
    fake.states = [("filled", 2, 2.02)]
    lab.manage()
    assert t["legs_left"] == {"short": 0, "long": 0}
    lab.manage()
    assert t["status"] == "closed" and t["pnl"] == round(0.60 * 100 * 2 - 2.02 * 100 * 2, 2) and t["pnl_incomplete"]
    assert any(r["event"] == "ALERT_LEG_OUT" for r in _rows(tmp_path))


def test_leg_out_sells_long_only_after_short_is_bought_back(tmp_path, monkeypatch):
    fake = FakeTrading()
    lab = _live_lab(tmp_path, monkeypatch, "14:41", fake)
    t = _open_trade(status="legging_out", legs_left={"short": 2, "long": 2}, leg_qty=2, leg_cash=0.0,
                    leg_attempts=0, leg_order=None)
    assert any("never a naked short" in w for w in lab.check_leg(t, "long", 2))
    lab.quotes = lambda syms: {syms[0]: NS(bid_price=1.0, ask_price=1.1)}
    lab.trades = [t]
    lab.manage()
    assert fake.sent[-1].symbol == SHORT
    fake.states = [("filled", 2, 1.1)]
    lab.manage()
    lab.manage()  # now the long leg
    req = fake.sent[-1]
    assert req.symbol == LONG and req.side.value == "sell" and req.position_intent.value == "sell_to_close"
    fake.states = [("filled", 2, 0.4)]
    lab.manage()
    lab.manage()
    assert t["status"] == "closed" and t["pnl"] == round((0.60 - 1.1 + 0.4) * 200, 2)


def test_two_leg_close_rejected_repeatedly_legs_out(tmp_path, monkeypatch):
    fake = FakeTrading(positions={LONG: 2, SHORT: -2})
    lab = _live_lab(tmp_path, monkeypatch, "14:05", fake, quote=(1.0, 1.1))
    t = _open_trade()
    lab.trades = [t]
    for _ in range(options_lab.CLOSE_FAILS_TO_LEG_OUT):
        lab.manage()  # sends a two-leg close
        assert t["status"] == "pending_close"
        fake.states = [("rejected", 0, None)]
        lab.manage()  # rejected: back to open
    lab.manage()
    assert t["status"] == "legging_out" and "rejected" in t["leg_out_reason"]


def test_still_open_at_close_by_legs_out(tmp_path, monkeypatch):
    fake = FakeTrading(positions={LONG: 2, SHORT: -2})
    lab = _live_lab(tmp_path, monkeypatch, options_lab.TIMING["0dte"]["close_by"], fake, quote=(1.0, 1.1))
    t = _open_trade(exit_reason="time exit before the 0DTE cutoff", close_attempts=9)
    lab.trades = [t]
    lab.manage()
    assert t["status"] == "legging_out" and t["legs_left"] == {"short": 2, "long": 2}


def test_positions_unreadable_still_sends_two_leg_close(tmp_path, monkeypatch):
    fake = FakeTrading(positions=ConnectionError("down"))
    lab = _live_lab(tmp_path, monkeypatch, "14:05", fake, quote=(1.0, 1.1))
    t = _open_trade()
    lab.trades = [t]
    lab.manage()
    assert t["status"] == "pending_close" and len(fake.sent[-1].legs) == 2


# --- finding 2: an open whose send result is lost stays live and counts -------------------------------------------
def _entry_lab(tmp_path, monkeypatch, fake):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.dry, lab.trading = False, fake
    fake.get_option_contracts = _contracts(TODAY)
    lab.chain = lambda sym, expiry, spot: _chain(700.0)
    _fresh_quotes(lab, _chain(700.0))
    lab.signal = lambda sym: ("put_credit", {"spot": 700.0})
    return lab


def test_open_send_failed_stays_live_counts_and_is_found_later(tmp_path, monkeypatch):
    fake = FakeTrading(submit_error=TimeoutError("read timeout"))
    lab = _entry_lab(tmp_path, monkeypatch, fake)
    lab.try_entry("11:30")
    t = lab.trades[0]
    assert t["status"] == "pending_open" and t["opened"] and "id" not in t["open_order"]
    assert t["status"] in options_lab.LIVE and t["max_loss"] > 0
    # it counts toward the total cap
    other = {"long": LONG, "short": SHORT, "width": 2.0, "qty": 1,
             "max_loss": options_lab.MAX_LOSS_TOTAL - t["max_loss"] + 1}
    assert "over the total cap" in lab.check_order(other, "open")
    # next pass: found by client id and managed
    fake.lookup = NS(id="real-1", status=NS(value="new"), qty=t["qty"], legs=[NS(symbol=t["long"]),
                                                                              NS(symbol=t["short"])])
    lab.manage()
    assert t["open_order"]["id"] == "real-1" and t["status"] == "pending_open"
    fake.states = [("filled", t["qty"], 0.5)]
    lab.manage()
    assert t["status"] == "open"


def test_open_send_failed_confirmed_absent_after_grace(tmp_path, monkeypatch):
    fake = FakeTrading(submit_error=TimeoutError("read timeout"))
    lab = _entry_lab(tmp_path, monkeypatch, fake)
    lab.try_entry("11:30")
    t = lab.trades[0]
    fake.lookup = RuntimeError('{"message":"order not found"}')
    lab.manage()
    assert t["status"] == "pending_open"  # too soon to call it absent
    t["sent_at"] = _time.time() - options_lab.OPEN_LOOKUP_GRACE_SEC - 1
    lab.manage()
    assert t["status"] == "send_failed" and not t["opened"]


def test_max_opens_counts_unknown_and_pending(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = _paper_trading()
    lab.trades = [{"status": "closed", "opened": True, "max_loss": 0}] * 3 + [{"status": "pending_open", "max_loss": 1}]
    t = {"long": LONG, "short": SHORT, "width": 2.0, "max_loss": 100.0, "qty": 1}
    assert "max opens reached" in lab.check_order(t, "open")


# --- finding 3: quote / account API errors never block the final close --------------------------------------------
def test_quote_api_error_still_sends_last_resort_close(tmp_path, monkeypatch):
    fake = FakeTrading(positions={LONG: 2, SHORT: -2})
    lab = _live_lab(tmp_path, monkeypatch, options_lab.TIMING["0dte"]["last_resort"], fake)
    del lab.spread_mid  # use the real one with a raising quote client
    lab.options = NS(get_option_latest_quote=lambda req: (_ for _ in ()).throw(ConnectionError("429")))
    t = _open_trade(close_attempts=8, exit_reason="time exit before the 0DTE cutoff")
    lab.trades = [t]
    lab.manage()
    assert t["status"] == "pending_close" and _limit(fake.sent[-1]) == 2.0
    assert any(r["event"] == "quote_error" for r in _rows(tmp_path))


def test_close_makes_no_account_call(tmp_path, monkeypatch):
    fake = FakeTrading()
    fake.get_account = lambda: (_ for _ in ()).throw(ConnectionError("account down"))
    lab = _live_lab(tmp_path, monkeypatch, "14:05", fake)
    r = lab.send(_open_trade(), "close", 1.0)
    assert r["status"] == "new" and len(fake.sent) == 1


# --- finding 4: last-resort credit close can bid above the width, inside the trade's budget ------------------------
def test_last_resort_credit_close_bids_through_width_within_budget(tmp_path, monkeypatch):
    _at(monkeypatch, options_lab.TIMING["0dte"]["last_resort"])
    lab = _bare_lab(tmp_path)
    t = _open_trade(close_attempts=5)
    px = lab.close_limit(t, 2.01, 2.12)
    assert px == 2.10  # natural + 0.05 = 2.17, capped at width + exit budget 0.10
    assert (px - t["entry_net"]) * 100 * t["qty"] <= t["max_loss"] + 1e-6
    assert lab.close_limit(t, 1.2, 1.3) == 2.0  # never below the width at last resort (old behaviour kept)
    assert lab.close_limit(_open_trade(credit=False, close_attempts=5), 0.5, 0.4) == 0.01
    _at(monkeypatch, options_lab.TIMING["0dte"]["hard_close"])
    assert lab.close_limit(t, 2.01, 2.12) == 2.0  # before last resort: never above the width


# --- finding 5: write-ahead, and a found order with other legs is never adopted -------------------------------------
def test_trade_is_saved_before_the_open_order_is_sent(tmp_path, monkeypatch):
    fake = FakeTrading()
    seen = []
    orig = fake.submit_order
    fake.submit_order = lambda req: seen.append(json.loads((tmp_path / "trades.json").read_text())) or orig(req)
    lab = _entry_lab(tmp_path, monkeypatch, fake)
    lab.try_entry("11:30")
    assert seen and seen[0][0]["id"] == "0929Z1" and seen[0][0]["status"] == "pending_open"
    assert seen[0][0]["open_order"]["client_order_id"] == "LAB-0929Z1-open-0"
    assert lab.trades[0]["open_order"]["id"] == "o1"


def test_duplicate_client_id_with_other_legs_is_not_adopted(tmp_path, monkeypatch):
    old = NS(id="real-order-1", status=NS(value="filled"), qty="3",
             legs=[NS(symbol="QQQ260929C00600000"), NS(symbol="QQQ260929C00602000")])
    fake = FakeTrading(submit_error=RuntimeError("client_order_id must be unique"), lookup=old)
    lab = _entry_lab(tmp_path, monkeypatch, fake)
    lab.try_entry("11:30")
    t = lab.trades[0]
    assert t["status"] == "id_conflict" and "id" not in t["open_order"]
    assert t["status"] in options_lab.CAP_STATUSES
    assert any(r["event"] == "ALERT_ID_CONFLICT" for r in _rows(tmp_path))


# --- finding 6: a working 0dte opening order is cancelled after OPEN_TTL_SEC -------------------------------------
def test_0dte_open_order_cancelled_after_ttl(tmp_path, monkeypatch):
    fake = FakeTrading(states=[("partially_filled", 1, 0.6)] * 2)
    lab = _live_lab(tmp_path, monkeypatch, "10:20", fake)
    t = _open_trade(status="pending_open", qty=3, open_order={"id": "o9"}, sent_at=_time.time() - 60)
    lab.trades = [t]
    lab.manage()
    assert fake.cancelled == []
    t["sent_at"] = _time.time() - options_lab.OPEN_TTL_SEC["0dte"] - 1
    lab.manage()
    assert fake.cancelled == ["o9"]
    fake.states = [("canceled", 1, 0.6)]
    lab.manage()
    assert t["status"] == "open" and t["qty"] == 1


def test_short_mode_open_order_waits_for_open_cancel(tmp_path, monkeypatch):
    fake = FakeTrading()
    lab = _live_lab(tmp_path, monkeypatch, "10:20", fake, mode="short")
    t = _open_trade(status="pending_open", open_order={"id": "o9"}, sent_at=_time.time() - 3600)
    lab.trades = [t]
    lab.manage()
    assert fake.cancelled == []


# --- finding 8: 0dte exit timing, the order-time caps and the short-mode locks ---------------------------------
def test_0dte_time_exit_sends_a_close(tmp_path, monkeypatch):
    fake = FakeTrading(positions={LONG: 2, SHORT: -2})
    tm = options_lab.TIMING["0dte"]
    lab = _live_lab(tmp_path, monkeypatch, "13:59", fake, quote=(1.3, 1.4))
    t = _open_trade()
    lab.trades = [t]
    lab.manage()
    assert fake.sent == [] and t["status"] == "open"
    _at(monkeypatch, tm["time_exit"])
    lab.manage()
    assert t["status"] == "pending_close" and t["exit_reason"] == "time exit before the 0DTE cutoff"
    assert _limit(fake.sent[-1]) == 1.33  # mid + first step


def test_0dte_hard_close_goes_through_natural(tmp_path, monkeypatch):
    _at(monkeypatch, options_lab.TIMING["0dte"]["hard_close"])
    lab = _bare_lab(tmp_path)
    assert lab.close_limit(_open_trade(), 1.30, 1.45) == 1.55  # natural + 0.10
    assert lab.close_limit(_open_trade(credit=False), 1.30, 1.20) == 1.10
    _at(monkeypatch, "14:19")
    assert lab.close_limit(_open_trade(), 1.30, 1.45) == 1.33


@pytest.mark.parametrize("credit,expect", [(True, 2.0), (False, 0.01)])
def test_0dte_last_resort_without_quote(tmp_path, monkeypatch, credit, expect):
    fake = FakeTrading(positions={LONG: 2, SHORT: -2})
    lab = _live_lab(tmp_path, monkeypatch, options_lab.TIMING["0dte"]["last_resort"], fake, quote=None)
    t = _open_trade(credit=credit, exit_reason="time exit before the 0DTE cutoff", close_attempts=4)
    lab.trades = [t]
    lab.manage()
    assert t["status"] == "pending_close" and _limit(fake.sent[-1]) == expect


def test_0dte_pending_open_cancelled_at_open_cancel(tmp_path, monkeypatch):
    fake = FakeTrading()
    lab = _live_lab(tmp_path, monkeypatch, options_lab.TIMING["0dte"]["open_cancel"], fake)
    t = _open_trade(status="pending_open", open_order={"id": "o7"}, sent_at=_time.time())
    lab.trades = [t]
    lab.manage()
    assert fake.cancelled == ["o7"]


def test_order_caps_refuse(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = _paper_trading()
    t = {"long": LONG, "short": SHORT, "width": 2.0, "qty": 1, "max_loss": 250.01}
    assert "over the per-trade cap" in lab.check_order(t, "open")
    t["max_loss"] = 200.0
    lab.trades = [{"status": "open", "max_loss": 300.0}, {"status": "pending_close", "max_loss": 251.0}]
    assert "over the total cap" in lab.check_order(t, "open")
    lab.trades = [{"status": "closed", "opened": True, "max_loss": 0.0}] * 4
    assert "max opens reached" in lab.check_order(t, "open")
    lab.trades = [{"status": "closed", "opened": True, "max_loss": 0.0}] * 3
    assert lab.check_order(t, "open") == []


def test_short_mode_dte_lock(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path, "short")
    lab.trading = _paper_trading()
    t = {"long": LONG, "short": SHORT, "width": 2.0, "qty": 1, "max_loss": 100.0}  # today: 0 DTE
    assert any("outside 1-10" in w for w in lab.check_order(t, "open"))
    t.update(long="SPY261001P00698000", short="SPY261001P00700000")
    assert lab.check_order(t, "open") == []
    t.update(long="SPY261012P00698000", short="SPY261012P00700000")
    assert any("outside 1-10" in w for w in lab.check_order(t, "open"))


def test_short_mode_ids_and_expiry_request(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path, "short")
    seen = []
    exp = TODAY + timedelta(days=2)
    lab.trading = NS(get_option_contracts=lambda req: seen.append(req) or _contracts(exp)(req),
                     **vars(_paper_trading()))
    rows = _chain(700.0)
    for r in rows:
        r["symbol"] = r["symbol"].replace("260929", "261001")
    lab.chain = lambda sym, expiry, spot: rows
    _fresh_quotes(lab, rows)
    lab.signal = lambda sym: ("put_credit", {"spot": 700.0})
    lab.try_entry("11:30")
    t = lab.trades[0]
    assert t["id"] == "09291" and t["open_order"]["client_order_id"] == "LAB-09291-open-0"
    assert seen[0].expiration_date is None and seen[0].expiration_date_gte == TODAY + timedelta(days=1)
    assert seen[0].expiration_date_lte == TODAY + timedelta(days=10)


def test_entry_row_after_send_with_status_and_fields(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY), **vars(_paper_trading()))
    lab.chain = lambda sym, expiry, spot: _chain(700.0)
    _fresh_quotes(lab, _chain(700.0))
    lab.signal = lambda sym: ("put_credit", {"spot": 700.0})
    lab.trades = [{"status": "closed", "opened": True, "max_loss": 0.0}] * 4  # max opens reached -> refused
    lab.try_entry("11:30")
    ev = [r["event"] for r in _rows(tmp_path)]
    assert ev.index("entry") < ev.index("open_order")
    entry = next(r for r in _rows(tmp_path) if r["event"] == "entry")
    assert entry["order_status"] == "refused" and entry["underlying_price"] == 700.0
    assert entry["minutes_to_close_by"] == options_lab.minutes("11:30", "14:40")
    assert entry["minutes_to_planning_cutoff"] == 210 and entry["quote_feed"] == "indicative"
    assert lab.trades[-1]["quote_feed"] == "indicative"


# --- finding 10: greek-less partner legs --------------------------------------------------------------------------
def _chain_with_greekless_partner():
    rows = _chain(700.0)
    best = min(rows, key=lambda r: abs(abs(r["delta"]) - 0.30))
    partner = next(r for r in rows if r["strike"] == best["strike"] - 2)
    partner["delta"] = None
    return rows, partner


def test_short_mode_drops_greekless_contracts_like_v1(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path, "short")
    lab.trading = NS(get_option_contracts=_contracts(TODAY + timedelta(days=2)))
    rows, _ = _chain_with_greekless_partner()
    lab.chain = lambda sym, expiry, spot: rows
    t, why = lab.build("SPY", "put_credit", 700.0)
    assert t is None and "partner" in why


def test_0dte_greekless_contract_may_be_the_partner(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    rows, partner = _chain_with_greekless_partner()
    lab.chain = lambda sym, expiry, spot: rows
    t, why = lab.build("SPY", "put_credit", 700.0)
    assert why == "ok" and t["long"] == partner["symbol"] and t["long_delta"] is None
    assert t["short_delta"] is not None


# --- finding 11: folders ---------------------------------------------------------------------------------------------
def test_state_folders_stay_under_the_date():
    base = Path("/s")
    assert options_lab.lab_dir(base, TODAY, "0dte", False) == base / "options_lab" / "2026-09-29" / "0dte"
    assert options_lab.lab_dir(base, TODAY, "0dte", True) == base / "options_lab" / "2026-09-29" / "0dte-dry"
    assert options_lab.lab_dir(base, TODAY, "short", False) == base / "options_lab" / "2026-09-29"
    assert options_lab.lab_dir(base, TODAY, "short", True) == base / "options_lab" / "2026-09-29-dry"


# --- finding 14: other mode's live trades, alert text, --expiry validation --------------------------------------
def test_warns_about_live_trades_of_the_other_mode(tmp_path):
    lab = _bare_lab(tmp_path)
    d = options_lab.lab_dir(tmp_path, TODAY, "short", True)
    d.mkdir(parents=True)
    (d / "trades.json").write_text(json.dumps([{"id": "09291", "status": "open"}, {"id": "09292", "status": "closed"}]))
    assert lab.other_mode_live() == ["09291"]


def test_past_close_by_alert_names_the_cutoffs_plainly(tmp_path, monkeypatch):
    _at(monkeypatch, "14:45")
    lab = _bare_lab(tmp_path)
    lab.trades = [_open_trade(status="pending_close")]
    lab.manage = lambda: None

    class Stop(Exception):
        pass

    monkeypatch.setattr(options_lab.time, "sleep", lambda s: (_ for _ in ()).throw(Stop()))
    with pytest.raises(Stop):
        lab.run()
    alert = next(r for r in _rows(tmp_path) if r["event"] == "ALERT_OPEN_PAST_CLOSE_BY")
    assert "SPY 15:30, QQQ 15:30" in alert["note"] and "{" not in alert["note"] and "15:00" in alert["note"]


def test_bad_expiry_argument_is_refused():
    lab_py = Path(__file__).resolve().parent.parent / "lab" / "options_lab.py"
    r = subprocess.run([sys.executable, str(lab_py), "--dry", "--expiry", "weekly"], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin"}, timeout=60)
    assert r.returncode != 0 and "--expiry must be one of" in r.stderr


# =================================================================================================================
# Round 2 review fixes (28 Sept 2026)
# =================================================================================================================
class _HTTPErr(Exception):
    """Stands in for alpaca's APIError: carries the HTTP status code of Alpaca's answer."""

    def __init__(self, status_code, msg="refused"):
        super().__init__(msg)
        self.status_code = status_code


def _legging(qty=2, **kw):
    t = _open_trade(qty=qty, status="legging_out", legs_left={"short": qty, "long": qty}, leg_qty=qty, leg_cash=0.0,
                    leg_attempts=0, leg_order=None, leg_max_loss=_open_trade(qty=qty)["max_loss"])
    t.update(kw)
    return t


# --- R2 finding 1 / 10: a single-leg close refused at submit time no longer loops forever ------------------------
def test_leg_send_refused_at_submit_clamps_to_account_and_sells_the_long(tmp_path, monkeypatch):
    fake = FakeTrading(positions={LONG: 2}, lookup=_HTTPErr(404, '{"message":"order not found"}'))
    orig = fake.submit_order

    def submit(req):  # buy_to_close of the (gone) short is refused with a 403; the long sale is accepted
        if getattr(req, "symbol", None) == SHORT:
            fake.sent.append(req)
            raise _HTTPErr(403, "insufficient qty")
        return orig(req)

    fake.submit_order = submit
    lab = _live_lab(tmp_path, monkeypatch, "14:41", fake)
    lab.quotes = lambda syms: {syms[0]: NS(bid_price=1.0, ask_price=1.1)}
    t = _legging()
    lab.trades = [t]
    for _ in range(3):
        lab.manage()
    shorts = [r for r in fake.sent if r.symbol == SHORT]
    # no order was created (4xx + 404): each retry uses a new client id and a bigger step
    assert [r.client_order_id for r in shorts] == [f"LAB-0929Z1-legshort-{i}" for i in range(3)]
    assert _limit(shorts[1]) > _limit(shorts[0])
    # two reads in a row show no short: legs_left lowered, and the long leg is sold on the next pass
    assert t["legs_left"] == {"short": 0, "long": 2} and t["pnl_incomplete"]
    lab.manage()
    req = fake.sent[-1]
    assert req.symbol == LONG and req.side.value == "sell" and req.qty == 2
    fake.states = [("filled", 2, 0.9)]
    lab.manage()
    lab.manage()
    assert t["status"] == "closed"
    assert any(r["event"] == "legs_clamped" for r in _rows(tmp_path))
    assert not any(r["event"] == "error" for r in _rows(tmp_path))


def test_leg_send_unknown_keeps_client_id_and_one_empty_read_never_clamps(tmp_path, monkeypatch):
    # submit times out and the lookup is down: the order MAY exist, so the client id is reused (Alpaca refuses a dupe)
    fake = FakeTrading(positions={}, submit_error=TimeoutError("read timeout"), lookup=ConnectionError("down"))
    lab = _live_lab(tmp_path, monkeypatch, "14:41", fake)
    lab.quotes = lambda syms: {syms[0]: NS(bid_price=1.0, ask_price=1.1)}
    t = _legging()
    lab.trades = [t]
    lab.manage()
    lab.manage()  # 2nd failure: 1st read (empty) is stored, not acted on
    assert t["legs_left"] == {"short": 2, "long": 2}
    fake.positions = {LONG: 2, SHORT: -2}
    lab.manage()  # 3rd: this read shows the short: the max of the two reads keeps legs_left
    lab.manage()  # 4th: alert
    assert t["legs_left"] == {"short": 2, "long": 2} and not t.get("pnl_incomplete")
    assert {r.client_order_id for r in fake.sent} == {"LAB-0929Z1-legshort-0"} and t["leg_attempts"] == 0
    assert all(r.symbol == SHORT for r in fake.sent)
    assert any(r["event"] == "ALERT_LEG_STUCK" for r in _rows(tmp_path))
    assert not any(r["event"] == "error" for r in _rows(tmp_path))


def test_leg_send_success_resets_the_failure_count(tmp_path, monkeypatch):
    fake = FakeTrading(positions={LONG: 2, SHORT: -2}, submit_error=TimeoutError("t"), lookup=ConnectionError("d"))
    lab = _live_lab(tmp_path, monkeypatch, "14:41", fake)
    lab.quotes = lambda syms: {syms[0]: NS(bid_price=1.0, ask_price=1.1)}
    t = _legging()
    lab.trades = [t]
    lab.manage()
    assert t["leg_send_fails"] == 1
    fake.submit_error = None
    lab.manage()
    assert t["leg_send_fails"] == 0 and t["leg_order"]["id"]


# --- R2 finding 2 / 11: no two live lab trades share an option symbol ---------------------------------------------
def test_new_trade_sharing_a_symbol_with_a_live_trade_is_refused(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY), **vars(_paper_trading()))
    lab.chain = lambda sym, expiry, spot: _chain(700.0)
    b, why = lab.build("SPY", "put_credit", 700.0)
    assert why == "ok"
    # live trade A is short B's long strike (the 10:15 / 11:30 up-day case): Alpaca would net it to zero
    a = {"id": "0929Z1", "status": "open", "max_loss": 150.0, "long": "SPY260929P00690000", "short": b["long"]}
    lab.trades = [a]
    t, why = lab.build("SPY", "put_credit", 700.0)
    assert t is None and "already a leg of a live lab trade" in why
    b.update({"qty": 1})
    assert any("already a leg of a live lab trade" in w for w in lab.check_order(b, "open"))
    a["status"] = "closed"  # a closed trade holds nothing: no refusal
    assert lab.build("SPY", "put_credit", 700.0)[1] == "ok" and lab.check_order(b, "open") == []


# --- R2 finding 3: the leg-out path is uncapped: its closed row says how it did against max_loss ---------------
def test_leg_out_close_reports_loss_against_max_loss(tmp_path, monkeypatch):
    fake = FakeTrading()
    lab = _live_lab(tmp_path, monkeypatch, "14:41", fake)
    t = _legging(qty=1, legs_left={"short": 0, "long": 0}, leg_cash=round(-6.10 * 100 + 0.01 * 100, 2),
                 leg_max_loss=150.0)
    lab.trades = [t]
    lab.manage()
    assert t["status"] == "closed" and t["leg_out_pnl"] == -549.0 and t["leg_out_over_max_loss"]
    closed = next(r for r in _rows(tmp_path) if r["event"] == "closed")
    assert closed["max_loss"] == 150.0 and closed["over_max_loss"] is True
    assert any(r["event"] == "ALERT_LEG_OUT_OVER_MAX_LOSS" for r in _rows(tmp_path))
    assert "NOT capped" in options_lab.__doc__


# --- R2 finding 4: the two-reads rule needs two reads IN A ROW ---------------------------------------------------
def test_unreadable_positions_reset_the_mismatch_count(tmp_path, monkeypatch):
    fake = FakeTrading(positions={SHORT: -2})
    lab = _live_lab(tmp_path, monkeypatch, "14:05", fake)
    t = _open_trade()
    assert lab.legs_ok(t) is False and t["leg_mismatch_hits"] == 1
    fake.positions = ConnectionError("down")
    assert lab.legs_ok(t) is True and t["leg_mismatch_hits"] == 0
    fake.positions = {SHORT: -2}
    assert lab.legs_ok(t) is False and t["status"] == "open" and t["leg_mismatch_hits"] == 1


# --- R2 finding 5: an empty positions read never abandons a trade ------------------------------------------------
def test_two_empty_reads_keep_the_trade_live_until_close_by(tmp_path, monkeypatch):
    fake = FakeTrading(positions={})
    lab = _live_lab(tmp_path, monkeypatch, "14:05", fake, quote=(1.5, 1.6))
    t = _open_trade()
    lab.trades = [t]
    lab.manage()
    lab.manage()
    assert t["status"] == "verify_gone" and t["status"] in options_lab.LIVE and t["qty"] == 2 and fake.sent == []
    lab.manage()
    assert t["status"] == "verify_gone"
    fake.positions = {LONG: 2, SHORT: -2}  # the empty reads were wrong: managed again
    lab.manage()
    assert t["status"] == "open" and any(r["event"] == "ALERT_LEGS_BACK" for r in _rows(tmp_path))
    lab.manage()
    assert t["status"] == "pending_close" and len(fake.sent[-1].legs) == 2


def test_empty_reads_close_the_trade_only_at_close_by(tmp_path, monkeypatch):
    fake = FakeTrading(positions={})
    lab = _live_lab(tmp_path, monkeypatch, options_lab.TIMING["0dte"]["close_by"], fake, quote=(1.5, 1.6))
    t = _open_trade(exit_reason="time exit before the 0DTE cutoff", close_attempts=9)
    lab.trades = [t]
    lab.manage()  # close_by: start_leg_out reads an empty account -> verify_gone, not closed on one read
    assert t["status"] == "verify_gone" and fake.sent == []
    fake.positions = ConnectionError("down")
    lab.manage()
    assert t["status"] == "verify_gone"
    fake.positions = {}
    lab.manage()
    assert t["status"] == "closed" and t["pnl_incomplete"] and t["qty"] == 0 and fake.sent == []
    assert any(r["event"] == "ALERT_LEGS_GONE_CONFIRMED" for r in _rows(tmp_path))


# --- R2 finding 7: an unusable Alpaca delta is never taken as-is -------------------------------------------------
def test_unusable_alpaca_deltas_are_replaced_by_computed_ones(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.underlying_price = lambda sym: 700.0
    snaps, true = _snaps_without_greeks()
    bad = {"SPY260929P00698000": float("nan"), "SPY260929P00697000": 0.0, "SPY260929P00696000": 0.3,
           "SPY260929C00702000": -0.4, "SPY260929C00703000": 1.0}
    for sym, d in bad.items():
        snaps[sym].greeks = NS(delta=d)
    snaps["SPY260929P00695000"].greeks = NS(delta=-0.12)  # a usable one is kept
    lab.options = NS(get_option_chain=lambda req: snaps)
    rows = {r["symbol"]: r for r in lab.chain("SPY", TODAY, 700.0)}
    for sym in bad:
        assert rows[sym]["delta_source"] == "computed" and rows[sym]["alpaca_delta_rejected"]
        assert abs(rows[sym]["delta"] - true[sym]) < 0.02
    assert rows["SPY260929P00695000"]["delta"] == -0.12 and rows["SPY260929P00695000"]["delta_source"] == "alpaca"
    row = next(r for r in _rows(tmp_path) if r["event"] == "delta_computed")
    assert set(row["alpaca_delta_rejected"]) == set(bad)
    assert all(options_lab.math.isfinite(r["delta"]) for r in rows.values() if r["delta"] is not None)


# --- R2 finding 8: a computed delta can be reproduced from the trade record --------------------------------------
def test_trade_records_the_delta_inputs(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    lab.underlying_price = lambda sym: 700.0
    snaps, _ = _snaps_without_greeks()
    lab.options = NS(get_option_chain=lambda req: snaps)
    t, why = lab.build("SPY", "put_credit", 699.5)
    assert why == "ok" and t["delta_spot"] == 700.0 and t["delta_spot_source"] == "latest_trade"
    tt = options_lab.years_to_expiry(TODAY, datetime(2026, 9, 29, 10, 15, tzinfo=options_lab.NY))
    assert t["delta_t_years"] == tt  # full precision
    iv, _ = options_lab.implied_vol((t["short_bid"] + t["short_ask"]) / 2, t["delta_spot"], t["short_strike"],
                                    t["delta_t_years"], "put")
    assert round(options_lab.bs_delta(700.0, t["short_strike"], tt, iv, "put"), 4) == t["short_delta"]
    assert "short_alpaca_iv" in t and "long_alpaca_iv" in t
    row = next(r for r in _rows(tmp_path) if r["event"] == "delta_computed")
    assert row["t_years"] == tt and row["minutes_to_expiry"] == 345.0


# --- R2 finding 9: test gaps ---------------------------------------------------------------------------------------
def test_chain_uses_the_live_trade_not_the_bar_for_the_delta(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.underlying_price = lambda sym: 701.0
    snaps, _ = _snaps_without_greeks(spot=701.0)
    lab.options = NS(get_option_chain=lambda req: snaps)
    lab.chain("SPY", TODAY, 700.0)
    row = next(r for r in _rows(tmp_path) if r["event"] == "delta_computed")
    assert row["spot"] == 701.0 and row["spot_source"] == "latest_trade"


def test_call_debit_delta_source_is_the_selected_legs(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    lab.underlying_price = lambda sym: 700.0
    snaps, _ = _snaps_without_greeks()
    lab.options = NS(get_option_chain=lambda req: snaps)
    t0, _ = lab.build("SPY", "call_debit", 700.0)
    snaps[t0["short"]].greeks = NS(delta=0.05)  # the partner (short) leg gets a valid, far-from-target Alpaca delta
    t, why = lab.build("SPY", "call_debit", 700.0)
    assert why == "ok" and t["long"] == t0["long"] and t["short"] == t0["short"]
    assert t["short_delta_source"] == "alpaca" and t["long_delta_source"] == "computed"
    assert t["delta_source"] == "computed"


def test_dry_run_never_reaches_the_account(tmp_path, monkeypatch):
    _at(monkeypatch, "14:41")
    lab = _bare_lab(tmp_path)  # dry
    lab.trading = NS(_base_url="https://paper-api.alpaca.markets",
                     submit_order=lambda req: pytest.fail("dry run sent an order"),
                     get_order_by_client_id=lambda cid: pytest.fail("dry run looked up an order"),
                     get_all_positions=lambda: pytest.fail("dry run read positions"))
    t = _legging()
    assert lab.held(t) is None
    assert lab.send_leg(t, "short", 2, 1.0)["status"] == "dry-run"
    assert lab.send(t, "close", 1.0)["status"] == "dry-run"


def test_fill_deltas_uses_the_pinned_rate():
    assert options_lab.RISK_FREE_RATE == 0.04 and options_lab.DIVIDEND_YIELD == 0.0
    # half a year out, where r moves the delta visibly: the pipeline must use RISK_FREE_RATE
    rows = [{"symbol": "X", "type": "put", "strike": 700.0, "bid": 20.0, "ask": 20.2, "delta": None}]
    options_lab.fill_deltas(rows, 700.0, 0.5)
    d, _, _ = options_lab.computed_delta(20.0, 20.2, 700.0, 700.0, 0.5, "put", r=0.04)
    d0, _, _ = options_lab.computed_delta(20.0, 20.2, 700.0, 700.0, 0.5, "put", r=0.0)
    assert rows[0]["delta"] == round(d, 4) and abs(round(d0, 4) - rows[0]["delta"]) > 0.005


# =================================================================================================================
# Day-1 post-mortem code defects (reports/Options lab day 1 post-mortem.md, 28 Sept 2026)
# =================================================================================================================
def _bars(first_hm, n, closes, extra=None):
    """`n` 1-minute bars from `first_hm` ET (stamped with their start minute, like Alpaca), UTC index."""
    import pandas as pd

    h, m = first_hm
    t0 = datetime(2026, 9, 29, h, m, tzinfo=options_lab.NY)
    idx = pd.DatetimeIndex([t0 + timedelta(minutes=i) for i in range(n)]).tz_convert("UTC")
    return pd.DataFrame({"open": closes, "high": [c + 0.05 for c in closes], "low": [c - 0.05 for c in closes],
                         "close": closes, "volume": [1000.0] * n}, index=idx)


# --- PM defect 1: "mom60" at 10:15 was the move since the first minute -------------------------------------------
def test_momentum_needs_a_true_60_minute_window(tmp_path, monkeypatch):
    import pandas as pd

    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    # 09:30..10:15: 45 completed bars plus the 10:15 bar still forming; down 0.5% since the first minute
    closes = [700.0 - 3.5 * i / 45 for i in range(46)]
    pre = _bars((9, 0), 30, [705.0] * 30)  # pre-market bars must never count
    lab.minute_bars = lambda sym: pd.concat([pre, _bars((9, 30), 46, closes)])
    kind, info = lab.signal("SPY")
    assert kind not in ("put_debit", "call_debit")  # the old code fired put_debit on a 45-minute move
    assert info["mom60_pct"] is None and "needs 61" in info["mom60_why"] and info["bars_completed"] == 45
    assert info["spot"] == closes[44]  # the forming 10:15 bar is not used
    assert info["last_bar"] == datetime(2026, 9, 29, 10, 14, tzinfo=options_lab.NY).astimezone(
        options_lab.timezone.utc).isoformat()
    # 10:31: 61 completed bars (09:30..10:30): a real 60-minute move, 10:30 close against the 09:30 close
    _at(monkeypatch, "10:31")
    closes = [700.0] * 30 + [700.0 - 3.5 * i / 30 for i in range(1, 32)]
    lab.minute_bars = lambda sym: _bars((9, 30), 61, closes)
    kind, info = lab.signal("SPY")
    assert kind == "put_debit" and info["mom60_pct"] == round((closes[60] / closes[0] - 1) * 100, 3)
    assert info["mom60_minutes"] == 60 and info["mom60_window"][0].startswith("2026-09-29T13:30")
    # a missing bar exactly 60 minutes back (feed gap): not checked, never a longer or shorter window
    df = _bars((9, 30), 61, closes)
    _at(monkeypatch, "10:32")  # 62 completed bars, but the 09:31 bar is missing
    lab.minute_bars = lambda sym: _bars((9, 30), 62, closes + [closes[-1]]).drop(df.index[1])
    kind, info = lab.signal("SPY")
    assert info["mom60_pct"] is None and "exactly 60 minutes" in info["mom60_why"]
    assert kind not in ("put_debit", "call_debit")


# --- PM defect 2: a close that receives money offered below the natural price -----------------------------------
def test_first_close_steps_never_worse_than_natural(tmp_path, monkeypatch):
    _at(monkeypatch, "14:05")
    lab = _bare_lab(tmp_path)
    debit = _open_trade(credit=False, entry=0.855)
    # day 1 QQQ: mid 0.77, natural 0.76 -> the old ladder offered mid - 0.03 = 0.74, below the natural
    assert lab.close_limit(debit, 0.77, 0.76) == 0.76
    assert lab.close_limit(debit, 0.90, 0.76) == 0.87  # mid - step when that is above the natural
    debit["close_attempts"] = 2
    assert lab.close_limit(debit, 0.77, 0.76) == 0.76
    credit = _open_trade(credit=True)
    assert lab.close_limit(credit, 0.55, 0.56) == 0.56  # we pay: never above the natural
    assert lab.close_limit(credit, 0.55, 0.70) == 0.58
    # the deliberate crossing at hard_close / attempt 3 / last resort is unchanged
    debit["close_attempts"] = 3  # through the natural: min(mid - 0.15, natural - 0.10)
    assert lab.close_limit(debit, 0.77, 0.76) == 0.62
    _at(monkeypatch, options_lab.TIMING["0dte"]["hard_close"])
    assert lab.close_limit(_open_trade(credit=False), 0.77, 0.76) == 0.66
    assert lab.close_limit(_open_trade(credit=True), 0.55, 0.56) == 0.66


# --- PM defect 3: trades.json lost the original size after a close -----------------------------------------------
def test_original_size_survives_the_close(tmp_path, monkeypatch):
    fake = FakeTrading(positions={LONG: 2, SHORT: -2}, states=[("filled", 2, 0.855)])
    lab = _live_lab(tmp_path, monkeypatch, "14:05", fake, quote=(0.80, 0.78))
    t = _open_trade(credit=False, entry=0.92, status="pending_open", open_order={"id": "o0"})
    orig_max_loss = t["max_loss"]
    lab.trades = [t]
    lab.manage()  # filled
    assert (t["orig_qty"], t["orig_max_loss"], t["orig_net"]) == (2, orig_max_loss, 0.855)
    lab.manage()  # time exit: close sent
    fake.states = [("canceled", 1, 0.74)]
    lab.manage()  # one of two closed
    assert t["qty"] == 1 and t["orig_qty"] == 2
    lab.manage()
    fake.states = [("filled", 1, 0.75)]
    lab.manage()
    assert t["status"] == "closed" and t["qty"] == 0 and t["max_loss"] == 0
    saved = json.loads((tmp_path / "trades.json").read_text())[0]
    assert (saved["orig_qty"], saved["orig_max_loss"], saved["orig_net"]) == (2, orig_max_loss, 0.855)
    closed = next(r for r in _rows(tmp_path) if r["event"] == "closed")
    assert closed["orig_qty"] == 2 and closed["orig_max_loss"] == orig_max_loss


# --- PM defect 4: the entry limit came from a quote about a minute old -------------------------------------------
def _debit_entry_lab(tmp_path, monkeypatch, chain_age_sec=0):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY), **vars(_paper_trading()))
    rows = _chain(700.0)
    stamp = (options_lab.ny_now() - timedelta(seconds=chain_age_sec)).isoformat()
    for r in rows:
        r["quote_time"] = stamp
    lab.chain = lambda sym, expiry, spot: [dict(r) for r in rows]
    lab.signal = lambda sym: ("put_debit", {"spot": 700.0})
    return lab, rows


def test_entry_skipped_when_the_fresh_quote_is_stale(tmp_path, monkeypatch):
    lab, rows = _debit_entry_lab(tmp_path, monkeypatch)
    _fresh_quotes(lab, rows, age_sec=45)
    lab.try_entry("11:30")
    assert lab.trades == []  # the old code sent the open on the old price
    skips = [r for r in _rows(tmp_path) if r["event"] == "no_trade"]
    assert skips and all("older than 30s" in r["why"] for r in skips)
    chk = next(r for r in _rows(tmp_path) if r["event"] == "entry_quote_check")
    assert chk["fresh"]["long"]["age_sec"] == 45.0 and chk["fresh"]["long"]["time"]


def test_entry_repriced_once_from_a_fresh_quote_that_moved(tmp_path, monkeypatch):
    lab, rows = _debit_entry_lab(tmp_path, monkeypatch, chain_age_sec=60)
    moved = [dict(r) for r in rows]
    long_sym = "SPY260929P00700000"
    for r in moved:  # the long leg got 0.10 dearer: the debit moved against us by 0.10
        if r["symbol"] == long_sym:
            r["bid"], r["ask"] = round(r["bid"] + 0.10, 2), round(r["ask"] + 0.10, 2)
    _fresh_quotes(lab, moved)
    lab.try_entry("11:30")
    t = lab.trades[0]
    assert t["long"] == long_sym
    chk = t["entry_quote_check"]
    planned = chk["planned"]
    assert chk["result"] == "repriced" and t["repriced"]
    assert t["net"] == round(planned["net"] + 0.10, 2) and t["open_order"]["limit"] == t["net"]
    assert t["qty"] <= planned["qty"] and t["max_loss"] <= options_lab.MAX_LOSS_PER_TRADE
    assert t["long_ask"] == round(planned["long_ask"] + 0.10, 2)
    entry = next(r for r in _rows(tmp_path) if r["event"] == "entry")
    assert entry["repriced"] and entry["planned_net"] == planned["net"] and entry["long_quote_time"]
    assert "older than 30s" in chk["reprice_why"] and "against" in chk["reprice_why"]


def test_entry_keeps_a_fresh_unchanged_price_and_journals_quote_times(tmp_path, monkeypatch):
    lab, rows = _debit_entry_lab(tmp_path, monkeypatch, chain_age_sec=5)
    _fresh_quotes(lab, rows, age_sec=2)
    lab.try_entry("11:30")
    t = lab.trades[0]
    assert t["entry_quote_check"]["result"] == "kept" and not t.get("repriced")
    entry = next(r for r in _rows(tmp_path) if r["event"] == "entry")
    assert entry["quote_check"] == "kept" and entry["long_quote_time"] == rows[0]["quote_time"]


def test_entry_skipped_when_the_repriced_trade_breaks_the_caps(tmp_path, monkeypatch):
    lab, rows = _debit_entry_lab(tmp_path, monkeypatch, chain_age_sec=60)
    moved = [dict(r) for r in rows]
    for r in moved:  # a quote too wide to trade on re-read
        r["ask"] = round(r["bid"] + 0.30, 2)
    _fresh_quotes(lab, moved)
    lab.try_entry("11:30")
    assert lab.trades == []
    assert any(r["event"] == "no_trade" and "re-price from the fresh quote refused" in r["why"]
               for r in _rows(tmp_path))


# --- R3 finding A: a REJECTED single-leg close lowers legs_left only when two reads in a row agree -------------
def _reject_lab(tmp_path, monkeypatch, positions):
    fake = FakeTrading(positions=positions)
    lab = _live_lab(tmp_path, monkeypatch, "14:41", fake)
    lab.quotes = lambda syms: {syms[0]: NS(bid_price=1.0, ask_price=1.1)}
    t = _legging()
    lab.trades = [t]
    return fake, lab, t


def test_rejected_leg_order_needs_two_reads_before_the_long_is_sold(tmp_path, monkeypatch):
    fake, lab, t = _reject_lab(tmp_path, monkeypatch, {LONG: 2, SHORT: -2})
    lab.manage()  # buy_to_close short sent
    fake.states, fake.positions = [("rejected", 0, None)], {LONG: 2}  # ONE partial read
    lab.manage()
    assert t["legs_left"] == {"short": 2, "long": 2}
    fake.positions = {LONG: 2, SHORT: -2}  # the account really holds the short
    lab.manage()
    assert fake.sent[-1].symbol == SHORT  # the short again, never the long
    fake.states = [("rejected", 0, None)]
    lab.manage()  # this read shows the short: the max of the two reads keeps legs_left
    assert t["legs_left"] == {"short": 2, "long": 2} and not t.get("pnl_incomplete")
    assert all(r.symbol == SHORT for r in fake.sent)
    # two rejects in a row that BOTH read no short: now lowered, and the long is sold
    fake.positions = {LONG: 2}
    for _ in range(2):
        lab.manage()
        fake.states = [("rejected", 0, None)]
        lab.manage()
    assert t["legs_left"] == {"short": 0, "long": 2} and t["pnl_incomplete"]
    lab.manage()
    assert fake.sent[-1].symbol == LONG and fake.sent[-1].side.value == "sell"


def test_rejected_leg_order_and_empty_reads_never_close_the_trade(tmp_path, monkeypatch):
    fake, lab, t = _reject_lab(tmp_path, monkeypatch, {LONG: 2, SHORT: -2})
    lab.manage()
    fake.states, fake.positions = [("rejected", 0, None)], {}  # one empty read
    lab.manage()
    assert t["status"] == "legging_out" and t["legs_left"] == {"short": 2, "long": 2}
    lab.manage()  # short re-sent
    fake.states = [("rejected", 0, None)]
    lab.manage()  # a 2nd empty read in a row: verify_gone (LIVE), never closed
    assert t["status"] == "verify_gone" and t["status"] in options_lab.LIVE and t["pnl_incomplete"]
    fake.positions = {LONG: 2, SHORT: -2}
    lab.manage()
    assert t["status"] == "open"


def test_leg_send_failures_with_two_empty_reads_go_to_verify_gone(tmp_path, monkeypatch):
    fake = FakeTrading(positions={}, submit_error=TimeoutError("t"), lookup=ConnectionError("d"))
    lab = _live_lab(tmp_path, monkeypatch, "14:41", fake)
    lab.quotes = lambda syms: {syms[0]: NS(bid_price=1.0, ask_price=1.1)}
    t = _legging()
    lab.trades = [t]
    for _ in range(3):
        lab.manage()
    assert t["status"] == "verify_gone" and t["status"] in options_lab.LIVE


# --- R3 finding B: start_leg_out at close_by / after close failures never lowers legs on ONE read ---------------
def test_close_by_leg_out_ignores_one_partial_read(tmp_path, monkeypatch):
    fake = FakeTrading(positions={LONG: 2})  # one read missing the short
    lab = _live_lab(tmp_path, monkeypatch, options_lab.TIMING["0dte"]["close_by"], fake, quote=(1.0, 1.1))
    lab.quotes = lambda syms: {syms[0]: NS(bid_price=1.0, ask_price=1.1)}
    t = _open_trade(exit_reason="time exit before the 0DTE cutoff", close_attempts=9)
    lab.trades = [t]
    lab.manage()
    assert t["status"] == "legging_out" and t["legs_left"] == {"short": 2, "long": 2}
    assert any(r["event"] == "legs_mismatch_one_read" for r in _rows(tmp_path))
    fake.positions = {LONG: 2, SHORT: -2}
    lab.manage()
    assert fake.sent[-1].symbol == SHORT and fake.sent[-1].side.value == "buy"


def test_legs_ok_confirmed_read_still_sets_legs_left(tmp_path, monkeypatch):
    lab = _live_lab(tmp_path, monkeypatch, "14:05", FakeTrading())
    t = _open_trade()
    lab.start_leg_out(t, "two reads agreed", (0, 2))
    assert t["legs_left"] == {"short": 2, "long": 0} and t["pnl_incomplete"]


# --- R3 finding C: the kept entry path applies the quote filter to the fresh quote ------------------------------
@pytest.mark.parametrize("how", ["wide", "zero_bid"])
def test_kept_path_refuses_a_fresh_quote_the_filter_rejects(tmp_path, monkeypatch, how):
    lab, rows = _debit_entry_lab(tmp_path, monkeypatch, chain_age_sec=5)
    bad = [dict(r) for r in rows]
    for r in bad:  # same mid, but too wide / no bid
        m = (r["bid"] + r["ask"]) / 2
        r["bid"], r["ask"] = (round(m - 0.225, 3), round(m + 0.225, 3)) if how == "wide" else (0.0, round(2 * m, 3))
    _fresh_quotes(lab, bad, age_sec=1)
    lab.try_entry("11:30")
    assert lab.trades == []
    chk = next(r for r in _rows(tmp_path) if r["event"] == "entry_quote_check")
    assert chk["result"] == "skip" and "too wide or empty" in chk["reprice_why"]


# --- R3: a re-priced trade is never larger than planned -------------------------------------------------------
def test_reprice_to_a_cheaper_debit_never_increases_size(tmp_path, monkeypatch):
    lab, rows = _debit_entry_lab(tmp_path, monkeypatch, chain_age_sec=5)
    moved = [dict(r) for r in rows]
    for r in moved:  # the long leg got 0.08 cheaper: a cheaper debit, a bigger size would fit the cap
        if r["symbol"] == "SPY260929P00700000":
            r["bid"], r["ask"] = round(r["bid"] - 0.08, 2), round(r["ask"] - 0.08, 2)
    _fresh_quotes(lab, moved, age_sec=1)
    lab.try_entry("11:30")
    t = lab.trades[0]
    chk = t["entry_quote_check"]
    assert chk["result"] == "repriced" and "for us" in chk["reprice_why"]
    assert t["net"] == round(chk["planned"]["net"] - 0.08, 2)  # the better price is taken
    assert t["qty"] <= chk["planned"]["qty"]
    fresh_room = int(options_lab.MAX_LOSS_PER_TRADE // (t["net"] * 100 + t["exit_cost_pc"] * 100))
    assert fresh_room > chk["planned"]["qty"]  # the test really exercises max_qty


# --- R3: credit-side keep / move-against logic ------------------------------------------------------------------
def _credit_entry_lab(tmp_path, monkeypatch):
    lab, rows = _debit_entry_lab(tmp_path, monkeypatch, chain_age_sec=5)
    lab.signal = lambda sym: ("put_credit", {"spot": 700.0})
    return lab, rows


def test_credit_entry_kept_on_an_unchanged_fresh_quote(tmp_path, monkeypatch):
    lab, rows = _credit_entry_lab(tmp_path, monkeypatch)
    _fresh_quotes(lab, rows, age_sec=1)
    lab.try_entry("11:30")
    t = lab.trades[0]
    chk = t["entry_quote_check"]
    assert t["credit"] and chk["result"] == "kept" and t["net"] == chk["planned"]["net"]
    assert chk["move"] == 0 and chk["fresh_mid"] == chk["planned"]["net"]


def test_credit_entry_repriced_when_the_credit_shrinks(tmp_path, monkeypatch):
    lab, rows = _credit_entry_lab(tmp_path, monkeypatch)
    plan = lab.build("SPY", "put_credit", 700.0)[0]
    moved = [dict(r) for r in rows]
    for r in moved:  # the short leg got 0.06 cheaper: we would receive less
        if r["symbol"] == plan["short"]:
            r["bid"], r["ask"] = round(r["bid"] - 0.06, 2), round(r["ask"] - 0.06, 2)
    _fresh_quotes(lab, moved, age_sec=1)
    lab.try_entry("11:30")
    t = lab.trades[0]
    chk = t["entry_quote_check"]
    assert chk["result"] == "repriced" and chk["move_against"] == 0.06 and "against" in chk["reprice_why"]
    assert t["net"] == round(plan["net"] - 0.06, 2)


def test_chain_records_the_snapshot_quote_time(tmp_path, monkeypatch):
    _at(monkeypatch, "10:15")
    lab = _bare_lab(tmp_path)
    lab.trading = NS(get_option_contracts=_contracts(TODAY))
    lab.underlying_price = lambda sym: 700.0
    snaps, _ = _snaps_without_greeks()
    stamp = datetime(2026, 9, 29, 10, 14, 50, tzinfo=options_lab.NY)
    for s in snaps.values():
        s.latest_quote.timestamp = stamp
    lab.options = NS(get_option_chain=lambda req: snaps)
    rows = lab.chain("SPY", TODAY, 700.0)
    assert rows and all(r["quote_time"] == stamp.isoformat() for r in rows)


# --- R3: entry quote check skip paths ---------------------------------------------------------------------------
def test_entry_skipped_when_the_quote_reread_fails(tmp_path, monkeypatch):
    lab, rows = _debit_entry_lab(tmp_path, monkeypatch, chain_age_sec=5)

    def boom(syms):
        raise ConnectionError("down")
    lab.quotes = boom
    lab.try_entry("11:30")
    assert lab.trades == []
    assert any(r["event"] == "no_trade" and "re-read failed" in r["why"] for r in _rows(tmp_path))


def test_entry_skipped_on_an_undated_fresh_quote(tmp_path, monkeypatch):
    lab, rows = _debit_entry_lab(tmp_path, monkeypatch, chain_age_sec=5)
    by = {r["symbol"]: r for r in rows}
    lab.quotes = lambda syms: {s: NS(bid_price=by[s]["bid"], ask_price=by[s]["ask"], timestamp=None) for s in syms}
    lab.try_entry("11:30")
    assert lab.trades == []
    assert any(r["event"] == "no_trade" and "undated" in r["why"] for r in _rows(tmp_path))


def test_undated_planned_quote_is_repriced_not_kept(tmp_path, monkeypatch):
    lab, rows = _debit_entry_lab(tmp_path, monkeypatch, chain_age_sec=5)
    for r in rows:
        r["quote_time"] = None
    _fresh_quotes(lab, rows, age_sec=1)
    lab.try_entry("11:30")
    chk = lab.trades[0]["entry_quote_check"]
    assert chk["result"] == "repriced" and "undated" in chk["reprice_why"]
    assert lab.trades[0]["long_quote_time"] == chk["fresh"]["long"]["time"]  # the fresh quote times are kept


# --- R3: the momentum reference is the bar exactly 60 minutes back, not the session's first bar ---------------
def test_momentum_reference_is_60_minutes_back_not_the_first_bar(tmp_path, monkeypatch):
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    closes = [690.0] * 59 + [700.0] * 60 + [703.5]  # 09:30..11:29: 120 completed bars
    lab.minute_bars = lambda sym: _bars((9, 30), 120, closes)
    kind, info = lab.signal("SPY")
    assert info["mom60_ref_close"] == 700.0  # the 10:29 close (the 09:30 close is 690)
    assert info["mom60_window"][0] == datetime(2026, 9, 29, 10, 29, tzinfo=options_lab.NY).astimezone(
        options_lab.timezone.utc).isoformat()
    assert kind == "call_debit" and info["mom60_pct"] == 0.5


# --- R3: orig_* on the leg-out and legs-gone closed rows --------------------------------------------------------
def test_closed_rows_carry_the_original_size(tmp_path, monkeypatch):
    lab = _live_lab(tmp_path, monkeypatch, "14:41", FakeTrading())
    t = _legging(qty=1, legs_left={"short": 0, "long": 0}, orig_qty=1, orig_max_loss=150.0)
    g = _open_trade(id="0929Z2", status="verify_gone", orig_qty=2, orig_max_loss=300.0)
    lab.trades = [t, g]
    lab.manage()
    closed = next(r for r in _rows(tmp_path) if r["event"] == "closed")
    gone = next(r for r in _rows(tmp_path) if r["event"] == "ALERT_LEGS_GONE_CONFIRMED")
    assert (closed["orig_qty"], closed["orig_max_loss"]) == (1, 150.0)
    assert (gone["orig_qty"], gone["orig_max_loss"]) == (2, 300.0)


def test_realized_losses_count_against_the_daily_total_cap(tmp_path, monkeypatch):
    """Owner cap: the whole day can lose at most MAX_LOSS_TOTAL, not only the trades open at once."""
    _at(monkeypatch, "11:30")
    lab = _bare_lab(tmp_path)
    lab.trading = _paper_trading()
    lab.trades = [{"status": "closed", "pnl": -600.0, "max_loss": 0.0},
                  {"status": "closed", "pnl": 100.0, "max_loss": 0.0}]
    assert lab.realized_loss() == 500.0
    t = {"long": "SPY260929P00698000", "short": "SPY260929P00700000", "width": 2.0, "max_loss": 249.0, "qty": 1}
    assert lab.check_order(t, "open") == []
    lab.trades[0]["pnl"] = -610.0  # realized loss 510 + 249 > 750, while 249 alone is under the per-trade cap
    assert lab.check_order(t, "open") == ["over the total cap"]
    lab.trades.append({"status": "closed", "pnl": 900.0, "max_loss": 0.0})
    assert lab.realized_loss() == 0.0
