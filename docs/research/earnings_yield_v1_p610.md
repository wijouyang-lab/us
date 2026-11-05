# Standalone Earnings Yield V1 — P6.10

Date: 2026-11-05
Branch: `research/earnings-yield-p610`
Status: **RESEARCH_ONLY — no composite score, no historical backtest**

## 1. Pool and coverage

| Metric | Count |
|---|---:|
| Common + ADR target | 5,502 |
| P6.8 VALUE_V1_DATA_READY | 2,529 |
| Candidate unique CIKs | 2,529 |
| Earnings Yield valid after period gate | **2,504 / 2,529 = 99.01%** |
| Earnings Yield ranked | **2,449** |
| `INSUFFICIENT_PEER_GROUP` | **55** |

All candidates are Common. ADR, market-cap-conflict, share-class-unverified,
missing-cap and special-industry records remain outside the ranking pool.

## 2. Earnings categories

| Category | Count |
|---|---:|
| Positive earnings | **1,272** |
| Negative earnings | **1,151** |
| Zero / near-zero earnings (<0.1% absolute EY) | **81** |
| Net income missing | **23** |
| Financial period after snapshot | **2** |

Negative Earnings Yield is retained. Missing Net Income is blank, never zero.
The two invalid-period records are blocked from ranking.

Distribution:

| Category | Median EY |
|---|---:|
| Positive | 0.0401 |
| Negative | -0.2016 |
| Near-zero | 0.0 |

## 3. Ranking by peer group

Comparisons are within `model_family × accounting_standard`; current SEC SIC is
a non-PIT industry proxy, not GICS.

| Group | Valid issuers | Status | Winsor low | Winsor high |
|---|---:|---|---:|---:|
| TECHNOLOGY / US GAAP | 499 | RANK_AVAILABLE | -6.573 | 0.622 |
| HEALTHCARE / US GAAP | 644 | RANK_AVAILABLE | -25.647 | 2.094 |
| INDUSTRIALS / US GAAP | 381 | RANK_AVAILABLE | -15.785 | 1.069 |
| OTHER_SERVICES / US GAAP | 338 | RANK_AVAILABLE | -6.234 | 0.402 |
| CONSUMER_DISCRETIONARY / US GAAP | 230 | RANK_AVAILABLE | -4.631 | 18.953 |
| MATERIALS / US GAAP | 165 | RANK_AVAILABLE | -4.807 | 0.196 |
| CONSUMER_STAPLES / US GAAP | 93 | RANK_AVAILABLE | -25.313 | 0.292 |
| COMMUNICATIONS / US GAAP | 55 | RANK_AVAILABLE | -7.663 | 13.113 |
| MATERIALS / IFRS | 44 | RANK_AVAILABLE | -2.213 | 1.298 |
| TECHNOLOGY / IFRS | 9 | INSUFFICIENT | — | — |
| INDUSTRIALS / IFRS | 15 | INSUFFICIENT | — | — |
| HEALTHCARE / IFRS | 9 | INSUFFICIENT | — | — |
| OTHER_SERVICES / IFRS | 12 | INSUFFICIENT | — | — |
| COMMUNICATIONS / IFRS | 5 | INSUFFICIENT | — | — |
| CONSUMER_DISCRETIONARY / IFRS | 3 | INSUFFICIENT | — | — |
| CONSUMER_STAPLES / IFRS | 2 | INSUFFICIENT | — | — |

Industry median EY (descriptive, not a cross-industry ranking):

| Family | Valid | Median EY |
|---|---:|---:|
| CONSUMER_DISCRETIONARY | 233 | 0.0325 |
| INDUSTRIALS | 396 | 0.0287 |
| CONSUMER_STAPLES | 95 | 0.0230 |
| OTHER_SERVICES | 350 | 0.0236 |
| COMMUNICATIONS | 60 | 0.0043 |
| MATERIALS | 209 | 0.0018 |
| TECHNOLOGY | 508 | 0.0016 |
| HEALTHCARE | 653 | -0.0958 |

Healthcare's negative median reflects the large loss-making biotech cohort; it
is not a cross-industry comparable ranking.

## 4. Accounting

| Standard | Candidates | Valid EY | Ranked |
|---|---:|---:|---:|
| US GAAP | 2,430 | 2,405 | **2,405** |
| IFRS | 99 | 99 | **44** |

Only Materials IFRS has >=30 issuers. IFRS and US GAAP are not pooled.

## 5. Correlation with other signals

Common-sample Spearman and Pearson:

| Pair | N | Pearson | Spearman |
|---|---:|---:|---:|
| Earnings Yield vs FCF Yield | 2,149 | 0.030 | **0.616** |
| Earnings Yield vs Quality V1 | 1,725 | 0.045 | **0.780** |
| Earnings Yield vs P/B | 2,252 | 0.002 | **0.208** |
| Earnings Yield vs P/S | 2,241 | 0.002 | **-0.072** |
| PE vs Earnings Yield (positive earnings) | 1,314 | — | **-1.000** |

Pearson is near zero because of extreme tails; Spearman is the more appropriate
diagnostic here.

Key conclusions:

- Earnings Yield is **not independent of Quality** (Spearman 0.780).
- Earnings Yield shares substantial information with FCF Yield (0.616).
- P/B has only weak relation (0.208); P/S is almost unrelated (-0.072).
- PE is the exact reciprocal of Earnings Yield for positive earnings and cannot
  be a second independent factor.

By accounting:

| Standard | EY/FCF | EY/Quality |
|---|---:|---:|
| US GAAP | 0.613 | 0.783 |
| IFRS | 0.610 | 0.742 |

By industry, EY/FCF Spearman ranges roughly from 0.22 (Communications) to 0.76
(Healthcare); EY/Quality ranges roughly from 0.74 (IFRS broadly) to 0.86
(Technology). Full values are in `earnings_yield_correlation_p610.json`.

## 6. Quality quadrants

Global median split among the 1,727 issuers with both EY and Quality:

| Quadrant | N | Avg EY | Avg Quality | Negative equity |
|---|---:|---:|---:|---:|
| HIGH_EY_HIGH_Q | **733** | 0.432 | 72.0 | 9 |
| HIGH_EY_LOW_Q | **131** | 0.033 | 47.2 | 0 |
| LOW_EY_HIGH_Q | **132** | -0.119 | 61.7 | 1 |
| LOW_EY_LOW_Q | **731** | -8,661.7 | 31.8 | 48 |

High-EY/Low-Quality is only 131 of 864 high-EY names (~15%). There is no
evidence of a large high-EY/low-quality risk cluster. The low-EY/low-quality
group is dominated by extreme negative yields and contains 48 negative-equity
names.

This is a descriptive quadrant table, not a validated Value+Quality strategy.

## 7. Robustness

| Check | Result |
|---|---|
| Winsorized vs raw percentile Spearman | **0.999998** |
| Mean absolute percentile change | **0.00553** |
| p95 absolute percentile change | **0.0** |
| Max absolute percentile change | **0.4658** |
| Positive / negative / near-zero / missing | 1,272 / 1,151 / 81 / 23 |
| Distinct reported financial periods | 178 |
| Invalid period blocked | 2 |

Winsorization does not materially change EY rankings. Raw and winsorized values
remain separately recorded.

## 8. Historical validation gate

P6.7 strict PIT remains failed:

```text
member-session coverage = 79.58% < 95%
ticker coverage = 69.77% < 98%
```

Therefore no 3/6/12-month return test, Q5-Q1, IC, HAC or multiple-testing result
is produced. `BACKTEST_READY` and `VALIDATION_READY` remain **false**.

## 9. Remaining blockers

- ADR ratio / ADR market cap: 314 records unverified.
- Share-class market cap: 697 Common records unverified.
- Market-cap conflicts: 741.
- Missing market cap: 65.
- Special industries: no standard EY peer group.
- Quality score unavailable for 780 EY-valid names.
- 55 records in insufficient peer groups (mostly IFRS).
- 2 financial-period anomalies blocked.
- P6.7 delisted PIT prices and membership gap.

## 10. Conclusion

Earnings Yield standalone coverage is **99.01%** of the P6.8 candidate pool, but:

- it is highly correlated with Quality (0.780);
- it shares 0.616 rank correlation with FCF Yield;
- PE is its exact inverse and cannot be a second factor;
- winsorization has negligible rank impact;
- no historical predictive test is possible under the current PIT gate.

Earnings Yield is a reasonable **next research candidate** for a single-factor
study, not a validated Alpha and not a production score.
