# P13 ATR_Pct 3Y/5Y Validation

Date: 2026-11-19
Branch: `research/p13-3y5y-atr-validation`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **NO_GO · DATA_ADMISSION = FAIL**

## 1. Data

Source: local FINSABER raw (`finsaber_prices_raw.csv`), 2000-01-03..2024-12-31,
1,017 symbols, OHLC, volume, `adjusted_close`.  
Membership: local `sp500_daily.csv` snapshots applied point-in-time with
`merge_asof`-style forward lookup; no current-constituent backfill.

5Y window: 2020-01-02..2024-12-02 (limited by labels and data end).

| coverage | result | threshold |
|---|---:|---:|
| member-day coverage | **98.68%** | 95% PASS |
| ticker coverage (5Y member union) | **95.72%** | 98% FAIL |
| median names/day | 498 | — |
| tickers with prices | 581 | — |

Data admission fails the ticker-coverage threshold. No portfolio is run.

Other limitations:

- `adjusted_close` supplier adjustment convention is not independently verified;
- delisted/security identity is not fully audited;
- ATR uses raw OHLC, returns use adjusted close; this is a mixed field treatment
  that must not be described as a verified total-return strategy;
- historical membership snapshots are sparse (changes, not daily), applied PIT.

## 2. Factor definition

`ATR_Pct = Wilder ATR(14) / close`, recomputed from raw OHLC.  
Signal at date t close; forward excess = adjusted-close return minus SPY Close
return over 5/10/20 trading days.

Pre-registered: Q5−Q1 20D excess, positive direction.  
Q1..Q5 by daily cross-sectional ATR_Pct.

## 3. 5Y results

Daily IC/spread, 1,258 signal dates, HAC lag=4:

| horizon | mean IC | Q5−Q1 | HAC t | p | BH q |
|---:|---:|---:|---:|---:|---:|
| 5D | — | +0.128% | 0.62 | 0.539 | 0.539 |
| 10D | — | +0.228% | 0.79 | 0.428 | 0.539 |
| **20D** | **+0.003** | **+0.509%** | **1.22** | **0.224** | **0.539** |

No horizon passes BH 10%. The 20D point estimate is positive but not
statistically distinguishable from zero.

## 4. Chronological 60/20/20

| segment | dates | start | end | mean IC20 | Q5−Q1 20D | HAC t | p |
|---|---:|---|---|---:|---:|---:|---:|
| Train | 718 | 2020-01-02 | 2022-11-04 | −0.006 | +0.653% | 1.05 | 0.295 |
| Validation | 224 | 2022-12-12 | 2023-11-01 | +0.036 | +0.973% | 1.07 | 0.287 |
| **Test** | **248** | **2023-12-07** | **2024-12-02** | **−0.049** | **−0.787%** | **−1.84** | **0.067** |

Test direction reverses and is negative. The pre-registered hypothesis fails.

## 5. 3Y sensitivity

2022-01-03..2024-12-02, 733 dates:

```text
mean IC20 = -0.0136
Q5-Q1 20D = +0.030%
HAC t = 0.07
p = 0.943
```

No recent 3Y ATR effect.

## 6. Decision

```text
DATA_ADMISSION = FAIL (ticker coverage 95.72% < 98%)
P13_ATR_ALPHA = NO_GO
P13_ATR_PORTFOLIO = NOT_RUN
```

Reasons:

1. Test 20D Q5−Q1 is negative;
2. 5Y HAC p=0.224, BH q=0.539;
3. 3Y effect is flat;
4. ticker coverage below threshold;
5. adjusted-close/raw-OHLC field mix and delisting identity not fully verified.

No IBKR cost model, no 50k portfolio, no parameter search, no alternative
windows. This closes the ATR_Pct candidate on this dataset.

## 7. Files

- `tools/research/p13_atr_validation.py`
- `tests/test_p13_atr_validation.py`
- `data/research/p13/p13_data_readiness.json`
- `p13_universe_audit.json`
- `p13_atr_daily_ic.csv`
- `p13_atr_quantiles.csv`
- `p13_atr_oos.csv`
- `p13_atr_hac.csv`
- `p13_atr_3y.json`
- `p13_manifest.json`

No model call, no API key, no broker, no order.
