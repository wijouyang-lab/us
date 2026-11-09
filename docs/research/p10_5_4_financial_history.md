# P10.5.4 Financial History and Amendment Audit

Date: 2026-11-09
Status: **P10_5_4_PARTIAL**
P10.6: **NOT AUTHORIZED**

## 1. AAPL quarterly facts

From 9,327 real accession facts:

- 11 fiscal years have Q1-Q4 QTD facts;
- 2 Q4 derivations completed: FY − Q1 − Q2 − Q3;
- no Company Facts backfill.

`aapl_quarterly_financials.csv` contains 9,327 fact rows with accession, tag,
unit, context, period start/end, duration, fiscal year and quarter.

`aapl_period_validation.csv` reports per-fiscal-year quarter/field coverage.

`aapl_qtd_ytd_derivation.csv` contains 2 real Q4 derivations (Revenue, Net
Income, CFO where available).

## 2. Amendment differences

30 comparison rows from AAPL amendments:

```text
UNIT_MISMATCH:    24
DUPLICATE_FACT:    6
TRUE_NUMERIC_CHANGE_CANDIDATE: 0
```

This explains the prior 19 “numeric differences” as **unit/duplicate issues**,
not verified restatements. No true numeric restatement was found; real as-of
testing remains DATA_BLOCKED.

`aapl_amendment_flag_audit.csv` marks AmendmentFlag as `FLAG_NOT_PRESENT`; it
was not read from the original amendment in this pass.

## 3. Form 25-NSE

The 3,663 number was an **unfiltered full-text hit count**, not 3,663 Form
25-NSE filings.

With `forms=25-NSE`, actual total is:

```text
45 hits
45 rows
```

The first page was parsed into filed-by/subject display names and CIKs.

Still not done:

- security class (common stock vs debt/ETF);
- ordinary-share exit verification;
- effectiveness date;
- historical S&P member intersection.

Therefore:

```text
verified common stock exits: 0
delisting_evidence.csv: empty
```

## 4. Decision

```text
P10_5_4_PARTIAL
P10_6_ALLOWED = false
```

No Shadow, no IBKR, no PAPER-50000.

## 5. Files

```text
data/research/p10_5_4_financial_history/
  aapl_quarterly_financials.csv
  aapl_qtd_ytd_derivation.csv
  aapl_period_validation.csv
  aapl_19_fact_differences_audit.csv
  aapl_amendment_flag_audit.csv
  aapl_fact_version_history.csv
  real_asof_query_tests.csv
  form25_accessions_deduplicated.csv
  form25_filed_by_subject.csv
  form25_security_classification.csv
  historical_common_stock_exits.csv
  delisting_evidence.csv
  p10_5_4_status.json
docs/research/p10_5_4_financial_history.md
tests/test_p10_5_4_financial_history.py
```
