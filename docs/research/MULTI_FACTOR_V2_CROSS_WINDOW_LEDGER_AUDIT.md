# V2 Cross-Window Independent Ledger Audit

Date: 2026-11-25
PR: #626
Branch: `research/multi-factor-strategy-competition-v1`

## 1. Independent reconstruction

A separate script rebuilt cash and market value from the trade ledgers for all
9 strategy/window combinations. It did not call the engine NAV function.

| Window | Strategy | Ledger rows | Closed | Open | Max NAV diff |
|---|---|---:|---:|---:|---:|
| 5Y | A | 400 | 390 | 10 | 2.91e-11 |
| 5Y | B | 407 | 397 | 10 | 5.82e-11 |
| 5Y | C | 413 | 403 | 10 | 5.82e-11 |
| 3Y | A | 288 | 278 | 10 | 4.37e-11 |
| 3Y | B | 287 | 277 | 10 | 3.64e-11 |
| 3Y | C | 294 | 284 | 10 | 2.91e-11 |
| 1Y | A | 107 | 97 | 10 | 3.64e-11 |
| 1Y | B | 112 | 102 | 10 | 2.18e-11 |
| 1Y | C | 115 | 105 | 10 | 4.37e-11 |

All differences are below 1e-10 USD.  
`OPEN_AT_END` positions are marked and not given fake sell fees.

## 2. Price gaps

`raw_close` is used for all executions; `mark_close` (ffill limit 5) only for
valuation. Stats from the final run:

| Window | Strategy | Skipped buys | Delayed exits | Stale holding days |
|---|---|---:|---:|---:|
| 5Y | A | 323 | 0 | 0 |
| 5Y | B | 157 | 0 | 0 |
| 5Y | C | 260 | 0 | 0 |
| 3Y | A | 264 | 0 | 0 |
| 3Y | B | 121 | 0 | 0 |
| 3Y | C | 216 | 0 | 0 |
| 1Y | A | 104 | 0 | 0 |
| 1Y | B | 54 | 0 | 0 |
| 1Y | C | 97 | 0 | 0 |

No delayed exits occurred in these snapshots. Skipped buys are candidates with
no real close on the execution day; they were not filled at stale prices.

`max_age` is reported as 0 by the current counter, which is not a fully
instrumented stale-age measure. That remains an audit gap.

## 3. Results

A 5Y unchanged: 9.83% CAGR, -14.15% MaxDD, 0.777 Sharpe (rf=0), 400 trades.

## 4. Status

```text
AUDIT = PARTIAL
```

Nine-group NAV reconciliation passes; synthetic behavior suite and full
stale-age instrumentation are still incomplete. No PAPER authorization.
