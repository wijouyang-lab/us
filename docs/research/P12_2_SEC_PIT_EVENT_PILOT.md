# P12.2: SEC Historical PIT Fundamentals and Filing-Event Pilot

Date: 2026-11-17
Branch: `research/p12-event-fundamental-feasibility`
Status: **READY_RESTRICTED for the 40-issuer pilot; DATA_BLOCKED for market-wide use**

---

## 1. Scope

This is data engineering and descriptive event work, not factor or strategy
research.

- 40 issuers fixed before inspecting financial results;
- CIK is the primary identifier; ticker is only a label;
- 30 current US issuers, 5 US non-surviving issuers, 5 foreign ADR issuers;
- US and foreign disclosure regimes are kept separate;
- no purchase, no broker, no paper/shadow.

Sample file: `data/research/p12_2_sample_universe.csv`

---

## 2. Data extraction

Sources:

- SEC submissions API (filing dates, acceptance datetimes, form, items);
- SEC companyfacts API, restricted to accession-ancestored facts;
- local FINSABER daily adjusted prices;
- SPY trading calendar.

Outputs:

```text
issuers:        40
fact rows:      59,897
filing events:   4,808
  8-K (US):      2,752
  6-K (foreign): 2,056
```

Facts are accession-level records with:

```text
CIK, ticker, accession, form, filing date, acceptance datetime,
fiscal period, period start/end, taxonomy, tag, unit, value,
source URL
```

No CompanyFacts latest value is backfilled without accession ancestry.

---

## 3. Fact coverage

```text
Revenue              9,074
NetIncome             7,895
Cash                  6,348
OperatingIncome       5,703
TotalDebt             5,191
TotalAssets           4,417
SharesOutstanding     4,211
OperatingCashFlow     4,027
GrossProfit           3,962
Capex                 3,514
```

All 40 issuers have at least one extracted fact. Foreign issuers use IFRS tags
and 20-F/40-F filings, not US GAAP 10-K/10-Q.

`TotalDebt` is not a single universal tag; it maps to `LongTermDebt`,
`LongTermDebtNoncurrent`, `DebtCurrent`, or `Borrowings`. This mapping limitation
is recorded, not hidden.

---

## 4. Filing and 8-K events

US 8-K events: 2,752. Acceptance datetime missing: 0.

Session classification (US 8-K):

```text
PREMARKET:     875
INTRADAY:      188
AFTER_HOURS: 1,684
NON_TRADING:     5
```

Item coverage (multi-item 8-Ks counted once per item):

```text
1.01 Material agreement        139 events / 26 issuers
2.01 Acquisition/disposition    28 / 19
2.02 Results of operations     840 / 34
5.02 Director/officer change   582 / 34
7.01 Regulation FD            496 / 33
8.01 Other events             757 / 34
```

The sum of item rows exceeds 8-K event count because an 8-K can carry multiple
items.

An 8-K acceptance datetime is not the exact earnings press-release time. The
panel provides a filing-time proxy, not an intraday news timestamp.

Foreign ADR 6-K events: 2,056. These are not merged into the 8-K taxonomy.

---

## 5. Price matching and descriptive reactions

```text
US 8-K events with price match: 2,752 / 2,752
Foreign 6-K events price match:     0 / 2,056
Events with reaction return:        2,706
```

Foreign ADRs are absent from the local price panel and are marked
`DATA_BLOCKED` for event returns.

Daily-only descriptive returns:

```text
session       events  mean reaction  median reaction
PREMARKET        875        +0.187%          +0.152%
INTRADAY         188        -0.009%          -0.057%
AFTER_HOURS    1,684        +0.054%          +0.017%
NON_TRADING        5        -0.307%          -0.407%
```

These are close-to-close descriptive statistics, not predictions or alpha.
With only daily OHLCV, exact intraday reactions cannot be identified.

---

## 6. PIT quality

File: `data/research/p12_2_pit_quality_summary.csv`

```text
sample issuers:             40
issuers fetched:            40
CIK/ticker mapping:         40
fact rows:              59,897
multi-accession groups:  18,097
acceptance missing:          0
events with return:       2,706
foreign price missing:     2,056
full-market claim:             0
```

`multi-accession groups` counts the same CIK/metric/tag/unit/period appearing in
more than one accession. It is an upper-bound version/restatement audit, not a
claim that all 18,097 are accounting restatements.

---

## 7. Annual coverage

`data/research/p12_2_annual_coverage.csv`

```text
rows: 590 issuer-years
range: 2009-2024
filings counted: 29,118
fact rows: 59,897
```

Quarterly coverage is in p12_2_quarterly_coverage.csv (2,056 issuer-periods).

Coverage is per issuer and year/quarter; it is not a market-wide panel.

---

## 8. Status by component

```text
P12_2_STATUS: READY_RESTRICTED
PILOT_SAMPLE: 40 issuers
US_8K_EVENTS: READY_RESTRICTED
US_PRICE_REACTIONS: READY_RESTRICTED (daily only)
FOREIGN_6K_EVENTS: PARTIAL
FOREIGN_PRICE_REACTIONS: DATA_BLOCKED
EXACT_EARNINGS_RELEASE_TIME: DATA_BLOCKED
INTRADAY_PRICE_REACTION: DATA_BLOCKED
MARKET_WIDE_PIT_PANEL: DATA_BLOCKED
PAID_DATA: NO_BUY
```

---

## 9. Direct answers

1. **Is the small-sample PIT panel usable?**
   Yes, for `READY_RESTRICTED`: accession-level facts and filing dates are
   traceable. It is not a market-wide PIT database.

2. **Are 8-K event times reliable?**
   Acceptance datetimes are available. Exact press-release time is not; the
   filing time is a proxy.

3. **Can daily prices support event studies?**
   Only descriptive close-to-close reactions. No intraday identification.

4. **Can this expand to broader US stocks?**
   Potentially with FSNDS/accession-level batch extraction, but not now.
   Market-wide status remains `DATA_BLOCKED`.

5. **What remains blocked?**
   Exact earnings timing, intraday reactions, foreign price coverage,
   market-wide identity/price panel, analyst estimates, and historical news.

---

## 10. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P12_2_STATUS: READY_RESTRICTED
PILOT_ISSUERS: 40
FACT_ROWS: 59897
EVENTS: 4808
US_8K_EVENTS: 2752
MARKET_WIDE_PIT: DATA_BLOCKED
EXACT_EARNINGS_TIME: DATA_BLOCKED
INTRADAY_REACTION: DATA_BLOCKED
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
P11_PRICE_FACTORS: NO-GO
IBKR_CONNECTED: NO
```

No purchase, registration, trial, VPS, broker, paper/shadow, portfolio or factor
construction.
