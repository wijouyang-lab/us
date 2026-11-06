# Fundamental Selection V1 — P6.16 reliability audit and real liquidity

Date: 2026-11-06
Branch: `research/invest-terminal-v1`
Status: **CURRENT_CROSS_SECTIONAL_RESEARCH · PIT_BACKTEST_BLOCKED · RESEARCH_ONLY**

This is a research candidate audit, not a buy/sell recommendation, not a
production strategy and not an Alpha claim. No PAPER-50000 order was placed.

## Key inputs and hashes

| File | Bytes | SHA256 |
|---|---:|---|
| `value_metric_rankings_p69.csv` | 2,432,988 | `646c83996698d9f03111569a4974b7093c39b0423ba69c45cd8c8c8caadc5cc5` |
| `quality_v1_scores_p66.csv` | 1,766,843 | `569359e7b7dd6b810a9716b1ad543ea4e3da48081befcc4d939821e4d50e147a` |
| `us_equities_current.csv` | 1,572,806 | `a36768832c0885a26048738948c268ee1e0b7884f47a43c10a63f1d24eef9795` |
| `us_equity_industry_sic_p65.csv` | 1,518,389 | `e06a6a71c24e1cb137f8c1880320b276e2a8af8b6ba819eac04a135bacf388d6` |
| `value_v1_readiness_p68.csv` | 2,545,964 | `28cc7623da1ab097d05bf1b10507e49f2cebc59f5e8a6bb4d104038ad83b5235` |
| `issuer_classification_p615.csv` | 855,928 | `189006e185dc325069fd4ca23e966581006f27862464d053ce4d9858f9a09cf4` |
| `us_market_quote_mapping_p62.csv` | 738,308 | `280f51ced794fbff8a41d4d6264eed2618c56fa2a56669006908ed23e9087891` |
| `garp_growth_metrics_p614.csv` | 4,993,286 | `d630aeef9df647e2c8bab2e6ea830b61cfe02e9ac6df7534ef00297307ded91c` |
| `liquidity_ohlcv_p616.csv` | 144 rows | SHA256 in fetch summary |
| P6.3 panel (not committed) | 67,433,497 | `5687b8644ceb5ccf3d94e055f98a0a204502e68edaebfda3a294899e98a99c31` |

Data as of: **2026-11-05**; complete trading session used for ADV:
**2026-11-05**.

## 1. Value valuation integrity

Top-50 audit status:

```text
VALUATION_VALID          35
VALUATION_INPUT_SUSPECT  15
VALUATION_DATA_BLOCKED    0
VALUATION_PERIOD_MISMATCH 0
```

The audit checks:

- market cap = P6.8 price × SEC shares (1%);
- P6.8 price vs P6.2 quote (1%);
- FCF = CFO − |CapEx| (1%);
- Earnings Yield × derived PE ≈ 1;
- filed date ≤ 2026-11-05;
- external yfinance close vs P6.2 price (flag >10%);
- extreme P/B/P/S/Earnings/FCF and microcap flags.

### CRMT / LIVE / WETH / CTRM / CAAS

| Ticker | P6 price | YF close | Market cap | P/B | P/S | EY | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| CRMT | 1.26 | 1.52 | $10.51M | 0.028 | 0.0082 | 4.89 | SUSPECT: extreme + external price diff + microcap + provider PE mismatch |
| LIVE | 7.45 | 7.50 | $22.88M | 0.249 | 0.0514 | 0.994 | VALID internally; microcap + provider PE mismatch |
| WETH | 0.864 | 0.76 | $11.56M | 0.078 | 0.256 | 0.620 | SUSPECT: external price diff + microcap |
| CTRM | 1.37 | 1.28 | $13.24M | 0.019 | 0.372 | 1.456 | SUSPECT: extreme + microcap + provider PE mismatch |
| CAAS | 4.29 | 4.13 | $129.43M | 0.287 | 0.169 | 0.331 | VALID internally; provider PE mismatch |

Market cap = price × SEC shares passed for all top50. FCF and EY/PE
reconciliation passed where inputs were present. The suspect flag does **not**
delete a stock from the original ranking; it is a data-quality warning.

## 2. Freshness gate

Thresholds:

```text
DOMESTIC US_GAAP: 400 days
FPI IFRS:         540 days
MIXED/NONE:       DATA_BLOCKED
```

| Ranking | Fresh | Stale | Update missing | Data blocked | Fresh scored |
|---|---:|---:|---:|---:|---:|
| Value | 5,073 | 114 | 155 | 111 | 846 |
| Quality | 4,247 | 388 | 830 | 84 | 2,155 |
| GARP | 4,349 | 342 | 676 | 86 | 2,924 |

**INMD Quality** uses 2023-12-31 / filed 2024-02-13: 1,040 days old, marked
`FUNDAMENTALS_STALE`, removed from the fresh ranking. Its original rank 5 remains
in the raw ranking.

Boundary: this gate uses the stored period/filed metadata in P6.6/P6.9/P6.15.
It does not claim a full subsequent 10-K/10-Q history audit.

## 3. Real ADV20/ADV60

Requested the 144 unique tickers in the three Top50 unions via yfinance current
OHLCV. All 144 returned 20 and 60 complete sessions:

```text
requested: 144
ADV OK:     144
last completed session: 2026-11-05
provider: yfinance
adjustment: UNADJUSTED_CLOSE_RAW_VOLUME
```

ADV is `Close × Volume`, averaged over the last 20/60 sessions; missing dates
were not filled with zero; the current incomplete day was excluded.

Examples:

```text
CRMT: ADV20 $0.69M, ADV60 $0.75M
LIVE: ADV20 $0.017M, ADV60 $0.044M
WETH: ADV20 $0.075M, ADV60 $0.068M
CTRM: ADV20 $0.082M, ADV60 $0.110M
CAAS: ADV20 $0.053M, ADV60 $0.143M
```

## 4. Final tradability scenarios

Final status combines fundamental rank + freshness + valuation audit (Value) +
tradability. `ELIGIBLE` is still a research-screen pass, not trading approval.

| Scenario | Value E/W/B | Quality E/W/B | GARP E/W/B |
|---|---:|---:|---:|
| Conservative | 9 / 1 / 40 | 29 / 0 / 21 | 13 / 2 / 35 |
| Balanced | 16 / 3 / 31 | 36 / 1 / 13 | 18 / 3 / 29 |
| Aggressive | 29 / 8 / 13 | 44 / 1 / 5 | 25 / 5 / 20 |

Balanced final:

```text
Value:   ELIGIBLE 16, WATCH 3, BLOCKED 31
Quality: ELIGIBLE 36, WATCH 1, BLOCKED 13
GARP:    ELIGIBLE 18, WATCH 3, BLOCKED 29
```

### Final ELIGIBLE Top (Value, only 16)

```text
ABG, GPI, CCS, EFOR, KBH, ACCO, DXC, VTOL, LEA, CTVA,
SLVM, SPB, INGM, AMPH, WHR, COLL
```

Quality ELIGIBLE top 20:

```text
TPL, USLM, CRDO, FIZZ, MLI, NVDA, IRMD, RIGL, MU, SNDK,
UTHR, KRYS, EVER, UI, PLTR, EXEL, KGC, INCY, LULU, RDDT
```

GARP ELIGIBLE top 18:

```text
QXO, ONDS, IBRX, AEVA, FDMT, LCID, OUST, LQDA, QBTS, IDYA,
ALAB, EVLV, RKLB, RBRK, RDDT, RELY, BBIO, NIO
```

## 5. Fresh top 20

Value fresh top20:

```text
CRMT, LIVE, WETH, SSTK, CAAS, CTRM, VISN, EBS, KROS, NUS,
MNDO, PSFE, BOSC, RGS, ABG, CRMD, USNA, NATR, IMMR, GPI
```

Quality fresh top20 (INMD removed):

```text
TPL, BUDA, USLM, IDR, CRDO, FIZZ, MLI, NVDA, BDTX, NVEC,
RAVE, IRMD, KROS, RIGL, MU, SNDK, UTHR, KRYS, EVER, MSGM
```

GARP fresh top20:

```text
CDZI, PROP, DVLT, QXO, GEVO, SMTK, NIXX, EOSE, WKHS, ONDS,
SPRU, NTRP, WKSP, IBRX, SPWR, TRAW, SPRO, AEVA, ACTG, FDMT
```

## 6. Valuation-valid Value top20

```text
LIVE, CAAS, EBS, NUS, MNDO, PSFE, ABG, CRMD, USNA, IMMR,
GPI, CRWS, CCS, EDUC, XTNT, ARKO, EFOR, STRT, KBH, ACCO
```

CRMT/WETH/CTRM and other suspect names remain in the raw top50 but are not in
this valuation-valid subset.

## 7. BDC / special-model audit

`BDC` explicit rows = **0**, SIC 6726 rows = **0**. This is a classification
coverage gap, not evidence that no BDCs are listed.

Name candidates with `BDC`/`Business Development`:

```text
BBDC, CCAP, GSBD, ICMB, KBDC, LIEN, PSBD, TPVG
```

Their classification is `UNCLASSIFIED/US_GAAP` in the current mapping. No BDC
model is invented.

GARP classification blocked: **293**, composed of:

```text
UNCLASSIFIED|NONE       65
UNCLASSIFIED|US_GAAP    27
other NONE/MIXED       201
```

REITs remain blocked for lack of P/FFO/AFFO/NAV. Banks/Insurance have P/B+ROE
data but no validated specialized model in this round.

## 8. Corrected GARP sensitivity

The 3/4/5 pools are rebuilt from all candidates, not from the already-filtered
scored rows:

| Pool | Candidate count | Top50 overlap with current |
|---|---:|---:|
| ≥3 metrics | 3,556 | 28/50 |
| ≥4 metrics | 3,101 | 50/50 |
| ≥5 metrics | 2,322 | 1/50 |
| Without 5Y | — | 28/50 |
| Peer vs true global | — | 25/50 |

The previous apparent 50/50 at min3 was an artifact of filtering to scored
stocks first.

## 9. Outputs

```text
value_rankings.csv, quality_rankings.csv, garp_rankings.csv
value_top50.csv, quality_top50.csv, garp_top50.csv
value_freshness_adjusted.csv
quality_freshness_adjusted.csv
garp_freshness_adjusted.csv
valuation_integrity_audit.csv
value_valuation_valid_top50.csv
tradability/value_tradable_candidates.csv
tradability/quality_tradable_candidates.csv
tradability/garp_tradable_candidates.csv
tradability/tradability_summary.json
special_model_coverage.json
selection_quality_report.json
freshness_summary.json
valuation_integrity_summary.json
```

## 10. Boundaries

- `CURRENT_CROSS_SECTIONAL_RESEARCH`
- `PIT_BACKTEST_BLOCKED`
- No Alpha, returns, Sharpe, drawdown, win rate or transaction-costed result.
- No PAPER-50000 mutation or real broker.
- ADV is current yfinance, not an execution-grade feed.
- ELIGIBLE is a research screen, not a trading approval.
