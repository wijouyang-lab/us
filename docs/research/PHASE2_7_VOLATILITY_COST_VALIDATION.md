# Phase 2.7 Volatility Portfolios with Non-Overlapping 60D Holds

Date: 2026-10-30
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`
No PIT claim. No production changes.

## 1. Data / scope

- Factor panel: 1,239,013 rows, 503 current tickers, 2016-09-19..2026-10-28.
- Factors: ATR_Percent, Realized_Volatility_20D, Beta_60D.
- Test start: 2018-01-01.
- Hold: exactly 60 trading sessions.
- Signal at close; entry next open; exit open after 60 sessions.
- Next signal = prior exit close, so periods do not overlap.
- 36 complete periods; no invalid periods.
- Last incomplete period is not evaluated.

No formal PIT date exists per Phase 2.6.

## 2. Portfolio construction

For each factor:

- Q1 = lowest 20%;
- Q5 = highest 20%;
- Q5-Q1 = long high minus low (research only, no borrow/financing model);
- equal weight;
- inverse-volatility weight using only signal-date `Realized_Volatility_20D`;
- single-name cap 5%, normalized;
- entry/exit at open.

Benchmarks:

- equal-weight all eligible names;
- SPY buy-and-hold open-to-open over the same 60-session window.

## 3. Results, equal weight, 10 bps per side

| Factor | Leg | CAGR | Sharpe | Max DD | Turnover |
|---|---|---:|---:|---:|---:|
| ATR_Percent | Q1 | 6.13% | 0.55 | -9.6% | 0.70 |
| ATR_Percent | Q5 | **27.26%** | 0.85 | -28.3% | 0.70 |
| ATR_Percent | Q5鈭扱1 | **20.04%** | 0.66 | -29.2% | 0.70 |
| Realized_Volatility_20D | Q1 | 8.86% | 0.75 | -10.9% | 0.98 |
| Realized_Volatility_20D | Q5 | 23.78% | 0.77 | -29.0% | 0.98 |
| Realized_Volatility_20D | Q5鈭扱1 | 14.27% | 0.52 | -25.7% | 0.98 |
| Beta_60D | Q1 | 8.54% | 0.87 | -11.8% | 0.82 |
| Beta_60D | Q5 | 23.24% | 0.70 | -37.0% | 0.82 |
| Beta_60D | Q5鈭扱1 | 13.47% | 0.41 | -37.8% | 0.82 |

Benchmarks:

```text
Equal weight: CAGR 13.72%, Sharpe 0.81, MaxDD -15.96%
SPY buyhold:  CAGR 12.38%, Sharpe 0.74, MaxDD -22.56%
```

ATR Q5 and Q5鈭扱1 beat both benchmarks, but with much larger drawdowns.

## 4. Cost sensitivity (Q5鈭扱1, equal weight)

| Factor | 10 bps | 25 bps | 50 bps |
|---|---:|---:|---:|
| ATR_Percent | 20.04% | 20.15% | 20.32% |
| Realized_Volatility_20D | 14.27% | 14.38% | 14.55% |
| Beta_60D | 13.47% | 13.42% | 13.33% |

Costs do **not** eliminate the spread, but the spread is gross of borrow, short
availability, market impact, and financing. Higher-cost CAGR barely moves
because turnover is modest and both legs pay similar costs; the long-short
spread can even rise slightly when one leg's cost differs.

## 5. Volatility-adjusted weights

At 50 bps:

| Factor | Equal Q5 CAGR | Inv-vol Q5 CAGR | Equal Q5鈭扱1 | Inv-vol Q5鈭扱1 |
|---|---:|---:|---:|---:|
| ATR | 25.98% | 24.83% | 20.32% | 18.79% |
| Realized Vol | 21.98% | 20.27% | 14.55% | 13.02% |
| Beta | 21.54% | 18.80% | 13.33% | 11.33% |

Inverse-vol weights slightly reduce drawdowns but also reduce CAGR and spread;
they do not improve the case.

## 6. Annual stability (Q5鈭扱1, 10 bps)

| Year | ATR | Realized Vol | Beta |
|---|---:|---:|---:|
| 2018 | +14.3% | +7.0% | +4.8% |
| 2019 | -9.6% | -11.8% | -22.1% |
| 2020 | +57.4% | +36.2% | +34.3% |
| 2021 | -8.0% | -7.7% | -5.9% |
| 2022 | -1.9% | -7.5% | -11.9% |
| 2023 | +27.7% | +18.1% | +37.4% |
| 2024 | +15.5% | +16.7% | +19.4% |
| 2025 | +45.8% | +40.8% | +46.1% |
| 2026* | +51.4% | +46.8% | +36.4% |

*2026 partial: 3 periods.

Negative in 2019, 2021, 2022. The result is not every-year stable.

## 7. Market environments

Mean Q5鈭扱1 net 10 bps per period:

| Factor | Bear | Bull | High vol | Low vol | Trend | Range |
|---|---:|---:|---:|---:|---:|---:|
| ATR | 14.55% | 1.98% | 10.25% | 4.11% | 2.90% | 9.51% |
| Realized Vol | 11.30% | 1.26% | 7.75% | 3.00% | 1.90% | 7.43% |
| Beta | 13.32% | 0.78% | 7.87% | 3.23% | 2.03% | 7.77% |

All three are concentrated in bear/high-vol/range environments and weak in
bull/trend markets.

## 8. Information overlap

Correlation of period Q5鈭扱1 returns:

| | ATR | Realized Vol | Beta |
|---|---:|---:|---:|
| ATR | 1.00 | 0.984 | 0.940 |
| Realized Vol | 0.984 | 1.00 | 0.946 |
| Beta | 0.940 | 0.946 | 1.00 |

ATR and Realized Volatility are nearly the same portfolio; Beta adds little
independent information.

## 9. Answers

1. **ATR 60D relation survives non-overlapping holds?**
   Yes in this sample: Q5 CAGR 27.26%, Q5鈭扱1 20.04%, but with -29% max drawdown.

2. **Is Realized Volatility just ATR?**
   Largely yes: Q5鈭扱1 correlation 0.984.

3. **Does Beta add independent information?**
   No. Correlation 0.94鈥?.95 with the other two; lower Sharpe and larger DD.

4. **Only in bear/high-vol?**
   Mostly. Bull/trend spread is small; bear/high-vol/range much stronger.

5. **Do costs eliminate Q5鈭扱1?**
   Not at 10/25/50 bps in this simplified model. But borrow, short availability,
   market impact and financing are absent.

6. **Does vol scaling improve?**
   Slightly lower drawdown, lower return and lower spread; no clear improvement.

## 10. Decision

**No `VALIDATED_ALPHA`.**

Classification:

- `WEAK_EXPLORATORY`: ATR Q5/Q5鈭扱1 and Realized Vol Q5/Q5鈭扱1.
- `REJECTED_AS_INDEPENDENT`: Beta (overlaps ATR/RV, worse drawdown).
- `CANDIDATE`: none, because:
  - current-universe survivorship bias;
  - 713 historical tickers absent from the price panel;
  - delisting returns unresolved;
  - negative years 2019, 2021, 2022;
  - no borrow/financing/short-availability model;
  - max drawdown -29%;
  - no PIT membership date.

## 11. Artifacts

- `tools/research/volatility_portfolio_validation.py`
- `tools/research/volatility_portfolio_stability.py`
- `tests/test_volatility_portfolio_validation.py`
- `docs/research/volatility_portfolios_phase27_2026-10-30.json`
- `docs/research/volatility_portfolio_stability_2026-10-30.json`

Tests: 4 passed.
