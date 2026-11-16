# P10.4.2: Norgate Data Pipeline Compatibility Preflight

Date: 2026-11-16
Branch: `research/p10-data-provider-evaluation`
Status: **INVESTIGATION + SYNTHETIC TEST ONLY — NO TRIAL, NO PURCHASE**

---

## 1. Question

Can this project run:

```text
Windows Norgate -> private storage -> GitHub Actions
```

for daily low-frequency US equity updates and scans?

Short answer:

```text
Direct GitHub Actions Ubuntu + Norgate: NO-GO
Windows PC/VPS + private store + private Actions: CONDITIONAL GO
Windows PC shutdown: fail closed; no fresh scan
Norgate trial now: NOT YET USEFUL for P9.1 validation
```

---

## 2. Official Norgate facts

### NDU is Windows-only

Norgate's installer requirements:

- Windows 10, Windows 11, Windows 365, Windows Server 2022/2025;
- VM usage explicitly allowed;
- 64-bit CPU, at least 4 GB RAM;
- .NET Framework 4.7.2+;
- NDU must remain open for automatic updates;
- database should not be on a network/cloud drive.

Official: https://norgatedata.com/ndu-installation.php

### Python package is Windows-only

PyPI requirements:

- Python 3.5+;
- Microsoft Windows 10/11 or Windows Server 2019/2022/2025;
- active Norgate subscription;
- NDU installed and running;
- writable local `.norgatedata` folder;
- Mac/Linux users must run NDU in a Windows VM and run Python inside that VM.

Official: https://pypi.org/project/norgatedata/

Therefore the package cannot run directly on GitHub Actions `ubuntu-latest`.

### What Python can retrieve

With NDU running on Windows:

- `price_timeseries()` for daily OHLCV;
- `index_constituent_timeseries()` for daily TRUE/FALSE membership;
- `assetid()` / `symbol()` for stable ID mapping;
- `last_quoted_date()` / `second_last_quoted_date()` for final trading dates;
- `last_database_update_time()` / `status()` for update checks;
- delisted database symbols via `database_symbols()` / `database()`;
- `watchlist_symbols()` for watchlists.

Official: https://pypi.org/project/norgatedata/

### Trial limitation

The trial is three weeks, Platinum level, but only **two years of history**.
It cannot validate 2007-2024 or full P9.1 coverage.

Official: https://norgatedata.com/data-package-faq.php

---

## 3. Can GitHub Actions Ubuntu use Norgate directly?

No.

Reasons:

1. NDU is Windows-only.
2. Python package requires a running NDU and a local Norgate database.
3. GitHub-hosted Ubuntu has no Windows NDU, no licensed database, no
   `.norgatedata` local store.
4. Running NDU in Wine or a Linux container is not an officially supported
   configuration.

Verdict:

```text
NORGATE_DIRECT_GITHUB_ACTIONS: NO-GO
```

---

## 4. Is the Norgate -> private store -> Actions architecture feasible?

Yes, conditionally.

```text
Windows 10/11 PC or Windows VPS
  - NDU open, daily update
  - Python export job
  - build OHLCV + membership + assetid + manifest
  - SHA256 checksums
        |
        | encrypted upload (TLS + client-side encryption)
        v
Private object storage / private DB
  - no public bucket
  - no public artifact
  - retention + versioning
        |
        | authenticated download
        v
GitHub Actions (private workflow or self-hosted runner)
  - verify SHA256
  - check data_updated_at
  - reject stale/incomplete snapshot
  - run scans against the snapshot only
```

Critical rule: the Actions workflow must never fall back to "latest available"
without an age check.

---

## 5. Windows shutdown behaviour

If the Windows machine is off:

- NDU cannot update;
- no new snapshot is uploaded;
- GitHub Actions can still run, but only against the **last successful snapshot**;
- if that snapshot is older than the freshness threshold, the workflow must fail
  closed and must not run a production scan.

Recommended gate:

```text
data_updated_at must be <= 3 calendar days old
and
latest trading date must be the most recent expected US session
```

If the PC is routinely off for days, daily automation is not reliable.

Verdict:

```text
WINDOWS_OFF_FALLBACK: ALLOWED ONLY WITH STALE-DATA BLOCK
```

---

## 6. Transfer and cloud processing licence

Norgate EULA:

- Personal, non-commercial use only.
- Processing environments include hosted/cloud environments, but only for the
  licensee's own personal use.
- No sharing, public display, redistribution or multi-user access.
- On subscription expiry: delete Content, exports, extracts and backups.
- Derived Data may be retained only within the EULA definition.

Relevant clause: https://norgatedata.com/subscribe/eula.php

Interpretation for this architecture:

```text
Private Windows PC/VPS:                     YES (personal use)
Private encrypted object storage:           CONDITIONAL / personal only
GitHub-hosted runner in a PRIVATE repo:     CONDITIONAL
Public GitHub repo/Pages/artifacts/logs:    NO
Public Dashboard:                           NO
Shared team/org use:                        NO
```

GitHub Actions is a third-party processing environment. The EULA allows
processing environments for the licensee, but does not explicitly name GitHub
Actions. Before actual use:

```text
NORGATE_GITHUB_ACTIONS_LICENSE: CONDITIONAL / WRITTEN_CONFIRMATION_RECOMMENDED
```

Do not put raw Norgate data in a public repository, public Actions artifact,
public cache, public log or public Pages output.

---

## 7. Windows Task Scheduler

Feasible:

- Task Scheduler starts NDU at logon/startup;
- NDU remains open;
- a second scheduled task runs the Python export;
- export writes a versioned snapshot and manifest;
- upload to private storage;
- local retry/logs.

Limitations:

- if the PC is off/asleep, the task does not run;
- NDU must be running, not just installed;
- Windows updates/reboots can interrupt;
- the Norgate database must remain local, not on a network/cloud drive;
- two-machine licence limit applies.

This is adequate for a personal workstation but not a highly available service.

---

## 8. Windows VPS option

If an always-on Windows host is required:

```text
Windows Server 2022/2025 VPS
4 vCPU, 8-16 GB RAM, 100+ GB SSD
```

Estimated recurring cost:

```text
$25-$80/month equivalent, provider-dependent
```

Plus:

- Windows licence included or extra;
- private object storage: roughly $1-$10/month;
- backup/snapshot storage;
- maintenance: OS patching, NDU restart, export failure handling, credential
  rotation, storage cleanup, roughly 2-4 hours/month.

These are planning estimates, not vendor quotes.

Verdict:

```text
WINDOWS_VPS: CONDITIONAL GO, but ongoing cost and maintenance
```

---

## 9. Alternatives without a long-running Windows PC

1. **On-demand Windows VM**: start daily, update, export, shut down. Lower cost
   than always-on but adds orchestration and boot time.
2. **Linux-native vendor** (EODHD/Sharadar): no Windows dependency, but PIT
   history/licence remain unverified.
3. **Self-hosted Windows runner**: works only while the machine is on; same
   shutdown limitation.
4. **Keep Norgate as research-only**, not daily production; use a Linux API
   vendor for daily scans.

There is no supported way to run NDU directly on GitHub-hosted Ubuntu.

---

## 10. Synthetic pipeline test

No Norgate data was downloaded or used.

Files:

- `tools/research/p10/synthetic_pipeline.py`
- `tests/test_p10_pipeline_compatibility.py`

Synthetic fields:

```text
ticker, assetid, date, OHLCV
membership: date, ticker, assetid, effective_date, is_member
data_updated_at
sha256
```

Validation:

- canonical JSON SHA256;
- missing required ticker;
- bad OHLCV;
- missing membership;
- stale data;
- future timestamp;
- synthetic-only marker.

Test result:

```text
4 passed
```

Staleness gate:

```text
max_age_days = 3
stale snapshot -> STALE_DATA -> blocked
tampered snapshot -> SHA256_MISMATCH -> blocked
missing ticker -> MISSING_TICKER -> blocked
```

The synthetic test proves the **gate design**, not Norgate coverage.

---

## 11. GO / NO-GO

### Direct Norgate in GitHub Actions Ubuntu

```text
NO-GO
```

### Windows PC + private storage + private Actions, with stale gate

```text
CONDITIONAL GO
```

Conditions:

- Windows host available and NDU running during update;
- private encrypted storage;
- private repo/private runner only;
- SHA256 + freshness + schema gate;
- no raw data in public outputs;
- written confirmation of GitHub Actions as a permitted processing environment.

### Always-on Windows VPS

```text
CONDITIONAL GO
```

Higher cost and maintenance; still needs licence confirmation and data isolation.

### Current project without Windows host

```text
NO-GO for Norgate daily automation
```

Use Linux-native data for daily scans or keep Norgate research-only.

---

## 12. Is the Norgate trial worth starting now?

**Not yet.**

Reasons:

- no Windows host/private pipeline prepared;
- trial only covers two years, so it cannot validate P9.1 2007-2024;
- it cannot prove GitHub Actions compatibility;
- licence confirmation for GitHub-hosted processing is still open.

Worth starting only after:

1. a Windows PC/VM is available;
2. a private storage path is designed;
3. the trial is explicitly limited to two-year mechanics;
4. written/licence review for Actions is underway.

---

## 13. Final status

```text
NORGATE_DIRECT_GITHUB_ACTIONS: NO-GO
NORGATE_WINDOWS_PC_TO_PRIVATE_STORE: CONDITIONAL GO
NORGATE_WINDOWS_VPS: CONDITIONAL GO (cost/maintenance)
WINDOWS_OFF_FALLBACK: FAIL CLOSED ON STALE DATA
NORGATE_GITHUB_ACTIONS_LICENSE: CONDITIONAL / WRITTEN_CONFIRMATION_RECOMMENDED
SYNTHETIC_PIPELINE_TEST: PASS (gate design only)
NORGATE_TRIAL_STARTED: NO
NORGATE_TRIAL_DATA_DOWNLOADED: NO
P9_DATA_REPRODUCIBILITY: BLOCKED
P9_RESULTS: ALL 8 NO-GO
```

---

## 14. Official sources

- NDU installation requirements: https://norgatedata.com/ndu-installation.php
- Norgate Python package: https://pypi.org/project/norgatedata/
- Norgate data FAQ: https://norgatedata.com/data-package-faq.php
- Norgate data content: https://norgatedata.com/data-content-tables.php
- Norgate EULA: https://norgatedata.com/subscribe/eula.php
- Norgate trial: https://norgatedata.com/freetrial.php
- Norgate system requirements: https://norgatedata.com/system-requirements.php
