# Unified Event Research Acceptance

Date: 2026-10-28
Research only. No production changes.

## Entrypoint

`tools/research/event_research_acceptance.py`

It combines:

- 503-panel and SPY freshness;
- updater metadata / failed ticker counts;
- stock readiness;
- SPY market-proxy readiness;
- archive integrity + rebuild;
- explicit exit code.

Exit codes:

```text
0 pass
2 valid but pending
1 fail / missing / corrupt
```

## Actual run

Command used real inputs and `archive_verify` from the first real run.

| Item | Value |
|---|---|
| Exit status | **pending** |
| Exit code | **2** |
| Panel latest | **2026-10-27** |
| SPY latest | **2026-10-27** |
| As-of | 2026-10-28T10:40Z |
| Required close | 2026-10-28 |
| Updater status | ok |
| Failed tickers | 0 |
| Stock readiness | 0 ready / 35 pending |
| SPY readiness | 0 ready / 35 pending |
| Archive verify | 1 run / 35 unique / 35 versions / 35 observations |
| Look-ahead flags | 0 |

Checks:

| Check | Status |
|---|---|
| panel/SPY date alignment | pass |
| required 10/28 close | **pending_provider_close** |
| updater | pass |
| stock readiness | pass (0 ready/35 pending) |
| SPY market mode | pass (0 ready/35 pending) |
| archive verify | pass |

The pending result is the correct outcome: a valid dataset with a future
provider close, not a corrupt archive.

## Artifacts

- `docs/research/event_research_acceptance_2026-10-28.json`
- `docs/research/event_capture_acceptance_checklist_2026-10-28.md`

## Tests

`tests/test_event_research_acceptance.py`:

- stale close returns pending, not pass;
- failed ticker count returns fail;
- missing input raises a clear error.

Plus existing archive/readiness tests.

## Boundary

- No event return experiment was run.
- No alpha claim.
- No production scan/scoring/stop/ledger/order/trigger changes.
