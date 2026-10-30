# Phase 2.1 Historical Data Quality Audit

Date: 2026-10-30
Research only. No production changes.

## 1. Price panel

Source: local `price10y_1028.csv`, not committed raw data.

| Metric | Result |
|---|---:|
| Rows | 1,239,013 |
| Tickers | 503 |
| Date range | 2016-09-19 .. 2026-10-28 |
| Duplicate ticker/date | 0 |
| Null close | 0 |
| Non-positive close | 0 |
| Zero volume | 2,305 |
| Invalid OHLC | **1** |
| Daily move >50% | 12 |
| Daily move >90% | 1 |

Invalid OHLC row:

```text
2021-05-05 HUBB
Open 195.98 / High 198.64 / Low 196.21 / Close 198.13
Low > Open
```

Split evidence: AAPL close is about $28 in 2016, consistent with split-adjusted
prices; the panel does **not** include dividends.

The 12 >50% moves include real events (COVID selloff, MRNA, CVNA, HOOD) and
should be reviewed individually before being treated as errors. They are not
automatically safe or automatically bad.

## 2. Current factor snapshots

| File | Rows | Dates | Tickers | Critical result |
|---|---:|---:|---:|---|
| `quant_factor_snapshot.csv` | 4,825 | 17 | 406 | only 2026-10-07..2026-10-29 |
| `quant_factor_backtest.csv` | 4,529 | 16 | 401 | **Forward_Return_20D = 0 non-null** |
| `quant_factor_validation.csv` | 72 | 鈥?| 鈥?| 20D N = 0 for all 24 factors |

Validation sample counts:

```text
5D:  N = 3,080
10D: N = 1,914
20D: N = 0
```

Therefore:

- no 20-day strategy-level return sequence exists;
- the 20D factor rows are `NOT_ENOUGH_DATA`;
- 10D coverage is materially smaller than 5D;
- no strategy Sharpe/CAGR can be computed from this snapshot history.

## 3. Portfolio and trade files

| File | Rows | Range | Use |
|---|---:|---|---|
| `portfolio_50000_history.csv` | 16 | 2026-10-06..2026-10-29 | paper ledger, not a strategy backtest |
| `trade_history.csv` | 397 | 2026-05-27..2026-10-26 | production/paper trade history, not research returns |

Neither is a multi-year strategy return series.

## 4. PIT and fundamental data

- `Fundamental_Score` exists in snapshots (2,063 nonzero rows), but there is no
  PIT fundamental history file and no verified filing-availability timestamp.
- SEC companyfacts sample: 5/5 have assets/revenue; only 3/5 have gross profit;
  `filed` is date-only.
- No historical index membership or delisted-security panel.
- No exact macro/news release-time history in the repository.
- PIT event admission remains 0.

## 5. Classification

### Reliable

- price panel structural integrity: no duplicate ticker/date, no null or
  non-positive closes;
- split-adjusted price levels;
- 503-ticker current universe for descriptive work;
- 5D/10D factor snapshots with explicit sample counts.

### Repairable

- one invalid HUBB OHLC row;
- zero-volume rows (liquidity filter needed);
- >50% moves requiring event/split review;
- 20D forward returns once enough future sessions mature;
- 10D/20D sample imbalance with more history.

### Free-source gaps

- historical S&P 500 membership and effective dates;
- delisted tickers and delisting returns;
- dividend-adjusted total-return series;
- exact SEC acceptance/public availability for fundamentals;
- exact macro/news release timestamps and revisions.

### Must exclude

- treating the current 503-ticker universe as historical membership;
- using current `Fundamental_Score` as historical PIT;
- using 20D validation rows (N=0) as evidence;
- using paper trade history as a strategy backtest;
- using factor IC as strategy returns.

## 6. Phase 2.1 decision

The data is **not yet sufficient** for the Phase 2.2 strategy-level return
series. The blocker is not code; it is the absence of a historical universe and
a mature 20D return sample.

Allowed next work:

1. define the standard strategy-return schema without inventing values;
2. run descriptive 5D/10D research with explicit non-PIT labels;
3. build repair tooling for the one bad OHLC row and liquidity filters;
4. accumulate 20D returns until the sample is mature.

Not allowed:

- publishing 20D Sharpe from N=0;
- using the current universe as if it were historical;
- claiming quality/value results without PIT fundamentals.

## 7. Reproduce

```bash
python -m tools.research.data_quality_audit \
  --price-panel ../price10y_1028.csv \
  --output docs/research/price_panel_audit_phase21_2026-10-30.json
```

Output:

`docs/research/price_panel_audit_phase21_2026-10-30.json`
