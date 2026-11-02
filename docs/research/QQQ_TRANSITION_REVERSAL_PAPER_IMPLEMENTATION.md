# QQQ reversal paper implementation

## Scope and safety

This is a broker-disconnected virtual execution engine for the frozen QQQ TRANSITION
five-session reversal candidate. It creates observations, order-intent records,
normalized Paper fills, a cash/share ledger, and mark-to-market NAV records. It cannot
connect to IBKR, select an account, transmit/cancel an order, or read credentials.

The protocol remains frozen from the research branch: $50,000 initial virtual capital,
25% target strategy sleeve ($12,500), BIL as the idle-capital instrument, next SPY
session Open entry, and exit at the Open five SPY sessions after entry. This code does
not tune the signal or start a prospective observation clock.

## Implemented

- SPY-calendar scheduling with exact next-session entry and five-further-session exit.
- Completed-close observation capture; stale or invalid source dates fail closed.
- Deterministic signal/order IDs and overlap suppression.
- Separate BIL sell / QQQ buy entry intents and QQQ sell / BIL buy exit intents.
- Strict PAPER-only fill normalization, timezone-aware UTC timestamps, fees and fill IDs.
- Import of a normalized execution CSV; it requires explicit PAPER mode and an intent ID
  for every execution. It deliberately does not ingest account numbers or credentials.
- Multiple executions per order and reconciliation of Filled, Partially Filled,
  Cancelled, Unfilled, and Inactive states. A broker-reported Filled order whose
  imported quantity does not reconcile is rejected.
- Event-driven cash and share accounting. Buys debit notional plus fees; sells credit
  notional less fees; insufficient cash, oversells, duplicate executions, inconsistent
  fee totals, and non-PAPER events fail closed.
- Daily NAV is computed from ledger cash and holdings. Cumulative fees are reported
  but are not deducted a second time because they have already reduced cash.
- Append-only JSONL event persistence with duplicate-ID and corrupt-log protection.
- Synthetic full round-trip test: BIL sell, QQQ buy, five-session hold, QQQ sell, BIL buy,
  and ending cash/units/NAV reconciliation.

## Normalized execution CSV

The importer expects these columns:

    intent_id,account_mode,broker_order_id,execution_id,fill_time_utc,fill_price,quantity,commission,other_fees

Every row must say PAPER. The intent_id must point to an existing order-intent event.
The importer is an adapter for a normalized manual/Flex Query export; it is not a
parser for every native IBKR Activity Statement layout. The operator must map each
broker execution to the correct intent and retain the original broker statement
outside Git. Never place account IDs, account numbers, tokens, or credentials in the
repository.

## Manual order sequencing

The intents are records only. For a future human-operated Paper dry run, the operator
must verify the account is PAPER in TWS, then execute and reconcile sequentially:

1. Entry: sell the required BIL quantity and wait for its final fill; only then buy QQQ
   within available proceeds. Do not assume the two legs fill simultaneously.
2. Exit: sell the actual QQQ units and wait for its final fill; only then buy BIL with
   available proceeds.
3. Import every partial execution separately. Do not replace partial fills with one
   blended estimate; reconcile remaining quantity and terminal broker status.
4. Record actual fill prices and commissions/fees separately. Slippage is reflected in
   the actual fill price versus the reference Open and must not be deducted again as a
   separate cash fee.

The initial virtual account is seeded at the supplied BIL mark to represent idle-capital
exposure. It is a virtual baseline, not evidence that a real Paper account already owns
those BIL shares. Before any prospective clock starts, the opening Paper account
positions/cash must be reconciled to a declared starting NAV and a human must approve
the operator checklist.

## Not implemented / remaining gates

- No live or Paper IBKR API/TWS/Gateway connection and no automated order submission.
- No native IBKR Activity Statement/Flex Query parser; normalized CSV mapping is required.
- No automatic market-data downloader or scheduled daily observer.
- No operator-approved account-opening checklist or broker-side dry run.
- No prospective observation clock is started by running these helpers.

Tests are run with:

    python -m pytest -q tests/test_qqq_transition_reversal_paper.py
