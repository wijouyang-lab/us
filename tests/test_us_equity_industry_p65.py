import csv, json, zipfile
from pathlib import Path
from tools.research.enrich_us_equity_industry_p65 import load_rules, model_family, enrich

MAP = Path("data/universe/sec_sic_model_family_map_p65.csv")


def test_bank_insurance_reit_are_distinct():
    rules = load_rules(MAP)
    assert model_family("6022", "State commercial banks", rules)[0] == "BANKS"
    assert model_family("6311", "Life insurance", rules)[0] == "INSURANCE"
    assert model_family("6798", "Real estate investment trusts", rules)[0] == "REIT"


def test_bdc_requires_explicit_description_not_name():
    rules = load_rules(MAP)
    assert model_family("6726", "Business Development Company", rules)[0] == "BDC"
    assert model_family("6726", "Investment Offices, NEC", rules)[0] == "OTHER_FINANCIALS"


def test_no_sic_is_unclassified_not_guessed():
    rules = load_rules(MAP)
    assert model_family("", "", rules) == ("UNCLASSIFIED", "NO_SIC")
    assert model_family("9999", "Unknown", rules)[0] == "OTHER_SERVICES"


def make_fixture(tmp_path):
    uni = tmp_path / "universe.csv"
    fields = ["ticker","security_name","exchange","security_type","CIK","SEC_name"]
    with uni.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        w.writerows([
            {"ticker":"AAA","security_name":"A Bank","exchange":"NASDAQ","security_type":"COMMON","CIK":"0000000001","SEC_name":"A"},
            {"ticker":"BBB","security_name":"B Bank","exchange":"NYSE","security_type":"COMMON","CIK":"0000000001","SEC_name":"A"},
            {"ticker":"CCC","security_name":"C ADR","exchange":"NASDAQ","security_type":"ADR","CIK":"0000000002","SEC_name":"C"},
            {"ticker":"NOCIK","security_name":"No CIK","exchange":"NYSE","security_type":"COMMON","CIK":"","SEC_name":""},
            {"ticker":"UUU","security_name":"U REIT","exchange":"NYSE","security_type":"UNCLASSIFIED","CIK":"0000000003","SEC_name":"U"},
        ])
    docs = {
        "0000000001": {"cik":"1","entityName":"A Bank","sic":"6022","sicDescription":"State commercial banks","entityType":"operating","stateOfIncorporation":"DE","addresses":{"business":{"country":"US"}}},
        "0000000002": {"cik":"2","entityName":"C Insurance","sic":"6311","sicDescription":"Life insurance","entityType":"operating","stateOfIncorporation":"NY","addresses":{"business":{"country":"US"}}},
        "0000000003": {"cik":"3","entityName":"U REIT","sic":"6798","sicDescription":"Real estate investment trusts","entityType":"operating","stateOfIncorporation":"MD","addresses":{"business":{"country":"US"}}},
    }
    z = tmp_path / "submissions.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for cik, doc in docs.items(): zf.writestr(f"CIK{cik}.json", json.dumps(doc))
    sp = tmp_path / "sp.csv"
    with sp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Ticker","Sector","Date_Added"]); w.writeheader()
        w.writerows([{"Ticker":"AAA","Sector":"Financials","Date_Added":""},
                     {"Ticker":"BBB","Sector":"Financials","Date_Added":""},
                     {"Ticker":"CCC","Sector":"Information Technology","Date_Added":""}])
    return uni, z, sp


def test_multiple_tickers_share_sic_and_adr_keeps_security_row(tmp_path):
    uni, z, sp = make_fixture(tmp_path)
    out = tmp_path / "sic.csv"; cov = tmp_path / "cov.json"
    d = enrich(z, out, cov, MAP, current=uni, sp_path=sp, retrieved_at="2026-11-05T00:00:00Z")
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 5
    assert {r["sic"] for r in rows if r["ticker"] in ("AAA","BBB")} == {"6022"}
    assert next(r for r in rows if r["ticker"] == "CCC")["sic"] == "6311"
    assert next(r for r in rows if r["ticker"] == "CCC")["model_family"] == "INSURANCE"
    assert next(r for r in rows if r["ticker"] == "NOCIK")["model_family"] == "UNCLASSIFIED"
    assert next(r for r in rows if r["ticker"] == "NOCIK")["mapping_rule"] == "NO_CIK"
    assert d["counts"]["target_with_sic"] == 3
    assert d["counts"]["target_missing_sic"] == 1
    assert d["counts"]["target_unique_ciks"] == 2 or d["counts"]["target_unique_ciks"] >= 2


def test_sp500_inconsistency_preserves_both_sources(tmp_path):
    uni, z, sp = make_fixture(tmp_path)
    out = tmp_path / "sic.csv"; cov = tmp_path / "cov.json"
    d = enrich(z, out, cov, MAP, current=uni, sp_path=sp)
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert all(r["sp500_sector"] for r in rows if r["ticker"] in ("AAA","CCC"))
    assert d["sp500_consistency"].get("INCONSISTENT", 0) >= 1
    assert "sp500_inconsistent_examples" in d
