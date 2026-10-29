# Forward Capture Validation and PIT Semantics Fix

Date: 2026-10-29 UTC
Research only. No production or canonical changes.

## 1. PIT semantics fixed

Previous ambiguity: a 2025 Fed page first fetched in 2026 was marked
`forward_observed`, which could be misread as usable for 2025 decisions.

New status model in `event_capture_store.py`:

| Situation | Status | PIT eligible |
|---|---|---|
| historical backfill | `retrospective_non_PIT` | false |
| current fetch of old announcement (>1h after publication) | `late_observation_not_pit` | false |
| first fetch within 1h of publication, exact time | `forward_observed` | true |
| date-only / missing published time | `published_time_unknown` | false |
| HTTP/parse failure | `capture_error` | false |

Additional fields:

```text
observation_kind
pit_eligible
decision_ready_at_utc
```

A non-null `first_seen_at_utc` alone no longer implies PIT eligibility.

## 2. Actual current Fed capture

Source:

`https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm`

| Field | Value |
|---|---|
| HTTP | 200 |
| event_id | 20261028 |
| published_at | 2026-10-28T18:00:00Z |
| first_seen_at_utc | 2026-10-29T15:24:19.718132Z |
| lag | ~21.4 hours |
| content_hash | `cebfd185...1065` |
| parse_status | exact |
| observation_kind | `late_observation_of_old_event` |
| pit_status | **late_observation_not_pit** |
| pit_eligible | **false** |

This is a real manual capture, but because it occurred 21 hours after release it
is **not** a live PIT observation.

Run twice; both records:

- same `first_seen_at_utc`;
- same content hash;
- version 1;
- unique event count = 1, duplicate capture = 1, update = 0, failure = 0.

Store:

`docs/research/fomc_forward_capture_current_2026-10-29.jsonl`

## 3. Legacy 2025 record migrated

The previous 2025-03-19 capture, first observed in 2026, was corrected from
`forward_observed` to:

```text
observation_kind = late_observation_of_old_event
pit_status = late_observation_not_pit
pit_eligible = false
```

Its true first_seen remains 2026-10-29.

## 4. SEC timestamp validation

Actual Apple CIK sample remains 10 filings:

- submissions HTTP 200;
- `acceptanceDateTime` parsed 10/10;
- filingDate/acceptance date mismatch 0;
- official SGML submission request still **HTTP 403**;
- SGML `ACCEPTANCE-DATETIME` verified 0/10.

Conclusion:

```text
SEC JSON acceptance time: parsed, useful as filing metadata
SEC first public visibility: UNVERIFIED
SEC first_seen: absent
SEC PIT eligibility: false
```

No 403 bypass attempted. Existing `pit_sec_edgar.py` already treats SGML
acceptance time as not first-public-availability; the JSON path is not used as
PIT evidence.

## 5. Manual collection workflow

Entry:

`tools/research/forward_capture.py`

- whitelist: `federalreserve.gov` press paths;
- explicit User-Agent;
- one URL per manual run;
- JSONL append;
- duplicate event ID dedup;
- first_seen preserved;
- version increments only on content hash change;
- failures stored with diagnostics.

No scheduler, service, or external trigger deployed.

## 6. Research admission status

Current evidence:

| Metric | Count |
|---|---:|
| raw JSONL records (all stores) | **14** |
| unique captured events | 3 |
| real first-seen records | 1 |
| simulated records | 0 |
| simulation flag missing (legacy) | 2 |
| true live PIT-eligible observations | **0** |
| late observations of old announcements | 2 unique |
| historical backfill records | 1 |
| published-evidence insufficient | 2 |
| decision-evidence insufficient | 3 |
| SEC records with verified public visibility | **0** |
| events usable for PIT backtest | **0** |

Audit command:

```bash
python -m tools.research.pit_sample_audit \
  --store "docs/research/fomc_*capture*.jsonl" \
  --output docs/research/pit_sample_audit_2026-10-29.json
```

Actual reason counts:

```text
simulation_flag_missing: 2
historical_backfill: 1
parse_status_not_exact: 1
source_evidence_not_verified: 2 (legacy records)
published_at_evidence_missing: 2
published_time_missing_or_naive: 1
first_seen_missing_or_naive: 1
research_ready_missing_or_naive: 2
decision_time_missing: 3
decision_evidence_missing: 3
late_observation: 2
observation_lag_exceeds_1h: 2
```

Unique events:

- 2025-03-19 Fed statement (late observed 2026);
- 2026-10-28 Fed statement (late observed 2026);
- 2010-01-27 historical backfill.

No event passes the PIT gate.

## 7. Tests

Latest targeted: **27 passed** across capture-store, forward-validation,
SEC-audit, batch-capture and PIT-admission tests. Full CI is reported after
commit.

## Artifacts

- capture store: `tools/research/event_capture_store.py`
- manual entry: `tools/research/forward_capture.py`
- current store: `docs/research/fomc_forward_capture_current_2026-10-29.jsonl`
- legacy store (migrated): `docs/research/fomc_forward_capture_2026-10-29.jsonl`
- backfill store: `docs/research/fomc_backfill_capture_2026-10-29.jsonl`
- SEC audit: `docs/research/sec_timestamp_audit_2026-10-29.json`
- PIT policy: `docs/research/PIT_RESEARCH_ADMISSION.md`
