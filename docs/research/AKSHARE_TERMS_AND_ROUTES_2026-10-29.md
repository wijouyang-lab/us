# AKShare Terms and Free-Route Audit

Date: 2026-10-29 UTC
Research-only. No bulk download, no canonical write.

## 1. Sina terms

Source:

https://finance.sina.com.cn/roll/2021-05-12/doc-ikmxzfmm2033220.shtml

- Title: 鏂版氮璐㈢粡鐢ㄦ埛鍗忚
- Version date: 2020-09-23
- Fetched: 2026-10-29
- HTTP: 200

Relevant clauses:

| Clause | Text / effect | Certainty |
|---|---|---|
| 2.5 | Without prior written authorization, no adaptation, copying, dissemination, vertical search, mirroring or trading of the service | **high** |
| 2.7 | Grants a personal, non-transferable, non-exclusive and **non-commercial** right to use the service | **high** |
| 6.1 | Without written permission, no copying/reading/using content for commercial purposes, no re-display outside the source page | **high** |
| 10.1 | Without permission, no robot/spider monitoring, copying, dissemination, display, mirroring, upload or download | **high** |
| 12 | No warranty of accuracy/completeness/fitness; use at own risk | **high** |

### What is confirmed

- Personal, non-commercial use is the only express permission.
- Copying, dissemination and bulk automated retrieval require **prior written
  authorization**.
- Raw price data cannot be published or redistributed on the current terms.

### What is NOT confirmed

| Question | Status |
|---|---|
| Long-term storage of raw historical prices | **UNRESOLVED** |
| Public derived research reports/charts | **UNRESOLVED** |
| Whether the undocumented `/staticdata/us/` endpoint is covered | **UNRESOLVED** |
| Whether a small validation download is permitted | **UNRESOLVED** |

Do not treat AKShare's MIT licence as a Sina data licence. No authorization
request was sent.

Official contact listed in the agreement: `finance.app@staff.sina.com.cn`
(not contacted).

## 2. Route status

| Route | AKShare function | Upstream | Auth | Status |
|---|---|---|---|---|
| Sina | `stock_us_daily` | `https://finance.sina.com.cn/staticdata/us/{ticker}` | none | **PARTIAL** |
| Eastmoney | `stock_us_hist` | `https://63.push2his.eastmoney.com/api/qt/stock/kline/get` | none | **UNVERIFIED** |
| Futu | `stock_us_hist_fu` | none available | n/a | **UNVERIFIED** |

### Sina sample status

| Sample | Status | Rows | Range | Reason |
|---|---|---:|---|---|
| ADCT | **REJECTED** | 1,622 | 2020-05-15 .. 2026-10-28 | ticker reuse; not old ADC Telecom |
| TWTR | **PASS** | 2,259 | 2013-11-07 .. 2022-10-27 | identity/date/OHLC consistent |
| SIVB | **PARTIAL** | 8,777 | 1987-10-26 .. 2023-03-09 | 3 invalid OHLC rows |

TWTR last close: 53.70 on 2022-10-27.

SIVB last close: 106.04 on 2023-03-09.

### SIVB anomaly investigation

The same three rows appear under both `adjust=""` and `adjust="qfq"`:

```text
2008-03-19  close 44.56 < low 44.57
2008-07-03  close 45.83 < low 45.84
2009-09-14  close 40.83 > high 40.82
```

So this is a source-level value inconsistency, not an adjustment artifact.
The values were **not modified**; SIVB remains PARTIAL.

### Eastmoney

Nine attempts (3 tickers 脳 3 secids) all failed before any HTTP status:

- environment proxy: `ProxyError: RemoteDisconnected`;
- direct no proxy: `WinError 10061 connection refused`.

This is **network-blocked / UNVERIFIED**, not evidence of no history.

### Futu

`ak.stock_us_hist_fu` is **not present in AKShare 1.20.2**. No public function
was available to test; status is UNVERIFIED, not "no data".

## 3. Data handling

```text
raw series persisted: 0
canonical rows added: 0
bulk 202-name download: no
ticker-reuse rows imported: 0
invalid OHLC rows modified: 0
```

Only validation summaries were stored.

## 4. Answers

1. **What do Sina terms confirm?**
   Personal non-commercial use; copying/dissemination/bulk retrieval require
   prior written permission. Long-term storage and public derived reports are
   not granted and remain unresolved.

2. **How usable are the three routes?**
   Sina is technically PARTIAL: TWTR passes, SIVB is partial, ADCT is reuse.
   Eastmoney is network-UNVERIFIED. Futu has no available function in this
   AKShare version.

3. **Which samples pass?**
   TWTR passes identity/date/OHLC. SIVB covers pre-failure dates but fails 3
   OHLC rows. ADCT fails identity/reuse.

4. **Which sources to continue/pause?**
   Sina can be used only for minimal technical validation until terms are
   resolved. Eastmoney and Futu are paused as unverified routes.

5. **What is missing before bulk 202-name recovery?**
   - written clarification of storage/redistribution rights;
   - a second independent free source for cross-checking;
   - a rule for source-level OHLC anomalies;
   - identity join by CIK/security, not ticker alone.

## 5. Artifacts

- route matrix: `docs/research/akshare_route_matrix_2026-10-29.json`
- Sina probe: `docs/research/akshare_sina_probe_2026-10-29.json`
- Eastmoney probe: `docs/research/akshare_eastmoney_us_probe_2026-10-29.json`
- code: `tools/research/akshare_sina_probe.py`
- tests: `tests/test_akshare_route_matrix.py`, `tests/test_akshare_sina_probe.py`
