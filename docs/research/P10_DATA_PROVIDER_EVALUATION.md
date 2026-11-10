# P10: US Historical Data Provider Evaluation

Date: 2026-11-10  
Branch: `research/p10-data-provider-evaluation`  
Status: **EVALUATION ONLY — NO PURCHASE, NO DATA COMMITTED**

---

## 1. Question

Can a US historical data service close the P9.1 gaps without repeating failed
free-source searches?

Required:

- at least 10 years of daily OHLCV;
- NYSE / NASDAQ / NYSE American coverage;
- delisted securities;
- historical ticker / symbol mapping;
- corporate actions (splits, dividends, spinoffs, ticker changes);
- historical index membership or PIT constituents;
- explicit research-use license and reproducible access;
- a real sample/trial before any claim is accepted.

P9.1 currently has:

```text
member-day coverage: 89.58% (< 95%)
ticker coverage:     91.55% (< 98%)
Finsaber source/license: UNKNOWN
SP500 local match: PASS
SP500 third-party redistribution: UNKNOWN
P9_DATA_REPRODUCIBILITY: BLOCKED
```

This evaluation does not change P9.1 results. All eight portfolios remain
`NO-GO`.

---

## 2. Bottom line

Three candidates merit a later trial:

1. **Sharadar Bundle — $29/month**  
   Best low/mid-cost candidate: active + delisted prices, corporate actions,
   fundamentals, S&P 500 constituents table, API/CSV, official sample endpoint.
   Over the ~$20 budget; personal-use license only.

2. **Norgate Data Platinum — $630/year ($52.50/month equivalent)**  
   Strongest survivorship-bias control: delisted securities back to 1990,
   historical index constituents, Python/Updater access, free trial.
   Over budget.

3. **EODHD Historian — EUR 19.99/month**  
   Close to the $20 budget and has an API, delisted ticker API and symbol-rename
   API. Whether delisted history and historical constituents are included in
   this specific plan is **UNKNOWN**.

No candidate is approved for purchase. No subscription or payment was made.

### Minimum feasible plan

For P9.1's requirements, the minimum candidate is **Sharadar Bundle at $29/month**,
because it is the only low-cost plan whose official page lists both delisted
prices/actions and an S&P 500 constituents table. It is still **above the ~$20
budget**, and the actual historical S&P 500 table coverage has not been verified.

At strict ≤$20:

- **Sharadar Prices at $9/month** covers prices, delisted securities and actions,
  but PIT index membership in this tier is **UNKNOWN**.
- **EODHD Historian at EUR 19.99** is at the budget edge; delisted/historical
  constituents inclusion is **UNKNOWN**.
- **Alpha Vantage free** is not sufficient: no delisted coverage claim and no PIT
  membership.

Therefore: **there is no verified, license-safe PIT solution at ≤$20/month in this
review.**

---

## 3. Provider comparison

Full machine-readable table:

`data/research/p10_provider_comparison.csv`

Prices are from official pricing pages as of **2026-11-10**. `UNKNOWN` means the
official page did not provide a usable numeric price or coverage statement.

### Low-price options

| Provider / product | Official price | History | Delisted | PIT constituents | Access | License | Trial |
|---|---:|---:|---|---|---|---|---|
| Sharadar Prices | **$9/mo** | 1997-12 | YES | UNKNOWN | API/CSV | Personal, no redistribution | Sample key |
| EODHD Historian | **EUR 19.99/mo** | UNKNOWN | UNKNOWN in plan | UNKNOWN | API/CSV | Personal | Sandbox/demo |
| Alpha Vantage free | $0 | 20+ years claim | NO | NO | API/CSV | UNKNOWN | Free key |
| Sharadar Bundle | **$29/mo** | 1998-01 | YES | YES (S&P 500 table) | API/CSV | Personal, no redistribution | Sample key |

### Complete / higher-cost options

| Provider / product | Official price | History | Delisted | PIT constituents | Access | License | Trial |
|---|---:|---:|---|---|---|---|---|
| Norgate Platinum | **$630/yr = $52.50/mo** | 1990 | YES | YES (historical index) | Updater/Python/CSV | Personal non-commercial | Free trial |
| Norgate Diamond | **$787.50/yr = $65.63/mo** | 1950 | YES | YES | Updater/Python/CSV | Personal non-commercial | Free trial |
| EODHD All-In-One | **EUR 99.99/mo** | UNKNOWN | UNKNOWN in plan | UNKNOWN | API/CSV | Personal | Sandbox |
| CRSP via WRDS | Institutional quote | 1925 | YES | YES | WRDS/API | Institutional | NO |

Other assessed products:

- **Massive (formerly Polygon) Stocks Starter** — official price not captured from
  the JS-rendered pricing page; coverage/license **UNKNOWN**.
- **Tiingo EOD** — official numeric price not captured; no sample validated.
- **SEC EDGAR CompanyFacts** — PIT fundamentals, $0, public domain; no prices.
- **FRED** — macro only, $0, public; no prices/membership.
- **GDELT** — news/events only, $0; no prices.

### Important qualification

The table records what the vendor's official page claims. It is **not** a
verification of:

- actual delisted ticker counts;
- whether the S&P 500 table is point-in-time and complete;
- corporate-action correctness;
- exchange coverage at the required 98% ticker gate;
- redistribution rights for a public GitHub repo.

---

## 4. Sample validation

Design file:

`data/research/p10_sample_validation.csv`

30 representative tickers × 3 leading candidates = 90 rows:

- current mega caps: AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, BRK.B;
- financials/energy/retail: JPM, XOM, WMT, COST;
- small caps: ANF, SIG, MTH, PRDO, CROX;
- delisted: LEHMQ, ENRNQ, WCOMQ, BSC;
- acquired: EMC, YHOO, ATVI, TWTR;
- renamed: ANTM→ELV, DISCA→WBD;
- special actions/spinoffs: GE, MMM, JNJ;
- multiple periods: 2001, 2002, 2008, 2016, 2020, 2022, 2023, 2024.

### Actual result

```text
PASS:        0
PARTIAL:     2   (AAPL only: Sharadar test-key sample; EODHD demo)
NOT_RUN:    88   (no paid subscription / no trial executed)
```

The two AAPL checks only confirm that a small OHLCV response is retrievable.
They do **not** validate 10 years, delisted names, historical membership,
corporate actions, repeatability or license.

No metric is marked PASS without a real provider sample.

---

## 5. Fundamentals, SEC, news, macro

These are separate sources, not assumed to come from the price vendor.

| Need | Candidate | Cost | License | PIT status |
|---|---|---:|---|---|
| SEC fundamentals / filings | SEC EDGAR CompanyFacts/Submissions | $0 | US public domain | Filing-date based; available |
| Macro | FRED | $0 | Public | Release-date series available |
| News/events | GDELT 2.0 | $0 | Open | Event stream; no price data |
| Fundamentals PIT | Sharadar Bundle | $29/mo | Personal | As-reported/AR dimensions claimed |
| News + fundamentals bundle | EODHD All-In-One | EUR 99.99/mo | Personal | UNKNOWN |

SEC/FRED/GDELT can support research, but do not substitute for delisted price
history or PIT index membership.

---

## 6. Economics

### Strict ~$20 budget

Possible:

- Sharadar Prices at $9/month — prices/delisted/actions, but PIT membership
  UNKNOWN and no fundamentals.
- EODHD Historian at EUR 19.99 — near budget, but delisted/PIT inclusion
  UNKNOWN.
- Alpha Vantage free — not sufficient for survivorship-free PIT.

Not possible with verified coverage:

- Norgate Platinum/Diamond;
- CRSP;
- EODHD All-In-One;
- Sharadar Bundle at $29.

### Recommended later trial

If a small overage is acceptable, trial **Sharadar Bundle** first. It is the
lowest-cost candidate that officially combines delisted prices, corporate
actions, fundamentals and S&P 500 constituents. Validate 30 samples plus the P9.1
coverage gates before purchase.

If the S&P 500 PIT table is present and complete, it can restore **S&P 500 PIT**
research. It does **not** automatically restore full all-listed/retired-market
PIT research; that needs Norgate Platinum/Diamond or CRSP-like coverage.

---

## 7. Can full-market PIT research be restored?

Conditionally:

```text
S&P 500 PIT:        CONDITIONAL on Sharadar Bundle sp500 coverage verification
Full US market PIT: CONDITIONAL on Norgate Platinum/Diamond or CRSP
Current status:     NOT VERIFIED / NO PURCHASE
```

No claim is made that any candidate meets the 95% member-day or 98% ticker gates
until the actual extract is measured.

---

## 8. Decision

```text
P10_PROVIDER_EVALUATION: COMPLETE
P10_PURCHASE_DECISION: NONE
P10_RECOMMENDED_TRIAL: Sharadar Bundle
P10_BUDGET_COMPATIBLE_WITH_VERIFIED_PIT: NO
P9_DATA_REPRODUCIBILITY: BLOCKED (unchanged)
P9_RESULTS: unchanged; all 8 NO-GO
```

Do not purchase or connect a vendor yet. The next step is a manual approval to
run a time-boxed Sharadar Bundle trial against the 30-sample validation and the
P9.1 coverage gates.

---

## 9. Official sources

- Norgate packages/pricing: https://norgatedata.com/stockmarketpackages.php
- Norgate EULA: https://norgatedata.com/subscribe/eula.php
- Sharadar prices: https://sharadar.com/prices
- Sharadar bundle: https://sharadar.com/bundle
- Sharadar subscription prices: https://sharadar.com/subscribe
- Sharadar personal license: https://sharadar.com/terms
- EODHD pricing: https://eodhd.com/pricing
- EODHD EOD API: https://eodhd.com/financial-apis/api-for-historical-data-and-volumes
- EODHD terms: https://eodhd.com/financial-apis/terms-conditions
- Massive pricing: https://massive.com/pricing
- Tiingo pricing: https://www.tiingo.com/about/pricing
- Alpha Vantage premium: https://www.alphavantage.co/premium/
- CRSP: https://www.crsp.org/products/research-products/crsp-us-stock-database
- SEC EDGAR API: https://www.sec.gov/edgar/sec-api-documentation
- FRED: https://fred.stlouisfed.org/
- GDELT: https://www.gdeltproject.org/
