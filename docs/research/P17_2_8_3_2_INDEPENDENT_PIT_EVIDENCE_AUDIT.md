# P17.2.8.3.2 Independent PIT Evidence Audit

Date: 2026-11-23
Branch: `research/p17-2-8-3-2-independent-pit-audit`
Base: PR #620 `b0c7c67354095672f90baee8f48a928cf959a232`
Status: **PARTIAL_COVERAGE_ONLY / DATA_LIMITATION**

## 1. Independent reconstruction

An independent parser re-read the 259 cached primary documents and 300 samples,
without importing the P17.2.8.3.1 parser.

```text
raw documents: 259
network requests: 0
verified: 235 / 300
```

The 235 points remain verified after independent parsing.

## 2. Corrected 41 classification

The previous report called all 41 "NO_HISTORICAL_FILING". Independent audit
splits them:

```text
NO_HISTORICAL_CIK_CANDIDATE: 21
NO_HISTORICAL_FILING:         20
```

So 21 samples had no historical CIK candidate at all, not merely a missing
filing.

## 3. Full status

| status | rows |
|---|---:|
| VERIFIED_RECONFIRMED | 235 |
| NO_HISTORICAL_CIK_CANDIDATE | 21 |
| NO_HISTORICAL_FILING | 20 |
| FILING_FOUND_IDENTITY_UNVERIFIED | 19 |
| SECURITY_TITLE_MISSING | 3 |
| AMBIGUOUS_SECURITY_CONTEXT | 2 |
| **total** | **300** |

PHM and MMM remain ambiguous. WHR/RVTY/EQR remain title missing. No sample was
promoted.

## 4. Cached recovery

No additional cached accession registry exists beyond the 259 selected
documents and their submissions JSON. Secondary recovery result:

```text
recovered: 0
```

No alternate historical accession was available locally with the required
acceptance, CIK and security-context evidence.

## 5. Anchors

| anchor | verified |
|---|---:|
| A 2020-06-30 | 76 |
| B 2022-06-30 | 75 |
| C 2024-06-28 | 84 |

A needs 4 more verified and 1 more CIK; B needs 5 more verified. C passes.

## 6. Clean replay

Two fresh runs produced:

```text
c081540d629e98d51e82a10556b76a62e25121e60b637dd99bd7dc0ee9500485
```

Both matched. No old output was used as input.

## 7. Decision

```text
P17_2_8_3_2_RESULT = PARTIAL_COVERAGE_ONLY
P17_2_8_3_2_SEC_ROUTE = DATA_LIMITATION / NO-GO
```

The 235 are independent, but the missing coverage is a data limitation, not a
parser problem. Stop the free SEC identity expansion route; retain 235 as a
limited research set only.

## 8. Files

- `tools/research/p17_2_8_3_2_independent_audit.py`
- `tests/test_p17_2_8_3_2_independent_audit.py`
- `data/research/p17_2_8_3_2/input_manifest.json`
- `document_registry.csv`
- `row_level_reconciliation.csv`
- `identity_exception_audit.csv`
- `cached_filing_recovery.csv`
- `anchor_coverage_recalculated.csv`
- `independent_raw_facts.csv`
- `independent_verification_summary.json`
- `output_manifest.json`
