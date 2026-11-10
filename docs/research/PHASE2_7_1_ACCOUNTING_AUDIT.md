# Phase 2.7.1 Independent Accounting Audit

Date: 2026-10-30
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`
No production changes. Original Phase 2.7 results are preserved; audit is separate.

## 1. Verdict

The original Phase 2.7 Q5鈭扱1 net return was **materially overstated** because the
short leg was treated as a long leg and its cost was added back:

```text
original: (Q5 gross 鈭?Q5 cost) 鈭?(Q1 gross 鈭?Q1 cost)
        = Q5 鈭?Q1 鈭?Q5cost + Q1cost
```

For a short Q1 leg, the correct accounting is:

```text
short Q1 net = 鈭扱1 gross 鈭?Q1 cost
Q5鈭扱1 net    = Q5 gross 鈭?Q5 cost 鈭?Q1 gross 鈭?Q1 cost
```

The sign of the Q1 cost was wrong. This is why higher costs could appear to
improve the Q5鈭扱1 CAGR.

The original Sharpe was also overstated by using CAGR / volatility instead of
mean period return / period volatility, and by summing holding days rather than
using elapsed calendar time.

## 2. Original vs corrected: ATR, 10 bps

| Metric | Original | Audit |
|---|---:|---:|
| Q5 CAGR | 27.26% | 26.76% |
| Q1 leg | +6.13% (long) | **鈭?.50% (short net)** |
| Q5鈭扱1 CAGR, 1x spread | 20.04% | **18.95%** |
| Q5鈭扱1 CAGR, 2x capital | not reported | **10.26%** |
| Q5鈭扱1 Sharpe | 0.66 | **0.358** |
| Q5鈭扱1 max drawdown 2x | not comparable | **鈭?5.04%** |
| 1x max drawdown | 鈭?9.2% | 鈭?9.75% |

## 3. Corrected cost sensitivity, Q5鈭扱1

### 1x spread (long 1 + short 1, denominator 1)

| Factor | 10 bps | 25 bps | 50 bps |
|---|---:|---:|---:|
| ATR | 18.95% | 17.95% | 16.30% |
| Realized Vol | 13.06% | 11.72% | 9.51% |
| Beta | 12.52% | 11.40% | 9.55% |

Costs now **monotonically reduce** each leg and the spread.

### 2x capital (100% long + 100% short; denominator 2)

| Factor | 10 bps | 25 bps | 50 bps |
|---|---:|---:|---:|
| ATR | 10.26% | 9.79% | 9.02% |
| Realized Vol | 7.24% | 6.60% | 5.54% |
| Beta | 7.40% | 6.86% | 5.97% |

The 1x spread must not be compared with 100%-long CAGR without stating that it
uses 2x gross exposure.

## 4. Per-period example

First ATR period:

```text
Q5 gross           +?
Q1 gross           +?
Q5 cost            0.10% (one side)
Q1 short cost      0.10% (one side)
Original spread    gross spread
Corrected spread   gross spread - 0.20%
```

Every period's `q1_short_net_{cost}` is stored in the audit JSON, along with
`spread_net_1x` and `spread_net_2x`.

## 5. CAGR / Sharpe / drawdown audit

- 36 non-overlapping periods, 2018鈥?026.
- Actual elapsed time: 8.736 years.
- CAGR uses actual first entry to last exit, not sum of holding days only.
- Sharpe = mean period return / period std 脳 鈭?252/60).
- Drawdown uses the compounded period net series.
- Q5鈭扱1 2x uses half the 1x spread each period, then compounds.

Original Sharpe 0.66 becomes **0.358**. This is a major difference; the original
Sharpe should not be used.

## 6. Short-leg / financing limitations

Even the corrected result is not a complete net long-short return:

- no borrow fee;
- no short locate/availability;
- no financing on the long or short;
- no dividends paid on short;
- no market impact;
- no hard-to-borrow constraints.

Therefore the corrected Q5鈭扱1 is **not** a deployable long-short return.

## 7. Factor correlations

Unchanged from Phase 2.7:

```text
ATR vs Realized Vol: 0.984
ATR vs Beta:         0.940
Realized Vol vs Beta: 0.946
```

ATR and Realized Volatility are effectively the same portfolio; Beta adds little.

## 8. Annual / regime

The corrected series keeps the same qualitative pattern:

- negative 2019, 2021, 2022;
- strong 2020, 2023鈥?026;
- concentrated in bear/high-vol/range environments;
- weak in bull/trend.

The raw period data is in the audit JSON; no periods were deleted.

## 9. Tests

`tests/test_volatility_accounting_audit.py`: **2 passed**

- initial cost once;
- zero turnover has zero cost;
- short leg = 鈭抔ross 鈭?cost;
- higher cost lowers both legs and spread;
- 2x spread is half of 1x.

Full CI after commit.

## 10. Impact on Phase 2.7 conclusions

Invalidated:

- original Q5鈭扱1 net CAGR and cost sensitivity;
- original claim that costs do not reduce the spread;
- original Sharpe 0.66;
- any comparison of 1x spread CAGR to 100%-long CAGR.

Still valid:

- ATR/RV Q5 gross is high with large drawdown;
- factors are highly correlated;
- performance is regime-dependent;
- current-universe survivorship bias remains;
- no PIT.

## 11. Artifacts

- `tools/research/volatility_accounting_audit.py`
- `tests/test_volatility_accounting_audit.py`
- `docs/research/volatility_accounting_audit_2026-10-30.json`
- `docs/research/volatility_accounting_audit_2026-10-30.csv`
- original Phase 2.7 JSON preserved unchanged
