# Forward Capture and SEC Timestamp Audit

Date: 2026-10-29 UTC
Research only. No canonical write.

## 1. Forward capture entry

Tool:

`tools/research/forward_capture.py`

Properties:

- manual invocation only; no scheduler/service;
- Fed source whitelist:
  - `www.federalreserve.gov` / `federalreserve.gov`;
  - `/newsevents/pressreleases/` or `/newsevents/press/`;
- configurable `--user-agent`, no impersonation or token;
- one URL per run; no retry loop or high-frequency polling.

Actual run:

```text
URL: https://www.federalreserve.gov/newsevents/pressreleases/monetary20250319a.htm
Store: docs/research/fomc_forward_capture_2026-10-29.jsonl
```

| Field | First run | Second run |
|---|---|---|
| http_status | 200 | 200 |
| parse_status | exact | exact |
| published_at | 2025-03-19T18:00:00Z | same |
| content_hash | `8aa870a9...b1ac` | same |
| first_seen_at_utc | 2026-10-29T15:14:31.445323Z | **same** |
| version | 1 | 1 |
| pit_status | forward_observed | forward_observed |

This is a real forward observation made on 2026-10-29 of a 2025 page: the
`first_seen` is 2026, not the 2025 publication date. It is not a historical PIT
sample.

### URL normalization

- query string and fragment removed for canonical identity;
- event ID parsed from `monetaryYYYYMMDDa.htm`, including
  `/press/monetary/20100127a.htm`;
- query-only URL changes do not create a duplicate event.

## 2. Historical backfill

Actual 2010-01-27 page:

```text
first_seen_at_utc = null
is_historical_backfill = true
pit_status = retrospective_non_PIT
parse_status = date_only
```

No historical first-seen was fabricated.

## 3. SEC timestamp audit

Source:

`https://data.sec.gov/submissions/CIK0000320193.json`

Sample: 10 recent filings (Apple CIK).

| Metric | Result |
|---|---:|
| HTTP | 200 |
| parsed `acceptanceDateTime` | 10 |
| missing | 0 |
| filingDate vs acceptance date mismatch | 0 |
| SGML submission fetch | **403** |
| SGML acceptance header verified | **0** |

Actual sample times are UTC values such as:

```text
2026-10-22T22:32:20Z  form 4
2026-10-16T20:29:07Z  form 144
```

Important limitation:

- `acceptanceDateTime` from submissions JSON is parsed, but it is **not**
  verified against the official SGML acceptance header (403 in this
  environment);
- neither value proves first public availability;
- no `first_seen_at_utc` exists for these historical filings;
- therefore SEC timestamps are **UNVERIFIED for PIT** and not eligible for a
  PIT backtest.

Evidence file:

`docs/research/sec_timestamp_audit_2026-10-29.json`

## 4. PIT admission rules

New research policy:

`docs/research/PIT_RESEARCH_ADMISSION.md`

Key rules:

- published time and first_seen are separate;
- backfill is never PIT;
- event must be available before decision time;
- failed/revised records must remain traceable;
- small/overlapping samples are descriptive only;
- SEC JSON acceptance time is not first visibility.

## 5. Continuous operation status

**No background service or external scheduler was deployed.**

Current capability:

- manual one-shot capture;
- duplicate-safe store;
- immutable first_seen on re-fetch;
- version history on content change.

Not available:

- unattended continuous scheduling;
- guaranteed process supervision;
- production alerting.

A production-like continuous collector would require a separately approved
scheduler/service; this round intentionally does not create one.

## 6. Tests

- URL normalization / duplicate query: 2 tests.
- first_seen / version / backfill / failure: 5 tests.
- forward whitelist: 2 tests.
- SEC audit fixture: 1 test.
- Existing FOMC/Fed regressions: previously 10 tests.

Full CI reported after commit.

## 7. Artifacts

- forward capture: `tools/research/forward_capture.py`
- event store: `tools/research/event_capture_store.py`
- live store: `docs/research/fomc_forward_capture_2026-10-29.jsonl`
- backfill store: `docs/research/fomc_backfill_capture_2026-10-29.jsonl`
- SEC audit: `docs/research/sec_timestamp_audit_2026-10-29.json`
- PIT policy: `docs/research/PIT_RESEARCH_ADMISSION.md`
- tests: `tests/test_forward_capture.py`, `tests/test_event_capture_store.py`,
  `tests/test_sec_timestamp_audit.py`
