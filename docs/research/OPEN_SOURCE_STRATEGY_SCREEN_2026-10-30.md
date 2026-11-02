# Open-Source Strategy Screen and Actual Backtests

Date: 2026-10-30
Research branch: `research/qlib-inspired-low-frequency-strategy`
Panel: `price10y_1028.csv` (local, not PIT; current-universe survivorship risk)
Window: 2016-09-19 .. 2026-10-28, 1,239,013 rows, 503 tickers

## 1. Executed candidate

Qlib-inspired composite, fixed pre-registered weights:

| Feature | Weight |
|---|---:|
| 12-1 momentum | 0.35 |
| 100-day trend | 0.25 |
| 60-day low volatility | 0.20 |
| 5-day reversal | 0.10 |
| dollar-volume trend | 0.10 |

Month-end close signal; next open entry; exit at open 20 sessions later;
top quintile, equal weight; same-universe equal-weight benchmark.

### Test period 2023-01-01 onward

| Cost | Ann. net | Sharpe | Max DD | Excess ann. | Excess Sharpe |
|---:|---:|---:|---:|---:|---:|
| 5 bps | 17.21% | 1.19 | -13.61% | 4.37% | 0.53 |
| 10 bps | 16.95% | 1.17 | -13.69% | 4.15% | 0.51 |
| 20 bps | 16.43% | 1.14 | -13.85% | 3.71% | 0.45 |

Observations: 44 months. Mean turnover: 0.378. Mean selected: 98.4 names.

Annual net returns at 10 bps:

| Year | Strategy | Benchmark | Excess |
|---|---:|---:|---:|
| 2023 | +11.62% | +7.25% | +4.37% |
| 2024 | +31.33% | +18.72% | +12.61% |
| 2025 | +10.86% | +14.79% | -3.92% |
| 2026 (8 months) | +9.26% | +4.16% | +5.09% |

## 2. Factor ablations (same panel, 2023+, 5 bps)

| Variant | Ann. net | Excess ann. |
|---|---:|---:|
| 12-1 momentum only | 26.49% | 13.31% |
| 100-day trend only | 19.68% | 6.73% |
| 5-day reversal only | 11.31% | -0.68% |
| 60-day low vol only | 3.70% | -8.19% |
| Composite | 17.21% | 4.37% |

Momentum dominates the recent-period result. The composite dilutes momentum
with low-vol, which underperformed badly in this window.

## 3. Earlier-period check (2018-2022, 10 bps)

This is a time-separated check, not an independent confirmation, because the
candidate design was chosen with awareness of the overall literature and data.

| Variant | Strategy ann. | Benchmark ann. | Excess ann. | Excess Sharpe |
|---|---:|---:|---:|---:|
| Composite | 7.81% | 10.90% | **-3.82%** | -0.44 |
| Momentum only | 11.20% | 10.90% | **-0.19%** | -0.02 |

The recent outperformance does not survive the earlier period.

## 4. Decision

**Do not promote the Qlib-inspired composite.**

Reasons:

1. 2023-2026 excess is positive but 2025 is negative.
2. 2018-2022 composite excess is negative (-3.82% annualized).
3. Momentum-only is strong in 2023-2026 but essentially zero excess in
   2018-2022; this is regime-dependent, not stable.
4. Current-universe panel has survivorship bias; no historical index membership.
5. Results are not PIT; no event timestamps or first-seen evidence are involved.
6. Monthly 20-session cohorts overlap and are serially dependent; no
   significance claim.
7. Costs are assumptions, not measured execution.

**Candidate status: research-only, rejected for promotion.**

## 5. Open-source projects screened

| Project | What was usable | Decision |
|---|---|---|
| Microsoft Qlib | Alpha158-style cross-sectional rank workflow | adopted pattern; no dependency |
| Backtrader | event-driven backtest engine | not adopted; existing vectorized panel sufficient |
| QuantConnect LEAN | full engine + data model | not adopted; too heavy for this panel |
| FinRL | RL training stack | not adopted; needs different data/objective and no PIT evidence |

No third-party code was copied or vendored. Framework results are not comparable
to this panel without importing their data and execution assumptions.

## 6. Missing data / blocked items

- No point-in-time index membership 鈫?survivorship bias remains.
- No fundamentals in the price panel 鈫?quality/value/profitability cannot be
  tested this round.
- No delisted-security panel 鈫?cannot remove survivorship bias.
- No independent untouched period after design selection 鈫?no clean OOS.
- SEC first-public-visibility remains unverified; event PIT count is 0.

## 7. Reproduce

```bash
python -m tools.research.qlib_inspired_low_frequency_strategy \
  --price-panel ../price10y_1028.csv \
  --output-prefix docs/research/qlib_low_frequency_10bps_2026-10-30 \
  --cost-bps 10

python -m tools.research.qlib_factor_ablations
python -m tools.research.qlib_earlier_period
```

Outputs:

- `qlib_low_frequency_{5,10,20}bps_2026-10-30.json/.csv`
- `qlib_factor_ablations_2026-10-30.json`
- `qlib_earlier_period_2018_2022_2026-10-30.json`
