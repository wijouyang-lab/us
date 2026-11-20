# P17.2.8.2 PIT Evidence Integrity

Date: 2026-11-20
Branch: `research/p17-2-8-2-pit-evidence-integrity`
Base: PR #617 `4e7f23ae548d3b02615d7b263d06a0db89eadaaf`
Status: **PARTIAL_COVERAGE_ONLY**

## 1. What was fixed

The prior 235 points had empty evidence ages for new rows and no target-context
CIK. This round re-parsed all cached SEC documents and required, for every
verified row:

- selected CIK == target context entity CIK;
- exact TradingSymbol == sample ticker;
- a non-empty Security12bTitle/Security12gTitle in the same contextRef;
- acceptance datetime <= 16:00 ET anchor cutoff;
- numeric evidence age;
- document SHA256 and contextRef.

XA conversion also fixed: Inline XBRL `contextref` is lower-case in the HTML
parser; the previous code read only `contextRef` and silently lost every
context pairing.

## 2. Revalidation result

```text
original 199: 198 VERIFIED_RECONFIRMED
new 37:       37 VERIFIED_RECONFIRMED
total:        235 / 300
```

Three previously unresolved rows are now classified:

```text
PHM  AMBIGUOUS_SECURITY_CONTEXT
MMM  AMBIGUOUS_SECURITY_CONTEXT
RVTY REVOKED_TITLE_MISSING
```

They were not counted in the old 198, so no previously verified point was
revoked; they remain unresolved.

## 3. Anchor coverage

| anchor | CIK | filings | verified |
|---|---:|---:|---:|
| A 2020-06-30 | 89 | 77 | **76** |
| B 2022-06-30 | 93 | 87 | **75** |
| C 2024-06-28 | 97 | 95 | **84** |

```text
A: CIK 89 < 90, verified 76 < 80 FAIL
B: CIK 93 >= 90, verified 75 < 80 FAIL
C: CIK 97 >= 90, verified 84 >= 80 PASS
```

No anchor set passes; A is one CIK and four verified points short; B is three
verified points short.

## 4. Exceptions

19 selected filings still have no target ticker in a matching context. They are
listed in `p17_2_8_2_19_exception_audit.csv`; this round did not complete
successor-event evidence for them.

## 5. P10

`p10_5_2_verified_identity_crosswalk.csv` exists with 80 rows and was loaded.
It did not add a verified point to the 300 in this round.

## 6. Decision

```text
P17_2_8_2_ORIGINAL_199_RECONFIRMED = 199
P17_2_8_2_NEW_38_RECONFIRMED = 38
P17_2_8_2_TOTAL_VERIFIED = 235
P17_2_8_2_ANCHOR_GATE = FAIL
P17_2_8_2_OVERALL = PARTIAL_COVERAGE_ONLY
```

No quarterly identity panel.

## 7. Files

- `tools/research/p17_2_8_2_evidence_integrity.py`
- `tests/test_p17_2_8_2_evidence_integrity.py`
- `data/research/p17_2_8_2/p17_2_8_2_original_199_revalidation.csv`
- `p17_2_8_2_new_38_revalidation.csv`
- `p17_2_8_2_19_exception_audit.csv`
- `p17_2_8_2_p10_crosswalk_audit.csv`
- `p17_2_8_2_reparsed_xbrl_facts.csv`
- `p17_2_8_2_context_registry.csv`
- `p17_2_8_2_ticker_security_mapping.csv`
- `p17_2_8_2_anchor_identity_results.csv`
- `p17_2_8_2_anchor_coverage.csv`
- `p17_2_8_2_acceptance_cutoff_audit.csv`
- `p17_2_8_2_future_evidence_audit.csv`
- `p17_2_8_2_stale_evidence_audit.csv`
- `p17_2_8_2_request_audit.csv`
- `p17_2_8_2_unresolved_summary.csv`
- `p17_2_8_2_summary.json`
- `p17_2_8_2_manifest.json`
