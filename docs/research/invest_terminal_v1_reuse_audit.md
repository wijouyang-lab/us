# Invest Terminal v1 — Reuse Audit and Integration Architecture

Date: 2026-11-06
Branch: `research/invest-terminal-v1`
Status: implementation branch; existing PR #460 reused, production paths untouched.

## 1. Reuse classification

| Existing asset | Class | Decision |
|---|---|---|
| `index.html`, `app.js`, `app.css` | A | Keep as Classic Dashboard; add a link to the new terminal; do not rewrite production JS. |
| `dashboard_export.py` | A | Read its JSON output only. Do not modify production exporter. |
| `dashboard/data/dashboard_data.json` | A | Source for market assets, stocks, macro, news, review. |
| `strategy-lab.html` | B | Keep as legacy research page; six-style registry is new and does not replace its rules. |
| `scan.py` / `review.py` / `evolve.py` | A (read-only) | Never imported or modified. |
| `us_market_calendar.py` | B | Reuse available date/price freshness concepts; no new calendar engine in v1. |
| `scan_us_option_engine.py` | D/E | No new options research; options hedge remains blocked. |
| `tools/paper_trading/account.py` | A | Reuse PAPER-50000 state, lots, dividends/splits. |
| `tools/paper_trading/engine.py` | A | Reuse proposal/confirm/cancel/fill; no auto-confirm path. |
| `tools/paper_trading/ibkr_costs.py` | A | Reuse IBKR Pro Tiered forward estimate. |
| `tools/paper_trading/store.py` | A | SQLite authoritative ledger; page is read-only. |
| `tools/paper_trading/valuation.py` | A | Reuse NAV/performance functions where prices exist. |
| `tools/investment_research/sec/` | A | Reuse SEC client/industry; no new SEC ZIP download. |
| P6.4–P6.13 research | D | Do not repeat; registry cites conclusions and blocks. |
| `research_price_history` / PIT studies | E | P6.7 PIT gates failed; no prediction claims. |
| Broker execution / IBKR live path | E | Frozen; no connection, no real orders. |

## 2. New namespace

```text
terminal.html
terminal/terminal.css
terminal/terminal.js
tools/invest_terminal/strategy_registry.py
tools/invest_terminal/risk.py
tools/invest_terminal/build_snapshot.py
tools/invest_terminal/server.py
dashboard/data/invest_terminal_data.json
```

The new page reads a generated read-only JSON snapshot. The optional local API
binds `127.0.0.1` and uses the existing PAPER-50000 engine. It has no broker
connectivity and cannot auto-confirm.

## 3. Product modules

| Module | Data source | V1 behavior |
|---|---|---|
| Daily Dashboard | dashboard market/macro/news | Real current snapshot, explicit timestamps. |
| Stock Research | dashboard active stocks | Filters and per-stock detail. |
| Strategy Lab | frozen registry | Six styles + four separate benchmarks; no fake PASS. |
| Paper Portfolio | PAPER-50000 SQLite | Cash, NAV, positions, orders, ledger. |
| Risk Center | account + current quotes | Concentration, drawdown, missing-price warnings, stress. |
| Performance | account ledger | No history means no fabricated curve. |

## 4. Strategy status

All six styles are `DATA_BLOCKED` in v1. This is deliberate:

- no validated PIT return series;
- no free full-market dividend event source;
- no forward EPS for PEG;
- no options/hedge data;
- no ticker-level cash-dividend allocation.

The registry records rules and evidence so a future PASS requires a separate,
frozen validation—not a code change that silently promotes research.

## 5. Safety invariants

- One account only: `PAPER-50000`.
- No short selling, margin, negative cash or stale/future quote fill.
- Every fill needs an explicit confirmation token.
- SQLite is authoritative; the page is read-only.
- `US-50000-001` is not merged or reused.
- New code does not import `scan.py`, `review.py`, `evolve.py` or broker paths.
- Benchmarks are not styled as investment styles.


## v1.1 security addendum

- The optional paper API is now same-origin, loopback-only, session-authenticated
  and CSRF-protected; no wildcard CORS.
- Public snapshots are token-redacted; SQLite is no longer Git-tracked.
- Dashboard refresh builds the terminal snapshot in the existing main-only
  workflow, after success and before its [skip ci] commit.
