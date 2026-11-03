# Low-Frequency ETF Strategy Research

Date: 2026-11-03  
Branch: `research/low-frequency-etf-strategies`  
Status: **NO-GO for all three candidates**

This is research only. No broker connection, no orders, no deployment.

## 1. Scope and pre-registered candidates

Universe: SPY, QQQ, IWM, EFA, EEM, TLT, IEF, GLD, DBC; BIL is cash.

Account: $50,000, long-only, no leverage, daily NAV. Study window
2007-05-30 to 2026-10-30. Each ETF uses its own available history; BIL starts
2007-05-30, so the common portfolio window starts there.

| ID | Rule fixed before running |
|---|---|
| A | 12-month total return; top 3 positive-momentum ETFs relative to BIL; monthly rebalance at next session open; BIL if none |
| B | 200-day SMA regime; inverse 60-day vol weights among qualifying ETFs; 10% annualized vol target; monthly rebalance at next open; BIL if none |
| C | Frozen QQQ TRANSITION: 252-day 5% lower tail of 5-session return, SPY TRANSITION, next-open entry, 5 further SPY sessions, 25% sleeve, remainder BIL |

No parameter search was performed. C was not re-tuned. A/B rules were fixed
before the run.

## 2. Data and sample split

All ten ETFs were listed before the 2007 start; BIL starts 2007-05-30, so the
common account window starts there. No pre-listing rows were synthesized or
forward-filled. Source is yfinance, provider-adjusted OHLCV, cutoff 2026-10-30.
Hashes are in `data/research/etf_strategy_study/manifest.json`.

The ETF list is today's surviving set, so survivorship/selection bias is
disclosed. No parameter was fitted on a training period; therefore the periods
are evaluation windows, not a fitted train/validation/test exercise:

```text
2007-2015  design/stress evaluation
2016-2020  independent time slice
2021-2026  recent slice; not a pristine holdout for QQQ reversal
```

## 3. Costs

Assumed **IBKR Pro Tiered**:

- commission = max($0.35, min($0.0035/share, 1% of trade value));
- SEC fee on sells = 0.0000278 × notional;
- FINRA TAF on sells = min($0.000166/share, $8.30);
- exchange/clearing = $0.000003/share;
- base slippage = **5 bps per leg**, with 1/3/10/20 bps sensitivity.

Slippage is **simulated**, because historical quoted spreads were not available.
It is not presented as realized historical execution cost.

## 4. Headline results at 5 bps/leg

| Strategy | Final NAV | CAGR | Vol | Sharpe | Sortino | Calmar | Max DD | Recovery | Trades | Exposure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A Dual Momentum | $131,257.51 | 5.10% | 13.52% | 0.44 | 0.55 | 0.20 | **-25.81%** | 684 sessions | 1,323 | 89.7% |
| B Trend/Vol | $130,855.98 | 5.08% | 8.63% | 0.62 | 0.80 | 0.31 | **-16.52%** | 636 sessions | 2,863 | 85.4% |
| C QQQ Transition | $73,066.71 | 1.98% | 1.98% | 1.00 | 0.73 | 0.36 | **-5.46%** | 1,322 sessions | 108 | 0.69% |
| BIL | $65,536.54 | 1.40% | 0.49% | 2.87 | — | — | -0.78% | — | — | 100% |
| SPY | $351,505.57 | 10.56% | 19.66% | 0.61 | — | — | -55.19% | — | — | 100% |

A and B both fail the 15% drawdown limit at the base cost. C passes drawdown but
produces only a small excess return over BIL.

## 5. Costs and cost sensitivity

### Total realized simulation cost at 5 bps/leg

| Strategy | Commission | SEC | TAF | Exchange | Slippage | Total |
|---|---:|---:|---:|---:|---:|---:|
| A | $1,524.57 | $457.81 | $32.74 | $1.83 | $16,483.53 | **$18,502.77** |
| B | $2,019.28 | $500.31 | $42.86 | $3.99 | $18,011.06 | **$20,575.41** |
| C | $67.02 | $21.41 | $1.61 | $0.14 | $769.86 | **$859.82** |

Monthly full rebalancing makes A/B costly; C's 25% sleeve has low turnover.

### CAGR across slippage assumptions

| Strategy | 1 bps | 3 bps | 5 bps | 10 bps | 20 bps |
|---|---:|---:|---:|---:|---:|
| A | 6.12% | 5.61% | 5.10% | 3.85% | 1.40% |
| B | 6.10% | 5.59% | 5.08% | 3.83% | 1.37% |
| C | 2.03% | 2.00% | 1.98% | 1.90% | 1.76% |

A/B remain above BIL at 5 bps but fail risk. At 20 bps their CAGR is only ~1.4%,
equal to BIL. C is not cost-fragile but has insufficient alpha.

## 6. Statistical tests

Newey-West HAC, lag 20, full daily time axis. Alpha is annualized mean daily
excess return; p-values BH-adjusted across A/B/C.

| Strategy | vs | Alpha | HAC t | raw p | BH q | 95% CI |
|---|---|---:|---:|---:|---:|---:|
| A | BIL | +4.50% | 1.64 | 0.101 | 0.101 | -0.88%..+9.88% |
| B | BIL | +3.94% | 2.34 | 0.019 | 0.057 | +0.65%..+7.23% |
| C | BIL | +0.58% | 1.86 | 0.063 | 0.095 | -0.03%..+1.20% |
| A | SPY | -6.10% | -1.85 | 0.065 | — | -12.57%..+0.38% |
| B | SPY | -6.65% | -2.10 | 0.036 | — | -12.88%..-0.43% |
| C | SPY | -10.01% | -2.69 | 0.007 | — | -17.31%..-2.71% |

No strategy has BH q < 0.05 versus BIL. B is closest (q=0.057) but fails the
drawdown criterion. C's alpha confidence interval includes zero.

Daily block bootstrap (20-session circular blocks, 500 samples) CAGR CI:

| Strategy | 2.5% | 97.5% |
|---|---:|---:|
| A | -0.46% | 10.38% |
| B | +1.84% | +8.56% |
| C | +1.32% | +2.67% |

## 7. Stage stability

| Strategy | 2007-2015 CAGR / DD | 2016-2020 CAGR / DD | 2021-2026 CAGR / DD |
|---|---:|---:|---:|
| A | 3.12% / -25.8% | 4.65% / -19.9% | 8.83% / -20.1% |
| B | 3.37% / -11.4% | 6.55% / -12.7% | 6.58% / -16.5% |
| C | 0.95% / -3.6% | 1.08% / -5.5% | 4.31% / -1.6% |

A has a 25.8% drawdown in the first period. B breaches 15% in 2021-2026. C is
the most stable by drawdown, but its recent 4.31% CAGR is not enough to prove a
statistically reliable excess over BIL, and 2021+ is not a pristine holdout
because QQQ reversal had been explored before.

## 8. Decision against the seven gates

| Gate | A | B | C |
|---|---|---|---|
| Positive excess after IBKR costs + 5 bps slip | Yes | Yes | Yes, small |
| Statistical support vs BIL | No (q=.101) | No (q=.057) | No (q=.095) |
| Max DD <= 15% | **No (-25.8%)** | **No (-16.5%)** | Yes (-5.5%) |
| Not one period | No | No (2021+ DD) | Mostly stable, but return low |
| Not a few trades | No (monthly concentration) | No (few assets) | No (108 trades, low exposure) |
| Reproducible NAV/orders | Yes | Yes | Yes |
| Failures documented | Yes | Yes | Yes |

Final: **FAILED** for A/B, **FAILED** for C (statistical and return gates).
There is no GO candidate and therefore no Paper validation plan yet.

## 9. What this does and does not prove

- A/B produce attractive long-run CAGR versus BIL, but with unacceptable
  drawdowns and cost/turnover burdens.
- B's HAC alpha is close to significance before BH (p=.019) but not after
  (q=.057), and it still fails the 15% DD gate.
- C is a low-risk, low-return sleeve; it does not yet demonstrate a reliable
  excess over cash, and its recent period is not untouched data.
- No result here is a deployable alpha. No parameter change was made to rescue
  any candidate.

## 10. Next pre-registered hypotheses (not tested)

1. **D. Curve/credit regime allocation**: use 10Y-3M or 10Y-2Y slope and
   high-yield spread to switch SPY/IEF/TLT/BIL; monthly; pre-register thresholds
   from economic definitions, not optimization.
2. **E. Commodity carry/roll**: DBC/GLD/TLT relative carry with a BIL fallback;
   requires a verified roll-yield/carry data source and is not testable from
   price-only data.

These are proposals only. They are not results and must be frozen before testing.

## 11. Artifacts

```text
data/research/etf_strategy_study/{SPY,QQQ,IWM,EFA,EEM,TLT,IEF,GLD,DBC,BIL}.csv
data/research/etf_strategy_study/manifest.json
docs/research/etf_strategy_study/results.json
docs/research/etf_strategy_study/trades_base5.csv
docs/research/etf_strategy_study/nav_A.csv
docs/research/etf_strategy_study/nav_B.csv
docs/research/etf_strategy_study/nav_C.csv
tools/research/low_frequency_etf.py
tests/test_low_frequency_etf.py
```

Data source: yfinance, provider-adjusted OHLCV, cutoff 2026-10-30. This has
survivorship/selection bias because the ETF list is today's surviving funds.
