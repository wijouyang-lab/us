# P12.5.3 CPI/Employment Cross-Sectional Exploratory Report

Date: 2026-11-19
Branch: `research/macro-cross-sectional-equity-response`
Base HEAD: `c39ebe67364c2364495125d2e6b9a234760e5eb3`
Status: **EXPLORATORY_ONLY · NO_GO for pre-registered hypotheses**

## 1. Design

- events: ALFRED date-only CPI/Employment, 2017-01-01 onward;
- signal: prior close before `release_date`;
- entry: first complete trading session after `release_date` (close proxy);
- forward excess: stock return minus SPY, D1/D5/D10/D20;
- beta: 252-day regression on SPY/TLT/GLD/IWM, minimum 180 observations;
- macro deviation: rolling 36-event median and MAD, computed from 2007–2026
  history and excluding the current and future events;
- tests pre-registered: CPI headline/core × Beta_TLT, headline × Beta_GLD;
  Employment payroll/unemployment × Beta_IWM, AHE MoM × Beta_TLT;
- BH across the full 36-test interaction/horizon grid.

Price caveat: unadjusted close only; this is not total return.

## 2. Sample

| item | result |
|---|---:|
| events used | 209 |
| CPI events | 105 |
| Employment events | 104 |
| stock–event observations | 87,706 |
| tickers | 481 |
| mean names/event | 419.6 |
| median names/event | 421 |

## 3. Event-level results

| horizon | interaction | events | mean IC | Top−Bottom | p | BH q |
|---:|---|---:|---:|---:|---:|---:|
| 20D | Payroll × Beta_IWM | 104 | −0.0816 | −1.755% | 0.0033 | 0.118 |
| 10D | Payroll × Beta_IWM | 104 | −0.0604 | −0.843% | 0.028 | 0.348 |
| 5D | Payroll × Beta_IWM | 104 | −0.0551 | −0.582% | 0.029 | 0.348 |
| 20D | Headline CPI × Beta_GLD | 95 | +0.0285 | +1.017% | 0.039 | 0.362 |
| 10D | Core YoY × Beta_TLT | 105 | +0.0443 | +0.392% | 0.060 | 0.362 |
| 20D | Headline CPI × Beta_TLT | 95 | +0.0442 | +0.803% | 0.342 | 0.684 |
| 5D | AHE MoM × Beta_TLT | 44 | +0.0467 | +0.491% | 0.106 | 0.454 |

Minimum BH q among pre-registered tests: **0.118**. No test survives 5% or 10%
BH correction. The payroll interaction has a consistent negative sign but is
not significant after correction.

## 4. Out-of-sample

Chronological 60/20/20 by release date; same-date CPI/Employment kept together.

| family / interaction | split | events | 20D mean IC |
|---|---|---:|---:|
| CPI headline × TLT | train | 63 | +0.029 |
| CPI headline × TLT | validation | 21 | +0.003 |
| CPI headline × TLT | test | 11 | +0.082 |
| Employment payroll × IWM | train | 62 | −0.128 |
| Employment payroll × IWM | validation | 21 | −0.023 |
| Employment payroll × IWM | test | 21 | −0.005 |

CPI 5D test IC is negative (−0.061); Employment 5D test IC is −0.042.  
The only positive test-period result is CPI 20D, with only 11 independent events
and no BH significance.

## 5. Decision

```text
PRE_REGISTERED_CPI_ALPHA = NO_GO
PRE_REGISTERED_EMPLOYMENT_ALPHA = NO_GO
BH_MIN_Q = 0.118
PRICE_QUALITY = UNADJUSTED_CLOSE / PIT_MEMBERSHIP_UNVERIFIED
STRATEGY_ALPHA_STATUS = EXPLORATORY_ONLY
```

No transaction-cost model or portfolio backtest was run. The price panel cannot
support total-return or next-open execution claims, and the pre-registered
interactions fail BH/OOS.

## 6. Limitations

- unadjusted close; splits/dividends can create false returns;
- historical membership and delisted names not verified;
- date-only events; no intraday timing;
- 36-event rolling deviations force a late start;
- only 11 CPI test events;
- no historical market consensus; `ROLLING_HISTORICAL_DEVIATION` only.

A FINSABER adjusted-close file exists locally but its license/membership audit is
not cleared and its full run did not complete within this round's budget. It is
not used for the reported numbers.
