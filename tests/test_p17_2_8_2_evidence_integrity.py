import json
from pathlib import Path

import pandas as pd


def test_300_rows():
    r = pd.read_csv("data/research/p17_2_8_2/p17_2_8_2_anchor_identity_results.csv", dtype=str)
    assert len(r) == 300
    assert r.anchor.value_counts().eq(100).all()


def test_237_verified():
    s = json.loads(Path("data/research/p17_2_8_2/p17_2_8_2_summary.json").read_text())
    assert s["verified"] == 235
    assert s["old_verified"] == 198
    assert s["new_verified"] == 37


def test_verified_key_fields_nonempty():
    r = pd.read_csv("data/research/p17_2_8_2/p17_2_8_2_anchor_identity_results.csv", dtype=str)
    v = r[r.identity_status == "VERIFIED_RECONFIRMED"]
    for col in ["selected_cik", "context_entity_cik", "acceptance_utc", "evidence_age_days", "document_sha256", "contextRef", "security_title"]:
        assert v[col].notna().all() and (v[col] != "").all()


def test_verified_cik_match():
    r = pd.read_csv("data/research/p17_2_8_2/p17_2_8_2_anchor_identity_results.csv", dtype=str)
    v = r[r.identity_status == "VERIFIED_RECONFIRMED"]
    assert (v.selected_cik == v.context_entity_cik).all()


def test_anchors():
    a = pd.read_csv("data/research/p17_2_8_2/p17_2_8_2_anchor_coverage.csv")
    assert a.cik_candidates.tolist() == [89, 93, 97]
    assert a.verified.tolist() == [76, 75, 84]


def test_gate_fails():
    a = pd.read_csv("data/research/p17_2_8_2/p17_2_8_2_anchor_coverage.csv")
    assert (a.cik_candidates >= 90).sum() == 2
    assert (a.verified >= 80).sum() == 1


def test_three_unresolved():
    r = pd.read_csv("data/research/p17_2_8_2/p17_2_8_2_anchor_identity_results.csv", dtype=str)
    assert (r.identity_status == "AMBIGUOUS_SECURITY_CONTEXT").sum() == 2
    assert (r.identity_status == "REVOKED_TITLE_MISSING").sum() == 3


def test_no_network():
    s = json.loads(Path("data/research/p17_2_8_2/p17_2_8_2_summary.json").read_text())
    assert s["network_requests"] == 0


def test_p10_80():
    p = pd.read_csv("data/research/p17_2_8_2/p17_2_8_2_p10_crosswalk_audit.csv")
    assert len(p) == 80


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_8_2/p17_2_8_2_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_8_2") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]

