# Full-history PIT recovery gate

Date: 2026-10-28  
Scope: research only. This gate does not change production behavior.

## Purpose

`tools/research/pit_recovery_gate.py` turns the predeclared recovery conditions into a fail-closed, machine-checkable decision. It reads a JSON audit summary and never fetches, fills, or modifies market data.

A passing result means only that the full-history PIT research process may resume. It does **not** authorize production deployment or prove alpha.

## Gates

All gates must pass:

1. Member-session bar coverage >= 95%.
2. At least 98% of the defined ticker set has >= 90% individual coverage.
3. Missing member-session bars <= 2% of expected bars.
4. At least 98% of unresolved historical tickers have both verified identity/membership evidence and verified OHLCV history.
5. A truly independent OHLCV source has been verified (re-reading Yahoo through another package does not qualify).
6. Maximum absolute Close difference on matched dates <= 0.5% after corporate-action adjustment.
7. Zero unexplained corporate-action breaks.
8. PIT availability-time audit passes.
9. At least 12 independent, non-overlapping out-of-sample windows.
10. The lower bound of the benchmark-adjusted, cost-adjusted net alpha confidence interval is greater than zero.

The 12-window threshold is a minimum process gate, not a guarantee of statistical power. All return calculations, dependence assumptions, multiple-testing exposure, and sample maturity still require review.

## Current snapshot

Using the audit figures currently recorded in `DATA_COVERAGE_AUDIT_2026-10-28.md`:

- Expected member sessions: 1,278,758
- Observed member sessions: 1,171,451 (91.61%)
- Tickers: 704
- Tickers with >= 90% coverage: 593 (84.23%)
- Unresolved historical tickers: 98; verified historical identity + OHLCV: 0
- Independent OHLCV source: not verified
- Matched Close difference: unavailable
- Corporate-action audit: incomplete
- Full-history PIT availability audit: not passed
- Independent non-overlapping OOS windows: 9
- Positive lower confidence bound for benchmark-adjusted net alpha: not established

This snapshot must fail closed. No coverage gate is relaxed to make the current data pass.

## Input schema example

Save an audit summary as JSON, then run:

```bash
python tools/research/pit_recovery_gate.py --input path/to/pit_audit_summary.json --output path/to/pit_gate_result.json
```

Example shape:

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
  "benchmark_adjusted_net_alpha_ci_lower": null
}
```

Exit code `0` means every research-resumption gate passes; exit code `1` means at least one gate fails. Invalid or inconsistent input raises a clear error rather than silently accepting the report.

## Operational decision

- Keep complete historical PIT model validation frozen until all gates pass.
- Current-survivor-universe experiments remain exploratory and isolated.
- Do not delete missing tickers, impute prices, alter denominators, or substitute successor-company prices.
- Do not merge this research work as evidence of deployable alpha.
- Do not change production scanner, scoring, stops, ledger, or external trigger.
