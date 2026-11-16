# P10.5.0: 20-Dollar One-Month Historical Data Value Gate

Date: 2026-11-16
Branch: `research/p10-data-provider-evaluation`
Candidate: **EODHD Historian — $19.99/month**
Decision: **NO_BUY**

Status:

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_SUBSCRIPTION: 1 MONTH
MAX_BUDGET_USD: 20
POST_CANCELLATION_RAW_DATA_RETENTION_REQUIRED: YES
```

---

## 1. Hard constraints

The purchase may only proceed if all are true:

1. no VPS;
2. no six-month/annual subscription;
3. one subscription ≤ $20;
4. at most one month;
5. downloaded raw data remains usable after cancellation;
6. clear, measurable gain over existing free data;
7. no continuing paid API needed to use downloaded history.

EODHD Historian meets the **price** and **retention** constraints. It does not
meet the **demonstrated incremental coverage** requirement.

---

## 2. Free-data gap audit

Method:

- membership from `sp500_daily.csv`;
- prices from `finsaber_prices_raw.csv`;
- trading days from `spy.csv`;
- interval `2007-05-30..2024-12-31`;
- `member-day` means an expected member ticker/date with a positive close.

Files:

- `data/research/eodhd_price_gap_inventory.csv` (887 tickers)
- `data/research/eodhd_incremental_coverage_estimate.csv`
- `data/research/eodhd_download_cost_estimate.json`

### Headline

```text
expected tickers in interval:      887
tickers with any price row:        807
missing tickers:                    80
member-day expected:         2,220,522
member-day observed:         2,113,080
member-day coverage:           95.16%
ticker coverage:               90.98%
missing member-days:           107,442
missing price days (within
first/last observed date):      21,819
missing removed/delisted tickers: 60 of 80
missing current/latest tickers:   20 of 80
```

Of the 80 missing:

```text
60  REMOVED_OR_DELISTED
20  CURRENT_OR_LATEST
```

`BRK.B` and `BF.B` are missing under class-symbol notation, indicating a
symbol-mapping issue as well as a coverage issue.

### Important definition conflict

P9.1's own `data_audit.json` records:

```text
member-day: 981,362 / 1,095,490 = 89.58%
ticker:     1,062 / 1,160     = 91.55%
```

The independent rebuild above gives `95.16%` member-day and `90.98%` ticker.
The two denominators and validity rules differ. This is recorded as:

```text
DATA_DEFINITION_CONFLICT: YES
P9_GATE_RESULT_FROM_REBUILD: NOT ACCEPTED AS PASS
```

The 95.16% is **not** claimed as a P9 PASS. The accepted P9 gate remains:

```text
member-day >= 95%
ticker >= 98%
```

### Four separate gaps

| Category | Measurement |
|---|---|
| A. Historical price gaps | 21,819 missing trading days within first/last observed dates |
| B. Delisted price gaps | 60 removed/delisted tickers with zero observed member-days; 83,415 missing member-days |
| C. Historical pool / membership gaps | 80 tickers missing; 107,442 missing member-days; no independent membership source beyond `sp500_daily.csv` |
| D. Corporate actions gaps | no independent split/dividend event file; `NOT_AVAILABLE_SEPARATELY`; adjusted close only |

Do not combine these into one "coverage" number.

---

## 3. EODHD incremental value

### Officially claimed

EODHD Historian official plan includes:

- EOD Historical All-World;
- delisted tickers;
- splits and dividends;
- Bulk EOD API.

Official:

- https://eodhd.com/pricing/
- https://eodhd.com/help/plans
- https://eodhd.com/financial-apis/api-for-historical-data-and-volumes
- https://eodhd.com/financial-apis/bulk-api-eod-splits-dividends
- https://eodhd.com/financial-apis/delisted-stock-companies-data-2

### Free demo actually verified

Demo API for AAPL/MSFT/TSLA:

| Ticker | Rows | Range | Repeat SHA256 |
|---|---:|---|---|
| AAPL | 9,283 | 1990-01-02..2026-11-10 | MATCH |
| MSFT | 9,283 | 1990-01-02..2026-11-10 | MATCH |
| TSLA | 4,118 | 2010-06-29..2026-11-10 | MATCH |

AAPL splits: 5 records, 1987-06-16..2020-08-31.

### Free demo not verified

Delisted candidates:

```text
TWTR   403
LEHMQ  403
ENRNQ  403
WCOMQ  403
BSC    403
```

They remain `NOT_RUN`. No paid endpoint was used.

### Paid-only uncertainty

Not verified without payment:

- actual delisted ticker coverage;
- actual per-ticker row completeness;
- whether the 80 missing tickers are recovered;
- symbol/class mapping for `BRK.B`/`BF.B`;
- historical S&P 500 membership (not included in Historian; add-on excluded);
- price history versioning/vintage.

Status:

```text
EODHD_DEMO_LARGE_CAP: PARTIAL (real sample)
EODHD_DEMO_DELISTED: NOT_RUN (403)
EODHD_PAID_COVERAGE: UNVERIFIED
PRICE_VINTAGE: NOT AVAILABLE
HISTORICAL_SP500_PIT: NOT INCLUDED
```

---

## 4. One-month download feasibility

Assumption: one EOD call per ticker for full history; one splits; one dividends;
one delisted list.

```text
tickers:                887
EOD calls:              887
splits calls:           887
dividends calls:        887
delisted-list calls:      1
total calls:          2,662
```

Official limits:

- 100,000 API calls/day;
- 1,000 requests/minute;
- Bulk whole-exchange request costs 100 calls.

At 2,662 calls, download is feasible in one day and well within one month.
Estimated files:

```text
OHLCV CSV:          887
splits CSV:         887
dividends CSV:      887
manifest:             1
total:            2,662
```

Storage estimate:

```text
raw price CSV: 600-1,200 MB
metadata:       10-50 MB
backup copy:   same again
```

Not measured; estimate only.

No VPS is required for the API download; a normal personal Windows computer and
local disk are sufficient.

---

## 5. Licence and retention

EODHD help:

- https://eodhd.com/help/personal-use
- https://eodhd.com/help/storage
- https://eodhd.com/help/ai-tools
- https://eodhd.com/financial-apis/terms-conditions

Constraints:

- personal, non-professional use only;
- private VPS/cloud allowed only for the licensee;
- no sharing/public display/redistribution;
- downloaded data may be retained after cancellation;
- cancellation stops updates;
- no raw data in public GitHub/Pages/artifacts;
- no public Dashboard;
- price data is current-version only, not historical vintage;
- corrected bars overwrite old values;
- adjusted close is recalculated.

For this project:

```text
LOCAL_WINDOWS_STORAGE: ALLOWED FOR PERSONAL USE
POST_CANCEL_RETENTION: ALLOWED
PUBLIC_GITHUB_RAW_DATA: NOT ALLOWED
PUBLIC_DERIVED_OUTPUTS: ONLY NON-RECONSTRUCTABLE AGGREGATES
VPS_REQUIRED: NO
```

---

## 6. Incremental value scenarios

From `eodhd_incremental_coverage_estimate.csv`:

| Scenario | Ticker coverage | Member-day | Claim |
|---|---:|---:|---|
| Free independent audit | 90.98% | 95.16% | MEASURED |
| P9 recorded | 91.55% | 89.58% | PROJECT RECORD |
| EODHD recovers half of 80 gaps | 95.49% | UNKNOWN | ESTIMATE ONLY |
| EODHD recovers all 80 gaps | 100% | 100% (algebraic upper bound) | NOT VERIFIED |
| Required P9 gate | 98% | 95% | GATE |

The upper bound is arithmetic, not evidence. No paid EODHD data was downloaded.

### Does it fix 98% ticker?

Potentially, only if it recovers at least:

```text
887 * 98% = 870 tickers
870 - 807 = 63 of the 80 missing
```

That is 79% of missing tickers. EODHD has not been shown to recover even one
delisted sample.

### Does it fix 95% member-day?

The independent rebuild is already 95.16%, but P9 records 89.58%. The conflict is
unresolved. EODHD price data alone cannot prove the P9 member-day denominator.

### Does it fix PIT universe?

No. EODHD Historian does not include historical S&P 500 membership. The $29.99
Historical Constituents add-on is excluded by this budget. So PIT membership
remains dependent on the existing `sp500_daily.csv`/other source.

### Does it provide price vintage?

No. EODHD provides the current version; corrections overwrite old records.

---

## 7. BUY gate

| Gate | Status |
|---|---|
| Price ≤ $20 | PASS — $19.99 |
| ≤ one month | PASS |
| No VPS | PASS |
| Retain raw data after cancel | PASS — official |
| One-month download feasible | PASS — 2,662 calls |
| Clear, quantified new historical coverage | **FAIL — unverified** |
| Fix/quantify 95% member-day honestly | **FAIL — baseline conflict** |
| PIT membership solved | **FAIL — not included** |

Decision:

```text
NO_BUY
```

Reason: the only verified EODHD evidence is three current mega-cap demo series.
The delisted demos are 403. The 80 missing tickers, real delisted recovery and
98% ticker improvement are unverified. A $19.99 experiment is cheap, but the
project's own rule requires a clear, quantified gain before purchase.

---

## 8. What would change the decision

A paid one-month purchase would be reconsidered if a legitimate pre-purchase
sample (without violating terms) showed:

1. at least 63 of the 80 missing tickers recover;
2. at least 95% member-day under the accepted denominator;
3. real delisted samples have complete histories;
4. `BRK.B`/`BF.B` and rename mappings resolve;
5. splits/dividends are downloadable and retainable;
6. one-month extraction is repeatable.

Until then:

```text
NO_PURCHASE: YES
```

---

## 9. Final status

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_SUBSCRIPTION: 1 MONTH
MAX_BUDGET_USD: 20
POST_CANCELLATION_RAW_DATA_RETENTION_REQUIRED: YES
EODHD_PRICE_USD_PER_MONTH: 19.99
EODHD_DEMO_LARGE_CAP: PARTIAL
EODHD_DEMO_DELISTED: NOT_RUN
EODHD_PAID_COVERAGE: UNVERIFIED
DATA_DEFINITION_CONFLICT: YES
P9_MEMBER_DAY_GATE: 95%
P9_TICKER_GATE: 98%
P9_DATA_REPRODUCIBILITY: BLOCKED
P9_RESULTS: ALL 8 NO-GO
```

No EODHD account was created, no payment details entered, no subscription
started, no paid data downloaded.
