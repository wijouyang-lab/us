# Price Adapter Validation Contract

Date: 2026-10-29 UTC
No data downloaded; no canonical write.

## Stage 1 鈥?provider authorization

Required before any download:

- written terms/licence for internal storage and derived reports;
- approved provider ID in policy;
- API key/UA configured through secrets;
- retention/redistribution scope recorded.

## Stage 2 鈥?read-only sample

For a fixed sample (HUBB 2026-10-28 plus ~10 varied tickers/dates):

- exact date join;
- OHLCV validity:
  - positive prices;
  - `High >= max(Open, Close, Low)`;
  - `Low <= min(Open, Close, High)`;
  - `Volume >= 0`;
- duplicate `(date,ticker)`;
- raw/adjusted field separation;
- split/dividend/action fields;
- missing values;
- provider timestamp/version;
- close/volume comparison with existing observation, without picking the
  "best-looking" value.

## Stage 3 鈥?coverage and PIT gate

- 503 current names + delisted universe;
- adjusted-close coverage;
- corporate-action coverage;
- revision/vintage support;
- no survivorship-only universe for PIT claims.

## Stage 4 鈥?staging acceptance

Only after stages 1鈥?:

- write to a separate staging dataset, not canonical;
- compare historical overlap;
- run duplicate/OHLC/date tests;
- produce provenance hash and report;
- human approval;
- only then canonical promotion.

## Existing validation hooks

- `tools/research/update_recent_prices_incremental.py`: target date and
  identical-prior-bar guards;
- `tools/research/recent_price_fallback_contract.py`: approved-provider,
  rights, adjusted basis, provenance and conflict checks;
- `tools/research/event_label_plan.py`: XNYS entry/+1/+5 dates only, returns
  null until provider approval.

## Current state

```text
approved_providers = []
HUBB = missing
panel = 502/503
acceptance = fail
```

No provider data has been acquired or persisted. No HUBB fill.

## Tests

- updater: 6 passed
- fallback contract: 7 passed
- entry label plan: 10 passed
