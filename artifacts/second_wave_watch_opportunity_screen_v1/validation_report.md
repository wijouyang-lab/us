# Validation Report — Second Wave Screen V1

Date: 2026-11-27

## Tests

```text
pytest -q tests/test_second_wave.py
7 passed
```

Covered:
1. 25 unique reviewed tickers.
2. 4 shortlisted, 21 rejected, all historical WATCH preserved.
3. No PAPER_CANDIDATE.
4. Scenario formula `equity = FCF × multiple − net debt`.
5. Price dates 2026-11-25.
6. 25 SEC sources.
7. No SNDK/EBS/CCS in shortlist.

## Data caveats

- Base multiple is a uniform 16x screen assumption; scenario multiples vary.
- SNDK FCF > revenue is a data outlier and rejected.
- IMMR FCF may include licensing/litigation timing; flagged.
- No full 10-K normalization for the 4 shortlisted names.
- No PIT, no adjusted total-return prices.
- No PAPER/IBKR/orders.

## Result

- 4 second-wave research names: IMMR, OPRX, PHR, NATR.
- 21 rejected from further research at this stage.
- 0 PAPER candidates.
