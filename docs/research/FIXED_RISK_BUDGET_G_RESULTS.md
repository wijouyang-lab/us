# G: Passive 20% QQQ / 80% BIL Risk Budget

Date: 2026-11-03
Branch: `research/fixed-risk-budget-qqq-bil`
Status: **PASSIVE_RISK_BUDGET_BASELINE**

Research only, not alpha, not a timing strategy, not deployable.

G answers: *how much equity risk can be carried under a 15% historical drawdown
constraint?* It does **not** test a forecast signal.

Important caveat: the 20% weight was chosen after preliminary drawdown
inspection. The fact that MaxDD <= 15% is therefore **not independent
validation**.

## 1. Rule and accounting

```text
QQQ 20% / BIL 80%
```

- $50,000; long-only; no leverage; no signal;
- monthly restore at last common session, next session raw Open;
- initial build raw Open;
- integer shares, residual cash;
- dividends paid on ex-date to shares held before ex-date, not reinvested;
- calibrated IBKR Pro Tiered historical-backtest approximation + 5 bps/leg.

No weight search was performed.

### Dividend / rebalance base

Dividends are credited to cash at line 136 (`a.credit_dividends(dt)`), then the
next monthly rebalance computes `nav_open = a.nav(dt, True)` at line 138. Because
`Account.nav()` includes cash, **accumulated cash dividends are included in the
monthly 20/80 weight base**. They are not reinvested daily, but they are
redeployed at the next monthly rebalance.

Measured effect over 2007-2026:

| Item | Value |
|---|---:|
| Average uninvested cash / NAV | **0.187%** |
| Average risky exposure | **19.967%** |
| Deviation from 20% target | **-0.033 pp** |

Known limitation: integer-share residual cash creates a tiny drag; no rule change
was made.

## 2. Sharpe definitions

- `sharpe_rf0`: annualized mean daily return / annualized daily volatility, rf=0.
- `sharpe_excess_bil`: annualized mean daily **excess over BIL total return**
  (cash dividends) / annualized volatility of that excess series, same calendar.

Both are reported for G, G0, G-SPY, QQQ, SPY and BIL.

## 3. Pre-registered passive controls

| ID | Rule |
|---|---|
| G | 20% QQQ / 80% BIL, monthly restore |
| G0 | 20% QQQ / 80% BIL, initial buy-and-hold, no rebalance |
| G-SPY | 20% SPY / 80% BIL, monthly restore, same costs |

G0/G-SPY were added to the pre-registration file before this run; no control was
added or replaced after seeing results.

## 4. Results at 5 bps/leg

| Variant | Final NAV | CAGR | Vol | Sharpe rf0 | Sharpe excess BIL | MaxDD | Order legs | Cost |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| G | $115,754.75 | 4.42% | 4.32% | 1.02 | 0.73 | **-11.38%** | 424 | $300.56 |
| G0 | $205,030.16 | 7.54% | 9.84% | 0.79 | 0.66 | **-22.60%** | 2 | $27.44 |
| G-SPY | $95,278.83 | 3.38% | 3.74% | 0.91 | 0.57 | -12.30% | 391 | $251.23 |

Benchmarks (cash dividends, no extra transaction costs):

| Benchmark | CAGR | Vol | Sharpe rf0 | Sharpe excess BIL | MaxDD |
|---|---:|---:|---:|---:|---:|
| BIL | 1.24% | 0.46% | 2.67 | 0.00 | -0.75% |
| QQQ | 15.13% | 21.60% | 0.76 | — | -53.22% |
| SPY | 10.56% | 19.66% | 0.61 | — | -55.19% |

G-SPY ends 2026-10-29 because the SPY snapshot lacks 2026-10-30; one session
shorter, disclosed.

### Drawdown dates

| Variant | Peak | Trough | Recovery |
|---|---|---|---|
| G | 2007-10-31 | 2009-03-09 | 2009-12-28 |
| G0 | 2007-10-31 | 2009-03-09 | 2010-12-10 |
| G-SPY | 2007-10-31 | 2009-03-09 | 2010-06-24 |

## 5. Direct answers

**1. Did monthly rebalancing's ~$300 cost add value?**

- G0 costs only **$27.44**, G costs **$300.56**; difference **$273**.
- G0 CAGR is **7.54%**, G is **4.42%**; rebalancing reduced CAGR by **3.12 pp**.
- But G0's risk drifted: average QQQ exposure **41.5%**, MaxDD **-22.60%** (fails 15%).
- G holds **19.97%** average risk and MaxDD **-11.38%** (passes).
- Conclusion: monthly rebalancing **did not add return**; it bought risk control.
  The $273 cost is trivial relative to that de-risking, but the strategy is a
  risk-budget implementation, not a return-enhancing strategy.

**2. How much of G's return depends on choosing QQQ vs SPY?**

- G CAGR 4.42% vs G-SPY 3.38%: **+1.04 pp**, about **24% of G's CAGR**.
- G Sharpe excess BIL 0.73 vs G-SPY 0.57.
- G MaxDD -11.38% vs G-SPY -12.30%.
- Conclusion: QQQ selection added return, but it is an **ex-post asset choice**,
  not a forecast. G-SPY remains a valid passive control with lower return.

**3. Does G pass?**

Yes, historical MaxDD -11.38% <= 15%, but because 20% was chosen after seeing
drawdown, this is not independent confirmation. Label remains
**PASSIVE_RISK_BUDGET_BASELINE**.

## 6. Stage results

| Variant | 2007-2015 | 2016-2020 | 2021-2026 |
|---|---|---|---|
| G | 2.89% / -11.38% | 5.59% / -6.00% | 5.79% / -7.27% |
| G0 | 3.40% / -10.16% | 11.40% / -14.93% | 10.83% / -22.60% |
| G-SPY | 1.67% / -12.30% | 3.93% / -7.03% | 5.18% / -4.74% |

## 7. Slippage sensitivity (G)

| 1 bps | 3 bps | 5 bps | 10 bps | 20 bps |
|---|---:|---:|---:|---:|---:|
| 4.43% / -11.36% | 4.43% / -11.37% | 4.42% / -11.38% | 4.41% / -11.41% | 4.38% / -11.43% |

## 8. Cost model

`tools/research/ibkr_costs.py`, `historical_backtest` layer:

- commission $0.0035/share, min $0.35, max 1%;
- SEC 0.0000206 sell;
- TAF $0.000166/share sell, holiday 2026-10-01..12-31;
- CAT $0.000003/share;
- clearing $0.00020/share, 0.5% notional cap assumption;
- exchange $0.00010/share base (0..0.00030 range);
- 5 bps/leg base slippage.

Historical fees are a **current-rate approximation**, not exact 2007-2026 IBKR
venue fees. No exact historical SmartRouting venue data exists.

## 9. Tests

`tests/test_fixed_risk_budget.py`: **6 passed**, covering initial equity, integer
shares, first cost, raw Open, dividends, cutoff injection, cost components, TAF
holiday, NAV reconciliation.

## 10. Artifacts

```text
docs/research/FIXED_RISK_BUDGET_G_PREREG.md
docs/research/FIXED_RISK_BUDGET_G_RESULTS.md
docs/research/fixed_risk_budget/results.json
docs/research/fixed_risk_budget/nav_G.csv
docs/research/fixed_risk_budget/nav_G0.csv
docs/research/fixed_risk_budget/nav_G-SPY.csv
docs/research/fixed_risk_budget/trades_G.csv
docs/research/fixed_risk_budget/trades_G0.csv
docs/research/fixed_risk_budget/trades_G-SPY.csv
data/research/fixed_risk_budget/{QQQ,SPY,BIL}.csv
data/research/fixed_risk_budget/manifest.json
tools/research/ibkr_costs.py
tools/research/fixed_risk_budget.py
tests/test_fixed_risk_budget.py
```
