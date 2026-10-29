# Legal Market Data Provider Comparison

Date: 2026-10-29 UTC
Research only. No production or canonical-panel changes.

## Decision

**No provider is approved.** `approved_providers=[]` remains.

The main blockers are written permission for repository retention/public
artifacts, adjusted-price semantics, revision metadata, and delisted/PIT
coverage. HTTP availability and matching values are not approval.

## Comparison

| Provider | Terms / status | Raw OHLCV | Adjusted close | Internal research | Long-term/private repo | Public artifact | Revision metadata | Cost/limit | Decision |
|---|---|---|---|---|---|---|---|---|---|
| Yahoo/yfinance (existing primary) | Terms not reviewed for repository storage | yes | Adj Close for some feeds | not authorized here | unverified | unverified | none in panel | rate-limited | primary only; no fallback approval |
| Alpaca Basic | [Terms PDF](https://s3.amazonaws.com/files.alpaca.markets/disclosures/library/TermsAndConditions.pdf): personal/non-commercial | yes | `adjustment` parameter, no `Adj_Close` field | limited personal | not clearly granted | no | no update/revision field | 200/min Basic; IEX only | **not approved** |
| Alpha Vantage | [Terms](https://www.alphavantage.co/terms_of_service/): personal/non-commercial unless written | yes | adjusted endpoints | limited personal | not clearly granted | no | no documented revision history | free key/throttled | **not approved** |
| AKShare / Sina | [Sina copyright](http://corp.sina.com.cn/chn/copyright.html): written permission required | 503/503 tested | qfq only; no `Adj_Close` | not granted in writing | **no** | **no** | **none** | no key; full-history fetch | **not approved** |
| Nasdaq page API | market-data policies require licence/review | valid HUBB row | no | unverified | **no** | **no** | `asOf=null` | public page endpoint | **not approved** |
| Stooq | no clear written terms; network failed | unavailable in test | unknown | unverified | unverified | unverified | unknown | free | **blocked/unverified** |
| LSEG | subscription/entitlement | not accessed | licensed product | paid | paid | paid | provider-specific | paid | **not approved** |
| SEC EDGAR | official public filings, not prices; fair-access UA required | n/a | n/a | event research only | public filings | public | filing timestamps | rate-limited | **event source only; UA absent** |
| FRED | official macro; API key/terms not configured | n/a | n/a | not executed | unverified | unverified | release timestamps | API key | **not executed** |

## Written evidence highlights

### Alpha Vantage

Terms state use is for **personal, non-commercial use** unless a written
agreement says otherwise. Commercial use includes providing information to
others. Therefore public repository artifacts/raw data are not approved.

- PDF SHA-256: `88ed3d22fe0f3624e76e53a210db3498b4a90712ab0d934356cc84b19ed1468a`

### Alpaca

Terms require use **solely for your own personal and non-commercial purposes**;
making content available through an application requires advance notice. This
does not establish permission for public raw-data artifacts.

- PDF SHA-256: `2dc774d4aeeafbe4c7f0565e7842d932bc8bc10488af805fce43b8734e7b9859`

### AKShare/Sina

Sina's copyright statement requires **written permission** before copying,
mirroring, or otherwise using its copyrighted content. No such permission was
found.

- HTML SHA-256: `6a6e8ced314992953edba492b20d70daa812abc2ca1a7c9dc4326d6e807e9f77`

## HUBB contract

| Requirement | Best candidate |
|---|---|
| exact date | AKShare/Nasdaq pass |
| valid raw OHLCV | AKShare/Nasdaq pass |
| canonical raw basis | pass on this date |
| adjusted data | only qfq/transform; no explicit `Adj_Close` |
| provenance | URL + hash available |
| revision metadata | **fail** |
| storage/use permission | **fail** |
| overall | **blocked** |

HUBB remains missing; panel 502/503; acceptance fail.

## Event-source assessment

- SEC EDGAR: public filings, but requires a real contact User-Agent and has
  fair-access limits. No valid configuration, so **not executed**.
- Earnings announcements: no free source approved; **not executed**.
- Macro calendar: FRED/other official sources require key/terms review;
  **not executed**.
- BLS: skipped for missing real contact identity.
- No placeholder identity was used.

## Concrete next actions

1. Obtain written permission or a licensed provider for raw daily data and
   public artifacts.
2. Require adjusted-close semantics and revision/update metadata.
3. Validate a delisted/PIT universe.
4. Only then submit a provider approval proposal.
