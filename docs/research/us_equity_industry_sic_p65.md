# SEC SIC Industry Enrichment and Quality Readiness — P6.5

Date: 2026-11-05
Branch: `research/us-equity-industry-p65`
Status: **SIC ENRICHMENT + QUALITY READINESS RE-AUDIT — no scores/backtests**

## 1. Source and run

- SEC submissions bulk: `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip`
- HTTP HEAD/GET: 200 / 200
- Size: **1,572,980,361 bytes**
- Last-Modified: Thu, 05 Nov 2026 06:11:55 GMT
- SHA-256: `bff9c5a5e95760238bbf007985a7c9605911982815c644269fe3d914ccb37097`
- Run: https://github.com/wijouyang-lab/us/actions/runs/42011831175
- Artifact: `us-equity-industry-p65` (`13407960895`)
- CompanyFacts and AkShare quotes were **not** re-downloaded.
- Raw submissions ZIP is gitignored.

`SEC_USER_AGENT` came from GitHub Actions Secret; no email is written in code.

## 2. SIC coverage

| Metric | Result |
|---|---:|
| Target Common + ADR | **5,502** |
| Records with SIC | **5,403** |
| Records without SIC | **99** |
| SIC coverage | **98.20%** |
| Unique target CIKs | **5,452** |
| Unique CIKs with SIC | **5,361** |
| Unique CIK SIC coverage | **98.33%** |
| SIC code missing | 99 |
| SIC description missing (where SIC exists) | 6 |
| UNCLASSIFIED records | 113 |
| UNCLASSIFIED with SIC | 81 |
| UNCLASSIFIED unique CIKs | 99 |

By security type:

| Type | Records | With SIC | Coverage |
|---|---:|---:|---:|
| Common | 5,187 | 5,089 | 98.11% |
| ADR | 315 | 314 | 99.68% |

By exchange:

| Exchange | Records | With SIC | Coverage |
|---|---:|---:|---:|
| NASDAQ | 3,397 | 3,379 | 99.47% |
| NYSE | 1,861 | 1,784 | 95.86% |
| NYSE American | 237 | 233 | 98.31% |
| NYSE Arca | 1 | 1 | 100% |
| Cboe BZX | 1 | 1 | 100% |
| OTHER:F | 5 | 5 | 100% |

## 3. Model family counts

SEC SIC is **not GICS**. The model family is a separate deterministic mapping
with a rule ID for every row.

| Model family | Records |
|---|---:|
| BANKS | **329** |
| INSURANCE | **104** |
| REIT | **164** |
| BDC | **0** |
| OTHER_FINANCIALS | **367** |
| UTILITIES | 127 |
| ENERGY | 130 |
| MATERIALS | 329 |
| INDUSTRIALS | 585 |
| TECHNOLOGY | 823 |
| COMMUNICATIONS | 154 |
| HEALTHCARE | 963 |
| CONSUMER_DISCRETIONARY | 358 |
| CONSUMER_STAPLES | 164 |
| OTHER_SERVICES | 806 |
| UNCLASSIFIED | **99** |

BDC remains 0 because no target issuer had both a SIC and an explicit
Business Development Company description. BDCs were not inferred from ticker or
company name; many BDCs are in the 99 missing-SIC group.

## 4. S&P 500 cross-check

| Consistency | Count |
|---|---:|
| Consistent | 365 |
| Inconsistent | 130 |
| No S&P 500 sector | 4,908 |
| Missing SIC | 99 |

Both `sic` and `sp500_sector` are retained on every row. Inconsistency is not
silently overwritten. Examples include:

```text
AAPL  SIC 3571 Electronic Computers / S&P Information Technology
AMGN  SIC 2836 Biological Products / S&P Health Care
COST  SIC 5331 Variety Stores / S&P Consumer Staples
```

SIC and GICS/sector are different systems; no claim of equivalence is made.

## 5. Quality re-audit

| Category | Count |
|---|---:|
| QUALITY_STANDARD_MODEL_DATA_AVAILABLE | **4,225** |
| QUALITY_STANDARD_MODEL_INPUT_READY | **3,342** |
| QUALITY_SPECIAL_MODEL_REQUIRED | **883** |
| QUALITY_INDUSTRY_MISSING | **99** |
| QUALITY_ACCOUNTING_STANDARD_BLOCKED | **273** |
| UNCLASSIFIED records | 113 |
| UNCLASSIFIED `INPUT_READY` (separate) | 44 |

By type:

| Type | Data available | Standard INPUT_READY | Special | Industry missing |
|---|---:|---:|---:|---:|
| Common | 3,980 | **3,141** | 839 | 98 |
| ADR | 245 | **201** | 44 | 1 |

By accounting:

| Standard | Records | INPUT_READY |
|---|---:|---:|
| US GAAP | 4,774 | **3,031** |
| IFRS | 455 | **311** |
| MIXED | 96 | 0 |
| NONE | 177 | 0 |

Special families (Banks, Insurance, Other Financials, REIT, BDC, Utilities,
Energy) are not forced into the standard Quality model. Standard families are
Materials, Industrials, Technology, Communications, Healthcare, Consumer
Discretionary, Consumer Staples and Other Services.

## 6. Reproduction of the old 322

| Metric | Count |
|---|---:|
| P6.4 old INPUT_READY | 322 |
| P6.5 new INPUT_READY | 3,342 |
| Intersection | **317** |
| Lost | **5** |
| Gained | 3,025 |

Lost tickers:

```text
CI, CNC, ELV, HUM, UNH
```

Reason: their SEC SIC is health insurance, so they now map to `INSURANCE` and
require a special model. P6.4 had used the S&P `Health Care` sector and treated
them as standard industrial-model candidates. This is an explicit, auditable
industry correction, not data loss.

317 of the old 322 remain reproducible. The 3,025 gained are mostly issuers
that previously had no industry classification but now have a valid SEC SIC.

## 7. Remaining missing-SIC securities

99 target records have no SIC. Examples:

```text
BOT, CCAP, CSWC, FRBA, HIFS, HRZN, ICMB, LIEN, NBN, NMFC,
OZK, PFX, PWRL, RCBC, RWAY, SAEN, SSBI, TOWN, ASBH,
BBDC, BCAT, BCSF, BCX, BIT, BMEZ, BMN, BOE, BST, BSTZ,
BTX, CEV, CION, DXYZ, ECAT, ECC, EFT, EIC, EQS, ETO, ETX,
EVF, EVN, FINS, FSCO, FSK, FT, FTF, GAB, GAM, GDV, GGT,
GGZ, GLU, GRX, GSBD, GUT, HQL, HTGC, IGI, IIM, IQI, IVAI,
KBDC, MAIN, MCI, MPV, NCDL, NXP, OBDC, OIA, OTF, PDCC,
PFLT, PIM, PMM, PMO, PNNT, PPT, PSBD, PSUS, RGT, RMT, RVT,
SCM, SPMC, TPVG, TRIN, TSLX, TY, TYG, VCV, VGM, VKI, VKQ,
VMO, VPV, VTN, VVR, XFLT
```

8 have no CIK at all. The rest lack SIC in the submissions data or were not
found in the bulk archive. No name-based inference was used.

## 8. Files

```text
tools/research/enrich_us_equity_industry_p65.py
tools/research/audit_quality_industry_readiness_p65.py
tests/test_us_equity_industry_p65.py
data/universe/us_equity_industry_sic_p65.csv
data/universe/sec_sic_model_family_map_p65.csv
data/universe/us_equity_industry_coverage_p65.json
data/universe/us_equity_quality_readiness_p65.csv
data/universe/sec_submissions_p65_meta.json
docs/research/us_equity_industry_sic_p65.md
.github/workflows/research-us-equity-industry-p65.yml
```

## 9. Tests

```text
tests/test_us_equity_industry_p65.py  9 passed
```

Covered:

- shared CIK across multiple tickers;
- raw SIC preservation;
- no-SIC UNCLASSIFIED;
- bank/insurance/REIT separation;
- BDC only with explicit description;
- ADR sharing issuer SIC while keeping a security row;
- no-CIK stays UNCLASSIFIED;
- S&P sector inconsistency retained;
- SIC does not automatically imply Quality INPUT_READY;
- old 322 reproduction (317 intersection, 5 documented losses).

## 10. Conclusion

SIC coverage is **98.20%** by security and **98.33%** by unique CIK. The main
industry gap fell from 5,007 to **99**.

Quality `INPUT_READY` rises to **3,342**, but this is a data-readiness count,
not a Quality score. Formal `SCORE_READY` and `BACKTEST_READY` remain **0**.

Next phase can start **Quality V1** for standard-model issuers, while keeping
Banks, Insurance, Other Financials, REIT, BDC, Utilities and Energy on separate
model tracks. IFRS remains separate from US GAAP.
