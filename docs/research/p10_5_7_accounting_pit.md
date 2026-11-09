# P10.5.7 Apple Retrospective Accounting Adjustment PIT Validation

Date: 2026-11-09
Status: **P10_5_7_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Accounting event

Original 10-K:

```text
0001193125-09-214859
```

Amendment:

```text
0001193125-10-012091
```

The amendment primary document was fetched and SHA-256 recorded. It contains
"retrospective" and "adoption" language.

Event classification:

```text
RETROSPECTIVE_ACCOUNTING_POLICY_ADOPTION
```

Not classified as an error restatement.

## 2. Real version switch

Five FY2008 fields, four query dates:

| Query | Expected |
|---|---|
| 2009-10-28 | original 10-K |
| 2010-01-25 | original 10-K |
| 2010-01-26 | amendment A |
| 2010-01-27 | amendment A/B |

Actual examples:

```text
Basic EPS: 5.48 (original) -> 6.94 (amendment)
Diluted EPS: 5.36 -> 6.78
Sales: 32.479B -> 37.491B
Gross Profit: 11.145B -> 13.197B
Operating Income: 6.275B -> 8.327B
```

20/20 query rows returned the expected accession/value.

## 3. 63 accession no-lookahead

Only 40 accessions had usable trade-availability dates in the parsed facts, so
the audit produced 40 rows, not 63. This is a real coverage limitation.

## 4. Panel

472 rows preserved. Panel grain/version separation is not final:

- FY2008 original and retrospective-adjusted values are both preserved in facts;
- final panel does not yet guarantee one version per as-of date for every field;
- two complete fiscal years of all core fields are not certified.

## 5. Form 25-NSE

45 rows preserved: 39 ETF/Trust, 6 UNRESOLVED. The 6 remain unresolved because
original filing detail/security class parsing was not completed. No ordinary
stock delisting claimed.

## 6. Decision

```text
P10_5_7_PARTIAL
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## 7. Files

```text
data/research/p10_5_7_accounting_pit/
  filing_evidence.json
  apple_accounting_change_evidence.csv
  apple_retrospective_adjustment_reconciliation.csv
  apple_accounting_event.json
  apple_real_version_history.csv
  apple_policy_adoption_asof_tests.csv
  aapl_63_accession_no_lookahead.csv
  aapl_quarterly_panel_final.csv
  aapl_panel_status.json
  form25_nse_45_final.csv
  form25_nse_unresolved_final.csv
  run_manifest_pre.json
  run_manifest.json
  p10_5_7_status.json
docs/research/p10_5_7_accounting_pit.md
tests/test_p10_5_7_accounting_pit.py
```
