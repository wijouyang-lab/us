# P12.3: SEC PIT Data Expansion, Raw-Filing Validation, and Event Window Correction

Date: 2026-11-17
Branch: `research/p12-event-fundamental-feasibility`
Status: **READY_RESTRICTED for the 140-issuer pilot; DATA_BLOCKED for market-wide use**

---

## 1. Scope

This is data construction and validation, not factor or strategy research.

Expanded sample: 140 issuers.

```text
US_CURRENT:            30
US_CURRENT_EXPANSION: 100
US_NON_SURVIVING:       5
FOREIGN_ADR:            5
```

The P12.2 40-issuer list is retained. Expansion rule was fixed before financial
results: top 100 current US-GAAP common stocks by 2026-11-05 market cap,
excluding P12.2 issuers.

CIK is primary. Ticker is only a mapping label. Foreign ADRs remain separate.

File: `data/research/p12_3_expanded_universe.csv`

---

## 2. Expanded panel

```text
issuers in fact panel: 139 / 140
fact rows:            222,804
events:                13,668
  US 8-K:              11,612
  foreign 6-K:          2,056
```

One issuer has no usable extracted facts; this is recorded, not replaced.

Ten required metrics remain:

```text
Revenue, GrossProfit, OperatingIncome, NetIncome, TotalAssets,
TotalDebt, Cash, OperatingCashFlow, Capex, SharesOutstanding
```

Annual coverage:

```text
issuer-years: 2,010
range: 2009-2024
filings counted: 102,205
```

Quarterly coverage:

```text
issuer-periods: 7,465
```

Files:

- `p12_3_accession_fact_panel.csv`
- `p12_3_annual_coverage.csv`
- `p12_3_quarterly_coverage.csv`

---

## 3. Raw-filing validation

Ten issuers were checked against their raw XBRL instance:

```text
AAPL, MSFT, JNJ, WMT, CAT, XOM, MON, RTN, BP, SAP
```

Coverage: 6 current, 2 non-surviving, 2 foreign; multiple industries and fiscal
year ends.

```text
filings parsed: 10
metric checks:  60
MATCH:          59
PANEL_MISSING:   1
CONFLICT:        0
```

The one missing check is BP `SharesOutstanding` in the panel; it was not silently
filled. No unexplained conflict remains after selecting annual-duration facts
rather than quarterly facts from the same 10-K.

Files:

- `p12_3_filing_validation.csv`
- `p12_3_fact_reconciliation.csv`

---

## 4. PIT version history

```text
version groups: 67,159
value-changed groups: 7,668
```

Every group with more than one accession retains:

```text
accessions, forms, filing dates, acceptance datetimes, values
```

`p12_3_version_history.csv`

PIT test: `as_of(panel, cik, metric, date)` filters on
`acceptance_datetime`/filing date and returns only versions known by that date.
The test confirms a later accession is not visible before its acceptance date.

---

## 5. Event window correction

US 8-K events: 11,612. Acceptance missing: 0.

Corrected windows:

```text
PREMARKET:
  D0 = event-day close / prior trading-day close
INTRADAY:
  D0 = event-day close / prior trading-day close
  (daily data cannot identify intraday time)
AFTER_HOURS:
  D0 = next trading-day close / event-day close
NON_TRADING:
  D0 = next trading-day close / prior trading-day close
D1 = next session after reaction day
D5 = five sessions after reaction day
```

`p12_3_event_window_returns.csv` contains `d0_return`, `d1_return`,
`d5_return`, `window_rule`, and `event_price_status`.

Descriptive US 8-K means (not alpha):

```text
session       D0 mean    D1 mean    D5 mean
PREMARKET     +0.273%    +0.077%    +0.588%
INTRADAY      +0.037%    +0.117%    +0.403%
AFTER_HOURS   +0.135%    +0.068%    +0.482%
NON_TRADING   no complete daily return
```

Foreign 6-K events have no local price match and are marked
`PRICE_MISSING`.

---

## 6. Status

```text
P12_3_STATUS: READY_RESTRICTED
EXPANDED_SAMPLE: 140 issuers
US_8K_EVENTS: READY_RESTRICTED
RAW_FILING_VALIDATION: 59/60 MATCH, 1 PANEL_MISSING, 0 CONFLICT
FOREIGN_6K_EVENTS: PARTIAL
FOREIGN_PRICE_REACTIONS: DATA_BLOCKED
EXACT_EARNINGS_RELEASE_TIME: DATA_BLOCKED
INTRADAY_PRICE_REACTION: DATA_BLOCKED
MARKET_WIDE_PIT_PANEL: DATA_BLOCKED
PAID_DATA: NO_BUY
```

---

## 7. Direct answers

1. **Can a small historical PIT panel be used?**
   Yes, `READY_RESTRICTED`: 140 issuers, accession-level facts, 10 metrics.

2. **Are 8-K times reliable?**
   Acceptance datetime is available and used; it is a filing-time proxy, not an
   exact press-release timestamp.

3. **Can daily prices support event studies?**
   Only descriptive D0/D1/D5 close-to-close returns. No intraday identification.

4. **Can this expand to the broader US market?**
   Not yet. The pilot is 140 issuers, 139 with facts, and foreign prices are
   missing. Market-wide status remains `DATA_BLOCKED`.

5. **What remains blocked?**
   Exact earnings timing, intraday reaction, foreign price coverage, market-wide
   identity/price panel, analyst estimates, historical news.

---

## 8. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P12_3_STATUS: READY_RESTRICTED
PILOT_ISSUERS: 140
FACT_ROWS: 222804
EVENTS: 13668
US_8K_EVENTS: 11612
RAW_VALIDATION_MATCH: 59 / 60
RAW_VALIDATION_CONFLICT: 0
MARKET_WIDE_PIT: DATA_BLOCKED
EXACT_EARNINGS_TIME: DATA_BLOCKED
INTRADAY_REACTION: DATA_BLOCKED
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
P11_PRICE_FACTORS: NO-GO
IBKR_CONNECTED: NO
```

No purchase, registration, trial, VPS, broker, paper/shadow, portfolio or factor
construction. Raw SEC JSON and raw prices are local-only; no raw data uploaded.
