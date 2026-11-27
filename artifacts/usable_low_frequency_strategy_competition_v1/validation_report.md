# Validation Notes — Strategy Competition V1

Date: 2026-11-27

## What is validated

- Monthly prices: 987 symbols, 2007-2024; adjusted close; 166,320 month-end rows.
- Backtest returns are generated from the monthly panel; signals use only data up to
  the rebalance month and returns start the following month.
- Costs are applied to turnover at 5/10/20 bps.
- Periods are chronological: train 2008-2016, validation 2017-2019, OOS 2020-2024.
- Max weight 5%; max 4 names per industry.
- Benchmarks: SPY, QQQ, SPY 10m trend, simple 12-1 momentum.
- $50,000 initial capital.

## What is NOT validated

- **Survivorship:** static 987-symbol list; delisted names not verified.
- **PIT fundamentals:** current quality/industry used in quality/industry variants.
- **Route C:** no historical filing-date panel; not run.
- **Ticker changes:** not verified.
- **Parameter stability:** only topN and market filter tested for Route A; SPY
  trend 8/10/12-month variants not fully tested.
- No intraday execution, borrow, taxes, or market impact.
- No claim of proven alpha or profitability.

## Interpretation

All stock-selection results are exploratory. SPY_TREND is a benchmark fallback
that meets the 15% drawdown target; it is not a stock-selection strategy and is
not PAPER-50000 authorized.

## Reproduction

```bash
python tools/research/strategy_competition/backtest.py
```

Reads `data/research/strategy_competition/*`; writes `artifacts/usable_low_frequency_strategy_competition_v1/`.
