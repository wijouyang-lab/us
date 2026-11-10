# P10.6.6 Quality Slice Finalization

Date: 2026-11-10

## Status

```text
QUALITY_SLICE_PARTIAL
```

## 1. 92-row status reconciliation

```text
P10.6.4:
  VERIFIED              50
  UNRESOLVED            40
  SOURCE_MISSING         2

P10.6.5/6:
  VERIFIED              46
  UNRESOLVED            34
  NOT_APPLICABLE        10
  SOURCE_MISSING         2
```

All transitions are XLNX rows:

- 6 previously unresolved became `NOT_APPLICABLE_AFTER_ACQUISITION`;
- 4 previously verified became `NOT_APPLICABLE_AFTER_ACQUISITION`.

Evidence: AMD–Xilinx acquisition closed 2022-02-14, 8-K
`0001104659-22-021762`, 25-NSE `0001354457-22-000131`.

No duplicate or reassigned rows.

## 2. 34 ambiguous contexts

34 remain `XBRL_CONTEXT_UNRESOLVED` after the bounded two-pass review.
No candidate was chosen by value proximity or by forcing CompanyFacts to match.
Reasons: multiple same-period contexts, segment/duplicate ambiguity, or no
unique consolidated fact.

## 3. IBM / INTC 2017

Found and parsed:

| Company | Accession | Instance | HTTP | Bytes |
|---|---|---|---|---|
| IBM | `0001047469-17-001061` | `ibm-20161231.xml` | 200 | 11,684,003 |
| INTC | `0000050863-17-000012` | `intc-20161231.xml` | 200 | 6,003,139 |

Status `SOURCE_RECOVERED`. However, the two original P10.6.4 rows were
placeholder rows without metrics; they were not integrated into the 92-row
metric table. The reconciliation therefore still shows 2 `SOURCE_FILE_MISSING`.

## 4. HPQ Total Liabilities

Searched original and amended HPQ instances.

`Liabilities` is not directly presented. `LiabilitiesAndStockholdersEquity`
exists, but a reliable paired `StockholdersEquity` context was not resolved for
the same instant. Therefore:

```text
HPQ Total Liabilities = XBRL_CONTEXT_UNRESOLVED
```

Not filled from current CompanyFacts and not replaced by current liabilities.

## 5. HPQ 10-K/A replay

Actual FY2022 changes:

| Metric | Original | Amended | Change |
|---|---:|---:|---:|
| Net Income | 3,203,000,000 | 3,132,000,000 | -71,000,000 (-2.22%) |
| Equity | -2,918,000,000 | -3,025,000,000 | -107,000,000 |
| Assets | 38,587,000,000 | 38,494,000,000 | -93,000,000 |
| OCF | 4,463,000,000 | 4,463,000,000 | UNCHANGED |
| Liabilities | unresolved | unresolved | unresolved |

PIT:

```text
2023-09-08  original
2023-09-11  original (conservative filing-date proxy)
2023-09-12  amended
```

No backfill.

## 6. Repeatability

Two full remediation runs produced identical deterministic CSV hashes:

```text
all_equal = true
```

This is pipeline determinism on fixed inputs, not a new OOS test.

## 7. Final verdict

The free SEC XBRL route can recover a substantial part of the five-name slice,
but cannot yet close all Quality inputs:

- 46 verified;
- 34 unresolved;
- 10 N/A;
- 2 source placeholders not integrated.

Therefore not `QUALITY_SLICE_ACCEPTED`.

## 8. Safety

```text
P10.6:          NOT AUTHORIZED
Shadow:         NOT STARTED
PAPER-50000:    UNTOUCHED
IBKR:           NOT CONNECTED
Merge:          NOT AUTHORIZED
```
