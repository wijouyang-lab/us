# FS2.4 Versioned Publisher

Date: 2026-11-26
PR #630

## Implementation

`tools/investment_research/fs2/publish_snapshot.py` now supports:

```text
publish
validate
verify
rollback
list-versions
```

Publish writes an immutable `versions/fs2_v<version>.json`, verifies SHA and
row count after readback, then atomically replaces the manifest. The manifest is
the single pointer; current/previous entries carry path, version, SHA, row count,
generated_at, prices_as_of, fundamentals_as_of.

Manifest replacement uses temp file + fsync + `os.replace`. A failed publish
leaves the old manifest and old snapshot intact.

Archive cleanup keeps 30 versions, never current or previous. Rollback also
builds a new manifest and atomically replaces it.

## Actual A→B→C→rollback evidence

```text
publish A: current vA, previous null
publish B: current vB, previous vA, archive 2 versions
publish C (10 rows): rejected
publish D (5601 rows): rejected
manifest SHA before/after failures: identical
rollback to vA: current vA, previous vB
verify: valid true
```

Formal manifest:

```text
schema_version 2
current fs2.v1.4
previous fs2.v1.3
current SHA d6d843146b8ce89723a97de2647f43a2d8578a002ff57adb1e5619bf198cbf78
verify: valid
```

## Limits

- The publisher does not implement a cross-file transaction; consistency is
  provided by immutable version files + atomic manifest pointer.
- Manifest write failure injection was tested at the code path level manually,
  not as an automated pytest suite in this round.
- Archive cleanup was exercised logically; no long 30-version retention run.
- Browser E2E remains 20/20 from FS2.3 and was not rerun after publisher-only
  changes.

## Browser compatibility

Manifest v2 shape unchanged: `current`/`previous` entries with `path`, `sha256`,
`row_count`. Page SHA/row/ticker validation and stale/fail-closed behavior
unchanged. Formal manifest verified.

## Production boundary

No Scan/Review/Evolve/score/ATR/stop/PAPER/IBKR changes. Draft, not merged.
## Automated fault suite (FS2.4.1)

`tests/test_fs2_publish.py` has 15 tests:

1. 31 versions + retention/disk consistency
2. pinned retained
3. rollback `../` rejected
4. rollback backslash rejected
5. missing rollback rejected
6. corrupted rollback data rejected
7. current corrupt -> verify fails
8. previous corrupt -> verify fails
9. manifest write failure -> old manifest unchanged
10. manifest os.replace failure -> old unchanged
11. version write failure -> old unchanged
12. cleanup failure -> current/previous still verify
13. rollback success
14. retained == disk after cleanup
15. verify full entry validation (Tier corruption)

Local run: 15 passed. CI run is authoritative.
