# P10.5.2: P9 Baseline Freeze, V2 Increment Correction and Identity Audit

Date: 2026-11-16
Branch: `research/p10-data-provider-evaluation`
Status: **AUDIT ONLY — NO PURCHASE, NO TRIAL, NO VPS**

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P9_BASELINE: PARTIALLY REPRODUCIBLE / TICKER POOL NOT_REPRODUCIBLE
IDENTITY_CONFIRMED: 2 / 80 EVIDENCE-BASED
P9_RESULTS: ALL 8 NO-GO
```

---

## 1. Baseline source manifest

File: `p10_5_2_source_manifest.csv`

| File | Bytes | Rows | Version / source |
|---|---:|---:|---|
| `sp500_daily.csv` | 5,533,628 | 2,720 | fja05680/sp500 commit `a2430f2...`; MIT repo metadata; third-party rights unverified |
| `spy.csv` | 189,975 | 6,311 | P9.1 repo, PR512 HEAD `9b07f58...` |
| `finsaber_prices_raw.csv` | 265,180,873 | 4,736,109 | FINSABER-reproduce commit `ba3a690...`; Apache-2.0 dataset card |
| `data_audit.json` | 564 | 1 | P9.1 repo |
| `pit_coverage_summary.json` | 499 | 1 | P8.2 repo |
| `pit_coverage_by_ticker.csv` | 36,617 | 1,062 | P8.2 repo; table rows, not valid-ticker count |

Hashes are in the manifest. Raw files are **not** committed.

---

## 2. P9 denominator: 2,198 vs 4,429

### P9 snapshot-observation baseline

```text
sp500_daily.csv rows used: 2,198
expected member-days:       1,095,490
valid close:                  986,358
verified tradable:            981,362
verified coverage:             89.58%
```

The P9 denominator is the sum of tickers over **irregular membership snapshot
rows**. It is not a daily member-day count.

### Daily-expanded rebuild

```text
SPY trading days:      4,429
expected member-days:  2,220,522
positive close:        2,113,080
coverage:                 95.16%
```

The 2x difference is explained by 2,198 snapshot rows being expanded to 4,429
trading days, not by a superior data source.

### Ticker pool

```text
2000-2024 snapshot union (deduplicated): 1,062
2007-2024 snapshot union:   921
2007-2024 daily union:      887
```

P9 records `1,160` expected tickers. That exact pool is **not reproducible** from
the current `sp500_daily.csv`, even back to 2000. The `1,062` figure in P9 is the
row count of `p8_2/pit_coverage_by_ticker.csv`; only **918** of those rows have a
valid price. It is not a valid-ticker coverage numerator.

```text
P9_TICKER_POOL: 1,160 / NOT_REPRODUCIBLE
P8_TABLE_ROWS: 1,062
P8_VALID_TICKER_ROWS: 918
CURRENT_SNAPSHOT_UNION: 1,062
CURRENT_DAILY_UNION: 887
```

Do not replace `1,160` with `1,062` (or the earlier unverified `1,096`) and call
it the original baseline. The difference must be recorded as a version/
provenance gap.

---

## 3. V2 increment: 30 = 24 + 6

Actual normalized ticker/date join:

```text
local covered tickers:       807
V2 covered tickers:          808
union covered tickers:       831
newly covered tickers:        24
existing covered + V2 add:     6
union increment:              30
V2 added member-days:     11,802
```

The 30 is **not** 30 new covered tickers:

```text
24 new coverage tickers
+ 6 existing tickers with additional member-days
= 30 changed tickers
```

The 6 existing additions:

```text
EP     +509 member-days
GHC      +1
GPC      +1
IPG      +1
MO       +1
VRTX     +1
```

The 24 new tickers include `BRK.B`, `BF.B`, and recent/current names such as
`CRWD`, `PLTR`, `SMCI`, `VST`, `WDAY`.

File: `p10_5_2_v2_incremental_ticker_diff.csv` (30 rows).

### Important

The 24 new tickers are **coverage events**, not identity confirmations. V2 adds
only 24 of the 80 zero-member tickers; 56 remain. Ticker coverage reaches 93.69%,
still below 98%.

---

## 4. Coverage definitions, separated

| Definition | Numerator / denominator | Result |
|---|---|---:|
| Snapshot-observation coverage | 986,358 / 1,095,490 | 90.04% |
| Snapshot verified-tradable | 981,362 / 1,095,490 | 89.58% |
| Daily member-day coverage | 2,113,080 / 2,220,522 | 95.16% |
| Valid OHLCV ticker coverage | 807 / 887 | 90.98% |
| P8 table valid tickers | 918 / 1,062 table rows | 86.44% |
| Identity-confirmed ticker coverage | 2 / 887 | 0.23% |

These are not interchangeable. In particular:

- P8 table valid ticker ratio is not a pool coverage;
- daily coverage is not the P9 snapshot baseline;
- identity-confirmed coverage is not price coverage.

The original P9 gates remain:

```text
member-day >= 95%
ticker >= 98%
```

P9.1's 8 NO-GO results are unchanged.

---

## 5. Identity audit

File: `p10_5_2_verified_identity_crosswalk.csv` (80 rows).

Summary:

```text
IDENTITY_CONFIRMED:   2  (BRK.B, BF.B share classes)
IDENTITY_CONFLICT:    9  ticker reuse
IDENTITY_PARTIAL:     7  acquired/bankrupt/renamed successor
UNRESOLVED:          62
```

### Confirmed

- `BRK.B` → Berkshire Hathaway Inc., Class B (SEC CIK 1067983).
- `BF.B` → Brown-Forman Corp., Class B (SEC CIK 14693).

Both are share-class mappings, not missing legal entities.

### High-confidence ticker reuse conflicts

| Ticker | V2/current SEC name | Expected legacy entity |
|---|---|---|
| LB | LandBridge Corp | L Brands |
| STI | Solidion Technology | SunTrust Banks |
| LLL | JX Luxventure | L3Harris |
| HCP | HashiCorp | HCP Inc |
| SE | Sea Ltd | legacy `SE` entity |
| TE | T1 Energy | TECO Energy |
| ALTR | Altair Engineering | Altera |
| BEAM | Beam Therapeutics | Beam Inc |
| PLL | Piedmont Lithium | Pall Corp |

These are **not** the same legal entities. The V2 rows must not be used to fill
their historical member-days without a CIK/date filter.

### Partial / event-unverified

- CA → CA Inc (acquired by Broadcom; event not re-fetched).
- EMC → EMC Corp (acquired by Dell; event not re-fetched).
- DTV → DIRECTV (acquired by AT&T; event not re-fetched).
- DO → Diamond Offshore (bankruptcy; event not re-fetched).
- SHLD → Sears Holdings (bankruptcy; event not re-fetched).
- WYND → Travel + Leisure successor.
- DNB → old/new Dun & Bradstreet entity.

### Unresolved

`CHK`, `SNDK`, `NE`, 59 others lack enough official historical evidence for a
binding identity match. They remain `UNRESOLVED`.

### Category counts

```text
C_TICKER_REUSE:          9
C_SHARE_CLASS:           2
C_RENAME_OR_REORG:       2
B_ACQUIRED_OR_BANKRUPT:  5
UNRESOLVED:              62
```

No index removal is automatically labeled exchange delisting.

---

## 6. Free-source licence

### FINSABER-reproduce

```text
dataset: finsaber-team/FINSABER-reproduce
commit:  ba3a6907a29027b1f40da3381f3bc834e08e99a6
file:    data/price/all_sp500_prices_2000_2024_delisted_include.csv
bytes:   265,180,873
sha256:  f67e397...fa83f
license: Apache-2.0 (dataset card)
```

Local `finsaber_prices_raw.csv` matches exactly.

Apache-2.0 on the dataset card does **not** prove every underlying market-data
supplier authorised redistribution. Do not expand that claim.

### FINSABER-V2-Data

```text
commit:  68bb21ef1500591c6f81e0cb934bcf079e807e38
license: other
```

Not Apache-2.0. Not cleared for production or public redistribution. No raw
parquet committed.

### EODHD

```text
EODHD_DECISION: NO_BUY
```

No registration, payment, subscription, trial or vendor contact.

---

## 7. Purchase decision

| Gate | Status |
|---|---|
| ≤ $20 | PASS |
| ≤ 1 month | PASS |
| No VPS | PASS |
| Retain raw after cancel | PASS |
| Quantified recovery of remaining gap | **FAIL / UNVERIFIED** |
| Correct legal entity for recovered rows | **FAIL — only 2/80 confirmed** |
| Baseline unified | **FAIL — 1,160 not reproducible** |
| 95% member-day on trusted baseline | **FAIL — denominator conflict** |
| 98% ticker | **FAIL — free union 93.69%** |
| PIT membership | **FAIL — not in Historian** |
| Price vintage | **FAIL — not available** |

```text
NO_BUY
```

Even with 24 free V2 tickers, 56 tickers remain and 9 new/relevant tickers are
identity conflicts. The paid candidate does not solve the baseline or identity
problem.

---

## 8. Unresolved items

1. The exact P9 `1,160` ticker pool file/version is missing.
2. P9 snapshot denominator vs daily denominator needs a formal definition freeze.
3. 62/80 identities remain unresolved.
4. V2 `other` licence needs a legal determination before use.
5. EODHD paid delisted coverage is unverified.
6. EODHD does not provide historical S&P 500 membership or price vintage.

---

## 9. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P9_BASELINE: SNAPSHOT REPRODUCIBLE; TICKER POOL NOT_REPRODUCIBLE
V2_INCREMENT: 24 NEW + 6 EXISTING = 30; 11,802 MEMBER-DAYS
V2_UNION_TICKER_COVERAGE: 93.69%
V2_UNION_MEMBER_DAY_COVERAGE: 95.69%
IDENTITY_CONFIRMED: 2 / 80
IDENTITY_CONFLICT: 9 / 80
IDENTITY_UNRESOLVED: 62 / 80
P9_MEMBER_DAY_GATE: 95%
P9_TICKER_GATE: 98%
P9_DATA_REPRODUCIBILITY: BLOCKED UNTIL BASELINE RECONCILED
P9_RESULTS: ALL 8 NO-GO
```

No purchase, no registration, no trial, no VPS, no private repository created.
