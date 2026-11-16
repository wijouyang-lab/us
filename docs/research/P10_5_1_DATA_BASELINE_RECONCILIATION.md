# P10.5.1: Free-Data Reconciliation, Identity Mapping and P9 Baseline

Date: 2026-11-16
Branch: `research/p10-data-provider-evaluation`
Status: **AUDIT ONLY — NO PURCHASE, NO TRIAL, NO VPS**

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P9_DATA_REPRODUCIBILITY: BLOCKED UNTIL BASELINE RECONCILED
P9_RESULTS: ALL 8 NO-GO
```

---

## 1. Why 887 vs 1,160 and 95.16% vs 89.58%

The two results are not two measurements of the same denominator. They use
different date grids, intervals and ticker pools.

### P9 recorded baseline

`data_audit.json` / P8.2 summary:

```text
expected member-days: 1,095,490
valid close:            986,358
verified tradable:      981,362
member-day coverage:      89.58%
```

This denominator is produced by iterating the **snapshot rows** in
`sp500_daily.csv` (2,198 rows from 2000-01-03 to 2024-12-31), not by expanding
membership to every NYSE trading day.

Exact reproduction from the current files:

```text
snapshot rows:       2,198
member-days:     1,095,490
valid close:       986,358
```

The `981,362` verified number additionally removes 4,996 zero/stale/corrupt/
unresolved rows under the P8/P9 policy.

### Independent daily-expanded audit

Expanding membership to the SPY trading calendar:

```text
trading days:        4,429
member-days:     2,220,522
positive close:  2,113,080
coverage:            95.16%
tickers:               887
tickers with price:    807
ticker coverage:     90.98%
```

The denominator is roughly doubled because 2,198 irregular snapshots are
expanded to 4,429 trading days. It is not a higher measure of the same thing.

### Ticker pool

Current membership file:

```text
2000-2024 snapshot union: 1,096 tickers
2007-2024 snapshot union:   921 tickers
2007-2024 daily union:      887 tickers
```

The P9 record says `1,160` expected and `1,062` actual. The `1,062` matches the
row count of `p8_2/pit_coverage_by_ticker.csv` (which has 918 tickers with any
valid price). The `1,160` pool cannot be reproduced from the current
`sp500_daily.csv`; it appears to come from an earlier file/version or a different
universe filter.

```text
TICKER_POOL_VERSION_MISMATCH: YES
P9_TICKER_POOL_REPRODUCIBLE: NO
```

### Positive close vs verified tradable

- `positive close`: `adjusted_close > 0`;
- `verified tradable`: full OHLCV, positive volume, no anomaly/corrupt/stale flag.

The difference explains `986,358` vs `981,362`, not the 2x denominator.

### Conclusion

Do not average the two results or select 95.16% as the P9 result.

The correct interpretation is:

```text
P9 RECORD: 89.58% on irregular snapshot rows, old ticker pool
INDEPENDENT: 95.16% on daily-expanded rows, current pool
DEFINITION CONFLICT: UNRESOLVED
```

A formal baseline decision is required before either can be used for acceptance.
This audit does not change P9.1's historical NO-GO or its results.

---

## 2. The 80 zero-member-day tickers

From `eodhd_price_gap_inventory.csv`:

```text
zero observed member-days: 80
with local price rows:      47
without local price rows:   33
```

The 47 with rows have prices that do not overlap their expected membership dates.
Possible causes:

- index removal before/after the local price window;
- ticker reuse by a different legal entity;
- rename/M&A/share-class change;
- membership effective-date mismatch;
- local price symbol pointing at a different security.

The 33 without rows include class-symbol variants such as `BRK.B` and `BF.B`,
whose local prices use no matching symbol.

### Identity audit status

File: `p10_5_1_identity_crosswalk.csv` (80 rows)

```text
with local price rows:       47
without local price rows:    33
categorized share-class:      2
ticker-reuse/multi-CIK:       0
review required:             66
unresolved:                  12
V2 CIK available:            68 / 80
V2 CIK unavailable:          12 / 80
identity confirmed:           0
```

No ticker is assumed to be the same legal entity merely because the string
matches. CIK/name availability from the free V2 file and SEC submissions was
used only as a clue, not as confirmation. Two clear conflicts are already
visible: ADCT maps to ADC Therapeutics while the expected membership period
predates that entity, and AT maps to AT&T Corp while the expected ticker may be
a different/legacy security. Both remain UNRESOLVED.

Categories:

```text
A. Index removal, still listed          NOT ESTABLISHED for these rows
B. Exchange delisting/bankruptcy        NOT ESTABLISHED without event evidence
C. Rename/M&A/ticker reuse/share class  PARTIAL (2 share-class; 0 multi-CIK)
UNRESOLVED                              remaining rows
```

The required conclusion is:

```text
INDEX_REMOVAL != EXCHANGE_DELISTING
IDENTITY_STATUS: UNRESOLVED for 80/80
```

---

## 3. FINSABER source verification

### Local file

```text
file:   finsaber_prices_raw.csv
bytes:  265,180,873
sha256: f67e3972dceefbbdf6c17b84b30957a7b83518401955fff8ae0bc4ae206fa83f
```

### FINSABER-reproduce

Public file:

```text
data/price/all_sp500_prices_2000_2024_delisted_include.csv
bytes: 265,180,873
sha256: f67e3972dceefbbdf6c17b84b30957a7b83518401955fff8ae0bc4ae206fa83f
```

The exact SHA256 and byte count match. Dataset card:

```text
repo: finsaber-team/FINSABER-reproduce
commit sha: ba3a6907a29027b1f40da3381f3bc834e08e99a6
license: Apache-2.0
```

So the local price file is the public FINSABER-reproduce CSV, not an unknown
private download.

### FINSABER-V2-Data

```text
repo: finsaber-team/FINSABER-V2-Data
commit sha: 68bb21ef1500591c6f81e0cb934bcf079e807e38
license: other
```

V2 is **not** Apache-2.0 and not unrestricted. Its README says users are
responsible for source-derived market/news/filing licence compliance.

Do not treat V2 as freely redistributable.

---

## 4. Free V2 incremental coverage

Downloaded only the 2007-2024 `price_daily` parquet partitions for audit; no
raw files were committed.

Canonical symbol normalization: `.` -> `-` (e.g. `BRK.B` vs `BRK-B`).

| Source | Tickers with member-day | Member-day coverage | Ticker coverage |
|---|---:|---:|---:|
| Local FINSABER | 807 | 95.16% | 90.98% |
| V2 only | 808 | 94.68% | 91.09% |
| Union local + V2 | **831** | **95.69%** | **93.69%** |

V2 adds:

```text
30 tickers
11,802 member-days
```

But:

- 56 expected tickers remain missing;
- 98% ticker gate not reached;
- V2 licence is `other`, not cleared for redistribution or production use;
- identity of V2 rows is still not fully confirmed.

```text
FREE_V2_INCREMENTAL_TICKERS: 30
FREE_V2_TICKERS_NEEDED_FOR_98PCT: 39 additional beyond the union
FREE_V2_LICENSE: OTHER / NOT CLEARED
FREE_V2_COVERAGE_PASS: NO
```

---

## 5. EODHD boundary remains

The paid demo still only verifies AAPL/MSFT/TSLA; delisted demos return 403.
No paid endpoint was used.

To reach 98% from the **free union** of 831:

```text
887 * 98% = 870
870 - 831 = 39 additional tickers
```

The earlier "63 of 80" requirement was relative to the local-only 807 baseline.
With V2 free additions, the paid requirement is smaller, but still unverified.

EODHD Historian:

- no historical S&P 500 membership;
- no price vintage;
- personal-use only, no public output;
- cannot assume non-reversible aggregates are publishable without checking
  commercial terms;
- $19.99 is within budget, but paid coverage and legal-entity identity are not
  demonstrated.

---

## 6. Purchase decision

### BUY gate

| Condition | Status |
|---|---|
| ≤ $20 | PASS |
| ≤ 1 month | PASS |
| No VPS | PASS |
| Retain raw after cancellation | PASS |
| Quantified recovery of ≥63/80 (or 39 beyond free union) | **FAIL / UNVERIFIED** |
| Correct legal-entity identity | **FAIL — 80 unresolved** |
| Baseline unified | **FAIL** |
| 95% member-day on trusted baseline | **FAIL — conflict** |
| PIT membership solved | **FAIL — not included** |
| Price vintage solved | **FAIL** |
| Public-output licence clear | **FAIL — requires commercial review** |

```text
NO_BUY
```

The free V2 supplement is useful for audit, but its licence and identity are not
cleared. EODHD remains an unverified paid experiment, not a justified purchase.

---

## 7. What must happen next

Before reconsidering $19.99:

1. formally choose the member-day denominator and date grid;
2. reconcile the 1,160 ticker pool with a versioned membership file;
3. map the 80 zero-member-day tickers to CIK/legal entity/event evidence;
4. distinguish A/B/C using official filings, not ticker strings;
5. establish V2 licence terms for any production use;
6. obtain a legal prepurchase sample for at least the 39 remaining tickers;
7. prove 95%/98% on the agreed baseline;
8. keep PIT and price-vintage limitations separate.

Until then:

```text
P9_DATA_REPRODUCIBILITY: BLOCKED UNTIL BASELINE RECONCILED
P9_RESULTS: ALL 8 NO-GO
```

---

## 8. Sources

- FINSABER-reproduce: https://huggingface.co/datasets/finsaber-team/FINSABER-reproduce
- FINSABER-V2-Data: https://huggingface.co/datasets/finsaber-team/FINSABER-V2-Data
- P9 data audit: `data/research/p9_1_support_resistance/data_audit.json`
- P8.2 coverage: `data/research/p8_2/pit_coverage_summary.json`
- P8.2 ticker table: `data/research/p8_2/pit_coverage_by_ticker.csv`
