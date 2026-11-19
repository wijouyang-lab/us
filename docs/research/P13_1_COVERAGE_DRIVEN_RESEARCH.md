# P13.1 Coverage-Driven Research

Date: 2026-11-19
Branch: `research/p13-coverage-driven-universe`
Start HEAD: `6f0d642d55391019a99329ded830f75459871097`
Status: **PRICE EXPLORATORY NO_GO; QUALITY DATA_BLOCKED**

## 1. Data manifest

| File | Role | Status |
|---|---|---|
| `_us_audit/pr512/.../finsaber_prices_raw.csv` | OHLC + `adjusted_close`, 2000–2024 | used |
| `_us_audit/pr512/.../historical_universe/sp500_daily.csv` | membership snapshots, PIT lookup | used |
| `_us_audit/pr512/.../p9_1_support_resistance/SPY.csv` | SPY `close` | used |
| `_us_audit/fund_p63/.../sec_fundamentals_panel_p63.csv.gz` | SEC us-gaap facts with `pit_available_date` | available but not used (see §6) |

`adjusted_close` adjustment convention is supplier-provided and not independently
verified. Returns are `ADJUSTMENT_UNVERIFIED`, not total-return verified.

## 2. Coverage audit (true member-day denominator)

| window | start | end | expected member-days | observed | member-day coverage |
|---|---|---|---:|---:|---:|
| 5Y | 2020-01-02 | 2024-12-31 | 633,971 | 625,608 | **98.68%** |
| 3Y | 2022-01-03 | 2024-12-31 | 378,944 | 373,588 | **98.59%** |

5Y: 581 priced tickers; median 499 names/day.  
3Y: 541 priced tickers; median 498 names/day.

Ticker coverage against the 5Y member union is **95.72%** (581/607), below the
98% threshold. This is separate from member-day coverage and is not hidden.

## 3. Coverage pools (5Y)

| pool | tickers | definition |
|---|---:|---|
| Broad Exploratory | 580 | member-days ≥20 and price history |
| Coverage ≥80% | 581 | stock coverage ≥80% of its member days |
| Coverage ≥95% | 581 | stock coverage ≥95% |
| Continuous 5Y / 3Y | 581 / 541 | ≥95% within window |

All 581 priced names have high within-name coverage; the missing risk is the 26
member tickers with no usable price history, which are not in the pool. The
pool is therefore **not** a complete PIT market.

## 4. Price behaviour study

Pre-registered: 20D excess vs SPY; daily Q5−Q1 for
`vol20` (20D realized volatility) and `mom20` (20-day momentum).  
5Y 2020–2024, HAC lag=4, BH over 4 directional tests.

| factor | direction | mean spread | HAC t | p | BH q |
|---|---|---:|---:|---:|---:|
| vol20 | high − low | +0.390% | 1.05 | 0.294 | 0.588 |
| vol20 | low − high | −0.390% | −1.05 | 0.294 | 0.588 |
| mom20 | high − low | −0.142% | −0.54 | 0.590 | 0.590 |
| mom20 | low − high | +0.142% | 0.54 | 0.590 | 0.590 |

No factor passes BH 10%.

OOS 60/20/20:

| segment | vol high−low | mom high−low |
|---|---:|---:|
| Train | +0.436% | −0.294% |
| Validation | +1.388% | −0.117% |
| **Test** | **−0.748%** | **+0.288%** |

The volatility effect changes sign in test; momentum is weak and inconsistent.
`PRICE_BEHAVIOUR = NO_GO`.

## 5. Date alignment

All signals use the stock's own close at date t; forward excess uses the same
stock entry and SPY entry dates at t+20. No forward-fill. The P13.1 script
operates on a single price panel per symbol and maps SPY by exact date.
Any row without both stock and SPY 20D prices drops from the factor panel.

## 6. Quality study

`sec_fundamentals_panel_p63.csv.gz` contains 67 MB of us-gaap facts with
`pit_available_date`, but the local coverage file maps tickers to CIKs for
5,615 securities and includes ADR/current listings. The following are not
verified:

- historical ticker → CIK identity for the 581 price-panel names;
- delisting/merger aliases;
- whether every joined CIK is the same security as the price symbol.

Joining current CIK mappings to historical prices would create identity risk.
Therefore:

```text
QUALITY_DATA = DATA_BLOCKED
QUALITY_STUDY = NOT_RUN
```

No ROA/ROE/OCF quality result is claimed.

## 7. Decision

```text
P13_1_PRICE_BEHAVIOUR = NO_GO
P13_1_QUALITY = DATA_BLOCKED
P13_1_STRATEGY = NOT_RUN
DATA_ADMISSION = PARTIAL (member-day pass; ticker coverage 95.72%)
```

No 50k portfolio, no IBKR cost model, no parameter search. The price results do
not survive BH and reverse in test; the quality sample identity is not reliable.

## 8. Files

- `tools/research/p13_1_coverage_research.py`
- `data/research/p13_1/p13_1_coverage.json`
- `p13_1_stock_coverage.csv`
- `p13_1_price_daily.csv`
- `p13_1_price_hac.csv`
- `p13_1_price_oos.csv`
- `p13_1_summary.json`

No model call, no API key, no broker, no order.
