"""V4-09 / V4-10 scratch: does the simulator account for displayed liquidity or for fill/payoff association?"""
from common import *
from lab.scalp.live.broker import SimBroker
from lab.scalp.live import orders as O
from dataclasses import replace
import pandas as pd
clk = {"t": T.ts("10:00:01")}
sim = SimBroker(lambda: clk["t"])
sim.update(clk["t"], {"SPY": Quote("SPY", 650.00, 650.01, 1.0, 1.0, clk["t"], clk["t"], Feed.SIM)})   # displayed size: 1 share each side
cand = Candidate("LAST30_MOM_SPY", 1, "SPY", "enter", 1, T.ts("10:00"))
spec = O.entry_bracket(cand, T.LAST30, sim.quotes["SPY"], 1_000_000.0, T.D, 0)[0]
print("displayed ask size = 1 share")
v1 = sim.submit(spec)                                                   # 1 share
v2 = sim.submit(replace(spec, client_order_id=spec.client_order_id.replace("-E0-", "-E1-"), qty=1))   # a second order for the same displayed share
v3 = sim.submit(replace(spec, client_order_id=spec.client_order_id.replace("-E0-", "-E2-"), qty=25))  # 25 shares against 1 displayed
print("order1 1 sh:", v1.status, v1.filled_qty, "| order2 1 sh (same displayed share):", v2.status, v2.filled_qty, "| order3 25 sh vs 1 displayed:", v3.status, v3.filled_qty)
print("position at 'broker':", [(p.symbol, p.qty) for p in sim.positions()])
print("=> SimBroker credits full size at the displayed ask irrespective of displayed size or earlier fills (no liquidity accounting).")
print("   (In the bot this cannot bind: EXPLORATORY_MAX_QTY=1 and one slot; GuardedBroker refuses qty>1 before the SimBroker.)")

# V4-10: a resting take-profit in QUOTE mode fills as soon as the bid reaches the limit; there is no queue/adverse-selection state
sim2 = SimBroker(lambda: clk["t"])
sim2.update(clk["t"], {"SPY": Quote("SPY", 650.00, 650.01, 100.0, 100.0, clk["t"], clk["t"], Feed.SIM)})
p = O.entry_bracket(cand, T.LAST30, sim2.quotes["SPY"], 1_000_000.0, T.D, 0)[0]
v = sim2.submit(p)
tp = p.take_profit
sim2.update(clk["t"], {"SPY": Quote("SPY", tp, tp + 0.01, 1.0, 1.0, clk["t"], clk["t"], Feed.SIM)})   # bid == take-profit limit, size 1 (a touch)
legs = {x.order_type: x.status for x in sim2.get_order(v.id).legs}
print("quote-mode: bid merely EQUALS the take-profit limit ->", legs, "(a touch fills; the MT-G4 rule says a resting limit needs a print STRICTLY through it, enforced only in bar mode / the SIP re-mark)")
