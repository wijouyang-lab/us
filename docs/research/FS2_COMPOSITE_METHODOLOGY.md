# FS2 Composite Methodology

Date: 2026-11-25
Status: RESEARCH_ONLY / NOT_A_BUY_SIGNAL

## Inputs

- Value/Quality/GARP rankings: `data/universe/selection/*_rankings.csv`
- Identity: FS-1 `universe_identity_v1.csv`
- Price/ADV/CA: FS-1 `price_cache_v1.csv.gz`, `liquidity_metrics_v1.csv`
- Fundamentals as-of: 2026-11-05; prices as-of: 2026-11-25

## Style scores

- Value: existing `value_rank` (PB, PS, Earnings Yield, FCF Yield).
- Quality: existing `quality_rank` (0.30 ROE + 0.25 ROA + 0.25 CFO/Assets +
  0.20 inverse leverage peer percentile).
- GARP: existing `garp_rank`, historical growth only, no forward EPS/PEG.
- Trend: FS-2 raw-price score:
  sign(20D return) + sign(60D return) + sign(price>MA20) + sign(MA20>MA60)
  − 1 if 60D drawdown < -15%.
  Marked `RAW_PRICE_RESEARCH_ONLY`; unadjusted prices.

Each style is a separate top-20% list; no simple average of scores.

## Tradability

- COMMON only for core; ADR is WATCH-only separate.
- ELIGIBLE requires 20D price, ADV20 ≥ $2,000,000 (research floor),
  CA OK, data age ≤7 days, 60D available.
- BLOCKED: corporate-action review, ETF/preferred/unclassified, missing price,
  liquidity below floor.
- INSUFFICIENT_DATA: 20D missing.

## Composite tiers

- TIER_1: at least 2 style top-20% tags + ELIGIBLE.
- TIER_2: one style tag + ELIGIBLE.
- WATCH: style tag but ADR/stale/insufficient, or no tag.
- BLOCKED: tradability blocked.

This is a research prioritization, not an expected-return probability.

## Counts

- Universe: 5,600
- Value top20%: 170
- Quality top20%: 463
- GARP top20%: 621
- Trend top20%: 1,107
- Multi-style: 404
- TIER_1: 343; TIER_2: 888; WATCH: 1,890; BLOCKED: 2,479
- ELIGIBLE_FOR_RESEARCH: 2,774
- Corporate-action blocked: 850
- Missing price: 579

## Limitations

- Fundamentals are current cross-sectional, not PIT.
- Prices unadjusted; no total return.
- 850 CA-blocked names cannot be promoted.
- 579 names lack price.
- Website integration is JSON-only; no dedicated UI page yet.
