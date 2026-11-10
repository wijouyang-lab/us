# Fed Event Label Plan

Date: 2026-10-29 UTC
Retrospective planning only. No returns fabricated.

## Result

Input: 114 Fed 2026 retrospective events with exact publication timestamps.

Output:

`docs/research/fed_2026_press_label_plan_2026-10-29.json`

```text
events: 114
expected entry mapped: 114
expected +1 mapped: 114
expected +5 mapped: 114
actual return labels: 0
label_status: pending_price_provider
missing_reason: no_approved_price_provider
entry date range: 2026-01-06 .. 2026-10-16
```

The 114 are still `retrospective_backfill`; no first-seen and no PIT
eligibility.

## Fixed rules

- Exchange calendar: **XNYS**.
- Timestamp: exact page `published_at` in UTC.\n- Retrospective availability: `available_at=null`, `availability_known=false`;\n  `mapping_time=published_at` for planning only.
- If `published_at < session close`, entry = that session.
- If `published_at >= session close`, entry = next session.
- Weekend/holiday: next session.
- Early close: actual XNYS close, not 16:00 assumption.
- `+1` = entry + 1 XNYS session.
- `+5` = entry + 5 XNYS sessions.
- No natural-day addition.
- No return is generated without an approved price provider.
- Missing/ambiguous time: `missing_event_time`.
- Insufficient sessions: `missing_trading_session`.

The rule is deterministic and conservative. The old same-day-close rule is kept only as a comparison artifact; see `EVENT_ENTRY_RULE_AUDIT_2026-10-29.md`.

## Tests

`tests/test_event_label_plan.py`: **8 passed**

Covered:

- premarket and intraday -> same session;
- after close -> next session;
- weekend -> Monday;
- Thanksgiving holiday;
- early close (2026-11-27) -> next session;
- +1/+5 session mapping;
- cross-year;
- missing time;
- no return without provider.

## PIT separation

This plan is **not** a PIT label set. The 36-event PIT dataset remains separate:

```text
PIT events: 36
entry labels: 35
+1: 0
+5: 0
```

The 114 retrospective mappings cannot be added to the PIT 200-event/365-day
count.
