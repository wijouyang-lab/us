#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C 线 CLI 简报 v2 —— 单只 ticker 的结构化简报（只读）。

用法：
    python scripts/ticker_brief.py AAPL                 # 纯文本
    python scripts/ticker_brief.py AAPL --md            # Markdown
    python scripts/ticker_brief.py AAPL --json          # 结构化 JSON
    python scripts/ticker_brief.py AAPL --date 2026-10-16

数据来源（全部只读，不 import 生产模块）：
  ai_snapshot.csv / quant_factor_snapshot.csv / portfolio_50000_transactions.csv
  portfolio_50000_txn_time.csv（侧车，精确时刻）/ trade_history.csv
  macro_data.json / dashboard/data/market_indicators.json

约定：缺数据一律 N/A，不抛异常；退出码恒 0（argparse 用法错误除外）。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

AI_SNAPSHOT = REPO / "ai_snapshot.csv"
QUANT_SNAPSHOT = REPO / "quant_factor_snapshot.csv"
TXN = REPO / "portfolio_50000_transactions.csv"
TXN_TIME = REPO / "portfolio_50000_txn_time.csv"
TRADE_HISTORY = REPO / "trade_history.csv"
MACRO_DATA = REPO / "macro_data.json"
MARKET_INDICATORS = REPO / "dashboard" / "data" / "market_indicators.json"
NA = "N/A"

FACTORS = [
    "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
    "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "ZScore_20D",
    "Beta_60D_SPY", "Stock_RS_20D_vs_SPY", "Quant_Score",
    "RSI", "MA20", "MA50", "MA20_Slope_Pct_5D", "ATR_Pct",
    "乖离率(%)", "MACD_HIST_LAST", "KDJ_J", "量比",
]
FG_CN = {"extreme fear": "极度恐惧", "fear": "恐惧", "neutral": "中性",
         "greed": "贪婪", "extreme greed": "极度贪婪"}
SENT_CN = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}


def read_csv(path: Path) -> list:
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def num(v):
    s = str(v if v is not None else "").strip()
    if not s or s.upper() == NA:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def fmt(v, d: int = 2) -> str:
    x = num(v)
    return NA if x is None else f"{x:.{d}f}"


def pct_rank(vals, target) -> str:
    t = num(target)
    if t is None or len(vals) < 5:
        return NA
    return f"{sum(1 for v in vals if v < t) / len(vals) * 100:.0f}"


def collect(ticker: str, as_of) -> dict:
    out = {"ticker": ticker, "as_of": as_of or "latest", "repo": REPO.name}

    ai = [r for r in read_csv(AI_SNAPSHOT)
          if (r.get("Ticker") or "").strip().upper() == ticker]
    ai.sort(key=lambda r: (r.get("Rec_Date") or ""), reverse=True)
    out["ai_history"] = {"count": len(ai), "rows": [
        {"rec_date": r.get("Rec_Date") or NA, "tag": r.get("Tag") or NA,
         "snapshot_type": r.get("Snapshot_Type") or NA,
         "final_score": num(r.get("Final_Score")),
         "ai_score": num(r.get("AI_Score"))} for r in ai[:5]]}

    rows = read_csv(QUANT_SNAPSHOT)
    dates = sorted({(r.get("Scan_Date") or "") for r in rows if r.get("Scan_Date")})
    hold = {"snapshot_date": NA, "sector": NA, "price": None, "universe": 0,
            "total_dates": 0, "total_rows": len(rows), "factors": {}, "note": NA}
    if rows and dates:
        target = as_of if (as_of and as_of in dates) else dates[-1]
        if as_of and as_of not in dates:
            hold["note"] = f"{as_of} 不在快照内，改用 {target}"
        same = [r for r in rows if (r.get("Scan_Date") or "") == target]
        mine = [r for r in same if (r.get("Ticker") or "").strip().upper() == ticker]
        hold["snapshot_date"] = target
        hold["universe"] = len(same)
        hold["total_dates"] = len(dates)
        if mine:
            r = mine[0]
            hold["sector"] = r.get("Sector") or NA
            hold["price"] = num(r.get("Price"))
            for f in FACTORS:
                if f not in r or num(r.get(f)) is None:
                    continue
                col = [num(x.get(f)) for x in same]
                col = [v for v in col if v is not None]
                hold["factors"][f] = {"value": num(r.get(f)),
                                      "pctl": pct_rank(col, r.get(f))}
        else:
            hold["note"] = f"该 ticker 在 {target} 无因子快照"
    out["factor_position"] = hold

    tmap = {}
    for r in read_csv(TXN_TIME):
        tid = (r.get("Txn_ID") or "").strip()
        if tid and r.get("Execution_Time"):
            tmap[tid] = r["Execution_Time"]

    tx = read_csv(TXN)
    sector = hold["sector"] if hold["sector"] != NA else ""
    pool = set()
    if sector:
        pool = {((r.get("Ticker") or "").strip().upper()) for r in rows
                if (r.get("Sector") or "") == sector}
    mine = [r for r in tx if (r.get("Ticker") or "").strip().upper() == ticker]
    scope = ticker
    if not mine and pool:
        mine = [r for r in tx if (r.get("Ticker") or "").strip().upper() in pool]
        scope = f"同 Sector（{sector}）"

    def _row(r):
        act = (r.get("Action") or "").strip().upper()
        tid = (r.get("Txn_ID") or "").strip()
        return {"time": tmap.get(tid) or f"{r.get('Date') or NA}（仅日期）",
                "precise": tid in tmap, "ticker": r.get("Ticker") or NA,
                "action": {"BUY": "买入", "SELL": "卖出"}.get(act, act or NA),
                "price": num(r.get("Price")), "shares": num(r.get("Shares")),
                "amount": num(r.get("Amount")), "realized_pnl": num(r.get("Realized_PnL"))}

    mine_sorted = sorted(mine, key=lambda x: x.get("Date") or "", reverse=True)
    out["trades"] = {"scope": scope, "count": len(mine),
                     "precise_time_available": len(tmap) > 0,
                     "rows": [_row(r) for r in mine_sorted[:10]]}

    mi = read_json(MARKET_INDICATORS)
    fg = mi.get("fear_greed") if isinstance(mi.get("fear_greed"), dict) else {}
    fw = mi.get("fedwatch") if isinstance(mi.get("fedwatch"), dict) else {}
    prob = fw.get("probabilities") if isinstance(fw.get("probabilities"), dict) else {}
    macro = read_json(MACRO_DATA)
    econ = macro.get("economic") if isinstance(macro.get("economic"), list) else []
    spk = [s for s in (macro.get("speakers") or []) if isinstance(s, dict)]
    out["macro"] = {
        "fear_greed": {"score": num(fg.get("score")),
                       "rating": FG_CN.get((fg.get("rating") or "").strip().lower(),
                                           fg.get("rating") or NA),
                       "timestamp": fg.get("timestamp") or NA},
        "fedwatch": {"next_meeting": fw.get("next_meeting") or NA,
                     "target_range": fw.get("current_target") or NA,
                     "probabilities": {k: num(v) for k, v in prob.items()}},
        "economic": [{"indicator": i.get("indicator") or NA,
                      "value": i.get("value") or NA, "prev": i.get("prev") or NA,
                      "date": i.get("date") or NA,
                      "sentiment": SENT_CN.get((i.get("sentiment") or "").lower(),
                                               i.get("sentiment") or NA)}
                     for i in econ[:6] if isinstance(i, dict)],
        "speakers": [{"person": s.get("person") or NA, "time": s.get("time") or NA,
                      "source": s.get("source") or NA,
                      "summary": s.get("content_cn") or s.get("content") or NA,
                      "sentiment": SENT_CN.get((s.get("sentiment") or "").lower(),
                                               s.get("sentiment") or NA)}
                     for s in spk[:3]],
    }
    return out


def render_text(d: dict) -> str:
    L = [f"# Ticker Brief: {d['ticker']}", ""]
    ai = d["ai_history"]
    L += ["## 1. AI 历史（ai_snapshot.csv）", ""]
    if not ai["count"]:
        L.append(f"- {NA}（无 AI 快照记录）")
    else:
        L.append(f"- 记录数：{ai['count']}")
        L += ["", "| Rec_Date | Tag | Snapshot_Type | Final_Score | AI_Score |",
              "|---|---|---|---|---|"]
        for r in ai["rows"]:
            L.append("| {} | {} | {} | {} | {} |".format(
                r["rec_date"], r["tag"], r["snapshot_type"],
                fmt(r["final_score"]), fmt(r["ai_score"])))

    fp = d["factor_position"]
    L += ["", "## 2. 因子位置（quant_factor_snapshot.csv）", ""]
    if fp["snapshot_date"] == NA:
        L.append(f"- {NA}（快照不可用）")
    else:
        L.append(f"- 快照日期：{fp['snapshot_date']}（该日共 {fp['universe']} 只；"
                 f"全表 {fp['total_dates']} 个日期 / {fp['total_rows']} 行）")
        L.append(f"- Sector：{fp['sector']}　Price：{fmt(fp['price'])}")
        if fp["note"] != NA:
            L.append(f"- 提示：{fp['note']}")
        if fp["factors"]:
            L += ["", "| 因子 | 值 | 当日百分位 |", "|---|---|---|"]
            for k, v in fp["factors"].items():
                L.append(f"| {k} | {v['value']:.4f} | {v['pctl']} |")

    tr = d["trades"]
    L += ["", "## 3. 交易明细（portfolio_50000_transactions.csv）", ""]
    L.append("- 已启用侧车精确时刻（portfolio_50000_txn_time.csv）"
             if tr["precise_time_available"]
             else f"- **数据源缺少精确时间，仅有日期**（无 {TXN_TIME.name} 侧车）")
    if tr["scope"] != d["ticker"]:
        L.append(f"- 该 ticker 无成交记录 → 退化为 {tr['scope']}")
    if not tr["count"]:
        L.append(f"- {NA}（无成交记录）")
    else:
        L.append(f"- 样本数：{tr['count']}（按日期倒序展示最近 {len(tr['rows'])} 笔）")
        L += ["", "| 时间 | Ticker | 操作 | 价格 | 股数 | 金额 | 已实现盈亏 |",
              "|---|---|---|---|---|---|---|"]
        for r in tr["rows"]:
            L.append("| {} | {} | {} | {} | {} | {} | {} |".format(
                r["time"], r["ticker"], r["action"], fmt(r["price"]),
                fmt(r["shares"], 0), fmt(r["amount"]), fmt(r["realized_pnl"])))

    m = d["macro"]
    L += ["", "## 4. 宏观环境（结论化）", ""]
    fgv = m["fear_greed"]
    L.append(f"- 恐惧贪婪指数：**{fmt(fgv['score'])}（{fgv['rating']}）**　"
             f"时间戳：{fgv['timestamp']}")
    fw = m["fedwatch"]
    parts = []
    for k, label in (("cut_25bp", "降息 25bp"), ("hold", "维持不变"),
                     ("hike_25bp", "加息 25bp"), ("cut_50bp", "降息 50bp")):
        v = fw["probabilities"].get(k)
        if v is not None:
            parts.append(f"{label} **{v:.1f}%**")
    L.append(f"- FedWatch（会议 {fw['next_meeting']}，目标区间 {fw['target_range']}）："
             + (" / ".join(parts) if parts else NA))
    if m["economic"]:
        L.append(f"- 宏观指标（{len(m['economic'])} 项）：")
        for e in m["economic"]:
            L.append(f"  - {e['indicator']}：**{e['value']}**（前值 {e['prev']}，"
                     f"{e['date']}，{e['sentiment']}）")
    else:
        L.append(f"- 宏观指标：{NA}")
    if m["speakers"]:
        s = m["speakers"][0]
        L.append(f"- 美联储讲话：最近一次 **{s['person']}**（{s['time']}，{s['source']}）："
                 f"{s['summary']}　立场：**{s['sentiment']}**")
        for s in m["speakers"][1:]:
            L.append(f"  - 另有 {s['person']}（{s['time']}）：{s['summary'][:60]}　[{s['sentiment']}]")
    else:
        L.append(f"- 美联储讲话：{NA}")
    L += ["", "---", "说明：本简报只读，不写文件；缺失项统一显示 N/A。"]
    return "\n".join(L)


def render_md(d: dict) -> str:
    head = [f"# Ticker Brief — `{d['ticker']}`", "",
            f"> 生成：`scripts/ticker_brief.py --md`　仓库：{d['repo']}　"
            f"指定日期：{d['as_of']}", ""]
    body = render_text(d).split("\n", 1)[1]
    return "\n".join(head) + "\n" + body


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="单只 ticker 的结构化简报（只读）")
    ap.add_argument("ticker", nargs="?", help="股票代码，如 AAPL")
    ap.add_argument("--ticker", dest="ticker_opt", help="同位置参数（兼容写法）")
    ap.add_argument("--date", default=None, help="指定 Scan_Date（YYYY-MM-DD）")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    ap.add_argument("--md", action="store_true", help="输出 Markdown")
    args = ap.parse_args(argv)

    raw = (args.ticker or args.ticker_opt or "").strip().upper()
    if not raw:
        print("用法：python scripts/ticker_brief.py <TICKER> [--md] [--json] [--date YYYY-MM-DD]")
        return 0

    data = collect(raw, args.date)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.md:
        print(render_md(data))
    else:
        print(render_text(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
