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
import re
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


def fear_greed_conclusion(score):
    """恐惧贪婪 -> 一行操作结论。"""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return NA
    if s <= 25:
        return "极度恐惧 —— 历史常见中长期底部区域，关注错杀机会，**建议暂停做空**"
    if s <= 45:
        return "恐惧 —— 情绪低迷，**建议逢低分批建仓，控制仓位**"
    if s <= 55:
        return "中性 —— 多空均衡，**跟随趋势操作**"
    if s <= 75:
        return "贪婪 —— 情绪升温，**持仓待涨，注意止盈线**"
    return "极度贪婪 —— 风险积聚，**警惕回调，建议逢高减仓**"


def cpi_conclusion(value):
    """CPI 同比 -> 一行宏观结论。"""
    try:
        v = float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return NA
    if v >= 4:
        return "通胀显著偏高 —— 利率环境承压，**估值扩张受限**"
    if v > 3:
        return "通胀偏高 —— 宏观利率环境承压，**限制估值扩张**"
    if v >= 2:
        return "通胀温和 —— 处于目标区间附近，**对估值中性**"
    return "通胀偏低 —— **利好久期资产，警惕需求走弱**"


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
        # 历史同类交易汇总（胜率 / 平均盈亏 / 盈亏比）
        _pnls = [x["realized_pnl"] for x in tr["rows"] if x.get("realized_pnl") is not None]
        if _pnls:
            _wins = [v for v in _pnls if v > 0]
            _loss = [v for v in _pnls if v <= 0]
            _wr = len(_wins) / len(_pnls) * 100
            _aw = sum(_wins) / len(_wins) if _wins else 0.0
            _al = abs(sum(_loss) / len(_loss)) if _loss else 0.0
            _rr_s = ("%.2f" % (_aw / _al)) if _al > 0 else NA
            L.append("- **历史同类交易汇总**：共 %d 笔，胜率 %.1f%%，平均盈利 +$%.2f，平均亏损 -$%.2f，盈亏比 %s" % (len(_pnls), _wr, _aw, _al, _rr_s))
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
    L.append(f"  - **分析结论**：{fear_greed_conclusion(fgv['score'])}")
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
        L.append(f"- 宏观指标（{len(m['economic'])} 项，最新发布值）：")
        for e in m["economic"]:
            L.append(f"  - {e['indicator']}：**{e['value']}**（前值 {e['prev']}，"
                     f"{e['date']}，{e['sentiment']}）")
        _cpi = next((e for e in m["economic"]
                     if "CPI" in str(e.get("indicator", "")) and "核心" not in str(e.get("indicator", ""))),
                    None)
        if _cpi:
            L.append(f"  - **CPI 结论**：{cpi_conclusion(_cpi.get('value'))}"
                     f"（数据月份 {_cpi.get('date')}，为最新已发布月度值）")
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


def _parse_watchlist(spec: str) -> list:
    """解析 --watchlist：逗号分隔，或一个每行一个 ticker 的 txt 文件。"""
    spec = (spec or "").strip()
    if not spec:
        return []
    p = Path(spec)
    if p.exists() and p.is_file():
        try:
            raw = p.read_text(encoding="utf-8-sig")
        except Exception:
            raw = ""
        items = [x.strip() for x in re.split(r"[\s,]+", raw) if x.strip()]
    else:
        items = [x.strip() for x in spec.split(",") if x.strip()]
    seen, out = set(), []
    for x in items:
        u = x.upper()
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _macro_text(m: dict) -> list:
    L = ["## 宏观环境（结论化，仅打印一次）", ""]
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
        L.append("- 宏观指标：")
        for e in m["economic"]:
            L.append(f"  - {e['indicator']}：**{e['value']}**（前值 {e['prev']}，"
                     f"{e['date']}，{e['sentiment']}）")
    else:
        L.append(f"- 宏观指标：{NA}")
    if m["speakers"]:
        s = m["speakers"][0]
        L.append(f"- 美联储讲话：最近一次 **{s['person']}**（{s['time']}，{s['source']}）："
                 f"{s['summary']}　立场：**{s['sentiment']}**")
    else:
        L.append(f"- 美联储讲话：{NA}")
    L.append("")
    return L


def _summary_line(datas: list) -> str:
    n = len(datas)
    ai = sum(1 for d in datas if d["ai_history"]["count"] > 0)
    tr = sum(1 for d in datas if d["trades"]["count"] > 0)
    names = ", ".join(d["ticker"] for d in datas)
    return (f"- 共 **{n}** 只票（{names}）：**{ai}** 只有 AI 快照记录，"
            f"**{tr}** 只有交易记录")


def _per_ticker_body(d: dict) -> str:
    """去掉 # Ticker Brief 标题与第 4 段宏观（宏观在日报头部统一打印）。"""
    body = render_text(d)
    body = body.split("\n", 1)[1]
    idx = body.find("## 4. 宏观环境")
    if idx >= 0:
        body = body[:idx].rstrip()
    body = body.strip("\n")
    # 逐票小节的内部标题降一级（避免与顶级 ## 冲突）
    body = "\n".join(("#" + ln) if ln.startswith("## ") else ln for ln in body.split("\n"))
    return body


def render_watchlist_text(datas: list) -> str:
    L = [f"# Watchlist Brief（{len(datas)} 只）", "", _summary_line(datas), ""]
    L += _macro_text(datas[0]["macro"]) if datas else []
    for i, d in enumerate(datas):
        if i:
            L += ["", "=" * 60, ""]
        L.append(_per_ticker_body(d))
        L.append("")
    L += ["---", "说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。"]
    return "\n".join(L)


def render_watchlist_md(datas: list) -> str:
    L = [f"# Watchlist Brief — {len(datas)} 只", "",
         f"> 生成：`scripts/ticker_brief.py --watchlist ... --md`　"
         f"仓库：{datas[0]['repo'] if datas else NA}　日期："
         f"{datas[0]['as_of'] if datas else NA}", "",
         _summary_line(datas), ""]
    L += _macro_text(datas[0]["macro"]) if datas else []
    for i, d in enumerate(datas):
        L += [f"---", "", f"## {i + 1}. `{d['ticker']}`", ""]
        L.append(_per_ticker_body(d))
        L.append("")
    L += ["---", "", "说明：只读简报；缺失项统一 N/A。宏观环境在头部统一展示，不重复。"]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="单只/批量 ticker 结构化简报（只读）")
    ap.add_argument("ticker", nargs="?", help="股票代码，如 AAPL")
    ap.add_argument("--ticker", dest="ticker_opt", help="同位置参数（兼容写法）")
    ap.add_argument("--watchlist", default=None,
                    help="批量：AAPL,MSFT,NVDA 或 watchlist.txt（每行一个）")
    ap.add_argument("--date", default=None, help="指定 Scan_Date（YYYY-MM-DD）")
    ap.add_argument("--json", action="store_true", help="输出结构化 JSON")
    ap.add_argument("--md", action="store_true", help="输出 Markdown")
    args = ap.parse_args(argv)

    if args.watchlist:
        tickers = _parse_watchlist(args.watchlist)
        if not tickers:
            print("watchlist 为空")
            return 0
        datas = [collect(tk, args.date) for tk in tickers]
        if args.json:
            print(json.dumps(datas, ensure_ascii=False, indent=2))
        elif args.md:
            print(render_watchlist_md(datas))
        else:
            print(render_watchlist_text(datas))
        return 0

    raw = (args.ticker or args.ticker_opt or "").strip().upper()
    if not raw:
        print("用法：python scripts/ticker_brief.py <TICKER> [--md] [--json] [--date YYYY-MM-DD]")
        print("      python scripts/ticker_brief.py --watchlist AAPL,MSFT,NVDA [--md|--json]")
        print("      python scripts/ticker_brief.py --watchlist watchlist.txt --md")
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
