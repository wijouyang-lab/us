import json
from pathlib import Path

import pandas as pd


def test_300_samples():
    s = pd.read_csv("data/research/p17_2_6/p17_2_6_sample_manifest.csv")
    assert len(s) == 300
    assert s.anchor.value_counts().eq(100).all()


def test_unique_tickers():
    s = pd.read_csv("data/research/p17_2_6/p17_2_6_sample_manifest.csv")
    assert s.ticker.nunique() == 258


def test_cik_candidates_233():
    s = pd.read_csv("data/research/p17_2_6/p17_2_6_sample_manifest.csv")
    assert s.cik_candidate.notna().sum() == 233


def test_anchor_expected_members():
    a = pd.read_csv("data/research/p17_2_6/p17_2_6_anchor_coverage.csv")
    assert a.expected_members.tolist() == [499, 498, 489]


def test_zero_verified_points():
    s = json.loads(Path("data/research/p17_2_6/p17_2_6_summary.json").read_text())
    assert s["asof_evidence"] == 0
    assert s["status"] == "DATA_BLOCKED"


def test_no_network_claim():
    r = pd.read_csv("data/research/p17_2_6/p17_2_6_request_audit.csv")
    assert r.network.iloc[0] == 0


def test_stale_and_missing_evidence():
    a = pd.read_csv("data/research/p17_2_6/p17_2_6_anchor_coverage.csv")
    assert a.stale.sum() == 3
    assert a.no_evidence.sum() == 297


def test_no_new_300_extraction():
    s = json.loads(Path("data/research/p17_2_6/p17_2_6_summary.json").read_text())
    assert "300 historical filings were not retrieved" in s["reason"]


def test_no_alpha_side_effects():
    assert not Path("data/research/p17_2_6/p17_2_6_nav.csv").exists()
    assert not Path("data/research/p17_2_6/p17_2_6_trade_ledger.csv").exists()


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_6/p17_2_6_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_6") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
