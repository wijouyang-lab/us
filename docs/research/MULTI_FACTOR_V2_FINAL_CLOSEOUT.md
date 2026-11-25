# PR #626 — Final Audit Closeout

Date: 2026-11-25

## Task progress

| Item | Weight | Status | Completion |
|---|---:|---|---:|
| P0 synthetic behavior tests | 50% | **NOT COMPLETE** | 0% |
| P1 max_age / missing-price stats | 20% | **COMPLETE** | 20% |
| P2 full pytest + CI + 9-group reconciliation | 20% | **COMPLETE** | 20% |
| P3 final report/status consistency | 10% | **COMPLETE** | 10% |
| **Total** | **100%** | **PARTIAL** | **50%** |

Remaining: 50%. Blocked work: 0% (P0 is incomplete, not technically blocked).
Final acceptance standard **not met**.

## What was actually run

- A/B/C, 5Y/3Y/1Y daily engine with raw-close execution and mark-close valuation.
- 5Y: A 9.83% CAGR, -14.15% MaxDD, 0.777 Sharpe (rf=0), 400 trades.
- 3Y: A 11.17%, -14.13%, 0.832, 288 trades.
- 1Y: A 19.01%, -7.75%, 1.232, 107 trades.
- 8 independent exit modes, 5/10/20 bps cost comparison.
- 9-group independent ledger NAV audit.

## 9-group independent NAV audit

All max absolute differences are < 1e-10 USD:

| Window | A | B | C |
|---|---:|---:|---:|
| 5Y | 2.91e-11 | 5.82e-11 | 5.82e-11 |
| 3Y | 4.37e-11 | 3.64e-11 | 2.91e-11 |
| 1Y | 3.64e-11 | 2.18e-11 | 4.37e-11 |

## Missing-price statistics

A 5Y: 323 skipped buys, 0 delayed exits, 0 stale holding days, max_age 0,
0 unvalued end positions, 0 valuation exceptions.

B 5Y: 157 skipped buys. C 5Y: 260 skipped buys. 3Y/1Y have similar nonzero
skipped-buy counts; delayed exits/stale days are 0 because held names always
had a real close on execution days.

`max_age` is now an explicit engine counter, but it reads 0 throughout; it is
not evidence that no stale marks existed historically, only that this engine's
held positions did not encounter missing raw closes over 5 days.

## P0 gap

Only 3 property/audit tests were added, not the required 12 synthetic
execution-path tests. The following are **NOT** covered by synthetic engine
tests:

- pending exit for 1/2/5/6 missing days;
- fixed6 vs fixed8 synthetic trigger dates;
- ATR20/25/30 synthetic trails;
- MA50/rank20/time20 synthetic independence;
- forced wrong-price negative test;
- synthetic fee/cash multi-trade reconciliation.

Therefore the audit cannot be marked PASS.

## Final decision

```text
AUDIT = AUDIT_PARTIAL
A = PROMISING_BUT_UNPROVEN
B = NO_GO
C = NO_GO
PAPER_50000 = NOT_AUTHORIZED
```

Walk-forward: **not authorized / not ready**.  
Production logic: unchanged.

## Files

- `MULTI_FACTOR_STRATEGY_V2_FINAL.md`
- `MULTI_FACTOR_V2_STRATEGY_COMPARISON.csv`
- `MULTI_FACTOR_V2_EXIT_COMPARISON.csv`
- `MULTI_FACTOR_V2_COST_SENSITIVITY.csv`
- `MULTI_FACTOR_V2_TRADE_LEDGER.csv`
- `MULTI_FACTOR_V2_DAILY_NAV.csv`
- `MULTI_FACTOR_V2_CROSS_WINDOW_RECONCILIATION.csv`
- `MULTI_FACTOR_V2_MISSING_PRICE_STATS.csv`
- `MULTI_FACTOR_V2_INDEPENDENT_NAV.csv`
- `MULTI_FACTOR_V2_INDEPENDENT_LEDGER_AUDIT.md`
- `MULTI_FACTOR_V2_CROSS_WINDOW_LEDGER_AUDIT.md`
