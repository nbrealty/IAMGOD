"""V4-16 scratch experiment: ROLLBACK artifact that cannot interpret a persisted open position.
Emulation: an open 1-share SPY bracket at the broker whose client id follows a DIFFERENT grammar than this code's
(what an older/newer build would have written, e.g. an unknown setup code). The bot is 'rolled back' = restarted on this code."""
import tempfile, pathlib
from common import *
from lab.scalp.live import restore as RS, orders as O
from lab.scalp.live.model import OrderSpec, Kind

tmp = pathlib.Path(tempfile.mkdtemp())
reg = C.Registry((T.LAST30,), T.REG.account_last4)
h = T.H(tmp, start="15:30:10", registry=reg)
h.px["SPY"] = 652.0
# an entry bracket under an id the current parse_client_id does not know (older/newer code version)
good = O.entry_bracket(Candidate("LAST30_MOM_SPY", 1, "SPY", "enter", 1, T.ts("15:29")), T.LAST30, h.sim.quotes["SPY"], 100_000.0, T.D, 0)[0]
from dataclasses import replace
alien = replace(good, client_order_id="SCALP-OLDV2-261001-1529-E0-abcdef")           # code OLDV2 is not in SETUP_CODES
print("current grammar parses the alien id:", O.parse_client_id(alien.client_order_id))
h.sim.by_cid  # (SimBroker.check_spec only needs the SCALP- prefix)
h.sim.submit(alien) if False else None
# SimBroker.submit -> check_spec -> O.validate -> parse_client_id must accept the id; the alien id fails local validation:
try:
    h.sim.submit(alien)
    print("alien id accepted by SimBroker (unexpected)")
except Exception as e:
    print("SimBroker/local validation refuses the alien id:", type(e).__name__, str(e)[:120])
# so create the position the way an older build would have: inject the position and legs directly
h.sim.inject_position("SPY", 1, 652.0)
oid = h.sim.add_foreign_order("SPY", "sell", 1, 660.0, cid="SCALP-OLDV2-261001-1529-E0-abcdef-TP")   # a resting leg with an alien id
cnt, st = RS.rebuild(h.sim, T.D, 100_000.0, 100_000.0, None, None, reg, h.t)
print("restore: adopted trade:", st.trade, "| extra (unexplained) positions:", [(p.symbol, p.qty) for p in st.extra_positions], "| notes:", st.notes[:2])
h2 = T.H(pathlib.Path(tempfile.mkdtemp()), start="15:30:10", registry=reg, counters=cnt, adopted=st, sim=h.sim)
h2.px["SPY"] = 652.0
for _ in range(15):
    h2.step(1)
print("engine outcome after 15 s:", "reconcile_halt" if h2.j.of("reconcile_halt") else "no halt", "| kill_done:", bool(h2.j.of("kill_done")), "| broker flat:", h2.flat(), "| HALT flag:", h2.flag("HALT").exists())
print("persisted-schema version fields present in state files? session/journal/pin: none (grep below)")
