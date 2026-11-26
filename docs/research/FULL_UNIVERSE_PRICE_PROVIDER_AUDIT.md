# Full-Universe Price Provider Audit V1.1

Date: 2026-11-25

## Test executed

yfinance, 6 months, daily, 500-ticker batches, threads enabled, per-batch
isolation and resume.

```text
valid download universe: 5,501 COMMON+ADR
successful tickers:      5,044
NO_DATA:                   457
20-valid-day coverage:   5,021 / 5,501 = 91.28%
60-valid-day coverage:   4,975 / 5,501 = 90.44%
```

By type:

- COMMON: 4,750 / 5,186 = 91.59%
- ADR: 271 / 315 = 86.03%

## Failures

- 457 names returned no usable rows (delisted, symbol mismatch, empty response).
- 470 names flagged `CORPORATE_ACTION_REVIEW` by >50% raw-close move.
- No company-action feed; flags are NOT confirmed splits.

## License

yfinance is unofficial Yahoo access. Research prototype only; not an
exchange-grade or production data license. No paid source used.

## Decision

`FREE_PROVIDER_PARTIALLY_SUFFICIENT`: enough for COMMON research above 90%,
not for ADR or a clean full-market production panel.
