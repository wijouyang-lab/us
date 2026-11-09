# P10.5.18 Final Lineage Validation

Date: 2026-11-10
Status: **P10_5_18_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Cash-flow inputs

```text
rows:                    16
period dates correct:    16
context ID present:      10
context ID missing:       6
context verified in XBRL: 0
```

The six missing context IDs were not invented. Period dates match, but
fact-level context verification is not complete.

## 2. Cash-flow quarterly values

24/24 OCF/Capex/FCF cells exact; max diff 0.

## 3. Core panel lineage

```text
core cells:          72
fact-level verified:  0
lineage incomplete:  72
```

No row is promoted to fact-level verified without an actual contextRef check.

## 4. HTML vs XBRL

40 HTML cells parsed from tables 84/85; merged against 40 secondary XBRL facts:

```text
HTML cells:          40
HTML-XBRL match:     40
mismatch:             0
```

This is still a same-issuer filing cross-check, not third-party validation.

## 5. Gross margin PRE

0/8; all `PRE_UNRESOLVED`.

## 6. EPS

4/4 annual EPS metrics remain PASS.

## 7. Not done

- finalizer offline temp rerun;
- PRE_RUN / POST_RUN manifest;
- real contextRef verification for 6 missing cash-flow facts;
- Gross margin PRE/label audit.

```text
P10_5_18_PARTIAL
AAPL_DATASET_READY = false
AAPL_FACT_PIT_READY = true (FY2008 limited)
HISTORICAL_UNIVERSE_READY = false
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## 8. Files

```text
data/research/p10_5_18_aapl_panel/
  aapl_cashflow_fact_inputs_v8.csv
  aapl_cashflow_quarterly_lineage_v8.csv
  aapl_core_panel_v8.csv
  aapl_fact_lineage_v8.csv
  aapl_40_html_xbrl_reconciliation_v3.csv
  aapl_gross_margin_pre_audit_v3.csv
  aapl_annual_eps_reconciliation_v2.csv
  aapl_context_audit_v8.csv
  p10_5_18_status.json
docs/research/p10_5_18_lineage_validation.md
tests/test_p10_5_18_lineage_validation.py
```
