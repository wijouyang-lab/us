import json
from pathlib import Path

import pandas as pd


def test_corrected_filing_counts():
    s = json.loads(Path("data/research/p17_2_1/p17_2_1_summary.json").read_text())
    assert s["filings"] == 75
    assert s["historical_filings_2020_2024"] == 8
    assert s["historical_symbol_facts"] == 16


def test_metadata_is_not_fabricated():
    r = pd.read_csv("data/research/p17_2_1/p17_2_1_filing_registry.csv", dtype={"accession": str})
    assert r.filing_date.notna().sum() == 2
    assert r.acceptance_datetime.notna().sum() == 2
    assert r.form.notna().sum() == 2


def test_accession_year_not_report_period():
    r = pd.read_csv("data/research/p17_2_1/p17_2_1_filing_registry.csv", dtype={"accession": str})
    y = r[r.accession.astype(str).str.startswith("0000320193")]["accession_year"].unique().tolist()
    assert all(str(v) == "2021" for v in y)


def test_historical_tickers():
    s = json.loads(Path("data/research/p17_2_1/p17_2_1_summary.json").read_text())
    assert set(s["historical_tickers"]) == {"AAPL", "NVDA", "NEE", "NEE.PRO", "NEE.PRP", "NEE.PRQ", "NEE.PRR", "GOOGL", "GOOG"}


def test_verified_is_zero():
    s = json.loads(Path("data/research/p17_2_1/p17_2_1_summary.json").read_text())
    assert s["verified_facts"] == 0
    assert s["cik_match_rate"] < 0.05


def test_status_partial_not_ready():
    s = json.loads(Path("data/research/p17_2_1/p17_2_1_summary.json").read_text())
    assert s["status"] == "IDENTITY_OBSERVATION_PARTIAL"


def test_cat_classes_preserved():
    o = pd.read_csv("data/research/p17_2_1/p17_2_1_filing_identity_observations.csv")
    cat = o[o.ticker.isin(["CAT", "CAT35"])]
    assert set(cat.ticker) == {"CAT", "CAT35"}


def test_manifest_hashes():
    import hashlib
    m = json.loads(Path("data/research/p17_2_1/p17_2_1_manifest.json").read_text())
    for name, meta in m["outputs"].items():
        p = Path("data/research/p17_2_1") / name
        assert p.exists() and p.stat().st_size == meta["bytes"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == meta["sha256"]
