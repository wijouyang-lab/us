import json
from pathlib import Path

import pandas as pd


def test_300_rows():
    r = pd.read_csv("data/research/p17_2_8_3_1/p17_2_8_3_1_anchor_identity_results.csv", dtype=str)
    assert len(r) == 300
    assert r.anchor.value_counts().eq(100).all()


def test_235_verified():
    s = json.loads(Path("data/research/p17_2_8_3_1/p17_2_8_3_1_summary.json").read_text())
    assert s["verified"] == 235
    assert s["status"]["VERIFIED_RECONFIRMED"] == 235


def test_259_raw_docs():
    s = json.loads(Path("data/research/p17_2_8_3_1/p17_2_8_3_1_summary.json").read_text())
    assert s["raw_documents"] == 259
    assert s["parse_success"] == 259


def test_anchor_counts():
    a = pd.read_csv("data/research/p17_2_8_3_1/p17_2_8_3_1_anchor_summary.csv")
    assert a.candidate_cik.tolist() == [89, 93, 97]
    assert a.verified.tolist() == [76, 75, 84]


def test_24_exceptions():
    e = pd.read_csv("data/research/p17_2_8_3_1/p17_2_8_3_1_exception_disposition.csv")
    assert len(e) == 24


def test_no_filing_41():
    s = json.loads(Path("data/research/p17_2_8_3_1/p17_2_8_3_1_summary.json").read_text())
    assert s["status"]["NO_HISTORICAL_FILING"] == 41


def test_verified_cik_match():
    r = pd.read_csv("data/research/p17_2_8_3_1/p17_2_8_3_1_anchor_identity_results.csv", dtype=str)
    v = r[r.identity_status == "VERIFIED_RECONFIRMED"]
    assert (v.selected_cik == v.context_entity_cik).all()


def test_network_zero():
    s = json.loads(Path("data/research/p17_2_8_3_1/p17_2_8_3_1_summary.json").read_text())
    assert s["network_requests"] == 0


def test_business_hash():
    s = json.loads(Path("data/research/p17_2_8_3_1/p17_2_8_3_1_summary.json").read_text())
    assert s["business_sha256"] == "11fca29a946bf98ef974646588f4873d30c03f7c29398027ebc1b095a6c0e924"


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_8_3_1/p17_2_8_3_1_output_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_8_3_1") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
