# AKShare Long-Term Data Suitability

Date: 2026-10-29 UTC
Research only. No production or canonical-panel changes.

## Short answer

AKShare/Sina is useful as a **research and cross-check source**, but it is **not
approved** as a canonical or fallback provider. HUBB remains missing, the panel
remains 502/503, and acceptance remains fail.

## Verified facts

- AKShare 1.20.2; MIT package license.
- Underlying endpoint: `finance.sina.com.cn/staticdata/us/{symbol}`.
- No login/token.
- Full-history response; no date-range parameter.
- 2026-10-28 HUBB raw/qfq: close 437.33, volume 1,163,782.
- 2026-10-28 coverage: 503/503 after BF.B/BRK.B aliases.
- 503 rows: 0 invalid OHLCV, 0 duplicate tickers.
- raw and qfq HUBB values are identical on 2026-10-28; qfq factor table has no
  recent event.
- repeated raw/qfq fetches within the test window produced byte-identical
  responses.

## Terms / license evidence

AKShare's MIT license covers the wrapper, not Sina's data.

Sina's copyright/terms page states (translated from the saved Chinese text):

> Without Sina's written permission, no person may copy or mirror any content
> owned by Sina, or use it in any other way, except as otherwise required by
> Chinese law.

- Source: `http://corp.sina.com.cn/chn/copyright.html`
- Saved evidence: `docs/research/akshare_2026-10-28/sina_copyright.txt`
- HTTP 200, raw body SHA-256:
  `6a6e8ced314992953edba492b20d70daa812abc2ca1a7c9dc4326d6e807e9f77`

No written permission for repository storage, retention, artifact
redistribution, or production use was found. This alone blocks provider
approval.

## Revision / version evidence

No update timestamp, revision ID, correction history, or per-row source version
is returned by the Sina endpoint. Repeating a fetch in the same window is
stable, but that is **not proof** that historical data is never revised. No
version mechanism exists to reproduce a past revision.

## Raw and qfq handling

If AKShare is retained for research:

- store raw and qfq in separate files/columns;
- label `price_basis` explicitly (`raw` or `qfq`);
- never create or rename a field to `Adj_Close`;
- retain the qfq factor table and apply it explicitly;
- hash each raw response.

HUBB qfq-factor coverage extends to 1970; latest factor row is 1985-08-12.
This covers HUBB history, but factor coverage for all 503 tickers was not
audited.

## Delisted / historical coverage

Four delisted/renamed probes returned HTTP 200 with non-empty bodies:

```text
TWTR, ATVI, SIVBQ, FRCB
```

This shows the endpoint can retain some historical symbols; it does not prove
systematic delisted coverage or a PIT universe. The existing 503 panel is
current-universe and survivorship-biased.

## HUBB fallback contract

| Requirement | Result |
|---|---|
| exact 2026-10-28 date | pass |
| valid raw OHLCV | pass |
| canonical raw price basis | pass on this date |
| explicit adjusted price | qfq only; no `Adj_Close` |
| revision/update evidence | **fail** |
| storage/redistribution permission | **fail** |
| provenance | URL + SHA-256 available |
| automated tests | fixture tests pass |
| overall | **not approved** |

HUBB remains missing; no manual value was inserted.

## Tests

- `tests/test_akshare_assessment.py`: **3 passed**
  - 503 coverage validity;
  - HUBB exact row;
  - raw/qfq evidence SHA-256 stability.

These are fixture tests, not a substitute for terms/revision verification.

## Remaining blockers

1. No written Sina permission for storage/retention/redistribution.
2. No revision/history metadata.
3. No explicit `Adj_Close`; qfq semantics are transform-based.
4. No systematic delisted/PIT coverage.
5. HUBB remains missing; panel 502/503; acceptance fail.

## Decision

Keep AKShare as a research/cross-check source. Do **not** add it to
`approved_providers` and do not write it into the canonical panel.

`blocked_no_approved_fallback` remains.
