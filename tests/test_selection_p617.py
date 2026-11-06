import csv, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/universe/selection"


def rows(name):
    with (OUT / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_quote_timestamp_unknown_is_not_a_price_error():
    meta = json.loads((ROOT / "data/universe/selection_inputs/quote_metadata_p617.json").read_text(encoding="utf-8"))
    assert meta["per_row_timestamp"] is False
    assert meta["timestamp_status"] == "QUOTE_TIMESTAMP_UNKNOWN"
    audit = rows("valuation_integrity_audit.csv")
    assert all(r["quote_timestamp_status"] == "QUOTE_TIMESTAMP_UNKNOWN" for r in audit)
    assert all(r["price_comparability"] == "PRICE_NOT_COMPARABLE" for r in audit)


def test_independent_recalculation_formulas_and_flags():
    s = json.loads((OUT / "valuation_recalculation_summary_p617.json").read_text(encoding="utf-8"))
    assert s["rows"] == 50
    assert s["status_counts"] == {"VALUATION_RECALCULATED_VALID": 45, "VALUATION_RECALCULATION_MISMATCH": 5}
    assert set(s["mismatch_tickers"]) == {"BOSC", "JL", "DOX", "INMD", "GASS"}
    r = {x["ticker"]: x for x in rows("valuation_recalculation_audit_p617.csv")}
    assert r["CRMT"]["recalc_status"] == "VALUATION_RECALCULATED_VALID"
    assert "EXTREME_EY_GT_200PCT" in r["CRMT"]["extreme_flags"]
    assert abs(float(r["CRMT"]["market_cap_calc"]) - float(r["CRMT"]["price"]) * float(r["CRMT"]["sec_shares"])) < 1


def test_sec_filing_history_and_supersession():
    s = json.loads((OUT / "filing_freshness_summary_p617.json").read_text(encoding="utf-8"))
    assert s["api_errors"] == 0
    assert s["status_counts"]["SUPERSEDED_BY_NEW_PERIODIC_FILING"] == 98
    assert s["status_counts"]["6K_LATER_NOT_VERIFIED"] == 13
    assert "INMD" in s["superseded_tickers"]
    history = rows("sec_filing_history_p617.csv")
    assert history and all(r["form"] in {"10-K", "10-Q", "20-F", "40-F", "6-K"} for r in history)
    assert not any(r["form"] == "8-K" for r in history)
    audit = {r["ticker"]: r for r in rows("filing_freshness_audit_p617.csv")}
    assert audit["INMD"]["audit_status"] == "SUPERSEDED_BY_NEW_PERIODIC_FILING"
    assert audit["CAAS"]["audit_status"] == "6K_LATER_NOT_VERIFIED"


def test_liquidity_quality_has_sessions_and_flags():
    s = json.loads((ROOT / "data/universe/selection_inputs/liquidity_fetch_summary_p616.json").read_text(encoding="utf-8"))
    assert s["requested"] == 144
    assert s["ok"] == 135
    assert s["quality_rows"] == 144
    q = {r["ticker"]: r for r in rows("liquidity_quality_audit_p617.csv")}
    assert all(r["unique_sessions"] == r["sessions"] for r in q.values())
    assert all(r["duplicate_dates"] == "False" for r in q.values())
    assert q["CRMT"]["quality_status"] == "LIQUIDITY_CORPORATE_ACTION_REVIEW"
    with (ROOT / "data/universe/selection_inputs/liquidity_sessions_p617.csv").open(encoding="utf-8", newline="") as f:
        sessions = list(csv.DictReader(f))
    seen = {(r["ticker"], r["date"]) for r in sessions}
    assert len(seen) == len(sessions)


def test_final_status_does_not_promote_bad_data():
    rows_all = []
    for kind in ("value", "quality", "garp"):
        rows_all += rows(f"tradability/{kind}_tradable_candidates.csv")
    for r in rows_all:
        if r["tradability_status"] == "ELIGIBLE":
            assert r["freshness_status"] == "FUNDAMENTALS_FRESH"
            assert r["sec_filing_status"] == "FILING_HISTORY_CONFIRMED"
            assert r["liquidity_quality_status"] == "LIQUIDITY_VALID"
            assert r["valuation_status"] in ("VALUATION_VALID", "VALUATION_NOT_APPLICABLE")
        if r["sec_filing_status"] == "SUPERSEDED_BY_NEW_PERIODIC_FILING":
            assert r["tradability_status"] != "ELIGIBLE"


def test_p617_reconciliation_and_summary():
    s = json.loads((OUT / "selection_quality_report_p617.json").read_text(encoding="utf-8"))
    assert s["status"] == "CURRENT_CROSS_SECTIONAL_RESEARCH"
    assert s["pit_status"] == "PIT_BACKTEST_BLOCKED"
    assert s["valuation_recalculation"]["status_counts"]["VALUATION_RECALCULATED_VALID"] == 45
    assert s["filing_freshness"]["status_counts"]["SUPERSEDED_BY_NEW_PERIODIC_FILING"] == 98
    rec = rows("tradability_reconciliation_p617.csv")
    assert len(rec) == 150
    t = s["tradability"]
    for kind in ("value", "quality", "garp"):
        x = t[kind]
        assert x["eligible"] + x["watch"] + x["blocked"] + x["data_blocked"] == 50
