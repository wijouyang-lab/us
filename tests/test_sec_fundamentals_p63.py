import csv, gzip, json, subprocess, sys, zipfile
from pathlib import Path
from tools.research.normalize_sec_companyfacts_p63 import classify_period, next_weekday


def make_fixture(tmp_path):
    uni = tmp_path / "universe.csv"
    fields = ["ticker", "security_name", "exchange", "security_type", "CIK", "SEC_name"]
    with uni.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        w.writerows([
            {"ticker": "AAA", "security_name": "A common", "exchange": "NASDAQ", "security_type": "COMMON", "CIK": "0000000001", "SEC_name": "A"},
            {"ticker": "BBB", "security_name": "B common", "exchange": "NYSE", "security_type": "COMMON", "CIK": "0000000001", "SEC_name": "A"},
            {"ticker": "CCC", "security_name": "C ADR", "exchange": "NASDAQ", "security_type": "ADR", "CIK": "0000000002", "SEC_name": "C"},
            {"ticker": "UUU", "security_name": "U unclassified", "exchange": "NYSE", "security_type": "UNCLASSIFIED", "CIK": "0000000003", "SEC_name": "U"},
        ])
    cik1 = {"entityName": "A Corp", "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
                {"val": 100, "start": "2025-01-01", "end": "2025-12-31", "filed": "2026-02-15", "accn": "A1", "form": "10-K", "fy": 2025, "fp": "FY"},
                {"val": 100, "start": "2025-01-01", "end": "2025-12-31", "filed": "2026-03-15", "accn": "A2", "form": "10-K", "fy": 2025, "fp": "FY"},
            ]}},
            "NetIncomeLoss": {"units": {"USD": [
                {"val": 50, "start": "2026-01-01", "end": "2026-06-30", "filed": "2026-08-01", "accn": "A3", "form": "10-Q", "fy": 2026, "fp": "Q2"},
            ]}},
            "Assets": {"units": {"USD": [{"val": 500, "end": "2026-06-30", "filed": "2026-08-01", "accn": "A4", "form": "10-Q"}]}},
        },
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [{"val": 10, "end": "2026-06-30", "filed": "2026-08-01", "accn": "A5", "form": "10-Q"}]}}},
    }}
    cik2 = {"entityName": "C Foreign", "facts": {"ifrs-full": {"Revenue": {"units": {"USD": [{"val": 200, "start": "2025-01-01", "end": "2025-12-31", "filed": "2026-03-01", "accn": "C1", "form": "20-F"}]}}}}}
    cik3 = {"entityName": "U Corp", "facts": {"us-gaap": {"Revenues": {"units": {"USD": [{"val": 1, "start": "2025-01-01", "end": "2025-12-31", "filed": "2026-02-01", "accn": "U1", "form": "10-K"}]}}}}}
    z = tmp_path / "facts.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for cik, doc in (("0000000001", cik1), ("0000000002", cik2), ("0000000003", cik3)):
            zf.writestr(f"CIK{cik}.json", json.dumps(doc))
    return uni, z


def test_period_classification_ytd_not_quarter():
    assert classify_period("2026-01-01", "2026-06-30", "10-Q") == "YTD"
    assert classify_period("2026-01-01", "2026-03-31", "10-Q") == "QUARTER"
    assert classify_period("2025-01-01", "2025-12-31", "10-K") == "ANNUAL"
    assert classify_period("", "2026-06-30", "10-Q") == "INSTANT"


def test_pit_next_weekday():
    assert next_weekday("2026-08-01") == "2026-08-03"
    assert next_weekday("2026-07-31") == "2026-08-03"


def test_normalize_shared_cik_and_taxonomy(tmp_path):
    uni, z = make_fixture(tmp_path)
    out = tmp_path / "panel.csv.gz"; meta = tmp_path / "meta.json"
    r = subprocess.run([sys.executable, "-m", "tools.research.normalize_sec_companyfacts_p63",
                        "--zip", str(z), "--universe", str(uni), "--out", str(out), "--meta", str(meta)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rows = list(csv.DictReader(gzip.open(out, "rt", encoding="utf-8")))
    assert rows
    assert all(r["cik"] == "0000000001" or r["cik"] in ("0000000002", "0000000003") for r in rows)
    cik1 = [r for r in rows if r["cik"] == "0000000001"]
    assert {r["tickers"] for r in cik1} == {"AAA|BBB"}
    rev = [r for r in cik1 if r["metric"] == "Revenue"]
    assert len(rev) == 2 and {r["accn"] for r in rev} == {"A1", "A2"}  # restatement retained
    assert all(r["filed"] for r in rows)
    net = next(r for r in cik1 if r["metric"] == "NetIncome")
    assert net["period_type"] == "YTD"
    assert next_weekday("2026-08-01") == "2026-08-03"
    assert any(r["taxonomy"] == "ifrs-full" for r in rows)
    m = json.loads(meta.read_text())
    assert m["counts"]["unique_ciks"] == 2
    assert m["counts"]["parsed_ciks"] == 3


def test_audit_coverage_outputs(tmp_path):
    uni, z = make_fixture(tmp_path); out = tmp_path / "panel.csv.gz"; meta = tmp_path / "meta.json"
    subprocess.run([sys.executable, "-m", "tools.research.normalize_sec_companyfacts_p63",
                    "--zip", str(z), "--universe", str(uni), "--out", str(out), "--meta", str(meta)], check=True)
    csvout = tmp_path / "cov.csv"; jsonout = tmp_path / "audit.json"
    r = subprocess.run([sys.executable, "-m", "tools.research.audit_sec_fundamentals_p63",
                        "--universe", str(uni), "--panel", str(out), "--meta", str(meta),
                        "--out-csv", str(csvout), "--out-json", str(jsonout)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    d = json.loads(jsonout.read_text())
    assert d["counts"]["target_records"] == 3
    assert d["counts"]["target_unique_ciks"] == 2
    assert d["by_type"]["ADR"]["ifrs"] == 1
    assert d["by_type"]["UNCLASSIFIED"]["records"] == 1
    assert d["metrics"]["Revenue"]["any"] >= 1
