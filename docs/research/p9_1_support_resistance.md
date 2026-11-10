# P9.1 Support/Resistance + Candlestick + MACD/KDJ

Date: 2026-11-09
Status: **P9_1_NO_GO**

Research only. No shorting, leverage, options, PAPER-50000 or IBKR.

## 1. Data audit

- S&P 500 effective-dated membership.
- 1,095,490 all member-days.
- 981,362 `VALID_VERIFIED_TRADABLE` from P8.2.2.
- 109,132 unknown, 117 corrupt, 34 unresolved, 4,845 zero/stale.
- Adjusted OHLC reconstructed from `adjusted_close / close`; dividends are not
  separately added.
- Price panel: 2000-01-03..2024-12-31.
- BIL data starts **2007-05-30**; portfolio can only be tested from that date.
- Pivot levels use only bars through the formation date; a pivot is confirmed
  only after 5 right-side bars.

## 2. Fixed definitions

Support/resistance:

- 5 left + 5 right bars pivot;
- confirmation at pivot index +5;
- ATR(14);
- 0.5 ATR touch band;
- at least 2 confirmed pivots in the prior 252 sessions;
- support and resistance separately computed.

Candles:

- Bullish engulfing: prior bearish, current bullish, current body covers prior
  body.
- Bearish engulfing: mirror.
- Morning star: first long bearish body (≥0.5 ATR), second body ≤50% of first,
  third bullish close above first body midpoint.
- Evening star: mirror.

MACD 12/26/9; KDJ 9/3/3 with RSV and K/D initial 50. Confirmation only.

## 3. Event study

204,180 raw signal rows across 8 experiments; 204,030 valid event observations
after horizon labels; 611,790 experiment-horizon observations (same event counted
at 5/10/20 days). The 24 cells report overlapping and non-overlapping results;
no future labels are zero-filled. The three counts are not interchangeable.

Strongest event cells:

| Experiment | H | Events | Mean | HAC t | BH q | Non-overlap q |
|---|---:|---:|---:|---:|---:|---:|
| A_LEVEL_TOUCH | 20 | 110,786 | 0.97% | 16.2 | 0.000 | 0.000 |
| B_PATTERN_ONLY | 20 | 74,781 | 0.72% | 14.0 | 0.000 | 0.000 |
| C_SUPPORT_PATTERN | 20 | 6,074 | 0.68% | 3.19 | 0.004 | 1.6e-06 |
| E_C_KDJ | 20 | 3,032 | 0.97% | 3.49 | 0.0016 | 9.2e-08 |
| F_C_BOTH | 20 | 949 | 1.30% | 2.28 | 0.045 | 0.0035 |

The event screen shows direction, but overlapping events and large sample counts
inflate naive t-statistics; non-overlap diagnostics reduce event counts. Event
significance is not portfolio success.

## 4. Portfolio backtest

Rules:

- $50,000; 20% equity budget ($10,000), 80% BIL;
- max 5 positions, $2,000 each;
- entry next open after signal close;
- 20-session maximum hold;
- IBKR Pro Tiered fees from `tools/paper_trading/ibkr_costs.py`;
- 5 bps slippage per side, separate from fees;
- no shorts, no leverage.

| Experiment | CAGR | MaxDD | Sharpe | Trades | Gate |
|---|---:|---:|---:|---:|---|
| A_LEVEL_TOUCH | 1.98% | -13.59% | 0.40 | 782 | NO-GO |
| B_PATTERN_ONLY | 1.96% | -11.09% | 0.42 | 731 | NO-GO |
| C_SUPPORT_PATTERN | 1.04% | -9.86% | 0.32 | 553 | NO-GO |
| D_C_MACD | 0.83% | -14.60% | 0.2747 | 441 | NO-GO |
| E_C_KDJ | 1.80% | -8.17% | 0.6232 | 620 | NO-GO |
| F_C_BOTH | 1.25% | -10.10% | 0.5485 | 350 | NO-GO |
| G_LEVEL_ALL_PATTERNS | 1.04% | -9.86% | 0.3188 | 553 | NO-GO |
| H_G_BOTH | 1.25% | -10.10% | 0.5485 | 350 | NO-GO |

Benchmark:

```text
20% QQQ + 80% BIL: CAGR 2.09%, Sharpe 1.35, MaxDD -3.79%
20% SPY + 80% BIL: CAGR 1.95%, Sharpe 1.30, MaxDD -3.32%
BIL:               CAGR 1.15%, Sharpe 2.26, MaxDD -0.78%
```

Sharpe definition: mean daily NAV return / sample standard deviation of daily
returns × √252; no separate risk-free subtraction (BIL is the 80% cash leg).
The JSON NAV series is the source of truth. The earlier 0.23/0.47/0.33 values
were stale and are replaced by the reproducible values above.

All 8 experiments fail the relative benchmark test. C has a positive event
signal but only 1.04% CAGR vs 2.09% for 20QQQ/80BIL; no incremental economic
value after costs.

## 5. MACD / KDJ increment

- C → D (MACD): CAGR falls 1.04% → 0.83%; no improvement.
- C → E (KDJ): CAGR rises 1.04% → 1.80%, but remains below 20QQQ/80BIL.
- C → F (both): 1.25%; below benchmark and below E.
- G/H are duplicate entry sets for this long-only implementation.

MACD/KDJ do not create a qualifying incremental strategy. No filter is retained
just to preserve an indicator.

## 6. OOS and periods

Portfolio data starts 2007-05-30 because BIL is unavailable earlier.

C periods:

```text
2007-2012: CAGR +1.26%, MaxDD -8.47%
2013-2017: CAGR -0.34%, MaxDD -8.23%
2018-2024: CAGR +1.86%, MaxDD -4.20%
```

The positive OOS window is not sufficient: full-period and validation periods
do not beat the passive 20QQQ/80BIL benchmark.

## 7. Decision

```text
GO:            0
NO-GO:         8 experiments
DATA_BLOCKED:  BIL before 2007; NDX/DJI history; historical fundamental PIT;
               event/macro PIT; 2025-2026 data
```

Reasons:

- support/pattern event information exists, but not enough cost-adjusted
  economic value;
- MACD/KDJ incremental value is not sufficient;
- all portfolios underperform the same-risk-budget passive benchmark;
- no experiment meets GO.

No P9 shadow is launched. P8/P8.1/P8.2/P8.3/P8.4 history is preserved.

## 8. Files

```text
data/research/p9_1_support_resistance/
  data_audit.json
  p9_1_signals.csv.gz
  event_results.csv
  event_results_raw.csv
  event_hac.csv
  event_bh.csv
  portfolio_A_LEVEL_TOUCH.json
  portfolio_B_PATTERN_ONLY.json
  portfolio_C_SUPPORT_PATTERN.json
  portfolio_D_C_MACD.json
  portfolio_E_C_KDJ.json
  portfolio_F_C_BOTH.json
  portfolio_G_LEVEL_ALL_PATTERNS.json
  portfolio_H_G_BOTH.json
  p9_1_status.json
docs/research/p9_1_support_resistance.md
tests/test_p9_1_support_resistance.py
```
