# Fixed Five-Factor Low-Frequency Validation (Research Only)

Date: 2026-10-28
Script: `tools/research/focused_lowfreq_validation.py`
Snapshot: `research_factor_snapshots_sp500_pit_2y.csv`

## Scope

This is a fixed, five-factor historical check, not a search and not a production
signal. The factors and directions were fixed in the script; no production
scanner, ledger, or trading module is imported.

## Data and method

- 222,388 snapshot rows
- 502 tickers
- 462 technical sessions
- 2024-12-09 to 2026-10-13
- Forward 20-session return from the snapshot `Price`
- Every 20th session rebalance (phase 0)
- Cross-sectional quintiles; long Q5 / short Q1
- 1%/99% winsorized forward return
- 1.0% round-trip cost assumption (5 bps one way, full turnover, two legs)
- 23 non-overlapping monthly observations
- Benjamini-Hochberg correction across the five fixed tests

## Results

| Factor | Fixed direction | Net Q5-Q1 | Positive months | t | p | BH q |
|---|---|---:|---:|---:|---:|---:|
| ATR_Pct | low volatility | -2.68% | 30.4% | -2.06 | 0.052 | 0.129 |
| Realized_Volatility_20D_Pct | low volatility | -2.56% | 34.8% | -2.26 | 0.034 | 0.129 |
| Momentum_60D_Pct | high momentum | -0.54% | 50.0% | -0.38 | 0.706 | 0.842 |
| RSI | low RSI (reversal) | +0.22% | 43.5% | 0.37 | 0.712 | 0.842 |
| Volume_Ratio_20D | high relative volume | -0.18% | 47.8% | -0.20 | 0.842 | 0.842 |

**No factor reaches BH q < 0.05.**

The low-volatility directions are negative. Reversing them to high-volatility
after observing the data would produce a positive raw result, but that is a
post-hoc direction change, not a pre-registered finding; it is not counted as
alpha.

## Limitations

- Only 23 non-overlapping monthly observations; low statistical power.
- Two-year sample only; no complete 10-year PIT panel.
- The 10-year PIT audit was blocked at 91.61% member-session coverage, with 98
  missing tickers; delisted names cannot be deleted without survivorship bias.
- No prospective/future holdout is mature yet.
- Costs are a fixed conservative approximation, not a full execution model.

## Decision

Research status remains **no validated deployable alpha**. Production scanning
and trading logic are unchanged. The next valid confirmation must use a
pre-registered future sample after the registration date, or a materially more
complete PIT universe.
