# Non-ATR Transaction-Cost Sensitivity

**Scope:** research-only sensitivity analysis on the existing adjusted-price artifact; no historical price refresh was performed for this report. The input yielded 612 strictly eligible tickers. The source data still has incomplete universe-wide coverage, so this is not a full-market-universe estimate.

## Full-history per-ticker metrics

| Strategy | One-way cost | Median annualized return | Tickers with positive total return | Median max drawdown | Median annualized turnover |
|---|---:|---:|---:|---:|---:|
| Mean reversion | 0 bps | 4.32% | 80.9% | -40.61% | 34.16x |
| Mean reversion | 5 bps | 2.57% | 70.3% | -42.64% | 34.16x |
| Mean reversion | 10 bps | 0.75% | 56.9% | -45.03% | 34.16x |
| Mean reversion | 20 bps | -2.67% | 28.8% | -51.71% | 34.16x |
| Momentum | 0 bps | 5.07% | 76.3% | -47.80% | 8.73x |
| Momentum | 5 bps | 4.55% | 73.7% | -48.95% | 8.73x |
| Momentum | 10 bps | 4.06% | 71.4% | -50.08% | 8.73x |
| Momentum | 20 bps | 3.26% | 67.2% | -52.03% | 8.73x |
| Trend | 0 bps | 4.23% | 74.3% | -50.05% | 1.46x |
| Trend | 5 bps | 4.16% | 74.2% | -50.14% | 1.46x |
| Trend | 10 bps | 4.09% | 74.2% | -50.22% | 1.46x |
| Trend | 20 bps | 3.93% | 73.5% | -50.50% | 1.46x |

Returns and drawdowns are medians across ticker-level backtests, not portfolio-level investment results. Annualized turnover is a diagnostic estimate from position changes; it is not a broker fill forecast.

## Walk-forward out-of-sample sensitivity

| Strategy | One-way cost | OOS ticker-window rows | Positive OOS rows | Median OOS window return | 10th percentile OOS return | Median OOS max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| Mean reversion | 0 bps | 4,141 | 66.5% | 6.21% | -16.03% | -13.75% |
| Mean reversion | 5 bps | 4,141 | 62.3% | 4.38% | -17.47% | -14.09% |
| Mean reversion | 10 bps | 4,141 | 57.6% | 2.63% | -18.94% | -14.49% |
| Mean reversion | 20 bps | 4,141 | 47.2% | -0.90% | -21.71% | -15.41% |
| Momentum | 0 bps | 4,141 | 49.1% | -0.08% | -20.65% | -19.29% |
| Momentum | 5 bps | 4,141 | 48.4% | -0.45% | -21.13% | -19.53% |
| Momentum | 10 bps | 4,141 | 47.5% | -0.89% | -21.76% | -19.80% |
| Momentum | 20 bps | 4,141 | 45.8% | -1.68% | -23.09% | -20.32% |
| Trend | 0 bps | 4,141 | 49.8% | 0.00% | -23.16% | -20.37% |
| Trend | 5 bps | 4,141 | 49.6% | 0.00% | -23.23% | -20.40% |
| Trend | 10 bps | 4,141 | 49.5% | 0.00% | -23.29% | -20.42% |
| Trend | 20 bps | 4,141 | 49.3% | 0.00% | -23.49% | -20.44% |


## Findings

1. **Mean reversion is highly cost-sensitive.** Median annualized return falls from 4.32% before costs to 2.57% at 5 bps, 0.75% at 10 bps, and -2.67% at 20 bps. The median annualized turnover is about 34x, which makes execution assumptions central to any further evaluation.
2. **Momentum and trend have lower turnover and lower cost sensitivity, but weaker OOS results.** Their median OOS window returns are near zero or negative, and their median drawdowns remain substantial.
3. **Drawdown remains a blocking risk concern.** Median full-history ticker-level maximum drawdowns are around -43% to -52% after costs. None of these baseline strategies should be promoted to live trading based on these results.
4. **Costs should be treated as a range, not a single truth.** The 0/5/10/20 bps values are fixed scenarios, not measured fills. Real slippage can depend on spread, liquidity, order size, volatility, and time of day.

## Next research gate

Before live-trading consideration, build a synchronized portfolio-level simulation with fixed capital, maximum position and sector exposure limits, a market benchmark, and the same cost scenarios. Use only the existing eligible histories and explicitly retain cash when signals are absent. Report portfolio CAGR, volatility, Sharpe, maximum drawdown, turnover, exposure, and worst calendar-year performance. Do not repeat historical downloads for this step.
