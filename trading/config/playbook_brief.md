# Strategy playbook (summary of reports/Trading strategy playbook.md)

Goal: beat a buy-and-hold index ETF after costs and taxes, with smaller drawdowns.
Realistic target: 6-10% a year, worst drawdown under ~15-20%. Anything much better
than that in a short period is more likely luck or a bug than skill.

Evidence to keep in mind:
- Retail traders mostly lose: 97% of persistent Brazilian futures day traders lost money;
  74-89% of EU retail CFD accounts lose; the most active US traders earned 11.4%/yr vs 17.9% for the market.
- Published edges shrink after publication (about 58% lower, McLean & Pontiff). Halve backtests.
- LLM trading agents mostly failed to beat buy-and-hold in controlled tests; Claude models lost
  35-42% in the Alpha Arena contests mainly through leverage, overtrading and weak risk control.
  Activity itself is the main source of loss. Doing nothing is often the best decision.

The four sleeves (share of total equity):
- A. Trend core, 50-60%. Faber GTAA-5: SPY, EFA, IEF, DBC, VNQ, 20% each, held only when the
  last month-end close is above its 10-month SMA, else T-bills (BIL). Volatility-scaled to 10%/yr.
  Monthly signal; its value is cutting drawdowns in long bear markets.
- B. RSI(2) dips, 15-25%. SPY/QQQ/IWM/DIA. Buy when close > 200-day SMA and RSI(2) < 10.
  Exit when close > 5-day SMA, after 10 days, or at a 3-ATR disaster stop. Max 2 positions.
  Works in steady uptrends; worst in high-volatility declines.
- C. Growth breakouts, 10-20%, on probation. Minervini trend template (price above rising 150/200-day
  SMAs, 50 > 150 > 200, within 25% of the 52-week high, 25%+ above the 52-week low, relative strength
  rank >= 70) plus a close above the 50-day pivot high on 1.5x average volume. Stop 2 ATR, max 8%.
  Exit on a close below the 10-day low or the 50-day SMA. Only when SPY is above its 200-day SMA.
  Win rates of 35-50% are normal; a few big winners pay for many small losses.
- D. Crypto trend, 0-10%, only if the owner opted in. BTC/ETH long/flat Donchian ensemble,
  volatility-targeted to 25%/yr.

Regimes (computed by code): bull_calm, bull_volatile (half size for B and C), bear (B and C off),
panic rebound (B and C off, momentum-crash risk), choppy (C off, B half size).

Principles from Market Wizards, Van Tharp and Mark Douglas: cut losses, let winners run, size small,
think in R-multiples (profit divided by the initial risk), judge the process over many trades rather
than single outcomes, and never raise risk to win back losses.
