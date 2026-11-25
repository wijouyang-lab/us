# FS2.1 Decision Consistency Audit

Date: 2026-11-25
PR #630

## 1. Tier × Tradability matrix (5,600 rows)

| Tradability | TIER_1 | TIER_2 | WATCH | BLOCKED |
|---|---:|---:|---:|---:|
| ELIGIBLE_FOR_RESEARCH | 343 | 888 | 1,543 | 0 |
| WATCH | 0 | 0 | 248 | 0 |
| INSUFFICIENT_DATA | 0 | 0 | 480 | 0 |
| BLOCKED | 0 | 0 | 0 | 2,098 |
| **Total** | **343** | **888** | **2,271** | **2,098** |

Rules verified:

- BLOCKED never enters TIER_1/TIER_2.
- INSUFFICIENT_DATA never enters TIER_1/TIER_2.
- TIER_1 all have style_count ≥2 and ELIGIBLE.
- TIER_2 all have style_count ≥1 and ELIGIBLE.
- Every row has exactly one tradability status.
- 5,600 unique tickers, 0 duplicates.

## 2. CA discrepancy 470 vs 850

Root cause found and fixed:

- FS-2 originally checked CA before “missing price”, and treated missing
  `corporate_action_status` as CA failure.
- This inflated CA blocked to 850.
- Correct order: CA block first only if status is actually
  `CORPORATE_ACTION_REVIEW`; missing price is INSUFFICIENT_DATA.

Current:

```text
FS-1 CA flags: 470
FS-2 CA blocked: 469
unmatched: 1 ticker absent from 5,600 composite identity
missing price: 579
  of which CA status known: 99 (blocked CA)
  of which no CA status: 480 (INSUFFICIENT_DATA)
```

No CA flag was released.

## 3. 579 missing price classification

```text
5,600 identity rows - 5,021 with 20D price = 579
  PRICE_20D_MISSING/INSUFFICIENT_DATA: 480
  CA-blocked with no price:              99
```

No ticker is described as “no price” if it merely has <20D; the code checks
price presence and length separately.

## 4. Candidate completeness

- ticker unique: 5,600
- duplicate ticker: 0
- duplicate CIK allowed only for multiple share classes; no automatic merge
- ADR: 237 WATCH, separate from COMMON
- ETF/preferred/UNCLASSIFIED: BLOCKED via identity
- missing style: NaN, never 0; style_count counts only true top20 flags
- Trend: raw price only, labelled `RAW_PRICE_RESEARCH_ONLY` in docs
- no future price used in trend computation (trailing windows)

## 5. Website

- New `terminal/candidates.html` loads `dashboard/data/fs2_candidates_v1.json`.
- Full 5,600 rows, filters for style/tier/tradability/type/industry/liquidity,
  search, sorting, pagination, detail panel.
- Missing values displayed as “—”, not 0.
- No BUY labels.
- Link added in `terminal.html`.
- Static-only; no live server test or public deployment verification.

## 6. Remaining gaps

- Website is not deployed/verified on GitHub Pages.
- 26 behavior tests not reached; current suite is 8 + new audit tests.
- Fundamentals as-of 2026-11-05, prices 2026-11-25.
- Prices unadjusted; CA unresolved.
