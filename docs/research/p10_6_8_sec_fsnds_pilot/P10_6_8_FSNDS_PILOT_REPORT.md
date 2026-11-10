# P10.6.8 SEC FSNDS Pilot

Date: 2026-11-10

## Status

```text
FSNDS_PILOT_PARTIAL
```

## 1. Data used

Downloaded SEC FSNDS `2017q1_notes.zip`:

```text
bytes:   498,205,726
sha256: 4bcf1c2dcfb58ae3d0c2b9f676ff7611600b5f2665a94e1f0bf43c6903bdf508
```

The archive contains SUB, NUM, DIM, TAG, PRE, CAL, TXT and REN tables.

Only 2017q1 was downloaded, not all four cutoff quarters. This is a scope limit.

## 2. Positive control (46 raw-XBRL verified facts)

All 46 records are outside 2017q1, so:

```text
NOT_IN_FSNDS_SCOPE: 46
```

This is not a value mismatch and not a pass. No positive-control conclusion can
be drawn from one quarter.

## 3. 34 ambiguous contexts

All 34 accessions are outside 2017q1:

```text
NOT_IN_FSNDS_SCOPE: 34
```

No ambiguous context was resolved by this pilot.

## 4. IBM / INTC 2017

FSNDS facts found:

- INTC: Net Income, Equity, Assets; Liabilities derived as Assets - Equity.
- IBM: Equity, Assets, OCF, Liabilities.

Missing:

- INTC OCF;
- IBM Net Income.

Therefore IBM/INTC still do not produce a complete five-input Quality set at
2017-03-31. No Quality ratio is claimed complete.

## 5. HPQ Total Liabilities

HPQ 2022q4 and 2023q3 FSNDS archives were not downloaded. The previously derived
values remain:

```text
Original: 41,505,000,000
Amended:  41,519,000,000
```

FSNDS cross-check status: `NOT_DOWNLOADED_2022Q4` / `NOT_DOWNLOADED_2023Q3`.

## 6. Five-company panel

Updated only IBM/INTC 2017 with FSNDS facts. Final status counts:

```text
VALID: 7
PARTIAL: 11
NOT_APPLICABLE_AFTER_ACQUISITION: 2
```

No ranking: sample is below 30 peers.

## 7. Repeatability

Two full successful builds were not completed. `all_equal` is not claimed.

## 8. Decision

FSNDS is usable and its `dimh=0x00000000`, `dimn=0`, empty `coreg` fields gave
clean consolidated facts for IBM/INTC. But one quarter is insufficient to judge
the 46 controls, 34 ambiguous contexts, or HPQ.

```text
FSNDS_PILOT_PARTIAL
```

Do not change P10.6.7's `STOP_SEC_XBRL_ROUTE`.

## 9. Safety

```text
P10.6:          NOT AUTHORIZED
Shadow:         NOT STARTED
PAPER-50000:    UNTOUCHED
IBKR:           NOT CONNECTED
Merge:          NOT AUTHORIZED
```
