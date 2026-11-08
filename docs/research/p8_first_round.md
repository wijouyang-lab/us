# P8 First-Round Quantitative Research

Date: 2026-11-08
Status: **P8_FIRST_ROUND_NO_GO · RESEARCH_ONLY · PIT_PARTIAL**

> P8.1 audit supersedes the original full-period CAGRs; see p8_1_audit.md.
> The 41-51% CAGRs were caused by contaminated price symbols.

This is the first round of the 10-day plan, not a completed 10-day project. It
uses existing infrastructure and reports actual results, including negative
results.

## 1. Inventory

| Module | Done | Reuse | Missing | Action |
|---|---|---|---|---|
| SEC CompanyFacts / filings | yes | yes | not every issuer cached | reuse |
| yfinance OHLCV | yes | yes | free provider, not execution-grade | reuse with quality checks |
| S&P 500 historical membership | yes | yes | latest snapshot 2026-08-18 | effective-date PIT |
| Nasdaq-100 membership | **no** | no | no interval file | **DATA_BLOCKED** |
| Dow 30 membership | **no** | no | no interval file | **DATA_BLOCKED** |
| Raw PIT price panel | yes | yes | ends 2024-12-31 | historical only |
| PIT recovery gate | yes | yes | prior 91.61%/98 missing retained | do not re-search failed sources |
| Factor engine | yes | yes | 503 current tickers, survivorship-biased | use only with PIT membership |
| HAC / Newey-West | partial | yes | not unified before | P8 reusable function |
| Multiple testing | no | no | no registry | P8 BH implementation |
| Walk-forward / label purge | yes | yes | not connected to P8 yet | deep-validation phase |
| Cost model | yes | yes | paper 5bps+0.5bps vs P8 10bps research | documented |
| Qlib | no | no | no verified adapter | not used |
| Value/Quality/GARP | yes | yes | P6.17 caveats | P7.1 Value only refreshed |
| P7 portfolio / shadow / Lab | yes | yes | shadow pending | reuse |

Detailed machine-readable inventory:

```text
data/research/p8/inventory.json
data/research/p8/universe_membership.csv
data/research/p8/universe_summary.json
```

## 2. Universe and PIT tiers

Current decision universe:

- S&P 500 last available snapshot: **2026-08-18**, 503 tickers.
- Nasdaq-100 / Dow 30: no historical interval file; **DATA_BLOCKED**.
- Current lists are not substituted for historical membership.

Historical PIT:

- effective-dated S&P 500 membership from `sp500_daily.csv`;
- price panel `finsaber_prices_raw.csv`, 2000-01-03..2024-12-31;
- mean available-member coverage in the PIT backtest: **92.45%**;
- prior 91.61% ten-year coverage and 98 missing OHLCV tickers remain recorded
  as data limitations.

Historical PIT does not block current research, but it does block claims of
historical Alpha/Sharpe for current 2026 strategies.

## 3. PIT equity technical screen

Method:

```text
month-end signal
next-session adjusted open entry
next month next-session adjusted open exit
top 20 equal weight
10 bps per side
monthly HAC (6 lags)
Benjamini-Hochberg across tested strategies
2015-2024 out-of-sample
```

Coverage: **92.45%**. Months: 298 (2000-01..2024-10). OOS: 118 months.

| Strategy | Full CAGR | OOS CAGR | Sharpe | OOS Sharpe | HAC t | BH q | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| Momentum 20 | 49.2% | 3.1% | 0.43 | 0.26 | 1.65 | 0.264 | NO-GO |
| Momentum 60 | 41.1% | 6.1% | 0.41 | 0.40 | 1.37 | 0.229 | NO-GO |
| Momentum 120 | 51.2% | 10.1% | 0.45 | 0.59 | 1.77 | 0.309 | NO-GO |
| Trend MA200 | 50.0% | 6.8% | 0.44 | 0.45 | 1.47 | 0.282 | NO-GO |
| Low Vol 60 | 11.0% | 10.4% | 0.89 | 0.84 | -2.41 | 0.127 | NO-GO |
| Reversal 5 | 38.1% | 6.2% | 0.48 | 0.37 | 1.39 | 0.262 | NO-GO |

The large full-period CAGR is not a validated edge: OOS returns collapse, HAC
t-statistics are below the pre-registered 1.64 threshold for the long-only
strategies, and all BH q-values exceed 0.10.

## 4. ETF multi-asset screen

Universe: SPY, QQQ, IWM, TLT, GLD, BIL. Adjusted-close proxy. 2008-02..2024-11.

| Strategy | CAGR | Sharpe | Max DD | OOS CAGR | OOS Sharpe |
|---|---:|---:|---:|---:|---:|
| Trend risk | 6.63% | 0.62 | -22.96% | 4.57% | 0.47 |
| Risk parity | 7.13% | 0.66 | -23.86% | 4.04% | 0.42 |
| SPY | 10.24% | 0.70 | -50.78% | 13.00% | 0.88 |
| QQQ | 15.61% | 0.87 | -49.74% | 18.26% | 1.00 |
| IWM | 7.34% | 0.45 | -52.47% | 7.75% | 0.46 |

Both ETF strategies reduce drawdown but underperform SPY/QQQ on OOS return and
Sharpe. They are **NO-GO** for shadow launch.

## 5. GO / NO-GO

```text
GO:       0
NO-GO:    8
DATA BLOCKED: Nasdaq-100, Dow 30, Qlib adapter
```

Files:

```text
data/research/p8/pit_strategy_results.json
data/research/p8/etf_multiasset_results.json
data/research/p8/strategy_gate_results.csv
data/research/p8/p8_status.json
```

No strategy is promoted to `RESEARCH_SHADOW_P8` because none passed the
pre-registered gates.

## 6. Remaining work

- Acquire/historical-validate Nasdaq-100 and Dow 30 interval membership.
- Extend the price panel to 2025-2026 for current OOS tracking (without mixing
  with the historical PIT).
- Connect walk-forward/label-purge to the P8 evaluator.
- Run factor-family (Value/Quality/GARP/Momentum/LowVol) unified tests.
- Run event/macro feasibility without pretending data exists.
- Only after a strategy passes gates: create `RESEARCH_SHADOW_P8`; do not touch
  PAPER-50000.

## 7. Boundaries

- No Alpha, no production readiness, no options/short/leverage.
- No PAPER-50000 or IBKR interaction.
- No current-index substitution for historical backtests.
- PR #512 remains Draft and unmerged.
