# Usable Low-Frequency Strategy Competition V1

Date: 2026-11-27. Research only. **No PAPER-50000, no IBKR, no orders.**

## Final answer

**No complex route passes the validation bar.** The only rule that meets the 15% drawdown target with positive OOS and cost-robust returns is **SPY 10-month trend** — a benchmark/fallback, not a stock-selection strategy.

| Candidate | OOS CAGR | OOS Sharpe | Full MaxDD | Verdict |
|---|---:|---:|---:|---|
| A_MOM_QUAL | 49.3% | 1.60 | **-52.2%** | Fails 15% DD |
| A_MOM_QUAL_IND | 44.8% | 1.52 | **-53.0%** | Fails 15% DD |
| B_IND_ROT | 25.5% | 0.99 | **-45.0%** | Fails 15% DD |
| SPY_TREND | **22.2%** | **1.85** | **-8.3%** | Meets DD, but simple benchmark |
| SPY | 14.5% | 0.80 | -23.9% | Benchmark |
| QQQ | 19.9% | 0.93 | -32.6% | Benchmark |

**Champion for next-stage paper review: SPY 10-month trend**, with the explicit
caveat that it does **not** prove stock-selection alpha.

## Data verdict

- 987 symbols, 2007-01-03 to 2024-12-31; 3,479,190 daily rows; 166,320 monthly rows.
- 710 names at 2024-12; static symbol set.
- **Delisted names not verified -> survivorship bias likely.**
- Splits/dividends: adjusted close available.
- Ticker/name changes: not verified.
- **No PIT fundamentals.** Quality/industry filters use current static classifications; those variants are look-ahead biased.
- Route C cannot be historically tested; no result is reported.
- No paid data purchased.

## Three routes

- **A:** 12-1 momentum + 52-week high + 6m return + liquidity; variants with static quality and industry.
- **B:** top 3 industries by median 6m return, then stock strength; 20 names.
- **C:** fundamental improvement + price confirmation; **NOT EVALUABLE** without PIT filing data.

## Costs

5 / 10 / 20 bps one-way. At 20 bps:

- A_MOM_QUAL full CAGR 25.6%; OOS 48.2%.
- A_MOM_QUAL_IND full 22.2%; OOS 43.6%.
- B_IND_ROT full 13.5%; OOS 23.8%.
- SPY_TREND full 18.1%; OOS 22.0%.

Trading costs do not rescue the drawdown failure.

## Risk

- A/B drawdowns exceed 15% over the full period, even with 20 bps costs.
- Market filter reduces A_MOM_QUAL_IND full DD to ~26.5% (20 names), still fails.
- A has ~8x annual turnover; B ~15x. SPY_TREND ~1.5x and 27 switches.
- Max 5% per name, max 4 per industry.
- Parameter stability: A topN 10/20/30 changes CAGR 32.5%→23.2%; with filter 27.1%→20.4%. Not stable enough.
- No single-stock dependence for SPY_TREND; A/B were not fully attribution-tested.

## Why Route C is absent

No historical filing-date fundamentals. Current `quality_pct` cannot be used as if
it were known in 2012. Building Route C from current data would be look-ahead.
It remains **DATA_UNAVAILABLE**, not a failed strategy.

## Execution for the fallback

- Monthly check of SPY vs its 10-month moving average (daily scan can update).
- If SPY above: hold SPY; if below: cash/BIL.
- $50,000, one ETF, no leverage, no shorts.
- Cost assumption 10 bps per switch; 27 switches over 17 years.
- Max DD historically 8.3%; target 15% satisfied.
- This is a **risk-managed beta** strategy; it does not justify claiming alpha.

## Files

- `strategy_results.csv` — 8 strategies × 4 periods × 3 cost levels.
- `equity_curves.csv` — monthly $50k curves.
- `parameter_stability.csv` — A topN and market filter.
- `data_audit.csv`.
- `latest_scan_example.csv` — latest A signal.
- `route_rules_and_data_audit.md`.
- `failure_analysis.md`.
- `validation_report.md`.

## Final gate

**No stock-selection strategy is validated.**  
**No strategy enters PAPER-50000 in this PR.**  
The only candidate for a small forward paper test is **SPY_TREND**, and only as
risk-managed beta, not as proof of a superior stock strategy.

**The single most important blocker: no delisted/PIT universe and no PIT
fundamentals.** Until those are obtained, A/B results remain exploratory.
