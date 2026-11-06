# P7 Strategy Assembly, Portfolios and Research Shadow

Date: 2026-11-06
Status: **P7_STRATEGY_RESEARCH · RESEARCH_ONLY · PIT_BACKTEST_BLOCKED**

This is a research strategy assembly, not a live mandate, not Alpha and not a
PAPER-50000 change. No broker or real order is involved.

## 1. Updated fundamentals

P6.17 identified 94 unique tickers superseded by a later periodic SEC filing.
P7 refreshes their SEC company facts:

```text
superseded rows: 94
UPDATED_FROM_SEC_COMPANYFACTS: 93
SIX_K_QUARANTINED:             1  (INMD)
```

Facts are limited to those filed on or before 2026-11-05. Old values are not
carried forward. Missing facts remain blank. INMD remains isolated because its
latest 6-K is not confirmed to contain financial data.

Files:

```text
data/universe/p7/updated_fundamentals.csv
data/universe/p7/updated_fundamentals_summary.json
```

## 2. Strategy definitions and launch status

| Strategy | Eligible | Status |
|---|---:|---|
| `VALUE_V1` | 13 | **LAUNCHABLE** |
| `QUALITY_V1` | 3 | NOT_LAUNCHABLE (<10) |
| `GARP_V1` | 0 | NOT_LAUNCHABLE (<10) |
| `BLENDED_V1` | 0 | NOT_LAUNCHABLE (<10, at least 2 factors required) |

No threshold was relaxed to manufacture 10 names.

Missing factors are not zero-filled. `strategy_scores.csv` records
`factors_present` and `factor_count`; BLENDED only uses available factor scores.

Files:

```text
strategy_scores.csv
strategy_candidates.csv
p7_strategy_status.json
```

## 3. VALUE_V1 portfolio

Constraints:

```text
long only
no leverage
13 holdings
5% cash
max issuer 10%
max sector 25%
ADV20/60 recorded for each holding
existing cost model: 5 bps slippage + 0.5 bps commission
```

Selected:

```text
ABG, GPI, CCS, EFOR, KBH, DXC, VTOL, LEA,
CTVA, SLVM, SPB, INGM, WHR
```

Sector weights:

```text
CONSUMER_DISCRETIONARY 20.00%
CONSUMER_STAPLES        8.02%
INDUSTRIALS             25.00%
MATERIALS                8.09%
OTHER_SERVICES          15.34%
TECHNOLOGY              18.55%
```

Initial one-way turnover 100%; expected annual one-way 25%; estimated initial
cost $26.12 on $47,500 invested.

Both `equal_weight` and `risk_adjusted` variants satisfy the issuer and sector
caps. The target file contains both.

Files:

```text
portfolio_weights.csv
portfolio_risk_summary.json
```

## 4. Independent RESEARCH_SHADOW_P7

Important separation:

```text
shadow_id:           RESEARCH_SHADOW_P7
paper account:       PAPER-50000
paper read:          false
paper write:         false
real orders:         false
initial capital:     $50,000
signal date:         2026-11-05
next session:        2026-11-06
```

The signal is after the 2026-11-05 close. No fill is simulated at a price that
was already known at signal time. The shadow starts with:

```text
NAV $50,000
cash $50,000
positions value $0
status PENDING_NEXT_SESSION
```

It will consume the next completed-session open/reference price, then record
fills and daily NAV. Until then, returns are `PENDING`, not zero and not
fabricated.

Files:

```text
shadow_positions.csv
shadow_nav.csv
p7_status.json
```

## 5. Benchmarks

Current snapshot only:

```text
SPY
QQQ
IWM
EQUAL_WEIGHT target reference (PENDING)
```

No historical strategy return is claimed. The benchmark file is a date-aligned
unadjusted-close snapshot from yfinance; no Alpha/Sharpe is computed.

Files:

```text
benchmark_snapshot.csv
benchmark_summary.json
```

## 6. Strategy Lab

`build_snapshot.py` now exposes `snapshot.p7`; Strategy Lab renders:

- four P7 strategies and launch status;
- eligible candidate table with factors present;
- target weights and notional;
- sector/cash/cost/turnover summary;
- shadow NAV status;
- benchmark snapshot.

The shadow is labelled `RESEARCH_ONLY` and is separate from PAPER-50000.

## 7. Boundaries

- No PAPER-50000 read or write.
- No IBKR/real broker.
- No historical PIT backtest, Alpha, Sharpe, drawdown or out-of-sample claim.
- `QUALITY_V1`, `GARP_V1`, `BLENDED_V1` are explicitly `NOT_LAUNCHABLE`.
- Updated SEC facts are latest available only up to 2026-11-05.
- 6-K content is still not parsed.
