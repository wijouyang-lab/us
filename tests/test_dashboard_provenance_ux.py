# -*- coding: utf-8 -*-
"""Regression tests for dashboard provenance / units / simulated-account labels."""
from pathlib import Path

from dashboard_export import _build_trade_stats

ROOT = Path(__file__).resolve().parents[1]


def _app():
    return (ROOT / "app.js").read_text(encoding="utf-8")


def test_scan_date_never_falls_back_to_generated_at():
    js = _app()
    assert "pending_scan_date || (DATA && DATA.generated_at" not in js
    assert "扫描时间未知/本次未提供" in js
    assert "Dashboard 生成" in js


def test_regime_missing_is_not_filled_from_market_vix():
    js = _app()
    assert "市场状态不可用（来源缺失）" in js
    assert "行情报价，与市场状态不同源" in js
    assert "市场状态不可用（来源缺失）" in js


def test_macro_units_and_unverified_period_labels():
    js = _app()
    assert "单位未核验" in js
    assert "期间/发布时间未核验" in js
    assert "FALLBACK" in js
    # no unconditional pp suffix in the forecast formatter
    assert "+ fmt(d, 2) + 'pp'" not in js
    assert "metricDelta(d, unit)" in js


def test_simulated_account_and_target_labels():
    js = _app()
    assert "真实行情 + 模拟组合" in js
    assert "SIMULATED / Paper" in js
    assert "待执行目标（未成交）" in js
    assert "未扣佣金" in js
    assert "本页不含任何模拟数据" not in js


def test_data_health_has_independent_status(tmp_path=None):
    js = _app()
    for token in ("FRESH", "STALE", "FALLBACK", "MISSING", "阈值"):
        assert token in js
    assert "renderDataHealth" in js
    assert "dataHealth" in (ROOT / "index.html").read_text(encoding="utf-8")


def test_avg_holding_uses_closed_buy_sell_pairs_not_open_positions():
    rows = [
        {"Txn_ID": "A|1|BUY", "Date": "2026-01-01", "Action": "BUY", "Unit_ID": "U1",
         "Realized_PnL": "0", "Amount": "1000"},
        {"Txn_ID": "A|2|SELL", "Date": "2026-01-04", "Action": "SELL", "Unit_ID": "U1",
         "Realized_PnL": "10", "Amount": "1010"},
        {"Txn_ID": "B|1|BUY", "Date": "2026-01-02", "Action": "BUY", "Unit_ID": "U2",
         "Realized_PnL": "0", "Amount": "1000"},
        {"Txn_ID": "B|2|SELL", "Date": "2026-01-08", "Action": "SELL", "Unit_ID": "U2",
         "Realized_PnL": "-20", "Amount": "980"},
    ]
    stats = _build_trade_stats(rows, [])
    assert stats["avg_holding_days"] == 4.5


def test_data_health_aggregates_macro_items_and_missing_timestamps():
    js = _app()
    assert "badItems = items.filter" in js
    assert "verification_status" in js
    assert "FALLBACK/UNVERIFIED" in js
    assert "时间戳缺失" in js
    assert "时间戳缺失" in js


def test_market_summary_is_deduplicated_from_full_list():
    js = _app()
    assert "TOP_KEYS = ['S&P 500', 'US10Y']" in js
    assert "dup[nmKey('VIX')] = 1" in js


def test_research_details_collapsed_and_no_deployable_alpha_claim():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert html.count("research-fold") >= 2
    assert "研究详情 · 决策输入" in html
    assert "研究详情 · 量化阶段" in html
    # existing research state must still be surfaced, not promoted
    js = _app()
    assert "NOT_READY" in js or "NOT_ENOUGH_DATA" in js or "DEGRADED" in js
