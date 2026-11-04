# Dividend Event Verification — P4.4

Date: 2026-11-04
Branch: `research/dividend-event-verification-p44`
Stacked target: `research/dividend-primary-source-p43`
Status: **CONFIGURATION_BLOCKED for new SEC fetches; code/tests complete**

## 1. Why actual P4.4 collection is blocked

P4.4 requires a real SEC `User-Agent` contact and explicitly forbids reusing a
placeholder for production collection.

Environment check:

```text
SEC_USER_AGENT absent
ALLOW_SEC_PLACEHOLDER unset for this run
```

No new SEC request was made. The existing P4.3 cache is retained and audited,
but it cannot be called a complete P4.4 scan.

This is a configuration block, not a finding that filings do not exist.

## 2. What was fixed in code

### Exhibit 99.1 downloader

`sec_filing_fetcher.py` now:

- reads actual `index.json` item metadata;
- selects primary by type/name;
- selects exhibits by `type` containing `EX-99`, description containing
  `Press Release`/`dividend`, or `ex99` name;
- downloads and hashes each selected exhibit independently;
- records document name, type, description, sequence, URL, HTTP status, byte
  size, SHA-256 and cache status;
- does not download images/CSS/scripts;
- never silently drops a failed document.

Test:

```text
test_exhibit_99_1_is_actually_downloaded
```

### Parser

`dividend_event_parser_p44.py` now requires:

- a sentence with `dividend`;
- `common stock` or `common share`;
- declared/approved/increased/announced;
- a per-share amount;
- rejection of preferred/depositary/price-target/analyst contexts.

It separates:

- announcement date;
- record date;
- payment date;
- ex-date (null + `EX_DATE_UNAVAILABLE` when absent).

### Field-level verifier

`dividend_event_verifier_p44.py` verifies only when all core fields exist:

```text
ticker, event_type, security_type, declared_per_share,
announcement_date, source_url, accession_number, evidence_sha256
```

`EX_DATE` missing does not block `DECLARED`; it is a separate status.

### False positives

`is_false_positive()` identifies the NEE $67.75 price-target text and records:

```text
FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET
is_event = false
```

## 3. CAT and BAC fixtures

The parser was tested against the exact announced structures:

### CAT

```text
declared_per_share = 1.63
previous_per_share = 1.51
record_date = 2026-07-20
payment_date = 2026-08-19
announcement_date = 2026-06-10
security_type = COMMON
ex_date_status = EX_DATE_UNAVAILABLE
```

It does **not** extract 1.51 as the new dividend.

### BAC

```text
declared_per_share = 0.32
security_type = COMMON
record/payment dates parsed when stated
preferred 1.75 is excluded
```

The preferred-only sentence produces no common event.

However, because P4.4 has no real SEC contact, these are **parser fixture tests**,
not freshly downloaded/verified production events. They are not written into the
verified event registry.

## 4. NEE false-positive register

`data/research/dividend_false_positives_p44.json` records:

```text
ticker = NEE
amount = 67.75
reason = FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET
is_event = false
source_url = SEC 8-K URL
evidence_status = URL_ONLY_NOT_DOWNLOADED
```

The raw document is not claimed as downloaded. The URL-only hash is not a
substitute for filing evidence.

## 5. Full 8-K coverage reality

From P4.3 cache:

| Metric | Count |
|---|---:|
| companies | 22 |
| 8-K filings in 24m | **581** |
| primary documents downloaded under P4.3 5-per-company cap | **110** |
| excluded by that cap | **471** |
| full P4.4 scan completed | **false** |

The code now supports unlimited `per_company`, but no new run was performed
because configuration is blocked. Therefore:

```text
581 seen != 581 scanned
```

This distinction is preserved in `dividend_coverage_p44.json`.

## 6. Actual event status

`data/research/dividend_events_p44.json`:

```text
status = CONFIGURATION_BLOCKED
verified = 0
partially_verified = 0
new events = 0
```

No CAT/BAC event is marked VERIFIED without a freshly fetched official document
and hash.

## 7. P4.1 scores

No score was increased:

| Status | Count |
|---|---:|
| SCORE_READY | 10 |
| NOT_READY | 18 |

All DPS growth remains blocked by split-basis verification.

## 8. Split evidence

P4.3's 22 split fact records remain:

```text
22 PARTIALLY_VERIFIED
0 SPLIT_CONFIRMED
```

The new exhibit downloader is ready to inspect split exhibits, but no new SEC
request was made in P4.4. XBRL fact end is still not treated as effective date.

## 9. Files

```text
tools/investment_research/dividend/sec_filing_fetcher.py       # exhibit fix
tools/investment_research/dividend/dividend_event_parser_p44.py
tools/investment_research/dividend/dividend_event_verifier_p44.py
tools/investment_research/dividend/dividend_coverage_audit_p44.py

data/research/dividend_events_p44.json
data/research/dividend_false_positives_p44.json
data/research/dividend_coverage_p44.json

tests/test_dividend_event_verification_p44.py
```

## 10. Remaining

1. Configure a real SEC `SEC_USER_AGENT` contact.
2. Run full 581 8-K scan; then download 471 currently excluded accessions.
3. Download EX-99.1 for CAT/BAC and verify with actual raw hashes.
4. Resolve NEE candidate exclusion in the actual fetched document.
5. Complete split effective-date evidence.
6. Establish DPS share basis per company.

No production/trade code changed. No Yahoo/AKShare/Finnhub data was used.
