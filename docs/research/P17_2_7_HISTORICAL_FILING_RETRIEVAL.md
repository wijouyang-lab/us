# P17.2.7 Historical Filing Retrieval & XBRL Verification

Date: 2026-11-20
Branch: `research/p17-2-7-historical-filing-xbrl-verification`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **PARTIAL_COVERAGE_ONLY**

## 1. Actual SEC work

```text
samples: 300
unique tickers: 258
unique CIKs: 204
Submissions JSON: 204
selected prior 10-K/10-Q: 218
primary documents downloaded/parsed: 218
network requests: 218
cache hits: 204
verified filing points: 199
```

Requests were at 1/second, no concurrency, cached by URL SHA-256, cap 600 not
approached. No 403/429 stop occurred.

## 2. Per-anchor results

| anchor | date | CIK candidates | filings | verified points | recent prior | stale | unresolved |
|---|---|---:|---:|---:|---:|---:|---:|
| A | 2020-06-30 | 67 | 59 | 59 | 59 | 0 | 41 |
| B | 2022-06-30 | 76 | 71 | 63 | 63 | 0 | 37 |
| C | 2024-06-28 | 90 | 88 | 77 | 77 | 0 | 23 |

All verified points are prior to the anchor's 16:00 ET cutoff; no future
filing was used. No stale point (>400 days) survived selection because the
latest prior filing was chosen.

## 3. Thresholds

```text
A: CIK 67 < 90; verified 59 < 80  FAIL
B: CIK 76 < 90; verified 63 < 80  FAIL
C: CIK 90 >= 90; verified 77 < 80 FAIL
```

No anchor passes both required gates. The C anchor passes CIK but not verified
security identity.

## 4. Why unresolved

- 82/300 samples had no current CIK candidate (mostly delisted/renamed names);
- 218 selected filings, but only 199 contained a matching ticker context;
- 19 selected filings had no matching `TradingSymbol` context (ticker absent,
  changed, or not in the cover-page DEI facts);
- no CIK conflict was fabricated.

## 5. Decision

```text
P17_2_7_FILING_RETRIEVAL = PASS (218 documents)
P17_2_7_VERIFIED_POINTS = 199/300
P17_2_7_ANCHOR_GATE = FAIL (A, B, C)
P17_2_7_OVERALL = PARTIAL_COVERAGE_ONLY
```

This is not enough to start a full 2020–2024 quarterly identity panel. The
historical SEC route works, but current-CIK mapping and cover-page ticker
coverage are insufficient for the 80/100 anchor gate.

## 6. Next step

- recover historical CIKs for the 82 unresolved samples from PR #390/P10;
- resolve 19 selected filings with no matching ticker context;
- re-run the same retrieval and context parser;
- require all three anchors ≥90 CIK and ≥80 verified before expansion.

## 7. Files

- `tools/research/p17_2_7_historical_filing_retrieval.py`
- `tests/test_p17_2_7_historical_filing_retrieval.py`
- `data/research/p17_2_7/p17_2_7_corrected_sample_audit.csv`
- `p17_2_7_cik_candidate_reconciliation.csv`
- `p17_2_7_submissions_registry.csv`
- `p17_2_7_historical_submissions_files.csv`
- `p17_2_7_selected_filings.csv`
- `p17_2_7_primary_document_registry.csv`
- `p17_2_7_raw_xbrl_facts.csv`
- `p17_2_7_context_registry.csv`
- `p17_2_7_ticker_security_mapping.csv`
- `p17_2_7_anchor_identity_results.csv`
- `p17_2_7_stale_evidence.csv`
- `p17_2_7_future_evidence_excluded.csv`
- `p17_2_7_identity_conflicts.csv`
- `p17_2_7_request_audit.csv`
- `p17_2_7_anchor_coverage.csv`
- `p17_2_7_summary.json`
- `p17_2_7_manifest.json`
