# P10.6.7 Quality Integration and SEC Route Decision

Date: 2026-11-10

## Status

```text
QUALITY_SLICE_PARTIAL
SEC_ROUTE_DECISION: STOP_SEC_XBRL_ROUTE
```

## 1. IBM / INTC 2017 integration

| Company | Facts found | Missing | Result |
|---|---:|---|---|
| IBM | 4 / 5 | Liabilities | partial |
| INTC | 2 / 5 | Equity, Liabilities, OCF | partial |

Net Income, Assets and OCF (where present) have accession, concept, contextRef,
period and unit. Because Quality V1 requires all five inputs, neither company can
produce all four ratios at 2017-03-31.

The original source placeholders are retained; they are not deleted.

## 2. HPQ Total Liabilities

Accounting identity:

```text
Total Liabilities = Assets - Stockholders' Equity
```

Verified separately for original and amended FY2022:

| Version | Assets | Equity | Liabilities |
|---|---:|---:|---:|
| Original | 38,587,000,000 | -2,918,000,000 | **41,505,000,000** |
| Amended | 38,494,000,000 | -3,025,000,000 | **41,519,000,000** |

Assets and Equity share the same contextRef and instant in each version:
`i24...I20221031` in the original, `c-6` in the amendment.

Status: `DERIVED_FORMULA_VERIFIED`.

## 3. 34 unresolved final classification

```text
MULTIPLE_CONSOLIDATED_CANDIDATES: 23
NO_CONSOLIDATED_FACT:             11
```

These are not silently dropped. They still affect Quality V1 because a company
needs all four ratios.

## 4. Five-company final panel

| Status | Rows |
|---|---:|
| VALID | 7 |
| PARTIAL | 11 |
| NOT_APPLICABLE_AFTER_ACQUISITION | 2 |

Only 7 of 20 company-cutoff rows have all four Quality inputs. The five-company
sample remains below 30 peers, so no new Quality ranking was generated.

## 5. Repeatability

Two complete runs produced identical CSV hashes:

```text
all_equal = true
```

## 6. SEC route decision

```text
STOP_SEC_XBRL_ROUTE
```

Reason:

- the same five-company slice still has 34 unresolved consolidated facts;
- IBM/INTC 2017 cannot be completed to all five inputs;
- only 7/20 final rows are valid;
- scaling to 60 companies would multiply the same ambiguity;
- a small patch cannot deterministically resolve the remaining contexts.

This is a decision to stop expanding the raw-XBRL route, not a claim that the
company data is worthless. The 46 verified facts and HPQ/SEC evidence remain
usable for a bounded Quality panel.

## 7. Safety

```text
P10.6:          NOT AUTHORIZED
Shadow:         NOT STARTED
PAPER-50000:    UNTOUCHED
IBKR:           NOT CONNECTED
Merge:          NOT AUTHORIZED
```
