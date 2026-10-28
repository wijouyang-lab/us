# Persistent Cross-Run Event Archive

Date: 2026-10-28
Research only. No production changes.

## Problem with artifacts alone

GitHub Actions artifacts are per-run, independent, and expire. They do not
provide a cumulative database and cannot be used as if they were one.

The persistent store therefore lives on a separate git branch:

```text
research/event-archive
```

main is never modified by the capture workflow.

## Store layout

```text
research/event-archive
  archive/event_archive.json
  archive/observations.json
  archive/latest_manifest.json
  runs/<run_id>/events.json
  runs/<run_id>/metadata.json
  runs/<run_id>/audit.json
  runs/<run_id>/manifest.json
```

- Every run keeps an immutable `runs/<run_id>/` snapshot.
- `event_archive.json` is the deduplicated cumulative version archive.
- `observations.json` links each run observation to `event_id` and
  `event_version_id`; repeated observations grow observations, not unique events.
- `manifest.json` records run ID, commit, run URL, capture/decision times,
  source statuses, hashes, merge counts, revisions, retractions, and conflicts.
- `latest_manifest.json` is the cumulative integrity manifest: run list, snapshot hashes, archive hash, observation hash, and run count.

## Workflow behavior

`.github/workflows/research-event-capture.yml`:

1. `workflow_dispatch` only.
2. Fed RSS capture, optional BLS if a real contact User-Agent is configured.
3. Checkout/fetch `research/event-archive` as a worktree.
4. Import the run snapshot through `event_archive_store.py`.
5. Verify rebuildability.
6. Commit and push only to `research/event-archive`.
7. Upload the per-run artifact for independent retention.

Security:

- top-level `contents: read`; only the capture job gets `contents: write` to
  persist the research branch;
- no schedule/push/pull_request/workflow_run triggers;
- no production workflow dependency;
- no secrets printed;
- no main-branch writes.

Concurrency:

```yaml
concurrency:
  group: research-event-archive
  cancel-in-progress: false
```

This serializes archive writers to reduce lost-update races. A push failure is
a visible workflow failure; the last valid branch commit is not overwritten.

## Recovery

```bash
git fetch origin research/event-archive
git worktree add /tmp/event-archive origin/research/event-archive
python -m tools.research.event_archive_store verify --store /tmp/event-archive
```

`verify` rebuilds the archive from all `runs/*/events.json` and fails if the
cumulative archive is not reproducible.

## Tests

`tests/test_event_archive_store.py` covers:

- two runs: observations grow, unique event does not;
- same run re-import: no extra observation;
- changed content: new version + supersedes link;
- retraction retained and counted;
- corrupt archive: explicit failure, no overwrite;
- timestamp conflict counting;
- rebuild from run snapshots.

Result: **14 passed**. Missing snapshots, hash mismatches, missing latest manifest, corrupt archive, and conflict counts are covered.

Also imported the real 35-event workflow artifact twice under different run IDs:

```text
unique events: 35
versions: 35
observations: 70
duplicates: 35
revisions: 0
retractions: 0
timestamp conflicts: 0
reproducible: true
```

This is simulated cross-run import using a real snapshot; it is **not** a
cross-day observation.

## Current reality

- Real workflow has run once on the default branch: 35 Fed events.
- Persistent archive workflow is in this Draft PR and has **not** run on the
  default branch.
- No cross-day sample exists yet.
- BLS and SEC secrets remain unconfigured.
- No event alpha claim.

## Growth and audit

Each Fed-only run adds roughly tens of KB. The branch provides full commit
history and per-run manifests. If growth becomes material, snapshots can later
be compacted into monthly files without changing the event ID/version semantics;
that is not needed at current volume.

## Canonical hash compatibility

Snapshot hashes use a canonical JSON byte representation:

- UTF-8, no BOM, no trailing newline
- sorted object keys
- compact separators `("," , ":")`
- `allow_nan=False`

The hash is computed by parsing the JSON and hashing canonical bytes, not the
working-tree bytes. LF and CRLF therefore produce the same hash.

Legacy archives created before this change used raw LF bytes in their run
manifests. Verification accepts the canonical hash or the legacy LF-normalized
hash. A real content change cannot match either and still fails.

Tests: 12 passed, including LF/CRLF equivalence, CRLF rewrite verification,
legacy raw hash acceptance, content-change failure, missing snapshots,
corrupt manifests, and rebuild checks.
