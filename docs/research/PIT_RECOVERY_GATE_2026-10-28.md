# Three-stage PIT research and deployment gates

Date: 2026-10-28  
Scope: research only. This gate does not change production behavior.

## Why three stages

The previous gate required 12 OOS windows and positive benchmark-adjusted alpha
before **resuming data recovery**. That is circular: strategy evidence cannot
exist until the historical data is recovered.

The gate now has three independent stages:

1. **Data research readiness** — may resume historical data recovery.
2. **Strategy validation** — may validate a strategy; requires data readiness
   plus OOS/cost evidence.
3. **Production deployment** — requires strategy validation plus risk,
   regression, paper-trading, and human review.

A failing strategy stage does **not** block data recovery.

## Stage 1: data research gates

All must pass:

1. Member-session bar coverage >= 95%.
2. At least 98% of tickers have >= 90% individual coverage.
3. Missing member-session bars <= 2% of expected.
4. At least 98% of missing historical tickers have verified identity/membership
   and verified OHLCV history.
5. An independent OHLCV source is verified; re-reading Yahoo is not enough.
6. Maximum absolute Close difference on matched dates <= 0.5% after corporate
   action adjustment.
7. Zero unexplained corporate-action breaks.
8. PIT availability-time audit passes.

Passing this stage permits data recovery. It does **not** prove alpha.

## Stage 2: strategy validation gates

All must pass, and data readiness is a prerequisite:

1. At least 12 independent, non-overlapping OOS windows.
2. Lower bound of benchmark-adjusted, cost-adjusted net alpha CI > 0.
3. Maximum drawdown <= 20%.
4. Robustness checks pass.

These are process gates, not a guarantee of statistical power. Dependence,
multiple-testing exposure, and sample maturity still require review.

## Stage 3: production deployment gates

All must pass, and strategy validation is a prerequisite:

1. Strategy validation ready.
2. Risk controls verified.
3. Production regression tests passed.
4. Paper-trading days >= 40.
5. Human review approved.

Passing the data or strategy stage never authorizes production deployment.

## Current snapshot

Using the figures in `DATA_COVERAGE_AUDIT_2026-10-28.md`:

- Expected member sessions: 1,278,758
- Observed: 1,171,451 (91.61%)
- Tickers: 704
- Tickers at >=90% coverage: 593 (84.23%)
- Missing historical tickers: 98; verified identity + OHLCV: 0
- Independent OHLCV source: not verified
- Matched Close difference: unavailable
- Corporate-action audit: incomplete
- PIT availability audit: not passed
- OOS windows: 9; benchmark-adjusted net alpha CI lower: not positive

Current result:

```text
data_research: false
strategy_validation: false
production_deployment: false
```

No gate is relaxed to make the current data pass.

## Input example

```json
{
  "member_sessions_expected": 1278758,
  "member_sessions_observed": 1171451,
  "ticker_total": 704,
  "tickers_at_least_90pct_coverage": 593,
  "missing_historical_tickers_total": 98,
  "missing_historical_tickers_with_verified_identity_and_ohlcv": 0,
  "independent_ohlcv_source_verified": false,
  "max_abs_close_difference_pct": null,
  "unexplained_corporate_action_breaks": null,
  "pit_availability_audit_passed": false,
  "independent_nonoverlapping_oos_windows": 9,
  "benchmark_adjusted_net_alpha_ci_lower": null,
  "max_drawdown_pct": null,
  "robustness_checks_passed": false,
  "risk_controls_verified": false,
  "production_regression_tests_passed": false,
  "paper_trading_days": 0,
  "human_review_approved": false
}
```

Run:

```bash
python tools/research/pit_recovery_gate.py \
  --input pit_audit_summary.json \
  --require-stage data
```

`--require-stage data` exits 0 only when data recovery may resume.
`--require-stage strategy` and `--require-stage production` are separate
downstream decisions. Exit code 1 means the selected stage fails; invalid or
inconsistent input raises a clear error.

## Operational decision

- Data recovery may start only after Stage 1 passes.
- Strategy validation may start only after Stage 1 passes **and** its own gates
  pass.
- Production deployment is a third, independent human-reviewed decision.
- Do not delete missing tickers, impute prices, alter denominators, or
  substitute successor-company prices.
- Keep current-survivor-universe experiments exploratory and isolated.
- Do not merge this research work as evidence of deployable alpha.
- Do not change production scanner, scoring, stops, ledger, or external trigger.
