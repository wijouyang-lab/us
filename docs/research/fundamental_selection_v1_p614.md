# Fundamental Selection V1 — P6.14

Date: 2026-11-06
Branch: `research/invest-terminal-v1`
Status: **CURRENT_CROSS_SECTIONAL_RESEARCH · RESEARCH_ONLY · PIT_BACKTEST_BLOCKED**

> Superseded for method corrections and tradability by P6.15
> (undamental_selection_v1_p615.md).

This is a research ranking, not a buy/sell signal, not a production strategy and
not evidence of Alpha.

## 1. Real inputs found

| File | Rows / size | SHA256 |
|---|---:|---|
| `value_metric_rankings_p69.csv` (P6.9) | 4,865,978 bytes | `646c83996698d9f03111569a4974b7093c39b0423ba69c45cd8c8c8caadc5cc5` |
| `quality_v1_scores_p66.csv` (P6.6) | 3,533,688 bytes | `569359e7b7dd6b810a9716b1ad543ea4e3da48081befcc4d939821e4d50e147a` |
| `us_equities_current.csv` (P6.1) | 3,145,614 bytes | `a36768832c0885a26048738948c268ee1e0b7884f47a43c10a63f1d24eef9795` |
| `garp_growth_metrics_p614.csv` (new, derived from P6.3) | 1,542,213 bytes | `864fa1ae4ae1aea92a935a74857a3eea35f603c249a966bfa5187ef9276cb7a9` |
| P6.3 SEC panel used to derive GARP | 67,433,497 bytes | `5687b8644ceb5ccf3d94e055f98a0a204502e68edaebfda3a294899e98a99c31` |

Supporting audits:

- `value_metric_audit_p69.json`: 2,529 candidates, 992 all-five intersection.
- `quality_v1_scoring_audit_p66.json`: 2,335 scored securities / 2,313 issuers.
- `sec_sic_model_family_map_p65.csv`: SIC to model-family rules.
- `quality_v1_model_spec_p66.json`: Quality V1 formula.

The large P6.3 panel is **not** committed to Git; it is the existing P6.3 artifact
used to derive `garp_growth_metrics_p614.csv`. The 28-company SEC sample is not
used as the stock pool.

## 2. Pool and exclusions

| Item | Count |
|---|---:|
| Current security identity rows | 5,615 |
| Value P6.9 Common candidates | **2,529** |
| Value unique CIKs | **2,529** |
| Value all-five (PE/PB/PS/EY/FCF) | **992** verified |
| Value all-four positive (PB/PS/EY/FCF) | **851** |
| Value partial / blocked candidates | 1,678 |
| Quality scored issuers | **2,313** |
| GARP current issuer rows | 5,453 |
| GARP history available | 4,028 |
| GARP ranked with at least 3 historical metrics | **3,579** |

Value candidate exclusions: ADR, unclassified, unverified market cap/share
classes, missing P6.8 READY status, non-positive PB/PS, negative EY/FCF for the
composite. No missing value is filled with zero.

## 3. Value V1

Peer group:

```text
SIC model_family × accounting_standard (US_GAAP / IFRS)
minimum 30 valid issuers
1%/99% winsorization inside peer group
```

Independent factors:

```text
P/B              lower is better (inverse percentile)
P/S              lower is better (inverse percentile)
Earnings Yield   higher is better
FCF Yield        higher is better
```

`value_composite_experimental` is an **EQUAL-WEIGHT average of all four
percentiles**, only when all four are available and positive. It is not an
approved Value strategy.

Coverage among 2,529 candidates:

```text
P/B              2,222
P/S              2,215
Earnings Yield   2,451
FCF Yield        2,118
four positive      851
all five P6.9      992
```

Top 20:

1. CRMT — 99.14 — America's Car-Mart — CONSUMER_DISCRETIONARY/US_GAAP
2. LIVE — 98.08 — Live Ventures — CONSUMER_DISCRETIONARY/US_GAAP
3. WETH — 97.89 — Wetouch Technology — TECHNOLOGY/US_GAAP
4. SSTK — 97.63 — Shutterstock — TECHNOLOGY/US_GAAP
5. CAAS — 97.41 — China Automotive Systems — INDUSTRIALS/US_GAAP
6. CTRM — 96.55 — Castor Maritime — INDUSTRIALS/US_GAAP
7. VISN — 92.93 — Vistance Networks — TECHNOLOGY/US_GAAP
8. EBS — 92.75 — Emergent BioSolutions — HEALTHCARE/US_GAAP
9. KROS — 92.59 — Keros Therapeutics — HEALTHCARE/US_GAAP
10. NUS — 92.52 — Nu Skin — CONSUMER_STAPLES/US_GAAP
11. MNDO — 91.01 — MIND C.T.I. — TECHNOLOGY/US_GAAP
12. PSFE — 90.96 — Paysafe — OTHER_SERVICES/US_GAAP
13. BOSC — 90.62 — B.O.S. Better Online Solutions — TECHNOLOGY/US_GAAP
14. RGS — 90.24 — Regis — OTHER_SERVICES/US_GAAP
15. ABG — 90.22 — Asbury Automotive — CONSUMER_DISCRETIONARY/US_GAAP
16. CRMD — 89.53 — CorMedix — HEALTHCARE/US_GAAP
17. USNA — 89.41 — USANA Health Sciences — HEALTHCARE/US_GAAP
18. NATR — 89.12 — Nature's Sunshine — HEALTHCARE/US_GAAP
19. IMMR — 88.68 — Immersion — TECHNOLOGY/US_GAAP
20. JL — 88.14 — J-Long Group — CONSUMER_DISCRETIONARY/US_GAAP

All top 50 have positive PB/PS/EY/FCF; no negative-earnings or negative-FCF
company is selected on the composite.

## 4. Quality V1

Reuses the P6.6 scored issuer rows and validates the published weighted score:

```text
30% ROE percentile
25% ROA percentile
25% CFO / average assets percentile
20% inverse liabilities / assets percentile
```

Peer group: `model_family × accounting_standard`; P6.6 minimum 30 issuers.
No weight redistribution.

Result: **2,313 unique scored issuers**, **0 recomputed-score mismatches**.
Top 20:

1. TPL — 96.51
2. BUDA — 96.48
3. USLM — 95.63
4. IDR — 95.12
5. INMD — 94.81
6. CRDO — 94.22
7. FIZZ — 94.15
8. MLI — 94.07
9. NVDA — 94.00
10. BDTX — 93.36
11. NVEC — 93.13
12. RAVE — 92.73
13. IRMD — 92.72
14. KROS — 92.47
15. RIGL — 92.12
16. MU — 92.06
17. SNDK — 91.94
18. UTHR — 91.90
19. KRYS — 91.86
20. EVER — 91.18

Special models (banks, insurers, REITs, BDC, other financials, utilities,
energy, unclassified) remain blocked from the standard Quality ranking, not
silently scored with an unsuitable model.

## 5. GARP historical growth (experimental)

Derived from annual SEC facts filed on or before 2026-11-05:

```text
Revenue Growth 1Y
Revenue CAGR 3Y / 5Y
EPS Growth 1Y
FCF Growth 1Y
Earnings Stability (last 3–5 annual EPS)
Operating Margin Expansion
Operating Leverage
```

No forward EPS, no PEG, no forecast. Negative/zero denominators produce null;
missing values are not zero.

Rows: 5,453 current issuers; 4,028 have enough history; **3,579** have at least
three ranked metrics. Equal-weight available historical percentiles; status is
`GARP_EXPERIMENTAL_HISTORICAL_GROWTH`.

Top 20:

1. QNST — 91.77
2. TLIH — 90.71
3. DAVE — 89.31
4. SEI — 89.05
5. ZJK — 88.80
6. ARXS — 88.17
7. UDR — 88.10
8. CPT — 87.38
9. FOA — 86.77
10. FIGR — 86.61
11. PKE — 86.18
12. MSC — 85.98
13. ANAB — 85.93
14. SE — 85.88
15. TGTX — 85.73
16. FPS — 85.57
17. GOLD — 85.56
18. FIVE — 85.37
19. TOST — 85.06
20. MU — 85.00

This is a historical growth-quality research list, not a GARP strategy.

## 6. Intersections and differences

Top-50 comparisons:

```text
Value ∩ Quality = 3
Value ∩ GARP    = 0
Quality ∩ GARP  = 3
All three       = 0
```

The three rankings are intentionally separate.

## 7. Sensitivity

From `selection_sensitivity.json`:

| Test | Top-50 overlap |
|---|---:|
| Value composite vs single P/B | 29/50 |
| Value composite vs single P/S | 28/50 |
| Value composite vs single EY | 21/50 |
| Value composite vs single FCF | 24/50 |
| Value peer-group vs global rank | 50/50 |
| Value winsorized vs raw percentile | 50/50 |
| Quality published weights | 50/50 |
| Quality equal weights | 43/50 |
| Quality ROE-heavy | 46/50 |
| Quality CFO-heavy | 45/50 |
| Quality peer vs global rank | 43/50 |

The single-factor overlap is materially lower than the composite overlap:
the four metrics are not interchangeable. Weight changes move some Quality
names. These are sensitivity diagnostics, not return results.

## 8. PIT and historical boundaries

```text
CURRENT_CROSS_SECTIONAL_RESEARCH
PIT_BACKTEST_BLOCKED
```

- Input `filed` dates are checked against `2026-11-05`.
- No future filing is used in top candidates.
- No historical returns, Sharpe, drawdown, win rate or PIT backtest are claimed.
- No current survivors are backfilled into a historical universe.
- No `BACKTEST_READY` or `PRODUCTION_READY` status.

## 9. Output files

```text
data/universe/selection/value_rankings.csv
data/universe/selection/value_top50.csv
data/universe/selection/quality_rankings.csv
data/universe/selection/quality_top50.csv
data/universe/selection/garp_rankings.csv
data/universe/selection/garp_top50.csv
data/universe/selection/selection_snapshot.json
data/universe/selection/selection_data_quality.json
data/universe/selection/selection_sensitivity.json
```

Reproduce:

```bash
python -m tools.investment_research.selection.build_rankings
python -m tools.investment_research.selection.sensitivity
```

GARP input regeneration (requires the existing P6.3 panel artifact, no download):

```bash
python -m tools.investment_research.selection.build_garp_metrics \
  --panel /path/to/sec_fundamentals_panel_p63.csv.gz
```

## 10. Known limits

- Value/Quality are **current cross-sectional**, not PIT backtests.
- Value uses P6.8 market caps/prices; no new vendor quote approval is implied.
- P/B, P/S and yields can be distorted for financial firms; special models are
  excluded from Quality but not all Value caveats disappear.
- The top Value list contains micro/small caps and foreign ordinary shares;
  liquidity and ADR/share-class checks remain necessary before any paper order.
- GARP uses annual history only; recent quarters and guidance are absent.
- No production score, scan, review, evolve, PAPER-50000 or broker path changed.
