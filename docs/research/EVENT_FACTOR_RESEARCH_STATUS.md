# Event-factor research status and completion gates

**Snapshot as of 2026-10-24 10:38 UTC.** This is a research status report, not an alpha claim. It must be refreshed after new captures or evaluation runs.

## Current evidence

| Area | Observed state | Interpretation |
|---|---|---|
| Archived event versions | 86 unique versions | Early prospective archive, not a historical training set |
| Event families | 51 macro releases, 18 central-bank items, 17 policy items | Fed/BEA coverage exists; coverage is not complete |
| Sources in archive | BEA RSS 49, Fed press 20, Fed speeches 15, Treasury auction announcement 1, Treasury auction result 1 | BLS RSS endpoints return HTTP 403 from GitHub-hosted runners; BLS values are captured separately through the public API |
| Reviewed labels | 0 of 86 | No event factor score may be treated as empirically validated |
| Ticker-linked events | 0 | Current event archive is mostly market-wide; it cannot yet evaluate company-specific news or earnings |
| SEC mapping | Static fallback mapped all 20 current watchlist symbols to CIKs | Mapping succeeded, but is not a live universe snapshot and must be reviewed when watchlist changes |
| SEC filing retrieval | 20 of 20 submissions requests returned HTTP 403 from GitHub-hosted runners | Company filings/earnings coverage remains blocked despite successful CIK mapping |
| Treasury curve data | 204 matched nominal/real dates and 204 derived inflation-compensation proxy rows | The historical observation dates do not prove historical availability; these rows are usable only at/after the actual snapshot retrieval timestamp |
| Empirical event-factor result | Not established | No validated label set and no qualifying event-factor out-of-sample result are available |

Evidence links:
- [Latest capture readiness report](../data/research/event-capture/event_capture_20261024T103806501408Z.readiness.json)
- [Latest capture metadata and source coverage](../data/research/event-capture/event_capture_20261024T103806501408Z.metadata.json)
- [Latest SEC mapping provenance](../data/research/event-capture/sec_universe_40086652063.metadata.json)
- [Latest derived Treasury proxy](../data/research/event-capture/treasury_breakeven_proxy_40086652063.json)
- [Source inventory](PIT_EVENT_SOURCE_INVENTORY.md)
- [Annotation guide](PIT_EVENT_LABEL_ANNOTATION_GUIDE.md)

## Completion gates

The research is **not complete** until all applicable gates below have evidence. A failed or null result is an acceptable scientific conclusion; unsupported claims of alpha are not.

1. **Source coverage:** company-specific news/filing collection works or a clearly documented alternative is implemented; all source failures and coverage counts remain visible.
2. **Point-in-time archive:** genuine prospective first-seen timestamps, unique event versions, valid source URLs, no imputed labels, and a point-in-time universe are available.
3. **Label review:** direction and impact annotations have a documented rubric, reviewer/provenance fields, and real review timestamps. Pending AI suggestions or numeric labels without review do not pass this gate.
4. **Evaluation panel:** event scores, price data, and decision timestamps are aligned without look-ahead; missing event coverage remains missing; delisted names and universe membership are handled without survivorship bias.
5. **Frozen evaluation:** chronological train/validation/test blocks, horizon purge, cost model, event-vs-price-only baseline, common-universe ablation, and predeclared sensitivity tests run on the same documented sample.
6. **Conclusion:** report sample sizes, source coverage, turnover, costs, drawdown, uncertainty intervals, and limitations. The conclusion may be positive, null, or inconclusive. Do not activate production merely because tests pass.

## Safety boundary

All additions remain research-only. The production scanner, ranking, external premarket trigger, portfolio construction, holdings ledger, and trading logic are unchanged. No research output is permission to trade live.
