"""Section E scratch: a strategy whose entry never fills (and one that the broker rejects) must book NO trading gain or loss."""
import tempfile, pathlib
from common import *
reg = C.Registry((T.LAST30,), T.REG.account_last4)
for label, kw in (("never filled (order rests, cancelled after 2 s)", {"sim_kw": {"fill_delay_s": 1e9}}), ("rejected by the broker (403)", {"sim_kw": {"reject_next": 403}})):
    h = T.H(pathlib.Path(tempfile.mkdtemp()), start="15:29:59", registry=reg, **kw); h.px["SPY"] = 652.0
    cash0 = h.sim.cash
    h.step(1, {"SPY": T.mkbars("SPY", "09:30", "15:29", 650.0, 652.0, wick=0.0)})
    h.until("15:32:00", 1)
    print(f"{label}: realized_pnl={h.c.realized_pnl} realized_honest={h.c.realized_honest} test_honest={h.c.test_honest} "
          f"round_trips={h.c.round_trips} entry_submits={h.c.entry_submits} trade_closed_lines={len(h.j.of('trade_closed'))} "
          f"fill_lines={len(h.j.of('fill'))} sim_cash_change={h.sim.cash - cash0} positions={[(p.symbol,p.qty) for p in h.sim.positions()]}")
