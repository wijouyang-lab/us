# SEC Cash Dividend Proxy — P6.13

Date: 2026-11-06
Branch: `research/sec-cash-dividend-proxy-p613`
Status: **ISSUER-LEVEL CASH PROXY FEASIBLE; TICKER-LEVEL DPS NOT ESTABLISHED**

## 1. P6.12 corrections

### Yahoo split adjustment

For 23 sample tickers with split history:

```text
SPLIT_ADJUSTMENT_OBSERVED_ADJUSTED = 19
SPLIT_ADJUSTMENT_UNVERIFIED = 4
NO_SPLIT_IN_HISTORY = 7
```

The validation compares pre/post-split DPS with the split factor. Yahoo is not
treated as uniformly verified; 4 cases remain `SPLIT_ADJUSTMENT_UNVERIFIED`.

### Nasdaq identity

Nasdaq rows now include:

```text
identity_status
security_type_verified
issuer_cik
```

All 13 attempted Nasdaq-listed sample rows match current ticker and Common/ADR
identity; no Preferred row is mixed into Common. This is not a general guarantee
that all Nasdaq preferred records are safe.

### Smarter counts

```text
current dividend profile: 30
recent last-payment event:  26
```

These are separate. A profile can exist without a returned last-payment event.

## 2. SEC fact inventory

Source: P6.3 normalized panel plus the existing 28-CIK raw CompanyFacts cache.
No SEC ZIP was downloaded.

| Fact | Count |
|---|---:|
| Total cash-dividend rows | **135,281** |
| Unique CIKs with cash facts | **2,300** |
| Positive payer evidence | **2,248** |
| No positive fact in window | **52** |
| Dividend status unknown | **3,249** |
| Complete filed dates | **2,300** |
| Duplicate facts detected | **5** |
| Negative raw values | **263** |
| Per-share rows from raw cache | **5,768** |
| Per-share CIKs in raw cache | **23** |

Actual cash tags:

| Taxonomy / tag | Rows |
|---|---:|
| `us-gaap:PaymentsOfDividendsCommonStock` | 77,326 |
| `us-gaap:PaymentsOfDividends` | 53,754 |
| `ifrs-full:DividendsPaid` | 4,201 |

Actual per-share tags in the raw cache:

```text
CommonStockDividendsPerShareDeclared   2,883
CommonStockDividendsPerShareCashPaid   2,885
```

These per-share tags are **not** in the P6.3 normalized panel and are available
only for the 23 cached CIKs, not full-market.

## 3. Currency and sign

Cash facts by unit:

```text
USD 131,805
CAD     807
JPY     352
EUR     483
GBP     315
CNY     422
other currencies ...
```

- Raw sign is preserved in `raw_value`.
- `normalized_cash_dividend` is the positive magnitude only for confirmed cash
  tags and compatible units.
- 263 rows have negative raw values; sign is preserved and flagged.
- Non-USD amounts are retained but not treated as directly comparable USD cash.

## 4. Coverage and allocation

| Status | Count |
|---|---:|
| Ticker-allocable Common | **5,100 CIKs** |
| Issuer-level, not ticker allocable | **141** |
| ADR ratio unverified | **308** |
| Multi-class issuers | **45** |
| TTM available | **6** |
| TTM unavailable | **5,543** |

`ISSUER_LEVEL_NOT_TICKER_ALLOCABLE` covers multi-ticker issuers and
unclassified/unsupported securities. Company total cash dividends are not
divided among tickers.

## 5. Payer evidence

```text
CONFIRMED_PAYER_EVIDENCE             2,248
NO_POSITIVE_FACT_IN_OBSERVATION_WINDOW  52
DIVIDEND_STATUS_UNKNOWN               3,249
CONFIRMED_NON_PAYER                       0
```

A positive SEC cash fact is payer evidence, not proof of a complete dividend
event history. No-fact records remain unknown.

## 6. Can TTM be reconstructed?

Only **6** CIKs have four contiguous, non-overlapping quarterly cash-dividend
facts. Most have annual or YTD-only facts; **TTM_UNAVAILABLE**.

No quarter/YTD amount is summed as a year. No future filing is used to fill a
historical TTM.

## 7. Cash amount vs DPS

These are separate:

- `CASH_DIVIDENDS_PAID`: issuer-level total cash paid;
- `CASH_DIVIDEND_PROXY`: issuer-level cash scale/persistence;
- `DPS`: per-share amount, absent from the normalized full-market panel.

Per-share facts from the raw cache are stored as `PER_SHARE_FACT` with
`normalized_cash_dividend` blank. They are never mixed with total cash.

## 8. Interpretation

`CASH_DIVIDEND_PROXY` is feasible only as:

```text
issuer-level cash amount / persistence / direction
```

It is not yet a cross-company yield or per-ticker dividend factor because:

- no full-market per-share facts;
- no ticker allocation for multi-class/ADR;
- only 6 TTM reconstructions;
- currency mix;
- no event dates;
- no confirmed non-payers.

Absolute cash amounts are scale-dependent. Without a validated denominator, they
must not be used as a cross-sectional yield factor.

## 9. Historical PIT / prediction

P6.7 strict PIT remains failed:

```text
member-session coverage 79.58% < 95%
ticker coverage 69.77% < 98%
```

The current snapshot is not a complete historical PIT dataset and cannot support
a predictive claim. `CASH_DIVIDEND_PROXY` is research infrastructure only.

## 10. Verdict

```text
SEC_CASH_DIVIDEND_PROXY = FEASIBLE_AT_ISSUER_LEVEL
TICKER_LEVEL_DPS = NOT_ESTABLISHED
FULL_HISTORICAL_PIT = NOT_READY
```

Useful fields:

- total cash paid by issuer;
- positive payer evidence;
- annual/period cash amounts;
- tag/taxonomy/accession provenance.

Not usable yet:

- ticker-level DPS from total cash;
- multi-class/ADR allocation;
- full-market TTM;
- dividend event dates;
- cross-company yield without a denominator;
- predictive/Alpha claims.

No production score, scan, trading, stop-loss, ledger or Dashboard change.
