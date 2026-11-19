# Macro Event Response Study

Date: 2026-11-03
Status: **DATA_BLOCKED / INCONCLUSIVE**
Branch: `research/macro-event-response`

## 1. Decision

The fixed 2007-2026 three-family study was **not executed**. The official BLS
live archive returned HTTP 403 in this environment, and the available FDLP
fallback ends in 2020. No 2021-2026 BLS events can be verified without browser
export or an approved access path. Therefore no empirical significance claim,
no NAV, and no 鈥渂est event family鈥?ranking is made.

This is a data-availability block, not evidence for or against the macro-event
hypothesis.

## 2. Sources and access

| Source | HTTP/status | Role |
|---|---:|---|
| `https://www.bls.gov/bls/news-release/cpi.htm` | **403** | primary official CPI index |
| `https://www.bls.gov/bls/news-release/empsit.htm` | **403** | primary official Employment index |
| `https://permanent.fdlp.gov/gpo146835/.../cpi.htm` | 200 | legacy fallback only, through 2020 |
| `https://permanent.fdlp.gov/gpo146835/.../empsit.htm` | 200 | legacy fallback only, through 2020 |
| Fed FOMC historical/current pages | 200 | 2007-2026 statements |

The code tries the **live BLS official archive first**. FDLP is retained only
as a clearly labelled `legacy_fallback_not_complete`. No Yahoo/FRED/news
aggregator was used to fill BLS gaps.

## 3. Event inventory

```text
CPI            166  (2007-2020, date-only index links)
Employment     166  (2007-2020, date-only index links)
FOMC           168  (2007-2026, scheduled 14:00 ET)
Total          500
```

FOMC events have a precise scheduled policy-release time and XNYS alignment.
BLS events from the legacy index have **no parsed per-release embargo time**;
they are marked `date_only` and are excluded from precise-time tests.

Coverage:

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

2025 October BLS release is genuinely absent; it was not synthesized.
2026 coverage stops at 2026-10-30.

## 4. Timestamp and revision status

Every record has:

```text
event_id, event_type, official_source, official_source_url,
publication_date, publication_time, timezone, publication_time_utc,
reference_period, source_retrieved_at_utc, source_content_sha256,
timestamp_confidence, verification_status, time_type,
source_role, hash_scope, tradable_session, alignment_status
```

Current state:

- FOMC: `time_type=scheduled_policy_release`, 14:00 ET, 168 records; each statement page fetched separately with its own SHA-256 (`hash_scope=individual_statement`);
- BLS: `time_type=date_only`, no time, 332 records;
- BLS hashes are **archive-index** hashes, not individual release hashes;
- no actual BLS first-publication second is claimed;
- revision notice parsing is implemented but only applies to imported release
  HTML, not to index-only records.

The code can parse an explicit line such as:

```text
Transmission of material in this release is embargoed until 8:30 a.m. (ET)
```

and convert it with `America/New_York`, correctly handling EST/EDT. This is
tested for 2021 and 2026. No release body was available through the blocked
BLS endpoint, so the current 332 BLS records remain `date_only`.

## 5. Offline import mode

The tool supports browser-saved official HTML:

```bash
python -m tools.research.macro_event_response \
  --offline-dir data/research/macro_event_response/offline
```

`offline/manifest.json` must list `family`, official `url`, and local `path`.
The loader:

- accepts only `www.bls.gov` or `www.federalreserve.gov`;
- computes a separate SHA-256 for each local file;
- parses the saved archive/release HTML;
- records `source_role=offline_manual_official`;
- does not attempt proxy rotation, identity spoofing, or access-control bypass.

## 6. Market data cutoff fix

`audit.json` now records:

```text
end                    = 2026-10-30
market_data_cutoff     = 2026-10-30
market_data_asof       = 2026-10-30
raw_market_max_date    = 2026-11-02
```

SPY/ETF sessions are filtered to `<= 2026-10-30`; 2026-11-02 is excluded from
alignment and from every market response calculation. The raw maximum date is
retained only for audit.

## 7. Readiness

| Requirement | Status |
|---|---|
| CPI full 2007-2026 | **No** |
| Employment full 2007-2026 | **No** |
| FOMC full 2007-2026 | Yes |
| Every precise event has official release page | No (BLS blocked) |
| Individual BLS release SHA-256 | No |
| Duplicate events | 0 |
| Missing months documented | Yes |
| 2021-2026 BLS correctly non-zero | **No, still zero because access is blocked** |
| Market data <= 2026-10-30 | Yes |
| Session alignment | FOMC aligned; BLS date-only |

Final status remains:

```text
DATA_BLOCKED
study_status = NOT_RUN_DATA_BLOCKED
```

## 8. Required answers

1. **Data sufficient?** No. BLS 2021-2026 and per-release timestamps are missing.
2. **Largest macro event effect?** Not determined; no study run.
3. **Direction consistent?** Not determined.
4. **Volatility rather than direction?** Not determined.
5. **Out-of-sample opportunity?** No claim.
6. **PASS/FAIL/INCONCLUSIVE?** **INCONCLUSIVE / DATA_BLOCKED.**

## 9. Deliverables

```text
data/research/macro_event_response/events.csv
data/research/macro_event_response/session_alignment.csv
data/research/macro_event_response/audit.json
data/research/macro_event_response/manifest.json
data/research/macro_event_response/coverage.svg
docs/research/MACRO_EVENT_RESPONSE.md
tools/research/macro_event_response.py
tools/research/plot_macro_coverage.py
tests/test_macro_event_response.py
```

Tests: **9 passed**. Full CI is reported in the PR.

No production Scan/Scoring/ATR/Stop changes. No Portfolio-50000 or generic paper
changes. No IBKR connection or orders. PR #441 remains Draft/Open and its
prospective account remains NOT_STARTED. PR #443 and #444 are not merged.
