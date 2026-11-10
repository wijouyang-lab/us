# P10.6.5 Quality PIT Remediation

Date: 2026-11-10

## Status

```text
QUALITY_SLICE_PARTIAL
```

No 60-name expansion. No Quality formula or 30-peer threshold change.

## 1. 92-row slice after remediation

| Status | Count |
|---|---:|
| XBRL_CONTEXT_VERIFIED | 46 |
| XBRL_CONTEXT_UNRESOLVED | 34 |
| NOT_APPLICABLE_AFTER_ACQUISITION | 10 |
| SOURCE_FILE_MISSING | 2 |

The 40 ambiguous rows were not forced green. XLNX post-acquisition rows were
classified as not applicable; 34 genuinely ambiguous/missing consolidated facts
remain unresolved. IBM/INTC 2017 source gaps remain `SOURCE_FILE_MISSING`.

## 2. XLNX lifecycle

Official evidence:

- 8-K `0001104659-22-021762`, 2022-02-14, acquisition closed.
- 25-NSE `0001354457-22-000131`, 2022-02-14, exchange delisting.

Cutoffs 2017/2020 are applicable; 2023/2026 are
`NOT_APPLICABLE_AFTER_ACQUISITION`. These rows do not enter peer scores.

## 3. HPQ 10-K/A replay

Original:

```text
0000047217-22-000068  filed 2022-12-06
```

Amended:

```text
0000047217-23-000075  filed 2023-09-11
```

FY2022 actual changes (USD):

| Metric | Original | Amended | Change |
|---|---:|---:|---:|
| Net Income | 3,203,000,000 | 3,132,000,000 | -71,000,000 (-2.22%) |
| Equity | -2,918,000,000 | -3,025,000,000 | -107,000,000 |
| Assets | 38,587,000,000 | 38,494,000,000 | -93,000,000 |
| OCF | 4,463,000,000 | 4,463,000,000 | UNCHANGED |
| Liabilities | not located | not located | UNRESOLVED |

The amendment changed net income, equity and assets; OCF did not change.
ContextRefs changed between filings (`i24...I20221031` -> `c-6`), so matching by
contextRef alone would have failed; the replay matched by period and metric.

## 4. PIT timeline

```text
2023-09-08  original 10-K values
2023-09-11  amendment filed; conservative proxy still uses original
2023-09-12  next session; amended values become usable
```

The amended values were not backfilled to 2017/2020/2023-03-31 cutoffs.

## 5. Repeatability

A second full five-name build was not executed. `all_equal` is not claimed.

## 6. Remaining blockers

1. 34 unresolved consolidated facts.
2. IBM/INTC 2017 source files missing.
3. HPQ Liabilities fact not located.
4. Full five-name repeatability not run.
5. 60-name expansion and full-market PIT remain blocked.

## 7. Safety

```text
P10.6:          NOT AUTHORIZED
Shadow:         NOT STARTED
PAPER-50000:    UNTOUCHED
IBKR:           NOT CONNECTED
Merge:          NOT AUTHORIZED
```
