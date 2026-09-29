"""V4-14 scratch experiment: TWO bot processes on the SAME account. Emulated as two independent Engine objects (own counters,
own journal, own in-memory slot) that share ONE SimBroker (= the one Alpaca account) and ONE state folder (KILL/HALT/blocked
files), ticked alternately with the same market snapshots. This is a logic emulation of two OS processes, not real concurrency."""
import tempfile, pathlib
from common import *
from lab.scalp.live.engine import Engine
from lab.scalp.live.journal import MemoryJournal
from lab.scalp.live.model import DayCounters, MarketSnapshot, Quote, LastTrade, Mode

def two_engines(first="A", parallel_race=False):
    tmp = pathlib.Path(tempfile.mkdtemp())
    reg = C.Registry((T.LAST30,), T.REG.account_last4)
    hA = T.H(tmp / "sA", start="15:29:59", registry=reg)
    hA.state = tmp / "shared"; hA.eng.state_dir = tmp / "shared"          # SAME state folder for both
    # B: separate journal/counters/engine, SAME broker and SAME state folder
    hB = T.H(tmp / "sB", start="15:29:59", registry=reg, sim=hA.sim)
    hB.state = tmp / "shared"; hB.eng.state_dir = tmp / "shared"
    for h in (hA, hB):
        h.px["SPY"] = 652.0
    return hA, hB

def snap(h, t, bars=None):
    h.t = t
    h.last_ok = t
    q = h.quotes()
    tr = {s: LastTrade(s, p + 0.005, 100, t - pd.Timedelta(milliseconds=500), Feed.IEX) for s, p in h.px.items()}
    return MarketSnapshot(t, q, tr, bars or {}, t, 20.0, dict(h.halted))

def tick_both(hA, hB, t, bars=None, order="AB"):
    for tag in order:
        h = hA if tag == "A" else hB
        h.sim.clock = (lambda t=t: t)
        h.sim.update(t, h.quotes() if False else {s: Quote(s, p, round(p + 0.01, 2), 100, 100, t, t, Feed.IEX) for s, p in h.px.items()})
        h.eng.tick(snap(h, t, bars))

def summarize(tag, hA, hB):
    print(f"  [{tag}] broker: submits={len(hA.sim.submits)} positions={[(p.symbol, p.qty) for p in hA.sim.positions()]} open_orders={len(hA.sim.open_orders())}")
    for n, h in (("A", hA), ("B", hB)):
        k = [x for x in h.j.kinds() if x in ("would_submit", "reconcile_mismatch", "reconcile_halt", "kill_start", "kill_done", "kill_order", "fill", "trade_closed", "halt_seen", "exit_start", "broker_error")]
        from collections import Counter
        print(f"     engine {n}: slot={h.eng.slot_state.value} flags={sorted(f.value for f in h.eng.flags)} lines={dict(Counter(k))}")

print("=== S1: both engines see the same 15:29 bar; A ticks first each second")
hA, hB = two_engines()
bars = T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)
t0 = T.ts("15:30:00")
tick_both(hA, hB, t0, {"SPY": bars})
decA = [d for d in hA.j.of("decision")]; decB = [d for d in hB.j.of("decision")]
print("  A decision:", [(d["accepted"], d["reasons"]) for d in decA], "| B decision:", [(d["accepted"], d["reasons"]) for d in decB])
summarize("15:30:00", hA, hB)
for s in range(1, 13):
    tick_both(hA, hB, t0 + pd.Timedelta(seconds=s))
summarize("15:30:12", hA, hB)
print("  HALT file present:", (hA.state / "HALT-dry").exists() or (hA.state / "HALT").exists(), " (dry-mode names)")
print("  broker orders touched by B's kill: cancels =", len(hA.sim.cancels), " kill/sell orders in submits =", [s.client_order_id.split('-')[2] + '-' + s.client_order_id.split('-')[4] for s in hA.sim.submits])

print("=== S2: RACE - both pass every pre-check in the same instant (B's pre-submit reconcile skipped to emulate the race), same client id")
hA, hB = two_engines()
from lab.scalp.live import engine as EN
orig_rec = EN.Engine._reconcile
hB.eng._reconcile = lambda now, force=False: [] if force else orig_rec(hB.eng, now, force)
tick_both(hA, hB, t0, {"SPY": bars})
decA = [d for d in hA.j.of("decision")]; decB = [d for d in hB.j.of("decision")]
print("  A decision:", [(d["accepted"], d["reasons"]) for d in decA], "| B decision:", [(d["accepted"], d["reasons"]) for d in decB])
print("  broker submits:", len(hA.sim.submits), " same client id for A and B parent:",
      hA.eng.trade.parent_cid == hB.eng.trade.parent_cid if hA.eng.trade and hB.eng.trade else None)
print("  both engines track the SAME broker order:", hA.eng.trade.parent_id == hB.eng.trade.parent_id if hA.eng.trade and hB.eng.trade else None)
# now both try to exit at 15:50 with the same deterministic exit ids
hA.px["SPY"] = 652.0
for s in range(1, 20 * 60 + 40):
    tick_both(hA, hB, t0 + pd.Timedelta(seconds=s))
    if not hA.sim.positions() and not hA.sim.open_orders() and s > 60:
        break
summarize("after 15:50 flatten", hA, hB)
print("  sells sent to the broker:", [(s.client_order_id.split('-')[4], s.qty) for s in hA.sim.submits if s.side == 'sell'])
print("  broker never short:", all(p.qty >= 0 for p in hA.sim.positions()))
