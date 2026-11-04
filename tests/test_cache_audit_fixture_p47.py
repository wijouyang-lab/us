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


def make_custom(tmp_path, items, files, accession="000119312526000099"):
    d=tmp_path/accession; d.mkdir(parents=True)
    (d/"index.json").write_text(json.dumps({"directory":{"item":items}}))
    for n,t in files.items(): (d/n).write_text(t)
    return d


def test_index_type_ex991_without_ex99_filename(tmp_path):
    make_custom(tmp_path, [{"name":"body.htm","type":"8-K"},{"name":"release.htm","type":"EX-99.1"}],
                {"body.htm":"Apple Inc. declared a dividend.","release.htm":"Apple Inc. $0.25 per share"})
    a=audit(cache_dir=tmp_path)
    roles={x["name"]:x["document_role"] for x in a["accessions"][0]["documents"]}
    assert roles["release.htm"]=="EXHIBIT"


def test_index_type_ex10_is_other_exhibit(tmp_path):
    make_custom(tmp_path, [{"name":"body.htm","type":"8-K"},{"name":"a.htm","type":"EX-10.1"}],
                {"body.htm":"Apple Inc. filed a report.","a.htm":"agreement"})
    a=audit(cache_dir=tmp_path)
    roles={x["name"]:x["document_role"] for x in a["accessions"][0]["documents"]}
    assert roles["a.htm"]=="OTHER_EXHIBIT"


def test_index_type_beats_conflicting_filename(tmp_path):
    make_custom(tmp_path, [{"name":"body.htm","type":"8-K"},{"name":"ex99-1.htm","type":"EX-10"}],
                {"body.htm":"Apple Inc. filing.","ex99-1.htm":"agreement"})
    a=audit(cache_dir=tmp_path)
    roles={x["name"]:x["document_role"] for x in a["accessions"][0]["documents"]}
    assert roles["ex99-1.htm"]=="OTHER_EXHIBIT"


def test_missing_index_discovers_local_html(tmp_path):
    d=tmp_path/"000119312526000100"; d.mkdir(parents=True)
    (d/"local.htm").write_text("Apple Inc. local filing")
    a=audit(cache_dir=tmp_path)
    assert a["accessions"][0]["documents"][0]["name"]=="local.htm"


def test_snapshot_path_controls_mapping(tmp_path):
    snap=tmp_path/"snap.json"
    snap.write_text(json.dumps({"FOO":{"cik":"0000000001","company_name":"Foo Corp"}}))
    cache=tmp_path/"cache"; d=cache/"000119312526000101"; d.mkdir(parents=True)
    (d/"index.json").write_text(json.dumps({"directory":{"item":[{"name":"p.htm","type":"8-K"}]}}))
    (d/"p.htm").write_text("Foo Corp declared a common stock dividend of $1.00 per share.")
    a=audit(cache_dir=cache, snapshot_path=snap)
    assert a["accessions"][0]["ticker"]=="FOO"


def test_candidate_offsets_and_context(tmp_path):
    make_custom(tmp_path, [{"name":"p.htm","type":"8-K"}],
                {"p.htm":"Apple Inc. declared a common stock dividend of $1.23 per share."})
    a=audit(cache_dir=tmp_path)
    c=a["candidates"][0]; loc=c["source_text_location"]
    assert loc["location_status"]=="OK"
    assert loc["start_char"] < loc["end_char"] and loc["matched_text"]=="$1.23"
    assert "Apple" in loc["context_before"]


def test_repeated_amount_is_ambiguous(tmp_path):
    make_custom(tmp_path, [{"name":"p.htm","type":"8-K"}],
                {"p.htm":"Apple Inc. declared a common stock dividend of $1.23 per share. Earlier $1.23 per share."})
    a=audit(cache_dir=tmp_path)
    assert a["candidates"][0]["source_text_location"]["location_status"]=="LOCATION_AMBIGUOUS"


def test_split_location_uses_own_hash(tmp_path):
    make_custom(tmp_path, [{"name":"p.htm","type":"8-K"}],
                {"p.htm":"Apple Inc. announced a 4-for-1 stock split effective August 31, 2020."})
    a=audit(cache_dir=tmp_path)
    assert a["split_mentions"] and a["split_mentions"][0]["source_filename"]=="p.htm"
    assert len(a["split_mentions"][0]["source_sha256"])==64


def test_ambiguous_name_match_never_selects_issuer(tmp_path):
    snap=tmp_path/"snap.json"
    snap.write_text(json.dumps({
        "FOO":{"cik":"0000000001","company_name":"Foo Corp"},
        "BAR":{"cik":"0000000002","company_name":"Bar Corp"}}))
    cache=tmp_path/"cache"
    amb=cache/"000119312526000200"; amb.mkdir(parents=True)
    (amb/"index.json").write_text(json.dumps({"directory":{"item":[{"name":"p.htm","type":"8-K"}]}}))
    (amb/"p.htm").write_text("Foo Corp and Bar Corp announced a transaction.")
    unique=cache/"000119312526000201"; unique.mkdir(parents=True)
    (unique/"index.json").write_text(json.dumps({"directory":{"item":[{"name":"p.htm","type":"8-K"}]}}))
    (unique/"p.htm").write_text("Foo Corp declared a dividend.")
    a=audit(cache_dir=cache, snapshot_path=snap)
    rows={r["accession"]:r for r in a["accessions"]}
    amb_row=rows["000119312526000200"]
    assert amb_row["mapping_method"]=="AMBIGUOUS_NAME_MATCH"
    assert amb_row["ticker"] is None and amb_row["issuer_cik"] is None
    assert amb_row["candidate_tickers"]==["BAR","FOO"]
    assert amb_row["mapping_source_filename"]=="p.htm"
    assert rows["000119312526000201"]["ticker"]=="FOO"
