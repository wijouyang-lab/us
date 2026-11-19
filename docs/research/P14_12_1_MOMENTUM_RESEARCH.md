# P14 12-1 Momentum Research

Date: 2026-11-19
Branch: `research/p14-12m-skip-month-momentum`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **NO_GO**

## 1. Data

Local FINSABER raw:

```text
2000-01-03 .. 2024-12-31
1,017 symbols
OHLC + adjusted_close
duplicate symbol/date: 0
```

Membership: local `sp500_daily.csv`, latest snapshot at or before signal date.
Price history before index inclusion is retained for factor formation; membership
is applied only at the signal date. 558 tickers produced at least one signal.

5Y: 2020-01-02..2024-12-31. 3Y: 2022-01-03..2024-12-31.
Member-day coverage from the same source: 5Y 98.68%, 3Y 98.59%; ticker coverage
95.72%/95.58%, 26 missing-price members retained in the denominator.

Price basis: `adjusted_close`; adjustment convention
`ADJUSTMENT_UNVERIFIED` (not total-return verified).

## 2. Factor and return definition

```text
MOM_12_1(t) = AdjClose(t-21)/AdjClose(t-252) - 1
entry = t+1 market session close
exit  = t+22 market session close
forward = AdjClose(t+22)/AdjClose(t+1) - 1
```

All positions use the single market calendar. Missing t-252, t-21, t+1 or t+22
prices exclude the observation; no forward fill.

## 3. 5Y results

| metric | value |
|---|---:|
| stock-date observations | 486,782 |
| signal dates | 983 |
| tickers | 558 |
| mean daily Rank IC | +0.0065 |
| Q5−Q1 21D | **+0.104%** |
| HAC lag20 t | 0.195 |
| HAC p | 0.845 |
| 21-day block bootstrap 95% CI | [−0.926%, +1.160%] |

Point estimate is positive but statistically indistinguishable from zero; CI
includes zero.

3Y sensitivity is not separately significant; no opposing large effect.

## 4. OOS with purge

| segment | dates | mean IC | Q5−Q1 | HAC t | p |
|---|---:|---:|---:|---:|---:|
| Train | 567 | −0.019 | −0.461% | −0.58 | 0.563 |
| Validation | 175 | +0.039 | +0.542% | 0.47 | 0.638 |
| **Test** | **197** | **+0.024** | **+0.693%** | **1.31** | **0.193** |

Test direction is positive but not significant. Train is negative, so the
direction is not stable across periods. Purge uses `exit < next signal`.

## 5. Long-only monthly proxy

Every 21 sessions, reset from the first valid date; equal-weight top 20%,
47 non-overlapping periods (2020-12-31..2024-11-04).

| metric | Top20 | Equal-weight universe |
|---|---:|---:|
| mean period return | +1.136% | +1.105% |
| gross excess | **+0.031%** | — |
| average turnover | 27.70% | — |
| holdings | 97 | ~490 |
| max drawdown | **−16.91%** | — |
| cumulative | 1.637 | 1.618 |

Cost sensitivity:

| bps/side | net mean | net excess vs EW |
|---:|---:|---:|
| 5 | 1.108% | +0.003% |
| 10 | 1.081% | **−0.024%** |
| 20 | 1.025% | **−0.080%** |

At 10 bps/side the long-only proxy loses its advantage. It also exceeds the
project 15% drawdown limit. No 50k portfolio is run.

## 6. Decision

```text
P14_DATA_QUALITY = PARTIAL
P14_PIT_MEMBERSHIP = PARTIAL
P14_PRICE_ADJUSTMENT = UNVERIFIED
P14_MOM_12_1_ALPHA = NO_GO
P14_OOS = FAIL (direction unstable, test not significant)
P14_LONG_ONLY = FAIL (10 bps net excess negative, DD -16.9%)
P14_COST_SENSITIVITY = FAIL
P14_PRODUCTION_READY = FALSE
P14_REAL_TRADING = NOT_AUTHORIZED
```

The 5Y Q5−Q1 is positive but HAC p=0.845 and bootstrap CI includes zero. The
long-only top20 gross advantage is only +3 bps per period and disappears at
10 bps/side. This is not a candidate.

## 7. Files

- `tools/research/p14_12_1_momentum.py`
- `tests/test_p14_12_1_momentum.py`
- `data/research/p14/p14_data_coverage.json`
- `p14_daily_ic.csv`
- `p14_momentum_signal_panel.csv` (local large panel)
- `p14_monthly_long_only.csv`
- `p14_cost_sensitivity.csv`
- `p14_oos_results.csv`
- `p14_hac_results.csv`
- `p14_block_bootstrap.csv`
- `p14_summary.json`
- `p14_manifest.json`

No model call, no API key, no broker, no order.
