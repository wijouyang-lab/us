# Restricted 466-Ticker Five-Factor Validation

Date: 2026-10-28
CURRENT-UNIVERSE EXPLORATORY 鈥?SURVIVORSHIP-BIASED
NOT A FULL PIT RESULT
NOT DEPLOYABLE ALPHA

## Scope

- 466 fully-priced current-universe tickers
- 2016-09-19 to 2026-10-14
- 2,532 sessions
- 1,179,912 panel rows
- Yahoo-derived existing price panel
- 37 incomplete tickers excluded

This is not a new factor search. Five fixed directions, one 20-session horizon,
one monthly rebalance, one 5 bps cost model, one chronological split.

## Method

- Monthly (20-session) rebalance at month end
- Q5 long / Q1 short, equal weight
- 1%/99% winsorization of the forward return
- 20-session forward return
- Liquidity filter: price >= $5, 20-day dollar volume >= $5M
- One-way name turnover; 5 bps per one-way turnover
- Train: through 2022-12-31
- Test: 2023-01-01 onward
- BH correction across exactly five test hypotheses

No parameter is selected from the test period.

## Test results (2023鈥?026)

| Factor | Direction | Net monthly | Annualized | Sharpe | p | BH q |
|---|---|---:|---:|---:|---:|---:|
| Vol60 | low volatility | -1.73% | -20.4% | -1.06 | 0.044 | 0.128 |
| ATR_Pct | low ATR | -1.61% | -19.1% | -1.04 | 0.051 | 0.128 |
| Mom12_1 | high 12-1 momentum | +0.72% | +7.4% | 0.44 | 0.334 | 0.334 |
| Mom1 | low 1-month reversal | -1.00% | -12.2% | -0.89 | 0.099 | 0.164 |
| MA50 | high trend | +0.58% | +6.3% | 0.46 | 0.328 | 0.334 |

**No positive factor reaches BH q < 0.05.**

The low-vol directions are significantly negative at raw p, but still fail BH.
That is evidence against the fixed low-vol direction, not alpha.

## Full-sample and train results

The CSV/JSON contain all three samples (all, train, test). Summary:

- All-sample: low-vol directions negative; momentum/trend near zero.
- Train 2016鈥?022: no consistent positive factor.
- Test 2023鈥?026: only weak positive momentum/trend, not significant.

No factor is consistently positive across train and test.

## Costs and turnover

- Mean turnover: roughly 22%鈥?8% depending on factor.
- Mean eligible names: 463.
- Mean long/short: about 93/92.
- 5 bps one-way; cost is not the main differentiator.
- At 10/20 bps the already-negative low-vol factors get worse; positive weak
  factors lose more.

## Benchmark

Equal-weight eligible universe on the same dates:

| Metric | Value |
|---|---:|
| Rebalances | 119 |
| Mean monthly | 1.24% |
| Annualized | 14.31% |
| Annualized vol | 16.73% |
| Sharpe | 0.86 |
| Max drawdown | -21.60% |

The long-short factors do not deliver a benchmark-relative edge. The
current-universe equal-weight benchmark itself is survivorship-biased; it is
not a PIT benchmark.

## Failure interpretation

- Low-volatility direction is negative, not positive.
- Momentum/trend are weak and insignificant.
- Short-term reversal fails out of sample.
- No candidate survives multiple-testing correction.
- Reversing low-vol after seeing the result would be post-hoc and is not counted.

## Files

- Script: `tools/research/restricted_466_factor_validation.py`
- Tests: `tests/test_restricted_466_factor_validation.py`
- Results: `docs/research/restricted_466_factor_validation_2026-10-28.{csv,json}`
- Universe manifest: `docs/research/restricted_universe_full_coverage_2026-10-28.csv`

## Conclusion

The fixed five-factor family does not provide validated OOS alpha in the
restricted current-universe sample. This is exploratory, survivorship-biased
evidence, not a full PIT result.

Do not promote any factor to production.

## Event/news variables: not included

The existing event pipeline can audit caller-supplied timestamps and first-seen
capture metadata, but it cannot manufacture historical point-in-time
availability. Backfilled SEC filings/RSS items do not acquire a historical
first-seen time, and historical consensus/label snapshots are not verified.

Therefore no news, earnings, macro, or corporate-event feature is included in
this experiment. Adding one would be a look-ahead risk, not a new predictor.
This is a documented blocker, not a null result.
