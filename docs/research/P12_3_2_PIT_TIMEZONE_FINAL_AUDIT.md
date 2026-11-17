# P12.3.2: SEC PIT Timezone and Low-Precision Time Final Audit

Date: 2026-11-17
Branch: `research/p12-event-fundamental-feasibility`
Status: **READY_RESTRICTED — timezone interpretation corrected**

---

## 1. Scope

This is a small correction to `tools/research/p12/pit_query.py`.

No sample expansion, no factor/strategy work, no changes to P12.3 or P12.3.1
result files.

---

## 2. Correction

Old behavior:

```python
pd.to_datetime(filing_date, utc=True) + 23:59:59
```

This treated a US/Eastern calendar date as a UTC date and could make a
filing-date-only fact appear up to 4–5 hours early.

New behavior:

- filing date is interpreted in `America/New_York`;
- missing acceptance uses the **US/Eastern end of that day**, then converts to
  UTC;
- precision remains `FILING_DATE_LOW_PRECISION`;
- a real acceptance timestamp always wins;
- date-only `asof("YYYY-MM-DD")` means US/Eastern end of day;
- a full `asof` timestamp must have an explicit timezone; naive timestamps raise
  `ASOF_TIMESTAMP_REQUIRES_EXPLICIT_TIMEZONE`;
- full fact identity, all periods, and accession-version selection are unchanged.

Examples:

```text
EDT filing 2009-07-22 -> known 2009-07-23T03:59:59Z
EST filing 2010-01-25 -> known 2010-01-26T04:59:59Z
```

---

## 3. Precision summary

`p12_3_2_precision_summary.csv`

```text
total fact rows:                 222,804
acceptance timestamp rows:       104,360
filing-date low-precision rows:  118,444
```

The 118,444 rows are not treated as precise publication times. They are usable
only at US/Eastern end of day and remain marked low precision.

---

## 4. Boundary tests

`p12_3_2_timezone_boundary_tests.csv`

```text
EDT date-only end of day:        PASS
EDT before boundary:             PASS (not visible)
EDT at boundary:                 PASS
EST date-only end of day:        PASS
EST before boundary:             PASS (not visible)
EST at boundary:                 PASS
acceptance before timestamp:     PASS (not visible)
acceptance at timestamp:         PASS
naive timestamp rejected:        PASS
all periods retained:            PASS
```

Boundary result:

```text
2009-07-23T03:59:58Z -> not visible
2009-07-23T03:59:59Z -> visible
2018-08-01T20:02:03Z -> not visible
2018-08-01T20:02:04Z -> visible
2010-01-26T04:59:58Z -> not visible
2010-01-26T04:59:59Z -> visible
```

Tests also cover:

- US/Eastern daylight time;
- US/Eastern standard time;
- acceptance timestamp vs filing-date fallback;
- date-only asof;
- `Z` timestamps;
- `-04:00` offset timestamps;
- before/after revision visibility;
- complete period retention.

---

## 5. What did not change

- no acceptance timestamp was rewritten;
- no fact identity was merged across tag/unit;
- no later 10-K/A or 10-Q/A was moved earlier;
- P12.3 and P12.3.1 files remain unchanged;
- 140-issuer pilot scope remains;
- P9 all NO-GO, P10 NO_BUY, P11 NO-GO.

---

## 6. Final status

```text
P12_3_2_STATUS: READY_RESTRICTED
PIT_TIMEZONE: READY_RESTRICTED
LOW_PRECISION_TIME: READY_RESTRICTED
NAIVE_TIMESTAMP_REJECTED: YES
DATE_ONLY_ASOF_ET_EOD: YES
TRUE_ACCEPTANCE_PRESERVED: YES
P12_3_FILES_PRESERVED: YES
MARKET_WIDE_PIT: DATA_BLOCKED
EXACT_EARNINGS_TIME: DATA_BLOCKED
INTRADAY_REACTION: DATA_BLOCKED
```

---

## 7. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P12_3_2_STATUS: READY_RESTRICTED
LOW_PRECISION_ROWS: 118444
ACCEPTANCE_ROWS: 104360
TIMEZONE_TESTS: 10 PASS
P12_3_1_EVENTS: 13668
P12_3_1_OK_COMPLETE: 10941
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
P11_PRICE_FACTORS: NO-GO
IBKR_CONNECTED: NO
```

No purchase, no VPS, no IBKR, no paper/shadow, no portfolio/factor construction,
no merge, no main change, no raw data upload.
