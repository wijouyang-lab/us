# PR #642 — Timing Correction and SPY Trend Re-Validation

Date: 2026-11-27. Research only. **No PAPER-50000, no IBKR, no orders.**

## What was wrong

The old SPY trend code computed:

```python
pos = (SPY > SPY.rolling(10).mean().shift(1)).astype(float)
gross = pos * r
```

The position at month `t` was applied to month `t` return. That is look-ahead:
the month-end signal cannot earn that same month's return.

The corrected implementation:

```python
signal_t = SPY_t > mean(SPY_{t-9..t})
position_t = signal_{t-1}       # executed next month
gross_t = position_t * r_t
```

Code: `tools/research/strategy_competition/timing.py`.

## Before vs after

| Metric | Old (look-ahead) | Corrected |
|---|---:|---:|
| Full CAGR 2008–2024 | 18.31% | **8.23%** |
| Full MaxDD | -8.33% | **-23.43%** |
| Full Sharpe (old formula) | 1.82 | — |
| Full Sharpe (standard) | — | **0.78** |
| OOS 2020–2024 CAGR | 22.16% | **9.40%** |
| OOS MaxDD | -8.33% | **-23.43%** |
| 20 bps full CAGR | 18.14% | **8.05%** |
| Switches | 27 | **29** |
| Annual turnover | 1.5x | **1.61x** |

The old result was almost entirely a timing artifact. The correction reduces CAGR
by more than half and triples the drawdown.

## Sharpe correction

Old `Sharpe` was `CAGR / annualized volatility`.  
Now:

```text
Sharpe = annualized mean monthly excess return / annualized volatility
       = (mean(r) * 12) / (std(r) * sqrt(12))
```

Risk-free rate is assumed 0% because no reliable monthly cash series was used;
this is a simplification and is disclosed. CAGR, volatility, MaxDD, Sortino and
Calmar remain separate.

Corrected SPY_TREND Sharpe: **0.78** full, **0.75** OOS.

## Cost sensitivity

| Cost | Full CAGR | OOS CAGR | Full MaxDD |
|---|---:|---:|---:|
| 5 bps | 8.32% | 9.51% | -23.20% |
| 10 bps | 8.23% | 9.40% | -23.43% |
| 20 bps | 8.05% | 9.17% | -23.91% |

**20 bps remains positive, but below SPY's 10.59% full CAGR.**  
The strategy no longer has a return advantage.

## Parameter stability

| Window | Full CAGR | Full MaxDD | OOS CAGR | OOS MaxDD |
|---|---:|---:|---:|---:|
| 8m exploratory | 10.32% | -23.43% | 9.40% | -23.43% |
| 10m pre-specified | 8.23% | -23.43% | 9.40% | -23.43% |
| 12m exploratory | 8.74% | -16.89% | 12.76% | -15.43% |

- The 10-month window was pre-specified before this correction.
- 8/12 are exploratory, not independent OOS.
- No window meets the 15% full-period drawdown target. The 12-month is closest at -16.89%.
- Results are not stable enough to claim parameter robustness.

## Versus benchmarks (10 bps, full)

| Strategy | CAGR | Vol | Sharpe | MaxDD |
|---|---:|---:|---:|---:|
| SPY_TREND corrected | 8.23% | 10.94% | 0.78 | -23.43% |
| SPY | 10.59% | 15.88% | 0.72 | -46.32% |
| QQQ | 15.47% | 18.91% | 0.86 | -44.80% |
| A_MOM_QUAL | 26.60% | 24.48% | 1.09 | -52.19% |
| B_IND_ROT | 15.19% | 19.92% | 0.81 | -45.05% |

SPY_TREND has lower drawdown than SPY, but lower return and similar Sharpe. It does
not meet the 15% target and does not beat SPY on return.

## Final gate

- **SPY_TREND does not meet 15% MaxDD.**
- **No complex route passes either** (A/B full MaxDD 45–55%).
- **No PAPER-50000 authorization.**
- **No verified stock-selection strategy.**
- The only valid conclusion: the old SPY fallback was a look-ahead artifact.

## Remaining data biases

- Static 987-symbol universe; delisted names not verified -> survivorship bias.
- No PIT fundamentals; Route C not evaluable.
- Zero risk-free assumption in Sharpe.
- No taxes, slippage, or market impact.
- Monthly close execution, not intraday.

## Decision

**No strategy enters forward paper validation.** The corrected SPY trend is
risk-reducing but not return-enhancing, and it fails the 15% drawdown target.
