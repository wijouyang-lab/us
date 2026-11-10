# P8.4 Market-Neutral Alpha and Conditional Regimes

Date: 2026-11-09
Status: **P8_4_NO_GO**

P8.3 history is preserved. This round tests whether stock-specific residual
signals survive after removing the market factor, and whether market regimes
explain any conditional performance.

## 1. P8.3 eligibility audit

P8.3 used a prior-60-session `|daily adjusted return| > 5x` filter. New audit:

| Threshold | Ticker-days | Unique tickers | GME days |
|---:|---:|---:|---:|
| 3x | 2,368 | 54 | 0 |
| 5x (primary) | 2,171 | 43 | 0 |
| 10x | 1,584 | 36 | 0 |

- 5x remains the pre-registered primary rule.
- 3x/10x are sensitivity only; they were not used to select the best IC.
- GME is not removed by the rule (no >3x day in the panel).
- A single anomaly continues to block the 60-session formation window; this is
  a known data-quality tradeoff, not a post-hoc rule.

## 2. Label missingness and denominators

- P8.3 panel rows: **352,036** across three horizons.
- All historical S&P member-days: **1,095,490**.
- These are different denominators; they are not interchangeable.
- Valid panel rows: 89.21%; labeled among valid: 99.88%.
- Valid rows without a label: **369**.
- Missing labels are NaN/CENSORED, never zero.
- Missingness is concentrated in early years and in higher-volatility names;
  the audit files show the actual distribution.

## 3. Residual market model

For each stock:

```text
r_i,t = alpha_i + beta_i * r_SPY,t + e_i,t
```

- 252-session rolling window;
- minimum 126 observations;
- beta/alpha/residual at formation use only data through the decision date;
- insufficient history -> factor unavailable, not filled.

Seven pre-registered residual factors:

1. `RESID_MOM_252` — residual cumulative return excluding last 21 sessions.
2. `RESID_REV_5`.
3. `RESID_REV_20`.
4. `IDIO_VOL_60`.
5. `DOWNSIDE_IDIO_60`.
6. `RESID_TREND_PERSIST_60`.
7. `BETA_ADJ_MOM_60`.

No prior P8.3 raw formula is relabeled as a new discovery.

## 4. Market regimes

Computed with only then-effective S&P members:

- SPY above/below MA200;
- SPY 20d/60d realized volatility;
- breadth = fraction above MA200 with ≥30 valid names;
- cross-sectional return dispersion;
- advance ratio;
- effective sample count; insufficient breadth => NaN/UNKNOWN.

No current index list backfills historical membership.

## 5. Statistical results

Unconditional tests: 7 × 3 horizons = 21.
Regime tests: 6 pre-registered interactions × 3 horizons × 2 regimes = 36.
Fama-MacBeth tests: 21.
Unified BH family: **78** hypotheses.

Unconditional top:

| Factor | H | Mean IC | HAC t | p | BH q |
|---|---:|---:|---:|---:|---:|
| RESID_REV_5 | 5 | +0.0149 | 2.21 | 0.027 | 0.301 |
| RESID_TREND_PERSIST_60 | 5 | -0.0145 | -2.40 | 0.016 | 0.319 |
| RESID_REV_20 | 5 | +0.0133 | 1.88 | 0.060 | 0.418 |

Fama-MacBeth found a negative `RESID_TREND_PERSIST_60` coefficient at H5
(t -3.71, BH q 0.016). The sign is negative, the unconditional IC is negative,
and it is not a positive long-only candidate. It is not selected after seeing
the result.

Conditional top:

```text
RESID_REV_5 in HIGH SPY vol, H5:
IC +0.0230, HAC t 2.33, BH q 0.308
```

No conditional test survives the 78-hypothesis BH family at q<=0.10.

## 6. Period robustness

2000-2007, 2008-2015, 2016-2024 are reported per factor/horizon. No factor has
the required combination of positive economic direction, BH significance,
stable sign, and acceptable label coverage.

## 7. Decision

```text
GO:            0
NO-GO:         7 residual factors / 21 unconditional tests
               36 regime tests / 21 Fama-MacBeth tests
DATA BLOCKED:  Nasdaq-100, Dow 30, historical fundamental PIT,
               event/macro PIT, 2025-2026 history
```

No factor qualifies for portfolio construction. No P8 shadow is launched.

## 8. Limitations

- 2000-2024 has been observed by earlier P8 work; these are exploratory and
  rolling historical tests, not pristine independent confirmation.
- Beta-window 126/504 sensitivity was not completed; only 252 is reported as
  primary. This is DATA_BLOCKED for the alternative windows, not silently
  claimed.
- No historical sector mapping; no sector attribution.
- No short/leverage/options; the long-only result cannot harvest a negative
  signal by shorting.

## 9. Files

```text
data/research/p8_4_market_neutral_alpha/
  p8_4_research_manifest.json
  eligibility_filter_audit.csv
  label_missingness_audit.csv
  label_missing_by_volatility.csv
  coverage_denominator_audit.json
  factor_definitions.json
  factor_ic_results.csv
  factor_fama_macbeth.csv
  factor_hac_results.csv
  factor_bh_results.csv
  factor_regime_results.csv
  factor_robustness.csv
  factor_correlation.csv
  p8_4_status.json
docs/research/p8_4_market_neutral_alpha.md
tests/test_p8_4_market_neutral.py
```
