# Phase 2.3 Momentum / Trend Walk-Forward Validation

Date: 2026-10-30
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`

## 1. PR #410

Merged: `0ea760dcbd4fccc915f1b352fb43bc7905c396f6`
CI: 1332 passed, 1 skipped.

## 2. Structural fixes before re-running

The Phase 2.2 technical backtest had a look-ahead defect:

```python
elig = day[...].dropna(subset=["Fwd20"])
```

This removed stocks whose future price was missing **before** ranking, so future
availability influenced the portfolio. Fixed:

- eligibility uses only signal-time price/liquidity;
- selected stock with missing future price invalidates that cohort;
- the portfolio is not silently shrunk.

Cost accounting was also understated:

- initial buy = 1 side;
- replacement = buy + sell = 2 sides;
- net = gross 鈭?cost_bps 脳 cost_units.

The benchmark is equal-weight of the same eligible universe; SPY is an
independent price series. All strategies use the same month-end dates.

## 3. Walk-forward setup

| Item | Value |
|---|---|
| Test years | 2021鈥?026 |
| Burn-in / training context | 2018鈥?020 |
| Test window | 1 calendar year |
| Strategy parameters | fixed; no tuning |
| Rebalance | month-end signal, next open |
| Hold | 20 sessions |
| Costs | 5 / 10 / 20 / 50 bps per side |
| Benchmark 1 | equal-weight eligible universe |
| Benchmark 2 | SPY buy-and-hold |

No parameter was selected using test-year returns. The 2026 window is partial
(8 months).

## 4. Per-window net CAGR at 10 bps

| Year | Momentum20 | Momentum60 | Trend | EW | SPY |
|---|---:|---:|---:|---:|---:|
| 2021 | 17.60% | 18.16% | 20.29% | 23.95% | 29.17% |
| 2022 | -12.83% | -4.32% | -3.07% | -4.73% | -20.15% |
| 2023 | 6.64% | -1.93% | 1.80% | 7.25% | 25.22% |
| 2024 | 33.70% | 32.60% | 34.58% | 19.06% | 24.09% |
| 2025 | 38.08% | 24.30% | 29.46% | 15.47% | 16.75% |
| 2026* | 24.15% | 7.52% | 13.77% | 6.24% | 15.50% |

Excess vs EW / SPY at 10 bps:

| Year | Mom20 vs EW | Mom20 vs SPY | Trend vs EW | Trend vs SPY |
|---|---:|---:|---:|---:|
| 2021 | -6.35% | -11.57% | -3.66% | -8.88% |
| 2022 | -8.10% | +7.32% | +1.66% | +17.08% |
| 2023 | -0.62% | -18.58% | -5.45% | -23.41% |
| 2024 | +14.64% | +9.61% | +15.52% | +10.48% |
| 2025 | +22.61% | +21.33% | +13.99% | +12.71% |
| 2026* | +17.92% | +8.65% | +7.54% | -1.73% |

**No candidate beats EW/SPY in 2021, 2022, or 2023.** The strong result is
concentrated in 2024鈥?025. This is not cross-window stability.

## 5. Cost sensitivity

Net CAGR at 5 / 10 / 20 / 50 bps per side:

| Year | Strategy | 5 | 10 | 20 | 50 |
|---|---|---:|---:|---:|---:|
| 2024 | Momentum20 | 34.86% | 33.70% | 31.41% | 24.75% |
| 2024 | Trend | 35.26% | 34.58% | 33.21% | 29.18% |
| 2025 | Momentum20 | 39.22% | 38.08% | 35.81% | 29.22% |
| 2025 | Trend | 30.11% | 29.46% | 28.15% | 24.29% |
| 2026* | Momentum20 | 25.20% | 24.15% | 22.07% | 16.03% |
| 2026* | Trend | 14.34% | 13.77% | 12.65% | 9.36% |

At 50 bps the 2024鈥?026 returns remain positive, but the earlier years still
underperform. The problem is not only cost; it is regime dependence.

## 6. Market environments

Classification uses only information known at the month-end:

- bull: SPY close 鈮?200-day MA; bear: below;
- high volatility: SPY 20-day vol 鈮?20%; low: below;
- trend: |200-day return| 鈮?10%; range: below.

10 bps net CAGR by environment:

| Strategy | Bull | Bear | High vol | Low vol | Trend | Range |
|---|---:|---:|---:|---:|---:|---:|
| Momentum20 | 15.5% | 18.6% | -7.1% | 20.7% | 23.2% | -0.4% |
| Momentum60 | 10.8% | 18.1% | -3.0% | 15.0% | 17.0% | 0.7% |
| Trend | 15.0% | 17.4% | -0.0% | 18.3% | 20.1% | 4.1% |

All three fail in high-volatility and range environments. The apparent
outperformance is concentrated in low-volatility trending markets.

## 7. Answers

1. **Momentum20 stable excess?** No. It underperforms in 2021鈥?023 and wins in
   2024鈥?026.
2. **Trend stable excess?** No. Same pattern; fails 2021鈥?023.
3. **Momentum60 more robust?** No. It is less extreme but still fails early and
   only modestly beats EW in 2022.
4. **Higher cost survivability?** At 50 bps the later-period result survives,
   but the early-period failure remains. No strategy is cost-proof across time.
5. **Different environments?** No. High-vol and range environments are weak.
6. **Overfitting?** No parameter search was run; the concentration in 2024鈥?025
   is regime dependence, not evidence of a tuned model.
7. **Survivorship bias sufficient to explain?** Cannot be ruled out. The
   universe is the current 503 names; delisted/historical constituents are
   missing. No claim of bias-free alpha.
8. **Candidates for next round?** Only Momentum20 and Trend, as exploratory
   candidates for rolling tests after historical universe is available.
9. **Stop investing?** Momentum60 for now; RSI, ATR, low-vol, mean reversion
   remain rejected.

## 8. Decision

**No strategy passes Phase 2.3.**

The results are not stable across test windows, not robust to high-vol/range
environments, and still use a survivorship-biased universe.

## 9. Artifacts

- `tools/research/walkforward_validation.py`
- `tests/test_walkforward_validation.py`
- `docs/research/walkforward_2021_2026_2026-10-30.json`
- corrected `docs/research/technical_strategies_phase22_2026-10-30.json`
- corrected subperiod JSONs
