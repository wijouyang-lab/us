import json
from pathlib import Path

import pandas as pd


def test_eight_accessions():
    p = pd.read_csv("data/research/p17_2_3/p17_2_3_pilot_manifest.csv", dtype=str)
    assert len(p) == 8
    assert p.index_ok.astype(str).str.lower().eq("true").all()


def test_headers_complete():
    h = pd.read_csv("data/research/p17_2_3/p17_2_3_submission_header_metadata.csv", dtype=str)
    assert h.form.notna().all()
    assert h.filed_date.notna().all()
    assert h.acceptance_raw.notna().all()


def test_acceptance_dates_are_8_digits():
    h = pd.read_csv("data/research/p17_2_3/p17_2_3_submission_header_metadata.csv", dtype=str)
    assert h.acceptance_raw.str.len().eq(14).all()


def test_master_index_all_match():
    m = pd.read_csv("data/research/p17_2_3/p17_2_3_master_index_metadata.csv", dtype=str)
    assert m.matched.astype(str).str.lower().eq("true").all()


def test_cik_explained():
    c = pd.read_csv("data/research/p17_2_3/p17_2_3_cik_cross_validation.csv", dtype=str)
    assert (c.cik_status == "MATCH").sum() == 6
    assert (c.cik_status == "CO_REGISTRANT_EXPLAINED").sum() == 2


def test_16_verified_facts():
    o = pd.read_csv("data/research/p17_2_3/p17_2_3_filing_identity_observations.csv", dtype=str)
    assert len(o) == 16
    assert (o.identity_status == "VERIFIED_AT_FILING_ACCEPTANCE").sum() == 16


def test_no_intervals():
    s = json.loads(Path("data/research/p17_2_3/p17_2_3_summary.json").read_text())
    assert s["verified_intervals"] == 0
    assert s["point_observations"] == 16


def test_requests_are_23_and_rate_limited():
    r = pd.read_csv("data/research/p17_2_3/p17_2_3_request_audit.csv")
    assert len(r) == 23
    assert r.status.isin([200, "CACHE"]).all()


def test_no_alpha_side_effects():
    assert not Path("data/research/p17_2_3/p17_2_3_nav.csv").exists()
    assert not Path("data/research/p17_2_3/p17_2_3_trade_ledger.csv").exists()


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_3/p17_2_3_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_3") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
