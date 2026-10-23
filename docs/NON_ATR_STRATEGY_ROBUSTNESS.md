# Non-ATR Strategy Robustness (Existing OOS Results)

This report summarizes the existing walk-forward out-of-sample (OOS) artifact. No price refresh or full historical backtest was run to produce this report.

## Strategy-level summary

| Strategy | OOS ticker-window rows | Tickers | Positive OOS rows | Median annualized return | Median Sharpe (zero risk-free rate) | Median max drawdown | 10th percentile OOS return |
|---|---:|---:|---:|---:|---:|---:|---:|
| Mean reversion | 2,988 | 506 | 63.3% | 4.20% | 0.372 | -13.06% | -15.30% |
| Momentum | 2,988 | 506 | 48.8% | -0.41% | 0.087 | -18.38% | -19.70% |
| Trend | 2,988 | 506 | 50.6% | 0.35% | 0.175 | -18.99% | -21.91% |

All figures above use the existing 5 bps one-way transaction-cost run.

## Split-level stability

| Strategy | Split | Ticker rows | Positive ticker rows | Median OOS return | 10th percentile OOS return | Median max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| Mean reversion | 1 | 506 | 59.1% | 4.87% | -26.09% | -22.72% |
| Mean reversion | 2 | 476 | 81.7% | 10.22% | -5.76% | -9.54% |
| Mean reversion | 3 | 455 | 47.9% | -0.50% | -19.91% | -15.13% |
| Mean reversion | 4 | 425 | 64.0% | 4.45% | -12.86% | -12.81% |
| Mean reversion | 5 | 398 | 59.0% | 2.49% | -11.78% | -10.40% |
| Mean reversion | 6 | 378 | 65.6% | 4.21% | -12.65% | -13.18% |
| Mean reversion | 7 | 350 | 65.4% | 5.58% | -15.77% | -11.17% |
| Momentum | 1 | 506 | 27.7% | -9.18% | -26.56% | -23.56% |
| Momentum | 2 | 476 | 77.5% | 25.19% | -11.84% | -16.28% |
| Momentum | 3 | 455 | 33.6% | -5.06% | -22.30% | -19.63% |
| Momentum | 4 | 425 | 45.4% | -1.14% | -16.97% | -16.12% |
| Momentum | 5 | 398 | 58.3% | 4.82% | -17.27% | -15.66% |
| Momentum | 6 | 378 | 48.7% | -0.29% | -17.20% | -19.55% |
| Momentum | 7 | 350 | 53.1% | 1.90% | -17.07% | -18.33% |
| Trend | 1 | 506 | 29.2% | -11.40% | -37.96% | -32.34% |
| Trend | 2 | 476 | 80.9% | 28.10% | -9.80% | -15.88% |
| Trend | 3 | 455 | 42.2% | -3.21% | -20.81% | -21.40% |
| Trend | 4 | 425 | 45.6% | 0.00% | -19.68% | -16.43% |
| Trend | 5 | 398 | 55.5% | 2.92% | -17.62% | -15.77% |
| Trend | 6 | 378 | 50.5% | 0.57% | -16.91% | -19.62% |
| Trend | 7 | 350 | 51.4% | 0.84% | -16.30% | -18.45% |

Split numbers are chronological walk-forward folds, not common calendar buckets. The displayed ticker rows within a split can have different start/end dates, so the date range should not be interpreted as a single synchronized market period.

## Decision

- Mean reversion is the strongest candidate for further research in this baseline comparison, but its advantage is not sufficient to select it for live trading.
- Momentum and trend have much more uneven split-level results, including weak early folds and strong performance in one fold. That suggests meaningful regime sensitivity.
- The 10th-percentile returns and drawdowns remain material. A median alone hides severe ticker-level losses.

## Limitations and next validation

- Ticker-window observations are correlated and are not independent statistical samples.
- The source run has incomplete universe-wide coverage. These are strict-filtered research results, not a full-market-universe estimate.
- This report is not a transaction-cost sensitivity test. Before strategy selection, the next step is to compare 0/5/10/20 bps one-way costs using the same exact point-in-time eligible sessions and to preserve portfolio-level exposure/risk constraints.
- These are research-only baselines and do not establish live-trading readiness.
