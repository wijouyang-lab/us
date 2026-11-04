# Finnhub Key A/B Security & Permission Audit — P3.1

Date: 2026-11-04
Status: **NOT_CONFIGURED / LICENSE_UNVERIFIED**

## 1. Configuration check

Only environment-variable names were inspected:

```text
FINNHUB_API_KEY_A   absent
FINNHUB_API_KEY_B   absent
FINNHUB_API_KEY     absent
```

No key value, request URL token, Authorization header or full exception was
written to the audit JSON, CSV, report, logs or tests.

`.env` and `.env.local` are gitignored. `.env.example` contains placeholders
only; no real values were added.

## 2. Why no API result

No Finnhub request was made because no credential exists in the environment.
This is `NOT_CONFIGURED`, not an API failure and not a licence verdict.

Therefore the following remain unknown:

- account identity;
- whether A and B belong to the same account;
- free plan name;
- per-minute and per-day limits;
- quote entitlement;
- daily candle entitlement;
- earliest historical date;
- split/dividend adjustment support;
- financials/dividends/earnings/profile permissions;
- rate-limit headers;
- error behavior for 401/403/429.

The two keys were not rotated to obtain extra quota.

## 3. Minimal future validation

When credentials are supplied locally, run each key independently:

1. `GET /quote?symbol=AAPL` — quote entitlement.
2. `GET /stock/candle?symbol=AAPL&resolution=D&from=...&to=...` with a short
   window — daily candle entitlement.
3. `GET /stock/profile2?symbol=AAPL` — identity metadata only.
4. Record HTTP status and limit headers if present.
5. Record quote success and candle success separately.
6. Stop on 401/403; do not retry with the other key to bypass a limit.
7. Do not call paid endpoints, start trials or add payment methods.

## 4. Licence conclusion

Finnhub terms are not confirmed for this project's storage/redistribution use.
No written permission was obtained.

| Use | Status |
|---|---|
| Local personal research | LICENSE_UNVERIFIED |
| Local historical storage | LICENSE_UNVERIFIED |
| Historical backtest | LICENSE_UNVERIFIED |
| Public GitHub data | LICENSE_UNVERIFIED |
| GitHub Pages display | LICENSE_UNVERIFIED |
| Public derived analysis | LICENSE_UNVERIFIED |

Key validity, if later confirmed, would not change these licence statuses.

## 5. Project impact

- P4 Dividend Quality does not use Finnhub or any market price.
- P3 price-dependent features remain `DATA_BLOCKED`.
- No Finnhub data is added to the paper account or production.
