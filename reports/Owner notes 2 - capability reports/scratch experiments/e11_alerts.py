"""Alert routing scratch: build the engine exactly as runner.make_engine does (no alert callback) and fire a kill switch;
see where the alert text goes."""
import tempfile, pathlib, io, contextlib, sys
from common import *
from lab.scalp.live import runner as RUN, state as S
import inspect
print("runner.make_engine parameters:", list(inspect.signature(RUN.make_engine).parameters))
tmp = pathlib.Path(tempfile.mkdtemp())
reg = C.Registry((T.LAST30,), T.REG.account_last4)
h = T.H(tmp, start="15:29:59", registry=reg); h.px["SPY"] = 652.0
h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)}); h.step(1)
err = io.StringIO()
with contextlib.redirect_stderr(err):
    h.eng.request_kill("scratch kill to see where alerts go")
    for _ in range(6): h.step(1)
print("engine.alert_fn:", h.eng.alert_fn)
print("alert lines in the JOURNAL:", [a["message"][:70] for a in h.j.of("alert")])
print("stderr text:", repr(err.getvalue()[:80]))
print("alerts.log exists in the state folder:", (h.state / S.ALERTS).exists())
