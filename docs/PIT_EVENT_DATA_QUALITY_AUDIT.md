# Point-in-Time Event Data Quality Audit

Status: research-only implementation note. No production scanner, scheduler, ranker, or order behavior is changed.

## Added pure helpers

- \`tools/research/pit_sec_edgar.py\`: parses caller-supplied SEC submissions JSON recent-filing arrays. It never makes a network request.
- \`tools/research/pit_macro_releases.py\`: normalizes caller-supplied macro release records while keeping the observation period, scheduled time, actual publication time, consensus timestamp, and vintage timestamp separate.
- \`tools/research/pit_event_coverage.py\`: reports event counts, availability statuses, eligibility reasons, eligible counts by family, and duplicate-version IDs.
- `tools/research/pit_event_archive.py`: maintains a deduplicated logical event-version archive, preserves the earliest first-seen time for unchanged versions, and selects the latest version known at a historical decision time.
- `tools/research/official_event_rss_collector.py`: captures BLS CPI, BLS Employment Situation, and Federal Reserve press-release RSS from a built-in official-host allowlist, with timestamp missingness, source-content hashes, and first-seen times.
- \`tools/research/pit_event_eligibility.py\`: rejects missing/naive timestamps, future events, observation timestamps preceding publication, unverifiable revisions, and stale records.

## Hard rules

1. A scheduled release timestamp is not proof that the actual release was published at that time.
2. A macro observation period (for example, a month or quarter) is not a publication timestamp.
3. A SEC filing date is not an exact publication timestamp. The raw submissions JSON acceptanceDateTime must also not be assumed to be verified UTC; it can be inconsistent for some records. Only a timestamp converted from the corresponding SGML submission header (or another independently verified UTC source) is accepted in verifiedPublishedAtUtc for primary point-in-time eligibility. The conversion uses fixed EST (UTC−05:00) as the SEC documentation specifies, rather than automatically applying daylight-saving offsets. This is an acceptance time, not a timestamp proving the instant the filing first became visible on SEC.gov; the collector's actual first-seen time remains mandatory for strict replay.
4. Events marked \`timestamp_missing\`, \`mapping_missing\`, \`fetch_error\`, or \`parse_error\` are counted but excluded from eligible signals.
5. Event updates must have a verifiable source update timestamp and a collector observation timestamp that is not earlier than the update.
6. The same event version ID appearing more than once causes a duplicate audit failure. Different versions of the same event are preserved, and a decision-time replay must select the latest version that had been observed by that decision.
7. Missing event coverage is not converted to a zero or neutral score.

## Audit report interpretation

- \`audit_status=pass\`: no duplicate IDs, explicit availability failures, or temporal-integrity violations were detected in this batch. This does not establish historical completeness or prove alpha.
- \`fail_missing_data\`: at least one record has explicit missing/unavailable coverage. Inspect the per-status and per-reason counts before using the batch.
- \`fail_temporal_integrity\`: timestamps conflict with decision-time causality.
- \`fail_duplicates\`: duplicate event IDs were found.

The audit is a data-integrity gate, not a performance evaluation. Do not run strategy selection or claim event-factor alpha until frozen snapshots, first-release vintages, and chronological walk-forward folds are available.


## Reproducible local audit

Prepare a JSON array containing already-normalized event records. Keep the input snapshot immutable and record its origin and collection time. Run:

    python -m tools.research.run_pit_event_audit --input normalized_events.json --decision-at 2026-10-15T13:00:00Z --max-age-days-by-type '{"macro_release":2,"earnings":3}' --expected-sources bls_cpi_rss,federal_reserve_press_rss --output audit_report.json

The output includes input_snapshot_sha256, the decision timestamp, freshness configuration, per-family coverage, rejection reasons, and macro-surprise eligibility. Reordering identical input rows does not change the snapshot hash. Any event content, timestamp, or freshness-configuration change does.

The CLI requires a timezone-aware ISO-8601 decision timestamp and a JSON array of event objects. It does not collect data. A pass status means only that the supplied batch passed the implemented structural checks; it does not prove source completeness, point-in-time correctness beyond recorded metadata, or predictive value. A macro surprise marked eligible is still a research feature, not a buy/sell recommendation.


## Optional official SEC source capture

The collector uses no API token, but SEC requests must identify the research application and a contact email in the User-Agent. Supply a JSON file with an explicit universe, for example:

    [{"cik":"0000320193","ticker":"AAPL"}]

Then run with your own contact address (do not use the placeholder literally):

    export SEC_USER_AGENT="US Quant Research your-real-email@domain.com"
    python -m tools.research.sec_event_collector --universe universe.json --start-date 2026-10-01 --end-date 2026-10-23 --output sec_events.json

The command writes the normalized JSON event array and a sibling metadata file. Each fetched official header gets a SHA-256 hash in the output for reproducibility. Existing output files are protected by default: choose new output names for each snapshot, or deliberately pass --overwrite only when replacement is intended. The metadata flags whether the request reaches earlier than the SEC submissions.recent window, whether the per-company limit truncated results, whether header timestamps were unverified, and any header fetch errors. This first implementation does not download older filings.files archives. It is rate-limited and research-only; it does not hook into Scan or the external scheduler.

The capture timestamp is the time this collector first observed each header. Backfilled historical filings do not acquire a fictional historical first-seen time, and therefore are not eligible for decisions before the current capture under the strict audit. Use repeated forward captures to build the observation archive.

To append a collected snapshot while deduplicating unchanged versions, run:

    python -m tools.research.pit_event_archive --input sec_events.json --archive sec_event_archive.json

The archive keeps distinct content/timestamp versions and ignores transient `fetch_error` rows as event versions; collection errors remain in the collector metadata. The audit pipeline automatically selects one event version per event ID as of `--decision-at` when given this versioned archive:

    python -m tools.research.run_pit_event_audit --input sec_event_archive.json --decision-at 2026-10-23T13:00:00Z --max-age-days-by-type '{"earnings":3,"company_news":2}' --output audit_report.json

The audit report distinguishes the full archive hash from the decision-time analysis snapshot hash. As with the collector, archive replay is only point-in-time verifiable from the first actual observation timestamp onward; it does not repair missing historical capture logs.


## SEC timestamp semantics references

- SEC Webmaster FAQ: https://www.sec.gov/about/webmaster-frequently-asked-questions — defines Acceptance Time as EST and notes that no timestamp identifies exactly when filing content first becomes available on SEC.gov.
- EDGAR Public Dissemination Technical Specification (10 March 2025): https://www.sec.gov/info/edgar/specifications/pds_dissemination_spec.pdf — identifies the acceptance time field as EST.


## Optional official macro/policy RSS capture

The RSS collector uses no API token, has a fixed allowlist of official feeds, and refuses to overwrite snapshot files unless explicitly told to. Set a real contact address for the User-Agent, then run:

    export OFFICIAL_FEED_USER_AGENT="US Quant Research your-real-email@domain.com"
    python -m tools.research.official_event_rss_collector --feeds bls_cpi,bls_employment,fed_all --output official_events.json

Supported feed keys are `bls_cpi` (https://www.bls.gov/feed/cpi.rss), `bls_employment` (https://www.bls.gov/feed/empsit.rss), `fed_all` (https://www.federalreserve.gov/feeds/press_all.xml), and `fed_speeches` (https://www.federalreserve.gov/feeds/speeches_and_testimony.xml). The BLS feeds are tagged as macro-release events; Federal Reserve press releases are deterministically tagged as central-bank communications when the title/description contains preselected monetary-policy terms, and otherwise as policy events. The official Federal Reserve speeches-and-testimony feed is tagged as central-bank communication.

RSS publication dates are retained as provider metadata but are not assumed to be proof of the instant the item first became public. The collector records its own first-seen time, saves a feed payload hash and coverage report, and flags missing timestamps. These feeds are useful for forward-observation of official headlines, but do not provide historical consensus snapshots and cannot by themselves establish an earnings/macro surprise alpha. Append the resulting JSON to the same logical archive with `python -m tools.research.pit_event_archive --input official_events.json --archive event_archive.json`.

Official feed directories: https://www.bls.gov/feed/ and https://www.federalreserve.gov/feeds/feeds.htm.


## One-command manual capture and audit

Run a manual research capture to save a unique snapshot, append it to the event-version archive, and audit the archive as of an explicit decision timestamp. No schedule or production hook is created.

    export OFFICIAL_FEED_USER_AGENT="US Quant Research your-real-email@domain.com"
    python -m tools.research.run_event_capture_cycle --output-dir research/event-data --decision-at 2026-10-23T13:00:00Z --max-age-days-by-type '{"macro_release":2,"central_bank":3,"policy":3,"company_news":2,"earnings":3}'

It writes timestamped `.events.json`, `.metadata.json`, and `.audit.json` files plus `event_archive.json`. Repeated captures preserve individual snapshots while deduplicating unchanged event versions in the archive. To optionally collect SEC company filings, add `--sec-universe universe.json --sec-start-date YYYY-MM-DD --sec-end-date YYYY-MM-DD` and configure `SEC_USER_AGENT` with a real contact email. Backfilled historical filings retain the actual observation time and cannot be presented as known at earlier decisions.

The command returns a nonzero status if every requested source fails, but a successful fetch can still produce a failing coverage audit. Review the saved audit before research use; this command never generates a buy/sell signal.
