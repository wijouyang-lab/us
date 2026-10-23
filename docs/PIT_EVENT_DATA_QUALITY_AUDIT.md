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
3. A SEC filing date without a verifiable timestamp is not sufficient for primary point-in-time eligibility.
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
