# P15 MAX21 Lottery-Demand Factor Research

Date: 2026-11-20
Branch: `research/p15-max21-lottery-demand`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **NO_GO**

## 1. Data and PIT

Local FINSABER raw, 2000-01-03..2024-12-31, 1,017 symbols,
`close` + `adjusted_close`, zero duplicate symbol/date.

Membership: local `sp500_daily.csv`, latest snapshot at or before signal date.
Factor formation uses full historical prices; membership is applied only on the
signal date, so pre-inclusion history can be used without future membership.

5Y: 2020-01-02..2024-12-31. 3Y sensitivity: 2022-01-03..2024-12-31.

Coverage from the same source/window:

```text
5Y member-day coverage = 98.68%
5Y ticker coverage     = 95.72%
priced tickers         = 581
missing-price members  = 26
```

Price basis `adjusted_close`; `ADJUSTMENT_UNVERIFIED`.

Price-quality audit: 16 non-positive closes, 6,969 absolute daily returns >50%,
55,009 adjusted/raw ratios <0.05 and 38,072 >20; these are retained, not
winsorized, and are a limitation for a MAX-based factor.

## 2. Factor and returns

```text
MAX21(t) = max 21 daily returns ending at t
entry = t+1 market close
exit  = t+22 market close
forward = AdjClose(t+22)/AdjClose(t+1) - 1
```

Requires 22 prices. No forward fill. Signal dates start 2020-01-02 after using
2019 history for warm-up.

## 3. 5Y results

| metric | value |
|---|---:|
| observations | 613,038 |
| signal dates | 1,234 |
| tickers | 580 |
| mean Rank IC | **−0.0020** |
| Q1−Q5 | **−0.377%** |
| HAC lag20 t | −0.750 |
| HAC p | 0.454 |
| 21-day block bootstrap CI | [−1.423%, +0.603%] |

Quantile means increase from Q1 to Q5:

```text
Q1 1.010%  Q2 1.048%  Q3 1.080%  Q4 1.170%  Q5 1.387%
```

This is the opposite of the lottery hypothesis: high MAX21 did better, and
Q1−Q5 is negative. The result is not statistically significant.

## 4. Volatility control

Correlation MAX21/RV21 = **0.849**.

Fama-MacBeth daily cross-sectional regression with both standardized:

| coefficient | mean | HAC t | p |
|---|---:|---:|---:|
| MAX21 | −0.00187 | −1.276 | 0.202 |
| RV21 | +0.00310 | 0.992 | — |

MAX21's negative coefficient remains in sign but is not significant after RV21.
`MAX21_INCREMENTAL_ALPHA = NOT_CONFIRMED`.

## 5. OOS with purge

| segment | dates | IC | Q1−Q5 | HAC t | p |
|---|---:|---:|---:|---:|---:|
| Train | 718 | −0.007 | −0.398% | −0.54 | 0.591 |
| Validation | 225 | +0.025 | −0.596% | −0.56 | 0.579 |
| Test | 247 | −0.024 | **+0.167%** | 0.26 | 0.796 |

Test has the wrong sign for the pre-registered direction and is not significant.
`P15_OOS = FAIL`.

## 6. Long-only bottom 20%

Fixed 21-session non-overlapping rebalance, 59 periods:

| metric | Bottom20 | Equal-weight universe |
|---|---:|---:|
| mean period return | 0.945% | 1.193% |
| gross excess | **−0.248%** | — |
| cumulative | 1.596 | 1.802 |
| max drawdown | **−32.06%** | — |
| average one-way turnover | 128.1% | low |

Costs (both legs, actual weight changes):

| bps/side | long net mean | EW net mean | net excess |
|---:|---:|---:|---:|
| 5 | 0.881% | 1.192% | **−0.311%** |
| 10 | 0.817% | 1.191% | **−0.374%** |
| 20 | 0.689% | 1.188% | **−0.499%** |

Bottom20 underperforms before and after costs; drawdown far exceeds the 15%
limit. No 50k portfolio.

## 7. Final status

```text
P15_DATA_QUALITY = PARTIAL
P15_PIT_MEMBERSHIP = PARTIAL
P15_PRICE_ADJUSTMENT = UNVERIFIED
P15_MAX21_ALPHA = NO_GO
P15_VOLATILITY_CONTROL = FAIL
P15_OOS = FAIL
P15_LONG_ONLY = FAIL
P15_COST_SENSITIVITY = FAIL
P15_DRAWDOWN = FAIL
P15_PRODUCTION_READY = FALSE
P15_REAL_TRADING = NOT_AUTHORIZED
```

Reasons: Q1−Q5 is negative, Test is near zero/wrong direction, MAX21 is 85%
correlated with RV21 and insignificant after control, long-only bottom20
underperforms, costs worsen it, drawdown −32%.

No parameter search, no alternative direction, no portfolio backtest beyond
the pre-registered proxy.

## 8. Files

- `tools/research/p15_max21_lottery_factor.py`
- `tests/test_p15_max21_lottery_factor.py`
- `data/research/p15/p15_data_coverage.json`
- `p15_stock_coverage.csv`
- `p15_membership_audit.csv`
- `p15_price_quality_audit.csv`
- `p15_daily_ic.csv`
- `p15_quantile_returns.csv`
- `p15_hac_results.csv`
- `p15_block_bootstrap.csv`
- `p15_fm_results.csv`
- `p15_fama_macbeth.csv`
- `p15_oos_results.csv`
- `p15_monthly_long_only.csv`
- `p15_cost_sensitivity.csv`
- `p15_summary.json`
- `p15_manifest.json`

46 MB signal panel kept local only.

No model call, no API key, no broker, no order.
