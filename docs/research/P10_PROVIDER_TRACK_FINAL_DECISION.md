# P10 Provider Track Final Decision

Date: 2026-11-16
Branch: `research/p10-data-provider-evaluation`
Status: **FINAL RESEARCH RECORD — NO PURCHASE**

---

## 1. Frozen facts

```text
P9_TICKER_POOL: NOT_REPRODUCIBLE
P9_TICKER_POOL_SIZE: 1160
P9_TICKER_POOL_SHA256: NOT_AVAILABLE
P9_MEMBER_DAY_GATE: 95%
P9_TICKER_GATE: 98%

IDENTITY_CONFIRMED: 2 / 80
IDENTITY_CONFLICT: 9 / 80
IDENTITY_PARTIAL: 7 / 80
IDENTITY_UNRESOLVED: 62 / 80

FREE_RESEARCH_TICKER_COVERAGE: 93.69%
LICENSE_CLEARED_PRODUCTION_COVERAGE: 0%

PURCHASE_DECISION: NO_BUY
PRODUCTION_DEPLOYMENT_READY: false
ALL_P9_STRATEGIES: NO_GO
```

Do not substitute 887, 921, 1,062 or the earlier unverified 1,096 for the
original 1,160 pool. The historical pool cannot be recovered from the current
files.

---

## 2. Reproduced facts

### P9 snapshot baseline

```text
snapshot rows:       2,198
member-days:     1,095,490
valid close:       986,358
verified tradable: 981,362
verified coverage:    89.58%
```

### Daily-expanded baseline

```text
SPY trading days:   4,429
member-days:    2,220,522
positive close: 2,113,080
coverage:           95.16%
```

### Pool sizes

```text
current 2000-2024 deduplicated snapshot union: 1,062
current 2007-2024 daily union:                    887
P8.2 table rows:                                1,062
P8.2 valid-price rows:                            918
P9 recorded expected pool:                      1,160
```

`1,062` is both the deduplicated snapshot union and the P8.2 table row count;
only 918 P8.2 rows have valid prices. Neither is the original 1,160 pool.

---

## 3. Identity status

The 80-row identity base table remains the complete zero-member-day audit table.

The 18-row `p10_5_3_historical_ticker_identity.csv` contains only classified
exceptions:

```text
2 confirmed share classes
9 ticker-reuse conflicts
7 partial acquired/bankrupt/renamed cases
```

It is **not** a replacement for the 80-row base table.

The 9 `C_TICKER_REUSE` cases are **identity conflicts / potential ticker reuse
risks**. Transfer events are not verified; no historical transfer date is
asserted without evidence.

Identity metrics have two distinct meanings:

```text
zero-coverage ticker identity confirmed: 2 / 80
newly confirmed among 887 research tickers: 2 / 887
```

The 2/887 figure is not a full identity audit of all 887 tickers.

---

## 4. Coverage classes

```text
free research coverage: 831 / 887 = 93.69% tickers
free member-day:      2,124,882 / 2,220,522 = 95.69%
identity-confirmed:       2 / 887 = 0.23%
license-cleared production: 0 / 887 = 0%
```

No observation with unresolved identity or unclear licence counts as production
coverage. Research coverage and production coverage are not interchangeable.

---

## 5. EODHD $19.99/month gap

EODHD Historian does not solve:

- the unrecoverable 1,160 P9 pool;
- the 9 identity conflicts;
- the 62 unresolved identities;
- historical S&P 500 PIT membership (add-on excluded);
- historical price vintage;
- public/team licence use;
- the 98% ticker gate from the current free union.

It was never purchased or trialled.

```text
EODHD_PAID_COVERAGE: UNVERIFIED
EODHD_PIT_MEMBERSHIP: NOT INCLUDED
EODHD_PRICE_VINTAGE: NOT AVAILABLE
```

---

## 6. Purchase reconsideration conditions

Reconsider only if **all** hold:

1. a specific critical gap is clearly identified and closed;
2. the recovered data is linked to the correct legal entity;
3. coverage meets 95% member-day and 98% ticker on the frozen baseline;
4. licence permits the intended private use;
5. total cost ≤ $20;
6. subscription ≤ one month;
7. no VPS required;
8. downloaded data can be retained legally after cancellation;
9. PIT and price-vintage limitations are documented separately.

Until then:

```text
NO_BUY
```

---

## 7. Replay status

Local replay script:

`tools/research/p10/replay_p9_baseline.py`

It verifies SHA-256 of all four inputs, including
`p8_2/pit_coverage_by_ticker.csv`, audits duplicate dates before
deduplication, and recomputes:

```text
snapshot_member_days: 1,095,490
snapshot_valid:         986,358
daily_member_days:    2,220,522
daily_valid:          2,113,080
```

Local result: `data/research/p10_5_3_replay_result.json`.

```text
input_hashes_verified: true
duplicate_date_audit_passed: true
duplicate_dates: 0
snapshot_replay_status: PASS
daily_replay_status: PASS
all_expected_matched: true
ci_replay: false
CI_REPLAY_NOT_EXECUTED
```

The 981,362 verified-tradable figure is from the P8.2 policy and was **not**
recomputed by this script.

CI cannot read the raw files because they are not in the public repository. The
input hashes are registered, but the CI process has not independently replayed
the calculation. Do not describe hash registration as a CI replay.

---

## 8. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P9_TICKER_POOL: NOT_REPRODUCIBLE
P9_MEMBER_DAY_GATE: 95%
P9_TICKER_GATE: 98%
FREE_RESEARCH_TICKER_COVERAGE: 93.69%
LICENSE_CLEARED_PRODUCTION_COVERAGE: 0%
IDENTITY_CONFIRMED: 2 / 80
IDENTITY_CONFLICT: 9 / 80
IDENTITY_PARTIAL: 7 / 80
IDENTITY_UNRESOLVED: 62 / 80
PURCHASE_DECISION: NO_BUY
PRODUCTION_DEPLOYMENT_READY: false
ALL_P9_STRATEGIES: NO_GO
P9_RESULTS: ALL 8 NO-GO
```

No purchase, registration, trial, VPS, private repository or raw-data upload.
