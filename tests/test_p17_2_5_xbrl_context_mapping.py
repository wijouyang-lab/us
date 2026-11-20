import json
from pathlib import Path

import pandas as pd


def test_all_16_points_verified():
    m = pd.read_csv("data/research/p17_2_5/p17_2_5_ticker_security_mapping.csv", dtype=str)
    assert len(m) == 16
    assert (m.identity_status == "VERIFIED_SECURITY_TICKER_POINT").sum() == 16


def test_filings_and_contexts():
    s = json.loads(Path("data/research/p17_2_5/p17_2_5_summary.json").read_text())
    assert s["filings"] == 8
    assert s["contexts"] > 3000


def test_goog_class_c():
    m = pd.read_csv("data/research/p17_2_5/p17_2_5_ticker_security_mapping.csv", dtype=str)
    assert m[m.ticker == "GOOG"].security_title.str.contains("Class C").all()


def test_googl_class_a():
    m = pd.read_csv("data/research/p17_2_5/p17_2_5_ticker_security_mapping.csv", dtype=str)
    assert m[m.ticker == "GOOGL"].security_title.str.contains("Class A").all()


def test_nee_preferred_titles():
    n = pd.read_csv("data/research/p17_2_5/p17_2_5_nee_preferred_audit.csv", dtype=str)
    assert n.ticker.nunique() == 4
    assert n.security_title.str.contains("Corporate Units").all()
    assert n.context_dimensions.str.contains("StatementClassOfStockAxis").all()


def test_context_ids_unique_per_filing():
    c = pd.read_csv("data/research/p17_2_5/p17_2_5_context_registry.csv", dtype=str)
    assert not c.duplicated(["accession", "context_id"]).any()


def test_issuer_cik_matches_context():
    m = pd.read_csv("data/research/p17_2_5/p17_2_5_ticker_security_mapping.csv", dtype=str)
    assert set(m.issuer_cik) == {"0000320193", "0000753308", "0001045810", "0001652044"}


def test_document_hashes_present():
    f = pd.read_csv("data/research/p17_2_5/p17_2_5_raw_xbrl_facts.csv", dtype=str)
    assert f.document_sha256.str.len().eq(64).all()


def test_no_intervals():
    i = pd.read_csv("data/research/p17_2_5/p17_2_5_security_conflicts.csv")
    assert i.status.iloc[0] == "NONE"
    s = json.loads(Path("data/research/p17_2_5/p17_2_5_summary.json").read_text())
    assert s["verified_intervals"] == 0


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_5/p17_2_5_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_5") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
