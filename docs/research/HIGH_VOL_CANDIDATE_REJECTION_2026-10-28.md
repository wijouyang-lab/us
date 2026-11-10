# High-Volatility Candidate: Verification and Rejection

Date: 2026-10-28
Research only. No production changes.

## Candidate

After the low-volatility directions were negative, the post-hoc reverse candidate
was: long high realized volatility / high ATR, short low, monthly rebalance,
20-session forward return, 1% winsorization, 5 bps one-way cost.

## 10-year current-universe check

Panel: `research_price_history_sp500_10y.csv`
1,233,984 rows, 503 tickers, 2016-09-19 to 2026-10-14
107 monthly rebalances, liquid universe (price >= $5, 20D dollar volume >= $5M)

| Candidate | Monthly net | NW t | Ann. Sharpe | Max DD |
|---|---:|---:|---:|---:|
| High Vol60 | +1.44% | 2.52 | 0.85 | -25.9% |
| High ATR_Pct | +1.47% | 2.74 | 0.88 | -24.0% |

This looks positive in isolation, but it is not market-neutral.

## Beta and alpha check

Regress the monthly long-short net return on the equal-weight universe return:

| Candidate | Beta | Monthly alpha | t(alpha) |
|---|---:|---:|---:|
| High Vol60 | 0.756 | +0.50% | 0.05 |
| High ATR_Pct | 0.746 | +0.54% | 0.06 |

The alpha is statistically indistinguishable from zero. Almost all of the
return is market beta.

Equal-weight universe benchmark over the same period: annualized mean 14.9%,
annualized volatility 17.9%, Sharpe about 0.83. The candidate's Sharpe (0.85-0.88)
is not materially better, with larger drawdown.

## Train/test

- 2016-2022: ATR net +0.97%/month, NW p = 0.168.
- 2023-2026: ATR net +2.18%/month, NW p = 0.010.
- But the 2023+ result still has beta about 0.75 and no alpha after the market
  regression.

## Decision

**Reject high-vol/ATR as an alpha candidate.** It is a high-beta volatility
exposure, not a market-neutral factor. No production change.
