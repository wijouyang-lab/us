import json
from pathlib import Path

import pandas as pd


def test_300_results():
    r = pd.read_csv("data/research/p17_2_7/p17_2_7_anchor_identity_results.csv", dtype=str)
    assert len(r) == 300


def test_199_verified():
    s = json.loads(Path("data/research/p17_2_7/p17_2_7_summary.json").read_text())
    assert s["verified_points"] == 199


def test_anchor_counts():
    a = pd.read_csv("data/research/p17_2_7/p17_2_7_anchor_coverage.csv")
    assert a.cik_candidates.tolist() == [67, 76, 90]
    assert a.verified_points.tolist() == [59, 63, 77]


def test_218_docs():
    s = json.loads(Path("data/research/p17_2_7/p17_2_7_summary.json").read_text())
    assert s["selected_filings"] == 218
    assert s["downloaded_docs"] == 218


def test_no_future_evidence():
    f = pd.read_csv("data/research/p17_2_7/p17_2_7_future_evidence_excluded.csv")
    assert len(f) == 0


def test_no_stale():
    st = pd.read_csv("data/research/p17_2_7/p17_2_7_stale_evidence.csv")
    assert len(st) == 0


def test_request_count():
    s = json.loads(Path("data/research/p17_2_7/p17_2_7_summary.json").read_text())
    assert s["network_requests"] == 218
    assert s["cache_hits"] == 204


def test_anchor_gate_fails():
    a = pd.read_csv("data/research/p17_2_7/p17_2_7_anchor_coverage.csv")
    assert (a.cik_candidates >= 90).sum() == 1
    assert (a.verified_points >= 80).sum() == 0


def test_no_alpha_side_effects():
    assert not Path("data/research/p17_2_7/p17_2_7_nav.csv").exists()
    assert not Path("data/research/p17_2_7/p17_2_7_trade_ledger.csv").exists()


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_7/p17_2_7_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_7") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
