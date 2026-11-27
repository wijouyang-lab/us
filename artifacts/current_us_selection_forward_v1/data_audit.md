# Current US Selection — Data Audit

Run date: 2026-11-27. Signal market date: **2026-11-25** (latest completed U.S. session; 11/26 holiday, 11/27 not closed at retrieval).

## Price data actually fetched

| Item | Result |
|---|---|
| Source | yfinance / Yahoo Finance, free, no subscription |
| Request | 5,501 cached tickers requested for 14 months |
| Rows | 1,534,850 |
| Unique symbols with data | **5,462** |
| Latest date | **2026-11-25** |
| History | 2025-09-26 → 2026-11-25 (14 months) |
| Missing/failed | 1 explicit `WSO.B` no-data; 39 symbols absent from result |
| Fields | open/high/low/close/adj close/volume |
| Adjustments | adjusted close; raw close for $5 filter |
| Delisted | **NOT verified** — static current universe; not usable for historical survivorship-free tests |
| 2026 history | Yes, current daily; no 2024 data substituted |

The old 987-name `v2_price` ends 2024-12 and was **not used for current signals**.

## Fundamental data

| Item | Result |
|---|---|
| Source | `unified_selection_v1_1.csv` / SEC Company Facts |
| Universe rows | 5,600 |
| Rows with `filed` date | 5,297 |
| Rows with `quality_pct` | 2,312 |
| Rows scored (price + fundamentals) | **5,072** |
| Public-date rule | `filed <= 2026-11-25`; used for quality fields |
| PIT historical ability | **PARTIAL for current only; NOT a historical PIT panel** |
| Revision/future leakage | current SEC facts may include later revisions; not fully PIT |
| Quality fields | ROE/ROA/CFO/assets/leverage via existing quality_pct; raw ROE/ROA/FCF available |
| Insufficient | missing quality -> not eligible for main watch, not zero-filled |

## Counts

| Metric | Count |
|---|---:|
| Price symbols | 5,462 |
| Scored universe | 5,072 |
| Main-watch eligible | 286 |
| Main watch (max 10) | 10 |
| Secondary | 30 |
| Quality available | 2,275 (scored) |
| Quality not public/missing | 2,797 |
| SPY latest | 2026-11-25; below 200d |

## Maximum gap

- No delisted-security history / no broad historical PIT universe.
- Only ~14 months of current daily data; cannot do multi-year current-universe validation.
- Quality coverage is only ~41% of the 5,600 universe.
- yfinance is free but rate-limited/unstable; one 429 was observed during ETF fetch.
- Corporate actions adjusted via vendor adjusted close; no independent verification.

## Data grade

- **A** current cross-sectional watchlist: usable for observation, with source/date/hash.
- **B** current price trend + current quality: usable as a screen, not as PIT-validated alpha.
- **C** historical strategy validation with this universe: **not usable** due survivorship/stale fundamentals.
