import json
from pathlib import Path

import pandas as pd


def test_pr390_overlap_46_36():
    s = json.loads(Path("data/research/p17_2_8_1/p17_2_8_1_summary.json").read_text())
    assert s["pr390_rows"] == 98
    assert s["overlap_rows"] == 46
    assert s["overlap_tickers"] == 36


def test_confidence_35_1():
    c = pd.read_csv("data/research/p17_2_8_1/p17_2_8_1_historical_cik_candidates.csv", dtype=str)
    assert c.identity_confidence.nunique() == 2


def test_recovered_38():
    s = json.loads(Path("data/research/p17_2_8_1/p17_2_8_1_summary.json").read_text())
    assert s["recovered_verified"] == 38


def test_total_237():
    s = json.loads(Path("data/research/p17_2_8_1/p17_2_8_1_summary.json").read_text())
    assert s["verified_total"] == 237


def test_anchor_counts():
    a = pd.read_csv("data/research/p17_2_8_1/p17_2_8_1_anchor_coverage.csv")
    assert len(a) == 3
    assert a.verified.tolist() == [77, 76, 84]


def test_anchor_gate():
    a = pd.read_csv("data/research/p17_2_8_1/p17_2_8_1_anchor_coverage.csv")
    assert (a.cik_candidates >= 90).sum() == 2
    assert (a.verified >= 80).sum() == 1


def test_network_76():
    s = json.loads(Path("data/research/p17_2_8_1/p17_2_8_1_summary.json").read_text())
    assert s["network_requests"] == 76


def test_no_alpha_side_effects():
    assert not Path("data/research/p17_2_8_1/p17_2_8_1_nav.csv").exists()
    assert not Path("data/research/p17_2_8_1/p17_2_8_1_trade_ledger.csv").exists()


def test_status_partial():
    s = json.loads(Path("data/research/p17_2_8_1/p17_2_8_1_summary.json").read_text())
    assert s["status"] == "PARTIAL_COVERAGE_ONLY"


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_8_1/p17_2_8_1_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_8_1") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
