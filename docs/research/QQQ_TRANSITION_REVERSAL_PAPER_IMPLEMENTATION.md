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
- Strict PAPER-only fill normalization, timezone-aware UTC timestamps, per-fill reference Open, fees and fill IDs.
- Side-aware realized slippage in bps and USD versus the reference Open; it is a diagnostic because actual fill prices already flow through cash accounting.
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

    intent_id,account_mode,broker_order_id,execution_id,fill_time_utc,fill_price,reference_price,quantity,commission,other_fees

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
4. Record actual fill prices, reference Open prices, and commissions/fees separately.
   The engine calculates side-aware slippage bps and USD. Slippage is already reflected
   in the actual fill-price cash flow and must not be deducted again as a cash fee.

The initial virtual account is seeded at the supplied BIL mark to represent idle-capital
exposure. It is a virtual baseline, not evidence that a real Paper account already owns
those BIL shares. Before any prospective clock starts, the opening Paper account
positions/cash must be reconciled to a declared starting NAV and a human must approve
the operator checklist.

## Local operator CLI

The local CLI makes the event-ledger workflow executable without adding any broker
connectivity. It writes only to the JSONL path supplied by the operator.

Initialize a fresh virtual account (this must be an empty event log):

    python scripts/qqq_transition_reversal_paper_reconcile.py seed paper/events.jsonl --date YYYY-MM-DD --bil-mark <BIL-open-mark>

Before any entry intent, copy
docs/research/qqq_paper_manual_preflight.template.json to a local JSON file, set the
session_date to the planned order session, and set every check to true only after the
operator and independent reviewer have verified it. Do not add account IDs, account
numbers, credentials, tokens, or free-text notes. Then record the preflight:

    python scripts/qqq_transition_reversal_paper_reconcile.py preflight paper/events.jsonl paper/preflight-YYYY-MM-DD.json

After the signal/protocol operator has created a trade ID and signal ID, persist the
entry intent pair. The CLI refuses to append intents unless an approved preflight
exists for the exact planned session:

    python scripts/qqq_transition_reversal_paper_reconcile.py entry-intents paper/events.jsonl --trade-id <trade-id> --signal-id <signal-id> --entry-session YYYY-MM-DD

After the operator has manually verified PAPER mode in TWS and completed the two
entry legs, map each execution into the normalized CSV schema above and import the
whole file (the import validates all rows against the current ledger before appending
any of them):

    python scripts/qqq_transition_reversal_paper_reconcile.py import-fills paper/events.jsonl paper/entry_fills.csv

Inspect the reconciled shares and cash:

    python scripts/qqq_transition_reversal_paper_reconcile.py status paper/events.jsonl

At the scheduled exit session, complete and record a second preflight with
session_date equal to the planned exit session. The CLI requires a separate exact-date
preflight before it will append the exit intents. Use the actual reconciled QQQ share
count and expected BIL notional:

    python scripts/qqq_transition_reversal_paper_reconcile.py preflight paper/events.jsonl paper/preflight-EXIT-DATE.json
    python scripts/qqq_transition_reversal_paper_reconcile.py exit-intents paper/events.jsonl --trade-id <trade-id> --signal-id <signal-id> --exit-session YYYY-MM-DD --qqq-quantity <actual-QQQ-shares> --estimated-proceeds <estimated-BIL-USD>
    python scripts/qqq_transition_reversal_paper_reconcile.py import-fills paper/events.jsonl paper/exit_fills.csv

Append a mark only after supplying the completed-session QQQ/BIL marks and their
source hashes:

    python scripts/qqq_transition_reversal_paper_reconcile.py nav paper/events.jsonl --date YYYY-MM-DD --qqq-mark <QQQ-close> --bil-mark <BIL-close> --qqq-source-hash <sha256> --bil-source-hash <sha256>

A NAV event for a date is immutable and duplicate date appends are rejected. The
preflight command records human attestations only; it does not submit orders or start
the prospective observation clock. See
docs/research/QQQ_TRANSITION_REVERSAL_MANUAL_PAPER_CHECKLIST.md for stop conditions
and the full rehearsal sequence. Keep original broker statements and any account
identifiers outside the repository. The example commands are for local ledger
operation, not broker commands.

## Order-status reconciliation

After importing executions, import one normalized status row per intent:

    intent_id,account_mode,broker_order_id,requested_quantity,broker_status

Run:

    python scripts/qqq_transition_reversal_paper_reconcile.py reconcile-orders paper/events.jsonl paper/order_status.csv

Statuses:

- `Filled`: imported quantity must equal requested quantity.
- `Partially Filled`: actual filled and remaining quantity retained.
- `Cancelled`: zero fills -> `CANCELLED`; partial -> `PARTIALLY_FILLED_CANCELLED`.
- `Submitted` / `PreSubmitted`: partial -> `PARTIALLY_FILLED`; zero -> `UNFILLED`.
- `Inactive`: zero -> `INACTIVE`; partial -> `PARTIALLY_FILLED_INACTIVE`.
- `LIVE` is rejected.
- A broker order ID that differs from imported fills is rejected.
- An overfill is rejected.
- Re-importing identical status rows is idempotent.

The import appends `ORDER_RECONCILIATION` events only. It creates no fills, changes no
cash, and transmits no orders. See the manual checklist for the TWS Paper sequence.

## Not implemented / remaining gates

- No live or Paper IBKR API/TWS/Gateway connection and no automated order submission.
- No native IBKR Activity Statement/Flex Query parser; normalized CSV mapping is required.
- No automatic market-data downloader or scheduled daily observer.
- No completed real-world Paper-account checklist or broker-side dry run; only the
  privacy-safe checklist template and local preflight recording gate are implemented.
- No prospective observation clock is started by running these helpers.

Tests are run with:

    python -m pytest -q tests/test_qqq_transition_reversal_paper.py
