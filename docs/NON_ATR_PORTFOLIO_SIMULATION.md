# Non-ATR Portfolio-Level Simulation Results

**Status:** research-only; not approved for live trading.  
**Input:** existing adjusted-price artifact from workflow run [39885406985](https://github.com/wijouyang-lab/us/actions/runs/39885406985). The portfolio run reused this artifact and did not refresh historical prices.  
**Eligibility:** 612 tickers eligible and 145 excluded by the existing strict PIT completeness screen. Universe-wide data coverage remains incomplete, so the result is a filtered research subset.

## Full-period portfolio results

Fixed-cost scenarios charge 0, 5, 10, or 20 bps per one-way traded notional. Capital is equal-weighted across the eligible point-in-time members present each session; inactive strategy positions remain in cash. Costs include changes in portfolio target weights, including entry/exit and reweighting.

| Strategy | Cost | CAGR | Annualized volatility | Sharpe (0% RF) | Max drawdown | Mean exposure | Annualized turnover | Worst calendar year |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Momentum | 0 bps | 5.92% | 8.30% | 0.734 | -15.84% | 57.90% | 8.91x | -8.72% |
| Momentum | 5 bps | 5.45% | 8.30% | 0.681 | -15.92% | 57.90% | 8.91x | -9.20% |
| Momentum | 10 bps | 4.98% | 8.30% | 0.627 | -16.00% | 57.90% | 8.91x | -9.68% |
| Momentum | 20 bps | 4.05% | 8.30% | 0.519 | -16.56% | 57.90% | 8.91x | -10.63% |
| Trend | 0 bps | 5.70% | 9.94% | 0.608 | -27.39% | 56.12% | 1.48x | -6.98% |
| Trend | 5 bps | 5.62% | 9.94% | 0.600 | -27.40% | 56.12% | 1.48x | -7.05% |
| Trend | 10 bps | 5.54% | 9.94% | 0.593 | -27.41% | 56.12% | 1.48x | -7.13% |
| Trend | 20 bps | 5.39% | 9.94% | 0.578 | -27.44% | 56.12% | 1.48x | -7.28% |
| Mean reversion | 0 bps | 5.29% | 9.06% | 0.614 | -20.79% | 24.29% | 34.32x | -6.25% |
| Mean reversion | 5 bps | 3.50% | 9.06% | 0.425 | -22.39% | 24.29% | 34.32x | -7.85% |
| Mean reversion | 10 bps | 1.74% | 9.06% | 0.235 | -25.20% | 24.29% | 34.32x | -9.42% |
| Mean reversion | 20 bps | -1.70% | 9.06% | -0.144 | -31.26% | 24.29% | 34.32x | -12.49% |

SPY buy-and-hold over the same price calendar had a 15.52% annualized return and 0.901 Sharpe (zero risk-free rate). This is a raw-return comparison, not a risk-matched comparison: the strategies held substantial cash, with mean exposure between 24% and 58%.

## Walk-forward held-out results at 5 bps

Seven chronological 252-session windows were evaluated. Annualized returns by window:

| Held-out window | Momentum | Trend | Mean reversion | SPY buy-and-hold |
|---|---:|---:|---:|---:|
| 2019-06-27 to 2020-06-25 | -6.89% | -12.06% | 1.63% | 7.92% |
| 2020-06-26 to 2021-06-25 | 33.74% | 35.30% | 13.40% | 40.87% |
| 2021-06-28 to 2022-06-27 | -4.32% | -1.02% | -1.59% | -7.62% |
| 2022-06-28 to 2023-06-28 | 1.87% | 2.43% | 6.45% | 14.13% |
| 2023-06-29 to 2024-06-28 | 8.79% | 7.11% | 1.91% | 26.45% |
| 2024-07-01 to 2025-07-02 | 3.41% | 5.12% | 5.75% | 15.43% |
| 2025-07-03 to 2026-07-06 | 10.93% | 11.90% | 5.87% | 22.43% |

These windows show regime dependence: momentum and trend performed poorly in the first window, strongly in 2020–2021, and more moderately afterward. Mean reversion was less volatile in the first window but deteriorated rapidly as cost assumptions increased.

## Interpretation and next gate

1. **Momentum is the current portfolio-level baseline leader on risk-adjusted metrics at 5 bps** (Sharpe 0.681, max drawdown -15.92%). This differs from the earlier per-ticker comparison; portfolio construction changes the ranking.
2. **Trend has similar CAGR but a much deeper maximum drawdown** (-27.40%), so it is not the default choice without stronger risk controls.
3. **Mean reversion is too turnover-sensitive to select as the primary strategy**: 34.32x annualized turnover and CAGR declines from 3.50% at 5 bps to -1.70% at 20 bps.
4. **None of these baselines beat SPY's raw return** in this sample, and the benchmark comparison is not risk matched. The next research gate should be risk-budgeting and exposure-aware comparisons, not parameter tuning.
5. Before considering paper deployment, test position caps, volatility targeting, drawdown circuit breakers, and a benchmark with matched exposure. Keep walk-forward folds untouched while setting risk rules, then validate those rules on later held-out data.

This simulation excludes taxes, market impact beyond the fixed bps scenarios, borrow/financing costs, and operational execution failures. The universe is not complete due to known historical coverage limitations. Do not treat these figures as expected live returns.
