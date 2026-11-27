# Validation Report — Four PRIORITY_WATCH V2

Date: 2026-11-27

## Automated tests

```text
pytest -q tests/test_four_review.py
....... [100%]
7 passed in 0.37s
```

Covered:

1. 195 rows corrected from `DATA_UNAVAILABLE` to `NOT_EVALUATED`.
2. Corrected 28,000 ledger counts: 1,342 CANDIDATE / 26,463 EXCLUDED / 195 NOT_EVALUATED.
3. Scenario formula `equity = FCF × multiple − net debt`; all four net cash.
4. Latest price date 2026-11-25.
5. Four WATCH decisions; zero PAPER.
6. Four SEC source URLs.
7. 20 financial rows (3 FY / latest Q / TTM per company).

## 195 reconciliation

`accounting_195_reconciliation.csv` preserves:

- `old_status = DATA_UNAVAILABLE`
- `new_status = NOT_EVALUATED`
- reason `NO_EVALUATION_PERFORMED_NOT_A_DATA_CHECK`

No data check was performed for these combinations; they were not evidence of
missing data. Corrected ledger: `candidate_accounting_28000_corrected.csv`.

## Real data checks

- RELY: $136M deferred-tax release flagged; SBC $155.1M; P/E 12.8 not normalized.
- FIVE: $169.5M IEEPA tariff refund flagged; comp +14.1%; reported gross margin 48.5% vs normalized ~35.6%.
- USLM: Q3 price +2.5%, volume +1.6%; 22.5x P/E.
- FIZZ: Q1 price +7.1%, volume −6.4%; gross margin ~35%.

## Limitations

- Third-year values were available for all four, but FCF is not presented for
  every historical FY due capex tag gaps.
- No full 10-K line-by-line read for every risk factor; material items were read
  from 10-Q/10-K extracts and SEC facts.
- Prices unadjusted; no total-return claim.
- No PIT, no forward model, no orders.
