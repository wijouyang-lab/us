# P17.2.5 XBRL Context Security Reconciliation

Date: 2026-11-20
Branch: `research/p17-2-5-xbrl-context-security-mapping`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **VERIFIED_CONTEXT_MAPPING (16/16 point observations)**

## 1. What changed

P17.2.4's conflicts were caused by taking the first title in the filing, not the
title in the ticker's own context. Re-parsing the 8 primary Inline XBRL documents
with exact `contextRef` pairing resolves them.

```text
filings: 8
contexts: 3,043
DEI facts: 321
ticker points: 16
VERIFIED_SECURITY_TICKER_POINT: 16
unresolved: 0
unique tickers: 9
verified intervals: 0
```

## 2. Alphabet

| ticker | title | class context |
|---|---|---|
| GOOG | Class C Capital Stock, $0.001 par value | separate context |
| GOOGL | Class A Common Stock, $0.001 par value | separate context |

GOOG and GOOGL are in different contexts in both 2023 filings. P17.2.4's
"GOOG conflict" is withdrawn.

## 3. NEE

| ticker | title | class member |
|---|---|---|
| NEE | Common Stock, $0.01 Par Value | default/common |
| NEE.PRO | 4.872% Corporate Units | nee:CorporateUnitsMember |
| NEE.PRP | 5.279% Corporate Units | nee:CorporateUnits5.279Member |
| NEE.PRQ | 6.219% Corporate Units | nee:CorporateUnits6.219Member |
| NEE.PRR | 6.926% Corporate Units | nee:CorporateUnits6926Member |

All four preferred/corporate-unit labels have their own title and
`StatementClassOfStockAxis` context. They are not common stock.

## 4. AAPL / NVDA

AAPL and NVDA each pair a single TradingSymbol with Common Stock title, exchange,
CIK and acceptance metadata. No multi-class ambiguity.

## 5. CIK

Issuer CIK is populated from the XBRL context, not from the accession prefix:

- AAPL 0000320193
- NEE 0000753308
- NVDA 0001045810
- GOOG 0001652044

NEE filings contain Florida Power & Light as a co-registrant (CIK
0000037634) in the submission header; security facts remain under the NextEra
context and are not merged.

## 6. Time

Raw acceptance, UTC and America/New_York are retained from the P17.2.3 header
evidence. Acceptance is an evidence time only; no `valid_from` is inferred.

## 7. Decision

```text
P17_2_5_CONTEXT_MAPPING = PASS
P17_2_5_VERIFIED_SECURITY_POINTS = 16
P17_2_5_UNRESOLVED = 0
P17_2_5_VERIFIED_INTERVALS = 0
P17_2_5_OVERALL = SECURITY_POINT_VERIFIED / INTERVAL_NOT_VERIFIED
```

This is still a point-in-time panel, not a complete historical identity panel.

## 8. Files

- `tools/research/p17_2_5_xbrl_context_mapping.py`
- `tests/test_p17_2_5_xbrl_context_mapping.py`
- `data/research/p17_2_5/p17_2_5_raw_xbrl_facts.csv`
- `p17_2_5_context_registry.csv`
- `p17_2_5_fact_context_join.csv`
- `p17_2_5_ticker_security_mapping.csv`
- `p17_2_5_issuer_cik_reconciliation.csv`
- `p17_2_5_alphabet_class_audit.csv`
- `p17_2_5_nee_preferred_audit.csv`
- `p17_2_5_verified_security_points.csv`
- `p17_2_5_unresolved_candidates.csv`
- `p17_2_5_security_conflicts.csv`
- `p17_2_5_coverage_summary.json`
- `p17_2_5_summary.json`
- `p17_2_5_manifest.json`

No alpha, NAV, trade ledger, or production change.
