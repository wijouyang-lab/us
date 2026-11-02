# QQQ TRANSITION 5-Day Reversal: Audited NAV Backtest

Date: 2026-11-02
Label: EXPLORATORY_ETF_SURVIVORSHIP_AND_PROVIDER_ADJUSTED_PRICES
Status: research candidate; not independently validated; not deployable.

## 1. Locked rules

- Only QQQ.
- Signal at close t: QQQ 5-session return <= 5th percentile of the prior 252 completed 5-session returns; threshold shifted one session.
- SPY regime at t must be TRANSITION.
- Entry next SPY session Open.
- Exit at the Open after exactly 5 further SPY sessions.
- One position maximum; overlapping signals skipped.
- Long only, no leverage.
- Idle strategy cash in BIL; reserve capital in BIL.
- Adjusted Open = Raw Open * Adj Close / Close.
- Missing/non-finite/non-positive entry, exit or daily mark fails closed.

No parameter changes, RSI, ATR, stops, or extra filters.

## 2. Warm-up correction

- QQQ/SPY data downloaded from 2006-01-03.
- BIL data from 2007-05-30.
- Indicators are computed on the full history.
- Portfolio NAV and execution start on 2007-05-30.
- No pre-2007 trades or NAV.
- 2007-05-30 has a complete 252-observation five-day return threshold and full SPY MA200/slope history.

Data end: 2026-10-30.

| File | SHA-256 |
|---|---|
| QQQ.csv | 6b0fd14f009339cd2d38bed8ab1730eef268349823d8a71885c9b3db52738e7a |
| BIL.csv | c7475e4b465bff0d9078319125a8b8548d089886bf92c3cda73931b30d810760 |
| SPY.csv | 28fc1b8439b23b573293893a8a4bb002850d8f81aac425573dc0bd1f5e093f6f |

SPY is the sole trading calendar. QQQ/BIL are explicitly aligned to it.

## 3. Warm-up impact: old vs corrected

| Metric | Before warm-up | Audited |
|---|---:|---:|
| Signals | 66 | **81** |
| Trades | 27 | **32** |
| Skipped overlaps | 39 | **49** |
| First trade | 2010-05-21 | **2007-08-15** |
| Completed / open | 27 / 0 | **32 / 0** |
| Pending at end | not reported | **0** |

The extra history creates 15 additional signals and 5 additional executed trades, including the first 2007 trade. It does not create pre-2007 trades.

## 4. Performance at 10 bps, all trading legs

All-legs means BIL-to-QQQ and QQQ-to-BIL conversions are both charged.

| Scheme | Total | CAGR | Vol | Sharpe (rf=0) | MaxDD | Calmar |
|---|---:|---:|---:|---:|---:|---:|
| BIL buyhold | 31.1% | 1.40% | 0.6% | 2.87 | -0.8% | 1.75 |
| SPY buyhold | 603.0% | 10.56% | 18.9% | 0.61 | -55.2% | 0.19 |
| QQQ buyhold | 1608.9% | 15.74% | 24.9% | 0.77 | -53.4% | 0.29 |
| 25% strategy | 43.0% | 1.86% | 2.3% | 0.82 | -6.4% | 0.29 |
| 50% strategy | 54.9% | 2.28% | 4.4% | 0.54 | -12.0% | 0.19 |
| 100% strategy (BIL idle) | 78.7% | 3.03% | 7.9% | 0.41 | -21.3% | 0.14 |
| 100% strategy only (cash idle) | 50.4% | 2.12% | 7.9% | 0.31 | -21.2% | 0.10 |

## 5. QQQ-only vs all-legs costs

At 10 bps:

| Weight | QQQ-only CAGR | All-legs CAGR | QQQ-only MaxDD | All-legs MaxDD |
|---|---:|---:|---:|---:|
| 25% | 1.97% | 1.86% | -6.5% | -6.4% |
| 50% | 2.48% | 2.28% | -12.1% | -12.0% |
| 100% | 3.37% | 3.03% | -21.2% | -21.3% |

BIL conversion costs reduce CAGR by 0.1-0.3pp; they are not hidden inside QQQ costs.

## 6. Cost sensitivity, all legs

CAGR / MaxDD:

| Weight | 5 bps | 10 bps | 20 bps | 50 bps |
|---|---:|---:|---:|---:|
| 25% | 1.97% / -6.5% | 1.86% / -6.4% | 1.66% / -6.1% | 1.16% / -5.5% |
| 50% | 2.48% / -12.1% | 2.28% / -12.0% | 1.90% / -11.7% | 0.90% / -11.3% |
| 100% | 3.37% / -21.2% | 3.03% / -21.3% | 2.36% / -21.6% | 0.35% / -23.5% |
| Strategy only | 2.26% / -21.1% | 2.12% / -21.2% | 1.84% / -21.4% | 0.99% / -22.0% |

## 7. Period diagnostics (10 bps, post-hoc)

| Period | 25% CAGR / DD | 50% CAGR / DD | 100% CAGR / DD |
|---|---:|---:|---:|
| 2007-2015 | 0.86% / -3.6% | 1.25% / -7.1% | 2.01% / -13.6% |
| 2016-2020 | 0.70% / -6.4% | 0.42% / -12.0% | -0.08% / -21.3% |
| 2021-2026 | 4.37% / -1.9% | 5.46% / -3.7% | 7.37% / -6.6% |

Not stable: 2016-2020 is near zero or negative for 100%. These splits are not a holdout.

## 8. Annual returns, 100% all-legs, 10 bps

| Year | Return |
|---|---:|
| 2007 | +5.2% |
| 2008 | -4.6% |
| 2009 | +0.3% |
| 2010 | +10.0% |
| 2011 | -3.1% |
| 2012 | -2.2% |
| 2013 | -0.1% |
| 2014 | -1.8% |
| 2015 | +15.3% |
| 2016 | +0.1% |
| 2017 | +0.7% |
| 2018 | -1.1% |
| 2019 | +9.3% |
| 2020 | -8.5% |
| 2021 | -0.1% |
| 2022 | +11.4% |
| 2023 | +9.9% |
| 2024 | +5.2% |
| 2025 | +6.2% |
| 2026* | +10.6% |

*through 2026-10-30. Each year uses the prior year-end NAV as its base.

## 9. 15% drawdown check, all legs

| Weight | 5 bps | 10 bps | 20 bps | 50 bps | Below 15%? |
|---|---:|---:|---:|---:|---|
| 25% | -6.5% | -6.4% | -6.1% | -5.5% | **Yes** |
| 50% | -12.1% | -12.0% | -11.7% | -11.3% | **Yes** |
| 100% | -21.2% | -21.3% | -21.6% | -23.5% | **No** |

Historical objective only; not a future guarantee.

## 10. Accounting and cost detail

- Initial NAV: first portfolio close = 1.0.
- QQQ buy/sell notional and BIL buy/sell notional are tracked separately.
- Costs are charged once per actual leg.
- For 100% all-legs at 10 bps: QQQ cost 0.076, BIL cost 0.076, total 0.152 of initial capital.
- One-way turnover 38.0x; two-way turnover 76.1x.
- 32 completed trades, 0 open, 0 pending.
- 0 missing execution price events.
- Average holding 7.1 calendar days / 5 sessions.
- Market exposure 2.76% of days.
- Sharpe annualization: sqrt(252), risk-free rate 0%.
- CAGR uses actual calendar time from first to last NAV.

## 11. Answers

1. **Do the original 27 trades still hold?** No. The corrected run has 32 completed trades; warm-up adds 5 trades. All 27 old trades remain, but they are not the full set.
2. **New early signals/trades?** Yes: 81 signals vs 66, first trade 2007-08-15 vs 2010-05-21.
3. **Positive after all costs?** Yes, but small: 1.86%/2.28%/3.03% CAGR for 25/50/100 at 10 bps.
4. **CAGR and MaxDD?** 25%: 1.86%/-6.4%; 50%: 2.28%/-12.0%; 100%: 3.03%/-21.3% (all legs, 10 bps).
5. **Still behind SPY/QQQ?** Yes, substantially: SPY 10.56%, QQQ 15.74%.
6. **Open trades or missing prices?** 0 open, 0 pending, 0 missing execution prices.
7. **Worth prospective paper validation?** Only as a research candidate with a prospective paper period. 32 trades, post-hoc regimes, ETF survivorship and provider-adjusted data are insufficient for independent validation.

## 12. Grade

**Research candidate only. Not independently validated. Not deployable.**
Audited NAV run; research-only.
