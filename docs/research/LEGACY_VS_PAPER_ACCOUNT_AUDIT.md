# Legacy $50K Portfolio vs PAPER-50000

Date: 2026-11-04
Decision: **separate accounts; no migration.**

## Legacy account

Source files:

```text
portfolio_50000_meta.json
portfolio_50000_positions.csv
portfolio_50000_transactions.csv
portfolio_50000_history.csv
```

Identity:

```text
portfolio_id = US-50000-001
initial_capital = 50,000.00 USD
start_date = 2026-10-06
```

Observed final state:

```text
transactions: 12 (6 BUY / 6 SELL)
all positions closed
cash: 49,824.92
stock value: 0.00
realized PnL: -175.08
NAV: 49,824.92
return: -0.35%
last history date: 2026-11-02
```

It is a completed, closed legacy portfolio with its own ledger and cash.

## New account

```text
account_id = PAPER-50000
initial_cash = 50,000.00
started 2026-11-04
positions = none
cash = 50,000.00
```

## Relationship

There is no transfer, shared transaction ID, shared cash ledger, or matching
opening instruction proving these are the same account. `US-50000-001` already
has a closed trading history and a non-$50,000 NAV; `PAPER-50000` has no trades.

Therefore:

- **No migration is authorized.**
- Legacy remains `US-50000-001`, read-only display.
- New account remains `PAPER-50000`.
- Total simulated capital is **not** $100,000 and must not be summed.
- Any web page must show both IDs and state side by side.

A future migration requires an explicit user-approved mapping of every legacy
transaction and cost basis, a dry-run diff, and a reversible audit log.
