# Unified Selection V1.1.1 — Effective Peer Gate & Traceability Fix

Date: 2026-11-26
PR #632

## Effective peer sample gate

Before:

- `group_n` = all securities in comparable group.
- 23 groups with total n >= 20.
- 517 rows received a group rank.

After:

- `group_total_n` = all securities in group.
- `group_eligible_n` = rows with all 4 dimensions and rankable status.
- Rank gate requires `group_eligible_n >= 20`.
- 30 comparable groups total.
- **6** groups have eligible n >= 20.
- **491** rows receive `group_rank` / `research_rank`.
- 5,109 rows are `NOT_COMPARABLE`.

No threshold was lowered and no missing data was imputed.

### Group distribution after

Largest eligible groups:

| Group | Total | Eligible |
|---|---:|---:|
| COMMON TECHNOLOGY STANDARD | 750 | 131 |
| COMMON OTHER_SERVICES STANDARD | 758 | 98 |
| COMMON INDUSTRIALS STANDARD | 559 | 86 |
| COMMON HEALTHCARE STANDARD | 901 | 73 |
| COMMON CONSUMER_DISCRETIONARY STANDARD | 330 | 63 |
| COMMON MATERIALS STANDARD | 304 | 40 |

Consumer Staples has total 154 but eligible 18, so it gets **no** rank.
This is the intended effective-peer gate.

## Tier changes

| Group | Before | After |
|---|---:|---:|
| TIER_A | 40 | 30 |
| TIER_B | 106 | 90 |
| TIER_C | 2,876 | 2,902 |
| BLOCKED | 2,578 | 2,578 |
| Total | 5,600 | 5,600 |

## Traceability cleanup

`fundamental_source`, `fiscal_period`, `filing_date`, `accession` now pass
through a cleaner that converts NaN, empty string, and literal "nan" to
`UNKNOWN`.

Unknown counts:

- fundamental_source: 303
- fiscal_period: 246
- filing_date: 246
- accession: 246

No filing date/accession was inferred. Quality source URL remains UNKNOWN where
the source file has no URL.

## Display / semantic honesty

- `composite_score` remains `DISPLAY_ONLY`; Trend is still a global percentile.
- Global composite is not restored as valid rank; `legacy_research_rank` is
  diagnostic only.
- `research_rank` is group rank and only for eligible-peer groups.
- Page shows `group_total_n / group_eligible_n / group_rank`, `composite_status`,
  raw metrics, source/filing/accession, adjustment and CA.
- PE, forward EPS, PEG remain UNAVAILABLE; no derivation.

## Tests

Updated/added tests cover:

- group total >=20 but eligible <20 → no rank;
- eligible >=20 → ranks allowed;
- all NOT_COMPARABLE rows have empty rank;
- TIER_A requires eligible n>=20, 4 dims, rank <=5, no risk;
- tier sum 5,600;
- traceability no NaN/empty/"nan" strings;
- PE/forward unavailable;
- JSON/SHA row count and page fail-closed.

## Output SHA

`dashboard/data/unified_selection_v1_1.json`:
`ef6f8c00fa94f023409f53158d1cdd6ce347b8dfac9b74619426077bf7139e50`

## Limits

- Trend remains global; group composite is display-only, not a validated
  industry-neutral score.
- 5,109 rows remain not comparable.
- No PIT, no unadjusted-price correction, no return validation.

## Production

No Scan/Review/Evolve/score/ATR/stop/ledger/PAPER/IBKR changes. PR #630
untouched.
