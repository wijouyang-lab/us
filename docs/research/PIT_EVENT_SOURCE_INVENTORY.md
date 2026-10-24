# Free official event-source inventory

This inventory separates sources already implemented in the research collector from sources that still require an adapter. A source being listed here does not mean its history is point-in-time complete or that its contents are already captured.

## Implemented adapters

| Event family | Source | Current collector key | Important limitation |
|---|---|---|---|
| CPI/core CPI releases | U.S. Bureau of Labor Statistics | `bls_cpi` | RSS endpoint returned HTTP 403 from GitHub Actions during capture; current CPI values are captured separately via the public API, but release surprises and historical vintages are not reconstructed |
| PCE/core PCE, GDP, personal income/outlays and other BEA releases | U.S. Bureau of Economic Analysis | `bea_releases` | Official release RSS is now collected; parsed publication time is not a vintage data history or a consensus snapshot |
| Employment/unemployment releases | U.S. Bureau of Labor Statistics | `bls_employment` | RSS endpoint returned HTTP 403 from GitHub Actions during capture; current employment/unemployment values are captured separately via the public API, but release surprises and historical vintages are not reconstructed |
| Central-bank releases and policy | Federal Reserve press feed | `fed_all` | Broad press feed; classification is based on title/description terms and should be reviewed |
| Fed speeches/testimony | Federal Reserve | `fed_speeches` | Captures official feed items, not every live remark or transcript revision |
| Treasury auction announcements and results | TreasuryDirect official RSS | `treasury_auction_announcements`, `treasury_auction_results` | Captures announcement/result headlines and source timestamps; does not itself parse auction bid-to-cover, tail, or yield statistics |
| Current CPI, core CPI, payrolls, unemployment and hourly earnings values | BLS public API v2 | `tools/research/bls_macro_series_capture.py` + `tools/research/build_bls_macro_panel.py` | Current snapshots can be aligned to decisions only after retrieval; revisions are not reconstructed, and no consensus surprises are included |
| Daily Treasury nominal and real par yield curves | U.S. Treasury official XML feeds | `tools/research/treasury_yield_curve_capture.py` (`--curve-type nominal` or `real`) | Produces maturity yields and nominal spreads/daily changes; real yields cover 5y–30y. Current historical downloads do not reconstruct historical first-seen times and are not PIT-eligible before retrieval |
| Nominal-minus-real inflation-compensation proxy | Derived from paired Treasury snapshots | `tools/research/treasury_breakeven_proxy.py` | Joins matched dates without interpolation; proxy can include inflation-risk/liquidity premia and is usable only after both snapshots were actually retrieved |
| Company filings / earnings-related disclosures | SEC EDGAR submissions and filing headers | `tools/research/sec_event_collector.py` with `build_sec_research_universe.py` | Live SEC endpoints may return 403 from GitHub-hosted runners. Collector metadata now reports per-error-type and HTTP-status counts plus bounded per-event error details; this diagnoses the block but does not bypass it. The capture workflow has an explicit static CIK fallback for the current 20-symbol watchlist. Unlisted tickers remain unmatched. Filing events are not verified earnings beat/miss or guidance surprises; current capture does not reconstruct historical first-seen |

## Required next adapters / data work

| Event family | Preferred free source | Current status in this research collector |
|---|---|---|
| Macro release vintages and consensus snapshots | BEA release/vintage data plus timestamped consensus source | Official BEA RSS headlines are collected; historical vintages and pre-release consensus snapshots are not integrated |
| Structured Treasury auction surprise metrics | TreasuryDirect auction result data | RSS headlines are captured; bid-to-cover, tail, and comparable surprise fields are not yet normalized |
| FOMC decision calendar, statements, minutes and voting-official communications | Federal Reserve official releases and calendars | Partially represented by Fed press/speeches feeds; event-specific parsing and coverage checks remain |
| Company earnings release, guidance and consensus surprise | Company investor-relations releases plus a source with timestamped consensus snapshots | An exploratory yfinance EPS-surprise recon exists, but historical first-seen and consensus provenance are not validated; do not treat it as a PIT factor or production-ready evidence |
| Market-wide / sector headlines and policy/person events | Official agency sources and vetted public feeds | Partial coverage only; source inventory and coverage must be expanded before claiming broad coverage |

## Collection and evaluation controls

- Every captured event version must preserve source URL, publication timestamp when available, actual collector first-seen timestamp, source/event identity, content hash, and source quality.
- A missing publication timestamp, missing source URL, or invalid time ordering must remain visible as a data-quality rejection; do not infer a timestamp from the event title or the market move.
- An official source's current archive can establish that an announcement exists, but does not automatically establish the exact historical time at which a simulated system could have observed it.
- For revised economic series, use release/vintage history where available. Do not substitute today's revised value for the value known at the historical decision time.
- Store expected-vs-actual or beat/miss fields only when both the actual value and the consensus snapshot, including its as-of timestamp and source, are verifiable.
- A successful HTTP fetch is source availability, not proof of complete coverage. Report empty feeds, partial sources, parse failures, and source-specific event counts separately.
- Do not connect this research capture to the production scanner or external trigger until explicit data-quality and out-of-sample gates are met.

## Operational command

The existing manual collector supports BLS CPI, BLS employment, BEA news releases, Fed press and speeches, plus TreasuryDirect auction announcements and results by default. Daily Treasury yield curve values can be captured separately with `tools.research.treasury_yield_curve_capture`; that command is manual and creates an immutable JSON snapshot. SEC collection uses an explicit CIK/ticker universe plus a contact-bearing SEC User-Agent. The workflow attempts the live SEC mapping first and uses a pinned, limited CIK fallback only if that request fails; update and verify the fallback when the watchlist changes. It creates no scheduled workflow:

```bash
python -m tools.research.run_event_capture_cycle \
  --output-dir data/research/captures \
  --decision-at 2026-10-23T13:00:00Z \
  --feeds bls_cpi,bls_employment,bea_releases,fed_all,fed_speeches,treasury_auction_announcements,treasury_auction_results
```

Replace the example decision time with the actual timezone-aware cutoff for the run. Do not use an example timestamp as if it were the current time. A run with no reviewed labels is expected to remain blocked from empirical scoring; do not loosen the gate to make the report green.
