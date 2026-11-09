# P10.5.9 AAPL Versioned Panel Finalization

Date: 2026-11-09
Status: **P10_5_9_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Panel v3

- 472 rows.
- Grain: `CIK + fiscal_year + fiscal_period + canonical_field + accounting_basis + source_accession`.
- A/B timestamps remain attributes, not duplicate rows.
- Original and retrospective-adjusted facts remain separate.

`AAPL_DATASET_READY = false`: FY2018/FY2019 two-year subset has 62 rows but not
all core fields with Q1–Q4; OCF/Capex/FCF coverage is incomplete.

## 2. FY2008 accounting version

Original accession `0001193125-09-214859`; amendment `0001193125-10-012091`.

20/20 fact-level as-of tests pass for five FY2008 fields across four dates.
Original values before 2010-01-26; adjusted values after.

`AAPL_FACT_PIT_READY = true` for this tested set, not all fields/periods.

## 3. Form 25-NSE

6 remaining records were probed via accession index JSON. Security class still
not resolved because the original security document was not parsed. They remain
`UNRESOLVED`; 39 ETF/Trust are preserved.

## 4. Status

```text
AAPL_DATASET_READY:      false
AAPL_FACT_PIT_READY:     true (20 FY2008 tests)
HISTORICAL_UNIVERSE_READY: false
P10_6_ALLOWED:           false
```

No Shadow, no IBKR, no PAPER-50000.

## 5. Files

```text
data/research/p10_5_9_aapl_panel/
  aapl_quarterly_panel_v3.csv
  aapl_panel_grain_final.csv
  aapl_panel_duplicate_final.csv
  aapl_panel_version_final.csv
  aapl_two_fy_panel_final.csv
  aapl_two_fy_quarterly_reconciliation.csv
  aapl_field_coverage_final.csv
  aapl_accounting_basis_audit.csv
  aapl_fact_level_asof_tests.csv
  aapl_fact_availability_audit.csv
  form25_nse_unresolved_final.csv
  form25_nse_45_final_v3.csv
  run_manifest_pre.json
  run_manifest.json
  p10_5_9_status.json
docs/research/p10_5_9_aapl_panel.md
tests/test_p10_5_9_aapl_panel.py
```
