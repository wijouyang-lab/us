import csv
from pathlib import Path

from tools.research.p10.validate_provider_evaluation import main, validate

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research"


def test_provider_comparison_has_official_evidence_and_unknowns():
    rows = list(csv.DictReader((DATA / "p10_provider_comparison.csv").open(encoding="utf-8")))
    assert len(rows) >= 10
    providers = {r["provider"] for r in rows}
    assert {"Sharadar", "Norgate Data", "EODHD", "CRSP via WRDS"} <= providers
    for r in rows:
        assert r["official_url"].startswith("https://")
        assert r["pricing_url"].startswith("https://")
        assert r["price_verified"] in {"YES", "NO"}
        if r["price_verified"] == "NO":
            assert "UNKNOWN" in r["price_display"] or r["price_display"].startswith("Institutional")


def test_sample_validation_has_30_tickers_and_no_unproven_pass():
    rows = list(csv.DictReader((DATA / "p10_sample_validation.csv").open(encoding="utf-8")))
    assert len({r["ticker"] for r in rows}) == 30
    assert {r["provider"] for r in rows} == {"Sharadar", "Norgate", "EODHD"}
    assert not [r for r in rows if r["status"] == "PASS"]
    assert all(r["status"] in {"PARTIAL", "NOT_RUN", "NOT_VERIFIED"} for r in rows)


def test_validator_passes():
    assert validate() == []
    assert main() == 0


def test_no_raw_vendor_files_committed():
    raw = list(DATA.glob("p10_*"))
    assert all(p.suffix in {".csv"} for p in raw)
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.sqlite"))
