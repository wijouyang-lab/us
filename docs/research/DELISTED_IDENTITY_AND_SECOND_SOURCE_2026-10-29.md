# Delisted Identity, OHLC Anomaly, and Second-Source Audit

Date: 2026-10-29 UTC
Research only. No canonical write.

## 1. Identity records

| Ticker | CIK | Company | Ticker end | Last trade | Event |
|---|---|---|---|---|---|
| TWTR | 0001418091 | TWITTER, INC. | 2022-10-27 | 2022-10-27 | acquisition completed 2022-10-27 (medium) |
| SIVB | 0000719739 | SVB FINANCIAL GROUP | 2023-03-09 | 2023-03-09 | FDIC receivership 2023-03-10 (high) |
| ADCT | 0000061478 | ADC TELECOMMUNICATIONS INC | 2010-12-09 | 2010-12-09 | merger completed 2010-12-09 (high) |

### TWTR

- SEC submissions: https://data.sec.gov/submissions/CIK0001418091.json
- Company: TWITTER, INC.; former name Twitter Inc (2007-11-30 .. 2010-01-08).
- IPO / first Sina date: 2013-11-07.
- Last Sina date: 2022-10-27, close 53.70.
- Form 25 filed: 2022-10-28.
- 8-K filed: 2022-10-31.

Exact merger document HTML returned SEC 403 (bot policy); the event date is
therefore **medium** confidence, while identity and ticker interval are high.

### SIVB

- SEC submissions: https://data.sec.gov/submissions/CIK0000719739.json
- Company: SVB FINANCIAL GROUP; former name SILICON VALLEY BANCSHARES
  (1995-04-13 .. 2005-05-24).
- Last Sina date: 2023-03-09, close 106.04.
- 8-K filed: 2023-03-10.
- Receivership date: 2023-03-10; **high** confidence.

### ADCT 鈥?important correction

- SEC submissions: https://data.sec.gov/submissions/CIK0000061478.json
- Company: ADC TELECOMMUNICATIONS INC.
- S&P **index removal**: 2007 (does not equal company delisting).
- Merger/Form 25: 2010-12-09.
- Form 15-12G: 2010-12-20.
- Sina series starts **2020-05-15**, after the old ticker ended.
- **REJECTED: ticker reuse.** The 2020+ ADCT series is not ADC
  Telecommunications.

No ticker-valid-from date for ADCT is asserted; it remains UNVERIFIED. This
avoids inventing a start date.

## 2. SIVB anomaly register

File: `docs/research/sivb_ohlc_anomalies_2026-10-29.csv`

| Date | Field | Value | Violation | Status |
|---|---|---:|---|---|
| 2008-03-19 | close | 44.56 | below low 44.57 | OPEN |
| 2008-07-03 | close | 45.83 | below low 45.84 | OPEN |
| 2009-09-14 | close | 40.83 | above high 40.82 | OPEN |

Facts:

- Source: Sina via `ak.stock_us_daily`.
- Present under both `adjust=""` and `adjust="qfq"`.
- No independent price source available yet.
- No value was modified.
- State machine: `OPEN` 鈫?`VERIFIED_SOURCE_ERROR` requires source evidence;
  `RESOLVED_WITH_EVIDENCE` additionally requires an independent source.
- All three remain **OPEN**.

## 3. Second free price source

### Nasdaq public quote API

URL pattern:

`https://api.nasdaq.com/api/quote/{ticker}/historical`

Results:

| Ticker | HTTP | Result |
|---|---|---:|
| AAPL (control) | 200 | 204,568 bytes, 1,804 rows |
| TWTR | 200 | 142 bytes, `rCode 400 Symbol not exists` |
| SIVB | 200 | 142 bytes, `rCode 400 Symbol not exists` |

The API works for a current symbol but does not expose these delisted symbols.
Status: **REJECTED for delisted coverage**.

### Stooq daily CSV

URL:

`https://stooq.com/q/d/l/?s={ticker}.us&i=d`

Result:

- HTTP 200, 796 bytes;
- HTML `noindex,nofollow` / noscript page, not CSV;
- no OHLC returned.

Status: **UNVERIFIED / anti-bot**, not 鈥渘o history.鈥?
### Existing routes

- Sina: technically PARTIAL, but terms unresolved and no independent source.
- Eastmoney: previously network-blocked; not retried.
- Futu: absent in AKShare 1.20.2; not retried.
- Yahoo/Wayback: already failed; not retried.

**Independent second source found: no.**

## 4. Quality gate

`tools/research/delisted_security_gate.py` blocks:

- missing CIK/ticker/company/ticker end;
- last trade after ticker end;
- series starts after ticker end (reuse);
- series extends after ticker end;
- duplicate dates;
- weekend rows;
- missing/non-positive OHLC;
- internal OHLC inconsistency;
- terms not approved;
- no independent cross-check;
- canonical write.

`tools/research/ohlc_anomaly_registry.py` blocks closing an anomaly without
evidence; `RESOLVED_WITH_EVIDENCE` requires an independent source.

## 5. Data impact

```text
TWTR valid technical series available: 2,259 rows
SIVB partial series available: 8,777 rows, 3 OPEN anomalies
ADCT rejected: 1,622 rows
imported to canonical: 0
2016 coverage: unchanged 336/484
```

## 6. Answers

1. **Identity:** TWTR/SIVB/ADCT have SEC CIKs and names. ADCT is the key
   correction: 2007 was index removal; company/ticker ended 2010.
2. **Anomaly:** three SIVB source-level OHLC errors are registered OPEN; no
   repair.
3. **Second source:** Nasdaq does not serve the delisted symbols; Stooq is
   anti-bot-blocked. No independent free OHLC source found.
4. **Ready for batch 202?** No. Terms, independent source, and anomaly
   resolution are still missing.

## 7. Artifacts

- identity JSON: `docs/research/delisted_identity_records_2026-10-29.json`
- identity CSV: `docs/research/delisted_identity_records_2026-10-29.csv`
- anomaly CSV: `docs/research/sivb_ohlc_anomalies_2026-10-29.csv`
- anomaly JSON: `docs/research/sivb_ohlc_anomalies_2026-10-29.json`
- second-source probe: `docs/research/second_price_source_probe_2026-10-29.json`
- gate: `tools/research/delisted_security_gate.py`
- anomaly state machine: `tools/research/ohlc_anomaly_registry.py`
- tests: `tests/test_delisted_security_gate.py`, `tests/test_ohlc_anomaly_registry.py`
