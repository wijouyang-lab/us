# Research Closure and Data-Readiness Gates

Date: 2026-10-29 (operational recheck)
Baseline: PR #399 `28060f24d907f0b0b75a323a6314084222a1077a`
Research only. No production changes.

## Frozen conclusion

Within the tested 466-ticker, current-universe, survivorship-biased panel:

- **No reliable alpha.**
- **No deployable strategy.**
- **No qualified paper-trading candidate.**
- 399-formula best positive: 3.1839% net, q=0.06687; still not significant.

This is a conclusion about the tested sample, **not proof that all future
low-frequency strategies are impossible**.

## Reopen gates

| Gate | Owner role | Verification | Current | Status |
|---|---|---|---|---|
| PIT universe + delisted OHLCV | research data owner (human) | PIT coverage + recovery gate | 91.61% member, 84.23% ticker, 0/98 delisted | **fail** |
| Independent adjusted prices/actions | research data owner (human) | independent adjusted source + action audit | 466 raw; SPY provider-only | **fail** |
| Qlib raw period results | strategy research owner (human) | committed per-period JSON + rerun | audit doc only | **fail** |
| Event pre-registered sample | event research owner (human) | `event_experiment_gate.py` | 35 events, 0 entry/+1/+5 | **not_eligible** |
| 10/28 official close | research operations owner (human) | provider close + incremental updater | 502/503 panel; HUBB close null; SPY 2,542 rows through 10/28 | **partial** |
| Second real cross-day capture | research operations owner (human) | workflow + archive verify | 2 runs; 40807180694 on 10/29; archive 420469c | **pass** |

Machine-readable:

`docs/research/RESEARCH_CLOSURE_DATA_READINESS_2026-10-28.json`

## Important distinctions

- **Data not ready does not mean the strategy is proven impossible.**
- **Qlib audit not independently rerun** 鈥?values are taken from the committed
  audit document; raw per-period JSON is missing.
- The event gate remains 35 unique events, 0 entry, 0 +1, and 0 +5; it is not an alpha finding.
- The 59-row capture has exactly the same 35 Fed event IDs plus 24 BLS rows. The BLS rows are not valid PIT evidence because the earlier capture used the placeholder contact@example.com. The clean gate run uses first-seen and derived available timestamps from run 40661139681, not the earlier observation time.
- The 10/28 close is partial (502/503; HUBB missing); the second capture is real and verified (run 40807180694; 2 runs, 36 events, 70 observations). No replay is counted as a real run.

## Evidence links

- Final conclusion PR #399: https://github.com/wijouyang-lab/us/pull/399
- Final acceptance audit: `docs/research/FINAL_ACCEPTANCE_AUDIT_2026-10-28.md`
- 466 validation: https://github.com/wijouyang-lab/us/pull/392
- Qlib audit: https://github.com/wijouyang-lab/us/pull/389
- Data coverage: https://github.com/wijouyang-lab/us/pull/390
- Event research: https://github.com/wijouyang-lab/us/pull/397
- First real event run: https://github.com/wijouyang-lab/us/actions/runs/40661139681

## Operational recheck — 2026-10-29 UTC (checked at 00:16:38Z)

### Price panel and SPY close

The configured Yahoo Chart/yfinance updater was rerun on 2026-10-29 UTC. The panel now contains 2026-10-28 for **502/503 tickers**; HUBB returned `close: null`, so the close gate is **partial**, not complete. SPY has 2026-10-28 with 2,542 rows and `Adj_Close` available. Duplicate rows 0; new invalid OHLCV 0; 10/27 overlap max close diff 0.0%. No intraday or synthetic value was substituted.

Evidence:
- [10/28 update report](https://github.com/wijouyang-lab/us/blob/research/event-market-alignment/docs/research/RECENT_PRICE_UPDATE_2026-10-29.md)
- [increment metadata](https://github.com/wijouyang-lab/us/blob/research/event-market-alignment/docs/research/recent_price_update_metadata_2026-10-29.json)
- [SPY metadata](https://github.com/wijouyang-lab/us/blob/research/event-market-alignment/docs/research/market_proxy_spy_metadata_2026-10-29.json)

### Exact reconciliation of 35 versus 59 events

The 59-row PR #393 capture is 12 BLS CPI + 12 BLS Employment + 20 Fed press + 15 Fed speeches. I compared event IDs directly: **all 35 Fed IDs overlap exactly** with the 35-event gate sample from real workflow run [40661139681](https://github.com/wijouyang-lab/us/actions/runs/40661139681); there are zero gate IDs missing from the 59-row capture. The other 24 rows are BLS records from the earlier capture that used the placeholder contact identity contact@example.com; the repository's superseding source note says not to use those BLS rows as valid PIT evidence. The correct eligible population remains 35, not 59 and not 94.

The two real observation times differ:
- 59-row capture's 35 Fed rows: first_seen / derived available from 2026-10-28 07:33:06.100095Z to 07:33:07.568705Z.
- Clean gate capture, run 40661139681: 2026-10-28 09:02:55.813905Z to 09:02:56.057755Z.
- The gate uses the later clean capture's timestamps. Its result remains **not eligible**: 35 unique events, 0 entry bars, 0 complete +1, 0 complete +5, and only 2.82e-6 days of observed coverage versus the preregistered minimum of 200 events and 365 days.

Evidence:
- [PR #393, 59-row capture](https://github.com/wijouyang-lab/us/pull/393)
- [Superseding note on BLS contact requirement](https://github.com/wijouyang-lab/us/blob/research/pit-event-forward/docs/research/PIT_EVENT_NOSECRET_RSS_2026-10-28.md)
- [PR #397 event gate](https://github.com/wijouyang-lab/us/pull/397)
- [Current archive manifest](https://github.com/wijouyang-lab/us/blob/research/event-archive/archive/latest_manifest.json)

### Second real cross-UTC-day capture

Completed on 2026-10-29 UTC:

- run [40807180694](https://github.com/wijouyang-lab/us/actions/runs/40807180694), success;
- artifact `research-event-capture-40807180694`, ID `12868333062`;
- archive commit [420469c](https://github.com/wijouyang-lab/us/commit/420469c897f35a53bd7ecfe5876a629c58e9ce19);
- `verify`: 2 runs, 36 unique events, 36 versions, 70 observations, reproducible=true;
- new run: +1 event, +1 version, 35 new observations, 34 duplicates, 0 revisions/retractions/conflicts;
- old `runs/40661139681/` unchanged in git diff `785b956..420469c`.

BLS remains skipped for missing contact User-Agent; Fed feeds returned 20 + 15 events.

### Controls

PRs [#397](https://github.com/wijouyang-lab/us/pull/397), [#398](https://github.com/wijouyang-lab/us/pull/398), [#399](https://github.com/wijouyang-lab/us/pull/399), and [#400](https://github.com/wijouyang-lab/us/pull/400) remain Draft. No auto-merge was enabled. No production scanner, scoring, stop, ledger, order path, or external trigger was changed.

## Research stop rule

Do not start another factor/model/parameter search on the same 466 sample.
Reopen only after the data gates above are satisfied and a new hypothesis is
pre-registered.

## Protection

PR #397, #398, #399 and this closure PR remain Draft. No auto-merge. Production
scanner, scoring, stops, ledger, order path, and external triggers unchanged.
