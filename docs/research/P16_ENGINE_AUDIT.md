# P16 Engine Audit (for P17)

Status: **PARTIAL — P16 results are not a valid base for P17**.

## A1 Entry ranking mismatch

- IC/research score: `0.5*rank(MOM63)+0.5*rank(MOM126)`.
- Portfolio score: `0.5*MOM63+0.5*MOM126` (raw values).

These are not equivalent. The number of order changes is not committed in the
P16 result files, so this audit cannot give an exact count; the mismatch is
confirmed by source inspection. P16 alpha is closed and is not revised.

## A2 Missing prices

P16 uses `pct_change()` without `fill_method=None`, and `rolling`/`shift` on
adjusted-close matrices. Valuation uses a local `ffill` matrix (`val`) but that
correction was made after the first run; the final P16 committed summaries are
therefore not fully auditable. There is no holding-level stale-price count,
stale NAV share, exit-failure list, or delisting/liquidation rule.

## A3 Regime statistics

P16 reported full-series counts 4,443 / 6,290. For the actual windows:

| window | RISK_ON | total |
|---|---:|---:|
| 2020-01-02..2024-12-31 | 979 | 1,258 |
| 2022-01-03..2024-12-31 | 533 | 753 |

SPY weekday dates absent: 234 (not proven holidays).

## A4 Regime scope

P16 regime only blocks new entries. It does not reduce existing exposure or
force liquidation. It is an entry filter, not a validated risk overlay.

## A5 Benchmark mismatch

Stocks use `adjusted_close`; SPY uses `close`. The benchmark is not the same
return basis. SPY close contains dividends? No — it is price return only.
No total-return claim is possible.

## A6 Risk metrics

P16 `sharpe` = CAGR / annualized volatility. This is not the daily excess-return
Sharpe. No risk-free series was used. NAV starts at 50,000 but the engine lacks
a full trade ledger, realized/unrealized P&L, and stale-price NAV attribution.

## A7 Execution

Entries use prior-close signal and current-close execution, which is acceptable
as a close proxy. But the engine has no explicit next-session execution table,
no duplicate-order guard, and no per-trade cash/cost ledger.

## A8 Tests

P16 has 7 summary-level tests, not 15 independent backtest behavior tests. This
audit does not reopen P16; P17 uses a separate engine only after identity is
fixed.

## Consequence

P16 cannot be used as evidence of entry/exit or regime alpha. P17 stops at the
PIT identity gate.
