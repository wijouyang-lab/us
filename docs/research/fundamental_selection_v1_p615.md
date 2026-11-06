# Fundamental Selection V1 — P6.15 corrections and tradability

Date: 2026-11-06
Branch: `research/invest-terminal-v1`
Status: **CURRENT_CROSS_SECTIONAL_RESEARCH · PIT_BACKTEST_BLOCKED · RESEARCH_ONLY**

This is a research candidate engine, not a buy/sell recommendation and not an
Alpha claim. No production scan/review/evolve or PAPER-50000 state was changed.

## Key inputs

| File | Bytes | SHA256 |
|---|---:|---|
| alue_metric_rankings_p69.csv | 2,432,988 | 646c83996698d9f03111569a4974b7093c39b0423ba69c45cd8c8c8caadc5cc5 |
| quality_v1_scores_p66.csv | 1,766,843 | 569359e7b7dd6b810a9716b1ad543ea4e3da48081befcc4d939821e4d50e147a |
| us_equities_current.csv | 1,572,806 | 36768832c0885a26048738948c268ee1e0b7884f47a43c10a63f1d24eef9795 |
| us_equity_industry_sic_p65.csv | 1,518,389 | e06a6a71c24e1cb137f8c1880320b276e2a8af8b6ba819eac04a135bacf388d6 |
| alue_v1_readiness_p68.csv | 2,545,964 | 28cc7623da1ab097d05bf1b10507e49f2cebc59f5e8a6bb4d104038ad83b5235 |
| issuer_classification_p615.csv | 855,928 | 189006e185dc325069fd4ca23e966581006f27862464d053ce4d9858f9a09cf4 |
| us_market_quote_mapping_p62.csv | 738,308 | 280f51ced794fbff8a41d4d6264eed2618c56fa2a56669006908ed23e9087891 |
| garp_growth_metrics_p614.csv | 4,993,286 | d630aeef9df647e2c8bab2e6ea830b61cfe02e9ac6df7534ef00297307ded91c |

## 1. Corrected GARP fiscal matching

`build_garp_metrics.py` now:

- chooses each metric's own latest annual period;
- matches the prior period only within explicit 52/53-week windows:
  - 1Y: target 365 days, ±35;
  - 3Y: target 1,096 days, ±45;
  - 5Y: target 1,826 days, ±60;
- requires the same period for OI/Revenue and CFO/Capex pairs;
- writes latest/prior period, filed dates, and actual days apart in
  `period_detail_json`;
- emits NULL and `INSUFFICIENT_DATA` reasons when a period is absent;
- does not create NaN/Infinity/complex values.

## 2. GARP metric corrections

Separate fields:

```text
operating_income_growth_1y
operating_leverage_ratio = OI Growth / Revenue Growth
operating_margin_expansion = current OI margin - prior OI margin
operating_growth_spread = OI Growth - Revenue Growth   # diagnostic only
```

`operating_growth_spread` is no longer called operating leverage.

`revenue_cagr_5y` is now an independent ranked metric. Coverage:

| GARP metric | Valid issuers |
|---|---:|
| Revenue Growth 1Y | 3,643 |
| Revenue CAGR 3Y | 3,188 |
| Revenue CAGR 5Y | 2,739 |
| EPS Growth 1Y | 2,214 |
| FCF Growth 1Y | 1,664 |
| Earnings Stability | 2,153 |
| Operating Margin Expansion | 3,144 |
| Operating Leverage Ratio | 1,727 |

EPS/FCF sign changes have `TURNED_NEGATIVE` / `TURNED_POSITIVE` / `BOTH_NONPOSITIVE`
status; a misleading ordinary growth percentage is not produced.

GARP base score requires **4 valid historical metrics** (3-metric rows are
`GARP_INSUFFICIENT_METRICS` WATCH). Ranked: **3,101** of 5,453 current issuers.

### GARP Top 20 after correction

```text
1  CDZI  99.41
2  PROP  99.11
3  DVLT  98.82
4  QXO   98.73
5  GEVO  98.64
6  SMTK  98.13
7  NIXX  98.13
8  EOSE  97.86
9  WKHS  97.73
10 ONDS  97.62
11 SPRU  97.14
12 NTRP  97.07
13 WKSP  97.00
14 IBRX  96.86
15 SPWR  96.74
16 TRAW  96.23
17 SPRO  95.85
18 AEVA  95.77
19 ACTG  95.71
20 FDMT  95.65
```

Before correction, the top names were QNST/TLIH/DAVE/SEI/ZJK/ARXS/UDR/CPT...
The change is material and expected: the old matching could use a global
`latest_end` and a 250-day tolerance, and did not rank 5Y CAGR.

## 3. Value strict-positive correction

Value candidates: **2,529**. Composite requires all four strictly positive:

```text
PB > 0
PS > 0
Earnings Yield > 0
FCF Yield > 0
```

All-four positive: **850** (was 851 before zero handling). The P6.9 five-metric
intersection is still **992** (PE/PB/PS/EY/FCF). Missing/zero/negative metrics
never receive a composite; the original factor ranks remain visible.

Top 20 after correction is unchanged at the top:

```text
CRMT, LIVE, WETH, SSTK, CAAS, CTRM, VISN, EBS, KROS, NUS,
MNDO, PSFE, BOSC, RGS, ABG, CRMD, USNA, NATR, IMMR, JL
```

## 4. Quality verification boundary

`QUALITY_SCORE_MISMATCHES = 0` verifies:

- the four published component percentiles and weights reconcile to the
  published `quality_v1_score`;
- peer percentiles recomputed from the raw ROE/ROA/CFO/leverage values reproduce
  the published peer percentiles with max absolute difference **0.0** and zero
  mismatches.

Still not independently recomputed from the P6.3 CompanyFacts panel inside this
selection module: the raw quality metrics are taken from P6.6's audited score
file. The exact boundary is:

```text
composite reconciliation:       validated
peer percentile recalculation: validated from P6.6 raw metrics
raw metric re-derivation:      P6.6 source, not rerun here
```

Quality scored issuers remain **2,313** with 0 mismatches.

## 5. Full-shop peer classification

`issuer_classification_p615.csv` combines P6.5 SIC model family and P6.8
accounting standard for **5,453** issuers. All 5,453 have a P6.5/P6.8
classification status; 293 GARP rows are `GARP_CLASSIFICATION_BLOCKED`
(UNCLASSIFIED/NONE) and are not placed into a valid peer group.

Value and Quality P6 source industry/accounting match the P6.5 classification
for all rows (5,453/5,453). There are 65 `UNCLASSIFIED|NONE` GARP rows; they are
explicitly blocked, not silently pooled.

## 6. Real sensitivity, not pseudo-global

Global and alternate-winsor schemes recompute percentiles from raw values.
`selection_sensitivity.json`:

| Test | Top-50 overlap |
|---|---:|
| Value peer vs true global | 36/50 |
| Value true global raw percentile | 36/50 |
| Value winsor 5/95 | 36/50 |
| Value winsor 10/90 | 36/50 |
| Value P/B single factor | 29/50 |
| Value P/S single factor | 28/50 |
| Value EY single factor | 21/50 |
| Value FCF single factor | 24/50 |
| Quality peer vs true global | 37/50 |
| Quality equal weights | 43/50 |
| Quality ROE-heavy | 46/50 |
| Quality CFO-heavy | 45/50 |
| GARP min 3 metrics | 50/50 |
| GARP min 4 metrics | 50/50 |
| GARP min 5 metrics | 1/50 |
| GARP without 5Y CAGR | 37/50 |
| GARP global | 40/50 |

These are rank-stability diagnostics only, not returns.

## 7. Tradability Screen

`tools/investment_research/selection/tradability.py` adds separate results. It
does **not** alter fundamental scores.

Available verified data:

- P6.2 current quote mapping: price, market cap, quote match status;
- P6.1 identity, listing, security type, exchange;
- P6.5/P6.8 classification.

Unavailable:

- 20/60-day average dollar volume. P6.2's batch mapping contains no volume
  fields. No synthetic ADV is generated.

Therefore:

```text
ELIGIBLE = 0
```

This is intentional: without ADV evidence, no stock is declared liquid enough to
trade. All price/market-cap-valid names are `WATCH` at most.

### Scenarios

| Scenario | Min price | Min mcap | Min ADV | Value WATCH/ELIGIBLE | Quality WATCH/ELIGIBLE | GARP WATCH/ELIGIBLE |
|---|---:|---:|---:|---:|---:|---:|
| Conservative | $5 | $2B | $5M | 10 / 0 | 29 / 0 | 15 / 0 |
| Balanced | $3 | $500M | $2M | 19 / 0 | 37 / 0 | 21 / 0 |
| Aggressive | $1 | $50M | $500K | 40 / 0 | 46 / 0 | 31 / 0 |

Top-50 status by balanced scenario:

```text
Value   WATCH 19, BLOCKED 31
Quality WATCH 37, BLOCKED 13
GARP    WATCH 21, BLOCKED 29
```

The large Value/BLOCKED count is mostly micro-cap/price threshold failures, not
a fundamental disqualification. The original rankings remain intact.

## 8. Special industry coverage

`special_model_coverage.json`:

| Family | Value rows | Quality rows | GARP rows | Model status |
|---|---:|---:|---:|---|
| BANKS | 328 | 333 | 328 | P/B+ROE possible; not implemented |
| INSURANCE | 102 | 104 | 102 | P/B+ROE possible; underwriting/capital unavailable |
| REIT | 164 | 170 | 164 | P/FFO/NAV not available; BLOCKED |
| BDC | 0 | 0 | 0 | NAV/credit not available; BLOCKED |
| OTHER_FINANCIALS | 365 | 376 | 365 | special review |
| UTILITIES | 126 | 128 | 126 | no specialized model |
| ENERGY | 130 | 134 | 130 | no specialized model |
| UNCLASSIFIED | 92 | 110 | 92 | excluded from valid peer group |

No special model is declared implemented in this round.

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
data/universe/selection/special_model_coverage.json
data/universe/selection/tradability/value_tradable_candidates.csv
data/universe/selection/tradability/quality_tradable_candidates.csv
data/universe/selection/tradability/garp_tradable_candidates.csv
data/universe/selection/tradability/tradability_summary.json
```

## 10. Status and limits

- Value/Quality/GARP are current cross-sectional research.
- No historical returns, Sharpe, drawdown, win rate, Alpha, BACKTEST_READY or
  PRODUCTION_READY.
- ADR and unclassified securities are not in the standard Value/Quality pool.
- Top Value names include small/micro caps; the tradability screen explicitly
  blocks many of them and cannot approve any without ADV.
- No special bank/insurance/REIT valuation model is claimed.
