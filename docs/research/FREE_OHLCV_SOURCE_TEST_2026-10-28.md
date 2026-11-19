# Free OHLCV Source Tests 鈥?Actual Results

Date: 2026-10-28
Research only. No API keys are stored or printed.

## Classification rule

A source is marked usable only if a real request returned at least one valid
historical OHLCV record for a requested ticker. HTTP 200, a JSON wrapper, or a
downloaded HTML file alone is not success.

## Results

| Source | Real request | HTTP/response | Valid OHLCV rows | Delisted support | Adjusted/corporate actions | Verdict |
|---|---|---|---|---|---:|---|
| Yahoo / yfinance (existing) | yes (prior audit) | 404 / no usable rows for 98 | 0 for failed tickers | no for these names | partial | not a recovery source |
| Stooq CSV | yes | 200 HTML JS challenge | 0 | unknown | unknown | unusable in this environment |
| Nasdaq quote API | yes | 200 JSON, `totalRecords=0` / Symbol not exists | 0 | no | no | unusable |
| Internet Archive | yes (prior PIT audit) | no usable legacy CSV | 0/98 | no recovery | unknown | no recovery |
| SEC company/submissions | yes | 200 JSON | 0 prices | identity only | filings only | not OHLCV |
| OpenBB | no provider stack/credentials | not requested | 0 | unknown | provider-dependent | blocked |
| Alpha Vantage live | no key configured | `SKIPPED_NO_API_KEY` | 0 | unverified | unverified | requires key |
| Alpha Vantage demo | yes | 200, Information only | 0 | no | no | not usable |
| FMP demo | yes | 401 Unauthorized | 0 | no | no | requires key |
| coiltrade membership | yes (file) | JSON membership | 0 prices | membership only | no | not OHLCV |
| shardul membership | yes (file) | YAML membership | 0 prices | membership only | no | not OHLCV |

## Specific failed samples

- AVB (currently listed): Yahoo failed; SEC identity exists.
- PARA (current/renamed): Yahoo failed; SEC identity exists.
- ATVI (acquired): Yahoo failed; SEC identity + membership removal exists.
- MYL (renamed VTRS): Yahoo failed; SEC identity + membership removal exists.

No sample produced a valid historical OHLCV series from an independent free
source.

## Alpha Vantage details

Adapter:

`tools/research/alpha_vantage_provider.py`

- key only from `ALPHA_VANTAGE_API_KEY`
- cache and 25/day counter
- 12-second minimum interval
- adjusted/unadjusted guard
- key redaction

Local output without key:

```text
AVB  -> SKIPPED_NO_API_KEY
ATVI -> SKIPPED_NO_API_KEY
MYL  -> SKIPPED_NO_API_KEY
PARA -> SKIPPED_NO_API_KEY
```

The actual free-tier history range, delisted support, and adjusted fields
remain unverified. Mocked tests: 6 passed.

## Conclusion

No independent free OHLCV source has produced valid historical records for the
failed tickers. Membership evidence and SEC evidence are identity-only.

The data-research gate remains blocked and the full-history PIT strategy
validation stays frozen.
