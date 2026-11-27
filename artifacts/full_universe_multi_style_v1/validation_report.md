# Validation Report — Multi-Style Discovery V1

Date: 2026-11-27

## Automated tests

```text
pytest -q tests/test_multi_style_discovery.py
.......... [100%]
10 passed in 0.50s
```

Covered:

1. 5,600 universe count.
2. Unique ticker/style rows.
3. COMMON/ADR only.
4. No composite/research_rank column in candidate files.
5. Peer group n >= 20.
6. Priority capped at 40, <=10 per style.
7. Style counts: VALUE 115, QUALITY 345, GARP 341, TREND 541.
8. Snapshot SHA matches.
9. Page asset exists.
10. Source register has SHA256.

## Chromium E2E

Real Chromium against local HTTP:

```text
loaded: true
meta: 2026-11-25 · 1342 candidates · 40 priority · 5600 universe
value: 115
priority: 40
small cap: 64
risk negative FCF: 138
Apple search: 2
detail: true
SHA mismatch fail-closed: true
```

Screenshot: `artifacts/full_universe_multi_style_v1/multi_style.png`.

## Data validity

- Prices are unadjusted yfinance closes, 2026-11-25.
- Fundamentals 2026-11-05, current cross-section, not PIT.
- No forward EPS/PEG.
- 470 CA review names: excluded from TREND and base eligibility.
- 739 UNKNOWN, 569 BLOCKED, 3,775 PARTIAL, 517 VERIFIED.
- Missing values remain blank/N/A; no zero fill.
- Turnaround has 0 candidates because 8-quarter operating history and one-off
  adjustments are not available across 5,600 names; not fabricated.

## Limitations

- 8-quarter full-universe financials are not available; style ranks rely on
  existing FS2 peer percentiles, which are cross-sectional.
- No historical PIT verification; no alpha claim.
- No full fundamental review of 40 priority names.
- No production/PAPER/IBKR changes.
