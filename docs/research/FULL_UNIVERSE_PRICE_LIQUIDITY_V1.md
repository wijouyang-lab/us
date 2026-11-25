# Full-Universe Price & Liquidity V1

Date: 2026-11-25
Branch: `research/full-universe-price-liquidity-v1`
Status: **PARTIAL** — full 5,615 universe cache not completed

## 1. Actual results

### P0 identity

```text
raw issuer rows:       5,615
unique ticker rows:    5,614
unique CIKs:           5,548
COMMON:                5,187
ADR:                     315
UNCLASSIFIED:            113
mapping HIGH:          5,593
mapping LOW:              22
```

All 5,615 are `CURRENT`. Identity is issuer-level, not a legal share-class
master; 22 low-confidence rows are not used for execution.

### P1 provider sample

Stratified sample: 36 tickers (12 each COMMON / ADR / UNCLASSIFIED).

```text
yfinance success: 36/36
```

This sample is too small to claim full-market coverage. It does show the free
provider can return 20+ sessions for the sampled names when the yfinance timezone
cache is pointed at a writable directory.

### P2 full market cache

The full 5,453-name batch run failed during a yfinance batch because a
non-string ticker reached `is_isin()`; no full-market cache file was produced.
The failed run is recorded, not hidden.

Only the Top100 union was acquired:

```text
top100 union: 285 tickers
yfinance rows: 71,535
success: 285/285
period: ~1 year
```

This is **285 / 5,615 ≈ 5.1%** of the identity universe, not 90%.

### P3 ADV / corporate action

From the 285-ticker cache:

```text
valid_days >= 20: 285
CORPORATE_ACTION_REVIEW: 22
ADV20/ADV60 computed from raw_close × raw_volume
```

22 flags are suspicious >50% raw-close moves, likely splits or bad prints.
They are BLOCKED pending review, not silently adjusted.

### P4 Top100 on-demand

Three strategy Top100 union = 285 tickers. All 285 have price and ADV.

```text
ELIGIBLE: 198
WATCH:     26
BLOCKED:   61
```

This verifies ranks 51–100 can be acquired on demand; the prior 144-ticker
Top50 snapshot was not the source.

## 2. Data coverage conclusion

- Full universe price cache: **NOT COMPLETE**.
- Top100 union: **COMPLETE (285/285)**.
- Full market coverage: **5.1% of identity rows**, not 90%.
- The 90% gate is not met.
- No paid vendor used.
- No production or PAPER changes.

## 3. Why the full batch failed

`yf.download` received a float ticker after the universe read path; `re.match`
in yfinance raised `TypeError: expected string or bytes-like object, got 'float'`.
The batch exception aborted the cache run before any full file was written.
The fix is to filter non-string/NaN tickers before batch construction and wrap
each batch in retry/error isolation. This is not yet implemented.

## 4. Files

- `tools/investment_research/price_liquidity/identity.py`
- `tools/investment_research/price_liquidity/provider.py`
- `tools/investment_research/price_liquidity/run.py`
- `data/universe/price_liquidity/universe_identity_v1.csv`
- `provider_coverage_v1.csv`
- `top100_cache_v1.csv`
- `liquidity_metrics_v1.csv`
- `corporate_action_audit_v1.csv`
- `top100_coverage_audit_v1.csv`

## 5. Completion

| Item | Weight | Status | Completion |
|---|---:|---|---:|
| P0 identity | 10% | done | 10% |
| P1 provider sample | 15% | partial | 8% |
| P2 full cache | 25% | failed/partial | 5% |
| P3 ADV/CA | 20% | partial (285) | 10% |
| P4 Top100 | 15% | done | 15% |
| P5 tests/report/CI | 15% | partial | 5% |
| **Total** | **100%** | **PARTIAL** | **53%** |

Remaining 47%; no claim of full-market coverage.
