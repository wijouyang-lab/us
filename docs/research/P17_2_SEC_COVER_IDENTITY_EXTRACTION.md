# P17.2 SEC Cover-Page XBRL Identity Extraction

Date: 2026-11-20
Branch: `research/p17-2-sec-cover-identity-extraction`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **PARSER_FEASIBLE · HISTORICAL_COVERAGE = DATA_BLOCKED**

## 1. What was actually parsed

Local SEC cache: `data/sec/filings_p43` with 75 usable Inline XBRL HTML filings.
No external download was performed; no new provider/API key.

Parser reads:

- `ix:nonNumeric` facts by local-name;
- `xbrli:context` identifiers and explicit dimensions;
- `dei:TradingSymbol`, `Security12bTitle`, `SecurityExchangeName`;
- CIK from the context identifier, paired with the filing's XBRL CIK.

Results:

```text
filings parsed: 75
identity symbol facts: 288
unique tickers: 109
verified-at-filing facts: 288
historical 2020/2022/2024 filings: 0
historical identity observations: 0
```

CAT example demonstrates multi-security extraction:

| ticker | class axis | class member | exchange |
|---|---|---|---|
| CAT | us-gaap:StatementClassOfStockAxis | us-gaap:CommonStockMember | NYSE |
| CAT35 | us-gaap:StatementClassOfStockAxis | CAT:Sec5.3Debentures...Member | NYSE |

The two classes keep separate contexts; CAT35 is not merged into CAT.

## 2. Historical coverage

The local filing cache is 2026-only. It contains no 2020, 2022, or 2024
primary documents, so it cannot create a historical identity timeline for the
P17.1 universe.

```text
P17_2_SEC_COVER_EXTRACTION = PARSER_FEASIBLE
P17_2_IDENTITY_OBSERVATION = DATA_BLOCKED
P17_2_HISTORICAL_TIMELINE = NOT_AVAILABLE
P17_2_RESTRICTED_FUNDAMENTAL_RESEARCH = DATA_BLOCKED
```

No daily coverage file is claimed: `p17_2_daily_identity_coverage.csv` is a
zero-filled placeholder for 2020–2024, not measured coverage.

## 3. Answers

1. Raw filing contains TradingSymbol? **Yes**, verified on local 2026 filings.
2. Filing-level observations? **288 symbol facts, 109 unique tickers (2026 only).**
3. CIK accuracy? **288/288 context CIK matched filing CIK in local parse.**
4. Security class? **Yes for CAT/CAT35; contexts preserved.**
5. Exchange coverage? **Present for local CAT facts; full coverage not measured.**
6. Tickers with 2020/2022/2024 filing observations? **0.**
7. 581 priced tickers with candidate CIK? **Not resolved; P17.1 candidates
   remain 53, and no historical filings.**
8. Filing-level verified? **0 historical; 288 2026 facts only.**
9. Carry-forward candidates? **0 historical.**
10. Identity conflicts? **Not testable historically.**
11. Ticker transition dates? **Not available from 2026 cache.**
12. Daily identity cross-section? **0 verified for 2020–2024.**
13. 100 names/80% days gate? **No.**
14. Free SEC filing data supports restricted PIT fundamental research? **Not
    with the current local cache; a historical SEC filing download is required.**
15. Stop? **Yes for this local-data route unless historical filings are
    acquired/processed under SEC-compliant rate limits.**

## 4. Parser quality

- Filing CIK vs XBRL context CIK: 288/288 for parsed symbol facts.
- Multi-class context pairing: CAT/CAT35 verified.
- No `dei:TradingSymbol` facts in many filings is a `NO_IDENTITY_FACT`, not a
  parser crash.
- Accession and document SHA256 recorded.
- `form`, `filing_date`, `acceptance_datetime` are blank in local cache because
  the local index only exposes `last-modified`; these are **not** fabricated.

Parser success on 75 local filings does not mean the 95% historical sample
criterion was met; that criterion applies to the historical pilot, which was
not possible.

## 5. P17.1 corrections

See `P17_1_OUTPUT_CORRECTION_AUDIT.md`: 53 was a unique candidate count, not a
daily cross-section; membership dates are not identity validity; candidate CIK
is not verified; the CompanyFacts 19-metric panel is not full raw XBRL; P17.1
had 10 tests, not 30+.

## 6. Files

- `tools/research/p17_2_sec_cover_identity_extraction.py`
- `tests/test_p17_2_sec_cover_identity_extraction.py`
- `docs/research/P17_1_OUTPUT_CORRECTION_AUDIT.md`
- `data/research/p17_2/p17_2_filing_registry.csv`
- `p17_2_filing_identity_observations.csv`
- `p17_2_xbrl_identity_facts.csv`
- `p17_2_sample_universe.csv`
- `p17_2_ticker_cik_candidates.csv`
- `p17_2_daily_identity_coverage.csv` (zero placeholder)
- `p17_2_parser_quality.json`
- `p17_2_summary.json`
- `p17_2_manifest.json`

No model call, no API key, no broker, no order.
