# Second Event Capture Acceptance Checklist

Date: 2026-10-28
Status: prepared; not executed. Cross-day run requires UTC date >= 2026-10-29.

## Trigger

```bash
gh workflow run research-event-capture.yml --repo wijouyang-lab/us
```

- workflow must be `workflow_dispatch`
- must run from default branch
- no auto-trigger

## Before run

- [ ] `gh secret list` shows no secret values; only note configured/not configured.
- [ ] Record current `research/event-archive` HEAD.
- [ ] Record existing run IDs and artifact IDs.
- [ ] Confirm UTC date is >= 2026-10-29.

## After run

- [ ] New workflow run ID differs from `40661139681`.
- [ ] Workflow conclusion is `success`, not just CI.
- [ ] New artifact ID belongs to the new run.
- [ ] `research/event-archive` HEAD advanced and contains a new `runs/<new_run_id>/`.
- [ ] Old `runs/40661139681/` files unchanged (compare hashes).
- [ ] `event_archive_store verify` succeeds.
- [ ] New run's UTC date is 2026-10-29 or later.
- [ ] New run metadata records actual capture time, source statuses, event counts.
- [ ] Cumulative counts reconcile.

## Verification commands

```bash
git -c core.autocrlf=false clone \
  --branch research/event-archive --single-branch \
  https://github.com/wijouyang-lab/us.git /tmp/event-archive

python -m tools.research.event_archive_store verify --store /tmp/event-archive
```

## Required counts

Report:

- total runs
- unique events
- versions
- observations
- duplicate observations
- new events
- revisions
- retractions
- timestamp conflicts
- failures
- BLS/SEC status

## Failure handling

- Do not overwrite old snapshots.
- Do not rewrite first-seen.
- Do not count local replay as a real run.
- Do not use placeholder contacts.
- If push is blocked by branch rules, report exact error; do not expand permissions or write main.
