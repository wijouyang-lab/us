# FS2.3 Test Coverage

Date: 2026-11-25
PR #630

## Totals

- Total Python tests in `tests/test_fs2_composite.py`: **34**
  - Direct decision-function tests: **21**
  - Static artifact/consistency checks: **13**
- Snapshot fault tests: **3** (A→B archive, corrupt C reject, manifest hash)
- Browser E2E assertions: **15** actual Chromium checks
- Existing project pytest result: **1551 passed, 1 skipped** before this round; final run recorded in report.

## Direct business tests (21)

Status:
- identity/ETF block
- CA block
- CA missing is blocked (not pass)
- missing price → INSUFFICIENT
- ADR → WATCH
- low ADV → BLOCKED
- stale → WATCH
- <60D → WATCH
- fully eligible
- ETF priority over CA
- ADR + low ADV → WATCH (ADR priority)
- CA priority over missing price
- stale + <60D → WATCH
- tier BLOCKED
- tier INSUFFICIENT
- tier1 requires 2 styles
- tier2 requires 1 style
- style 0 → WATCH
- pct_rank NaN preserved
- snapshot validator accepts real 5,600 rows
- tier enum / eligible not blocked

Static checks (13): matrix, uniqueness, fixed counts, page existence, CA count,
style counts, shortlist subset, JSON/data presence, etc. They are NOT counted
as behavior tests.

## Browser E2E

Executed locally with Playwright Chromium 156, local HTTP server:
- load: PASS
- 5,600 rows in DOM paging: PASS (50 initial, 112 pages)
- style filter: 170 rows
- tier filter: 343 rows
- tradability filter: 2,098 blocked
- security type: 315 ADR
- industry: 16 options, 328 rows for first
- liquidity: 1,821 high
- ticker search: 1 AAPL
- detail: PASS
- sort: PASS (A first)
- pagination: 51–100, 50 rows
- warning: PASS
- dates/version: fs2.v1.4, 2026-11-25 / 2026-11-05
- JSON failure: clear error, no stale masquerade: PASS

Not tested: company-name search, page-refresh state, duplicate record across all
pages, old-snapshot banner. E2E 15/20 requirements.

Screenshots: `artifacts/fs2_3/candidates_page.png`, `candidates_failure.png`.
