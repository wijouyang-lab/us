# Current US Selection & Forward Signal V1

Research only. No PAPER-50000, no IBKR, no orders.

## Run

```bash
python tools/research/current_live/build_watchlist.py
python tools/research/current_live/track_forward.py
```

`build_watchlist.py` reads:

- `data/research/current_live_v1/daily_14m.parquet`
- `etf_1y.parquet`
- `unified_selection_v1_1.csv`

and writes the watchlist, immutable snapshot, forward table, and weekly stats.

## Snapshot rules

- Snapshot name includes signal date and SHA-256 prefix.
- Existing snapshot files are never overwritten.
- A rerun with different content creates a different hash/version; development
  versions are kept under `snapshots/archive_development/`.
- `signals_history.json` points to the canonical snapshot.

## Forward rules

- Horizons: 5/10/20/40 **trading days** after the signal date.
- Returns use adjusted close; entry is the signal-date close.
- If the horizon date does not exist: `PENDING`.
- No future price is filled.
- Matured signals remain in the table; PENDING rows are not deleted.

## Page

`terminal/current_watch.html`; data at `dashboard/data/current_watch.json` with
SHA-256 verification, fail-closed.

## Constraints

- 5,462 quote symbols; 5,072 scored; 286 eligible; 10 main watch.
- Quality available for 2,275 scored names; missing is never zero-filled.
- No delisted/PIT universe; current screen only, not a validated alpha claim.
