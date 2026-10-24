# PIT event-factor research status

Last verified capture: **2026-10-23 17:14 UTC**. This is a data-readiness status report, not an alpha claim.

## Evidence captured

- **86** immutable event versions in the archive.
- **30** event versions were published within the 30-day annotation window at the latest capture cutoff. The workflow generated a separate queue with **30 pending rows** ([CSV](../../data/research/event-capture/annotation_queue_39993404661.csv), [report](../../data/research/event-capture/annotation_queue_39993404661.report.json)).
- Source coverage in the archive: BEA releases (49), Federal Reserve press releases (20), Fed speeches/testimony (15), Treasury auction announcements (1), Treasury auction results (1).
- The BLS CPI and employment RSS feeds and SEC ticker-to-CIK mapping endpoint returned **HTTP 403** from the GitHub Actions runner. A separate public BLS API snapshot succeeded with **5/5 current series**: CPI, core CPI, nonfarm payrolls, unemployment rate, and average hourly earnings. SEC filing capture is therefore currently skipped by the best-effort workflow. The SEC company-ticker mapping endpoint also returned **HTTP 403**, so SEC filing capture was skipped for this run; the workflow now continues with the other sources rather than failing the whole capture.
- Treasury current-year XML capture returned **203 nominal rows and 203 real-yield rows**. The real-yield schema uses `TC_*` fields; nominal uses `BC_*`.
- Capture and readiness evidence files are stored under `data/research/event-capture/`, including immutable event snapshots, source reports, BLS snapshots, Treasury snapshots, and pending annotation queues. One older BEA item contains a scheme-less but recoverable official URL; this is reported explicitly by the readiness audit, while new captures normalize such links to HTTPS.


- **Derived Treasury inflation-compensation proxy:** 203 nominal/real observation dates matched (0 unmatched dates) in `data/research/event-capture/treasury_breakeven_proxy_39993404661.json`, covering 2026-01-02 through 2026-10-22. The exact conservative availability timestamp is **2026-10-23 17:14:52.697468 UTC**, the later actual retrieval time. These historical observation dates are not valid for earlier point-in-time decisions; this snapshot is only eligible at/after that retrieval time. The nominal-minus-real spread is a proxy, not pure expected inflation.

## What is not complete

- **0 event versions have direction/impact labels; 0 are reviewed or validated.** The annotation queue intentionally leaves scores blank. No labels were invented.
- Current BLS values and current-year Treasury downloads are snapshots retrieved now. Their historical observation periods do not reconstruct when those values were first available. They must not be backfilled into earlier decisions.
- BLS RSS is still unavailable from the runner. The public API provides current levels but not consensus expectations or release surprises.
- SEC company filing headers were not captured in the latest successful run because SEC universe mapping returned HTTP 403. Historical company earnings beat/miss, guidance surprise, and timestamped consensus snapshots are not yet validated.
- A point-in-time-correct universe, aligned price labels, and the reviewed event score panel have not yet been evaluated together in the final chronological out-of-sample test.

## Research gates

| Gate | Current status |
|---|---|
| Official event capture and immutable archive | Partial pass; several official feeds work, BLS RSS returns 403 |
| Nominal and real Treasury capture | Pass for current snapshot; historical PIT eligibility begins at retrieval |
| Current BLS macro snapshot | Pass for 5 series; no historical vintage or consensus |
| Human-reviewed event labels | **Blocked** |
| PIT event signal panel | Not yet valid for empirical scoring without reviewed labels |
| Walk-forward event factor vs price-only baseline | **Not yet evaluated on validated labeled data** |
| Empirical alpha established | **False** |
| Production activation allowed | **False** |

Do not promote this research to production or describe it as profitable until the label review, point-in-time data gates, and frozen out-of-sample evaluation are complete. A source-coverage audit passing only means that the capture itself was structurally valid.
