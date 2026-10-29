# AKShare / Sina Delisted Price Probe

Date: 2026-10-29 UTC
Research-only interface validation. No canonical write.

## Versions and endpoints

| Item | Value |
|---|---|
| AKShare | **1.20.2** |
| AKShare package licence | MIT |
| Function | `ak.stock_us_daily(symbol=...)` |
| Upstream URL | `https://finance.sina.com.cn/staticdata/us/{ticker}` |
| Auth/token/API key | **none** |
| Account required | **no** |
| Full data persisted | **no** |
| Canonical write | **no** |

The `stock_us_daily` wrapper is a Sina endpoint, not an independent data
source. AKShare itself does not grant rights to Sina data.

## Actual HTTP

Direct GET to the Sina static-data URL returned **HTTP 200** for all three
samples.

Example sizes:

```text
ADCT: 19,694 bytes
TWTR: 24,146 bytes
SIVB: 78,866 bytes
```

The payload is a JavaScript-encoded Sina price blob, decoded by AKShare.

## Three-sample results

| Ticker | Rows | First | Last | OHLCV | Result |
|---|---:|---|---|---|---|
| ADCT | 1,622 | 2020-05-15 | 2026-10-28 | present | **rejected: ticker reuse** |
| TWTR | 2,259 | 2013-11-07 | 2022-10-27 | present, valid | **accepted** |
| SIVB | 8,777 | 1987-10-26 | 2023-03-09 | 3 invalid OHLC rows | **rejected: OHLC invalid** |

### ADCT

- Old ADC Telecommunications left the index in 2007.
- Returned series starts **2020-05-15**, after a ticker reassignment.
- First/last cannot belong to the old company.
- Correctly rejected by `series_starts_after_delisting_ticker_reuse` and
  `series_extends_after_delisting_ticker_reuse`.

### TWTR

- Twitter IPO: 2013-11-07.
- Last trading day before the Musk acquisition: 2022-10-27.
- Last close: **53.70**.
- 2,259 rows; no duplicate dates; no weekend rows; no invalid OHLC.
- Identity and date range are consistent with the pre-acquisition Twitter Inc.

This is the first technical pass in the current free-source search.

### SIVB

- SVB Financial / Silicon Valley Bank series starts 1987-10-26.
- Last row: **2023-03-09**, close **106.04**, before the 2023-03-10 failure.
- 8,777 rows; no duplicate dates; no weekend rows.
- 3 OHLC inconsistencies:

```text
2008-03-19  close 44.56 < low 44.57
2008-07-03  close 45.83 < low 45.84
2009-09-14  close 40.83 > high 40.82
```

These are small but still fail strict OHLC validation. The series is
**not accepted as-is**.

## Eastmoney path

Function:

`ak.stock_us_hist(symbol="105.TWTR")`

Upstream:

`https://63.push2his.eastmoney.com/api/qt/stock/kline/get`

Actual result:

- 3 tickers 脳 3 possible secids (`105`, `106`, `107`) = **9 attempts**.
- All failed before an HTTP status:
  - via environment proxy: `ProxyError: RemoteDisconnected`;
  - direct/no proxy: `WinError 10061 connection refused`.
- No rows returned.
- Status: **UNVERIFIED / network-blocked**, not 鈥渘o delisted data.鈥?
This path is not evidence of coverage and was not retried beyond the nine
documented attempts.

## Licence / storage

Sina/AKShare data terms are **not confirmed** for:

- long-term storage;
- research redistribution;
- public derived reports;
- bulk download.

Therefore:

```text
technical TWTR pass: yes
legal clearance: no
bulk expansion to 202 names: not allowed
import to canonical: no
```

The probe stores only a validation summary, not the full TWTR/SIVB series.

## Coverage effect

```text
new canonical price rows: 0
new verified imported series: 0
technically validated series available: 1 (TWTR, 2,259 rows)
partial but invalid series: 1 (SIVB, 8,777 rows, 3 OHLC errors)
rejected reuse: 1 (ADCT)
2016 constituent coverage: unchanged at 336/484
```

One technical pass is not enough to expand to 202 names, especially with
unclear Sina terms.

## Answers

1. **Does any tested free interface return pre-delisting OHLC?**
   Yes: Sina via `stock_us_daily` returned TWTR through 2022-10-27 and SIVB
   through 2023-03-09.

2. **Does it pass identity/date/OHLC checks?**
   TWTR passes. SIVB fails 3 OHLC rows. ADCT is ticker reuse and is rejected.

3. **Can it be imported?**
   No. Sina terms for storage/redistribution are not confirmed, so only
   interface-level validation is allowed.

4. **Can coverage expand to 202 names?**
   Not under current terms. One verified technical sample is insufficient, and
   the licence gate is unresolved.

5. **Does this solve survivorship bias?**
   No. No data was added to the panel.

## Artifacts

- Sina probe: `docs/research/akshare_sina_probe_2026-10-29.json`
- Eastmoney probe: `docs/research/akshare_eastmoney_us_probe_2026-10-29.json`
- code: `tools/research/akshare_sina_probe.py`
- tests: `tests/test_akshare_sina_probe.py`
