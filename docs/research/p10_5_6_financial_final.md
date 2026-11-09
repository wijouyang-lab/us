# P10.5.6 Financial History Finalization

Date: 2026-11-09
Status: **P10_5_6_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Unit normalization and amendment result

Normalized `USDperShareItemType` and `iso4217_USD_per_shares` to `USD/share`;
`USD`/`iso4217_USD` to `USD`.

30 rows:

| Final status | Count |
|---|---:|
| TRUE_NUMERIC_CHANGE_CANDIDATE | 13 |
| NORMALIZED_EQUAL | 11 |
| DUPLICATE_FACT | 6 |
| **Total** | **30** |

The 13 numeric candidates are real comparative values from the FY2009 10-K/A
versus the earlier FY2008 10-K, e.g.:

- Basic EPS 5.48 -> 6.94
- Diluted EPS 5.36 -> 6.78
- Gross Profit 11.145B -> 13.197B
- Operating Income 6.275B -> 8.327B
- Sales Revenue 32.479B -> 37.491B

This is not a unit artifact. It is a real disclosed comparative change and is
kept as `TRUE_NUMERIC_CHANGE_CANDIDATE`, not automatically called an accounting
restatement.

## 2. Real as-of tests

For each of the 13 candidates, two queries were made:

- before amendment availability: returns original accession/value;
- after amendment availability: returns amendment accession/value.

```text
BEFORE_AMENDMENT: 13 PASS
AFTER_AMENDMENT:  13 PASS
```

The query filters by field + period start + period end, not just field.

## 3. Form 25-NSE

45 rows preserved:

- 39 ETF/Trust;
- 6 unresolved;
- ordinary common stock verified: 0.

Ordinary Form 25 was not ingested in this run. No delisting list was fabricated.

## 4. Panel

Prior 472-row quarterly panel and 12 Q4 derivations are preserved. The final
panel is still PARTIAL because:

- panel grain/field coverage not fully closed;
- 24 old unit rows are now explained, but two complete fiscal years of all core
  fields are not yet proven clean.

## 5. Manifest

`run_manifest_pre.json` and `run_manifest.json` with output hashes.

## 6. Decision

```text
P10_5_6_PARTIAL
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## 7. Files

```text
data/research/p10_5_6_financial_final/
  amendment_unit_normalization_final.csv
  amendment_comparison_final_v2.csv
  real_asof_query_tests.csv
  aapl_asof_full_accession_tests.csv
  form25_nse_45_final.csv
  form25_nse_unresolved_audit.csv
  form25_accessions.csv
  form25_issuer_evidence.csv
  historical_common_stock_delisting_audit.csv
  run_manifest_pre.json
  run_manifest.json
  p10_5_6_status.json
docs/research/p10_5_6_financial_final.md
tests/test_p10_5_6_financial_final.py
```
