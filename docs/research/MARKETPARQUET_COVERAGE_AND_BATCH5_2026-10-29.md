# MarketParquet Coverage Test and Batch 5

Date: 2026-10-29 UTC
Research only. No canonical write.

## 1. MarketParquet actual date access

No account, direct GET:

| Date | HTTP | Bytes | Rows | Result |
|---|---|---:|---:|---|
| 2026-10-28 | 200 | 232,449 | 6,503 | parsed |
| 2026-10-27 | 200 | 232,014 | 6,499 | parsed |
| 2026-10-22 | 200 | 233,079 | 6,521 | parsed |
| 2026-10-21 | 401 | 111 | 0 | login required |
| 2026-10-20 | 401 | 111 | 0 | login required |
| 2026-09-28 | 401 | 111 | 0 | free account covers last year |
| 2026-04-30 | 401 | 111 | 0 | free account covers last year |
| 2025-11-03 | 401 | 111 | 0 | free account covers last year |

Conclusion:

```text
No-account window: 7 recent trading files
30/180/350 days ago: HTTP 401
365-day access: free account/API key required, not tested
```

The official page says a free account covers roughly the last 365 days. That is
consistent with the 401 boundary but **not independently verified** without
creating an account.

### License

https://marketparquet.com/license

- internal research/storage: allowed;
- derived charts/statistics: allowed;
- raw redistribution/public hosting: prohibited.

The raw Parquet files remain local under `_us_audit/mp_sample/`; none are
committed.

### Quality 鈥?three recent files

| Check | Result |
|---|---|
| duplicate `(date,symbol)` | 0 |
| invalid OHLC | 0 |
| non-positive close | 0 |
| fields | date, symbol, asset_type, open, high, low, close, volume |

No TWTR/SIVB/CTLT appear in these recent files; this is expected and does not
test delisted coverage.

## 2. Second-source matrix

| Source | Free range | Delisted coverage | License | Actual test | Conclusion |
|---|---|---|---|---|---|
| MarketParquet | 7 days no account; ~365 days with free account | recent files only; no TWTR/SIVB/CTLT in sample | internal allowed, raw redistribution prohibited | 200/401 dates parsed | **recent-only; not 2016** |
| ADGSTUDIOS | unknown | unknown | unreachable | HTTP 502 | **UNVERIFIED** |
| Stooq | unknown | unknown | unclear | 200 anti-bot HTML | **UNVERIFIED** |
| Nasdaq API | current only | TWTR/SIVB `Symbol not exists` | no redistribution licence | AAPL control 1,804 rows | **REJECTED delisted** |
| Sina/AKShare | technical full history | TWTR pass; SIVB partial | unresolved | TWTR 2,259 / SIVB 8,777 | **no import** |

No second long-history, delisted-inclusive, licence-clear free source was found.

## 3. Batch 5 鈥?25 more names

Selected 2016 gaps with known merger, bankruptcy, successor or reuse risk:

```text
ENDP, FTR, LLTC, LVLT, MJN, MUR, PBI, R, RAI, SPLS,
STJ, SWN, TDC, TGNA, WFM, CSRA, GGP, KORS, NAVI, PDCO,
RRC, SNI, SRCL, CBS, FL
```

### Results

| Category | Count |
|---|---:|
| `STILL_TRADING` | **6** |
| `DELISTED_OR_ACQUIRED` | **17** |
| `TICKER_OR_NAME_CHANGED` | **2** |
| Total | **25** |

### Still trading

`MUR, PBI, R, TDC, NAVI, RRC`

PBI has old 25-NSE filings, but current PBI ticker remains; therefore not
classified as delisted.

### Changed

- KORS -> CPRI (Capri Holdings)
- CBS -> PARA (Paramount), later delisted

### Delisted/acquired

`ENDP, FTR, LLTC, LVLT, MJN, RAI, SPLS, STJ, SWN, TGNA, WFM, CSRA, GGP, PDCO, SNI, SRCL, FL`

Evidence: SEC `25-NSE`/`15-12G` metadata. Exact common-stock last-trade date is
still not independently established.

## 4. Combined status

| Category | Count |
|---|---:|
| `HISTORICAL_MEMBERSHIP_ONLY` | **79** |
| `DELISTED_OR_ACQUIRED` | **59** |
| `STILL_TRADING` | **39** |
| `TICKER_OR_NAME_CHANGED` | **22** |
| `TICKER_REUSE_SUSPECTED` | **2** |
| `IDENTITY_UNRESOLVED` | **1** |
| Total | **202** |

Reviewed: **123 / 202**.

All still:

```text
price_status = NO_SERIES_IN_CURRENT_PANEL
```

## 5. Data conclusion

- Actual MarketParquet download works, but no-account access is only 7 recent
  trading days.
- A free account may extend to ~365 days, but this was not tested and would
  still not cover 2016.
- No free long-history delisted source with clear storage/redistribution terms
  was found.
- Current evidence supports a recent-window pipeline test only, not a
  survivorship-free 2016鈥?024 backtest.

## Artifacts

- source audit: `docs/research/marketparquet_source_audit_2026-10-29.json`
- v6 classification: `docs/research/missing_202_reason_classification_v6_2026-10-29.csv`
- batch 5 SEC: `docs/research/missing_202_batch5_sec_2026-10-29.json`
- local sample only: `_us_audit/mp_sample/`
