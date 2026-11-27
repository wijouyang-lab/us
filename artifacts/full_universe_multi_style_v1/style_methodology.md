# Style Methodology

All styles use independent screens; no unified composite score.

## Base eligibility
- COMMON or ADR.
- FS2 `tradability_status=ELIGIBLE_FOR_RESEARCH`.
- CA status not `CORPORATE_ACTION_REVIEW`.
- ADV20 >= $2,000,000.
- Peer group (security_type | industry) has >=20 eligible names.
- No ETF/ETN/warrant/preferred.

## VALUE
Existing FS2 `value_pct` (PB/PS/Earnings Yield/FCF Yield; PE only eligibility). Candidate if pct >= 0.80. Special financials excluded from standard cross-industry comparison.

## QUALITY
Existing FS2 `quality_pct` (30% ROE, 25% ROA, 25% CFO/assets, 20% inverse leverage). Candidate if pct >= 0.80.

## GARP
Existing `garp_pct` (historical growth only; no forward EPS/PEG). Candidate if pct >= 0.80.

## TREND
Peer percentile of FS2 `trend_pct` within security_type|industry; require >=0.80 and 60D return >0. CA-review names excluded. Raw prices, unadjusted.

## TURNAROUND
Requires 8 quarters of operating history, margin/OCF/FCF improvement and one-off exclusion. Current full-universe data does not provide this; **0 candidates**, not fabricated.

## Ranking
Within-style score is the existing peer percentile (0–1). Rows are ranked within style. `PRIORITY_RESEARCH` = top 10 per style with VERIFIED data and score >=0.90. No cross-style composite.
