# Dividend Evidence Closure — P4.2

Date: 2026-11-04
Branch: `research/dividend-quality-p42-evidence-closure`
Stacked target: `research/dividend-quality-p41-hardening`
Status: **evidence incomplete; no DPS CAGR promoted**

## 1. Result first

- 28 companies checked against SEC CompanyFacts and SEC filing metadata.
- **22 split-conversion facts** were found across **12 tickers**.
- **0** split events are `SPLIT_CONFIRMED`; all lack an official effective date
  and/or announcement evidence.
- **0 formal dividend declaration/EX/record/payment events** were verified.
- **0 companies** have a verified DPS share basis.
- All 28 remain `DPS_SPLIT_BASIS_UNVERIFIED`.
- P4.1's 10 `SCORE_READY` companies remain 10; the evidence gate did not increase
  scores.

## 2. SEC split facts found

The only structured split source used was SEC CompanyFacts tag:

```text
StockholdersEquityNoteStockSplitConversionRatio1
```

Examples:

| Ticker | Ratio | Fact period end | Form | Accession |
|---|---:|---|---|---|
| AAPL | 4.0 | 2020-08-28 | 10-K | 0000320193-20-000096 |
| AAPL | 7.0 | 2014-06-06 | 10-Q | 0001193125-14-277160 |
| NVDA | 4.0 | 2021-07-19 | 10-K | 0001045810-22-000036 |
| NVDA | 10.0 | 2024-06-30 | 10-Q | 0001045810-25-000116 |
| HON | 0.5 | 2026-06-30 | 10-Q | (from filing) |
| DUK | 0.3333 | 2012-12-31 | 10-K | (from filing) |

Ratio convention:

```text
new_shares_per_old_share
4-for-1 = 4.0
1-for-10 reverse = 0.1
```

These facts are **not** enough to form a confirmed split event because:

- the XBRL fact period end is not the split effective date;
- no announcement/effective date was independently extracted;
- no official company action document was fetched for each event;
- no source share basis is proven.

Therefore each is:

```text
PARTIALLY_VERIFIED
```

and no `SPLIT_CONFIRMED` is claimed.

## 3. Split status coverage

| Status | Tickers |
|---|---:|
| SPLIT_CONFIRMED | **0** |
| PARTIALLY_VERIFIED | **12** |
| SPLIT_HISTORY_INCOMPLETE | **16** |
| NO_SPLIT_VERIFIED | **0** |
| SPLIT_BASIS_UNVERIFIED | **28** overall DPS basis |

A missing split announcement is **not** treated as proof of no split.  
No ticker receives `NO_SPLIT_VERIFIED` merely because no fact was found.

## 4. Formal dividend events

`dividend_event_collector.py` requires, for every event:

- ticker and CIK;
- event type;
- announcement date;
- official https source;
- accession where applicable;
- evidence SHA-256;
- separate ex/record/payment dates.

It rejects events without source/date/hash and cannot mark `VERIFIED` without
evidence notes.

No official event records were supplied or automatically inferred.  
Result:

```text
data/research/dividend_events_p42.json = []
```

This is an explicit evidence gap, not a claim that no dividends were declared.

Annual DPS declines remain:

```text
POSSIBLE_REDUCTION
is_event = false
```

They are not converted into `REDUCED` events.

## 5. DPS share-basis propagation

`dividend_quality.py` now gates all growth-derived fields on split-basis evidence:

- `dps_growth_1y`
- `dps_cagr_3y`
- `dps_cagr_5y`
- `consecutive_growth_years`
- `total_positive_growth_years`
- `dividend_cuts`
- `dps_volatility`

When unverified:

```text
growth_status = DPS_SPLIT_BASIS_UNVERIFIED
values = null
raw_* fields retained for audit only
```

Continuity itself (5 consecutive years with positive DPS) remains independently
available, because it does not require a growth-rate comparison.

`adjust_dps()` only adjusts `AS_DECLARED_AT_TIME` values for future **verified**
splits. `SPLIT_ADJUSTED` data is not adjusted again; `UNKNOWN` is blocked.

## 6. Recomputed 28-company status

Classification unchanged:

| Class | Count |
|---|---:|
| DIVIDEND_PAYER | 22 |
| NON_DIVIDEND_PAYER | 5 |
| DIVIDEND_DATA_BLOCKED | 1 (XOM) |

Payout:

| Status | Count |
|---|---:|
| OK | 18 |
| INSUFFICIENT_DATA | 8 |
| PERIOD_MISMATCH | 2 |

FCF coverage:

| Status | Count |
|---|---:|
| OK | 13 |
| DATA_BLOCKED | 14 |
| PERIOD_MISMATCH | 1 |

Score status:

| Status | Count |
|---|---:|
| SCORE_READY | **10** |
| NOT_READY | **18** |

P4.1 -> P4.2 scores are unchanged for the 10 ready companies. No rule was relaxed
to add a score.

## 7. Files

```text
tools/investment_research/dividend/evidence_registry.py
tools/investment_research/dividend/split_evidence_collector.py
tools/investment_research/dividend/dividend_event_collector.py
tools/investment_research/dividend/dividend_quality_report_p42.py

data/research/split_evidence_p42.json
data/research/dividend_events_p42.json
data/research/dividend_quality_p42.json

tests/test_dividend_evidence_p42.py
```

## 8. Remaining evidence work

1. Fetch and parse official 8-K/IR documents to set split announcement and
   effective dates; current XBRL facts are partial only.
2. Establish `source_share_basis` per DPS series; currently all UNKNOWN.
3. Populate formal DECLARED/EX/RECORD/PAYMENT events; currently zero.
4. Resolve XOM historical identity.
5. Bank/insurer/REIT dedicated models remain future work.

No production scan/trade code was touched. No Yahoo/AKShare/Finnhub was used.
