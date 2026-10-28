# Secret-Free RSS Capture and BLS Contact Requirement

Date: 2026-10-28
Research only. No production changes.

## Result

- Federal Reserve RSS works with an honest project User-Agent and **no secret**.
- BLS RSS returns **HTTP 403** without a contact-bearing User-Agent.
- The collector now skips BLS per-feed when no contact User-Agent exists, while
  continuing Fed collection.
- A clean no-secret capture produced **35 Fed events** from 2/4 sources.
- BLS is explicitly marked `skipped_missing_contact_user_agent`; it is not treated
  as zero events and not fabricated.

## User-Agent decisions

Default used:

```text
wj-quant-research/1.0 (+https://github.com/wijouyang-lab/us)
```

No email, fake identity, or secret is embedded.

Actual BLS test with that User-Agent:

```text
HTTP 403 Forbidden
```

Actual Fed test with the same User-Agent:

```text
HTTP 200
```

Therefore `OFFICIAL_FEED_USER_AGENT` is **not** a blanket requirement:

- Fed feeds: no secret required.
- BLS feeds: a real contact-bearing User-Agent is required by the source.
- SEC: separate `SEC_USER_AGENT` requirement; still absent.

## Secret-free capture

Clean directory:

```text
docs/research/event_forward_nosecret_2026-10-28/
```

| Metric | Value |
|---|---:|
| Runs | 2 |
| Configured sources | 4 |
| Successful sources | 2 |
| Skipped BLS sources | 2 |
| Events per run | 35 |
| Unique events | 35 |
| Archive versions | 35 |
| Total observations | 70 |
| Duplicate observations | 35 |
| Audit status | pass |
| Real revisions | 0 |
| Real retractions | 0 |

Source quality:

| Source | Events | Capture success |
|---|---:|---:|
| bls_cpi_rss | 0 | 0% (skipped) |
| bls_employment_situation_rss | 0 | 0% (skipped) |
| federal_reserve_press_rss | 20 | 100% |
| federal_reserve_speeches_rss | 15 | 100% |

The two runs are on the **same UTC date**; this is not multi-day evidence.

## Important correction to earlier 59-event capture

The earlier 59-event BLS/Fed captures used `contact@example.com`, which is not a
real contact identity. They remain technical demonstration artifacts but are
**not** valid BLS PIT evidence. Do not use those BLS records for event alpha.

The clean secret-free Fed capture is the defensible forward evidence until a
real BLS contact secret is configured.

## Files

- `docs/research/event_forward_nosecret_2026-10-28/event_archive.json`
- `.../source_quality.json`
- `.../revision_audit.json`
- `.../*.events.json`, `*.metadata.json`, `*.audit.json`

## Workflow

The workflow was split into a separate minimal Draft PR:

https://github.com/wijouyang-lab/us/pull/394

It is `workflow_dispatch` only and no longer requires a secret for Fed feeds.
Until that PR is reviewed/merged, dispatch from the default branch remains
blocked.

## Remaining blockers

- Real BLS contact User-Agent secret (`OFFICIAL_FEED_USER_AGENT`) is absent.
- `SEC_USER_AGENT` is absent; SEC requests remain 0.
- No cross-day forward sample yet.
- No event alpha claim.
