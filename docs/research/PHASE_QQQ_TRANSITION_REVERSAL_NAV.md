# QQQ TRANSITION 5-Day Reversal: Independent NAV Backtest

Date: 2026-11-02
Label: EXPLORATORY_ETF_SURVIVORSHIP_AND_PROVIDER_ADJUSTED_PRICES
Status: research candidate only; not validated; not deployable.

## 1. Locked rules

- Only QQQ.
- Signal at close t: QQQ 5-session total return <= 5th percentile of the prior 252 completed 5-session returns. The threshold is shifted one session.
- SPY regime at t must be TRANSITION.
- Entry next SPY session Open.
- Exit at the Open after exactly 5 further SPY sessions.
- One position maximum; overlapping signals skipped.
- Long only, no leverage.
- Idle strategy cash in BIL; portfolio reserve also BIL.
- Adjusted Open = Raw Open * Adj Close / Close.
- Missing exact entry/exit price fails closed.

No RSI, ATR, stop loss, extra filters, alternate assets, or parameter changes.

## 2. Data

Common start: 2007-05-30 (QQQ/BIL/SPY). End: 2026-10-30.

| File | SHA-256 |
|---|---|
| QQQ.csv | 1a44bda88803a63c6f32c3c1d5f187b6883965c6f4eed9c34d643a201fa751ff |
| BIL.csv | 03e8a1c6b66ef30547d63042609f05d46747d35380c6747fea014da058f63658 |
| SPY.csv | 3e61de10decbf7f1cbc465b769aafdbb17786a7eac7892690a8c34a1feaaffa2 |

Provider: Yahoo Finance via yfinance, split/dividend-adjusted provider data. This is not an audited total-return index.

## 3. Signal and trade count

- QQQ TRANSITION signals: 66.
- Executed trades: 27.
- Skipped overlapping signals: 39.
- Missing execution prices: 0.
- Market exposure: 2.76% of days (about 27 x 5 sessions).
- Average holding: 7.1 calendar days (5 sessions).
- Turnover: 8.8x / 17.6x / 35.1x initial capital for 25/50/100%.

## 4. Performance at 10 bps per side

| Scheme | Total | CAGR | Vol | Sharpe (rf=0) | MaxDD | Calmar |
|---|---:|---:|---:|---:|---:|---:|
| BIL buyhold | 31.1% | 1.40% | 0.6% | 2.87 | -0.8% | 1.75 |
| SPY buyhold | 603.0% | 10.56% | 18.9% | 0.61 | -55.2% | 0.19 |
| QQQ buyhold | 1608.9% | 15.74% | 24.9% | 0.77 | -53.4% | 0.29 |
| 25% strategy / 75% BIL | 47.2% | 2.01% | 2.3% | 0.87 | -6.6% | 0.30 |
| 50% strategy / 50% BIL | 63.4% | 2.56% | 4.4% | 0.60 | -12.3% | 0.21 |
| 100% strategy (BIL idle) | 95.7% | 3.52% | 7.9% | 0.48 | -21.2% | 0.17 |
| 100% strategy only (cash idle) | 50.4% | 2.12% | 7.9% | 0.31 | -21.2% | 0.10 |

Total return is from the NAV series, not an arithmetic sum.

## 5. Cost sensitivity

CAGR / MaxDD by per-side cost:

| Weight | 5 bps | 10 bps | 20 bps | 50 bps |
|---|---:|---:|---:|---:|
| 25% | 2.06% / -6.7% | 2.01% / -6.6% | 1.92% / -6.5% | 1.66% / -6.3% |
| 50% | 2.65% / -12.3% | 2.56% / -12.3% | 2.39% / -12.2% | 1.91% / -12.0% |
| 100% | 3.66% / -21.1% | 3.52% / -21.2% | 3.23% / -21.3% | 2.37% / -21.9% |
| Strategy only | 2.26% / -21.1% | 2.12% / -21.2% | 1.84% / -21.4% | 0.99% / -22.0% |

Costs are charged once on entry notional and once on exit notional. BIL earns its adjusted-close return; no separate cash yield was invented.

## 6. Period diagnostics (post-hoc, not holdout)

10 bps:

| Period | 25% CAGR / DD | 50% CAGR / DD | 100% CAGR / DD |
|---|---:|---:|---:|
| 2007-2015 | 1.06% / -3.7% | 1.63% / -7.2% | 2.71% / -13.5% |
| 2016-2020 | 0.76% / -6.6% | 0.56% / -12.3% | 0.20% / -21.2% |
| 2021-2026 | 4.54% / -2.0% | 5.73% / -3.7% | 7.70% / -6.4% |

The result is not stable across periods; 2016-2020 is the weakest. These splits are post-hoc and were not used to choose parameters.

## 7. Annual returns, 10 bps

| Year | 25% | 50% | 100% |
|---|---:|---:|---:|
| 2007 | 2.5% | 2.5% | 2.5% |
| 2008 | 1.6% | 1.6% | 1.6% |
| 2009 | 0.3% | 0.3% | 0.3% |
| 2010 | 2.7% | 5.4% | 10.8% |
| 2011 | -0.7% | -1.3% | -2.5% |
| 2012 | -0.6% | -1.1% | -2.0% |
| 2013 | -0.1% | -0.1% | -0.1% |
| 2014 | -0.5% | -0.9% | -1.6% |
| 2015 | 4.0% | 8.0% | 15.7% |
| 2016 | 0.1% | 0.1% | 0.1% |
| 2017 | 0.7% | 0.7% | 0.7% |
| 2018 | 1.1% | 0.5% | -0.5% |
| 2019 | 4.1% | 6.1% | 9.5% |
| 2020 | -2.1% | -4.3% | -8.0% |
| 2021 | -0.1% | -0.1% | -0.1% |
| 2022 | 4.5% | 7.4% | 12.5% |
| 2023 | 6.5% | 7.9% | 10.2% |
| 2024 | 5.2% | 5.2% | 5.2% |
| 2025 | 4.9% | 5.6% | 6.7% |
| 2026* | 5.5% | 7.5% | 10.8% |

*through 2026-10-30.

## 8. 15% drawdown objective

| Weight | 5 bps | 10 bps | 20 bps | 50 bps | Below 15%? |
|---|---:|---:|---:|---:|---|
| 25% | -6.7% | -6.6% | -6.5% | -6.3% | **Yes, all costs** |
| 50% | -12.3% | -12.3% | -12.2% | -12.0% | **Yes, all costs** |
| 100% | -21.1% | -21.2% | -21.3% | -21.9% | **No** |
| Strategy only | -21.1% | -21.2% | -21.4% | -22.0% | **No** |

This is a historical risk objective, not a guarantee.

## 9. Answers

1. **Positive after costs?** Yes, but small: 25/50/100% CAGR 2.0%/2.6%/3.5% at 10 bps; strategy-only 2.1%.
2. **Versus benchmarks?** Beats BIL (1.4%) but badly trails SPY (10.6%) and QQQ (15.7%). It is not attractive absolute or relative to equity benchmarks.
3. **Stable across periods?** No. 2016-2020 is near zero or negative for 100%; 2021+ is strongest. Post-hoc only.
4. **Max drawdowns:** 25% -6.6%, 50% -12.3%, 100% -21.2% at 10 bps.
5. **Any below 15%?** 25% and 50% pass all tested costs; 100% and strategy-only fail.
6. **Next stage?** Only if treated as a research candidate with a prospective paper period. The 27-trade sample, post-hoc period analysis, ETF survivorship and provider-adjusted prices are insufficient for independent validation or deployment.

## 10. Limitations

- ETF survivor set; no closed/liquidated funds.
- Yahoo adjusted prices, not audited total return.
- 27 trades; low market exposure (2.76%).
- Regime and threshold were discovered on the same history.
- Period splits are post-hoc.
- No bid/ask, market impact, capacity, taxes, or fill rejection.
- No PIT universe.
- Not production; no orders.

## 11. Artifacts

- tools/research/qqq_transition_reversal_nav.py
- tests/test_qqq_transition_reversal_nav.py
- docs/research/qqq_transition_reversal_nav/results.json
- docs/research/qqq_transition_reversal_nav/daily_nav.csv
- docs/research/qqq_transition_reversal_nav/trade_ledger.csv
- data/research/qqq_transition_reversal/{QQQ,BIL,SPY}.csv
