# Unified Multi-Strategy Research Status

**Status date:** 2026-10-22  
**Scope:** research only. No production scoring, scan, stops, portfolio, or ledger changes.

## Latest 2Y PIT comparison

Source: [comparison workflow run 39725102501](https://github.com/wijouyang-lab/us/actions/runs/39725102501), completed successfully for both 2Y and 10Y jobs.

- 212,869 rows, 498 tickers, 443 valid signal dates (2024-12-09 through 2026-09-16).
- Strategy direction was selected on training data and frozen for validation/test.
- Test returns are 20-session returns with an estimated turnover-based cost of 10 bps per side.
- The test segment contains only **4 non-overlapping observations**. These results are **insufficient evidence** and must not be used to rank strategies.

| Strategy | Frozen direction | Test net return / 20 sessions | Net excess vs. equal-weight panel | Test observations | Assessment |
|---|---|---:|---:|---:|---|
| ATR volatility | HIGH | +1.671% | +1.524% | 4 | Insufficient evidence |
| Mean reversion (Z-score) | LOW | +0.289% | +0.141% | 4 | Insufficient evidence |
| 20D momentum | HIGH | -0.485% | -0.633% | 4 | Insufficient evidence |
| MA-slope reversal | HIGH | +0.272% | +0.124% | 4 | Insufficient evidence |

Cost sensitivity on the same four observations:

| Strategy | 5 bps/side | 10 bps/side | 20 bps/side |
|---|---:|---:|---:|
| ATR volatility | +1.699% | +1.671% | +1.616% |
| Mean reversion (Z-score) | +0.363% | +0.289% | +0.140% |
| 20D momentum | -0.416% | -0.485% | -0.624% |
| MA-slope reversal | +0.342% | +0.272% | +0.131% |

## Refreshed 10Y PIT multi-strategy comparison

**Fresh source artifact:** [10Y PIT snapshot run 39712671160](https://github.com/wijouyang-lab/us/actions/runs/39712671160), completed successfully on 2026-10-22. The artifact was regenerated from the current mainline research pipeline and contains updated snapshots, forward-return data, IC output, plus dedicated ATR validation reports.

**Comparison source:** [run 39725102501](https://github.com/wijouyang-lab/us/actions/runs/39725102501), 10Y job `compare-10y-latest` completed successfully. Verified artifact: `unified-multi-strategy-comparison-10y-latest`.

- 1,038,059 rows, 498 tickers, 2,453 valid signal dates (2016-12-12 through 2026-09-16 in the signal-factor panel).
- All four strategies have 24 non-overlapping test observations.
- Portfolio: top/bottom 20% equal-weight long-only, 20-session observation spacing, 20-date purge at split boundaries.
- Common-panel cost estimate: turnover-based, 5/10/20 bps per side; not fill-level slippage.

| Strategy | Frozen direction | Gross return / 20 sessions | Net return / 20 sessions | Net excess vs. equal-weight panel | Win rate | Rough Sharpe | Drawdown | Turnover |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| ATR volatility | HIGH | +2.244% | +2.190% | +1.480% | 75.0% | 1.99 | -11.250% | 29.261% |
| Mean reversion (Z-score) | LOW | +0.389% | +0.229% | -0.480% | 66.7% | 0.32 | -10.633% | 82.060% |
| 20D momentum | LOW | +0.656% | +0.501% | -0.209% | 62.5% | 0.68 | -8.990% | 79.616% |
| MA-slope reversal | LOW | +0.610% | +0.458% | -0.252% | 58.3% | 0.50 | -8.454% | 78.023% |

Test cost sensitivity (net return per 20 sessions):

| Strategy | 5 bps/side | 10 bps/side | 20 bps/side |
|---|---:|---:|---:|
| ATR volatility | +2.217% | +2.190% | +2.135% |
| Mean reversion (Z-score) | +0.309% | +0.229% | +0.069% |
| 20D momentum | +0.578% | +0.501% | +0.346% |
| MA-slope reversal | +0.534% | +0.458% | +0.306% |

### Separate ATR execution checks

The refreshed workflow also regenerated the dedicated ATR reports. They use different implementations/entry conventions from the unified four-strategy panel; compare them as robustness checks, not as exactly interchangeable estimates.

- Dedicated close-to-close ATR report: 1,038,059 rows, test (n=24), net mean return **+2.215%** and net excess **+1.505%** at 10 bps per side.
- Next-open-entry execution report: 1,038,058 valid execution samples, test (n=24), net mean return **+2.196%** and net excess **+1.460%** at 10 bps per side.

## Interpretation and limitations

1. In the refreshed common 10Y comparison, only ATR volatility has positive test-period net excess against the equal-weight panel. Mean reversion, 20D momentum, and MA-slope reversal have negative net excess. These are descriptive historical estimates, not strategy approval.
2. Although 24 non-overlapping observations is more informative than the 2Y test's four observations, it is still a small test sample. The source panel has already been used in exploratory research; this is not a blind final holdout.
3. The unadjusted OHLC can distort returns around splits/dividends. The constituent file lacks complete `Date_Removed` history, so survivorship bias remains; the panel cannot be described as strict point-in-time membership.
4. Costs are turnover-based estimates, not a fill-level execution simulation. Live liquidity, spread, slippage, stop paths, rejected orders, and portfolio constraints are not fully represented.
5. Do not promote any strategy into production from these findings. The next validation gate is split/dividend-adjusted prices, historical constituent entry/exit dates, walk-forward/regime robustness, and execution-level testing on an untouched holdout.
