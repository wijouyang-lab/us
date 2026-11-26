# FS2.3 Data & Manifest Audit

Date: 2026-11-26

## Price coverage recomputed from files

From `data/universe/price_liquidity/download_status_v1.csv`:

```text
identity rows      5,615
VALID tickers      5,600
COMMON             5,187
ADR                  315
download universe  5,501
SUCCESS            5,044
NO_DATA              457
20D                5,021
60D                4,975
```

| Group | 20D | Coverage |
|---|---:|---:|
| COMMON | 4,750 / 5,186 | 91.59% |
| ADR | 271 / 315 | 86.03% |
| COMMON+ADR | 5,021 / 5,501 | 91.28% |

457 NO_DATA are not classified as delisted and are not imputed.  
470 CA flags are unconfirmed price jumps, not confirmed splits.  
Prices remain unadjusted; no total-return claim.

## FS2 final counts

From `composite_candidates_v1.csv`:

```text
rows                 5,600
TIER_1                 343
TIER_2                 888
WATCH                2,271
BLOCKED              2,098
ELIGIBLE             2,774
CA blocked             469
CA + identity block      1 (SAEN)
NO_PRICE_HISTORY       556
LESS_THAN_20D           23
20D_TO_59D              46
60D_AVAILABLE        4,975
```

The earlier methodology counts 1,890/2,479/850 were from the pre-fix
version where missing price was misclassified as CA; they are superseded.

## Manifest

`schema_version: 2`; current `fs2.v1.4`; previous `fs2.v1.3`.
Formal SHA of current JSON matches manifest. Browser loads manifest, verifies
SHA/row count/unique ticker, falls back to previous with STALE banner, and fails
closed if neither verifies.
