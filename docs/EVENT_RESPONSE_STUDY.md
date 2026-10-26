 # Event Response Study: Research-Only Method

This tool reports what supplied daily prices did after the collector first observed the earliest valid version of an event. It is descriptive, not a strategy or proof of causal alpha.

## Input format

Supply a frozen JSON array of normalized events/versioned archive records and a price CSV with these columns:

    date,ticker,open,close
    2026-10-23,SPY,100.00,101.25
    2026-10-23,AAPL,250.00,252.00

The loader supports `--price-basis auto|adjusted|raw` (default `auto`). If the CSV contains Adj Open and Adj Close, it uses those. If only Adj Close is present alongside raw Open and Close, it derives same-session adjusted Open as `Open * Adj Close / Close`. Missing adjustment values are skipped rather than silently falling back to raw prices. If no adjusted fields exist, `auto` uses raw OHLC and records that basis in the report; pass `--price-basis adjusted` to require adjusted fields. The script does not download prices. For the repository's `research_price_history_sp500_10y.csv`, the `auto` mode uses its Adj Close and derives Adj Open consistently. For `quant_factor_price_history.csv`, which has raw OHLCV only, the report will mark raw price basis.

## Manual run

    python -m tools.research.pit_event_response_study --events event_archive.json --prices-csv daily_prices.csv --price-basis auto --study-end-date 2026-10-23 --horizons 1,5,10 --round-trip-cost-bps 5 --max-age-days-by-type '{"macro_release":2,"policy":3,"central_bank":3,"company_news":2,"earnings":3}' --report event_response_report.json --observations-csv event_response_observations.csv

The report includes event-level observations, family-level mean and median gross returns, win rates, assumed cost-adjusted returns, source-delay minutes, snapshot hashes, and explicit skip counts. Horizon N counts the entry session as session one. A 1-session return is entry Open to that session Close.

## Anti-lookahead rules

- Only the earliest valid version per event ID is used. Later revisions are excluded; the study never projects revised content backward.
- Events must be marked available and have timezone-aware publication and first-seen timestamps, with publication no later than first-seen. Optional freshness limits exclude stale records.
- If first seen before 09:30 New York time, an event may use that session's Open. If first seen at or after 09:30, entry is no earlier than the next available session's Open.
- Market-wide macro_release, central_bank, policy and geopolitical events without ticker mapping use SPY as a broad-market proxy. Company news and earnings require explicit ticker mappings.
- A ticker-specific aggregator RSS request is not enough to verify company relevance: Yahoo Finance ticker queries can include headlines unrelated to the requested symbol. Such records carry `ticker_mapping_status=unverified_query_scope` and are skipped until the mapping is explicitly verified or human-reviewed.
- Overlapping windows are not independent. The script does not infer sentiment, estimate significance, test causal alpha, or generate a buy/sell signal.

## Interpretation limit

The event is anchored to the time this collector first observed it, which may be later than the publisher timestamp or the instant the item first became public. Therefore this measures returns after system observation, not necessarily the original market reaction. Historical backfill cannot reconstruct an unrecorded historical first-seen time. Verify coverage before any walk-forward strategy evaluation.
