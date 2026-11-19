# P17.1 Identity Reconciliation

Date: 2026-11-20
Branch: `research/p17-1-identity-reconciliation`
Base: `9b07f588dd5af05017d2d4cba36ae87a23d9460a`
Status: **DATA_BLOCKED**

## 1. Corrected P17 numbers

P17's earlier fields were misleading:

- `mapped_tickers=3` included 2 confirmed with **no prices** and 1 conflict (LB);
- `unique_ciks=23` included candidate CIKs from unresolved rows;
- 581 priced tickers were all UNRESOLVED;
- verified price member-days = 0.

Correct fields:

```text
verified_identity_tickers = 2       (BRK.B, BF.B; no price)
candidate_high_tickers = 54         (PR390 overlap)
verified_price_tickers = 0
candidate_price_tickers = 53
verified_price_member_days = 0
candidate_price_member_days = 38,690
```

So P17's 0.397% is **not** a valid claim of price-identity coverage; it is a
verified-identity rate with zero price intersection. P17's conclusion remains
DATA_BLOCKED.

## 2. PR #390 integration

Source: commit `fb39cff3`, 98 rows.

| item | result |
|---|---:|
| source rows | 98 |
| P13 overlap | **54** |
| overlap high | 53 |
| overlap medium | 1 |
| overlap expected member-days | 38,948 |
| high expected member-days | 38,108 |
| medium expected member-days | 840 |
| overlap observed member-days | 38,690 |
| high observed member-days | 37,850 |
| medium observed member-days | 840 |

The 54 overlap names were all UNRESOLVED in P17; P17 omitted this source.
They are now `CANDIDATE_HIGH`/`CANDIDATE_MEDIUM`, not VERIFIED. The source high
label is retained separately as `source_confidence`.

FRC remains medium. DAY has no price.

## 3. P10 crosswalk audit

80 rows; 26 tickers are in P13; only 2 are `IDENTITY_CONFIRMED` (BRK.B, BF.B),
and both have no price. The other P10 statuses are unresolved/conflict/partial.
P17 did not lose a large verified set; the crosswalk itself is small.

## 4. SEC CompanyFacts audit

Recomputed from the 6.39M-row panel:

```text
rows: 6,391,195
CIKs: 5,368
unique tickers-field strings: 5,367
metrics: 19
taxonomies: us-gaap 6,085,978; ifrs-full 176,432; dei 128,785
DEI tags: EntityCommonStockSharesOutstanding only
TradingSymbol: NOT_AVAILABLE
SecurityExchangeName: NOT_AVAILABLE
null pit_available_date: 0
PIT range: 2013-03-19..2026-11-05
```

The old 3,913 CIK / 15 metric figures are superseded by the direct recount.
`tickers` is a current submission/company field, not a dated historical symbol,
so it is only a candidate identity signal.

## 5. Coverage

Full 607 tickers / 633,971 expected member-days:

- verified: 2 tickers, 2,516 member-days, 0 observed price days;
- candidate high: 54 tickers, 38,948 expected, 38,690 observed;
- unresolved: 551 tickers.

Priced 581 tickers / 625,608 observed member-days:

- verified × price: 0;
- candidate × price: 53 tickers / 38,690 days;
- unresolved × price: 528 tickers;
- maximum candidate cross-section: 53 names/day.

The exploratory gate of ≥100 names on ≥80% of signal days is **not met**.

## 6. Security classes / conflicts

COG/CTRA share CIK 0000858470; DISCA/DISCK/WBD share CIK 0001437107. CIK is an
issuer identity, not a unique security. They remain separate security_ids with
`SHARE_CLASS_AMBIGUOUS`; no financial facts are joined across classes.

## 7. Decision

```text
P17_1_STATUS = DATA_BLOCKED
P17_1_VERIFIED_PRICE_TICKERS = 0
P17_1_CANDIDATE_PRICE_TICKERS = 53
P17_1_PIT_RESEARCH_READY = FALSE
```

P17's 0.397% was a real verified-rate number but had no price coverage; adding
PR390 raises candidate coverage to about 6.1% of observed member-days, not
verified status. It is still far below a usable 100-name daily cross-section.

Existing free data cannot support a full-market PIT fundamental study without
a real historical identity master. No alpha, no portfolio, no cost analysis was
run.

## 8. Files

- `tools/research/p17_1_identity_reconciliation.py`
- `tests/test_p17_1_identity_reconciliation.py`
- `data/research/p17_1/p17_1_p390_identity_reconciliation.csv`
- `p17_1_p10_crosswalk_reconciliation.csv`
- `p17_1_security_identity_intervals.csv`
- `p17_1_security_class_aliases.csv`
- `p17_1_identity_conflicts.csv`
- `p17_1_sec_dei_tag_audit.csv`
- `p17_1_sec_facts_full_audit.csv`
- `p17_1_identity_coverage_full.csv`
- `p17_1_identity_coverage_priced.csv`
- `p17_1_unresolved_priced_tickers.csv`
- `p17_1_summary.json`
- `p17_1_manifest.json`

No model call, no API key, no broker, no order.
