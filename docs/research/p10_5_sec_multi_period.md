# P10.5 Multi-Period SEC Coverage and 30-Company Accession Pilot

Date: 2026-11-09
Status: **P10_5_SEC_MULTI_PERIOD_PARTIAL**
Strategy ready: **NO**

## 1. AAPL: all 66 filings explained

Dataset quarters required by filing date: **64** distinct quarters.

Only 2024q1 is downloaded.

| Dataset status | Count |
|---|---:|
| DATASET_MATCHED | 1 |
| NOT_IN_DATASET (quarter not downloaded) | 65 |
| **Total** | **66** |

The 65 are not marked as parse failures. They are outside the downloaded
quarter. No attempt was made to assume a fiscal period equals a filing quarter;
quarter is derived from filingDate.

## 2. Four-table parsing and accession match

2024q1 dataset:

- SUB, NUM, TAG, PRE parsed;
- accession/adsh exact match;
- AAPL 2024 10-Q `0000320193-24-000006`: 123 comparison rows,
  121 matched, 0 differences, 2 missing.

The two missing facts are retained.

## 3. 30-company accession pilot

The sample is the first 30 alphabetical members of the latest historical
membership snapshot; this is **not** the required 10 early-XBRL / 10 Inline /
10 delisted design.

Actual:

```text
companies:            30
accessions selected:  120 (2 10-K + 2 10-Q each)
accessions parsed:    120
format:               SEPARATE_XBRL (this sample)
historical delisted:  0
```

This is real accession-level parsing, not metadata. It is still a biased sample
because the CIK mapping is the current SEC ticker map.

## 4. Field coverage

`cross_section_30_field_coverage.csv` has field/company records for 18 fields.

Coverage highlights:

- Assets, CFO, basic shares: 120/120 accessions;
- Net Income: 117;
- EPS/equity/cash: 114-116;
- Capex: 87;
- Gross Profit: 46;
- Revenue via multiple tags; no single tag covers all companies.

No field is declared complete across all companies.

## 5. Restatement and QTD/YTD

`restatement_lineage.csv` and `financial_period_derivation.csv` are headers only.
No QTD/YTD or restatement logic is claimed. This fails the P10.5 acceptance
criteria for those areas.

## 6. PIT time

All records remain acceptance-proxy:

- A: conservative next session;
- B: A plus one full session;
- `availability_status = PIT_ACCEPTANCE_PROXY`;
- no `PIT_PUBLICATION_VERIFIED`.

## 7. Reproducibility

P10.5 generated:

- `run_manifest.json`;
- `data_manifest.json`;
- source SHA-256;
- parser version;
- dependency lock hash;
- output SHA-256;
- partial status.

Large SEC ZIP/CSV caches are not committed; their URL/SHA are in the P10.4
download manifest.

## 8. Acceptance against P10.6

| Requirement | Result |
|---|---|
| 30 companies | YES (30) |
| 120 accession parses | YES (120) |
| Historical delisted | NO (0) |
| Core fields explainable | PARTIAL |
| QTD/YTD derivation | NO |
| Restatement lineage | NO |
| Two PIT clocks | YES (A/B proxy) |
| Original/dataset anomalies traceable | PARTIAL |

Therefore:

```text
P10_6 GATE: DATA_BLOCKED
```

Do not start fundamental factor research.

## 9. Files

```text
data/research/p10_5_sec_multi_period/
  aapl_required_dataset_periods.csv
  aapl_all_accession_match.csv
  aapl_dataset_facts.csv
  aapl_dataset_reconciliation.csv
  cross_section_30_accession_coverage.csv
  cross_section_30_facts.csv
  cross_section_30_field_coverage.csv
  cross_section_30_company_coverage.csv
  historical_cik_mapping_verified.csv
  restatement_lineage.csv
  financial_period_derivation.csv
  run_manifest.json
  data_manifest.json
  p10_5_coverage.json
  p10_5_status.json
docs/research/p10_5_sec_multi_period.md
tests/test_p10_5_sec_multi_period.py
```
