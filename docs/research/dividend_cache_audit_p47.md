# Legacy SEC Cache Audit — P4.7

Date: 2026-11-04
Branch: `research/dividend-legacy-cache-audit-p47`
Stacked target: `research/dividend-evidence-execution-p45`
Status: **PRELIMINARY_ONLY / LEGACY_PLACEHOLDER_UA**

If the local cache directory is absent (for example in CI), the audit reports
LEGACY_CACHE_UNAVAILABLE and the cache-dependent tests skip; it does not
re-download or fabricate a 110-file result.

## 1. Inventory

Local cache:

```text
data/sec/filings_p43/
```

Actual audit:

| Metric | Count |
|---|---:|
| accession directories | **131** |
| local HTML documents | **221** |
| primary documents | **128** |
| exhibit-only accessions | **3** |
| documents with SHA-256 | **221/221** |
| ticker-mapped accessions | **131** |
| unmapped accessions | **0** |

Status counts:

| Status | Count |
|---|---:|
| EXHIBIT_99_REFERENCED | 71 |
| OTHER_EXHIBIT_REFERENCED | 32 |
| NO_EXHIBIT_REFERENCE | 24 |
| EXHIBIT_CACHED | 2 |
| PRIMARY_CACHED | 1 |
| ATTACHMENT_REFERENCE_UNSPECIFIED | 1 |
| MISSING_LOCAL_FILE | 0 |
| URL_ONLY_NOT_DOWNLOADED | 0 |
| HASH_UNVERIFIED | 0 |

The 131 is the number of local accession directories, not 581. P4.3 only
downloaded a 5-per-company subset for the event scan.

## 2. Provenance gate

Every record carries:

```text
provenance_status = LEGACY_PLACEHOLDER_UA
evidence_status = PRELIMINARY_ONLY
```

No audit result is:

```text
VERIFIED
SPLIT_CONFIRMED
OFFICIAL_EVIDENCE_CLOSED
```

No formal event or split status was changed.

## 3. Document classification

- `EXHIBIT_99_REFERENCED`: 71 accessions explicitly reference EX-99/99.1.
- `OTHER_EXHIBIT_REFERENCED`: 32 reference another numbered exhibit.
- `NO_EXHIBIT_REFERENCE`: 24 primary-only accessions with no exhibit wording.
- `EXHIBIT_CACHED`: 2 exhibit-only accessions.
- `PRIMARY_CACHED`: 1 primary with no exhibit classification.
- `ATTACHMENT_REFERENCE_UNSPECIFIED`: 1 generic attachment reference.
- 131/131 accessions are now mapped; no guessed mapping remains.

## 4. Dividend candidate audit

13 candidate records from local text:

| Candidate type | Count |
|---|---:|
| PRELIMINARY_8K_CANDIDATE | **1** (BAC $0.32) |
| HISTORICAL_DIVIDEND_CONTEXT | **11** |
| FALSE_POSITIVE | **1** (NEE $67.75) |

Only the BAC record has an 8-K-like announcement context and a per-share
common amount. It is still:

```text
PRELIMINARY_ONLY
is_event = false
```

No candidate has `ex_date`; none is inferred.

Historical-context records include NEE 0.35/0.425 and NVDA 0.01/0.024/0.04/0.12
from 10-K/10-Q text; they are not new declarations.

## 5. CAT / BAC / NEE special audit

### CAT

The accession:

```text
000110465926072929
```

has a cached primary document `tm2617177d1_8k.htm`, but **no EX-99.1**.
It is classified:

```text
EXHIBIT_REQUIRED
```

The primary does not contain the $1.63/$1.51 announcement text. Therefore the
CAT dividend cannot be verified from this cache.

### BAC

The accession:

```text
000007085826000364
```

also has a primary but no cached EX-99.1:

```text
EXHIBIT_REQUIRED
```

A preliminary $0.32 candidate was found in a primary 8-K text, but the official
press-release exhibit was not cached. It remains preliminary.

The preferred $1.75 is not counted as a common dividend.

### NEE

The local `$67.75` record is:

```text
FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET
is_event = false
```

The primary document is cached, but the amount is a price target/valuation
reference, not a dividend.

## 6. Split mentions

Local text search found split-related passages in **26** accessions:

```text
ratio: some found
effective date: not confirmed
status: PARTIALLY_VERIFIED / PRELIMINARY_LEGACY_CACHE
SPLIT_CONFIRMED: 0
```

XBRL fact period end and filing date were not used as effective dates.
No split event was promoted.

## 7. Files

```text
tools/investment_research/dividend/dividend_cache_audit_p47.py
data/research/dividend_cache_audit_p47.json
tests/test_dividend_cache_audit_p47.py
```

The audit uses only local file reads. It does not import or call urllib,
requests, httpx, Yahoo, AKShare, or Finnhub.

## 8. Remaining

1. 81 accessions need actual EX-99.1 downloads.
2. CAT/BAC official exhibits are still not cached; their $1.63/$0.32 events are
   not verified.
3. 9 accessions remain unmapped to ticker/CIK.
4. 131 local accessions ≠ 581 full 8-K inventory.
5. Split effective dates still need explicit official sentences.
6. Legacy cache is preliminary only and cannot enter the formal registry.

No production/trade code changed.


## 9. P4.7.1 identity and per-file fixes

All nine previously unmapped accessions now resolve from local primary text and
the 28-company registry:

```text
000010088517000056 -> UNP
000032018715000113 -> NKE
000119312514084762 -> CRM
000119312515023732 -> AAPL
000132616014000003 -> DUK
000165204416000022 -> GOOGL
000165204423000016 -> GOOGL
000165204423000045 -> GOOGL
000168285219000009 -> MRNA
```

Each record now has `submitter_cik_hint`, `issuer_cik`, `mapping_method`,
`mapping_confidence`, source filename and SHA-256. Mapped: **131/131**, unmapped:
**0**.

Candidates and split mentions are parsed per HTML document; each has its own
`source_filename`, `source_sha256`, `source_document_role` and
`source_text_location`. Exhibit text cannot inherit the primary hash.

Attachment classification changed from a broad 81 `EXHIBIT_REQUIRED` bucket to:

```text
EXHIBIT_99_REFERENCED 71
OTHER_EXHIBIT_REFERENCED 32
NO_EXHIBIT_REFERENCE 24
EXHIBIT_CACHED 2
PRIMARY_CACHED 1
ATTACHMENT_REFERENCE_UNSPECIFIED 1
```

Generic "attached" no longer implies EX-99.1. Split mentions increased to 26
because per-exhibit text is now scanned separately; no split is confirmed.

Six fixture tests in `tests/test_cache_audit_fixture_p47.py` run in CI without
the gitignored cache and cover issuer vs submitter CIK, per-file hashes,
UNMAPPED fallback, EX-99 classification and no-VERIFIED protection.
