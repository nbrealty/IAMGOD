"""Book O's own ledger (owner decision 6, OPT-7, OPT-16, OPT-26).

The shared paper account holds the rules book's stock and book O's option spreads side by side. This ledger
records what O owns, so each book values, reconciles and trades only its own things:
- open spreads (`SpreadLot`) booked from actual (possibly partial) mleg fills (OPT-7);
- MaxLoss and budgeted loss from strikes and the actual fill credit, never from Claude's numbers (OPT-7);
- honest costs counted twice (OPT-16): results at the paper fill, and under the one cost model
  (half the quoted cost at entry and at exit plus model fees);
- the "amount invested" per trade = the MaxLoss committed at entry (owner decision 6);
- stock that O received from an assignment (OPT-26), which O sells and the rules book never adopts;
- daily marks for the breakers (OPT-30, OPT-31).

State lives in `state_dir/options/ledger.json` (JSON, written atomically), separate from the stock books.
Money is in dollars for the whole position unless a name ends in `_per_share`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path

import pandas as pd

from ..config import STATE_DIR
from .book import OPEN_STATUSES, breaker_status, dte, num, ob_policy, open_fraction, to_date
from .models import MULTIPLIER, OptionLeg, OptionQuote, SpreadLot

LEDGER_FILE = "ledger.json"
DEFAULT_MODEL_FEE = 0.04  # rulebook cost model: $0.04 per contract per side, each leg


def _model_fee(policy) -> float:
    return float(ob_policy(policy).get("cost_model_fee_per_contract", DEFAULT_MODEL_FEE))


def _legs_quoted_cost(quotes: dict | None) -> float | None:
    """Sum of (ask - bid) over the two legs from {"short": {bid, ask}, "long": {bid, ask}}; None if missing."""
    if not quotes:
        return None
    total = 0.0
    for leg in ("short", "long"):
        q = quotes.get(leg) or {}
        bid, ask = num(q.get("bid")), num(q.get("ask"))
        if bid is None or ask is None or ask < bid:
            return None
        total += ask - bid
    return total


def _legs_mid(quotes: dict | None) -> float | None:
    """Short mid minus long mid, per share (the spread's mid credit to open or mid debit to close)."""
    if not quotes or _legs_quoted_cost(quotes) is None:
        return None
    s, lg = quotes["short"], quotes["long"]
    return (float(s["bid"]) + float(s["ask"])) / 2 - (float(lg["bid"]) + float(lg["ask"])) / 2


def entry_credit_from_fill(fill: dict) -> float | None:
    """Credit per share actually received. Accepts leg prices {"legs": {short, long}}, `credit_per_share`

    (positive = credit), or Alpaca's signed mleg `net_price` (negative = credit, OPT-14).
    """
    legs = fill.get("legs") or {}
    if num(legs.get("short")) is not None and num(legs.get("long")) is not None:
        return float(legs["short"]) - float(legs["long"])
    if num(fill.get("credit_per_share")) is not None:
        return float(fill["credit_per_share"])
    if num(fill.get("net_price")) is not None:
        return -float(fill["net_price"])
    return None


def exit_debit_from_fill(fill: dict) -> float | None:
    """Debit per share actually paid to close. Leg prices, `debit_per_share`, or signed `net_price` (debit > 0)."""
    legs = fill.get("legs") or {}
    if num(legs.get("short")) is not None and num(legs.get("long")) is not None:
        return float(legs["short"]) - float(legs["long"])
    if num(fill.get("debit_per_share")) is not None:
        return float(fill["debit_per_share"])
    if num(fill.get("net_price")) is not None:
        return float(fill["net_price"])
    return None


def filled_contracts(fill: dict) -> int:
    """Whole contracts in this fill report (OPT-7). Missing, NaN or negative -> 0.

    `contracts` is the quantity of THIS fill (an increment). `filled_qty` is Alpaca's running total for the
    whole order; the ledger books only the part it has not booked yet (see OptionsBook._increment).
    """
    return max(0, int(num(fill.get("contracts", fill.get("filled_qty")), 0.0)))


def _is_cumulative(fill: dict) -> bool:
    return "contracts" not in fill and "filled_qty" in fill


@dataclass
class OptionsBook:
    """Book O's ledger. JSON-safe through to_dict/from_dict; `lots` holds every spread that is not closed."""

    lots: dict[str, SpreadLot] = field(default_factory=dict)
    # One record per closed spread; see _closed_record for the fields.
    closed: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)  # {date, kind, lot_id, detail}
    o_stock: dict[str, float] = field(default_factory=dict)  # shares O owns after an assignment (OPT-26)
    marks: list[dict] = field(default_factory=list)  # {date, o_pnl, day_pnl} for OPT-30 / OPT-31
    peak_pnl: float = 0.0  # O's own high-water mark of cumulative P&L (OPT-31)
    halted: bool = False  # OPT-31 latch; only the owner resets it
    seq: int = 0
    # Fill idempotency: per order_id {qty, value} already booked (value = price x qty), and fill ids seen.
    order_fills: dict[str, dict] = field(default_factory=dict)
    seen_fill_ids: list[str] = field(default_factory=list)

    # --- persistence ------------------------------------------------------------------------------

    @staticmethod
    def path(state_dir: Path = STATE_DIR) -> Path:
        return Path(state_dir) / "options" / LEDGER_FILE

    def to_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["lots"] = {k: l.to_dict() for k, l in self.lots.items()}
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> "OptionsBook":
        d = dict(d or {})
        known = {f.name for f in fields(cls)}
        d = {k: v for k, v in d.items() if k in known}  # tolerate newer or older files
        d["lots"] = {k: SpreadLot.from_dict(v) for k, v in (d.get("lots") or {}).items()}
        return cls(**d)

    @classmethod
    def load(cls, state_dir: Path = STATE_DIR) -> "OptionsBook":
        p = cls.path(state_dir)
        return cls.from_dict(json.loads(p.read_text())) if p.exists() else cls()

    def save(self, state_dir: Path = STATE_DIR) -> None:
        p = self.path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, default=str))
        tmp.replace(p)

    # --- queries -----------------------------------------------------------------------------------

    def open_lots(self) -> list[SpreadLot]:
        return [l for l in self.lots.values() if l.status in OPEN_STATUSES]

    def all_lots(self) -> list[SpreadLot]:
        """Open lots plus closed ones rebuilt from their records (for OPT-18/OPT-24 cycle checks)."""
        return self.open_lots() + [SpreadLot.from_dict(r["lot"]) for r in self.closed if r.get("lot")]

    def committed_max_loss(self) -> float:
        """Owner decision 6: the amount invested = MaxLoss still committed by the open spreads.

        A partial close releases its share: MaxLoss x (open + assigned-but-unsettled contracts) / entry contracts.
        """
        return sum(float(l.max_loss) * open_fraction(l) for l in self.open_lots())

    def open_budgeted_loss(self) -> float:
        """OPT-9: budgeted loss still committed (pro rata after partial closes)."""
        return sum(float(l.budgeted_loss) * open_fraction(l) for l in self.open_lots())

    def invested_per_trade(self) -> list[dict]:
        """Owner decision 6: one row per trade with the MaxLoss committed at entry (`invested`) and now."""
        rows = [{"lot_id": l.lot_id, "entry_date": l.entry_date, "invested": l.max_loss,
                 "committed": float(l.max_loss) * open_fraction(l), "status": l.status} for l in self.open_lots()]
        rows += [{"lot_id": r["lot_id"], "entry_date": r["entry_date"], "invested": r["max_loss"],
                  "committed": 0.0, "status": "closed"} for r in self.closed]
        return sorted(rows, key=lambda r: str(r["entry_date"]))

    def closed_rs(self) -> list[float]:
        """R_net of each closed spread (= R_model, the cost-model view) for OPT-32."""
        return [float(r["R"]) for r in self.closed if num(r.get("R")) is not None]

    def week_count(self, date) -> int:
        """OPT-9: spreads opened in the ISO week of `date` (open or closed)."""
        wk = pd.Timestamp(to_date(date)).isocalendar()[:2]
        dates = [l.entry_date for l in self.open_lots()] + [r["entry_date"] for r in self.closed]
        return sum(1 for d in dates if d and pd.Timestamp(d).isocalendar()[:2] == wk)

    def loss_exit_expiries(self) -> set[str]:
        """OPT-24: expiries in which a spread was closed at a loss."""
        return {r["expiry"] for r in self.closed if num(r.get("pnl"), 0.0) < 0}

    def realized_pnl_actual(self) -> float:
        """Cash P&L at the paper fills, minus actual fees (what the account really made)."""
        closed = sum(float(r["realized_pnl"]) - float(r.get("fees_actual", 0.0)) for r in self.closed)
        opened = sum(float(l.realized_pnl) - float(l.tags.get("fees_actual", 0.0)) for l in self.open_lots())
        return closed + opened

    def _event(self, date, kind: str, lot_id: str | None, **detail) -> None:
        self.events.append({"date": str(date), "kind": kind, "lot_id": lot_id, **detail})

    def _increment(self, fill: dict, price: float | None) -> tuple[int, float | None, str | None]:
        """Contracts and price per share of the NEW part of a fill report; (0, None, why) when nothing is new.

        A `fill_id` seen before is a duplicate. With `filled_qty` (Alpaca's running total for the order) only
        the part above what this order already booked is new, and the price is read as the order's average fill
        price, so the new part's price is (avg x total - booked value) / new. With `contracts` the report is one
        increment at its own price.
        """
        fid = fill.get("fill_id") or fill.get("execution_id")
        if fid and str(fid) in self.seen_fill_ids:
            return 0, None, "duplicate fill_id"
        k = filled_contracts(fill)
        oid = fill.get("order_id")
        done = self.order_fills.get(str(oid), {"qty": 0, "value": 0.0}) if oid else {"qty": 0, "value": 0.0}
        if _is_cumulative(fill) and oid:
            new = k - int(done["qty"])
            if new <= 0:
                return 0, None, "no new contracts in the order's running filled_qty"
            if price is not None:
                price = (price * k - float(done["value"])) / new
            k = new
        if k <= 0 or price is None:
            return 0, None, None
        return k, price, None

    def _mark_booked(self, fill: dict, k: int, price: float) -> None:
        fid = fill.get("fill_id") or fill.get("execution_id")
        if fid:
            self.seen_fill_ids.append(str(fid))
        oid = fill.get("order_id")
        if oid:
            d = self.order_fills.setdefault(str(oid), {"qty": 0, "value": 0.0})
            d["qty"] = int(d["qty"]) + k
            d["value"] = float(d["value"]) + price * k

    def apply_breakers(self, *, day_pnl, o_pnl, equity, date=None, policy: dict | None = None) -> dict:
        """OPT-30/31/32 from this ledger's peak, closed R and latch. An OPT-31 halt is latched in `halted`, so
        entries stay stopped even if the drawdown later recovers, until the owner calls reset_halt (like RISK-15).
        """
        st = breaker_status(day_pnl=day_pnl, o_pnl=o_pnl, o_peak=self.peak_pnl, equity=equity,
                            closed_rs=self.closed_rs(), halted=self.halted, policy=policy)
        if st["halt"] and not self.halted:
            self.halted = True
            self._event(date, "halted", None, reasons=st["reasons"])
        return st

    def reset_halt(self, date, by: str = "owner") -> None:
        """Only the owner resets the OPT-31 halt."""
        self.halted = False
        self._event(date, "halt_reset", None, by=by)

    def _new_id(self, date) -> str:
        self.seq += 1
        return f"O-{to_date(date).isoformat()}-{self.seq}"

    # --- entries (OPT-7, OPT-16) ------------------------------------------------------------------

    def open_spread(self, candidate: dict, fill: dict, date, *, shadow: bool = True, lot_id: str | None = None,
                    tags: dict | None = None, policy: dict | None = None) -> SpreadLot | None:
        """Book an entry fill. Only the filled contracts become the lot; the rest is cancelled, not chased (OPT-7).

        A second fill for the same `order_id` merges into its lot (one order, not an add); a repeated report
        books nothing new (see _increment). Returns the lot or None when nothing filled or the credit is unknown.
        The shadow book (OPT-36) passes its model fill as the credit (mid credit - half the quoted cost) with the
        leg quotes, so its R_paper and R_model differ only by fees.
        """
        order_id = fill.get("order_id")
        lot = next((l for l in self.open_lots() if order_id and l.tags.get("order_id") == order_id), None)
        k, credit, dup = self._increment(fill, entry_credit_from_fill(fill))
        if k <= 0 or credit is None:
            self._event(date, "duplicate_fill" if dup else "entry_not_filled", lot.lot_id if lot else None,
                        order_id=order_id, requested=fill.get("requested"), **({"why": dup} if dup else {}))
            return lot if dup else None
        self._mark_booked(fill, k, credit)
        if lot is None:
            lot = self._new_lot(candidate, date, shadow, lot_id, tags)
            self.lots[lot.lot_id] = lot
        self._add_entry(lot, candidate, fill, k, credit, date, policy)
        return lot

    def _new_lot(self, c: dict, date, shadow: bool, lot_id, tags) -> SpreadLot:
        s, lg = c["short"], c["long"]
        return SpreadLot(
            lot_id=lot_id or self._new_id(date), underlying=c["underlying"], expiry=c["expiry"],
            type=c.get("type", "put"),
            short_leg=OptionLeg(s["symbol"], c.get("type", "put"), float(s["strike"]), c["expiry"], "short", 0),
            long_leg=OptionLeg(lg["symbol"], c.get("type", "put"), float(lg["strike"]), c["expiry"], "long", 0),
            contracts=0, width=abs(float(s["strike"]) - float(lg["strike"])), entry_credit_per_share=0.0,
            max_loss=0.0, budgeted_loss=0.0, entry_date=to_date(date).isoformat(), status="open", shadow=shadow,
            tags={**(tags or {}), "entry_contracts": 0, "fees_actual": 0.0, "model_pnl_adj": 0.0})

    def _add_entry(self, lot, c, fill, k, credit, date, policy) -> None:
        """Weighted credit; MaxLoss and budget from the actual credit (OPT-7); cost model and slippage (OPT-16)."""
        old = lot.contracts
        lot.entry_credit_per_share = (lot.entry_credit_per_share * old + credit * k) / (old + k)
        lot.contracts = old + k
        lot.short_leg.qty = lot.long_leg.qty = lot.contracts
        qc = _legs_quoted_cost(fill.get("quotes"))
        qc = num(c.get("quoted_cost"), 0.0) if qc is None else qc
        mid = _legs_mid(fill.get("quotes"))
        mid = num(c.get("mid_credit"), credit) if mid is None else mid
        max_loss = (lot.width - lot.entry_credit_per_share) * MULTIPLIER * lot.contracts
        if max_loss <= 0:
            self._event(date, "warning", lot.lot_id, detail="fill credit >= width; MaxLoss floored at 0")
        lot.max_loss = max(0.0, max_loss)
        qc_total = lot.tags.get("entry_quoted_cost_dollars", 0.0) + qc * MULTIPLIER * k
        lot.tags["entry_quoted_cost_dollars"] = qc_total
        lot.budgeted_loss = lot.max_loss + qc_total + 4 * float(ob_policy(policy)["fees_per_contract"]) * lot.contracts
        lot.tags["model_fee"] = _model_fee(policy)
        lot.costs += 0.5 * qc * MULTIPLIER * k + 2 * lot.tags["model_fee"] * k
        lot.tags["model_fees"] = float(lot.tags.get("model_fees", 0.0)) + 2 * lot.tags["model_fee"] * k
        lot.tags["fees_actual"] += num(fill.get("fees"), 2 * float(ob_policy(policy)["fees_per_contract"]) * k)
        lot.tags["entry_contracts"] += k
        lot.tags["order_id"] = fill.get("order_id")
        # OPT-16 model view: the entry would have filled at mid - half the quoted cost.
        lot.tags["model_pnl_adj"] += ((mid - 0.5 * qc) - credit) * MULTIPLIER * k
        lot.events.append(self._fill_row(date, "entry", c, fill, k, credit, mid, qc))
        self._event(date, "entry_fill", lot.lot_id, contracts=k, requested=fill.get("requested"),
                    credit=credit, remainder_cancelled=max(0, int(num(fill.get("requested"), k)) - k))

    @staticmethod
    def _fill_row(date, kind, c, fill, k, price, mid, qc) -> dict:
        """OPT-16 honest-cost log row: bid/ask/mid per leg at decision and at fill, slippage, underlying move.

        Slippage is None (unknown) when there is no mid at the fill.
        """
        # entry: slippage = credit given up vs mid; exit: extra debit paid vs mid. Positive = worse for us.
        slip = None if mid is None else ((mid - price) if kind == "entry" else (price - mid))
        spot_d, spot_f = num(c.get("spot")), num(fill.get("spot"))
        decision = {k2: c.get(k2) for k2 in ("mid_credit", "quoted_cost", "spot")}
        for leg in ("short", "long"):
            lq = c.get(leg)
            decision[leg] = {x: lq.get(x) for x in ("symbol", "bid", "ask", "mid") if x in lq} \
                if isinstance(lq, dict) else None
        return {
            "date": str(date), "kind": kind, "contracts": k, "price_per_share": price, "mid_at_fill": mid,
            "quoted_cost_at_fill": qc, "decision": decision,
            "quotes_at_fill": fill.get("quotes"), "slippage_per_share": slip,
            "slippage_dollars": None if slip is None else slip * MULTIPLIER * k,
            "slippage_pct_of_mid": (slip / abs(mid)) if slip is not None and mid else None,
            "spot_at_fill": spot_f,
            "spot_move_pct": (spot_f / spot_d - 1) if spot_d and spot_f is not None else None,
            "order_id": fill.get("order_id"),
        }

    # --- exits ------------------------------------------------------------------------------------

    def close_spread(self, lot_id: str, fill: dict, date, reason: str, *, policy: dict | None = None) -> dict | None:
        """Book an exit fill (whole spread, both legs). A partial fill closes only what filled; the lot stays open

        with the rest. Returns the closed-spread record when the lot reaches zero, else None. Repeated reports of
        the same order book nothing new (see _increment). `decision_quotes` ({short, long} bid/ask/mid) and
        `decision_spot` log the decision-time view (OPT-16). `settlement: True` marks an expiry with no trade
        (no quoted cost, no fees).
        """
        lot = self.lots.get(lot_id)
        if lot is None:
            self._event(date, "exit_not_filled", lot_id, reason=reason)
            return None
        k, debit, dup = self._increment(fill, exit_debit_from_fill(fill))
        k = min(k, lot.contracts)
        if k <= 0 or debit is None:
            self._event(date, "duplicate_fill" if dup else "exit_not_filled", lot_id, reason=reason,
                        **({"why": dup} if dup else {}))
            return None
        self._mark_booked(fill, k, debit)
        settlement = bool(fill.get("settlement"))
        qc = 0.0 if settlement else _legs_quoted_cost(fill.get("quotes"))
        if qc is None:  # no exit quotes logged: charge the entry's quoted cost per share (safer than zero)
            n0 = max(1, int(lot.tags.get("entry_contracts", 0) or 1))
            qc = float(lot.tags.get("entry_quoted_cost_dollars", 0.0)) / (MULTIPLIER * n0)
        mid = _legs_mid(fill.get("quotes"))
        dq = fill.get("decision_quotes") or {}
        c = {"spot": fill.get("decision_spot"), "short": dq.get("short"), "long": dq.get("long")}
        fee = 0.0 if settlement else float(lot.tags.get("model_fee", _model_fee(policy)))
        lot.realized_pnl += (lot.entry_credit_per_share - debit) * MULTIPLIER * k
        lot.costs += 0.5 * qc * MULTIPLIER * k + 2 * fee * k
        lot.tags["model_fees"] = float(lot.tags.get("model_fees", 0.0)) + 2 * fee * k
        lot.tags["fees_actual"] += num(fill.get("fees"), 2 * float(ob_policy(policy)["fees_per_contract"]) * k)
        # model view: exit at mid + half the quoted cost; with no mid the fill is taken as the mid
        model_debit = (mid if mid is not None else debit) + 0.5 * qc
        lot.tags["model_pnl_adj"] += (debit - model_debit) * MULTIPLIER * k
        paid = (lot.exit_debit_per_share or 0.0) * lot.tags.get("exit_contracts", 0) + debit * k
        lot.tags["exit_contracts"] = lot.tags.get("exit_contracts", 0) + k
        lot.exit_debit_per_share = paid / lot.tags["exit_contracts"]
        lot.contracts -= k
        lot.short_leg.qty -= k
        lot.long_leg.qty -= k
        lot.events.append(self._fill_row(date, "exit", c, fill, k, debit, mid, qc))
        self._event(date, "exit_fill", lot_id, contracts=k, debit=debit, reason=reason)
        return self._maybe_close(lot, date, reason)

    def settle_expiry_worthless(self, lot_id: str, date, spot, reason: str = "expired worthless") -> dict | None:
        """Both puts expired out of the money (spot at or above the short strike): the close debit is 0."""
        lot = self.lots.get(lot_id)
        s = num(spot)
        if lot is None or s is None or s < lot.short_leg.strike or dte(lot.expiry, date) > 0:
            return None
        return self.close_spread(lot_id, {"contracts": lot.contracts, "debit_per_share": 0.0, "fees": 0.0,
                                          "settlement": True}, date, reason)

    # --- assignment (OPT-26) ----------------------------------------------------------------------

    def record_assignment(self, lot_id: str, contracts: int, date) -> None:
        """The short put was assigned: O now owns 100 shares per contract at the short strike (O sells them)."""
        lot = self.lots[lot_id]
        k = min(int(contracts), int(lot.short_leg.qty))
        if k <= 0:
            return
        shares = k * MULTIPLIER
        lot.short_leg.qty -= k
        lot.contracts = min(lot.short_leg.qty, lot.long_leg.qty)
        b = lot.tags.setdefault("broken", {"contracts": 0, "shares_open": 0.0, "settle_debit": 0.0})
        b["contracts"] += k
        b["shares_open"] += shares
        self.o_stock[lot.underlying] = self.o_stock.get(lot.underlying, 0.0) + shares
        lot.status = "incident"
        self._event(date, "assignment", lot_id, contracts=k, shares=shares, strike=lot.short_leg.strike)

    def record_stock_sale(self, lot_id: str, shares: float, price: float, date) -> dict | None:
        """OPT-26 step 1: O sold assigned stock. The loss vs the strike is part of the spread's settlement."""
        lot = self.lots[lot_id]
        b = lot.tags.get("broken") or {}
        q = min(float(shares), float(b.get("shares_open", 0.0)))
        if q <= 0:
            return None
        b["shares_open"] -= q
        b["settle_debit"] += (lot.short_leg.strike - float(price)) * q
        self.o_stock[lot.underlying] = self.o_stock.get(lot.underlying, 0.0) - q
        if abs(self.o_stock[lot.underlying]) < 1e-9:
            del self.o_stock[lot.underlying]
        self._event(date, "stock_sale", lot_id, shares=q, price=float(price))
        return self._maybe_finish_broken(lot, date)

    def close_orphan_long(self, lot_id: str, contracts: int, price: float, date) -> dict | None:
        """OPT-26 step 2 (only after the stock is flat): sell the long put that lost its short partner."""
        lot = self.lots[lot_id]
        b = lot.tags.get("broken") or {}
        k = min(int(contracts), int(lot.long_leg.qty - lot.short_leg.qty))
        if k <= 0 or b.get("shares_open", 0.0) > 1e-9:
            return None
        lot.long_leg.qty -= k
        b["settle_debit"] -= float(price) * MULTIPLIER * k
        b["longs_sold"] = b.get("longs_sold", 0) + k
        self._event(date, "orphan_long_sold", lot_id, contracts=k, price=float(price))
        return self._maybe_finish_broken(lot, date)

    def _maybe_finish_broken(self, lot: SpreadLot, date) -> dict | None:
        b = lot.tags.get("broken") or {}
        if b.get("shares_open", 0.0) > 1e-9 or lot.long_leg.qty != lot.short_leg.qty or not b.get("contracts"):
            return None
        k = b["contracts"]
        lot.realized_pnl += lot.entry_credit_per_share * MULTIPLIER * k - b["settle_debit"]
        lot.costs += 2 * float(lot.tags.get("model_fee", DEFAULT_MODEL_FEE)) * k
        lot.tags["model_fees"] = float(lot.tags.get("model_fees", 0.0)) + \
            2 * float(lot.tags.get("model_fee", DEFAULT_MODEL_FEE)) * k
        debit = b["settle_debit"] / (MULTIPLIER * k)
        done = lot.tags.get("exit_contracts", 0)
        lot.exit_debit_per_share = ((lot.exit_debit_per_share or 0.0) * done + debit * k) / (done + k)
        lot.tags["exit_contracts"] = done + k
        lot.tags["broken"] = {"contracts": 0, "shares_open": 0.0, "settle_debit": 0.0}
        lot.status = "open"
        return self._maybe_close(lot, date, "OPT-26 assignment clean-up")

    def _maybe_close(self, lot: SpreadLot, date, reason: str) -> dict | None:
        if lot.contracts > 0 or lot.short_leg.qty > 0 or lot.long_leg.qty > 0:
            return None
        lot.status = "closed"
        rec = _closed_record(lot, date, reason)
        self.closed.append(rec)
        del self.lots[lot.lot_id]
        self._event(date, "closed", lot.lot_id, reason=reason, pnl=rec["pnl"], R=rec["R"])
        return rec

    # --- marks and breakers inputs (OPT-30, OPT-31) -------------------------------------------------

    def record_mark(self, date, o_pnl: float) -> float:
        """Store O's cumulative P&L for `date`; return today's change (day P&L). Updates the high-water mark."""
        d = to_date(date).isoformat()
        hist = [m for m in self.marks if m["date"] != d]
        prev = hist[-1]["o_pnl"] if hist else 0.0
        day = float(o_pnl) - float(prev)
        hist.append({"date": d, "o_pnl": round(float(o_pnl), 2), "day_pnl": round(day, 2)})
        self.marks = hist
        self.peak_pnl = max(float(self.peak_pnl), float(o_pnl))
        return day


def _closed_record(lot: SpreadLot, date, reason: str) -> dict:
    """One row per closed spread, with R at the paper fill and under the cost model (OPT-16).

    Two views only, no third blend: `R_paper` = (paper-fill P&L - actual fees) / MaxLoss, and `R_model` = the
    P&L had every fill been at the cost model's price (entry at mid - half the quoted cost, exit at mid + half
    the quoted cost) minus model fees, / MaxLoss. The headline `R` (R_net, used by OPT-32) and `pnl` (used by
    the OPT-24 loss test) are the cost-model view. `costs` is kept for display only: it is the model's costs
    measured from mid and must not be subtracted from the paper fill again.
    """
    fees = float(lot.tags.get("fees_actual", 0.0))
    ml = float(lot.max_loss)
    # model fees: 2 legs per contract per side traded (legacy lots: assume both sides)
    model_fees = float(lot.tags["model_fees"]) if "model_fees" in lot.tags else \
        4 * float(lot.tags.get("model_fee", DEFAULT_MODEL_FEE)) * int(lot.tags.get("entry_contracts", 0))
    model_pnl = lot.realized_pnl + float(lot.tags.get("model_pnl_adj", 0.0)) - model_fees
    return {
        "date": to_date(date).isoformat(), "lot_id": lot.lot_id, "underlying": lot.underlying,
        "expiry": lot.expiry, "type": lot.type, "short_strike": lot.short_leg.strike,
        "long_strike": lot.long_leg.strike, "width": lot.width, "contracts": int(lot.tags.get("entry_contracts", 0)),
        "entry_date": lot.entry_date, "entry_credit": lot.entry_credit_per_share,
        "exit_debit": lot.exit_debit_per_share, "max_loss": ml, "invested": ml, "budgeted_loss": lot.budgeted_loss,
        "realized_pnl": lot.realized_pnl, "costs": lot.costs, "fees_actual": fees,
        "pnl": model_pnl, "pnl_paper": lot.realized_pnl - fees,
        "R": model_pnl / ml if ml > 0 else None,
        "R_paper": (lot.realized_pnl - fees) / ml if ml > 0 else None,
        "R_model": model_pnl / ml if ml > 0 else None,
        "reason": reason, "shadow": lot.shadow, "tags": dict(lot.tags), "lot": lot.to_dict(),
    }


# --- equity attribution (owner decision 6) ----------------------------------------------------------


def _mid_of(q: OptionQuote | None) -> float | None:
    return q.mid if isinstance(q, OptionQuote) else None


def lot_unrealized(lot: SpreadLot, quotes, spot=None) -> dict:
    """Mark one open lot. Intact spreads: credit - (short mid - long mid), per share x 100 x contracts; a missing

    quote marks the spread at the width cap (the worst case). Assigned stock is marked at `spot` (at the strike,
    flagged unmarked, when spot is missing); leftover long puts at their mid (0 when missing).
    """
    qmap = {q.symbol: q for q in (quotes or []) if isinstance(q, OptionQuote)}
    sm, lm = _mid_of(qmap.get(lot.short_leg.symbol)), _mid_of(qmap.get(lot.long_leg.symbol))
    unmarked = sm is None or lm is None
    close_cost = lot.width if unmarked else min(lot.width, max(0.0, sm - lm))
    value = (lot.entry_credit_per_share - close_cost) * MULTIPLIER * lot.contracts
    b = lot.tags.get("broken") or {}
    if b.get("contracts"):
        s = num(spot)
        unmarked = unmarked or (b.get("shares_open") and s is None)
        stock_loss = (lot.short_leg.strike - (s if s is not None else lot.short_leg.strike)) * b["shares_open"]
        extra_longs = max(0, lot.long_leg.qty - lot.short_leg.qty)
        value += lot.entry_credit_per_share * MULTIPLIER * b["contracts"] - b["settle_debit"] - stock_loss \
            + (lm or 0.0) * MULTIPLIER * extra_longs
    return {"unrealized": value, "unmarked": bool(unmarked)}


def o_pnl(ledger: OptionsBook, quotes, spot=None) -> float:
    """O's cumulative P&L: realized at the paper fills (minus actual fees) plus the open lots' marks."""
    return ledger.realized_pnl_actual() + sum(lot_unrealized(l, quotes, spot)["unrealized"]
                                              for l in ledger.open_lots())


def o_value(ledger: OptionsBook, quotes, spot=None) -> float:
    """O's share of the shared account (rulebook Conventions): committed MaxLoss + realized P&L + open marks.

    The rules book's equity is account equity minus this (see rules_equity).
    """
    return ledger.committed_max_loss() + o_pnl(ledger, quotes, spot)


def rules_equity(account_equity: float, ledger: OptionsBook, quotes, spot=None) -> float:
    """Owner decision 6: the rules book's equity = account equity - O's value."""
    return float(account_equity) - o_value(ledger, quotes, spot)
