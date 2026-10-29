# PIT Research Admission Rules

Date: 2026-10-29 UTC
Research-branch policy only. No production changes.

A record may enter a PIT research sample only if all conditions hold:

1. Stable event identity: source URL/ID can be normalized and deduplicated.
2. Source is official or has a documented, verifiable provenance.
3. `published_at` and `first_seen_at_utc` are separate fields.
4. `first_seen_at_utc` came from an actual system observation, not from a
   historical page date or a backfill run.
5. Historical backfills are explicitly `retrospective_non_PIT` and keep
   `first_seen_at_utc = null`.
6. A current observation of an old announcement is `late_observation_not_pit`;
   it cannot be used for historical event windows even though
   `first_seen_at_utc` is non-null.
7. The event was available before the trading decision time.
8. Event timestamps, price timestamps, timezone and exchange calendar agree.
9. Failed/revised observations have diagnostic status and version history.
10. No zero-fill, no interpolation, no synthetic event dates.
11. Small or overlapping samples are descriptive only; no alpha claim.

The event store must preserve prior versions and must never overwrite the first
successful observation timestamp.

SEC-specific rule: `acceptanceDateTime` from submissions JSON is not equivalent
to first public visibility or to `first_seen_at_utc`. Without an official SGML
acceptance header or a real observation, the timestamp is **UNVERIFIED** for PIT.
