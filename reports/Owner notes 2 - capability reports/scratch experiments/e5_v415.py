"""V4-15 scratch experiment: STATE FOLDER FULL (real ENOSPC on a tiny tmpfs) or unwritable while a protected position is open.
Answers: what does a failing journal/heartbeat/flag write do to entries, exits, the heartbeat and the watchdog?"""
import os, sys, tempfile, pathlib, traceback, shutil
from common import *
from lab.scalp.live import journal as J, state as S, runner as RUN, watchdog as W
from lab.scalp.live.model import MarketSnapshot, Quote, LastTrade, Mode

TINY = pathlib.Path("/tmp/claude-0/-home-user-IAMGOD/6e4d9533-109b-52a4-b160-33463d24abe1/scratchpad/capability/exp/tiny")

def fill_disk():
    n = 0
    fd = os.open(TINY / "filler.bin", os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        while True:
            try:
                os.write(fd, b"x" * 512); n += 512
            except OSError:
                break
    finally:
        os.close(fd)
    return n

def free_disk():
    (TINY / "filler.bin").unlink(missing_ok=True)

def fresh(start="15:29:59", journal_on_tiny=True):
    for p in TINY.iterdir():
        if p.is_file(): p.unlink()
        else: shutil.rmtree(p, ignore_errors=True)
    reg = C.Registry((T.LAST30,), T.REG.account_last4)
    h = T.H(pathlib.Path(tempfile.mkdtemp()), start=start, registry=reg)
    fj = J.FileJournal(TINY / "journal.jsonl", Mode.DRY, h.clock)
    h.eng.journal = fj; h.eng.broker.journal = fj
    h.eng.state_dir = TINY; h.state = TINY
    h.px["SPY"] = 652.0
    return h, fj

BARS = T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)
def where(e):
    tb = traceback.extract_tb(e.__traceback__)
    return " <- ".join(f"{f.name}" for f in reversed(tb[-6:]))

print("=== CASE 1: disk fills BEFORE the entry signal (15:30): is any order sent?")
h, fj = fresh()
used = fill_disk()
try:
    h.step(1, {"SPY": BARS})
    print("  tick completed (unexpected)")
except OSError as e:
    print(f"  tick raised {type(e).__name__} errno={e.errno}: {where(e)}")
print("  orders that reached the broker:", len(h.sim.submits), "| positions:", [(p.symbol, p.qty) for p in h.sim.positions()])

print("=== CASE 2: disk fills WHILE a protected position is open; next tick that has to journal")
h, fj = fresh()
h.step(1, {"SPY": BARS})
h.step(1)
print("  before: slot", h.eng.slot_state.value, "stop_confirmed", h.eng.trade.stop_confirmed, "positions", [(p.symbol, p.qty) for p in h.sim.positions()], "open orders", len(h.sim.open_orders()))
fill_disk()
# quiet ticks: does the ENGINE need to write anything?
errs = []
for s in range(60):
    try:
        h.step(1)
    except OSError as e:
        errs.append((h.t.strftime("%H:%M:%S"), type(e).__name__, where(e)))
        break
print("  first failure during quiet ticks:", errs[:1] or "none in 60 quiet ticks (engine had nothing to journal)")

print("=== CASE 3: disk full, the 15:50 TIME_EXIT falls due (position open, bracket legs live at the broker)")
h, fj = fresh()
h.step(1, {"SPY": BARS}); h.step(1)
h.t = T.ts("15:49:50")
h.step(1)
fill_disk()
raised = None
for s in range(30):
    try:
        h.step(1)
    except OSError as e:
        raised = (h.t.strftime("%H:%M:%S"), type(e).__name__, where(e)); break
print("  raised at", raised)
print("  exit sell sent to the broker?:", [x.client_order_id.split('-')[4] for x in h.sim.submits if x.side == 'sell'] or "NO", "| position:", [(p.symbol, p.qty) for p in h.sim.positions()],
      "| bracket legs still live at broker:", [(o.order_type, o.status) for o in h.sim.open_orders()])

print("=== CASE 4: the Runner loop on a full disk: heartbeat write")
h, fj = fresh()
h.step(1, {"SPY": BARS}); h.step(1)
S.write_heartbeat(TINY, h.t, "dry", h.eng.status())
hb_before = S.heartbeat_age_s(TINY, h.t + pd.Timedelta(seconds=1), "dry")
fill_disk()
try:
    S.write_heartbeat(TINY, h.t + pd.Timedelta(seconds=1), "dry", h.eng.status())
    print("  heartbeat write OK (unexpected)")
except OSError as e:
    print(f"  heartbeat write raised {type(e).__name__} errno={e.errno}; old heartbeat file still there, age now {S.heartbeat_age_s(TINY, h.t + pd.Timedelta(seconds=40), 'dry'):.0f}s after 40 s (stale > {C.HEARTBEAT_STALE_S}s)")
print("  leftover temp files from the failed atomic write:", sorted(p.name for p in TINY.iterdir() if p.name.endswith('.tmp')))

print("=== CASE 5: WATCHDOG on the same full disk (stale heartbeat, position open at the broker, PAPER-mode logic on a SimBroker)")
h, fj = fresh()
h.step(1, {"SPY": BARS}); h.step(1)
S.write_heartbeat(TINY, h.t, "paper", h.eng.status())
fill_disk()
wt = h.t + pd.Timedelta(seconds=45)          # heartbeat is 45 s old
wclock = lambda: wt
wj = J.FileJournal(TINY / "journal" / "wd.jsonl", Mode.PAPER, wclock)
h.sim.clock = wclock
st = T.session(T.D)
wd = W.Watchdog(Mode.PAPER, TINY, wclock, wj, broker=h.sim, quote_fn=None, sleep=lambda s: None, session=st, lock_wait_s=0.2)
try:
    r = wd.check()
    print("  watchdog.check() returned:", r)
except Exception as e:
    print(f"  watchdog.check() raised {type(e).__name__}: {e}  [{where(e)}]")
print("  after the watchdog: positions", [(p.symbol, p.qty) for p in h.sim.positions()], "open orders", len(h.sim.open_orders()),
      "| HALT file written:", (TINY / "HALT").exists(), "| acted flag:", wd.acted)
print("  run_watchdog() wrapper with the same state (max_checks=1): ", end="")
h2, _ = fresh()
h2.step(1, {"SPY": BARS}); h2.step(1)
S.write_heartbeat(TINY, h2.t, "paper", h2.eng.status()); fill_disk()
wt = h2.t + pd.Timedelta(seconds=45); h2.sim.clock = wclock
wj2 = J.FileJournal(TINY / "journal" / "wd2.jsonl", Mode.PAPER, wclock)
wd2 = W.Watchdog(Mode.PAPER, TINY, wclock, wj2, broker=h2.sim, quote_fn=None, sleep=lambda s: None, session=st, lock_wait_s=0.2)
try:
    W.run_watchdog(wd2, max_checks=1)
    print("returned normally")
except Exception as e:
    print(f"RAISED {type(e).__name__}: {e} [{where(e)}]")
print("  broker after watchdog: positions", [(p.symbol, p.qty) for p in h2.sim.positions()], "open orders", len(h2.sim.open_orders()))
