# SEC EDGAR Readiness

Date: 2026-10-29 UTC
Status: code/tests ready; **real access not executed**.

## Identity gate

`tools/research/contact_user_agent.py` validates:

- `SEC_USER_AGENT` present and single-line;
- a syntactically valid contact email;
- no placeholder domains/local parts;
- missing/invalid -> exception before any request.

No real SEC User-Agent is configured. Therefore no SEC submissions, 8-K, or
Archives request was made. This is `not_executed`, not a success.

## Parsed fields

- CIK / ticker;
- accession number;
- form (`8-K`, `10-Q`, `10-K`, etc.);
- filing date (date only, not public time);
- items;
- primary document;
- SGML `ACCEPTANCE-DATETIME` when separately supplied and verified.

## Timestamp semantics

- `filingDate` is never treated as exact public time.
- Raw `acceptanceDateTime` is not treated as verified UTC.
- Official SGML `ACCEPTANCE-DATETIME` maps from SEC-documented fixed EST.
- Missing/duplicate/mismatched/invalid acceptance headers fail closed.
- If unavailable, `published_at_utc=None` and `availability_status=timestamp_missing`.

## Event classification

- `8-K` item `2.02` -> `earnings`;
- `10-K`/`10-Q` -> `earnings`;
- other `8-K` -> `company_news`;
- dedup by accession/event ID; amendments retained as versions.

## Tests

`tests/test_pit_sec_edgar.py`, `tests/test_sec_event_collector.py`,
`tests/test_contact_user_agent.py`: **20 passed**

Covered:

- raw acceptanceDateTime not trusted as UTC;
- filingDate not treated as publication time;
- fixed EST conversion in summer/winter;
- missing/duplicate/invalid/mismatched acceptance header;
- 8-K 2.02 earnings classification and 5.02 company news;
- placeholder/missing User-Agent rejected before request;
- collector uses verified SGML acceptance time.

## Blockers

1. no real `SEC_USER_AGENT`;
2. no approved storage/redistribution review for SEC responses;
3. no real event count or coverage from SEC yet.
