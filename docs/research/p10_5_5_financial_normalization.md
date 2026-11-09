# P10.5.5 Normalized AAPL Facts and Form 25 Classification

Date: 2026-11-09
Status: **P10_5_5_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. AAPL normalized data

From 9,327 real accession facts:

- normalized fact table with canonical fields, period type, fiscal year,
  quarter, unit, context and source hash;
- quarterly panel: 472 rows;
- 11 fiscal years with Q1-Q4 QTD records;
- 12 Q4 derivations: FY − Q1 − Q2 − Q3;
- revenue tag audit, gross profit audit, missingness and reconciliation.

Revenue tags remain multiple concepts; no unconditional addition.

## 2. Amendment comparison

30 rows preserved:

```text
UNIT_MISMATCH: 24
DUPLICATE_FACT: 6
TRUE_NUMERIC_CHANGE: 0
```

Final classification does **not** claim a numeric restatement. AmendmentFlag is
`FLAG_NOT_PRESENT` because it was not parsed from the original amendment.

## 3. Form 25-NSE

45 exact-form records:

- subject CIK candidate retained;
- security type classified from display name where possible;
- ordinary common stock exits verified: **0**;
- ordinary Form 25 not yet ingested;
- no delisting evidence table fabrication.

## 4. Real as-of

Using real accession `trade_available_date` values, 4 query cases were run. They
verify that a query returns only an accession available by that date. This is a
real-timeline smoke test, not a full historical fact-version chain.

## 5. Manifest

Pre-run capture plus post-run output hashes:

```text
run_manifest_pre.json
run_manifest.json
manifest_capture_mode = PRE_RUN_PLUS_POST_RUN
```

## 6. Decision

```text
P10_5_5_PARTIAL
P10_6_ALLOWED = false
```

Remaining: ordinary Form 25, verified common-stock exits, true numeric
restatement chain, complete historical identity map.

No Shadow, no IBKR, no PAPER-50000.

## 7. Files

```text
data/research/p10_5_5_financial_normalization/
  aapl_normalized_facts.csv
  aapl_normalized_quarterly_panel.csv
  aapl_field_mapping.csv
  aapl_missingness_audit.csv
  aapl_quarterly_reconciliation.csv
  aapl_revenue_mapping_audit.csv
  aapl_gross_profit_mapping_audit.csv
  aapl_qtd_ytd_derivation.csv
  amendment_comparison_final.csv
  amendment_unit_normalization.csv
  duplicate_fact_audit.csv
  amendment_flag_final.csv
  form25_nse_subject_audit.csv
  form25_security_type_audit.csv
  historical_common_stock_exit_candidates.csv
  historical_common_stock_exit_verified.csv
  historical_member_exit_intersection.csv
  real_asof_query_tests.csv
  run_manifest_pre.json
  run_manifest.json
  p10_5_5_status.json
docs/research/p10_5_5_financial_normalization.md
tests/test_p10_5_5_normalization.py
```
