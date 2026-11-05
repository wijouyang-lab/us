# Issuer Market Cap and Value V1 Readiness — P6.8

Date: 2026-11-05
Branch: `research/value-market-cap-p68`
Status: **DATA READINESS AUDIT ONLY — no formal Value score/backtest**

## 1. Market-cap semantics

P6.2 `quote_market_cap_raw` is not automatically an issuer-total market cap:

- 45 CIKs have multiple tickers;
- 86 target security records are in multi-ticker CIKs;
- B/A-class examples have different raw caps per ticker;
- 314 ADR records cannot be validated without ADR ratios;
- only one multi-ticker CIK had identical caps across its tickers (3 records); that is evidence, not proof of issuer-total semantics.

Validation rule used:

```text
single-ticker Common
+ non-ADR
+ positive cap and price
+ SEC CommonSharesOutstanding available
+ implied shares = cap / price within 10% of SEC shares
=> ISSUER_MARKET_CAP_VALIDATED
```

This is a cap/price/SEC-share reconciliation, not a new filing fetch.

## 2. Market-cap status

| Status | Records |
|---|---:|
| `ISSUER_MARKET_CAP_VALIDATED` | **3,685** |
| `ISSUER_MARKET_CAP_CONFLICT` | **741** |
| `SHARE_CLASS_MARKET_CAP_UNVERIFIED` | **697** |
| `ADR_MARKET_CAP_UNVERIFIED` | **314** |
| `MARKET_CAP_MISSING` | **65** |
| Total | **5,502** |

Market cap present: **5,437 / 5,502**.

| Type | Records | Cap present | Validated | Value DATA_READY |
|---|---:|---:|---:|---:|
| Common | 5,187 | 5,123 | 3,685 | 2,529 |
| ADR | 315 | 314 | 0 | 0 |

## 3. Value V1 readiness

| Status | Records |
|---|---:|
| `VALUE_V1_DATA_READY` | **2,529** |
| `VALUE_V1_BLOCKED` | **1,653** |
| `VALUE_SPECIAL_MODEL_REQUIRED` | **1,320** |

No ADR is in the standard `VALUE_V1_DATA_READY` pool. No special industry is
forced into the standard enterprise model.

## 4. Metric coverage

Denominator: 5,502 target securities.

| Metric | Ticker ready | Ticker coverage | Unique CIK coverage |
|---|---:|---:|---:|
| PE | 2,035 | **36.99%** | 37.33% |
| P/B | 3,280 | **59.61%** | 60.16% |
| P/S | 2,963 | **53.85%** | 54.35% |
| Earnings Yield | 3,466 | **63.00%** | 63.57% |
| FCF Yield | 2,808 | **51.04%** | 51.50% |
| EV/EBITDA | 0 | **0%** | 0% |

PE is restricted to positive Net Income. Negative earnings are retained in
Earnings Yield, not deleted.

FCF is only calculated when both OCF and CapEx exist; missing CapEx is not
treated as zero.

EV/EBITDA is blocked because Depreciation & Amortization is not in the P6.3
mapped metric set:

```text
EV_EBITDA -> EV_DATA_INCOMPLETE
DEPRECIATION_AMORTIZATION_NOT_IN_P63_METRIC_MAP
```

## 5. Provider PE reconciliation

| Metric | Count |
|---|---:|
| Derived and provider PE both available | **2,035** |
| Absolute mismatch > 20% | **1,108** |
| Mismatch rate | **54.45%** |

Possible causes include provider TTM vs annual NetIncome, share-class market
cap semantics, and provider adjustment methodology. No "better" value was
silently selected.

## 6. Multi-class / ADR treatment

- Multi-ticker CIKs: **45**
- Multi-ticker security records: **86**
- ADR records: **314** with cap present (1 missing)
- Records requiring independent class/ADR handling: **1,011**
  - 314 ADR
  - 697 share-class-unverified Common

`quote_market_cap_raw` must not be treated as issuer total for these records.
For A/B classes, the caps differ by ticker; summing and ADR-ratio conversion
remain separate research work.

## 7. Industry applicability

| Family | Records | Cap validated | Value DATA_READY |
|---|---:|---:|---:|
| TECHNOLOGY | 823 | 530 | 512 |
| INDUSTRIALS | 585 | 423 | 405 |
| HEALTHCARE | 963 | 713 | 657 |
| CONSUMER_DISCRETIONARY | 358 | 245 | 234 |
| CONSUMER_STAPLES | 164 | 103 | 96 |
| COMMUNICATIONS | 154 | 66 | 60 |
| MATERIALS | 329 | 243 | 211 |
| OTHER_SERVICES | 806 | 392 | 354 |
| BANKS | 329 | 291 | 0 (special) |
| INSURANCE | 104 | 90 | 0 (special) |
| OTHER_FINANCIALS | 367 | 214 | 0 (special) |
| REIT | 164 | 148 | 0 (special) |
| UTILITIES | 127 | 97 | 0 (special) |
| ENERGY | 130 | 103 | 0 (special) |
| UNCLASSIFIED | 99 | 27 | 0 |

Banks should use P/B and related financial metrics, not standard PE/EV.
REITs need P/B/FFO-style treatment; standard EV/EBITDA is not established here.
Insurance and other financials also require separate applicability rules.

## 8. Accounting

| Standard | Records | Value DATA_READY |
|---|---:|---:|
| US GAAP | 4,774 | 2,430 |
| IFRS | 455 | 99 |
| MIXED | 96 | 0 |
| NONE | 177 | 0 |

IFRS and US GAAP remain separate.

## 9. What can start next

Metric-level readiness is sufficient for a **sub-indicator** Value study:

- P/B: 3,280 securities;
- Earnings Yield: 3,466;
- P/S: 2,963;
- FCF Yield: 2,808;
- PE: 2,035.

A standard enterprise Value V1 candidate pool of **2,529** is available for
research. It must not be called a score or production-ready model.

## 10. Blockers kept

1. 741 market-cap conflicts.
2. 697 share-class-unverified Common records.
3. 314 ADR records without verified ADR ratios.
4. 65 missing market caps.
5. EV/EBITDA has no D&A field in P6.3, so 0 ready.
6. 1,108 PE provider/derived mismatches require reconciliation.
7. Special industries need separate valuation models.
8. P6.3 PIT remains next-weekday, without exchange holiday adjustment.

No production Value score, scan, trading, stop-loss, ledger, Dashboard or P6.1–P6.7 result was changed.
