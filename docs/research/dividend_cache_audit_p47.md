# Legacy SEC Cache Audit — P4.7.2

Date: 2026-11-04
Branch: `research/dividend-legacy-cache-audit-p47`
Stacked target: `research/dividend-evidence-execution-p45`
Status: **PRELIMINARY_ONLY / LEGACY_PLACEHOLDER_UA**

## 1. Final inventory

Local cache: `data/sec/filings_p43/`

| Metric | Count |
|---|---:|
| accession directories | **131** |
| discovered local HTML documents | **224** |
| ticker/CIK mapped accessions | **131** |
| unmapped accessions | **0** |
| documents with SHA-256 | **224/224** |

The earlier 221 count was the index-listed count. P4.7.2 also discovers local
HTML where the usable index was incomplete, giving 224 actual documents. This
is not a claim of 581 filings.

## 2. Document roles (SEC index metadata first)

The cached `index.json` from SEC uses `text.gif` for every item, so it does not
contain usable document types. Roles therefore fall back to filename inference
and are marked as such. When an index item has a real type, that type wins.

| Role | Count | Source |
|---|---:|---|
| PRIMARY | **129** | FILENAME_INFERENCE |
| ANCILLARY | **87** | FILENAME_INFERENCE |
| OTHER_EXHIBIT | **5** | FILENAME_INFERENCE |
| EXHIBIT | **3** | FILENAME_INFERENCE |
| UNKNOWN | **0** | — |

Each document stores:

```text
index_document_type
index_description
document_role
document_role_source
document_role_confidence
```

`document_role_source` is `SEC_INDEX_TYPE`, `FILENAME_INFERENCE`, or `UNKNOWN`.
No missing index was treated as “no file”; local HTML is discovered directly.

## 3. Reference classification

| Status | Count |
|---|---:|
| EXHIBIT_99_REFERENCED | **71** |
| OTHER_EXHIBIT_REFERENCED | **25** |
| NO_EXHIBIT_REFERENCE | **27** |
| EXHIBIT_CACHED | **6** |
| PRIMARY_CACHED | **1** |
| ATTACHMENT_REFERENCE_UNSPECIFIED | **1** |
| 合计 | **131** |

`EXHIBIT_99_REFERENCED` means the primary text refers to EX-99/99.1. It does
**not** mean 71 exhibits were downloaded or 71 announcements were verified.
Only 3 actual EXHIBIT documents and 5 OTHER_EXHIBIT documents are cached.

## 4. Candidate events

| Type | Count |
|---|---:|
| PRELIMINARY_8K_CANDIDATE | **1** |
| HISTORICAL_DIVIDEND_CONTEXT | **10** |
| FALSE_POSITIVE | **1** |
| total | **12** |

All are:

```text
provenance_status = LEGACY_PLACEHOLDER_UA
evidence_status = PRELIMINARY_ONLY
verification_status = PRELIMINARY_ONLY
is_event = false
```

### BAC

The only 8-K candidate:

```text
accession 000007085826000364
source bac-20260723.htm
amount $0.32
```

Its official EX-99.1 is not cached:

```text
EXHIBIT_99_REFERENCED
EX-99.1 cached = NO
```

### CAT

```text
accession 000110465926072929
EXHIBIT_99_REFERENCED
EX-99.1 cached = NO
```

No $1.63 event is verified.

### NEE

```text
FALSE_POSITIVE_NON_DIVIDEND_PRICE_TARGET
$67.75
is_event = false
```

## 5. Text locations

Every candidate and split mention carries:

```text
source_filename
source_sha256
source_document_role
source_text_location
```

Location fields:

```text
start_char
end_char
matched_text
context_before
context_after
text_normalization_version = normalized_text_v1
```

Offsets are in normalized text, not raw HTML bytes.

Candidate location result:

| Result | Count |
|---|---:|
| OK (unique) | **6** |
| LOCATION_AMBIGUOUS | **6** |
| LOCATION_UNRESOLVED | **0** |

Split mentions:

```text
22 mentions
all LOCATION_AMBIGUOUS (the word "split" repeats)
SPLIT_CONFIRMED = 0
```

No line numbers or unique offsets were fabricated.

## 6. Mapping

All nine formerly unmapped accessions resolve from local primary text and the
28-company registry:

```text
UNP, NKE, CRM, AAPL, DUK, GOOGL, GOOGL, GOOGL, MRNA
```

Each mapping has:

```text
submitter_cik_hint
issuer_cik
ticker
mapping_method
mapping_confidence
mapping_source_filename
mapping_source_sha256
```

The accession prefix is only a submitter hint. It is never accepted as the
issuer CIK.

## 7. Parameterized audit

`audit(cache_dir=..., snapshot_path=..., mapping_registry=...)` now:

- loads the supplied snapshot inside the function;
- passes it to accession mapping and name inference;
- does not use a module-import-time global snapshot;
- accepts a temporary registry for fixture tests;
- remains entirely offline.

## 8. CI fixture tests

`tests/test_cache_audit_fixture_p47.py`: **14 passed**, run in CI without the
gitignored cache. They cover:

- EX-99.1 index type without an `ex99` filename;
- EX-10 as OTHER_EXHIBIT;
- index type winning over a conflicting filename;
- missing index discovering local HTML;
- custom `snapshot_path`;
- candidate offsets/context;
- repeated amount → ambiguous;
- split location and own SHA-256;
- exhibit candidate own SHA-256;
- no VERIFIED from a legacy cache.

The 12 real-cache integration tests remain skipped in CI because the cache is
gitignored and absent from checkout.

## 9. Formal status unchanged

```text
VERIFIED dividend events = 0
SPLIT_CONFIRMED = 0
DPS share basis verified = 0/28
FULL_SCAN = CONFIGURATION_BLOCKED
```

No network request, no EX-99.1 download, no other data provider, no production
strategy change.

## 10. Remaining

1. 71 EX-99 references still need actual exhibit retrieval.
2. CAT and BAC EX-99.1 are not cached.
3. 6 candidate and 22 split locations are ambiguous; no fake unique offsets.
4. 131 local accessions remain a subset of 581.
5. Split effective dates remain unconfirmed.
6. Formal re-fetch requires a real SEC user agent in a future phase.


## 11. Final ambiguity rule (P4.7 freeze)

`infer_meta()` now returns `AMBIGUOUS_NAME_MATCH` when several company names
tie at the longest match but map to different tickers:

```text
ticker = null
issuer_cik = null
candidate_tickers = [...]
mapping_source_filename = ...
mapping_source_sha256 = ...
```

It never picks one company, never uses the submitter CIK as issuer CIK, and does
not raise. Unique matches are unaffected.

The new fixture puts two registered company names in one primary and a unique
name in a second accession; only the unique one acquires an issuer.

All 224 document roles are **low-confidence filename inference** because the
cached SEC `index.json` uses `text.gif` for every item. Index types take
precedence when actually present (verified by fixture), but the real cache has
no usable type.

Final frozen counts:

```text
131 accessions
224 documents
224/224 SHA-256
131/131 mapped
0 unmapped

129 PRIMARY
87 ANCILLARY
5 OTHER_EXHIBIT
3 EXHIBIT

71 EXHIBIT_99_REFERENCED
25 OTHER_EXHIBIT_REFERENCED
27 NO_EXHIBIT_REFERENCE
6 EXHIBIT_CACHED
1 PRIMARY_CACHED
1 ATTACHMENT_REFERENCE_UNSPECIFIED
```

Twelve candidates and 22 split mentions are unchanged. Formal states remain
zero VERIFIED events, zero SPLIT_CONFIRMED, 0/28 DPS share basis, and
`FULL_SCAN = CONFIGURATION_BLOCKED`.
