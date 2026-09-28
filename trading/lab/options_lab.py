"""Options lab: a one-day, paper-only, defined-risk options experiment (owner request, 28 Sept 2026).

This is NOT book O and never counts in its record. It exists to learn options mechanics and intraday behaviour
on paper money, with hard locks that do not depend on anyone's judgement:

- paper account only (the client is created with paper=True, and the account must report as paper);
- two-leg vertical spreads only (same underlying, expiry and type, 1:1, one long and one short leg), sent as ONE
  multi-leg LIMIT DAY order, so the worst case is known before entry: never a naked short option;
- underlyings SPY and QQQ only; expiry 1 to 10 calendar days away (never same-day, never held overnight);
- worst case per trade <= MAX_LOSS_PER_TRADE, all open trades <= MAX_LOSS_TOTAL, at most MAX_OPENS a day;
- every order id starts with "LAB-", so the stock books and book O never touch these orders;
- everything is closed by CLOSE_BY (15:50 New York); no new entries after LAST_ENTRY.

Entries are rule-based and checked at fixed times; each writes its reasons to the journal. Exits: take profit at
50% of the maximum gain, stop at 50% of the maximum loss, or the time exit. Everything is logged to
state/options_lab/<date>/journal.jsonl (under TRADER_STATE_DIR or trading/state).
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
PREFIX = "LAB-"  # not "OPT-": book O and the stock books never match it
UNDERLYINGS = ("SPY", "QQQ")
MAX_LOSS_PER_TRADE = 250.0
MAX_LOSS_TOTAL = 750.0
MAX_OPENS = 4
WIDTH = {"SPY": 2.0, "QQQ": 2.0}
MIN_DTE, MAX_DTE = 1, 10
ENTRY_TIMES = ("10:15", "11:30", "13:00", "14:15")
LAST_ENTRY = "14:30"
CLOSE_BY = "15:50"
TIME_EXIT = "15:35"   # time exit starts here so the ladder has 15+ minutes to fill
HARD_CLOSE = "15:45"  # from here the close pays through the natural price, every 30 s
LAST_RESORT = "15:48"  # credit close bids the full width, debit close offers 0.01: fills for sure
REPRICE_SEC = 60      # an unfilled close is cancelled and re-priced one step further after this
STEPS = (0.03, 0.06, 0.10, 0.15, 0.25, 0.40)
TERMINAL = {"filled", "canceled", "expired", "rejected", "done_for_day", "replaced", "stopped", "suspended"}
LIVE = ("pending_open", "open", "pending_close")
TAKE_PROFIT, STOP = 0.5, 0.5
BACKSTOP = 0.8  # credit spreads stop on the underlying crossing the short strike; this value stop is the backstop
MAX_QUOTE_SPREAD = 0.20  # a leg with a bid-ask wider than this ($) is not traded


def ny_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(NY)


def hhmm(t: datetime) -> str:
    return t.strftime("%H:%M")


class Lab:
    def __init__(self, state_dir: Path, *, dry: bool = False):
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.trading.client import TradingClient

        key, secret = os.environ["ALPACA_RULES_KEY"], os.environ["ALPACA_RULES_SECRET"]
        self.trading = TradingClient(key, secret, paper=True)
        self.stocks = StockHistoricalDataClient(key, secret)
        self.options = OptionHistoricalDataClient(key, secret)
        self.dry = dry
        self.today = ny_now().date()
        self.dir = state_dir / "options_lab" / (self.today.isoformat() + ("-dry" if dry else ""))
        self.dir.mkdir(parents=True, exist_ok=True)
        self.book_path = self.dir / "trades.json"
        self.trades: list[dict] = json.loads(self.book_path.read_text()) if self.book_path.exists() else []
        self.done_checkpoints: set[str] = {t.get("checkpoint") for t in self.trades if t.get("checkpoint")}
        self.done_checkpoints |= set(json.loads((self.dir / "checkpoints.json").read_text())) \
            if (self.dir / "checkpoints.json").exists() else set()

    # --- logging -------------------------------------------------------------------------------------------
    def log(self, event: str, **data) -> None:
        # `event` (not `kind`): callers pass the signal's `kind=` as data.
        row = {"time": ny_now().isoformat(timespec="seconds"), "event": event, **data}
        with open(self.dir / "journal.jsonl", "a") as f:
            f.write(json.dumps(row, default=str) + "\n")
        print(f"[{hhmm(ny_now())}] {event}: {json.dumps(data, default=str)[:400]}", flush=True)

    def save(self) -> None:
        self.book_path.write_text(json.dumps(self.trades, indent=1, default=str))
        (self.dir / "checkpoints.json").write_text(json.dumps(sorted(self.done_checkpoints)))

    # --- market data ---------------------------------------------------------------------------------------
    def minute_bars(self, sym: str):
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        import pandas as pd

        start = datetime.combine(self.today, datetime.min.time(), NY).replace(hour=9, minute=30)
        if ny_now() <= start + timedelta(minutes=1):
            return pd.DataFrame()
        df = self.stocks.get_stock_bars(StockBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame.Minute,
                                                         start=start, feed=DataFeed.IEX)).df
        return df.xs(sym, level="symbol") if len(df) else df

    def chain(self, sym: str, expiry: date, spot: float) -> list[dict]:
        from alpaca.data.enums import OptionsFeed
        from alpaca.data.requests import OptionChainRequest

        snaps = self.options.get_option_chain(OptionChainRequest(
            underlying_symbol=sym, expiration_date=expiry, feed=OptionsFeed.INDICATIVE,
            strike_price_gte=round(spot * 0.93, 0), strike_price_lte=round(spot * 1.07, 0)))
        out = []
        for osym, s in snaps.items():
            q, g = getattr(s, "latest_quote", None), getattr(s, "greeks", None)
            if q is None or g is None or q.bid_price is None or q.ask_price is None:
                continue
            typ = "call" if osym[-9] == "C" else "put"
            out.append({"symbol": osym, "type": typ, "strike": int(osym[-8:]) / 1000.0, "bid": float(q.bid_price),
                        "ask": float(q.ask_price), "delta": float(g.delta or 0.0), "iv": s.implied_volatility})
        return out

    def expiry_for(self, sym: str) -> date | None:
        from alpaca.trading.requests import GetOptionContractsRequest

        r = self.trading.get_option_contracts(GetOptionContractsRequest(
            underlying_symbols=[sym], expiration_date_gte=self.today + timedelta(days=MIN_DTE),
            expiration_date_lte=self.today + timedelta(days=MAX_DTE), limit=1000))
        exps = sorted({c.expiration_date for c in (r.option_contracts or [])})
        # 2+ calendar days gives the trade a little room; fall back to the nearest allowed expiry.
        for e in exps:
            if (e - self.today).days >= 2:
                return e
        return exps[0] if exps else None

    # --- the rules that pick a trade ------------------------------------------------------------------------
    def signal(self, sym: str) -> tuple[str | None, dict]:
        """Opening-range + VWAP trend rule. Up day -> bull put credit spread; down day -> bear call credit spread;
        strong 60-minute momentum -> a debit spread in its direction. Otherwise no trade."""
        df = self.minute_bars(sym)
        if len(df) < 45:
            return None, {"why": "not enough minute bars yet"}
        close = df["close"]
        spot = float(close.iloc[-1])
        orh, orl = float(df["high"].iloc[:30].max()), float(df["low"].iloc[:30].min())
        vwap = float((df["close"] * df["volume"]).sum() / max(1.0, df["volume"].sum()))
        mom60 = spot / float(close.iloc[-61]) - 1 if len(close) > 61 else spot / float(close.iloc[0]) - 1
        info = {"spot": spot, "opening_range": [orh, orl], "vwap": round(vwap, 2), "mom60_pct": round(mom60 * 100, 3)}
        if abs(mom60) >= 0.004:
            return ("call_debit" if mom60 > 0 else "put_debit"), {**info, "why": "60-minute move of 0.4% or more"}
        if spot > orh and spot > vwap:
            return "put_credit", {**info, "why": "above the 30-minute opening range and VWAP"}
        if spot < orl and spot < vwap:
            return "call_credit", {**info, "why": "below the 30-minute opening range and VWAP"}
        return None, {**info, "why": "inside the opening range or mixed signals: no trade"}

    def build(self, sym: str, kind: str, spot: float) -> tuple[dict | None, str]:
        expiry = self.expiry_for(sym)
        if expiry is None:
            return None, "no expiry 1-10 days out"
        rows = self.chain(sym, expiry, spot)
        typ = "put" if kind.startswith("put") else "call"
        legs = sorted([r for r in rows if r["type"] == typ], key=lambda r: r["strike"])
        by_strike = {r["strike"]: r for r in legs}
        width = WIDTH[sym]
        credit = kind.endswith("credit")
        # Short leg ~0.30 delta for credit spreads; long leg ~0.50 delta (near the money) for debit spreads.
        target = 0.30 if credit else 0.50
        pick = min(legs, key=lambda r: abs(abs(r["delta"]) - target), default=None)
        if pick is None:
            return None, "no quotes"
        if credit:
            short = pick
            far = short["strike"] - width if typ == "put" else short["strike"] + width
            long = by_strike.get(far)
        else:
            long = pick
            far = long["strike"] + width if typ == "call" else long["strike"] - width
            short = by_strike.get(far)
        if long is None or short is None:
            return None, f"no {width:.0f}-wide partner strike"
        for leg in (long, short):
            if leg["ask"] - leg["bid"] > MAX_QUOTE_SPREAD or leg["bid"] <= 0:
                return None, f"leg {leg['symbol']} quote too wide or empty ({leg['bid']}/{leg['ask']})"
        mid = (short["bid"] + short["ask"]) / 2 - (long["bid"] + long["ask"]) / 2  # >0 credit, <0 debit
        if (mid > 0) != credit:
            return None, f"mid {mid:.2f} has the wrong sign for a {kind} (bad quotes)"
        net = round(abs(mid), 2)
        if net <= 0.05:
            return None, "net price too small to trade"
        structural = (width - net) * 100 if credit else net * 100
        per_contract_gain = net * 100 if credit else (width - net) * 100
        if structural <= 0:
            return None, "bad quotes (no risk?)"
        # Budget the exit too: closing costs about half of each leg's quoted spread (research playbook, section 8).
        exit_cost = ((long["ask"] - long["bid"]) + (short["ask"] - short["bid"])) / 2 * 100
        per_contract_loss = structural + exit_cost
        qty = int(MAX_LOSS_PER_TRADE // per_contract_loss)
        room = MAX_LOSS_TOTAL - sum(t["max_loss"] for t in self.trades if t["status"] in LIVE)
        qty = min(qty, int(room // per_contract_loss))
        if qty < 1:
            return None, f"one contract risks ${per_contract_loss:.0f}, over the cap or the remaining room"
        return {"underlying": sym, "kind": kind, "expiry": expiry.isoformat(), "type": typ, "credit": credit,
                "long": long["symbol"], "short": short["symbol"], "long_strike": long["strike"],
                "short_strike": short["strike"], "width": width, "qty": qty, "net": net,
                "max_loss": round(per_contract_loss * qty, 2), "structural_max_loss": round(structural * qty, 2),
                "exit_cost_budget": round(exit_cost * qty, 2), "max_gain": round(per_contract_gain * qty, 2),
                "short_delta": short["delta"], "long_delta": long["delta"]}, "ok"

    # --- orders ------------------------------------------------------------------------------------------------
    def check_order(self, t: dict, intent: str) -> list[str]:
        """The lab's own locks, checked right before any order is sent."""
        from trader.options.models import is_occ, parse_occ

        out = []
        acct = self.trading.get_account()
        if "paper-api" not in str(getattr(self.trading._base_url, "value", self.trading._base_url)):
            out.append("not a paper account")
        a, b = parse_occ(t["long"]) if is_occ(t["long"]) else None, parse_occ(t["short"]) if is_occ(t["short"]) else None
        if not a or not b:
            return out + ["legs are not option symbols"]
        if a["underlying"] != b["underlying"] or a["expiry"] != b["expiry"] or a["type"] != b["type"]:
            out.append("legs are not one vertical")
        if a["underlying"] not in UNDERLYINGS:
            out.append("underlying not allowed")
        if abs(a["strike"] - b["strike"]) != t["width"]:
            out.append("width mismatch")
        dte = (date.fromisoformat(a["expiry"]) - self.today).days
        if intent == "open":
            if not (MIN_DTE <= dte <= MAX_DTE):
                out.append(f"expiry {dte} days away is outside {MIN_DTE}-{MAX_DTE}")
            if t["max_loss"] > MAX_LOSS_PER_TRADE + 1e-6:
                out.append("over the per-trade cap")
            opens = [x for x in self.trades if x["status"] in LIVE and x is not t]
            if sum(x["max_loss"] for x in opens) + t["max_loss"] > MAX_LOSS_TOTAL + 1e-6:
                out.append("over the total cap")
            if len([x for x in self.trades if x.get("opened")]) >= MAX_OPENS:
                out.append("max opens reached")
            if hhmm(ny_now()) > LAST_ENTRY:
                out.append("after the last entry time")
        if not isinstance(t["qty"], int) or t["qty"] < 1:
            out.append("bad quantity")
        return out

    def send(self, t: dict, intent: str, limit_net: float) -> dict:
        """One multi-leg LIMIT DAY order. Alpaca sign: a negative limit is a net credit, a positive one a debit."""
        from alpaca.trading.enums import OrderClass, OrderSide, PositionIntent, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

        why = self.check_order(t, intent)
        if why:
            return {"status": "refused", "why": why}
        if intent == "open":
            legs = [(t["long"], OrderSide.BUY, PositionIntent.BUY_TO_OPEN),
                    (t["short"], OrderSide.SELL, PositionIntent.SELL_TO_OPEN)]
            receive = t["credit"]
        else:
            legs = [(t["long"], OrderSide.SELL, PositionIntent.SELL_TO_CLOSE),
                    (t["short"], OrderSide.BUY, PositionIntent.BUY_TO_CLOSE)]
            receive = not t["credit"]
        limit = -abs(limit_net) if receive else abs(limit_net)
        cid = f"{PREFIX}{t['id']}-{intent}-{t.get('close_attempts', 0) if intent == 'close' else 0}"
        req = LimitOrderRequest(qty=t["qty"], order_class=OrderClass.MLEG, time_in_force=TimeInForce.DAY,
                                limit_price=round(limit, 2), client_order_id=cid, extended_hours=False,
                                legs=[OptionLegRequest(symbol=s, ratio_qty=1, side=sd, position_intent=pi)
                                      for s, sd, pi in legs])
        if self.dry:
            return {"status": "dry-run", "client_order_id": cid, "limit": round(limit, 2)}
        try:
            o = self.trading.submit_order(req)
        except Exception as e:  # it may have reached Alpaca anyway: the fixed client id finds it (and blocks dupes)
            try:
                o = self.trading.get_order_by_client_id(cid)
            except Exception:
                return {"status": "send_failed", "why": f"{type(e).__name__}: {str(e)[:300]}", "client_order_id": cid}
        return {"status": str(o.status.value), "id": str(o.id), "client_order_id": cid, "limit": round(limit, 2)}

    def order_state(self, order_id: str) -> dict:
        o = self.trading.get_order_by_id(order_id)
        return {"status": str(o.status.value), "filled_qty": float(o.filled_qty or 0),
                "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None}

    def close_limit(self, t: dict, mid: float, natural: float) -> float:
        """Mid plus a growing step per attempt; from attempt 3 or HARD_CLOSE, through the natural price.
        A credit close never pays more than the width (the budgeted max loss), so it always converges."""
        n = t.get("close_attempts", 0)
        step = STEPS[min(n, len(STEPS) - 1)]
        hard = hhmm(ny_now()) >= HARD_CLOSE or n >= 3
        last = hhmm(ny_now()) >= LAST_RESORT
        extra = 0.10 * max(1, n - 2)
        if t["credit"]:  # we pay: higher is more aggressive; LAST_RESORT pays the width (= budgeted max loss)
            px = t["width"] if last else (max(mid + step, natural + extra) if hard else mid + step)
            return round(min(t["width"], max(0.01, px)), 2)
        px = 0.01 if last else (min(mid - step, natural - extra) if hard else mid - step)  # we receive
        return round(max(0.01, px), 2)

    def underlying_price(self, sym: str) -> float | None:
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestTradeRequest

        try:
            return float(self.stocks.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=sym,
                                                                                    feed=DataFeed.IEX))[sym].price)
        except Exception:
            return None

    def spread_mid(self, t: dict) -> tuple[float, float] | None:
        from alpaca.data.enums import OptionsFeed
        from alpaca.data.requests import OptionLatestQuoteRequest

        q = self.options.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=[t["long"], t["short"]],
                                                                          feed=OptionsFeed.INDICATIVE))
        try:
            lb, la = float(q[t["long"]].bid_price), float(q[t["long"]].ask_price)
            sb, sa = float(q[t["short"]].bid_price), float(q[t["short"]].ask_price)
        except (KeyError, TypeError):
            return None
        if la <= 0 or sa <= 0:
            return None
        # (mid value of what we hold as a positive, natural price to close it)
        if t["credit"]:
            return round((sb + sa) / 2 - (lb + la) / 2, 2), round(sa - lb, 2)
        return round((lb + la) / 2 - (sb + sa) / 2, 2), round(lb - sa, 2)

    # --- the loop ------------------------------------------------------------------------------------------------
    def try_entry(self, checkpoint: str) -> None:
        self.done_checkpoints.add(checkpoint)
        for sym in UNDERLYINGS:
            kind, info = self.signal(sym)
            self.log("signal", checkpoint=checkpoint, underlying=sym, kind=kind, **info)
            if not kind:
                continue
            t, why = self.build(sym, kind, info["spot"])
            if t is None:
                self.log("no_trade", checkpoint=checkpoint, underlying=sym, kind=kind, why=why)
                continue
            t.update({"id": f"{self.today:%m%d}{len(self.trades) + 1}", "checkpoint": checkpoint, "status": "pending_open",
                      "signal": info})
            r = self.send(t, "open", t["net"])
            t["open_order"], t["sent_at"] = r, time.time()
            if "id" not in r:  # refused / dry-run / send_failed
                t["status"] = r["status"]
            else:
                t["opened"] = True
            self.trades.append(t)
            self.log("open_order", trade=t)
            self.save()
            break  # at most one new trade per checkpoint

    def _cancel(self, order_id: str) -> None:
        try:
            self.trading.cancel_order_by_id(order_id)
        except Exception as e:  # already filled / cancelled / pending_cancel: the next status read settles it
            self.log("cancel_failed", order_id=order_id, error=str(e)[:200])

    def manage(self) -> None:
        for t in self.trades:
            try:
                self._manage_one(t)
            except Exception as e:  # one trade's failure must never stop the other trades' exits
                self.log("error", id=t.get("id"), error=f"{type(e).__name__}: {str(e)[:300]}")
        self.save()

    def _manage_one(self, t: dict) -> None:
        now = hhmm(ny_now())
        if t["status"] == "pending_open":
            st = self.order_state(t["open_order"]["id"])
            if st["status"] in TERMINAL:
                filled = int(st["filled_qty"])
                if filled > 0:  # filled, or partly filled then cancelled: we hold `filled` spreads
                    t.update({"status": "open", "max_loss": round(t["max_loss"] * filled / t["qty"], 2),
                              "qty": filled, "entry_net": abs(st["filled_avg_price"] or t["net"])})
                    self.log("filled_open", id=t["id"], qty=filled, entry_net=t["entry_net"], order=st["status"])
                else:
                    t["status"] = "not_filled"
                    self.log("open_not_filled", id=t["id"], status=st["status"])
            elif now >= "14:45":
                self._cancel(t["open_order"]["id"])  # settles on a later pass; an open is never re-sent
        elif t["status"] == "open":
            q = self.spread_mid(t)
            if q is None:
                if now < HARD_CLOSE or "last_value" not in t:
                    return
                q = (t["last_value"], t["last_value"])
            value, natural = q
            entry = t["entry_net"]
            pnl = (entry - value) if t["credit"] else (value - entry)
            max_gain = entry if t["credit"] else t["width"] - entry
            max_loss = t["width"] - entry if t["credit"] else entry
            reason = t.get("exit_reason")  # once an exit is decided it is never undecided
            if reason is None:
                spot = self.underlying_price(t["underlying"])
                crossed = spot is not None and t["credit"] and (
                    spot < t["short_strike"] if t["type"] == "put" else spot > t["short_strike"])
                value_stop = -pnl >= (BACKSTOP if t["credit"] else STOP) * max_loss
                # A stop must show on two checks in a row, so one bad quote cannot close a trade.
                t["stop_hits"] = t.get("stop_hits", 0) + 1 if (crossed or value_stop) else 0
                if pnl >= TAKE_PROFIT * max_gain:
                    reason = "take profit (50% of max gain)"
                elif t["stop_hits"] >= 2:
                    reason = (f"stop: {t['underlying']} {spot:.2f} crossed the short strike {t['short_strike']}"
                              if crossed else f"stop ({int((BACKSTOP if t['credit'] else STOP) * 100)}% of max loss)")
                elif now >= TIME_EXIT:
                    reason = "time exit before the close"
            t["last_value"], t["last_pnl"] = value, round(pnl * 100 * t["qty"], 2)
            if reason:
                limit = self.close_limit(t, value, natural)
                r = self.send(t, "close", limit)
                t.update({"exit_reason": reason, "close_order": r, "close_sent": time.time()})
                if "id" in r:
                    t["status"] = "pending_close"
                self.log("close_order", id=t["id"], reason=reason, value=value, natural=natural, limit=limit,
                         attempt=t.get("close_attempts", 0), result=r)
        elif t["status"] == "pending_close":
            st = self.order_state(t["close_order"]["id"])
            if st["status"] in TERMINAL:
                done = int(st["filled_qty"])
                if done > 0:
                    exit_net = abs(st["filled_avg_price"] or 0)
                    per = (t["entry_net"] - exit_net) if t["credit"] else (exit_net - t["entry_net"])
                    t["pnl"] = round(t.get("pnl", 0.0) + per * 100 * done, 2)
                    t["max_loss"] = round(t["max_loss"] * (t["qty"] - done) / t["qty"], 2)
                    t["qty"] -= done
                t["close_attempts"] = t.get("close_attempts", 0) + 1  # next cid and a bigger step
                if t["qty"] <= 0:
                    t["status"] = "closed"
                    self.log("closed", id=t["id"], pnl=t["pnl"], reason=t.get("exit_reason"))
                else:
                    t["status"] = "open"  # re-priced on the next pass, only now that the old order is dead
                    self.log("close_not_filled", id=t["id"], status=st["status"], left=t["qty"])
            elif time.time() - t.get("close_sent", 0) >= (30 if now >= HARD_CLOSE else REPRICE_SEC):
                self._cancel(t["close_order"]["id"])

    def run(self) -> None:
        self.log("start", dry=self.dry, caps={"per_trade": MAX_LOSS_PER_TRADE, "total": MAX_LOSS_TOTAL, "opens": MAX_OPENS})
        while True:
            now = hhmm(ny_now())
            if now >= "16:00":
                break
            try:
                for cp in ENTRY_TIMES:
                    if now >= cp and cp not in self.done_checkpoints and now <= LAST_ENTRY:
                        self.try_entry(cp)
            except Exception as e:  # an entry failure must never skip this pass's exits
                self.log("error", where="entry", error=f"{type(e).__name__}: {str(e)[:300]}")
            self.manage()
            if not any(t["status"] in LIVE for t in self.trades) and now > CLOSE_BY:
                break
            time.sleep(30)
        closed = [t for t in self.trades if t["status"] == "closed"]
        left = [t["id"] for t in self.trades if t["status"] in LIVE]
        if left:
            self.log("ALERT_STILL_OPEN", ids=left, note="close these by hand before 16:00 / check the account")
        self.log("summary", trades=len(self.trades), closed=len(closed),
                 pnl=round(sum(t.get("pnl", 0.0) for t in self.trades), 2), still_open=left)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    state = Path(os.environ.get("TRADER_STATE_DIR", Path(__file__).resolve().parent.parent / "state"))
    Lab(state, dry="--dry" in sys.argv).run()
