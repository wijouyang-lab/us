# Invest Terminal v1 — Acceptance Evidence

Date: 2026-11-06
Branch: `research/invest-terminal-v1`
PR: #512 (Draft)
HEAD: `d1437717219829ef92d9a26dcf08e96148db978d`

## Acceptance checklist

| # | Requirement | Evidence | Result |
|---|---|---|---|
| 1 | Existing Dashboard remains functional | `index.html` only gains a link; full CI passes 1,417 tests | PASS |
| 2 | Six styles with explicit rules and status | `tools/invest_terminal/strategy_registry.py`; all six `DATA_BLOCKED` with reasons | PASS (honest block) |
| 3 | Benchmarks independent | SPY/QQQ/BIL/EQUAL_WEIGHT registry; not included in six styles; UI marks DATA_BLOCKED | PASS |
| 4 | PAPER-50000 cash/positions/NAV/orders | `build_snapshot.py` reads `paper.sqlite`; current account 50,000 USD, 0 positions, 0 orders | PASS |
| 5 | Manual confirmation | Local API test: propose PENDING, positions unchanged; confirm creates 1 share | PASS |
| 6 | Cost traceability | Existing IBKR Pro Tiered `ibkr_costs.py`; paper engine records fees | PASS |
| 7 | Risk/review real data | Risk derived from account cash/positions; no positions yields CASH_ONLY; no fake VaR | PASS (limited by empty portfolio) |
| 8 | Mobile layout | `terminal.css` 900px/560px breakpoints + viewport meta | PASS |
| 9 | No fabricated strategy performance | All styles DATA_BLOCKED; `nav_series=[]`; benchmark gaps explicit | PASS |
| 10 | Tests | Full CI 1,417 passed, 1 skipped; integration 28 tests | PASS |
| 11 | Production scan/review/evolve unaffected | New package does not import them; no production files changed except index link | PASS |

## End-to-end paper API demonstration

Run against a temporary SQLite account:

```text
propose PENDING True
positions before confirm []
confirmed 1 positions [{'ticker': 'AAPL', 'shares': 1, ...}]
```

This proves there is no auto-fill. The committed `data/paper_trading/paper.sqlite`
was not mutated: account still has 0 orders and 0 ledger rows.

## CI

- Full Test: https://github.com/wijouyang-lab/us/actions/runs/42168541451
- Terminal workflow: https://github.com/wijouyang-lab/us/actions/runs/42168541439
- Artifact: `invest-terminal-snapshot` (`13479727536`)

## Blocked, not hidden

- Full-market scanner: only one dashboard-tracked stock exists.
- Benchmark quotes: no current SPY/QQQ/BIL in dashboard snapshot.
- NAV history and strategy attribution: no ledger history.
- PIT validation: P6.7 gate remains 79.58%/69.77%, below 95%/98%.
- Dividend ticker DPS: only issuer-level cash proxy; 10 TTM CIKs.
- Options/macro hedge: no chain/IV/financing data.

These blocks are rendered as blocked states, not zeros or synthetic returns.
