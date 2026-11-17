# P12.4.1: PIT Fundamental Changes and 8-K Event Study

Date: 2026-11-17
Branch: `research/p12-event-fundamental-feasibility`
Status: **DESCRIPTIVE_ONLY — no tradable-alpha claim**

Protocol: `P12_4_1_PRE_REGISTERED_STUDY_PROTOCOL.md` (frozen before returns).

---

## 1. Sample

```text
issuers: 140
fundamental accessions: 2,624
fundamental issuers: 114
US 8-K accessions: 11,612
US 8-K issuers: 133
```

Fundamental disclosure sample is 10-K/10-Q only. Foreign 6-K is excluded from
the US 8-K statistics.

---

## 2. Fundamental changes

Metric coverage:

```text
revenue_growth:      1,865
op_margin_change:    1,863
cash_conversion:     2,393
leverage_change:     1,264
shares_change:         765
```

Rules enforced:

- accession-level facts only;
- same taxonomy/tag/unit;
- quarterly flows only for 10-Q; annual flows only for 10-K; YTD excluded;
- prior-year same period must be visible at the current filing;
- no zero-fill;
- denominator <= 0 excluded;
- entry is the first trading day strictly after `known_at`.

Result:

```text
P12_4_1_FUNDAMENTAL: NO_SIGNAL
```

Best validation IC is about 0.054 (`cash_conversion`, 10d), but its 95% CI is
0.011–0.105 and the remaining metrics are near zero with CIs spanning zero.
That is not enough for a multi-test claim; no fundamental metric is marked
`PROMISING`.

Files:

- `p12_4_1_fundamental_panel.csv`
- `p12_4_1_fundamental_stats.csv`

---

## 3. 8-K event study

Panel:

```text
accessions: 11,612
issuers:       133
D0 available: 10,945
D1 available: 10,944
D5 available: 10,941
D10 available: 10,930
D20 available: 10,869
```

D0/D1/D5 use P12.3.1; D10/D20 are new only where price coverage exists.

Top D5 excess categories (eligible):

```text
2.02 INTRADAY:  +0.609% (n=154, 27 issuers)
2.03 AFTER_HOURS:+0.370% (n=542, 89)
5.02 AFTER_HOURS:+0.294% (n=1,600, 123)
8.01 PREMARKET: +0.246% (n=708, 106)
7.01 PREMARKET: +0.246% (n=1,117, 98)
```

The 5.02 AFTER_HOURS D20 result is significant before overlap control
(+0.675%, q<0.001), but it disappears after excluding overlapping events:

```text
all:                  +0.675%
exclude overlap 20d:  -0.011%
clean both filters:   -0.002%
```

2.02 AFTER_HOURS D20 is more persistent:

```text
all:                  +0.711%
explore:              +0.955%
validate:             +0.636%
exclude overlap 20d:  +0.613%
clean both:           +0.857%
```

It remains a candidate for future work, but this study does not claim a
tradable edge: no costs, one event category, many tests, and event clustering.

Files:

- `p12_4_1_8k_panel.csv`
- `p12_4_1_8k_stats.csv`
- `p12_4_1_overlap_sensitivity.csv`

---

## 4. Statistics and limitations

- exploration 2009–2018; validation 2019–2024;
- cluster bootstrap by CIK, 300 draws;
- BH FDR across 8-K category/session/period tests;
- minimum 100 accessions and 20 issuers;
- same-day 10-K/10-Q flagged;
- overlapping same-issuer events flagged;
- no cost model, no portfolio.

Limitations:

- 140-issuer pilot, not full market;
- 2,056 foreign 6-K events have no local price;
- 26 US event accessions lack a complete D0/D1/D5 window;
- low-precision filing-date facts use US/Eastern end of day;
- fundamentals cannot be treated as a quarterly PIT panel for all firms;
- D10/D20 coverage declines at the end of the sample.

---

## 5. Conclusions

```text
P12_4_1_STATUS: DESCRIPTIVE_ONLY
FUNDAMENTAL_CHANGE: NO_SIGNAL
8K_EVENT_DIFFERENCES: DESCRIPTIVE_ONLY
2.02_AFTER_HOURS_D20: DESCRIPTIVE_ONLY (candidate for future OOS)
5.02_AFTER_HOURS_D20: NO_SIGNAL_AFTER_OVERLAP_CONTROL
TRADABLE_ALPHA: NOT_CLAIMED
MARKET_WIDE: DATA_BLOCKED
```

No strategy, portfolio, live/paper trading or allocation is proposed.

---

## 6. Final state

```text
NO_PURCHASE: YES
VPS_REQUIRED: NO
MAX_BUDGET_USD: 20
P12_4_1_STATUS: DESCRIPTIVE_ONLY
FUNDAMENTAL_ACCESSIONS: 2624
US_8K_ACCESSIONS: 11612
D20_AVAILABLE: 10869
TRADABLE_ALPHA: NOT_CLAIMED
P9_RESULTS: ALL 8 NO-GO
P10_PURCHASE_DECISION: NO_BUY
P11_PRICE_FACTORS: NO-GO
IBKR_CONNECTED: NO
```

No purchase, no VPS, no IBKR, no paper/shadow, no portfolio, no merge/main change,
no raw data upload.
