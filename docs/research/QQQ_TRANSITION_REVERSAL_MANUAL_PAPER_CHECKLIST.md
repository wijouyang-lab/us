# QQQ TRANSITION reversal — manual Paper rehearsal checklist

## Purpose and boundary

This checklist is for a human-supervised **IBKR Paper-only** rehearsal of the frozen
QQQ TRANSITION five-session reversal candidate. It is an operational safety and
reconciliation gate, not a strategy approval.

The repository code remains broker-disconnected. It cannot log in to TWS, choose an
account, transmit/cancel an order, or start a prospective observation clock. The
checklist command writes an attestation event only. Every order must be entered by a
human in the IBKR Paper interface after checking the visible account mode.

The strategy stays frozen: $50,000 virtual capital; 25% initial sleeve ($12,500);
BIL idle-capital instrument; signal after a completed close; enter on the next SPY
session's Open; exit at the Open five further SPY sessions after entry. Do not tune
thresholds, holding period, regime, or sizing during the paper period.

## A. Before preparing an entry

- Confirm the visible TWS account selector and account banner show the Paper account.
  Do not rely on a remembered username, prior session, or account suffix. Do not
  include account IDs, account numbers, login names, passwords, tokens, or API
  credentials in the checklist, event log, CSV, GitHub issue, or repository.
- Confirm the account currency and the paper cash/positions statement. Reconcile
  opening cash and positions to the opening account record. The virtual $50,000 seed
  is a strategy accounting baseline; it does not prove the broker Paper account has
  that same balance or already owns the virtual BIL shares.
- Verify the exact frozen strategy commit/config and record its SHA in the research
  evidence outside the checklist's free-text fields (the checklist intentionally has
  no free-text field).
- Confirm QQQ, SPY, and BIL inputs are complete for the required session, the data
  as-of date equals the signal date, and source files/hashes have been retained.
  A stale, future-dated, missing, non-finite, or non-positive input means **stop**.
- Confirm the signal was computed only after the completed regular-session close.
  Confirm the SPY calendar: entry is the next SPY session, and exit is the Open five
  further SPY sessions after entry.
- Before using an opening-auction order, verify the available order type, time-in-force,
  submission cutoff, and account-specific Paper behavior in the current TWS interface
  and current broker documentation. Do not assume a generic Market order submitted
  at any time will fill at the official historical Open. Record the actual fill time
  and price. If the available order behavior cannot implement the frozen Open rule,
  do not place the order; record the limitation.

## B. Entry sequence — two separate legs

The order-intent records are not broker orders. A human must perform and reconcile
each step in TWS:

1. Verify the planned entry session and the current Paper account banner again.
2. Submit the planned BIL sell leg manually, using the broker-confirmed order type.
3. Wait for terminal status and import every BIL execution separately. Reconcile
   executed shares, unfilled remainder, average fill price, execution IDs, timestamps,
   commissions, and other fees.
4. Only after actual BIL proceeds are known, calculate available cash and the QQQ
   buy quantity. Do not size the QQQ buy from an estimated or intended BIL notional.
5. Submit the QQQ buy manually. Import each partial execution separately and reconcile
   actual QQQ units, cash, and fees.
6. Rebuild the virtual ledger with the status command. It must agree with the imported
   execution records before the position is treated as open.

Do not assume the two entry legs execute simultaneously or at their reference Open.
If the BIL sale is partial/cancelled/inactive, size the QQQ buy only from actual net
proceeds. If the QQQ buy is partial/cancelled/inactive, record the actual partial
position; do not fabricate the requested quantity.

## C. Holding period and daily marks

- Use the SPY calendar, not calendar days or QQQ-only dates, to count the five
  further sessions after the entry session.
- Record a daily completed-session QQQ and BIL mark, its as-of date, source, and hash.
  Do not forward-fill a missing mark or use an intraday quote as a completed close.
- Recompute NAV from ledger cash, QQQ units, BIL units, and the two marks.
  Cumulative commissions/fees are disclosed but must not be deducted again: actual
  fill cash flows already include them.
- Reference-Open slippage is a diagnostic. For a buy, adverse slippage is
  (fill price / reference Open − 1) × 10,000 bps; for a sell it is
  (reference Open / fill price − 1) × 10,000 bps under the fill-price-dollar model
  retained in this implementation. Do not also subtract slippage as a second cash
  expense.

## D. Exit sequence — two separate legs

At the scheduled exit session:

1. Reconfirm the date is exactly five SPY sessions after entry and verify the Paper
   account banner.
2. Sell the actual reconciled QQQ share quantity manually. Import every execution.
3. Wait for actual net QQQ sale proceeds and terminal status.
4. Buy BIL only using actual available proceeds; import every execution.
5. Rebuild ledger status and NAV. Confirm QQQ shares are zero, BIL units/cash reconcile,
   and all commissions/fees and execution IDs are accounted for.

A rejected, inactive, partially filled, or cancelled order is not a full fill. Record
the remainder explicitly and do not represent the trade as closed until the residual
position has been reconciled.

## E. Stop / pause conditions

Stop before submitting the next leg and reconcile with the operator/reviewer whenever
any of the following occurs:

- Paper account mode cannot be visibly confirmed, or a Live account is selected.
- The order type, time-in-force, submission cutoff, or open-auction behavior is unclear.
- Strategy/config hash differs from the frozen research version.
- Signal date, SPY entry/exit date, data as-of date, or source hash does not reconcile.
- Missing/stale/invalid prices, non-finite values, or missing reference Open.
- Broker status says Filled but imported executions do not add up to the requested amount.
- Duplicate execution ID, overfill, insufficient proceeds, oversell, or negative cash.
- Commission/other-fee totals, execution timestamps, or broker statement cannot be
  reconciled to the normalized CSV.
- NAV calculated from the event log differs from the broker Paper statement after
  accounting for the explicitly documented starting cash/positions and valuation marks.

Do not resolve a discrepancy by editing old JSONL rows, changing a fill, or silently
altering a strategy parameter. Preserve the original broker statement outside Git,
record a new corrective/reconciliation event only after review, and keep prior records
unchanged. Never add an account identifier or credential to the repository.

## F. Record the preflight attestation

1. Copy docs/research/qqq_paper_manual_preflight.template.json to a local file outside
   the repository's tracked paths (for example, paper/preflight-YYYY-MM-DD.json).
2. Set session_date to the actual planned order session.
3. Set every required check to true only after the condition has actually been
   verified by the operator and independent reviewer. Leave anything uncertain as
   false; do not use a template full of true values.
4. Keep only the three top-level fields shown in the template. Do not add IDs, account
   numbers, login data, secrets, or free-text notes.
5. Run:

       python scripts/qqq_transition_reversal_paper_reconcile.py preflight paper/events.jsonl paper/preflight-YYYY-MM-DD.json

6. The preflight must be recorded for the exact planned_session before the CLI will
   append its order intents. An entry intent for another date requires a separate
   preflight. The same applies to the exit session.

The resulting PAPER_PREFLIGHT_REVIEW event says
orders_transmitted=false and observation_clock_started=false. It is only evidence
that the checklist was attested. It does not prove an order was placed, a broker fill
occurred, or the prospective observation period began.

## G. Required evidence after the rehearsal

Retain outside Git the broker statement/export and source input files. In the
append-only event log retain the seed, preflight, order-intent, per-execution fill,
and daily NAV events. Reconcile at least:

- Four possible legs: BIL sell, QQQ buy, QQQ sell, BIL buy.
- Order ID and every execution ID; requested, filled, and remaining quantities.
- Actual fill prices, reference Opens, timestamps with timezone, commission, and fees.
- Opening and closing BIL/QQQ units, cash, cumulative fees, and daily NAV.
- Any cancelled, rejected, inactive, or partially filled status and how the remaining
  quantity was handled.

A synthetic test is not broker execution evidence. Completion of this checklist is
not strategy validation or permission for Live trading.
