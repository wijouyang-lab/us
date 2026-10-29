# Recent-Price Provider Contract Assessment

Date: 2026-10-29 UTC
Research only. No production changes.

## Decision

**B. Blocked 鈥?no approved fallback provider.**

HUBB 2026-10-28 remains missing. The 503 panel stays 502/503 (`partial`), and
event acceptance remains fail. This is a deliberate fail-closed result.

## Existing contract

- Canonical 503 panel: `yahoo_chart_yfinance`, raw OHLCV.
- No documented recent-panel fallback.
- PIT historical refresh has separate archive/EODHD fallbacks; those do not
  apply to the recent panel.
- Portfolio entry pricing explicitly forbids current/intraday substitutes.

## Candidate assessment

### Nasdaq historical page API

Observed response for HUBB 2026-10-28:

```text
HTTP 200
date 10/28/2026
open 444.68, high 444.805, low 426.91, close 437.33, volume 1,163,860
```

| Requirement | Result |
|---|---|
| exact date | pass |
| valid raw OHLCV | pass |
| volume | pass (shares) |
| adjusted close | **absent** |
| update/revision metadata | **absent** (`asOf: null`) |
| documented storage/use rights | **not verified** |
| independent of Yahoo | yes |
| second independent adjusted source | **not found** |

The endpoint is a public Nasdaq web page API, not a documented market-data
feed. Nasdaq's market-data policies require review/licensing for non-display
and redistribution uses. There is no evidence in the repository authorizing
storage or reuse. Therefore Nasdaq is **not approved**.

### Other candidates

| Provider | Result | Missing |
|---|---|---|
| Stooq | network proxy/SSL failure | no data |
| Hubbell IR | no public daily OHLCV row | no data |
| LSEG | subscription required | no access/licence |
| Alpha Vantage | demo key only | no key; free-tier terms |
| Twelve Data | demo key only | no key; free-tier terms |
| EODHD | demo/paid token required | no key; terms |

## Contract implementation

`tools/research/recent_price_fallback_contract.py` evaluates a candidate row
without fetching or writing. It requires:

- exact target date;
- valid raw OHLCV and nonzero volume;
- provider on the approved list;
- verified data rights;
- matching price basis;
- adjusted close when the consumer requires it;
- source URL, fetch time, SHA-256 provenance;
- no duplicate existing row;
- close conflict tolerance of $0.01;
- fail-closed rejection otherwise.

Current policy:

`docs/research/recent_price_fallback_policy_2026-10-29.json`

```json
{"status":"blocked_no_approved_fallback","approved_providers":[]}
```

No provider is enabled. The module is not wired to write the panel.

## Tests

`tests/test_recent_price_fallback_contract.py`: **7 passed**

Coverage:

- primary valid -> no fallback;
- missing/invalid primary -> candidate check;
- approved valid candidate + provenance -> accepted;
- unapproved Nasdaq -> rejected;
- invalid OHLC/date/price basis -> rejected;
- missing provenance/duplicate/conflict -> rejected;
- unverified rights -> rejected.

Existing updater null-close test: **4 passed**.

## Why HUBB is not patched

- No approved provider.
- Nasdaq lacks adjusted close, revision metadata, and documented rights.
- Yahoo meta current price is not a daily close.
- Adding 437.33 manually would create an unaudited one-off and violate the
  no-synthetic-row rule.

## Panel / event state

- HUBB 2026-10-28 missing.
- Panel 502/503; duplicates 0; new invalid OHLCV 0; 10/27 overlap diff 0.0%.
- SPY complete through 2026-10-28.
- Second real capture complete: run 40807180694, 2 runs, 36 events, 70
  observations.
- Readiness: 35 entry, 0 +1, 0 +5, 1 pending entry.
- Gate: `not_eligible` (36 < 200; <365 days).

## Next executable action

Obtain a provider with:

1. documented storage/redistribution rights;
2. adjusted close or an explicitly scoped raw-only contract;
3. update/revision metadata;
4. provenance URL + hash;
5. an independent adjusted-close cross-check.

Until then, keep `blocked_no_approved_fallback`.
