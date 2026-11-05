# US Dividend Event Source Audit — P6.11

Date: 2026-11-05
Branch: `research/us-dividend-source-p611`
Status: **SOURCE UNAVAILABLE — 30-security feasibility audit, zero event responses**

## 1. AkShare capability check

Installed version: **1.20.2**.

| Check | Result |
|---|---|
| `stock_us_dividend_payout` exists | **No** |
| `stock_us_financial_indicator` exists | **No** |
| US dividend-event endpoint | **None** |
| Alternative `stock_financial_us_analysis_indicator_em` | Exists |
| Alternative signature | `(symbol, indicator)` |
| Alternative endpoint | Eastmoney `datacenter.eastmoney.com/securities/api/data/v1/get`, `RPT_USF10_FN_GMAININDICATOR` |
| Alternative payout field | `PAYOUT_RATIO` present |
| Alternative DPS / ex-date / payment-date fields | **None** |
| Network requests made | **0** |

The alternative is a financial-indicator endpoint, not a dividend-event API. It
cannot supply per-share dividend, announcement, ex-date, record date or payment
date.

## 2. 30-security sample

Selection from the P6.1 universe:

| Group | Count | Purpose |
|---|---:|---|
| A. recent SEC cash-flow payer | 18 | event-source success test |
| B. historical / unclear / no recent fact | 6 | stopped or irregular dividend test |
| C. no SEC dividend fact | 3 | empty-response behavior |
| D. ADR | 3 | ADR ratio/currency test |

Group A includes **CAT** and **BAC** as required regression names (BAC is in
group B because P6.3 has no recent `DividendsPaid` fact for it).

Sample tickers:

```text
A: CAT, KO, PG, XOM, O, NEE, VZ, MCD, HD, IBM, CSCO, F,
   PEP, WMT, T, LOW, INTC, PLD
B: BAC, JNJ, DUK, AAL, AURE, BBGI
C: ABNB, ACAD, AAOI
D: ASML, BZ, ATAT
```

## 3. Event source result

| Metric | Count |
|---|---:|
| Securities attempted | 30 |
| Successful historical dividend-event responses | **0** |
| Events returned | **0** |
| DPS present | **0** |
| announcement_date complete | **0** |
| ex_dividend_date complete | **0** |
| record_date complete | **0** |
| payment_date complete | **0** |
| currency complete | **0** |
| Duplicate events | **0** |

Status:

```text
SOURCE_UNAVAILABLE:       30
DIVIDEND_STATUS_UNKNOWN:  30
DIVIDEND_EVENTS_FOUND:     0
DIVIDEND_EVENT_FIELDS_COMPLETE: 0
CONFIRMED_NON_PAYER:       0
```

No empty response was interpreted as a non-payer.

## 4. SEC cross-check

| SEC fact | Sample count |
|---|---:|
| Cash-flow `DividendsPaid` fact | **24** |
| Positive SEC cash-dividend evidence | **25** |
| Per-share dividend fact in P6.3 metric map | **0** |
| SEC per-share tag available | **No** |

The P6.3 normalized panel contains `DividendsPaid` (total cash paid), but not:

```text
CommonStockDividendsPerShareDeclared
CommonStockDividendsPerShareCashPaid
```

`DividendsPaid` is **not** DPS and is not substituted for DPS. No vendor event
field can be reconciled against SEC per-share facts.

## 5. ADR

Three ADR names were selected. No vendor events were returned, and ADR ratios
were not verified. ADR DPS, record/payment dates and currency conversion are
therefore **not computable**. Raw ADR events would be retained separately if a
source existed; no final ADR DPS is produced here.

## 6. Empty-response behavior

The empty event file is not treated as proof of non-payment:

- `CONFIRMED_NON_PAYER = 0`;
- `DIVIDEND_STATUS_UNKNOWN = 30`;
- the 25 positive SEC cash-flow facts are separate evidence, not event-level
  confirmation.

## 7. Should this source be expanded to 5,502?

**No.**

Current source cannot supply any of the required event fields. Expanding it would
produce 5,502 empty/unknown records, not dividend data.

If a future AkShare version exposes a real US dividend-event endpoint:

- at least **5,502 sequential requests** (plus ADR-specific checks);
- approximately **1.5+ hours** at 1 second/request minimum;
- provider rate-limit and IP-block risk;
- no bulk response demonstrated;
- ADR ratio/currency still needs independent verification.

That expansion is not justified before a working event endpoint is validated on
this 30-name sample.

## 8. Verdict

```text
AKSHARE_US_DIVIDEND_EVENT_SOURCE = UNAVAILABLE
```

The 30-name pilot cannot establish DPS, announcement, ex-date, record date,
payment date, frequency or currency. SEC cash-flow `DividendsPaid` is useful as
payer evidence only. No confirmed non-payer can be inferred from empty vendor
responses.

No production score, scan, trade, dashboard or P6.1–P6.10 result was changed.
