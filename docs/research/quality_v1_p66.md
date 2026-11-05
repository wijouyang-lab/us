# Quality V1 Full-Market Research Score — P6.6

Date: 2026-11-05
Branch: `research/quality-v1-p66`
Label: **RESEARCH_ONLY / NOT_PRODUCTION_APPROVED / NOT_BACKTEST_VALIDATED**

## 1. Scope

Main pool: **5,502 Common + ADR**.
P6.5 standard-model candidates: **3,342 securities / 3,307 unique CIKs**.

Special families are excluded from the standard model:

```text
BANKS, INSURANCE, REIT, BDC, OTHER_FINANCIALS, UTILITIES, ENERGY, UNCLASSIFIED
```

No SEC bulk, submissions bulk, CompanyFacts, or quote re-download was performed.

## 2. Formula

Peer groups:

```text
model_family × accounting_standard
```

Minimum peer group: **30 unique issuers**.

```text
Quality V1 =
  30% × ROE percentile
+ 25% × ROA percentile
+ 25% × CFO / Average Assets percentile
+ 20% × Inverse Liabilities / Assets percentile
```

- ROE = NetIncome / average StockholdersEquity
- ROA = NetIncome / average TotalAssets
- CFO / average TotalAssets
- Liabilities / TotalAssets, ranked inversely
- All four primary metrics required
- No weight redistribution
- 1% / 99% winsorization within the current peer group
- Operating Margin is diagnostic only, weight **0**

## 3. Results

| Metric | Count |
|---|---:|
| Candidate securities | **3,342** |
| Candidate unique CIKs | **3,307** |
| Issuers with four complete metrics | **2,405** |
| Scored issuers | **2,313** |
| **Scored securities** | **2,335** |
| `INSUFFICIENT_PEER_GROUP` securities | **92** |
| `QUALITY_V1_BLOCKED` | **1,854** |
| `QUALITY_V1_SPECIAL_MODEL_REQUIRED` | **1,221** |
| Formal `SCORE_READY` | **0** |
| `BACKTEST_READY` | **0** |

The 2,335 scored securities include duplicate tickers sharing a CIK; the unique
issuer count is 2,313.

## 4. Accounting split

| Standard | Records in pool | Scored |
|---|---:|---:|
| US GAAP | 4,774 | **2,288** |
| IFRS | 455 | **47** |
| MIXED | 96 | 0 |
| NONE | 177 | 0 |

IFRS and US GAAP are ranked separately. Only the Materials IFRS group reached
30 issuers; other IFRS groups were insufficient and received no percentile
score.

## 5. Metric coverage and blockers

Candidate issuer denominator: 3,307.

| Metric | Valid issuers | Missing | Valid rate |
|---|---:|---:|---:|
| ROE | 2,831 | 476 | 85.61% |
| ROA | 3,131 | 176 | 94.68% |
| CFO / average assets | 3,055 | 252 | 92.38% |
| Liabilities / assets | 2,763 | 544 | 83.55% |
| Operating Margin (diagnostic) | 2,629 | 678 | 79.50% |

The binding constraint is the requirement that all four primary metrics exist:
only 2,405 issuers have all four. Liabilities and average equity are the main
missing inputs.

Blocked reasons:

```text
P6_5_SPECIAL_MODEL                 1221
NOT_P6_5_STANDARD_INPUT_READY       939
FINANCIAL_METRICS_OR_PIT_INCOMPLETE 915
INSUFFICIENT_PEER_GROUP              92
```

## 6. Score distribution and diagnostics

| Statistic | Value |
|---|---:|
| Scored securities | 2,335 |
| Minimum | 0.70 |
| Median | 51.30 |
| Maximum | 96.51 |
| ROE >2 or <-1 | 355 |
| ROA >1 | 9 |
| Liabilities/Assets >2 | 2 |
| Negative average equity among scored | 0 |

Extremes are retained and winsorized only inside the peer group; they are not
silently deleted. Negative equity with a non-positive average equity denominator
does not produce ROE.

## 7. Peer groups

| Group | Issuers | Scored securities | Status |
|---|---:|---:|---|
| HEALTHCARE / US GAAP | 539 | 539 | SCORED |
| TECHNOLOGY / US GAAP | 549 | 552 | SCORED |
| INDUSTRIALS / US GAAP | 330 | 333 | SCORED |
| OTHER_SERVICES / US GAAP | 345 | 348 | SCORED |
| CONSUMER_DISCRETIONARY / US GAAP | 215 | 218 | SCORED |
| MATERIALS / US GAAP | 127 | 128 | SCORED |
| CONSUMER_STAPLES / US GAAP | 88 | 91 | SCORED |
| COMMUNICATIONS / US GAAP | 73 | 79 | SCORED |
| MATERIALS / IFRS | 47 | 47 | SCORED |
| TECHNOLOGY / IFRS | 22 | 0 | INSUFFICIENT |
| INDUSTRIALS / IFRS | 21 | 0 | INSUFFICIENT |
| HEALTHCARE / IFRS | 19 | 0 | INSUFFICIENT |
| OTHER_SERVICES / IFRS | 17 | 0 | INSUFFICIENT |
| CONSUMER_DISCRETIONARY / IFRS | 4 | 0 | INSUFFICIENT |
| CONSUMER_STAPLES / IFRS | 4 | 0 | INSUFFICIENT |
| COMMUNICATIONS / IFRS | 5 | 0 | INSUFFICIENT |

## 8. Top 10 by scored peer group

Scores are 0–100 and are **not** production or Alpha claims.

```text
TECHNOLOGY / US GAAP
CRDO 94.22, NVDA 94.00, NVEC 93.13, MU 92.06, SNDK 91.94,
EVER 91.18, MSGM 90.81, UI 90.66, PLTR 90.59, RDDT 90.31

HEALTHCARE / US GAAP
INMD 94.81, BDTX 93.36, IRMD 92.72, KROS 92.47, RIGL 92.12,
UTHR 91.90, KRYS 91.86, EXEL 90.53, ELMD 89.79, ISRG 89.57

INDUSTRIALS / US GAAP
ESEA 90.30, NVR 89.58, LRCX 88.88, XPEL 88.62, GNTX 88.06,
IESC 87.91, GSL 87.83, OFLX 87.48, EHLD 86.22, CRCT 84.36

MATERIALS / US GAAP
USLM 95.63, IDR 95.12, MLI 94.07, UG 89.13, WDFC 88.43,
CRS 86.34, IPAR 85.67, HWM 85.04, HL 84.65, NEU 83.54

MATERIALS / IFRS
KGC 90.43, AU 89.57, WPM 87.34, AEM 81.06, ERO 80.96,
IAG 79.57, OR 78.19, B 76.70, AGI 76.60, GFI 75.96

CONSUMER_DISCRETIONARY / US GAAP
LULU 90.35, MCRI 90.07, BKE 89.07, JL 88.23, ODC 88.00,
HERE 87.79, GRDN 87.65, WSM 87.63, CPRT 87.44, ATAT 87.19

CONSUMER_STAPLES / US GAAP
BUDA 96.48, FIZZ 94.15, RAVE 92.73, COCO 88.75, LWAY 86.31,
CALM 84.20, JBSS 82.56, VITL 81.76, PPC 79.89, INGR 79.83

COMMUNICATIONS / US GAAP
OSW 85.89, IDT 85.27, ADEA 84.59, CXDO 83.90, SPOK 83.70,
RSI 82.19, AHMA 78.56, CALX 78.42, FABC 74.86, LTH 74.59

OTHER_SERVICES / US GAAP
TPL 96.51, INCY 90.39, IDCC 88.13, ACFN 87.80, YELP 87.78,
PXED 86.96, PDD 86.61, AOS 85.84, TREX 85.65, NFLX 85.17
```

## 9. Caveats

1. Industry is the SEC SIC model family, not GICS. SIC/GICS differences are
   preserved in P6.5; some technology names can appear under Industrials or
   Other Services.
2. P6.3 PIT is `filed -> next weekday`, without exchange holiday adjustment or
   exact acceptanceDateTime.
3. The score uses the latest complete annual period visible by 2026-11-05.
   No YTD fact is treated as annual.
4. Restatement versions are retained in the panel; the latest filed version at
   a period end is used for scoring.
5. No historical stability, out-of-sample, or transaction-cost validation has
   been performed.
6. `SCORE_READY` and `BACKTEST_READY` remain **false** for every security.

## 10. Conclusion

Quality V1 produced **2,335 scored securities / 2,313 unique issuers** from the
3,342 P6.5 candidates. The main limitation is not the formula but missing
current/prior balance-sheet inputs and the all-four-metric requirement.

This is a research hypothesis suitable for the next historical stability test,
not a validated factor and not a production score.
