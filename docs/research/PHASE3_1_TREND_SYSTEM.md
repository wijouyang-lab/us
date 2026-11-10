# Phase 3.1 Unified Trend Strategy Core V1

Date: 2026-11-02
Label: `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`
Research only. No production changes. Not deployable; not validated alpha.

## 1. Scope

Implemented:

- unified ETF + stock ranking pond;
- Long-only, no short/leverage/margin/options;
- weekly decisions;
- two-stage WATCH 鈫?CONFIRMED entry;
- dynamic candidate count, no fixed 5/10/20 cap;
- dynamic cash is left to Phase 3.2 risk engine;
- configurable rules, deterministic ranking;
- actual signal output.

No portfolio allocation or risk sizing is implemented in this phase.

## 2. Two-stage rules

### WATCH

All three:

```text
Close > MA50
Mom20 > 0
Rel20 vs SPY > 0
```

WATCH never creates a buy candidate.

### CONFIRMED

Requires:

```text
two consecutive weekly WATCH evaluations
Close > MA200
MA50 > MA200
MA200 20-session slope > 0
```

### Exit

```text
soft: two consecutive weeks Close < MA50 AND Mom20 < 0
hard: Close < MA200
```

Exit resets confirmation. Re-entry must repeat the two-stage process.

## 3. Score

Four equally weighted groups:

| Group | Components |
|---|---|
| Trend | Mom20, Mom60, Mom120, Close/MA50, MA50/MA200 |
| Relative strength | Rel20, Rel60, Rel120 vs SPY |
| Stability | 鈭扸ol60, DD60 |
| Risk efficiency | Mom20 / Vol60 |

Cross-sectional percentile ranks are computed **only at each weekly snapshot**; no future parameters, no class bonus, no neutral fill. Missing required component 鈫?no score.

Ties sorted by ticker.

## 4. Weekly timing

- Last actual trading day of each week.
- Signal only after that close.
- `next_trading_date` is the next actual session.
- Simulation buy price must be next-session open; never signal close.
- Holiday weeks use the actual last session.
- A weekly date with fewer than 100 assets is skipped (incomplete cross-section).

Actual sample: 460 weekly signal dates, 227,188 asset-date rows.

## 5. ETF / stock coverage audit

| Class | Count | Rows each | Data range |
|---|---:|---:|---|
| ETF | 4 (GLD, IWM, QQQ, TLT) | 4,232 | 2010-01-04..2026-10-29 |
| Stock | 503 | ~2,500 | 2016-09..2026-10-28 |
| Benchmark | SPY | 鈥?| excluded from candidate pool |

SPY is used as benchmark only.

No ETF PIT membership history exists. ETF prices are current provider histories, not
point-in-time fund universes. No delisting/closure treatment.

## 6. Actual signal counts

```text
assets:              507
ETFs:                  4
stocks:              503
weekly signal dates: 460
WATCH rows:       39,748
CONFIRMED rows:   76,544
buy candidates:   76,544
exit signals:      6,424
```

"Buy candidates" means confirmed with a score; there is **no** position sizing,
cash target, or fixed number of holdings. All confirmed assets can be candidates.

## 7. Explicit limitations

- current 503-name stock panel, survivorship-biased;
- no historical PIT membership;
- no delisting returns;
- only 4 ETFs; no broad ETF universe;
- no dividends;
- no transaction-cost/portfolio simulation in this phase;
- no risk engine, no cash model;
- no claim of alpha or deployability;
- 2026 partial;
- not connected to Strategy Lab formal ranking.

## 8. Tests

`tests/test_trend_v1.py`: **10 passed**

- future price mutation does not change past score;
- WATCH not buy;
- two-week confirmation;
- exit and re-entry reset;
- ETF/stock same rank pool;
- no fixed holding cap;
- missing data fail-closed;
- holiday/partial week dates;
- signal vs next-entry date separation;
- deterministic repeat.

## 9. Artifacts

- `tools/research/trend_v1/data.py`
- `tools/research/trend_v1/scoring.py`
- `tools/research/trend_v1/state.py`
- `tools/research/trend_v1/signals.py`
- `tools/research/trend_v1/run.py`
- `tests/test_trend_v1.py`
- `docs/research/trend_v1_coverage_2026-11-02.json`
- local full signals: `docs/research/trend_v1_signals_2026-11-02.csv`

## 10. Conclusion

Trend V1 core code is complete. It is a research signal engine, not a strategy
with proven returns. Phase 3.2 must add risk sizing, cash allocation, turnover
cost and portfolio accounting before any performance claim.
