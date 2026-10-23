# Point-in-time event label annotation guide

This is a research annotation protocol, not a trading recommendation. Never invent a label to make the dataset pass readiness checks.

## Required fields

For each archived event version, retain the original collector fields and add:

- `direction_score`: finite number in [-1, 1], or null when direction is ambiguous or evidence is insufficient.
- `impact_score`: finite number in [0, 1], or null when impact cannot be assessed.
- `label_review_status`: `pending`, `reviewed`, or `validated`. Use `reviewed` / `validated` only after a real review has occurred.
- `label_reviewed_at_utc`: timezone-aware ISO-8601 timestamp of the review; null until reviewed.
- `label_rationale`: short evidence-based explanation referencing only the source content used for the annotation.
- `labeler_id` and `reviewer_id`: non-secret internal identifiers if available. Do not put personal email addresses or credentials in the archive.
- `label_schema_version`: version of the written scoring rubric.

## Generate a pending review queue

The capture workflow stores prospective events at `data/research/event-capture/event_archive.json`. Create a separate, non-overwriting CSV queue for recent items:

```bash
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
AS_OF="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python -m tools.research.build_event_annotation_queue \
  --archive data/research/event-capture/event_archive.json \
  --as-of "$AS_OF" \
  --max-age-days 30 \
  --output "data/research/event-capture/annotation_queue_$STAMP.csv" \
  --report "data/research/event-capture/annotation_queue_$STAMP.report.json"
```

The queue contains no proposed scores. Direction and impact stay blank, every row remains `pending`, and only events within the declared age window that were actually observed by `AS_OF` are included. A queue report is not evidence that labels have been reviewed.

## Import reviewed annotations without overwriting the source archive

After a real review, fill the score, review timestamp, rationale, labeler, reviewer, and schema columns. Keep ambiguous scores blank rather than inventing values; the import tool requires both scores for rows marked `reviewed` or `validated`. It ignores `pending` rows and refuses unknown or duplicate event-version IDs, invalid ranges, missing provenance, future review timestamps, and self-validated rows.

```bash
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
AS_OF="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python -m tools.research.apply_event_annotations \
  --archive data/research/event-capture/event_archive.json \
  --annotations-csv data/research/event-capture/annotation_queue_39993404661.csv \
  --as-of "$AS_OF" \
  --output "data/research/event-capture/event_archive_labeled_$STAMP.json" \
  --report "data/research/event-capture/event_annotation_import_$STAMP.json"
```

This creates a separate derived archive; the original append-only source archive remains unchanged. Re-run the readiness audit against the derived archive before building the reviewed signal panel.


## Direction rubric

Score the likely direction for the named ticker or clearly stated market scope, based only on information actually available in the archived source at its point-in-time cutoff:

- `-1.0`: strongly negative
- `-0.5`: moderately negative
- `0.0`: neutral, mixed, or no defensible directional implication
- `+0.5`: moderately positive
- `+1.0`: strongly positive

Intermediate values are allowed when the evidence supports them. Do not infer a ticker-specific direction from a broad macro headline without documenting the scope and rationale. For events with genuinely mixed implications, use 0 or null rather than forcing a sign.

## Impact rubric

- `0.0`: no plausible material market relevance
- `0.25`: low expected relevance
- `0.5`: moderate relevance
- `0.75`: high relevance
- `1.0`: potentially market-moving / highly material

Impact means ex-ante expected relevance, not the realized price move. Do not use subsequent returns, later headlines, revised macro values, or hindsight about the eventual outcome to assign either score.

## Review and point-in-time safeguards

1. Preserve each source event version and its original `published_at_utc`, `first_seen_at_utc`, `source_url`, and content hash. Never rewrite historical timestamps to make an event eligible.
2. Annotate from the archived version available at the decision cutoff. If the source page has since changed and the historical version is unavailable, mark the annotation uncertain or leave scores null.
3. Keep `pending` labels pending until review is actually complete. A valid numeric score or a filled review timestamp alone is not proof of independent review.
4. Prefer a second reviewer who did not create the initial label. Record the reviewer's identifier and review time; document any disagreements and resolution.
5. Never label from forward returns or use post-event outcomes as evidence for the direction/impact score. Those outcomes belong only in the evaluation target.
6. Missing or ambiguous labels stay missing. Do not replace them with zero, carry forward another event's label, or use a headline model's guess as a validated label.
7. Freeze the rubric before the final out-of-sample period. If the rubric changes, increment `label_schema_version` and report the change.

## Before empirical evaluation

Run `tools.research.audit_pit_event_data_readiness` against the exact archive and decision timestamps. Inspect rejected-event reasons and label provenance, not only the top-level status. Then run the predeclared chronological evaluation against the paired price-only baseline. Passing the audit means only that specified data-quality gates passed; it does not establish predictive value or authorize production activation.
