# Invest Terminal v1 — Implementation Status

Date: 2026-11-06
Branch: `research/invest-terminal-v1`
Mode: research + paper only

## Delivered in this branch

- Integrated `terminal.html` with six primary sections:
  Daily Dashboard, Stock Research, Strategy Lab, Paper Portfolio, Risk Center,
  Performance & Review.
- Six frozen strategy definitions with explicit universe, selection, entry, exit,
  rebalance, sizing, risk, cost and evidence.
- Independent benchmark registry: SPY, QQQ, BIL, EQUAL_WEIGHT. They are not
  treated as investment styles.
- PAPER-50000 read model: account, cash, NAV, positions, orders, ledger.
- Optional local API for manual proposal/confirmation using the existing paper
  engine; no broker path and no auto-confirm.
- Risk Center: cash/position concentration, missing prices, drawdown/volatility
  when history exists, and current-exposure stress.
- Performance: no NAV history means no fabricated curve; benchmark gaps are
  explicit.
- Reuse audit and safety invariants in `invest_terminal_v1_reuse_audit.md`.

## What is intentionally blocked

All six strategies are `DATA_BLOCKED`. No strategy is `PASS`:

- Value: share-class/ADR and PIT-validated returns incomplete.
- Quality: P6.7 strict PIT gate failed.
- GARP: no free forward EPS/consensus.
- Trend: PIT price coverage below gate.
- Dividend: no complete free full-market event source.
- Macro/Hedge: no historical option chain/borrow/financing.

This is a platform-quality result, not a failure to find a pretty backtest.

## Local use

Generate the read-only snapshot:

```bash
python -m tools.invest_terminal.build_snapshot
```

Open `terminal.html` from the repository root. For manual paper trading:

```bash
python -m tools.invest_terminal.server
# open terminal.html?api=http://127.0.0.1:8765
```

The server binds only `127.0.0.1`, uses the existing `paper.sqlite`, and requires
an explicit confirmation token. Static GitHub Pages remains read-only.

## Safety checks

- One PAPER-50000 account; no US-50000-001 merge.
- No margin, shorting or negative cash.
- Stale/future quote rejection in the existing engine.
- IBKR Pro Tiered forward cost model reused.
- New package does not import production scan/review/evolve or broker APIs.
- `index.html` only gains a link; existing Dashboard code is untouched.

## Next-stage gates

A strategy can move to PASS only with a separately frozen, documented validation
and a clean PIT dataset. Until then the UI must keep `DATA_BLOCKED` and must not
show synthetic Sharpe, CAGR, drawdown or strategy attribution.
