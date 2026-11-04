# P4.5.1 Recovery, Cache Protection and SEC Limiter

Date: 2026-11-04
Branch: `research/dividend-evidence-execution-p45`
PR: #471 (Draft, appended commit)
Status: **CONFIGURATION_BLOCKED for network collection**

## 1. Actual result

```text
SEC_USER_AGENT_CONFIGURED     no
new SEC requests              0
new filings downloaded        0
manifest expected accessions  not built (requires SEC submissions)
```

No SEC request was made. The code now refuses to start without a real contact.

## 2. Fixed manifest recovery

`sec_fetch_manifest.py` now stores:

- `expected_accessions` inventory;
- per-accession status;
- index status;
- primary status;
- exhibit statuses;
- text-scan flag;
- retry count;
- last attempt;
- error status.

Rules:

- only `FETCHED_COMPLETE` + successful documents + `text_scanned=true` can skip;
- `FETCHED_PARTIAL`, `FETCH_FAILED`, `INDEX_FETCH_FAILED` are retryable;
- cached successful documents are reused;
- only failed documents are re-requested by the fetcher cache.

`complete()` now requires:

1. non-empty expected inventory;
2. every expected accession recorded;
3. every one complete;
4. successful document hashes;
5. text scanned.

A partial accession can never produce `FULL_SCAN_COMPLETE`.

## 3. Full-scan statuses

```text
FULL_SCAN_COMPLETE
FULL_SCAN_PARTIAL
FULL_SCAN_ATTEMPTED_WITH_FAILURES
CONFIGURATION_BLOCKED
```

Current status: `CONFIGURATION_BLOCKED`.

## 4. Cache protection

`.gitignore` now excludes:

```text
data/sec/filings_p43/
data/sec/filings_p44/
data/sec/filings_p45/
```

Raw filing bodies are not staged by Git. Manifest/hash/status summaries remain
committable.

## 5. Global SEC limiter

New:

```text
tools/investment_research/sec/rate_limiter.py
```

- one process-wide `RateLimiter`;
- interval >= 0.25s;
- used by `SECClient` (submissions/companyfacts) and `FilingFetcher`
  (index/primary/exhibit);
- thread-safe;
- no client-local timer;
- no concurrent bypass.

Test with two SEC clients confirms the second wait is after the first interval.

## 6. Tests

`tests/test_recovery_p451.py`: **10 passed**

Covered:

- expected inventory required;
- partial not complete and retryable;
- text-scan required;
- missing accession blocks complete;
- failed exhibit blocks complete;
- config block does not call network;
- `.gitignore` coverage;
- two clients share limiter;
- placeholder invalid;
- repeated upsert no duplicate.

Full P4 suite remains green.

## 7. Remaining

- Configure a real `SEC_USER_AGENT` locally.
- Run `--check-config`; only `SEC_USER_AGENT_CONFIGURED` permits collection.
- Then build the 581-accession inventory and execute the full scan.

No production/trade code changed. No Finnhub call.
