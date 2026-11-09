# P10.1 Non-Price Information PIT Availability Audit

Date: 2026-11-09
Status: **P10_1_PIT_DATA_PARTIAL**

This is a source audit, not a strategy backtest.

## 1. Probe results

Sample: AAPL, CIK 0000320193.

- SEC `submissions` JSON: HTTP 200; 1,006 recent filings returned; both
  `filingDate` and `acceptanceDateTime` present; 10-K, 10-Q, 8-K metadata
  available.
- SEC `companyfacts` JSON: HTTP 200; 25,604 fact rows; filed dates range
  2009-07-22..2026-11-06; accession numbers present.
- SEC `companyfacts` is a current aggregate. It can contain amended/latest
  facts; it is not a complete as-filed historical snapshot.
- ALFRED vintage endpoint timed out in this environment.
- No free historical analyst-consensus snapshot was verified.
- No free news archive with reliable first-publication timestamps was verified.

## 2. Source audit

| Source | PIT availability | Status |
|---|---|---|
| SEC submissions / filing metadata | filingDate + acceptanceDateTime | PIT_VERIFIED_SAMPLE |
| SEC Company Facts / XBRL | filed date + accession; current aggregate | PARTIAL |
| SEC 10-K/10-Q as-filed | accession-level parser not built | PARTIAL |
| SEC 8-K events | filing timestamps; content extraction missing | PARTIAL |
| Analyst consensus / EPS surprise | no free PIT snapshot | DATA_BLOCKED |
| News first publication | no verified archive | DATA_BLOCKED |
| Macro ALFRED vintages | endpoint timed out / no vintage key | DATA_BLOCKED |
| ETF corporate actions / dividends | vendor actions only | PARTIAL |

Full table:

- [source_audit.csv](data/research/p10_1_pit_sources/source_audit.csv)
- [coverage_by_source.csv](data/research/p10_1_pit_sources/coverage_by_source.csv)
- [probe_results.json](data/research/p10_1_pit_sources/probe_results.json)

## 3. Quality gates

```text
DATA_AVAILABLE:       SEC submissions, Company Facts, ETF actions
PIT_VERIFIED:         SEC submissions metadata (sample)
COVERAGE_VERIFIED:    none
STRATEGY_READY:       none
```

No source is `STRATEGY_READY` for a 2000-2024 cross-sectional strategy.

## 4. What can be researched next

1. **Actual reported financial changes** from accession-level SEC filings:
   revenue, earnings, cash flow, assets, shares outstanding. Do not call this
   “EPS surprise” without a historical consensus snapshot.
2. **8-K event dates** using `acceptanceDateTime`; content taxonomy and
   materiality mapping must be built and audited first.
3. **Macro vintages** only after ALFRED/FRED vintage access is validated; current
   FRED levels are not historical vintages.
4. **News** only as non-PIT exploratory data until first-publication timestamps
   are proven.

## 5. What is blocked

- Historical analyst consensus and revisions.
- Historical EPS surprise.
- News first-publication archive.
- ALFRED macro vintages in this environment.
- Full historical as-filed XBRL coverage (2000-2008, amendments, restatements).

## 6. Decision

```text
P10_1_PIT_DATA_PARTIAL
STRATEGY_READY = NONE
```

Do not start a fundamental/news/macro strategy yet. The next step is a bounded
accession-level SEC pilot on the historical S&P universe, with coverage and
as-filed timestamp validation, not another round of price-only formulas.

## 7. Files

```text
data/research/p10_1_pit_sources/
  source_audit.csv
  coverage_by_source.csv
  probe_results.json
  p10_1_status.json
docs/research/p10_1_pit_sources.md
```
