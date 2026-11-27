# Tier A 30 — TTM & Valuation Audit Summary

Date: 2026-11-27
PR #633 base; audit branch `research/tier-a-30-valuation-audit-v1`.

## Result

- 30/30 companies have a TTM or explicit FY-as-TTM state.
- 26 companies: `FY + latest YTD - prior-year YTD`.
- 4 companies: latest annual report is the latest period (`FY_AS_TTM`): DHI, AMTM, WDFC, GSL.
- 0 companies with `TTM_UNAVAILABLE` in the final table.
- Previous labels `revenue_ttm`, `net_income`, `fcf` were not true TTM for 26 companies. They are replaced.

## Before → after highlights

| Ticker | P/E before | P/E TTM | EV/FCF before | EV/FCF TTM |
|---|---:|---:|---:|---:|
| SFM | 9.39 | 9.91 | 10.29 | 14.27 |
| LRN | 9.93 | 10.05 | 7.46 | 6.40 |
| G | 13.40 | 12.58 | 10.96 | **22.65** |
| ADUS | 23.81 | 20.56 | 21.28 | 15.31 |
| TMDX | 17.22 | **22.69** | 21.12 | **62.65** |
| COLL | 12.36 | **20.35** | 1.96 | 1.91 |
| CRMD | 2.78 | 7.08 | 0.56 | 0.32 |
| IPAR | 27.13 | **34.99** | 24.34 | 19.22 |

Full table: `valuation_before_after.csv`.

## Debt corrections

The old extraction could take one debt tag and miss current/noncurrent components. Material changes:

| Ticker | Old debt | New debt | Note |
|---|---:|---:|---|
| DHI | N/A | $6.05B | `NotesPayable` now captured; old debt was missing |
| PPG | $6.16B | $6.83B | components added |
| CHD | $1.78B | $2.21B | components added |
| GSL | $0.54B | $0.82B | current/noncurrent components |
| HII | $2.70B | $2.91B | current portion |
| TMDX | $54.8M | $34.0M | reduced by component reconciliation |

`balance_sheet_debt_audit.csv` records `TOTAL_TAG` vs `SUM_COMPONENTS`; no total and components are added together.

## Five CONTINUE reassessment

See `five_continue_reassessment.md`. **G and TMDX are downgraded to WATCH** on TTM cash-flow/valuation evidence. The original PR #633 is not edited; this audit recommends the change.

## Remaining limitations

- SEC XBRL tags vary; some companies lack gross profit/D&A or a clean debt tag.
- TTM uses YTD cash-flow data, which is YTD not single-quarter; the formula is FY + YTD − prior YTD, not a sum of four standalone quarters.
- DHI/AMTM/WDFC use latest annual because no later interim was available; GSL is a 20-F filer with annual only.
- NRDS market cap uses FS2 2026-11-05 fallback because SEC share count is missing.
- No PIT, no adjusted total-return prices, no forward estimates.
- Price date is 2026-11-25.

## Files

- `ttm_metrics.csv`
- `balance_sheet_debt_audit.csv`
- `quarter_period_audit.csv`
- `valuation_before_after.csv`
- `five_continue_reassessment.md`
- `data_quality_tests.md`
