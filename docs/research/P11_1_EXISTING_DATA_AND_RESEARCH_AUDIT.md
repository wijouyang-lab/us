# P11.1: Existing Individual-Stock Data and Research Audit

Date: 2026-11-16
Branch: `research/p11-individual-stock-selection`
Status: **P11.1 PARTIAL — RESEARCH ONLY, NO PURCHASE, NO BROKER**

```text
P11_1_STATUS: PARTIAL
PRICE_FACTOR_RESEARCH: READY_RESTRICTED
FUNDAMENTAL_PIT_RESEARCH: NO_GO
EVENT_INCREMENT_RESEARCH: NO_GO
NEWS_MACRO_RESEARCH: NO_GO
FULL_MARKET_CLAIM: NO_GO
```

---

## 1. Scope

P11 is individual-stock selection, not ETF rotation. ETFs are allowed only as
benchmarks/cash (SPY, BIL).

This phase audits what can actually be studied before building factors. It does
not run a new factor backtest or change P9.

---

## 2. Existing research retained

### P6 Fundamental Selection V1

Current cross-sectional only:

```text
data_as_of: 2026-11-05
value rows:       5,453
value candidates: 2,529
value all-four:     850
quality scored:   2,313
GARP ranked:      3,101
```

Official status:

```text
CURRENT_CROSS_SECTIONAL_RESEARCH
PIT_BACKTEST_BLOCKED
```

Reasons:

- valuation needs historical price/shares;
- peer percentiles are current-sectional;
- GARP is historical growth only, no forward EPS/analyst estimates;
- freshness/stale/blocked buckets exist.

P6 is not a PIT backtest dataset.

### P9.1

All eight combinations remain **NO-GO**. Do not reuse P9 event results as P11
alpha evidence; P9 is event research, not an individual-stock selection system.

### P10

Provider track remains **NO_BUY**. EODHD/Norgate/Sharadar not purchased.

### P10.6 SEC fundamentals

P10.6 pilots are `PARTIAL`/`QUALITY_SLICE_PARTIAL`; the largest sample is small
and not `READY_FOR_BACKTEST`. Do not mark them READY.

---

## 3. Universe audit

File: `data/research/p11_1_universe_inventory.csv`

### Price panel

```text
source: finsaber S&P 500 price panel
tickers with any price: 983
rows:               4,736,109
range:              2000-01-03..2024-12-31
fields:             date, symbol, OHLCV, adjusted_close
```

This is **S&P 500 only**, not all US listed stocks.

Known gaps:

- 80 zero-member-day tickers in the P9 interval;
- 60 removed/delisted tickers with no observed member-day prices;
- 33 tickers have no local price rows;
- 47 have price rows but no member-day overlap;
- 2 share-class variants (`BRK.B`, `BF.B`) absent locally;
- 9 high-confidence ticker-reuse conflicts;
- 62 identities unresolved.

P9 pool itself is `NOT_REPRODUCIBLE` at 1,160. Do not treat 983 or 887 as full
market.

### Fundamentals

```text
value candidates: 2,529
quality scored:   2,313
GARP ranked:      3,101
```

Overlap with price panel:

```text
value:   600
quality: 613
GARP:    600
```

Only ~600 names have both current fundamentals and historical prices. This is
much smaller than the 2,529+ current fundamental universe.

### SEC filing history

```text
rows:    9,426
tickers:   144
range:   1995-02-14..2026-11-05
fields:  ticker, cik, form, filingDate, reportDate, accession
```

This is a small filing-date sample, not a full-market event text corpus. It
cannot support a historical 8-K sentiment or event study across all stocks.

### Not available

- full historical news corpus/sentiment;
- analyst estimates/revisions;
- earnings surprise history;
- historical macro panel;
- IBKR/broker integration;
- OTC/microcap full universe.

---

## 4. Factor readiness

File: `data/research/p11_1_factor_readiness.csv`

### A. Price/technical — READY_RESTRICTED

Can compute on 983 S&P names, 2000-2024:

- 5/10/20/60/120-day momentum;
- relative strength vs SPY;
- trend slope;
- volume anomaly;
- volatility;
- gap and drawdown.

Caveats:

- survivorship bias: no full delisted/OTC universe;
- 80 missing member tickers;
- symbol/share-class issues;
- no guarantee the 983 names represent all US stocks.

### B. Fundamentals — CURRENT_ONLY / NO_GO for PIT backtest

ROE/ROA/ROIC, FCF, leverage, margins, growth, valuation, earnings quality exist
only as a current cross-section for most names.

Only 600-613 names overlap with price history. No historical PIT panel, no
historical valuation prices/shares, no forward estimates.

Cannot test 2007-2024 fundamentals without first building PIT data.

### C. Events — NO_GO

- earnings dates: no historical calendar;
- 8-K: only 144 tickers with filing dates; no text/sentiment;
- M&A/management/contracts/litigation: not systematically collected.

No event-increment backtest is valid.

### D. News/macro — NO_GO

- no historical news sentiment panel;
- no industry news history;
- no macro/rates panel;
- no policy/person speech dataset.

Do not fabricate sentiment or proxies.

---

## 5. Core research questions: what can be answered now

| Question | Status |
|---|---|
| Predict 5/10/20-day individual returns with price factors | Can test on 983 S&P names, restricted |
| Factor complementarity (price factors) | Can test |
| Year/industry/size stability | Industry/size coverage limited; can do year and price-based size proxy |
| Top-group vs SPY/BIL | Can test with costs |
| Costs and turnover | Can test |
| Survivorship/lookahead | Must be treated as a known limitation, not proven clean |
| HAC + multiple-testing | Can apply to price-factor tests |
| Fundamentals predicting returns | NO_GO until PIT panel |
| Earnings/8-K/news increment | NO_GO until data |
| Full-market individual-stock selection | NO_GO |

No full-market claim is allowed.

---

## 6. Data and licence boundaries

- FINSABER-reproduce dataset card: Apache-2.0; upstream market-data rights not
  fully verified.
- FINSABER V2: `other / NOT CLEARED`; do not use in production.
- SEC filings: public, but only a small sample here.
- No raw market data is committed by P11.
- No vendor subscription, trial, registration, VPS or broker connection.

---

## 7. P11.1 conclusion

```text
P11_1_STATUS: PARTIAL
PRICE_FACTOR_RESEARCH: READY_RESTRICTED (S&P 500 price panel only)
FUNDAMENTAL_PIT_RESEARCH: NO_GO
EVENT_INCREMENT_RESEARCH: NO_GO
NEWS_MACRO_RESEARCH: NO_GO
FULL_MARKET_CLAIM: NO_GO
```

What is possible now:

- a strictly labelled S&P 500 price-factor study;
- 5/10/20-day cross-sectional tests with HAC and multiple-testing correction;
- SPY/BIL benchmarks and transaction costs;
- explicit survivorship/identity limitations.

What is not possible:

- full US listed universe;
- PIT fundamental backtest;
- earnings/news/8-K event increment;
- claiming P9 strategies are GO;
- any broker/paper/live integration.

---

## 8. Next best experiment

**P11.2 price-factor evaluation on the restricted S&P 500 panel**, not a new
strategy and not a full-market claim.

Design:

- 983 price tickers, 2000-2024;
- 5/10/20-day forward returns;
- momentum, relative strength, trend slope, volume anomaly, volatility,
  gap/drawdown;
- cross-sectional ranks;
- year/industry/size buckets where supported;
- Newey-West HAC;
- BH/Storey multiple testing;
- SPY and BIL benchmarks;
- costs and turnover;
- strict out-of-sample split;
- report identity/survivorship limitations.

Only after that should P11.3 consider fundamentals, and only if a PIT panel is
built.

---

## 9. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P11_1_STATUS: PARTIAL
PRICE_FACTOR_RESEARCH: READY_RESTRICTED
FUNDAMENTAL_PIT_RESEARCH: NO_GO
EVENT_INCREMENT_RESEARCH: NO_GO
NEWS_MACRO_RESEARCH: NO_GO
FULL_MARKET_CLAIM: NO_GO
P9_RESULTS: ALL 8 NO-GO (unchanged)
P10_PURCHASE_DECISION: NO_BUY (unchanged)
IBKR_CONNECTED: NO
PAPER_50000_USED: NO
```
