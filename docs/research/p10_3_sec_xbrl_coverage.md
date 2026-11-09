# P10.3 SEC Historical XBRL Recovery and Coverage

Date: 2026-11-09
Status: **P10_3_SEC_XBRL_PARTIAL**
Strategy ready: **NO**

## 1. AAPL 66 filings: every filing now classified

| Status | Count |
|---|---:|
| INLINE_XBRL_PARSED | 23 |
| SEPARATE_XBRL_PARSED | 40 |
| ORIGINAL_FILE_NO_XBRL | 3 |
| ORIGINAL_FILE_UNAVAILABLE | 0 |
| PARSER_UNSUPPORTED | 0 |
| DATA_INVALID | 0 |
| UNRESOLVED | 0 |
| **Total** | **66** |

This corrects the P10.2 interpretation: the 43 old filings were **not**
automatically unparseable. 40 had separate XBRL instance documents and were
recovered from the accession directory.

- separate-XBRL facts: 4,860
- separate-XBRL fields: 18
- P10.2 inline facts: 4,467
- 3 filings have no XBRL instance in the accession directory.

The original accession, instance URL, SHA-256, contexts, period start/end, and
values are retained.

## 2. What was checked

For every old filing:

1. accession directory `index.json`;
2. all `.xml` files;
3. exclusion of taxonomy/calculation/definition/label/presentation files;
4. independent XBRL instance download;
5. namespace-aware instance parsing;
6. contexts and period bounds;
7. core us-gaap facts;
8. SHA-256 and parse status.

No current Company Facts values were substituted for missing as-filed facts.

## 3. SEC Financial Statement Data Sets

Probe:

```text
2024q1.zip: HTTP 200
size: 124,336,804 bytes
used: false
```

The dataset is available but was **not ingested**. Download date is not filing
date, and the dataset cannot replace accession-level verification. Marked
`AVAILABLE_NOT_FETCHED`, not “matched.”

## 4. PIT availability

Every AAPL filing has:

- `accepted_at`;
- `accepted_et`;
- `first_public_available_at` = empty;
- `first_public_available_evidence` = empty;
- `first_market_usable_A`;
- `first_market_usable_B`;
- `availability_status = PIT_ACCEPTANCE_PROXY`.

The SEC acceptance timestamp is not exact public visibility. A is the next
conservative session after acceptance; B is one full session later. Both are
reported; neither is called `PIT_PUBLICATION_VERIFIED`.

## 5. 30-company cross-section

```text
tickers:        30
with CIK:       30
metadata only:  30
actual as-filed parse: 0
```

This is a real limitation, not a coverage claim. The mapping uses the current
SEC ticker file, so delisted-inclusive history is not established.

## 6. Field coverage

18 separate-XBRL fields include Revenue, Gross Profit, Operating Income, Net
Income, EPS, Assets, Liabilities, Equity, Cash, Debt, CFO, Capex, and shares.

Still incomplete:

- QTD from YTD using two accession versions;
- amendment/restatement lineage;
- field-level coverage across 30 companies;
- delisted CIK mapping;
- exact first-publication timestamps.

## 7. Data status

```text
DATA_AVAILABLE:          AAPL inline + separate XBRL
ACCEPTANCE_TIME_VERIFIED: AAPL 66/66
PIT_ACCEPTANCE_PROXY:    AAPL 66/66
PIT_PUBLICATION_VERIFIED: NONE
COVERAGE_VERIFIED:       NO
STRATEGY_READY:          NO
```

## 8. Decision

Do not start P10.4 fundamental factor research. First expand actual accession
parsing to 30 historical names and implement QTD/restatement lineage.

No Shadow. No IBKR. No PAPER-50000.

## 9. Files

```text
data/research/p10_3_sec_xbrl_coverage/
  aapl_all_status.csv
  separate_xbrl_facts.csv
  pit_time_audit.csv
  cross_section_30_status.csv
  p10_3_coverage.json
  p10_3_status.json
docs/research/p10_3_sec_xbrl_coverage.md
tests/test_p10_3_sec_xbrl.py
```
