# Backtest Audit: Test-Scope Benchmark and Execution Alignment

Date: 2026-10-29 UTC
Research only. Original results preserved.

## Core finding

The old `120` benchmark observation count and factor `45` test count were not
comparable:

- `120` = full-sample benchmark, 2016鈥?026.
- `45` = 2023鈥?026 factor test after requiring 20D forward labels.

The old comparison used a **full-period benchmark** against a **test-period
factor**. This was a scope mismatch, not extra factor samples.

## Date counts

| Item | Count |
|---|---:|
| All month-end dates in panel | 122 |
| Full benchmark valid dates | 120 |
| 2023鈥?026 month-end dates | 46 |
| Test dates with 20D labels | **45** |
| Factor test dates | **45** |
| Audit rows | 45 |

Why 122 -> 120: two full-history dates have fewer than 80 eligible names.
Why 46 -> 45: the final test month lacks a complete 20-session forward label.

## Corrected benchmark

Using exactly the 45 factor test dates and the same eligible universe:

| Metric | Old (wrong scope) | Corrected test scope |
|---|---:|---:|
| n | 120 | **45** |
| Annualized | 14.71% | **11.68%** |
| Vol | 16.70% | 13.26% |
| Sharpe | 0.881 | **0.881** |
| Max drawdown | -21.60% | **-13.14%** |

The old benchmark was not a valid test-period comparator.

## Factor test results, same 45 dates

| Factor | Net month | Annualized | Sharpe | Max DD | p | BH q |
|---|---:|---:|---:|---:|---:|---:|
| Vol60 low | -1.58% | -18.90% | -0.98 | -59.0% | 0.0649 | 0.1967 |
| ATR% low | -1.44% | -17.43% | -0.94 | -56.8% | 0.0787 | 0.1967 |
| 12-1 momentum | +0.55% | +5.29% | 0.31 | -23.2% | 0.4561 | 0.4561 |
| 1-month reversal | -0.83% | -10.42% | -0.74 | -45.0% | 0.1746 | 0.2910 |
| MA50 | +0.46% | +4.76% | 0.35 | -18.1% | 0.4329 | 0.4561 |

All still below the corrected 11.68% benchmark; no positive BH q<0.05.

## Execution-timing issue

Original backtest computes:

```text
signal at month-end close
forward return from same close to close+20 sessions
```

This has zero execution lag: the factor is observed at the close and assumed
filled at the same close. That is not an executable assumption.

### Lagged next-open sensitivity

Corrected execution assumption:

```text
signal at month-end close
entry at next session open
exit at open after 20 sessions
```

| Metric | Original close-to-close | Lagged next-open |
|---|---:|---:|
| Test observations | 45 | 44 |
| Benchmark annualized | 11.68% | 10.49% |
| Benchmark Sharpe | 0.881 | 0.819 |
| Vol60 net annual | -18.90% | -19.16% |
| ATR% net annual | -17.43% | -18.15% |
| 12-1 net annual | +5.29% | +10.37% |
| 1M reversal net annual | -10.42% | -13.19% |
| MA50 net annual | +4.76% | +7.99% |

No lagged factor beats the lagged benchmark; no BH q<0.05.

The lagged result is closer to executable but still assumes an open fill with
no slippage. It is not a live-trading result.

## Costs and turnover

- 5 bps one-way 脳 turnover.
- Mean turnover roughly 22%鈥?8%.
- Gross-to-net reduction is visible but small relative to the no-edge result.
- Initial book turnover is treated as full turnover; no double-count detected
  in the one-way definition.

## Monthly audit

Per-month table:

`docs/research/restricted_503_backtest_audit_2026-10-29.csv`

Contains:

- signal date;
- entry assumption date;
- exit date after 20 sessions;
- eligible/labeled/missing names;
- benchmark return;
- factor gross/net/turnover/cost.

## Artifacts

- Audit JSON: `docs/research/restricted_503_backtest_audit_2026-10-29.json`
- Audit CSV: `docs/research/restricted_503_backtest_audit_2026-10-29.csv`
- Lagged results: `docs/research/restricted_503_factor_lagged_2026-10-29.json/.csv`
- Original baseline results preserved.

## Conclusion

The 120 vs 45 gap is fully explained by full-sample vs test-sample scope.

Correctly compared, the five fixed factors still fail to beat the
equal-weight benchmark and show no positive BH-significant result. Original
close-fill results are optimistic; next-open sensitivity remains negative for
the benchmark-relative conclusion.

No new factors, no parameter search, no alpha claim.
