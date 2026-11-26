# FS2.3 Runtime & E2E Acceptance (v2)

Date: 2026-11-26
PR #630 / branch `research/full-universe-price-liquidity-v1`

## Manifest v2

`dashboard/data/fs2_candidates_manifest.json`:

```json
{
  "schema_version": 2,
  "current": {"version":"fs2.v1.4","path":"fs2/versions/fs2_v1.4.json","row_count":5600,"sha256":"d6d843..."},
  "previous": {"version":"fs2.v1.3","path":"fs2/versions/fs2_v1.3.json","row_count":5600,"sha256":"69b5d9..."}
}
```

Both version files are complete 5,600-row JSON files.

The page:

1. fetches manifest;
2. validates schema;
3. fetches current, computes SHA-256 in browser;
4. validates 5,600 rows, unique ticker, required fields;
5. falls back to previous if current fails;
6. shows STALE ARCHIVED SNAPSHOT banner with previous version/date;
7. fails closed with `CANDIDATE SNAPSHOT UNAVAILABLE` if both fail.

## E2E: 20/20

Chromium 156, local HTTP:

| Check | Result |
|---|---|
| load | PASS |
| 5,600 rows | PASS (112 pages) |
| style filter | PASS (170) |
| tier filter | PASS (343) |
| tradability filter | PASS (2,098) |
| security type | PASS (315 ADR) |
| industry | PASS (16 options) |
| liquidity | PASS (1,821) |
| ticker search | PASS |
| company search "Apple" | PASS (4 rows) |
| sort | PASS |
| pagination | PASS |
| all pages 0 duplicates | PASS (5,600 unique) |
| all pages no omission | PASS (5,600) |
| detail panel | PASS |
| missing `—` / zero `0` | PASS (`isMissing(0)=false`, `fmt(0)="0"`) |
| RESEARCH ONLY | PASS |
| dates/version | PASS |
| stale archive banner | PASS |
| fail closed | PASS |

Screenshots: `artifacts/fs2_3/page_v2.png`, `stale_v2.png`, `fail_closed_v2.png`.

## Snapshot fault tests

- A→B: archive A retained, manifest current B.
- C 10 rows: rejected, B hash unchanged, manifest unchanged, archive count unchanged.
- current missing: browser falls back to `fs2.v1.3`, banner visible.
- manifest missing: fail closed.

## Zero/missing fix

`!r.value_rank` replaced with explicit `isMissing`:

- `0` → displayed `0`;
- `null` / `undefined` / `""` → `—`;
- detail “Missing” only uses explicit missing check.

## Data

```text
COMMON 20D 4,750/5,186 = 91.59%
ADR 20D 271/315 = 86.03%
total 5,021/5,501 = 91.28%
NO_DATA 457
CA REVIEW 470 (469 CA-blocked + SAEN identity-blocked)
```

Prices unadjusted; no PIT.
