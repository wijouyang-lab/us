# Phase 3.2 Dynamic Portfolio Risk Engine

Date: 2026-11-02
Base: `research/phase3-1-trend-system` (#424, Draft)
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`
Research only. No production changes.

## 1. Scope

Consumes Phase 3.1 WATCH/CONFIRMED/EXIT, score and weekly dates. Adds:

- inverse-volatility sizing;
- 10% single-asset cap;
- 20% correlation-cluster cap;
- 10% annualized portfolio volatility target;
- 0鈥?00% cash;
- drawdown defence;
- daily research ledger and costs;
- four-way comparison.

## 2. Sizing

```text
eligible = CONFIRMED + valid score + sufficient history
raw weight = 1 / Vol60
single cap = 10%
60D correlation cluster cap = 20%
expected portfolio vol = sqrt(w' Cov w)
scale = min(1, 10% / expected vol)
gross <= 100%; remainder = cash
```

No fixed number of holdings. No WATCH asset is bought.

Defence ladder:

| Drawdown | Gross cap |
|---|---:|
| 0鈥?% | 100% |
| 5鈥?% | 75% |
| 8鈥?0% | 50% |
| 10鈥?2% | 25% |
| 12鈥?5% | 0% |
| 鈮?5% | HARD_RISK_BREACH |

The cap is applied at the next weekly rebalance. It cannot guarantee a 15% maximum drawdown.

## 3. Execution and accounting

- Weekly signal at last actual close.
- Execution at next actual Open.
- No signal-close fill.
- Daily mark-to-close NAV.
- Costs on actual buy and sell amounts once.
- Cash return 0%.
- Separate research ledger; production `$50,000` ledger untouched.

## 4. Actual four-way comparison, 2018-01-01..2026-10-28, 10 bps

| Scheme | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar |
|---|---:|---:|---:|---:|---:|---:|
| A SPY buyhold | 12.66% | 17.08% | 0.724 | 0.892 | 鈭?4.10% | 0.371 |
| B SPY trend/cash | 12.63% | 16.95% | 0.724 | 0.892 | 鈭?4.04% | 0.371 |
| C equal-weight confirmed | 9.51% | 17.08% | 0.619 | 0.747 | 鈭?3.09% | 0.288 |
| D risk engine | **3.73%** | **10.81%** | **0.394** | **0.481** | **鈭?0.39%** | **0.183** |

D diagnostics:

```text
average stock exposure: 76.6%
average cash:           23.4%
average holdings:       34.6
max single weight:      10.0%
max cluster weight:     20.0%
total cost:             11.54% of initial capital
turnover:               58.5x initial capital
hard breaches:          1 (first 2020-03-12; max DD 2020-03-25)
```

**The 15% drawdown target was not met.** Actual max drawdown was 鈭?0.39%.

### Cost sensitivity for D

| Cost (bps/side) | CAGR | MaxDD |
|---:|---:|---:|
| 5 | 4.32% | 鈭?0.33% |
| 10 | 3.73% | 鈭?0.39% |
| 20 | 2.56% | 鈭?0.53% |
| 50 | **鈭?.85%** | **鈭?4.57%** |

At 50 bps the risk portfolio has a negative CAGR.

## 5. Annual returns

| Year | B SPY trend | C equal | D risk |
|---|---:|---:|---:|
| 2018 | 鈭?.0% | 鈭?.6% | 鈭?.4% |
| 2019 | +28.6% | +23.7% | +16.2% |
| 2020 | +15.1% | +13.5% | 鈭?.6% |
| 2021 | +28.7% | +26.4% | +15.8% |
| 2022 | 鈭?9.9% | 鈭?7.3% | 鈭?.9% |
| 2023 | +24.8% | +12.9% | +5.1% |
| 2024 | +23.9% | +22.1% | +18.2% |
| 2025 | +16.6% | +10.1% | +0.4% |
| 2026* | +12.5% | +8.8% | 鈭?.3% |

*through 2026-10-28.

## 6. Interpretation

- B adds almost nothing over A: SPY trend filter is invested ~99.8% of days.
- C underperforms SPY buyhold with similar drawdown.
- D cuts volatility and drawdown, but gives up most return; it is not more attractive on Sharpe/Calmar.
- The risk model does not achieve the 15% target.
- No evidence of a superior executable strategy.

## 7. Limitations

- current 503-stock panel, survivorship bias;
- 4 ETFs only; no ETF PIT membership;
- no delisting/fund-closure returns;
- no dividends: price returns only, not total return;
- no borrow/financing (long-only);
- cash return 0%;
- 2026 partial;
- no transaction-cost model beyond bps;
- no live execution, slippage or capacity;
- no PIT.

## 8. Tests

`tests/test_trend_v1_portfolio.py`: **7 passed**

- defense ladder/HARD state;
- no candidates 鈫?cash;
- weights 鈮?00% and single cap;
- correlated group cap;
- cash/cost accounting;
- no negative cash;
- risk uses only prices up to signal date.

Full CI after commit.

## 9. Commands

```bash
python3.12 -m tools.research.trend_v1.backtest_run \
  --stocks price10y_1028.csv \
  --etf-dir proxy_data \
  --spy proxy_data/SPY.csv \
  --output docs/research/trend_v1_portfolio_2026-11-02.json \
  --daily-out docs/research/trend_v1_daily_2026-11-02.csv
```

## 10. Conclusion

The core risk engine is implemented and produces a real daily ledger. It reduces
drawdown from roughly 鈭?4% to 鈭?0%, but at 3.73% CAGR it is less attractive than
SPY buyhold and equal-weight confirmed. The 15% target is **not met**, and this
is not deployable alpha.
No live trading or production ledger changes.
