"""Research-only non-ATR strategy baselines.

Signals are computed using information available at the close of session t and
are shifted one row before returns are earned, preventing same-close lookahead.
This module is intentionally isolated from production order/signal generation.
"""
from __future__ import annotations

import pandas as pd


def build_strategy_returns(
    prices: pd.DataFrame,
    *,
    price_col: str = "Adj Close",
    momentum_lookback: int = 126,
    trend_fast: int = 50,
    trend_slow: int = 200,
    mean_reversion_lookback: int = 5,
    mean_reversion_entry_z: float = -1.5,
    mean_reversion_exit_z: float = -0.25,
) -> pd.DataFrame:
    """Return daily close-to-close strategy series for one ticker.

    Input must have a Date column and adjusted close prices for a single ticker.
    The three long-only baselines are momentum, moving-average trend, and
    short-horizon mean reversion. Positions are lagged by one session.
    """
    required = {"Date", price_col}
    if not required.issubset(prices.columns):
        raise ValueError(f"prices must contain columns: {', '.join(sorted(required))}")
    if min(momentum_lookback, trend_fast, trend_slow, mean_reversion_lookback) < 2:
        raise ValueError("lookback windows must be at least 2")
    if trend_fast >= trend_slow:
        raise ValueError("trend_fast must be smaller than trend_slow")
    if mean_reversion_entry_z >= mean_reversion_exit_z:
        raise ValueError("mean-reversion entry threshold must be below exit threshold")

    frame = prices[["Date", price_col]].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame[price_col] = pd.to_numeric(frame[price_col], errors="coerce")
    frame = frame.dropna(subset=["Date", price_col])
    frame = frame[frame[price_col] > 0].sort_values("Date")
    frame = frame.drop_duplicates("Date", keep="last").reset_index(drop=True)
    if frame.empty:
        raise ValueError("no valid positive prices")
    close = frame[price_col].astype(float)
    daily_return = close.pct_change().fillna(0.0)

    momentum = close / close.shift(momentum_lookback) - 1.0
    momentum_position = (momentum > 0).astype(float)

    fast_ma = close.rolling(trend_fast, min_periods=trend_fast).mean()
    slow_ma = close.rolling(trend_slow, min_periods=trend_slow).mean()
    trend_position = (fast_ma > slow_ma).astype(float)

    rolling_mean = close.rolling(mean_reversion_lookback, min_periods=mean_reversion_lookback).mean()
    rolling_std = close.rolling(mean_reversion_lookback, min_periods=mean_reversion_lookback).std(ddof=0)
    z_score = (close - rolling_mean) / rolling_std.replace(0, pd.NA)
    # Stateful hysteresis avoids repeatedly entering/exiting around one threshold.
    mean_reversion_position = []
    holding = 0.0
    for value in z_score:
        if pd.notna(value):
            if holding == 0.0 and value <= mean_reversion_entry_z:
                holding = 1.0
            elif holding == 1.0 and value >= mean_reversion_exit_z:
                holding = 0.0
        mean_reversion_position.append(holding)

    positions = pd.DataFrame({
        "momentum_position": momentum_position,
        "trend_position": trend_position,
        "mean_reversion_position": mean_reversion_position,
    }, index=frame.index)
    # Signal observed after today's close can only earn the next session's return.
    lagged_positions = positions.shift(1).fillna(0.0)
    result = pd.DataFrame({
        "Date": frame["Date"],
        "Adj Close": close,
        "buy_and_hold_return": daily_return,
        "momentum_return": lagged_positions["momentum_position"] * daily_return,
        "trend_return": lagged_positions["trend_position"] * daily_return,
        "mean_reversion_return": lagged_positions["mean_reversion_position"] * daily_return,
        "momentum_position": positions["momentum_position"],
        "trend_position": positions["trend_position"],
        "mean_reversion_position": positions["mean_reversion_position"],
    })
    return result


def summarize_returns(returns: pd.Series, *, annualization: int = 252) -> dict:
    """Summarize a daily simple-return series without assuming risk-free returns."""
    series = pd.to_numeric(returns, errors="coerce").dropna().astype(float)
    if series.empty:
        return {"observations": 0, "total_return": None, "annualized_return": None,
                "annualized_volatility": None, "sharpe_zero_rf": None, "max_drawdown": None}
    if annualization < 1:
        raise ValueError("annualization must be positive")
    equity = (1.0 + series).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    years = len(series) / annualization
    annualized_return = float(equity.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 and equity.iloc[-1] > 0 else None
    volatility = float(series.std(ddof=1) * annualization ** 0.5) if len(series) > 1 else 0.0
    sharpe = float(series.mean() / series.std(ddof=1) * annualization ** 0.5) if len(series) > 1 and series.std(ddof=1) > 0 else None
    drawdown = equity / equity.cummax() - 1.0
    return {
        "observations": int(len(series)),
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": volatility,
        "sharpe_zero_rf": sharpe,
        "max_drawdown": float(drawdown.min()),
    }
