# P10.6.2 Quality Historical Panel

Date: 2026-11-10

## Status

```text
QUALITY_PIT_PANEL_PARTIAL
```

The historical Quality **inputs** are partially reconstructed. A valid Quality
V1 score/rank could not be produced because the fixed 20-company sample is
smaller than the V1 peer-group minimum of 30.

## 1. Raw SEC verification

P10.6.1 core facts: 638.

```text
raw XBRL contextRef verified: 0
accession-traceable facts:    638
PIT_DATE_PROXY:               638 (core)
PIT_EXACT_PUBLIC_TIME:        0
```

This round did not fetch raw instances for all 76 company-cutoff filings.
Therefore no fact is labelled `FACT_LEVEL_VERIFIED`. The CompanyFacts accession
is retained, but contextRef is empty.

## 2. Quality inputs

Five inputs were used:

```text
NetIncomeLoss, StockholdersEquity, Assets,
OperatingCashFlow, Liabilities
```

Available companies by cutoff:

| Cutoff | ROE | ROA | CFO/Assets | Liabilities/Assets | Complete inputs |
|---|---:|---:|---:|---:|---:|
| 2017-03-31 | 15 | 18 | 19 | 13 | 10 |
| 2020-03-31 | 16 | 19 | 19 | 13 | 11 |
| 2023-03-31 | 16 | 19 | 19 | 14 | 12 |
| 2026-03-31 | 17 | 19 | 19 | 14 | 13 |

XOM has no usable us-gaap facts in P10.6.1 and is retained as unresolved; it is
not replaced.

## 3. Quality V1 scoring

Quality V1 weights:

```text
ROE 0.30, ROA 0.25, CFO/Assets 0.25, Liabilities/Assets 0.20
```

The V1 implementation requires at least **30 peers** in a model-family /
accounting-standard group before percentile scoring. The fixed pilot has 19
companies with facts, so:

```text
valid V1 scores: 0
valid V1 ranks:  0
reason: PEER_GROUP_TOO_SMALL
```

No weights were changed, no peer minimum was lowered, and no ad-hoc ranking was
substituted.

## 4. Exit classification

The five non-surviving names are not all “delistings”:

| Ticker | Exit |
|---|---|
| MON | Acquisition (Bayer) |
| CELG | Acquisition (Bristol-Myers Squibb) |
| RTN | Merger (Raytheon Technologies) |
| ETFC | Acquisition (Morgan Stanley) |
| XLNX | Acquisition (AMD) |

None is classified as bankruptcy or liquidation.

## 5. PIT

- filing date is used as `PIT_DATE_PROXY`;
- no trade on filing date; next-session rule applies;
- no accession filed after the cutoff was used;
- exact public time is not claimed;
- post-cutoff revisions are excluded by `filed <= cutoff`;
- a dedicated amendment/restatement test was not completed.

## 6. Verdict

The Quality accounting inputs can be partially reconstructed from free SEC
CompanyFacts. The pilot cannot validate the V1 rank because the sample is below
the 30-peer threshold and raw contextRef verification is absent.

To proceed:

1. Expand to at least 30–50 peers per model-family/accounting-standard group.
2. Verify accession facts against original XBRL instances.
3. Complete amendment/revision tests.
4. Keep Value/GARP blocked until historical prices exist.

This is not a backtest and not an Alpha claim.

## 7. Safety

```text
P10.6:          NOT AUTHORIZED
Shadow:         NOT STARTED
PAPER-50000:    UNTOUCHED
IBKR:           NOT CONNECTED
Merge:          NOT AUTHORIZED
```
