# P10.4 SEC Financial Statement Data Sets Integration

Date: 2026-11-09
Status: **P10_4_SEC_DATASET_PARTIAL**
Strategy ready: **NO**

## 1. Actual download

```text
dataset:      2024q1
URL:          https://www.sec.gov/files/dera/data/financial-statement-data-sets/2024q1.zip
bytes:        124,336,804
sha256:       94c7894b00903f8ff7186c4250ba1c1daa1bde8b3a0b26fae68f72608b2ffc9b
unzipped:     yes
```

Parsed tables:

```text
SUB:  6,028 rows
NUM:  3,428,694 rows
TAG:  parsed
PRE:  parsed
```

The raw 590 MB of extracted CSV and the 124 MB zip are not committed; the
download manifest records URL, quarter, size, SHA-256, download time and parser
version.

## 2. AAPL accession matching

Minimal downloaded set: only 2024q1.

Of the 66 AAPL filings:

```text
MATCHED in downloaded dataset:       1  (0000320193-24-000006)
NOT_IN_DOWNLOADED_DATASET:          65
```

The 65 missing are **not** marked as failed or matched; they are explicitly
`NOT_IN_DOWNLOADED_DATASET`.

## 3. Cross-check with original XBRL

For the matched 2024 10-Q:

```text
comparison rows:      123
matched values:       121
value differences:    0
missing in dataset:   2
```

The 2 missing facts are retained and reported; they were not dropped to improve
the match rate. Dataset and original accession values agree where comparable.

## 4. 30-company sample

```text
cross-section rows:   30
actual parsed:        0
```

The 30-company file remains metadata-only. It was not expanded to 120
accessions, so the P10.4 acceptance criterion for 30 companies is **not met**.

## 5. Historical CIK mapping

`historical_cik_mapping.csv` is built from the current SEC ticker file. It has
`confidence = CURRENT_ONLY`; it is not a historical/delisted-inclusive map.

## 6. Restatement and period derivation

`restatement_lineage.csv` and `financial_period_derivation.csv` are headers only.
No restatement or QTD/YTD derivation is claimed.

## 7. PIT availability

`pit_availability_audit.csv` copies P10.3's A/B acceptance proxy. No exact
first-public-visible timestamp is available. All records remain
`PIT_ACCEPTANCE_PROXY`; none is `PIT_PUBLICATION_VERIFIED`.

## 8. Data quality status

```text
DATA_AVAILABLE:          2024q1 SEC dataset
DATASET_ACCESSION_MATCH: 1 AAPL accession
ORIGINAL_XBRL_MATCH:     121 values, 0 diffs, 2 missing
COVERAGE_VERIFIED:       NO
STRATEGY_READY:          NO
```

## 9. Blockers

- only one quarter downloaded;
- 65 AAPL filings outside the downloaded quarter;
- 30-company as-filed parsing not done;
- historical/delisted CIK mapping not established;
- no restatement lineage;
- no QTD/YTD derivation;
- no exact publication timestamps;
- no analyst consensus.

## 10. Decision

```text
P10_4_SEC_DATASET_PARTIAL
P10.4 STRATEGY_READY = NO
```

Do not begin fundamental factor backtests. No Shadow, no IBKR, no PAPER-50000.

## 11. Files

```text
data/research/p10_4_sec_dataset_integration/
  sec_dataset_download_manifest.csv
  sec_dataset_accession_match.csv
  aapl_sec_dataset_comparison.csv
  aapl_dataset_reconciliation.json
  cross_section_30_accession_coverage.csv
  cross_section_30_field_coverage.csv
  historical_cik_mapping.csv
  restatement_lineage.csv
  financial_period_derivation.csv
  pit_availability_audit.csv
  p10_4_coverage.json
  p10_4_status.json
docs/research/p10_4_sec_dataset_integration.md
tests/test_p10_4_sec_dataset.py
```
