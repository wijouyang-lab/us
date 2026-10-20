#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Paper Trading 日报：只统计真实模拟成交；净收益包含滑点与佣金。"""
from __future__ import annotations

import csv
import math
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from scripts.paper_trading import SLIPPAGE_BPS, COMMISSION_BPS, PRICE_SCHEMA_VERSION
LEDGER = REPO / "portfolio_paper_transactions.csv"
PRICE_FILE = REPO / "quant_factor_price_history.csv"
OBSERVATIONS_FILE = REPO / "portfolio_paper_observation_dates.csv"
OUT = REPO / "docs" / "PAPER_TRADING_REPORT.md"

INITIAL_CAPITAL = 50000.0
TH_WIN = 55.0
TH_RR = 1.2
TH_EXP = 0.5
TH_DD = -5.0
TH_DAYS = 40
PLAN_START = "2026-10-19"
US_TZ = ZoneInfo("America/New_York")


def read_rows(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def read_prices(today: str):
    by_ticker: dict[str, list[tuple[str, float]]] = {}
    observed_dates = set()
    if not PRICE_FILE.exists():
        return by_ticker, []
    with PRICE_FILE.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "schema_version" not in reader.fieldnames:
            print("[paper-report] FAIL-CLOSED：价格历史没有 schema_version；当前价与浮盈亏不显示")
            return by_ticker, []
        rows = list(reader)
    versions = {str(r.get("schema_version") or "").strip() for r in rows}
    if not rows or versions != {PRICE_SCHEMA_VERSION}:
        print(
            "[paper-report] FAIL-CLOSED：价格历史不是全量 "
            f"{PRICE_SCHEMA_VERSION}（versions={sorted(versions)}）；"
            "当前价与未实现盈亏显示 N/A，需先完成全量历史重建"
        )
        return by_ticker, []
    for r in rows:
        tk = (r.get("Ticker") or "").strip().upper()
        d = (r.get("Date") or "").strip()
        px = fnum(r.get("Close"))
        if tk and d and px is not None and px > 0:
            by_ticker.setdefault(tk, []).append((d, px))
            if PLAN_START <= d <= today:
                observed_dates.add(d)
    for tk in by_ticker:
        by_ticker[tk].sort(key=lambda x: x[0])
        tmp = {d: px for d, px in by_ticker[tk]}
        by_ticker[tk] = sorted(tmp.items())
    return by_ticker, sorted(observed_dates)


def last_price(tk: str, prices: dict):
    series = prices.get(tk, [])
    return series[-1] if series else (None, None)


def read_observation_dates(today: str, path: Path = OBSERVATIONS_FILE) -> list[str]:
    """Return actual ET dates on which Paper Trading successfully wrote an observation."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    dates = set()
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            d = (row.get("Run_Date") or "").strip()
            try:
                parsed = datetime.strptime(d, "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                continue
            if PLAN_START <= parsed <= today:
                dates.add(parsed)
    return sorted(dates)


def estimated_net_unrealized(row: dict, current_close: float):
    shares = fnum(row.get("Shares"))
    entry = fnum(row.get("Entry_Price"))
    entry_fee = fnum(row.get("Entry_Commission")) or 0.0
    if not shares or not entry or not current_close:
        return None, None
    estimated_exit = current_close * (1.0 - SLIPPAGE_BPS / 10000.0)
    exit_fee = estimated_exit * shares * COMMISSION_BPS / 10000.0
    net = (estimated_exit - entry) * shares - entry_fee - exit_fee
    denominator = entry * shares + entry_fee
    return net, (net / denominator * 100.0 if denominator > 0 else None)


def drawdown_gate_pass(closed_trade_count: int, max_drawdown_pct: float) -> bool:
    """A drawdown threshold cannot pass until at least one closed trade exists."""
    return closed_trade_count > 0 and max_drawdown_pct >= TH_DD


def fmt_pct(v, decimals=2):
    return "N/A" if v is None or not math.isfinite(v) else f"{v:+.{decimals}f}%"


def fmt_num(v, decimals=2):
    return "N/A" if v is None or not math.isfinite(v) else f"{v:.{decimals}f}"


def main() -> int:
    today = datetime.now(US_TZ).strftime("%Y-%m-%d")
    rows = read_rows(LEDGER)
    prices, _price_dates = read_prices(today)

    open_rows = [
        r for r in rows
        if (r.get("Action") or "").upper() == "BUY"
        and not r.get("Exit_Date")
        and fnum(r.get("Entry_Price")) is not None
    ]
    pending_rows = [r for r in rows if (r.get("Action") or "").upper() == "PENDING"]
    closed = [
        r for r in rows
        if (r.get("Action") or "").upper() == "SELL"
        and r.get("Exit_Date")
        and fnum(r.get("PnL_Pct")) is not None
    ]

    pcts = [fnum(r.get("PnL_Pct")) for r in closed]
    pcts = [p for p in pcts if p is not None]
    wins = [p for p in pcts if p > 0]
    losses = [p for p in pcts if p <= 0]
    n = len(pcts)
    win_rate = len(wins) / n * 100 if n else None
    avg_win = sum(wins) / len(wins) if wins else None
    avg_loss = abs(sum(losses) / len(losses)) if losses else None
    rr = avg_win / avg_loss if avg_win is not None and avg_loss not in (None, 0) else None
    exp = sum(pcts) / n if n else None
    be_rr = ((100 - win_rate) / win_rate) if win_rate is not None and win_rate > 0 else None

    pnl_sum = sum(fnum(r.get("PnL")) or 0.0 for r in closed)
    cum = pnl_sum / INITIAL_CAPITAL * 100
    peak = 0.0
    run = 0.0
    dd = 0.0
    for r in sorted(closed, key=lambda x: x.get("Exit_Date") or ""):
        run += fnum(r.get("PnL")) or 0.0
        peak = max(peak, run)
        dd = min(dd, run - peak)
    max_dd = dd / INITIAL_CAPITAL * 100
    observation_dates = read_observation_dates(today)
    days = len(observation_dates)
    observation_range = (
        f"{observation_dates[0]} 至 {observation_dates[-1]}"
        if observation_dates else "尚无成功运行记录"
    )

    def ok(cond):
        return "PASS" if cond else "NOT MET"

    L = [
        f"# Paper Trading 日报 — {today}\n",
        "> 数据源：portfolio_paper_transactions.csv + quant_factor_price_history.csv",
        "> 本报告只统计已成交模拟交易；PENDING 不算持仓，VOID 不参与业绩。所有 PnL 为扣除模型滑点与佣金后的净值。\n",
        "> 观察期按 Paper Trading 在 Scan 成功后实际运行的 ET 日期统计；本轮实际记录区间会按观察日志计算，仅有行情数据但没有成功运行记录的日期不计入。\n",
        f"> 模型成本：单边滑点 {SLIPPAGE_BPS:.1f} bps；单边佣金 {COMMISSION_BPS:.1f} bps。成本为研究假设，不代表任何特定券商实际费率。\n",
        "## 评估门槛\n",
        "| 指标 | 要求 | 当前值 | 状态 |",
        "|---|---|---|---|",
        f"| 已平仓胜率 | ≥ {TH_WIN:.1f}% | {fmt_num(win_rate, 1) + ('%' if win_rate is not None else '')} | {ok(win_rate is not None and win_rate >= TH_WIN)} |",
        f"| 盈亏比 | ≥ {TH_RR:.2f} | {fmt_num(rr, 2)} | {ok(rr is not None and rr >= TH_RR)} |",
        f"| 平均净期望值 | ≥ +{TH_EXP:.2f}%/笔 | {fmt_pct(exp)} | {ok(exp is not None and exp >= TH_EXP)} |",
        f"| 盈亏平衡所需盈亏比 | < 实际盈亏比 | {fmt_num(be_rr, 2)} vs {fmt_num(rr, 2)} | {ok(be_rr is not None and rr is not None and rr > be_rr)} |",
        f"| 最大回撤 | 不低于 {TH_DD:.2f}% | {fmt_pct(max_dd) if n else 'N/A'} | {ok(drawdown_gate_pass(n, max_dd))} |",
        f"| 成功 Scan 观察日 | ≥ {TH_DAYS} 日 | {days} 日（实际记录区间：{observation_range}） | {ok(days >= TH_DAYS)} |",
        "\n任一项未达标或样本不足，都不构成转实盘依据。\n",
        f"## 当前持仓：{len(open_rows)} 只\n",
    ]
    if open_rows:
        L += [
            "| Ticker | 信号日 | 成交日 | 参考开盘 | 模拟成交价 | 最新收盘日 | 最新收盘 | 估算净浮盈亏 | 净浮盈亏% |",
            "|---|---|---|---:|---:|---|---:|---:|---:|",
        ]
        for r in open_rows:
            tk = (r.get("Ticker") or "").upper()
            d, cur = last_price(tk, prices)
            net, pct = estimated_net_unrealized(r, cur) if cur is not None else (None, None)
            L.append(
                f"| {tk} | {r.get('Signal_Date') or '-'} | {r.get('Entry_Date') or '-'} | "
                f"{fmt_num(fnum(r.get('Reference_Entry_Price')))} | {fmt_num(fnum(r.get('Entry_Price')))} | "
                f"{d or 'N/A'} | {fmt_num(cur)} | {fmt_num(net)} | {fmt_pct(pct)} |"
            )
    else:
        L.append("（无已成交持仓）")
    L.append("")

    L += [f"## 待成交信号：{len(pending_rows)} 条\n"]
    if pending_rows:
        L += ["| Ticker | 信号日 | 当前状态 |", "|---|---|---|"]
        for r in pending_rows:
            L.append(f"| {r.get('Ticker')} | {r.get('Signal_Date') or '-'} | {r.get('Reason') or '等待下一交易日有效开盘价'} |")
    else:
        L.append("（无待成交信号）")
    L.append("")

    L += [
        "## 已平仓净绩效\\n",
        "| 指标 | 值 |",
        "|---|---:|",
        f"| 已平仓交易数 | {n} |",
        f"| 胜率 | {fmt_num(win_rate, 1) + ('%' if win_rate is not None else '')} |",
        f"| 平均盈利 | {fmt_pct(avg_win)} |",
        f"| 平均亏损 | {fmt_pct(-avg_loss) if avg_loss is not None else 'N/A'} |",
        f"| 盈亏比 | {fmt_num(rr, 2)} |",
        f"| 平均每笔净期望值 | {fmt_pct(exp)} |",
        f"| 总净盈亏 | {pnl_sum:+.2f} USD |",
        f"| 相对初始资金净收益 | {fmt_pct(cum)} |",
        f"| 已平仓权益曲线最大回撤 | {fmt_pct(max_dd) if n else 'N/A'} |",
        "",
    ]

    L += ["## 已平仓明细\\n"]
    if closed:
        L += [
            "| Ticker | 信号日 | 成交日 | 退出日 | 买入成交价 | 卖出成交价 | 净 PnL USD | 净收益率 | 持有交易日 | 退出原因 |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---|",
        ]
        for r in sorted(closed, key=lambda x: x.get("Exit_Date") or ""):
            L.append(
                f"| {r.get('Ticker', '')} | {r.get('Signal_Date') or '-'} | "
                f"{r.get('Entry_Date') or '-'} | {r.get('Exit_Date') or '-'} | "
                f"{fmt_num(fnum(r.get('Entry_Price')))} | {fmt_num(fnum(r.get('Exit_Price')))} | "
                f"{fmt_num(fnum(r.get('PnL')))} | {fmt_pct(fnum(r.get('PnL_Pct')))} | "
                f"{r.get('Hold_Days') or '-'} | {r.get('Reason') or '-'} |"
            )
    else:
        L.append("（尚无有效平仓记录）")

    L += [
        "",
        "## 数据质量提示\\n",
        "- 成交价取信号日之后首个有有效 Open 的完整日线；若不存在，订单留在 PENDING，绝不退回旧收盘价。",
        "- 净 PnL 已含进出场滑点和佣金；尚未包含可能的税费、借券费、市场冲击与券商特定收费。",
        "- 20 个持有交易日根据价格数据中的实际交易日计数，而非只跳过周末的日历近似。",
        "- VOID 交易保留审计痕迹，不纳入胜率、持仓或盈亏统计。",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"written: {OUT} (closed={n}, open={len(open_rows)}, pending={len(pending_rows)}, observation_days={days})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
