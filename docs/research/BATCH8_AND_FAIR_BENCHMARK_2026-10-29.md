# Batch 8 and Fair Benchmark Audit

Date: 2026-10-29 UTC
Research only. No canonical write.

## 1. Batch 8 鈥?25 names

```text
CMA, MRO, QRVO, RHI, VFC, WHR, WRK, XRAY, ZION,
DFS, EMN, FMC, HES, IPG, K, KMX, LKQ, MHK,
WBA, CAG, CPB, EA, EQR, HOLX, MMC
```

| Category | Count |
|---|---:|
| `STILL_TRADING` | **12** |
| `DELISTED_OR_ACQUIRED` | **11** |
| `TICKER_OR_NAME_CHANGED` | **2** |
| Total | **25** |

Still trading:

`RHI, VFC, WHR, XRAY, ZION, EMN, FMC, KMX, LKQ, MHK, CAG, CPB`

Changed:

- `EQR -> VMRK` (Vivmark Residential)
- `MMC -> MRSH`

Delisted/acquired:

`CMA, MRO, QRVO, DFS, HES, IPG, K, WBA, EA, HOLX`

SEC evidence examples:

| Ticker | SEC 25-NSE | SEC 15-12G |
|---|---|---|
| CMA | 2026-02-02 | 2026-02-12 |
| MRO | 2024-11-22 | 2024-12-02 |
| QRVO | 2026-10-05 | 2026-10-15 |
| DFS | 2025-05-19 | 2025-05-29 |
| HES | 2025-07-18 | 2025-07-28 |
| IPG | 2025-11-28 | 2025-12-08 |
| K | 2025-12-11 | 2025-12-22 |
| WBA | 2025-08-28 | 2025-09-08 |
| EA | 2026-08-04 | 2026-08-14 |
| HOLX | 2026-04-07 | 2026-04-17 |

## 2. Combined status

| Category | Count |
|---|---:|
| `DELISTED_OR_ACQUIRED` | **84** |
| `STILL_TRADING` | **78** |
| `TICKER_OR_NAME_CHANGED` | **33** |
| `HISTORICAL_MEMBERSHIP_ONLY` | **4** |
| `TICKER_REUSE_SUSPECTED` | **2** |
| `IDENTITY_UNRESOLVED` | **1** |
| Total | **202** |

Reviewed: **198 / 202**.

Remaining 4:

```text
PSKY, SOLS, TAP, TTD
```

## 3. Benchmark fairness audit

### Original implementation

- Factor and benchmark use the same test month-end dates.
- Both use 20-session forward returns.
- Both use equal-weight Q5/Q1 or equal-weight benchmark.
- Original benchmark has **zero turnover and zero cost**.
- Factor uses 5 bps 脳 turnover.

### Problems found

1. **Different pool**: benchmark uses all price-eligible names with Fwd20;
   each factor further drops missing factor values.
2. **Zero-cost benchmark**: original benchmark is a frictionless market
   return, not an executable rebalanced strategy.
3. **Overlap was only a count**: it did not distinguish windows, pairs, and
   independent observations.
4. **Cost side was implicit**: 5 bps was per unit one-way book turnover; not
   explicitly double-sided.

### Fixes implemented

In `tools/research/fixed5_walkforward_audit.py`:

- added explicit `--cost-bps`;
- added **common-pool benchmark**: same dates, all five factor values and
  Fwd20 available;
- added **net benchmark**: 1.0 full monthly rebalance turnover 脳 cost_bps;
- added annual `excess_vs_common_ann` and `excess_vs_net_ann`;
- added `benchmark_common_by_year`, `benchmark_net_by_year`;
- added cost/overlap metadata;
- added 10 bps sensitivity.

Original zero-cost benchmark is retained and clearly named.

## 4. Actual annual benchmark results

| Year | Original zero-cost | Common pool | Net benchmark (5 bps) |
|---|---:|---:|---:|
| 2023 | 5.34% | 5.45% | **4.71%** |
| 2024 | 21.02% | 20.61% | **20.31%** |
| 2025 | 14.88% | 14.23% | **14.20%** |
| 2026 (9m) | 13.65% | 13.74% | **12.98%** |

The zero-cost benchmark was not systematically flattering the strategy by much;
giving the benchmark a full rebalance cost lowers it slightly but does not create
stable alpha.

## 5. 12-1 momentum fair excess

| Year | Factor net | Common benchmark | Net benchmark | Excess vs common | Excess vs net |
|---|---:|---:|---:|---:|---:|
| 2023 | 10.70% | 5.45% | 4.71% | +5.25% | +5.99% |
| 2024 | 34.26% | 20.61% | 20.31% | +13.65% | +13.95% |
| 2025 | -5.95% | 14.23% | 14.20% | -20.17% | -20.14% |
| 2026 (9m) | -3.85% | 13.74% | 12.98% | -17.59% | -16.83% |

The sign flips across years. 2023/24 gains are not stable.

## 6. Overlap and statistics

Code definition:

```text
gap_sessions = session_index(next_month_end) - session_index(current_month_end)
overlapping_windows = count(gap_sessions < 20)
```

Actual:

```text
month-end dates: 46
valid annual observations: 45
2023: 12, 2024: 12, 2025: 12, 2026: 9
overlapping adjacent pairs: 6
horizon: 20 sessions
```

`45` is the number of monthly metric rows, not 45 independent observations.
Annual metrics are descriptive; no cross-year q-value is claimed.

Annualization uses:

```text
(1 + mean monthly return)^12 - 1
```

2026 is partial and must not be read as a full year.

## 7. Missing data and bias

- `dropna` removes missing Fwd20/factor values; no zero-fill.
- Mean names per annual factor bucket are roughly 490鈥?00.
- Current 503-name panel is survivorship-biased.
- Results are current-universe exploratory, not full historical market alpha.

## 8. Conclusion

- No fixed five-factor has stable net excess across 2023鈥?026.
- Benchmark fairness adjustments do not change that conclusion.
- 12-1 momentum is the strongest but fails in 2025/2026.
- Low-vol/ATR remain negative.
- 45 monthly rows with 6 overlaps are insufficient for strong significance.
- Do not deploy or claim validated alpha.

## Artifacts

- v9 classification: `docs/research/missing_202_reason_classification_v9_2026-10-29.csv`
- batch 8 SEC: `docs/research/missing_202_batch8_sec_2026-10-29.json`
- fair 5 bps: `docs/research/fixed5_walkforward_2026-10-29_annual.csv`
- 10 bps: `docs/research/fixed5_walkforward_10bps_2026-10-29_annual.csv`
- tool: `tools/research/fixed5_walkforward_audit.py`
