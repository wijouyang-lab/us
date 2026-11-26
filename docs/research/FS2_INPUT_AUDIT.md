# FS2 Input Audit

Date: 2026-11-25
PR: #630 / branch `research/full-universe-price-liquidity-v1`

## Fundamental inputs

| File | Rows | Status |
|---|---:|---|
| value_rankings.csv | 5,453 | 850 VALUE_EXPERIMENTAL_ALL_FOUR |
| quality_rankings.csv | 5,549 | 2,313 QUALITY_V1_SCORED |
| garp_rankings.csv | 5,453 | 3,101 GARP_EXPERIMENTAL_HISTORICAL_GROWTH |

- Value uses PB, PS, Earnings Yield, FCF Yield; PE only eligibility, not a
  duplicate scored factor.
- Quality formula matches 30/25/25/20 and has recompute mismatch checks.
- GARP is historical growth only; no forward EPS/PEG.
- Fundamentals as-of 2026-11-05, not PIT; do not call them PIT.

## Price inputs

- `price_cache_v1.csv.gz`: 704,128 rows, 5,044 tickers.
- 20D coverage 5,021/5,501 valid COMMON+ADR; COMMON 91.59%.
- ADV uses raw_close × raw_volume.
- 470 corporate-action review flags; all blocked.
- 457 no-data tickers.
- No full adjusted-price/total-return panel.

## Identity

- 5,615 rows, 5,600 VALID, 14 invalid symbol, 1 missing.
- COMMON 5,187; ADR 315; UNCLASSIFIED 113.
- Low-confidence mappings 22.

## Website

- Existing `dashboard/data/invest_terminal_data.json` selection is stale
  (2026-11-05 data, generated 2026-11-09).
- No dedicated FS2 page.
- New `dashboard/data/fs2_candidates_v1.json` is a data artifact only; not wired
  into a UI page.

## Conflicts / gaps

- Fundamental as-of and price as-of differ by ~20 days.
- Corporate-action flags are unconfirmed price jumps, not confirmed splits.
- Price basis is unadjusted.
- No daily automation; FS2 run is manual.
