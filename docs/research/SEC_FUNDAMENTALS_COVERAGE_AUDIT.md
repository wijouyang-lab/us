# SEC Fundamentals Coverage Audit — P2.1

Date: 2026-11-04
Sample: **28 companies**, not full-market coverage.

## 1. Decision summary

P2.1 fixes period/PIT/ROE/debt logic and adds ROIC, interest coverage, 5-year
stability, operating leverage ratio and margin expansion.

Still intentionally blocked:

- all price-based valuation (no authorized quote);
- PEG (no licensed forward EPS);
- XOM historical identity (SEC current ticker maps to a new holding company).

## 2. Sample

28 tickers:

```text
AAPL MSFT GOOGL NVDA CRM ADBE
AMZN HD MCD NKE
CAT HON UNP
XOM CVX NEE DUK
JNJ PFE UNH MRNA
JPM BAC BRK.B MET
PLD O
RIVN
```

Sectors are currently supplied by the caller. SEC SIC extraction is **not yet
implemented**; `sic`/`sicDescription` exist in Submissions and are next-step work.

Identity:

- SEC ticker map hits: **28/28**
- usable CompanyFacts with revenue: **27/28**
- XOM: SEC currently maps to `ExxonMobil Holdings Corp`, CIK 2115436, 555 facts,
  no historical revenue. Predecessor CIK 34088 was not silently substituted.
  XOM is `INSUFFICIENT_DATA`.

## 3. Metric coverage (OK / 28)

| Metric | Coverage |
|---|---:|
| Revenue | 27 |
| Net income | 27 |
| Free cash flow | 21 |
| Stockholders' equity | 24 |
| Total debt | 22 |
| Gross margin | 12 |
| Operating margin | 21 |
| Net margin | 27 |
| ROE | 23 |
| **ROIC** | **7** |
| FCF conversion | 21 |
| Debt/equity | 24 |
| Net debt/EBITDA | 6 |
| **Interest coverage** | **12** |
| **Revenue stability** | **26** |
| **Earnings stability** | **17** |
| Revenue growth | 27 |
| EPS growth | 24 |
| FCF growth | 18 |
| 3y revenue CAGR | 27 |
| 5y revenue CAGR | 25 |
| **Operating leverage ratio** | **15** |
| **Operating margin expansion** | **15** |
| PEG | 0 (blocked) |
| PE/PB/EV/FCF yield | 0 (blocked) |

## 4. Period handling

Revenue period types: TTM 25, FY 2, missing 1 (XOM).

Rules:

- TTM requires four non-overlapping consecutive quarters spanning 350–380 days.
- YTD differencing only within the same fiscal year, concept, unit and matching
  start/end: Q2 = H1 − Q1, Q3 = 9M − H1, Q4 = FY − 9M.
- FY fallback is explicitly labelled `FY`.
- FCF requires identical CFO/CapEx start/end; otherwise `INSUFFICIENT_DATA`.
- Every metric carries period_start/end/type, fiscal year/period and all inputs.

## 5. PIT behavior

- timestamp as-of: OBSERVED_FIRST_SEEN uses first_seen; ACCEPTANCE_ESTIMATE uses
  accepted_at; FILED_DATE_ONLY is excluded on the same calendar day and allowed
  only on later days; UNKNOWN is excluded.
- date-only as-of: filing must be strictly before the date.
- no silent timestamp truncation.
- amended filings are separate facts; historic as-of keeps the older version.

Current OK-metric quality:

| Quality | Count |
|---|---:|
| ACCEPTANCE_ESTIMATE | 611 |
| FILED_DATE_ONLY | 36 |
| OBSERVED_FIRST_SEEN | 0 |
| UNKNOWN | 0 |

No OBSERVED_FIRST_SEEN is claimed; this is a historical backfill.

## 6. ROE before/after

| Company | Old (period-end equity) | New (average equity) |
|---|---:|---:|
| AAPL | 111.4% | 142.3% |
| MSFT | 28.6% | 34.2% |
| NVDA | 77.0% | 117.2% |

ROE uses TTM net income / average beginning-ending equity, with both equity facts
in `input_facts`. Negative average equity → `NOT_APPLICABLE`.

## 7. TTM / FCF before/after

- Old TTM took the latest four 70–100 day facts without continuity checks.
- New TTM rejects overlaps/gaps and falls back to FY or insufficient.
- AAPL revenue changed from 458.39B to 478.83B after period/version correction.
- FCF requires identical CFO/CapEx periods; bank/REIT FCF often returns
  `INSUFFICIENT_DATA` instead of mixing periods.

## 8. Debt and EV

Debt rule is stored in `debt_rule`:

- if `LongTermDebt` total exists, add only `ShortTermBorrowings`; do not add
  `LongTermDebtCurrent` again;
- else `LongTermDebtNoncurrent + LongTermDebtCurrent + ShortTermBorrowings`;
- missing debt → `INSUFFICIENT_DATA`, not zero.

```text
EV = market cap + total debt - cash
```

Only when market cap, debt and cash are valid. Missing debt/cash returns
`INSUFFICIENT_DATA`. EV/EBITDA requires matching EBIT/D&A periods and positive
EBITDA.

## 9. ROIC

```text
NOPAT = EBIT × (1 - effective tax rate)
Invested Capital = interest-bearing debt + equity - cash
ROIC = NOPAT / average invested capital
```

- effective tax = tax expense / pretax income, same period;
- missing tax, pretax <= 0, tax rate outside 0..1, average IC <= 0, missing
  beginning/ending balances → explicit non-OK status;
- banks/insurers → `NOT_APPLICABLE`;
- all inputs retained, beginning and ending.

## 10. Interest coverage

EBIT / interest expense with matching periods. Interest-income concepts are not
mapped. Missing/zero interest → `INSUFFICIENT_DATA`/`NOT_APPLICABLE`, never
Infinity. Banks/insurers → `NOT_APPLICABLE`.

## 11. Stability and GARP

- Revenue stability: 5 annual observations, yearly growth, positive years, CAGR,
  volatility.
- Earnings stability: 5 annual operating-income observations, negative years and
  sign changes retained.
- Fewer than 5 years → `INSUFFICIENT_DATA`.
- GARP separates:
  - `operating_leverage_ratio = OI growth / revenue growth`;
  - `operating_margin_expansion = OI growth - revenue growth`.
- zero/non-positive bases → `NOT_APPLICABLE`; periods must match.

## 12. Provenance audit

All OK metrics checked for non-empty `input_facts`, period type, formula version,
concept/unit/start/end/filed/accepted/accession/form.

Result: **0 OK metrics with missing provenance.**

## 13. Tests

```text
tests/test_sec_client.py        3 passed
tests/test_sec_fundamentals.py  9 passed
tests/test_sec_p21.py          15 passed
```

P2.1 tests include same-day 16:00/20:00 acceptance, filed-only same-day
exclusion, observed first-seen, missing quarter, average-equity ROE, missing-cash
EV, ROIC/interest matching, and GARP leverage ratio.

## 14. Still missing

- SIC-based industry classification;
- full-market ingestion;
- bank/insurer ROIC model;
- complete interest-expense tag coverage;
- authorized price/current shares;
- exact intraday historical visibility;
- 10-K/10-Q body parsing;
- pages and order API.


## 15. P2.2 addendum

- ROIC now requires EBIT/tax/pretax exact period and period_type equality; beginning
  and ending Debt+Cash+Equity are matched to one balance-sheet date.
- Net Debt input_facts contain Total Debt components and Cash.
- Net Debt/EBITDA input_facts contain Debt, Cash, EBIT and D&A.
- EV is refused when Debt or Cash is missing; no zero substitution.
- TTM/YTD selects one XBRL concept per series; no Revenue alias splicing.
- Stability requires five consecutive fiscal years.
- GARP zero revenue growth: margin expansion can be OK while leverage ratio is
  NOT_APPLICABLE.
- DCF is in `tools/investment_research/value/dcf.py`; 17/28 sample companies have
  an OK scenario DCF, with discount/terminal/growth sensitivity tables.
- SIC classification is live: Banking 2, Insurance 3, REIT 2, Energy 2, Utilities 2,
  Healthcare 3, Retail 3, Software 4, Semiconductor 1, Technology Hardware 1,
  Industrial 4, Unmapped 1.
- XOM remains CIK 2115436 / insufficient history; no silent predecessor merge.
