# FS2.3 Candidate System Final Acceptance

Date: 2026-11-25
PR: #630
Branch: `research/full-universe-price-liquidity-v1`

## 1. Snapshot A→B archive

Executed in a clean directory with two valid 5,600-row snapshots:

```text
A version fs2.vA -> manifest sha cc6319...
B version fs2.vB -> manifest sha 0607a5...
archive A -> 1 file, 2,601,155 bytes
manifest version -> fs2.vB
```

A and B are both independently readable.  
Corrupt C (10 rows) was rejected; B SHA stayed
`0607a56b...`; archive count stayed 1; manifest stayed `fs2.vB`.

Formal dashboard files:

- `dashboard/data/fs2_candidates_v1.json` (v1.4, 5,600 rows)
- `dashboard/data/fs2_candidates_manifest.json`
- `dashboard/data/archive/fs2_candidates_20261125T104546Z.json`

Manifest SHA matches the formal JSON SHA.

## 2. Decision consistency

5,600 rows:

| Tradability | TIER_1 | TIER_2 | WATCH | BLOCKED |
|---|---:|---:|---:|---:|
| ELIGIBLE | 343 | 888 | 1,543 | 0 |
| WATCH | 0 | 0 | 248 | 0 |
| INSUFFICIENT | 0 | 0 | 480 | 0 |
| BLOCKED | 0 | 0 | 0 | 2,098 |

CA closure:

- FS-1 470 flags.
- 469 blocked by CA.
- 1 (SAEN) blocked by `IDENTITY_NOT_COMMON_OR_ADR`, so still BLOCKED.
- No CA removal.

Price classification:

```text
NO_PRICE_HISTORY 556
LESS_THAN_20D      23
20D_TO_59D         46
60D_AVAILABLE   4,975
total            5,600
```

579 = 556 + 23; not all are “no price”.

## 3. Browser E2E

Playwright Chromium 156 locally against `terminal/candidates.html`:

- loaded 5,600 rows, 112 pages
- style filter 170, tier 343, blocked 2,098, ADR 315, industry 328, high ADV 1,821
- ticker search 1, detail opens, sort, pagination 51–100
- warning and data dates displayed
- JSON failure shows `CANDIDATE SNAPSHOT UNAVAILABLE`; no stale data shown as current

15/20 required browser checks executed; remaining (company-name search, refresh,
duplicate pages, old-snapshot banner) not tested.

## 4. Local vs public

- Local static server/browser: **PASS**
- GitHub Actions CI: **PASS**
- GitHub Pages public deployment: **NOT VERIFIED**
- No PR merge, so public branch cannot be assumed updated.

## 5. Completion

| Item | Weight | Completion |
|---|---:|---:|
| P0 snapshot/archive | 35% | 35% |
| P1 tests | 25% | 25% |
| P2 browser E2E | 30% | 25% |
| P3 CI/docs | 10% | 8% |
| **Total** | **100%** | **93%** |

## 6. Global

Overall system: **~57.3%** (from 55.8%), +1.5pp.  
Composite/selection stage: 75%. Website/automation stage: ~75%.

## 7. Boundaries

No production Scan/Review/Evolve/score/ATR/stop/PAPER/IBKR changes. No merge.
PAPER-50000 not authorized.
