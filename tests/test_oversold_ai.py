# -*- coding: utf-8 -*-
"""超跌候选：板块上限 + AI 三维分析（离线/失败降级）。"""
import importlib.util
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "oversold_ai", _REPO_ROOT / "scripts" / "oversold_ai.py")
ai_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ai_mod)

import dashboard_export as de  # noqa: E402

HEADER = ("Scan_Date,Technical_Date,Ticker,Name,Sector,Price,RSI_14,Bias_Pct,"
          "ZScore_20D,ATR_Pct,Volume_Ratio_20D,Momentum_20D_Pct,Momentum_60D_Pct,"
          "MA20,MA50,Technical_Score_25,Event_Score,Quant_Score,Beta_60D_SPY,"
          "Stock_RS_20D_vs_SPY,Market_Regime\n")


def _row(ticker, sector="Technology", rsi=25, bias=-12, z=-2.2, px=50, atr=4,
         vr=1.0, mom=-10, mom60=-20, ma20=56, ma50=60, ts=5, es=8, qs=25,
         beta=1.1, rs=-15, regime="NORMAL", scan="2026-10-26"):
    return (f"{scan},2026-10-25,{ticker},Name {ticker},{sector},{px},{rsi},{bias},"
            f"{z},{atr},{vr},{mom},{mom60},{ma20},{ma50},{ts},{es},{qs},{beta},{rs},{regime}\n")


def _write(tmp_path: Path, body: str):
    p = tmp_path / "quant_factor_snapshot.csv"
    p.write_text(HEADER + body, encoding="utf-8")
    return p


def test_normalize_ai_defaults_and_truncates():
    out = ai_mod.normalize_ai({"verdict": "强烈买入", "technical": "x" * 500})
    assert out["verdict"] == "观察"
    assert len(out["technical"]) == 160
    assert out["fundamental"] is None


def test_normalize_ai_keeps_valid_verdict():
    for v in ("关注", "观察", "谨慎", "回避"):
        assert ai_mod.normalize_ai({"verdict": v})["verdict"] == v


def test_cap_by_sector_limits_each_sector():
    cands = [
        {"ticker": "T1", "sector": "Technology", "score": 90},
        {"ticker": "T2", "sector": "Technology", "score": 85},
        {"ticker": "T3", "sector": "Technology", "score": 80},
        {"ticker": "H1", "sector": "Healthcare", "score": 70},
        {"ticker": "H2", "sector": "Healthcare", "score": 65},
        {"ticker": "H3", "sector": "Healthcare", "score": 60},
        {"ticker": "E1", "sector": "Energy", "score": 55},
    ]
    out = ai_mod.cap_by_sector(cands, cap=2, final=10)
    assert [c["ticker"] for c in out] == ["T1", "T2", "H1", "H2", "E1"]


def test_cap_by_sector_respects_final_limit():
    cands = [{"ticker": f"X{i}", "sector": f"S{i}", "score": 100 - i} for i in range(15)]
    out = ai_mod.cap_by_sector(cands, cap=2, final=10)
    assert len(out) == 10


def test_build_facts_contains_three_dimensions():
    c = {"ticker": "AAA", "score": 60, "rsi": 22, "bias_pct": -15,
         "zscore": -2.5, "atr_pct": 4.2, "drawdown_pct": -20,
         "momentum_60d_pct": -33, "volume_ratio_20d": 1.2, "beta": 1.1,
         "rs_20d_vs_spy": -18, "market_regime": "NORMAL",
         "technical_score": 5, "event_score": 8, "quant_score": 25,
         "ref_price": 50, "stop_loss": 46,
         "enrich": {"pe_ttm": 20.5, "roe": 0.18, "news": [{"title": "t"}]}}
    facts = ai_mod.build_facts(c, ["market news"])
    assert facts["technical"]["rsi_14"] == 22
    assert facts["fundamental"]["pe_ttm"] == 20.5
    assert facts["news"][0]["title"] == "t"
    assert facts["market_news"] == ["market news"]


def test_offline_main_writes_capped_candidates(tmp_path):
    body = (_row("T1") + _row("T2") + _row("T3") +
            _row("H1", sector="Healthcare") + _row("H2", sector="Healthcare") +
            _row("H3", sector="Healthcare") + _row("E1", sector="Energy"))
    snap = _write(tmp_path, body)
    out = tmp_path / "oversold_candidates.json"
    rc = ai_mod.main(["--snapshot", str(snap), "--out", str(out), "--offline"])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    tickers = [c["ticker"] for c in payload["candidates"]]
    assert tickers == ["T1", "T2", "H1", "H2", "E1"]
    assert all("ai" not in c for c in payload["candidates"])
    assert payload["ai_count"] == 0


def test_missing_snapshot_keeps_old_file(tmp_path):
    out = tmp_path / "oversold_candidates.json"
    out.write_text('{"schema": 1, "candidates": [{"ticker": "KEEP"}]}', encoding="utf-8")
    rc = ai_mod.main(["--snapshot", str(tmp_path / "nope.csv"),
                      "--out", str(out), "--offline"])
    assert rc == 0
    assert "KEEP" in out.read_text(encoding="utf-8")

def test_dashboard_export_passes_ai_and_sector(tmp_path):
    repo = tmp_path / "repo"
    data = repo / "dashboard" / "data"
    data.mkdir(parents=True)
    (data / "oversold_candidates.json").write_text(
        '{"schema": 1, "ai_model": "m", "ai_count": 1, "candidates": ['
        '{"ticker": "aaa", "sector": "Technology", "score": 60,'
        ' "ai": {"verdict": "买入", "technical": "RSI 超卖", "news": "财报超预期"}}]}',
        encoding="utf-8")
    parsed = de._read_oversold(repo)
    assert parsed["ai_model"] == "m"
    assert parsed["ai_count"] == 1
    c = parsed["candidates"][0]
    assert c["ticker"] == "AAA"
    assert c["sector"] == "Technology"
    assert c["ai"]["verdict"] == "观察"          # 非法结论归为观察
    assert c["ai"]["technical"] == "RSI 超卖"

def test_load_news_reads_market_and_ticker_news(tmp_path):
    data = tmp_path / "dashboard_data.json"
    data.write_text(
        '{"news": {"market_news": [{"headline": "M1"}, {"headline": "M2"}],'
        ' "ticker_news": {"AAA": [{"headline": "H1", "source": "Reuters"}]}}}',
        encoding="utf-8")
    market, ticker_news = ai_mod.load_news(data)
    assert market == ["M1", "M2"]
    assert ticker_news["AAA"][0]["title"] == "H1"
    assert ticker_news["AAA"][0]["publisher"] == "Reuters"


def test_build_facts_prefers_ticker_news():
    c = {"ticker": "AAA", "enrich": {"news": [{"title": "yf"}]}}
    facts = ai_mod.build_facts(c, ["m"], {"AAA": [{"title": "ticker"}]})
    assert facts["news"][0]["title"] == "ticker"
