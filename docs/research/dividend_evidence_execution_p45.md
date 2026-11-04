# Dividend Evidence Execution — P4.5

Date: 2026-11-04
Branch: `research/dividend-evidence-execution-p45`
Stacked target: `research/dividend-event-verification-p44`
Status: **CONFIGURATION_BLOCKED**

## 1. Configuration gate

`--check-config` result:

```text
SEC_USER_AGENT_NOT_CONFIGURED
```

No real contact is present in the local environment.

Per P4.5 rules:

- no new SEC request was made;
- placeholder bypass was removed from the production fetcher;
- setting `ALLOW_SEC_PLACEHOLDER` no longer helps; `example.com` is
  `SEC_USER_AGENT_INVALID`;
- no retry loop and no alternate provider was used.

Therefore the 581-accession full scan is not executed in this round. The existing
P4.3 cache remains auditable but is not a P4.5 full scan.

## 2. What is implemented

### SEC fetcher

`sec_filing_fetcher.py` now has:

```text
SEC_USER_AGENT_CONFIGURED
SEC_USER_AGENT_NOT_CONFIGURED
SEC_USER_AGENT_INVALID
CONFIGURATION_BLOCKED
```

and `python -m ... --check-config` prints only the status.

Document selection now uses index metadata:

- type;
- description;
- sequence;
- filename;
- primary and EX-99/Press Release selection.

Statuses:

```text
FETCHED_COMPLETE
FETCHED_PARTIAL
FETCH_FAILED
INDEX_FETCH_FAILED
CONFIGURATION_BLOCKED
```

An exhibit failure makes the accession `FETCHED_PARTIAL`, never a silent success.

### Full scan driver

`dividend_full_scan_p45.py`:

- scans all 22 payers and all 8-Ks in 24 months;
- no per-company cap;
- resumes from `sec_fetch_manifest_p45.json`;
- records each accession/document status and SHA;
- stops at `CONFIGURATION_BLOCKED` before networking when UA is absent.

### Parser / verifier

`dividend_event_parser_p44.py` is used with:

- common stock / common share requirement;
- preferred/depositary exclusion;
- declared/approved/increased verbs;
- separate record/payment dates;
- `EX_DATE_UNAVAILABLE` when absent.

`dividend_event_verifier_p44.py` now can require a real manifest entry:

- accession exists;
- document URL matches;
- HTTP status 200;
- SHA-256 matches the downloaded bytes.

A self-supplied URL/hash without manifest evidence cannot be VERIFIED.

## 3. CAT / BAC parser smoke

Actual official files were **not** fetched in P4.5 because configuration is
blocked. The parser fixtures still confirm the expected semantics:

CAT:

```text
declared 1.63
previous 1.51
record 2026-07-20
payment 2026-08-19
```

BAC:

```text
declared 0.32 common
preferred 1.75 excluded
```

These remain parser tests, not downloaded event records.

## 4. NEE false positive

NEE $67.75 is recorded as:

```text
FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET
is_event = false
source = SEC 8-K URL
evidence_status = URL_ONLY_NOT_DOWNLOADED
```

No DECLARED/INCREASED event is generated.

## 5. Coverage reality

P4.3 cache:

| Metric | Count |
|---|---:|
| 22 companies' 8-K records | 581 |
| primary documents downloaded | 110 |
| excluded by old 5-per-company cap | 471 |
| P4.5 full scan | **NOT RUN** |
| status | CONFIGURATION_BLOCKED |

`581 seen != 581 scanned`.

## 6. Events and scores

`data/research/dividend_events_p45.json`:

```text
verified = 0
partially_verified = 0
new events = 0
status = CONFIGURATION_BLOCKED
```

P4.1 scores remain:

```text
SCORE_READY 10
NOT_READY   18
```

No split/event evidence was promoted.

## 7. Split facts

22 P4.3 split facts remain:

```text
PARTIALLY_VERIFIED = 22
SPLIT_CONFIRMED    = 0
```

P4.5 did not run new downloads. XBRL fact end is still not effective date.

## 8. Files

```text
tools/investment_research/dividend/sec_fetch_manifest.py
tools/investment_research/dividend/dividend_full_scan_p45.py
tools/investment_research/dividend/dividend_event_pipeline_p45.py

data/research/sec_fetch_manifest_p45.json
data/research/dividend_events_p45.json
data/research/dividend_false_positives_p45.json
data/research/split_evidence_p45.json
data/research/dividend_coverage_p45.json

tests/test_dividend_evidence_p45.py
```

## 9. Next requirement

Set a real contact locally, then run:

```bash
python -m tools.investment_research.dividend.sec_filing_fetcher --check-config
```

Expected:

```text
SEC_USER_AGENT_CONFIGURED
```

Only then execute the 581-accession full scan. No placeholder should be used.

No production/trade code was modified. No Finnhub call was made.
