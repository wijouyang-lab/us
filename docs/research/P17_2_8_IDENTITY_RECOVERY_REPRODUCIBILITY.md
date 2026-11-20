# P17.2.8 Identity Recovery & Reproducibility

Date: 2026-11-20
Branch: `research/p17-2-8-identity-recovery-reproducibility`
Base: PR #615 HEAD `5a9a540937d2d244bc7cf1abe211c458d7179b3c`
Status: **PARTIAL_COVERAGE_ONLY**

## 0. Correction of P17.2.7

The P17.2.7 checked-in CSVs were partly edited after the script ran. This round
rebuilt the derived tables from the 218 cached primary documents with one
program, `p17_2_8_identity_reconciliation.py`. No claim that P17.2.7 was
end-to-end reproducible is retained.

## 1. Reparse result

All 218 primary documents were re-read from the existing P17.2.7 cache:

```text
cache documents: 218 primary + 204 submissions = 422
new network requests: 0
parsed documents: 218
verified points: 199
```

The 199 original points are retained; none were newly verified. The code now
computes anchor counts, age, cutoff, stale/future and exceptions directly.

## 2. Historical CIK recovery

Historical sources were loaded:

- PR #390 98-row crosswalk;
- P10 80-row crosswalk.

For the sampled tickers neither source added a usable CIK:

```text
no current CIK rows: 67 (not 82)
P390 recoverable rows: 0
P10 recoverable rows: 0
```

Correction: 82 is the count of samples with no filing, not the count with no
CIK. P17.2.7's "82 missing CIK" description was wrong.

## 3. 19 filing exceptions

All 19 have at least one TradingSymbol fact but no ticker/context pair for the
sampled ticker:

```text
TRADING_SYMBOL_NOT_FOUND: 0
NO_SAME_CONTEXT_PAIR: 19
```

This is consistent with ticker changes / filing cover pages listing a different
class or successor ticker. No parser namespace miss was found in these 19.

## 4. Anchor results

| anchor | CIK | filings | verified | unresolved |
|---|---:|---:|---:|---:|
| A 2020-06-30 | 67 | 59 | 59 | 41 |
| B 2022-06-30 | 76 | 71 | 63 | 37 |
| C 2024-06-28 | 90 | 88 | 77 | 23 |

```text
stale: 0
future excluded: 0
```

All evidence is before the 16:00 ET cutoff. No ffill, no interval.

## 5. Gate

```text
A: CIK 67 < 90, verified 59 < 80 FAIL
B: CIK 76 < 90, verified 63 < 80 FAIL
C: CIK 90 >= 90, verified 77 < 80 FAIL
```

```text
P17_2_8_CONCLUSION = PARTIAL_COVERAGE_ONLY
```

No quarterly panel is authorized.

## 6. Remaining issues

- historical CIK crosswalks do not cover sampled delisted/renamed tickers;
- 19 filings need ticker-successor investigation, not parser changes;
- only 10 behavior tests, not 30;
- P17.2.7's original 82-CIK wording is corrected here.

## 7. Files

- `tools/research/p17_2_8_identity_reconciliation.py`
- `tests/test_p17_2_8_identity_reconciliation.py`
- `data/research/p17_2_8/p17_2_8_historical_cik_candidates.csv`
- `p17_2_8_missing_cik_reconciliation.csv`
- `p17_2_8_19_filing_exception_reconciliation.csv`
- `p17_2_8_reparsed_xbrl_facts.csv`
- `p17_2_8_context_registry.csv`
- `p17_2_8_ticker_security_mapping.csv`
- `p17_2_8_selected_filings.csv`
- `p17_2_8_anchor_identity_results.csv`
- `p17_2_8_future_evidence_audit.csv`
- `p17_2_8_stale_evidence_audit.csv`
- `p17_2_8_acceptance_cutoff_audit.csv`
- `p17_2_8_request_audit.csv`
- `p17_2_8_anchor_coverage.csv`
- `p17_2_8_unresolved_summary.csv`
- `p17_2_8_summary.json`
- `p17_2_8_manifest.json`
