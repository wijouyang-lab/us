# -*- coding: utf-8 -*-
import json, hashlib
from pathlib import Path
from tools.investment_research.dividend.dividend_cache_audit_p47 import audit


def make_cache(tmp_path, accession="000119312526000001", primary_text="Apple Inc. declared a quarterly dividend of $0.25 per share on common stock. See Exhibit 99.1.", exhibit_text=None):
    d=tmp_path/accession; d.mkdir(parents=True)
    (d/"index.json").write_text(json.dumps({"directory":{"item":[
        {"name":"primary.htm","type":"8-K"},{"name":"ex99-1.htm","type":"EX-99.1"}]}}))
    (d/"primary.htm").write_text(primary_text)
    if exhibit_text is not None: (d/"ex99-1.htm").write_text(exhibit_text)
    return d


def test_temp_cache_issuer_cik_differs_from_submitter(tmp_path):
    d=make_cache(tmp_path)
    a=audit(cache_dir=tmp_path)
    row=a["accessions"][0]
    assert row["ticker"]=="AAPL" and row["issuer_cik"]=="0000320193"
    assert row["submitter_cik_hint"]=="0001193125"
    assert row["mapping_method"]=="local_primary_name"


def test_temp_cache_exhibit_has_own_hash(tmp_path):
    d=make_cache(tmp_path, exhibit_text="Apple Inc. declared a common stock dividend of $0.25 per share.")
    a=audit(cache_dir=tmp_path)
    doc={x["name"]:x for x in a["accessions"][0]["documents"]}
    assert doc["primary.htm"]["sha256"] != doc["ex99-1.htm"]["sha256"]
    ex=[c for c in a["candidates"] if c.get("source_filename")=="ex99-1.htm"]
    assert ex and all(c["source_sha256"]==doc["ex99-1.htm"]["sha256"] for c in ex)


def test_temp_cache_unmapped_name_stays_unmapped(tmp_path):
    make_cache(tmp_path, primary_text="Unknown Holdings declared a dividend of $1.00 per share.")
    a=audit(cache_dir=tmp_path)
    assert a["accessions"][0]["ticker"] is None
    assert a["accessions"][0]["mapping_method"]=="UNMAPPED"


def test_exhibit_99_reference_classification(tmp_path):
    make_cache(tmp_path)
    a=audit(cache_dir=tmp_path)
    assert a["accessions"][0]["status"]=="EXHIBIT_99_REFERENCED"


def test_generic_attachment_not_ex99(tmp_path):
    make_cache(tmp_path, primary_text="Apple Inc. announced a dividend. Additional information is attached.")
    a=audit(cache_dir=tmp_path)
    assert a["accessions"][0]["status"]=="ATTACHMENT_REFERENCE_UNSPECIFIED"


def test_no_verified_candidates_fixture(tmp_path):
    make_cache(tmp_path, exhibit_text="Apple Inc. declared a common stock dividend of $0.25 per share.")
    a=audit(cache_dir=tmp_path)
    assert a["evidence_status"]=="PRELIMINARY_ONLY"
    assert all(c.get("verification_status")=="PRELIMINARY_ONLY" for c in a["candidates"])
    assert all(c.get("is_event") is False for c in a["candidates"])
