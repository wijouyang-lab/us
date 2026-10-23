# Free official event-source inventory

This inventory separates sources already implemented in the research collector from sources that still require an adapter. A source being listed here does not mean its history is point-in-time complete or that its contents are already captured.

## Implemented adapters

| Event family | Source | Current collector key | Important limitation |
|---|---|---|---|
| CPI/core CPI releases | U.S. Bureau of Labor Statistics | `bls_cpi` | RSS publication time and retrieval time are distinct; historical first-seen is not reconstructed |
| PCE/core PCE, GDP, personal income/outlays and other BEA releases | U.S. Bureau of Economic Analysis | `bea_releases` | Official release RSS is now collected; parsed publication time is not a vintage data history or a consensus snapshot |
| Employment/unemployment releases | U.S. Bureau of Labor Statistics | `bls_employment` | RSS is a rolling feed, not a complete historical event archive |
| Central-bank releases and policy | Federal Reserve press feed | `fed_all` | Broad press feed; classification is based on title/description terms and should be reviewed |
| Fed speeches/testimony | Federal Reserve | `fed_speeches` | Captures official feed items, not every live remark or transcript revision |
| Company filings / earnings-related disclosures | SEC EDGAR submissions and filing headers | optional SEC universe in `run_event_capture_cycle.py` | Filing events are not equivalent to verified earnings beat/miss or guidance surprise; a current backfill does not reconstruct historical first-seen |

## Required next adapters / data work

| Event family | Preferred free source | Current status in this research collector |
|---|---|---|
| PCE/core PCE, personal income/outlays, GDP | BEA official news releases and release schedule | Not yet implemented as a collector adapter |
| Treasury announcements, auction results, policy statements | U.S. Treasury official releases | Not yet implemented as a collector adapter |
| FOMC decision calendar, statements, minutes and voting-official communications | Federal Reserve official releases and calendars | Partially represented by Fed press/speeches feeds; event-specific parsing and coverage checks remain |
| Company earnings release, guidance and consensus surprise | Company investor-relations releases plus a source with timestamped consensus snapshots | Not yet implemented as a verified beat/miss pipeline |
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

The existing manual collector supports BLS CPI, BLS employment, BEA news releases, Fed press, and Fed speeches by default. SEC collection is optional and requires an explicit CIK/ticker universe plus a contact-bearing SEC User-Agent. It creates no scheduled workflow:

```bash
python -m tools.research.run_event_capture_cycle \
  --output-dir data/research/captures \
  --decision-at 2026-10-23T13:00:00Z \
  --feeds bls_cpi,bls_employment,fed_all,fed_speeches
```

Replace the example decision time with the actual timezone-aware cutoff for the run. Do not use an example timestamp as if it were the current time. A run with no reviewed labels is expected to remain blocked from empirical scoring; do not loosen the gate to make the report green.
