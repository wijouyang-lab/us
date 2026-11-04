# Dividend Quality — P4

Date: 2026-11-04
Branch: `research/dividend-quality-p4` (stacked on PR #460)
Data: SEC CompanyFacts only. No Yahoo, AKShare, Finnhub, IBKR or paper-account data.

## 1. Scope

Implemented a no-price Dividend Quality research module. It does not calculate
Dividend Yield, Forward Yield, yield ranking or price-based valuation.

## 2. Sample classification

28 companies:

| Classification | Count |
|---|---:|
| DIVIDEND_PAYER | 22 |
| NON_DIVIDEND_PAYER | 5 |
| DIVIDEND_DATA_BLOCKED | 1 |
| DIVIDEND_CUT_OR_SUSPENDED | 0 formal events |

XOM is `DIVIDEND_DATA_BLOCKED`: SEC's current XOM CIK is the new holding company
with insufficient historical dividend facts. No predecessor CIK was substituted.

Non-payers (ADBE, AMZN, BRK.B, MRNA, RIVN) are not scored as bad quality.

## 3. Metric coverage

Denominator is the 22 payers unless stated.

| Metric | OK / 22 |
|---|---:|
| Net income payout | 20 |
| FCF payout | 14 |
| FCF dividend coverage | 14 |
| 5-year DPS CAGR | 17 |
| Dividend continuity | 19 |
| Score with >=3 evidence components | 20 |

`NOT_READY` scores: 8 companies, including non-payers and companies with too few
payer metrics.

## 4. Company results

Scores are descriptive research summaries, not alpha or buy/sell signals.

| Ticker | Class | Score | 5y DPS CAGR | NI payout | FCF coverage |
|---|---|---:|---:|---|---|
| AAPL | PAYER | 89.1 | 4.5% | OK | OK |
| MSFT | PAYER | 100.0 | 10.2% | OK | OK |
| GOOGL | PAYER | 66.1 | — | OK | OK |
| NVDA | PAYER | 100.0 | — | OK | OK |
| CRM | PAYER | 66.7 | — | OK | OK |
| HD | PAYER | 88.5 | 8.9% | OK | OK |
| MCD | PAYER | 87.7 | 7.3% | OK | OK |
| NKE | PAYER | 72.0 | 8.8% | OK | OK |
| CAT | PAYER | 92.1 | 7.6% | OK | OK |
| HON | PAYER | 71.3 | 4.8% | OK | OK |
| UNP | PAYER | 96.9 | 7.0% | OK | OK |
| CVX | PAYER | 58.7 | — | OK | OK |
| NEE | PAYER | 95.2 | 10.1% | OK | DATA_BLOCKED |
| DUK | PAYER | 37.4 | 2.0% | OK | OK |
| JNJ | PAYER | NOT_READY | — | INSUFFICIENT | N/A |
| PFE | PAYER | NOT_READY | 2.4% | INSUFFICIENT | N/A |
| UNH | PAYER | 97.0 | 12.6% | OK | OK |
| JPM | PAYER | 100.0 | 10.0% | OK | DATA_BLOCKED |
| BAC | PAYER | 100.0 | 8.4% | OK | DATA_BLOCKED |
| MET | PAYER | 84.6 | 4.3% | OK | DATA_BLOCKED |
| PLD | PAYER | 66.7 | 11.7% | OK | DATA_BLOCKED |
| O | PAYER | 45.2 | 2.9% | OK | DATA_BLOCKED |
| XOM | DATA_BLOCKED | — | — | INSUFFICIENT | DATA_BLOCKED |
| ADBE/AMZN/BRK.B/MRNA/RIVN | NON_PAYER | — | — | N/A | N/A |

## 5. Growth and cuts

- 17/22 payers have a computed 5-year DPS CAGR.
- 19/22 have at least 5 consecutive years of positive per-share dividends.
- `dividend_cuts` counts annual DPS declines >5%; total **11** across the payer
  sample.
- These are descriptive annual flags, not formal DECLARED/REDUCED events.

Per-share DPS and total cash dividends are stored separately. Cash-total changes
are never used as DPS growth.

## 6. Capital allocation

The report keeps separate:

- dividends paid;
- share repurchases;
- long-term debt repayment;
- CFO;
- FCF.

No buyback is counted as a dividend.

## 7. PIT and accounting

- Uses SEC `Snapshot.available()` gating from PR #460.
- `filed_date` and `acceptance_datetime` are retained; no historical first-seen
  claim is made.
- Annual series are same concept/unit/fiscal-year only.
- DPS uses `USD/shares`; cash uses USD.
- Payout/coverage require same period; missing FCF returns `DATA_BLOCKED`.
- Negative net income/FCF returns `NOT_APPLICABLE`, not a normal payout.
- No price fields are accepted anywhere in this module.

## 8. Dividend events

`dividend_events.py` implements:

```text
DECLARED, EX_DATE, RECORD_DATE, PAYMENT_DATE,
REDUCED, SUSPENDED, RESUMED, INCREASED
```

Rules:

- source URL + source type + evidence SHA-256 required;
- event ID is deterministic from ticker/type/date/source/evidence;
- duplicate evidence dedupes;
- annual DPS decline is only `POSSIBLE_REDUCTION`, `is_event=false`.

**No formal event list was populated in this round.** The annual values alone
cannot prove a declaration, ex-date or suspension; additional 8-K/IR evidence is
still required. This is an explicit gap, not a silent event claim.

## 9. Excluded metrics

Not calculated:

```text
Dividend Yield
Forward Dividend Yield
Price-based payout valuation
Dividend yield ranking
Margin of safety
```

Reason: no authorized current market price.

## 10. Coverage / gaps

- Payout coverage 20/22; FCF coverage 14/22.
- 5-year DPS history 17/22.
- JNJ/PFE lack sufficient payout inputs.
- Banks/REITs often lack industrial FCF; FCF coverage is blocked, not zero.
- XOM identity/history is blocked.
- Event evidence not collected.
- Score is not validated against returns and must not be treated as alpha.

## 11. Reproduction

```bash
python -m tools.investment_research.dividend.dividend_quality_report
python -m pytest -q tests/test_dividend_quality.py tests/test_dividend_events.py
```

Output:

```text
data/research/dividend_quality_p4.json
```

## 12. Tests

`	extntests/test_dividend_quality.py  6 passed
tests/test_dividend_events.py   4 passed
`

Total 10 passed for P4. Full CI result is reported with the PR.
