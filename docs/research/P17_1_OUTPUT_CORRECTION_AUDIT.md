# P17.1 Output Correction Audit

P17.1 (#607) remains unchanged. This file records the corrected interpretation.

1. `daily_cross_section_max_candidate = 53` was `len(priced_candidate)` — a
   unique ticker count, not a daily cross-section. P17.1 did not compute daily
   membership × price counts.
2. The 53 is unique candidate tickers, not measured daily max.
3. `valid_from`/`valid_to` used membership added/removed, not security identity
   validity. Membership dates do not prove ticker validity.
4. `evidence_filed_date` was populated from `latest_relevant_filing` (often
   8-K), not a filing date for the identity facts; `form` was empty.
5. Candidate CIK is not verified CIK.
6. The 19-metric CompanyFacts panel is not the full raw filing XBRL; it omits
   cover-page DEI identity tags such as `dei:TradingSymbol`.
7. P17.1 had 10 tests, not 30+.

These are source/pipeline corrections, not a change to P17.1's DATA_BLOCKED
conclusion.
