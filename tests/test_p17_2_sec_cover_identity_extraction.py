import json
from pathlib import Path

import pandas as pd


def test_parser_finds_dei_symbols_and_cik():
    o = pd.read_csv("data/research/p17_2/p17_2_filing_identity_observations.csv")
    assert len(o) > 0
    assert o.ticker.str.len().gt(0).all()
    assert (o.issuer_cik.astype(str).str.zfill(10) == o.filing_cik.astype(str).str.zfill(10)).all()


def test_cat_classes_are_separate():
    o = pd.read_csv("data/research/p17_2/p17_2_filing_identity_observations.csv")
    cat = o[o.ticker.isin(["CAT", "CAT35"])]
    assert set(cat.ticker) == {"CAT", "CAT35"}
    assert cat.security_class_member.nunique() >= 2


def test_exchange_and_title_paired():
    o = pd.read_csv("data/research/p17_2/p17_2_filing_identity_observations.csv")
    cat = o[o.ticker == "CAT"].iloc[0]
    assert "Common" in cat.security_title
    assert "New York" in cat.exchange


def test_no_historical_observation_claim():
    q = json.loads(Path("data/research/p17_2/p17_2_parser_quality.json").read_text())
    assert q["local_filings"] == 75
    assert q["historical_2020_2024_filings"] == 0
    assert q["historical_identity_observations"] == 0
    assert q["parser_status"] == "PARSER_FEASIBLE_LOCAL_2026_ONLY"


def test_daily_coverage_is_zero_placeholder():
    d = pd.read_csv("data/research/p17_2/p17_2_daily_identity_coverage.csv")
    assert d.verified_identity.max() == 0
    assert len(d) > 1200


def test_summary_is_blocked():
    s = json.loads(Path("data/research/p17_2/p17_2_summary.json").read_text())
    assert s["status"] == "DATA_BLOCKED"
    assert s["quality"]["coverage_status"] == "DATA_BLOCKED_NO_HISTORICAL_FILINGS"


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2/p17_2_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]


def test_no_alpha_side_effects():
    assert not Path("data/research/p17_2/p17_2_nav.csv").exists()
    assert not Path("data/research/p17_2/p17_2_trade_ledger.csv").exists()
