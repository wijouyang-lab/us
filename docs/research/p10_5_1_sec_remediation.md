# P10.5.1 SEC Coverage Remediation Audit

Date: 2026-11-09
Status: **P10_5_1_DATA_BLOCKED**
P10.6: **NOT AUTHORIZED**

## 1. What is preserved

P10.5's 120 parsed accessions are retained as:

```text
PARSER_VALIDATION_SAMPLE
```

They are not deleted and not re-parsed. They are **not** a valid historical
research sample because they were selected from the current SEC ticker map.

## 2. AAPL 66 filings

```text
required dataset quarters: 64
downloaded:                1 (2024q1)
DATASET_MATCHED:           1
NOT_IN_DATASET:            65
PRE_DATASET_COVERAGE_START: filings before 2009-04-15
```

65 are **not downloaded**, not “SEC has no historical data”. Every filing has a
final status.

## 3. 30-company remediation

Reclassification result:

```text
companies:                  30
PARSER_VALIDATION_SAMPLE:   30
valid historical sample:    0
historical delisted:        0
accessions parsed:          120
```

`historical_cik_mapping_verified.csv` and `delisted_company_evidence.csv` are
empty because no verified delisted-inclusive identity map exists in the
repository.

This fails the 10 early-XBRL / 10 Inline / 10 delisted design.

## 4. Field and version status

- P10.5 18-field coverage preserved.
- Revenue and Gross Profit still have multiple tags and incomplete coverage.
- `restatement_lineage.csv` remains empty; no real accession lineage.
- `financial_period_derivation.csv` remains empty; no real QTD/YTD.
- `get_facts_as_of` is implemented only for a synthetic unit test; it is **not**
  applied to a verified historical dataset.

## 5. PIT

A/B acceptance proxies preserved. No `PIT_PUBLICATION_VERIFIED`.

## 6. Decision

```text
P10_5_1_DATA_BLOCKED
P10_6_ALLOWED: NO
```

Reasons:

1. only 1 of 64 AAPL quarters downloaded;
2. no verified delisted companies;
3. no historical CIK identity evidence;
4. no real restatement lineage;
5. no real QTD/YTD derivation.

Do not start P10.6. No Shadow, no IBKR, no PAPER-50000.

## 7. Files

```text
data/research/p10_5_1_sec_remediation/
  aapl_all_accession_final_match.csv
  aapl_quarterly_dataset_manifest.csv
  aapl_accession_fact_coverage.csv
  aapl_dataset_reconciliation.csv
  aapl_dataset_status.json
  historical_sample_selection.csv
  historical_cik_mapping_verified.csv
  delisted_company_evidence.csv
  valid_sample_accessions.csv
  valid_sample_parse_coverage.csv
  restatement_lineage.csv
  asof_query_test_results.csv
  financial_period_derivation.csv
  pit_availability_audit.csv
  run_manifest.json
  data_manifest.json
  p10_5_1_status.json
docs/research/p10_5_1_sec_remediation.md
tests/test_p10_5_1_remediation.py
```
