# P12.4.1 Pre-Registered Study Protocol

Date: 2026-11-17
Status: **FROZEN BEFORE RETURN ANALYSIS**

## Samples

- SEC PIT pilot: 140 issuers, 2009-2024.
- Fundamental disclosures: 10-K and 10-Q accessions only.
- Event study: US 8-K accessions only; foreign 6-K excluded.
- Minimum inference threshold: 100 accessions and 20 issuers per category.

## Fundamental metrics

1. Revenue YoY growth.
2. Operating margin change (operating income / revenue, YoY).
3. Cash conversion (operating cash flow / net income).
4. Net leverage change ((total debt - cash) / total assets, YoY).
5. Shares outstanding change (YoY).

Rules:

- only accession-visible facts, using `known_at`;
- same taxonomy/tag/unit; no cross-tag merging;
- flows: 10-Q quarterly only (duration 60-110 days); 10-K annual only
  (duration 300-400 days); YTD is excluded;
- stocks: instant at period end;
- prior-year same fiscal quarter/period must be known at the current filing;
- denominators <= 0 are excluded;
- missing is missing, never zero;
- 10-Q/YTD period mismatches are not silently repaired.

## Event returns

Fundamental disclosures:

- entry = first trading day strictly after `known_at`;
- exit = entry + 5/10/20 trading days;
- close-to-close adjusted returns;
- SPY excess only if the same dates exist.

8-K:

- use P12.3.1 D0/D1/D5 definitions;
- add D10/D20 from the reaction date when prices exist;
- one accession = one event, regardless of multiple items;
- 9.01 is an exhibit tag, not an independent economic event;
- item/session groups are separate;
- INTRADAY daily D0 is not an intraday measurement;
- same-day 10-K/10-Q is flagged;
- overlapping same-issuer events are flagged and excluded in sensitivity.

## Statistics

- exploration: 2009-2018;
- validation: 2019-2024;
- report n accessions, n issuers, mean, median, positive rate, 95% CI;
- cluster bootstrap by CIK (500 draws) for confidence intervals;
- Benjamini-Hochberg FDR across reported category tests;
- minimum threshold below which only descriptive results are allowed;
- D5/D20 are primary; D0 descriptive.

## Conclusions

Each result is classified only as:

```text
DATA_BLOCKED
DESCRIPTIVE_ONLY
NO_SIGNAL
PROMISING_NEEDS_OOS
```

No strategy or tradable-alpha claim.
