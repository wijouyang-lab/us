# P17.2.3 SEC Historical Accession Metadata Pilot

Date: 2026-11-20
Branch: `research/p17-2-3-sec-historical-accession-pilot`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **PILOT_PASS · identity point observations only**

## 1. User-Agent gate

```text
SEC_USER_AGENT: PRESENT
```

The value was not printed, logged, committed, or written to output. SEC requests
used it only in the HTTP header. No placeholder email was used.

## 2. Requests

```text
official SEC requests: 23
rate: <= 1 request/second, no concurrency
403/429: none
cache: local under data/research/p17_2_3/cache (not committed)
```

23 = 8 filing index.json + 8 complete submission texts + 7 quarterly Master
Index downloads (one quarter reused for NEE 2023).

## 3. Pilot result — 8 accessions

All eight historical accessions were recovered:

| accession | ticker | form | filed | acceptance | report period | master |
|---|---|---|---|---|---|---|
| 000032019321000065 | AAPL | 10-Q | 2021-07-28 | 2021-07-27 18:03:42 | 2021-06-26 | match |
| 000075330821000014 | NEE | 10-K | 2021-02-12 | 2021-02-12 16:07:50 | 2020-12-31 | match |
| 000075330823000019 | NEE | 10-K | 2023-02-17 | 2023-02-17 16:06:40 | 2022-12-31 | match |
| 000104581021000163 | NVDA | 10-Q | 2021-11-22 | 2021-11-19 16:31:56 | 2021-10-31 | match |
| 000104581022000079 | NVDA | 10-Q | 2022-05-27 | 2022-05-26 16:30:23 | 2022-05-01 | match |
| 000104581024000316 | NVDA | 10-Q | 2024-11-21 | 2024-11-20 16:31:17 | 2024-10-27 | match |
| 000165204423000016 | GOOGL | 10-K | 2023-02-03 | 2023-02-02 18:04:13 | 2022-12-31 | match |
| 000165204423000045 | GOOGL | 10-Q | 2023-04-26 | 2023-04-25 20:15:00 | 2023-03-31 | match |

Coverage:

```text
index.json: 8/8
submission header: 8/8
filed date: 8/8
acceptance datetime: 8/8
Master Index exact match: 8/8
```

## 4. CIK cross-validation

```text
prefix = Master Index CIK and prefix in header filers: 6/8
co-registrant (NEE / Florida Power & Light): 2/8, explained
unexplained conflicts: 0
```

The two NEE filings list both NextEra (0000753308) and Florida Power & Light
(0000037634); Master Index keys the filing under FP&L. This is a multi-filer
structure, not a fabricated conflict.

## 5. Identity facts

```text
symbol facts: 16
VERIFIED_AT_FILING_ACCEPTANCE: 16
VERIFIED_INTERVAL: 0
```

Each verified fact is a point observation at the filing acceptance time, not a
complete ticker validity interval. The status does not extend backward or
forward.

Historical tickers: AAPL, NVDA, NEE, NEE.PRO, NEE.PRP, NEE.PRQ, NEE.PRR, GOOGL,
GOOG. P13 common-ticker overlap: 5 (AAPL, GOOG, GOOGL, NEE, NVDA).

## 6. Decision

```text
P17_2_3_METADATA_RECOVERY = PASS (8/8)
P17_2_3_CIK_VALIDATION = PASS WITH 2 EXPLAINED CO-REGISTRANTS
P17_2_3_POINT_OBSERVATIONS = 16
P17_2_3_VERIFIED_INTERVALS = 0
P17_2_3_PIT_IDENTITY = HISTORICAL_IDENTITY_OBSERVATION_PARTIAL
```

The pilot shows the SEC official path is usable. It does **not** show that a
100-name daily PIT cross-section is available. Expansion to 75 accessions is
technically justified, but interval verification and much broader coverage are
still needed before fundamental PIT research.

## 7. Files

- `tools/research/p17_2_3_sec_accession_pilot.py`
- `tests/test_p17_2_3_sec_historical_accession_pilot.py`
- `data/research/p17_2_3/p17_2_3_pilot_manifest.csv`
- `p17_2_3_sec_index_metadata.csv`
- `p17_2_3_submission_header_metadata.csv`
- `p17_2_3_master_index_metadata.csv`
- `p17_2_3_cik_cross_validation.csv`
- `p17_2_3_filing_identity_observations.csv`
- `p17_2_3_identity_conflicts.csv`
- `p17_2_3_request_audit.csv`
- `p17_2_3_historical_identity_coverage.csv`
- `p17_2_3_summary.json`
- `p17_2_3_manifest.json`

No alpha, NAV, trade ledger, or production change.
