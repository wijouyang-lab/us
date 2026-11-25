# Multi-Factor Price Strategy V2 — Final

Date: 2026-11-25
Branch: `research/multi-factor-strategy-competition-v1`
PR: #626
Status: **PROMISING_BUT_UNPROVEN** (A risk profile); no PAPER authorization

## 1. What was run

- Daily close-to-close engine, signal at prior close, execution at next close.
- 502-ticker snapshot, 2016-12-12..2026-10-13.
- Top 10, max 10 positions, 0.50% risk per trade, 10% single-name cap.
- Double-side cost: 10 bps per side (buy and sell each 10 bps).
- Windows: 5Y 2021-10-14..2026-10-13; 3Y 2023-10-13..; 1Y 2025-10-13..
- Exits: fixed 6%, fixed 8%, ATR20, ATR25, ATR30, MA50, rank, time 20d.
- Benchmarks: SPY, QQQ, BIL, price-return only (no total-return claim).

The prior V2 script was replaced by a vectorized engine. The slow nested
DataFrame loop was not used for results.

## 2. Strategy results

| Window | Strategy | CAGR | Vol | Sharpe | MaxDD | Trades |
|---|---|---:|---:|---:|---:|---:|
| 5Y | A | 9.30% | 12.7% | 0.763 | -11.46% | 637 |
| 5Y | B | 6.81% | 12.0% | 0.607 | -12.33% | 635 |
| 5Y | C | 7.93% | 12.7% | 0.664 | -12.88% | 635 |
| 3Y | A | 16.96% | 14.0% | 1.193 | -10.77% | 438 |
| 3Y | B | 14.23% | 12.9% | 1.092 | -12.33% | 435 |
| 3Y | C | 17.60% | 13.9% | 1.237 | -11.05% | 433 |
| 1Y | A | 35.91% | 14.8% | 2.146 | -8.14% | 139 |
| 1Y | B | 22.01% | 14.8% | 1.420 | -12.27% | 147 |
| 1Y | C | 30.41% | 14.4% | 1.911 | -8.47% | 141 |

5Y benchmarks:

| Benchmark | CAGR | Vol | Sharpe | MaxDD |
|---|---:|---:|---:|---:|
| SPY | 11.85% | 17.2% | 0.747 | -25.36% |
| QQQ | 15.14% | 22.9% | 0.734 | -35.62% |
| BIL | 3.58% | 0.28% | 12.52 | -0.05% |

A underperforms SPY CAGR by ~2.5pp but has less than half the SPY drawdown and a
slightly higher Sharpe. It meets the 15% drawdown target on 5Y/3Y/1Y.

## 3. Exit comparison (A, 5Y, 10 bps/side)

| Exit | CAGR | MaxDD | Sharpe | Trades |
|---|---:|---:|---:|---:|
| fixed6 | 14.13% | -18.57% | 0.807 | 643 |
| fixed8 | 10.16% | -16.33% | 0.748 | 608 |
| ATR20 | 12.01% | -14.12% | 0.805 | 734 |
| ATR25 | 9.30% | **-11.46%** | 0.763 | 637 |
| ATR30 | 8.70% | -12.31% | 0.845 | 585 |
| MA50 | 8.77% | -15.57% | 0.710 | 590 |
| rank | -2.46% | -17.36% | -0.481 | 244 |

ATR25 gives the best drawdown; ATR30 best Sharpe. Fixed6 has higher return but
breaches 15% DD. Rank exit is destructive.

## 4. Cost sensitivity (A, 5Y)

| bps/side | CAGR | MaxDD | Sharpe |
|---|---:|---:|---:|
| 5 | 10.26% | -11.08% | 0.833 |
| 10 | 9.30% | -11.46% | 0.763 |
| 20 | 7.40% | -12.31% | 0.622 |

## 5. Conclusion

```text
A = PROMISING_BUT_UNPROVEN
B = NO_GO
C = NO_GO
OVERALL = PROMISING_BUT_UNPROVEN
PAPER_50000 = NOT_AUTHORIZED
```

Why not PAPER:

1. No strict chronological OOS/walk-forward was run.
2. A underperforms SPY CAGR on 5Y and 3Y.
3. The 1Y result is exceptional and likely regime-specific.
4. The universe is a 502-name partial PIT snapshot, not full market.
5. Prices are unadjusted close, not total return.

Why not pure NO_GO: A has a genuine risk profile (5Y DD -11.5% vs SPY -25.4%,
Sharpe 0.763 vs 0.747) and survives 20 bps costs with positive CAGR. It is worth
observing, not funding.

## 6. Data limitations

- Price only; no dividend adjustment.
- No delisting return.
- Historical universe incomplete.
- No strict OOS; all results are in-sample-ish.
- Financial strategies are not part of V2; current fundamentals remain
  current-selection only.

## 7. Files

- `tools/research/mf_strategy_v2_fast.py`
- `tests/test_mf_strategy_v2_fast.py`
- `docs/research/MULTI_FACTOR_STRATEGY_V2_FINAL.md`
- `docs/research/MULTI_FACTOR_V2_STRATEGY_COMPARISON.csv`
- `docs/research/MULTI_FACTOR_V2_EXIT_COMPARISON.csv`
- `docs/research/MULTI_FACTOR_V2_COST_SENSITIVITY.csv`
- `docs/research/MULTI_FACTOR_V2_TRADE_LEDGER.csv`
- `docs/research/MULTI_FACTOR_V2_DAILY_NAV.csv`
- `docs/research/MULTI_FACTOR_V2_ANNUAL_RETURNS.csv`
- `docs/research/MULTI_FACTOR_V2_RUNTIME_PROFILE.md`
