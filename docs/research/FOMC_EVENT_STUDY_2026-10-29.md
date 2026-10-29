# FOMC Event Study 鈥?Multi-Proxy Feasibility

Date: 2026-10-29 UTC
Research only; no canonical write.

## 1. Sources and coverage

### Fed FOMC statements

- Source: Federal Reserve Board public press releases.
- Index: `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`
- 2023-01-01 .. 2025-12-10.
- Parsed 25 `monetary*.a.htm` pages.
- 25 exact release timestamps.
- 24 used as FOMC rate statements; 1 excluded as a longer-run-goals strategy statement.

All 24 used statements released at 2:00 p.m. ET; timezone handled with
America/New_York and converted to UTC. Fed material is public domain with
attribution; Board pages exclude third-party material.

### ETF proxies

Downloaded from Yahoo chart API for 2023-01-03 .. 2026-10-29:

| Proxy | Rows | First | Last | Duplicate dates | Invalid OHLC |
|---|---:|---|---|---:|---:|
| SPY | 960 | 2023-01-03 | 2026-10-29 | 0 | 0 |
| QQQ | 960 | 2023-01-03 | 2026-10-29 | 0 | 0 |
| IWM | 960 | 2023-01-03 | 2026-10-29 | 0 | 0 |
| TLT | 960 | 2023-01-03 | 2026-10-29 | 0 | 0 |
| GLD | 960 | 2023-01-03 | 2026-10-29 | 0 | 0 |

Prices are raw `Open`/`Close`; no dividend adjustment over the short 1/5-day
window. Yahoo data remains research-only with redistribution unspecified and
is stored in a local proxy directory, not committed raw.

## 2. Event and trading rules

```text
event type: FOMC statement
release time: 2:00 p.m. ET
entry: event at/after open -> next session open
+1: close of entry+1 session
+5: close of entry+5 session
cost: 5 bps one-way, 10 bps round-trip
```

No overlapping 20-day windows are expected because FOMC meetings are spaced
weeks apart. All 24 entry dates are unique.

## 3. Actual results

Mean returns, net of 10 bps round-trip:

| Proxy | n | Unique entries | Gross +1 | Net +1 | Gross +5 | Net +5 | Baseline +1 | Baseline +5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SPY | 24 | 24 | -0.118% | -0.218% | +0.141% | +0.041% | +0.106% | +0.398% |
| QQQ | 24 | 24 | -0.066% | -0.166% | +0.277% | +0.177% | +0.138% | +0.548% |
| IWM | 24 | 24 | -0.191% | -0.291% | -0.484% | -0.584% | +0.040% | +0.211% |
| TLT | 24 | 24 | +0.127% | +0.027% | -0.697% | -0.797% | -0.013% | -0.101% |
| GLD | 24 | 24 | -0.071% | -0.171% | -0.228% | -0.328% | +0.132% | +0.612% |

Observations:

- No proxy has a positive net +1 result.
- QQQ has a positive net +5, but it is below its unconditional baseline.
- TLT +1 is positive but small; +5 strongly negative.
- IWM and GLD are negative at both horizons.
- The event sample is 24 observations; no statistical significance is claimed.

## 4. Event-type and PIT limits

- Only FOMC statements; the 2025 longer-run-goals strategy statement is
  excluded, not mixed with rate decisions.
- Publication timestamps are exact but **not historical first-seen**. No PIT.
- No intraday data; entry is next open (2 p.m. release is after open).
- Event news and market reaction may overlap; no causal attribution.
- Sample 2023鈥?025 only; no 2026 FOMC statement was present in the existing
  2026 index.

## 5. Existing other directions audited

| Direction | Existing code/data | Status |
|---|---|---|
| SEC filings | `tools/research/sec_event_collector.py` and `pit_sec_edgar.py` | Has `first_seen`, but requires a real contact User-Agent; not run this round |
| Earnings events | `earnings_surprise_recon.py` | Existing, but no end-to-end event timestamp validation this round |
| Fed macro | Fed timed events + this study | **Selected and run** |

Fed was selected because timestamps are public, exact, and machine-readable;
SEC/earnings require additional identity/acceptance-time validation.

## 6. Conclusion

FOMC event study is feasible as a **descriptive, retrospective** exercise.
The current evidence does **not** support a deployable event alpha:

- 24 events only;
- no net positive +1 across proxies;
- +5 results are below unconditional baselines where positive;
- no PIT first-seen;
- no intraday reaction measurement.

Do not promote to a strategy. A next-stage validation would need more events,
PIT capture, and pre-registered event/entry rules.

## 7. Artifacts

- event source: `docs/research/fomc_2023_2025_timed_2026-10-29.json`
- proxy audit: `docs/research/proxy_source_audit_2026-10-29.json`
- event results: `docs/research/fomc_event_study_2026-10-29.json`
- event detail: `docs/research/fomc_event_study_2026-10-29_events.csv`
- code: `tools/research/fomc_event_study.py`
- tests: `tests/test_fomc_event_study.py`
