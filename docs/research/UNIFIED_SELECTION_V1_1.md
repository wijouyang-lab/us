# Unified Selection V1.1 — Industry Comparability & Raw Metrics

Date: 2026-11-26
PR #632, branch `research/unified-stock-selection-v1`

## Comparability audit

Code evidence:

- Value percentiles: `build_rankings.py` lines 133–145 group by
  `(model_family, accounting_standard)` and winsorize 1/99 within group.
- Quality: inherits P6.6 peer percentiles; `build_rankings.py` lines 204–225
  independently recompute peer percentiles by
  `(model_family, accounting_standard, metric)`.
- GARP: `build_rankings.py` lines 259–270 group historical metrics by
  `(model_family, accounting_standard)`.
- Trend: FS2 `trend_pct` is a **global** percentile over all priced names.

Conclusion:

- Value/Quality/GARP are industry+accounting peer adjusted.
- Trend is not.
- Therefore the old global 4-style composite is **NOT_COMPARABLE** across
  industries and security types. It is retained only as legacy diagnostic.

## New grouping

`comparable_group = security_type | industry | SPECIAL_FINANCIAL/STANDARD`.

- 30 groups total.
- 23 groups have n ≥ 20.
- 517 rows have all 4 dimensions and belong to n ≥ 20 groups; only these get a
  within-group `group_rank` and `composite_status=GROUP_COMPARABLE_DISPLAY_ONLY`.
- All other rows: `composite_status=NOT_COMPARABLE`, `research_rank` empty.
- BANKS/INSURANCE/REIT/OTHER_FINANCIALS: 959 rows, flagged
  `special_industry=true`; they are not compared to standard-industry peers.
- `composite_legacy_not_comparable=true` on every row.

## Groups

| Group | Count |
|---|---:|
| TIER_A | 40 |
| TIER_B | 106 |
| TIER_C | 2,876 |
| BLOCKED | 2,578 |

Tier A requires within-group rank ≤5, 4 dimensions, no risk flag. This is a
research priority, not BUY.

## Raw metric coverage

| Metric | Available |
|---|---:|
| PB | 3,280 |
| PS | 2,963 |
| Earnings Yield | 3,466 |
| FCF Yield | 2,808 |
| PE | **0 — UNAVAILABLE_NOT_IN_SOURCE_RANKING** |
| ROE / ROA / CFO/A / L/A | 2,404 each |
| Revenue growth 1Y | 3,904 |
| EPS growth 1Y | 2,382 |
| FCF growth 1Y | 1,844 |
| Trend 20D/60D/MA | computed from FS1 raw cache |

Missing numeric values remain NaN/empty; no zero fill. No PE was derived from
EY; it is explicitly unavailable.

## Traceability

- `fundamental_source` = value `source_url` where present, else `UNKNOWN`.
- `fiscal_period`, `filing_date`, `accession` merged from Value/Quality/GARP
  files where present; otherwise `UNKNOWN`.
- `revision_status=UNKNOWN`.
- Price: `YFINANCE_RAW_CLOSE`, `UNADJUSTED`, `price_as_of=2026-11-25`.
- GARP: `FORWARD_GROWTH_UNAVAILABLE`; `forward_eps`/`peg` UNAVAILABLE.

## Website

`terminal/unified.html` now loads v1.1 JSON (SHA-256 verified) and shows:
comparable group, group N/rank, composite status, raw value/quality/growth/trend
metrics, source/filing/accession, price adjustment/CA status.

E2E (Chromium): loaded 5,600; TIER_A 40; search Apple 4; detail has comparable
group/Quality raw/UNAVAILABLE; abort JSON → fail closed.

## Limits

- Trend is global, so even group composite is display-only, not a validated
  cross-industry score.
- Only 517 rows get group ranks; 5,083 are not comparable.
- Current cross-section, not PIT; unadjusted prices.
- No alpha/backtest/paper claim.

## Production

No Scan/Review/Evolve/score/ATR/stop/ledger/PAPER/IBKR changes. PR #630 not
merged or modified.
