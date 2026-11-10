# Historical Price Provider Status

Date: 2026-10-29 UTC
No provider is approved. No canonical panel write.

## Admission states

| Status | Providers | Evidence |
|---|---|---|
| `approved` | **none** | no written storage/redistribution licence |
| `blocked_pending_terms` | Yahoo, Alpha Vantage, Alpaca, AKShare/Sina, Nasdaq, Stooq | existing terms review; redistribution/storage not granted |
| `blocked_pending_coverage` | free candidates | no systematic delisted/PIT adjusted coverage |
| `paid_candidate` | LSEG, EODHD/Polygon-class licensed feeds | no subscription or quote; terms not verified |

## Required for approval

1. Official terms explicitly permit internal research, long-term storage,
   derived statistics and public derived reports.
2. Daily OHLCV and adjusted close.
3. Corporate actions and delisted/history coverage.
4. Revision/version or PIT support.
5. API key/limits and cost documented.
6. Reproducible provenance.

## Minimal compliant route

A paid/negotiated licence is the shortest path. Exact vendor, cost and
redistribution scope remain **unverified** because no subscription or written
quote was obtained. API accessibility is not a licence.

## HUBB

HUBB 2026-10-28 remains missing; panel 502/503; acceptance fail.
