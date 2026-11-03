# -*- coding: utf-8 -*-
"""Behavior test for Data Health aggregation using the real app.js."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _render(data, meta):
    src = (ROOT / "app.js").read_text(encoding="utf-8")
    marker = "  boot();\n  renderDataHealth();"
    assert marker in src
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
    p = ROOT / "tests" / "_health_harness.js"
    p.write_text(harness + src + tail, encoding="utf-8")
    try:
        proc = subprocess.run(["node", str(p)], capture_output=True, text=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip().splitlines()[-1])["html"]
    finally:
        p.unlink(missing_ok=True)


def _data():
    return {
        "generated_at": "2026-11-03T00:00:00Z",
        "market": {"updated_at": "2026-11-03T00:00:00Z"},
        "macro_forecast": {"generated_at": "2026-11-03T00:00:00Z", "as_of": None,
                           "source": "TradingEconomics", "items": [
                               {"key": "cpi", "verification_status": "unverified",
                                "source_status": "unverified"}]},
        "news": {"updated_at": "2020-01-01T00:00:00Z", "source": "news"},
        "portfolio": {"snapshot_asof": "2020-01-01"},
    }


def _meta():
    return {"pending_scan_date": None, "market_updated_at": "2026-11-03T00:00:00Z",
            "technical_updated_at": "2026-11-03T00:00:00Z", "ai_status": "pending",
            "quote_provider": "yfinance", "network_status": "ok"}


def test_health_aggregates_macro_and_stale_news_and_ledger():
    html = _render(_data(), _meta())
    assert "FALLBACK" in html
    assert "STALE" in html
    assert "MISSING" in html
    assert "FALLBACK/UNVERIFIED" in html
