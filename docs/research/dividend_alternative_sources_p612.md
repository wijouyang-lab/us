# Free US Dividend Alternative Sources — P6.12

Date: 2026-11-06
Branch: `research/us-dividend-alternative-sources-p612`
Status: **30-name source validation — no full-market collection**

## 1. Sample

Same 30 names as P6.11:

```text
CAT, KO, PG, XOM, O, NEE, VZ, MCD, HD, IBM,
CSCO, F, PEP, WMT, T, LOW, INTC, PLD,
BAC, JNJ, DUK, AAL, AURE, BBGI,
ABNB, ACAD, AAOI,
ASML, BZ, ATAT
```

Groups: 18 recent SEC payer, 6 historical/unclear, 3 no SEC dividend fact,
3 ADR. No SEC ZIP, submissions ZIP or quote re-download.

## 2. SmarterDividends

Endpoint:

```text
GET https://smarterdividends.com/api/v1/stocks/{ticker}
```

Attribution: https://smarterdividends.com/dividend-api

| Result | Count |
|---|---:|
| Requests | 30 |
| HTTP 200 | 30 |
| HTTP 429 | 0 |
| Tickers with returned data | 26 |
| Last-payment events | 26 |
| DPS in last-payment event | 26 |
| Ex-date present | 26 |
| Pay-date present | 23 |
| Declaration date present | **0** |
| Record date present | **0** |
| Currency present | **0** |
| Raise/cut records (not payments) | **957** |
| Full payment history | **No** |

Actual response contains:

```text
current/annual profile
last_payment {ex_date, pay_date, amount}
next_ex_date, next_pay_date (often null)
changes[] raise/cut history
```

`changes[]` are raise/cut events, not every quarterly payment. `annual_amount`
and `last_payment` are not a complete historical event series. No declaration or
record date and no currency field are returned.

Decision: **B — current dividend profile / recent event only.**

## 3. Yahoo Finance / yfinance

Version: **yfinance 1.7.0**. One `Ticker.dividends` call per sample.

| Result | Count |
|---|---:|
| Requests | 30 |
| HTTP 429 | **0** |
| Tickers with dividends | 26 |
| Historical ex-date/DPS events | **4,267** |
| Currency field | **0** |
| Payment date | **0** |
| Declaration date | **0** |
| Record date | **0** |
| Full ex-date + amount series | **Yes** (26 names) |
| Full payment-event fields | **No** |

Yahoo provides ex-date and per-share amount history, split-adjusted. It does not
provide payment, declaration, record date or explicit currency in the tested
response. ADR ratio/currency remain unverified.

Decision: **B — historical DPS/ex-date series, not a complete event record.**

## 4. Nasdaq Dividend History

Only Nasdaq-listed sample names were attempted.

| Result | Count |
|---|---:|
| Nasdaq-listed attempted | 13 |
| HTTP 200 | 13 |
| HTTP 429 | 0 |
| Tickers with rows | **9** |
| Events | **416** |
| DPS | 416 |
| Ex-date | 416 |
| Payment date | 367 |
| Declaration date | 358 |
| Record date | 416 |
| Currency | 416 |
| Errors / no rows | 4 (`AURE`, `ABNB`, `ACAD`, `AAOI`) |

Nasdaq returned full row fields for the nine covered tickers:

```text
exOrEffDate, type, amount, declarationDate, recordDate, paymentDate, currency
```

Limitations:

- only Nasdaq-listed securities;
- amounts are **not split-adjusted** per Nasdaq;
- preferred dividends must not be mixed into common;
- no non-Nasdaq/ADR full-market coverage.

Decision: **A only for Nasdaq-listed names, not full-market A.**

## 5. Comparison

| Capability | Smarter | Yahoo | Nasdaq |
|---|---|---|---|
| Current profile | **Yes** | No | Yes |
| Recent event | **Yes** | Yes | Yes |
| Raise/cut history | **Yes (957)** | No | No |
| Full payment events | **No** | No | **Yes, Nasdaq-only** |
| Ex-date | Yes | Yes | Yes |
| Pay-date | 23/26 | No | 367/416 |
| Declaration date | No | No | 358/416 |
| Record date | No | No | 416/416 |
| Currency | No | No | 416/416 |
| ADR dividend ready | No | No | No |
| Split-adjusted | Unknown | Yahoo-adjusted | **Not adjusted** |

## 6. SEC cross-check

P6.11 SEC evidence reused:

- 24 sample names have a cash-flow `DividendsPaid` fact;
- 25 have positive cash-dividend evidence;
- 0 have a per-share dividend fact in the P6.3 map.

No direct DPS reconciliation is possible because SEC `DividendsPaid` is total
cash paid, not DPS. Vendor `last_payment.amount`/Yahoo DPS and SEC cash amounts
are retained separately.

## 7. Empty / no-data behavior

- Smarter: 26/30 have data; 4 no last payment; no data is **UNKNOWN**, not
  non-payer.
- Yahoo: 26/30 have dividend history; 4 empty; **UNKNOWN**.
- Nasdaq: 9/13 have rows; 4 no rows; **UNKNOWN**.
- `CONFIRMED_NON_PAYER` remains **0** for all sources.

## 8. ADR

ASML/BZ/ATAT return events, but:

- no ADR ratio is verified;
- Smarter/Yahoo provide no currency;
- Nasdaq currency is USD for its rows, but ADR ratio is still missing;
- no final ADR DPS is computed.

## 9. Decision

```text
FULL_MARKET_A = false
SMARTERDIVIDENDS = B_CURRENT_PROFILE_ONLY
YAHOO_FINANCE = B_HISTORICAL_DPS_EX_DATE_ONLY
NASDAQ_DIVIDEND_HISTORY = A_ONLY_FOR_NASDAQ_LISTED_NOT_FULL_MARKET
```

No single free source supplies complete, split-adjusted, all-market dividend
events with declaration/record/payment/currency fields.

## 10. Is full-market collection justified?

**No, not as a complete event dataset.**

- Smarter: 30 requests; no rate-limit issue observed, but no full history.
- Yahoo: 30 requests; no 429 observed, but no event dates/currency.
- Nasdaq: 13 sample requests; only Nasdaq and unadjusted.

A full 5,502 collection would be at least 5,502 Smarter/Yahoo requests and only
a Nasdaq subset, with mixed adjustment and field completeness. That is not
sufficient for a full Dividend event database.

## 11. CASH_DIVIDEND_PROXY

Yes, a clearly labeled proxy is possible:

```text
CASH_DIVIDEND_PROXY
= SEC cash-flow DividendsPaid (total cash paid)
```

It can classify payer evidence and cash amount, but it cannot supply DPS, ex-date,
record date, payment date, frequency or currency. It must not be called dividend
event history or used as DPS.

## 12. Artifact

Raw responses and normalized outputs are uploaded as the GitHub Actions artifact.
No paid CSV, Pro data, trial account or credit card was used.
