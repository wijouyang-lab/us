# ETF Regime-Conditioned Reversal Results

Date: 2026-11-02  
Status: **PROMISING RESEARCH CANDIDATE ONLY — NOT STRATEGY VALIDATION**  
Implementation: [PR #429](https://github.com/wijouyang-lab/us/pull/429)  
Latest artifact run: [41408287341](https://github.com/wijouyang-lab/us/actions/runs/41408287341)  
Regime report: Actions artifact `short-term-reversal-etf-history` (includes source CSVs, manifest, aggregate screen, and regime diagnostics).

## 1. Reproducibility and scope

- Yahoo Finance via yfinance 1.7.0; no API token.
- Symbols: GLD, IWM, QQQ, TLT, BIL, SGOV, SHV; SPY supplies the exchange-session calendar and market regime.
- Price data were downloaded in the same GitHub Actions run that produced the result. The output remains a third-party provider artifact and is not production data.
- Regime workflow's ETF history normalization and event-study tests passed; stock screen also completed successfully.
- Full repository tests for this commit were still running when this report was written; do not mark the overall CI gate green until that run concludes.

The initial ETF event study found QQQ was the only asset with a strong aggregate event-vs-non-event result across the initial seven-ETF / three-horizon / 21-test family. The follow-up below conditions on SPY market state and expands the correction family to **63 tests**.

## 2. Locked event definition

For each ETF separately:

1. Compute its split/dividend provider-adjusted five-session return.
2. Event at signal close t when that return is at or below the 5th percentile of its trailing 252 completed five-session returns. The threshold is shifted by one session, so t is not in its own threshold.
3. Enter at the next SPY session Open; exit at the Open exactly H further SPY sessions later, for H = 1, 3, 5.
4. Adjusted Open is raw Open × (Adj Close / Close), used as a provider-adjusted total-return proxy.
5. Compare event returns with SPY and, when the ETF history overlaps, BIL.
6. Apply round-trip cost stresses of 5, 10, 20, and 50 bps per side.

SPY state at signal close:
- RISK_ON: Close > MA200 and MA200 20-session slope > 0.
- RISK_OFF: Close < MA200 and MA200 20-session slope < 0.
- TRANSITION: all other observations. This is a residual/mixed state, not a definitive sideways-market label.

Within each ETF/horizon, the HAC OLS model includes market-state intercept controls and Event × market-state interactions. It estimates the event-minus-non-event return effect within each regime, using a 20-session Newey-West lag. BH correction is applied across all 63 ETF × horizon × regime tests. P-values use a normal approximation.

## 3. Main finding

Only three of the 63 adjusted tests have BH q < 0.05, and all three belong to QQQ:

| ETF | Horizon | SPY regime | Events | Non-overlap | Mean event total return | Mean excess vs SPY | Net excess vs SPY at 10 bps/side | Event effect vs non-event | HAC t | BH q |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| QQQ | 1 | RISK_OFF | 90 | 90 | +1.149% | +0.301% | +0.101% | +1.206% | 3.405 | 0.0393 |
| QQQ | 3 | TRANSITION | 103 | 56 | +1.433% | +0.592% | +0.392% | +1.321% | 3.095 | 0.0393 |
| QQQ | 5 | TRANSITION | 103 | 43 | +2.166% | +0.839% | +0.639% | +1.920% | 3.174 | 0.0393 |

The 5-session QQQ TRANSITION result is the strongest candidate for a dedicated follow-up:

- 103 signal events, 43 non-overlapping events.
- Mean event return +2.166%; median +1.586%.
- Mean excess vs SPY +0.839% per event.
- Net mean excess vs SPY +0.639% at 10 bps per side and +0.439% at 20 bps per side under the simple round-trip deduction.
- At 50 bps per side, this mean excess becomes negative; the cost result is not robust to very high execution costs.

QQQ has no meaningful RISK_ON reversal result in this screen. The QQQ RISK_OFF 3-day and 5-day tests do not pass the 63-test BH threshold. The 1-day RISK_OFF result is statistically interesting but has only +0.101% net excess vs SPY at 10 bps per side and turns negative at 20 bps per side.

No other ETF passed the 63-test BH screen. SGOV has small, statistically detectable event effects in some cells but does not show attractive excess versus SPY after costs; do not interpret its low-volatility response as an alpha strategy.

## 4. QQQ chronological sensitivity — post-hoc, not holdout

The QQQ 5-day TRANSITION result was described across four chronological periods after inspecting the full-sample discovery. These rows are explicitly **post-hoc** and are not independent confirmation.

| Period | Events | Non-overlap | Mean excess vs SPY | Net excess at 10 bps/side | Net excess at 20 bps/side |
|---|---:|---:|---:|---:|---:|
| 1999–2006 | 22 | 11 | +1.535% | +1.335% | +1.135% |
| 2007–2015 | 46 | 16 | +0.394% | +0.194% | -0.006% |
| 2016–2020 | 14 | 7 | +1.737% | +1.537% | +1.337% |
| 2021–2026-10 | 21 | 9 | +0.486% | +0.286% | +0.086% |

This is a useful robustness clue: the mean excess direction remains positive across the four periods at the 10 bps/side stress, but the smallest periods have very few independent events, and the 2007–2015 result is essentially zero at 20 bps/side. It is not a substitute for an untouched forward period.

## 5. Decision and strategy architecture

- The stock short-term relative-reversal study remains a negative research result. Do not resurrect or tune it.
- Do not promote all ETF mean reversion as a strategy family.
- Keep one candidate only: **QQQ extreme-down / 5-day recovery, gated to the predeclared SPY TRANSITION state**.
- Treat QQQ RISK_OFF 1-day as secondary discovery evidence, not an additional strategy sleeve.
- GLD, IWM, TLT, BIL, SGOV, and SHV remain non-passing for this reversal hypothesis.
- BIL / SHV remain candidates for defensive cash parking, not alpha sleeves. TLT remains duration risk, not cash.

The next valid task is an execution-aware, non-overlapping daily-NAV simulation of the locked QQQ TRANSITION candidate. It must not tune the threshold, holding period, regime boundary, or cost model against this same sample. Include idle cash / BIL outside trades, compare against SPY and QQQ buy-and-hold, and report trade count, skipped signals, exposure, turnover, CAGR, volatility, Sharpe, max drawdown, and costs. Any historic result remains exploratory because the signal and regimes have already been inspected. A prospective paper period is required before approval.

## 6. Limitations

- Current surviving ETF set only; no reconstructed history of closed/liquidated funds.
- Yahoo Finance Adj Close is a provider-adjusted total-return proxy, not an independently audited total-return index.
- Event windows overlap; non-overlapping counts are shown. The next portfolio simulation must enforce one live position at a time.
- Event-level round-trip cost deductions do not model bid/ask spread, market impact, capacity, fill rejection, or tax.
- The period sensitivity is post-hoc; it is not an untouched holdout.
- This report is a research screen, not a portfolio CAGR, deployable alpha, or strategy approval.
