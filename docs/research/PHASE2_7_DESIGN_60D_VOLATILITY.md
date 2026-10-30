# Phase 2.7 Design 鈥?60D Volatility Factors, Non-Overlapping

Status: design only; do not run until Phase 2.6 data gates are resolved.

## Candidates

- 60D ATR_Percent (high-volatility long leg)
- 60D Realized_Volatility_20D
- 60D Beta_60D
- SPY buy-and-hold
- equal-weight current universe benchmark

## Core test

- Signal at month-end close; enter next open.
- Hold exactly 60 trading sessions; **no overlapping cohorts**.
- Rebalance only after exit.
- Rank eligible stocks; long top quintile; optional short bottom quintile.
- Equal weight and inverse-volatility weight variants.
- Weights normalized to 1; cash earns 0 unless specified.

## Data gate

Only dates whose membership is:

- from an official/high-confidence historical source;
- with effective date evidence;
- with matching OHLCV;
- with delisting return handling;

may be labelled `PIT`.

Current Phase 2.6 data fails these gates, so the first run must be labelled
`EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`, not PIT.

## Costs

Per side: **10, 25, 50 bps**.
Charge both entry and exit; initial buy = one side, replacement = buy + sell.
Report gross and net separately; never net only.

## Benchmarks

- SPY buy-and-hold, independent price series;
- equal-weight same eligible universe;
- same dates and holding periods.

## Metrics

CAGR, annualized vol, Sharpe (0 risk-free), max drawdown, turnover, trades,
excess vs EW, excess vs SPY, per-year and regime breakdown.

## Regimes

Pre-defined at month-end using SPY:

- bull/bear: close vs 200D MA;
- high/low vol: 20D annualized vol vs 20%;
- trend/range: |200D return| vs 10%.

No regime defined using future returns.

## Multiplicity

Three factors 脳 two weighting schemes 脳 three cost levels. Report all, not only
best. No parameter search; no repeated threshold tuning.

## Failure criteria

Reject if:

- no non-overlapping windows;
- sign flips across years or regimes;
- net excess disappears at 25 bps;
- result depends on one year;
- membership/price coverage below gate;
- delisting returns unavailable and material.

## Forbidden

- using current 503 names as PIT;
- filling delisting returns with zero;
- overlapping 60D cohorts;
- selecting parameters on the test period;
- claiming alpha from IC significance.
