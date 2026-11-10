# Paired Excess-Return Audit

Date: 2026-10-29 UTC
Research only. No new factors or parameters.

## Data and test

- Panel: `price10y_1028.csv`, 1,239,013 rows, 503 names, 2,542 sessions.
- Test: 2023鈥?026, 45 monthly dates with complete 20D labels.
- Same eligible universe per date, requiring all five factor values and Fwd20.
- Benchmark: equal-weight mean of the same date/universe.
- Cost: 5 bps one-way 脳 turnover.
- Entry assumption: month-end close signal, zero execution lag; **exploratory**.

## Winsorization

Two separate modes:

1. **raw**: neither factor nor benchmark winsorized.
2. **winsorized**: both use the same 1%/99% bounds, computed per date within
   the same eligible universe.

No mixing of the two modes.

## Excess results 鈥?raw

Excess = factor net 鈭?same-date benchmark.

| Factor | Mean monthly excess | Annualized excess | Paired t | p | BH q | Positive months | Active vol | Active maxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Vol60 low | -3.45% | -34.37% | -2.58 | 0.0133 | 0.0334 | 40.0% | 31.1% | -85.1% |
| ATR% low | -3.43% | -34.20% | -2.64 | 0.0113 | 0.0334 | 37.8% | 30.1% | -84.7% |
| 12-1 momentum | -0.10% | -1.24% | -0.10 | 0.9181 | 0.9181 | 53.3% | 23.4% | -29.4% |
| 1M reversal | -2.04% | -21.91% | -2.29 | 0.0270 | 0.0450 | 31.1% | 20.7% | -70.5% |
| MA50 | -0.47% | -5.54% | -0.53 | 0.5982 | 0.7477 | 44.4% | 20.7% | -35.8% |

Annualized excess uses `(1 + mean monthly excess)^12 - 1`.

## Excess results 鈥?winsorized

| Factor | Mean monthly excess | Annualized excess | Paired t | p | BH q | Positive months | Active vol | Active maxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Vol60 low | -3.04% | -30.95% | -2.36 | 0.0227 | 0.0541 | 40.0% | 29.9% | -81.7% |
| ATR% low | -3.03% | -30.87% | -2.44 | 0.0190 | 0.0541 | 40.0% | 28.9% | -81.3% |
| 12-1 momentum | -0.24% | -2.83% | -0.24 | 0.8091 | 0.8091 | 53.3% | 22.9% | -33.0% |
| 1M reversal | -1.93% | -20.86% | -2.21 | 0.0324 | 0.0541 | 31.1% | 20.3% | -68.2% |
| MA50 | -0.50% | -5.83% | -0.58 | 0.5681 | 0.7101 | 42.2% | 20.2% | -36.1% |

No factor has positive excess. Low-vol/ATR/reversal have **significantly
negative** excess in raw mode; winsorized q is ~0.054, not significant at 5%.

## Auxiliary net-vs-zero tests

The old factor net return vs zero is retained as an auxiliary metric, not as
alpha evidence:

| Mode | Vol60 | ATR | Mom12 | Mom1 | MA50 |
|---|---:|---:|---:|---:|---:|
| raw p | 0.0212 | 0.0185 | 0.2293 | 0.1726 | 0.3317 |
| raw q | 0.0531 | 0.0531 | 0.2866 | 0.2866 | 0.3317 |
| winsor p | 0.0399 | 0.0345 | 0.3107 | 0.1843 | 0.3770 |
| winsor q | 0.0998 | 0.0998 | 0.3770 | 0.3072 | 0.3770 |

The low-vol net-vs-zero result is weak and not the same as excess-vs-benchmark.
It does not establish alpha.

## Overlap / HAC

Test-date session gaps are 19鈥?3 sessions:

- 6 adjacent pairs have <20 sessions;
- 18 have 鈮?0 sessions.

Thus 20D windows partially overlap; ordinary t independence is imperfect.
Newey鈥揥est lag-1 sensitivity:

| Mode | Vol60 | ATR | Mom12 | Mom1 | MA50 |
|---|---:|---:|---:|---:|---:|
| raw NW t | -2.42 | -2.51 | -0.11 | -2.51 | -0.51 |
| winsor NW t | -2.21 | -2.30 | -0.25 | -2.43 | -0.56 |

The negative low-vol excess remains directionally robust; no positive alpha.

## Execution caveat

The main result is **close-to-close, zero-lag exploratory**. The separate
next-open sensitivity (prior artifact) has 44 observations and a lower
benchmark; it is not mixed into this table. No claim of executable open/close
fills is made.

## Conclusion

On same dates, same eligible universe and same winsorization:

- no factor has positive excess return;
- low-vol/ATR/reversal significantly underperform in raw mode;
- momentum and MA50 are indistinguishable from benchmark;
- no reliable alpha;
- 45 overlapping months are not robust significance evidence for a deployable
  strategy.

## Artifacts

- monthly CSV: `docs/research/restricted_503_excess_audit_2026-10-29_monthly.csv`
- JSON: `docs/research/restricted_503_excess_audit_2026-10-29.json`
- code: `tools/research/restricted_503_excess_audit.py`
- tests: `tests/test_excess_audit.py`
