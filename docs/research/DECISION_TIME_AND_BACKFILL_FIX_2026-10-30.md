# Decision-Time and Backfill Semantics Fix

Date: 2026-10-30 UTC
Research only. No production changes.

## 1. Synthetic decision time removed

`.github/workflows/research-event-capture.yml` previously did:

```bash
decision="$(date -u -d '+20 minutes' +%Y-%m-%dT%H:%M:%SZ)"
... --decision-at "$decision"
```

This fabricated a decision time in the future. It has been removed.

The workflow now:

- runs only via `workflow_dispatch`;
- has no `schedule:` / `cron:`;
- passes no `--decision-at`;
- records capture and readiness only.

`run_event_capture_cycle.py` now accepts no decision by default and writes:

```text
pit_status = not_evaluated_no_decision_log
decision_at_utc = null
coverage_audit.eligible_events = 0
```

No default or fallback decision time is generated.

## 2. Backfill flag preserved

`event_research_dataset.py` had:

```python
"is_historical_backfill": False
```

It now passes the event's actual `is_historical_backfill` value.

`pit_admission.py` now fails closed:

- `True` 鈫?`historical_backfill`
- missing/None 鈫?`historical_backfill_flag_missing`
- only explicit `False` can pass

This applies to `pit_event_eligibility.py` too, because it routes through the
same admission function.

## 3. Workflow state

Repository state after this fix:

| Property | State |
|---|---|
| manual `workflow_dispatch` | present |
| scheduled cron | **removed** |
| workflow deployed on default branch | no |
| continuous background service | no |
| production trigger changed | no |

`run_event_capture_cycle` metadata now includes:

```text
scheduled_workflow_created = false
scheduled_workflow_active = false
pit_evaluated = false (when no decision is supplied)
```

## 4. Actual tests

```text
16 passed (workflow + capture cycle)
50 passed (PIT dataset/eligibility/capture chain)
```

Full CI reported after commit.

## 5. Current PIT status

- real unique events: 3
- late observations: 2
- historical backfill: 1
- true PIT-admitted: **0**
- SEC first-public-visibility: still unverified (SGML 403)
- continuous service: not deployed

## 6. Next official window

Recheck the official calendar before acting:

- https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- https://www.federalreserve.gov/newsevents/pressreleases/2026-press-fomc.htm

Next regular FOMC meeting: 2026-12-08..09. Only a real observation at release
time counts; no synthetic decision or backdated capture.
