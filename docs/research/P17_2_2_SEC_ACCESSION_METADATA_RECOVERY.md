# P17.2.2 SEC Accession Metadata Recovery

Date: 2026-11-20
Branch: `research/p17-2-2-sec-accession-metadata-recovery`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **SEC_DOWNLOAD_BLOCKED_MISSING_USER_AGENT · DATA_BLOCKED**

## 1. Gate

```text
SEC_USER_AGENT: MISSING
SEC_DOWNLOAD: BLOCKED
```

No SEC request was made. No placeholder/email was fabricated. No browser
impersonation or proxy was used. Because the User-Agent is absent, Filing Index,
complete submission text, Master Index, and acceptance datetime recovery were
not attempted.

## 2. Accession parsing (local)

75 P17.2.1 accessions parsed:

```text
valid 18-digit accessions: 75 / 75
accession years: 2026 59; 2020–2024 8; 2014–2018 6; 2025 2
```

Each has:

- no-dash accession;
- dashed accession;
- accession prefix CIK;
- accession year;
- sequence;
- SEC Archives directory URL.

Accession parsing is not metadata verification; the URL was constructed but not
requested.

## 3. Local metadata coverage

| field | available |
|---|---:|
| form | 2 / 75 |
| filed date | 2 / 75 |
| acceptance datetime | 2 / 75 |
| independent registrant CIK | 2 / 75 |

Only 2 filings have complete local metadata. The other 73 remain
`METADATA_PARTIAL/INDEX_MISSING`.

## 4. Historical facts

P17.2.1 historical subset:

```text
2020–2024 accessions: 8
symbol facts: 16
tickers: 9
```

All 16 are downgraded to `CANDIDATE_ONLY`; 0 are
`VERIFIED_AT_FILING_ACCEPTANCE`.

P13 membership overlap:

```text
AAPL, GOOG, GOOGL, NEE, NVDA = 5 tickers
```

The preferred NEE.PRO/PRP/PRQ/PRR tickers are not in the P13 common-ticker
coverage, so they do not add membership coverage.

## 5. Not run

- SEC Filing Index fetch;
- complete submission text;
- Master Index;
- CIK cross-validation;
- acceptance timeline;
- 110–125 ticker expansion;
- 2020/2022/2024 filing search.

All blocked at the User-Agent gate.

## 6. Decision

```text
P17_2_2_METADATA_RECOVERY = NOT_RUN
P17_2_2_HISTORICAL_VERIFIED_FACTS = 0
P17_2_2_VERIFIED_INTERVALS = 0
P17_2_2_PIT_IDENTITY_GATE = DATA_BLOCKED
P17_2_2_OVERALL = DATA_BLOCKED
```

Filing point observations would not equal complete identity intervals even if
metadata were recovered. No alpha, no portfolio, no NAV, no trade ledger.

## 7. Unblock

Configure a real `SEC_USER_AGENT` with a contact the user can be reached at,
outside Git and outside logs. Then run a pilot of 8 historical accessions at
≤1 request/second with cache and no parallel downloads.

## 8. Files

- `tools/research/p17_2_2_sec_accession_metadata_recovery.py`
- `tests/test_p17_2_2_sec_accession_metadata_recovery.py`
- `data/research/p17_2_2/p17_2_2_accession_registry.csv`
- `p17_2_2_sec_index_metadata.csv`
- `p17_2_2_submission_header_metadata.csv`
- `p17_2_2_master_index_metadata.csv`
- `p17_2_2_cik_cross_validation.csv`
- `p17_2_2_filing_download_audit.csv`
- `p17_2_2_filing_identity_observations.csv`
- `p17_2_2_historical_identity_coverage.csv`
- `p17_2_2_summary.json`
- `p17_2_2_manifest.json`

No model call, no API key, no broker, no order.
