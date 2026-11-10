# MarketParquet Coverage, Batch 6, and Fixed-5 OOS

Date: 2026-10-29 UTC
Research only. No canonical write.

## 1. MarketParquet actual access

| Date | HTTP | Rows | Result |
|---|---|---:|---|
| 2026-10-28 | 200 | 6,503 | parsed |
| 2026-10-27 | 200 | 6,499 | parsed |
| 2026-10-22 | 200 | 6,521 | parsed |
| 2026-10-21 | 401 | 0 | login required |
| 2026-09-28 | 401 | 0 | free account covers last year |
| 2026-04-30 | 401 | 0 | free account covers last year |
| 2025-11-03 | 401 | 0 | free account covers last year |

Actual no-account window: **7 recent trading days**.

The 365-day free-account claim is documented but **not verified**; no account
was created.

License: internal research/storage and derived results allowed; raw Parquet
public redistribution prohibited. Raw files remain local only.

## 2. Other sources

No new source was tested twice after prior blocks:

- ADGSTUDIOS: 502, unverified.
- Stooq: anti-bot HTML, unverified.
- Nasdaq: current-only; delisted symbols rejected.
- Sina/AKShare: technical partial; terms unresolved.

**No second long-history, delisted-inclusive, licence-clear free source.**

## 3. Batch 6 鈥?25 names

```text
HRS, JEC, NFX, SCG, TSS, VIAB, CTL, NBL, LB, VAR,
DISCK, FBHS, NLSN, TWTR, SIVB, PXD, JNPR, FLR, GT, JEF,
MAC, MAT, TMK, TRIP, COTY
```

| Category | Count |
|---|---:|
| `STILL_TRADING` | **7** |
| `TICKER_OR_NAME_CHANGED` | **8** |
| `DELISTED_OR_ACQUIRED` | **10** |
| Total | **25** |

Still trading:

`FLR, GT, JEF, MAC, MAT, TRIP, COTY`

Changed:

`HRS -> LHX, JEC -> J, CTL -> LUMN, LB -> BBWI, FBHS -> FBIN, TMK -> GL, VIAB -> PARA, DISCK -> WBD`

Delisted/acquired:

`NFX, SCG, TSS, NBL, VAR, NLSN, TWTR, SIVB, PXD, JNPR`

TWTR/SIVB are confirmed by SEC empty ticker and 25-NSE/15-12G metadata, not
only by price gaps. Exact last-trade price is still not independently verified.

## 4. Combined status

| Category | Count |
|---|---:|
| `HISTORICAL_MEMBERSHIP_ONLY` | **54** |
| `DELISTED_OR_ACQUIRED` | **69** |
| `STILL_TRADING` | **46** |
| `TICKER_OR_NAME_CHANGED` | **30** |
| `TICKER_REUSE_SUSPECTED` | **2** |
| `IDENTITY_UNRESOLVED` | **1** |
| Total | **202** |

Reviewed: **148 / 202**.

## 5. Fixed-five chronological OOS

Tool:

`tools/research/fixed5_walkforward_audit.py`

No new factors, no parameter search. Annual buckets, 2023鈥?026; signals at
month-end close; 5 bps one-way; benchmark equal-weight eligible universe.

| Year | n | Benchmark ann | Best factor | Best ann | Worst factor | Worst ann |
|---|---:|---:|---|---:|---|---:|
| 2023 | 12 | 5.34% | 12-1 momentum | 10.70% | ATR low | -18.81% |
| 2024 | 12 | 21.02% | 12-1 momentum | 34.26% | ATR low | -20.40% |
| 2025 | 12 | 14.88% | MA50 | 14.69% | ATR low | -33.06% |
| 2026 | 9 | 13.65% | MA50 | -3.34% | Vol60 | -24.38% |

Key facts:

- 12-1 momentum beat benchmark in 2023/2024 but lost in 2025/2026.
- MA50 was near benchmark in 2025 but negative in 2026.
- Low-vol/ATR factors were consistently negative.
- No factor is stable across all years.
- 2026 has only 9 months; annualized metric is not a full-year result.
- Costs are included, but no slippage/execution latency model beyond 5 bps.
- Current-universe panel remains survivorship-biased; results are exploratory.

Conclusion: **no stable, deployable alpha across chronological OOS years.**

## 6. Tests

- Batch 6 classifier: 12 tests total in `test_missing_reason_classifier.py`.
- Fixed-5 OOS: 2 tests.
- MarketParquet source: 4 tests.

Full CI is reported in the final chat after the commit.

## 7. Artifacts

- v7: `docs/research/missing_202_reason_classification_v7_2026-10-29.csv`
- batch 6 SEC: `docs/research/missing_202_batch6_sec_2026-10-29.json`
- annual OOS: `docs/research/fixed5_walkforward_2026-10-29.json/.csv`
- tool: `tools/research/fixed5_walkforward_audit.py`
- MarketParquet audit: `docs/research/marketparquet_source_audit_2026-10-29.json`
