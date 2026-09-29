"""V4-08 scratch experiment: fixed-price round trip (bid 650.00 / ask 650.01, never moves) through the REAL Engine
(DRY mode, SimBroker). The expected loss is computed BY HAND below with Decimal from published constants, without
importing costs.py, orders.py, sizing.py or engine helpers. Then compared with the journal and the SimBroker ledger."""
import tempfile, pathlib
from decimal import Decimal as Dc, ROUND_CEILING
from common import *

tmp = pathlib.Path(tempfile.mkdtemp())
reg = C.Registry((T.LAST30,), T.REG.account_last4)
h = T.H(tmp, start="15:29:59", registry=reg, px={"SPY": 650.0, "QQQ": 560.0})
cash0 = h.sim.cash
bars = T.mkbars("SPY", "09:30", "15:29", 650.0, 650.0, wick=0.0)          # flat day: first half hour close 650 > prev close 648
h.step(1, {"SPY": bars})                                                   # 15:30:00, LAST30 long signal
h.until("15:50:30", 1)
lines = h.j.lines
buys = [x for x in lines if x["kind"] == "fill" and x["side"] == "buy"]
sells = [x for x in lines if x["kind"] == "fill" and x["side"] == "sell"]
closed = [x for x in lines if x["kind"] == "trade_closed"]
print("fills:", [(x["side"], x["qty"], x["price"], x["role"], x["fees"]) for x in lines if x["kind"] == "fill"])
print("closed:", [(x["how"], x["paper_pnl"], x["honest_slip"], x["fees"], x["honest_pnl"]) for x in closed])

# ---------------- HAND CALCULATION (no app helpers) ----------------
ask, bid = Dc("650.01"), Dc("650.00")
buy_px, sell_px = ask, bid                                   # a marketable buy fills at the ask, the exit sell at the bid
paper = sell_px - buy_px                                     # -0.01
slip = Dc("0.01") * 2                                        # $0.01 per share per side (published MT-G4 convention)
def up_cent(x): return x.quantize(Dc("0.01"), rounding=ROUND_CEILING)
sec = up_cent(sell_px * 1 * Dc("20.60") / Dc(1_000_000))     # SEC s31, $20.60 per $1M sold, rounded UP to the cent
taf = up_cent(Dc(1) * Dc("0.000195"))                        # FINRA TAF per share sold, rounded UP to the cent
cat_buy = Dc(1) * (Dc("0.000001") + Dc("0.000002"))          # CAT 2026-1 + historical assessment 1A, per share, not rounded
cat_sell = cat_buy
fees = sec + taf + cat_buy + cat_sell
honest = paper - slip - fees
print(f"HAND: paper {paper}  slip {slip}  SEC {sec}  TAF {taf}  CAT {cat_buy}+{cat_sell}  fees {fees}  honest {honest}")

ok = True
def chk(name, got, want, tol=1e-9):
    global ok
    good = abs(float(got) - float(want)) <= tol
    ok &= good
    print(f"  {'OK ' if good else 'BAD'} {name}: app {got} hand {want}")
chk("buy fill price", buys[0]["price"], buy_px)
chk("sell fill price", sells[0]["price"], sell_px)
chk("paper P&L", closed[0]["paper_pnl"], paper)
chk("honest slippage", closed[0]["honest_slip"], slip)
chk("fees total", closed[0]["fees"], fees)
chk("honest P&L", closed[0]["honest_pnl"], honest)
chk("buy-fill fee", buys[0]["fees"], cat_buy)
chk("sell-fill fee", sells[0]["fees"], sec + taf + cat_sell)
# independent ledger: the SimBroker's own cash (not costs.py)
chk("sim cash change (paper P&L)", h.sim.cash - cash0, paper)
print("counters realized_honest", h.c.realized_honest, "realized_pnl", h.c.realized_pnl)
chk("engine counters realized_honest", h.c.realized_honest, honest)
print("no trading gain from no-fill: n_fills =", len(buys) + len(sells))
print("RESULT V4-08 scratch:", "PASS" if ok else "FAIL")
