# P10.5.3 Execution Recovery

Date: 2026-11-09
Status: **P10_5_3_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. Actual SEC downloads

Three real ZIPs were requested, received, ZIP-tested and parsed:

| Quarter | Bytes | SUB | NUM | ZIP |
|---|---:|---:|---:|---:|
| 2009q2 | 144,894 | parsed | parsed | OK |
| 2019q4 | 98,753,299 | parsed | parsed | OK |
| 2024q1 | 124,336,804 | parsed | parsed | OK |

The 2009q2 file is very small; that is an actual file property, not a
fabricated empty response.

NUM schema probe:

- all three quarters contain `segments` in the parsed schema;
- no claim is made that older semantics are identical.

## 2. AAPL fact consolidation

Combined real accession facts from:

- P10.3 40 separate-XBRL AAPL filings;
- P10.2 23 inline-XBRL AAPL filings.

```text
facts: 9,327
```

No Company Facts backfill.

## 3. Amendment comparison

AAPL amendments present:

```text
10-K/A: 1
10-Q/A: 1
```

Comparison of same field + period found 30 matching rows:

```text
numeric differences: 19
text-only:           11
```

Important: the 19 “numeric differences” are **not yet verified as true
restatements**. They may be duplicate facts, unit/scale issues, period
misalignment, or comparison against the wrong base accession. They are retained
for review, not promoted to `NUMERIC_RESTATEMENT` truth.

`real_asof_query_tests.csv` therefore has no verified PASS case. Real numeric
restatement testing remains DATA_BLOCKED.

## 4. EDGAR Form 25 search

Actual request:

```text
URL: https://efts.sec.gov/LATEST/search-index?q=%22FORM%2025-NSE%22
HTTP: 200
bytes: 60,975
total hits: 3,663
```

The search endpoint is reachable. However, this run did not parse the hit list
into issuer/subject CIK pairs or verify ordinary-share delistings. Therefore:

```text
delisting_evidence.csv = empty
verified delisted companies = 0
```

No NYSE/Nasdaq filer CIK is used as an issuer CIK.

## 5. Sample

P10.5 120 parsed accessions remain `PARSER_VALIDATION_SAMPLE`.
A 10-company subset is retained as `P10_5_3_VALIDATION_ONLY`; it is not a
delisted-inclusive historical sample.

## 6. Not completed

- verified delisted companies;
- real numeric restatement lineage;
- real as-of historical query;
- real QTD/YTD/FY derivation;
- compliant 30-company historical sample.

## 7. Decision

```text
P10_5_3_PARTIAL
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## 8. Files

```text
data/research/p10_5_3_execution_recovery/
  download_log.json
  aapl_quarterly_dataset_manifest.csv
  sec_num_schema_diff.csv
  aapl_historical_financial_facts.csv
  aapl_financial_field_coverage.csv
  aapl_fact_source_audit.json
  restatement_lineage.csv
  fact_version_history.csv
  real_asof_query_tests.csv
  edgar_search_log.json
  edgar_form25_search_results.csv
  delisting_evidence.csv
  valid_sample_10_accessions.csv
  p10_5_3_status.json
docs/research/p10_5_3_execution_recovery.md
tests/test_p10_5_3_execution.py
```
