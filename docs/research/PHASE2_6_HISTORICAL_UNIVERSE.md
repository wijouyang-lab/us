# Phase 2.6 Historical Universe and Survivorship Audit

Date: 2026-10-30
Research only. No production changes.

## 1. Current 503-name panel

- 1,239,013 rows, 503 tickers, 2016-09-19..2026-10-28.
- It is a **current** universe, not historical S&P 500 membership.
- No delisted names, no historical constituents, no dividend total return.
- Current results remain `EXPLORATORY_CURRENT_UNIVERSE_SURVIVORSHIP_BIASED`.

## 2. Free historical membership source tested

Source:

```text
https://github.com/fja05680/sp500
S&P 500 Historical Components & Changes (Updated).csv
```

Actual fetch:

- 2,720 snapshots;
- 1996-01-02..2026-08-18;
- 1,209 unique tickers;
- membership count 487鈥?07.

This is a **third-party reconstruction**, not an official S&P DJI source. It has
no company identifier, no official change notices, and no delisting returns.

### Coverage vs current price panel

| Year | Snapshot | Members | Match current panel | Missing price |
|---:|---|---:|---:|---:|
| 1996 | 1996-12-27 | 488 | 152 | 336 |
| 2000 | 2000-12-29 | 492 | 200 | 292 |
| 2010 | 2010-12-31 | 497 | 276 | 221 |
| 2016 | 2016-12-30 | 506 | 338 | 168 |
| 2020 | 2020-12-21 | 505 | 399 | 106 |
| 2024 | 2024-12-23 | 503 | 461 | 42 |
| 2026 | 2026-08-18 | 503 | 495 | 8 |

Aggregate:

- 496 historical tickers overlap the 503-name panel;
- **713 historical tickers are not in the price panel**;
- this is an upper bound on missing/delisted/ticker-changed names, not a clean
  delisting count.

The 713 cannot be classified reliably without company IDs, ticker-change
records, and delisting dates. They are **not** silently treated as delisted or
removed.

## 3. Identity and ticker changes

The source provides ticker strings only. It has:

- no permanent company identifier;
- no merger/acquisition mapping;
- no ticker-reuse flag;
- no effective date for ticker changes.

Therefore the engine does **not** merge old and new tickers. Each ticker is a
separate string identity with `company_identifier = null` and
`ticker identity unverified`. This avoids false continuity.

## 4. Delisting and delisting returns

Actual state:

- 713 historical tickers absent from the current panel;
- no reliable historical OHLCV for those names in the project;
- no delisting dates or last-trade prices for them;
- no cash/stock consideration or delisting return data.

We cannot calculate:

- how many are true delistings vs ticker changes;
- delisting returns;
- the bias from assuming zero delisting return.

No zero-return or last-close assumption is made. Missing delisting returns are
recorded as unavailable.

## 5. Historical universe data structure

`tools/research/historical_universe.py`

Each member record contains:

```text
ticker
company_identifier = null
index = SP500
effective_start_date
effective_end_date
source = fja05680/sp500
source_confidence = third_party_medium
membership_status = member
evidence_note
pit_eligible = false
```

Query interface:

```python
HistoricalUniverse(path).query(date)
HistoricalUniverse(path).get_historical_universe(date, pit_only=False)
```

Behavior:

- uses latest snapshot at or before the query date;
- marks `STALE_SNAPSHOT` after 7 days;
- `pit_only=True` returns an empty set because third-party medium confidence is
  not admitted to PIT;
- no future member appears in a prior query;
- exited members are absent after their effective end.

Real query sample:

```text
2026-08-18 -> OK, 503 members, pit_eligible false
2026-10-28 -> STALE_SNAPSHOT, 71 days, pit_eligible false
```

## 6. PIT status

No date is admitted to formal PIT research.

Reasons:

1. membership source is third-party medium confidence;
2. no official effective-date/change notices;
3. no company identity mapping;
4. no delisted OHLCV;
5. no delisting returns;
6. latest snapshot is stale after 2026-08-25.

The code is fail-closed: `pit_only=True` returns empty.

## 7. Tests

`tests/test_historical_universe.py`:

- entry/exit boundary;
- no future member in earlier date;
- delisted/ticker-exited name remains only in its historical interval;
- stale snapshot is not PIT;
- third-party membership is not admitted to PIT;
- repeated query deterministic.

5 passed.

## 8. What is possible now

- exploratory current-universe research (existing Phase 2.5);
- historical membership **coverage report** with medium confidence;
- identifying names missing from the price panel;
- preventing current-universe data from being called PIT.

Not possible without more data:

- formal PIT S&P 500 backtest;
- bias-free historical factor validation;
- delisting-return-adjusted strategy results.

## 9. Artifacts

- `tools/research/historical_universe.py`
- `tests/test_historical_universe.py`
- `docs/research/historical_universe_coverage_2026-10-30.json`
- local membership CSV: `data/research/historical_universe/sp500_daily.csv`
- Phase 2.7 design: `docs/research/PHASE2_7_DESIGN_60D_VOLATILITY.md`

## 10. Conclusion

Free data **does not** currently support a credible full historical PIT S&P 500
reconstruction. It supports a partial, medium-confidence membership audit and a
clear gap count.

No PIT date is approved. No current-universe result is upgraded.
