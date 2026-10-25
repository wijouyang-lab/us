# Formula Factor Empirical Results — 2026-10-25

## Run and data

- Research-only workflow: [run 40171684376](https://github.com/wijouyang-lab/us/actions/runs/40171684376)
- Commit: `ce0bbdbf593f91a684d105958360f746d53477a6`
- Dataset: `research_backtest_sp500_pit_2y.csv`
- Rows: 222,388; date range: 2024-12-09 through 2026-10-13.
- Selected base features: `ATR_Pct`, `Realized_Volatility_20D_Pct`, `Momentum_5D_Pct`, `Momentum_20D_Pct`, `Momentum_60D_Pct`, `RSI`, `MA20_Slope_Pct_5D`, `Beta_60D_SPY`.
- Formula candidates: 92; candidate × horizon rows: 276 (5D, 10D, 20D).
- Inference: Newey–West HAC tests on daily IC and daily Q5–Q1 spread with lag horizon−1, then separate Benjamini–Hochberg FDR correction within each horizon.

## Main result

**No candidate passes the 5% Benjamini–Hochberg FDR threshold for either daily IC or Q5–Q1 spread at any of the three horizons.** Therefore, this search has not established a statistically robust alpha factor after accounting for the candidate family.

The most persistent exploratory signal is the standalone `ATR_Pct` / `Realized_Volatility_20D_Pct` family. Their daily Q5–Q1 spreads are positive in all three chronological folds, but the corrected p-values remain above 0.05.

| Horizon | Candidate | Gross Q5−Q1 mean | After assumed 5 bp/leg | HAC spread p | FDR q (spread) | FDR q (IC) |
|---|---|---:|---:|---:|---:|---:|
| 5D | `z__ATR_Pct` | 0.6583% | 0.5583% | 0.0172 | 0.1351 | 0.3928 |
| 10D | `z__ATR_Pct` | 1.3458% | 1.2458% | 0.0081 | 0.0736 | 0.2677 |
| 20D | `z__ATR_Pct` | 2.6988% | 2.5988% | 0.0073 | 0.0659 | 0.3059 |
| 5D | `z__Realized_Volatility_20D_Pct` | 0.6047% | 0.5047% | 0.0168 | 0.1351 | 0.3928 |
| 10D | `z__Realized_Volatility_20D_Pct` | 1.2530% | 1.1530% | 0.0065 | 0.0736 | 0.2677 |
| 20D | `z__Realized_Volatility_20D_Pct` | 2.4958% | 2.3958% | 0.0078 | 0.0659 | 0.3059 |

Returns above are average forward-horizon Q5−Q1 differences, not annualized portfolio returns. Forward labels overlap, so these rows must not be interpreted as a realizable compounded strategy.

## Robustness and limits

1. **Multiple testing:** none of 92 candidates per horizon passes 5% FDR, despite several unadjusted HAC p-values below 0.05.
2. **Fold direction:** ATR and realized-volatility candidates have positive net Q5−Q1 means in each of the three reported folds, but folds are only temporal slices of the same approximately two-year dataset, not an independent external holdout.
3. **Cost approximation:** the current net spread subtracts a fixed 5 bp per leg. It does not use observed turnover and excludes slippage, borrow costs, liquidity/capacity constraints, market impact, and portfolio-level compounding.
4. **Dependence:** HAC with horizon−1 lags reduces sensitivity to serial dependence but does not fully solve overlapping labels, heteroskedasticity, universe composition, or all possible data leakage.
5. **Point-in-time claims:** the dataset is named as a PIT backtest, but this result alone does not independently audit the historical universe membership or each feature's availability timestamp.
6. **No production activation:** these are exploratory research results. Do not add these factors to live ranking, scanning, portfolio construction, or trading rules.

## Next research gate

Before claiming a usable factor, freeze the candidate family and protocol, audit the point-in-time universe/feature timestamps, compare against ATR and simple baselines on identical dates, perform turnover-aware cost and portfolio simulations, and reserve an untouched later holdout. If the signal fails corrected inference or realistic costs, record it as rejected rather than tuning repeatedly against the same period.
