# Non-ATR Risk-Control Results

Research-only evaluation of portfolio-level risk controls using the existing adjusted-price artifact. This report was rechecked against workflow run 39894660308 at code commit f76d88d0267de533e4b969a380b93f07889feddb, after correcting first-session turnover accounting. Regression tests including future-return leakage and initial-entry turnover pass on follow-up commit 963b2583ef604e9cc29a42a6c3cb8fb7b8f125d3. No historical prices were refreshed.

## Configuration tested

- 8% annualized volatility target using a 63-session lookback
- 50% maximum gross exposure; the overlay only scales exposure down
- 15% drawdown trigger followed by a 20-session cash cooldown
- One-way transaction-cost scenarios of 0, 5, 10, and 20 bps
- Lagged signals and point-in-time eligible universe from the existing simulation

## Full-period comparison at 5 bps one-way cost

| Strategy | Profile | CAGR | Annualized volatility | Sharpe (0% RF) | Max drawdown | Mean exposure | Max exposure | Annual turnover | Worst calendar year |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Momentum | Baseline | 5.45% | 8.30% | 0.681 | -15.92% | 57.90% | 95.58% | 8.91x | -9.20% |
| Momentum | Risk-managed | 4.43% | 6.34% | 0.715 | -11.01% | 44.20% | 50.00% | 10.09x | -7.26% |
| Trend | Baseline | 5.62% | 9.94% | 0.600 | -27.40% | 56.12% | 90.46% | 1.48x | -7.05% |
| Trend | Risk-managed | 4.08% | 6.80% | 0.623 | -15.72% | 42.31% | 50.00% | 1.77x | -5.80% |
| Mean reversion | Baseline | 3.50% | 9.06% | 0.425 | -22.39% | 24.29% | 96.54% | 34.32x | -7.85% |
| Mean reversion | Risk-managed | 1.82% | 5.85% | 0.337 | -16.84% | 22.42% | 50.00% | 34.80x | -7.81% |

## Interpretation

1. The overlay materially reduced realized volatility and maximum drawdown for all three strategies at 5 bps. The largest drawdown improvement was for trend, from -27.40% to -15.72%.
2. Momentum's Sharpe improved modestly from 0.681 to 0.715 while CAGR fell by about 1.02 percentage points. Its worst calendar year improved from -9.20% to -7.26%.
3. Trend's Sharpe improved from 0.600 to 0.623 while CAGR fell by about 1.54 percentage points. Its maximum drawdown improved by about 11.68 percentage points.
4. Mean reversion's Sharpe fell from 0.425 to 0.337 and CAGR fell by about 1.68 percentage points. The overlay reduces risk, but does not make this high-turnover strategy more attractive at the 5 bps assumption.
5. The overlay raises estimated turnover modestly for momentum and trend. Mean reversion already has very high turnover (~34.3x annualized); these fixed-cost results should be treated cautiously.
6. The 20 bps mean-reversion case is poor for both profiles; the risk overlay does not rescue it. Do not select a strategy based on the risk-managed curve alone.

## Walk-forward observations at 5 bps

- Momentum: drawdown improved in each held-out window shown in the report; the 2019-2020 window's annualized loss improved from -6.89% to -4.21%, and the latest 2025-2026 window returned 10.93% baseline versus 9.71% risk-managed.
- Trend: the 2019-2020 window's maximum drawdown improved from -27.40% to -15.72%; the latest window returned 11.90% baseline versus 10.74% risk-managed.
- Mean reversion: drawdown generally improved, but the first held-out window changed from +1.63% baseline to -6.93% risk-managed. This warns against assuming a volatility overlay always improves outcomes.

These are descriptive walk-forward windows, not a guarantee of future performance. Configuration has not been selected on a fresh untouched validation set, and no live execution/slippage model is included.

## Limitations and next gate

- Market-wide price coverage remains incomplete; this simulation only covers the strictly eligible point-in-time subset. Historical gap repair is intentionally out of scope for this iteration.
- Costs are fixed basis-point assumptions, not observed fills; market impact, borrow, taxes, and operational failures are not modeled.
- The SPY benchmark's full-period annualized return was about 15.52% in this calendar, above these strategy results. Because the strategies maintain substantial cash exposure, this is not a risk-matched comparison.
- This is research-only. Do not enable live trading based on this report alone.

Next gate: retain momentum and trend as candidates for additional robustness checks; do not prioritize mean reversion at higher costs. Before any deployment decision, verify signal timing, portfolio accounting, execution-cost sensitivity, and operational safeguards on a separate validation run.
