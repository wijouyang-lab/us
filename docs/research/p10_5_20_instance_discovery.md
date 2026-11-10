# P10.5.20 SEC Instance Discovery and Eight-Filing Closure

Date: 2026-11-10
Status: **P10_5_20_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Discovery fixed

The prior code only looked for `*_htm.xml`. Old filings use names such as
`aapl-20171230.xml`, so they were incorrectly reported missing.

This run discovers instance candidates from each accession's `index.json`
without requiring `_htm.xml`, excluding CAL/DEF/LAB/PRE/XSD.

```text
packages requested:       8
packages available:       8
instances verified:       8
contexts parsed:       2,551
facts parsed:         8,707
```

## 2. Cash-flow contexts

```text
cashflow inputs:            16
period matches:             16
contextRefs verified:       16
cashflow metric cells exact: 24/24
```

All 16 OCF/Capex inputs now have one unique context candidate with matching
start/end and no dimensions.

## 3. Core 72-cell lineage

```text
core cells:                 72
FACT_LEVEL_VERIFIED:        44
DERIVED_LINEAGE_VERIFIED:   28
LINEAGE_INCOMPLETE:          0
```

Direct facts: Revenue/GrossProfit/NetIncome/EPS plus Q4 OI inputs.
Derived: 24 cash-flow cells, 2 Q4 Operating Income, 2 FY2019 Products+Services
revenue cells.

## 4. HTML/XBRL

40/40 preserved.

## 5. Gross margin PRE

0/8; `PRE_UNRESOLVED`. Linkbase parsing not completed.

## 6. EPS

4/4 annual metrics PASS retained.

## 7. Not done

- Gross margin PRE/LAB audit;
- finalizer offline temp rerun;
- PRE_RUN/POST_RUN manifest;
- independent review of every derived lineage field.

```text
P10_5_20_PARTIAL
AAPL_DATASET_READY = false
AAPL_FACT_PIT_READY = true (FY2008 limited)
HISTORICAL_UNIVERSE_READY = false
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.
