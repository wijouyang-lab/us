# P10.6.3 Quality Peer Expansion and First Legal Ranking

Date: 2026-11-10

## Status

```text
QUALITY_PILOT_RANKING_READY
```

This is a pilot-sample ranking, not a market-wide ranking, not an OOS strategy,
and not `QUALITY_PIT_PANEL_ACCEPTED`.

## 1. Peer grouping

Existing Quality V1 rule:

```text
group = model_family + accounting_standard + cutoff
MIN_PEER = 30
```

All four metrics must be present for a company to be scored. Missing values are
not filled with zero.

## 2. Cohort

60 Technology/US_GAAP companies, selected before extraction from the existing
quality ranking population. XLNX is included as a non-surviving acquisition
case.

## 3. Results by cutoff

| Cutoff | Valid peers | Scored | Status |
|---|---:|---:|---|
| 2017-03-31 | 37 | 37 | PILOT_SAMPLE_RANKING |
| 2020-03-31 | 45 | 45 | PILOT_SAMPLE_RANKING |
| 2023-03-31 | 46 | 46 | PILOT_SAMPLE_RANKING |
| 2026-03-31 | 48 | 48 | PILOT_SAMPLE_RANKING |

All four cutoffs clear the 30-peer gate. Percentiles, weights and ranks are
computed independently per cutoff.

## 4. Raw XBRL verification

```text
contextRef verified: 0
amendment replay:    0
```

The cohort uses SEC CompanyFacts accession data. No raw instance was fetched for
all 240 company-cutoff rows. Therefore no row is `FACT_LEVEL_VERIFIED` and the
panel cannot be called `QUALITY_PIT_PANEL_ACCEPTED`.

## 5. PIT / revisions

- All selected facts satisfy `filed <= cutoff`.
- All are `PIT_DATE_PROXY`.
- Exact public time is not claimed.
- No post-cutoff filing is used.
- The 10-K/A replay test was not completed.

No future information leakage was observed in the `filed <= cutoff` check, but
the absence of raw context verification limits the conclusion.

## 6. Ranking output

- `quality_historical_scores.csv`: per-cutoff V1 scores and ranks.
- Status is `PILOT_SAMPLE_RANKING`, not a full-market rank.
- The cohort is a technology-only sample; it is not a cross-sector ranking.

## 7. Remaining blockers

1. Raw XBRL contextRef verification for 240 panel rows.
2. 10-K/A amendment replay.
3. Multi-sector peer groups with >=30 peers for Value/GARP or cross-sector work.
4. Historical price/market cap for Value.
5. Delisting/merger returns for actual OOS returns.

## 8. Safety

```text
P10.6:          NOT AUTHORIZED
Shadow:         NOT STARTED
PAPER-50000:    UNTOUCHED
IBKR:           NOT CONNECTED
Merge:          NOT AUTHORIZED
```
