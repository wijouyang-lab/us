# P10.5.10 AAPL FY2018/FY2019 Cash-Flow Panel

Date: 2026-11-09
Status: **P10_5_10_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Cash flow reconstruction

Using real accessions:

- FY2018 Q1/Q2/Q3/FY;
- FY2019 Q1/Q2/Q3/FY.

OCF QTD:

```text
Q1 = direct
Q2 = H1 - Q1
Q3 = 9M - H1
Q4 = FY - 9M
```

Capex uses cash-flow statement `PaymentsToAcquirePropertyPlantAndEquipment`,
positive outflow; FCF = OCF - Capex.

All 8 quarters match the supplied independent targets exactly after converting
to USD millions.

## 2. Panel

9 metrics × 8 quarters = 72 cells produced.

However, Q4 `OperatingIncomeLoss` was derived from FY minus Q1–Q3 and the
resulting value is inconsistent with the source period semantics. It is not
accepted as research-ready. Therefore:

```text
P10_5_10_PARTIAL
AAPL_DATASET_READY = false
```

## 3. READY

```text
AAPL_DATASET_READY:        false
AAPL_FACT_PIT_READY:       true (FY2008 tested set)
HISTORICAL_UNIVERSE_READY: false
P10_6:                     NOT AUTHORIZED
```

No Shadow, no IBKR, no PAPER-50000.

## 4. Files

```text
data/research/p10_5_10_aapl_cashflow/
  aapl_two_fy_panel_complete.csv
  aapl_two_fy_field_matrix.csv
  aapl_cashflow_quarterly_reconstruction.csv
  aapl_cashflow_reconciliation.csv
  aapl_capex_sign_audit.csv
  aapl_two_fy_metric_reconciliation.csv
  aapl_accounting_basis_final.csv
  aapl_two_fy_asof_tests.csv
  run_manifest_pre.json
  run_manifest.json
  p10_5_10_status.json
docs/research/p10_5_10_aapl_cashflow.md
tests/test_p10_5_10_cashflow.py
```
