# QQQ Transition vs Risk-Matched Passive QQQ/BIL

Date: 2026-11-03
Branch: `research/fixed-risk-budget-qqq-bil`
Status: **FROZEN — NO_EXTRA_STRATEGY_VALUE / NO-GO**

The Transition research is frozen. Do not search parameters, windows, cost assumptions or risk targets. Archived evidence: PR438 adjusted/sleeve NAV reproduced to 0.00000165 max daily error; 10.5337% is an adjusted-NAV weight; raw/cash exact risk match is unfinished.

Research only. No orders, no broker, no deployment.

## 1. Main comparison object

Pre-specified PR #438 config:

```text
w25_c10_all_legs
25% sleeve, 10 bps all-legs, 252/5%/TRANSITION/5 sessions
```

No other config was selected after results.

## 2. Risk matching

Passive QQQ/BIL, monthly restore, raw Open, integer shares, cash dividends,
`historical_backtest` IBKR costs, 10 bps/leg.

The QQQ weight was solved only from full-sample annualized volatility:

| Item | Value |
|---|---:|
| Transition target vol | **2.2661%** |
| Matched QQQ weight | **10.5337%** |
| Risk-matched actual vol | **2.2662%** |
| Volatility error | **0.00006 pp** |

The weight does **not** use CAGR or MaxDD. Risk matching is ex-post descriptive,
not out-of-sample validation and not alpha.

## 3. Main table

All at 10 bps/leg; same 2007-05-30..2026-10-30 calendar.

| Metric | Transition | Risk-matched QQQ/BIL | G (10 bps) |
|---|---:|---:|---:|
| Final NAV | $71,489.48 | **$88,184.62** | $115,525.17 |
| CAGR | 1.86% | **2.96%** | 4.41% |
| Volatility | 2.27% | 2.27% | 4.31% |
| Sharpe rf=0 | 0.82 | **1.30** | 1.02 |
| Sharpe excess BIL | 0.29 | **0.76** | 0.73 |
| MaxDD | -6.37% | **-5.55%** | -11.41% |
| Peak | 2020-03-04 | 2008-08-14 | 2007-10-31 |
| Trough | 2020-03-16 | 2009-03-09 | 2009-03-09 |
| Recovery | 2023-04-20 | 2009-11-09 | 2009-12-28 |
| Longest underwater | 1,322 | **339** | 542 |
| Order legs | 128 | 397 | 430 |
| Total cost | **$1,901.21** | **$320.17** | $449.25 |

## 4. Direct conclusion

**QQQ Transition did not beat the risk-matched passive portfolio.**

- Passive CAGR **2.96%** vs Transition **1.86%**: **+1.10 pp** for passive.
- Passive MaxDD **-5.55%** vs Transition **-6.37%**.
- Passive Sharpe excess BIL **0.76** vs Transition **0.29**.
- Passive costs **$320** vs Transition **$1,901**.
- Transition held a 25% sleeve but was in market only ~3.3% of the time, so its
  realized risk was only ~2.27%; the risk-matched passive portfolio used ~10.5%
  QQQ continuously and produced more return at similar/lower drawdown.

This is consistent with the Transition result being **not evidence of timing
skill**; it is dominated by a simple passive exposure at the same realized vol.

## 5. Stage results

| Stage | Transition CAGR / DD | Risk-matched CAGR / DD |
|---|---:|---:|
| 2007-2015 | 0.86% / -3.65% | 1.74% / -5.55% |
| 2016-2020 | 2.20% / -6.37% | 6.45% / -3.02% |
| 2021-2026 | 6.34% / -1.95% | 10.24% / -3.76% |

## 6. Statistical evidence

20-lag HAC daily excess over BIL total return:

| Strategy | Excess/yr | t | p | 95% CI |
|---|---:|---:|---:|---:|
| Transition | +0.63% | 1.76 | 0.079 | -0.07%..+1.34% |
| Risk-matched | +1.71% | 3.69 | 0.0002 | +0.80%..+2.62% |
| G | — | — | — | — |

Circular block bootstrap CAGR 95% CI:

| Strategy | Low | High |
|---|---:|---:|
| Transition | -0.07% | +1.36% |
| Risk-matched | +0.82% | +2.59% |

Transition's excess is not statistically significant at 5%; risk-matched
passive is.

## 7. Cost / accounting caveat

- Transition NAV is PR #438's already-net 10 bps all-legs series.
- Passive and G use the calibrated `historical_backtest` layer at 10 bps.
- Transition total cost in dollars is `0.038024266 * 50000 = $1,901.21`; its
  `order_legs` is 128 (32 round trips ×4 legs).
- The Transition ledger cannot be converted to the new
  `historical_backtest` fee schedule without rerunning PR #438; original net NAV
  is retained and labeled. No mixed cost table is presented.

## 8. G comparison

G at 10 bps: CAGR 4.41%, vol 4.31%, MaxDD -11.41%, cost $449.
G has higher return but roughly **1.9× the realized volatility** of the matched
pair; its MaxDD is about twice as deep. It is a different risk budget, not a
like-for-like winner.

## 9. Artifacts

```text
data/research/transition_risk_match/transition_daily_nav.csv
data/research/transition_risk_match/transition_results.json
data/research/transition_risk_match/QQQ.csv
data/research/transition_risk_match/BIL.csv
docs/research/transition_risk_match/risk_match.json
docs/research/transition_risk_match/nav_transition.csv
docs/research/transition_risk_match/nav_risk_matched.csv
docs/research/transition_risk_match/trades_risk_matched.csv
tools/research/transition_risk_match.py
tests/test_transition_risk_match.py
```
