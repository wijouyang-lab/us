# Phase 2.7.4 Non-Overlapping 20D Portfolio

Date: 2026-10-30
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`
No production changes.

## 1. Design

- Initial signal: first eligible date after 2018-01-01.
- Signal at close.
- Entry next open.
- Hold exactly 20 trading sessions.
- Exit at open.
- Next signal = prior exit close; next entry next open.
- No overlapping cohorts; 100% capital per period, cash between periods.
- Equal weight; no additions/removals inside a period.
- Missing selected price 鈫?entire period invalid; no shrinking.
- 105 complete periods; 0 invalid.
- Actual window: 2018-02-01..2026-10-28.

This is **not** the same experiment as the monthly-cohort model: the signal
frequency is lower and the capital model is now explicit.

## 2. Performance at 10 bps per side

| Strategy | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|
| Momentum20 | 6.48% | 0.42 | 鈭?4.1% |
| Momentum60 | 8.48% | 0.51 | 鈭?4.0% |
| Trend | 9.09% | 0.54 | 鈭?4.7% |
| RSI | 5.38% | 0.35 | 鈭?2.6% |
| MeanReversion | **10.14%** | 0.54 | 鈭?0.7% |
| LowVol | 3.05% | 0.28 | 鈭?1.4% |
| ATR | 1.66% | 0.19 | 鈭?0.9% |
| Equal weight | 6.84% | 0.45 | 鈭?6.1% |
| SPY buyhold | **12.80%** | 0.73 | 鈭?4.1% |

No strategy beats SPY. MeanReversion beats equal weight but has 鈭?0.7% drawdown.

## 3. Cost sensitivity

CAGR at 10 / 25 / 50 bps:

| Strategy | 10 | 25 | 50 |
|---|---:|---:|---:|
| Momentum20 | 6.48% | 2.72% | 鈭?.26% |
| Momentum60 | 8.48% | 4.64% | 鈭?.46% |
| Trend | 9.09% | 5.24% | 鈭?.89% |
| RSI | 5.38% | 1.66% | 鈭?.27% |
| MeanReversion | 10.14% | 6.25% | 0.06% |
| LowVol | 3.05% | 鈭?.59% | 鈭?.39% |
| ATR | 1.66% | 鈭?.93% | 鈭?.65% |

**At 50 bps, all strategies are 鈮?% CAGR.** Costs eliminate the apparent edge.

## 4. Annual results (10 bps)

| Year | Momentum20 | Trend | MeanRev | LowVol | ATR |
|---|---:|---:|---:|---:|---:|
| 2018 | 鈭?5.7% | 鈭?2.2% | 鈭?5.8% | 鈭?1.4% | 鈭?.9% |
| 2019 | +24.5% | +18.0% | +27.9% | +22.7% | +20.4% |
| 2020 | +4.5% | +10.5% | +11.7% | +1.1% | 鈭?.6% |
| 2021 | +22.7% | +22.2% | +31.6% | +18.6% | +16.5% |
| 2022 | 鈭?4.1% | 鈭?5.5% | 鈭?.4% | 鈭?.2% | 鈭?.1% |
| 2023 | +14.2% | +15.3% | +12.1% | +0.9% | +1.1% |
| 2024 | +18.1% | +16.7% | +24.6% | +9.1% | +9.3% |
| 2025 | +13.9% | +12.9% | +1.2% | 鈭?.5% | 鈭?.5% |
| 2026* | +9.2% | +18.5% | +10.8% | 鈭?.8% | 鈭?.1% |

*2026 through 2026-10-28.

## 5. Market environment

Mean daily return annualized by SPY regime (10 bps):

| Strategy | Bear | Bull | High vol | Low vol |
|---|---:|---:|---:|---:|
| Momentum20 | 鈭?5.9% | +19.2% | 鈭?.7% | +11.0% |
| Trend | 鈭?5.5% | +22.1% | +1.1% | +13.4% |
| MeanReversion | 鈭?7.1% | +22.0% | +8.2% | +13.4% |

These are annualized mean daily returns, not CAGR. The full trend/range table is
in `nonoverlap_summary_2026-10-30.json`.

The full regime table is in `nonoverlap_summary_2026-10-30.json`. In general,
strategies remain weak in the 2018 and 2022 bear/high-vol periods; MeanReversion
is strongest in 2019/2021, not consistently.

## 6. Comparison with monthly cohort model

| Item | Monthly cohort (old) | Non-overlap (new) |
|---|---:|---:|
| Signal frequency | monthly | every 20 sessions |
| Cohorts | 120 candidate | 105 complete |
| Overlaps | **41** | **0** |
| Momentum20 CAGR | 13.97% | 6.48% |
| Trend CAGR | 14.17% | 9.09% |
| MeanReversion CAGR | 7.47% | 10.14% |
| Capital model | average of cohorts; not merged | 100% per period, cash |
| Validity | provisional | valid non-overlap design |

The two are **different experiments**, not a simple correction. The monthly
model's higher momentum/trend result depended on overlapping cohorts and
undefined capital allocation.

## 7. Tests

`tests/test_nonoverlap_portfolio_backtest.py`: **3 passed**

- adjacent periods do not overlap;
- each period is 20 held sessions;
- next signal = prior exit;
- incomplete last period excluded;
- deterministic schedule.

Full CI after commit.

## 8. Remaining limits

- current 503-name universe, survivorship bias;
- 713 historical tickers missing from price panel;
- no delisting returns;
- no Phase 2.6 PIT dates;
- no dividends;
- no borrow/financing (long-only here, but cash return 0);
- no market impact/slippage beyond bps;
- 2026 partial.

## 9. Conclusion

**No strategy is validated.**

- Non-overlap Momentum20/Trend underperform SPY;
- MeanReversion has highest CAGR but 鈭?0.7% DD and fails at 50 bps;
- all strategies are 鈮?% at 50 bps;
- the monthly-cohort result cannot be used as the actual portfolio result.

## 10. Artifacts

- `tools/research/nonoverlap_portfolio_backtest.py`
- `tools/research/nonoverlap_stability.py`
- `tools/research/nonoverlap_summary.py`
- `tests/test_nonoverlap_portfolio_backtest.py`
- `docs/research/nonoverlap_portfolios_phase274_2026-10-30.json` (local detail)
- `docs/research/nonoverlap_summary_2026-10-30.json`
- `docs/research/nonoverlap_stability_2026-10-30.json`
