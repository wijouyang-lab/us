# P9.2.1 Trade Ledger and Two-Sided Cost Audit

Date: 2026-11-09
Status: **P9_2_1_LEDGER_PARTIAL**
Strategy: **P9.1 remains NO-GO**

## 1. Code evidence

P9.1 `portfolio.py`:

```python
# BUY
f = fees(shares, buy, "BUY", date)["cost"]
eq_cash -= gross + f; costs += f
# SELL
f = fees(shares, sell, "SELL", date)["cost"]
eq_cash += gross - f; costs += f
```

Both legs call the IBKR Pro Tiered model. Sell side includes SEC/TAF rules;
buy side does not. 5 bps slippage is applied to both fill prices.

## 2. Reconstructed ledger

For A-H, every closed P9.1 trade was expanded into BUY and SELL legs.

| Strategy | BUY | SELL | Round trips | Buy fees | Sell fees | All-in cost | P9.1 reported fees |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 782 | 782 | 782 | $355.46 | $395.60 | $2,228.34 | $751.41 |
| B | 731 | 731 | 731 | $322.48 | $360.36 | $2,109.36 | $683.20 |
| C | 553 | 553 | 553 | $265.00 | $294.64 | $1,608.70 | $562.11 |
| D | 441 | 441 | 441 | $222.24 | $245.94 | $1,283.31 | $468.56 |
| E | 620 | 620 | 620 | $293.26 | $326.08 | $1,789.69 | $619.34 |
| F | 350 | 350 | 350 | $178.77 | $198.16 | $1,040.61 | $376.93 |
| G | 553 | 553 | 553 | $265.00 | $294.64 | $1,608.70 | $562.11 |
| H | 350 | 350 | 350 | $178.77 | $198.16 | $1,040.61 | $376.93 |

Finding:

- Sell fees are **not omitted**. Both sides are charged.
- `total_costs` in P9.1 JSON is **fees only**; it excludes the 5 bps slippage,
  which is embedded in fill prices.
- Therefore the reported “cost” understates all-in transaction cost. This is a
  reporting-label issue, not a missing cash deduction.
- No P9.1 return restatement is needed for a missing sell fee; the reported
  total-cost metric should be relabelled as fees-only.

## 3. Ledger completeness

P9.1 JSON stores only closed trades. It has:

- no `signal_date`;
- no order/fill split;
- no open positions;
- no per-leg fee columns;
- no explicit unmatched-sell check.

Thus:

```text
closed round-trip ledger:   reconstructed
open positions:             NOT_STORED_IN_P9_1_JSON
full NAV reconciliation:    PARTIAL
```

P9.1 code exits after 20 sessions, so open positions at the end are possible
but not listed. They are not treated as realized sales.

## 4. Reconciliation

The ledger reconciles fee-only totals to P9.1 within a few dollars; residual is
consistent with open-position BUY fees included in P9.1 `costs` but absent from
the closed-trade ledger. Slippage is the large difference:

```text
C fees-only:        $559.65
C all-in:           $1,608.70
C reported costs:   $562.11
C slippage:         $1,049.05
```

The all-in cost is already reflected in NAV via worse fill prices; it is not
double-counted.

## 5. FIFO

A fixed FIFO matcher is implemented and tested:

```text
buys 100 + 50
sells 120 + 40
=> matches 100, 20, 30; unmatched sell 10
```

P9.1 itself does not have partial exits; its JSON has one BUY and one SELL per
closed trade. No partial-sell statistics are invented.

## 6. Decision

```text
BUY and SELL both charged:       YES
Sell fee omitted:                NO
P9.1 returns need restatement:   NO
P9.1 reported total cost label:  NEEDS CORRECTION (fees only)
Ledger completeness:             PARTIAL
P9.1 strategy:                   NO-GO
```

No Shadow. No IBKR. No PAPER-50000.

## 7. Files

```text
data/research/p9_2_1_trade_ledger/
  trade_ledger.csv
  round_trip_trades.csv
  trade_cost_reconciliation.csv
  trade_cost_audit.json
docs/research/p9_2_1_trade_ledger_audit.md
tests/test_p9_2_1_trade_ledger.py
```
