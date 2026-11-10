# P8.2.1 Event-Time Safety, Full OHLCV and Switch Costs

Date: 2026-11-08
Status: **P8_2_1_EVENT_TIME_NO_GO · RESEARCH_ONLY**

P8, P8.1 and P8.2 artifacts are preserved. This is an independent P8.2.1 set.

## 1. Look-ahead fix

P8.2 method C used anomaly dates *inside the future holding interval* to decide
whether to buy at formation. That is look-ahead.

New method D:

- at formation, only anomalies with event date ≤ formation are known;
- an anomaly in the factor lookback makes the factor unavailable at that
  formation;
- an anomaly that happens **during** the holding period is not used to change
  the holdings;
- that strategy-month is marked `DATA_INVALID_UNPRICEABLE`;
- the affected exposure is reported, not silently deleted or zero-filled.

Actual result:

```text
strategy-month DATA_INVALID: 48
mean invalid exposure:       5.10%
```

Method C (P8.2) remains only as a look-ahead diagnostic; method D is the formal
event-time candidate.

## 2. Revised anomaly classification

3,041 anomaly rows, 109 tickers:

```text
VERIFIED_CORRUPT             735
ZERO_VOLUME_OR_STALE       1,199
UNRESOLVED                 1,105
VERIFIED_REAL_RETURN           2  (GME)
VERIFIED_CORPORATE_ACTION      0
```

Zero volume is no longer automatically corruption. CBE/ACS remain
`VERIFIED_CORRUPT` with price-basis/identity evidence; GME remains a real move.
No corporate action was asserted without an external source.

## 3. Full OHLCV coverage

Denominator remains all effective-dated S&P member-days:

```text
member-days:                 1,095,490
valid adjusted close:          986,358  (90.04%)
full OHLCV:                    986,358  (90.04%)
verified tradable:             981,362  (89.58%)
unknown:                       109,132  (9.96%)
corrupt:                           117
zero/stale:                          9
unresolved:                         34
duplicate ticker-date rows:           0
```

Full OHLCV checks: positive OHLC, low ≤ open/close ≤ high, finite volume, and
volume ≥ 0. Verified tradable additionally requires volume > 0 and no
corrupt/unresolved/stale flag.

The old 90.02% figure was close-only; the full/tradable figures are now distinct.

## 4. Factor-window audit

6 strategies × tickers, 5,478 audit rows:

| Strategy | Evaluations | Known anomaly skipped | Insufficient window |
|---|---:|---:|---:|
| Momentum20 | 136,254 | 138 | 482 |
| Momentum60 | 136,254 | 248 | 1,030 |
| Momentum120 | 136,254 | 390 | 2,423 |
| Trend MA200 | 136,254 | 517 | 4,267 |
| Low Vol60 | 136,254 | 248 | 1,030 |
| Reversal5 | 136,254 | 78 | 34 |

No unresolved anomaly is silently used in signal ranking.

## 5. Method C vs formal D

| Strategy | C CAGR | D CAGR | C OOS | D OOS | D HAC active t | D max DD |
|---|---:|---:|---:|---:|---:|---:|
| Momentum20 | 7.7% | 6.7% | 5.4% | 6.5% | -2.06 | -70.0% |
| Momentum60 | 5.7% | 6.4% | 7.7% | 8.1% | -2.30 | -58.1% |
| Momentum120 | 11.4% | 11.6% | 11.4% | 11.4% | -1.73 | -63.2% |
| Trend MA200 | 10.4% | 10.3% | 8.0% | 8.9% | -1.82 | -58.0% |
| Low Vol60 | 9.5% | 8.8% | 11.4% | 12.0% | -2.45 | -34.7% |
| Reversal5 | 14.6% | 13.6% | 8.6% | 10.1% | -0.70 | -68.5% |

The look-ahead fix changes results modestly, but every formal D strategy has
negative active HAC and unacceptable drawdown. All remain **NO-GO**.

## 6. Walk-forward with real switch costs

- 60-month train
- 1-month purge
- 12-month test
- 19 windows
- 8 strategy switches
- actual target holdings compared before/after switch
- L1 weight change used; 10bps per side

```text
selected CAGR:        6.10%
selected Sharpe:      0.398
max drawdown:        -64.96%
HAC active vs EW:    -2.554
p-value:              0.0106
```

The negative active HAC means the dynamic selection underperformed the
equal-weight benchmark. Gate: **NO-GO**.

Switch detail:

```text
data/research/p8_2_1/walk_forward_switches.csv
```

## 7. BH consistency

Primary 8-strategy family and a 24-hypothesis A/B/C/D data-method sensitivity
are both reported. Some individual q values are below 0.10, but those rows also
have negative active t-statistics or fail drawdown; no row is promoted to GO by
changing the family.

`bh_consistency.json` contains both families, with the counting rule explicit.

## 8. Final

```text
GO:            0
NO-GO:         8 primary strategies
DATA BLOCKED:  Nasdaq-100 interval, Dow 30 interval,
               historical fundamental PIT, 2025-2026 historical panel
```

No P8 shadow is launched. P7 `RESEARCH_SHADOW_P7` remains independent.

## 9. Files

```text
data/research/p8_2_1/ticker_anomaly_audit.csv
data/research/p8_2_1/anomaly_classification.json
data/research/p8_2_1/ohlcv_coverage_summary.json
data/research/p8_2_1/ohlcv_coverage_by_year.csv
data/research/p8_2_1/factor_window_audit.csv
data/research/p8_2_1/event_time_results.json
data/research/p8_2_1/event_time_monthly.csv
data/research/p8_2_1/event_time_holdings.csv
data/research/p8_2_1/walk_forward_results.json
data/research/p8_2_1/walk_forward_switches.csv
data/research/p8_2_1/bh_consistency.json
data/research/p8_2_1/strategy_gate_results_p821.csv
data/research/p8_2_1/p8_2_1_status.json
```
