# P12.5.3.1 Statistical Integrity and Event Alignment Report

Date: 2026-11-19
Branch: `research/macro-cross-sectional-equity-response`
Base HEAD: `180c1ac4718620dde114dabea200613e80a250a5`
Status: **NO_GO persists; PRICE_RETURN_ONLY / UNADJUSTED_PRICE**

## 1. Fixes

1. **Price basis:** stock `Price` and ETF `Close` are both unadjusted. Previous
   ETF `Adj Close` mix was removed.
2. **Calendar:** SPY sessions are the single calendar. `fwd()` takes entry and
   exit by SPY position and requires exact stock + SPY prices on both dates.
   No forward fill.
3. **Beta:** inner date intersection of stock/SPY/TLT/GLD/IWM; 252-day window,
   minimum 180 returns.
4. **HAC:** event-level IC/spread series, Newey-West lags 0–4.
5. **Block bootstrap:** 5,000 resamples by same-date blocks, seed 20261119.
6. **Purge:** train/validation events whose D20 window reaches the next split
   are removed.
7. **BH:** all 36 pre-registered interaction/horizon tests.

## 2. Sample and alignment

| item | result |
|---|---:|
| events used | 209 |
| CPI / Employment | 105 / 104 |
| stock-event observations | 87,706 |
| tickers | 481 |
| names/event mean / median | 419.6 / 421 |
| D1/D5/D10/D20 valid | 87,706 each |
| price basis | unadjusted close |
| calendars | SPY sessions only |

Rows missing entry, exit, or beta history were dropped before the panel write.
No stock price was forward-filled.

## 3. Event-level comparison

| interaction | horizon | mean IC | Top−Bottom | ordinary p | ordinary BH q |
|---|---:|---:|---:|---:|---:|
| Payroll × Beta_IWM | 20D | −0.082 | −1.779% | 0.0029 | 0.104 |
| Payroll × Beta_IWM | 10D | −0.061 | −0.854% | 0.026 | 0.312 |
| Payroll × Beta_IWM | 5D | −0.056 | −0.595% | 0.025 | 0.312 |
| CPI headline × Beta_TLT | 20D | +0.029 | +0.336% | 0.540 | 0.657 |
| CPI core × Beta_TLT | 20D | +0.040 | +0.676% | 0.216 | 0.421 |
| CPI headline × Beta_GLD | 20D | +0.016 | +0.324% | 0.443 | 0.591 |

The previous CPI GLD effect disappears after strict alignment. Payroll remains
negative but does not pass ordinary BH 10% (q=0.104).

## 4. HAC (lag 4, conservative)

| interaction | horizon | NW t (spread) | p | BH q |
|---|---:|---:|---:|---:|
| Payroll × Beta_IWM | 20D | −2.719 | 0.0077 | 0.221 |
| Payroll × Beta_IWM | 10D | −2.190 | 0.0308 | 0.221 |
| Payroll × Beta_IWM | 5D | −2.484 | 0.0146 | 0.221 |
| CPI headline × Beta_TLT | 20D | −1.27 | 0.207 | >0.5 |

HAC makes the payroll sign stronger but BH still fails (q=0.221).  
The complete lag 0–4 sensitivity is in `p12_5_3_1_hac_sensitivity.csv`.

## 5. Block bootstrap

Payroll × Beta_IWM, 20D:

```text
blocks = 104 event dates
boot mean = -1.793%
95% CI = [-2.952%, -0.714%]
```

The negative block-bootstrap CI excludes zero, but this is a single
pre-registered interaction among 36 tests and does not survive BH.  
CPI headline × Beta_TLT 20D bootstrap CI includes zero.

## 6. Purged OOS

| split | raw event dates | purged event dates | removed |
|---|---:|---:|---|
| train | 125 | 122 | 2020-04-10, 2021-04-02, 2023-02-14 |
| validation | 42 | 40 | 2023-04-07, 2024-11-13 |
| test | 42 | 42 | none |

Purged 20D IC:

| interaction | train | validation | test |
|---|---:|---:|---:|
| CPI headline × TLT | +0.027 | +0.004 | +0.081 |
| CPI core × TLT | +0.042 | +0.002 | +0.092 |
| Payroll × IWM | −0.131 | −0.030 | −0.005 |

CPI Test has only **11 event dates**; its positive point estimate is not
statistically reliable and its 5D sign is negative. Payroll is directionally
stable negative but attenuates to near zero in test.

## 7. Decision

```text
PRICE_BASIS = UNADJUSTED_CLOSE
DATE_ALIGNMENT = SPY_SESSION_STRICT
HAC_MAIN = LAG_4
BOOTSTRAP = 5000_BLOCKS
PURGE = D20_BOUNDARY
BH_MIN_Q_ORDINARY = 0.104
BH_MIN_Q_HAC = 0.221
PRE_REGISTERED_CPI_ALPHA = NO_GO
PRE_REGISTERED_EMPLOYMENT_ALPHA = NO_GO
STRATEGY_ALPHA_STATUS = NO_GO
```

No cost model or portfolio backtest is permitted. The payroll negative result is
interesting but: (a) fails BH, (b) uses unadjusted prices, (c) has unverified
membership/delisting, and (d) has a near-zero test IC.

## 8. Limitations

- Unadjusted close; splits/dividends not handled.
- PIT membership and delisted names unverified.
- Date-only events; no intraday timing.
- FINSABER adjusted file not used (license/membership not cleared).
- No historical consensus.

## 9. Files

- `tools/research/p12_5_3_macro_equity_alpha.py`
- `tools/research/p12_5_3_1_inference.py`
- `tools/research/p12_5_3_1_purged_oos.py`
- `tests/test_p12_5_3_macro_equity_alpha.py`
- `data/research/macro_cross_sectional/p12_5_3_event_results.csv`
- `p12_5_3_oos_results.csv`
- `p12_5_3_1_hac_sensitivity.csv`
- `p12_5_3_1_bootstrap.csv`
- `p12_5_3_1_purge.json`
- `p12_5_3_1_oos_purged.csv`
- `p12_5_3_1_alignment_audit.json`

No model call, no API key, no broker, no order.
