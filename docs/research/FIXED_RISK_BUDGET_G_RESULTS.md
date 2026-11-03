# G: Fixed 20% QQQ / 80% BIL Risk Budget

Date: 2026-11-03
Branch: `research/fixed-risk-budget-qqq-bil`
Status: **RISK_BUDGET_BASELINE / RESEARCH_CANDIDATE**

Research only. This is **not** a timing strategy and not evidence of alpha.
It is an exploratory / implementation-validation baseline because a prior
historical screen was already seen.

## 1. Rule

```text
QQQ 20% / BIL 80%
```

- $50,000 initial equity;
- long-only, no leverage, no forecast signal;
- monthly restore at last common session, next session raw Open;
- integer shares, residual cash retained;
- initial build at raw Open;
- dividends credited on ex-date to prior holdings, not reinvested;
- all subsequent trades pay calibrated IBKR costs.

No weight grid search or post-hoc optimization was performed.

## 2. Calibrated IBKR cost model

Applied via `tools/research/ibkr_costs.py`:

| Component | Assumption |
|---|---|
| Commission | $0.0035/share, min $0.35, max 1% |
| SEC | 0.0000206 × sell notional |
| TAF | $0.000166/share sell, $8.30 cap; 2026-10-01..12-31 holiday = 0 |
| CAT | $0.000003/share |
| NSCC/DTC clearing | $0.00020/share, 0.5% notional cap assumption |
| Exchange/pass-through | $0.00010/share base; range 0..$0.00030 |
| Slippage | 1/3/5/10/20 bps per leg |

The exchange/pass-through amount is an assumption because historical IBKR
SmartRouting venue fills cannot be reconstructed. It is not presented as an
actual historical venue fee.

## 3. Results at 5 bps/leg

| Metric | G |
|---|---:|
| Final NAV | $115,754.75 |
| CAGR | 4.42% |
| Volatility | 4.32% |
| Sharpe | 1.02 |
| **Max DD** | **-11.38%** |
| Peak / trough / recovery | 2007-10-31 / 2009-03-09 / 2009-12-28 |
| Longest underwater | 542 sessions |
| Order legs | 424 |
| Total cost | $300.56 |
| Commission | $149.98 |
| SEC / TAF / CAT | $2.31 / $0.17 / $0.01 |
| Clearing / exchange | $0.62 / $0.31 |
| Slippage | $147.16 |
| Dividend cash | $20,729.34 |
| Exposure | 20.0% |
| Alpha vs BIL | +3.19%, p=0.0003 |
| Alpha vs QQQ | -11.95%, p=0.0005 |
| Bootstrap CAGR 95% CI | +2.82% .. +6.16% |

### Benchmarks (cash dividends, no extra transaction costs)

| Benchmark | CAGR | Vol | MaxDD |
|---|---:|---:|---:|
| BIL | 1.24% | 0.46% | -0.75% |
| QQQ | 15.13% | 21.60% | -53.22% |

## 4. Stage-local

| Stage | CAGR / MaxDD |
|---|---:|
| 2007-2015 | 2.89% / -11.38% |
| 2016-2020 | 5.59% / -6.00% |
| 2021-2026 | 5.79% / -7.27% |

## 5. Slippage sensitivity

| 1 bps | 3 bps | 5 bps | 10 bps | 20 bps |
|---|---:|---:|---:|---:|---:|
| 4.43% / -11.36% | 4.43% / -11.37% | 4.42% / -11.38% | 4.41% / -11.41% | 4.38% / -11.43% |

## 6. Decision

| Gate | Result |
|---|---|
| Positive excess after costs | Yes |
| Statistical support vs BIL | Yes |
| Max DD <= 15% | **Yes (-11.38%)** |
| Not one stage | Yes, all stages positive |
| Enough trades/exposure | Yes for a 20% budget; 424 legs |
| PIT / data | Daily QQQ/BIL, no macro PIT dependency |
| Accounting reproducible | Yes |

G passes the risk gate and is labeled **RISK_BUDGET_BASELINE / RESEARCH_CANDIDATE**.

It is not a GO alpha claim: the 20% equity budget explains the return and risk,
and the historical result is exploratory/implementation validation. A true
confirmatory test needs frozen rules plus forward paper data.

## 7. Tests

`tests/test_fixed_risk_budget.py` covers initial equity, integer shares, initial
cost, raw Open, dividend entitlement, cutoff injection, cost components, and the
2026 TAF holiday.

## 8. Artifacts

```text
docs/research/FIXED_RISK_BUDGET_G_PREREG.md
docs/research/FIXED_RISK_BUDGET_G_RESULTS.md
docs/research/fixed_risk_budget/results.json
docs/research/fixed_risk_budget/nav_G.csv
docs/research/fixed_risk_budget/trades_G.csv
data/research/fixed_risk_budget/QQQ.csv
data/research/fixed_risk_budget/BIL.csv
data/research/fixed_risk_budget/raw/{QQQ,BIL}.csv
data/research/fixed_risk_budget/manifest.json
tools/research/ibkr_costs.py
tools/research/fixed_risk_budget.py
tests/test_fixed_risk_budget.py
```
