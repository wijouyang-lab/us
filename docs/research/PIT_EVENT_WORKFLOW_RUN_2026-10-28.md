# Default-Branch Research Event Workflow Run

Date: 2026-10-28
Research only. No production changes.

## Run

| Item | Value |
|---|---|
| Workflow | `Research Event Capture` |
| Trigger | manual `workflow_dispatch` |
| Run ID | `40657490417` |
| Run URL | https://github.com/wijouyang-lab/us/actions/runs/40657490417 |
| Commit | `1f747202c6f73b6b842c2c7941947c997cb5da23` |
| Artifact | `research-event-capture-40657490417` |
| Artifact size | 15,281 bytes |
| Artifact retention | 90 days |
| Job result | **success** |

This is a real default-branch workflow execution, not a local simulation.

## Capture result

| Metric | Value |
|---|---:|
| Events | **35** |
| Configured sources | 4 |
| Successful sources | 2 |
| Skipped BLS sources | 2 |
| Audit status | **pass** |
| Eligible at decision time | **35/35** |
| Unique events | 35 |
| Versions | 35 |

Source status from the artifact metadata:

| Source | Status | Events |
|---|---|---:|
| bls_cpi_rss | `skipped_missing_contact_user_agent` | 0 |
| bls_employment_situation_rss | `skipped_missing_contact_user_agent` | 0 |
| federal_reserve_press_rss | `ok` | 20 |
| federal_reserve_speeches_rss | `ok` | 15 |

SEC was not part of this workflow run. `SEC_USER_AGENT` remains absent;
SEC request count is **0**.

## Artifact contents

- `event_capture_20261028T083250320591Z.events.json`
- `event_capture_20261028T083250320591Z.metadata.json`
- `event_capture_20261028T083250320591Z.audit.json`
- `event_archive.json`

Copied to:

`docs/research/event_forward_workflow_2026-10-28/`

## Workflow review

- `workflow_dispatch` only; no schedule/push/pull_request/workflow_run.
- `permissions: contents: read`.
- No production workflow dependency or concurrency group.
- `OFFICIAL_FEED_USER_AGENT` is optional; Fed uses honest project default.
- BLS is skipped per-source without contact UA.
- Artifact upload uses `if-no-files-found: error` and 90-day retention.
- Logs do not print secret values.

## Limitations

- Only one default-branch run so far.
- Still same UTC date as earlier captures; not cross-day evidence.
- No BLS or SEC data.
- No event alpha claim.
