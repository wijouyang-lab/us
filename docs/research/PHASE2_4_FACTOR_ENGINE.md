# Phase 2.4 Unified Historical Factor Engine

Date: 2026-10-30
Research only. No production changes.

## 1. Pre-coding audit

Existing factor logic:

- `quant_factor_lab.py`: current snapshot helpers, `zscore_20d`, momentum.
- `dashboard_export.py`: RSI/ATR/KDJ/MACD current-row helpers, not a unified
  historical panel.
- `quant_factor_validation.py`: factor-statistics consumer, not a calculator.
- `technical_strategy_backtest.py`: own momentum/trend/RSI/ATR/low-vol
  calculations, now superseded for factor production by this engine.
- `forward_return.py`: reusable label module; **not** duplicated here.
- Price panel: split-adjusted OHLCV, no dividends. 1,239,013 rows, 503 tickers,
  2016-09-19..2026-10-28.
- SPY: independent local series for Beta and relative strength.

Dependencies: pandas, numpy, pyarrow already installed. No new dependency.

## 2. Engine

`tools/research/factor_engine.py`

Inputs: `Date, Ticker, Open, High, Low, Close, Volume`; optional SPY close.

20 factors:

| Factor | Formula / window | Warm-up |
|---|---|---:|
| MA20/50/200 | close rolling mean | 20/50/200 |
| MA20_Slope_5D | MA20 / MA20.shift(5) 鈭?1 | 25 |
| MACD_Hist | EMA12 鈭?EMA26 鈭?EMA9(signal) | 35 |
| ADX14 | Wilder DI/DX/ADX | 28 |
| Momentum_5D/20D/60D/120D | close / close.shift(n) 鈭?1 | n |
| RSI14 | Wilder average gain/loss | 14 |
| KDJ_J | 9-day RSV, K/D EWM alpha 1/3, J=3K鈭?D | 9 |
| Bias20 | close/MA20 鈭?1 | 20 |
| ATR_Percent | Wilder ATR14 / close | 14 |
| Realized_Volatility_20D | std(daily return, 20) 脳 鈭?52 | 20 |
| Beta_60D | rolling 60 cov(stock, SPY)/var(SPY) | 60 |
| ZScore20 | (close鈭扢A20)/std20 | 20 |
| Volume_Ratio_5D/20D | volume / volume MA | 5/20 |
| Stock_RS_20D_vs_SPY | stock 20D return 鈭?SPY 20D return | 20 |

Factors use only current/past data. No forward-return column exists in the
factor table. SPY is aligned by date; if SPY is unavailable, Beta and Stock_RS
are NaN, not fabricated.

## 3. Status model

`factor_status()` distinguishes:

- `FACTOR_AVAILABLE`
- `FACTOR_WARMUP`
- `MISSING_INPUT`
- `LABEL_NOT_MATURED`
- `VALIDATION_INSUFFICIENT`
- `VALIDATED`

A factor being computed never implies `VALIDATED`. Validation is a separate
research decision.

## 4. Full historical backfill

| Metric | Value |
|---|---:|
| Rows | 1,239,013 |
| Tickers | 503 |
| Date range | 2016-09-19..2026-10-28 |
| Runtime | **11.0 s** |
| Output size | ~23 MB Parquet |
| Output | `data/research/factor_snapshots/factors_10y_2026-10-30.parquet` |

This Parquet is local research output and is not committed to Git.

### Coverage (selected; full file in JSON)

| Factor | Valid | Coverage | Warm-up rows |
|---|---:|---:|---:|
| MA20 | 1,229,456 | 99.23% | 9,557 |
| MA50 | 1,214,395 | 98.01% | 24,618 |
| MA200 | 1,139,290 | 91.95% | 99,723 |
| MACD_Hist | 1,222,427 | 98.66% | 17,088 |
| ADX14 | 1,225,896 | 98.94% | 13,574 |
| RSI14 | 1,231,927 | 99.43% | 6,539 |
| Beta_60D | 1,208,873 | 97.57% | 29,638 |
| Stock_RS_20D_vs_SPY | 1,228,953 | 99.19% | 9,557 |
| Volume_Ratio_5D | 1,236,440 | 99.79% | 2,012 |

Lowest coverage is MA200 at 91.95%, entirely consistent with the 200-day
warm-up and short-history tickers. No factor was filled.

## 5. Forward-return labels

Reused `tools/research/forward_return.py`; no duplicate implementation.

Full factor dates 脳 5 horizons, vectorized session-index maturity check,
validated against the real module on a 5,000-row sample:

| Horizon | MATURED | NOT_MATURED | MISSING_PRICE |
|---:|---:|---:|---:|
| 1D | 1,238,007 | 503 | 503 |
| 5D | 1,235,995 | 2,515 | 503 |
| 10D | 1,233,480 | 5,030 | 503 |
| 20D | 1,228,451 | 10,059 | 503 |
| 60D | 1,208,371 | 30,139 | 503 |

`NOT_MATURED` is a label state, not a factor failure.

## 6. Future-data leakage test

The test mutates all prices after a cutoff and recomputes factors:

```text
future prices 脳 1.5 after cutoff
all factor rows at/before cutoff must be identical
```

Result: **passed**. This verifies actual numerical invariance, not just code
inspection. Additional tests: ticker isolation, date sorting, warm-up,
missing input, SPY/Beta alignment, no forward columns, deterministic rerun.

## 7. Tests

`tests/test_factor_engine.py`: **6 passed**.

Full project CI is reported after commit.

## 8. AKShare evaluation

Installed version: 1.20.2. Actual `stock_us_daily(symbol, adjust="")` sample:

| Ticker | Rows | Start | End | Missing | Duplicate | Invalid OHLC |
|---|---:|---|---|---:|---:|---:|
| AAPL | 10,064 | 1984-09-07 | 2026-10-29 | 0 | 0 | 0 |
| MSFT | 9,682 | 1986-03-13 | 2026-10-29 | 0 | 0 | 0 |
| NVDA | 5,796 | 1999-01-22 | 2026-10-29 | 0 | 0 | 0 |
| TSLA | 3,935 | 2011-01-26 | 2026-10-29 | 0 | 0 | 0 |
| SPY | 6,494 | 2001-01-02 | 2026-10-29 | 0 | 0 | 1 |

Repeated AAPL requests: same shape, same last close.

Limitations:

- not a PIT universe source;
- no delisted coverage guarantee;
- adjustments are vendor-dependent;
- no historical industry classification or VIX evaluated here;
- not used as a replacement for the existing price panel.

## 9. Remaining limits

- current 503 universe: survivorship bias;
- no dividend total return;
- no historical index membership;
- no historical sector mapping;
- 20D/60D labels are only partially mature at the latest dates;
- no factor validation yet; coverage is not alpha evidence.

## 10. Artifacts

- `tools/research/factor_engine.py`
- `tools/research/factor_label_maturity.py`
- `tests/test_factor_engine.py`
- `docs/research/factor_engine_summary_2026-10-30.json`
- `docs/research/factor_forward_label_maturity_2026-10-30.json`
- `docs/research/akshare_us_sample_2026-10-30.json`
- local Parquet: `data/research/factor_snapshots/factors_10y_2026-10-30.parquet`
