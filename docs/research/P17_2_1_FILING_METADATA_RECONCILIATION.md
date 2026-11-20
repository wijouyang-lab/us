# P17.2.1 Filing Metadata Reconciliation

Date: 2026-11-20
Branch: `research/p17-2-1-filing-metadata-reconciliation`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **IDENTITY_OBSERVATION_PARTIAL · METADATA DATA_BLOCKED**

## 1. Corrected P17.2 counts

P17.2 hardcoded:

```text
historical_2020_2024_filings = 0
historical_identity_observations = 0
filing_years = []
```

Those were wrong. Recomputed from the actual 75 local filing directories and
accession strings:

| item | corrected |
|---|---:|
| local filings | 75 |
| accession 2026 | 59 |
| accession 2020–2024 | **8** |
| pre-2020 | 6 |
| 2025 | 2 |
| symbol facts total | 288 |
| historical symbol facts (2020–2024) | **16** |
| historical tickers | 9 |

Historical tickers found:

```text
AAPL, NVDA, NEE, NEE.PRO, NEE.PRP, NEE.PRQ, NEE.PRR, GOOGL, GOOG
```

P17.2's "0 historical" was a code default, not measured.  
This run finds 8 historical filing directories / 16 symbol facts in the local
cache. The earlier external audit's 16 filings / 18 facts cannot be reproduced
from this local cache; the discrepancy is recorded, not papered over.

## 2. Metadata availability

Only 2 of 75 directories contain `*-index.html`, which is the only local source
found for:

- form;
- filing date;
- acceptance datetime;
- report period;
- registrant CIK.

For the other 73, only `index.json` (file list) and the document are present.
Therefore:

| field | coverage |
|---|---:|
| form | 2 / 75 |
| filing_date | 2 / 75 |
| acceptance_datetime | 2 / 75 |
| report_period | 2 / 75 |
| index registrant CIK | 2 / 75 |
| XBRL context CIK | 75 / 75 |

CIK match rate against an independent index CIK is **1/75 = 1.33%**, not 100%.
The 288-symbol facts are therefore `CANDIDATE_ONLY`, not
`VERIFIED_AT_FILING_ACCEPTANCE`.

## 3. Parser findings

The Inline XBRL parser still extracts:

- `dei:TradingSymbol`;
- `dei:Security12bTitle`;
- `dei:SecurityExchangeName`;
- context CIK and security-class dimensions.

CAT/CAT35 remain separate contexts when present. Multi-class support is real,
but **historical metadata is missing**, so the facts cannot be assigned a
verified filing date/acceptance time.

## 4. Filing-year semantics

- Accession year is derived from the official accession directory name;
- report period is not used as filing date;
- acceptance time is only used when present in the local index;
- no date was synthesized from `report_period`.

Accession year 2021 with report period 2020-12-31 is correctly kept as a 2021
filing, not a 2020 filing.

## 5. Sample expansion

The local cache has only 75 filings and no SEC Master Index / complete submission
text. The planned 110–125 ticker sample and 2020/2022/2024 filing search were
not completed. No external download was attempted because no valid SEC
User-Agent contact is configured; using a placeholder would violate the task.

```text
SEC_DOWNLOAD = BLOCKED_USER_AGENT
SAMPLE_EXPANSION = NOT_RUN
```

## 6. Decision

```text
P17_2_1_FILING_METADATA = DATA_BLOCKED
P17_2_1_HISTORICAL_FACTS = PARTIAL (8 filings / 16 facts / 9 tickers)
P17_2_1_VERIFIED_AT_FILING = 0
P17_2_1_IDENTITY_INTERVAL = NOT_ESTABLISHED
P17_2_1_RESTRICTED_FUNDAMENTAL_RESEARCH = DATA_BLOCKED
```

The corrected registry proves historical cover XBRL exists locally, but the
metadata needed to make it PIT-verifiable (form, filing date, acceptance time,
index CIK) is missing for 73/75 files. P17.2's "verified" statuses are therefore
withdrawn.

## 7. Required unblock

1. SEC-compliant User-Agent with real contact information.
2. Download and cache the relevant SEC Master Index quarters / complete
   submission text, or the filing index headers for the 73 missing dirs.
3. Map each accession to form, filing date, acceptance datetime, period, CIK.
4. Re-run the parser only after metadata is present.
5. Then test 2020/2022/2024 observations and PIT membership.

## 8. Files

- `tools/research/p17_2_1_filing_metadata.py`
- `tests/test_p17_2_1_filing_metadata.py`
- `data/research/p17_2_1/p17_2_1_filing_registry.csv`
- `p17_2_1_filing_identity_observations.csv`
- `p17_2_1_summary.json`
- `p17_2_1_manifest.json`

No model call, no API key, no broker, no order.
