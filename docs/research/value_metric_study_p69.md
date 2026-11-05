# Standalone Value Metric Study — P6.9

Date: 2026-11-05
Branch: `research/value-metric-study-p69`
Status: **CROSS-SECTIONAL METRIC STUDY — no composite score, no backtest**

## 1. Pool

| Metric | Count |
|---|---:|
| Common + ADR target | 5,502 |
| P6.8 `VALUE_V1_DATA_READY` | **2,529** |
| Candidate unique CIKs | **2,529** |
| Duplicate-CIK candidate securities | **0** |
| ADR candidates | 0 |

All ranked observations come from P6.8-validated issuer market caps and standard
model families. ADR, share-class-unverified, market-cap-conflict and missing-cap
records stay outside the ranking pool.

## 2. Metric coverage in 2,529 candidates

| Metric | Valid securities | Coverage | Ranked unique CIKs |
|---|---:|---:|---:|
| PE | 1,314 | **51.96%** | 1,224 |
| P/B | 2,272 | **89.84%** | 2,222 |
| P/S | 2,266 | **89.60%** | 2,215 |
| Earnings Yield | 2,506 | **99.09%** | 2,451 |
| FCF Yield | 2,170 | **85.80%** | 2,118 |

`Earnings Yield` has the largest coverage and fewest missing values. `PE` is the
most limited because it requires positive Net Income.

## 3. Intersection

| Intersection | Unique issuers |
|---|---:|
| All five metrics | **992** |
| Four of five | 1,051 |
| Three of five | 392 |

A model requiring all five metrics would fall from 2,529 to **992** issuers
(39.2% of candidates).

## 4. By type and accounting

| Type | Securities | PE | PB | PS | Earnings Yield | FCF Yield |
|---|---:|---:|---:|---:|---:|---:|
| Common | 2,529 | 1,314 | 2,272 | 2,266 | 2,506 | 2,170 |
| ADR | 0 | 0 | 0 | 0 | 0 | 0 |

| Accounting | Securities | PE | PB | PS | Earnings Yield | FCF Yield |
|---|---:|---:|---:|---:|---:|---:|
| US GAAP | 2,430 | 1,253 | 2,179 | 2,177 | 2,407 | 2,085 |
| IFRS | 99 | 61 | 93 | 89 | 99 | 85 |

IFRS and US GAAP are ranked separately.

## 5. By model family

| Family | Securities | PE | PB | PS | Earnings Yield | FCF Yield |
|---|---:|---:|---:|---:|---:|---:|
| TECHNOLOGY | 512 | 270 | 465 | 501 | 508 | 461 |
| HEALTHCARE | 657 | 167 | 583 | 478 | 653 | 598 |
| INDUSTRIALS | 405 | 280 | 382 | 391 | 398 | 320 |
| OTHER_SERVICES | 354 | 234 | 305 | 327 | 350 | 285 |
| CONSUMER_DISCRETIONARY | 234 | 167 | 203 | 230 | 233 | 203 |
| MATERIALS | 211 | 106 | 202 | 188 | 209 | 170 |
| CONSUMER_STAPLES | 96 | 58 | 82 | 91 | 95 | 83 |
| COMMUNICATIONS | 60 | 32 | 50 | 60 | 60 | 50 |

Special families (Banks, Insurance, REIT, BDC, Other Financials, Utilities,
Energy, Unclassified) are not in this standard-pool table.

## 6. PE and Earnings Yield redundancy

For positive-earnings companies:

```text
Earnings Yield = 1 / PE
```

Observed Spearman correlation:

```text
PE vs Earnings Yield = -1.000
```

This is not two independent signals. A future Value composite must not assign
both full independent weights. PE requires positive earnings; Earnings Yield can
also include losses, which changes the sample but not the reciprocal identity
for profitable companies.

## 7. Correlation matrix (Spearman, unique issuer values)

| | PE | PB | PS | Earnings Yield | FCF Yield |
|---|---:|---:|---:|---:|---:|
| PE | 1.000 | 0.373 | 0.375 | **-1.000** | -0.276 |
| PB | 0.373 | 1.000 | 0.485 | 0.207 | 0.167 |
| PS | 0.375 | 0.485 | 1.000 | -0.072 | -0.251 |
| Earnings Yield | -1.000 | 0.207 | -0.072 | 1.000 | 0.615 |
| FCF Yield | -0.276 | 0.167 | -0.251 | 0.615 | 1.000 |

PB and PS are moderately related (0.485). Earnings Yield and FCF Yield are
positively related (0.615), but not identical. PE is the reciprocal of Earnings
Yield.

## 8. Winsorization sensitivity

| Metric | Value |
|---|---:|
| Ranked metric-observations | 10,230 |
| Mean absolute rank change after 1%/99% winsorization | **0.0057** |
| 95th percentile change | **0.0** |
| Maximum change | **0.4975** |

Winsorization has almost no rank impact in these groups. Raw values are still
retained separately.

## 9. Extremes and anomalies

| Metric | N | Min | Q1% | Q99% | Max | Outside winsor |
|---|---:|---:|---:|---:|---:|---:|
| PE | 1,314 | 0.0049 | 0.366 | 21,000.4 | 64,224,451 | 28 |
| PB | 2,272 | 0.0104 | 0.104 | 75.81 | 3,766.8 | 46 |
| PS | 2,266 | 0.0011 | 0.0438 | 2,283.6 | 14,485.7 | 46 |
| Earnings Yield | 2,506 | -6,318,354 | -10.41 | 1.29 | 204.9 | 52 |
| FCF Yield | 2,170 | -45.58 | -5.05 | 0.597 | 9.32 | 44 |

Anomalies retained but winsorized for ranking:

- negative earnings: **1,190** candidates;
- negative/zero equity: **254**;
- negative FCF: **921**;
- provider PE mismatch >20% among candidates: **748**;
- distinct financial periods: **178**.

The extreme PE/EY values are driven by near-zero earnings or equity and must not
be used as raw rankings without winsorization.

## 10. Winsorization and raw ranks

Each security row retains:

```text
raw metric
winsorized metric
raw percentile
winsorized percentile
metric status
```

`METRIC_RANK_AVAILABLE`: **2,474** target securities.
`INSUFFICIENT_PEER_GROUP`: **55** target securities.
`METRIC_BLOCKED`: 2,973 target securities (mostly outside the P6.8 candidate pool).

No `VALUE_V1_COMPOSITE_SCORE`, `SCORE_READY` or `BACKTEST_READY` is produced.

## 11. Which metrics are suitable for next stage

Strongest standalone coverage:

1. **Earnings Yield — 99.09%**, includes losses, but highly redundant with PE;
2. **P/B — 89.84%**;
3. **P/S — 89.60%**;
4. **FCF Yield — 85.80%**;
5. **PE — 51.96%**, positive-earnings only.

A next-stage single-metric study should start with **Earnings Yield** for
coverage, while using PE only as its positive-earnings equivalent. P/B and P/S
are the next most complete standalone candidates.

## 12. Industry comparability

Standard families have enough observations, but:

- current SIC is a non-PIT industry proxy;
- SIC is not GICS;
- Banks, Insurance, REIT, BDC, Other Financials, Utilities and Energy remain
  outside the standard peer groups;
- Healthcare has low PE coverage (167/657) because many issuers are loss-making;
- Technology and Industrials have better positive-earnings coverage.

No cross-industry raw ranking is used; all ranks are within
`model_family × accounting_standard`.

## 13. Conclusion

- Five metrics are measurable but have very different coverage: **51.96% to
  99.09%**.
- Only **992** candidates have all five metrics.
- PE and Earnings Yield are not independent (Spearman **-1.000**).
- Winsorization is not a major rank driver (mean change 0.0057).
- There is **not enough evidence to assign Value V1 composite weights**.
- The next study should be metric-specific, starting with Earnings Yield, with
  P/B/P/S/FCF as separate diagnostics.

No production score or trading use.
