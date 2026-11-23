# P17.2.8.3.3 Closeout Validation

Date: 2026-11-23
Branch: `research/p17-2-8-3-3-closeout-validation`
Base: PR #623 `38dae94c9d3a88e25d84230613fd1d68bf8e50eb`
Status: **PARTIAL_COVERAGE_ONLY / DATA LIMITATION**

## 1. Cache inventory

Real full scan of both local SEC cache directories:

```text
cache files: 498
submissions JSON: 239
accessions parsed: 263,545
network requests: 0
```

Every file was hashed and classified. The earlier `recovered=0` was not a
directory-wide proof; this run is.

## 2. Alternative accession recovery

After excluding the already-selected accession, requiring a fully unambiguous
target context, and checking the cached primary document, there was **no
additional recoverable accession**:

```text
recovered: 0
```

A same-accession MMM candidate was found and rejected as a recovery because it
was not an alternative filing and has an empty-title MMM context.

## 3. 41 classification

Independent adjudication:

```text
NO_HISTORICAL_CIK_CANDIDATE: 21
NO_HISTORICAL_FILING:         20
```

The split is retained because the 21 have no historical security CIK candidate,
while the 20 have a selected CIK but no qualifying prior filing.

## 4. 235 revalidation

```text
VERIFIED_RECONFIRMED: 235
context/title exceptions: 0
```

All 235 pass:

- ticker/context/title pairing;
- context entity CIK == selected CIK;
- acceptance before 16:00 ET cutoff;
- evidence age in range;
- document SHA256 and contextRef present.

## 5. Anchors

| anchor | verified | gate |
|---|---:|---|
| A 2020-06-30 | 76 | FAIL |
| B 2022-06-30 | 75 | FAIL |
| C 2024-06-28 | 84 | PASS |

PIT gate remains FAIL.

## 6. Replay

Two fresh runs produced the same business hash:

```text
eb136aa437a5b2df155dc4133cc1ca6dc0edb22efa3434c0bfdf757173645750
```

No output from the first run was used by the second.

## 7. Decision

```text
P17_2_8_3_3_STATUS = PARTIAL_COVERAGE_ONLY
P17_2_8_3_3_SEC_ROUTE = DATA_LIMITATION / NO-GO
```

The cache is fully inventoried, no alternative accession is recoverable, and
235 points remain valid. A/B coverage still fails the 90/80 gate. Stop the free
SEC identity route.

## 8. Files

- `tools/research/p17_2_8_3_3_closeout_audit.py`
- `tests/test_p17_2_8_3_3_closeout_audit.py`
- `data/research/p17_2_8_3_3/cache_inventory.csv`
- `cache_accession_inventory.csv`
- `cache_accession_crosswalk.csv`
- `cached_filing_recovery.csv`
- `row_level_classification_adjudication.csv`
- `verified_235_context_audit.csv`
- `verified_235_exception_review.csv`
- `validation_summary.json`
- `input_manifest.json`
- `output_manifest.json`
- `clean_replay_comparison.json`
