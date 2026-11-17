# P12.1: US Individual-Stock Fundamental and Event Data Audit

Date: 2026-11-17
Branch: `research/p12-event-fundamental-feasibility`
Status: **DATA FEASIBILITY ONLY — NO STRATEGY, NO PURCHASE**

---

## 1. Question

Can free data support real historical PIT research on US individual stocks for:

- fundamentals;
- 10-K/10-Q/8-K events;
- earnings and company announcements;
- news and corporate events;
- macro/policy events;
- analyst expectations?

Short answer:

```text
Macro PIT:                 READY_RESTRICTED
SEC filings/fundamentals:  READY_RESTRICTED (small sample; as-filed required)
Market-wide fundamental PIT: DATA_BLOCKED
Exact earnings timing:     DATA_BLOCKED
Structured 8-K event data: DATA_BLOCKED
Historical news sentiment: DATA_BLOCKED
Analyst estimates:         NO_BUY / DATA_BLOCKED
```

No factor or model is built here.

---

## 2. Existing project evidence retained

- P6 Fundamental Selection V1: `CURRENT_CROSS_SECTIONAL_RESEARCH`,
  `PIT_BACKTEST_BLOCKED`.
- P9.1: all 8 `NO-GO`; unchanged.
- P10: `NO_BUY`; unchanged.
- P10.6 SEC pilots: `PIT_PILOT_PARTIAL`, `FSNDS_PILOT_PARTIAL`; not
  `READY_FOR_BACKTEST`.
- P11: price-factor route closed `NO-GO`.

P6/P10.6 are not proof of a market-wide historical PIT panel.

---

## 3. Data-source inventory

File: `data/research/p12_1_data_source_inventory.csv`

Columns:

```text
source, type, history_start, history_end, stock_coverage, delisted,
pit_timing, delay, missing_rate, free_limit, cost, license, status, notes, evidence_url
```

### SEC CompanyFacts

- all SEC XBRL filers;
- facts carry accession/filing dates, but `companyfacts` is a **latest restated
  view**, not a historical as-filed panel;
- exact PIT requires accession-level facts / FSNDS;
- free, public domain, fair-access rate limits;
- status: `READY_RESTRICTED`.

### SEC submissions / 10-K / 10-Q / 8-K

- filing dates and acceptance datetimes;
- 8-K item codes, but not a structured event/announcement-time database;
- exact press-release time (before/after market) is not guaranteed;
- status: `READY_RESTRICTED` for filing-date research.

### SEC Financial Statement Data Sets (FSNDS)

- quarterly as-filed numeric data, 2009 Q1 onward;
- large archives; one quarter was tested in P10.6.8;
- accession-level as-filed data is the best free route to PIT fundamentals;
- status: `READY_RESTRICTED` for a limited panel, not market-wide.

### SEC full-text search

- filing text, 2001+;
- useful for 8-K discovery;
- not a clean event taxonomy or release-time feed;
- status: `READY_RESTRICTED`.

### FRED / ALFRED

- macro series and release calendar;
- ALFRED provides real-time vintages;
- FRED alone is latest revised data, not PIT;
- status: `READY_RESTRICTED`.

### BLS / BEA

- CPI/PPI/employment/GDP;
- release timing and revisions need vintage handling;
- free API keys/limits;
- status: `READY_RESTRICTED` with revision caveats.

### Federal Register / FOMC / speeches

- policy/regulatory documents and publication dates;
- FOMC statements/speeches have official timestamps;
- event interpretation is not structured;
- status: `READY_RESTRICTED`.

### GDELT 2.0

- global news/event stream, 2015+;
- 15-minute updates;
- company matching/sentiment is a proxy, not verified company news;
- status: `READY_RESTRICTED`.

### Company IR / press releases

- issuer-specific;
- no standard historical archive/timestamp;
- earnings release exact time and guidance history are not uniform;
- status: `DATA_BLOCKED`.

### Analyst estimates / ratings

- no free historical PIT consensus/estimate revisions;
- current web pages are not a historical panel;
- paid vendor would be required;
- status: `NO_BUY` for the current $20/no-subscription constraint.

### FINSABER V2 news/filings

- 2.9M news rows / 71k filings (dataset card), 2009-2025;
- licence `other`, not cleared;
- status: `DATA_BLOCKED` for production.

---

## 4. Actual local coverage

### SEC filing sample

```text
tickers: 144
filings: 9,426
range: 1995-02-14..2026-11-05
forms: 10-Q 4,647; 6-K 3,078; 10-K 1,499; 20-F 177; 40-F 25
```

This is a **small sample**, not the full SEC universe.

File: `data/research/p12_1_filing_coverage_by_year.csv`

### P6 current fundamentals

```text
value rows:       5,453
value candidates: 2,529
quality scored:   2,313
GARP ranked:      3,101
status: current cross-section only, PIT_BACKTEST_BLOCKED
```

### P10.6 SEC PIT pilot

```text
fixed names: 20
usable:      19
cutoffs:     2017, 2020, 2023, 2026
status:      PIT_PILOT_PARTIAL
```

The FSNDS pilot tested only `2017q1`, not all quarters.

### Price panel

```text
1,017 symbols 2000-2024; 983 with 2007+ data
PIT-filtered union: 887
```

Not a full US listed universe.

---

## 5. What free data can support

### READY_RESTRICTED

- macro release-date studies using ALFRED vintages;
- SEC filing-date event studies;
- small-sample as-filed fundamental panels using FSNDS/accession data;
- 8-K text discovery, not a complete event database;
- company-level price reactions around SEC filing dates.

### DATA_BLOCKED

- market-wide historical PIT fundamentals from CompanyFacts alone;
- exact earnings announcement time (before/after close);
- earnings surprise / guidance history without analyst consensus;
- structured M&A/management/litigation events from free sources;
- historical company news sentiment;
- company IR archive across all issuers.

### NO_BUY

- historical analyst estimates/ratings/revisions;
- paid event/news archives;
- market-wide cleaned PIT fundamentals;
- exact intraday release-time data.

---

## 6. PIT rules that must be enforced

1. A fact is usable only after its **filing/acceptance timestamp**, not period end.
2. CompanyFacts latest values must not be backfilled into earlier dates.
3. Use accession-level facts or FSNDS for as-filed values.
4. Macro values must use ALFRED vintages or release dates, not latest revisions.
5. News must use original publication time; GDELT is a proxy, not issuer truth.
6. Earnings dates from 8-K Item 2.02 are filing dates, not exact release times.
7. Analyst consensus cannot be inferred from price or news.

---

## 7. Stage decision

```text
P12_1_STATUS: PARTIAL
MACRO_PIT: READY_RESTRICTED
SEC_FILING_EVENTS: READY_RESTRICTED
MARKET_WIDE_FUNDAMENTAL_PIT: DATA_BLOCKED
EARNINGS_TIMING: DATA_BLOCKED
NEWS_SENTIMENT: DATA_BLOCKED
ANALYST_EXPECTATIONS: NO_BUY
COMPANY_IR_HISTORY: DATA_BLOCKED
```

A limited SEC filing/macro event study is possible. A market-wide historical PIT
fundamental/news/analyst study is not possible with the current free data.

---

## 8. Recommended next step

Do **not** build factors yet.

If continuing, the only defensible limited experiment is:

- a small as-filed SEC panel (e.g. 20-50 names) with accession timestamps;
- a macro release-date study using ALFRED vintages;
- filing-date price reactions, not earnings-surprise claims;
- explicit sample/selection disclosure.

This is a data pilot, not a market-wide strategy.

---

## 9. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P12_1_STATUS: PARTIAL
P6_PIT: DATA_BLOCKED
P10_6_PIT: PARTIAL / NOT_READY
P11_PRICE_FACTORS: NO-GO
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
IBKR_CONNECTED: NO
```

No purchase, registration, trial, VPS, broker connection or raw-data upload.
