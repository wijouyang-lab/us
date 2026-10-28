# Qlib Backtest Audit 鈥?Corrected Metrics

Date: 2026-10-28
Research only. No production changes.

## Audit findings

The original baseline report overstated the result because of three calculation
choices:

1. **Winsor thresholds were estimated on each test-date distribution.** That is
   test-set information leakage. The audit uses thresholds estimated from the
   training labels only.
2. **Annual return used arithmetic monthly mean** (`(1+mean)^12-1`) instead of
   compounding the actual monthly series (`prod(1+r)^(12/n)-1`).
3. **Turnover/cost was ambiguous and double-counted.** The audit defines
   turnover as one-way name changes relative to the gross book, and applies
   `one_way_bps * turnover` per rebalance. Initial opening is full turnover.
4. **"Average 492 names" was the full cross-section**, not portfolio holdings.
   The actual legs are about 99 long and 98 short; 492 is the average number of
   eligible names in each cross-section.

## Corrected fixed-model result

| Metric | Old report | Corrected |
|---|---:|---:|
| Test rebalances | 9 | 9 |
| Gross monthly | 3.51% | 2.94% |
| Net monthly, 5 bps | 3.46% | 2.91% |
| Annualized net | 50.3% | **39.85%** |
| Annualized vol | 16.4% | 14.36% |
| Sharpe | 3.06 | **2.78** |
| Max drawdown | -2.75% | -2.72% |
| Turnover | 55.2% | 55.2% |
| Average eligible names | 492 | 491.9 |
| Average long / short | not reported | **99 / 98** |
| Raw t-stat | 2.18 | 2.11 |

Cost sensitivity (same gross series):

| One-way cost | Net monthly | Annualized net | Sharpe |
|---|---:|---:|---:|
| 5 bps | 2.91% | 39.85% | 2.78 |
| 10 bps | 2.88% | 39.40% | 2.74 |
| 20 bps | 2.83% | 38.49% | 2.67 |

Costs are not the main driver at this turnover; the low number of independent
observations is.

## Benchmark-adjusted alpha

Equal-weight benchmark on exactly the same 9 dates:

- mean monthly: 0.48%
- annualized: 5.91%
- Sharpe: 0.43

Regression of the net monthly spread on the equal-weight benchmark:

| Value | Estimate |
|---|---:|
| Alpha monthly | +2.90% |
| Beta | 0.023 |
| Alpha t | **1.95** |
| Alpha 95% CI | **[-0.0002, 0.0582]** |

The confidence interval includes zero. The previous report's "alpha t 鈮?0.08"
was not from the same corrected series and is superseded by this audit.

## Stability

| Sample | Rebalances | Annualized net | Sharpe | t-stat |
|---|---:|---:|---:|---:|
| Test first half | 4 | 27.9% | 1.62 | 0.87 |
| Test second half | 5 | 50.2% | 3.76 | 2.03 |
| Test all | 9 | 39.9% | 2.78 | 2.11 |

The halves are not stable and each is very small.

## Walk-forward refit

Refitting an expanding-window Ridge model at each test date, purging the final
20 sessions before each refit:

| Metric | Fixed model | Walk-forward |
|---|---:|---:|
| Rebalances | 9 | 9 |
| Net monthly | 2.91% | 1.12% |
| Annualized net | 39.9% | **12.5%** |
| Sharpe | 2.78 | **0.65** |
| Max drawdown | -2.7% | **-12.2%** |
| t-stat | 2.11 | **0.60** |

The fixed-model result does not survive honest rolling refits. This is the main
reason it is not a deployable strategy.

## Bootstrap uncertainty

5,000 bootstrap resamples of the 9 monthly net returns:

- mean monthly 95% CI: **[0.26%, 5.34%]**
- Sharpe 95% CI: **[0.22, 9.42]**

The Sharpe interval is extremely wide because n=9.

## Data and bias

- 2-year PIT snapshot: 222,388 rows, 502 tickers, 462 dates.
- 10-year panel: 1,233,984 rows, 503 tickers, 2,532 dates.
- 10-year panel is current-universe and survivorship-biased; it was not used to
  claim a PIT result.
- 10-year PIT coverage remains 91.61%; the 98 missing delisted tickers are not
  imputed or deleted.
- OpenBB independent multi-source verification remains blocked: no provider
  package stack and no provider credentials.

## Conclusion

The high fixed-model Sharpe came from a short, selected 9-month window and did
not survive walk-forward refitting. After correcting the winsorization leakage,
annualization, turnover/cost, and holdings reporting:

> **No deployable alpha is established. The 9-month test is insufficient, and
> the walk-forward result is not significant.**
