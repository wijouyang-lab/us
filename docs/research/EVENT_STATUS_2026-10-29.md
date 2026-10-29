# Event Research Status — 2026-10-29 UTC

## Real archive

| Item | Value |
|---|---|
| Runs | 2 |
| First run | 40661139681 (2026-10-28) |
| Second run | 40807180694 (2026-10-29) |
| Archive commit | 420469c897f35a53bd7ecfe5876a629c58e9ce19 |
| Unique events | 36 |
| Versions | 36 |
| Observations | 70 |
| Verify | true |

Second run additions: +1 event, +1 version, 35 observations, 34 duplicate
observations, 0 revisions, 0 retractions, 0 timestamp conflicts.

## Price readiness

Using real archive and 2026-10-28 bars:

| Horizon | Count |
|---|---:|
| entry | 35 |
| +1 | 0 |
| +5 | 0 |
| pending entry | 1 |
| ready | 0 |
| excluded | 0 |
| look-ahead flags | 0 |

- 35 events first seen 2026-10-28 now have the 2026-10-28 entry bar.
- `+1` requires the 2026-10-29 close, which is not yet available.
- `+5` requires later sessions.
- No future bar is filled with zero.

## Gate

`event_experiment_gate_2026-10-29.json`:

```text
status: not_eligible
unique_events: 36
coverage_days: <1
entry_results: 35
plus_1_results: 0
plus_5_results: 0
```

Gap to preregistration:

```text
events: 36 / 200 (short 164)
coverage: <1 / 365 days
entry: 35 / 200
+1: 0 / 200
+5: 0 / 200
```

No alpha experiment was run.

## Source constraints

- Fed feeds: 20 + 15 events.
- BLS: skipped for missing real contact User-Agent; no placeholder identity.
- SEC: no contact User-Agent configured; no requests claimed.
- Third-party/free event sources (SEC announcements, earnings, macro calendar)
  have not been admitted; they need coverage and licensing review.

## Capture reliability

- Main workflow still has `workflow_dispatch` only; it is not self-scheduling.
- The scheduled-capture proposal is PR #398, still Draft and **not active**.
- Two real manual runs exist; no third run is claimed.
- Duplicate/idempotency and immutable snapshots are covered by archive tests.
- Missing price observations remain pending; no zero-fill.

## Next

- After 2026-10-29 close, append the real bar and recompute +1; +5 remains
  pending.
- Continue only real forward captures; do not count replay/simulation.
- Keep 200-event/365-day gate unchanged.
