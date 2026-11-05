# Free Market Data Audit — P3.0

Date: 2026-11-04
Scope: AKShare, Yahoo/yfinance, Finnhub Key A/B.
Production code untouched.

## 1. Executive result

No source is approved for the formal data layer.

| Source | Technical | License | Overall |
|---|---|---|---|
| Yahoo/yfinance | TECHNICAL_PASS | LICENSE_UNVERIFIED | DATA_BLOCKED |
| AKShare/Sina | TECHNICAL_PASS | LICENSE_UNVERIFIED | DATA_BLOCKED |
| Finnhub Key A | NOT_CONFIGURED | LICENSE_UNVERIFIED | DATA_BLOCKED |
| Finnhub Key B | NOT_CONFIGURED | LICENSE_UNVERIFIED | DATA_BLOCKED |

Technical success is not authorization.

## 2. Finnhub keys

Environment checked by name only:

```text
FINNHUB_API_KEY_A  absent
FINNHUB_API_KEY_B  absent
FINNHUB_API_KEY    absent
```

No Finnhub request was made. Therefore:

- neither key validity nor account identity is established;
- the two keys cannot be claimed to belong to the same account;
- free-plan quotas, quote permission, candle permission and earliest history
  are all **UNVERIFIED**;
- no key rotation or quota-stacking test was performed;
- no paid endpoint or trial was used;
- no key value was written to JSON/CSV/log/report.

Result: `NOT_CONFIGURED`, not PASS.

## 3. Yahoo/yfinance

### Coverage

31 symbols (28 companies + QQQ/BIL/SPY), 10-year request:

| Period | Symbols with data | Minimum rows | Median rows |
|---|---:|---:|---:|
| 1y | 31/31 | 252 | 252 |
| 2y | 31/31 | 501 | 501 |
| 5y | 31/31 | 1250 | 1254 |
| 10y | 31/31 | 1250 | 2511 |

- 30/31 have ~2,511 rows (full 10 years).
- RIVN has 1,250 rows because its IPO is inside the window; not padded.
- Total rows: 76,087.
- Duplicate dates: 0.
- Bad OHLC rows: 0.
- Zero-volume rows: 2.
- >35% close jumps: 1 (MRNA), to be checked against a corporate action before use.

`history()` includes Open/High/Low/Close/Adj Close/Volume and actions.
`Dividends`, `Splits`, `Actions` worked on the tested names:

```text
AAPL div 92 split 5 actions 97
MSFT div 91 split 9 actions 100
QQQ  div 90 split 1 actions 91
BIL  div 127 split 1 actions 128
SPY  div 136 split 0 actions 136
JPM  div 172 split 4 actions 176
XOM  div 258 split 5 actions 263
```

### Quality

OHLC consistency passed for the 31 symbols; no non-positive rows in this batch.
The one >35% jump is retained as an anomaly, not silently repaired.

### License

Yahoo public terms restrict redistribution and commercial display. No written
permission was obtained. `LICENSE_UNVERIFIED`.

## 4. AKShare / Sina

### Provider

`ak.stock_us_daily()` is not a generic AKShare feed. Source inspection shows:

```text
https://finance.sina.com.cn/staticdata/us/{symbol}
```

and a Sina forward-adjustment endpoint. Provider: **Sina Finance**.

### Coverage

31/31 symbols returned data.

| Period | Symbols with data | Minimum rows | Median rows |
|---|---:|---:|---:|
| 1y | 31/31 | 252 | 252 |
| 2y | 31/31 | 501 | 501 |
| 5y | 31/31 | 1250 | 1254 |
| 10y | 31/31 | 1250 | 2511 |

- Total rows: 225,710; history reaches 1980 for several names.
- 30/31 have ~2,511 rows in the 10-year window; RIVN 1,250.
- Duplicate dates: 0.
- **Bad OHLC rows: 75**.
- Zero-volume rows: 3.
- **>35% close jumps: 84**, mostly split artifacts because `adjust=""`
  returns unadjusted prices while Yahoo historical Close is split-adjusted.

Anomaly examples:

```text
BRK.B  49 bad OHLC rows
CAT     8 bad rows, 3 jumps
MCD     5 bad rows, 5 jumps
HD      3 bad rows, 1 jump
AAPL    7 jumps (split history)
GOOGL   2 jumps (20:1 split)
NVDA    7 jumps (splits)
```

### Corporate actions

No dedicated AKShare US dividend/split/actions endpoint was found in this
environment. The daily interface exposes OHLCV only. Unadjusted split jumps are
present, so raw AKShare prices cannot be used for multi-year return calculation
without a separately verified action table.

### License

AKShare is open source, but the upstream Sina data terms were not verified.
`LICENSE_UNVERIFIED`; library licence is not a data licence.

## 5. Cross-validation

Same ticker, same date, raw Close (not adjusted close):

- 31 pairs compared.
- median common days per ticker: 2,512.
- most recent-era prices agree to near machine precision for many names.
- split-era differences are enormous:

```text
AAPL max abs diff 379.57  (4:1 split)
GOOGL max abs diff 2846.93 (20:1 split)
AMZN max abs diff 3544.84 (20:1 split)
NVDA max abs diff 1101.96 (splits)
```

This is **not** a provider error by itself; it proves the two Close fields do not
share the same split-adjustment convention. `adjusted_close` is therefore not
cross-comparable across providers. A 0.01 threshold produces 352 flagged days
on average, dominated by split histories; it cannot be used without aligning
actions first.

## 6. Quality findings

| Check | Yahoo | AKShare |
|---|---:|---:|
| Symbols | 31 | 31 |
| Rows | 76,087 | 225,710 |
| Duplicates | 0 | 0 |
| Bad OHLC rows | 0 | 75 |
| Zero volume | 2 | 3 |
| >35% jumps | 1 | 84 |
| Full 10y (30/31) | yes | yes |
| RIVN short history | 1,250 | 1,250 |

AKShare's 75 bad rows and 84 jumps make it `TECHNICAL_PASS` only with anomaly
handling; it is not clean enough to be a formal multi-year price source as-is.

## 7. Permissions / usage

All three sources are `LICENSE_UNVERIFIED` for every target use:

| Use | Status |
|---|---|
| Private research | LICENSE_UNVERIFIED |
| Local historical backtest | LICENSE_UNVERIFIED |
| Long-term local storage | LICENSE_UNVERIFIED |
| Derived factors | LICENSE_UNVERIFIED |
| Save data in GitHub repo | LICENSE_UNVERIFIED |
| Display on GitHub Pages | LICENSE_UNVERIFIED |
| Public/shared results | LICENSE_UNVERIFIED |

No source qualifies as `PASS`.

## 8. What can be used now

- **Nothing for the formal data layer.**
- Yahoo and AKShare may be used only for exploratory comparisons after a written
  licence determination and after split/action reconciliation.
- Finnhub cannot be used at all until keys, account identity, plan, quotas and
  terms are verified.
- No market data from this audit is added to production or the paper account.
- Trend/Hedge and price-based Value metrics remain `DATA_BLOCKED`.

## 9. Blockers

1. Finnhub Key A/B are absent; account identity and free-plan permissions unknown.
2. Yahoo license does not permit assumed redistribution/public display.
3. AKShare/Sina upstream terms are not verified.
4. AKShare has 75 bad OHLC rows and 84 split jumps.
5. Yahoo raw Close and AKShare raw Close use different split conventions.
6. No verified action table to reconcile them.
7. No written permission for GitHub data storage or Pages display.

## 10. Recommendation

Do not buy data and do not lower standards. The next acceptable step is a
licence-first decision:

- obtain written terms/permission for one source, or
- use a user-supplied local price file with explicit rights, or
- keep price-dependent features `DATA_BLOCKED`.

Only after that should a canonical `symbol/date/OHLCV/actions` layer be built.
