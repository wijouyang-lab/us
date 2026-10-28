# Post-Event Bar Readiness and Price-Basis Audit

Date: 2026-10-28
Research only. No strategy or production changes.

## Result

Inputs:

- 35 real Fed events, first seen 2026-10-28
- Price panel updated through 2026-10-27
- Current panel is raw OHLCV; no adjusted close
- As-of: `2026-10-28T09:50:00Z`

| Status | Count |
|---|---:|
| `ready` | **0** |
| `pending_future_bar` | **35** |
| `excluded` | **0** |
| publication-forward candidates | **35** |
| look-ahead flags | **0** |

Every event is pending, not an error:

- all events are market-wide and the event records carry no ticker;
- the current panel has no `SPY`/market proxy, so `missing_market_proxy`;
- there is no completed post-2026-10-28 close bar yet;
- adjusted price is unavailable;
- corporate actions are unverified.

No event is marked `ready` until all of these are resolved.

## Tool

`tools/research/event_post_bar_readiness.py`

Checks per event:

- aware `available_at` and `as_of`;
- event version known at `as_of`;
- real post-availability trading bar;
- close strictly after availability;
- +1 and +5 subsequent sessions;
- missing ticker/price, duplicate bars, invalid OHLCV;
- raw vs adjusted price basis;
- corporate-action verification;
- future-event/version leakage.

Output statuses:

- `ready`: bars + verified price basis + no hard error;
- `pending_future_bar`: valid event, but missing future bars, market proxy, adjusted price, or corporate-action verification;
- `excluded`: invalid/missing timestamp, source URL/ID, decision order, duplicate/invalid bar, or look-ahead.

Missing future bar is **not** treated as corrupted data.

## Price basis limitation

The panel contains raw OHLCV only.

- Raw close change is **not** total return.
- Splits/dividends are not adjusted.
- Corporate actions are not verified.
- Do not use raw-close returns as complete total return.
- Current readiness therefore stays `pending` even with enough bars.

A future price-basis upgrade must add verified adjusted close or corporate-action
factors without rewriting raw history.

## Real-data reasons

Observed reasons on all 35:

```text
missing_market_proxy
missing_entity_ticker
adjusted_price_unavailable
corporate_actions_unverified
```

No `excluded` reason such as missing timestamp, invalid source, duplicate bar,
or decision inversion was observed.

## Tests

`tests/test_event_post_bar_readiness.py` 鈥?**8 passed**:

- ready requires bars and verified price basis;
- future bars 鈫?pending, not missing-data error;
- unverified adjustment 鈫?pending;
- missing timezone 鈫?excluded;
- duplicate bar 鈫?excluded;
- invalid OHLCV 鈫?excluded;
- no entry bar 鈫?pending;
- after-close event uses next session;
- market-wide event with explicit proxy can become ready.

## Boundary

No event study was run. No alpha result is claimed.

Until there is:
1. a real post-first-seen daily close,
2. a valid market proxy,
3. verified adjusted/corporate-action basis,

the event sample remains `pending_future_bar`.
