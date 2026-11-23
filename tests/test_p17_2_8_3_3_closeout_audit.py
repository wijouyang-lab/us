import json
from pathlib import Path

import pandas as pd


def test_300_rows():
    r = pd.read_csv("data/research/p17_2_8_3_3/row_level_classification_adjudication.csv", dtype=str)
    assert len(r) == 300
    assert r.anchor.value_counts().eq(100).all()


def test_235_verified():
    s = json.loads(Path("data/research/p17_2_8_3_3/validation_summary.json").read_text())
    assert s["verified"] == 235


def test_21_20_split():
    s = json.loads(Path("data/research/p17_2_8_3_3/validation_summary.json").read_text())
    assert s["status"]["NO_HISTORICAL_CIK_CANDIDATE"] == 21
    assert s["status"]["NO_HISTORICAL_FILING"] == 20


def test_cache_files_498():
    s = json.loads(Path("data/research/p17_2_8_3_3/validation_summary.json").read_text())
    assert s["cache_files"] == 498
    assert s["submissions"] == 239


def test_no_recovery():
    s = json.loads(Path("data/research/p17_2_8_3_3/validation_summary.json").read_text())
    assert s["recovered"] == 0


def test_anchors():
    r = pd.read_csv("data/research/p17_2_8_3_3/row_level_classification_adjudication.csv", dtype=str)
    a = r.groupby("anchor").new_status.apply(lambda x: (x == "VERIFIED_RECONFIRMED").sum())
    assert a.to_dict() == {"A": 76, "B": 75, "C": 84}


def test_verified_context_audit():
    v = pd.read_csv("data/research/p17_2_8_3_3/verified_235_context_audit.csv", dtype=str)
    assert len(v) == 235
    assert v.context_match.astype(str).str.lower().eq("true").all()
    assert v.title_present.astype(str).str.lower().eq("true").all()


def test_no_network():
    s = json.loads(Path("data/research/p17_2_8_3_3/validation_summary.json").read_text())
    assert s["network_requests"] == 0


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_8_3_3/output_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_8_3_3") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]


def test_business_hash():
    s = json.loads(Path("data/research/p17_2_8_3_3/validation_summary.json").read_text())
    assert s["business_sha256"] == "eb136aa437a5b2df155dc4133cc1ca6dc0edb22efa3434c0bfdf757173645750"
