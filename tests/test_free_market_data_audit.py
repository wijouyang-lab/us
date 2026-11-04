# -*- coding: utf-8 -*-
import pandas as pd
from pathlib import Path
from tools.research.audit_free_market_data import _quality, finnhub_status, TICKERS


def test_quality_detects_duplicates_and_bad_ohlc():
    idx = pd.to_datetime(["2026-01-02","2026-01-02","2026-01-05"])
    df = pd.DataFrame({"Open":[10,10,0],"High":[11,11,0],"Low":[9,9,0],
                       "Close":[10,10,0],"Volume":[100,100,-1]}, index=idx)
    q = _quality(df,"T","X")
    assert q["duplicates"] >= 1 and q["bad_ohlcv_rows"] >= 1


def test_quality_empty():
    assert _quality(pd.DataFrame(),"T","X")["status"] == "DATA_MISSING"


def test_finnhub_without_keys_is_not_configured(monkeypatch):
    for k in ("FINNHUB_API_KEY_A","FINNHUB_API_KEY_B","FINNHUB_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    r = finnhub_status()
    assert r["status"] == "NOT_CONFIGURED"
    assert "secret" not in str(r).lower()


def test_ticker_universe_has_28_plus_etfs():
    assert len(TICKERS) == 31
    assert {"QQQ","BIL","SPY"}.issubset(TICKERS)


def test_actual_audit_results_do_not_claim_license_pass():
    import json
    d = json.loads(Path("data/research/free_market_data_audit_p3.json").read_text())
    assert d["ratings"]["yahoo"]["overall"] == "DATA_BLOCKED"
    assert d["ratings"]["akshare"]["overall"] == "DATA_BLOCKED"
    assert d["ratings"]["finnhub"]["technical"] == "NOT_CONFIGURED"
    assert all(v["license"] == "LICENSE_UNVERIFIED" for v in d["ratings"].values())


def test_actual_coverage_has_31_per_source_and_periods():
    import json
    d = json.loads(Path("data/research/free_market_data_audit_p3.json").read_text())
    for src in ("Yahoo/yfinance", "AKShare/Sina"):
        s = d["summary"][src]
        assert s["symbols"] == 31 and s["ok"] == 31
        assert s["period_coverage"] == {"1y":31,"2y":31,"5y":31,"10y":31}
    assert d["summary"]["AKShare/Sina"]["bad_ohlcv_rows"] == 75
