# Data Quality Tests — TTM Audit

Command:

```text
pytest -q tests/test_tier_a_valuation_audit.py
.......... [100%]
10 passed in 0.39s
```

| # | Test | Result |
|---|---|---|
| 1 | 30 rows, unique tickers | PASS |
| 2 | 26 TTM rows satisfy FY + YTD − prior YTD | PASS |
| 3 | 4 FY_AS_TTM are exactly DHI/AMTM/WDFC/GSL | PASS |
| 4 | FCF = OCF − Capex for all populated rows | PASS |
| 5 | No valuation missing value is filled with 0 | PASS |
| 6 | Debt method is TOTAL_TAG / SUM_COMPONENTS / N/A | PASS |
| 7 | Market cap = price × shares (except NRDS fallback) | PASS |
| 8 | All price dates are 2026-11-25 | PASS |
| 9 | 120 period rows; YTD days >= 80 | PASS |
| 10 | 30 source URLs present | PASS |

## Limitations of the tests

- The TTM identity test uses the stored FY/YTD/prior-YTD values; it does not re-read the original SEC JSON for each row.
- It verifies period length >=80 days, not that every YTD start is exactly fiscal-year start; the audit table has start dates for manual review.
- `N/A` strings are parsed by pandas as NaN; the debt-method test treats NaN as the explicit N/A state.
- NRDS market cap is intentionally excluded from the price×shares identity because SEC share count is missing.
- No network calls in CI.

## Data gaps

- 4 companies use FY as TTM because no later interim exists: DHI, AMTM, WDFC, GSL.
- GSL is a 20-F filer; no 10-Q quarterly series.
- NRDS share count missing; FS2 market cap fallback.
- Some XBRL tags (gross profit, D&A, debt) are unavailable and remain N/A.
