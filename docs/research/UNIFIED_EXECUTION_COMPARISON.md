# Unified Execution Comparison: Transition vs Passive QQQ/BIL vs G

Date: 2026-11-03
Branch: `research/fixed-risk-budget-qqq-bil`
Status: **Transition still does not beat risk-matched passive**

## 1. Scope

Same $50,000, same QQQ/BIL raw Open/Close, same dividends, same IBKR
`historical_backtest` fees, same 1/3/5/10/20 bps execution scenarios.

The Transition trade sequence is rebuilt from PR #438's
`w25_c10_all_legs` ledger: 32 round trips, 129 order legs including the initial
BIL purchase. No signal parameter was changed.

## 2. Fee / slippage model

- IBKR Pro Tiered current-rate approximation (`historical_backtest`).
- Commission, SEC, TAF, CAT, clearing, exchange separately recorded.
- Buy price = raw Open × (1 + slip); sell = raw Open × (1 - slip).
- Slippage is an execution scenario, not measured NBBO or actual IBKR fill.
- The 2026 TAF holiday is applied only in its actual window, not the full history.

## 3. Main results at 3 bps/leg

| Metric | Transition | Risk-matched 10.5337% QQQ | G 20% |
|---|---:|---:|---:|
| Final NAV | $72,369.62 | **$88,165.78** | $115,324.60 |
| CAGR | 1.92% | **2.96%** | 4.40% |
| Volatility | 2.06% | 2.27% | 4.31% |
| Sharpe rf=0 | 0.94 | **1.30** | 1.02 |
| Sharpe excess BIL | 0.35 | **0.76** | 0.73 |
| MaxDD | -5.46% | -5.55% | -11.38% |
| Peak / trough / recovery | 2020-03-04 / 2020-03-16 / 2023-01-26 | 2008-08-14 / 2009-03-09 / 2009-11-09 | 2007-10-31 / 2009-03-09 / 2009-12-28 |
| Longest underwater | 1,264 | **339** | 542 |
| Order legs | 129 | 401 | 427 |
| IBKR fees | $101.30 | $143.58 | $154.43 |
| Slippage | $557.18 | $53.86 | $88.28 |
| Total cost | $658.48 | $197.43 | $242.71 |
| Cost-before NAV | $73,028.10 | $88,363.21 | $115,567.31 |
| Cost-before CAGR | 1.97% | 2.98% | 4.41% |

At 3 bps the passive portfolio has slightly higher vol than the rebuilt
Transition (2.27% vs 2.06%), so it is not exactly vol-matched in this rebuild.
The original risk match was to PR #438's 2.266% NAV vol with 10.5337% QQQ; that
weight is retained, not re-optimized.

## 4. PR #438 original at 10 bps

| Metric | Transition (PR438) | Risk-matched 10.5337% |
|---|---:|---:|
| CAGR | 1.86% | **2.95%** |
| Volatility | 2.27% | 2.26% |
| Sharpe rf0 | 0.82 | **1.30** |
| Sharpe excess BIL | 0.29 | **0.75** |
| MaxDD | -6.37% | -5.55% |
| Total cost | $1,901.21 | $324.18 |

This is the cleanest risk-matched comparison: both ~2.27% vol. Passive wins on
return, drawdown, Sharpe and cost.

## 5. Cost sensitivity

| Slip | Transition CAGR / MaxDD / cost | Passive CAGR / MaxDD / cost | G CAGR / MaxDD / cost |
|---|---:|---:|---:|
| 1 bps | 1.97% / -5.45% / $219 | 2.99% / -5.54% / $67 | 4.41% / -11.36% / $82 |
| 3 bps | 1.92% / -5.46% / $658 | 2.96% / -5.55% / $197 | 4.40% / -11.38% / $243 |
| 5 bps | 1.87% / -5.47% / $1,098 | 2.93% / -5.55% / $328 | 4.37% / -11.40% / $404 |
| 10 bps | 1.80% / -5.53% / $1,933 | 2.95% / -5.55% / $324 | 4.38% / -11.42% / $448 |
| 20 bps | 1.67% / -5.67% / $3,072 | 2.91% / -5.55% / $578 | 4.32% / -11.47% / $875 |

*(cost values are scenario-generated; exact table is in `results.json`.)*

Passive beats Transition at every slip level. Difference is not a cost artifact.

## 6. Direct answers

1. **Does Transition still underperform?** Yes, at 1/3/5/10/20 bps.
2. **Return or cost?** Both: Transition has lower gross return and roughly 3× the
   total cost of the passive portfolio. Its cost-before CAGR is also lower.
3. **Consistent across slips?** Yes.
4. **Extra return after risk matching?** No; at the clean 10 bps match it is
   lower by ~1.1 pp CAGR.
5. **Statistically significant?** Transition's excess over BIL at 3 bps is
   +0.69%/yr, p=0.039; passive is +1.71%/yr, p=0.0002. Transition's bootstrap
   CI barely excludes zero; it is not better than passive.
6. **G as passive benchmark?** Yes, as a 20% risk budget; it has more return and
   roughly 1.9× the vol/MaxDD of the matched pair.
7. **Further OOS?** No strategy has independent OOS validation. Transition
   should not be promoted.

## 7. Artifacts

```text
docs/research/unified_execution/results.json
docs/research/unified_execution/nav_Transition.csv
docs/research/unified_execution/nav_Transition_before_cost.csv
docs/research/unified_execution/nav_RiskMatched.csv
docs/research/unified_execution/nav_RiskMatched_before_cost.csv
docs/research/unified_execution/nav_G.csv
docs/research/unified_execution/nav_G_before_cost.csv
docs/research/unified_execution/trades_Transition.csv
docs/research/unified_execution/trades_RiskMatched.csv
docs/research/unified_execution/trades_G.csv
tools/research/unified_execution_comparison.py
tests/test_unified_execution_comparison.py
```
