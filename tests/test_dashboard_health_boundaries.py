# -*- coding: utf-8 -*-
"""Behavior tests for Data Health status boundaries."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _render(data, meta):
    src = (ROOT / "app.js").read_text(encoding="utf-8")
    marker = "  boot();\n  renderDataHealth();"
    src = src.replace(marker, "  globalThis.__renderHealth = renderDataHealth;\n  globalThis.__setState = function(d,m){ DATA=d; META=m; };", 1)
    harness = (
        "globalThis.document={addEventListener(){},querySelectorAll(){return[]},getElementById(){return null},"
        "querySelector(sel){globalThis.__els=globalThis.__els||{};if(!globalThis.__els[sel])globalThis.__els[sel]={innerHTML:'',textContent:''};return globalThis.__els[sel];}};\n"
        "globalThis.window={addEventListener(){},IT:null};\n"
        "globalThis.fetch=()=>Promise.resolve({json:()=>Promise.resolve({})});\n"
    )
    tail = (
        "\nglobalThis.__setState(" + json.dumps(data) + "," + json.dumps(meta) + ");\n"
        "globalThis.__renderHealth();\n"
        "console.log(JSON.stringify({html: (globalThis.__els['#dataHealth']||{}).innerHTML || ''}));\n"
    )
    p = ROOT / "tests" / "_health_boundary_harness.js"
    p.write_text(harness + src + tail, encoding="utf-8")
    try:
        proc = subprocess.run(["node", str(p)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip().splitlines()[-1])["html"]
    finally:
        p.unlink(missing_ok=True)


def _data(**over):
    d = {
        "generated_at": "2026-11-03T00:00:00Z",
        "market": {"updated_at": "2026-11-03T00:00:00Z"},
        "macro_forecast": {"generated_at": "2026-11-03T00:00:00Z", "as_of": None,
                           "source": "TradingEconomics", "items": [
                               {"key": "cpi", "verification_status": "verified",
                                "source_status": "verified"}]},
        "news": {"updated_at": "2026-11-03T00:00:00Z", "source": "news"},
        "portfolio": {"snapshot_asof": "2026-11-03"},
    }
    d.update(over)
    return d


def _meta(**over):
    m = {"pending_scan_date": "2026-11-03", "market_updated_at": "2026-11-03T00:00:00Z",
         "technical_updated_at": "2026-11-03T00:00:00Z", "ai_generated_at": "2026-11-03T00:00:00Z",
         "ai_status": "ok", "quote_provider": "yfinance", "network_status": "ok"}
    m.update(over)
    return m


def test_macro_over_45_days_is_stale():
    d = _data(macro_forecast={"generated_at": "2020-01-01T00:00:00Z", "as_of": None,
                              "source": "x", "items": [{"verification_status": "verified"}]})
    html = _render(d, _meta())
    assert "STALE" in html
    assert "超过 45 天" in html


def test_macro_fallback_is_not_fresh():
    d = _data(macro_forecast={"generated_at": "2026-11-03T00:00:00Z", "as_of": None,
                              "source": "x", "items": [{"verification_status": "unverified"}]})
    html = _render(d, _meta())
    assert "FALLBACK" in html


def test_invalid_and_future_timestamps_are_missing_not_fresh():
    html = _render(_data(market={"updated_at": "not-a-date"}),
                   _meta(market_updated_at="not-a-date", technical_updated_at="2099-01-01T00:00:00Z"))
    assert "时间戳无效" in html
    assert "时间戳在未来" in html
    assert html.count("MISSING") >= 2


def test_missing_news_ai_ledger_timestamps_are_missing():
    html = _render(_data(news={}, portfolio={}), _meta(ai_generated_at=None, ai_status="pending"))
    assert "时间戳缺失" in html or "MISSING" in html
    assert html.count("MISSING") >= 2


def test_old_ai_news_ledger_are_stale():
    html = _render(_data(news={"updated_at": "2020-01-01T00:00:00Z"},
                         portfolio={"snapshot_asof": "2020-01-01"}),
                   _meta(ai_generated_at="2020-01-01T00:00:00Z", ai_status="ok"))
    assert html.count("STALE") >= 3
