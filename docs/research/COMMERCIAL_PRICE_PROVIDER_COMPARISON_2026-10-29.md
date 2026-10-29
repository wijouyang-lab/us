# Commercial Price Provider Comparison

Date: 2026-10-29 UTC
No purchase, no subscription, no canonical writes.

## Status

| Provider | Official pages | Coverage claim | Adjusted/corporate actions | Delisted/PIT | Commercial status |
|---|---|---|---|---|---|
| Polygon.io | https://polygon.io/pricing, https://polygon.io/terms | US equities/ETFs | vendor docs; not verified on trial | not verified | `quote_required` + `terms_confirmation_required` |
| EODHD | https://eodhd.com/pricing, https://eodhd.com/financial-apis/ | global/US EOD | vendor claims adjusted EOD; not verified | vendor claims historical/delisted; not verified | `quote_required` + `terms_confirmation_required` |
| Alpaca Algo Trader Plus | https://docs.alpaca.markets/us/docs/about-market-data-api | US stocks, SIP, $99/month listed | no explicit `Adj_Close` field | delisted not established | `blocked_pending_terms` (personal/noncommercial) |
| LSEG | https://www.lseg.com/en/data-analytics | enterprise | licensed | enterprise | `quote_required` |

Official pages were reachable (HTTP 200), but **reachability is not a licence**.
No prices/terms were accepted or purchased.

## Minimum compliant scope to request

- internal quantitative research;
- persistent raw + adjusted daily bars;
- corporate actions and delisted/historical universe;
- derived returns/statistics and internal reports;
- public derived reports with explicit redistribution scope;
- revision/version history or documented correction process;
- API access and rate limits.

## Key unresolved terms

1. Whether raw bars may be stored in a private repository.
2. Whether derived data/reports may be public.
3. Whether delisted securities and historical index membership are included.
4. Whether adjusted-close and corporate-action history are included.
5. Whether redistribution of any raw rows is allowed.
6. Actual price for the required internal-use tier.

## Recommendation

Request written quotes and terms confirmation from **Polygon** and **EODHD**
for the minimum scope above. Do not subscribe or accept terms until the six
questions are answered. If neither allows public derived reports, restrict the
project to internal research and publish only aggregate methodology, not raw
data.

No approved provider; `approved_providers=[]`; HUBB remains missing.
## Inquiry status

Drafts:

`docs/research/VENDOR_INQUIRY_DRAFTS_2026-10-29.md`

- Polygon contact: https://polygon.io/contact (`sales@massive.com` observed)
- EODHD contact: `sales@eodhistoricaldata.com` observed on EODHD site
- No email has been sent.
- Both are **pending vendor response**.
