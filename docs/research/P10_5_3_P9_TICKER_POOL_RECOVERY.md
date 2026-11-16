# P10.5.3: P9 Ticker Pool Recovery and Identity Closeout

Date: 2026-11-16
Branch: `research/p10-data-provider-evaluation`
Status: **FORENSIC AUDIT ONLY — NO PURCHASE, NO TRIAL, NO VPS**

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P9_TICKER_POOL: NOT_REPRODUCIBLE
P9_RESULTS: ALL 8 NO-GO
```

---

## 1. Can the 1,160 ticker pool be recovered?

Search scope:

- current P10 branch and PR512 worktree;
- `sp500_daily.csv`, P8/P8.2 intermediate files;
- `universe_membership.csv`;
- P8.2 `pit_coverage_by_ticker.csv`;
- Git history/worktrees;
- P9/P8 documentation and scripts;
- local audit artifacts.

No file, commit, branch, script output or manifest containing a 1,160-ticker
expected pool was found.

Current reproducible pools:

```text
2000-2024 snapshot union: 1,096
2007-2024 snapshot union:   921
2007-2024 daily union:      887
P8.2 table rows:           1,062
P8.2 rows with valid price:  918
```

The `1,062` is the **row count** of `pit_coverage_by_ticker.csv`, not a valid
ticker count. The P9 statement `1,062 / 1,160` mixes a table row count with an
unrecoverable expected pool.

```text
P9_TICKER_POOL_1160: NOT_REPRODUCIBLE
SHA256_OF_1160_LIST: NOT_AVAILABLE
```

Do not substitute `1,096` or `887` for the original. Do not change P9.1 results.

### Proposed new baseline (not automatically adopted)

A versioned new baseline should use the daily-expanded definition:

```text
scope: 2007-05-30..2024-12-31
ticker union: 887
expected member-days: 2,220,522
source: frozen sp500_daily + spy files
```

This is a **proposal**, not a replacement for the historical P9 baseline.

---

## 2. Reproducible vs non-reproducible artifacts

File: `p10_5_3_baseline_reconstruction_manifest.csv`

| Artifact | Status |
|---|---|
| P9 snapshot denominator 1,095,490 | REPRODUCIBLE |
| P9 daily denominator 2,220,522 | REPRODUCIBLE |
| P9 ticker pool 1,160 | **NOT_REPRODUCIBLE** |
| P8.2 table 1,062 rows / 918 valid | REPRODUCIBLE TABLE, NOT POOL |
| Source hashes/bytes | RECORDED |

Exact snapshot reconstruction:

```text
2,198 snapshot rows
1,095,490 member-days
986,358 valid close
981,362 verified tradable
89.58% verified coverage
```

Exact daily reconstruction:

```text
4,429 trading days
2,220,522 member-days
2,113,080 positive close
95.16% coverage
```

The denominator difference is not a data improvement; it is a date-grid
definition difference.

---

## 3. Coverage definitions

| Definition | Numerator / denominator | Inputs / algorithm |
|---|---|---|
| Snapshot-observation | 986,358 / 1,095,490 | `sp500_daily` snapshot rows × tickers; positive `adjusted_close` |
| Verified-tradable | 981,362 / 1,095,490 | same, excluding zero/stale/corrupt/unresolved |
| Daily member-day | 2,113,080 / 2,220,522 | latest snapshot per SPY session, 2007-05-30..2024-12-31 |
| Valid OHLCV ticker | 807 / 887 | tickers with any valid member-day in daily expansion |
| Identity-confirmed ticker | 2 / 887 | BRK.B and BF.B only |
| License-cleared production | 0 / 887 | no vendor licence cleared for production/public use |

Do not average or select the highest. Original gates:

```text
member-day >= 95%
ticker >= 98%
```

The free research union is 831/887 = 93.69% ticker, still below 98%.

---

## 4. Nine identity conflicts

File: `p10_5_3_historical_ticker_identity.csv`

The V2 current SEC name is not the historical entity for these tickers:

| Ticker | Current V2/ SEC name | Expected historical entity | Result |
|---|---|---|---|
| LB | LandBridge Corp | L Brands | C_TICKER_REUSE |
| STI | Solidion Technology | SunTrust Banks | C_TICKER_REUSE |
| LLL | JX Luxventure | L3Harris | C_TICKER_REUSE |
| HCP | HashiCorp | HCP Inc | C_TICKER_REUSE |
| SE | Sea Ltd | legacy SE entity | C_TICKER_REUSE |
| TE | T1 Energy | TECO Energy | C_TICKER_REUSE |
| ALTR | Altair Engineering | Altera | C_TICKER_REUSE |
| BEAM | Beam Therapeutics | Beam Inc | C_TICKER_REUSE |
| PLL | Piedmont Lithium | Pall Corp | C_TICKER_REUSE |

Transfer dates are `NOT_VERIFIED`; no old-entity CIK is asserted where evidence
was not recovered. These V2 rows must not fill historical member-days.

---

## 5. Seven partial identities

| Ticker | Finding | Category |
|---|---|---|
| CA | CA Inc; acquisition event not re-fetched | B_ACQUIRED |
| EMC | EMC Corp; Dell acquisition not re-fetched | B_ACQUIRED |
| DTV | DirecTV; AT&T acquisition not re-fetched | B_ACQUIRED |
| DO | Diamond Offshore; bankruptcy event not re-fetched | B_BANKRUPT |
| SHLD | Sears Holdings; bankruptcy event not re-fetched | B_BANKRUPT |
| WYND | Wyndham Destinations / Travel + Leisure successor | C_RENAME |
| DNB | old/new Dun & Bradstreet entity | C_REORG |

These remain `IDENTITY_PARTIAL`, not confirmed.

The remaining 62 remain `UNRESOLVED`.

---

## 6. Share-class mapping

### BRK.B

```text
issuer: Berkshire Hathaway Inc.
issuer CIK: 1067983
class: Class B
canonical ticker: BRK.B
provider aliases: BRK-B
status: IDENTITY_CONFIRMED (share class)
```

### BF.B

```text
issuer: Brown-Forman Corp.
issuer CIK: 14693
class: Class B
canonical ticker: BF.B
provider aliases: BF-B; legacy BFB
status: IDENTITY_CONFIRMED (share class)
```

Normalization:

```text
BFB -> BF.B
BF-B -> BF.B
BRK-B -> BRK.B
```

The issuer CIK identifies the issuer, not a class-specific security ID. Local
FINSABER has no `BF.B`/`BRK.B` rows; V2 uses `BF-B`/`BRK-B`.

---

## 7. V2 status consistency

Updated fields:

- `p10_5_2_v2_incremental_ticker_diff.csv`
- `p10_5_2_verified_identity_crosswalk.csv`

Each has:

```text
identity_status_at_join
identity_status_after_review
```

At join:

```text
all 30 changed tickers: UNRESOLVED
```

After review:

```text
BRK.B: IDENTITY_CONFIRMED
BF.B:  IDENTITY_CONFIRMED
other 28: UNRESOLVED or prior status
```

The 24-new/6-existing count is unchanged:

```text
30 = 24 new coverage + 6 existing added
11,802 added member-days
```

### Licence

FINSABER-reproduce: Apache-2.0 dataset card; upstream rights not fully verified.

FINSABER-V2: `other / NOT CLEARED`.

Neither is admitted to production scanning.

---

## 8. Production coverage

```text
Free research ticker coverage:        831 / 887 = 93.69%
Identity-confirmed ticker coverage:     2 / 887 = 0.23%
License-cleared production coverage:    0 / 887 = 0%
```

The production number is zero because:

- V2 licence is not cleared;
- most identities are unresolved;
- no paid vendor data is licensed;
- PIT membership source is not independently verified.

Do not report 93.69% as production coverage.

---

## 9. Purchase decision

| Gate | Status |
|---|---|
| ≤ $20 | PASS |
| ≤ 1 month | PASS |
| No VPS | PASS |
| Free coverage reaches 98% | FAIL — 93.69% |
| Remaining tickers recoverable | UNVERIFIED |
| Legal entity confirmed | FAIL — 2/80 |
| Baseline reproducible | PARTIAL — pool 1,160 missing |
| PIT membership | FAIL — not in Historian |
| Price vintage | FAIL |
| Public licence | FAIL — V2 other |

```text
NO_BUY
```

The paid candidate does not repair the unrecoverable 1,160 pool or the identity
conflicts. It cannot be justified until the baseline is frozen and identity
evidence is complete.

---

## 10. Final status

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P9_SNAPSHOT_DENOMINATOR: REPRODUCIBLE
P9_DAILY_DENOMINATOR: REPRODUCIBLE
P9_TICKER_POOL: NOT_REPRODUCIBLE
P9_TICKER_POOL_SHA256: NOT_AVAILABLE
IDENTITY_CONFIRMED: 2 / 80
IDENTITY_CONFLICT: 9
IDENTITY_PARTIAL: 7
IDENTITY_UNRESOLVED: 62
V2_INCREMENT: 24 NEW + 6 EXISTING; 11,802 MEMBER-DAYS
FREE_RESEARCH_TICKER_COVERAGE: 93.69%
IDENTITY_CONFIRMED_TICKER_COVERAGE: 0.23%
LICENSE_CLEARED_PRODUCTION_COVERAGE: 0%
P9_MEMBER_DAY_GATE: 95%
P9_TICKER_GATE: 98%
P9_DATA_REPRODUCIBILITY: BLOCKED UNTIL BASELINE RECONCILED
P9_RESULTS: ALL 8 NO-GO
```

No purchase, registration, trial, VPS, private repository or raw market data.
