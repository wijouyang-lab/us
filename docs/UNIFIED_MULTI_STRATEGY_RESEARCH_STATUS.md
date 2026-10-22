# Unified Multi-Strategy Research Status

**Status date:** 2026-10-22  
**Scope:** research only. No production scoring, scan, stops, portfolio, or ledger changes.

## Latest 2Y PIT comparison

Source: GitHub Actions [run 39712068759](https://github.com/wijouyang-lab/us/actions/runs/39712068759), both comparison jobs completed successfully. The dynamic 10Y artifact-resolution change then passed in [workflow run 39712479021](https://github.com/wijouyang-lab/us/actions/runs/39712479021), and its corresponding [Test run 39712479045](https://github.com/wijouyang-lab/us/actions/runs/39712479045) also succeeded. A separate 10Y point-in-time rebuild has now been launched in the temporary research branch via [run 39712671160](https://github.com/wijouyang-lab/us/actions/runs/39712671160); its generated data and downstream comparison have not yet completed review.

- 212,869 rows, 498 tickers, 443 valid signal dates (2024-12-09 through 2026-09-16).
- Signal direction was chosen on the training segment and then frozen for validation/test.
- Reported test returns are 20-session returns, with an estimated turnover-based cost of 10 bps per side.
- The test segment contains only **4 non-overlapping observations**. Per the framework's own guardrail, all four results are **insufficient evidence**; the apparent returns and Sharpe ratios must not be treated as reliable estimates.

| Strategy | Frozen direction | Test net return / 20 sessions | Net excess vs. equal-weight panel | Test observations | Assessment |
|---|---|---:|---:|---:|---|
| ATR volatility | HIGH | +1.671% | +1.524% | 4 | Insufficient evidence |
| Mean reversion (Z-score) | LOW | +0.289% | +0.141% | 4 | Insufficient evidence |
| 20D momentum | HIGH | -0.485% | -0.633% | 4 | Insufficient evidence |
| MA-slope reversal | HIGH | +0.272% | +0.124% | 4 | Insufficient evidence |

Cost sensitivity on the same four observations:

| Strategy | 5 bps/side | 10 bps/side | 20 bps/side |
|---|---:|---:|---:|
| ATR volatility | +1.699% | +1.671% | +1.616% |
| Mean reversion (Z-score) | +0.363% | +0.289% | +0.140% |
| 20D momentum | -0.416% | -0.485% | -0.624% |
| MA-slope reversal | +0.342% | +0.272% | +0.131% |

## 10Y reference comparison — historical input, not decision-grade

The earlier [comparison run 39712068759](https://github.com/wijouyang-lab/us/actions/runs/39712068759) used the 10Y artifact from workflow run `39599854065`, created at commit `1ec710b97ede10fbc9f5ae9298aaea213b954117`. That artifact predates a later research fix. The figures below preserve the old reference results only; **do not use them to select a strategy**.

- 1,038,059 rows, 498 tickers, 2,453 signal dates (2016-12-12 through 2026-09-16).
- 24 non-overlapping test observations.

| Strategy | Frozen direction | Test net return / 20 sessions | Net excess vs. equal-weight panel | Test observations |
|---|---|---:|---:|---:|
| ATR volatility | HIGH | +2.190% | +1.480% | 24 |
| Mean reversion (Z-score) | LOW | +0.229% | -0.480% | 24 |
| 20D momentum | LOW | +0.501% | -0.209% | 24 |
| MA-slope reversal | LOW | +0.458% | -0.252% | 24 |

The workflow has been hardened to resolve the latest successful 10Y snapshot run dynamically and include its run ID, source commit, and creation time in the comparison artifact. **This does not refresh the dataset**: the newest available artifact can still be stale. A new successful run of `research-snapshots-sp500-pit-10y-once.yml` is still required before the 10Y results can be considered current.

## Interpretation and next gate

1. The 2Y test is too small to support a strategy ranking: four observations are not enough, regardless of a positive mean or Sharpe.
2. The historical 10Y reference is stale until a new run of the 10Y point-in-time pipeline succeeds and its generated artifacts are inspected.
3. The strategy directions above are selected on training data, but this panel has already been used for exploratory research; this is not a blind final holdout.
4. S&P 500 membership history is not fully point-in-time and OHLC/corporate-action limitations remain. Costs are estimates, not fill-level slippage.
5. Do not promote any of these strategies into production. Next validation gate: refresh 10Y PIT data, rerun all four strategies, then require sufficient untouched test observations plus robustness to costs and regime splits.
