# Data Quality Report

Universe 5,600; data quality is per row, not an overall claim.

| Metric | Count |
|---|---:|
| total_tickers | 5600 |
| COMMON | 5186 |
| ADR | 315 |
| other | 99 |
| price_liquidity_20d | 5044 |
| adv20_2m_plus | 3093 |
| market_cap_available | 5388 |
| verified | 517 |
| partial | 3775 |
| blocked | 569 |
| unknown | 739 |
| corporate_action_review | 470 |

## Rules

- BLOCKED: non-common / CA review / identity issue; not in candidates.
- UNKNOWN: no usable 4-dimension data.
- PARTIAL: 2–3 dimensions or peer sample/coverage gap.
- VERIFIED: 4 dimensions + eligible peer group n≥20 + price/liquidity + CA OK.
- Missing values are never zero; N/A remains blank.
- Prices unadjusted; CA names excluded from TREND.
- Special financials (BANKS/INSURANCE/REIT/OTHER_FINANCIALS) are not compared to standard-industry EV/FCF or FCF-yield distributions.
