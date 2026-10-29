# AOS 2026-10-28 Date-Alignment Root Cause

Date: 2026-10-29 UTC
Research only. No production changes.

## Finding

The bad AOS row was:

```text
Date: 2026-10-28
Open 62.00, High 62.54, Low 61.04, Close 62.06, Volume 1,185,400
```

Those are exactly the 2026-10-27 values. The provider response for AOS
contained two bars:

```text
timestamp 1793107800 -> 2026-10-27: 62.00 / 62.54 / 61.04 / 62.06 / 1,185,400
timestamp 1793194200 -> 2026-10-28: 62.60 / 62.60 / 60.47 / 60.86 / 2,549,200
```

## Root cause

The generic updater was **not** mis-parsing dates:

- `download_batch` converts each yfinance index timestamp with
  `pd.Timestamp(day).date()`;
- the bulk update correctly wrote 495 new 10/28 rows;
- AOS was among the tickers missing from the bulk response.

The error occurred in the manual AOS retry: the first array element (the
10/27 bar) was copied and labeled with the target date `2026-10-28`. There was
no assertion that the selected provider row's source date equaled the target
date before writing.

## Correction

Verified 2026-10-28 AOS row:

```text
Open 62.60, High 62.60, Low 60.47, Close 60.86, Volume 2,549,200
```

This row matches AKShare/Sina and the 10/28 Yahoo response. The local 10/28
increment was corrected; the canonical panel was not written.

## Regression guards

`tools/research/update_recent_prices_incremental.py` now:

1. accepts an explicit `target_date`;
2. appends only rows whose source `Date == target_date`;
3. returns `target_date_missing=True` if the target is absent;
4. rejects a target-date row whose OHLCV exactly equals the prior session,
   reporting `identical_previous_rows`;
5. exposes `rejected_identical_previous_bar` / `pending_provider_close` statuses.

The exact-copy guard catches the AOS failure mode; the target-date filter
prevents an older source row from being relabeled.

## Tests

`tests/test_update_recent_prices_incremental.py`: **6 passed**

New cases:

- previous session relabeled as target -> not appended;
- target absent -> no prior-session fill;
- null close/invalid OHLCV -> rejected;
- idempotent repeat -> no duplicate.

## Full panel check

- 10/28 rows: 502 (HUBB missing).
- 10/27 rows: 503.
- Rows exactly equal to prior session: **0**.
- Duplicate `(Date, Ticker)`: **0**.
- AOS 10/28 vs AKShare/Sina: close 60.86, volume 2,549,200 (AKShare 2,549,155).

HUBB remains missing; no synthetic fill.
