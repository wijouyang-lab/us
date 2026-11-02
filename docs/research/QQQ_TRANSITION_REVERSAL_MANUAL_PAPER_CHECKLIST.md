# QQQ TRANSITION reversal - manual IBKR Paper rehearsal checklist

## Purpose and boundary

This checklist is for a human-supervised **IBKR Paper-only** rehearsal of the frozen
QQQ TRANSITION five-session reversal candidate. It is an operational safety and
reconciliation gate, not a strategy approval.

The repository code is broker-disconnected. It cannot log in to TWS, choose an
account, transmit/cancel orders, or start a prospective observation clock. The
checklist command writes an attestation event only. Every order must be entered by a
human in the IBKR Paper interface after checking the visible account mode.

Frozen strategy: $50,000 virtual capital; 25% initial sleeve ($12,500); BIL as the
idle-capital instrument; signal after a completed close; entry at the next SPY
session Open; exit at the Open five further SPY sessions after entry. Do not tune
thresholds, holding period, regime, or sizing during the paper period.

## A. Before preparing an entry

- Confirm the visible TWS account selector and account banner show the **Paper**
  account. Do not rely on a remembered username, prior session, or account suffix.
  Do not put account IDs, account numbers, logins, passwords, tokens, or API
  credentials in the checklist, event log, CSV, GitHub issue, or repository.
- Confirm USD currency and the Paper cash/positions statement. Reconcile opening cash
  and positions to the opening account record. The virtual $50,000 seed is a strategy
  accounting baseline; it does not prove the broker Paper account has that balance or
  already owns the virtual BIL shares.
- Verify the frozen strategy commit/config and record its SHA in research evidence
  outside the checklist (the checklist has no free-text field).
- Confirm QQQ, SPY, and BIL inputs are complete for the session, the data as-of date
  equals the signal date, and source hashes are retained. Stale, future-dated,
  missing, non-finite, or non-positive input means **stop**.
- Confirm the signal was computed only after the completed regular-session close.
  Confirm the SPY calendar: entry is the next SPY session; exit is the Open five
  further SPY sessions after entry.
- Before using an opening-auction order, verify the available order type,
  time-in-force, submission cutoff, and account-specific Paper behavior in the
  current TWS interface and current broker documentation. Do not assume a generic
  Market order submitted at any time fills at the official historical Open. Record
  the actual fill time and price. If the available behavior cannot implement the
  frozen Open rule, do not place the order; record the limitation.

## B. Entry sequence - two separate legs

The order-intent records are not broker orders. A human performs and reconciles each
step in TWS:

1. Verify the planned entry session and the Paper account banner again.
2. Submit the planned BIL sell leg manually, using the broker-confirmed order type.
3. Wait for terminal status and import every BIL execution separately. Reconcile
   executed shares, unfilled remainder, average fill price, execution IDs, timestamps,
   commissions, and other fees.
4. Only after actual BIL proceeds are known, calculate available cash and the QQQ buy
   quantity. Do not size the QQQ buy from an estimated or intended BIL notional.
5. Submit the QQQ buy manually. Import each partial execution separately and reconcile
   actual QQQ units, cash, and fees.
6. Rebuild the virtual ledger with `status`. It must agree with imported executions
   before the position is treated as open.

Do not assume the two entry legs execute simultaneously or at their reference Open.
If the BIL sale is partial/cancelled/inactive, size QQQ only from actual net proceeds.
If the QQQ buy is partial/cancelled/inactive, record the actual partial position; do
not fabricate the requested quantity.

## C. Holding period and daily marks

- Use the SPY calendar, not calendar days or QQQ-only dates, to count five further
  sessions after entry.
- Record a daily completed-session QQQ and BIL mark, its as-of date, source, and hash.
  Do not forward-fill a missing mark or use an intraday quote as a completed close.
- Recompute NAV from ledger cash, QQQ units, BIL units, and the two marks.
  Cumulative commissions/fees are disclosed but must not be deducted again: actual
  fill cash flows already include them.
- Reference-Open slippage is a diagnostic. For a buy, adverse slippage is
  `(fill / reference - 1) * 10000` bps; for a sell it is
  `(reference - fill) / reference * 10000` bps. Do not subtract slippage as a second
  cash expense.

## D. Exit sequence - two separate legs

At the scheduled exit session:

1. Reconfirm the date is exactly five SPY sessions after entry and verify the Paper
   account banner.
2. Sell the actual reconciled QQQ share quantity manually. Import every execution.
3. Wait for actual net QQQ sale proceeds and terminal status.
4. Buy BIL only using actual available proceeds; import every execution.
5. Rebuild ledger status and NAV. Confirm QQQ shares are zero, BIL units/cash
   reconcile, and all commissions/fees and execution IDs are accounted for.

A rejected, inactive, partially filled, or cancelled order is not a full fill. Record
the remainder explicitly and do not represent the trade as closed until the residual
position is reconciled.

## E. Order status and execution CSV workflow

### Execution fill CSV

Columns:

    intent_id,account_mode,broker_order_id,execution_id,fill_time_utc,fill_price,reference_price,quantity,commission,other_fees

- `account_mode` must be `PAPER`.
- `intent_id` must match an existing ORDER_INTENT.
- `execution_id` and `broker_order_id` must match the broker export.
- `fill_time_utc` must be timezone-aware.
- Import every partial execution separately.

CLI:

    python scripts/qqq_transition_reversal_paper_reconcile.py import-fills paper/events.jsonl paper/fills.csv

### Order status CSV

Columns:

    intent_id,account_mode,broker_order_id,requested_quantity,broker_status

One row per intent, after the executions for that order have been imported:

- `Filled`: imported quantity must equal requested quantity.
- `Partially Filled` / `Submitted` / `PreSubmitted` with partial quantity:
  normalized as `PARTIALLY_FILLED`, retaining filled and remaining quantity.
- `Submitted` / `PreSubmitted` with zero fills: `UNFILLED`.
- `Cancelled`: `CANCELLED` if zero fills, `PARTIALLY_FILLED_CANCELLED` if partial.
- `Inactive`: `INACTIVE` or `PARTIALLY_FILLED_INACTIVE`; record the anomaly.
- `Filled` with incomplete imported quantity: rejected.
- Imported fill quantity greater than requested: rejected.
- `account_mode` must be `PAPER`; `LIVE` is rejected.
- `broker_order_id` must match every imported fill for that intent.
- Re-importing the same status rows is idempotent and does not double-book.

CLI:

    python scripts/qqq_transition_reversal_paper_reconcile.py reconcile-orders paper/events.jsonl paper/order_status.csv

The status command after reconciliation:

    python scripts/qqq_transition_reversal_paper_reconcile.py status paper/events.jsonl

## F. Stop / pause conditions

Stop before the next leg and reconcile with the operator/reviewer when:

- Paper mode cannot be visibly confirmed, or a Live account is selected.
- Order type, TIF, submission cutoff, or opening-auction behavior is unclear.
- Strategy/config hash differs from the frozen research version.
- Signal date, SPY entry/exit date, data as-of date, or source hash does not reconcile.
- Missing/stale/invalid prices, non-finite values, or missing reference Open.
- Broker says Filled but imported executions do not add up to the request.
- Duplicate execution ID, overfill, insufficient proceeds, oversell, or negative cash.
- Commission/fee totals, timestamps, or broker statement do not reconcile.
- NAV from the event log differs from the Paper statement after documented starting
  cash/positions and valuation marks.

Do not resolve a discrepancy by editing old JSONL rows, changing a fill, or silently
altering a strategy parameter. Preserve the original broker statement outside Git;
append a corrective/reconciliation event only after review. Never add an account
identifier or credential to the repository.

## G. Record the preflight attestation

1. Copy `docs/research/qqq_paper_manual_preflight.template.json` to a local file
   outside tracked paths, for example `paper/preflight-YYYY-MM-DD.json`.
2. Set `session_date` to the actual planned order session.
3. Set every required check to true only after the operator and independent reviewer
   have verified it. Leave uncertain items false.
4. Keep only the three top-level fields in the template. Do not add IDs, account
   numbers, login data, secrets, or free-text notes.
5. Run:

       python scripts/qqq_transition_reversal_paper_reconcile.py preflight paper/events.jsonl paper/preflight-YYYY-MM-DD.json

6. The preflight must be recorded for the exact planned session before order intents
   can be appended. A separate preflight is required for the exit session.

The resulting PAPER_PREFLIGHT_REVIEW event says `orders_transmitted=false` and
`observation_clock_started=false`. It is attestation evidence only; it does not prove
an order was placed, a fill occurred, or the prospective period began.

## H. Required evidence after the rehearsal

Retain outside Git the broker statement/export and source inputs. In the append-only
event log retain the seed, preflight, order-intent, per-execution fill, order-status
reconciliation, and daily NAV events. Reconcile:

- Four possible legs: BIL sell, QQQ buy, QQQ sell, BIL buy.
- Order ID and every execution ID; requested, filled, and remaining quantities.
- Actual fill prices, reference Opens, timezone-aware timestamps, commissions, fees.
- Opening and closing BIL/QQQ units, cash, cumulative fees, daily NAV.
- Any cancelled, rejected, inactive, or partially filled status and the residual.

A synthetic test is not broker execution evidence. Completing this checklist is not
strategy validation or permission for Live trading.

