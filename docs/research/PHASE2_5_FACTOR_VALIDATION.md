# Phase 2.5 Factor Validation

Date: 2026-10-30
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`
Not PIT. Not validated alpha. No production changes.

## 1. Phase 2.4 correction first

The prior Phase 2.4 maturity report showed 503 `MISSING_PRICE` per horizon.
That was a status bug in the vectorized maturity checker:

- last signal date 2026-10-28 has no next session;
- `forward_return.py` correctly calls this `NOT_MATURED`, not missing.

Fixed and regenerated:

| Horizon | MATURED | NOT_MATURED | MISSING_PRICE |
|---:|---:|---:|---:|
| 1D | 1,238,007 | 1,006 | 0 |
| 5D | 1,235,995 | 3,018 | 0 |
| 10D | 1,233,480 | 5,533 | 0 |
| 20D | 1,228,451 | 10,562 | 0 |
| 60D | 1,208,371 | 30,642 | 0 |

The 503 records were one last-session row per ticker, all historical-sequence
end, not mid-series delisting or ticker changes.

Full labels were actually generated, not inferred from maturity counts:

```text
data/research/forward_return_labels/labels_{1,5,10,20,60}d.parquet
```

## 2. Validation scope

- Factor panel: 1,239,013 rows, 503 tickers, 2016-09-19..2026-10-28.
- Validation period: 2018-01-01..2026-10-28.
- Daily cross-sectional IC, minimum 30 names.
- 20 factors 脳 5 horizons.
- 219,780 daily factor/horizon observations with both IC and Rank IC.

Methods:

- Pearson IC and Spearman Rank IC computed per signal date;
- Newey-West HAC standard errors on daily IC series;
- Benjamini-Hochberg FDR across 100 factor/horizon tests;
- Q1鈥換5 equal-weight future-return groups;
- annual and rolling 12-month stability;
- market environments from SPY 200D MA, 20D vol, 200D return.

## 3. FDR results

Only 6 of 100 tests have q < 0.05, all at 60D:

| Horizon | Factor | Mean Rank IC | Rank ICIR | Positive Rank IC | Q5鈭扱1 | q |
|---:|---|---:|---:|---:|---:|---:|
| 60 | ATR_Percent | +0.0627 | +0.260 | 58.6% | +5.46% | 0.00051 |
| 60 | Realized_Volatility_20D | +0.0542 | +0.248 | 59.3% | +4.73% | 0.00065 |
| 60 | Beta_60D | +0.0571 | +0.213 | 58.6% | +4.19% | 0.00509 |
| 60 | MA20 | -0.0343 | -0.253 | 36.7% | -2.91% | 0.00065 |
| 60 | MA50 | -0.0334 | -0.247 | 36.5% | -2.90% | 0.00065 |
| 60 | MA200 | -0.0361 | -0.271 | 35.8% | -3.16% | 0.00051 |

No 1D, 5D, 10D, or 20D factor survives FDR.

Interpretation: at 60D, high volatility/high beta ranks are associated with
higher future returns, while high price-to-MA is associated with lower future
returns. This is a cross-sectional statistical association, not a tradeable
strategy.

## 4. Annual stability

ATR_Percent 60D Rank IC:

| Year | Mean Rank IC | Dates |
|---|---:|---:|
| 2018 | -0.026 | 251 |
| 2019 | +0.015 | 252 |
| 2020 | +0.225 | 253 |
| 2021 | -0.021 | 252 |
| 2022 | +0.001 | 251 |
| 2023 | +0.122 | 250 |
| 2024 | +0.012 | 252 |
| 2025 | +0.144 | 250 |
| 2026* | +0.112 | 146 |

MA200 60D is negative most years but not all; its sign flips in 2019 and 2023.
ATR has strong 2020 and 2023鈥?026, but negative/weak 2018, 2021, 2022.

## 5. Rolling 12-month stability

| Factor (60D) | Positive rolling windows | Last | Min | Max |
|---|---:|---:|---:|---:|
| ATR_Percent | 71.5% | 0.107 | -0.115 | 0.254 |
| Realized_Volatility_20D | 71.8% | 0.086 | -0.117 | 0.226 |
| Beta_60D | 70.5% | 0.079 | -0.156 | 0.230 |
| MA200 | 30.5% | -0.057 | -0.171 | 0.074 |

The volatility factors have long positive stretches but also clear reversals.

## 6. Market environments (60D, Mean Rank IC)

| Factor | Bull | Bear | High vol | Low vol | Trend | Range |
|---|---:|---:|---:|---:|---:|---:|
| ATR_Percent | 0.037 | 0.164 | 0.186 | 0.027 | 0.034 | 0.110 |
| Realized_Volatility_20D | 0.028 | 0.164 | 0.186 | 0.018 | 0.025 | 0.102 |
| Beta_60D | 0.041 | 0.139 | 0.155 | 0.030 | 0.038 | 0.096 |
| MA200 | -0.028 | -0.070 | -0.056 | -0.033 | -0.031 | -0.048 |

ATR/RV/Beta are strongest in high-volatility and bear/range states. This is
consistent with a volatility-risk premium, but also means the result is
environment-dependent.

## 7. Q1鈥換5

Mean future 60D return by quintile (gross, overlapping):

| Factor | Q1 | Q2 | Q3 | Q4 | Q5 | Q5鈭扱1 |
|---|---:|---:|---:|---:|---:|---:|
| ATR_Percent | 1.92% | 2.19% | 2.88% | 3.65% | 7.37% | +5.46% |
| Realized_Volatility_20D | 2.08% | 2.32% | 2.96% | 3.84% | 6.81% | +4.73% |
| Beta_60D | 2.39% | 2.41% | 3.06% | 3.56% | 6.59% | +4.19% |
| MA200 | 5.56% | 3.55% | 3.26% | 3.05% | 2.40% | -3.16% |

Per-quintile means are in `stability.json`. These are gross, not net, and the
60D windows overlap. No transaction cost or slippage is applied in this table;
therefore no net strategy claim is made.

## 8. Classification

| Class | Factors |
|---|---|
| `WEAK_EXPLORATORY` | 60D ATR_Percent, Realized_Volatility_20D, Beta_60D; 60D MA20/MA50/MA200 |
| `REJECTED` | all 1D/5D/10D/20D factors; all other 60D factors |
| `CANDIDATE` | none |
| `VALIDATED_ALPHA` | none |

Reason no candidate:

- annual sign instability;
- high-vol/range dependence;
- no net-of-cost group portfolio;
- 60D overlapping labels;
- current-universe survivorship bias;
- no historical constituent/delisting correction.

## 9. Survivorship bias

All results are from the current 503 names. Missing delisted securities,
historical index membership, delisting returns, and dividend total return.
The page labels this `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`.

## 10. Artifacts

Local (not committed, large):

- `data/research/factor_validation/daily_ic.parquet` 鈥?219,780 rows
- `data/research/factor_validation/summary.csv` 鈥?100 factor/horizon rows
- `data/research/factor_validation/annual.csv`
- `data/research/factor_validation/stability.json`
- `data/research/forward_return_labels/labels_{1,5,10,20,60}d.parquet`

Code:

- `tools/research/factor_validation.py`
- `tools/research/factor_stability.py`
- `tools/research/full_forward_labels.py`
- `tests/test_factor_validation.py`

## 11. Remaining limits

- no cost-adjusted Q5鈭扱1 in this run;
- no historical universe;
- no delisted returns;
- no dividend total return;
- no Strategy Lab ranking integration;
- no `VALIDATED_ALPHA`.
