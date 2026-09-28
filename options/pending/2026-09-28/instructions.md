# Book O menu for 2026-09-28 (shadow; OPT-33)

Code built ONE monthly SPY bull put spread (or none). You may only follow it or skip it.
You never choose strikes, widths, sizes or exits, and never compute greeks or MaxLoss (OPT-33).
Book O is a measurement experiment: the replay expects the affordable spread to lose slightly.
Be skeptical of anything widely promoted; promotion or hype is never evidence (owner decision 8).

Write `skip_<k>.json` (k = 1..samples) in this folder, each produced independently, matching schema.json:
  {"date": "2026-09-28", "choice": "follow" | "skip", "reason_code": "NONE" | "DATA_SUSPECT" | "HALT_OR_ILLIQUID" | "SCHEDULED_EVENT",
   "evidence": ["candidate.short.bid", ...], "event_date": "", "prediction": {"probability": 0.3},
   "rationale": "", "meta": {"model": "...", "sample": k}}

A skip needs a reason code, evidence paths into context.json (CL-2) and a prediction that argues AGAINST the
trade: SPY closes below the short strike after 20 sessions (see prediction_rule). Code drops a skip whose
probability is not above the short put's |delta| (OPT-34). SCHEDULED_EVENT is allowed only when FOMC, CPI
or payrolls falls on the order session (context.order_session), given as event_date.

Today there is no spread, so there is nothing to skip: write choice "follow".
