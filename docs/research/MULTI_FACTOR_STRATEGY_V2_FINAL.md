# Multi-Factor Price Strategy V2 — Execution & Exit Audit

Date: 2026-11-25
Branch: `research/multi-factor-strategy-competition-v1`
PR: #626
Final HEAD: `1a9999ccb82b11e75d9e09b7c5c305f39ede02cc` (before this audit commit)
Status: **PROMISING_BUT_UNPROVEN**, no PAPER authorization

## 1. P0 fixes

- Exits are confirmed on **prior close** and executed at **current close**.
- Entries already used prior-close signal and current-close execution.
- Ledger records `signal_date`, `entry_date`, `execution_date`,
  `exit_signal_date`, `exit_execution_date`, entry/exit prices, shares, both fees,
  gross and net PnL.
- Final open positions are emitted as `OPEN_AT_END`, not silently dropped.
- NAV is computed as `cash + market value` every day.

No OHLC Low/High is available, so no intraday stop assumption is claimed.

## 2. P1 exit independence

Independent modes: fixed6, fixed8, ATR20, ATR25, ATR30, MA50, rank20, time20.
No implicit time exit is added to other modes.

## 3. Corrected results

| Window | Strategy | CAGR | Vol | Sharpe | MaxDD | Trades |
|---|---|---:|---:|---:|---:|---:|
| 5Y | A | 9.83% | 13.2% | 0.777 | -14.15% | 400 |
| 5Y | B | 5.94% | 11.5% | 0.560 | -14.33% | 407 |
| 5Y | C | 8.18% | 12.8% | 0.679 | -12.03% | 413 |
| 3Y | A | 11.17% | 13.9% | 0.832 | -14.13% | 288 |
| 3Y | B | 6.87% | 12.5% | 0.594 | -14.10% | 287 |
| 3Y | C | 11.48% | 13.6% | 0.865 | -12.03% | 294 |
| 1Y | A | 19.01% | 15.0% | 1.232 | -7.75% | 107 |
| 1Y | B | 12.52% | 13.5% | 0.942 | -10.86% | 112 |
| 1Y | C | 15.14% | 15.2% | 1.003 | -11.00% | 115 |

Benchmarks:

| Window | SPY CAGR | SPY DD | QQQ CAGR | QQQ DD |
|---|---:|---:|---:|---:|
| 5Y | 11.85% | -25.36% | 15.14% | -35.62% |
| 3Y | 21.87% | -19.00% | 26.94% | -22.88% |
| 1Y | 17.41% | -9.13% | 23.62% | -12.19% |

## 4. Old vs corrected

| Metric | Preliminary | Corrected |
|---|---:|---:|
| A 5Y CAGR | 9.30% | **9.83%** |
| A 5Y MaxDD | -11.46% | **-14.15%** |
| A 3Y CAGR | 16.96% | **11.17%** |
| A 1Y CAGR | 35.91% | **19.01%** |

The old 3Y/1Y figures were inflated by same-close exits and implicit time exits.
The corrected 5Y return is slightly higher but drawdown is worse and still under
15%.

## 5. Exit comparison (A, 5Y)

| Exit | CAGR | MaxDD | Sharpe | Trades |
|---|---:|---:|---:|---:|
| fixed6 | 4.59% | -24.00% | 0.349 | 75 |
| fixed8 | 11.37% | -21.24% | 0.697 | 50 |
| ATR20 | 10.94% | -13.85% | 0.760 | 550 |
| ATR25 | 9.83% | **-14.15%** | 0.777 | 400 |
| ATR30 | 8.93% | -11.52% | **0.818** | 318 |
| MA50 | 8.89% | -14.13% | 0.632 | 277 |
| rank20 | -2.42% | -17.30% | -0.469 | 236 |
| time20 | 8.80% | -12.99% | 0.705 | 530 |

ATR25 remains the best balance for a 15% target. ATR30 has the best Sharpe and
lower DD. fixed6 is clearly bad; fixed8 has high CAGR but breaches 15%.

## 6. Cost sensitivity (A, 5Y)

| bps/side | CAGR | MaxDD | Sharpe |
|---|---:|---:|---:|
| 5 | 10.41% | -13.86% | 0.818 |
| 10 | 9.83% | -14.15% | 0.777 |
| 20 | 8.68% | -14.77% | 0.696 |

## 7. Ledger / NAV

- 400 A trades over 5Y, 407 B, 413 C.
- Ledger: 1,220 rows including 30 `OPEN_AT_END`.
- Buy and sell fees are both recorded from actual notional.
- PnL = gross − buy fee − sell fee.
- NAV = cash + mark-to-market holdings each day.
- Final open positions are explicitly marked, not discarded.

## 8. Conclusion

```text
A = PROMISING_BUT_UNPROVEN
B = NO_GO
C = NO_GO
OVERALL = PROMISING_BUT_UNPROVEN
PAPER_50000 = NOT_AUTHORIZED
```

A meets 15% DD on 5Y/3Y/1Y but underperforms SPY CAGR on 5Y/3Y, has no strict
walk-forward OOS, uses a partial 502-name universe, and unadjusted close prices.
It is observation-only.

## 9. Files

- `tools/research/mf_strategy_v2_fast.py`
- `tests/test_mf_strategy_v2_fast.py`
- `docs/research/MULTI_FACTOR_STRATEGY_V2_FINAL.md`
- `docs/research/MULTI_FACTOR_V2_STRATEGY_COMPARISON.csv`
- `docs/research/MULTI_FACTOR_V2_EXIT_COMPARISON.csv`
- `docs/research/MULTI_FACTOR_V2_COST_SENSITIVITY.csv`
- `docs/research/MULTI_FACTOR_V2_TRADE_LEDGER.csv`
- `docs/research/MULTI_FACTOR_V2_DAILY_NAV.csv`
- `docs/research/MULTI_FACTOR_V2_ANNUAL_RETURNS.csv`
- `docs/research/MULTI_FACTOR_V2_RUNTIME_PROFILE.md`
## V2.1 Independent audit addendum

- Raw close and mark close are separated; trades use raw close only.
- Pending exits are retried on the next real close; no same-close fill.
- Open positions are `OPEN_AT_END`.
- Independent ledger reconstruction: max NAV difference 2.91e-11 USD.
- A 5Y unchanged: 9.83% CAGR, -14.15% MaxDD, 0.777 Sharpe, 400 trades.
- `MULTI_FACTOR_V2_INDEPENDENT_LEDGER_AUDIT.md` has the audit details.
- Status remains `PROMISING_BUT_UNPROVEN`; no PAPER authorization.
