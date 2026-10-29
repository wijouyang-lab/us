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
| 10/28 official close | research operations owner (human) | provider close + incremental updater | committed 503-ticker panel and SPY proxy both still end 10/27; no verified 10/28 row | **pending** |
| Second real cross-day capture | research operations owner (human) | workflow + archive verify | manifest still records one run (#40661139681); no 10/29 UTC run | **pending** |

Machine-readable:

`docs/research/RESEARCH_CLOSURE_DATA_READINESS_2026-10-28.json`

## Important distinctions

- **Data not ready does not mean the strategy is proven impossible.**
- **Qlib audit not independently rerun** 鈥?values are taken from the committed
  audit document; raw per-period JSON is missing.
- The event gate remains 35 unique events, 0 entry, 0 +1, and 0 +5; it is not an alpha finding.
- The 59-row capture has exactly the same 35 Fed event IDs plus 24 BLS rows. The BLS rows are not valid PIT evidence because the earlier capture used the placeholder contact@example.com. The clean gate run uses first-seen and derived available timestamps from run 40661139681, not the earlier observation time.
- The 10/28 close and second cross-day capture remain pending. No replay is counted as a real run.

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

The last committed increment metadata reports 503 tickers requested, 503 with rows, 4,527 rows across 2026-10-15 through 2026-10-27, and zero missing tickers. Its last date is still **2026-10-27**. The separate SPY proxy has 2,541 rows, no duplicate/invalid rows, and a last date of **2026-10-27**.

Public Yahoo Finance history search results now show a 2026-10-28 SPY row, but the Yahoo locale mirrors returned different exact close values. I therefore did not treat the snippets as verified pipeline evidence. The configured Yahoo Chart/yfinance increment and SPY artifacts have not been refreshed in this run; the GitHub tools available here do not expose a price-updater dispatch or repository execution action. The 10/28 close gate remains pending until both actual datasets contain the official 2026-10-28 bar and pass validation. No intraday price was substituted.

Evidence:
- [503-ticker updater metadata](https://github.com/wijouyang-lab/us/blob/research/event-market-alignment/docs/research/recent_price_update_metadata_2026-10-28.json)
- [SPY proxy metadata](https://github.com/wijouyang-lab/us/blob/research/event-market-alignment/docs/research/market_proxy_spy_metadata_2026-10-28.json)
- [Yahoo Finance SPY history (NZ)](https://nz.finance.yahoo.com/quote/SPY/history/)
- [Yahoo Finance SPY history (DE)](https://de.finance.yahoo.com/quote/SPY/history/)

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

The current archive manifest was generated at 2026-10-28T09:02:58.711468Z and contains exactly one run: 40661139681, with 35 unique event IDs, 35 versions, and 35 observations. The archive snapshot hash is f331902dc94303620bee8c2cc6f5e0ae5382fef4d944dac082c8e2016546cc9d; the corresponding archive commit is [785b956](https://github.com/wijouyang-lab/us/commit/785b9565a7c603bb43959cd4d504ead80298fc10). No second run on 2026-10-29 UTC is recorded.

The manual workflow is present on [main](https://github.com/wijouyang-lab/us/blob/main/.github/workflows/research-event-capture.yml) because PR #394 was merged, so GitHub Actions supports dispatching it. However, the connected GitHub toolset in this execution exposes no workflow_dispatch operation. I did **not** rerun or replay the old capture and did **not** claim a second run. A distinct run must still be dispatched and verified.

### Controls

PRs [#397](https://github.com/wijouyang-lab/us/pull/397), [#398](https://github.com/wijouyang-lab/us/pull/398), [#399](https://github.com/wijouyang-lab/us/pull/399), and [#400](https://github.com/wijouyang-lab/us/pull/400) remain Draft. No auto-merge was enabled. No production scanner, scoring, stop, ledger, order path, or external trigger was changed.

## Research stop rule

Do not start another factor/model/parameter search on the same 466 sample.
Reopen only after the data gates above are satisfied and a new hypothesis is
pre-registered.

## Protection

PR #397, #398, #399 and this closure PR remain Draft. No auto-merge. Production
scanner, scoring, stops, ledger, order path, and external triggers unchanged.
