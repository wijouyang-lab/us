import json
from pathlib import Path

import pandas as pd


def test_300_rows():
    r = pd.read_csv("data/research/p17_2_8_3/p17_2_8_3_anchor_identity_results.csv", dtype=str)
    assert len(r) == 300
    assert r.groupby("anchor").size().eq(100).all()


def test_groups_199_38_63():
    r = pd.read_csv("data/research/p17_2_8_3/p17_2_8_3_anchor_identity_results.csv", dtype=str)
    assert r.group.value_counts().to_dict() == {"ORIGINAL_199": 199, "OTHER_UNVERIFIED": 63, "NEW_38": 38}


def test_status_235():
    s = json.loads(Path("data/research/p17_2_8_3/p17_2_8_3_summary.json").read_text())
    assert s["status"]["VERIFIED_RECONFIRMED"] == 235
    assert s["samples"] == 300


def test_original_group_198():
    r = pd.read_csv("data/research/p17_2_8_3/p17_2_8_3_anchor_identity_results.csv", dtype=str)
    o = r[r.group == "ORIGINAL_199"]
    assert (o.identity_status == "VERIFIED_RECONFIRMED").sum() == 198
    assert (o.identity_status == "AMBIGUOUS_SECURITY_CONTEXT").sum() == 1


def test_new_group_37():
    r = pd.read_csv("data/research/p17_2_8_3/p17_2_8_3_anchor_identity_results.csv", dtype=str)
    n = r[r.group == "NEW_38"]
    assert (n.identity_status == "VERIFIED_RECONFIRMED").sum() == 37
    assert (n.identity_status == "REVOKED_TITLE_MISSING").sum() == 1


def test_anchor_counts():
    a = pd.read_csv("data/research/p17_2_8_3/p17_2_8_3_anchor_summary.csv")
    assert a.candidate_cik.tolist() == [89, 93, 97]
    assert a.verified.tolist() == [76, 75, 84]


def test_24_exceptions():
    e = pd.read_csv("data/research/p17_2_8_3/p17_2_8_3_exception_disposition.csv")
    assert len(e) == 24
    assert e.identity_status.value_counts().to_dict() == {
        "FILING_FOUND_IDENTITY_UNVERIFIED": 19,
        "REVOKED_TITLE_MISSING": 3,
        "AMBIGUOUS_SECURITY_CONTEXT": 2,
    }


def test_no_network():
    s = json.loads(Path("data/research/p17_2_8_3/p17_2_8_3_summary.json").read_text())
    assert s["network_requests"] == 0
    assert s["cache_hits"] == 235


def test_business_hash():
    s = json.loads(Path("data/research/p17_2_8_3/p17_2_8_3_summary.json").read_text())
    assert s["business_sha256"] == "f726a1e351ebfa0e10faa4443ba83031f6e5819e5699b85044f3c8f3e05b0c95"


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_8_3/p17_2_8_3_output_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_8_3") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
