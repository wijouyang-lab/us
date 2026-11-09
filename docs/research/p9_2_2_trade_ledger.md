# P9.2.2 Full Ledger Reconstruction and Exact-Replay Audit

Date: 2026-11-09
Status: **P9_2_2_LEDGER_PARTIAL**
P9.1: **NO-GO**

## 1. What was built

A full daily replay of the P9.1 A-H rules with:

- BUY/SELL order fields;
- reference price and execution price;
- commission, exchange fee, regulatory fee;
- fees-only and slippage, separately;
- all-in execution cost;
- positions, cash, BIL units/value, stock value, NAV;
- daily NAV identity;
- open positions at end;
- FIFO matcher.

Outputs:

```text
trade_ledger_final.csv
round_trip_trades_final.csv
open_positions_final.csv
daily_nav_reconciliation.csv
all_in_cost_reconciliation.csv
```

## 2. Important failure to reproduce P9.1 exactly

The full replay does **not** reproduce P9.1 JSON order counts:

| Strategy | P9.1 JSON closed | Replay BUY | Replay SELL | Open |
|---|---:|---:|---:|---:|
| A | 782 | 856 | 855 | 1 |
| B | 731 | 734 | 733 | 1 |
| C | 553 | 568 | 563 | 5 |
| D | 441 | 456 | 455 | 1 |
| E | 620 | 619 | 619 | 0 |
| F | 350 | 356 | 356 | 0 |
| G | 553 | 568 | 563 | 5 |
| H | 350 | 356 | 356 | 0 |

This is not a rounding issue. It means the exact P9.1 signal/data/execution version
cannot be proven identical from the repository artifacts.

Therefore:

```text
exact P9.1 NAV reconciliation: DATA_BLOCKED
exact P9.1 cost reconciliation: DATA_BLOCKED
P9.1 metric restatement: NOT DONE
```

The replay is a valid **new diagnostic ledger**, not a silent replacement for
P9.1 results.

## 3. Cost definitions

```text
fees_only = commission + exchange_fee + regulatory_fee
BUY slippage  = shares * (execution - reference)
SELL slippage = shares * (reference - execution)
all_in = fees_only + slippage
```

Positive slippage is adverse; negative is price improvement. Fees are deducted
from cash. Slippage is already embedded in execution price and is **not**
deducted from NAV a second time.

## 4. Daily NAV

Every daily row satisfies:

```text
NAV = cash + stock market value + BIL units * BIL price
```

`nav_identity_max_abs = 0` in the generated data.

Open positions are marked at the last available close and remain open; they are
not treated as realized sales.

## 5. All-in cost summary

The new replay all-in costs are:

| Strategy | Fees only | Slippage | All-in |
|---|---:|---:|---:|
| A | $802.72 | $1,479.24 | $2,281.96 |
| B | $683.56 | $1,423.02 | $2,106.58 |
| C | $568.95 | $1,053.19 | $1,622.15 |
| D | $476.88 | $820.97 | $1,297.85 |
| E | $607.91 | $1,144.70 | $1,752.60 |
| F | $377.52 | $662.20 | $1,039.71 |
| G | $568.95 | $1,053.19 | $1,622.15 |
| H | $377.52 | $662.20 | $1,039.71 |

Because the replay differs from P9.1, these are not presented as P9.1's exact
original costs.

## 6. Conclusion

```text
All orders complete:              NO — replay differs from P9.1
BUY/SELL fees consistent:         YES in replay
All slippage reconstructable:     YES in replay
Open positions:                   13 across 8 strategies
NAV identity:                     PASSES in replay
P9.1 CAGR/MaxDD restatement:      NO, exact replay DATA_BLOCKED
P9.1 strategy:                    STILL NO-GO
```

No Shadow, no IBKR, no PAPER-50000.
