# P11.2.2: Final Price-Factor Result Audit

Date: 2026-11-17
Branch: `research/p11-individual-stock-selection`
Status: **NO-GO — no reliable positive individual-stock price alpha**

---

## 1. Scope

P11.2.2 is the final methodology/result audit of the price-factor study. It
does not add factors, does not enter P11.3, and does not change P9 or P10.

Original P11.2 and P11.2.1 files remain in place.

---

## 2. Corrections versus P11.2.1

1. **Raw vs excess returns**
   - raw individual-stock forward returns are primary;
   - SPY excess returns are stored separately;
   - SPY close-to-close is not a fair match for stock open-to-close;
   - `BENCHMARK_FAIR: NO`.

2. **No future-Y eligibility**
   - eligibility uses only same-day signal + PIT membership;
   - missing future returns are counted, not used to select the sample.

3. **No silent `nanmean` in portfolio**
   - Top10 and quintile missing values are counted;
   - incomplete portfolio dates are reported;
   - no missing stock is treated as zero or removed from eligibility.

4. **Corrected non-overlap**
   - every h-th full trading date is sampled;
   - after dropping non-IC dates, no re-compression is allowed;
   - before/after values are reported.

5. **True OLS slope**
   - `slope_n` is a rolling OLS slope of log price, annualized;
   - it is not `mom_n/n`.

6. **Duplicate factors**
   - 20 raw factor names;
   - 17 independent;
   - `rs20/rs60/rs120` are rank-identical to matching momentum and are
     diagnostic aliases only.

---

## 3. Extreme >500% forward returns

A separate audit file lists 8,099 ticker/date/horizon observations with forward
returns above 500%:

`data/research/p11_2_2_extreme_return_audit.csv`

All are marked:

```text
UNCONFIRMED_EXTREME
```

No independent corporate-action/price file was available to prove each one is
an error. Therefore none is called `CORRUPT` and none is removed from the primary
all-record estimate.

The primary all-record estimate is data-quality-contaminated. A sensitivity run
that excludes only these unconfirmed extremes is reported as diagnostic, not as
the primary result.

---

## 4. Sample and missing results

```text
price symbols: 1,017 (983 with 2007+ data)
dates: 2000-01-03..2024-12-31
mean return coverage: 99.80%
Top10 incomplete dates: 24,394 (cell-level)
Quintile incomplete dates: 107,722 (cell-level)
```

`Top10` returns are computed only for complete dates; incomplete dates are
reported, not silently `nanmean`-ed.

---

## 5. Key results

### Raw returns, all records

```text
mom5 / 5d:
  IC raw       -0.01440
  HAC t        -4.34
  BH q          0.00086
  Top10 raw    +4.47%
  Top10 excess +4.32%
  Net raw      +4.39%
  non-overlap IC -0.01579
```

This looks positive for Top10 only because a small number of extreme forward
returns dominate the raw mean. It is not a usable long-only result: the same
factor has a negative IC, and the extreme records are unconfirmed data.

```text
vol60 / 5d:
  Top10 raw    +15.39%
  BH q          0.1875
```

Also dominated by extremes; not alpha evidence.

### BH-significant factors

```text
BH q < 0.05: 2 / 60
both mom5 negative:
  mom5/5d  q 0.00086
  mom5/10d q 0.04098
positive BH-significant: 0
```

### All-record maximum (not the alpha conclusion)

```text
vol60 / 20d:
  net Top10 raw: +19.09%
  BH q:           0.647
```

This is an unconfirmed-extreme-contaminated number, not a strategy result.
`volume_price_corr20 / 20d` is +4.74% raw net, q 0.230, likewise unreliable.

### Sensitivity excluding unconfirmed >500% extremes

Diagnostic P11.2.1-style run:

```text
max positive net Top10: +0.247% (vol_change/20d, q 0.979)
positive significant: 0
```

This is the cleaner estimate. It shows no positive alpha.

### OOS 2018-2024

No factor has an economically meaningful positive OOS mean IC. Best is around
+0.004, not tradeable.

### Non-overlap

Corrected fixed-calendar sampling gives:

```text
mom5/5d non-overlap IC -0.01579
```

Still negative; the short-horizon reversal remains, but it is not long alpha.

---

## 6. Before/after

| Item | P11.2.1 | P11.2.2 |
|---|---|---|
| Sample eligibility | Y not used | Y not used |
| Top10 returns | raw, incomplete via nanmean | raw, incomplete dates counted |
| Raw vs excess | excess only | raw primary; excess separate |
| Extreme >500% | excluded as "corrupt" | included primary; unconfirmed audit |
| Non-overlap | compressed after drops | fixed full-calendar sampling |
| Slope | true OLS | true OLS |
| RS duplicates | marked | marked |
| Benchmark fair | no | no |

The all-record raw Top10 is **not** a valid alpha conclusion. The cleaner
sensitivity estimate remains near zero/negative.

---

## 7. Decision

```text
P11_2_2_STATUS: NO-GO
RAW_FORWARD_RETURNS: PRIMARY
SPY_EXCESS_RETURNS: SECONDARY_ONLY
BENCHMARK_FAIR: NO
POSITIVE_TRADEABLE_ALPHA: NO
POSITIVE_BH_SIGNIFICANT_FACTORS: 0
OOS_CONFIRMED: NO
PORTFOLIO_CONSTRUCTION_READY: NO
```

The price-factor route is closed. Do not proceed to P11.3 with these factors.

---

## 8. Reproducibility

Original data hashes and local run command are recorded in:

`data/research/p11_2_2/p11_2_2_run_manifest.json`

```text
local raw files: not committed
data files: aggregate results only
CI: synthetic/static tests only; no raw market data
```

Run command:

```bash
python -m tools.research.p11.factor_study_v22 \
  --base ../pr512/data/research \
  --out data/research/p11_2_2
```

---

## 9. Files

- `data/research/p11_2_2/p11_2_2_factor_results.csv`
- `data/research/p11_2_2/p11_2_2_annual_ic.csv`
- `data/research/p11_2_2/p11_2_2_quintile_returns.csv`
- `data/research/p11_2_2/p11_2_2_factor_correlation.csv`
- `data/research/p11_2_2/p11_2_2_factor_catalog.csv`
- `data/research/p11_2_2/p11_2_2_experiment_config.json`
- `data/research/p11_2_2/p11_2_2_extreme_return_audit.csv`
- `data/research/p11_2_2/p11_2_2_run_manifest.json`

---

## 10. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P11_2_2_STATUS: NO-GO
RAW_FORWARD_RETURNS_PRIMARY: YES
SPY_BENCHMARK_FAIR: NO
POSITIVE_TRADEABLE_ALPHA: NO
POSITIVE_BH_SIGNIFICANT_FACTORS: 0
OOS_CONFIRMED: NO
PORTFOLIO_CONSTRUCTION_READY: NO
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
IBKR_CONNECTED: NO
```
