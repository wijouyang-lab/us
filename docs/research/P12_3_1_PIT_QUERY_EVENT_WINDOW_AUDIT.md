# P12.3.1: PIT Query and 8-K Event Window Final Audit

Date: 2026-11-17
Branch: `research/p12-event-fundamental-feasibility`
Status: **READY_RESTRICTED for the 140-issuer pilot; DATA_BLOCKED for market-wide use**

---

## 1. Scope

This is a correction of P12.3 query and event-window logic. The 140 issuers and
all P12.3 files are preserved; no sample expansion and no factor construction.

---

## 2. PIT `as_of()` correction

Old behavior returned one latest row for CIK+metric, not a historical panel.

New behavior:

- filters only facts known by the query timestamp;
- identity is:

```text
CIK, metric, taxonomy, tag, unit, period_start, period_end
```

- chooses the latest visible accession independently for each identity;
- returns **all** historical periods and all identities;
- keeps different units/tags separate;
- acceptance timestamp is used when available;
- missing acceptance falls back to filing date at 23:59:59 and is marked
  `FILING_DATE_LOW_PRECISION`;
- later 10-K/A/10-Q/A cannot enter an earlier snapshot.

Evidence: `p12_3_1_asof_query_tests.csv`

```text
three_plus_periods: 49 rows / 29 periods
before ABT revision: 43 periods
after ABT revision:  46 periods
same day 19:00: 41 periods
same day 21:00: 42 periods
future date:     41 periods (no later accession)
```

Same-day tests use the actual acceptance timestamps
(`2018-08-01T20:02:04Z`), so pre/post ordering is real, not date-only.

---

## 3. Event window correction

P12.3 had an early `fd not in trading_days` check that prevented the
NON_TRADING branch from running.

P12.3.1 rules:

```text
PREMARKET:
  event-day close / prior trading-day close
INTRADAY:
  event-day close / prior trading-day close
  (daily bars cannot identify the intraday moment)
AFTER_HOURS:
  next trading-day close / event-day close
NON_TRADING:
  first trading day after event / prior trading-day close
D1:
  next session close / D0 reaction-day close
D5:
  5th session close / D0 reaction-day close
```

A non-trading event now uses the first trading day after the filing date, not
one extra delayed session.

---

## 4. Event status reconciliation

All 13,668 events have exactly one primary status:

```text
OK_COMPLETE:               10,941
FOREIGN_PRICE_MISSING:      2,056
US_SYMBOL_NOT_FOUND:          619
NO_PREVIOUS_CLOSE:             46
D5_MISSING:                     3
NO_EVENT_CLOSE:                 2
D1_MISSING:                     1
TOTAL:                     13,668
```

No duplicate or unclassified event.

Window completeness (not just D0):

```text
D0 available: 10,945
D1 available: 10,944
D5 available: 10,941
Fully complete (D0+D1+D5): 10,941
```

NON_TRADING events:

```text
20 total
15 OK_COMPLETE
3 FOREIGN_PRICE_MISSING
2 US_SYMBOL_NOT_FOUND
```

Files:

- `p12_3_1_event_status_reconciliation.csv`
- `p12_3_1_event_window_returns.csv`
- `p12_3_1_event_window_coverage.csv`

---

## 5. Additional 10-Q / amendment validation

P12.3's original 10-K check is preserved:

```text
10 filings, 60 checks, 59 MATCH, 1 PANEL_MISSING, 0 CONFLICT
```

Additional 10-Q/10-Q/A check:

```text
issuers: AAPL, MSFT, JNJ, MON
checks:  16
MATCH:   10
PERIOD_AGGREGATION_MISMATCH: 6
CONFLICT: 0
```

MON uses a real `10-Q/A` accession. The six differences are quarterly-vs-YTD
context differences, recorded as period aggregation differences, not silently
corrected.

File: `p12_3_1_fact_version_validation.csv`

Foreign issuers do not file 10-Q; BP is covered by its 20-F in the P12.3
validation.

---

## 6. Final status

```text
P12_3_1_STATUS: READY_RESTRICTED
PIT_ASOF_HISTORY: READY_RESTRICTED
EVENT_WINDOW_RECONCILIATION: READY_RESTRICTED
EVENT_STATUS_COMPLETE: 13,668 / 13,668
D0_COMPLETE: 10,945
D1_COMPLETE: 10,944
D5_COMPLETE: 10,941
FULL_WINDOW_COMPLETE: 10,941
NON_TRADING_WINDOW: READY_RESTRICTED
FOREIGN_PRICE: DATA_BLOCKED
EXACT_EARNINGS_TIME: DATA_BLOCKED
INTRADAY_REACTION: DATA_BLOCKED
MARKET_WIDE_PIT: DATA_BLOCKED
```

---

## 7. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P12_3_1_STATUS: READY_RESTRICTED
EVENTS: 13668
OK_COMPLETE: 10941
D0_COMPLETE: 10945
D1_COMPLETE: 10944
D5_COMPLETE: 10941
RAW_10K_MATCH: 59 / 60
RAW_10Q_MATCH: 10 / 16
RAW_10Q_PERIOD_MISMATCH: 6
MARKET_WIDE_PIT: DATA_BLOCKED
EXACT_EARNINGS_TIME: DATA_BLOCKED
INTRADAY_REACTION: DATA_BLOCKED
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
P11_PRICE_FACTORS: NO-GO
IBKR_CONNECTED: NO
```

No purchase, no VPS, no IBKR, no paper/shadow, no portfolio/factor construction,
no raw SEC JSON/XBRL or price files uploaded.
