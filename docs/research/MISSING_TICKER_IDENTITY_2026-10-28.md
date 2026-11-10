# 98 Missing Tickers: SEC Identity Evidence

Date: 2026-10-28
Research only. No production changes.

## Result summary

Input: `missing_tickers_classification_2026-10-28.csv`
Evidence run: SEC submissions API via `enrich_missing_ticker_identity.py`
Output: `missing_tickers_identity_2026-10-28.csv`

| Metric | Count |
|---|---:|
| Failed tickers | 98 |
| Matched to membership record with CIK | **98/98** |
| SEC submissions fetched/cached | 98 |
| High identity confidence | **97** |
| Medium identity confidence | **1** (`FRC`, no priority filing found) |
| Unresolved identity | **0** |
| Membership removal recorded | **98/98** |

Every matched ticker has:

- CIK
- company name from SEC submissions
- S&P membership added / removed dates
- SEC submissions evidence URL
- latest relevant 8-K/10-K/10-Q where available
- event effective date separated from filing availability date

## What the evidence proves 鈥?and does not prove

Proved:

- The ticker can be mapped to a specific SEC registrant and CIK via the
  historical membership row.
- The S&P membership removal date is recorded.
- A relevant SEC filing date is usually available.

Not proved:

- **Removal from the S&P 500 is not proof of delisting.** A company may be
  removed after acquisition, market-cap decline, spin-off, or index
  rebalancing.
- SEC filing availability is not the same as the merger/removal effective date.
- A ticker change is not established by fuzzy string matching. Where the SEC
  `formerNames` field shows name changes, that is name evidence, not
  ticker-successor proof.
- No OHLCV history is provided by SEC.

## Examples

| Ticker | Company | CIK | Membership removed | Latest filing | Filing date | Confidence |
|---|---|---|---|---:|---|---|
| ATVI | Activision Blizzard | 0000718877 | 2023-10-18 | 8-K | 2023-10-16 | high |
| ABMD | ABIOMED | 0000815094 | 2022-12-22 | 8-K | 2022-12-22 | high |
| ALXN | Alexion | 0000899866 | 2021-07-21 | 8-K | 2021-07-22 | high |
| CELG | Celgene | 0000816284 | 2019-11-21 | 8-K | 2019-11-21 | high |
| SIVB | SVB Financial | 0000719739 | 2023-03-15 | 8-K | 2024-11-08 | high |
| FRC | First Republic Bank | 0001132979 | 2023-05-04 | none found | 鈥?| medium |

`FRC` remains medium: identity is established by CIK/membership, but no
priority filing was found in the recent submissions table. Do not infer a
delisting event from that absence.

## Files

- Enriched CSV:
  `docs/research/missing_tickers_identity_2026-10-28.csv`
- Script:
  `tools/research/enrich_missing_ticker_identity.py`
- Tests:
  `tests/test_enrich_missing_ticker_identity.py`

## Next recovery step

Identity is now largely resolved. OHLCV recovery is still blocked:

1. For each confirmed acquisition/merger, obtain the historical price series
   from a lawful delisted-price source.
2. For name changes/ticker changes, verify with the exchange/company filing;
   do not use fuzzy matching.
3. For `FRC`, review SEC filings manually.
4. Membership/CIK evidence cannot replace OHLCV; coverage remains 91.61%.

No prices were filled or inferred.
