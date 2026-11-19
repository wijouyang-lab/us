# P12.5.1 Official BLS Macro Event Recovery

Date: 2026-11-19
Branch: `research/macro-cross-sectional-equity-response`
Base HEAD: `747e44976a3081eeb89f48132d37cf6b34671592`
Status: **PARTIAL — dates/initial values recovered; official embargo times not**.

## 1. BLS official access

Programmatic requests (requests/curl, normal UA, no proxy, no identity spoofing):

| URL | status |
|---|---:|
| `https://www.bls.gov/bls/news-release/cpi.htm` | 403 |
| `https://www.bls.gov/bls/news-release/empsit.htm` | 403 |
| `https://www.bls.gov/news.release/archives/cpi_01182007.htm` | 403 |
| `https://download.bls.gov/pub/news/release/cpi.nr0.htm` | 403 |

No BLS HTML/PDF release body was available. Therefore no per-release embargo
time was extracted, and no 08:30 ET assumption was applied.

## 2. ALFRED recovery

Used ALFRED's public download form with all vintage dates, no API key. Raw ZIPs
were kept under local `data/_download/alfred/` and are not committed.

| Series | ALFRED vintages | First vintage | Last vintage |
|---|---:|---|---|
| CPIAUCSL | 671 | 1972-07-21 | 2026-11-10 |
| CPILFESL | 671 | 1972-07-21 | 2026-10-14 |
| PAYEMS | 861 | 1955-05-06 | 2026-11-06 |
| UNRATE | 801 | 1960-03-15 | 2026-11-06 |
| CES0500000003 | 188 | 2011-03-04 | 2026-11-06 |

For each observation, initial release is the first non-null vintage cell.
Revisions are retained in the panel but never overwrite the initial value.

## 3. Recovered event table

Output: `data/research/macro_cross_sectional/bls_macro_events.csv`

| family | events | years | initial value coverage |
|---|---:|---:|---:|
| CPI | 237 | 20 (2007–2026) | 99.16% headline MoM, 99.16% core MoM |
| Employment | 237 | 20 (2007–2026) | 99.58% payroll change, 100% unemployment |
| **Total** | **474** | | |

- `initial_headline_value`: CPI MoM SA, percent, from first vintage.
- `initial_core_value`: core CPI MoM SA, percent.
- `initial_payroll_change`: PAYEMS change, thousands, same vintage.
- `initial_unemployment_rate`: UNRATE, percent.
- `initial_earnings_mom/yoy`: AHE, percent; only 187 events because
  CES0500000003 vintage history starts 2011.
- `reference_period` is the observation month, never the release date.
- `release_date` is the ALFRED vintage date.
- `embargo_time_local`, `scheduled_release_time`, `actual_publication_time`
  are blank: official time evidence is missing.
- `timestamp_precision=date_only`, `timestamp_confidence=none`.

## 4. 2025/2026 special audit

ALFRED dates show:

- CPI 2025-10 report: **missing**; next CPI is 2025-12-18 (reference 2025-11).
- Employment 2025-10 report: **missing**; 2025-09 Employment released
  2025-11-20.
- CPI 2025-09 released 2025-10-24 (delayed).
- No synthetic event was created for the missing October reports.

This is consistent with a real release disruption, but without BLS release pages
the exact reason/announcement cannot be independently quoted here.

## 5. Reconciliation with P12.5 old table

| family | old | new | added |
|---|---:|---:|---:|
| CPI | 166 | 237 | +71 |
| Employment | 166 | 237 | +71 |

Old table stopped at 2020-10 with date-only index links. New table extends
through 2026-11 and adds first-vintage values. No old date was deleted without a
replacement event; duplicates were deduplicated by release date.

## 6. Consensus audit

```text
MARKET_CONSENSUS_STATUS = DATA_BLOCKED
```

No free, timestamped pre-release consensus history was found. No current or
post-hoc survey value was relabeled as historical consensus.

## 7. Status

```text
CPI_EVENT_DATA = PARTIAL
EMPLOYMENT_EVENT_DATA = PARTIAL
CPI_EXACT_EMBARGO_TIME_COVERAGE = 0%
EMPLOYMENT_EXACT_EMBARGO_TIME_COVERAGE = 0%
CPI_INITIAL_VALUE_COVERAGE = 99.16%
EMPLOYMENT_INITIAL_PAYROLL_COVERAGE = 99.58%
ALFRED_VINTAGE_COVERAGE = 100% of downloaded series
MARKET_CONSENSUS = DATA_BLOCKED
```

Precise intraday event studies remain blocked. Date-level initial-value event
studies are possible, but must be labeled date-only and cannot claim 08:30 ET.

## 8. Tests and reproducibility

```text
tests/test_p12_5_1_bls_recovery.py  5 passed
python tools/research/bls_alfred_recovery.py
python tools/research/bls_build_events.py
python tools/research/bls_audit.py
```

- EST embargo conversion: 08:30 -> 13:30 UTC.
- EDT embargo conversion: 08:30 -> 12:30 UTC.
- date-only input yields no inferred time.
- reference period is not release date.
- first vintage is not overwritten by later revision.

## 9. Files

- `tools/research/bls_alfred_recovery.py`
- `tools/research/bls_build_events.py`
- `tools/research/bls_audit.py`
- `tests/test_p12_5_1_bls_recovery.py`
- `data/research/macro_cross_sectional/bls_macro_events.csv`
- `data/research/macro_cross_sectional/alfred_initial_values.csv`
- `data/research/macro_cross_sectional/bls_event_coverage_audit.json`
- `data/research/macro_cross_sectional/alfred_vintage_audit.json`
- `data/research/macro_cross_sectional/bls_source_manifest.json`

No model call, no API key, no broker, no order.
