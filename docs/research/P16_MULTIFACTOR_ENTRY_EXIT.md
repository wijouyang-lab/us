# P16 Multifactor Entry/Exit Research

Date: 2026-11-20
Branch: `research/p16-multifactor-entry-exit`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **NO_GO / PARTIAL**

## 1. What was actually run

Local FINSABER adjusted-close data, PIT S&P membership, 2020-01-02..2024-12-31
(1,259 portfolio days). Entry score:

```text
Trend = 0.5 * cross-sectional rank(MOM63) + 0.5 * rank(MOM126)
```

Regime: SPY close > 200D SMA = RISK_ON; below = RISK_OFF.
Exit variants: time (21 sessions), trend (close < SMA50), risk
(20D vol > 2× its 252D median), both.

No MAX21/MOM12-1/ATR/volume-shock factor was retested. Fundamental PIT
quality/growth/exit: **DATA_BLOCKED** (ticker→CIK historical identity not
verified).

## 2. Entry factor result

| metric | value |
|---|---:|
| signal dates | 1,234 |
| mean Rank IC | **−0.0028** |
| Q5−Q1 21D | −0.164% |
| naive t | −1.005 |

Trend has no positive cross-sectional predictive power in this sample.
Entry quality and growth/value were not run because PIT identity is blocked.

## 3. Portfolio results (offline, $50k, long-only)

Selected variants:

| variant | CAGR | vol | max DD |
|---|---:|---:|---:|
| Time exit, no regime, 5 bps | 7.61% | 30.4% | −40.6% |
| Time exit, no regime, 10 bps | 6.36% | 30.4% | −41.7% |
| Trend exit, no regime, 10 bps | 3.88% | 27.3% | −37.6% |
| Trend exit, regime, 10 bps | 8.71% | 23.3% | −29.9% |
| Risk exit, regime, 10 bps | 8.53% | 23.9% | −28.3% |
| Trend+risk, regime, 10 bps | **9.01%** | 23.1% | **−29.8%** |
| Trend+risk, regime, 20 bps | 4.51% | 23.0% | −39.5% |
| SPY buy & hold | **14.28%** | 21.0% | −33.7% |

- Regime reduces average exposure from ~10 to ~8.3 positions and lowers
  drawdown, but does not meet 15%.
- Trend/risk exits improve drawdown versus time-only but sacrifice return and
  add costs; at 20 bps the best variants collapse.
- No variant beats SPY CAGR; all exceed 15% max drawdown.
- Average positions ~8–10, so many days hold cash; no benchmark equal-weight
  portfolio with identical costs was built (PARTIAL).

## 4. Exit comparison

| exit | 10 bps CAGR | max DD | incremental vs time |
|---|---:|---:|---|
| Time | 6.36% | −41.7% | baseline |
| Trend | 3.88% | −37.6% | lower DD, lower return |
| Risk | 3.76% | −31.3% | lower DD, lower return |
| Both | 1.69% | −38.8% | worst return |

Exits reduce tail risk but do not beat time-only after costs. The "independent
exit improves risk-adjusted return" hypothesis is not confirmed.

## 5. Decision

```text
P16_ENTRY_TREND = NO_GO
P16_ENTRY_QUALITY = DATA_BLOCKED
P16_ENTRY_GROWTH_VALUE = DATA_BLOCKED
P16_EXIT_TREND = NO_GO
P16_EXIT_RISK = NO_GO
P16_REGIME = INCONCLUSIVE (lower DD, higher return, but no 15% DD)
P16_FULL_SYSTEM = NO_GO
P16_COST_SENSITIVITY = FAIL
P16_DATA_QUALITY = PARTIAL
P16_PIT_MEMBERSHIP = PARTIAL
P16_PRICE_ADJUSTMENT = UNVERIFIED
P16_PRODUCTION_READY = FALSE
```

No 15% drawdown, no SPY/equal-weight outperformance, negative entry IC,
10 bps costs erode the exit benefit. No production, paper, or orders.

## 6. Files

- `tools/research/p16_multifactor_entry_exit.py`
- `tests/test_p16_multifactor_entry_exit.py`
- `data/research/p16/p16_summary.json`
- `p16_entry_ic.csv`
- `p16_nav_*.csv` (24 variants)
- `p16_benchmark.json`
- `p16_manifest.json`

Fundamental module, trade ledger, holdings history, industry concentration and
attribution are not claimed; quality is blocked and the portfolio engine does
not yet emit per-trade ledger. Those are real gaps, not passes.
