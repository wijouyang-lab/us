# Free Data Source Test and Missing Batch 4

Date: 2026-10-29 UTC
Research only. No canonical write.

## 1. MarketParquet

Official guide:

https://marketparquet.com/guides/free-historical-stock-data

License:

https://marketparquet.com/license

### Actual download

No-signup recent file:

`https://marketparquet.com/api/data/download/stock_daily/2026-10-28.parquet`

| Item | Value |
|---|---|
| HTTP | 200 |
| bytes | 232,449 |
| SHA-256 | `676580077ac560be844b6b2a95a0c172b9a84da65596229f247df7c805bf904c` |
| rows | 6,503 |
| symbols | 6,503 |
| date | 2026-10-28 |
| fields | `date, symbol, asset_type, open, high, low, close, volume` |
| AAPL | open 346.92, high 347.18, low 343.52, close 343.83 |
| MSFT | open 531.82, high 535.00, low 526.135, close 531.01 |
| duplicate `(date,symbol)` | 0 |
| invalid OHLC | 0 |
| non-positive close | 0 |

### Delisted sample check

The one-day file **does not contain** TWTR, SIVB or CTLT. This is expected:
those securities had already stopped trading. The no-signup file cannot test
delisted coverage.

### Free range

- No account: newest **7 daily files**.
- Free account/API key: roughly **last 365 days**.
- Full history: paid archive.

The free tier is **recent-only**, not 2016 history.

### License

Confirmed from MarketParquet license page:

- personal/commercial internal research allowed;
- storage on private machines/servers allowed;
- derived charts/statistics/research allowed;
- **raw file redistribution/public hosting prohibited**;
- license is per account, perpetual for delivered files.

Therefore the sample is kept in a local research directory only; no Parquet is
committed to the public repository.

Status: **RECENT_ONLY / PARTIAL**, not usable for 2016鈥?024 delisted history.

## 2. ADGSTUDIOS Stocks API

https://stocks.adgstudios.co.za/

Actual response:

```text
HTTP 502 Bad gateway (Cloudflare)
```

- No API response.
- No terms page reachable.
- No data downloaded.
- Status: **UNVERIFIED_NETWORK_502**, not 鈥渘o historical data鈥?

No retry beyond the recorded request.

## 3. Other public routes

| Source | Actual result | Status |
|---|---|---|
| Stooq | HTTP 200 HTML anti-bot page, not CSV | UNVERIFIED |
| Nasdaq quote API | AAPL control 1,804 rows; TWTR/SIVB `Symbol not exists` | REJECTED for delisted |
| Sina/AKShare | TWTR/SIVB technically available; terms unresolved | PARTIAL / no import |

No new source provides verified 2016 history plus delisted names plus clear
license.

## 4. Missing Batch 4

25 names selected from 2016 gaps with known mergers, spin-offs, ticker changes
or acquisition evidence:

```text
COL, ESRX, EVHC, TWX, CELG, RHT, SYMC, MYL, RTN, UTX,
XEC, COG, CXO, FLIR, KSU, TIF, XLNX, WLTW, CERN, CTXS,
PBCT, DISCA, FB, PKI, ETFC
```

### Results

| Category | Count |
|---|---:|
| `DELISTED_OR_ACQUIRED` | **19** |
| `TICKER_OR_NAME_CHANGED` | **6** |
| `STILL_TRADING` | 0 |

### Changed/rebranded

| Old | New |
|---|---|
| SYMC | GEN (Gen Digital) |
| UTX | RTX |
| WLTW | WTW |
| FB | META |
| PKI | RVTY |
| DISCA | WBD (later delisted) |

### Delisted/acquired

`COL, ESRX, EVHC, TWX, CELG, RHT, MYL, RTN, XEC, COG, CXO, FLIR, KSU, TIF, XLNX, CERN, CTXS, PBCT, ETFC`

Evidence is SEC `25-NSE`/`15-12G` metadata; it does not independently prove the
last trade price.

### Evidence audit of Batch 3 flags

- **CTRA**: empty SEC tickers plus 25-NSE/15-12G in 2026; `DELISTED_OR_ACQUIRED`
  at **medium** confidence until a company announcement is attached.
- **CDAY**: ticker changed and later 2026 acquisition forms; classify
  `TICKER_OR_NAME_CHANGED`, not a simple delisting.
- **FI**: SEC ticker field says `FISV`, while the reviewed label is `FI`;
  mapping is not settled. Keep `TICKER_OR_NAME_CHANGED` with an open question,
  not a delisted claim.

`25-NSE`/`15-12G` are not used alone to infer common-stock last-trade dates.

## 5. Combined status

| Category | Count |
|---|---:|
| `HISTORICAL_MEMBERSHIP_ONLY` | **104** |
| `DELISTED_OR_ACQUIRED` | **42** |
| `STILL_TRADING` | **33** |
| `TICKER_OR_NAME_CHANGED` | **20** |
| `TICKER_REUSE_SUSPECTED` | **2** |
| `IDENTITY_UNRESOLVED` | **1** |
| Total | **202** |

Reviewed: **98 / 202**.

All price status remains:

```text
NO_SERIES_IN_CURRENT_PANEL
```

## 6. Conclusion on data

- No tested free source provides **long-history delisted OHLC** with clear
  internal-storage/redistribution terms.
- MarketParquet is viable for **recent** validation, not 2016 history, and its
  raw files cannot be published.
- ADGSTUDIOS is unreachable.
- Sina remains technically usable but terms-unresolved.

No canonical price data was changed.

## 7. Artifacts

- source audit: `docs/research/marketparquet_source_audit_2026-10-29.json`
- v5 classification: `docs/research/missing_202_reason_classification_v5_2026-10-29.csv`
- batch 4 SEC: `docs/research/missing_202_batch4_sec_2026-10-29.json`
- local sample (not committed): `mp_sample/stock_daily_2026-10-28.parquet`
