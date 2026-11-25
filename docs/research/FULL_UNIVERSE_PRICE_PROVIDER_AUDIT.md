# Full-Universe Price Provider Audit

Date: 2026-11-25
Source tested: yfinance (unofficial Yahoo Finance access)

## Sample

36 tickers, stratified 12 each:

- COMMON
- ADR
- UNCLASSIFIED

Result: 36/36 returned at least 20 rows.

This is not evidence for 5,453 names. The sample does not cover large/mid/small/
micro market-cap strata, all exchanges, share classes, recent corporate actions
or delisted names. Those strata remain **NOT_TESTED**.

## What worked

- Daily OHLC, Close, Adj Close, Volume.
- `period=6mo` and `period=1y`.
- Writable yfinance timezone cache required; default location failed with
  `OperationalError: unable to open database file`.

## What failed

- Full-universe batch: `TypeError: expected string or bytes-like object, got
  'float'` from a non-string ticker.
- `$` preferred-share tickers can 404.
- Occasional DNS/curl timeout (`GM` during top100 fetch), but batch continued.

## License / limits

yfinance is unofficial and not a licensed real-time market data source. It is
acceptable for research prototyping, not for production execution, and not a
guarantee of exchange-grade prices. No paid vendor or API key used.

## Conclusion

Provider audit: **PARTIAL**. Free source works for sampled and top100 names;
full-market reliability is unproven.
