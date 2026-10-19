#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Paper Trading 日报：胜率 / 盈亏比 / 期望值 / 最大回撤 / 达标判定。

输入：portfolio_paper_transactions.csv
输出：docs/PAPER_TRADING_REPORT.md（每日覆盖）
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "portfolio_paper_transactions.csv"
PRICE_FILE = REPO / "quant_factor_price_history.csv"
OUT = REPO / "docs" / "PAPER_TRADING_REPORT.md"

INITIAL_CAPITAL = 50000.0
TH_WIN = 55.0
TH_RR = 1.2
TH_EXP = 0.5
TH_DD = -5.0
TH_DAYS = 40


def read_rows(path: Path) -> list:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def last_price(tk: str, prices: dict):
    s = prices.get(tk, [])
    return s[-1][1] if s else None


def main() -> int:
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    rows = read_rows(LEDGER)

    prices: dict = {}
    if PRICE_FILE.exists():
        with PRICE_FILE.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                tk = (r.get("Ticker") or "").strip().upper()
                try:
                    px = float(r.get("Close") or "")
                except ValueError:
                    continue
                if tk:
                    prices.setdefault(tk, []).append(((r.get("Date") or ""), px))
        for k in prices:
            prices[k].sort()

    open_rows = [r for r in rows if not r.get("Exit_Date")]
    closed = [r for r in rows if r.get("Exit_Date") and fnum(r.get("PnL_Pct")) is not None]
    pcts = [fnum(r["PnL_Pct"]) for r in closed]
    wins = [p for p in pcts if p > 0]
    losses = [p for p in pcts if p <= 0]

    n = len(pcts)
    win_rate = len(wins) / n * 100 if n else float("nan")
    avg_win = sum(wins) / len(wins) if wins else float("nan")
    avg_loss = abs(sum(losses) / len(losses)) if losses else float("nan")
    rr = avg_win / avg_loss if (wins and losses and avg_loss) else float("nan")
    exp = (win_rate / 100 * avg_win - (1 - win_rate / 100) * avg_loss) if n and wins and losses else float("nan")
    be_rr = (1 - win_rate / 100) / (win_rate / 100) if n and win_rate > 0 else float("nan")

    pnl_sum = sum(fnum(r.get("PnL")) or 0 for r in closed)
    cum = pnl_sum / INITIAL_CAPITAL * 100
    # 最大回撤（按平仓顺序累计 PnL）
    peak, dd, run = 0.0, 0.0, 0.0
    for r in sorted(closed, key=lambda x: x.get("Exit_Date") or ""):
        run += fnum(r.get("PnL")) or 0
        peak = max(peak, run)
        dd = min(dd, run - peak)
    max_dd = dd / INITIAL_CAPITAL * 100
    days = len({r.get("Exit_Date") for r in closed}) + len({r.get("Entry_Date") for r in open_rows})

    def ok(cond):
        return "✅" if cond else "❌"

    L = [f"# Paper Trading 日报 — {today}\n",
         "> 数据：`portfolio_paper_transactions.csv`（**与实盘完全隔离**）",
         "> 评估标准见 `docs/PAPER_TRADING_PLAN.md`\n",
         "## 评估标准（必须全部达标才进实盘）\n",
         "| 指标 | 阈值 | 当前值 | 是否达标 |", "|---|---|---|---|",
         f"| 20D 胜率 | ≥ {TH_WIN}% | {win_rate:.1f}% | {ok(n and win_rate >= TH_WIN)} |",
         f"| 盈亏比 | ≥ {TH_RR} | {rr:.2f} | {ok(n and rr >= TH_RR)} |",
         f"| 期望值 | ≥ +{TH_EXP}%/笔 | {exp:+.2f}% | {ok(n and exp >= TH_EXP)} |",
         f"| 盈亏平衡所需盈亏比 | < 实际盈亏比 | {be_rr:.2f} vs {rr:.2f} | {ok(n and rr > be_rr)} |",
         f"| 最大回撤 | ≤ {TH_DD}% | {max_dd:.2f}% | {ok(n and max_dd >= TH_DD)} |",
         f"| 观察期 | ≥ {TH_DAYS} 交易日 | {days} 天 | {ok(days >= TH_DAYS)} |",
         ""]

    L += [f"## 当前持仓（未平仓）：{len(open_rows)} 只\n"]
    if open_rows:
        L += ["| Ticker | Entry_Date | Entry_Price | 当前价 | 浮盈% | Hold_Days |",
              "|---|---|---|---|---|---|"]
        for r in open_rows:
            ep = fnum(r.get("Entry_Price"))
            cur = last_price(r.get("Ticker", "").upper(), prices)
            pct = (cur / ep - 1) * 100 if (ep and cur) else float("nan")
            L.append(f"| {r.get('Ticker')} | {r.get('Entry_Date')} | {ep:.2f} | "
                     f"{cur:.2f} | {pct:+.2f}% | {r.get('Hold_Days') or '-'} |")
    else:
        L.append("（无持仓）")
    L.append("")

    L += ["## 已平仓统计\n", "| 指标 | 值 |", "|---|---|",
          f"| 总笔数 | {n} |",
          f"| 胜率 | {win_rate:.1f}% |" if n else "| 胜率 | N/A |",
          f"| 平均盈利 | {avg_win:.2f}% |" if wins else "| 平均盈利 | N/A |",
          f"| 平均亏损 | {avg_loss:.2f}% |" if losses else "| 平均亏损 | N/A |",
          f"| 盈亏比 | {rr:.2f} |" if n else "| 盈亏比 | N/A |",
          f"| 期望值 | {exp:+.2f}%/笔 |" if n else "| 期望值 | N/A |",
          f"| 盈亏平衡所需盈亏比 | {be_rr:.2f} |" if n else "| 盈亏平衡所需盈亏比 | N/A |",
          f"| 累计收益 | {cum:+.2f}% |",
          f"| 最大回撤 | {max_dd:.2f}% |",
          ""]

    L += ["## 已平仓明细\n"]
    if closed:
        L += ["| Ticker | Entry_Date | Exit_Date | Entry_Price | Exit_Price | PnL_Pct | Hold_Days | Reason |",
              "|---|---|---|---|---|---|---|---|"]
        for r in sorted(closed, key=lambda x: x.get("Exit_Date") or ""):
            L.append(f"| {r.get('Ticker')} | {r.get('Entry_Date')} | {r.get('Exit_Date')} | "
                     f"{fnum(r.get('Entry_Price')) or 0:.2f} | {fnum(r.get('Exit_Price')) or 0:.2f} | "
                     f"{fnum(r.get('PnL_Pct')) or 0:+.2f}% | {r.get('Hold_Days')} | {r.get('Reason')} |")
    else:
        L.append("（尚无平仓记录 —— 观察期刚启动）")
    L += ["", "---", "说明：本报告每日由 `scripts/paper_trading_report.py` 覆盖生成。", ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"[report] written {OUT.name} | 平仓 {n} 笔 / 在持 {len(open_rows)} 只")
    if n:
        print(f"[report] 胜率 {win_rate:.1f}% | 盈亏比 {rr:.2f} | 期望 {exp:+.2f}% | "
              f"累计 {cum:+.2f}% | 最大回撤 {max_dd:.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
