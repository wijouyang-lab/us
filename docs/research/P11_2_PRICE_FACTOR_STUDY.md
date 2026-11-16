# P11.2: Price-Factor Predictive Study

Date: 2026-11-17
Branch: `research/p11-individual-stock-selection`
Status: **NO-GO for tradeable alpha; PARTIAL statistical evidence**

---

## 1. Scope and design

This is an individual-stock price-factor study, not an ETF strategy and not a
new trading system.

- source: local FINSABER S&P 500 price panel;
- price symbols: 1,017 (983 with 2007+ observations);
- membership: PIT snapshot expansion, not a fixed current list;
- dates: 2000-01-03..2024-12-31;
- SPY: market benchmark;
- BIL: cash benchmark where covered;
- factors: 20;
- horizons: 5/10/20 trading days;
- cells: 60 factor-horizon tests;
- cost assumption: 20 bps round-trip;
- winsorization: 1/99% cross-section before IC/quintiles.

Signal at close t; entry next adjusted open; exit adjusted close t+h.
SPY uses close-to-close as a documented proxy because no SPY open series is
stored.

Full definitions: `P11_2_FACTOR_DEFINITIONS.md`.

---

## 2. PIT and universe limits

The price file has 1,017 symbols over 2000-2024, but only ~500 members are
available on a typical date. The PIT-filtered union is 887 tickers, not 1,017.

Known limitations:

- 80 zero-member tickers;
- 62 unresolved identity cases;
- 9 ticker-reuse conflicts;
- no full OTC/microcap/delisted universe;
- volume is raw, not split-normalized; volume factors are `DATA_LIMITED`;
- PIT membership snapshots are not a perfect daily membership source.

This is a **restricted S&P 500 diagnostic**, not a full-market backtest.

---

## 3. Results

File: `data/research/p11_2/p11_2_factor_results.csv`

### Statistical highlights

```text
factor-horizon cells: 60
BH q < 0.05:            2
both are mom5 negative:
  mom5 / 5d:  IC -0.0144, q 0.0026, net top10 -0.163%
  mom5 / 10d: IC -0.0125, q 0.0419, net top10 -0.171%
```

This is a weak short-horizon reversal signal, not a long-only alpha:

- IC is negative, so high past 5-day winners underperform;
- the top decile is also negative after cost;
- the economic magnitude is far below a viable strategy;
- 58 of 60 cells do not survive BH at 5%.

### Positive results after cost

The largest positive net top-decile figures are tiny:

```text
vol_change / 20d: +0.189% (q 0.963)
vol_anom20 / 20d: +0.139% (q 0.823)
mom120/rs120/slope120 / 20d: +0.098% (q 0.823)
```

None has BH evidence; all are within noise.

### OOS

```text
OOS period: 2018-2024
best OOS mean IC: vol_change/10d = +0.00398
```

That is economically negligible. No factor has a stable, positive, cost-adjusted
OOS top-decile result.

### Quintiles

`p11_2_quintile_returns.csv` contains 60 factor-horizon quintile means. The
spread is noisy and generally not monotonic.

### Factor correlation

`p11_2_factor_correlation.csv` shows the expected clusters:

- mom5/mom10/mom20;
- rs20/rs60/rs120;
- slope20/slope60/slope120;
- dd20/dd60/dd120.

No combination was selected/reoptimized after seeing OOS results.

---

## 4. Direct answers

1. **Which factors predict?**
   Only a weak negative 5-day momentum effect; no positive predictor with
   meaningful magnitude.

2. **Survive multiple testing?**
   Two negative mom5 cells, q<0.05. They do not create a long-only strategy.

3. **Stable across years?**
   No. Momentum is negative in dev/val/OOS, but the economic effect is small;
   vol factors change sign.

4. **OOS?**
   No economically meaningful OOS factor.

5. **Combinations better?**
   Not tested for optimization; correlation clusters show redundancy. No
   evidence to justify a multi-factor portfolio.

6. **After costs?**
   No. Best positive net is +0.19% per 20-day top-decile, statistically
   indistinguishable from zero.

7. **Survivorship/universe issues?**
   Yes. Restricted S&P 500 panel, missing tickers, identity conflicts, volume
   adjustments. Results are diagnostic, not production.

8. **Next stage portfolio construction?**
   **NO-GO.** Do not build a portfolio from these price factors.

---

## 5. Stage decision

```text
P11_2_STATUS: NO-GO
STATISTICAL_EVIDENCE: PARTIAL (2/60 negative mom5 cells)
TRADEABLE_ALPHA: NO
OOS_CONFIRMED: NO
COST_ADJUSTED_ALPHA: NO
PORTFOLIO_CONSTRUCTION_READY: NO
```

No new strategy is declared. P9's eight NO-GO results and P10 NO_BUY remain
unchanged.

---

## 6. Why not proceed to P11.3

- no positive factor survived economic and statistical filters;
- fundamental data is current-only and cannot be joined historically for
  2007-2024;
- event/news data is incomplete;
- full-market universe is unavailable;
- the observed effects are too small relative to costs.

A fundamentals study would need a PIT panel first; this phase does not provide
one.

---

## 7. Files

- `data/research/p11_2/p11_2_factor_results.csv`
- `data/research/p11_2/p11_2_annual_ic.csv`
- `data/research/p11_2/p11_2_quintile_returns.csv`
- `data/research/p11_2/p11_2_factor_correlation.csv`
- `data/research/p11_2/p11_2_experiment_config.json`
- `data/research/p11_2/p11_2_summary.json`
- `tools/research/p11/factor_study.py`
- `docs/research/P11_2_FACTOR_DEFINITIONS.md`

All results are aggregate; no raw market data is committed.

---

## 8. Final status

```text
P11_2_STATUS: NO-GO
PRICE_FACTOR_RESEARCH: COMPLETED_RESTRICTED
TRADEABLE_ALPHA: NO
OOS_CONFIRMED: NO
PORTFOLIO_CONSTRUCTION_READY: NO
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
IBKR_CONNECTED: NO
```
