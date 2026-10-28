# SPY Market Proxy and Readiness

Date: 2026-10-28
Research only. No production changes.

## SPY data

Separate proxy file:

`docs/research/market_proxy_spy_2026-10-28.csv`

Metadata:

`docs/research/market_proxy_spy_metadata_2026-10-28.json`

| Metric | Value |
|---|---:|
| Ticker | SPY |
| Rows | 2,541 |
| Date range | 2016-09-19 to 2026-10-27 |
| Duplicates | 0 |
| Invalid OHLCV | 0 |
| Adjusted close available | **yes** |
| Source | Yahoo chart via yfinance |
| Fetched at | 2026-10-28T10:01:14Z |

SPY is stored separately and is **not** treated as a 503-panel stock signal.

## Price basis

- `raw OHLCV`: unadjusted close.
- `Adj Close`: provider-adjusted close; used only with the proxy and labeled.
- `total return`: not claimed unless dividends are reinvested and verified.
- Splits/dividends: provider adjustment exists for SPY, but corporate-action
  reconciliation is not independently audited.

The 503-stock panel remains raw OHLCV without adjusted close.

## Readiness with SPY

Command:

```bash
python -m tools.research.event_post_bar_readiness \
  --events <archive events> \
  --price-panel <updated panel> \
  --market-proxy SPY \
  --market-proxy-file research_market_proxy_spy.csv \
  --market-proxy-adjusted \
  --as-of 2026-10-28T10:00:00Z
```

Actual:

| Status | Count |
|---|---:|
| `ready` | **0** |
| `pending_future_bar` | **35** |
| `excluded` | **0** |
| publication-forward candidates | 35 |
| look-ahead flags | 0 |

Reasons in explicit `market_proxy_spy` mode:

```text
pending_future_entry_bar
```

The proxy uses provider `Adj_Close` (`provider_adjustment_only`). Stock-mode
raw/unverified price-basis reasons are reported separately and are not applied
to the market-proxy mode.

The SPY proxy is available through 2026-10-27. Events were first seen
2026-10-28, and the 2026-10-28 close is not yet available. No same-day or
earlier close was used.

## 2026-10-28 close

Current UTC at check time: 2026-10-28T10:00Z. US market has not closed.
No 2026-10-28 bar was appended.

This is a **future-bar pending** condition, not missing historical data.

## Files

- `tools/research/fetch_market_proxy.py`
- `tests/test_fetch_market_proxy.py`
- `docs/research/market_proxy_spy_2026-10-28.csv`
- `docs/research/market_proxy_spy_metadata_2026-10-28.json`
- `docs/research/event_post_bar_readiness_spy_2026-10-28.json`

## Boundary

No event alpha test was run. SPY is a market proxy, not a stock alpha result.
