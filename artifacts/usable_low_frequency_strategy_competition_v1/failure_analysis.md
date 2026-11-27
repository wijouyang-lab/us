# Failure Analysis — Corrected

## SPY_TREND

The original 18.3% CAGR / -8.3% DD / Sharpe 1.82 was produced with same-month
look-ahead: the month-end position earned that month's return. After shifting
positions one month:

- Full CAGR: 8.23%
- Full MaxDD: -23.43%
- Full standard Sharpe: 0.78
- OOS CAGR: 9.40%
- 20 bps full CAGR: 8.05%

This is below SPY's 10.59% full CAGR and above the 15% drawdown target.
It fails.

## Route A

- A_MOM_QUAL OOS 49.3% but full MaxDD -52.2%.
- Quality filter uses current static classification, a look-ahead input.
- Static universe -> survivorship bias.
- Parameter instability: topN 10/20/30 changes full CAGR from 32.5% to 23.2%.
- Fails drawdown, PIT, survivorship.

## Route B

- Full CAGR 15.2%, MaxDD -45.0%, turnover ~14.9x.
- Static industry classification; no PIT.
- Fails drawdown and data quality.

## Route C

- No historical filing-date fundamentals.
- Cannot be evaluated; no synthetic EPS/PEG was created.

## Remaining blocker

No delisted/PIT universe and no PIT fundamentals. All stock-selection results
remain exploratory; no strategy is validated.
