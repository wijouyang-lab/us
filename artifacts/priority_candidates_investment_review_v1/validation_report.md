# Validation Report — Priority Review V1

Date: 2026-11-27

## Automated tests

```text
pytest -q tests/test_priority_review.py
......... [100%]
9 passed in 0.40s
```

Covered:

1. 28,000 ticker/style ledger, one status each.
2. Candidate quality counts sum to 1,342.
3. CRMD historical ELIMINATE override.
4. 4 PRIORITY_WATCH tickers.
5. No PAPER_CANDIDATE.
6. 39 unique reviewed tickers.
7. 39 SEC source URLs.
8. TTM method / financial metrics present.
9. Page JSON SHA matches.

## Chromium E2E

```text
loaded: true
PRIORITY_WATCH filter: 8 rows (4 unique tickers across styles)
ELIMINATE filter: 3 rows (CRMD across styles)
CRMD search: 3 rows
detail: Investment decision = ELIMINATE
SHA mismatch fail-closed: true
```

Screenshot: `artifacts/priority_candidates_investment_review_v1/multi_style_review.png`.

## 28,000 accounting

- CANDIDATE: 1,342
- EXCLUDED: 26,463
- DATA_UNAVAILABLE: 195
- Total: 28,000
- Every row has exactly one status; no ticker/style pair is silently dropped.

The 195 are combinations not present in candidate or exclusion outputs; they are marked DATA_UNAVAILABLE with reason `NOT_IN_CANDIDATE_OR_EXCLUSION_OUTPUT`, not imputed.

## Quality reconciliation

Candidate rows: VERIFIED 606, PARTIAL 661, UNKNOWN 75; unique candidate tickers 1,006. The 517 universe VERIFIED count is ticker-level, while candidate rows can repeat across styles; only 394 unique candidate tickers are VERIFIED. Priority rows are all VERIFIED.

## Data caveats

- TTM uses FY + YTD − prior YTD; 39 review rows have 10 INSUFFICIENT due missing/invalid TTM revenue/FCF (not zero-filled).
- GOLD revenue negative in extraction -> INSUFFICIENT, not used as valuation.
- Financials are current cross-section, not PIT.
- Prices are 2026-11-25 unadjusted.
- 470 CA names excluded from trend.
- No PAPER/IBKR/order.
