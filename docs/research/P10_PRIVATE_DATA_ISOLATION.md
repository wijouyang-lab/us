# P10.4.3: Private Data Isolation and Production Data Gate Preflight

Date: 2026-11-16
Branch: `research/p10-data-provider-evaluation`
Status: **ARCHITECTURE + SYNTHETIC TESTS ONLY — NO TRIAL, NO PURCHASE**

---

## 1. Public repository constraint

`wijouyang-lab/us` remains public. It must not receive:

- raw Norgate Content;
- exported price/membership files;
- Norgate database copies;
- API keys or storage credentials;
- private workflow logs/artifacts/cache containing data.

The public repository may receive only non-reversible aggregates, e.g. counts,
coverage percentages, gate statuses and synthetic fixtures.

Repository visibility is not changed in this phase.

---

## 2. Private repository architecture

```text
Windows 10/11 PC or Windows VPS
  NDU running, database local
  Python exporter
  synthetic or licensed export
  snapshot + manifest
        |
        | TLS + client-side encryption
        v
Private object storage (S3/R2/B2 or private DB)
  private bucket, versioning, lifecycle
  no public URL
        |
        | OIDC / short-lived credentials
        v
Private GitHub repository
  private Actions workflow
  validate signature + freshness + coverage
  private scan results
        |
        | publish only non-reversible aggregates
        v
Public repository: docs, summaries, no raw data
```

Use a **separate private repository**; do not make the current repository private
and do not add private data workflows to it.

### Existing GitHub account

A private repository can be created under the existing account later. This phase
does not create it or change settings.

Private-repo Actions minutes and storage are account-plan dependent; budget must
be checked before use.

---

## 3. Minimal permissions and credentials

Private workflow:

```yaml
permissions:
  contents: read
```

Rules:

- no write token in the data-processing job;
- cloud access via GitHub OIDC short-lived credentials, not long-lived keys;
- secrets in GitHub Environment, restricted to protected branches;
- no secrets in pull-request workflows;
- no secrets exposed to forks;
- no `pull_request_target` with data credentials;
- artifact retention minimal/disabled for raw data;
- cache disabled for raw data;
- logs must not print rows, keys or signed URLs;
- rotate storage credentials/keys; revoke on removal;
- separate key IDs for signing and cloud access.

No implementation is added here; this is a design requirement.

---

## 4. US trading-date gate

`data_updated_at` alone is insufficient. A fresh upload can still contain stale
prices.

Required checks are derived from actual rows, not metadata:

```text
data_updated_at                 (timezone required)
actual overall latest OHLCV date
actual per-ticker latest dates
actual membership latest date
expected_last_us_session        (XNYS calendar)
```

The following metadata is retained only to detect inconsistencies:

```text
reported_latest_price_date
reported_membership_latest_date
```

It is never trusted as the source of truth.

`expected_last_us_session` is computed with `exchange_calendars` XNYS, not
natural days. It handles weekends, US holidays and early closes.

Implemented behavior:

- after a normal session close, that session is expected;
- before close, the previous session is expected;
- holidays/weekends resolve to the previous session;
- early close uses the exchange calendar's close time;
- calendar failure blocks the pipeline.

Any of these must block:

```text
LATEST_PRICE_DATE_LAG
REPORTED_LATEST_MISMATCH
PER_TICKER_LATEST_LAG
CORE_TICKER_MISSING
MEMBERSHIP_LATEST_LAG
REPORTED_MEMBERSHIP_MISMATCH
MEMBERSHIP_RECORD_MISSING
MEMBERSHIP_DAY_INCOMPLETE
CALENDAR_UNAVAILABLE
STALE_DATA
FUTURE_DATA_UPDATED_AT
TIMESTAMP_WITHOUT_TIMEZONE
```

A fresh `data_updated_at` cannot override a lagging actual price/membership date.

---

## 5. Coverage gate

Membership semantics are explicit:

- `is_member=True`: constituent on that date;
- `is_member=False`: valid non-constituent record, not missing;
- no row for expected ticker/date: missing data.

Member-day denominator uses an **independent expected membership baseline**, not
the supplier's own rows. If that baseline is absent, status is
`EXPECTED_MEMBERSHIP_NOT_VERIFIABLE` and the gate cannot PASS.

Interface checks:

- expected vs actual ticker set;
- core ticker set (hard block);
- member-day expected/actual from the independent baseline;
- per-day True/False record completeness;
- assetid/ticker consistency;
- duplicate ticker/date;
- finite/positive volume;
- OHLC finite, positive, high >= open/close, low <= open/close.

Coverage rules:

```text
core ticker missing          -> BLOCK regardless of overall percentage
overall ticker coverage <98% -> BLOCK
member-day coverage <95%     -> BLOCK
missing non-core ticker at 98% -> allowed
```

Two fixed scopes:

```text
A. TRIAL_MECHANICS: max 2 years from actual trial_start_date
B. P9_FULL_HISTORY: 2007-05-30 .. 2024-12-31 exactly
```

P9_FULL_HISTORY checks actual first/last OHLCV dates and membership end; editing
`membership_start_date` metadata cannot change the acceptance interval.

A trial result must never be reported as full-history coverage.

---

## 6. Integrity and anti-rollback

A SHA256 stored in the same JSON is only corruption detection. It cannot stop an
attacker who changes both data and hash.

Design:

- data file (`snapshot.json`);
- separate manifest (`manifest.json`);
- manifest contains `data_sha256`, `version`, `created_at`, `source`, `schema`;
- HMAC-SHA256 over the manifest fields with a secret key not in the repository;
- validator rejects missing signature, wrong key and modified manifest;
- state file records last accepted version;
- lower version -> `ROLLBACK`;
- equal version -> `DUPLICATE_VERSION`;
- source/schema mismatch -> block.

`commit_bundle()` implements the closed loop:

1. validate signature/data;
2. read last accepted version;
3. reject lower/equal;
4. write a temp state file;
5. `fsync` then atomic `os.replace`;
6. only then return `committed=True`.

A state-write failure returns `STATE_WRITE_FAILED` and does not start a scan.
The local JSON state is synthetic-only; production must use a durable trusted
store (database/object-store conditional write/KMS), not a mutable local file.

For production, replace the synthetic HMAC with Ed25519/minisign or a KMS-backed
signature. The private key never enters Git or CI logs.

Tests cover modified data, data+SHA modified together, modified manifest, missing
signature, wrong key, duplicate/rollback, state-write failure and schema/source
mismatch.

---

## 7. Synthetic test results

Files:

- `tools/research/p10/synthetic_pipeline.py`
- `tests/test_p10_pipeline_compatibility.py`

Result:

```text
15 passed
```

Cases:

```text
valid synthetic bundle                         PASS
actual AAPL latest lag vs metadata             BLOCK
overall metadata claims newer than rows        BLOCK
membership metadata claims newer than rows     BLOCK
valid is_member=False record                    PASS
missing membership row                          BLOCK
missing independent baseline                    NOT_VERIFIABLE
non-core missing at 98%                         PASS
core ticker missing at 98%                      BLOCK
commit success updates durable state            PASS
rollback / duplicate version                    BLOCK
state-write failure                             BLOCK, no state
P9 start/end boundaries                         PASS/BLOCK
trial claimed as P9 full history                BLOCK
bad OHLCV / naive timestamp                     BLOCK
US holiday and early close calendar             PASS
```

All fixtures are explicitly `synthetic: true`.

---

## 8. Norgate EULA review (2026-11-07)

Official: https://norgatedata.com/subscribe/eula.php

Relevant points:

- Personal Use means the licensee's own non-commercial use.
- Processing Environments may include third-party hosted/cloud/analysis services,
  provided Content remains solely for the licensee and the provider gets no
  independent use right.
- Content exported/copied remains Content.
- Derived Data can include backtests, statistics, models and results that cannot
  reconstruct Content.
- No public/shared/multi-user access or redistribution.
- On expiry, delete Content, exports, extracts and backups; Derived Data may be
  retained within the EULA definition.

Interpretation:

```text
Private Windows PC/VPS:                  YES — personal
Private encrypted object storage:        CONDITIONAL — personal only
Private GitHub Actions processing:       CONDITIONAL — not explicitly named
Public GitHub/Pages/artifacts/logs:      NO
Shared team/org use:                     NO
```

Do not claim the EULA forbids third-party cloud processing; it allows personal
processing environments. Do not claim GitHub Actions is automatically approved.
Obtain written confirmation for the exact GitHub-hosted setup.

---

## 9. Retention and deletion policy

On subscription end:

- delete Norgate Content, exports, extracts and backups;
- delete private object-store versions containing Content;
- delete private workflow caches/artifacts containing Content;
- retain only Derived Data that meets the EULA definition;
- keep coverage/audit aggregates only if they cannot reconstruct Content;
- record deletion date and scope.

The public repository must never contain a copy requiring deletion.

---

## 10. Cost and maintenance

Windows VPS planning estimate:

```text
4 vCPU, 8-16 GB RAM, 100+ GB SSD: $25-$80/month equivalent
private object storage:           $1-$10/month
private Actions minutes/storage:  account-plan dependent
maintenance:                     2-4 hours/month
```

Additional work:

- Windows patching/reboot recovery;
- NDU update/restart monitoring;
- signed export failure alerts;
- storage lifecycle and key rotation;
- monthly restore/rollback drill.

These are estimates, not vendor quotes.

---

## 11. GO / NO-GO

### Public repo direct processing

```text
NO-GO
```

### Windows PC/VPS + private store + private repo/Actions

```text
CONDITIONAL GO
```

Conditions:

- private repository and private storage;
- OIDC/short-lived credentials;
- signed, versioned snapshot;
- US-calendar freshness gate;
- 95%/98% gates applied only in the correct scope;
- no raw data in public outputs;
- written/licence review for GitHub-hosted processing.

### No Windows host

```text
NO-GO for Norgate daily automation
```

### Trial

```text
NOT YET
```

The three-week trial is only two years and cannot validate P9.1 2007-2024. It is
worth starting only after a Windows host and private pipeline exist, and only as
a mechanics test.

---

## 12. Final status

```text
PUBLIC_REPO_RAW_VENDOR_DATA: NO
PRIVATE_REPO_ARCHITECTURE: DESIGNED / NOT CREATED
PRIVATE_STORAGE: DESIGNED / NOT CREATED
SIGNED_DATA_GATE: SYNTHETIC PASS
US_CALENDAR_GATE: SYNTHETIC PASS
TRIAL_MECHANICS_SCOPE: SEPARATE
P9_FULL_HISTORY_SCOPE: SEPARATE
MEMBER_DAY_GATE: 95%
TICKER_GATE: 98%
NORGATE_GITHUB_ACTIONS_LICENSE: CONDITIONAL / WRITTEN_CONFIRMATION_RECOMMENDED
NORGATE_TRIAL_STARTED: NO
NORGATE_TRIAL_DATA_DOWNLOADED: NO
P9_DATA_REPRODUCIBILITY: BLOCKED
P9_RESULTS: ALL 8 NO-GO
```

No repository was created, no visibility changed, no vendor data downloaded, no
trial started, no purchase made.
