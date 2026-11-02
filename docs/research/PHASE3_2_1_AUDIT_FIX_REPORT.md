# Phase 3.2.1 Risk Engine Audit Fixes

Date: 2026-11-02
Base: `research/phase3-2-risk-engine` (PR #425)
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`

## 1. Corrections from ChatGPT audit

| # | Finding | Fix |
|---|---|---|
| 1 | Drawdown sign mismatch disabled defence | `simulate()` now passes positive drawdown magnitude `max(0, -dd)`; end-to-end tests cross all five thresholds |
| 2 | SPY bearish weeks did not liquidate | every weekly SPY signal emits an event; bearish weeks emit an empty target and move to cash |
| 3 | Rank score ignored by sizing | inverse-vol weights multiplied by rank percentile tilt: best 1.0x, worst 0.5x; no fixed count |
| 4 | Empty weeks did not rebalance | events are built per signal date, including empty candidate sets; empty target sells all |
| 5 | Average holdings understated | `n_holdings` is actual daily outstanding names, not zero on non-rebalance days |
| 6 | Unlimited forward-fill | closes ffill limited to 5 days; held stale >5 days raises `StalePriceError` |
| 7 | Single asset rejected | one-asset portfolio allowed; only zero-vol/no-history fails |
| 8 | Double cost haircut | removed `1 - 2c` reserve; target is scaled only by the actual computed cost once |

## 2. Old vs corrected, 10 bps

| Scheme | Old CAGR | New CAGR | Old MaxDD | New MaxDD | Old Sharpe | New Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| A SPY buyhold | 12.66% | 12.66% | 鈭?4.10% | 鈭?4.10% | 0.724 | 0.724 |
| B SPY trend/cash | 12.63% | **8.46%** | 鈭?4.04% | **鈭?8.05%** | 0.724 | **0.750** |
| C equal confirmed | 9.51% | 9.31% | 鈭?3.09% | 鈭?3.12% | 0.619 | 0.608 |
| D risk engine | 3.73% | **鈭?.24%** | 鈭?0.39% | **鈭?2.24%** | 0.394 | **鈭?.241** |

B now liquidates in bearish weeks: CAGR falls but drawdown is roughly halved; Sharpe slightly improves.

D now stays below 15% drawdown, but at a negative CAGR. It is **not** a success.

## 3. D diagnostics (10 bps, corrected)

```text
average stock exposure:  15.9%
average cash:            84.1%
average daily holdings:  43.2
max single weight:        3.16%
max cluster weight:      17.6%
stale holding-days:       0
total cost:               2.34% of initial capital
turnover:                11.7x
HARD breaches:            0
state occupancy:     CASH_DEFENSE 1672 days
                     DEFENSIVE_75 266
                     NORMAL 145
                     DEFENSIVE_50 94
                     DEFENSIVE_25 38
```

The defence ladder is now actually engaged, but the 12% cash state is sticky:
with no risk, the portfolio cannot recover its high-water mark. This produces a
mostly-cash portfolio and negative CAGR. This is an unresolved design issue, not
a parameter optimization.

## 4. Cost sensitivity (corrected D)

| Cost | CAGR | MaxDD |
|---:|---:|---:|
| 5 bps | 鈭?.01% | 鈭?2.57% |
| 10 bps | 鈭?.24% | 鈭?2.24% |
| 20 bps | 鈭?.12% | 鈭?2.45% |
| 50 bps | 鈭?.21% | 鈭?2.90% |

Costs are no longer monotonic because the path-dependent cash defence changes
exposure; all cases are negative. The low sensitivity reflects the 84% cash
position, not a robust cost model.

## 5. Annual returns (corrected)

| Year | B SPY trend | C equal | D risk |
|---|---:|---:|---:|
| 2018 | +2.1% | 鈭?.0% | 鈭?.7% |
| 2019 | +5.1% | +23.8% | +7.2% |
| 2020 | +1.7% | +13.6% | 鈭?.7% |
| 2021 | +28.8% | +26.4% | 0.0% |
| 2022 | 鈭?3.5% | 鈭?7.3% | 0.0% |
| 2023 | +12.3% | +12.9% | 0.0% |
| 2024 | +24.0% | +22.2% | 0.0% |
| 2025 | +11.4% | +10.1% | 0.0% |
| 2026* | +9.1% | +8.8% | 0.0% |

*through 2026-10-28.

D's zero years are cash after the 2020 breach; this is not a recovered strategy.

## 6. Stale-price policy

- closes forward-filled maximum 5 trading days;
- held asset missing >5 days raises `StalePriceError`;
- stale holding-days are reported;
- C had 116 stale holding-days, no breach; D had 0.

## 7. Tests

`tests/test_trend_v1_audit_fixes.py`: **12 passed**
`tests/test_trend_v1_spy_benchmark.py`: **1 passed**
Existing trend/portfolio tests: **17 passed**

New coverage:

- drawdown sign through `simulate()`;
- all five defence thresholds end-to-end;
- rank tilt changes weights;
- empty weekly event liquidates;
- daily holdings persist;
- stale price fails closed;
- single asset allowed;
- exact cost fixture;
- bearish SPY week emits cash event.

## 8. Remaining issues

- 12% cash defence is sticky and prevents recovery;
- D is negative CAGR and mostly cash;
- no dividends, delisting returns, ETF PIT membership;
- current 503-name survivorship bias;
- price returns only;
- no live slippage/capacity;
- B's 2019 result is sensitive to the exact weekly trend filter; no parameter tuning was done.

## 9. Conclusion

The audit's correctness findings are fixed and the corrected engine is
implemented. It does **not** produce an attractive strategy:

- B improves drawdown but gives up substantial CAGR;
- C still underperforms SPY;
- D meets the 15% drawdown level only by moving mostly to cash, with negative
  CAGR and no recovery mechanism.

No deployment or Strategy Lab ranking is justified.
Audit fix branch is research-only.
