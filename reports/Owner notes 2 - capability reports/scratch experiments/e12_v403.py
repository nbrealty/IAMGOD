"""V4-03 scratch: an ordinary eligible minute with NO human-strategy signal - does it appear anywhere in the journal as a decision point?
Replays a whole quiet session (390 minutes x 2 symbols, no setup can fire) through the real engine via runner.replay."""
import sys, tempfile, pathlib
sys.path.insert(0, "/home/user/IAMGOD/trading"); sys.path.insert(0, "/home/user/IAMGOD/trading/tests")
sys.dont_write_bytecode = True
import pandas as pd
from datetime import date
from lab.scalp.live import runner as RUN, market as M, journal as J, config as C
from lab.scalp.live.clock import SessionTimes
from lab.scalp.live.model import Mode, Bar, Feed, as_ny
from lab.scalp.signals import Ctx
QUIET = date(2026, 10, 6)
def ts(h, d=QUIET): return as_ny(f"{d} {h}")
def flat_bars(sym, px):
    return [Bar(sym, ts("09:30") + pd.Timedelta(minutes=k), px, px + 0.01, px - 0.01, px, 5000.0, Feed.SIP) for k in range(390)]
bars = {"QQQ": flat_bars("QQQ", 560.0), "SPY": flat_bars("SPY", 650.0)}
st = SessionTimes.from_calendar(QUIET, ts("09:30"), ts("16:00"))
clock = M.SimClock(st.open)
market = M.ReplayMarket(QUIET, bars, M.bar_quote_fn(bars), clock, open_ts=st.open, close_ts=st.close)
j = J.MemoryJournal(Mode.REPLAY, clock)
out = RUN.replay(QUIET, e0=100_000.0, market=market, journal=j, ctx_by_symbol={"QQQ": Ctx(), "SPY": Ctx()}, session=st,
                 state_dir=tempfile.mkdtemp(), out=lambda s: None)
kinds = {}
for x in j.lines:
    kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
print("eligible completed minutes delivered to the engine:", 2 * 390, "| ticks run:", out["ticks"])
print("journal line kinds:", kinds)
print("decision lines (one per human-strategy candidate):", kinds.get("decision", 0), "-> ordinary minutes with no signal leave no per-minute record in the journal")
