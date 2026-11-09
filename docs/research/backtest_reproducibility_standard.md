# Backtest Reproducibility Standard

Date: 2026-11-09
Status: **P9_2_3_STANDARD_ESTABLISHED**
P9.1: **P9_1_ORIGINAL_RESULT_NOT_REPRODUCIBLE**

## 1. P9.1 final trace

Checked:

- P9.1 HEAD `9b07f588dd5af05017d2d4cba36ae87a23d9460a`;
- committed strategy/portfolio code;
- committed `p9_1_signals.csv.gz`;
- committed P9.1 JSON/artifacts;
- current raw price file;
- cost model;
- PR #512 history.

Missing / insufficient:

- no immutable SHA-256 of the price file at P9.1 runtime;
- no record of the exact raw-price version;
- no stored open positions or full daily ledger;
- no run manifest at the time;
- P9.2.2 replay order counts differ (A 856 vs 782; C 568 vs 553).

Therefore:

```text
ORIGINAL_RESULT_REPORTED:       YES
ORIGINAL_RESULT_REPRODUCED:     NO
ORIGINAL_RESULT_VERIFIED:       NO
ORIGINAL_RESULT_NOT_REPRODUCIBLE: YES
```

P9.1 CAGR/MaxDD remain historical **reported** values, not independently verified.
No attempt was made to tune rules to match them.

## 2. P9.2.2 independent reconciliation

The existing daily NAV was not used to recompute itself. Orders were replayed
from the ledger:

- initial cash $10,000;
- BUY cash decrement with fees;
- SELL cash increment with fees;
- share positions per ticker;
- BIL units × BIL price;
- stock mark-to-market;
- open positions retained;
- unmatched sells checked.

Results:

| Strategy | Max abs NAV diff | Mean abs NAV diff | Unmatched sells | Open positions |
|---|---:|---:|---:|---:|
| A | 2.18e-11 | 5.35e-12 | 0 | 1 |
| B | 7.28e-12 | 7.55e-13 | 0 | 1 |
| C | 1.46e-11 | 2.45e-12 | 0 | 4 |
| D | 1.46e-11 | 2.33e-12 | 0 | 1 |
| E | 2.18e-11 | 5.73e-12 | 0 | 0 |
| F | 2.18e-11 | 3.77e-12 | 0 | 0 |
| G | 1.46e-11 | 2.45e-12 | 0 | 4 |
| H | 2.18e-11 | 3.77e-12 | 0 | 0 |

Status:

```text
INDEPENDENT_RECONCILIATION_PASS
```

This verifies the P9.2.2 ledger internally, **not** P9.1.

## 3. Fixed cost definitions

```text
fees_only = commission + exchange_fee + regulatory_fee
BUY slippage  = quantity × (execution - reference)
SELL slippage = quantity × (reference - execution)
all_in = fees_only + slippage
```

Fees enter cash. Slippage is embedded in execution price; it is not deducted
from NAV twice. Negative slippage is allowed.

## 4. Run manifest

Every future run must emit:

```text
run_manifest.json
data_manifest.json
signal_log.csv
trade_ledger.csv
round_trip_trades.csv
open_positions.csv
daily_nav.csv
cost_reconciliation.csv
performance_metrics.json
run_status.json
```

Manifest required fields are in:

- `run_manifest.schema.json`
- `run_manifest_example.json`

It records commit, dirty status, diff hash, Python, dependency lock, source
hashes, cost model, parameters, dates, calendar, timezone, execution rule,
command, seed, initial capital, output hashes and status.

If any required output or input hash is missing, status must be
`NOT_REPRODUCIBLE`.

## 5. Test requirements

Implemented:

- same input hashes produce same signal/order concept (hash-level test);
- independent cash rebuild;
- independent position rebuild;
- independent NAV rebuild;
- fees sum;
- slippage once;
- open positions not sold;
- mini ledger: buy, partial sell, full sell, open position, unmatched sell;
- missing-key downgrade.

## 6. Decision

```text
P9.1 exact reproduction:      STOPPED / NOT REPRODUCIBLE
P9.2.2 ledger independent:    PASS
New runs must use manifest:   YES
P9.1 strategy:                NO-GO
```

No more time is to be spent reconstructing P9.1's original runtime.

## 7. Files

```text
data/research/p9_2_3_reproducibility/
  run_manifest.schema.json
  run_manifest_example.json
  ledger_independent_reconciliation.csv
  ledger_independent_daily.csv
  reproducibility_audit.json
docs/research/backtest_reproducibility_standard.md
tests/test_p9_2_3_reproducibility.py
```
