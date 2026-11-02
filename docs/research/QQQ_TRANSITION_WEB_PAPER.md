# QQQ TRANSITION Web Paper Account

Date: 2026-11-02
Status: SIMULATED historical replay; no broker connection; no prospective clock.

## 1. Purpose

An independent $50,000 web-simulated account for the frozen QQQ TRANSITION
five-session reversal candidate. It is **not** Portfolio-50000, **not**
`portfolio_paper_transactions.csv`, and **not** an IBKR Paper fill record.

Every fill is marked:

```text
status = SIMULATED
execution_mode = HISTORICAL_REPLAY
```

The account is deterministic and rebuilt from committed QQQ/SPY/BIL inputs.

## 2. Frozen protocol

- Initial capital: $50,000.
- QQQ strategy sleeve: 25% ($12,500).
- BIL: idle strategy cash and 75% reserve.
- Signal: QQQ 5-session return <= 5th percentile of the prior 252 completed
  5-session returns; threshold shifted one session.
- Regime: SPY TRANSITION only.
- SPY is the sole trading calendar.
- Entry: next SPY session Open.
- Exit: Open after five further SPY sessions.
- One position maximum; overlapping signals skipped and recorded.
- Long only; no leverage.
- Cost: 10 bps per leg on BIL sell, QQQ buy, QQQ sell, BIL buy.
- No RSI, ATR, stop, or additional filters.

## 3. Implementation

`scripts/qqq_transition_paper.py`

Outputs:

```text
qqq_transition_paper/ledger.json
qqq_transition_paper/daily_nav.csv
qqq_transition_paper/fills.csv
qqq_transition_paper/signals.csv
dashboard/data/qqq_transition_paper.json
```

The ledger records:

- initial capital, sleeve fraction, cost;
- current NAV, cash, QQQ units, BIL units;
- every simulated fill leg, price, quantity, notional and cost;
- every signal, planned entry, entry/exit status;
- daily NAV, QQQ/BIL values and zero-signal days;
- max drawdown, total cost, trade count;
- strategy fingerprint, engine version, and QQQ/SPY/BIL SHA-256 hashes.

No forward-fill or interpolation of execution prices. Missing/non-finite/non-positive
prices fail closed.

## 4. Current simulated result

Historical replay start: 2007-05-30; data as-of 2026-10-30.

| Metric | Value |
|---|---:|
| Initial capital | $50,000.00 |
| Simulated NAV | $71,489.52 |
| Cumulative return | +42.98% |
| Max drawdown | -6.37% |
| Cash | $0.00 |
| QQQ units | 0 |
| BIL units | 779.60 |
| Current weight | 0% |
| Status | BIL |
| Trades | 32 |
| Fills | 128 |
| Signals | 81 |
| Skipped overlaps | 49 |
| Total cost | $1,901.21 |

This is a **historical replay**, not a prospective paper-trading record. It must not
be presented as live/forward evidence.

## 5. Web integration

- Root `index.html` has an independent `qqqPaperSec` panel after Portfolio-50000.
- `app.js` fetches `dashboard/data/qqq_transition_paper.json` separately.
- The panel is visually separate (purple left border and `SIMULATED` badge).
- The panel shows initial capital, NAV, return, cash, QQQ, BIL, weight, status,
  cost, max drawdown, data as-of, recent fills and recent signals.
- The browser never generates signals or fills.

Local verification:

```bash
python -m http.server 8765
# http://127.0.0.1:8765/
```

## 6. Isolation

The implementation does not read or write:

- `portfolio_50000_positions.csv`
- `portfolio_50000_transactions.csv`
- `trade_history.csv`
- `portfolio_paper_transactions.csv`
- production Scan/Review/ATR/order paths.

## 7. Workflow

`.github/workflows/qqq-transition-web-paper.yml`

- Weekdays 21:45 UTC (after US close in DST and standard time).
- Manual dispatch supported.
- Rebuilds the deterministic simulated ledger.
- Commits only `qqq_transition_paper/` and
  `dashboard/data/qqq_transition_paper.json`.
- Does not modify `paper-trading.yml`.
- No IBKR connection, no order transmission.
- If the next Open is missing, the account remains in a pending state rather than
  fabricating a fill.

## 8. Tests

`tests/test_qqq_transition_paper.py`: 9 passed.

- complete four-leg entry/exit;
- 25% initial sleeve;
- cost 10 bps per leg, charged once;
- exit exactly five SPY sessions after entry;
- daily NAV/cash/unit consistency;
- idempotent rebuild;
- missing/invalid price fail-closed;
- dashboard contract;
- independent panel and Portfolio-50000 isolation.

Static dashboard tests remain green (runtime 19/19; data stability 34/34).
