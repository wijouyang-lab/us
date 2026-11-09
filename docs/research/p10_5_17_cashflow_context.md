# P10.5.17 Cash-Flow Period Selection and Note 12 HTML Locators

Date: 2026-11-10
Status: **P10_5_17_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Cash flow

Rebuilt from exact accession + context start/end, not `iloc[0]`:

| FY | Q1 | Q2 | Q3 | Q4 |
|---|---:|---:|---:|---:|
| 2018 OCF | 28,293 | 15,130 | 14,488 | 19,523 |
| 2018 Capex | 2,810 | 4,195 | 3,267 | 3,041 |
| 2019 OCF | 26,690 | 11,155 | 11,636 | 19,910 |
| 2019 Capex | 3,355 | 2,363 | 2,000 | 2,777 |

```text
cashflow inputs:       16
period matches:        16 (by exact dates)
context IDs present:   10
context IDs missing:    6
quarterly cells:       24
exact:                 24/24
max diff:               0
```

FCF = OCF - Capex. The six missing context IDs are not fabricated.

## 2. Note 12 HTML

Fixed the pandas call using `BytesIO`.

```text
HTTP 200
HTML bytes: 2,714,204
HTML cells parsed: 40
HTML locators:     40
```

Tables 84 (FY2019) and 85 (FY2018); row/column and cell locators stored.
Values are parsed from the HTML cell text, not copied from XBRL.

## 3. Remaining context gaps

```text
context gaps:          43
fact-level traceable:  29
```

The 43 gaps are not fixed; no generic context was promoted to real contextRef.

## 4. Gross margin PRE

Still `PRE_UNRESOLVED` for all 8 quarters; no PRE/label audit claimed.

## 5. Finalizer/Manifest

No temporary-directory rerun and no PRE/POST manifest in this run.

## 6. Status

```text
P10_5_17_PARTIAL
AAPL_DATASET_READY = false
AAPL_FACT_PIT_READY = true (FY2008 limited)
HISTORICAL_UNIVERSE_READY = false
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## 7. Files

```text
data/research/p10_5_17_aapl_panel/
  aapl_core_panel_v7.csv
  aapl_cashflow_fact_inputs_v7.csv
  aapl_cashflow_quarterly_lineage_v7.csv
  aapl_40_html_note_crosscheck_v2.csv
  aapl_context_audit_v7.csv
  aapl_gross_margin_pre_audit_v2.csv
  aapl_annual_eps_reconciliation_v2.csv
  p10_5_17_status.json
docs/research/p10_5_17_cashflow_context.md
tests/test_p10_5_17_cashflow_context.py
```
