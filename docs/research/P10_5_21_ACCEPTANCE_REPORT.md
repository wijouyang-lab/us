# P10.5.21 AAPL 2018–2019 Dataset Acceptance

Date: 2026-11-10

## Status

```text
CORE_DATASET_ACCEPTED     = true
GROSS_MARGIN_AUDIT_PARTIAL = true
AAPL_DATASET_READY        = false
HISTORICAL_UNIVERSE_READY = false
P10_6_AUTHORIZED          = false
```

The 72 core cells are accepted for the AAPL FY2018/FY2019 sample only.
Gross Margin PRE/LAB audit remains unresolved. This is not a market-wide
dataset or a strategy authorization.

## 1. Core classification

| Transformation | Count |
|---|---:|
| DIRECT_FACT | 48 |
| RECONSTRUCTED_FROM_CUMULATIVE_FACTS | 12 |
| DERIVED_FORMULA (FCF) | 8 |
| DERIVED_FROM_ANNUAL_MINUS_9M | 2 |
| RECONSTRUCTED_FROM_COMPONENTS | 2 |
| **Total** | **72** |

Q1 OCF/Capex are treated as direct Q1 facts. Q2–Q4 OCF/Capex are cumulative
differences. FCF is OCF minus Capex. Q4 Operating Income is FY minus 9M.
FY2019 Q2/Q3 Revenue is Products plus Services.

## 2. Legacy crosswalk

29 old provisional context records were mapped by
accession + metric + fiscal period + context to v10.

```text
legacy_rows:   29
mapped:        29
unresolved:     0
```

## 3. Gross margin

```text
quarters audited:   8
resolved:           0
unresolved:         8
```

Reason: PRE/LAB linkbase parsing was not completed. Values are retained but not
claimed as a completed Gross Margin audit.

## 4. Offline finalizer

The finalizer ran with `--offline` from local inputs. A second run in a fresh
temporary directory produced byte-identical deterministic CSVs.

```text
all_equal: true
```

PRE_RUN and POST_RUN evidence is in
`aapl_dataset_run_manifest.json`; the pre-run snapshot is also separate.

## 5. Deliverables

```text
data/research/p10_5_21_aapl_dataset/
  aapl_fundamentals_2018_2019.csv
  aapl_fundamentals_lineage.csv
  aapl_legacy_lineage_crosswalk.csv
  aapl_gross_margin_audit.csv
  aapl_dataset_run_manifest.json
  aapl_dataset_run_manifest_pre.json
  p10_5_21_status.json
docs/research/P10_5_21_ACCEPTANCE_REPORT.md
```

## 6. Not authorized

No Shadow, no IBKR, no PAPER-50000, no production deployment, no PR merge,
and no P10.6.
