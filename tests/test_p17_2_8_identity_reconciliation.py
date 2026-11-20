import json
from pathlib import Path

import pandas as pd


def test_300_results():
    r = pd.read_csv("data/research/p17_2_8/p17_2_8_anchor_identity_results.csv", dtype=str)
    assert len(r) == 300


def test_199_verified():
    s = json.loads(Path("data/research/p17_2_8/p17_2_8_summary.json").read_text())
    assert s["verified_points"] == 199


def test_anchor_counts():
    a = pd.read_csv("data/research/p17_2_8/p17_2_8_anchor_coverage.csv")
    assert a.cik_candidates.tolist() == [67, 76, 90]
    assert a.verified.tolist() == [59, 63, 77]


def test_67_missing_cik_not_82():
    s = json.loads(Path("data/research/p17_2_8/p17_2_8_summary.json").read_text())
    assert s["missing_current_cik_rows"] == 67
    assert s["no_filing_rows"] == 82


def test_19_exceptions_context():
    e = pd.read_csv("data/research/p17_2_8/p17_2_8_19_filing_exception_reconciliation.csv")
    assert len(e) == 19
    assert e.failure_reason.eq("NO_SAME_CONTEXT_PAIR").all()


def test_no_stale_or_future():
    s = json.loads(Path("data/research/p17_2_8/p17_2_8_summary.json").read_text())
    assert s["stale"] == 0 and s["future"] == 0


def test_gate_fails():
    a = pd.read_csv("data/research/p17_2_8/p17_2_8_anchor_coverage.csv")
    assert (a.cik_candidates >= 90).sum() == 1
    assert (a.verified >= 80).sum() == 0


def test_no_new_network():
    s = json.loads(Path("data/research/p17_2_8/p17_2_8_summary.json").read_text())
    assert s["network_requests"] == 0


def test_no_alpha_side_effects():
    assert not Path("data/research/p17_2_8/p17_2_8_nav.csv").exists()
    assert not Path("data/research/p17_2_8/p17_2_8_trade_ledger.csv").exists()


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_8/p17_2_8_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_8") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
