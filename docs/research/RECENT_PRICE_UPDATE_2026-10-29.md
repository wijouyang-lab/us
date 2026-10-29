# 2026-10-28 Close Update and Second Real Capture

Date: 2026-10-29 UTC
Research only. No production changes.

## Second real event capture

| Item | Value |
|---|---|
| Workflow run | **40807180694** |
| URL | https://github.com/wijouyang-lab/us/actions/runs/40807180694 |
| Trigger | `workflow_dispatch` from `main` |
| Started UTC | 2026-10-29T02:34:44Z |
| Completed UTC | 2026-10-29T02:35:33Z |
| Status | **success** |
| Artifact | `research-event-capture-40807180694`, ID `12868333062` |
| Archive commit | `420469c897f35a53bd7ecfe5876a629c58e9ce19` |

### Archive verification

```text
runs: 2
unique_event_ids: 36
versions: 36
observations: 70
reproducible: true
```

New run counts:

```text
new_events: 1
new_versions: 1
new_observations: 35
duplicate_observations: 34
revisions: 0
retractions: 0
timestamp_conflicts: 0
```

Old snapshot `runs/40661139681/` unchanged:

- Git diff `785b956..420469c -- runs/40661139681` is empty.
- Canonical JSON hashes match; raw-byte check differed only because the
  earlier local clone used CRLF.

Source statuses:

```text
fed_all:     ok, 20 events
fed_speeches: ok, 15 events
bls_cpi:      skipped_missing_contact_user_agent
bls_employment: skipped_missing_contact_user_agent
```

BLS is not represented as success.

## 10/28 price update

### 503 panel

| Item | Value |
|---|---|
| Provider | Yahoo chart via yfinance |
| Latest date | **2026-10-28** |
| Rows | 1,239,013 |
| Tickers | 503 |
| New 10/28 rows | 502 |
| Missing on 10/28 | **HUBB** |
| Duplicate rows | 0 |
| New invalid OHLCV | 0 |
| 10/27 overlap Close max diff | 0.0% |
| Download status | **partial** |

HUBB returned `close: null` for 10/28 from Yahoo; no intraday or synthetic
value was substituted. Therefore the panel is **502/503**, not complete.

Increment: `docs/research/recent_price_increment_2026-10-28.csv`

Metadata: `docs/research/recent_price_update_metadata_2026-10-29.json`

### SPY

| Item | Value |
|---|---|
| Latest date | **2026-10-28** |
| Rows | 2,542 |
| Duplicates | 0 |
| Invalid removed | 0 |
| `Adj_Close` | available |
| Source | Yahoo chart via yfinance |
| Fetched UTC | 2026-10-29T02:37:42Z |

SPY is separate from the 503 panel and is not a stock signal.

## Readiness after 10/28

Using 36 real archive events and the 10/28 panel/SPY:

| Mode | Entry | +1 | +5 | Ready | Pending entry | Pending +1 | Pending +5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| SPY market proxy | 35 | 0 | 0 | 0 | 1 | 35 | 0 |
| Stock | 0 | 0 | 0 | 0 | 36 | 0 | 0 |

The 35 events with first-seen 2026-10-28 now have the 10/28 entry bar. They
still need 2026-10-29 (+1) and later (+5) closes. One new event was first seen
2026-10-29 and has no entry bar yet.

## Gate

`event_experiment_gate_2026-10-29.json`:

```text
status: not_eligible
unique_events: 36
coverage_days: <1
entry_results: 35
plus_1_results: 0
plus_5_results: 0
```

No event alpha test was run.

## Acceptance

Unified acceptance exit status is **fail** because one ticker (HUBB) is
missing from 10/28; this is a partial-data state, not a successful close and not
a complete archive failure:

`docs/research/event_research_acceptance_2026-10-29.json`

## Remaining blockers

1. HUBB 10/28 official close missing from provider.
2. No 2026-10-29 close yet; +1/+5 incomplete.
3. Event sample 36 < 200; coverage < 365 days.
4. BLS/SEC User-Agent secrets still absent.
