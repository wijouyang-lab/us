# P10.2 SEC Accession-Level As-Filed Pilot

Date: 2026-11-09
Status: **P10_2_SEC_AS_FILED_PARTIAL**
Strategy ready: **NO**

## 1. AAPL end-to-end

CIK `0000320193`; 10-K/10-Q/10-K/A/10-Q/A from 2009-01-01..2024-12-31.

Actual:

```text
filings:                 66
parsed inline XBRL:      23
no core/old format:      43
facts extracted:         4,467
accession timestamps:    66/66
trade-available dates:   66/66
```

All 43 failures are 2009-01-23..2019-01-30, before inline XBRL in these
filings. Parsed filings are 2019-05-01..2024-11-01. This is a real coverage
limit; no attempt was made to infer old values from later filings.

Per filing retained:

- accession, CIK, form, filing date;
- acceptanceDateTime;
- fiscal year/period;
- primary document URL;
- SHA-256;
- download time;
- parser version;
- parse status;
- trade-available date and timing class.

## 2. As-filed field extraction

Core fields found include:

- Revenue;
- Gross Profit;
- Operating Income;
- Net Income;
- Basic/Diluted EPS;
- Assets, Liabilities, Equity;
- Cash;
- Long-Term Debt;
- Operating Cash Flow;
- Capex;
- Basic/Diluted Shares;
- Shares Outstanding.

Facts remain per accession and period context; they are not collapsed to the
latest Company Facts values. `period_start`/`period_end` are retained.

## 3. Quarter/YTD and amendments

The pilot retains YTD/period contexts and multiple accession versions. It does
**not** yet implement a complete Q1/Q2/Q3/Q4 derivation or a full restatement
lineage. Those are marked incomplete, not replaced by later values.

- 10-K/A: 1 filing.
- 10-Q/A: 1 filing.
- Same-period multiple accessions are retained separately.

## 4. Trading availability

For every filing, `acceptanceDateTime` is converted to UTC and US/Eastern.
Conservative rule:

- pre-open on a trading day: same session;
- during/after session, weekend or holiday: next trading session.

No filingDate-is-signal-date shortcut. A later earnings-event study must use the
`trade_available_date`, not filingDate.

## 5. 30-company cross-section

Deterministic 30 tickers from the latest historical membership snapshot.
CIK mapping comes from SEC `company_tickers.json`.

```text
tickers:        30
with CIK:       30
metadata only:  30
as-filed parsed: 0 (this pilot only)
```

Limitations:

- current SEC ticker map, not a delisted-inclusive historical mapping;
- only metadata checked for 30 names;
- no claim of historical coverage;
- no claim of field coverage across 30 names.

## 6. 8-K

`aapl_8k_index.csv` contains 84 8-K filings with accession, filing date,
acceptanceDateTime, and raw item string. No event classification is created.
Only Item 2.02 may be treated as an earnings-related event in a later phase;
other items remain raw.

## 7. Quality status

```text
DATA_AVAILABLE:      AAPL 10-K/10-Q, SEC metadata, 8-K index
PIT_VERIFIED:        filing acceptance timestamps (AAPL sample)
COVERAGE_VERIFIED:   NO
STRATEGY_READY:      NO
```

Why not strategy-ready:

- 43/66 old filings did not parse;
- only one company was parsed end-to-end;
- 30-company sample is metadata-only;
- no delisted-inclusive CIK mapping;
- no QTD/YTD derivation or restatement lineage yet;
- no field-level cross-company coverage.

## 8. Next

1. Parse 2019+ inline XBRL for 30 historical names, including delisted names
   with known CIKs.
2. Build QTD from YTD using the **two accession versions** that were actually
   available at the time.
3. Add amendment/restatement lineage and as-of queries.
4. Build a field mapping dictionary and coverage table by company/year/field.
5. Only then test actual financial changes vs forward returns; still no
   analyst-consensus EPS surprise.

## 9. Files

```text
data/research/p10_2_sec_as_filed/
  aapl_filings_index.csv
  aapl_as_filed_facts.csv
  aapl_8k_index.csv
  field_coverage.csv
  cross_section_30.csv
  p10_2_coverage.json
  p10_2_status.json
docs/research/p10_2_sec_as_filed.md
tests/test_p10_2_sec_as_filed.py
```
