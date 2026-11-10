# First Real Historical Backtest 鈥?2026-10-29

Research only. No production changes.

## What was actually run

Existing fixed five-factor research, reused without a new factor search:

```bash
python -m tools.research.restricted_503_factor_validation \
  --price-panel price10y_1028.csv \
  --output-prefix docs/research/restricted_503_factor_validation_2026-10-29
```

The panel is the existing 503-ticker raw OHLCV research panel, updated through
2026-10-28. HUBB remains missing on 10/28, so complete-case filtering leaves
**465 tickers**.

## Data

| Item | Value |
|---|---:|
| Rows | 1,182,030 |
| Tickers after complete-date filter | 465 |
| Sessions | 2,542 |
| Date range | 2016-09-19 .. 2026-10-28 |
| Price basis | raw OHLCV |
| Survivorship | current-universe; **survivorship-biased** |
| Label | CURRENT-UNIVERSE EXPLORATORY 鈥?NOT PIT 鈥?NOT DEPLOYABLE |

## Design

- Five pre-existing directions only:
  - Vol60 low
  - ATR% low
  - 12-1 momentum high
  - 1-month reversal low
  - MA50 high
- 20-session forward return, 20-session rebalance.
- Monthly cross-sectional Q5/Q1.
- Winsorize 1%/99% based on current cross-section (exploratory; not full PIT).
- 5 bps one-way turnover cost.
- Chronological train 鈮?022, test 2023鈥?026.
- No parameter selection on test.
- Benchmark: equal-weight eligible universe.

## Test-period results (2023鈥?026)

45 rebalances, net:

| Factor | Net monthly | Annualized | Sharpe | p | BH q |
|---|---:|---:|---:|---:|---:|
| Vol60 low | -1.58% | -18.89% | -0.98 | 0.0649 | 0.1967 |
| ATR% low | -1.44% | -17.43% | -0.94 | 0.0787 | 0.1967 |
| 12-1 momentum | +0.55% | +5.29% | 0.31 | 0.4561 | 0.4561 |
| 1-month reversal | -0.83% | -10.42% | -0.74 | 0.1746 | 0.2910 |
| MA50 | +0.46% | +4.76% | 0.35 | 0.4329 | 0.4561 |

No positive factor survives BH q<0.05.

Benchmark:

```text
n = 120 monthly observations
annualized = 14.71%
Sharpe = 0.88
max drawdown = -21.60%
```

All five candidates underperform the benchmark; none is statistically
significant after correction.

## Cost and turnover

- Cost model: 5 bps one-way 脳 turnover.
- Mean turnover: ~22%鈥?8% by factor.
- Gross/net difference is small; absence of edge is not a cost artifact.

## Out-of-sample status

- Chronological train/test exists.
- Test period has 45 monthly rebalances; tiny.
- No rolling-refit model; these are fixed factors.
- No claim of deployable alpha.

## Artifacts

- `docs/research/restricted_503_factor_validation_2026-10-29.csv`
- `docs/research/restricted_503_factor_validation_2026-10-29.json`
- `tools/research/restricted_503_factor_validation.py`

## Conclusion

The first real run on the current 465-complete-name panel finds **no reliable
long-only/short-long factor edge** in the fixed five directions. This is not a
new search and not an alpha claim. It is consistent with the prior 466-name
result, with small changes from the updated panel.

Next work should improve data/PIT/universe, not search more factors on the same
sample.
## Audit correction

The 14.71% benchmark in this first report was **full-sample**, not the 45-month
test scope. See `BACKTEST_AUDIT_2026-10-29.md` for the corrected test benchmark
(11.68%, Sharpe 0.881) and next-open execution sensitivity. Original results
are retained, not overwritten.
