# Event Source Assessment 鈥?SEC / Earnings / Macro

Date: 2026-10-29 UTC
Research only. No new API requests without valid identity.

## Current state

- 36 unique events from Fed RSS.
- Entry 35; +1/+5 0.
- No new event capture since run 40807180694.
- No SEC or macro request has been executed.

## SEC EDGAR

Official API documentation:

https://www.sec.gov/edgar/sec-api-documentation

Potential fields:

- CIK / accession number;
- form type (8-K, 10-Q, 10-K);
- `filingDate` (date only);
- acceptance datetime when available;
- primary document / items.

Assessment:

| Requirement | Status |
|---|---|
| legitimate contact User-Agent | **not configured** |
| real request executed | **no** |
| exact public timestamp | not assumed |
| filingDate treated as exact time | **no** |
| dedup key | accession number (planned) |
| revision handling | amendment forms (planned) |

`filingDate` is a date, not an exact public release timestamp. A future
implementation must retain `event_time=unknown` when only a date is available.

## BLS

- Official BLS API requires a contact User-Agent/registration for some access.
- No valid `OFFICIAL_FEED_USER_AGENT` is configured.
- Status: `skipped_missing_contact_user_agent`; no request, no placeholder.

## FRED

https://fred.stlouisfed.org/

- API key and terms review required.
- Release timestamps and revisions must be preserved.
- Status: **not executed**.

## BEA

https://www.bea.gov/

- API key and terms review required.
- Release timestamps/revisions must be preserved.
- Status: **not executed**.

## Federal Reserve

- Existing Fed RSS collection is the only real source.
- 20 press + 15 speeches in the current capture.
- Publication timestamps are retained; first-seen remains the actual observation.

## Earnings announcements

- No free, licensed earnings-calendar source has been approved.
- Status: **not executed**.

## Conclusion

No new event source is admitted. The 36-event sample remains below the
pre-registered 200-event / 365-day gate. No alpha test is authorized.
