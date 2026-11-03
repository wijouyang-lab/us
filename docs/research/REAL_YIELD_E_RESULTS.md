# E: 10-Year Real-Yield Shock Filter

Date: 2026-11-03
Branch: `research/real-yield-shock-filter`
Status: **FAILED / NO-GO**

Research only. No Dashboard, broker integration, or orders.

## 1. Pre-registered rule

Frozen before the run in `docs/research/REAL_YIELD_E_PREREG.md`.

```text
real_yield_change_63 = latest_visible_DFII10 - DFII10 63 SPY sessions earlier
trigger = real_yield_change_63 >= 0.50 percentage points
```

| State | Allocation |
|---|---|
| Trigger | BIL 100% |
| No trigger | SPY 70%, IEF 15%, TLT 15% |
| Missing/invalid signal | BIL 100% |

Monthly at the last SPY session. Data must be visible at least one full trading
day before the decision; next SPY session raw Open. $50,000, long-only, no
leverage. 5 bps/leg base; 1/3/5/10/20 bps sensitivity. No threshold/window search.

## 2. PIT audit

| Item | Result |
|---|---|
| Primary series | FRED/ALFRED `DFII10`, daily 10Y TIPS constant maturity |
| ALFRED vintage coverage | from 2003; all 233 decision dates have a vintage |
| Decision vintage | prior SPY session (one full trading-day lag) |
| Current and 63-session base | **both read from the same decision vintage** |
| Missing vintages | 0 / 233 |
| Triggers | 22 |
| Cross-check | `DGS10` downloaded as a nominal-rate diagnostic, not substituted for PIT |
| `T10YIE` | not used as the long PIT series |

No revised full-history value was backfilled into a decision date. A missing or
invalid signal holds BIL. ALFRED publication dates are availability dates, not
verified publication minutes; the strategy uses an extra full session lag.

Raw responses are retained gzip-compressed with SHA-256 in
`data/research/real_yield_shock/pit_DFII10_raw.jsonl.gz` and
`data/research/real_yield_shock/manifest.json`.

## 3. Results at 5 bps/leg

| Metric | E |
|---|---:|
| Final NAV | $255,340.14 |
| CAGR | 8.76% |
| Volatility | 11.17% |
| Sharpe | 0.81 |
| Max drawdown | **-32.18%** |
| Peak / trough / recovery | 2007-10-09 / 2009-03-09 / 2010-10-25 |
| Longest underwater | 766 sessions |
| Order legs | 642 |
| Total cost | $3,871.97 |
| Exposure | 90.3% |
| Triggers / missing | 22 / 0 |
| Alpha vs BIL | +9.03%, p<0.001 |
| Alpha vs SPY | -1.13%, p=0.587 |
| CAGR bootstrap 95% CI | +4.43% .. +13.58% |

### Stage-local drawdown

| Stage | CAGR / DD |
|---|---:|
| 2007-2015 | 6.69% / -32.18% |
| 2016-2020 | 12.86% / -21.65% |
| 2021-2026 | 8.76% / -15.00% |

### Slippage sensitivity

| 1 bps | 3 bps | 5 bps | 10 bps | 20 bps |
|---|---:|---:|---:|---:|---:|
| 8.89% / -32.04% | 8.82% / -32.12% | 8.76% / -32.18% | 8.60% / -32.36% | 8.28% / -32.64% |

Costs do not explain the failure; the signal is too late and the 70% equity
allocation takes the full 2008 drawdown before the first trigger.

## 4. Comparison

| Strategy | CAGR | Max DD |
|---|---:|---:|
| E real-yield shock | 8.76% | **-32.18%** |
| D curve/NFCI exploratory | 8.42% | -24.27% |
| BIL | 1.40% | -0.78% |
| SPY | 10.56% | -55.19% |

E improves CAGR over D but is materially worse on drawdown. It does not meet the
15% limit and is not a candidate.

## 5. Decision

| Gate | Result |
|---|---|
| Positive excess after costs | Yes |
| Statistical support vs BIL | Yes |
| Max DD <= 15% | **No (-32.18%)** |
| Not one stage | No: 2008 dominates |
| Enough exposure/trades | Yes |
| PIT reliable | Yes for DFII10 under the stated one-session lag |
| Reproducible NAV/orders | Yes |

**E = FAILED / NO-GO.** No parameter was changed to rescue it.

## 6. Artifacts

```text
docs/research/REAL_YIELD_E_PREREG.md
docs/research/REAL_YIELD_E_RESULTS.md
docs/research/real_yield_shock/results.json
docs/research/real_yield_shock/nav_E.csv
docs/research/real_yield_shock/trades_E.csv
docs/research/real_yield_shock/triggers_E.csv
data/research/real_yield_shock/DFII10.csv
data/research/real_yield_shock/pit_DFII10.csv
data/research/real_yield_shock/pit_DFII10_raw.jsonl.gz
data/research/real_yield_shock/manifest.json
data/research/real_yield_shock/{SPY,IEF,TLT,BIL}.csv
tools/research/real_yield_shock.py
tests/test_real_yield_shock.py
```
