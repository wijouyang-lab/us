# P9.2 Benchmark and Price-Adjustment Audit

Date: 2026-11-09
Status: **P9_2_BENCHMARK_CORRECTED_STRATEGY_NO_GO**

Independent audit branch. P9.1 history is not overwritten.

## 1. P9.1 benchmark bug

P9.1 code:

```python
series = 0.2*QQQ + 0.8*BIL
pct = 0.2*series.pct_change() + 0.8*BIL.pct_change()
```

The first line already creates a price basket. Applying `0.2` again produces
approximately **4% QQQ / 96% BIL**, not 20/80. Exact reproduction:

```text
P9.1 reported:              CAGR 2.09%, MaxDD -3.79%
P9.1 formula reproduced:    CAGR 2.08%, MaxDD -3.79%
```

## 2. Corrected benchmark

Data: yfinance auto-adjusted QQQ/SPY/BIL, 2007-05-30..2024-12-31, return
weighted, daily rebalanced, no cost (same no-cost assumption as P9.1):

| Benchmark | CAGR | MaxDD | Vol |
|---|---:|---:|---:|
| 20% QQQ + 80% BIL | **4.28%** | **-11.43%** | 4.44% |
| 20% SPY + 80% BIL | 3.19% | -11.57% | 4.74% |
| 100% BIL | 1.14% | -0.79% | 0.51% |

P9.1 benchmark was not merely a different rebalance frequency; it was a
different portfolio weight (4/96). All P9.1 strategy comparisons must use the
corrected benchmark.

## 3. G comparison

G reported, through 2026-10-30:

```text
CAGR 4.42%, MaxDD -11.38%
```

Rebuilt with current yfinance adjusted data and daily 20/80 rebalance:

```text
CAGR 4.54%, MaxDD -11.43%
delta CAGR +0.12 pp, delta MaxDD -0.05 pp
```

The exact G code/data is not present in this repository. The reconstruction is
therefore **PARTIAL**, but it is close enough to identify the P9.1 2.09% figure
as the double-scaling error, not a legitimate G-vs-P9.1 data difference.

## 4. Corporate actions and dividends

- QQQ: 83 dividends through 2024, 1 split.
- SPY: 129 dividends, 0 splits.
- BIL: 107 dividends, 1 split.
- P9.1 ETF data matches yfinance adjusted closes at the endpoints checked.
- `auto_adjust` includes dividends and splits for the ETFs.
- P9.1 stock OHLC uses `adjusted_close/raw_close`, so historical patterns use
  **future dividend adjustment**. Strict PIT signal data is therefore
  `PARTIAL`.
- No independent dividend ledger; no claim of fully audited dividend
  reinvestment.
- Portfolio stock returns use adjusted open, so cash dividends are embedded in
  price return, not separately credited. No double counting, but also no
  independent dividend cash accounting.

## 5. Strategy exposure

| Strategy | Avg equity | Avg BIL | Max budget | Annualized turnover | Trades | Cost |
|---|---:|---:|---:|---:|---:|---:|
| A | 12.0% | 88.0% | 20% | 2.95x | 782 | $751 |
| B | 11.1% | 88.9% | 20% | 2.72x | 731 | $683 |
| C | 9.2% | 90.8% | 20% | 2.26x | 553 | $562 |
| D | 7.3% | 92.7% | 20% | 1.82x | 441 | $469 |
| E | 9.6% | 90.4% | 20% | 2.32x | 620 | $619 |
| F | 5.8% | 94.2% | 20% | 1.41x | 350 | $377 |

Risk-matched benchmarks:

```text
10% QQQ + 90% BIL: CAGR 2.72%, MaxDD -5.30%
10% SPY + 90% BIL: CAGR 2.18%, MaxDD -5.32%
```

Even against 10/90, C (1.04%) and A (1.98%) fail. Low exposure does not explain
the underperformance.

## 6. Event table completion

`event_stats_complete.csv` has all 24 experiment/horizon cells:

- events;
- non-overlap events;
- absolute mean;
- excess SPY;
- excess BIL;
- HAC t, p, BH q;
- 95% CI.

Non-overlap definition: per ticker, keep the first event, then require at least
`horizon * 7/5` calendar days before the next event. This is a conservative
greedy filter, not a full covariance adjustment. Same-day cross-sectional
correlation remains in the raw event sample; the non-overlap table reduces
serial overlap only.

Event mean returns are not strategy Alpha.

## 7. Impact on P9.1 conclusions

- P9.1 “underperformed 20QQQ/80BIL” remains true, and is larger than reported.
- P9.1 reported benchmark CAGR 2.09% is invalid.
- P9.1 reported benchmark MaxDD -3.79% is invalid; corrected -11.43%.
- P9.1 strategy MaxDD comparison therefore changes materially.
- P9.1 NO-GO remains; no GO, no Shadow.
- Strict PIT signal data remains PARTIAL because of future-adjusted OHLC.

## 8. Files

```text
data/research/p9_2_benchmark_audit/
  benchmark_rebuild.json
  benchmark_variants.csv
  risk_matched_benchmarks.csv
  corporate_actions_audit.csv
  strategy_exposure_audit.csv
  event_stats_complete.csv
  p9_2_audit_status.json
docs/research/p9_2_benchmark_audit.md
```
