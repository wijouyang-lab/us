#!/usr/bin/env python3
"""Shared return accounting with explicit capital denominators.

Conventions:
- Long return is per 1 unit of long capital.
- Short return is per 1 unit of short notional; short_net = -underlying + -cost.
- 1x spread = long_net + short_net (one long unit + one short unit).
- 2x capital return = 1x spread / 2 when both legs require one unit each.
- CAGR uses elapsed calendar years between first entry and last exit.
- Sharpe uses mean/std of period returns, not CAGR / vol.
"""
from __future__ import annotations

import numpy as np


def long_net(long_gross: float, long_cost: float) -> float:
    return long_gross - long_cost


def short_net(underlying_gross: float, short_cost: float) -> float:
    return -underlying_gross - short_cost


def long_short_net(long_net_return: float, short_net_return: float) -> float:
    return long_net_return + short_net_return


def capital_return(net_pnl_per_unit: float, capital_units: float) -> float:
    if capital_units <= 0:
        raise ValueError("capital_units must be positive")
    return net_pnl_per_unit / capital_units


def cost_units(previous, current, initial: bool = False) -> float:
    """One side for initial buy; buy+sell for replacements."""
    if initial or not previous:
        return 1.0
    return 2.0 * len(set(current) - set(previous)) / max(len(current), 1)


def cagr(returns, years: float) -> float:
    r = np.asarray(returns, float)
    if len(r) == 0 or years <= 0:
        raise ValueError("returns and positive years required")
    return float(np.prod(1 + r) ** (1 / years) - 1)


def sharpe(returns, periods_per_year: float) -> float | None:
    r = np.asarray(returns, float)
    if len(r) < 2:
        return None
    sd = float(np.std(r, ddof=1))
    return float(np.mean(r) / sd * np.sqrt(periods_per_year)) if sd > 0 else None


def max_drawdown(returns) -> float:
    r = np.asarray(returns, float)
    equity = np.concatenate(([1.0], np.cumprod(1 + r)))
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1).min())
