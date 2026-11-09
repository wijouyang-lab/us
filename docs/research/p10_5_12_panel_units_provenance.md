# P10.5.12 AAPL Panel Units and Provenance

Date: 2026-11-09
Status: **P10_5_12_PARTIAL**
P10.6: **NOT AUTHORIZED**

## Fixed

- Cash-flow values are no longer double-scaled. OCF/Capex/FCF 24 cells use
  USD millions once.
- OCF/Capex/FCF max absolute difference against P10.5.10 independent targets = 0.
- Quarterly source accessions for Q1-Q3 use the period-specific 10-Q accessions;
  no Q1-Q3 cell uses FY2019/FY2018 10-K accession.
- Q4 values use the FY 10-K quarter context where available.

## Still incomplete

- 72 cells exist, but 11 are `UNRESOLVED` because the period-specific 10-Q
  facts do not contain a match for Revenue in FY2018 Q1-Q3 and some FY2019 Q4
  fields.
- Revenue tag coverage in those 10-Qs remains unresolved; not filled from the
  later 10-K comparative accession.
- Gross Profit direct/derived separation and PRE verification still incomplete.
- `AAPL_DATASET_READY=false`.

```text
AAPL_FACT_PIT_READY = true (FY2008 limited scope)
HISTORICAL_UNIVERSE_READY = false
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## Files

```text
data/research/p10_5_12_aapl_panel/
  aapl_two_fy_panel_final_v2.csv
  aapl_72_provenance_audit.csv
  aapl_cell_validation.csv
  aapl_unit_audit.csv
  aapl_cashflow_unit_check.csv
  aapl_bad_accessions.csv
  p10_5_12_status.json
docs/research/p10_5_12_panel_units_provenance.md
tests/test_p10_5_12_panel_units.py
```
