"""Scalp lab: research minute-chart day-trading setups on historical 1-minute bars, paper/backtest only.

    cd trading
    python -m lab.scalp download --symbols SPY QQQ --start 2024-09-03 --end 2026-09-25
    python -m lab.scalp backtest --symbols SPY QQQ --start 2024-09-03 --end 2026-09-25
    python -m lab.scalp report

Modules: data (Alpaca SIP bars, cached), signals (setups as pure functions, reusable live), backtest (fills,
costs, baselines, statistics), report (json/csv/markdown). This package never places, changes or cancels
orders, and imports nothing from trader/.
"""
