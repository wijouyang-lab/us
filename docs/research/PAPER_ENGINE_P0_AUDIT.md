# P0 Paper Engine Safety Audit

Date: 2026-11-04
PR: #460

## Fixed

1. **Quote validation**
   - strict ISO-8601 parse with timezone;
   - rejects naive timestamps, future timestamps (>60s skew), stale quotes
     (default 12h, configurable);
   - proposal and confirmation both validate freshness;
   - stores `price_source`, `price_type`, `price_asof_utc`.
2. **Reservations**
   - buy reservation includes slippage-adjusted notional plus estimated fees;
   - all PENDING buys are included, so one cash balance cannot be double-spent;
   - sell reservations subtract pending sells;
   - slippage is restricted to 0..100 bps (negative rejected).
3. **Persistence and concurrency**
   - SQLite (`data/paper_trading/paper.sqlite`) is authoritative for account,
     orders, ledger and action events;
   - WAL mode, `BEGIN IMMEDIATE`, process lock;
   - confirmation updates the order only if still `PENDING`; otherwise the whole
     transaction rolls back;
   - account state, order state and fill ledger are committed in one transaction;
   - JSON is no longer authoritative.
4. **Order lifecycle**
   - proposals require a user-held confirmation token;
   - single-use confirmation; cancel only PENDING; expired proposals fail closed.
5. **NAV**
   - missing prices raise; no zero fill; no synthetic quotes.
6. **Dividend / split**
   - account-level dividend and split methods, with source/date fields;
   - split adjusts shares and per-share cost; zero-fraction handling still needs a
     dedicated policy event.

## Tests

`tests/test_paper_trading_platform.py`: **15 passed**

Added cases:

- future quote rejected;
- stale quote rejected;
- negative slippage rejected;
- multiple PENDING buys reserve fees/slippage;
- confirmation single-use;
- duplicate order, insufficient cash/position, cancel, expiry;
- NAV reconciliation and missing price fail-closed.

## Still open

- Dividend/split event IDs and idempotency are not yet exposed as a service;
- crash-recovery replay command is not yet implemented;
- no authenticated order API or web UI yet;
- no licensed quote provider yet; current fills require caller-supplied prices.
