# P12.5 Macro Event × Individual Equity Sensitivity

Date: 2026-11-19
Branch: `research/macro-cross-sectional-equity-response`
Base HEAD before work: `7da0a4614e701fa6329b91231d8dc48dc3ce3474` (PR #559, Draft)
Status: `STRATEGY_ALPHA_STATUS = NO_GO` for FOMC rate sensitivity; BLS CPI/Employment precise events `DATA_BLOCKED`.

## 1. Official event data audit

Attempted live official pages:

```text
https://www.bls.gov/bls/news-release/cpi.htm       -> HTTP 403
https://www.bls.gov/bls/news-release/empsit.htm    -> HTTP 403
```

No proxy/identity spoofing was used. The existing local archive has:

| family | events | date range | precision |
|---|---:|---|---|
| CPI | 166 | 2007-01-18..2020-10-13 | DATE_ONLY_NOT_PRECISE |
| Employment Situation | 166 | 2007-01-05..2020-10-02 | DATE_ONLY_NOT_PRECISE |
| FOMC | 168 | 2007-01-31..2026-10-28 | 14:00 America/New_York, medium confidence |

No CPI/Employment event can be assigned an official embargo/publication time from
a verified release page. They were therefore excluded from empirical tests; they
were not filled with an assumed 08:30 ET. `MACRO_EVENT_DATA_STATUS = PARTIAL`
(CPI/Employment precise timestamps `DATA_BLOCKED`).

## 2. FOMC empirical sample

Local PIT snapshot `research_factor_snapshots_sp500_pit_10y.csv`
(artifact run 39712671160, size 197,758,512 bytes):

- 76 FOMC events with sufficient pre-event history;
- 31,779 stock-event observations;
- 479 tickers;
- 2017-12-13 to 2026-07-29;
- beta window 252 trading days, minimum 180;
- signal = last close strictly before publication date;
- returns from event-session close to close at 1/5/10/20 days;
- excess = stock return − SPY return.

Limitations: snapshot `Price` is unadjusted close; no dividend/split total-return
adjustment. Close-to-close is a research proxy, not executable next-open fill.

## 3. Results

Univariate event-level tests (76 events), BH across 12 tests:

| horizon | feature | mean IC | IC t | mean top-bottom | spread t | raw p | BH q |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1D | Beta_TLT | +0.038 | 1.27 | +0.345% | 2.19 | 0.032 | 0.192 |
| 5D | Beta_TLT | -0.015 | -0.52 | +0.073% | 0.23 | 0.820 | 0.984 |
| 10D | Beta_TLT | -0.020 | -0.68 | +0.009% | 0.02 | 0.984 | 0.984 |
| 20D | Beta_TLT | -0.025 | -0.83 | -0.318% | -0.50 | 0.616 | 0.954 |
| 20D | Beta_SPY | +0.045 | 1.30 | +1.508% | 1.75 | 0.084 | 0.335 |

The only raw 5% result is 1D Beta_TLT top-minus-bottom (+34.5 bps, t=2.19,
p=0.032), but BH q=0.192; it does not survive multiple testing. Its 95% event
bootstrap-style normal CI is approximately +0.04% to +0.65%, but the event
distribution is not independent of market regime.

## 4. Out-of-sample

Events split chronologically 60/20/20:

| split | events | 1D IC | 5D IC | 10D IC | 20D IC |
|---|---:|---:|---:|---:|---:|
| train | 45 | +0.089 | +0.010 | +0.009 | +0.009 |
| validation | 15 | -0.057 | -0.096 | -0.116 | -0.105 |
| test | 16 | -0.014 | -0.009 | -0.009 | -0.045 |

The train-period 1D signal reverses in validation and remains negative in test.
No stable OOS rate-sensitivity alpha was found. Therefore no portfolio backtest,
IBKR cost model, or 20% QQQ/80% BIL comparison was run: doing so after a failed
OOS would be data mining.

## 5. Decision

```text
STRATEGY_ALPHA_STATUS = NO_GO
DATA_READINESS = PARTIAL (FOMC precise; CPI/Employment blocked)
STATISTICAL_VALIDITY = NO (BH q=0.192 for best result)
OUT_OF_SAMPLE_VALIDITY = NO (test IC negative at all horizons)
COST_ADJUSTED_VALIDITY = NOT_TESTED (no tradable signal)
PORTFOLIO_VALIDITY = NOT_TESTED
PRODUCTION_READINESS = NO
```

This confirms `FOMC × Beta_TLT` is not a deployable cross-sectional strategy at
1/5/10/20 days. The next useful step is obtaining verified BLS release pages
(initial release values and embargo times) or a licensed PIT macro surprise
source; repeating technical-factor permutations is not justified.

## 6. Reproducibility

Script: `tools/research/p12_5_fomc_rate_beta.py`
Tests: `tests/test_p12_5_macro_research.py` (3 passed)
Outputs: `data/research/macro_cross_sectional/` with:
`summary.json`, `event_results.csv`, `oos_ic.csv`, `fomc_rate_beta_panel.csv`,
`manifest.json`.

Raw snapshot and raw HTML remain local/uncommitted.
No model call, no API key, no broker, no order.
