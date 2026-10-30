# Phase 2.7.3 Accounting Integration

Date: 2026-10-30
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`
No production changes. Original reports preserved.

## 1. Shared accounting module hardened

`tools/research/portfolio_accounting.py`

Added validation:

- rejects NaN/Inf returns;
- rejects returns 鈮?鈭?00%;
- rejects empty returns;
- zero-volatility Sharpe 鈫?`None`;
- CAGR requires positive elapsed years;
- max drawdown from compounded equity.

Tests: `tests/test_portfolio_accounting.py`, **14 passed**.

## 2. Phase 2.3: partial fix, not yet a valid portfolio

Fixed in `technical_strategy_backtest.py`:

- removed `dropna(Fwd20)` look-ahead in universe selection;
- entry/exit dates now use actual trading sessions, not month-index offsets;
- CAGR uses actual first-entry to last-exit calendar time;
- Sharpe uses mean/std of period returns;
- max drawdown uses compounded equity;
- equal-weight/SPY use matched 20-session windows.

### Original vs recomputed, net 10 bps

| Strategy | Old CAGR | Old Sharpe | New CAGR | New Sharpe | New MaxDD |
|---|---:|---:|---:|---:|---:|
| Momentum20 | 15.01% | 0.793 | 13.97% | 0.788 | 鈭?3.9% |
| Momentum60 | 13.09% | 0.685 | 12.47% | 0.712 | 鈭?2.9% |
| Trend | 14.75% | 0.803 | 14.17% | 0.817 | 鈭?0.9% |
| RSI | 7.34% | 鈥?| 6.34% | 0.407 | 鈭?6.1% |
| MeanReversion | 8.45% | 鈥?| 7.47% | 0.422 | 鈭?5.1% |
| LowVol | 5.17% | 鈥?| 4.50% | 0.386 | 鈭?8.0% |
| ATR | 5.08% | 鈥?| 4.55% | 0.393 | 鈭?7.0% |

Benchmarks:

```text
Equal weight: CAGR 11.53%, Sharpe 0.689
SPY:          CAGR 10.25%, Sharpe 0.660
```

### Critical remaining issue: overlapping cohorts

Monthly signals with 20-session holds produce overlapping positions:

```text
120 candidate cohorts
41 overlapping next-signal-before-prior-exit cases
```

The code averages cohort returns but does **not** define capital allocation when
cohorts overlap. Therefore the new CAGR/Sharpe are **not yet an actual portfolio
return** and must not be treated as final.

Required next step: either

- use a non-overlapping 20-session schedule; or
- specify and implement capital allocation across simultaneous cohorts.

Until then, Phase 2.3 numbers remain provisional.

## 3. event_factor_backtest fixed

Old:

```python
gross - 4 * cost_bps_per_side
```

New:

- long turnover = actual member changes;
- short turnover independently;
- initial = 1 side each;
- replacement = 2 sides each;
- cost rate = bps 脳 (long units + short units);
- no trade 鈫?no cost.

Fields added:

```text
long_cost_units
short_cost_units
cost_rate
```

Existing event tests pass. Event research still lacks net execution validation
for all real frictions.

## 4. Other modules

| Module | Decision |
|---|---|
| `factor_quantile_backtest.py` | keep `GROSS_RETURN_ONLY`; no costs/net claim |
| `multi_strategy_comparison.py` | mean/std Sharpe and turnover cost correct for long-only; keep |
| `low_frequency_atr_*` | cost may be one-sided; flag, do not use as complete net |
| Phase 2.5 Q1鈥換5 | gross only; no net/Sharpe claim |
| Phase 2.7 | original invalid; use #416 corrected audit |
| Phase 2.7.1 | independent audit retained |

## 5. Tests

Targeted:

```text
20 passed
```

Coverage:

- accounting NaN/Inf/鈮も垝100%;
- long/short direction;
- 1x/2x capital;
- initial/zero-turnover cost;
- event turnover cost;
- technical CAGR/Sharpe date usage;
- drawdown equity curve.

Full CI after commit.

## 6. Still missing

- capital allocation for overlapping Phase 2.3 cohorts;
- borrow/financing/short dividends;
- market impact;
- historical PIT universe and delisting returns;
- Phase 2.6 has zero PIT dates.

## 7. Conclusion

Phase 2.3 accounting is improved but **not complete** because of overlapping
cohorts. No new strategy optimization should begin. Phase 2.7 original numbers
remain superseded by #416; Phase 2.5 remains gross-only.
