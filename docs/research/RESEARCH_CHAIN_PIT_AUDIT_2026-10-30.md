# Research Chain PIT Audit

Date: 2026-10-30 UTC
Research only. No production or canonical changes.

## 1. Entry points checked

| Entry | PIT behavior | Status |
|---|---|---|
| `tools/research/event_capture_store.py` | capture status only; admission separate | hardened |
| `tools/research/forward_capture.py` | manual live capture; whitelist | hardened |
| `tools/research/capture_batch.py` | manual batch, first_seen preserved | added |
| `tools/research/pit_admission.py` | authoritative multi-evidence decision | hardened |
| `tools/research/pit_sample_audit.py` | cross-file latest-version audit | hardened |
| `tools/research/event_research_dataset.py` | now calls `admit` in forward mode | fixed |
| `tools/research/pit_event_eligibility.py` | now calls `admit` after temporal checks | fixed |
| `tools/research/fed_event_study.py` | retrospective only; no PIT mode | descriptive |
| `tools/research/fomc_event_study.py` | retrospective only; no PIT mode | descriptive |
| fixed-five factor tools | price-only; no event PIT claim | descriptive |

## 2. Bypass paths found and fixed

1. **`first_seen` non-null was enough in old code** 鈫?now requires explicit
   simulation flag, source evidence, published-time evidence, research-ready
   time, decision time, and decision evidence.
2. **`official_fed_page` alone was accepted as time evidence** 鈫?now requires
   `published_at_evidence=official_release_time_in_page` (or verified SGML).
3. **`decision_at` could be injected by audit CLI** 鈫?removed; records must
   carry a real `decision_at_utc` and `decision_evidence`.
4. **`event_research_dataset.py` computed its own `pit_eligible`** 鈫?now calls
   the unified `admit` function for forward mode.
5. **`pit_event_eligibility.py` used only timestamp order** 鈫?now calls
   `admit`; missing evidence fails with `pit_admission:*`.
6. **Stored `pit_eligible`/`pit_status` flags** are ignored by admission;
   editing JSONL cannot bypass the decision.
7. **Multi-version duplicates** are collapsed by `event_id` + highest version
   in the audit; files are deduplicated by path.

## 3. Actual audit output

Command:

```bash
python -m tools.research.pit_sample_audit \
  --store "docs/research/fomc_*capture*.jsonl" \
  --output docs/research/pit_sample_audit_2026-10-29.json
```

| Metric | Count |
|---|---:|
| raw JSONL records | 14 |
| unique events | 3 |
| real first-seen records | 1 |
| simulated records | 0 |
| simulation-flag missing (legacy) | 2 |
| late observations | 2 |
| historical backfills | 1 |
| published evidence insufficient | 2 |
| decision evidence insufficient | 3 |
| **PIT admitted** | **0** |

Current unique events:

```text
20100127 鈥?historical backfill / date-only
20250319 鈥?late observation
20261028 鈥?late observation
```

No event has a true short-lag live observation plus an independent strategy
decision record.

## 4. Batch capture

`capture_batch.py` actual run:

```text
batch-20261029-a: new=1, duplicate=0, updated=0, failed=0
batch-20261029-b: new=0, duplicate=1, updated=0, failed=0
```

- same event_id;
- same first_seen_at_utc;
- version 1 both times;
- batch summary JSONL separate from event JSONL;
- no scheduler.

## 5. SEC status

- 10/10 JSON `acceptanceDateTime` parsed;
- filingDate vs acceptance date mismatches 0;
- official SGML remains HTTP 403;
- no verified first-public-visibility time;
- SEC PIT admitted 0.

## 6. Tests

Latest targeted:

```text
44 passed
```

Covering:

- strict admission;
- missing simulation flag;
- unknown source/published evidence;
- naive timestamps;
- decision missing/early;
- stored flags cannot bypass;
- event dataset forward mode uses admission;
- `pit_event_eligibility` uses admission;
- multi-file/version dedupe;
- batch new/duplicate and first_seen preservation;
- unmatched glob / empty file error handling.

Full CI reported after commit.

## 7. Artifacts

- admission: `tools/research/pit_admission.py`
- audit: `tools/research/pit_sample_audit.py`
- batch: `tools/research/capture_batch.py`
- runbook: `docs/research/FED_LIVE_CAPTURE_RUNBOOK.md`
- audit JSON: `docs/research/pit_sample_audit_2026-10-29.json`
- event dataset: `tools/research/event_research_dataset.py`
- eligibility: `tools/research/pit_event_eligibility.py`
