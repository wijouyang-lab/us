# Validation Report — Three-Candidate Audit

Date: 2026-11-27

## Tests

```text
pytest -q tests/test_three_audit.py
....... [100%]
7 passed
```

Covered:

1. 14 deliverable files present.
2. IMMR scenario is `NOT_ESTIMABLE`; no FCF assigned.
3. PHR adjusted FCF = reported 80.747M − SBC 67.5M = 13.247M.
4. OPRX adjusted FCF = 19.889M − 7.0M = 12.889M.
5. Scenario formula `equity = FCF × multiple − net debt`.
6. Price date 2026-11-25.
7. 3 final decisions; 0 PAPER.

## Data checks

- IMMR: parent revenue 15.924M + BNED 1,714.770M; NCI 67.4%; no parent-only FCF.
- PHR: SBC 67.5M = 84% of TTM FCF; capitalized software 13.3M already in capex.
- OPRX: OCF 19.889M; SBC 7.0M; top five ~47%; one 10% customer no current-period revenue.
- No zero-filled missing values.
- No adjusted-price total-return claim.
