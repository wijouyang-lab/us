# P12.3.3: America/New_York DST End-of-Day Boundary Fix

Date: 2026-11-17
Branch: `research/p12-event-fundamental-feasibility`
Status: **READY_RESTRICTED — DST boundary corrected**

---

## 1. Defect

`_et_end_of_day()` added a fixed 24-hour `Timedelta` to local midnight:

```python
pd.Timestamp(day).tz_localize(ET) + pd.Timedelta(days=1) - 1 second
```

On US DST transition days this is wrong:

- spring forward day is 23 hours long;
- fall back day is 25 hours long.

The new implementation builds the **next local calendar midnight before
localizing**, then subtracts one second:

```python
next_midnight = pd.Timestamp(day).normalize() + pd.Timedelta(days=1)
local = next_midnight.tz_localize("America/New_York") - pd.Timedelta(seconds=1)
return local.tz_convert("UTC")
```

## 2. Boundary results

```text
spring 2025-03-09 -> 2025-03-10T03:59:59Z
fall   2025-11-02 -> 2025-11-03T04:59:59Z
normal EDT 2025-07-01 -> 2025-07-02T03:59:59Z
normal EST 2025-12-02 -> 2025-12-03T04:59:59Z
```

Visibility:

```text
spring 03:59:58Z -> not visible
spring 03:59:59Z -> visible
fall   04:59:58Z -> not visible
fall   04:59:59Z -> visible
```

File: `data/research/p12_3_3_dst_boundary_tests.csv` — 8/8 PASS.

## 3. Preserved behavior

- filing-date fallback and date-only `asof()` share `_et_end_of_day()`;
- `FILING_DATE_LOW_PRECISION` remains;
- real acceptance timestamps are unchanged and still take precedence;
- full timestamps require explicit timezone;
- fact identity, periods and accession-version selection unchanged;
- P12.3/P12.3.1/P12.3.2 files preserved.

## 4. Final status

```text
P12_3_3_STATUS: READY_RESTRICTED
SPRING_DST_BOUNDARY: PASS
FALL_DST_BOUNDARY: PASS
NORMAL_EDT: PASS
NORMAL_EST: PASS
TIMEZONE_TESTS: 8 PASS
LOW_PRECISION_ROWS: 118444
ACCEPTANCE_ROWS: 104360
MARKET_WIDE_PIT: DATA_BLOCKED
EXACT_EARNINGS_TIME: DATA_BLOCKED
INTRADAY_REACTION: DATA_BLOCKED
```

No purchase, VPS, IBKR, paper/shadow, portfolio/factor construction, PR merge,
main change or raw-data upload.
