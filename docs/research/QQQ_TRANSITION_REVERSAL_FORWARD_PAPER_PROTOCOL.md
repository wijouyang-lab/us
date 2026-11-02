# QQQ TRANSITION 5-Day Reversal — Prospective Paper Protocol

**Status:** protocol proposal only; not activated; no brokerage connection or orders are created by this change.  
**Parent research result:** PR #438, HEAD `9b6effa6b76d860e583ba5b2edd9d79083997ffd`.  
**Strategy grade:** Research Candidate. Not independently validated. Not deployable.  
**Protocol date:** 2026-11-02.

## 1. Purpose and boundaries

This protocol defines a prospective, event-by-event paper observation process for the frozen QQQ reversal candidate. It is intended to measure whether the signal can be generated without look-ahead, whether scheduled opening orders can be handled consistently, and what the broker paper simulator reports for fills and commissions.

It is **not** a production deployment plan, a request to place live orders, or evidence of alpha. It must not change the production scanner, production scoring, ATR stop logic, trade ledger, or the generic paper-trading system.

No API credentials, account identifiers, or secrets belong in this repository. No live order route is permitted. The protocol remains inactive until a separate implementation and paper-account operating procedure are reviewed.

## 2. Why the existing generic paper system must not be reused

The repository's existing `scripts/paper_trading.py` and `.github/workflows/paper-trading.yml` serve a different strategy:

- Generic scan candidates, not QQQ reversal signals.
- A 20-trading-day holding rule and a -5% close-based stop, not the QQQ strategy's five-further-SPY-session open exit.
- A shared `portfolio_paper_transactions.csv` ledger and a workflow gated to `main`.

Reusing that workflow or ledger would mix distinct signal populations, holding rules, and performance records. This strategy therefore requires its own isolated observations, order-intent records, fill records, and NAV ledger. The existing watchdog's 40-observation-day counter is not an adequate validation threshold for this low-frequency strategy.

## 3. Frozen strategy contract

The following are copied from the audited PR #438 result and must not be tuned during prospective observation:

| Item | Frozen definition |
|---|---|
| Instruments | QQQ for the risk sleeve; BIL for idle/reserve capital |
| Regime instrument | SPY |
| Signal calculation | After the completed close of session t |
| QQQ event | 5-session QQQ adjusted-price return at t is at or below the 5th percentile of the prior 252 completed 5-session returns; the threshold is shifted one session |
| Regime gate | SPY is TRANSITION at t under the audited MA200 / 20-session MA200 slope definition |
| Entry | Next SPY session's regular-session opening opportunity |
| Exit | Open after exactly five further SPY sessions following entry |
| Overlap | One position maximum; overlapping signals are skipped and logged |
| Direction | Long QQQ only; no leverage |
| Idle capital | BIL, including the reserve sleeve |
| Primary prospective sizing | 25% of a $50,000 virtual portfolio (initial target sleeve $12,500); remaining portfolio capital stays in BIL |
| Other historical sizes | 50% retained as a historical comparator only; 100% excluded from prospective order sizing because audited MaxDD exceeded the 15% objective |
| Stops / extra filters | None; do not add RSI, ATR, stop-losses, or discretionary filters |

The 25% size is selected as the conservative operating candidate because its audited 10 bps all-legs MaxDD was approximately -6.4%, leaving more historical headroom against the 15% objective than the 50% candidate. This is a sizing choice, not a new signal parameter or a claim that future drawdown is bounded.

## 4. Prospective session workflow

Every SPY session must produce an observation record, including zero-signal sessions.

1. **After close on t:** use only completed QQQ and SPY bars available as of t. Compute the frozen signal and regime. Record the data-as-of date, source, retrieval timestamp, raw input file hashes, code commit, rule/parameter fingerprint, 5-day return, threshold, SPY regime, and signal outcome.
2. **Signal day with no open position:** create one immutable order intent for the next SPY session. The intent records the exact planned date, QQQ target sleeve notional, and the paired BIL sell / QQQ buy legs. Do not create a second active intent while a position or next-session entry is pending.
3. **Next session opening:** any test order must be submitted only in the clearly selected IBKR Paper account, with regular-hours-only eligibility. Record the actual order submission time, broker order ID, each execution time, each partial fill, average fill price, quantity, and each reported commission/fee. If a fill is late, partial, rejected, or absent, record that fact; never replace it with the historical Open or backdate it.
4. **Scheduled exit session:** after five further SPY sessions, create the paired QQQ sell / BIL buy intent for the opening. Record the actual paper fills and all costs in the same manner.
5. **Daily reconciliation:** reconcile the virtual $50,000 ledger to all four actual paper order legs (BIL sell, QQQ buy, QQQ sell, BIL buy), cash/residuals, units, commissions, and adjusted end-of-day marks. Keep the raw broker statement/export as the execution evidence.

The historical backtest's `Open` is a reference mark, not a promise of an IBKR fill. A paper fill must be represented by its actual simulator-reported fill price and timestamp. Any mismatch between the planned opening and the actual fill is an execution deviation and remains visible in the ledger.

### Required record fields

**Daily observation record**

- `session_date`, `observed_at_utc`, `data_asof_date`
- `qqq_source`, `spy_source`, `bil_source`, retrieval timestamps, file SHA-256 hashes
- `code_sha`, `rule_fingerprint`, `lookback=252`, `quantile=0.05`, `hold_sessions=5`
- `qqq_ret5`, `threshold_5pct`, `spy_ma200`, `spy_slope20`, `spy_regime`
- `signal`, `overlap_skipped`, `reason`, `planned_entry_session`, `planned_exit_session`

**Order / fill record — one row per execution**

- `signal_id`, `trade_id`, `symbol`, `side`, `leg` (BIL_TO_QQQ or QQQ_TO_BIL)
- `account_mode=PAPER`, `order_type=MARKET`, `time_in_force`, `outside_rth=false`
- `broker_order_id`, `broker_execution_id`, `submitted_at_utc`, `fill_time_utc`
- `reference_open`, `fill_price`, `filled_quantity`, `remaining_quantity`, `fill_notional`
- `commission`, `exchange_fees`, `regulatory_fees`, `total_fees`
- `status`, `deviation_code`, `source_statement_id`

**Daily virtual NAV record**

- `date`, `virtual_cash`, `qqq_units`, `bil_units`, `qqq_mark`, `bil_mark`
- `qqq_value`, `bil_value`, `fees_to_date`, `nav`, `drawdown`
- data source/hash and a pointer to the supporting observation and fill records.

Records are append-only. Corrections must be new, linked records; never silently overwrite a previous signal, price snapshot, order intent, or fill.

## 5. IBKR Paper account interpretation and limitations

IBKR states that PaperTrader executions are simulated and do not execute on an exchange or settle at a clearing house. Its simulator uses real market prices and sizes but fills are simulated from the top of the book, without deep-book access. IBKR also documents differences in the handling of market orders and some order types.

Consequences for this protocol:

- Paper fills and commission reports are useful for operational rehearsal and a first execution-cost observation, but they are **not** live fills and cannot measure full market impact or guarantee the same execution in a funded account.
- Record the broker's reported fills and charges; do not replace them with assumed 1/3/5/10 bps.
- Keep a separate reference-open slippage calculation for each leg. For buys, adverse slippage is `(fill_price / reference_open - 1) * 10,000`; for sells, it is `(reference_open / fill_price - 1) * 10,000`. Store signed raw price differences as well so favorable executions are not discarded.
- Do not assume that a regular market order is an opening-auction fill. Preserve the actual timestamp and classify timing deviation.

Official IBKR references:
- [Paper Trading Account — IBKR Campus](https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/)
- [TWS PaperTrader — How it works and limitations](https://www.interactivebrokers.com/en/software/paperTrader2.php)

## 6. Data integrity and no-look-ahead controls

- Signal generation is permitted only after the relevant session's completed bars are available.
- SPY remains the sole session calendar. QQQ/BIL data must be explicitly joined to SPY sessions; never forward-fill or interpolate execution prices.
- Missing, non-finite, non-positive, stale, or not-yet-completed required bars fail closed. Do not create an order intent for an invalid observation.
- Archive immutable per-session input snapshots or immutable source objects and SHA-256 hashes. A later provider revision must not rewrite the original record.
- Retain the existing 2006 warm-up data for indicator calculation, but prospective portfolio/NAV observations begin only on the independently declared paper start date.
- Signal calculations and order intents must be reproducible from the saved inputs and the recorded code SHA.

## 7. Evaluation gates appropriate to a low-frequency strategy

The corrected historical sample contains 32 completed trades over approximately 19.4 years, or about 1.65 completed trades per year. A 40-trading-day counter designed for a daily multi-stock scanner would therefore be misleading.

Use two separate review concepts:

### Operational review

- Review no earlier than 12 calendar months after the first valid prospective observation.
- Require at least 5 completed round trips before judging the order/ledger workflow; otherwise label the result `INSUFFICIENT_SAMPLE` and continue observing.
- Every signal day, including zero-signal days, must be accounted for.
- Every submitted order must be reconciled to broker execution evidence; no fabricated Open fills, unexplained missing legs, or overwritten records.
- Operational review does not establish alpha and does not authorize live trading.

### Statistical review

- Do not label the strategy independently validated based on a small paper sample.
- A checkpoint at 20 completed round trips is only a trigger for a deeper review, not an automatic pass. Assess uncertainty around net excess return versus BIL, trade-level dependence, actual paper execution costs, drawdown, and the predeclared 15% historical risk objective.
- The historical event rate implies that collecting 20 prospective round trips could take many years. If the sample remains inadequate, the correct result is `INSUFFICIENT_SAMPLE`, not a relaxed rule or a shorter observation window.
- No threshold or strategy parameter may be changed during the prospective period. Any change requires a new version, a new fingerprint, and a new observation cohort.

### Risk and stop conditions

- If virtual NAV drawdown reaches or exceeds 15% from its high-water mark, pause new paper entries and flag a manual research review. Do not silently add a stop to an existing trade; any open trade follows the frozen exit rule unless a separate safety decision is explicitly documented.
- Stop the run on any data-integrity failure, missing execution evidence, duplicate signal/order ID, unexpected overlapping position, or live-account mode detection.
- No paper result, including a positive one, automatically enables live trading.

## 8. Isolation and activation checklist

Before any prospective run begins, a separate implementation review must prove:

- [ ] Dedicated files/paths for QQQ observations, QQQ order intents, QQQ fills, and QQQ daily NAV.
- [ ] No reads/writes to `portfolio_paper_transactions.csv`, `portfolio_50000_*`, or production trading ledgers.
- [ ] Explicit Paper account mode; no live credentials or secrets in GitHub.
- [ ] No automatic order submission from GitHub Actions. An operator must verify Paper mode and submit/confirm the paper orders.
- [ ] Idempotent daily signal generation and unique signal/trade/order IDs.
- [ ] Unit tests for first-next-session entry, five-further-session exit, overlaps, no-signal days, missing prices, delayed/partial/unfilled orders, duplicate events, and statement reconciliation.
- [ ] Dry-run validation with synthetic data before the first prospective signal.
- [ ] A dated freeze record for this protocol, code SHA, input source, sizing, order type, and paper account configuration.

Until every item is implemented and reviewed, the strategy remains **NOT ACTIVE FOR PAPER EXECUTION**. This document alone does not start the observation clock.
