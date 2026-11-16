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
    assert all(p.suffix in {".csv", ".json"} for p in raw)
    assert not list(DATA.glob("*.parquet"))
    assert not list(DATA.glob("*.sqlite"))


def test_sharadar_tiers_are_not_mislabeled_as_full_history():
    rows = list(csv.DictReader((DATA / "p10_provider_comparison.csv").open(encoding="utf-8")))
    by_key = {(r["provider"], r["product"]): r for r in rows}
    assert by_key[("Sharadar", "Prices 5 Years")]["history_tier"] == "5 years"
    assert by_key[("Sharadar", "Prices 10 Years")]["history_tier"] == "10 years"
    assert by_key[("Sharadar", "Prices Full History")]["history_tier"] == "full history"
    assert by_key[("Sharadar", "Prices Full History")]["price_monthly_usd"] == "39.00"
    assert by_key[("Sharadar", "Bundle Full History")]["price_monthly_usd"] == "69.00"
    assert by_key[("Sharadar", "Bundle 5 Years")]["price_monthly_usd"] == "29.00"
    assert by_key[("Sharadar", "Bundle 5 Years")]["history_tier"] != "full history"


def test_eodhd_historian_price_is_usd_and_has_retention_notes():
    rows = list(csv.DictReader((DATA / "p10_provider_comparison.csv").open(encoding="utf-8")))
    r = next(x for x in rows if x["provider"] == "EODHD" and x["product"] == "Historian")
    assert r["price_monthly_usd"] == "19.99"
    assert r["annual_price_usd"] == "199.00"
    assert "EUR" not in r["price_display"]
    assert "retain" in r["license_after_cancel"].lower()
    assert r["delisted_support"].startswith("YES")


def test_free_sample_results_are_real_and_reproducible():
    import json
    d = json.loads((DATA / "p10_free_sample_results.json").read_text(encoding="utf-8"))
    for t in ("AAPL", "MSFT", "TSLA"):
        x = d[f"eodhd_demo_{t}"]
        assert x["status"] == 200
        assert x["rows"] > 1000
        assert x["first"] <= "1990-01-03" if t != "TSLA" else x["first"] == "2010-06-29"
        assert x["repeat_sha256_match"] is True
    assert d["eodhd_demo_AAPL"]["splits_rows"] >= 4
    assert d["sharadar_sample_AAPL"]["rows"] > 1000
