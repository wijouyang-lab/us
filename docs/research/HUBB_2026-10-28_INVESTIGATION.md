# HUBB 2026-10-28 Close Investigation

Date: 2026-10-29 UTC
Research only. No production changes.

## Result

**Blocked.** HUBB 2026-10-28 remains missing from the canonical 503 panel.

The provider (Yahoo chart) returned HTTP 200 but an incomplete and internally
invalid daily bar. No documented fallback applies to the recent 503 panel, so
no CSV row was patched and no web price was selected.

## Raw Yahoo response

Evidence files:

- `hubb_2026-10-28/yahoo_query1.raw`
- `hubb_2026-10-28/yahoo_query2.raw`
- `hubb_2026-10-28/nasdaq.raw`
- `hubb_2026-10-28/evidence.json`

Key fields for 2026-10-28:

```text
timestamp: 1793194200 -> 2026-10-28T13:30:00Z = 09:30 ET (session open)
open:      444.67999267578125
high:      444.05499267578125
low:       426.9100036621094
close:     null
adjclose:  null
volume:    1163816
```

Invalid reasons:

1. `close` is null.
2. `adjclose` is null.
3. `open 444.68 > high 444.055`, so the daily OHLC is invalid even before close.

Yahoo's `meta.regularMarketPrice` is 437.33 and `meta.fulldayPrice` is 438.83,
but neither is the daily close array and neither may be substituted for a
formal daily bar.

## Independent comparison

### Nasdaq historical API

HTTP 200, 10/28/2026 row:

```text
close:  $437.33
open:   $444.68
high:   $444.805
low:    $426.91
volume: 1,163,860
```

This is a valid OHLC row and corroborates 437.33 as the likely close.
However, the canonical panel's source contract is Yahoo raw OHLCV; Nasdaq is
not a documented fallback for the recent panel.

### Nasdaq fallback evaluation

| Requirement | Nasdaq result |
|---|---|
| exact trading date | 10/28/2026, matches |
| timezone/trading date | US/Eastern date; no timestamp |
| OHLC validity | valid |
| volume | 1,163,860 shares |
| adjusted close | **not provided** |
| update/revision metadata | **not provided** |
| independent of Yahoo | yes |
| data-use/storage permission | **not documented** |
| second independent adjusted source | **not found** |

Nasdaq's page is a raw `Close/Last` table, not an adjusted-close feed. The
existing 503 panel is raw OHLCV, so raw basis is not in itself incompatible.
The blockers are: no adjusted-close field, no revision/update metadata, no
documented permission to store/redistribute, and no second independent
adjusted-close source. Nasdaq is therefore **not approved** as a fallback.

### Other checks

| Source | Result |
|---|---|
| Stooq CSV | blocked by proxy/SSL failure |
| Hubbell investor-relations site | no public daily close row found |
| LSEG | subscription required; no public row |
| Yahoo query1 / query2 | identical incomplete bar |

## Existing source rules

- Canonical 503 panel: `yahoo_chart_yfinance`, raw OHLCV.
- No approved fallback for a single recent-panel missing close.
- The PIT historical refresh has separate legacy/Internet Archive fallbacks;
  those do not apply to this recent panel.
- Portfolio entry pricing explicitly forbids fallback to real-time/other close
  fields.

Therefore adding Nasdaq's 437.33 would be a new, unaudited source contract, not
an existing rule.

## Decision

Keep:

```text
HUBB 2026-10-28 = missing
panel = 502/503
download_status = partial
acceptance = fail
```

No manual CSV edit, no intraday/after-hours substitute, no synthetic row.

## What would unblock

Either:

1. Yahoo publishes a valid HUBB 10/28 OHLCV + adjusted-close row; or
2. A reviewed source-priority/fallback contract explicitly authorizes Nasdaq
   (or another audited provider) for recent-panel gaps, with provenance and
   tests.

## Tests

Targeted updater tests must include a null-close provider row and assert that
the row is dropped, not coerced.

The full 503 rerun already occurred before this investigation; it produced
502/503 and must not be reported as complete.
