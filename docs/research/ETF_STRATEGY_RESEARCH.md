# Low-Frequency ETF Strategy Research

Date: 2026-11-03
Branch: `research/low-frequency-etf-strategies`
Status: **NO-GO for all three candidates**

This is research only. No broker connection, no orders, no deployment.

## 1. Scope and pre-registered candidates

Universe: SPY, QQQ, IWM, EFA, EEM, TLT, IEF, GLD, DBC; BIL is cash.

Account: $50,000, long-only, no leverage, daily NAV. Portfolio window
2007-05-30 to 2026-10-30.

| ID | Rule fixed before running |
|---|---|
| A | 12-month total return; top 3 positive-momentum ETFs relative to BIL; monthly rebalance at next session open; BIL if none |
| B | 200-day SMA regime; inverse 60-day vol weights among qualifying ETFs; 10% annualized vol target; monthly rebalance at next open; BIL if none |
| C | Frozen QQQ TRANSITION: 252-day 5% lower tail of 5-session return, SPY TRANSITION, next-open entry, 5 further SPY sessions, 25% sleeve, remainder BIL |

No parameter search was performed. C was not re-tuned. A/B rules were fixed
before the run. No D/E search was run.

## 2. Warm-up, data and snapshot

Indicators use all available history **before** 2007-05-30; NAV and trades only
from 2007-05-30. A/B/C are computed on the full history and then evaluated on
the portfolio window.

```text
A: 252-session momentum uses 2006-2007 history (and earlier).
B: 200-day SMA + 60-day vol use pre-2007 history.
C: QQQ 252-day/5-session quantile + SPY MA200/slope20 use pre-2007 history.
BIL listed 2007-05-30; before its 252-day history exists, A's absolute BIL
filter is unavailable and the strategy holds BIL. No value was synthesized.
```

Raw downloads end 2026-11-02. A separate backtest snapshot is cut at
2026-10-30; only that snapshot is loaded by the engine.

| Snapshot | Max date | Rows SPY | Purpose |
|---|---|---:|---|
| raw download | 2026-11-02 | 6,749 | provenance only |
| backtest input | 2026-10-30 | 6,748 | all indicators/NAV/trades |

`data/research/etf_strategy_study/manifest.json` records both SHA-256 sets,
download time, raw max, research cutoff, and backtest-input max.

All ten ETFs were listed before the 2007 portfolio start; IWM 2000-05, EFA
2001-08, EEM 2003-04, GLD 2004-11, DBC 2006-02. No pre-listing rows were
synthesized or forward-filled. Source is yfinance, provider-adjusted OHLCV.

The ETF list is today's surviving set, so survivorship/selection bias is
disclosed. No parameter was fitted on a training period; the periods below are
evaluation windows, not a fitted train/validation/test exercise.

## 3. Price and cost accounting

- Signals use adjusted Close (total-return series) through the signal close.
- Execution uses **raw Open** at the next session; raw Open is the tradable
  historical price reference.
- NAV marks positions at **raw Close**, with ex-date cash dividends credited to
  cash. AdjClose is used only for signal history, not as a NAV or execution price.
- Raw OHLC is split-adjusted by the provider; no split adjustment is applied
  twice. Dividends are credited separately.
- Missing portfolio-session prices raise an error; no forward-fill.

IBKR Pro Tiered simulation:

```text
commission = max($0.35, min($0.0035/share, 1% of trade value))
sell SEC   = 0.0000278 脳 notional
sell TAF   = min($0.000166/share, $8.30)
exchange   = $0.000003/share
base slip  = 5 bps per leg; sensitivity 1/3/10/20 bps
```

This is a **historical simulation assumption**, not a claim of actual past IBKR
execution. Slippage is simulated because historical quoted spreads were not
available.

## 4. Headline results at 5 bps/leg

| Strategy | Final NAV | CAGR | Vol | Sharpe | Sortino | Calmar | Max DD | Peak鈫扵rough | Trough鈫扲ecovery | Longest UW | Order legs | Exposure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A Dual Momentum | $160,960.99 | 6.21% | 13.51% | 0.51 | 0.65 | 0.24 | **-25.59%** | 78 | 553 | 630 | 733 | 78.5% |
| B Trend/Vol | $172,469.83 | 6.59% | 8.84% | 0.77 | 1.02 | 0.43 | **-15.20%** | 412 | 177 | 588 | 1,643 | 75.4% |
| C QQQ Transition | $72,679.94 | 1.94% | 2.06% | 0.95 | 0.69 | 0.35 | **-5.52%** | 8 | 500 | 1,322 | 129 (32 round trips) | 0.78% |
| BIL | $65,536.54 | 1.40% | 0.49% | 2.87 | 鈥?| 鈥?| -0.78% | 鈥?| 鈥?| 鈥?| 鈥?| 100% |
| SPY | $351,505.57 | 10.56% | 19.66% | 0.61 | 鈥?| 鈥?| -55.19% | 鈥?| 鈥?| 鈥?| 鈥?| 100% |

Drawdown dates:

| Strategy | Peak | Trough | Recovery |
|---|---|---|---|
| A | 2008-07-14 | 2008-10-31 | 2011-01-12 |
| B | 2022-03-08 | 2023-10-26 | 2024-07-12 |
| C | 2020-03-04 | 2020-03-16 | 2022-03-09 |

A and B fail the 15% drawdown limit at the base cost. B misses by 0.20
percentage points. C passes drawdown but its excess over BIL is small.

Annualized turnover (total traded notional / final NAV / years):

```text
A 2.59x    B 2.87x    C 1.29x
```


## 5. Costs and cost sensitivity

### Total realized simulation cost at 5 bps/leg

| Strategy | Commission | SEC | TAF | Exchange | Slippage | Total |
|---|---:|---:|---:|---:|---:|---:|
| A | $457.44 | $111.51 | $7.16 | $0.27 | $4,044.67 | **$4,621.04** |
| B | $772.67 | $132.69 | $10.05 | $0.37 | $4,810.48 | **$5,726.25** |
| C | $74.97 | $25.06 | $1.60 | $0.06 | $933.25 | **$1,034.94** |

### CAGR and max DD across slippage assumptions

| Strategy | 1 bps | 3 bps | 5 bps | 10 bps | 20 bps |
|---|---:|---:|---:|---:|---:|
| A CAGR | 6.43% | 6.32% | 6.21% | 5.94% | 5.40% |
| A MaxDD | -25.5% | -25.6% | -25.6% | -25.7% | -25.9% |
| B CAGR | 6.82% | 6.70% | 6.59% | 6.30% | 5.76% |
| B MaxDD | -14.85% | -15.03% | -15.20% | -15.65% | -16.45% |
| C CAGR | 2.02% | 1.98% | 1.94% | 1.86% | 1.68% |
| C MaxDD | -5.51% | -5.53% | -5.52% | -5.56% | -5.70% |

B is within 15% only at 1鈥? bps slippage, not at the pre-registered 5 bps base.
No lower-slippage assumption is substituted for the decision.

## 6. Statistical tests

Newey-West HAC, lag 20, full daily time axis. Alpha is annualized mean daily
excess return; p-values BH-adjusted across A/B/C.

| Strategy | vs | Alpha | HAC t | raw p | BH q | 95% CI |
|---|---|---:|---:|---:|---:|---:|
| A | BIL | +5.55% | 2.02 | 0.043 | 0.065 | +0.17%..+10.93% |
| B | BIL | +5.38% | 3.10 | 0.002 | **0.006** | +1.98%..+8.78% |
| C | BIL | +0.55% | 1.68 | 0.094 | 0.094 | -0.09%..+1.20% |
| A | SPY | -5.04% | -1.52 | 0.127 | 鈥?| -11.52%..+1.44% |
| B | SPY | -5.28% | -1.68 | 0.093 | 鈥?| -11.44%..+0.87% |
| C | SPY | -10.08% | -2.68 | 0.007 | 鈥?| -17.45%..-2.72% |

B has a statistically supported excess over BIL at the 5% BH threshold. It still
fails the 15% drawdown gate. A does not survive BH. C's alpha CI includes zero.

Daily block bootstrap (20-session circular blocks, 500 samples) CAGR CI:

| Strategy | 2.5% | 97.5% |
|---|---:|---:|
| A | +0.88% | +11.91% |
| B | +3.00% | +10.21% |
| C | +1.23% | +2.74% |

## 7. PR #438 comparison for C

PR #438 frozen config (`w25_c5_qqq_only`) has 32 trades. PR #451 with the same
252/5%/TRANSITION/5-session rules has 32 trades. Signal dates are inferred as the
prior SPY session; entry/exit dates and prices are compared in
`docs/research/etf_strategy_study/pr438_comparison.csv`.

| Check | Result |
|---|---|
| Trade count | 32 vs 32 |
| Exact entry/exit-date matches | 30 / 32 |
| One-session differences | 2: 2011-08-10鈫?011-08-11; 2020-03-17鈫?020-03-18 |
| Price convention | PR #438 uses adjusted Open; PR #451 uses raw Open |
| Max entry price difference | $9.76 (not like-for-like; raw vs adjusted) |
| Max exit price difference | $9.96 (not like-for-like; raw vs adjusted) |
| Max gross-return difference | 0.108% |

The two one-session shifts occur when the 252-day threshold is borderline and
the vendor-adjusted history differs slightly. They are explained as data-provider
revisions, not rule changes. PR #438's published entry/exit prices use adjusted
Open and are not directly comparable to PR #451's raw tradable Open. The remaining
CAGR gap (2.02% vs 1.94%) is the four-leg (BIL+QQQ) cost model versus PR #438's
QQQ-only cost model, plus price-convention and provider revisions.

Signal dates are the prior SPY session, so the two signal-date differences map
one-for-one to the two entry shifts. PR #438's `units` column is a fractional
portfolio weight (about 0.006), while PR #451 records actual ETF shares. The
quantities are therefore not directly comparable; trade count, signal/entry/exit
dates, and gross returns are the comparison basis.

## 8. Stage stability

| Strategy | 2007-2015 CAGR / DD | 2016-2020 CAGR / DD | 2021-2026 CAGR / DD |
|---|---:|---:|---:|
| A | 4.26% / -25.6% | 5.66% / -18.9% | 9.97% / -18.8% |
| B | 5.38% / -12.4% | 7.66% / -12.0% | 7.66% / -15.2% |
| C | 0.88% / -3.6% | 1.09% / -5.5% | 4.30% / -1.7% |

A has unacceptable drawdown in every period. B exceeds 15% only in 2021-2026
(-15.20%). C is stable by drawdown but its recent return is low, and 2021+ is
not pristine for QQQ reversal.

## 9. Decision against the seven gates

| Gate | A | B | C |
|---|---|---|---|
| Positive excess after IBKR costs + 5 bps slip | Yes | Yes | Yes, small |
| Statistical support vs BIL | No (q=.065) | **Yes (q=.006)** | No (q=.090) |
| Max DD <= 15% | **No (-25.59%)** | **No (-15.20%)** | Yes (-5.52%) |
| Not one period | No | No (2021+ DD) | Mostly stable, but return low |
| Not a few trades | No (monthly concentration) | No (few assets) | No (32 trades, low exposure) |
| Reproducible NAV/orders | Yes | Yes | Yes |
| Failures documented | Yes | Yes | Yes |

Final: **FAILED** for A and B; **FAILED** for C (statistical and return gates).
No GO candidate and therefore no Paper validation plan yet.

B is the strongest candidate: significant alpha (q=.006), 6.59% CAGR, but a
-15.20% baseline drawdown. It cannot be promoted by changing the cost assumption
or re-optimizing.

## 10. What this does and does not prove

- A/B produce attractive long-run CAGR versus BIL; A has unacceptable drawdown,
  B is just outside the risk gate.
- B's HAC alpha survives BH, but risk control fails at the base cost.
- C is a low-risk, low-return sleeve; its alpha CI includes zero.
- No result is deployable. No parameter change was made to rescue any candidate.

## 11. Next pre-registered hypotheses (not tested)

1. **D. Curve/credit regime allocation**: 10Y-3M or 10Y-2Y slope and high-yield
   spread switching SPY/IEF/TLT/BIL; monthly; thresholds fixed from economic
   definitions, not optimization.
2. **E. Commodity carry/roll**: DBC/GLD/TLT relative carry with BIL fallback;
   requires verified roll-yield/carry data, not price-only proxy.

These are proposals only. No D/E search was run.

## 12. Artifacts

```text
data/research/etf_strategy_study/raw/*.csv
data/research/etf_strategy_study/*.csv
data/research/etf_strategy_study/manifest.json
docs/research/etf_strategy_study/results.json
docs/research/etf_strategy_study/metrics_summary.csv
docs/research/etf_strategy_study/stage_summary.csv
docs/research/etf_strategy_study/trades_base5.csv
docs/research/etf_strategy_study/pr438_trade_ledger.csv
docs/research/etf_strategy_study/pr438_comparison.csv
docs/research/etf_strategy_study/pr438_comparison.json
docs/research/etf_strategy_study/nav_A.csv
docs/research/etf_strategy_study/nav_B.csv
docs/research/etf_strategy_study/nav_C.csv
tools/research/low_frequency_etf.py
tests/test_low_frequency_etf.py
```

Data source: yfinance, provider-adjusted OHLCV. Survivorship/selection bias
remains because the ETF list is today's surviving funds.
