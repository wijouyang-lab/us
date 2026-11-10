# Qlib Execution + OpenBB Provider Block

Date: 2026-10-28
Research only. No production changes.

## Qlib: actual execution

- Qlib **0.9.7** wheel: `pyqlib-0.9.7-cp312-cp312-win_amd64.whl`
- `import qlib` returns version `0.9.7`.
- Python 3.12.14, Windows AMD64.
- Full `pip install pyqlib` hung resolving the large optional dependency set.
  The wheel itself downloaded normally; minimal runtime dependencies were
  installed independently and `import qlib` then succeeded.
- The research machine's dependency set is isolated in `_us_audit/venv`; no
  project requirements or production environment were changed.

### Data and split

Input: `research_factor_snapshots_sp500_pit_2y.csv`

- 211,903 labeled rows
- 498 tickers
- 441 technical dates
- 2024-12-10 to 2026-09-15 in the labeled sample
- 15 features; `Price` is not a feature
- 20-session forward label per ticker
- Features use data up to `Technical_Date`; no random shuffle

```text
train: 2024-12-09 .. 2025-06-30
valid: 2025-07-01 .. 2025-12-31
test:  2026-01-01 .. 2026-10-13
```

### Model

`qlib.contrib.model.linear.LinearModel(estimator="ridge", fit_intercept=True)`

- Alpha selected only on validation: 0.1
- Test untouched during selection
- Month-end Q5/Q1, long Q5 / short Q1
- 1%/99% winsorized forward returns
- 5 bps one-way; turnover from name changes

### Test result

| Metric | Value |
|---|---:|
| Rebalances | 9 |
| Gross monthly | +3.51% |
| Net monthly | +3.46% |
| Annualized net | +50.3% |
| Annualized vol | 16.4% |
| Sharpe | 3.06 |
| Max drawdown | -2.75% |
| Positive months | 77.8% |
| Turnover | 55.2% |
| Raw t-stat | 2.18 |
| Equal-weight benchmark annual | +5.9% |

### Interpretation

This is a **research result, not a deployable alpha**:

- only 9 non-overlapping test months;
- validation selected a high-Sharpe model from a 6-month window;
- regressing the test spread on the equal-weight benchmark gives an alpha
  t-stat near **0.08**;
- the 10-year file is current-universe and survivorship-biased;
- no prospective holdout has matured.

## OpenBB: provider block

OpenBB's PyPI `openbb==5.0.0` wheel is a 3.8 KB meta-package that requires a
large set of provider packages (`openbb-core`, `openbb-yfinance`, `openbb-fmp`,
`openbb-polygon`, `openbb-tiingo`, `openbb-sec`, ...). It was not installed in
this research environment.

There are no provider API keys in this environment. `yfinance` is the same
Yahoo source already used; it is not an independent multi-source check. No
OpenBB network request was made.

**OpenBB multi-source verification remains blocked** by:

1. no installed provider stack;
2. no free independent provider credentials;
3. no delisted-history entitlement.

No provider response or delisted coverage improvement is claimed.
