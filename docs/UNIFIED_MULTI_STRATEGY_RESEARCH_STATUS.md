# Unified Multi-Factor Low-Frequency Research Status

> **Data-validity hold — latest refresh attempt 2026-10-22:** [Run 39736390746](https://github.com/wijouyang-lab/us/actions/runs/39736390746) failed its publication gate after applying the CIK-guarded alias registry. For the 2016-10-21 to 2026-10-21 research window, member-session coverage improved to **91.01%** (1,169,733 of 1,285,347 expected bars); **591 of 714 historical tickers (82.77%)** met the 90% individual coverage threshold. The workflow still requires at least 95% member-session coverage and at least 98% ticker coverage. The alias registry canonicalized 26 same-issuer symbol rows, and single-ticker fallback recovered 11 symbols, but **123 tickers remain below the per-ticker threshold**. The gate blocked publication and previous research CSV inputs were preserved. The current audit is archived as artifact `12407587840` (`pit-price-refresh-audit-39736390746`).
>
> The older reports below were generated from a static price CSV whose last signal date was 2026-09-16, despite the workflow completing successfully on 2026-10-22. They are historical diagnostics, **not a valid point-in-time strategy ranking**. Do not promote or select a strategy using those metrics. The remaining gaps include renamed/delisted historical symbols and some symbols whose individual Yahoo Finance response contains no usable OHLC rows; this run does not prove every missing symbol is truly delisted. The 26-entry same-CIK alias registry improves coverage but is not enough. Next work must distinguish genuine historical delistings from still-trading symbols that the provider fails to return, and evaluate a second source for those gaps. Do not lower the coverage thresholds to make the refresh pass.

**Status date:** 2026-10-22  
**Scope:** research-only. No production scoring, scan, stops, portfolio, or ledger changes.

## Data sources and method

- Prior 10Y PIT snapshot artifact: [run 39712671160](https://github.com/wijouyang-lab/us/actions/runs/39712671160) completed successfully on 2026-10-22, but reused static price inputs ending at signal date 2026-09-16; diagnostic only.
- Prior 7-strategy comparison: [run 39726814223](https://github.com/wijouyang-lab/us/actions/runs/39726814223) generated full reports successfully, but its 10Y leg depended on that stale price input; diagnostic only. The newer gated refresh failed as documented above, so no fresh comparison was produced.
- Portfolio: rank the factor cross-section each signal date; equal-weight the top or bottom 20%; 20-session forward-return horizon; non-overlapping observations; 20 signal-date purge at train/validation/test boundaries.
- Strategy direction is selected using training data only and then held fixed for validation and test. Costs are turnover-based estimates at 5/10/20 bps per side, not a fill-level slippage model.
- Candidate factors: ATR percent, realized 20-day volatility, 20-day Z-score, RSI, 20-day momentum, 60-day momentum, and 5-day MA20 slope.

## 10Y PIT comparison — 7 strategies

Input panel: 1,038,059 merged ticker/date rows, 498 tickers, 2,453 valid signal dates from 2016-12-12 to 2026-09-16. Each strategy has 24 non-overlapping test observations.

### Test set (10 bps per side)

| Strategy | Factor | Frozen direction | n | Gross return / 20D | Net return / 20D | Net excess vs equal-weight panel | Win rate | Rough Sharpe | Max drawdown | Turnover |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ATR volatility | ATR_Pct | HIGH | 24 | +2.244% | +2.190% | +1.480% | 75.0% | 1.99 | -11.250% | 29.261% |
| Realized volatility | Realized_Volatility_20D_Pct | HIGH | 24 | +1.935% | +1.838% | +1.128% | 70.8% | 1.60 | -13.720% | 50.883% |
| Mean reversion | ZScore_20D | LOW | 24 | +0.389% | +0.229% | -0.480% | 66.7% | 0.32 | -10.633% | 82.060% |
| RSI signal | RSI | LOW | 24 | +0.466% | +0.327% | -0.382% | 66.7% | 0.45 | -9.447% | 71.508% |
| 20D momentum | Momentum_20D_Pct | LOW | 24 | +0.656% | +0.501% | -0.209% | 62.5% | 0.68 | -8.990% | 79.616% |
| 60D momentum | Momentum_60D_Pct | LOW | 24 | +0.601% | +0.512% | -0.197% | 54.2% | 0.59 | -8.693% | 46.515% |
| MA-slope reversal | MA20_Slope_Pct_5D | LOW | 24 | +0.610% | +0.458% | -0.252% | 58.3% | 0.50 | -8.454% | 78.023% |

### 10Y test cost sensitivity

Net mean return per 20-session observation:

| Strategy | 5 bps / side | 10 bps / side | 20 bps / side |
|---|---:|---:|---:|
| ATR volatility | +2.217% | +2.190% | +2.135% |
| Realized volatility | +1.886% | +1.838% | +1.740% |
| Mean reversion | +0.309% | +0.229% | +0.069% |
| RSI signal | +0.397% | +0.327% | +0.188% |
| 20D momentum | +0.578% | +0.501% | +0.346% |
| 60D momentum | +0.557% | +0.512% | +0.424% |
| MA-slope reversal | +0.534% | +0.458% | +0.306% |

**Reading:** in this exploratory holdout-like segment, ATR and realized-volatility factors show positive net excess over the equal-weight panel; the other five show negative net excess. That is a descriptive observation, not proof of live alpha or a sufficient basis to pick a live strategy. There are only 24 observations and the same source panel has been used in prior exploratory research, so this is not an untouched final holdout.

## 2Y PIT comparison — same 7 factors

Input panel: 212,869 rows, 498 tickers, 443 signal dates from 2024-12-09 to 2026-09-16. The test segment has only **4 non-overlapping observations**, so every result is insufficient evidence regardless of its point estimate.

| Strategy | Frozen direction | n | Net return / 20D | Net excess vs equal-weight panel | Assessment |
|---|---|---:|---:|---:|---|
| ATR volatility | HIGH | 4 | +1.671% | +1.524% | Insufficient evidence |
| Realized volatility | HIGH | 4 | +1.302% | +1.154% | Insufficient evidence |
| Mean reversion | LOW | 4 | +0.289% | +0.141% | Insufficient evidence |
| RSI signal | LOW | 4 | +1.537% | +1.390% | Insufficient evidence |
| 20D momentum | HIGH | 4 | -0.485% | -0.633% | Insufficient evidence |
| 60D momentum | HIGH | 4 | -1.742% | -1.890% | Insufficient evidence |
| MA-slope reversal | HIGH | 4 | +0.272% | +0.124% | Insufficient evidence |

Because n=4, the 2Y panel is not useful for reliable strategy ranking.

## Separate ATR execution checks

The fresh 10Y snapshot workflow also regenerated the dedicated ATR reports. These have different implementations/entry conventions from the common seven-factor panel and should be read as separate robustness checks.

- Dedicated close-to-close ATR: test (n=24), net mean return **+2.215%**, net excess **+1.505%** at 10 bps per side.
- Next-open entry validation: test (n=24), net mean return **+2.196%**, net excess **+1.460%** at 10 bps per side.

## Limits and next research gates

1. The source OHLC is unadjusted, so splits and dividends can distort return calculations.
2. Historical constituent membership lacks complete exit dates. The panel therefore does not guarantee strict point-in-time membership and may retain survivorship bias.
3. Cost modeling is turnover-based; fills, spreads, market impact, rejected orders, stop-order paths, liquidity, and portfolio constraints are not fully simulated.
4. Seven candidates increase multiple-comparison/data-mining risk. Selection of factors and directions on this already-explored panel may overstate generalization.
5. Do not promote any strategy into production based on these results. Next gates are split/dividend-adjusted prices, complete historical membership entry/exit dates, regime and walk-forward robustness, and execution-level validation on an untouched holdout.

## Engineering and safety status

- The multi-factor comparator was vectorized to rank each factor/date panel once rather than repeating the expensive grouping for every direction, split, and cost scenario.
- A regression test verifies that the vectorized daily portfolio constituents match the previous reference implementation, with only floating-point aggregation tolerance.
- Production scoring, scan, stops, portfolio, and ledger behavior remain unchanged.
