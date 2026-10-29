# Fed Live Capture Runbook (Windows)

Research-only manual procedure. No scheduler or background service.

## 1. Find the official release

1. Open the Fed FOMC calendar:
   `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`
2. For the current release, use the official `monetaryYYYYMMDDa.htm` link.
3. Confirm the page contains `For release at H:MM a.m./p.m. EDT|EST`.
4. Record the scheduled time and timezone before running.

Do not treat the calendar date alone as an exact publication time.

## 2. Before release

- Open PowerShell in the repository.
- Confirm PR/branch and clean state:
  ```powershell
  git status --short
  git rev-parse HEAD
  gh pr view 398 --repo wijouyang-lab/us --json state,isDraft,headRefOid
  ```
- Record current UTC:
  ```powershell
  (Get-Date).ToUniversalTime().ToString("o")
  ```
- Confirm store path and existing event count.

## 3. At/after release

Run once, manually:

```powershell
cd <repo>
.\..\venv\Scripts\python.exe -m tools.research.capture_batch `
  --url "https://www.federalreserve.gov/newsevents/pressreleases/monetaryYYYYMMDDa.htm" `
  --store "docs/research/fomc_live_capture_<date>.jsonl" `
  --batch-id "fed-<date>-a"
```

Do not use fake URLs, non-Fed domains, or automated loops.

For a single URL, `tools/research/forward_capture.py` is also valid.

## 4. Verify the record

Open the newest JSONL line and check:

- `http_status = 200`
- `parse_status = exact`
- `published_at` matches the page
- `first_seen_at_utc` is the actual current UTC
- `content_hash` present
- `is_simulated = false`
- `is_historical_backfill = false`
- `observation_kind`
- `source_evidence = official_fed_page`
- `published_at_evidence = official_release_time_in_page`

If the first observation is more than one hour after `published_at`, the record
is **late** and cannot enter PIT.

## 5. Repeat and version behavior

Run the same URL again:

- same `event_id` must not create a new independent event;
- `first_seen_at_utc` must be unchanged;
- unchanged content must keep the same version;
- changed content may create a new version, but must keep first_seen.

## 6. Network / parse failure recovery

- A failed fetch is stored with `parse_status = http_error/network_error`.
- Do not delete failed records.
- Rerun the same URL later; a successful retry may create the first valid
  observation, but must not overwrite an existing first_seen.
- If the page parsed incorrectly, keep the failure record and inspect manually;
  do not guess the release time.

## 7. Backup and duplicate checks

```powershell
Copy-Item docs/research/fomc_live_capture_*.jsonl <private-backup>\ -Force
Get-Content docs/research/fomc_live_capture_*.jsonl | Measure-Object -Line
```

Check duplicate event IDs and versions:

```powershell
Get-Content <store> | ConvertFrom-Json |
  Group-Object event_id |
  Select-Object Name, Count
```

## 8. Admission check

Run:

```powershell
.\..\venv\Scripts\python.exe -m tools.research.pit_sample_audit `
  --store "docs/research/fomc_*capture*.jsonl" `
  --output docs/research/pit_sample_audit_<date>.json
```

Only `pit_admitted > 0` after a genuine short-lag observation is meaningful.
`first_seen` alone is not enough.

## 9. Run states

| State | Meaning |
|---|---|
| `live_forward_observation` | observed within 1h; candidate only |
| `late_observation_of_old_event` | first seen too late |
| `historical_backfill` | today's download of old page |
| `capture_error` | HTTP/parse failure |
| `date_only` | no exact time; not PIT |

No background process is started by this runbook.
