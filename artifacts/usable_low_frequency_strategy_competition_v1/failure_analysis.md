# Failure Analysis

## Route A — Momentum + quality

- OOS 2020-2024 looks strong (A_MOM_QUAL +49.3% CAGR, Sharpe 1.60).
- Full 2008-2024 max drawdown is **-52.2%**, far above the 15% target.
- At 20 bps, full CAGR 25.6%; costs are not the main problem.
- Quality filter uses current static `quality_pct`, a look-ahead input.
- 987-symbol static universe -> survivorship bias.
- Parameter instability: topN 10/20/30 changes full CAGR from 32.5% to 23.2%; market filter still leaves DD ~26.5%.
- **Fail: drawdown, PIT, survivorship, parameter stability.**

## Route B — Industry first

- Full CAGR 15.2%, Sharpe 0.76, max DD **-45.0%**.
- Annual turnover ~14.9x; 20 bps costs reduce full CAGR to 13.5%.
- Industry classification is current static; historical industry membership not PIT.
- Top-3 industry concentration raises timing risk; 27 switches? 203 rebalance months.
- **Fail: drawdown, turnover, PIT, survivorship.**

## Route C — Fundamental improvement + price

- **NOT HISTORICALLY EVALUABLE.**
- Repository has no historical filing-date fundamental panel.
- Using current `quality_pct` would leak future data.
- No synthetic/estimated EPS or PEG was created.
- **Fail: no PIT data. Not a strategy failure; a data failure.**

## Benchmark fallback — SPY 10-month trend

- Full CAGR 18.3%, Sharpe 1.82, max DD **-8.3%**, 27 switches.
- At 20 bps full CAGR 18.1%.
- Beats SPY and QQQ risk-adjusted; no single-stock dependence.
- **But it is not stock selection and proves no alpha.**
- Parameter stability across 8/10/12 months was not fully tested in this PR.

## Single most important blocker

**No delisted/PIT universe and no PIT fundamentals.** Until those are acquired,
A/B cannot be labeled historically validated.
