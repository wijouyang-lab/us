import csv, gzip, json
from pathlib import Path
from tools.research.score_quality_v1_p66 import (
    calc_quality_metrics, average_balance, select_annual, build_issuer_financials,
)

OUT = Path("data/universe")


def test_roe_roa_and_average_balances():
    current = {"NetIncome": 100, "TotalAssets": 1000, "StockholdersEquity": 500,
               "TotalLiabilities": 400, "OperatingCashFlow": 150, "Revenue": 800,
               "OperatingIncome": 80}
    prior = {"TotalAssets": 800, "StockholdersEquity": 400}
    m = calc_quality_metrics(current, prior)
    assert round(m["roe"], 6) == round(100 / 450, 6)
    assert round(m["roa"], 6) == round(100 / 900, 6)
    assert round(m["cfo_to_avg_assets"], 6) == round(150 / 900, 6)
    assert m["liabilities_to_assets"] == 0.4
    assert round(m["operating_margin"], 6) == 0.1


def test_missing_prior_balance_blocks_average_metrics():
    current = {"NetIncome": 100, "TotalAssets": 1000, "StockholdersEquity": 500,
               "TotalLiabilities": 400, "OperatingCashFlow": 150, "Revenue": 800, "OperatingIncome": 80}
    m = calc_quality_metrics(current, {})
    assert m["roe"] is None and m["roa"] is None and m["cfo_to_avg_assets"] is None
    assert average_balance(1000, None) is None


def test_negative_equity_does_not_produce_roe():
    current = {"NetIncome": 10, "TotalAssets": 1000, "StockholdersEquity": 500,
               "TotalLiabilities": 700, "OperatingCashFlow": 20, "Revenue": 100, "OperatingIncome": 10}
    prior = {"TotalAssets": 900, "StockholdersEquity": -100}
    m = calc_quality_metrics(current, prior)
    assert m["avg_equity"] == 200
    assert m["roe"] == 0.05
    prior2 = {"TotalAssets": 900, "StockholdersEquity": -600}
    m2 = calc_quality_metrics(current, prior2)
    assert m2["avg_equity"] == -50
    assert m2["roe"] is None


def write_panel(path):
    fields = ["cik","metric","unit","period_type","value","start","end","filed","accn","form",
              "taxonomy","tag","pit_available_date"]
    rows = [
        {"cik":"0000000001","metric":"NetIncome","unit":"USD","period_type":"ANNUAL","value":"100",
         "start":"2025-01-01","end":"2025-12-31","filed":"2026-02-15","accn":"A1","form":"10-K",
         "taxonomy":"us-gaap","tag":"NetIncomeLoss","pit_available_date":"2026-02-17"},
        {"cik":"0000000001","metric":"NetIncome","unit":"USD","period_type":"YTD","value":"999",
         "start":"2026-01-01","end":"2026-06-30","filed":"2026-08-01","accn":"A2","form":"10-Q",
         "taxonomy":"us-gaap","tag":"NetIncomeLoss","pit_available_date":"2026-08-03"},
        {"cik":"0000000001","metric":"OperatingCashFlow","unit":"USD","period_type":"ANNUAL","value":"50",
         "start":"2025-01-01","end":"2025-12-31","filed":"2026-02-15","accn":"A3","form":"10-K",
         "taxonomy":"us-gaap","tag":"NetCashProvidedByUsedInOperatingActivities","pit_available_date":"2026-02-17"},
        {"cik":"0000000001","metric":"TotalAssets","unit":"USD","period_type":"INSTANT","value":"1000",
         "start":"","end":"2025-12-31","filed":"2026-02-15","accn":"A4","form":"10-K",
         "taxonomy":"us-gaap","tag":"Assets","pit_available_date":"2026-02-17"},
        {"cik":"0000000001","metric":"TotalAssets","unit":"USD","period_type":"INSTANT","value":"800",
         "start":"","end":"2024-12-31","filed":"2025-02-15","accn":"A5","form":"10-K",
         "taxonomy":"us-gaap","tag":"Assets","pit_available_date":"2025-02-18"},
        {"cik":"0000000001","metric":"StockholdersEquity","unit":"USD","period_type":"INSTANT","value":"500",
         "start":"","end":"2025-12-31","filed":"2026-02-15","accn":"A6","form":"10-K",
         "taxonomy":"us-gaap","tag":"StockholdersEquity","pit_available_date":"2026-02-17"},
        {"cik":"0000000001","metric":"StockholdersEquity","unit":"USD","period_type":"INSTANT","value":"450",
         "start":"","end":"2024-12-31","filed":"2025-02-15","accn":"A7","form":"10-K",
         "taxonomy":"us-gaap","tag":"StockholdersEquity","pit_available_date":"2025-02-18"},
        {"cik":"0000000001","metric":"TotalLiabilities","unit":"USD","period_type":"INSTANT","value":"500",
         "start":"","end":"2025-12-31","filed":"2026-02-15","accn":"A8","form":"10-K",
         "taxonomy":"us-gaap","tag":"Liabilities","pit_available_date":"2026-02-17"},
        {"cik":"0000000001","metric":"Revenue","unit":"USD","period_type":"ANNUAL","value":"800",
         "start":"2025-01-01","end":"2025-12-31","filed":"2026-02-15","accn":"A9","form":"10-K",
         "taxonomy":"us-gaap","tag":"Revenues","pit_available_date":"2026-02-17"},
        {"cik":"0000000001","metric":"OperatingIncome","unit":"USD","period_type":"ANNUAL","value":"80",
         "start":"2025-01-01","end":"2025-12-31","filed":"2026-02-15","accn":"A10","form":"10-K",
         "taxonomy":"us-gaap","tag":"OperatingIncomeLoss","pit_available_date":"2026-02-17"},
        {"cik":"0000000001","metric":"NetIncome","unit":"USD","period_type":"ANNUAL","value":"9999",
         "start":"2026-01-01","end":"2026-12-31","filed":"2026-12-15","accn":"FUTURE","form":"10-K",
         "taxonomy":"us-gaap","tag":"NetIncomeLoss","pit_available_date":"2026-12-17"},
    ]
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def test_ytd_not_used_and_pit_cutoff(tmp_path):
    p = tmp_path / "panel.csv.gz"; write_panel(p)
    annual, instant, _ = select_annual(p)
    out = build_issuer_financials(annual, instant)
    f = out["0000000001"]
    assert f["metrics"]["roe"] is not None
    assert f["metrics"]["roa"] is not None
    assert f["period"] == "2025-12-31"
    # YTD 999 did not enter NetIncome; 100 is used
    assert f["current"]["NetIncome"]["value"] == 100
    assert f["accn"] != "FUTURE"


def test_ifrs_and_gaap_are_separate_groups():
    d = json.load(open(OUT / "quality_v1_scoring_audit_p66.json", encoding="utf-8"))
    groups = d["verification"]["group_verification"]
    assert "TECHNOLOGY|US_GAAP" in groups
    assert "TECHNOLOGY|IFRS" in groups
    assert "MATERIALS|IFRS" in groups


def test_multi_ticker_same_cik_scores_identical():
    rows = [r for r in csv.DictReader(open(OUT / "quality_v1_scores_p66.csv", encoding="utf-8"))
            if r["scoring_status"] == "QUALITY_V1_SCORED"]
    by = {}
    for r in rows: by.setdefault(r["cik"], []).append(r)
    multi = next(v for v in by.values() if len(v) > 1)
    scores = {x["quality_v1_score"] for x in multi}
    assert len(scores) == 1


def test_insufficient_peer_group_has_no_score():
    d = json.load(open(OUT / "quality_v1_scoring_audit_p66.json", encoding="utf-8"))
    assert d["verification"]["status_counts"]["INSUFFICIENT_PEER_GROUP"] == 92
    rows = [r for r in csv.DictReader(open(OUT / "quality_v1_scores_p66.csv", encoding="utf-8"))
            if r["scoring_status"] == "INSUFFICIENT_PEER_GROUP"]
    assert rows and all(not r["quality_v1_score"] for r in rows)


def test_actual_candidate_and_score_counts():
    d = json.load(open(OUT / "quality_v1_scoring_audit_p66.json", encoding="utf-8"))
    assert d["candidate_securities"] == 3342
    assert d["verification"]["scored_securities"] == 2335
    assert d["verification"]["all_checks_pass"] is True
    assert d["score_ready"] is False and d["backtest_ready"] is False
