# P10.5.16 Fact Lineage Closure

Date: 2026-11-10
Status: **P10_5_16_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Annual EPS

Ten annual input facts were extracted from the two 10-Ks:

- Net Income;
- Basic weighted-average shares;
- Diluted weighted-average shares;
- Basic EPS;
- Diluted EPS.

Using Decimal:

| FY | Basic recalc | Diluted recalc | Status |
|---|---:|---:|---|
| 2018 | 12.0134 | 11.9059 | PASS |
| 2019 | 11.9658 | 11.8859 | PASS |

No quarter EPS sum was used.

## 2. Cash-flow lineage

16 OCF/Capex fact rows reconstructed. 10 have a usable context; 6 still lack
context. FCF remains derived from OCF - Capex.

## 3. Note 12 HTML probe

Actual 10-K URL requested; `pandas.read_html` failed with HTML parse error.
No row/column locator was fabricated.

```text
html_note_locators: 0
note12_status: HTML_PARSE_ERROR
```

The existing 40 XBRL secondary facts remain as a separate check.

## 4. Context gaps

```text
core cells:            72
context gaps:          43
fact-level traceable:  29
```

The 43 gaps remain unresolved; no generic context string is promoted to
traceable.

## 5. Gross margin PRE

`aapl_gross_margin_pre_audit.csv` marks all 8 quarters as
`PRE_NOT_PARSED`; no PRE evidence is claimed.

## 6. Decision

```text
P10_5_16_PARTIAL
AAPL_DATASET_READY = false
AAPL_FACT_PIT_READY = true (FY2008 limited)
HISTORICAL_UNIVERSE_READY = false
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## 7. Files

```text
data/research/p10_5_16_aapl_panel/
  aapl_annual_eps_input_facts.csv
  aapl_annual_eps_reconciliation_v2.csv
  aapl_cashflow_lineage_v6.csv
  aapl_40_secondary_v6.csv
  aapl_40_html_note_crosscheck.csv
  aapl_context_audit_v6.csv
  aapl_gross_margin_pre_audit.csv
  note12_html_probe.json
  p10_5_16_status.json
docs/research/p10_5_16_lineage_closure.md
tests/test_p10_5_16_lineage_closure.py
```
