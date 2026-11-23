# P17.2.8.3 PIT Evidence Close-out

Date: 2026-11-23
Branch: `research/p17-2-8-3-pit-evidence-closeout`
Base: PR #618 `089ff065e79ed4d2f030d9d3d454d21f0d19320d`
Status: **PARTIAL_COVERAGE_ONLY**

## 1. Corrected grouping

The prior file labels were wrong. From the P17.2.8.1 baseline, using both
provenance and prior verified status:

```text
ORIGINAL_199:      199 rows
NEW_38:             38 rows
OTHER_UNVERIFIED:   63 rows
```

Revalidation:

| group | reconfirmed | ambiguous | title missing | no filing | filing unverified |
|---|---:|---:|---:|---:|---:|
| ORIGINAL_199 | 198 | 1 (PHM) | 0 | 0 | 0 |
| NEW_38 | 37 | 0 | 1 | 0 | 0 |
| OTHER_UNVERIFIED | 0 | 1 (MMM) | 2 (WHR, EQR) | 41 | 19 |

Total: **235 verified / 300**.

## 2. Status totals

```text
VERIFIED_RECONFIRMED: 235
NO_HISTORICAL_FILING: 41
FILING_FOUND_IDENTITY_UNVERIFIED: 19
REVOKED_TITLE_MISSING: 3
AMBIGUOUS_SECURITY_CONTEXT: 2
```

## 3. Anchor coverage

| anchor | candidate CIK | verified | gate |
|---|---:|---:|---|
| A 2020-06-30 | 89 | 76 | FAIL |
| B 2022-06-30 | 93 | 75 | FAIL |
| C 2024-06-28 | 97 | 84 | PASS |

A is one CIK and four verified points short; B is five verified points short.
No gate change.

## 4. 24 exceptions

- PHM: two PHM contexts (rights vs common shares), ambiguous; not promoted.
- MMM: empty-title MMM context plus common-stock MMM and debt symbols; ambiguous.
- WHR, RVTY, EQR: no non-empty title in the target context; title missing.
- 19 `FILING_FOUND_IDENTITY_UNVERIFIED`: target symbol not paired with a title
  in the selected filing; no promotion.

No sample was upgraded by guessing.

## 5. P10

P10 file exists with 80 rows. It was loaded and audited; it did not add a
verified point in this round. No fuzzy or current-name promotion.

## 6. Clean replay

Two fresh output directories were produced by the same entry point:

```text
business result SHA256:
f726a1e351ebfa0e10faa4443ba83031f6e5819e5699b85044f3c8f3e05b0c95
```

Both runs matched. No old CSV was used to fill outputs. The script refuses a
non-empty output directory.

## 7. Data access

```text
cache hits (verified evidence): 235
network requests: 0
HTTP errors: 0
```

All evidence came from existing local SEC cache.

## 8. Decision

```text
P17_2_8_3_ANCHOR_GATE = FAIL
P17_2_8_3_STATUS = PARTIAL_COVERAGE_ONLY
```

No quarterly PIT panel.

## 9. Files

- `tools/research/p17_2_8_3_closeout.py`
- `tests/test_p17_2_8_3_closeout.py`
- `data/research/p17_2_8_3/p17_2_8_3_input_manifest.json`
- `p17_2_8_3_output_manifest.json`
- `p17_2_8_3_anchor_identity_results.csv`
- `p17_2_8_3_anchor_summary.csv`
- `p17_2_8_3_context_registry.csv`
- `p17_2_8_3_raw_xbrl_exception_facts.csv`
- `p17_2_8_3_exception_disposition.csv`
- `p17_2_8_3_cik_conflicts.csv`
- `p17_2_8_3_request_audit.csv`
- `p17_2_8_3_reconciliation.csv`
- `p17_2_8_3_summary.json`

## P17.2.8.3.1 Raw Filing Forensic Replay

This section supersedes the prior "cache hits = verified rows" claim.

### Raw documents

```text
raw documents found/read: 259
parse successes: 259
parse exceptions: 0
missing raw documents: 41
network requests: 0
```

The 259 documents were read directly from the P17.2.7/P17.2.8.1 Inline XBRL
cache. The 41 samples without a filing remain NO_HISTORICAL_FILING.

### Full 300 revalidation

```text
VERIFIED_RECONFIRMED: 235
NO_HISTORICAL_FILING: 41
FILING_FOUND_IDENTITY_UNVERIFIED: 19
REVOKED_TITLE_MISSING: 3
AMBIGUOUS_SECURITY_CONTEXT: 2
```

Raw replay confirms the prior 235; no new point was promoted. PHM and MMM
remain ambiguous; WHR/RVTY/EQR remain title-missing.

### Anchors

| anchor | candidate CIK | verified |
|---|---:|---:|
| A | 89 | 76 |
| B | 93 | 75 |
| C | 97 | 84 |

Gate still fails.

### Clean replay

Two fresh runs produced:

```text
11fca29a946bf98ef974646588f4873d30c03f7c29398027ebc1b095a6c0e924
```

Both matched, and the result was produced directly from raw cached documents.

### Route decision

```text
P17_2_8_3_1_SEC_IDENTITY_ROUTE = DATA_LIMITATION / NO-GO
```

A is 1 CIK and 4 verified short; B is 5 verified short. No further P17.2.8.4
sampling loop is authorized. Retain 235 points as limited evidence only.
