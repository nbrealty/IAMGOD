"""Live PAPER minute trader for the scalp lab (see DESIGN.md). Paper account ALPACA_SCALP_* only; SPY and QQQ
shares, long only, 1 share per trade in the EXPLORATORY lane. Never uses the ALPACA_RULES_* keys to trade.

    cd trading
    python -m lab.scalp.live check-account
    python -m lab.scalp.live replay --date 2026-09-28
    python -m lab.scalp.live run --mode dry
"""
