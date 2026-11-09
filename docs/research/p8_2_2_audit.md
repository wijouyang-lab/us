# P8.2.2 Data Integrity Audit and Frozen Backtest Semantics

Date: 2026-11-09
Status: **P8_2_2_AUDIT_COMPLETE_NO_GO**

P8, P8.1, P8.2 and P8.2.1 artifacts are preserved. This is a new audit result.

## 1. The 48 invalid months: what P8.2.1 actually did

P8.2.1 had a real code defect:

```python
dts.append(mdte)          # every month
ret[name].append(net)     # only valid strategy-months
```

There was no placeholder for `DATA_INVALID_UNPRICEABLE` months. Therefore the
`zip(dts, ret[name])` alignment shifted after the first invalid month. The
reported CAGR/Sharpe/HAC could use a return from a different month and silently
dropped invalid months. This is a methodology bug, not a valid NAV treatment.

P8.2.2 fixes it:

- the fixed month calendar is retained;
- every strategy gets one slot per month, `None` for invalid;
- invalid months are `DATA_INVALID_UNPRICEABLE`, never zero;
- metrics are explicitly `valid_subset` only;
- `nav_complete = false` for equity strategies;
- no complete-NAV or full-period performance claim is made for affected series.

P8.2.1's 48 invalid strategy-months are preserved as a historical audit finding;
P8.2.2's real-time rule produces its own invalid count (42 strategy-months:
4+6+7+11+2+12), reported below. The difference is expected because P8.2.1 used
the post-hoc classification set; P8.2.2 does not.

## 2. Event-time provenance

Formal method E uses a deterministic rule:

```text
|adjusted close daily return| > 5x
```

- `event_date`: historical price date.
- `source_available_at`: price-panel event date.
- `detected_at`: rule event date (after close), not today's audit date.
- `classification_updated_at`: 2026-11-09 audit run.
- `post_hoc_used_for_signal`: **false**.

Today's `VERIFIED_CORRUPT` / `ZERO_VOLUME_OR_STALE` / `UNRESOLVED` labels are
**not** used in historical signal formation. CBE/ACS/GME post-hoc labels remain
in the audit for evidence only.

The formal rule is a real-time data-integrity filter, not a claim that all
post-hoc corrupt labels were known historically.

Time-travel helper:

```text
available_on(event_date, decision_date, detected_at)
```

An event with `detected_at > decision_date` is unavailable. Tests cover this.

File: `event_time_policy.json`, `event_time_audit.csv`.

## 3. Complete member-day partition

Every one of 1,095,490 effective member-days has exactly one status:

| Status | Count |
|---|---:|
| VALID_VERIFIED_TRADABLE | 981,362 |
| UNKNOWN_MISSING_DATA | 109,132 |
| VERIFIED_CORRUPT | 117 |
| ZERO_VOLUME_OR_STALE | 4,845 |
| UNRESOLVED | 34 |
| INVALID_OHLC_RELATION | 0 |
| INVALID_VOLUME | 0 |
| DUPLICATE_OR_CONFLICT | 0 |
| OTHER_INVALID | 0 |
| **Total** | **1,095,490** |

This resolves the unexplained differences:

- Full OHLCV = 986,358;
- Verified tradable = 981,362;
- Difference 4,996 = 117 corrupt + 34 unresolved + 4,845 zero/stale;
- `ZERO_VOLUME_OR_STALE` is not collapsed into `VERIFIED_CORRUPT`;
- `FULL_OHLCV` is not equivalent to tradable.

The full coverage remains below the 95% member-day and 98% ticker gates.

## 4. Method E results (valid-subset; not complete NAV)

| Strategy | Valid months | Invalid months | CAGR* | OOS CAGR* | Sharpe* | Max DD* | HAC active t |
|---|---:|---:|---:|---:|---:|---:|---:|
| Momentum20 | 294 | 4 | 7.7% | 5.5% | 0.39 | -64.5% | -2.48 |
| Momentum60 | 292 | 6 | 6.6% | 7.7% | 0.42 | -59.9% | -3.23 |
| Momentum120 | 291 | 7 | 12.6% | 10.9% | 0.60 | -63.8% | -2.16 |
| Trend MA200 | 287 | 11 | 11.9% | 8.0% | 0.59 | -59.8% | -2.19 |
| Low Vol60 | 296 | 2 | 12.0% | 11.4% | 0.96 | -34.7% | -2.26 |
| Reversal5 | 286 | 12 | 16.6% | 8.9% | 0.53 | -68.6% | -0.24 |

`*` valid-subset only. The fixed calendar includes invalid months; they are not
zero-filled, not deleted from the calendar, and not claimed as complete NAV.
Every equity strategy has `nav_complete = false` because of the invalid months.

No event-time strategy has positive active HAC; all fail the -35% drawdown
threshold except Low Vol, whose active HAC is still negative. **All NO-GO.**

## 5. Walk-forward

60m train / 1m purge / 12m test; 19 windows; 6 switches; actual target-holding
L1 switch cost:

```text
selected CAGR (valid subset): 7.37%
selected Sharpe:              0.477
max drawdown:                -63.87%
HAC active vs EW:             -2.137
p-value:                       0.0326
```

Dynamic selection underperformed EW. NO-GO.

## 6. BH and final status

Primary 8-strategy family (6 equity + 2 ETF). Some q values are below 0.10, but
those rows have negative active HAC or fail drawdown; no row is promoted by
changing the family. The 24-hypothesis A/B/C/D sensitivity remains reported.

```text
GO:            0
NO-GO:         8 primary strategies
DATA BLOCKED:  Nasdaq-100, Dow 30, historical fundamental PIT,
               2025-2026 historical panel
```

No P8 shadow. P7 shadow remains independent.

## 7. Files

```text
data/research/p8_2_2/ticker_anomaly_audit.csv
data/research/p8_2_2/anomaly_classification.json
data/research/p8_2_2/event_time_policy.json
data/research/p8_2_2/event_time_audit.csv
data/research/p8_2_2/member_day_status_summary.json
data/research/p8_2_2/member_day_status_by_year.csv
data/research/p8_2_2/member_day_status_by_ticker.csv
data/research/p8_2_2/ohlcv_coverage_summary.json
data/research/p8_2_2/factor_window_audit.csv
data/research/p8_2_2/event_time_results.json
data/research/p8_2_2/event_time_monthly.csv
data/research/p8_2_2/event_time_holdings.csv
data/research/p8_2_2/walk_forward_results.json
data/research/p8_2_2/walk_forward_switches.csv
data/research/p8_2_2/strategy_gate_results_p822.csv
data/research/p8_2_2/p8_2_2_status.json
```
