# Fundamental Selection V1 — P6.17 independent audit

Date: 2026-11-06
Branch: `research/invest-terminal-v1`
Status: **CURRENT_CROSS_SECTIONAL_RESEARCH · PIT_BACKTEST_BLOCKED · RESEARCH_ONLY**

This round validates the P6.16 artifacts. It does not add factors and does not
change the original rankings. No PAPER-50000, broker, or production Scan/Review/
Evolve state was touched.

## 1. Quote timestamp correction

P6.2 upstream is `tools/research/audit_us_market_quotes_p62.py`. It fetches
`ak.stock_us_spot_em()` and records `generated_at`, but the mapping CSV has no
per-row quote timestamp. The documented snapshot time is a source-level value,
not a per-symbol guarantee.

P6.17 therefore:

- records source `P6.2 AkShare`, `generated_at=2026-11-05T08:34:41Z`,
  `documented_snapshot=2026-11-05T08:16:00Z`, 15-minute delay;
- marks per-row quote status **QUOTE_TIMESTAMP_UNKNOWN**;
- marks any comparison with the later yfinance close
  **PRICE_NOT_COMPARABLE**, not a data error;
- no longer generates the old >10% external-price suspect flag.

P6.17 tradability uses the yfinance completed-session close for the same session
as ADV, with `price_asof` per row; P6.2 quote is retained for provenance.

CRMT/WETH/CTRM/LIVE/CAAS re-audit:

| Ticker | Quote timestamp | Recalc arithmetic | Extreme flags | P6.17 interpretation |
|---|---|---|---|---|
| CRMT | UNKNOWN | VALID | EY/PB/PS/microcap | arithmetic consistent; extreme inputs remain a research risk |
| LIVE | UNKNOWN | VALID | microcap | internally consistent |
| WETH | UNKNOWN | VALID | microcap | internally consistent |
| CTRM | UNKNOWN | VALID | EY/PB/PS/microcap | arithmetic consistent; extreme inputs remain a research risk |
| CAAS | UNKNOWN | VALID | none | internally consistent |

No stock was removed to make the audit pass.

## 2. Independent Value recalculation

Recomputed from P6.8/P6.9 raw inputs:

```text
mcap = price * sec_shares
P/B = mcap / equity
P/S = mcap / revenue
EY = net_income / mcap
PE = mcap / net_income
FCF = CFO - |CapEx|
FCF yield = FCF / mcap
```

Top50 result:

```text
VALUATION_RECALCULATED_VALID          45
VALUATION_RECALCULATION_MISMATCH       5
VALUATION_PERIOD_MISMATCH              0
VALUATION_UNIT_OR_CURRENCY_MISMATCH     0
VALUATION_SHARES_STALE_OR_UNVERIFIED    0 primary / 5 secondary
VALUATION_DATA_BLOCKED                 0
```

Mismatch tickers:

```text
BOSC, JL, DOX, INMD, GASS
```

Their recomputed mcap and ratios differ by >1% from the stored P6.8 values;
the shares ratio is also outside 1%. These are **not deleted**; they are flagged.

`VALUATION_SHARES_STALE_OR_UNVERIFIED` is present as a secondary flag on the
five mismatch rows. XBRL tags/units are not present in the readiness file, so
unit/currency is recorded as `ASSUMED_USD_FROM_P6_3`, not claimed as directly
verified.

## 3. SEC subsequent-filing audit

SEC Submissions fetched for all 144 unique Top50 tickers:

```text
requested tickers: 144
history rows:       9,426
audit rows:           150
API errors:             0
```

Forms included: 10-K, 10-Q, 20-F, 40-F, 6-K. **8-K is excluded.**

Status:

```text
FILING_HISTORY_CONFIRMED                 39
SUPERSEDED_BY_NEW_PERIODIC_FILING        98 audit rows / 94 unique tickers
6K_LATER_NOT_VERIFIED                    13
FILING_DATA_BLOCKED                       0
```

The 6-K rule: a later 6-K is not assumed to contain financial data and is never
treated as a confirmed update. Those names are `6K_LATER_NOT_VERIFIED`.

Superseded unique tickers are recorded in
`filing_freshness_summary_p617.json`; examples include INMD, TPL, USLM, NVDA,
MU, QXO, CDZI and CRDO.

This is stricter than P6.16's 400/540-day check: a later 10-Q/10-K/20-F/40-F
with a later report period is identified even if the old annual period is under
400 days old.

Full unique superseded list:

`	ext
ACTG, AEVA, ALAB, AMPH, APPF, ARKO, ARWR, BBIO, BDTX, BKE, BKTI, BUDA,
CDZI, CLSK, COCO, COLL, CRDO, CRMD, CUE, DAVE, DOCS, DOX, DVLT, EOSE,
EVER, EVGO, EVLV, EXEL, FDMT, FIZZ, GEVO, GOOG, GWAV, HLLY, IBRX, IDR,
IDYA, INCY, INMD, INSP, IRMD, ISRG, JL, KROS, KRUS, KRYS, LASE, LCID,
LEDS, LOCL, LQDA, LRCX, LULU, MCRI, MLI, MSGM, NIXX, NSSC, NTRP, NVDA,
NVEC, NVR, ONDS, OUST, PLTR, PROP, QBTS, QXO, RBRK, RDDT, RELY, RGS,
RIGL, RKLB, SENS, SIGA, SMTK, SNDK, SPRO, SPRU, SPWR, SSTK, TPL, TRAW,
UG, USLM, UTHR, VISN, VNRX, WDC, WKHS, WKSP, XPEL, XTIA
`

## 4. Liquidity quality

Manual yfinance refresh:

```text
requested: 144
LIQUIDITY_VALID: 135
LIQUIDITY_STALE: 0
LIQUIDITY_CORPORATE_ACTION_REVIEW: 9
LIQUIDITY_INVALID_SESSIONS: 0
LIQUIDITY_DATA_BLOCKED: 0
session rows: 18,432
```

Corporate-action review tickers:

```text
CIIT, CPOP, CRMT, LASE, LQDA, NVEC, SMTK, SPWR, WLDS
```

These have a >50% close-to-close move in the 60-session window. This is a
review flag, not proof of a split. Every ticker has unique session dates, 20/60
distinct sessions, finite numbers, positive close and non-negative volume.
No zero filling is used.

The external refresh is a separate manual `workflow_dispatch` workflow; regular
CI uses the fixed snapshot and does not depend on yfinance/SEC being reachable.

## 5. P6.16 vs P6.17 status counts

| Ranking | P6.16 E/W/B | P6.17 E/W/B |
|---|---|---:|
| Value | 16 / 3 / 31 | **13 / 5 / 32** |
| Quality | 36 / 1 / 13 | **3 / 34 / 13** |
| GARP | 18 / 3 / 29 | **0 / 20 / 30** |

The large Quality/GARP reduction is caused mainly by SEC later periodic filings:
most 2026 annual/quality rows have a later 10-Q. They remain WATCH, not silently
upgraded.

### P6.17 scenario counts (E/W/B)

| Scenario | Value | Quality | GARP |
|---|---:|---:|---:|
| Conservative | 9/0/41 | 29/0/21 | 11/0/39 |
| Balanced | 16/0/34 | 36/0/14 | 16/0/34 |
| Aggressive | 34/0/16 | 43/0/7 | 24/0/26 |

`final_scenario_counts` are generated from the same per-row final status logic;
they are not independently hand-written.

### Final ELIGIBLE

Value (13):

```text
ABG, GPI, CCS, EFOR, KBH, DXC, VTOL,
LEA, CTVA, SLVM, SPB, INGM, WHR
```

Quality (3):

```text
MU, UI, WDFC
```

GARP (0): no candidate passes freshness + SEC + liquidity + valuation gates.

## 6. Raw Top20 and corrected views

Original Top20 (unchanged from P6.15/P6.16 raw rankings):

Value:

```text
CRMT, LIVE, WETH, SSTK, CAAS, CTRM, VISN, EBS, KROS, NUS,
MNDO, PSFE, BOSC, RGS, ABG, CRMD, USNA, NATR, IMMR, JL
```

Quality:

```text
TPL, BUDA, USLM, IDR, INMD, CRDO, FIZZ, MLI, NVDA, BDTX,
NVEC, RAVE, IRMD, KROS, RIGL, MU, SNDK, UTHR, KRYS, EVER
```

GARP:

```text
CDZI, PROP, DVLT, QXO, GEVO, SMTK, NIXX, EOSE, WKHS, ONDS,
SPRU, NTRP, WKSP, IBRX, SPWR, TRAW, SPRO, AEVA, ACTG, FDMT
```

P6.17 final ELIGIBLE is intentionally much shorter; the full
freshness/liquidity/valuation-adjusted ordering is in the audit CSVs.

## 7. Special models / BDC

BDC remains 0 explicitly classified rows, 0 SIC 6726 rows, and 8 name
candidates (`BBDC`, `CCAP`, `GSBD`, `ICMB`, `KBDC`, `LIEN`, `PSBD`, `TPVG`) all
currently `UNCLASSIFIED/US_GAAP`. This is a coverage gap, not a statement that
no BDCs exist. No BDC model was invented.

REIT remains `SPECIAL_MODEL_REQUIRED`; Banks/Insurance have P/B+ROE but no
validated specialized model in this round. Special-model names cannot become
ELIGIBLE through the generic screen.

## 8. Key hashes and dates

Data cutoff: **2026-11-05**. ADV last completed session: **2026-11-05**.

| File | Bytes | SHA256 |
|---|---:|---|
| `liquidity_ohlcv_p616.csv` | 28,269 | `b66bf4f9bf255a74699a309964083c491d041de07b21d0592e51854c113a102f` |
| `liquidity_sessions_p617.csv` | 1,489,097 | `94b485c77c852a1b91fe64369702b3ab90ca010900040d175dc32da8f8bfd47c` |
| `quote_metadata_p617.json` | 690 | `40f3d60c13acf53484dbf70c041410eb0149c0c2b65c998a8334cd1bbfab7342` |
| `sec_filing_history_p617.csv` | 1,407,902 | `08b8201c7ec797a828801e83c91bec18564d8faa42c46f6058875d65ac0713c0` |
| `filing_freshness_audit_p617.csv` | 30,937 | `0ce9a6094708a0b02c10b5b9f72c9de28e36dcee2e88337ea8c41579868060e3` |
| `filing_freshness_summary_p617.json` | 2,003 | `b86d0bf8d54da6db6a29079c782bfeb742db8863379a4e737a014ec222a2b777` |
| `liquidity_quality_audit_p617.csv` | 14,357 | `1247804c72bfbffeded7ab6308ce1c10d5fb0cd6b483614e99e365727288e226` |
| `valuation_recalculation_audit_p617.csv` | 28,855 | `f35a64488dd0e2d21f621b3b49f0996474b18da77fd2de60de616dce629b9cd6` |

## 9. Outputs

```text
valuation_recalculation_audit_p617.csv
valuation_recalculation_summary_p617.json
sec_filing_history_p617.csv
filing_freshness_audit_p617.csv
filing_freshness_summary_p617.json
liquidity_quality_audit_p617.csv
tradability_reconciliation_p617.csv
selection_quality_report_p617.json
```

Supporting snapshots:

```text
liquidity_ohlcv_p616.csv
liquidity_sessions_p617.csv
liquidity_fetch_summary_p616.json
quote_metadata_p617.json
```

## 10. Boundaries

- PIT backtest remains blocked.
- 6-K content is not parsed; a 6-K is not confirmation of financial data.
- SEC companyfacts are not used here for a full XBRL tag/unit reconciliation;
  readiness inputs already contain USD values, and tags are recorded as absent.
- ADV is a free yfinance snapshot, not execution-grade data.
- No Alpha, return, Sharpe, drawdown, win-rate or transaction-cost claim.
- PR #512 remains Draft and unmerged.
