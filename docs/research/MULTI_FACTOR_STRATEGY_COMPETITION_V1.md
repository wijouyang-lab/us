# Multi-Factor Strategy Competition V1

Date: 2026-11-25
Branch: `research/multi-factor-strategy-competition-v1`
Base: `research/invest-terminal-v1` (`9b07f588`)
Status: **DATA_LIMITED / NO_GO for price-only A**

## 1. Scope actually executed

Reused local 10Y PIT price snapshot (502 tickers, 2016-12-12..2026-10-13)
and current SEC fundamentals file (31 KB, 502 tickers). No PIT fundamental
history was available at usable coverage (`235/300` PIT identity points; A/B
anchors failed 90/80). No new data source was purchased.

Monthly rebalance every 21 trading days, 2020-01-31..2024-12-31, top 10 equal
weight, 5 bps one-way cost approximation, next-session monthly close execution.
No daily stop/exit simulation was run. This is a simplified competition, not a
full execution backtest.

## 2. Strategy definitions

### A — trend / momentum / volume

Score = z(Momentum_20D) + z(Momentum_60D) + z(Stock_RS_vs_SPY) +
z(Volume_Ratio_20D) + z(MA20_Slope_5D) − z(Realized_Vol_20D).

Top 10, monthly rebalance. Exit = next monthly rank replacement.
No daily stop; this is a limitation.

### B — quality / growth / value

Current fundamentals only: ROE, FCF margin, net margin. Growth and valuation
were not available with PIT timestamps in a usable panel. Score is constant
per ticker across the backtest, so B **contains look-ahead** and is not a valid
historical strategy.

### C — multi-dimensional

0.6 × A + 0.4 × B. Same look-ahead contamination from B.

## 3. Results (monthly, 2020-01..2024-12)

| Strategy | CAGR | Vol | Sharpe | MaxDD | Final NAV |
|---|---:|---:|---:|---:|---:|
| A trend/volume | 3.08% | 20.9% | 0.147 | **-42.25%** | 57,884 |
| B current quality* | 14.50% | 20.1% | 0.721 | -19.61% | 96,222 |
| C 60/40* | 12.21% | 24.0% | 0.509 | -35.99% | 87,245 |
| SPY | 12.83% | 21.2% | 0.605 | -34.10% | 91,083 |
| QQQ | 18.48% | 25.8% | 0.717 | -35.62% | 116,682 |
| BIL | 2.36% | 0.27% | 8.84 | -0.21% | 56,073 |

\* B/C use current fundamentals applied to history, so their results are not
valid OOS evidence.

A has poor return, worst drawdown, and the highest turnover (92% per month).
It fails the 15% risk target and does not beat SPY.

B's apparent Sharpe is attractive but is look-ahead contaminated. It cannot
be entered into PAPER-50000.

C inherits B's look-ahead and has a -36% drawdown. Not a candidate.

## 4. Final decision

```text
PRICE_ONLY_A = NO_GO
B = INVALID_FOR_HISTORICAL_DECISION (current fundamentals only)
C = INVALID_FOR_HISTORICAL_DECISION
OVERALL = DATA_LIMITED
PAPER_50000 = NOT_AUTHORIZED
```

No strategy qualifies for PAPER-50000. The only way to change this decision is
a usable PIT fundamental panel covering enough of the universe and dates; that
is outside the current free-data route (P17 free SEC identity = NO-GO).

## 5. Remaining gaps

- No PIT quality/growth/value panel.
- No full daily stop/exit comparison.
- No historical universe beyond the 502-ticker snapshot.
- No delisting returns or total-return prices.
- No trade ledger with actual fills/costs.

## 6. Files

- `tools/research/mf_strategy_competition.py`
- `tests/test_mf_strategy_competition.py`
- `data/research/mf_v1/strategy_comparison.csv`
- `nav_A.csv`, `nav_B.csv`, `nav_C.csv`
- `summary.json`
- `docs/research/MULTI_FACTOR_STRATEGY_COMPARISON_V1.csv`
- `docs/research/MULTI_FACTOR_FEATURE_CATALOG_V1.csv`
- `docs/research/MULTI_FACTOR_EXIT_COMPARISON_V1.csv`
- `docs/research/MULTI_FACTOR_TRADE_LEDGER_V1.csv`
