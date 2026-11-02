# Macro Event Response Study

Date: 2026-11-03
Status: **DATA_BLOCKED / INCONCLUSIVE**
Branch: `research/macro-event-response`

## 1. Decision first

The fixed 2007-2026 three-family study **was not run**, because official BLS
release timestamps for 2021-2026 could not be retrieved and the archived BLS
pages cover only 2007-2020. Running the 15-test family on a truncated sample
would violate the pre-specified window and the 2021-2026 stability requirement.

No empirical result is reported. **This is not a PASS and not a FAIL of the
market hypothesis; it is a data-availability block.**

## 2. Scope and sources

Families:

```text
BLS Consumer Price Index
BLS Employment Situation
Federal Reserve FOMC Statement
```

Official sources:

- BLS CPI archive: https://www.bls.gov/bls/news-release/cpi.htm
- BLS Employment archive: https://www.bls.gov/bls/news-release/empsit.htm
- Fed FOMC historical: https://www.federalreserve.gov/monetarypolicy/fomc_historical.htm
- Fed FOMC calendar: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

Access results:

| Source | HTTP | Result |
|---|---:|---|
| BLS CPI archive, live | **403** | Akamai bot block |
| BLS Employment archive, live | **403** | Akamai bot block |
| BLS CPI GPO archive | 200 | coverage through 2020 |
| BLS Employment GPO archive | 200 | coverage through 2020 |
| Fed FOMC historical pages 2007-2020 | 200 | statements available |
| Fed FOMC current calendar 2021-2026 | 200 | statements available |

The live BLS 403 is recorded in `audit.json`; it was not bypassed with Yahoo
Finance headlines or unverified aggregators.

## 3. Event inventory and coverage

The audit built **500 official events**:

```text
CPI       166
Employment 166
FOMC      168
```

All 500 have a valid XNYS tradable session under the pre-specified alignment
rule (`ALIGNED`).

Coverage by year:

| Year | CPI | Employment | FOMC |
|---:|---:|---:|---:|
| 2007 | 12 | 12 | 9 |
| 2008 | 12 | 12 | 9 |
| 2009 | 12 | 12 | 8 |
| 2010 | 12 | 12 | 9 |
| 2011 | 12 | 12 | 8 |
| 2012 | 12 | 12 | 8 |
| 2013 | 12 | 12 | 8 |
| 2014 | 12 | 12 | 8 |
| 2015 | 12 | 12 | 8 |
| 2016 | 12 | 12 | 8 |
| 2017 | 12 | 12 | 8 |
| 2018 | 12 | 12 | 8 |
| 2019 | 12 | 12 | 9 |
| 2020 | 10 | 10 | 12 |
| 2021 | **0** | **0** | 8 |
| 2022 | **0** | **0** | 8 |
| 2023 | **0** | **0** | 8 |
| 2024 | **0** | **0** | 8 |
| 2025 | **0** | **0** | 9 |
| 2026 | **0** | **0** | 7 |

The GPO snapshot ends in October 2020, so 2020 also lacks the last two BLS
releases. FOMC coverage is complete for 2007-2026.

## 4. Timestamp status

Every event has:

```text
event_id
event_type
official_source
official_source_url
publication_date
publication_time
timezone
publication_time_utc
reference_period
source_retrieved_at_utc
source_content_sha256
timestamp_confidence
verification_status
time_type
tradable_session
```

Important limitation:

- the archived BLS index gives the **release date** from the filename;
- 08:30 ET is recorded as the **scheduled standard time**, not a verified
  per-release actual timestamp;
- FOMC 14:00 ET is recorded as the **scheduled policy-release time**, not a
  verified actual second-level timestamp;
- `time_type` therefore says `scheduled_standard` or
  `scheduled_policy_release`, not `actual`;
- for BLS, the source content hash is the **archive-index** hash, not the hash
  of each individual news release; `hash_scope` records this.

These limitations are exactly why the study was not promoted to a precise
intraday event study.

## 5. Session alignment

Rule:

- BLS 08:30 ET is before the 09:30 open 鈫?same XNYS session;
- FOMC 14:00 ET is after the open 鈫?**next** XNYS session;
- weekend/holiday 鈫?next XNYS session;
- `date_only` events are kept separate and are not used for precise-time tests.

All available events aligned, but this alignment is **calendar-scheduled**, not
verified against actual publication seconds.

## 6. Why the empirical study was stopped

Required for the pre-specified study:

1. three families over 2007-2026;
2. date and time completeness;
3. official timestamps;
4. 15-test family with 3D primary;
5. three fixed periods including 2021-2026.

Actual:

- CPI: 0 events in 2021-2026;
- Employment: 0 events in 2021-2026;
- FOMC: full;
- live BLS pages: 403;
- no verified actual BLS times.

Filling the BLS gap from FRED, Yahoo, or news headlines would violate the
official-source and no-substitution rules. Therefore:

```text
study_status = NOT_RUN_DATA_BLOCKED
```

No event-study CSV, no HAC/BH table, no NAV, no 鈥渨hich event matters鈥?ranking is
reported. Reporting one from a truncated sample would be data dredging.

## 7. Required questions

1. **Is data sufficient?**
   No. BLS CPI and Employment are missing 2021-2026, and actual BLS timestamps
   are not verified.

2. **Which macro event has the largest effect?**
   Not determined. The study was not run.

3. **Is the direction consistent?**
   Not determined.

4. **Is the effect concentrated in volatility rather than direction?**
   Not determined.

5. **Is there an out-of-sample opportunity?**
   No claim. There is no empirical result to validate.

6. **PASS, FAIL or INCONCLUSIVE?**
   **INCONCLUSIVE / DATA_BLOCKED.** This is not evidence for or against the
   macro-event hypothesis.

## 8. What would unblock the study

One of:

1. official BLS archived release pages for 2021-2026 with retrievable publication
   timestamps;
2. an approved BLS data-access path that returns release timestamps;
3. a documented official historical release-time dataset;
4. a revised pre-specified window ending in 2020, approved before looking at
   results, with the 2021-2026 period explicitly out of scope.

Only after that should the frozen 15-test family, matched non-event controls,
HAC/BH, and daily NAV be run.

## 9. Engineering and isolation

- Code: `tools/research/macro_event_response.py`
- Coverage chart: `tools/research/plot_macro_coverage.py`
- Tests: `tests/test_macro_event_response.py` (6 passed)
- Events: `data/research/macro_event_response/events.csv`
- Alignment: `data/research/macro_event_response/session_alignment.csv`
- Audit: `data/research/macro_event_response/audit.json`
- Hash manifest: `data/research/macro_event_response/manifest.json`
- Chart: `data/research/macro_event_response/coverage.svg`

No production Scan/Scoring/ATR/Stop changes. No Portfolio-50000 or generic paper
changes. No IBKR connection or orders. PR #441 remains Draft/Open and its
prospective account remains NOT_STARTED. PR #443 and #444 are not merged.
