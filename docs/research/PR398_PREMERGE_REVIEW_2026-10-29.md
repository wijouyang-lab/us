# PR #398 Pre-Merge Review

Date: 2026-10-29 UTC
Reviewer: research automation check
Verdict: **ready for user review after one fix; not merged**.

## 1. Scope and write paths

The scheduled job only:

- writes `docs/research/event_forward_runs/<timestamp>/` (artifact input);
- pushes commits to `research/event-archive`;
- uploads an artifact.

It does not write main, canonical prices, scanner output, scoring, stops,
ledger, order path, or external triggers. `git push` target is explicitly:

```text
HEAD:research/event-archive
```

## 2. Trigger requirements

`workflow_dispatch` +:

```yaml
schedule:
  - cron: "15 21 * * 1-5"
```

GitHub only runs `schedule` and exposes `workflow_dispatch` for a workflow that
exists on the **default branch**. This branch-only PR cannot actually be
scheduled or manually dispatched until it is reviewed and merged. No scheduled
run is claimed.

## 3. Critical bug found and fixed

Previously:

```yaml
FEEDS: ${{ github.event.inputs.feeds }}
...
--feeds "$FEEDS"
```

On a `schedule` event there are no inputs, so `FEEDS` is empty. The CLI rejects
an empty feed list unless SEC is enabled:

```text
select at least one RSS feed or provide --sec-universe
```

A scheduled run would have failed immediately.

Fix:

```bash
feeds="${FEEDS:-bls_cpi,bls_employment,fed_all,fed_speeches}"
--feeds "$feeds"
```

A regression test now checks the non-empty default.

## 4. DST / close timing

Cron is UTC; US regular close is 16:00 ET:

| US regime | 16:00 ET in UTC | 21:15 UTC |
|---|---|---|
| EDT (summer) | 20:00 UTC | 1h15m after close |
| EST (winter) | 21:00 UTC | 15m after close |

21:15 UTC is after the normal close in both regimes. GitHub scheduled runs can
be delayed, which only increases the post-close margin. The job does not compute
+1/+5, so it cannot fabricate future returns.

## 5. Permissions

- top level: `contents: read`;
- only capture job: `contents: write`;
- no `write-all`;
- no `pull_request`, `push`, or `workflow_run` trigger;
- concurrency group `research-event-archive`, cancellation disabled;
- timeout 15 minutes.

## 6. Idempotency / failures

- timestamped capture directory;
- archive import deduplicates event IDs/versions;
- existing snapshots are fetched via worktree; no overwrite;
- `git diff --cached --quiet` avoids empty archive commits;
- `verify` runs before push;
- source statuses preserved; BLS without real UA remains skipped;
- artifact upload is `if: always()` for diagnosis;
- failure after a partial capture still leaves metadata; no success claim.

## 7. Artifact / public-data review

- artifact `research-event-capture-<run_id>`;
- retention 90 days;
- observed archive files: `events.json`, `metadata.json`, `audit.json`,
  `manifest.json`;
- no credentials or HTTP raw bodies;
- public Fed event data may still be publicly downloadable; residual risk
  documented for review.

## 8. Unresolved issues

1. Must be merged to default branch before it can schedule or be manually
   dispatched.
2. BLS/SEC still lack real contact User-Agent configuration.
3. 503 price provider license remains unresolved; no return observations are
   produced by this workflow.
4. Scheduled holidays still invoke the workflow; source may return no new events.
5. Public artifact risk needs explicit approval.

## Recommendation

Do not merge or enable auto-merge without user approval. After merge, perform a
single manual run first, verify artifact/archive, then monitor the first
scheduled run.
