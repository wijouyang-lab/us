# Paper Trading Engine

PAPER only. No IBKR connection, no real orders.

- account: one $50,000 account, no per-strategy cash
- order: propose -> user confirmation -> fill
- integer shares, long-only, no negative cash
- fees: IBKR forward-estimate layer, separately from reference price
- authoritative store: SQLite (WAL + BEGIN IMMEDIATE)
- ledger: append-only table; JSON/CSV are exports only
- NAV: explicit prices required; missing price fails closed

```bash
python -m tools.paper_trading.cli --root data/paper_trading account
python -m tools.paper_trading.cli --root data/paper_trading propose \
  --client-id demo-1 --ticker AAPL --side BUY --shares 10 --price 200 \
  --asof 2026-11-04T20:00:00Z --strategy VALUE
# inspect proposal, then:
python -m tools.paper_trading.cli --root data/paper_trading confirm \
  --order-id <id> --token <token>
```

No synthetic quotes or fake positions are created by this package.
