# Six-Style Full-Market Data Readiness — P6.4

Date: 2026-11-05
Branch: `research/us-market-six-styles-p64`
Status: **READINESS AUDIT ONLY — no scores, no backtests**

## 1. Inputs and artifact

- P6.1 current registry: `data/universe/us_equities_current.csv`
- P6.2 quote mapping: `data/universe/us_market_quote_mapping_p62.csv`
- P6.2 quote coverage: `data/universe/us_market_quote_coverage_p62.json`
- P6.3 coverage: `data/universe/sec_fundamentals_coverage_p63.csv`
- P6.3 audit: `data/universe/sec_fundamentals_audit_p63.json`
- P6.3 panel artifact: `sec-fundamentals-p63` (`13402038887`), run `42001009069`

The P6.3 panel was downloaded from the existing GitHub Actions artifact. The
1.4GB SEC bulk ZIP was **not** downloaded again.

## 2. Pool accounting

| Metric | Value |
|---|---:|
| Target Common + ADR | **5,502** |
| Common | 5,187 |
| ADR | 315 |
| Unique tickers | 5,502 |
| Unique target CIKs | **5,452** |
| Records without CIK | **8** |
| UNCLASSIFIED records | 113 |
| UNCLASSIFIED unique CIKs | 99 |

CompanyFacts is issuer-level: the 5,502 securities map to 5,452 unique CIKs.
Multiple tickers sharing a CIK share financial facts but keep separate quote
and valuation rows.

## 3. Style status summary

### INPUT_READY

| Style | Count |
|---|---:|
| Value | **0** |
| Quality | **322** |
| GARP | **0** |
| Trend | **0** |
| Dividend | **0** |
| Hedge | **0** |

### Full status counts

| Style | DATA_AVAILABLE | DATA_QUALITY_PASS | INPUT_READY | SCORE_READY | BACKTEST_READY |
|---|---:|---:|---:|---:|---:|
| Value | 1,037 | 4,290 | **0** | 0 | 0 |
| Quality | 1,002 | 3,903 | **322** | 0 | 0 |
| GARP | 973 | 4,071 | **0** | 0 | 0 |
| Trend | 5,465 | 23 | **0** | 0 | 0 |
| Dividend | 459 | 1,814 | **0** | 0 | 0 |
| Hedge | 5,465 | 23 | **0** | 0 | 0 |

`DATA_AVAILABLE` and `DATA_QUALITY_PASS` are not score or backtest readiness.

## 4. Value

Available/quality-pass counts exist, but **INPUT_READY is 0** because:

```text
market-wide share-class verification is absent
ADR ratio is unverified
EV / EBITDA inputs are not established market-wide
```

The P5.3 28-company share-class validation was **not** generalized to the full
market. PE, PB, P/S, earnings yield and P/CF may be mechanically computable for
some securities, but they are not automatically comparable or complete Value
inputs.

Principal blockers:

```text
VALUE_SHARE_CLASS_OR_ADR_RATIO_UNVERIFIED   5502
VALUE_EV_EBITDA_UNVERIFIED                  5502
```

## 5. Quality

Quality is the only style with confirmed `INPUT_READY`:

```text
322 securities
```

Reasons for the small count:

- 5,007 target securities have no reliable industry classification in the
  current P6.1 registry;
- 157 records are in special sectors requiring separate models;
- Quality requires at least two annual NetIncome observations and two instant
  Assets/Equity observations;
- IFRS and US GAAP are kept separate;
- mixed accounting standards do not enter the industrial model.

No banks, insurers, REITs or BDCs were forced into a generic industrial model.
Known special-sector records are marked `SPECIAL_INDUSTRY_MODEL_REQUIRED`;
unknown/missing sectors are marked `INDUSTRY_CLASSIFICATION_MISSING`.

## 6. GARP

- Historical growth pass: **4,071**.
- `INPUT_READY`: **0**.
- `FORWARD_GROWTH_READY`: **0**.
- Forward EPS / PEG: **DATA_BLOCKED**.

Historical Revenue/EPS growth can be measured, but no free, credible forward
EPS source was found. Historical EPS is not being relabeled as analyst forward EPS.

## 7. Trend

| Component | Count |
|---|---:|
| Current quote ready | **5,488** |
| Historical price ready | **23** |
| PIT universe ready | **0** |
| Trend backtest ready | **0** |

The 5,488 current quotes include 4 ambiguous and 10 invalid target rows from P6.2.
Only the previously audited 28-company history subset contains 23 quality-pass
series. This is not a market-wide historical price dataset.

Trend remains blocked by:

```text
TREND_PIT_UNIVERSE_NOT_READY
TREND_HISTORY_NOT_MARKET_WIDE
```

`BACKTEST_READY` is false for all 5,502, and the P6.3 PIT date is still a
next-weekday approximation without holiday adjustment.

## 8. Dividend

| Class | Count |
|---|---:|
| Confirmed dividend payer (any DividendsPaid) | **2,273** |
| Dividend data missing | **3,229** |
| Confirmed non-payer | **0** |

Status:

| Status | Count |
|---|---:|
| DATA_AVAILABLE | 459 |
| DATA_QUALITY_PASS | 1,814 |
| INPUT_READY | 0 |

Missing `DividendsPaid` is **not** treated as zero dividends. DPS, frequency,
announcement timing, FCF and payout ratios are not complete enough for
`INPUT_READY`.

## 9. Hedge / risk control

| Component | Count |
|---|---:|
| Current quote available | 5,488 |
| Risk-control input ready | **23** |
| Options hedge input ready | **0** |

Risk-control metrics (volatility, beta, correlation, drawdown, liquidity proxy)
are only supported for the 23 historical series. Historical option chains,
implied volatility, Greeks, borrow availability/cost and financing cost are not
available, so this is not an options-hedge dataset.

## 10. Industry coverage

| Industry group | Records | Quality INPUT_READY |
|---|---:|---:|
| Information Technology | 75 | 73 |
| Industrials | 81 | 77 |
| Health Care | 60 | 58 |
| Consumer Discretionary | 46 | 45 |
| Consumer Staples | 32 | 28 |
| Communication Services | 21 | 21 |
| Materials | 23 | 20 |
| Utilities | 31 | 0 (special) |
| Financials | 75 | 0 (special) |
| Real Estate | 30 | 0 (special) |
| Energy | 21 | 0 (special) |
| **INDUSTRY_CLASSIFICATION_MISSING** | **5,007** | **0** |

Banks, insurance, REITs and BDCs cannot be separated from the current
S&P-sector-only map. No name-based guessing was used.

## 11. Accounting and exchange

| Accounting | Records | Quality INPUT_READY |
|---|---:|---:|
| US GAAP | 4,774 | 322 |
| IFRS | 455 | 0 |
| MIXED | 96 | 0 |
| NONE | 177 | 0 |

| Exchange | Records | Quality INPUT_READY |
|---|---:|---:|
| NASDAQ | 3,397 | 121 |
| NYSE | 1,861 | 201 |
| NYSE American | 237 | 0 |
| Other/Arca/BZX | 7 | 0 |

## 12. Cross-cutting blockers

Top blockers:

```text
VALUE_SHARE_CLASS_OR_ADR_RATIO_UNVERIFIED   5502
VALUE_EV_EBITDA_UNVERIFIED                  5502
GARP_FORWARD_EPS_MISSING                    5502
TREND_PIT_UNIVERSE_NOT_READY                5502
TREND_HISTORY_NOT_MARKET_WIDE               5502
OPTIONS_HISTORY_BORROW_FINANCING_MISSING    5502
INDUSTRY_CLASSIFICATION_MISSING             5007
QUALITY_INDUSTRY_MODEL_UNRESOLVED           5007
```

## 13. What can be shared

Shared by CIK:

- SEC financial facts;
- accounting-standard classification;
- Revenue, NetIncome, Assets, Equity, OCF, Cash, Debt, Shares facts.

Must remain security-level:

- current quote and market cap;
- share class;
- ADR ratio;
- per-ticker valuation;
- liquidity and price history.

## 14. Free-source assessment

Reusable:

- Nasdaq Trader directories;
- SEC CompanyFacts bulk;
- AkShare current quote batch.

Confirmed insufficient for full readiness:

- no free forward EPS consensus;
- no historical option chains / Greeks / borrow cost;
- no complete dividend announcement/payment calendar;
- no market-wide historical PIT price coverage;
- no market-wide industry/SIC classification in the P6.1 registry.

## 15. Next phase

P6.5 should prioritize **Quality** first: it already has 322 `INPUT_READY`
securities with verified accounting standards and sufficient annual/instant
history. Before a formal score, add an industry/SIC source and keep special
industries separate.

Do not start full Value until share-class and ADR ratio verification exists.
Do not start GARP PEG until a credible forward EPS source exists.
