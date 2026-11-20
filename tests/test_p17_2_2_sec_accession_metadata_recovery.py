import json
from pathlib import Path

import pandas as pd


def test_accession_parser_18_digits():
    a = pd.read_csv("data/research/p17_2_2/p17_2_2_accession_registry.csv", dtype=str)
    assert len(a) == 75
    assert a.accession_no_dash.str.len().eq(18).all()
    assert a.parse_status.eq("PARSED").all()


def test_dashed_accession_and_prefix():
    a = pd.read_csv("data/research/p17_2_2/p17_2_2_accession_registry.csv", dtype=str)
    r = a[a.accession_no_dash == "000032019321000065"].iloc[0]
    assert r.accession_dashed == "0000320193-21-000065"
    assert r.accession_prefix_cik == "0000320193"
    assert r.accession_year == "2021"


def test_no_sec_user_agent_no_download():
    s = json.loads(Path("data/research/p17_2_2/p17_2_2_summary.json").read_text())
    assert s["user_agent_status"] == "MISSING"
    assert s["download_status"] == "SEC_DOWNLOAD_BLOCKED_MISSING_USER_AGENT"


def test_metadata_is_only_two():
    m = pd.read_csv("data/research/p17_2_2/p17_2_2_sec_index_metadata.csv").iloc[0]
    assert m.has_form == 2 and m.has_acceptance == 2 and m.metadata_complete == 2


def test_historical_counts():
    s = json.loads(Path("data/research/p17_2_2/p17_2_2_summary.json").read_text())
    assert s["metadata"]["historical_2020_2024"] == 8
    assert s["coverage"]["historical_symbol_facts"] == 16
    assert s["coverage"]["historical_tickers"] == 9


def test_p13_overlap_five():
    c = pd.read_csv("data/research/p17_2_2/p17_2_2_historical_identity_coverage.csv").iloc[0]
    assert set(eval(c.p13_overlap_tickers_list)) == {"AAPL", "GOOG", "GOOGL", "NEE", "NVDA"}


def test_all_historical_facts_candidate_only():
    o = pd.read_csv("data/research/p17_2_2/p17_2_2_filing_identity_observations.csv")
    assert o.identity_status.eq("CANDIDATE_ONLY").all()
    assert not o.metadata_verified.any()


def test_no_acceptance_claim():
    a = pd.read_csv("data/research/p17_2_2/p17_2_2_acceptance_timeline.csv")
    assert a.status.iloc[0] == "UNAVAILABLE"


def test_no_alpha_side_effects():
    assert not Path("data/research/p17_2_2/p17_2_2_nav.csv").exists()
    assert not Path("data/research/p17_2_2/p17_2_2_trade_ledger.csv").exists()


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_2/p17_2_2_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_2") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
