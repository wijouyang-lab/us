# P10.6 Backtest Design (conditional, not authorized)

This design is proposed only for the point at which the preflight blockers are
closed. It is not a current authorization.

## Universe and timing

- Point-in-time S&P 500 effective-dated members.
- No current-index survivorship.
- Signal at date t uses only filed facts available by the conservative
  `PIT_ACCEPTANCE_PROXY` trade date.
- Execute at the next executable session; never use same-bar close.
- Long-only, no leverage, no shorting, no options.
- Initial capital $50,000; MaxDD hard limit 15%.

## Models

- Value: P/B, P/S, earnings yield, FCF yield.
- Quality: ROE, ROA, CFO/assets, liabilities/assets.
- GARP: revenue/EPS/FCF growth, stability, margin expansion, operating leverage.

Each model gets the same universe, timing, cost model and rebalance rules.
No model-specific date cherry-picking.

## Costs

Separate ledger:

1. BUY commission
2. SELL commission
3. Regulatory fees
4. Slippage
5. Other documented fees

Slippage embedded in execution price must not be deducted again.

## Benchmarks

- SPY total return.
- Equal-weight eligible universe.
- Risk-matched passive benchmark.

## Metrics

CAGR, MaxDD, annualized volatility, Sharpe, Calmar, turnover, trading cost,
exposure, holding period, OOS return, benchmark excess return.

## Statistics

- Walk-forward with purge/embargo.
- HAC / Newey-West.
- BH multiple-testing correction.
- No repeated test-set tuning.
- Report failed and unstable windows, not only best results.

## Gate

A strategy can only be called a candidate if, after all costs:

- OOS return is positive;
- risk-matched benchmark advantage is reliable;
- HAC and BH support the result;
- MaxDD <= 15%;
- no material PIT or survivorship bias remains.

Otherwise the result is `NO-GO`, not `NO_ALPHA`.
