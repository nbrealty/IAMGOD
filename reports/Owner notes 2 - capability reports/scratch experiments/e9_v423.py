"""V4-23 scratch: can the bot ever have opposite-side orders interacting in the same symbol? Track, at EVERY tick of four full
lifecycles, whether a live BUY and a live SELL rest together in one symbol (bracket children of the same parent excluded).
Note: this checks sequencing only; SimBroker does not emulate Alpaca's wash-trade rejection itself."""
from common import *
from lab.scalp.live import orders as O
import pandas as pd

def watch(h, label, until=None, secs=1):
    bad = []
    n = 0
    def check():
        opens = h.sim.open_orders()
        for sym in {o.symbol for o in opens}:
            buys = [o for o in opens if o.symbol == sym and o.side == "buy"]
            sells = [o for o in opens if o.symbol == sym and o.side == "sell"]
            if buys and sells:
                # children of the SAME bracket parent are one complex order for Alpaca (buy parent + its sell legs)
                bad.append((h.t.strftime("%H:%M:%S"), sym, [(o.client_order_id[-9:], o.status) for o in buys], [(o.order_type, o.status) for o in sells]))
    return check, bad

def run_case(label, setup):
    h = setup()
    check, bad = watch(h, label)
    return h, check, bad

# (i) normal entry -> 15:50 TIME_EXIT
reg = C.Registry((T.LAST30,), T.REG.account_last4)
h = T.H(__import__("pathlib").Path(__import__("tempfile").mkdtemp()), start="15:29:59", registry=reg); h.px["SPY"] = 652.0
check, bad = watch(h, "i")
h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)}); check()
while h.t < T.ts("15:52:00"):
    h.step(1); check()
print("(i) entry -> stop confirmed -> 15:50 TIME_EXIT: simultaneous live BUY+SELL in one symbol at any tick:", bad or "never")

# (ii) entry order unfilled -> cancel after 2 s, slow cancel 4 s, then next entry is impossible until the cancel is confirmed
h = T.H(__import__("pathlib").Path(__import__("tempfile").mkdtemp()), start="15:29:59", registry=reg, sim_kw={"fill_delay_s": 1e9, "cancel_delay_s": 4}); h.px["SPY"] = 652.0
check, bad = watch(h, "ii")
h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)}); check()
while h.t < T.ts("15:30:30"):
    h.step(1); check()
print("(ii) unfilled entry, slow cancel:", bad or "never", "| broker submits", len(h.sim.submits))

# (iii) stop watchdog escalation: price gaps below the stop-limit, legs cancelled, PROTECT sell
h = T.H(__import__("pathlib").Path(__import__("tempfile").mkdtemp()), start="15:29:59", registry=reg); h.px["SPY"] = 652.0
check, bad = watch(h, "iii")
h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)}); check(); h.step(1); check()
h.px["SPY"] = h.eng.trade.stop_limit - 1.0
while h.t < T.ts("15:31:00") and h.eng.trade is not None:
    h.step(1); check()
print("(iii) stop escalation:", bad or "never", "| exit reason", [x["reason"] for x in h.j.of("exit_start")])

# (iv) kill switch with legs live
h = T.H(__import__("pathlib").Path(__import__("tempfile").mkdtemp()), start="15:29:59", registry=reg); h.px["SPY"] = 652.0
check, bad = watch(h, "iv")
h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)}); check(); h.step(1); check()
h.eng.request_kill("scratch")
for _ in range(10):
    h.step(1); check()
print("(iv) kill switch:", bad or "never", "| flat", h.flat())
