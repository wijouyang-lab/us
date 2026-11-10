# FOMC History Extension and first_seen Capture

Date: 2026-10-29 UTC
Research only. No canonical write.

## 1. Coverage

| Item | Result |
|---|---:|
| 2010鈥?022 statement records | **107** |
| exact release time | **58** |
| date-only (no precise time) | **49** |
| 2023鈥?025 statements | **25** |
| combined 2010鈥?025 | **132** |
| combined exact | **83** |
| combined date-only | **49** |
| event study usable (exact, rate statements) | **82** |

### Year coverage

```text
2010鈥?025
```

- 2010鈥?014: date-only pages; no time assumed.
- 2015鈥?025: exact time parsed from official pages.
- 2025 longer-run-goals strategy statement is retained with a separate event
  type and excluded from the rate-statement study.
- Missing precise time is preserved as `date_only`; it is never defaulted to
  2:00 p.m.

### Evidence

- 2010鈥?014 Fed historical pages: no `For release at` time.
- 2015鈥?025 pages: `For release at h:mm a.m./p.m. EDT|EST`.
- Source: `federalreserve.gov` official press releases.
- Fed public-domain disclaimer permits reuse with attribution.

Manual sampling of 2010, 2012, 2014, 2016 pages confirmed the above; 2010/2012/2014
had no exact time, 2016 had `2:00 p.m.`.

## 2. first_seen capture

Tool:

`tools/research/event_capture_store.py`

Live store:

`docs/research/fomc_live_capture_final_2026-10-29.jsonl`

Actual observations:

| Field | First fetch | Second fetch |
|---|---|---|
| event_id | 20250319 | 20250319 |
| first_seen_at_utc | 2026-10-29T15:04:36.738184Z | same |
| version | 1 | 1 |
| http_status | 200 | 200 |
| parse_status | exact | exact |
| pit_status | forward_observed | forward_observed |

The second fetch preserved the first observation time and did not create a
spurious version. Content hash is now based on the stable release-body segment,
not the entire dynamic HTML page.

Historical backfill:

`docs/research/fomc_backfill_capture_2026-10-29.jsonl`

For 2010-01-27:

```text
first_seen_at_utc = null
pit_status = retrospective_non_PIT
parse_status = date_only
```

No historical first-seen was fabricated.

Failure handling is tested for non-200/parse failures; failed observations are
written with `http_status`/`parse_status` rather than silently dropped.

## 3. Extended event study

Events: 82 exact FOMC rate statements, 2015鈥?025; 82 unique entry dates.
Proxies: SPY, QQQ, IWM, TLT, GLD; 4,232 rows each, 2010-01-04..2026-10-29,
0 duplicates, 0 invalid OHLC. Raw open/close; 10 bps round-trip.

| Proxy | Gross +1 | Net +1 | Gross +5 | Net +5 | Baseline +1 | Baseline +5 |
|---|---:|---:|---:|---:|---:|---:|
| SPY | -0.207% | -0.307% | +0.006% | -0.094% | +0.083% | +0.306% |
| QQQ | -0.184% | -0.284% | +0.181% | +0.081% | +0.116% | +0.433% |
| IWM | -0.349% | -0.449% | -0.398% | -0.498% | +0.039% | +0.225% |
| TLT | +0.140% | +0.040% | -0.081% | -0.181% | +0.000% | -0.046% |
| GLD | +0.188% | +0.088% | +0.207% | +0.107% | +0.060% | +0.288% |

No proxy has a positive net +1 result. GLD/TLT have small positive +1, but GLD
+5 remains below its unconditional baseline; TLT +5 is negative. No stable
multi-proxy alpha.

## 4. Limitations

- Historical publication timestamps are official, but there is **no historical
  first-seen**; all historical events remain non-PIT.
- Exact time coverage starts only in 2015; 2010鈥?014 excluded from returns.
- 82 events, 82 unique entry dates; FOMC spacing avoids 20D overlap.
- Raw ETF closes are not dividend-adjusted; short windows limit but do not
  eliminate this issue.
- ETF proxy data from Yahoo remains research-only; no raw files committed.
- No intraday reaction; entry is next open.
- No statistical significance claim.

## 5. Tests

- FOMC history/date-only/duplicate: 2 tests.
- Event capture: 5 tests.
- Extended event study: 3 tests.
- Full CI is reported after commit.

## 6. Artifacts

- combined events: `docs/research/fomc_2010_2025_combined_2026-10-29.json`
- 2010鈥?022 base: `docs/research/fomc_2010_2022_statements_2026-10-29.json`
- 2010: `docs/research/fomc_2010_statements_2026-10-29.json`
- 2021鈥?022 supplement: `docs/research/fomc_2010_2022_supplement_2026-10-29.json`
- live capture: `docs/research/fomc_live_capture_final_2026-10-29.jsonl`
- backfill: `docs/research/fomc_backfill_capture_2026-10-29.jsonl`
- event study: `docs/research/fomc_event_study_2010_2025_2026-10-29.json`
- proxy audit: `docs/research/proxy_source_audit_2026-10-29.json`
- code: `tools/research/fomc_event_study.py`, `tools/research/event_capture_store.py`
