# Price Recovery Audit and Current Gate Result

Date: 2026-10-28
Research only. No production changes.

## Recovery status for 98 failed tickers

Machine-readable file:

`docs/research/price_recovery_audit_2026-10-28.csv`

| Status | Count |
|---|---:|
| `identity_only` | **98** |
| `recovered_but_unverified` | 0 |
| `recovered_and_validated` | 0 |
| `no_usable_free_source_found` | 0 |
| `unresolved_identity` | 0 |

All 98 have verified CIK/membership identity and **zero** valid OHLCV rows in
the existing independent price panel. Identity verification is not price
recovery.

Fields include:

```text
ticker
identity_verified
membership_verified
price_source
valid_ohlcv_rows
first_valid_date
last_valid_date
adjusted_price_available
corporate_actions_verified
independent_crosscheck_available
recovery_status
evidence_url
failure_reason
```

`adjusted_price_available`, `corporate_actions_verified`, and
`independent_crosscheck_available` are all false: no source has been verified
for these fields.

## Current PIT gate result

Input:

`docs/research/pit_gate_current_input_2026-10-28.json`

Output:

`docs/research/pit_gate_current_result_2026-10-28.json`

Command:

```bash
python tools/research/pit_recovery_gate.py \
  --input docs/research/pit_gate_current_input_2026-10-28.json \
  --require-stage data
```

Exit code: **1**

```text
eligible_to_resume_full_history_pit_research: false
strategy_validation_ready: false
production_deployment_ready: false
```

Reasons:

- member-session coverage 91.61% < 95%
- ticker coverage 84.23% < 98%
- 0/98 failed tickers have verified OHLCV
- no independent OHLCV source
- no cross-source Close validation
- corporate-action audit incomplete
- PIT availability audit not passed

The gate correctly fails closed. It also confirms the stage split: data recovery
is not blocked by the missing 12 OOS windows or alpha CI.

## Membership coverage

Annual and per-ticker outputs are under:

`docs/research/membership_coverage_2026-10-28/`

See the analysis:

`docs/research/MEMBERSHIP_COVERAGE_2026-10-28.md`

Key result: membership data adds 381鈥?91 historical names at full-history level
but **zero** of the 218鈥?28 new names inside the 10-year price window have
prices. Membership cannot fill OHLCV gaps.

## Decision

The data-research stage is still blocked. Do not resume full-history PIT
strategy validation and do not treat current-universe results as deployable
alpha.

No production scanner, scoring, stop, ledger, order path, or external trigger
was modified.
