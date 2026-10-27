#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""超跌候选：板块上限 + AI 三维分析（技术面 / 基本面 / 消息面）。

流程：
  1. 复用 scripts/oversold_screen.py 的规则筛选，得到按评分排序的候选池（≤40）；
  2. 用 yfinance 补齐板块、估值/盈利指标与个股新闻；失败则降级为快照字段；
  3. 板块上限：每个板块最多 2 只，截取前 10；
  4. 逐只调用 ClawSocket（ai_router.gpt_generate_text），让模型只基于给定事实
     输出 {verdict, technical, fundamental, news, risk, summary}；
  5. 写回 dashboard/data/oversold_candidates.json（fail-closed：无密钥/模型失败时
     仍写出规则候选，只是 ai 字段缺失，前端显示 pending）。

边界：不写任何 quant_* 文件、不进账本、不产生交易；AI 只解释给定数据，不预测价格。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.oversold_screen import load_latest_rows, screen  # noqa: E402

DEFAULT_SNAPSHOT = REPO_ROOT / "quant_factor_snapshot.csv"
DEFAULT_OUT = REPO_ROOT / "dashboard" / "data" / "oversold_candidates.json"
DEFAULT_DATA = REPO_ROOT / "dashboard" / "data" / "dashboard_data.json"

POOL_MAX = 24
FINAL_MAX = 10
SECTOR_CAP = 2
VERDICTS = ("关注", "观察", "谨慎", "回避")
AI_MODEL_ENV = "OVERSOLD_AI_MODEL"


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def enrich_one(c: dict) -> dict:
    """用 yfinance 补板块/基本面/新闻；任何失败都返回空 dict（降级）。"""
    out = {}
    try:
        import socket
        socket.setdefaulttimeout(10)
        import yfinance as yf
        t = yf.Ticker(c["ticker"])
        info = t.info or {}
        out.update({
            "sector": info.get("sector") or None,
            "industry": info.get("industry") or None,
            "pe_ttm": _num(info.get("trailingPE")),
            "pe_forward": _num(info.get("forwardPE")),
            "pb": _num(info.get("priceToBook")),
            "roe": _num(info.get("returnOnEquity")),
            "profit_margin": _num(info.get("profitMargins")),
            "revenue_growth": _num(info.get("revenueGrowth")),
            "earnings_growth": _num(info.get("earningsGrowth")),
            "market_cap": _num(info.get("marketCap")),
        })
        news = []
        try:
            for n in (t.news or [])[:4]:
                content = n.get("content") or {}
                title = content.get("title") or n.get("title")
                publisher = (content.get("provider") or {}).get("displayName") or n.get("publisher")
                when = content.get("pubDate") or n.get("providerPublishTime")
                if title:
                    news.append({"title": str(title)[:160], "publisher": publisher, "time": when})
        except Exception:
            pass
        out["news"] = news
    except Exception:
        return {}
    return out


def merge_enrich(cands, workers: int = 6, timeout: int = 15):
    """逐只 enrich，每只放到独立子进程里跑并硬超时，避免 yfinance 卡住整个刷新。"""
    import subprocess

    def run_one(c):
        try:
            proc = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--enrich-one", c["ticker"]],
                capture_output=True, text=True, timeout=timeout,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return json.loads(proc.stdout.strip().splitlines()[-1])
        except Exception:
            pass
        return {}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(run_one, cands))
    for c, e in zip(cands, results):
        if e:
            c["enrich"] = e
            if e.get("sector"):
                c["sector"] = e["sector"]
    return cands


def cap_by_sector(cands, cap: int = SECTOR_CAP, final: int = FINAL_MAX):
    counts, out = {}, []
    for c in cands:
        key = str(c.get("sector") or c.get("snapshot_sector") or "未分类").strip() or "未分类"
        if counts.get(key, 0) >= cap:
            continue
        counts[key] = counts.get(key, 0) + 1
        out.append(c)
        if len(out) >= final:
            break
    return out


def build_facts(c: dict, market_news, ticker_news=None) -> dict:
    e = c.get("enrich") or {}
    news = (ticker_news or {}).get(c["ticker"]) or e.get("news") or []
    return {
        "ticker": c["ticker"],
        "name": c.get("name"),
        "sector": c.get("sector") or c.get("snapshot_sector"),
        "industry": e.get("industry"),
        "rule_score": c.get("score"),
        "technical": {
            "rsi_14": c.get("rsi"),
            "bias_vs_ma20_pct": c.get("bias_pct"),
            "zscore_20d": c.get("zscore"),
            "atr_pct": c.get("atr_pct"),
            "momentum_20d_pct": c.get("drawdown_pct"),
            "momentum_60d_pct": c.get("momentum_60d_pct"),
            "volume_ratio_20d": c.get("volume_ratio_20d"),
            "beta_60d_spy": c.get("beta"),
            "rs_20d_vs_spy": c.get("rs_20d_vs_spy"),
            "market_regime": c.get("market_regime"),
            "technical_score_25": c.get("technical_score"),
            "event_score": c.get("event_score"),
            "quant_score": c.get("quant_score"),
        },
        "fundamental": {
            "pe_ttm": e.get("pe_ttm"),
            "pe_forward": e.get("pe_forward"),
            "pb": e.get("pb"),
            "roe": e.get("roe"),
            "profit_margin": e.get("profit_margin"),
            "revenue_growth": e.get("revenue_growth"),
            "earnings_growth": e.get("earnings_growth"),
            "market_cap": e.get("market_cap"),
        },
        "news": news,
        "market_news": market_news,
        "reference_stop": c.get("stop_loss"),
        "reference_price": c.get("ref_price"),
    }


SYSTEM = (
    "你是美股观察板块的分析助手。只能使用用户提供的事实，不得编造数字、新闻或财报。"
    "输出必须是 JSON：{\"verdict\":\"关注|观察|谨慎|回避\",\"technical\":\"...\","
    "\"fundamental\":\"...\",\"news\":\"...\",\"risk\":\"...\",\"summary\":\"...\"}。"
    "每个字段不超过 80 个汉字；缺少某类数据时明确写“数据缺失”，不要猜测。"
    "个股新闻为空时，可用 market_news 概括大盘/板块消息面，并注明「市场层面」。"
    "这是观察笔记，不是投资建议，不预测价格。"
)


def analyze_one(c: dict, market_news, ticker_news=None) -> dict | None:
    try:
        from ai_router import gpt_generate_text, extract_json_object
    except Exception:
        return None
    facts = build_facts(c, market_news, ticker_news)
    try:
        text = gpt_generate_text(
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
            ],
            max_tokens=2500,
            reasoning_effort="low",
            model=os.environ.get(AI_MODEL_ENV) or None,
        )
        obj = extract_json_object(text)
        if not isinstance(obj, dict):
            return None
        return normalize_ai(obj)
    except Exception as exc:
        print(f"[WARN] {c.get('ticker')} AI 分析失败：{exc}", file=sys.stderr)
        return None


def normalize_ai(obj: dict) -> dict:
    verdict = str(obj.get("verdict") or "").strip()
    if verdict not in VERDICTS:
        verdict = "观察"

    def s(key):
        v = str(obj.get(key) or "").strip()
        return v[:160] or None

    return {
        "verdict": verdict,
        "technical": s("technical"),
        "fundamental": s("fundamental"),
        "news": s("news"),
        "risk": s("risk"),
        "summary": s("summary"),
    }


def load_news(data_path: Path, limit: int = 6):
    """从 dashboard_data.json 读取市场新闻与个股新闻。

    结构：news = {market_news: [...], ticker_news: {TICKER: [...]}, ...}
    返回 (market_headlines, {TICKER: [{title, publisher}]})。
    """
    try:
        raw = json.loads(data_path.read_text(encoding="utf-8"))
    except Exception:
        return [], {}
    news = raw.get("news")
    market, ticker_news = [], {}
    if isinstance(news, dict):
        for n in (news.get("market_news") or [])[:limit]:
            if isinstance(n, dict):
                title = n.get("headline_cn") or n.get("headline")
                if title:
                    market.append(str(title)[:140])
        for tk, items in (news.get("ticker_news") or {}).items():
            if not isinstance(items, list):
                continue
            rows = []
            for n in items[:4]:
                if isinstance(n, dict) and (n.get("headline") or n.get("headline_cn")):
                    rows.append({
                        "title": str(n.get("headline_cn") or n.get("headline"))[:160],
                        "publisher": n.get("source"),
                    })
            if rows:
                ticker_news[str(tk).upper()] = rows
    elif isinstance(news, list):
        for n in news[:limit]:
            if isinstance(n, dict):
                title = n.get("headline_cn") or n.get("headline")
                if title:
                    market.append(str(title)[:140])
    return market, ticker_news


def build_payload(asof, cands, ai_ok: int, model: str | None):
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asof": asof,
        "source": "规则筛选（RSI/Bias/ZScore + 流动性 + ATR）· 板块上限 2 · AI 三维分析 · 未回测",
        "note": (
            "规则版观察信号 + AI 解读（技术面/基本面/消息面）；未做回测、不预测价格、"
            "不构成投资建议，不进入 $50k 账本。"
        ),
        "ai_model": model,
        "ai_count": ai_ok,
        "candidates": cands,
    }


def _atomic_write(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--enrich-one" and len(argv) > 1:
        print(json.dumps(enrich_one({"ticker": argv[1]}), ensure_ascii=False))
        return 0

    ap = argparse.ArgumentParser(description="超跌候选：板块上限 + AI 三维分析")
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--offline", action="store_true", help="不联网、不调用 AI，只做板块上限")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    asof, rows = load_latest_rows(Path(args.snapshot))
    if not rows:
        print("[WARN] 因子快照缺失或为空，保留现有候选文件不动", file=sys.stderr)
        return 0

    pool = screen(rows, asof, max_candidates=POOL_MAX)
    if not pool:
        _atomic_write(Path(args.out), build_payload(asof, [], 0, None))
        print(f"[OK] {asof}：无候选", file=sys.stderr)
        return 0

    market_news, ticker_news = ([], {}) if args.offline else load_news(Path(args.data))
    if not args.offline:
        pool = merge_enrich(pool)

    final = cap_by_sector(pool, SECTOR_CAP, FINAL_MAX)

    ai_ok = 0
    model = None
    if not args.offline:
        model = os.environ.get(AI_MODEL_ENV) or None
        for c in final:
            ai = analyze_one(c, market_news, ticker_news)
            if ai:
                c["ai"] = ai
                ai_ok += 1

    payload = build_payload(asof, final, ai_ok, model)
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    _atomic_write(Path(args.out), payload)
    print(f"[OK] {asof}：{len(final)} 条候选，AI 分析 {ai_ok} 条 -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
