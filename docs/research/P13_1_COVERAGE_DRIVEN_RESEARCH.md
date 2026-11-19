# P13.1.1 Corrected Coverage and Price Research

Date: 2026-11-19
Branch: `research/p13-coverage-driven-universe`
Start HEAD: `e795630472e4c3d154e4966e798c0b11aa050cdf`
Status: **CORRECTED · PRICE BEHAVIOUR NO_GO · QUALITY DATA_BLOCKED**

## 1. What was corrected

1. Expected member-days are now built **before** filtering prices: every
   SPY-calendar day × every member in the latest prior snapshot.
2. All historical members are retained, including 26 with no price rows.
3. Per-stock coverage uses expected member-days, not the stock's own price rows.
4. Entry/Exit use one market calendar; stock and SPY must have exact same dates.
5. Stock and SPY both use raw Close. SPY has no Adj Close, so using stock
   adjusted close vs SPY close was wrong.
6. 20D HAC uses lag=19; moving-block bootstrap uses 20-day blocks.
7. OOS purge removes labels whose 20D exit crosses the next segment boundary.
8. Quality remains DATA_BLOCKED (ticker/CIK identity not verified).

SPY calendar checks:

```text
duplicate SPY dates: 0
duplicate membership snapshots: 0
duplicate symbol/date prices: 0
SPY missing business days: 46 (holidays; no synthetic dates)
```

## 2. Coverage (expected = all member-days)

| window | start | end | expected member-days | observed | coverage |
|---|---|---|---:|---:|---:|
| 5Y | 2020-01-02 | 2024-12-31 | 633,971 | 625,608 | **98.68%** |
| 3Y | 2022-01-03 | 2024-12-31 | 378,944 | 373,588 | **98.59%** |

5Y:

- expected tickers: **607**
- priced tickers: **581**
- ticker coverage: **95.72%**
- median priced names/day: **499**
- 26 members with zero prices, retained in the denominator and listed separately

3Y:

- expected tickers: 566
- priced: 541
- ticker coverage: 95.58%
- median names/day: 498

## 3. Pools (5Y)

| pool | count |
|---|---:|
| Broad Exploratory (≥20 observed member-days) | 580 |
| Coverage ≥80% | 581 |
| Coverage ≥95% | 580 |
| Missing-price members | 26 |

`Coverage ≥95%` is not called "continuous"; maximum missing streaks and annual/
quarterly coverage are in `p13_1_stock_coverage.csv`. The missing names mean
this is not a complete PIT market.

## 4. Return alignment

All observations contain:

```text
signal_date = entry_date
exit_date = 20th following SPY calendar session
stock_entry_price / stock_exit_price
benchmark_entry_price / benchmark_exit_price
stock_return / benchmark_return / excess_return
```

604,026 aligned observations; 20-row sample in
`p13_1_alignment_sample.csv`. No forward fill. Return basis:
`CLOSE_PRICE_ONLY / ADJUSTMENT_UNVERIFIED` (not total return).

## 5. Price results (corrected)

5Y, 20D excess, HAC lag=19, BH over 6 tests (2 factors × 3 cohorts):

| cohort | factor | mean Q5−Q1 | HAC t | p | BH q |
|---|---|---:|---:|---:|---:|
| broad | vol20 | +0.584% | 0.954 | 0.340 | 0.840 |
| broad | mom20 | −0.312% | −0.807 | 0.420 | 0.840 |
| cover80 | vol20 | +0.584% | 0.954 | 0.340 | 0.840 |
| cover80 | mom20 | −0.312% | −0.807 | 0.420 | 0.840 |
| cover95 | vol20 | +0.569% | 0.932 | 0.351 | 0.840 |
| cover95 | mom20 | −0.307% | −0.797 | 0.426 | 0.840 |

No result passes BH 10%. 20-day moving-block bootstrap CIs include zero for all
primary factors.

3Y sensitivity:

```text
vol20 Q5-Q1 = -0.065%, HAC t = -0.111, p = 0.912
mom20 Q5-Q1 = +0.199%, HAC t = +0.646, p = 0.518
```

## 6. OOS purge

Chronological 60/20/20 by signal date, with 20D exit-boundary purge:

| cohort | segment | dates | vol20 spread | mom20 spread |
|---|---|---:|---:|---:|
| broad | Train | 710 | +0.781% | −0.538% |
| broad | Validation | 224 | +0.987% | −0.226% |
| broad | **Test** | **244** | **−0.989%** | **+0.097%** |

Volatility changes sign in Test; momentum is near zero and inconsistent.
`P13_1_PRICE_BEHAVIOUR = NO_GO`.

## 7. Quality

```text
P13_1_QUALITY = DATA_BLOCKED
```

The SEC panel exists but historical ticker → CIK → security identity for the
price panel is not verified; ADR/current listings cannot replace historical
identity. No quality result is claimed.

## 8. Final status

```text
P13_1_MEMBER_DAY_COVERAGE = RECALCULATED
P13_1_TICKER_COVERAGE = 95.72% (5Y), 95.58% (3Y)
P13_1_PRICE_ALIGNMENT = PASS
P13_1_RETURN_BASIS = UNVERIFIED (close price, adjustment unverified)
P13_1_HAC = PASS (lag 19)
P13_1_OOS_PURGE = PASS
P13_1_PRICE_BEHAVIOUR = NO_GO
P13_1_QUALITY = DATA_BLOCKED
P13_1_STRATEGY = NOT_RUN
```

No 50k portfolio, no IBKR cost model, no parameter search. Old P13.1 numbers
are `SUPERSEDED_INVALID_METHOD`.

## 9. Files

- `tools/research/p13_1_coverage_research.py`
- `tests/test_p13_1_coverage_research.py`
- `p13_1_coverage.json`
- `p13_1_stock_coverage.csv`
- `p13_1_missing_price_members.csv`
- `p13_1_aligned_panel.csv`
- `p13_1_alignment_sample.csv`
- `p13_1_price_hac.csv`
- `p13_1_block_bootstrap.csv`
- `p13_1_price_oos.csv`
- `p13_1_summary.json`
- `p13_1_manifest.json`

No model call, no API key, no broker, no order.
