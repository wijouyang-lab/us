# Short-Term Reversal Research Protocol

Date: 2026-11-02

Status: **protocol only; no strategy approval, no production changes, no multi-strategy allocator changes**.

Research branch is based on `research/phase3-2-2-recovery`. This document does not reopen Trend V1 or change its negative decision.

## 1. Why this is a new, narrow question

Mean reversion has already been explored. The next experiment must not rerun the same 20-session design under a new name.

| Existing experiment | Existing definition | Reported result | Interpretation |
|---|---|---|---|
| Technical `MeanReversion` | `Rev5 = -(Close / Close[-5] - 1)`; monthly signal; bottom-tail names long; next Open entry; 20-session Open-to-Open exit | 104 monthly observations; 10 bps net CAGR 8.45%; Sharpe 0.356; max drawdown -34.69%; mean turnover 0.777; gross excess CAGR vs equal-weight -1.13 pp | 20-session holding did not add value vs equal-weight |
| Z-Score cross-sectional test | Long low `ZScore_20D`; 20-session forward return; non-overlapping observations | Test n=24; net +0.229% / 20 sessions; net excess vs equal-weight -0.480% / 20 sessions; rough Sharpe 0.32; turnover 82.06% | Small sample, negative excess, high turnover |
| Factor quintile report | Daily Z-Score ranks; Q5-Q1 | 20D spread +0.2642%; non-monotonic; overlapping labels; in-sample direction; no costs | Factor separation only, not a tradeable strategy |

The new hypothesis is deliberately narrower:

> **After an unusually weak five-session move relative to SPY, does a long-only basket experience a short-lived rebound over the next 1–5 sessions, and does that relationship vary by broad-market regime?**

This differs from the previous 20-session tests by (a) using market-relative rather than only absolute weakness, (b) focusing on 1/3/5-session exits, and (c) predeclaring market-regime slices rather than assuming one average effect.

## 2. Stock experiment: predeclared primary specification

### Universe and label

- Input: `research_price_history_sp500_10y.csv` plus `research_spy_sp500_10y.csv`.
- Label every result `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`.
- The backfill script downloads the **current** Wikipedia S&P 500 list. Historical membership filtering does not restore removed or delisted companies that are absent from that download. Do not call this a complete point-in-time universe.
- Use the SPY trading calendar as the exchange-session calendar.
- Eligibility at signal close: Close >= $5, 20-session average dollar volume >= $5 million, and at least 80 eligible names for the cross-section. These are inherited screening values, not optimized in this experiment.
- Use split-adjusted Close for signal calculations and raw Open for hypothetical execution. This is a **price-return** study; dividends are not credited. Never label it total return.

### Signal

For each stock and signal close t:

`RelRet5(t) = [Close(t) / Close(t-5) - 1] - [SPY_Close(t) / SPY_Close(t-5) - 1]`

Rank eligible stocks by `RelRet5` on each signal date. The candidate portfolio is the lowest 20% (most negative relative five-session returns), equal-weighted and long-only.

Do not add RSI thresholds, volatility filters, MA filters, sector filters, or parameter searches to the primary specification. Those may be separately registered as later hypotheses only after this screen is reported.

### Execution and horizons

- Signal is formed after close t.
- Entry is the next SPY session Open.
- Exit is the SPY session Open exactly H sessions after entry.
- Primary horizon: **H=3 sessions**.
- Robustness horizons: H=1 and H=5 sessions.
- If a selected stock lacks Open on the exact SPY entry or exit session, exclude that event and report the missing-price count. Do not jump to the ticker's next available row, forward-fill, or silently carry a stale price.
- The equal-weight eligible-universe benchmark and SPY benchmark use the exact same entry and exit timestamps.

The initial output is an **event study**, not a daily-NAV portfolio backtest. Forward returns overlap when every market session generates a signal. Use Newey-West/HAC standard errors with lag H-1 for mean-return and excess-return tests; disclose the number of dates and effective non-overlapping observations. Do not present an event-return series Sharpe or CAGR as though it were a continuously invested strategy.

For transparent cost stress, show round-trip deductions at 5/10/20/50 bps per side. This simple event-level cost stress is not a substitute for portfolio turnover, spread, market impact, or fill simulation.

## 3. Market-regime conditioning (fixed before looking at results)

Use SPY information available at signal close only:

- **RISK_ON:** SPY Close > MA200 and MA200 / MA200[-20] - 1 > 0.
- **RISK_OFF:** SPY Close < MA200 and MA200 / MA200[-20] - 1 < 0.
- **TRANSITION:** all other observations.

Report the same primary stock signal separately in all three states. Also report, as a secondary descriptive split, candidates above vs below their own MA200. Do not use the regime-conditioned result to tune the definition in this experiment.

The main question is whether the reversal signal is positive after costs and whether it behaves differently in risk-on, risk-off, and transition periods. A weak result in risk-off is not a reason to search the same test set for a more favorable threshold.

## 4. Chronological reporting

Use the existing chronological reporting blocks for comparability:

- Development description: 2018-01-01 through 2020-12-31.
- Validation description: 2021-01-01 through 2023-12-31.
- Later-period report: 2024-01-01 through the last date common to the stock and SPY panels.

Purge any event whose entry/exit crosses a reporting boundary. These periods are **not an untouched holdout**: the same underlying panel has already been used in earlier factor and strategy research. Results can screen hypotheses and describe temporal variation, but cannot constitute final independent OOS proof. Do not choose a winning horizon or regime based on the later-period report and then present it as confirmatory.

For each horizon and regime, report at minimum: event dates, selected-name count, mean/median gross return, mean/median excess vs equal-weight and SPY, win rate, HAC standard error/t-stat/95% CI, round-trip cost sensitivity, missing execution-price count, and non-overlapping observation count. Apply Benjamini-Hochberg correction across the predeclared horizon-by-regime family; show raw and adjusted p-values. No ranking based only on raw p-values.

## 5. ETF experiment: separate time-series study

The four ETF symbols used by Trend V1 are GLD, IWM, QQQ, and TLT. They are not present as reproducible price files in the current repository tree; Trend V1 expects one CSV per ETF in a local `--etf-dir`. Therefore the ETF leg is **data-blocked** until those source files and their provenance are supplied or reproduced.

Do not mix four ETFs into the stock cross-sectional ranking. With only four funds, a cross-sectional ETF result would be too fragile. For each ETF independently:

- compute its five-session price return;
- define an extreme-down event as a five-session return at or below its trailing 252-session 5th percentile, calculated strictly using observations before t;
- signal after close t, enter next session Open, and exit after 1/3/5 SPY sessions;
- report each ETF separately and then an explicitly labeled descriptive aggregate; do not imply the four funds represent the full ETF universe.

This is an exploratory time-series event study. It remains exposed to ETF survivorship/closure bias and excludes distributions unless a validated total-return series is available. Do not substitute SPY for the missing ETF files.

## 6. Data and implementation guards

The eventual runner must fail closed or count and exclude the affected observation for:

- duplicate ticker/session rows;
- non-positive or missing OHLC;
- missing exact SPY calendar entry/exit Open;
- insufficient lookback for the signal or regime;
- stale/missing stock observations;
- zero or inadequate dollar volume;
- insufficient cross-sectional names;
- event windows that cross a chronological boundary.

Use the common SPY session calendar for all holding horizons. A ticker's next available row is not necessarily the next exchange session.

Preserve raw inputs. Do not silently repair extreme returns, delisting gaps, ticker aliases, or corporate-action events. Record input SHA, date range, ticker counts, row counts, exclusions, and the data-source label in each output.

## 7. Interpretation and stop rules

This screen is a hypothesis test, not a strategy launch.

A result is **not a pass** merely because:

- gross returns are positive;
- win rate exceeds 50%;
- one regime or horizon looks attractive;
- a raw p-value is below 0.05;
- a four-ETF aggregate is positive.

A research candidate would need positive net excess at the predeclared primary horizon, confidence intervals and multiple-testing results that support a non-random effect, evidence that it is not driven by a few names or one calendar episode, and robustness to 20/50 bps cost stress. Any retrospective result on this reused panel remains exploratory. A genuinely independent forward paper period is required before strategy approval.

If the primary 3-session result is not economically positive after the 10 bps/side stress, record a negative result and do not continue threshold tuning on the same panel. Any follow-up must state a genuinely different hypothesis before its data are inspected.

## 8. Current decision

- Trend V1 remains a negative research result and is not an allocator input.
- Existing 20-session mean-reversion experiments do not show stable excess return.
- The stock short-term relative-reversal screen is sufficiently distinct to justify one tightly predeclared exploratory test.
- The ETF leg cannot be reproduced from repository-tracked ETF files yet.
- No adaptive allocator, Strategy Lab ranking, production scanner, order entry, or production portfolio/ledger change is authorized by this research protocol.
