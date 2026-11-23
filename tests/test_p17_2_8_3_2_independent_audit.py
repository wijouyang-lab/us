import json
from pathlib import Path

import pandas as pd


def test_300_rows():
    r = pd.read_csv("data/research/p17_2_8_3_2/row_level_reconciliation.csv", dtype=str)
    assert len(r) == 300
    assert r.anchor.value_counts().eq(100).all()


def test_235_verified():
    s = json.loads(Path("data/research/p17_2_8_3_2/independent_verification_summary.json").read_text())
    assert s["verified"] == 235
    assert s["status"]["VERIFIED_RECONFIRMED"] == 235


def test_41_split():
    s = json.loads(Path("data/research/p17_2_8_3_2/independent_verification_summary.json").read_text())
    assert s["status"]["NO_HISTORICAL_CIK_CANDIDATE"] == 21
    assert s["status"]["NO_HISTORICAL_FILING"] == 20


def test_259_docs():
    d = pd.read_csv("data/research/p17_2_8_3_2/document_registry.csv")
    assert d.accession.nunique() == 259


def test_anchors():
    a = pd.read_csv("data/research/p17_2_8_3_2/anchor_coverage_recalculated.csv")
    assert a.verified.tolist() == [76, 75, 84]


def test_exceptions_24():
    e = pd.read_csv("data/research/p17_2_8_3_2/identity_exception_audit.csv")
    assert len(e) == 24


def test_recovery_zero():
    r = pd.read_csv("data/research/p17_2_8_3_2/cached_filing_recovery.csv")
    assert r.recovered.iloc[0] == 0


def test_no_network():
    s = json.loads(Path("data/research/p17_2_8_3_2/independent_verification_summary.json").read_text())
    assert s["network_requests"] == 0


def test_business_hash():
    s = json.loads(Path("data/research/p17_2_8_3_2/independent_verification_summary.json").read_text())
    assert s["business_sha256"] == "c081540d629e98d51e82a10556b76a62e25121e60b637dd99bd7dc0ee9500485"


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_8_3_2/output_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_8_3_2") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
