#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""决策输入层：把各板块压缩成一份只读、可审计的快照。

输出：dashboard/data/decision_inputs.json
  {schema, generated_at, asof, features: [{key,label,group,value,unit,status,source}]}

只做聚合，不做任何加权/阈值/买卖判断；策略如何使用由量化研究（GPT）定义。
任何模块缺失 → 该项 status=missing、value=null，绝不补 0。
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "dashboard" / "data"
OUT = DATA / "decision_inputs.json"

BULL = ("rally", "surge", "beat", "upgrade", "record high", "strong", "growth", "profit",
        "gain", "rebound", "利好", "上涨", "大涨", "超预期", "上调", "增长", "反弹", "创新高")
BEAR = ("plunge", "slump", "fall", "drop", "miss", "downgrade", "layoff", "recession",
        "warning", "cut", "loss", "weak", "selloff", "crash", "tariff", "利空", "下跌",
        "暴跌", "低于预期", "下调", "裁员", "衰退", "警告", "亏损", "关税")


def load(name, default=None):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except Exception:
        return default


def senti(text):
    t = str(text or "").lower()
    b = sum(1 for w in BULL if w in t)
    s = sum(1 for w in BEAR if w in t)
    return "bull" if b > s else ("bear" if s > b else "neutral")


def feature(key, label, group, value, unit="", status="ok", source=""):
    return {"key": key, "label": label, "group": group, "value": value,
            "unit": unit, "status": status, "source": source}


def build():
    feats = []

    # 宏观
    mi = load("macro_indicators.json") or {}
    items = mi.get("items") or []
    if items:
        ok = sum(1 for i in items if i.get("value") is not None)
        feats.append(feature("macro_ok", "宏观有值项", "宏观", ok, f"/{len(items)}",
                             "ok" if ok == len(items) else "partial", "macro_indicators"))
        miss = [i.get("name") for i in items if i.get("value") is None]
        feats.append(feature("macro_missing", "缺失项", "宏观", len(miss), "",
                             "ok" if not miss else "partial", "macro_indicators"))
    else:
        feats.append(feature("macro_ok", "宏观有值项", "宏观", None, "", "missing", "macro_indicators"))

    mf = load("macro_forecast.json") or {}
    rows = {i.get("key"): i for i in (mf.get("items") or [])}
    for key, label in (("cpi_yoy", "CPI预期差"), ("core_cpi_yoy", "核心CPI预期差"),
                       ("unrate", "失业率预期差"), ("cpi_mom", "CPI月率预期差")):
        r = rows.get(key)
        if r and r.get("actual") is not None and r.get("forecast") is not None:
            v = round(float(r["actual"]) - float(r["forecast"]), 2)
            feats.append(feature(key + "_surprise", label, "宏观", v, "pp", "ok", "macro_forecast"))
        else:
            feats.append(feature(key + "_surprise", label, "宏观", None, "pp", "missing", "macro_forecast"))

    # 市场情绪
    mki = load("market_indicators.json") or {}
    fg = (mki.get("fear_greed") or {}) if isinstance(mki, dict) else {}
    score = fg.get("score") if isinstance(fg, dict) else None
    feats.append(feature("fg_score", "恐惧贪婪", "情绪", score,
                         "", "ok" if score is not None else "missing", "market_indicators"))
    fed = (mki.get("fedwatch") or {}) if isinstance(mki, dict) else {}
    prob = (fed.get("probabilities") or {}).get("hold")
    if prob is None:
        prob = (fed.get("meetings") or [{}])[0].get("hold_prob")
    feats.append(feature("fed_hold", "最近会议按兵不动概率", "情绪", prob,
                         "%", "ok" if prob is not None else "missing", "market_indicators"))

    # 超跌
    ov = load("oversold_candidates.json") or {}
    cands = ov.get("candidates") or []
    if cands:
        rsis = [c.get("rsi") for c in cands if c.get("rsi") is not None]
        feats.append(feature("oversold_count", "超跌候选数", "超跌", len(cands), "", "ok", "oversold"))
        feats.append(feature("oversold_rsi", "平均RSI", "超跌",
                             round(sum(rsis) / len(rsis), 1) if rsis else None,
                             "", "ok" if rsis else "partial", "oversold"))
    else:
        feats.append(feature("oversold_count", "超跌候选数", "超跌", 0, "", "ok", "oversold"))

    # 供应链
    sk = load("skill_serenity.json") or {}
    pri = sk.get("priorities") or []
    feats.append(feature("serenity_top", "研究优先级数", "供应链", len(pri), "",
                         "ok" if pri else "missing", "skill_serenity"))
    sv = load("serenity_verified.json") or {}
    vitems = sv.get("items") or []
    feats.append(feature("serenity_verified", "已核验", "供应链",
                         sum(1 for i in vitems if i.get("status") == "verified"),
                         f"/{len(pri)}", "ok" if vitems else "missing", "serenity_verified"))

    # 新闻 / 讲话情绪
    news = load("news_data.json") or {}
    market_news = news.get("market_news") or []
    if market_news:
        cnt = {"bull": 0, "bear": 0, "neutral": 0}
        for n in market_news:
            cnt[senti(n.get("headline_cn") or n.get("headline"))] += 1
        feats.append(feature("news_bull", "新闻利好", "新闻", cnt["bull"], f"/{len(market_news)}",
                             "ok", "news_data"))
        feats.append(feature("news_bear", "新闻利空", "新闻", cnt["bear"], f"/{len(market_news)}",
                             "ok", "news_data"))
    else:
        feats.append(feature("news_bull", "新闻利好", "新闻", None, "", "missing", "news_data"))

    try:
        dd = json.loads((DATA / "dashboard_data.json").read_text(encoding="utf-8"))
        speakers = ((dd.get("macro") or {}).get("speakers") or [])
    except Exception:
        speakers = []
    if speakers:
        cnt = {"bull": 0, "bear": 0, "neutral": 0}
        for s in speakers:
            k = s.get("sentiment")
            if k in ("bullish", "bearish", "neutral"):
                cnt["bull" if k == "bullish" else ("bear" if k == "bearish" else "neutral")] += 1
            else:
                cnt[senti(s.get("content_cn") or s.get("content"))] += 1
        feats.append(feature("speaker_bear", "讲话利空", "新闻", cnt["bear"], f"/{len(speakers)}",
                             "ok", "macro.speakers"))
    else:
        feats.append(feature("speaker_bear", "讲话利空", "新闻", None, "", "missing", "macro.speakers"))

    asof = mi.get("generated_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asof": asof,
        "note": "只读决策输入快照：权重/阈值/买卖规则由量化研究定义，本层不做判断。",
        "features": feats,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="聚合各板块为决策输入快照")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    payload = build()
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=out.name + ".", suffix=".tmp", dir=str(out.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(f"[OK] 决策输入 {len(payload['features'])} 项 -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
