# Point-in-Time Event Data Quality Audit

Status: research-only implementation note. No production scanner, scheduler, ranker, or order behavior is changed.

## Added pure helpers

- \`tools/research/pit_sec_edgar.py\`: parses caller-supplied SEC submissions JSON recent-filing arrays. It never makes a network request.
- \`tools/research/pit_macro_releases.py\`: normalizes caller-supplied macro release records while keeping the observation period, scheduled time, actual publication time, consensus timestamp, and vintage timestamp separate.
- \`tools/research/pit_event_coverage.py\`: reports event counts, availability statuses, eligibility reasons, eligible counts by family, and duplicate IDs.
- \`tools/research/pit_event_eligibility.py\`: rejects missing/naive timestamps, future events, observation timestamps preceding publication, unverifiable revisions, and stale records.

## Hard rules

1. A scheduled release timestamp is not proof that the actual release was published at that time.
2. A macro observation period (for example, a month or quarter) is not a publication timestamp.
3. A SEC filing date is not an exact publication timestamp. The raw submissions JSON acceptanceDateTime must also not be assumed to be verified UTC; it can be inconsistent for some records. Only a timestamp converted from the corresponding SGML submission header (or another independently verified UTC source) is accepted in verifiedPublishedAtUtc for primary point-in-time eligibility. Ambiguous or nonexistent New York local times are rejected.
4. Events marked \`timestamp_missing\`, \`mapping_missing\`, \`fetch_error\`, or \`parse_error\` are counted but excluded from eligible signals.
5. Event updates must have a verifiable source update timestamp and a collector observation timestamp that is not earlier than the update.
6. The same event ID appearing more than once causes a duplicate audit failure; downstream feature generation must deduplicate/version records explicitly rather than silently count duplicates.
7. Missing event coverage is not converted to a zero or neutral score.

## Audit report interpretation

- \`audit_status=pass\`: no duplicate IDs, explicit availability failures, or temporal-integrity violations were detected in this batch. This does not establish historical completeness or prove alpha.
- \`fail_missing_data\`: at least one record has explicit missing/unavailable coverage. Inspect the per-status and per-reason counts before using the batch.
- \`fail_temporal_integrity\`: timestamps conflict with decision-time causality.
- \`fail_duplicates\`: duplicate event IDs were found.

The audit is a data-integrity gate, not a performance evaluation. Do not run strategy selection or claim event-factor alpha until frozen snapshots, first-release vintages, and chronological walk-forward folds are available.


## Reproducible local audit

Prepare a JSON array containing already-normalized event records. Keep the input snapshot immutable and record its origin and collection time. Run:

    python -m tools.research.run_pit_event_audit --input normalized_events.json --decision-at 2026-10-15T13:00:00Z --max-age-days-by-type '{"macro_release":2,"earnings":3}' --output audit_report.json

The output includes input_snapshot_sha256, the decision timestamp, freshness configuration, per-family coverage, rejection reasons, and macro-surprise eligibility. Reordering identical input rows does not change the snapshot hash. Any event content, timestamp, or freshness-configuration change does.

The CLI requires a timezone-aware ISO-8601 decision timestamp and a JSON array of event objects. It does not collect data. A pass status means only that the supplied batch passed the implemented structural checks; it does not prove source completeness, point-in-time correctness beyond recorded metadata, or predictive value. A macro surprise marked eligible is still a research feature, not a buy/sell recommendation.


## Optional official SEC source capture

The collector uses no API token, but SEC requests must identify the research application and a contact email in the User-Agent. Supply a JSON file with an explicit universe, for example:

    [{"cik":"0000320193","ticker":"AAPL"}]

Then run with your own contact address (do not use the placeholder literally):

    export SEC_USER_AGENT="US Quant Research your-real-email@domain.com"
    python -m tools.research.sec_event_collector --universe universe.json --start-date 2026-10-01 --end-date 2026-10-23 --output sec_events.json

The command writes the normalized JSON event array and a sibling metadata file. The metadata flags whether the request reaches earlier than the SEC submissions.recent window, whether the per-company limit truncated results, and any header fetch errors. This first implementation does not download older filings.files archives. It is rate-limited and research-only; it does not hook into Scan or the external scheduler.

The capture timestamp is the time this collector first observed each header. Backfilled historical filings do not acquire a fictional historical first-seen time, and therefore are not eligible for decisions before the current capture under the strict audit. Use repeated forward captures to build a proper observation archive before trying a no-lookahead event-factor backtest.
