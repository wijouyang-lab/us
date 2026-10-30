# Research Status Master 鈥?Phase 2.1鈥?.9

Date: 2026-10-30
Research only. No production changes. No deployable alpha.

Machine-readable source:

```text
data/research/research_status.json
```

## Status table

| Phase | Area | Evidence | Data | PIT | Statistical | Portfolio | Deployment |
|---|---|---|---:|---|---|---|---|
| 2.1 | data_quality_audit | 1 | partial | failed | n/a | not_tested | not_eligible |
| 2.2 | forward_returns | 1 | partial | failed | n/a | not_tested | not_eligible |
| 2.3 | technical_walkforward | 1 | partial | failed | provisional | invalid_overlapping_cohorts | not_eligible |
| 2.4 | unified_factor_engine | 1 | available | failed | n/a | not_tested | not_eligible |
| 2.5 | factor_ic | 2 | available | failed | FDR 60D vol only | not_tested | not_eligible |
| 2.6 | historical_universe | 1 | partial | failed | n/a | not_tested | not_eligible |
| 2.7 | volatility_portfolios | 0 | available | failed | superseded | invalid_short_accounting | not_eligible |
| 2.7.1 | volatility_accounting_audit | 1 | available | failed | corrected descriptive | audited short accounting | not_eligible |
| 2.7.2 | research_accounting_audit | 1 | available | failed | n/a | not_tested | not_eligible |
| 2.7.3 | accounting_integration | 1 | available | failed | partial | overlap_unresolved | not_eligible |
| 2.7.4 | nonoverlap_portfolio | 3 | available | failed | tested no stable edge | non-overlapping tested no pass | not_eligible |
| 2.8 | event_macro | 1 | partial | failed | insufficient sample | not_tested | not_eligible |
| 2.9 | pit_timestamp_vintage | 1 | unavailable | failed | n/a | not_tested | not_eligible |

## Confirmed facts

1. The current 503-name panel is not a historical PIT universe.
2. Phase 2.5's 60D factor statistics are cross-sectional evidence, not
   tradeable strategy returns.
3. Phase 2.7's original short accounting is invalid; use 2.7.1.
4. Phase 2.7.3's overlapping cohorts are not a real portfolio CAGR.
5. Phase 2.7.4 is the current non-overlapping comparison, but still
   survivorship-biased.
6. Phase 2.8's 150 SEC events are a descriptive sample, not event alpha.
7. Phase 2.9 found 0 verified SEC first-public times and 0 verified macro vintages.
8. No fully validated deployable alpha exists.

## Evidence levels

- Level 0: data unavailable.
- Level 1: exploratory.
- Level 2: statistical support (Phase 2.5 only for 60D volatility factors).
- Level 3: non-overlapping capital/cost portfolio test (Phase 2.7.4; no pass).
- Level 4: strict PIT (none).
- Level 5: production eligible (none).

## Data recovery gates

### Historical universe
Official/verifiable membership, effective dates, company identity, delisting
and corporate actions, historical prices, delisting returns.

### SEC events
Verified first-public timestamp, historical company identity, no acceptance-time
substitution.

### Macro
ALFRED/FRED vintage, first-release value, revision history, release timestamp.

### Analyst expectations
Historical point-in-time expectations and release dates.

Each gate must be machine-checked before any PIT claim.

## Strategy Lab

The page must not show exploratory factors as formal rankings, must keep the
survivorship label, state costs, date range, PIT status and sample limits.
No change is made in this phase.

## Conclusion

The project has built data/factor infrastructure and rejected several apparent
edges. It has **not** produced a deployable strategy. The binding constraints are
historical membership, delisting returns, first-public timestamps and macro
vintages 鈥?not further parameter tuning.
