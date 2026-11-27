# Current Watchlist Methodology

## Universe
- 5,462 symbols with 14 months of daily data.
- 5,072 scored after merging current fundamentals and requiring 220+ observations.
- Main eligibility: COMMON/ADR; price ≥ $5; ADV20 ≥ $2M; 6m return >0; price ≥ 52w high × 0.75; price > MA50 > MA200; quality_pct available and filing date ≤ signal date; score ≥ 50.

## Score
- 50% trend percentile: 40% 12-1, 20% 6m, 20% 52w position, 10% above MA50, 10% relative SPY 6m.
- 35% existing quality_pct (ROE/ROA/CFO/assets/leverage), only if SEC filing date ≤ signal date.
- 15% liquidity (log ADV20).
- Risk penalty: 20d vol >65%, liabilities/assets >0.8, negative FCF.
- Industry cap: max 2 per industry; max 10 names; no padding.

## NOT predictive
The score is a ranking heuristic, not expected return. No historical alpha claim.

## Data limitations
- yfinance current 14-month window; free/rate-limited.
- Static 5,462-symbol universe; delisted not verified.
- Quality coverage 2,275 scored names.
- Current SEC facts may be revised; only filing date ≤ signal is checked.
- No PIT historical panel; page is a current watchlist, not a backtest.
