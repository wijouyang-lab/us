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

| Strategy | Final NAV | CAGR | Vol | Sharpe | Sortino | Calmar | Max DD | Recovery | Order legs | Exposure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A Dual Momentum | $161,098.96 | 6.21% | 13.52% | 0.51 | 0.65 | 0.24 | **-25.60%** | 633 sessions | 738 | 89.6% |
| B Trend/Vol | $160,857.37 | 6.20% | 8.63% | 0.74 | 0.96 | 0.41 | **-15.18%** | 588 sessions | 1,557 | 85.4% |
| C QQQ Transition | $73,066.71 | 1.98% | 1.98% | 1.00 | 0.73 | 0.36 | **-5.46%** | 1,322 sessions | 108 (27 round trips) | 0.69% |
| BIL | $65,536.54 | 1.40% | 0.49% | 2.87 | — | — | -0.78% | — | — | 100% |
| SPY | $351,505.57 | 10.56% | 19.66% | 0.61 | — | — | -55.19% | — | — | 100% |

A and B both fail the 15% drawdown limit at the base cost. B misses by only
0.18 percentage points; C passes drawdown but produces only a small excess over
BIL.

## 5. Costs and cost sensitivity

### Total realized simulation cost at 5 bps/leg

| Strategy | Commission | SEC | TAF | Exchange | Slippage | Total |
|---|---:|---:|---:|---:|---:|---:|
| A | $509.45 | $111.93 | $8.40 | $0.31 | $4,048.96 | **$4,679.05** |
| B | $774.23 | $122.42 | $10.87 | $0.40 | $4,425.32 | **$5,333.24** |
| C | $67.02 | $21.41 | $1.47 | $0.05 | $769.86 | **$859.82** |

### CAGR and max DD across slippage assumptions

| Strategy | 1 bps | 3 bps | 5 bps | 10 bps | 20 bps |
|---|---:|---:|---:|---:|---:|
| A CAGR | 6.43% | 6.33% | 6.21% | 5.94% | 5.41% |
| A MaxDD | -25.5% | -25.6% | -25.6% | -25.6% | -25.9% |
| B CAGR | 6.41% | 6.31% | 6.20% | 5.94% | 5.39% |
| B MaxDD | -14.9% | -15.0% | -15.2% | -15.7% | -16.5% |
| C CAGR | 2.03% | 2.00% | 1.98% | 1.90% | 1.76% |
| C MaxDD | -5.4% | -5.5% | -5.5% | -5.5% | -5.6% |

B is within 15% only at 1–3 bps slippage, not at the pre-registered 5 bps base.
No lower-slippage assumption is substituted for the decision.

## 6. Statistical tests

Newey-West HAC, lag 20, full daily time axis. Alpha is annualized mean daily
excess return; p-values BH-adjusted across A/B/C.

| Strategy | vs | Alpha | HAC t | raw p | BH q | 95% CI |
|---|---|---:|---:|---:|---:|---:|
| A | BIL | +5.55% | 2.02 | 0.043 | 0.063 | +0.17%..+10.94% |
| B | BIL | +5.00% | 2.97 | 0.003 | **0.009** | +1.70%..+8.30% |
| C | BIL | +0.58% | 1.86 | 0.063 | 0.063 | -0.03%..+1.20% |
| A | SPY | -5.04% | -1.52 | 0.127 | — | -11.52%..+1.44% |
| B | SPY | -5.59% | -1.76 | 0.078 | — | -11.81%..+0.63% |
| C | SPY | -10.01% | -2.69 | 0.007 | — | -17.31%..-2.71% |

B has a statistically supported excess over BIL at the 5% BH threshold. It still
fails the 15% drawdown gate. A does not survive BH. C's alpha CI includes zero.

Daily block bootstrap (20-session circular blocks, 500 samples) CAGR CI:

| Strategy | 2.5% | 97.5% |
|---|---:|---:|
| A | +0.57% | +11.55% |
| B | +2.90% | +9.77% |
| C | +1.32% | +2.67% |

## 7. Stage stability

| Strategy | 2007-2015 CAGR / DD | 2016-2020 CAGR / DD | 2021-2026 CAGR / DD |
|---|---:|---:|---:|
| A | 4.26% / -25.6% | 5.68% / -19.0% | 9.97% / -18.8% |
| B | 4.52% / -10.9% | 7.66% / -12.0% | 7.68% / -15.2% |
| C | 0.95% / -3.6% | 1.08% / -5.5% | 4.31% / -1.6% |

A has unacceptable drawdown in every period. B exceeds 15% only in 2021-2026
(-15.18%) and is otherwise within the limit. C is stable by drawdown but its
recent return is low, and 2021+ is not pristine for QQQ reversal.

## 8. Decision against the seven gates

| Gate | A | B | C |
|---|---|---|---|
| Positive excess after IBKR costs + 5 bps slip | Yes | Yes | Yes, small |
| Statistical support vs BIL | No (q=.063) | **Yes (q=.009)** | No (q=.063) |
| Max DD <= 15% | **No (-25.6%)** | **No (-15.18%)** | Yes (-5.46%) |
| Not one period | No | No (2021+ DD) | Mostly stable, but return low |
| Not a few trades | No (monthly concentration) | No (few assets) | No (27 round trips, low exposure) |
| Reproducible NAV/orders | Yes | Yes | Yes |
| Failures documented | Yes | Yes | Yes |

Final: **FAILED** for A and B; **FAILED** for C (statistical and return gates).
No GO candidate and therefore no Paper validation plan yet.

B is the strongest candidate: it has a significant excess over BIL and a CAGR of
6.20%, but its 5 bps base-case drawdown is -15.18%, just outside the 15% target.
It cannot be promoted by changing the slippage assumption or re-optimizing.

## 9. What this does and does not prove

- A/B produce attractive long-run CAGR versus BIL, but A has unacceptable
  drawdown; B is just outside the drawdown gate.
- B's HAC alpha survives BH (q=.009), but risk control fails at the base cost.
- C is a low-risk, low-return sleeve; it does not demonstrate a reliable excess
  over cash, and its recent period is not untouched data.
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
docs/research/etf_strategy_study/metrics_summary.csv
docs/research/etf_strategy_study/stage_summary.csv
docs/research/etf_strategy_study/trades_base5.csv
docs/research/etf_strategy_study/nav_A.csv
docs/research/etf_strategy_study/nav_B.csv
docs/research/etf_strategy_study/nav_C.csv
tools/research/low_frequency_etf.py
tests/test_low_frequency_etf.py
```

Data source: yfinance, provider-adjusted OHLCV, cutoff 2026-10-30. This has
survivorship/selection bias because the ETF list is today's surviving funds.
