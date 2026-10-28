# Forward PIT Event Capture 鈥?First Real Observation

Date: 2026-10-28
Research only. No production changes.

## Actual capture

Command:

```bash
OFFICIAL_FEED_USER_AGENT="..." \
python -m tools.research.run_event_capture_cycle \
  --output-dir docs/research/event_forward_capture_2026-10-28 \
  --decision-at 2026-10-28T07:33:48Z \
  --feeds bls_cpi,bls_employment,fed_all,fed_speeches
```

Result:

| Metric | Value |
|---|---:|
| Events captured | **59** |
| Configured sources | 4 |
| Successful sources | **4** |
| Audit status | **pass** |
| Eligible at decision timestamp | **59** |
| Missing sources | none |
| Duplicate event IDs | 0 |
| Duplicate version IDs | 0 |

Event types:

- macro_release: 24
- central_bank: 18
- policy: 17

The first run used a decision timestamp earlier than the first-seen capture and
correctly produced `fail_no_data`; the second run used a decision timestamp
after first-seen and passed. Both snapshots are retained. This demonstrates the
fail-closed behavior rather than hiding it.

## Sources actually tested

| Source | Endpoint | HTTP/status | Items | Events | Result |
|---|---|---|---:|---:|---|
| BLS CPI RSS | `https://www.bls.gov/feed/cpi.rss` | ok | 12 | 12 | captured |
| BLS Employment RSS | `https://www.bls.gov/feed/empsit.rss` | ok | 12 | 12 | captured |
| Federal Reserve press | `https://www.federalreserve.gov/feeds/press_all.xml` | ok | 20 | 20 | captured |
| Federal Reserve speeches | `https://www.federalreserve.gov/feeds/speeches_and_testimony.xml` | ok | 15 | 15 | captured |

No API key was required. No key appears in artifacts.

### Sources checked but not run

- **SEC EDGAR**: existing `sec_event_collector.py` and tests; requires a
  user-supplied CIK/ticker universe and `SEC_USER_AGENT`. Not run in this
  capture to avoid pretending a historical first-seen time.
- **BEA**: existing code accepts caller-supplied macro records; no official BEA
  network collector and no API key in this environment. Not run.
- **Treasury**: no existing official Treasury auction/announcement collector
  was found in the repository. Not implemented here; this is a separate
  provider task, not a reason to invent an endpoint.
- **Alpha Vantage**: not relevant to event capture and no key.

## Strict schema mapping

Canonical adapter:

`tools/research/pit_event_canonical.py`

| Requested field | Existing source | Rule |
|---|---|---|
| `event_id` | `event_id` | required |
| `event_type` | `event_type` | existing taxonomy |
| `entity_id` | `tickers` or `market` | explicit tickers; macro feeds use `market` |
| `source` | `source` | required |
| `source_url` | `source_url` | http(s) required for validation |
| `event_time` | `event_time_utc` | only explicit event occurrence time |
| `source_published_at` | `published_at_utc` | provider-declared timestamp |
| `first_seen_at` | `first_seen_at_utc` | actual collector observation |
| `retrieved_at` | `retrieved_at_utc` | only if supplied; not inferred |
| `available_at` | max(published, first_seen, update_seen) | conservative, auditable |
| `revision_id` | `event_version_id` or content hash | preserves versions |
| `payload_hash` | `content_hash` | content fingerprint |
| `supersedes_event_id` | existing field | version chain |
| `timestamp_confidence` | derived | `parsed_utc`, `date_only`, or `missing` |
| `validation_status` | derived | `validated` or `rejected` |

Critical semantics:

- `event_time` is **not** `source_published_at`.
- `first_seen_at` is the real capture time; no historical backfill invents it.
- `available_at` is the latest known observer timestamp, not a claim of exact
  first public availability.
- `parsed_utc` means timezone-aware ISO parsing succeeded; it does **not** mean
  the publisher's timestamp is an exact public-availability instant.
- Date-only records are `date_only` and rejected for strict validation.
- Missing source URL or missing required timestamp is rejected.

## Source quality

Machine-readable:

`docs/research/event_forward_capture_2026-10-28/source_quality.json`

| Source | Events | Validated | Timestamp parsed | Capture success | Revisions |
|---|---:|---:|---:|---:|---:|
| bls_cpi_rss | 12 | 12 | 100% | 100% | 12/12 |
| bls_employment_situation_rss | 12 | 12 | 100% | 100% | 12/12 |
| federal_reserve_press_rss | 20 | 20 | 100% | 100% | 20/20 |
| federal_reserve_speeches_rss | 15 | 15 | 100% | 100% | 15/15 |

`revision_rate` is 1.0 per source because each event currently has one observed
version. It is not evidence of source revision behavior; revision testing is
covered by mocked archive tests.

## Files

- `event_capture_*.events.json` 鈥?immutable capture snapshots
- `event_capture_*.metadata.json` 鈥?request status, timestamps, source reports
- `event_capture_*.audit.json` 鈥?as-of coverage audit
- `event_archive.json` 鈥?deduplicated version archive
- `source_quality.json` 鈥?per-source quality report

## What this does not prove

- It does **not** provide historical PIT data.
- RSS `pubDate` is provider metadata, not a verified exact public instant.
- No news sentiment, earnings surprise, or event alpha is inferred.
- 59 events are not enough for an event alpha claim.
- No production scan, score, stop, ledger, order path, or external trigger was
  changed.

## Repeated snapshots and revision audit

Four consecutive captures were run against the same feeds:

| Snapshot | Decision mode | Audit | Events | New versions | Duplicate versions |
|---|---|---|---:|---:|---:|
| 20261028T073301486355Z | pre-capture | fail_no_data | 0 eligible | 59 | 0 |
| 20261028T073348231487Z | post-capture | pass | 59 | 0 | 59 |
| 20261028T074328910024Z | post-capture | pass | 59 | 0 | 59 |
| 20261028T074518525119Z | post-capture | pass | 59 | 0 | 59 |

Archive: 59 unique event IDs, 59 versions, 236 total observations, 177
duplicate observations. No duplicate event IDs were created.

Machine-readable:

`docs/research/event_forward_capture_2026-10-28/revision_audit.json`

Per-source revision audit:

| Source | Observations | Unique events | Versions | Duplicates | Revisions | Timestamp conflicts |
|---|---:|---:|---:|---:|---:|---:|
| bls_cpi_rss | 48 | 12 | 12 | 36 | 0 | 0 |
| bls_employment_situation_rss | 48 | 12 | 12 | 36 | 0 | 0 |
| federal_reserve_press_rss | 80 | 20 | 20 | 60 | 0 | 0 |
| federal_reserve_speeches_rss | 60 | 15 | 15 | 45 | 0 | 0 |

Current snapshots show no source revisions or timestamp conflicts. Revision
handling is covered by mocked archive tests, not by a real changed source yet.

## Decision-time protection

`--decision-at` before capture start now requires explicit
`--allow-pre-capture-decision`; the run is marked
`decision_mode=retrospective_replay`. Without the flag it fails closed.

Events are still selected only by `first_seen_at_utc <= decision_at_utc`.
A retrospective decision cannot include an event observed later.

## SEC forward capture

Explicit universe:

`docs/research/sec_forward_universe_2026-10-28.json`

Companies: AAPL, MSFT, AVB, ATVI.

Actual SEC request was **skipped** because `SEC_USER_AGENT` is not configured.
No SEC data is claimed. The existing `sec_event_collector.py` remains the
implementation; it separates `acceptanceDateTime` from the actual first-seen
time and warns that filing dates are not exact public moments.

## Manual research workflow

`.github/workflows/research-event-capture.yml`

- `workflow_dispatch` only
- no schedule, no production workflow dependency
- separate concurrency-free research job
- reads `OFFICIAL_FEED_USER_AGENT` from a secret
- skips clearly if the secret is absent
- uploads immutable capture artifacts
