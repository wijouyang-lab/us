# P10.6.4 Quality XBRL Replay

Date: 2026-11-10

## Status

```text
XBRL_VERTICAL_SLICE_PARTIAL
QUALITY_LINEAGE_PARTIAL
```

The five-name vertical slice partially passed; the 60-name / 240-row expansion
was not executed after the slice did not reach full verification.

## 1. Fixed five-name slice

| Ticker | Role |
|---|---|
| AAPL | current |
| IBM | current |
| INTC | current |
| XLNX | acquisition exit |
| HPQ | 10-K/A case |

No cohort member was replaced.

## 2. Raw XBRL context verification

```text
slice rows:                 92
XBRL_CONTEXT_VERIFIED:      50
XBRL_CONTEXT_UNRESOLVED:    40
SOURCE_FILE_MISSING:         2
```

50 facts now have a real accession, concept, contextRef, start/end, unit and
raw value from the original instance.

The 40 unresolved rows are mostly missing or ambiguous consolidated facts
(Liabilities/OCF/tag-period), not silently filled. The 2 missing rows are XLNX
filings after its acquisition / outside the available 10-K window.

## 3. 60-name expansion

Not run. Because the vertical slice was not fully verified, expanding to 240
rows would only multiply unverified facts. This is a deliberate stop, not a
claim of completion.

```text
60-company actual input context verification: 0
```

## 4. Amendment replay

HPQ timeline locked:

```text
original 10-K: 0000047217-22-000068, filed 2022-12-06
10-K/A:        0000047217-23-000075, filed 2023-09-11
```

Status: `AMENDMENT_REPLAY_UNRESOLVED`. The amendment's financial-fact changes
were not parsed in this slice. No success is claimed.

## 5. Repeatability

A second full 60-name build was not executed. Therefore `all_equal` is not
claimed. The existing P10.6.3 rankings were not modified.

## 6. Rankings

No ranking was recomputed in this round. P10.6.3 remains
`PILOT_SAMPLE_RANKING_ONLY`; it is not an OOS strategy and has high survivor
bias.

## 7. Remaining blockers

1. Resolve 40 ambiguous/missing slice facts.
2. Verify all 240 cohort rows.
3. Complete 10-K/A and comparative-period replay.
4. Run two clean full builds and compare.
5. Historical universe and delisting returns remain blocked.

## 8. Safety

```text
P10.6:          NOT AUTHORIZED
Shadow:         NOT STARTED
PAPER-50000:    UNTOUCHED
IBKR:           NOT CONNECTED
Merge:          NOT AUTHORIZED
```
