# Multi-Style Investment Platform — Phase 1 Architecture

Date: 2026-11-04
Branch: `research/multi-style-investment-platform`
Status: Phase 1 design only; no production code changed.

## 1. Existing system (read-only)

```text
scan.py / review.py / evolve.py / option engine
  -> CSV / JSON
  -> dashboard_export.py
  -> dashboard/data/dashboard_data.json
  -> index.html + app.js + app.css
```

These remain untouched. The new platform writes only under its own namespace:

```text
tools/paper_trading/
tools/investment_research/
tools/portfolio/
data/paper_trading/
docs/research/multi_style_platform/
```

No new module imports `scan.py`, `review.py`, `evolve.py`, or any broker
execution module. No browser code calls an LLM or computes production
recommendations.

## 2. Product modules

| Page | Backend source | Phase |
|---|---|---|
| Overview | account + portfolio snapshot | 2 |
| Stock Screener | SEC fundamentals snapshot | 3 |
| Stock Analysis | per-style analyzer | 3-4 |
| Value / Quality / GARP | fundamental analyzers | 3 |
| Trend Following | daily OHLCV analyzer | 4 |
| Dividend | fundamentals + verified actions | 4 |
| Macro & Hedging | ETF prices + risk | 4 |
| Paper Trading | proposal/confirm engine | 2 |
| Portfolio | valuation + risk | 2 |
| Trade History | immutable ledger | 2 |
| Strategy Comparison | tagged-account snapshots | 6 |
| Research & Risk | audit/data provenance | 2-6 |

## 3. Account model

One account only:

```text
account_id = PAPER-50000
initial_cash = 50000.00 USD
account_type = PAPER
real_trading = false
```

No strategy gets its own cash. Strategies only tag intents and positions. Every
order reserves the same cash pool.

State:

```text
account_state.json   cash, positions, realized_pnl, fees, nav
orders.json          proposals and terminal states
ledger.jsonl         append-only fills, dividends, splits, fees
daily_nav.csv        date, cash, positions_value, nav
```

`account_state.json` is replaced atomically (`temp + os.replace`). The ledger is
append-only and never rewritten.

## 4. Order lifecycle

```text
research signal
  -> proposed order (PENDING, confirmation token)
  -> user confirms
  -> validation (integer shares, cash, position, price timestamp)
  -> simulated fill at supplied reference price +/- slippage
  -> cash/positions update
  -> immutable ledger
```

Rules:

- AI cannot call `confirm` or `execute` directly.
- A proposal expires; only `PENDING` can be cancelled.
- Duplicate `client_order_id` is rejected idempotently.
- No short selling, no margin, no negative cash.
- Buy price = reference × (1 + slippage); sell = reference × (1 − slippage).
- Reference price and simulated fill are stored separately.
- Missing/stale price fails closed.
- Commission and regulatory fees use `tools/paper_trading/ibkr_costs.py`
  (`forward_estimate` for paper; `historical_backtest` only for historical
  studies).

## 5. Fundamental research contract

Every metric result:

```json
{
  "ticker": "AAPL",
  "metric": "pe_ttm",
  "value": 28.4,
  "status": "OK",
  "observation_date": "2026-09-30",
  "available_at": "2026-10-30T20:05:00Z",
  "source": "SEC companyfacts",
  "form": "10-K",
  "accession": "000...",
  "license_status": "public_sec",
  "missing_reason": null
}
```

- `null` stays null; never replaced by 0.
- Negative earnings / negative book value produce `NOT_APPLICABLE`, not fake
  multiples.
- Cyclical industry flag changes interpretation, not the formula.
- No forward estimates are presented as historical facts.
- Intrinsic value is a range with explicit assumptions, not a point target.
- SEC `filed` timestamp is the availability gate; amended filings are separate
  versions.

## 6. Style modules (pre-registration required)

VALUE, QUALITY, GARP, TREND, DIVIDEND, HEDGE each have:

```text
universe.json
rules.md
signal.py
```

Frozen before evaluation: universe, metrics, ranking, buy/sell, rebalance,
position sizing, risk, costs. Failed variants remain in the registry.

Trend is a new independent implementation. The frozen A/B/C and Transition
NO-GO results are not evidence for it.

Dividend simulation uses only verified ex-dates and amounts. Unverified actions
are excluded and reported.

Hedge research evaluates cost, carry, correlation change and inverse-ETF daily
reset; it is not a naive "buy SH when market falls" rule.

## 7. Data layer

Allowed for Phase 3:

- SEC submissions / companyfacts / XBRL, public and timestamped;
- exchange/issuer corporate-action documents;
- licensed or user-supplied OHLCV with provenance.

Not allowed:

- FMP/FINSABER as a production source while its upstream licence is unresolved;
- Yahoo as an "independent" source;
- month-end index holdings as daily membership;
- forward-filled or interpolated prices.

Every record has `source`, `fetched_at`, `observation_date`, `available_at`,
`sha256`, `license_status`, `missing_reason`.

## 8. Phase gates

1. Phase 1: this design only.
2. Phase 2: one $50k paper account, orders, ledger, costs, NAV, tests.
3. Phase 3: Value/Quality/GARP on SEC data.
4. Phase 4: Trend/Dividend/Hedge.
5. Phase 5: pages, only wired to real backend endpoints.
6. Phase 6: combined analysis/comparison.
7. Phase 7: forward paper trading with frozen data snapshots.

No page button may be enabled before its backend path exists. No static fake
data. No production scan/trade imports. No broker connection.
