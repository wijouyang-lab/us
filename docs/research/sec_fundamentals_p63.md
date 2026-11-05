# SEC Market-Wide Fundamentals — P6.3

Date: 2026-11-05
Branch: `research/us-market-fundamentals-p63`
Status: **BULK COLLECTION COMPLETE — coverage audit only**

## 1. Source and bulk download

Official URL:

```text
https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip
```

Download:

| Field | Value |
|---|---|
| HTTP HEAD/GET | 200 / 200 |
| Content-Length | 1,417,753,205 bytes |
| Last-Modified | Thu, 05 Nov 2026 06:04:26 GMT |
| Downloaded bytes | 1,417,753,205 |
| SHA-256 | `4be51ebf2d25b7770ce8638e54e60b49a362707f6c80049b0efdaafd41607682` |
| ZIP entries | 20,547 |
| Parsed target CIKs | 5,494 |

Only one bulk ZIP request was made. The raw ZIP is gitignored.

Run:

```text
https://github.com/wijouyang-lab/us/actions/runs/42001009069
```

Artifact:

```text
sec-fundamentals-p63
id 13402038887
```

## 2. CIK coverage

| Metric | Count |
|---|---:|
| Target Common + ADR records | **5,502** |
| Records with CIK | **5,494** |
| Unique target CIKs | **5,452** |
| Missing CIK records | **8** |
| UNCLASSIFIED records | 113 |
| UNCLASSIFIED unique CIKs | 99 |
| Panel rows | **6,391,195** |
| Unique CIKs in panel | 5,368 |

Missing CIK tickers:

```text
FRBA, HIFS, NBN, RCBC, SAEN, SSBI, TOWN, ASBH
```

UNCLASSIFIED missing-CIK examples (not in main denominator):

```text
BAC$E, BAC$L, EPR$E, FITB$I, GAB$H, GGN$B, GS$D,
MS$A, MS$F, NLY$F, SCE$L, SCE$M, SCE$N, VNO$L
```

## 3. CompanyFacts coverage

### By record

| Type | Records | With CIK | CompanyFacts found | Coverage | US GAAP | IFRS |
|---|---:|---:|---:|---:|---:|---:|
| Common | 5,187 | 5,180 | 5,036 | **97.09%** | 4,700 | 397 |
| ADR | 315 | 314 | 304 | **96.51%** | 170 | 154 |
| UNCLASSIFIED | 113 | 99 | 73 | 64.60% | 50 | 24 |

### By unique CIK

```text
target unique CIKs: 5,452
unique CIKs with panel facts: 5,298
coverage: 97.17%
```

No CompanyFacts file was parsed for some target CIKs; a file/facts absence is
**not** evidence that the issuer reported nothing. CompanyFacts only contains
standard-taxonomy facts.

### By exchange

| Exchange | Records | Found | Coverage |
|---|---:|---:|---:|
| NASDAQ | 3,397 | 3,325 | 97.88% |
| NYSE | 1,861 | 1,783 | 95.81% |
| NYSE American | 237 | 225 | 94.94% |
| NYSE Arca | 1 | 1 | 100% |
| Cboe BZX | 1 | 1 | 100% |
| OTHER:F | 5 | 5 | 100% |

## 4. Metric coverage

Denominator: **5,502** target Common+ADR records.

| Metric | Any history | Any coverage | Last 12 months | Recent coverage |
|---|---:|---:|---:|---:|
| Revenue | 4,477 | 81.37% | 3,985 | 72.43% |
| NetIncome | 5,275 | 95.87% | 5,004 | 90.95% |
| EPSBasic | 5,026 | 91.35% | 4,699 | 85.41% |
| EPSDiluted | 5,010 | 91.06% | 4,662 | 84.73% |
| TotalAssets | 5,315 | 96.60% | 5,125 | 93.15% |
| StockholdersEquity | 5,309 | 96.49% | 5,113 | 92.93% |
| OperatingCashFlow | 5,298 | 96.29% | 5,061 | 91.98% |
| CapitalExpenditure | 4,208 | 76.48% | 3,603 | 65.49% |
| CashAndCashEquivalents | 4,990 | 90.69% | 4,405 | 80.06% |
| LongTermDebt | 3,464 | 62.96% | 2,600 | 47.26% |
| CommonSharesOutstanding | 4,716 | 85.71% | 4,385 | 79.70% |
| DividendsPaid | 2,273 | 41.31% | 1,821 | 33.10% |

The weakest core fields are:

```text
DividendsPaid
LongTermDebt
CapitalExpenditure
Revenue
```

The strongest are:

```text
NetIncome, TotalAssets, StockholdersEquity, OperatingCashFlow
```

CompanyFacts file presence is not the same as metric completeness.

## 5. ADR / foreign issuers

ADR CompanyFacts coverage is 96.51%, but standard-taxonomy mix differs:

```text
ADR US GAAP: 170
ADR IFRS:    154
```

IFRS facts are retained separately from US GAAP. They are not merged into a
single accounting basis for scoring.

## 6. PIT / period handling

Panel fields include:

```text
cik, entity_name, tickers, metric, taxonomy, tag, unit, value,
start, end, filed, accn, form, fy, fp, frame, period_type,
pit_available_date, pit_rule
```

Periods:

```text
INSTANT
QUARTER
YTD
ANNUAL
OTHER
```

Rules:

- Q2/Q3 YTD is classified as `YTD`, not single-quarter.
- `end` is not treated as the investor-known date.
- `filed` and `accn` are retained.
- `pit_available_date` = next weekday after `filed`.
- PIT rule currently does **not** adjust for exchange holidays and does not use
  acceptanceDateTime. This is conservative but not exact.
- Restatements with the same period and different `accn` are retained, not
  overwritten.
- Units are retained; different units are not mixed in one value.

## 7. Panel output

```text
data/universe/sec_fundamentals_panel_p63.csv.gz
```

Size:

```text
67,433,497 bytes
```

SHA-256:

```text
5687b8644ceb5ccf3d94e055f98a0a204502e68edaebfda3a294899e98a99c31
```

Because it is **>25 MB**, it is uploaded as a GitHub Actions artifact and is
not committed to Git. The audit/coverage CSV and metric map are committed.

## 8. Tests

```text
tests/test_sec_fundamentals_p63.py  4 passed
```

Covered:

- shared CIK for multiple tickers parsed once;
- US GAAP and IFRS recognition;
- accession/filed retention;
- unit separation;
- Q2/YTD not relabeled as quarter;
- restatements retained;
- missing standard tags;
- UNCLASSIFIED separate cohort;
- no network in unit tests.

## 9. Interpretation

What is ready:

- CIK mapping and unique-company accounting;
- bulk CompanyFacts ingestion;
- standard taxonomy mapping;
- raw fact provenance and PIT-safe `filed` dates;
- core metric coverage statistics;
- ADR/IFRS preservation.

What is **not** ready:

- six-style scores;
- cross-accounting-standard comparison;
- complete metric coverage for every issuer;
- precise intraday PIT availability;
- industry completeness thresholds;
- any backtest.

## 10. Next phase

P6.4 can start from the coverage panel, but only for metrics with explicit
coverage gates. Dividend and long-term-debt fields are too sparse for universal
scoring. ADR/IFRS issuers require separate accounting-basis handling.

No production scan, scoring, trading, Dashboard, or PR #497 changes were made.
