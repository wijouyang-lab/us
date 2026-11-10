# Final Research Acceptance Audit

Date: 2026-10-28
Research only. No production changes.

## Scope

Audit the claims in PR #399 against source artifacts. Do not rerun experiments
without a reproducible defect.

## Claim-by-claim verification

| Claim | Source | Verification |
|---|---|---|
| 399 formula candidates, no positive BH/BY q<0.05 | run `40328953758` aggregate artifact `formula_factor_extended_report.json` | **verified**: 399 unique candidates, 1,197 candidate-horizon rows, 0 positive q<0.05 |
| Best positive 20D formula 3.1839%, q 0.06687 | same aggregate | **verified**; report corrected from an older 2.81%/0.546 figure |
| Qlib fixed 39.85%, Sharpe 2.78 | `QLIB_BACKTEST_AUDIT_2026-10-28.md` | documented; not independently rerun because raw Qlib result file is not committed |
| Qlib walk-forward 13.24%, Sharpe 0.69, t 0.64 | same audit report | documented; not independently rerun |
| 466 candidate table and benchmark | `restricted_466_factor_validation_2026-10-28.json/csv` | **verified**: 1,179,912 rows, 466 tickers, 2,532 sessions; values match report |
| 466 BH q values 0.128/0.128/0.334/0.164/0.334 | same JSON | **verified** |
| Benchmark 14.31%, Sharpe 0.855, maxDD -21.60% | same JSON | **verified** |
| PIT coverage 91.61%, ticker coverage 84.23% | `DATA_COVERAGE_AUDIT_2026-10-28.md` | **verified from audit report**; source PIT denominator 1,278,758 / 1,171,451 |
| Survivorship bias / no adjusted close | 466 result JSON `label`; panel schema | **verified** |
| 35 event sample, 0 entry/+1/+5 | archive run `40661139681`; SPY readiness JSON | **verified** |
| Event sample not eligible | `event_experiment_gate_2026-10-28.json` | **verified** |

## What is reproducible

- 399 formula aggregate: 399 unique candidates, 0 positive BH/BY q<0.05; best
  positive 20D turnover-aware net 3.1839%, q=0.06687.
- 466 five-factor table, benchmark, BH q, costs and turnover.
- Event sample count and 0/0/0 horizon coverage.
- Data coverage percentages and survivorship/raw-price limitations.

## What is not independently reproducible from stored files

- Qlib fixed/walk-forward metrics are taken from the committed audit report;
  the raw per-period Qlib result JSON is not in the main research tree.
- This does **not** invalidate the report, but those two rows should be treated
  as documented-audit evidence rather than a fresh reproduction.

## Conclusion correctness

The report does **not** call any of the following alpha:

- positive but non-significant factors;
- fixed Qlib result without walk-forward;
- high-vol result with market beta;
- survivorship-biased equal-weight benchmark.

It explicitly states:

```text
No reliable alpha.
No deployable strategy.
No paper-trading candidate.
```

Correct.

## Required correction

PR #399 needed one number correction:

- old: best 399-formula positive ~2.81%, q~0.546
- corrected: **3.1839%, q=0.06687**

This correction has been applied to the report and JSON.

## Tests / CI

- PR #399 CI: **1325 passed, 1 skipped** on the final PR commit before this
  audit correction; CI must be re-run after the correction.
- No production path changed.

## Remaining data limitations

- 10/28 official close: pending at audit time.
- Second real cross-day event run: not executed.
- Event sample: 35 < 200; 0 complete +1/+5.
- 466 panel: current-universe, survivorship-biased, raw OHLCV.
- No independent adjusted-close/corporate-action validation for the 466 panel.

## Acceptance decision

**Conditionally accepted after the 399 number correction.**
No alpha claim, no deployment, no paper-trading candidate.

PR #399 remains Draft; no auto-merge.
