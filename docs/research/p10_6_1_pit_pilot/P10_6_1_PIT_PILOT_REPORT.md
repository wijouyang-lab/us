# P10.6.1 SEC PIT Reconstruction Pilot

Date: 2026-11-10

## Final status

```text
PIT_PILOT_PARTIAL
```

The pilot shows that a limited as-of annual fundamental panel can be reconstructed
from free SEC CompanyFacts with accession and filing-date traceability. It does
not prove a market-wide historical panel, and it is not a backtest authorization.

## 1. Coverage reconciliation

`986,198 + 109,132 = 1,095,330`; the missing 160 are quarantined member-days.

| Metric | Numerator | Denominator | Coverage |
|---|---:|---:|---:|
| verified member-days | 986,198 | 1,095,490 | 90.02% |
| valid price member-days | 986,358 | 1,095,490 | 90.04% |
| unknown member-days | 109,132 | 1,095,490 | 9.96% |
| quarantined member-days | 160 | 1,095,490 | 0.0146% |
| ticker coverage | 1,062 | 1,160 | 91.55% |
| delisting-return verified | 0 | 1,095,490 | 0.00% |
| total-return verified | 0 | 1,095,490 | 0.00% |

Price coverage is **not** the same as the 90.02% verified member-day figure.

## 2. Fixed sample

20 companies were fixed before extraction:

- 15 current large caps;
- 5 non-surviving: MON, CELG, RTN, ETFC, XLNX.

20/20 SEC CompanyFacts requests returned HTTP 200.

19/20 produced usable us-gaap facts. XOM's current CIK returned no usable
us-gaap facts in this pilot; it was not replaced after seeing results.

## 3. Core reconstruction

Four cutoffs: 2017-03-31, 2020-03-31, 2023-03-31, 2026-03-31.

| Cutoff | Core facts | Of 9 metrics × 20 |
|---|---:|---:|
| 2017-03-31 | 157 | 87.2% |
| 2020-03-31 | 160 | 88.9% |
| 2023-03-31 | 160 | 88.9% |
| 2026-03-31 | 161 | 89.4% |
| **Total** | **638 / 720** | **88.6%** |

```text
DIRECT:           562
DERIVED_FORMULA:   76
PIT_DATE_PROXY:   934 of 1,014 total rows
PIT_UNRESOLVED:     0
```

Derived values are TotalDebt (component sum) and FCF (OCF - |Capex|).
They are not described as direct facts.

## 4. PIT handling

- Facts are selected only when `filed <= cutoff` and `end <= cutoff`.
- No later accession is used at an earlier cutoff.
- SEC CompanyFacts has filing date but no per-fact acceptance time.
- Every fact is therefore `PIT_DATE_PROXY`; earliest trade is the next session.
- No `PIT_PUBLICATION_VERIFIED` claim is made.
- ContextRef is empty because CompanyFacts is an aggregated accession feed, not
  a raw instance. This is a material limitation, not a pass.

## 5. Revisions

Later filings are excluded by `filed <= cutoff`. A dedicated 10-K/A revision
test was not completed. No observed future-filed accession was used in the pilot.

## 6. Factor reconstruction

| Model | Reconstructable | Status |
|---|---|---|
| Value | 0 / 4 | blocked: no historical market cap/price at each cutoff |
| Quality | 4 / 4 financial ratios | partial: standard tags; 19/20 sample; PIT proxy |
| GARP | 3 growth families partial | needs multi-year as-of series and historical price for valuation |

Value cannot be reconstructed from SEC alone because market cap requires a
historical price snapshot at the same cutoff.

## 7. Verdict

The free SEC route is worth expanding **only for Quality-style accounting
factors**, and only after adding raw-instance contextRef parity and fixing the
sample coverage. It is not sufficient by itself for Value or GARP because
historical market prices are missing.

## 8. Reproducibility

A second full extraction produced byte-identical CSV hashes for all three outputs.

## 9. Not authorized

```text
P10.6:          NOT AUTHORIZED
Shadow:         NOT STARTED
PAPER-50000:    UNTOUCHED
IBKR:           NOT CONNECTED
Merge:          NOT AUTHORIZED
```

PIT_PILOT_PARTIAL is not READY_FOR_BACKTEST.
