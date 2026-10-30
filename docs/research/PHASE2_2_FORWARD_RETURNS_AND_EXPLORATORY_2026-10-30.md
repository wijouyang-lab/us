# Phase 2.2 Forward Returns and Exploratory Technical Research

Date: 2026-10-30
Research only. Label for all strategy results:
`EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`

## 1. Why 20D was zero

Actual snapshot dates:

```text
2026-10-07 .. 2026-10-29 (17 sessions)
```

Price panel last date:

```text
2026-10-28
```

The 2026-10-29 snapshot cannot have an entry price; the price panel ends one
day earlier.

Forward-return build with signal close -> next open entry -> open exit H
sessions later:

| Horizon | MATURED | NOT_MATURED | MISSING_PRICE |
|---:|---:|---:|---:|
| 1D | 4,236 | 588 | 1 |
| 5D | 3,079 | 1,745 | 1 |
| 10D | 1,913 | 2,911 | 1 |
| 20D | **0** | **4,824** | 1 |
| 60D | **0** | **4,824** | 1 |

Cause:

1. signals only started 2026-10-07;
2. 20 trading sessions after entry are not yet available;
3. 2026-10-29 has no next-session open;
4. one ticker/date is missing from the price panel.

There is no date-alignment or ticker-matching bug. 20D will become available
only after enough future sessions exist. The first 20D label cannot mature
before roughly early November 2026; the exact date must be derived from the
actual trading calendar, not assumed.

## 2. Standard forward-return module

`tools/research/forward_return.py`

- horizons: 1, 5, 10, 20, 60;
- entry = next session open after signal;
- exit = open after H additional sessions;
- statuses: `MATURED`, `NOT_MATURED`, `MISSING_PRICE`;
- records dates/prices/return/source/status/reason;
- never fills missing prices, never uses natural days.

Actual output:

`docs/research/forward_returns_phase22_2026-10-30.csv`

Tests: 5 passed, covering normal, not matured, missing ticker/signal,
non-trading signal, invalid price.

## 3. Exploratory 5D/10D factor IC

Only MATURED labels; no factor IC equals strategy Sharpe.

| Factor | 5D mean rank IC | 5D dates | 10D mean rank IC | 10D dates |
|---|---:|---:|---:|---:|
| Momentum_5D | +0.303 | 11 | +0.211 | 7 |
| Momentum_20D | +0.037 | 11 | -0.036 | 7 |
| RSI_14 | +0.167 | 11 | +0.071 | 7 |
| Bias_Pct | +0.205 | 11 | +0.086 | 7 |
| ATR_Pct | -0.261 | 11 | -0.307 | 7 |
| MA20_Slope_5D | -0.072 | 11 | -0.112 | 7 |
| Realized_Vol_20D | -0.253 | 11 | -0.308 | 7 |
| Quant_Score | +0.179 | 11 | +0.077 | 7 |

Sample is only 11 dates (5D) and 7 dates (10D), ~419 names per date. This is
research-direction evidence only, not a strategy validation.

## 4. Ten-year exploratory technical backtest

7 strategies + equal-weight and SPY; 104 monthly cohorts, 2018-01-31..2026-10-28,
top quintile, 20-session hold, 10 bps net.

| Strategy | Net CAGR | Excess vs EW | Turnover |
|---|---:|---:|---:|
| Momentum20 | 15.01% | +3.89% | 0.78 |
| Momentum60 | 13.09% | +1.70% | 0.48 |
| Trend | 14.75% | +3.05% | 0.44 |
| RSI | 7.34% | -2.75% | 0.80 |
| Mean reversion | 8.45% | -1.13% | 0.78 |
| Low volatility | 5.17% | -6.19% | 0.55 |
| ATR | 5.08% | -6.45% | 0.43 |
| Equal weight | 11.52% | 鈥?| 鈥?|
| SPY buyhold | 10.24% | 鈥?| 鈥?|

Gross max drawdowns: Momentum20 -22.0%, Trend -19.6%, LowVol -16.3%,
MeanReversion -34.5%, RSI -25.8%, ATR -16.1%.

### Time split

| Strategy | 2018鈥?021 net CAGR | 2018鈥?021 excess vs EW | 2022鈥?026 net CAGR | 2022鈥?026 excess vs EW |
|---|---:|---:|---:|---:|
| Momentum20 | 13.00% | **-1.52%** | 16.76% | +8.76% |
| Momentum60 | 14.91% | -0.22% | 11.55% | +3.37% |
| Trend | 14.45% | -0.74% | 14.99% | +6.41% |
| RSI | 17.02% | **+2.90%** | -0.32% | -7.35% |
| Mean reversion | 11.28% | -1.04% | 6.09% | -1.21% |
| Low volatility | 9.96% | -5.31% | 1.21% | -6.94% |
| ATR | 9.64% | -5.79% | 1.30% | -7.01% |

Momentum/trend only outperform in the later period; RSI only in the earlier
period. No strategy has stable excess across both.

## 5. Decision

- No formal strategy passes.
- 20D remains unavailable; no 20D Sharpe is claimed.
- Momentum20 and Trend are research candidates for the next rolling test, not
  deployable.
- Low-vol, ATR, RSI, mean reversion fail the stability check.
- All results remain survivorship-biased, current-universe, non-PIT.

## 6. Data quality actions

- HUBB 2021-05-05 is the only invalid OHLC row; exclude that row/date from
  research rather than overwrite raw data.
- 2,305 zero-volume rows should be excluded by the existing liquidity filter.
- 12 >50% moves require event review; not automatically deleted.
- Raw `price10y_1028.csv` must not be overwritten.

## 7. Artifacts

- `tools/research/forward_return.py`
- `tests/test_forward_return.py`
- `tools/research/exploratory_factor_ic.py`
- `tools/research/technical_strategy_backtest.py`
- `docs/research/forward_returns_phase22_2026-10-30.csv`
- `docs/research/exploratory_factor_ic_phase22_2026-10-30.json`
- `docs/research/technical_strategies_phase22_2026-10-30.json`
- `docs/research/technical_strategies_2018_2021_2026-10-30.json`
- `docs/research/technical_strategies_2022_2026_2026-10-30.json`
