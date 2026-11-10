# Alpaca Free Market Data Assessment

Date: 2026-10-29 UTC
Research only. No production changes. No canonical panel writes.

## Security first

The API key pasted into chat is treated as **compromised**. It was not used,
copied, stored, logged, or committed. Rotate it in the Alpaca dashboard.

No `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` / `ALPACA_API_KEY` /
`ALPACA_API_SECRET` was present in the process environment. Therefore **no real
Alpaca API request was made** and no Alpaca HUBB bar or 503 coverage was
observed. This report does not claim otherwise.

## Official plan facts

From the Alpaca Market Data docs:

- Trading API Basic is free.
- Basic real-time equities coverage is **IEX only**, ~2.5% of market volume.
- Historical data is available since 2016, with a latest-15-minutes limitation.
- Basic limit: 200 historical API calls/minute.
- Historical `feed` can be `iex` or `sip`; SIP access/limits depend on
  subscription. The docs say the `end` parameter must be at least 15 minutes
  old to query SIP without a subscription, but also describe Basic historical
  access as limited. **Actual account entitlement is unverified.**
- The free feed is not a consolidated-tape close. IEX-only bars cannot be
  assumed to equal the official consolidated close.

Official sources:

- https://docs.alpaca.markets/us/docs/about-market-data-api
- https://docs.alpaca.markets/us/docs/historical-stock-data-1
- https://docs.alpaca.markets/us/docs/market-data-faq
- https://docs.alpaca.markets/us/reference/stockbars

## SIP/IEX verification status 鈥?not executed

Credential names checked without printing values:

```text
APCA_API_KEY_ID=absent
APCA_API_SECRET_KEY=absent
ALPACA_API_KEY=absent
ALPACA_API_SECRET=absent
```

Therefore no real request was sent for any of:

| Request | Status |
|---|---|
| HUBB 2026-10-28 `feed=sip`, `adjustment=raw` | **not executed** |
| HUBB 2026-10-28 `feed=iex`, `adjustment=raw` | **not executed** |
| HUBB 2026-10-28 `adjustment=all` | **not executed** |
| 503 batch coverage | **not executed** |

No SIP permission, HTTP status, response hash, HUBB row, or 503 coverage is
claimed. The adapter's SIP/IEX/`all` behavior is covered only by synthetic
fixtures; those are not market evidence.

## Bars API shape

Example documented daily bar:

```json
{"t":"2023-09-29T04:00:00Z","o":172.02,"h":173.07,"l":170.341,"c":171.21,"v":51861083}
```

- `t`: timestamp
- `o/h/l/c/v`: raw or adjusted OHLCV according to the `adjustment` parameter
- `n`, `vw`: trade count / VWAP
- no separate `Adj_Close` field

The endpoint supports `adjustment=raw|split|dividend|all`. This is a transformed
bar series, not an `Adj_Close` column. For a raw panel, only `adjustment=raw`
could be compared; for adjusted analysis, the adjustment semantics would need
separate validation.

## HUBB 2026-10-28

**Unverified.** With no secure credentials, no Alpaca request was executed. No
Alpaca HUBB row exists to compare with Yahoo/Nasdaq. Mock fixtures in tests are
synthetic and are not market evidence.

## 503 coverage

**Unverified.** No batch request, pagination, coverage rate, missing list,
delisted-history result, or feed/permission result can be claimed without a
real account request.

The adapter supports batch symbols and `next_page_token`, but only mock tests
have run.

## Adapter and tests

`tools/research/alpaca_market_data.py`:

- reads only environment credentials;
- never logs headers or secrets;
- uses Stock Bars endpoint, not orders;
- supports `feed` and `adjustment`;
- follows pagination;
- hashes each raw response page;
- raises explicit 401/403/429 errors;
- does not write the canonical panel.

Tests: `tests/test_alpaca_market_data.py` 閳?**8 passed**, fixed fixtures only.

Covered: missing credentials, pagination/provenance, 429/403, null close/invalid
OHLCV survival for downstream rejection, raw adjustment/no Adj_Close claim.

## Contract decision

| Requirement | Alpaca status |
|---|---|
| exact date | unverified |
| valid raw OHLCV | unverified |
| adjusted close | no explicit field; adjustment parameter only |
| update/revision metadata | not documented in bars payload |
| documented storage/right to publish artifacts | not established |
| official consolidated close | Basic feed is IEX only; SIP entitlement unverified |
| provenance URL + SHA-256 | adapter can provide; no real response yet |
| free-tier sustainability | 200 calls/min documented; batch needed |

**Not approved.** `blocked_no_approved_fallback` remains.

## Reproducible command (only with secure credentials)

Do not paste keys into shell history or logs. Set env vars in a secure runner:

```bash
python - <<'PY'
from datetime import date
from tools.research.alpaca_market_data import fetch_daily_bars
out = fetch_daily_bars(["HUBB"], date(2026,10,28), date(2026,10,29), feed="iex", adjustment="raw")
print(out["rows"], out["pages"])
PY
```

A real run must also test `feed=sip` and record the exact HTTP 403/422 message
without printing credentials.

## Current state

- HUBB 2026-10-28 remains missing.
- 503 panel remains 502/503 (`partial`).
- Acceptance remains fail.
- Event sample remains 36; entry 35, +1 0, +5 0; gate `not_eligible`.
- No fallback provider is enabled.
