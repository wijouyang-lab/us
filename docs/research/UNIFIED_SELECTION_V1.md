# Unified Stock Selection V1

Date: 2026-11-26
Branch: `research/unified-stock-selection-v1`
Base: `research/full-universe-price-liquidity-v1` (PR #630, stacked research PR)
Status: RESEARCH ONLY — NOT A BUY/SELL SIGNAL

## Inputs

- FS2 composite: `data/research/fs2/composite_candidates_v1.csv`
- 5,600 unique tickers; FS2 v1.4
- Fundamentals as-of 2026-11-05; prices 2026-11-25
- Price unadjusted; no PIT; no historical backtest claim.

Input SHA256:
`2cc5a072c93bf4d5b2cb5ff306bb2835914e3b8000c8d34e190b5b686fb97e92`

## Model

Existing ranks/percentiles only, no new factor:

- Value: FS2 `value_rank` / `value_pct` (850 scored)
- Quality: `quality_rank` / `quality_pct` (2,312)
- GARP: `garp_rank` / `garp_pct` (3,101), historical growth only
- Trend: `trend_pct` (5,501), RAW_PRICE_RESEARCH_ONLY

`dimension_coverage` = count of available style percentiles.  
`composite_ready` requires all 4 percentiles and non-blocked status.  
`composite_score` is the equal-weight mean of the four percentiles **only when
all four exist**; it is a display ordering, not a validated return forecast.
Missing dimensions stay NaN and never become zero.

## Results

| Group | Count |
|---|---:|
| TIER_A | 16 |
| TIER_B | 262 |
| TIER_C | 2,744 |
| BLOCKED | 2,578 |
| composite_ready | 517 |
| composite_not_ready | 5,083 |

Data quality:

| Status | Count |
|---|---:|
| FULL | 660 |
| PARTIAL | 2,919 |
| MINIMAL | 1,922 |
| MISSING | 99 |

Blocked/insufficient rows have `research_rank` NaN.  
Tier A is a research-priority group, not BUY.

## Files

- `data/research/unified_selection/unified_selection_v1.csv`
- `unified_top100_v1.csv`
- `unified_selection_summary.json`
- `dashboard/data/unified_selection_v1.json`
- `dashboard/data/unified_selection_v1.sha256`
- `terminal/unified.html`

Output SHA256:
`2ea6ca284bcb535380d3fcb5590d9cc553c146e49f8eade1c777cb6d30a6387d`

## Website

Unified Selection page:
- 5,600 rows, search, group/security/industry/data-quality filters, sorting, paging, details.
- Browser checks: load 5,600; Tier A 16; search Apple 4; AAPL detail; JSON abort fail-closed.
- Screenshot: `artifacts/unified_selection/unified_page.png`.

## Limits

- Only 660 rows have all four dimensions; 5,083 cannot form a comparable composite.
- Only 16 Tier A; small candidate set.
- Fundamentals are current cross-sectional, not PIT.
- Prices unadjusted; 469 CA blocked; 457 no-data names excluded.
- No return/alpha validation, no paper trading.

## Production boundary

No Scan/Review/Evolve/score/ATR/stop/PAPER/IBKR changes. New branch and Draft
PR only; PR #630 is not merged or modified.
