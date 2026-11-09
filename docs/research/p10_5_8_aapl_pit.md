# P10.5.8 AAPL PIT Panel Finalization

Date: 2026-11-09
Status: **P10_5_8_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. 63 accession availability

Filled the 23 missing trade-available dates from the P10.3 accession metadata.

```text
accessions:                 63
with timestamp:             63
missing source timestamp:    0
no-lookahead rows:          63
```

A/B rules preserved: A = next executable session; B = one full session later.
All remain `PIT_ACCEPTANCE_PROXY`.

## 2. Panel

472 rows. Grain now documented as:

```text
CIK + fiscal_year + fiscal_period + canonical_field
+ accounting_version + source_accession
```

A/B dates are separate attributes, not duplicate rows.

`accounting_version` is present, but the panel still lacks the full FY2008
original/adjusted QTD separation across every field.

## 3. FY2008 accounting versions

13 real numeric candidates retained with:

- original accession `0001193125-09-214859`;
- amendment `0001193125-10-012091`;
- event `RETROSPECTIVE_ACCOUNTING_POLICY_ADOPTION`;
- original and adjusted values.

## 4. Form 25-NSE

45 rows: 39 ETF/Trust, 6 unresolved. The 6 remain unresolved because the
original security document was not parsed. Ordinary Form 25 not ingested.

## 5. Decision

```text
P10_5_8_PARTIAL
P10_6_ALLOWED = false
```

Blocked: full two-fiscal-year core panel, 6 Form 25-NSE security docs.

No Shadow, no IBKR, no PAPER-50000.

## 6. Files

```text
data/research/p10_5_8_aapl_pit/
  aapl_63_accession_availability_final.csv
  aapl_63_accession_no_lookahead_final.csv
  aapl_timestamp_missingness_audit.csv
  aapl_availability_status.json
  aapl_quarterly_panel_v2.csv
  aapl_panel_grain_audit.csv
  aapl_panel_duplicate_audit.csv
  aapl_panel_version_audit.csv
  apple_accounting_versioned_facts.csv
  apple_policy_adoption_version_timeline.csv
  apple_accounting_version_tests.csv
  aapl_two_fy_quarterly_final.csv
  aapl_quarterly_annual_reconciliation.csv
  aapl_core_field_coverage.csv
  aapl_q4_derivation_final.csv
  aapl_two_fy_status.json
  aapl_revenue_presentation_audit.csv
  aapl_gross_profit_final_audit.csv
  aapl_canonical_mapping_final.csv
  form25_nse_45_final_v2.csv
  form25_nse_unresolved_resolution.csv
  run_manifest_pre.json
  run_manifest.json
  p10_5_8_status.json
docs/research/p10_5_8_aapl_pit.md
tests/test_p10_5_8_aapl_pit.py
```
