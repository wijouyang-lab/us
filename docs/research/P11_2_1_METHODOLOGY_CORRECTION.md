# P11.2.1: Price-Factor Methodology Audit and Rerun

Date: 2026-11-17
Branch: `research/p11-individual-stock-selection`
Status: **NO-GO — methodology corrected, no reliable positive individual-stock alpha**

---

## 1. Purpose

P11.2 found no positive tradeable alpha, but its methodology had six defects.
This phase fixes them, preserves the original P11.2 outputs, and reruns the
study under a stricter design.

This is still individual-stock research, not ETF rotation. SPY/BIL are only
benchmarks/cash.

---

## 2. Defects fixed

| Defect | P11.2 | P11.2.1 |
|---|---|---|
| Sample selected using future Y | `X` and `Y` both required before eligibility | eligibility uses same-day `X` + PIT membership only; missing Y counted separately |
| Portfolio returns winsorized | Y winsorized for quintiles/top10 | winsorization only for IC diagnostics; portfolio returns raw |
| `slope_n` = `mom_n/n` | not a separate factor | true rolling OLS slope of log price, annualized |
| `rs_n` duplicates `mom_n` | treated as independent | marked duplicate; 20 raw / 17 independent |
| SPY timing mismatch | SPY close-to-close vs stock open-to-close | explicitly marked **NOT_FAIR_COMPARISON** |
| Cost/overlap too simple | 20bps, no non-overlap check | simplified cost labelled; HAC lag h-1; non-overlap IC added |

Additional fixes:

- positive forward returns >500% are flagged as corrupt data and excluded;
- negative extreme/delisting losses are not truncated;
- missing returns are recorded, not filled;
- factor eligibility is not conditioned on future availability.

---

## 3. Experiment design (locked before rerun)

```text
price symbols: 1,017 (983 with 2007+ data)
PIT membership: snapshot expansion
dates: 2000-01-03..2024-12-31
raw factors: 20
independent factors: 17 (rs20/rs60/rs120 duplicate mom)
horizons: 5/10/20
cells: 60
execution: next adjusted open -> adjusted close
cost: 20 bps round-trip, simplified
IC winsorization: 1/99% cross-section
portfolio returns: raw, not winsorized
periods: 2000-2012 dev, 2013-2017 val, 2018-2024 OOS
```

Benchmark:

```text
SPY close-to-close proxy
BENCHMARK_FAIR_COMPARISON: NO
```

The SPY file has no open series, so stock open-to-close and SPY close-to-close
are not strictly comparable. This is a limitation, not a hidden adjustment.

---

## 4. Sample and missing-result audit

At each date:

- eligible = PIT member AND same-day factor finite;
- future Y is **not** used to determine eligibility;
- missing Y is counted, not dropped from the eligibility decision;
- corrupt positive Y > 500% is flagged separately;
- negative extreme returns are retained.

Result:

```text
mean return coverage:      99.80%
cell-level missing-return observations: 371,166
cell-level corrupt positive returns: 18,959
```

These are disclosed, not silently removed.

---

## 5. Before/after key results

Original P11.2 (winsorized portfolio, Y-filtered sample) had no positive factor:

```text
max positive net top10: ~ +0.19%
significant: 2/60, both mom5 negative
```

Corrected P11.2.1:

```text
max positive net top10: +0.247% (one cell)
significant: 2/60, both mom5 negative
positive significant: 0
```

The very large raw top10 values that appeared before corrupt-return filtering
were driven by bad price observations (e.g. CBE +33,999x). They are not alpha.
After removing corrupt positive returns, top10 returns collapse to near zero.

---

## 6. IC and significance

```text
mom5 / 5d:  IC -0.01446, HAC t -4.35, BH q 0.00080
mom5 / 10d: IC -0.01251, HAC t -3.21, BH q 0.03998
```

Both are negative. No positive factor survives BH 5%.

```text
positive BH-significant factors: 0
```

Best positive net top10:

```text
volume_price_corr20 / 20d: +0.0126% (q 0.20)
```

Economically negligible.

---

## 7. OOS and non-overlap

OOS 2018-2024 best mean IC:

```text
vol_change / 10d: +0.0040
```

No positive OOS factor is economically meaningful.

Non-overlap sensitivity:

```text
mom5 / 5d non-overlap IC -0.01605, t -3.42
```

The negative 5-day reversal survives non-overlap sampling, but it is still a
negative/short-horizon effect, not a long-only alpha.

---

## 8. Turning over and costs

```text
turnover range: 2.9% to 67.8%
cost model: 20 bps round-trip, simplified
```

Turnover counts top-decile name changes; it is a one-way name-change fraction.
The 20bps is not IBKR Pro Tiered actual cost, not slippage, not borrow, not
market impact.

No positive factor is robust to even this simplified cost.

---

## 9. Factor duplication audit

Raw factors: 20  
Independent: 17

Duplicate pairs:

```text
rs20  -> mom20
rs60  -> mom60
rs120 -> mom120
```

Their cross-sectional ranks are identical (correlation 1.0); they are diagnostic
aliases only.

True OLS slope is no longer `mom_n/n`:

```text
corr(slope20, mom20) = 0.891
corr(slope60, mom60) = 0.892
corr(slope120,mom120)= 0.890
```

They remain related but are not identical.

---

## 10. Final decision

```text
P11_2_1_STATUS: NO-GO
METHODOLOGY_CORRECTED: YES
POSITIVE_TRADEABLE_ALPHA: NO
POSITIVE_BH_SIGNIFICANT_FACTORS: 0
OOS_CONFIRMED: NO
BENCHMARK_FAIR: NO
PORTFOLIO_CONSTRUCTION_READY: NO
FULL_MARKET_CLAIM: NO
```

The price-factor route is closed. No P11.3 portfolio construction from these
factors.

---

## 11. Files

- `tools/research/p11/factor_study_v21.py`
- `data/research/p11_2_1/p11_2_1_factor_results.csv`
- `data/research/p11_2_1/p11_2_1_annual_ic.csv`
- `data/research/p11_2_1/p11_2_1_quintile_returns.csv`
- `data/research/p11_2_1/p11_2_1_factor_correlation.csv`
- `data/research/p11_2_1/p11_2_1_factor_catalog.csv`
- `data/research/p11_2_1/p11_2_1_experiment_config.json`
- `data/research/p11_2_1/p11_2_1_summary.json`

Original P11.2 results are retained under `data/research/p11_2/`.

All outputs are aggregate; no raw market data is committed.

---

## 12. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P11_2_1_STATUS: NO-GO
METHODOLOGY_CORRECTED: YES
RAW_FACTORS: 20
INDEPENDENT_FACTORS: 17
POSITIVE_TRADEABLE_ALPHA: NO
POSITIVE_BH_SIGNIFICANT_FACTORS: 0
OOS_CONFIRMED: NO
BENCHMARK_FAIR: NO
PORTFOLIO_CONSTRUCTION_READY: NO
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
IBKR_CONNECTED: NO
```
