# Qlib Linear Baseline 鈥?PIT 2-Year Panel

Date: 2026-10-28
Research only. No production changes.

## Environment

- Windows 11, AMD64
- Python 3.12.14
- Qlib **0.9.7** (`pyqlib-0.9.7-cp312-cp312-win_amd64.whl`)
- `import qlib` succeeds.
- Qlib was installed into the existing isolated _us_audit virtualenv.
- Full `pip install pyqlib` dependency resolution hung; the wheel was downloaded
  directly and minimal runtime dependencies were installed separately
  (`ruamel.yaml`, `pydantic-settings`, `python-dotenv`, `joblib`, `cloudpickle`,
  `python-redis-lock`, `redis`, `filelock`, `dill`, `fire`, `loguru`, `tqdm`,
  `pymongo`, `scikit-learn`, `threadpoolctl`, `narwhals`).
- No production environment or lockfile was changed.

## Data

Input: `research_factor_snapshots_sp500_pit_2y.csv`

- 211,903 rows after requiring all features and a mature 20-session label
- 498 tickers
- 441 technical dates
- 2024-12-10 to 2026-09-15 in the labeled sample
- Features are the 15 numeric technical factors; `Price` is not a feature
- Label: 20-session forward return computed per ticker
- Features are built from data up to `Technical_Date`; `Scan_Date` is later
- No random shuffle; strict time segments

Segments:

```text
train: 2024-12-09 .. 2025-06-30
valid: 2025-07-01 .. 2025-12-31
test:  2026-01-01 .. 2026-10-13
```

## Model

`qlib.contrib.model.linear.LinearModel(estimator="ridge", fit_intercept=True)`

- Median/ridge alpha selected only on validation from
  `{0.1, 1.0, 10.0, 100.0}`.
- Selected alpha: **0.1**.
- Model fit on train only; test is untouched.
- Predictions at month-end test dates are sorted into Q5/Q1.
- Long Q5, short Q1, equal weight within legs.
- 1%/99% winsorized forward returns.
- 5 bps one-way; turnover from month-to-month name changes.

## Test result

| Metric | Value |
|---|---:|
| Test rebalances | 9 |
| Gross monthly spread | +3.51% |
| Net monthly spread | +3.46% |
| Annualized net return | +50.3% |
| Annualized volatility | 16.4% |
| Sharpe | 3.06 |
| Max drawdown (monthly) | -2.75% |
| Positive months | 77.8% |
| Mean turnover | 55.2% |
| Mean names per month | 492 |
| Raw t-stat of mean spread | 2.18 |
| Equal-weight benchmark annual return | +5.9% |
| Equal-weight benchmark Sharpe | 0.43 |

## Why this is not a deployable alpha

- Only **9 non-overlapping test months**.
- The model was selected on a 6-month validation window with a very high
  Sharpe; selection uncertainty is large.
- The test monthly spread is volatile; the raw t-stat is 2.18, but a regression
  on the equal-weight benchmark over 9 months gives an alpha t-stat near **0.08**.
- The 10-year panel is current-universe and cannot be used for
  survivorship-free inference.
- No prospective holdout has matured.
- The result is a **research candidate/artifact**, not production evidence.

## Artifact

- Script: `tools/research/qlib_lowfreq_baseline.py`
- Test: `tests/test_qlib_lowfreq_baseline.py` (skips if Qlib is absent)
- Model output: generated JSON, not committed

## Decision

Qlib is now actually installed, imported, trained, and evaluated on a strict
time split. The result is not sufficient for production. No strategy change.
