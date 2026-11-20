import json
from pathlib import Path

import pandas as pd


def test_16_facts_split():
    o = pd.read_csv("data/research/p17_2_4/p17_2_4_identity_point_observations.csv", dtype=str)
    assert len(o) == 16
    assert (o.identity_status == "VERIFIED_SECURITY_TICKER_POINT").sum() == 8
    assert (o.identity_status == "IDENTITY_CONFLICT").sum() == 8


def test_preferred_conflict():
    o = pd.read_csv("data/research/p17_2_4/p17_2_4_identity_point_observations.csv", dtype=str)
    pref = o[o.ticker.str.startswith("NEE.PR")]
    assert len(pref) == 6
    assert pref.identity_status.eq("IDENTITY_CONFLICT").all()


def test_goog_class_conflict():
    o = pd.read_csv("data/research/p17_2_4/p17_2_4_identity_point_observations.csv", dtype=str)
    assert o[o.ticker == "GOOG"].identity_status.eq("IDENTITY_CONFLICT").all()
    assert o[o.ticker == "GOOGL"].identity_status.eq("VERIFIED_SECURITY_TICKER_POINT").all()


def test_verified_unique_tickers():
    s = json.loads(Path("data/research/p17_2_4/p17_2_4_summary.json").read_text())
    assert s["p17_2_3"]["unique_verified_tickers"] == 4
    assert s["p17_2_3"]["unique_conflict_tickers"] == 5


def test_no_intervals():
    i = pd.read_csv("data/research/p17_2_4/p17_2_4_identity_intervals.csv")
    assert i.status.iloc[0] == "NONE"


def test_daily_gate_fails():
    s = json.loads(Path("data/research/p17_2_4/p17_2_4_cross_section_summary.json").read_text())
    assert s["max_verified"] == 1
    assert s["gate_100"] is False


def test_request_provenance_unverifiable():
    s = json.loads(Path("data/research/p17_2_4/p17_2_4_summary.json").read_text())
    assert s["request"]["original_network_count"] == "ORIGINAL_NETWORK_REQUEST_COUNT_UNVERIFIABLE"
    assert s["request"]["cache_hits"] == 23


def test_75_metadata_only_two():
    a = pd.read_csv("data/research/p17_2_4/p17_2_4_75_accession_audit.csv")
    assert len(a) == 75
    assert a.metadata_complete.sum() == 2


def test_field_conflicts_three():
    c = pd.read_csv("data/research/p17_2_4/p17_2_4_field_conflicts.csv")
    assert len(c) == 3
    assert c.accession.nunique() == 3


def test_no_alpha_side_effects_and_manifest():
    assert not Path("data/research/p17_2_4/p17_2_4_nav.csv").exists()
    assert not Path("data/research/p17_2_4/p17_2_4_trade_ledger.csv").exists()
    import hashlib
    m = json.loads(Path("data/research/p17_2_4/p17_2_4_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_4") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
