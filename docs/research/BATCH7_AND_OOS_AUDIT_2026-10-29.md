# Batch 7 Identity and Fixed-5 OOS Audit

Date: 2026-10-29 UTC
Research only. No canonical write.

## 1. Batch 7 鈥?25 names

Selected from remaining 2016-style gaps and known corporate actions:

```text
CPRI, HOG, HP, HRB, JWN, KSS, M, FLS, FTI, HBI,
LEG, NOV, PRGO, SLG, UNM, WU, XRX, GPS, PVH, UA,
UAA, LNC, NWL, SEE, VNO
```

| Category | Count |
|---|---:|
| `STILL_TRADING` | **20** |
| `DELISTED_OR_ACQUIRED` | **4** |
| `TICKER_OR_NAME_CHANGED` | **1** |
| Total | **25** |

Still trading:

`CPRI, HOG, HP, HRB, KSS, M, FLS, FTI, NOV, PRGO, SLG, UNM, WU, XRX, PVH, UA, UAA, LNC, NWL, VNO`

Changed:

- `GPS -> GAP` (Gap Inc.)

Delisted/acquired:

`JWN, HBI, LEG, SEE`

SEC evidence:

- JWN: 25-NSE 2025-05-21, 15-12G 2025-06-02.
- HBI: 25-NSE 2025-12-01, 15-12G 2025-12-11.
- LEG: 25-NSE 2026-08-27, 15-12G 2026-09-08.
- SEE: 25-NSE 2026-04-09, 15-12G 2026-04-20.

`25-NSE`/`15-12G` are metadata evidence, not an independent last-trade price.

## 2. Combined 202 status

| Category | Count |
|---|---:|
| `DELISTED_OR_ACQUIRED` | **73** |
| `STILL_TRADING` | **66** |
| `TICKER_OR_NAME_CHANGED` | **31** |
| `HISTORICAL_MEMBERSHIP_ONLY` | **29** |
| `TICKER_REUSE_SUSPECTED` | **2** |
| `IDENTITY_UNRESOLVED` | **1** |
| Total | **202** |

Reviewed: **173 / 202**. Remaining: **29**.

## 3. Fixed-five OOS audit

Tool:

`tools/research/fixed5_walkforward_audit.py`

### Cost convention

Actual code:

```text
cost = cost_bps / 10000 * turnover
```

- Primary: **5 bps per unit one-way book turnover**.
- Initial book turnover = 1.0, so initial cost = 5 bps.
- Benchmark: zero turnover, **zero cost**.
- This is not explicitly double-sided; a 10 bps sensitivity was run to test
  cost understatement.
- No duplicate deduction observed; cost is charged once per rebalance.

### Test dates and overlap

```text
configured test month-ends: 46
annual observations: 45
2023: 12
2024: 12
2025: 12
2026: 9 (partial year)
overlapping 20D windows: 6 (gaps < 20 sessions)
```

Therefore the monthly observations are **not all independent**. Annual
statistics are descriptive, not fully independent significance tests.

### Factor directions

```text
Vol60   -1  (low volatility)
ATR_Pct -1  (low ATR)
Mom12_1 +1  (high 12-1 momentum)
Mom1    -1  (low 1-month return / reversal)
MA50    +1  (high price/MA50)
```

### Annual results (5 bps)

| Year | n | Benchmark ann | Best factor | Best ann | Worst factor | Worst ann |
|---|---:|---:|---|---:|---|---:|
| 2023 | 12 | 5.34% | 12-1 momentum | 10.70% | ATR low | -18.81% |
| 2024 | 12 | 21.02% | 12-1 momentum | 34.26% | ATR low | -20.40% |
| 2025 | 12 | 14.88% | MA50 | 14.69% | ATR low | -33.06% |
| 2026 | 9 | 13.65% | MA50 | -3.34% | Vol60 | -24.38% |

- 12-1 momentum beat in 2023/2024 but was negative in 2025/2026.
- MA50 was near benchmark in 2025 but negative in 2026.
- Low-vol/ATR were consistently negative.
- 2026 is not a full year.

### 10 bps sensitivity

A 10 bps run was executed. Net returns fell slightly, but no factor changed from
negative to stable positive; conclusions do not depend on the 5 bps assumption.

### Benchmark and data coverage

- Benchmark uses the same test dates and eligible price universe.
- Factor portfolios further require factor values; no zero-fill.
- Mean names per annual bucket are roughly 490鈥?00.
- Current 503 panel is **survivorship-biased**; no complete 2016 delisted
  universe.

### Missing data

Missing factor/price observations are dropped by `dropna`, not filled with zero.
Annual `n` and `mean_names` are reported; no hidden imputation.

### Multiple testing

The five factors 脳 four annual periods are reported descriptively. No q-value
is claimed across years; no factor is declared significant after correction.

## 4. Answers

1. **Is there stable net excess return?** No.
2. **Does cost adjustment change the conclusion?** No; 5 vs 10 bps does not
   create stable alpha.
3. **Do a few months dominate?** 12-1 momentum has strong 2023/2024 and weak
   2025/2026; not stable. Full annual table is in CSV.
4. **Are observations sufficient?** 45 monthly buckets, 6 overlapping; not
   enough for a strong independent-significance claim.
5. **Survivorship/overlap/data-gap effects?** Yes: current-universe bias,
   partial overlap, and pre-2016 coverage limitations remain.

## 5. Artifacts

- v8 classification: `docs/research/missing_202_reason_classification_v8_2026-10-29.csv`
- batch 7 SEC: `docs/research/missing_202_batch7_sec_2026-10-29.json`
- 5 bps annual: `docs/research/fixed5_walkforward_2026-10-29_annual.csv`
- 10 bps annual: `docs/research/fixed5_walkforward_10bps_2026-10-29_annual.csv`
- tool: `tools/research/fixed5_walkforward_audit.py`
