"""SPY trend timing with explicit t signal -> t+1 execution."""
import pandas as pd

def trend_signal(prices: pd.Series, window: int) -> pd.Series:
    """Signal observed at month t (price vs trailing mean through t)."""
    return (prices > prices.rolling(window).mean()).astype(float)

def trend_positions(prices: pd.Series, window: int) -> pd.Series:
    """Position held during month t+1, based only on signal at t."""
    return trend_signal(prices, window).shift(1).fillna(0.0)

def spy_trend_backtest(prices: pd.Series, window: int = 10, cost_bps: float = 10):
    r = prices.pct_change()
    pos = trend_positions(prices, window)
    gross = pos * r
    turnover = pos.diff().abs().fillna(pos.abs())
    net = gross - turnover * cost_bps / 10000.0
    return gross, net, turnover, pos


def annualized_sharpe(returns, risk_free_annual=0.0):
    r = returns.dropna()
    excess = r - risk_free_annual/12.0
    vol = r.std(ddof=0) * (12 ** 0.5)
    return (excess.mean()*12)/vol if vol else float('nan')
