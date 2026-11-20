# P17.2.8.1 Crosswalk Recovery & Replay

Date: 2026-11-20
Branch: `research/p17-2-8-1-crosswalk-recovery-and-replay`
Base: `research/p17-2-8-identity-recovery-reproducibility` (PR #616)
Status: **PARTIAL_COVERAGE_ONLY**

## 1. PR #390 input

Actual file:

`_us_p171/data/research/p17_1/p17_1_p390_identity_reconciliation.csv`

- 98 source rows;
- `candidate_cik` and `cik` both read;
- missing-current-CIK samples: 67;
- overlap: **46 ticker-date rows / 36 unique tickers**;
- 35 unique tickers high, 1 medium (FRC);
- row-level confidence: 44 high, 2 medium because some tickers have multiple anchors.

P17.2.8's claim of 0 PR390 matches was wrong. The old code only read `cik` and
ignored `candidate_cik`/row matching.

## 2. Actual retrieval

For the PR390 candidates:

```text
new SEC network requests: 76
  Submissions JSON: 36
  primary documents: 40
cache hits: 0
no 403/429
```

A filing was selected only if its acceptance was before the anchor's
16:00 ET cutoff. The same exact ticker/contextRef rule was used.

## 3. Recovered points

```text
new VERIFIED_FILING_POINT: 38 / 46
still unverified: 8
total verified points: 237 / 300
```

The 38 new points are not candidate CIKs; each has a matching ticker and
security title in the same context.

## 4. Anchor results

| anchor | CIK candidates | filings | verified |
|---|---:|---:|---:|
| A 2020-06-30 | 89 | 77 | **77** |
| B 2022-06-30 | 93 | 87 | **76** |
| C 2024-06-28 | 97 | 95 | **84** |

Gate:

```text
A: CIK 89 < 90 (by 1); verified 77 < 80  FAIL
B: CIK 93 >= 90; verified 76 < 80         FAIL
C: CIK 97 >= 90; verified 84 >= 80        PASS
```

No anchor pair passes all three; C passes.

## 5. Decision

```text
P17_2_8_1_PR390_IMPORT = PASS (46 rows)
P17_2_8_1_NEW_VERIFIED = 38
P17_2_8_1_TOTAL_VERIFIED = 237
P17_2_8_1_ANCHOR_GATE = FAIL (A, B, C)
P17_2_8_1_OVERALL = PARTIAL_COVERAGE_ONLY
```

This is real progress but still not enough for a quarterly identity panel.

## 6. Remaining gaps

- 8 recovered candidates still have no matching ticker context;
- A is one CIK short and three verified points short;
- B is four verified points short;
- 19 P17.2.7 exception filings still need successor-ticker event evidence;
- the new entry point does not yet emit every file required by the task
  (input manifest, conflicts, future/stale, unresolved summary);
- tests are 10, not 30.

## 7. Files

- `tools/research/p17_2_8_1_identity_reconciliation.py`
- `tests/test_p17_2_8_1_identity_reconciliation.py`
- `data/research/p17_2_8_1/p17_2_8_1_historical_cik_candidates.csv`
- `p17_2_8_1_anchor_identity_results.csv`
- `p17_2_8_1_anchor_coverage.csv`
- `p17_2_8_1_request_audit.csv`
- `p17_2_8_1_summary.json`
- `p17_2_8_1_manifest.json`
