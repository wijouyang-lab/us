# Full-Universe Price & Liquidity V1.1

Date: 2026-11-25
Branch: `research/full-universe-price-liquidity-v1`
PR: #630

## 1. Full cache executed

The float-ticker crash was fixed by validating every raw ticker before any
batch:

```text
identity rows:          5,615
VALID:                  5,600
INVALID_SYMBOL_FORMAT:     14
MISSING_TICKER:             1
COMMON:                 5,187
ADR:                      315
UNCLASSIFIED:             113
```

Download universe: 5,501 valid COMMON+ADR tickers.

Batch download used 500-ticker batches, `threads=True`, 6 months, per-batch
isolation, retry and resume. Final cache:

```text
downloaded rows:   704,128
cache tickers:       5,044
NO_DATA:               457
20-valid-day:        5,021 / 5,501 = 91.28%
60-valid-day:        4,975 / 5,501 = 90.44%
```

By security type:

| Type | Tickers | Has 20D | Coverage |
|---|---:|---:|---:|
| COMMON | 5,186 | 4,750 | **91.59%** |
| ADR | 315 | 271 | **86.03%** |
| Total | 5,501 | 5,021 | **91.28%** |

The 90% target is met for active COMMON, not for ADR. It is not a full 100%
claim.

## 2. ADV / corporate actions

```text
CORPORATE_ACTION_REVIEW: 470 / 5,044
```

Flags are based only on an absolute raw-close move >50%; no split/action feed
is available. They remain BLOCKED and are not silently adjusted. All are
`UNCONFIRMED_PRICE_JUMP` pending external evidence.

## 3. Top100 outside ranks

Top100 union: 285 tickers, all 285 have 20D ADV.
Top 101–150 by strategy: 150 rows, **136** have 20D data, **132 ELIGIBLE**,
18 blocked. This proves ranks 51–150 can use the same interface, not only the
old 144 snapshot.

## 4. Free-provider decision

```text
FREE_PROVIDER_PARTIALLY_SUFFICIENT
```

- COMMON 20D coverage **91.59%** meets 90%.
- ADR only **86.03%**.
- 457/5,501 names have no current data.
- 470/5,044 corporate-action flags remain unresolved.
- No paid source; no full-market adjusted prices/actions.

## 5. Completion

| Item | Weight | Status | Completion |
|---|---:|---|---:|
| P0 ticker validation | 15% | done | 15% |
| P1 batch/resume | 25% | done | 25% |
| P2 full download/coverage | 25% | done (with partial ADR) | 23% |
| P3 101+ dynamic | 10% | done | 10% |
| P4 ADV/actions | 10% | partial | 5% |
| P5 tests/CI/report | 15% | partial | 8% |
| **Total** | **100%** | **PARTIAL** | **86%** |

System price-stage completion: **86%** (from 53%).

## 6. Files

- `tools/investment_research/price_liquidity/{identity,batch,run}.py`
- `data/universe/price_liquidity/price_cache_v1.csv.gz`
- `download_universe.csv`
- `download_status_v1.csv`
- `provider_coverage_v1.csv`
- `liquidity_metrics_v1.csv`
- `corporate_action_audit_v1.csv`
- `top100_coverage_audit_v1.csv`
- `top101_150_audit_v1.csv`
- `universe_identity_v1.csv`
