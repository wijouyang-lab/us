# Historical Event Source Assessment

Date: 2026-10-29 UTC
Research only. No new requests without valid identity.

## Decision

No new historical source is admitted. Existing Fed RSS forward events remain
the only real event population.

## Comparison

| Source | Official URL | Historical coverage | Time precision | Revision / vintage | Access | Storage/public artifact | Real request | New events |
|---|---|---|---|---|---|---|---|---|
| SEC EDGAR submissions / 8-K | https://www.sec.gov/edgar/sec-api-documentation | provider filing archive; exact start not measured | filingDate = date only; SGML ACCEPTANCE-DATETIME = second (fixed EST) | amendments/accession versions; no one-click vintage API | public; real contact UA required | filing records are public; written terms/retention review **unverified** | **not executed** | 0 |
| Federal Reserve press/speeches | https://www.federalreserve.gov/newsevents.htm | RSS window; 2026 press archive observed: 114 links | RSS published_at; archive date-only | page corrections not versioned in RSS | public; contact UA for BLS only; Fed RSS works with project UA | public official pages; redistribution terms not formally reviewed | Fed RSS **yes**; 2026 archive **yes** | 0 PIT; 114 retrospective |
| BLS releases / archives | https://www.bls.gov/bls/news-release/ | archive pages, not measured | release date/time; revisions | BLS revisions | API/contact UA; no configured identity | **unverified** | **not executed** | 0 |
| BEA releases | https://www.bea.gov/news/schedule | archive/schedule, not measured | scheduled/actual release time; revisions | BEA revisions | API key/terms; not configured | **unverified** | **not executed** | 0 |
| FRED / ALFRED | https://fred.stlouisfed.org/ | long macro history; vintages | release timestamps; ALFRED vintage dates | explicit vintage support | API key/terms; not configured | **unverified** | **not executed** | 0 |
| Earnings calendar | no approved free source | n/a | often date only | vendor-specific | n/a | n/a | **not executed** | 0 |

## Key distinctions

- A historical publication timestamp is not a historical `first_seen_at`.
- `filingDate` alone is not an exact public time.
- BLS/BEA/FRED revisions must use vintage/release records, not today鈥檚 latest
  value substituted backward.
- SEC accession identity is stable; amendments are separate versions, not
  overwrites.
- No source is counted as PIT until a real forward observation or an explicit
  vintage record exists.

## Current real access

- Fed press RSS: 20 events, ok.
- Fed speeches RSS: 15 events, ok.
- archive: 36 unique, 70 observations, verify true.
- No SEC/BLS/BEA/FRED request in this phase.

## Blocking conditions

1. No valid `SEC_USER_AGENT` / `OFFICIAL_FEED_USER_AGENT`.
2. No approved API keys for BEA/FRED.
3. No written storage/redistribution review for public artifacts.
4. Historical archive coverage has not been measured with real requests.
5. SEC acceptance timestamps require SGML retrieval, not filingDate.

## Consequence

The current 36 events remain forward-PIT only. A future historical/backfilled
dataset must be stored separately, explicitly marked
`observation_mode=retrospective_backfill`, and must not be added to the PIT
count or used to claim the 200-event/365-day gate.
## Actual Fed historical probe

A real read of the official 2026 Fed press archive at
`https://www.federalreserve.gov/newsevents/pressreleases/2026-press.htm`
returned **114 press links** (HTTP 200).

Evidence:

- Source URL: `https://www.federalreserve.gov/newsevents/pressreleases/2026-press.htm`
- Raw HTML SHA-256 `4dd6ae63f551c463f0bd0574d33dae6939af4e12673ab03edfb8527e2b59f3b7` (raw page not committed)
- `docs/research/fed_2026_press_retrospective_2026-10-29.json`

Classification:

```text
observation_mode: retrospective_backfill
timestamp_precision: date_only
first_seen_at: null
pit_eligible: false
```

These 114 are **not** PIT events and are not an addition to the 36-event PIT
sample. They show that the Fed historical archive is technically accessible
without extra credentials, but exact publication times, storage/redistribution
terms, and historical first-seen remain unresolved.

No return labels are attached because no approved price source is available.
