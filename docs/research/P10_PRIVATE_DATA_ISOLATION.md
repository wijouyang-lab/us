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

Required fields:

```text
data_updated_at
expected_last_us_session
latest_price_date
per_ticker_latest_price_date
membership_latest_date
```

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
PER_TICKER_LATEST_MISSING
MEMBERSHIP_LATEST_LAG
EXPECTED_SESSION_MISMATCH
CALENDAR_UNAVAILABLE
STALE_DATA
FUTURE_DATA_UPDATED_AT
```

A fresh `data_updated_at` cannot override a lagging price date.

---

## 5. Coverage gate

Interface supports:

- expected ticker set;
- actual ticker set;
- member-day expected/actual;
- per-day membership completeness;
- assetid/ticker mapping;
- duplicate ticker/date;
- OHLCV positivity and high/low/close range.

Gates remain:

```text
member-day >= 95%
ticker >= 98%
```

Two scopes are separate:

```text
A. TRIAL_MECHANICS: 2-year window only
B. P9_FULL_HISTORY: 2007-05-30 .. 2024-12-31
```

A trial result must never be reported as full-history coverage. The full-history
scope uses the same gates and the full interval.

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

For production, replace the synthetic HMAC with Ed25519/minisign or a KMS-backed
signature. The private key never enters Git or CI logs.

Tests cover:

- modified data;
- modified data + updated SHA (HMAC still fails);
- modified manifest;
- missing signature;
- wrong key;
- duplicate version;
- rollback;
- schema/source mismatch.

---

## 7. Synthetic test results

Files:

- `tools/research/p10/synthetic_pipeline.py`
- `tests/test_p10_pipeline_compatibility.py`

Result:

```text
10 passed
```

Cases:

```text
valid same-session bundle                  PASS
stale latest price with fresh updated_at  BLOCK
one ticker latest date missing            BLOCK
one membership day missing                BLOCK
ticker coverage below 98%                 BLOCK
member-day coverage below 95%             BLOCK
data tampered + SHA updated               HMAC_MISMATCH
missing signature                         BLOCK
wrong key                                 HMAC_MISMATCH
rollback/duplicate version                BLOCK
schema/source/scope mismatch              BLOCK
US holiday and early close calendar       PASS
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
