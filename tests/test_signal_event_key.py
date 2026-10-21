# -*- coding: utf-8 -*-
"""Scheme C: signal events are (Date, Ticker, Tag); positions remain one per ticker."""

import ast
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from test_pending_supplement import (  # noqa: E402
    TARGET_DATE,
    _load_supplement,
    _write_pending,
)

from trade_history_quality import deduplicate_trade_history, review_event_key  # noqa: E402
import portfolio_50000 as pf  # noqa: E402


REPO = Path(__file__).resolve().parents[1]


def _run(tmp_path, monkeypatch, rows, name="us_stocks_pending_20261020.csv"):
    fn, ns = _load_supplement(tmp_path)
    for row in rows:
        ns["OHLC"][(row["Ticker"], TARGET_DATE)] = {"open": "100", "close": "101"}
    _write_pending(tmp_path, rows, name=name)
    monkeypatch.chdir(tmp_path)
    return fn()


def _trade(tmp_path):
    path = tmp_path / "trade_history.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _row(tag, ticker="AAA"):
    return {
        "Date": TARGET_DATE, "Ticker": ticker, "Tag": tag, "Name": ticker + " Inc",
        "Scan_Ref_Price": "100", "Stop_Loss": "$95",
    }


def _portfolio(tmp_path):
    recs = pf.load_recommendations(tmp_path)
    meta = {
        "start_date": TARGET_DATE, "initial_capital": "50000",
        "unit_dollars": "5000", "exposure_target": "0.8",
        "portfolio_id": pf.PORTFOLIO_ID,
    }
    positions, txns = [], []
    pf.process_buys(positions, txns, recs, meta, TARGET_DATE, offline=True)
    return positions, txns


def _load_review_function(name):
    tree = ast.parse((REPO / "review.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {
        "pd": pd,
        "os": os,
        "normalize_date": lambda value: pd.to_datetime(value, errors="coerce"),
        "clean_text": lambda value, default="": str(value if value not in (None, "") else default).strip(),
    }
    exec(compile(module, "<review-fn>", "exec"), ns)
    return ns[name]


def test_same_file_core_and_observation_both_kept_but_one_position(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, [_row("Core_Dragon"), _row("Observation")])
    trade = _trade(tmp_path)
    assert len(trade) == 2
    assert trade["Tag"].tolist() == ["Core_Dragon", "Observation"]
    assert trade["Ticker"].nunique() == 1
    positions, txns = _portfolio(tmp_path)
    assert len(positions) == 1
    assert len(txns) == 1


def test_two_pending_files_keep_both_tags(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, [_row("Core_Dragon")])
    assert len(_trade(tmp_path)) == 1
    # A new same-date Pending arrives later; the earlier file is now .processed.
    _run(tmp_path, monkeypatch, [_row("Observation")])
    trade = _trade(tmp_path)
    assert len(trade) == 2
    assert set(trade["Tag"]) == {"Core_Dragon", "Observation"}


def test_core_then_later_observation_is_not_skipped(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, [_row("Core_Dragon")])
    assert set(_trade(tmp_path)["Tag"]) == {"Core_Dragon"}
    _run(tmp_path, monkeypatch, [_row("Observation")])
    assert set(_trade(tmp_path)["Tag"]) == {"Core_Dragon", "Observation"}


def test_observation_then_later_core_is_not_skipped(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, [_row("Observation")])
    assert set(_trade(tmp_path)["Tag"]) == {"Observation"}
    _run(tmp_path, monkeypatch, [_row("Core_Dragon")])
    assert set(_trade(tmp_path)["Tag"]) == {"Observation", "Core_Dragon"}


def test_same_event_rerun_is_idempotent(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, [_row("Core_Dragon")])
    _run(tmp_path, monkeypatch, [_row("Core_Dragon")])
    trade = _trade(tmp_path)
    assert len(trade) == 1
    assert trade.iloc[0]["Tag"] == "Core_Dragon"


def test_duplicate_rows_in_one_file_are_deduped(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, [_row("Core_Dragon"), _row("Core_Dragon")])
    trade = _trade(tmp_path)
    assert len(trade) == 1
    assert trade.iloc[0]["Tag"] == "Core_Dragon"


def test_portfolio_persisted_rerun_has_no_duplicate_buy(tmp_path, monkeypatch):
    """Run the production Portfolio entry point twice against the same files."""
    _run(tmp_path, monkeypatch, [_row("Core_Dragon"), _row("Observation")])
    monkeypatch.setattr(pf, "us_today_str", lambda: TARGET_DATE)

    pf.run(tmp_path, offline=True)
    pos1 = pd.read_csv(tmp_path / pf.POSITIONS_FILE, dtype=str, keep_default_na=False)
    tx1 = pd.read_csv(tmp_path / pf.TRANSACTIONS_FILE, dtype=str, keep_default_na=False)
    hist1 = pd.read_csv(tmp_path / pf.HISTORY_FILE, dtype=str, keep_default_na=False)

    buys1 = tx1[tx1["Action"].astype(str).str.upper() == "BUY"]
    assert len(pos1) == 1 and pos1.iloc[0]["Status"] == "OPEN"
    assert len(buys1) == 1 and len(tx1) == 1
    assert len(hist1) == 1
    txn_id = buys1.iloc[0]["Txn_ID"]
    rec_id = buys1.iloc[0]["Recommendation_ID"]
    assert pos1.iloc[0]["Ticker"] == "AAA"
    assert pos1.iloc[0]["Recommendation_ID"] == rec_id

    # Keep all persisted files; run the same production flow again.
    pf.run(tmp_path, offline=True)
    pos2 = pd.read_csv(tmp_path / pf.POSITIONS_FILE, dtype=str, keep_default_na=False)
    tx2 = pd.read_csv(tmp_path / pf.TRANSACTIONS_FILE, dtype=str, keep_default_na=False)
    hist2 = pd.read_csv(tmp_path / pf.HISTORY_FILE, dtype=str, keep_default_na=False)

    buys2 = tx2[tx2["Action"].astype(str).str.upper() == "BUY"]
    assert len(pos2) == 1 and pos2.iloc[0]["Status"] == "OPEN"
    assert len(buys2) == 1 and len(tx2) == 1
    assert len(hist2) == 1
    assert buys2.iloc[0]["Txn_ID"] == txn_id
    assert buys2.iloc[0]["Recommendation_ID"] == rec_id
    assert pos2.iloc[0]["Recommendation_ID"] == rec_id
    assert pos2.iloc[0]["Ticker"] == "AAA"


def test_tag_whitespace_case_and_missing_are_stable():
    find = _load_review_function("find_existing_record")
    df = pd.DataFrame([
        {"Date": pd.Timestamp("2026-10-20"), "Ticker": "AAA", "Tag": "Observation"},
        {"Date": pd.Timestamp("2026-10-20"), "Ticker": "AAA", "Tag": ""},
    ])
    # Whitespace is trimmed; case is preserved and is not merged.
    assert find(df, "2026-10-20", "AAA", " Observation ") is True
    assert find(df, "2026-10-20", "AAA", "observation") is False
    assert find(df, "2026-10-20", "AAA", "") is True
    # Missing Tag is its own empty event, not a wildcard.
    legacy = pd.DataFrame([{"Date": pd.Timestamp("2026-10-20"), "Ticker": "AAA"}])
    assert find(legacy, "2026-10-20", "AAA", "") is True
    assert find(legacy, "2026-10-20", "AAA", "Core_Dragon") is False


def test_review_event_key_distinguishes_tags():
    event_key = _load_review_function("review_event_key")
    a = event_key({"Rec_Date": "2026-10-20", "Ticker": "AAA", "Tag": "Core_Dragon"})
    b = event_key({"Rec_Date": "2026-10-20", "Ticker": "AAA", "Tag": "Observation"})
    assert a != b
    assert a[0] == b[0] and a[1] == b[1]


def test_deduplicate_trade_history_keeps_different_tags():
    df = pd.DataFrame([
        {"Date": "2026-10-20", "Ticker": "AAA", "Tag": "Core_Dragon", "Stop_Loss": "95"},
        {"Date": "2026-10-20", "Ticker": "AAA", "Tag": "Observation", "Stop_Loss": "95"},
    ])
    out = deduplicate_trade_history(df)
    assert len(out) == 2
    assert set(out["Tag"]) == {"Core_Dragon", "Observation"}


def test_legacy_missing_tag_loads_and_dedupes_without_keyerror():
    df = pd.DataFrame([
        {"Date": "2026-10-20", "Ticker": "AAA", "Stop_Loss": "95"},
        {"Date": "2026-10-20", "Ticker": "AAA", "Stop_Loss": "95"},
    ])
    out = deduplicate_trade_history(df)
    assert len(out) == 1
    assert review_event_key(out).tolist() == ["AAA|2026-10-20|"]


def _load_review_append(tmp_path):
    tree = ast.parse((REPO / "review.py").read_text(encoding="utf-8"))
    names = {"review_event_key", "append_review_rows"}
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    module = ast.Module(body=funcs, type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {
        "pd": pd,
        "os": os,
        "REVIEW_HISTORY": str(tmp_path / "review_history.csv"),
        "REVIEW_COLUMNS": [
            "Review_Date", "Ticker", "Name", "Tag", "Rec_Date", "Rec_Price", "Cur_Price",
            "Status", "Price_5D", "PnL_5D", "Price_10D", "PnL_10D", "Price_20D",
            "PnL_20D", "Review_Stage",
        ],
        "MILESTONE_FIELDS": [],
        "clean_text": lambda value, default="": str(value if value not in (None, "") else default).strip(),
        "_milestone_stage": lambda *args, **kwargs: "OPEN",
    }
    exec(compile(module, "<review-append>", "exec"), ns)
    return ns["append_review_rows"]


def test_review_history_keeps_tags_separate_and_is_idempotent(tmp_path):
    append = _load_review_append(tmp_path)

    def row(tag, px):
        return {
            "Review_Date": "2026-10-21", "Ticker": "AAA", "Name": "AAA Inc", "Tag": tag,
            "Rec_Date": "2026-10-20", "Rec_Price": "100", "Cur_Price": "101",
            "Status": "Active", "Price_5D": px, "PnL_5D": "", "Price_10D": "",
            "PnL_10D": "", "Price_20D": "", "PnL_20D": "", "Review_Stage": "OPEN",
        }

    append([row("Core_Dragon", "105"), row("Observation", "106")])
    out = pd.read_csv(tmp_path / "review_history.csv", dtype=str, keep_default_na=False)
    assert len(out) == 2
    assert set(out["Tag"]) == {"Core_Dragon", "Observation"}
    assert out.set_index("Tag").loc["Core_Dragon", "Price_5D"] == "105"
    assert out.set_index("Tag").loc["Observation", "Price_5D"] == "106"

    append([row("Core_Dragon", "105"), row("Observation", "106")])
    out2 = pd.read_csv(tmp_path / "review_history.csv", dtype=str, keep_default_na=False)
    assert len(out2) == 2


def test_status_update_only_targets_matching_tag(tmp_path):
    path = tmp_path / "trade_history.csv"
    pd.DataFrame([
        {"Date": "2026-10-20", "Ticker": "AAA", "Tag": "Core_Dragon", "Status": "Active"},
        {"Date": "2026-10-20", "Ticker": "AAA", "Tag": "Observation", "Status": "Active"},
    ]).to_csv(path, index=False)
    fn = _load_review_function("update_trade_history_status")
    ns = fn.__globals__
    ns.update({"TRADE_HISTORY": str(path), "REVIEW_SESSION_DATE": "2026-10-21"})
    fn("AAA", "2026-10-20", "Stop_Loss_Hit", "90", tag="Core_Dragon")
    out = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert out.loc[out["Tag"] == "Core_Dragon", "Status"].tolist() == ["Stop_Loss_Hit"]
    assert out.loc[out["Tag"] == "Observation", "Status"].tolist() == ["Active"]


def test_risk_and_trailing_stop_only_target_matching_tag(tmp_path):
    path = tmp_path / "trade_history.csv"
    pd.DataFrame([
        {"Date": "2026-10-20", "Ticker": "AAA", "Tag": "Core_Dragon",
         "Status": "Active", "Stop_Loss": "95", "Trail_Stop": "95"},
        {"Date": "2026-10-20", "Ticker": "AAA", "Tag": "Observation",
         "Status": "Active", "Stop_Loss": "95", "Trail_Stop": "95"},
    ]).to_csv(path, index=False)

    trailing = _load_review_function("update_trade_history_trailing_stop")
    trailing.__globals__["TRADE_HISTORY"] = str(path)
    trailing("AAA", "2026-10-20", "97", {"ma20": "100", "ma50": "99", "atr_pct": "2"},
             tag="Core_Dragon")

    risk = _load_review_function("write_review_risk_linkage_us")
    risk.__globals__.update({
        "TRADE_HISTORY": str(path), "REVIEW_SESSION_DATE": "2026-10-21",
        "safe_float": lambda value, default=None: float(value) if value not in (None, "") else default,
    })
    risk("AAA", "2026-10-20", "STOP_NEAR", "97", "100", "near", tag="Core_Dragon")

    out = pd.read_csv(path, dtype=str, keep_default_na=False)
    core = out[out["Tag"] == "Core_Dragon"].iloc[0]
    obs = out[out["Tag"] == "Observation"].iloc[0]
    assert core["Trail_Stop"] == "97"
    assert core["Review_Risk_Status"] == "STOP_NEAR"
    assert obs["Trail_Stop"] == "95"
    assert obs["Review_Risk_Status"] == ""
