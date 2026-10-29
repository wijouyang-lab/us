# Expanded Coverage 閳?Second-Round Validation

Date: 2026-10-29 UTC
Research only. Original panel preserved.

## Coverage before/after

| Metric | Original complete-date run | Expanded available-history |
|---|---:|---:|
| Panel unique tickers | 503 | 503 |
| Tickers with all 2,542 dates | **465** | n/a |
| Tickers used in factor cross-section | 465 | **503** |
| Test-period mean names | 464.4 | **496.8** |
| New usable tickers | 閳?| **+38** |
| Rows used | 1,182,030 | **1,239,013** |
| Added usable rows | 鈥?| **+56,983** |
| New raw price rows downloaded | 0 | 0 |

This is an improvement in **universe utilization**, not newly fabricated price
rows. The same 1,239,013-row raw panel is used; the old complete-date filter
used only 1,182,030 of those rows.

## Missing-ticker classification

38 tickers are not full-history:

| Category | Count |
|---|---:|
| History starts after panel start (IPO/listing) | **36** |
| Single-date gap (`FISV` 2025-11-12) | 1 |
| Provider missing latest date (`HUBB` 2026-10-28) | 1 |

CSV:

`docs/research/missing_ticker_classification_2026-10-29.csv`

No delisted ticker is present in this current-universe panel. Historical
constituent/delisted price coverage remains unresolved and cannot be claimed.

## Annual coverage

| Year | Rows | Tickers | Sessions |
|---|---:|---:|---:|
| 2016 | 34,194 | 469 | 73 |
| 2017 | 118,282 | 472 | 251 |
| 2018 | 118,953 | 476 | 251 |
| 2019 | 120,936 | 482 | 252 |
| 2020 | 122,442 | 487 | 253 |
| 2021 | 123,424 | 491 | 252 |
| 2022 | 123,492 | 493 | 251 |
| 2023 | 123,477 | 495 | 250 |
| 2024 | 125,324 | 498 | 252 |
| 2025 | 124,767 | 500 | 250 |
| 2026 | 103,722 | 503 | 207 |

## Second-round backtest

Fixed five factors, unchanged definitions and parameters:

- 20D forward, monthly rebalance, Q5/Q1;
- 5 bps one-way;
- train 2016閳?022; test 2023閳?026;
- expanded available history (no complete-date filter).

Test: 45 monthly observations, benchmark **13.58%** annualized, Sharpe **0.997**,
max drawdown **-13.36%**.

| Factor | Net month | Annualized | Sharpe | Max DD | p | BH q |
|---|---:|---:|---:|---:|---:|---:|
| Vol60 low | -2.02% | -23.55% | -1.08 | -67.8% | 0.0376 | 0.0939 |
| ATR% low | -2.00% | -23.23% | -1.10 | -67.3% | 0.0326 | 0.0939 |
| 12-1 momentum | +0.83% | +8.50% | 0.45 | -24.7% | 0.3102 | 0.3246 |
| 1M reversal | -0.94% | -11.68% | -0.78 | -48.2% | 0.1501 | 0.2501 |
| MA50 | +0.64% | +6.75% | 0.45 | -20.7% | 0.3246 | 0.3246 |

No positive factor beats the 13.58% benchmark; no positive BH q<0.05.

## Data quality

Checks applied through the existing loader/evaluator:

- duplicate `(Date,Ticker)`: 0 in panel;
- OHLCV validity: existing panel has one known legacy HUBB 2021 anomaly; no
  synthetic rows;
- missing labels: dropped, not zero-filled;
- date alignment: XNYS monthly dates from panel; no natural-day arithmetic;
- survivorship: current-universe, still biased;
- adjusted close: not available in panel; raw only.

## What is still not solved

1. No delisted/historical-universe price data.
2. No approved adjusted-close/corporate-action feed.
3. HUBB 2026-10-28 still missing.
4. PIT/universe bias remains.
5. No new free delisted source was validated.

## Artifacts

- `docs/research/restricted_503_factor_expanded_2026-10-29.csv/.json`
- `docs/research/missing_ticker_classification_2026-10-29.csv`
- `tools/research/restricted_503_factor_expanded.py`
- report: this file

## Conclusion

Second-round validation is executable on the existing free panel and expands
the cross-section from 465 to 503 names. It still finds no reliable alpha and
does not solve delisted/current-universe bias. More factor search is not
justified; data coverage and PIT remain the limiting work.
