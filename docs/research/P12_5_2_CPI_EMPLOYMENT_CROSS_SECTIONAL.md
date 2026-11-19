# P12.5.2 ALFRED PIT Correction and CPI/Employment Research Gate

Date: 2026-11-19
Branch: `research/macro-cross-sectional-equity-response`
Base HEAD: `9ffd458402aa8bcfe50b4bb47cf0a1f710ca85a6`
Status: **DATA_FIXED_PARTIAL · EQUITY_GATE = DATA_BLOCKED · NO EMPIRICAL ALPHA CLAIM**

## 1. ALFRED observation window fix

The recovery window was extended from `2007-01-01` to `2006-01-01` so the
2006-12 reference month is available for the first 2007 releases.

Recovered:

- CPI 2007-01-18, reference 2006-12, initial headline MoM +0.545%.
- Employment 2007-01-05, reference 2006-12, initial payroll change +167k.

Both were previously missing. The target event range remains 2007-01-01 to the
latest recovered release; the 2006 warm-up rows are not counted as events.

## 2. Same-vintage calculation fix

`initial_events()` now stores, for the **first vintage column** of each
observation:

```text
initial_value
prior_value_same_vintage
prior_year_value_same_vintage
vintage_column
vintage_index
```

The builder computes:

```text
MoM = current / prior_month_same_vintage - 1
YoY = current / prior_year_same_vintage - 1
```

It no longer looks up the year-ago value using that older observation's own
first vintage. `PAYEMS` change is current PAYEMS minus the prior-month PAYEMS
**as revised in this same release vintage**, not the prior month's first print.

## 3. Rebuilt event data

| family | events | years | initial coverage |
|---|---:|---:|---:|
| CPI | 238 | 2007–2026 | 237/238 headline MoM; 237/238 core MoM |
| Employment | 238 | 2007–2026 | 238/238 payroll change; 238/238 unemployment |
| **Total** | **476** | | |

Earnings MoM/YoY coverage is lower because `CES0500000003` ALFRED vintages start
in 2011; no pre-2011 earnings values are fabricated.

CPI 2025-10 and Employment 2025-10 remain absent (`NO_RELEASE` / `NOT_COLLECTED`
in the audit), not filled or treated as zero. CPI 2025-11 MoM is not fabricated
from a missing October index.

## 4. Old-table reconciliation

Primary key: `(event_type, release_date)` with `empsit -> employment`.

| check | result |
|---|---:|
| old CPI events | 166 |
| old Employment events | 166 |
| matched old events | **332 / 332** |
| missing_from_new | **0** |
| newly recovered events | **144** |
| duplicate events | **0** |
| date mismatches | **0** |
| reference-period mismatches | **0** |

All old events, including 2007-01-05 and 2007-01-18, now exist in the new table.
The 144 new events are the 2021–2026 extension plus the corrected 2007 start,
net of the two 2025-10 non-releases.

## 5. Source and timestamp status

```text
BLS live HTML/PDF: 403
ALFRED initial vintage: available
ALFRED vintage dates: 671-861 per series
BLS official release-date verification: 0 events
BLS official embargo verification: 0 events
timestamp_precision: date_only
timestamp_confidence: none
```

`release_date` is an ALFRED vintage date, not a BLS news-release body timestamp.
No 08:30 ET value is imputed. `source_manifest` records each series ZIP SHA256
and each output file SHA256.

## 6. Equity price gate

Audited local PIT snapshot (not re-downloaded this round):

| item | result |
|---|---|
| rows | 1,047,578 |
| tickers | 502 |
| date range | 2016-12-12 to 2026-10-13 |
| price field | unadjusted `Price` only |
| Open/High/Low | absent |
| Adj Close | absent |
| split adjustment | absent |
| dividend adjustment | absent |
| PIT membership verified | **NO** |
| delisted-name completeness | **NO** |

Events from 2017 onward: 118 CPI + 118 Employment = 236.  
Events with at least 20 names on the release date: **228**.  
Median names per covered event: **422**.  
Eight events have no same-day snapshot coverage (mostly the 2026 releases after
the snapshot end).

### Gate verdict

```text
EQUITY_PRICE_READINESS = DATA_BLOCKED
```

Reasons:

1. `Price` is unadjusted close; it is not total return.
2. No historical PIT membership/delisting proof; current S&P names cannot be
   backfilled.
3. No Open/High/Low, so next-open fills cannot be modeled.
4. Macro release dates are date-only, so intraday windows cannot be defined.

The task explicitly forbids using this panel to infer tradable Alpha. Therefore
the CPI/Employment cross-sectional model was **not run** and no portfolio/cost
backtest was performed.

## 7. Final decision

```text
CPI_EVENT_DATA = PARTIAL (238 events; initial values 237/238; no embargo time)
EMPLOYMENT_EVENT_DATA = PARTIAL (238 events; initial values 238/238; no embargo time)
MARKET_CONSENSUS = DATA_BLOCKED
EQUITY_PRICE_READINESS = DATA_BLOCKED
STRATEGY_ALPHA_STATUS = DATA_BLOCKED
```

The data infrastructure is materially better: initial values are PIT-correct,
old events are fully reconciled, and missing releases are explicit. The equity
gate is still not satisfied, so no claim about CPI/Employment stock selection is
made.

## 8. Required next data

To proceed to the pilot, obtain:

1. A PIT total-return equity panel with delisted names.
2. Verified event-date membership or an explicit survivorship-bias sensitivity.
3. Open prices for next-session entry, or freeze a close-only entry rule.
4. BLS release bodies/schedules for embargo times, or accept date-only and drop
   intraday claims.

Until then, only descriptive date-level work is allowed.

## 9. Tests and files

```text
tests/test_p12_5_1_bls_recovery.py   5 passed
tests/test_p12_5_macro_research.py   3 passed
```

Files:

- `tools/research/bls_alfred_recovery.py`
- `tools/research/bls_build_events.py`
- `tools/research/bls_audit.py`
- `tools/research/p12_5_2_price_audit.py`
- `tests/test_p12_5_1_bls_recovery.py`
- `data/research/macro_cross_sectional/bls_macro_events.csv`
- `data/research/macro_cross_sectional/alfred_initial_values.csv`
- `data/research/macro_cross_sectional/bls_event_coverage_audit.json`
- `data/research/macro_cross_sectional/alfred_vintage_audit.json`
- `data/research/macro_cross_sectional/bls_source_manifest.json`
- `data/research/macro_cross_sectional/p12_5_2_price_audit.json`

No model call, no API key, no broker, no order.
