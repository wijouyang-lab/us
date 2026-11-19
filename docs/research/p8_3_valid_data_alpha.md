# P8.3 Valid-Data Alpha Research

Date: 2026-11-09
Status: **P8_3_NO_GO**

This round uses only data that exists in the repository and is available at the
formation date. P8/P8.1/P8.2/P8.2.1/P8.2.2 artifacts are preserved.

## 1. Valid research panel

Inputs:

- effective-dated S&P 500 membership;
- `finsaber_prices_raw.csv`, 2000-01-03..2024-12-31;
- raw OHLCV;
- no current 2025-2026 data mixed with history.

Formation-time eligibility:

```text
positive OHLC and finite volume
volume > 0
no >5x one-day adjusted-close shock in prior 60 sessions
```

No post-hoc P8.2.2 `VERIFIED_*` classification is used as a historical signal
filter. Forward labels are handled separately and never fed into signal
eligibility.

Panel outputs:

```text
valid_research_universe.csv
valid_research_panel.parquet
valid_data_coverage_by_year.csv
valid_data_coverage_by_ticker.csv
valid_data_coverage_by_sector.csv   -> DATA_BLOCKED
valid_forward_label_coverage.csv
valid_data_research_manifest.json
```

Actual panel:

```text
sample rows: 352,036
valid member-day coverage in sampled dates: 89.21%
forward-label coverage among sampled rows: 91.13%
forward-label coverage among valid names: 99.88%
```

Annual valid coverage starts around 79-80% in 2000-2003 and rises above 95% in
2016+. This is not changed or smoothed.

Sector coverage is **DATA_BLOCKED**: no reliable historical sector mapping is
available in the PIT panel.

## 2. Candidate formulas

33 formulas registered before looking at results:

- risk-adjusted momentum (5/20/60/120, upside/downside, acceleration);
- volatility structure (short/long, change, vol-of-vol, downside, drawdown);
- price efficiency/range/breakout/gap;
- volume surprise/trend/price-volume correlation;
- interactions (volume × price impact, trend × volume, reversal × downside).

Full definitions:

```text
factor_definitions.json
candidate_factor_registry.csv
```

No formula was selected or dropped based on its P8.3 result.

## 3. Factor IC and quintiles

For each factor:

- 5/10/20-day forward labels;
- non-overlapping sample dates for each horizon (step = horizon);
- rank IC, mean, std, ICIR;
- top/bottom quintile, top-minus-bottom;
- Newey-West HAC;
- BH across all 99 factor-horizon hypotheses.

Best raw IC values were small:

| Factor | Horizon | Mean IC | HAC t | p | BH q |
|---|---:|---:|---:|---:|---:|
| REVERSAL_DOWNSIDE_5 | 5 | +0.0173 | 2.07 | 0.038 | 0.943 |
| EFF_VOLUME | 10 | +0.0124 | 2.22 | 0.026 | 1.000 |
| UP_VOLUME_RATIO_20 | 20 | +0.0127 | 1.14 | 0.256 | 1.000 |
| VOLUME_Z_20 | 10 | +0.0108 | 1.80 | 0.072 | 1.000 |

All 99 BH q values are far above 0.10. No factor survives multiple testing.
The raw p-values are not independent findings; they are 1 of 99 attempts.

Files:

```text
factor_ic_results.csv
factor_quantile_results.csv
factor_hac_results.csv
factor_bh_results.csv
factor_robustness.csv
factor_coverage.csv
factor_ic_timeseries.csv
factor_correlation.csv
```

## 4. Period stability

Only 14 of 99 factor-horizon pairs have the same IC sign across the three
pre-declared periods (2000-2007, 2008-2015, 2016-2024). The best raw IC factors
are not sign-stable.

No factor has both:
- BH significance at 0.10;
- positive top-minus-bottom;
- stable sign across periods.

Therefore `strategy_candidates.csv` is an empty registry with headers, not a
silently deleted file.

## 5. Decision

```text
GO:            0
NO-GO:         33 formulas / 99 factor-horizon tests
DATA BLOCKED:  Nasdaq-100, Dow 30, historical fundamental PIT,
               event/macro PIT, 2025-2026 history
```

No factor qualifies for portfolio construction. No `RESEARCH_SHADOW_P8` is
launched. P7 remains independent.

## 6. Limitations

- Only S&P 500 effective membership is PIT-available.
- Historical fundamental PIT is absent; P7.1 current Value is not a historical
  backtest.
- Event/macro data is not validated to the required timestamp standard.
- The 2025-2026 panel is separate and not concatenated.
- The factor screen is a research screen, not a claim of Alpha.
