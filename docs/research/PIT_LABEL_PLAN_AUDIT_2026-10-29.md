# PIT Event Label Plan Audit

Date: 2026-10-29 UTC

## Input

- 36 real PIT events from the archive;
- `available_at` backed by first-seen evidence;
- `decision_at` equal to `available_at` in the current dataset;
- XNYS calendar;
- next-open entry rule.

## Plan result

```text
events: 36
expected entry dates: 36
expected entry 2026-10-28: 35
expected entry 2026-10-29: 1
actual entry price labels: 35
actual +1 returns: 0
actual +5 returns: 0
```

Why 35 actual entries:

- 35 events have the 2026-10-28 entry bar;
- 1 event has no 2026-10-29 close yet;
- expected entry date is not a real price or return.

## Field separation

| Field | Meaning |
|---|---|
| `available_at` | strategy first can use event |
| `decision_at` | strategy decision time; must be >= available |
| `mapping_time` | decision time used for entry planning |
| `entry_date` | expected tradable session |
| `entry_time_utc` | expected open |
| `return_1d/5d` | null until approved prices |

No event is mapped earlier than `decision_at`. No retrospective row is in this
file.

## Artifacts

`docs/research/event_pit_label_plan_2026-10-29.json`

## Blockers

- no approved price provider;
- +1/+5 remain null;
- 10/29 close not yet available.
