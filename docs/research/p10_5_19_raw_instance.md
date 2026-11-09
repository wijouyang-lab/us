# P10.5.19 Raw XBRL Instance Verification

Date: 2026-11-09
Status: **P10_5_19_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. SEC packages

8 accession packages downloaded and parsed:

```text
packages:           8
contexts parsed:  1,004
facts parsed:     3,596
```

Inventory: `sec_package_inventory.csv`.

## 2. Cash-flow context

```text
input rows:                16
period matches:            16
context verified in XBRL:   6
metric cells exact:        24/24
```

The six restored contexts are:

- FY2019 H1 OCF/Capex -> `FD2019Q2YTD`;
- FY2019 9M OCF/Capex -> `FD2019Q3YTD`;
- FY2019 FY OCF/Capex -> `FD2019Q4YTD`.

The other 10 inputs were not verified: the raw-instance matcher returned zero
candidates for 2018 and 2019 Q1, likely due context/period serialization. They
are not marked verified.

## 3. Core panel

```text
core cells:          72
fact-level verified:  0
lineage incomplete:  72
```

Cash-flow cells are not promoted merely because 6 input contexts were found;
quarterly FCF cells still lack a complete two-input verification chain.

## 4. HTML/XBRL

40/40 remain matched from P10.5.18.

## 5. Gross margin PRE

0/8; all `PRE_UNRESOLVED`.

## 6. EPS

4/4 annual metrics PASS.

## 7. Not done

- Full 72-cell contextRef verification;
- Gross margin PRE/LAB;
- finalizer offline rerun;
- PRE_RUN/POST_RUN manifests.

```text
P10_5_19_PARTIAL
AAPL_DATASET_READY = false
AAPL_FACT_PIT_READY = true (FY2008 limited)
HISTORICAL_UNIVERSE_READY = false
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.
