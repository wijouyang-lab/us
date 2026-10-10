#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""$50,000 Long-Term Portfolio Ledger（长期模拟投资组合账本）

设计原则
--------
1. **只做镜像，不发明交易逻辑**
   - 买入价：直接取 trade_history.Price（= 推荐日真实 Open，项目正式定义）
   - 卖出：完全沿用 Review 已裁决的终态 Status + Exit_Price，本模块**不实现第二套止损**
   - 标的资格：只认 Tag == Core_Dragon（Observation 不进 Portfolio）

2. **现金/权益/盈亏全部由 Transaction Ledger 确定性推导**
   - Cash = 50000.00 - Σ(BUY.amount) + Σ(SELL.amount)
   - 现金不作为独立状态保存 → 物理上不可能被"每日重置"
   - Initial Capital 只在 meta 文件不存在时写入一次

3. **幂等**
   - BUY 幂等键：Ticker|Rec_Date|Tag|BUY
   - SELL 幂等键：Ticker|Rec_Date|Tag|SELL|Exit_Date
   - History 同一天 upsert，不产生重复快照

4. **金额全程 Decimal，落盘 2 位小数**；股数为整数

用法：python portfolio_50000.py [--data-dir .]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, InvalidOperation
from pathlib import Path

# ------------------------------------------------------------------ 常量
PORTFOLIO_ID = "US-50000-001"
INITIAL_CAPITAL = Decimal("50000.00")
UNIT_DOLLARS = Decimal("10000.00")          # 1 Unit 回退基准（#4：评分缺失时仍用 1 Unit，向后兼容）
MAX_OPEN_POSITIONS_DEPRECATED = 4           # 仅历史参考：#4 起不再作硬守卫（改为浮动 3-5 + 百分比仓位）
UNIT_IDS = ["U001", "U002", "U003", "U004"]

CORE_TAG = "Core_Dragon"
# Review 已写入 Exit_Date / Exit_Price 的终态（出现新状态只需在此登记，不改逻辑）
TERMINAL_STATUSES = {
    "Stop_Loss_Hit", "Dropped", "Period_Matured", "Observation_Closed",
    "Target_Reached", "Closed", "Exited",
}

META_FILE = "portfolio_50000_meta.json"
POSITIONS_FILE = "portfolio_50000_positions.csv"
TRANSACTIONS_FILE = "portfolio_50000_transactions.csv"
HISTORY_FILE = "portfolio_50000_history.csv"

POSITION_COLUMNS = [
    "Portfolio_ID", "Unit_ID", "Ticker", "Shares", "Entry_Price", "Entry_Date",
    "Cost_Basis", "Current_Price", "Extended_Price", "Extended_Time", "Market_Value", "Unrealized_PnL",
    "Unrealized_PnL_Pct", "Weight_Pct", "Status", "Stop_Loss",
    "Recommendation_ID", "Last_Update", "Cooldown_Until",
]
TRANSACTION_COLUMNS = [
    "Txn_ID", "Date", "Ticker", "Action", "Shares", "Price", "Amount",
    "Realized_PnL", "Cash_After", "Reason", "Recommendation_ID", "Scan_Date",
    "Portfolio_ID", "Unit_ID", "Pending_Reason",
]
HISTORY_COLUMNS = [
    "Date", "Cash", "Stock_Value", "Total_Equity", "Realized_PnL",
    "Unrealized_PnL", "Total_PnL", "Return_Pct", "Open_Positions", "Portfolio_ID",
]

ZERO = Decimal("0")
CENT = Decimal("0.01")


# ------------------------------------------------------------------ 工具
def money(v) -> Decimal:
    """转为 Decimal 并quantize 到 2 位小数（金额落盘/展示统一口径）。"""
    try:
        if v is None or v == "":
            return ZERO.quantize(CENT)
        if isinstance(v, Decimal):
            d = v
        else:
            d = Decimal(str(v))
        if not d.is_finite():
            return ZERO.quantize(CENT)
        return d.quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return ZERO.quantize(CENT)


def dec(v) -> Decimal | None:
    """宽松解析为 Decimal；不可解析返回 None（绝不用 0 顶替缺价）。"""
    try:
        if v is None or v == "":
            return None
        d = Decimal(str(v).replace(",", "").strip())
        return d if d.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def us_today_str() -> str:
    """美东当前日期 YYYY-MM-DD（Portfolio 交易日口径）。"""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        # 兜底：UTC-5（不引入额外依赖，且仅影响日期，不影响任何价格）
        from datetime import timedelta, timezone
        return datetime.now(timezone.utc - timedelta(hours=5)).strftime("%Y-%m-%d")


# ------------------------------------------------------------------ 买入冷却
COOLDOWN_DAYS = 7   # 止损后同名 ticker 冷却天数


def _cooldown_until(today: str, days: int = COOLDOWN_DAYS) -> str:
    """止损冷却到期日 = 止损日 + days 天（默认 7）。today 为 YYYY-MM-DD。"""
    from datetime import datetime as _dt, timedelta as _td
    try:
        d = _dt.strptime(today, "%Y-%m-%d").date() + _td(days=days)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return ""   # 解析失败不写，避免脏值


def _load_cooldowns(positions: list[dict]) -> dict[str, str]:
    """从 positions 收集仍有效的止损冷却到期日 {TICKER: 'YYYY-MM-DD'}。
    CLOSED 行仍保留 Cooldown_Until；空值忽略（旧数据自动跳过）。"""
    out: dict[str, str] = {}
    for p in positions:
        cd = str(p.get("Cooldown_Until", "")).strip()
        if cd:
            out[str(p.get("Ticker", "")).upper()] = cd
    return out


def _ymd_shift(today: str, days: int) -> str:
    """today(YYYY-MM-DD) 平移 days 天，返回同格式字符串（days 可为负）。"""
    from datetime import datetime as _dt, timedelta as _td
    try:
        return (_dt.strptime(today, "%Y-%m-%d").date() + _td(days=days)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _recent_stop_tickers(transactions: list[dict], today: str) -> set[str]:
    """近 1–2 日（today 与 yesterday）发生 'Intraday Stop Loss' 的 ticker 集合。"""
    yest = _ymd_shift(today, -1)
    out: set[str] = set()
    for t in transactions:
        if str(t.get("Action", "")).upper() != "SELL":
            continue
        if str(t.get("Reason", "")) != "Intraday Stop Loss":
            continue
        d = str(t.get("Date", ""))
        if d == today or d == yest:
            out.add(str(t.get("Ticker", "")).upper())
    return out


def _had_stop_today(transactions: list[dict], today: str) -> bool:
    """今日是否发生过任意 'Intraday Stop Loss' 卖出（用于全清仓停手判断）。"""
    return any(
        str(t.get("Action", "")).upper() == "SELL"
        and str(t.get("Reason", "")) == "Intraday Stop Loss"
        and str(t.get("Date", "")) == today
        for t in transactions
    )


# ------------------------------------------------------------------ #4 浮动只数 + 百分比仓位
def _stock_pct(positions: list[dict], transactions: list[dict]) -> Decimal:
    """当前总股票市值 / 总资产（现金 + 股票）。期权由期权引擎另计，不在此口径。"""
    cash = derive_cash(transactions)
    stock = ZERO
    for p in positions:
        if str(p.get("Status", "")).upper() == "OPEN":
            stock += dec(p.get("Market_Value")) or ZERO
    total = cash + stock
    return (stock / total) if total > 0 else ZERO


def unit_dollars_for(rec: dict, equity: Decimal) -> Decimal:
    """#4 按信号强度动态 Unit：评分越高单只可配越多；但缺评分时退化为固定 1 Unit（向后兼容）。

    单只受 25% 上限钳制。rec 当前无 AI_Score 字段（评分链路未落地）→ 返回 UNIT_DOLLARS，
    行为与 v1 完全一致（见 WEEKEND_IMPLEMENTATION_PLAN §4.7「未落地时退化为固定 1 Unit」）。
    评分链路落地后：factor = clamp((score-60)/30 + 0.5, 0.5, 1.25)（60→0.5U, 90→1.25U, 100→1.25U）。
    """
    score = rec.get("AI_Score")
    try:
        score = float(score) if score is not None else None
    except (TypeError, ValueError):
        score = None
    if score is None or score <= 0:
        return min(UNIT_DOLLARS, equity * Decimal("0.25"))   # 向后兼容：1 Unit
    factor = max(Decimal("0.5"),
                 min(Decimal("1.25"),
                     (Decimal(str(score)) - 60) / Decimal("30") + Decimal("0.5")))
    size = UNIT_DOLLARS * factor
    return min(size, equity * Decimal("0.25"))


def _within_alloc(rec: dict, positions: list[dict], transactions: list[dict],
                  equity: Decimal) -> tuple[bool, str]:
    """#4 四维占比预审（股票侧）：单只≤25% / 总股票≤80%。
    返回 (ok, 原因)。期权≤15% 与现金≥5% 由期权引擎 / 预算双保险兜底，本函数只挡股票侧超配。"""
    stock_pct = _stock_pct(positions, transactions)
    new_size = unit_dollars_for(rec, equity)
    proj_stock = stock_pct * equity + new_size
    if new_size > equity * Decimal("0.25"):
        return False, "单只将超 25%"
    if proj_stock > equity * Decimal("0.80"):
        return False, "总股票将超 80%"
    return True, ""


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            return [dict(r) for r in csv.DictReader(f)]
    except Exception as e:
        print(f"⚠️ 读取 {path.name} 失败：{e}")
        return []


def write_csv_rows(path: Path, columns: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in columns})


def rec_id_of(ticker: str, rec_date: str, tag: str) -> str:
    return f"{str(ticker).upper()}|{rec_date}|{tag}"


# ------------------------------------------------------------------ 价格
def _fmt_ext_time(ts) -> str:
    """把 yfinance 返回的（通常为 tz-aware）时间戳格式化为 'MM-DD HH:MM ET'。失败留空。"""
    if ts is None:
        return ""
    try:
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")
        dt_et = ts.astimezone(et)
        return dt_et.strftime("%m-%d %H:%M ET")
    except Exception:
        try:
            return str(ts)
        except Exception:
            return ""


def _fetch_extended_price(ticker: str, yf) -> tuple[Decimal | None, str]:
    """含盘前/盘后的最新成交价（prepost=True，1 分钟粒度）。失败返回 (None, '')，绝不抛错。"""
    try:
        df_ext = yf.Ticker(ticker).history(period="1d", interval="1m", prepost=True)
        if df_ext is None or len(df_ext) == 0:
            return None, ""
        series = df_ext["Close"].dropna()
        if series.empty:
            return None, ""
        px = dec(series.iloc[-1])
        ts = df_ext.index[-1] if hasattr(df_ext.index, "__getitem__") else None
        return (px if px is not None and px > 0 else None), _fmt_ext_time(ts)
    except Exception:
        return None, ""


def fetch_last_closes(tickers: list[str]) -> dict[str, dict]:
    """取最新价。返回 {TICKER: {"current": Decimal|None, "extended": Decimal|None, "extended_time": str}}。

    - current：常规时段收盘价（prepost=False，EOD 基准），取不到则该 ticker 不入表。
    - extended：含盘前/盘后的最新成交价（prepost=True）；失败留空，不影响 current。
    取不到任何价时返回空 dict —— 由调用方回退到上一快照价格，绝不编造。
    """
    out: dict[str, dict] = {}
    if not tickers:
        return out
    try:
        import yfinance as yf  # 与 review.py 同一数据源
    except Exception:
        return out
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period="5d", auto_adjust=False)
            if hist is None or hist.empty:
                continue
            series = hist["Close"].dropna()
            if series.empty:
                continue
            current = dec(series.iloc[-1])
            if current is None or current <= 0:
                continue
            extended, ext_time = _fetch_extended_price(t, yf)
            out[t.upper()] = {
                "current": current,
                "extended": extended,
                "extended_time": ext_time,
            }
        except Exception:
            continue
    return out


# ------------------------------------------------------------------ 核心逻辑
def ensure_meta(data_dir: Path, today: str) -> dict:
    """初始化即幂等：文件已存在时绝不重写 initial_capital / start_date。"""
    p = data_dir / META_FILE
    if p.exists():
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
            if m.get("initial_capital") and m.get("start_date"):
                return m
        except Exception:
            pass  # 损坏则重建，但 start_date 仍取当前日，不虚构历史
    meta = {
        "portfolio_id": PORTFOLIO_ID,
        "initial_capital": str(INITIAL_CAPITAL),
        "start_date": today,
        "unit_dollars": str(UNIT_DOLLARS),
        "max_open_positions": MAX_OPEN_POSITIONS_DEPRECATED,  # 仅历史字段，#4 起不再作硬守卫
        "currency": "USD",
    }
    p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"🆕 Portfolio 初始化：{PORTFOLIO_ID}  初始本金 ${INITIAL_CAPITAL}  起始日 {today}")
    return meta


def derive_cash(transactions: list[dict]) -> Decimal:
    """现金完全由交易流水推导 —— 不保存余额快照，杜绝每日重置。"""
    cash = INITIAL_CAPITAL
    for t in transactions:
        amt = dec(t.get("Amount")) or ZERO
        if str(t.get("Action", "")).upper() == "BUY":
            cash -= amt
        elif str(t.get("Action", "")).upper() == "SELL":
            cash += amt
    return cash.quantize(CENT, rounding=ROUND_HALF_UP)


def load_recommendations(data_dir: Path) -> dict[str, dict]:
    """从 trade_history 读取推荐事件（只读）。key = Recommendation_ID。"""
    rows = read_csv_rows(data_dir / "trade_history.csv")
    out: dict[str, dict] = {}
    for r in rows:
        ticker = str(r.get("Ticker", "")).upper().strip()
        rec_date = str(r.get("Date", "")).strip()
        tag = str(r.get("Tag", "")).strip()
        if not ticker or not rec_date:
            continue
        rid = rec_id_of(ticker, rec_date, tag)
        out[rid] = {
            "Recommendation_ID": rid,
            "Ticker": ticker,
            "Rec_Date": rec_date,
            "Tag": tag,
            "Price": dec(r.get("Price")),
            "Status": str(r.get("Status", "")).strip(),
            "Exit_Date": str(r.get("Exit_Date", "")).strip(),
            "Exit_Price": dec(r.get("Exit_Price")),
            "Stop_Loss": str(r.get("Stop_Loss", "")).strip(),
        }
    return out


def next_free_unit(positions: list[dict]) -> str | None:
    used = {str(p.get("Unit_ID", "")).upper()
            for p in positions if str(p.get("Status", "")).upper() == "OPEN"}
    for uid in UNIT_IDS:
        if uid not in used:
            return uid
    return None


def process_sells(positions, transactions, recs, today) -> list[str]:
    """SELL：完全沿用 Review 的终态裁决 + Exit_Price。不实现第二套止损。"""
    log: list[str] = []
    existing_txn = {str(t.get("Txn_ID", "")) for t in transactions}
    for p in positions:
        if str(p.get("Status", "")).upper() != "OPEN":
            continue
        rid = str(p.get("Recommendation_ID", ""))
        rec = recs.get(rid)
        if not rec:
            continue
        if rec["Status"] not in TERMINAL_STATUSES:
            continue
        exit_px = rec["Exit_Price"]
        exit_date = rec["Exit_Date"]
        # fail-safe：退出价/退出日缺失时不卖，等 Review 补齐（绝不猜测价格）
        if exit_px is None or exit_px <= 0 or not exit_date:
            log.append(f"⏸  {p.get('Ticker')} 已终态({rec['Status']})但缺 Exit_Price/Exit_Date，暂不卖出")
            continue
        shares = int(dec(p.get("Shares")) or 0)
        if shares <= 0:
            continue
        entry = dec(p.get("Entry_Price")) or ZERO
        txn_id = f"{rid}|SELL|{exit_date}"
        if txn_id in existing_txn:
            continue
        realized = (exit_px - entry) * Decimal(shares)
        amount = exit_px * Decimal(shares)
        transactions.append({
            "Txn_ID": txn_id,
            "Date": exit_date,
            "Ticker": p.get("Ticker", ""),
            "Action": "SELL",
            "Shares": str(shares),
            "Price": str(money(exit_px)),
            "Amount": str(money(amount)),
            "Realized_PnL": str(money(realized)),
            "Cash_After": "",   # 全部 transaction 写完后统一回填
            "Reason": f"Review exit: {rec['Status']}",
            "Recommendation_ID": rid,
            "Scan_Date": rec["Rec_Date"],
            "Portfolio_ID": PORTFOLIO_ID,
            "Unit_ID": p.get("Unit_ID", ""),
        })
        existing_txn.add(txn_id)
        p["Shares"] = "0"
        p["Status"] = "CLOSED"
        p["Current_Price"] = str(money(exit_px))
        p["Market_Value"] = "0.00"
        p["Unrealized_PnL"] = "0.00"
        p["Unrealized_PnL_Pct"] = "0.00"
        p["Weight_Pct"] = "0.00"
        p["Last_Update"] = today
        if rec["Status"] == "Stop_Loss_Hit":          # 新增：仅止损才冷却
            p["Cooldown_Until"] = _cooldown_until(today)
        log.append(f"💰 SELL {p.get('Ticker')} {shares}股 @ {money(exit_px)}（{rec['Status']}） 已实现盈亏 {money(realized)}")
    return log


def process_buys(positions, transactions, recs, meta, today) -> list[str]:
    """BUY：新 Core 推荐、未持有、有空闲 Unit、现金足够 → 买 1 Unit。
    含三道买入冷却闸门：全清仓停手 / 7 天字段冷却 / 近 1-2 日止损防御。"""
    log: list[str] = []
    start_date = str(meta.get("start_date", ""))
    existing_txn = {str(t.get("Txn_ID", "")) for t in transactions}
    open_tickers = {str(p.get("Ticker", "")).upper()
                    for p in positions if str(p.get("Status", "")).upper() == "OPEN"}
    open_count = sum(1 for p in positions if str(p.get("Status", "")).upper() == "OPEN")
    cash = derive_cash(transactions)
    # 总资产（现金 + 现有 OPEN 股票市值）：买入不改变总资产（现金↔股票互换），循环内恒定。
    equity = cash + sum((dec(p.get("Market_Value")) or ZERO)
                        for p in positions
                        if str(p.get("Status", "")).upper() == "OPEN")

    # —— 闸门 0：全清仓当天停手 ——
    # 持仓已全 CLOSED 且今日发生过盘中/盘后止损 → 当日不再新开买入（防反复止损）。
    if open_count == 0 and _had_stop_today(transactions, today):
        log.append("⏸  今日已全清仓（含止损）→ 当日停手，不再新开买入")
        return log

    # —— 闸门 1 数据：7 天字段冷却 + 近 1-2 日止损防御 ——
    cooldowns = _load_cooldowns(positions)                       # {TICKER: "YYYY-MM-DD"}
    stopped_recent = _recent_stop_tickers(transactions, today)    # 止损当天+次日

    # 按推荐日期升序处理，保证先来的推荐先占用 Unit（确定性，不受 dict 顺序影响）
    candidates = [r for r in recs.values()
                  if r["Tag"] == CORE_TAG
                  and r["Status"] == "Active"
                  and r["Rec_Date"] >= start_date
                  and r["Price"] is not None and r["Price"] > 0]
    candidates.sort(key=lambda r: (r["Rec_Date"], r["Ticker"]))

    for rec in candidates:
        rid = rec["Recommendation_ID"]
        buy_id = f"{rid}|BUY"
        if buy_id in existing_txn:
            continue                      # 幂等：同一推荐只买一次
        if rec["Ticker"] in open_tickers:
            log.append(f"⏸  {rec['Ticker']} 已持仓 → HOLD（不重复买入）")
            continue

        # —— 闸门 1：7 天字段冷却 ——
        cd = cooldowns.get(rec["Ticker"])
        if cd and today <= cd:
            log.append(f"⏸  {rec['Ticker']} 处于止损冷却期（至 {cd}）→ 跳过")
            continue
        # —— 闸门 2：近 1-2 日刚止损（防御，覆盖旧数据无 Cooldown_Until 的情况）——
        if rec["Ticker"] in stopped_recent:
            log.append(f"⏸  {rec['Ticker']} 近 1–2 日刚止损 → 暂不复买（防御）")
            continue

        # —— 闸门 3：浮动只数 + 百分比仓位（#4）——
        # 原「固定 4 只 × 固定 1 Unit」硬守卫已移除；改为四维占比预审：
        # 单只≤25% / 总股票≤80%（期权≤15% 与现金≥5% 由期权引擎/预算双保险兜底）。
        ok, why = _within_alloc(rec, positions, transactions, equity)
        if not ok:
            log.append(f"⏸  {rec['Ticker']} 占比约束拦截（{why}）→ 跳过")
            continue
        price = rec["Price"]
        target = unit_dollars_for(rec, equity)
        shares = int((target / price).to_integral_value(rounding=ROUND_DOWN))
        if shares < 1:
            log.append(f"⏸  {rec['Ticker']} 单价 {money(price)} 超过目标仓位 {money(target)} → 跳过")
            continue
        amount = money(Decimal(shares) * price)
        if amount > target:        # 双保险：绝不超目标仓位
            shares -= 1
            if shares < 1:
                continue
            amount = money(Decimal(shares) * price)
        if amount > cash:
            log.append(f"⏸  {rec['Ticker']} 现金不足（需 {amount}，可用 {money(cash)}）→ 跳过")
            continue
        unit = next_free_unit(positions)
        if unit is None:
            log.append(f"⏸  {rec['Ticker']} 无空闲 Unit → 跳过")
            continue
        transactions.append({
            "Txn_ID": buy_id,
            "Date": rec["Rec_Date"],
            "Ticker": rec["Ticker"],
            "Action": "BUY",
            "Shares": str(shares),
            "Price": str(money(price)),
            "Amount": str(amount),
            "Realized_PnL": "0.00",
            "Cash_After": "",
            "Reason": "Core recommendation -> 1 Unit long",
            "Recommendation_ID": rid,
            "Scan_Date": rec["Rec_Date"],
            "Portfolio_ID": PORTFOLIO_ID,
            "Unit_ID": unit,
        })
        existing_txn.add(buy_id)
        positions.append({
            "Portfolio_ID": PORTFOLIO_ID,
            "Unit_ID": unit,
            "Ticker": rec["Ticker"],
            "Shares": str(shares),
            "Entry_Price": str(money(price)),      # 买入价永久固定，之后永不更新
            "Entry_Date": rec["Rec_Date"],
            "Cost_Basis": str(amount),
            "Current_Price": str(money(price)),
            "Market_Value": str(amount),
            "Unrealized_PnL": "0.00",
            "Unrealized_PnL_Pct": "0.00",
            "Weight_Pct": "0.00",
            "Status": "OPEN",
            "Stop_Loss": rec["Stop_Loss"],
            "Recommendation_ID": rid,
            "Last_Update": today,
        })
        open_tickers.add(rec["Ticker"])
        open_count += 1
        cash -= amount
        log.append(f"🛒 BUY {rec['Ticker']} {shares}股 @ {money(price)} = {amount}（{unit}）")
    return log


def mark_to_market(positions, prices: dict[str, dict], today: str):
    """盯市：更新 OPEN 仓位的市值与浮盈 + 扩展时段价。取不到价则沿用上一快照价格（不编造）。"""
    stock_value = ZERO
    unrealized = ZERO
    for p in positions:
        if str(p.get("Status", "")).upper() != "OPEN":
            continue
        tkr = str(p.get("Ticker", "")).upper()
        shares = int(dec(p.get("Shares")) or 0)
        entry = dec(p.get("Entry_Price")) or ZERO
        info = prices.get(tkr) or {}
        px = info.get("current")
        if px is None:
            px = dec(p.get("Current_Price"))      # 回退：上一快照价
        if px is None or px <= 0:
            px = entry                            # 最后兜底：成本价（0 浮盈，下次刷新校正）
        # 扩展时段价（盘前/盘后），失败留空，不影响 Current_Price / 市值
        ext = info.get("extended")
        ext_time = info.get("extended_time") or ""
        mv = money(Decimal(shares) * px)
        upl = money(Decimal(shares) * (px - entry))
        upl_pct = ((px - entry) / entry * Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP) if entry > 0 else ZERO
        p["Current_Price"] = str(money(px))
        # 扩展时段价：本次取不到（限流/无成交）时保留上一快照值，绝不擦掉已拿到的好值。
        old_ext = str(p.get("Extended_Price") or "").strip()
        if ext is None and old_ext:
            p["Extended_Price"] = old_ext
            p["Extended_Time"] = str(p.get("Extended_Time") or "").strip()
        else:
            p["Extended_Price"] = "" if ext is None else str(money(ext))
            p["Extended_Time"] = "" if not ext_time else str(ext_time)
        p["Market_Value"] = str(mv)
        p["Unrealized_PnL"] = str(upl)
        p["Unrealized_PnL_Pct"] = str(upl_pct)
        p["Last_Update"] = today
        stock_value += mv
        unrealized += upl
    return stock_value.quantize(CENT), unrealized.quantize(CENT)


def fill_weights(positions, total_equity: Decimal):
    for p in positions:
        if str(p.get("Status", "")).upper() != "OPEN":
            p["Weight_Pct"] = "0.00"
            continue
        mv = dec(p.get("Market_Value")) or ZERO
        w = (mv / total_equity * Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP) if total_equity > 0 else ZERO
        p["Weight_Pct"] = str(w)


def upsert_history(history: list[dict], row: dict):
    """同一交易日只保留一行（upsert），保证重复运行不产生重复快照。"""
    for i, h in enumerate(history):
        if str(h.get("Date", "")) == row["Date"]:
            history[i] = row
            return
    history.append(row)


# ------------------------------------------------------------------ 盘中机械止损
MAX_INTRADAY_STOPS_PER_DAY = 2          # 单日最多止损 2 只（决策 2）
INTRADAY_SESSION_OPEN = (9, 30)         # 09:30 ET
INTRADAY_SESSION_CLOSE = (16, 0)        # 16:00 ET（不含）


def _et_now():
    """美东当前时间（供时段守卫；无需联网）。失败时回退 EDT（UTC-4）。"""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        from datetime import timezone, timedelta
        return datetime.now(timezone.utc - timedelta(hours=4))


def _run_intraday_stop(data_dir: Path, today: str, offline: bool,
                       now_et=None) -> dict:
    """盘中机械止损：检查 OPEN 持仓，实时价 ≤ Stop_Loss 则机械卖出。

    设计约束（只加不改）：
      · 不调用 process_buys / process_sells —— 只做"检查 + 卖"；
      · 执行价 = 触发时实时价（fetch_last_closes 的 current，prepost=False）；
      · 取不到实时价 → 不触发（绝不猜价，与 Review DATA_MISSING 一致）；
      · 单日最多止损 2 只；全部持仓 CLOSED → 不再触发；已 CLOSED/已今日止损的不重复处理；
      · 触发写 transactions（Reason="Intraday Stop Loss", Pending_Reason="True" 待 AI 补原因）；
      · 时段守卫：仅 09:30 ≤ ET < 16:00 执行，其他时间静默退出（exit 0）。
    """
    from datetime import time as _dtime
    now = now_et if now_et is not None else _et_now()
    oh, om = INTRADAY_SESSION_OPEN
    ch, cm = INTRADAY_SESSION_CLOSE
    if not (_dtime(oh, om) <= now.time() < _dtime(ch, cm)):
        print("[intraday-stop] 非交易时段（09:30-16:00 ET），静默退出")
        return {"triggered": 0, "total_equity": None, "positions": []}

    positions = read_csv_rows(data_dir / POSITIONS_FILE)
    transactions = read_csv_rows(data_dir / TRANSACTIONS_FILE)
    open_pos = [p for p in positions if str(p.get("Status", "")).upper() == "OPEN"]
    if not open_pos:
        print("[intraday-stop] 无 OPEN 持仓，跳过")
        return {"triggered": 0, "total_equity": None, "positions": []}

    open_tickers = sorted({str(p.get("Ticker", "")).upper() for p in open_pos})
    prices = {} if offline else fetch_last_closes(open_tickers)

    existing_txn = {str(t.get("Txn_ID", "")) for t in transactions}
    # 今日已盘中止损数（与本次本批次计数合计，封顶单日上限）
    stopped_today = sum(
        1 for t in transactions
        if str(t.get("Action", "")).upper() == "SELL"
        and str(t.get("Reason", "")) == "Intraday Stop Loss"
        and str(t.get("Date", "")) == today
    )

    triggered = 0
    new_txns: list[dict] = []
    for p in sorted(open_pos, key=lambda x: str(x.get("Ticker", "")).upper()):
        if stopped_today + triggered >= MAX_INTRADAY_STOPS_PER_DAY:
            print(f"[intraday-stop] 已达单日上限 {MAX_INTRADAY_STOPS_PER_DAY} 只，停止触发")
            break
        tkr = str(p.get("Ticker", "")).upper()
        stop = dec(p.get("Stop_Loss"))
        if stop is None or stop <= 0:
            continue                                    # 无有效止损线，跳过
        info = prices.get(tkr) or {}
        px = info.get("current")
        if px is None:
            print(f"[intraday-stop] {tkr} 取不到实时价，跳过（不猜价）")
            continue
        if px > stop:
            continue                                    # 未触及止损
        # —— 触发止损 ——
        rid = str(p.get("Recommendation_ID", "")) or tkr
        shares = int(dec(p.get("Shares")) or 0)
        if shares <= 0:
            continue
        entry = dec(p.get("Entry_Price")) or ZERO
        txn_id = f"INTRADAY|{tkr}|{today}"
        if txn_id in existing_txn:
            continue                                    # 幂等：今日已止损，不再处理
        realized = (px - entry) * Decimal(shares)
        amount = px * Decimal(shares)
        new_txns.append({
            "Txn_ID": txn_id,
            "Date": today,
            "Ticker": tkr,
            "Action": "SELL",
            "Shares": str(shares),
            "Price": str(money(px)),
            "Amount": str(money(amount)),
            "Realized_PnL": str(money(realized)),
            "Cash_After": "",
            "Reason": "Intraday Stop Loss",
            "Recommendation_ID": rid,
            "Scan_Date": str(p.get("Entry_Date", "")),
            "Portfolio_ID": PORTFOLIO_ID,
            "Unit_ID": str(p.get("Unit_ID", "")),
            "Pending_Reason": "True",
        })
        p["Shares"] = "0"
        p["Status"] = "CLOSED"
        p["Current_Price"] = str(money(px))
        p["Market_Value"] = "0.00"
        p["Unrealized_PnL"] = "0.00"
        p["Unrealized_PnL_Pct"] = "0.00"
        p["Weight_Pct"] = "0.00"
        p["Last_Update"] = today
        p["Cooldown_Until"] = _cooldown_until(today)   # 盘中机械止损：止损日 + 7 天冷却
        existing_txn.add(txn_id)
        triggered += 1
        print(f"🛑 INTRADAY STOP {tkr} {shares}股 @ {money(px)}（止损线 {money(stop)}）")

    if new_txns:
        transactions.extend(new_txns)
        write_csv_rows(data_dir / TRANSACTIONS_FILE, TRANSACTION_COLUMNS, transactions)
        write_csv_rows(data_dir / POSITIONS_FILE, POSITION_COLUMNS, positions)
    else:
        print("[intraday-stop] 本次无触发")
    return {"triggered": triggered, "total_equity": None, "positions": positions}


# ------------------------------------------------------------------ 主流程
def run(data_dir: Path, offline: bool = False, price_only: bool = False,
        intraday_stop: bool = False) -> dict:
    today = us_today_str()
    if intraday_stop:
        # 盘中机械止损：只在 09:30 ≤ ET < 16:00 触发，复用 fetch_last_closes（prepost=False）。
        # 不调用 process_buys / process_sells，只做"检查 + 卖"。默认（无此 flag）完全不进入此分支。
        return _run_intraday_stop(data_dir, today, offline)
    positions = read_csv_rows(data_dir / POSITIONS_FILE)
    transactions = read_csv_rows(data_dir / TRANSACTIONS_FILE)
    history = read_csv_rows(data_dir / HISTORY_FILE)

    # 仅刷新价格模式：跳过买卖处理与交易/历史写回，避免与盘后 review 抢同一份账本。
    # 无持仓时直接返回，且不调用 ensure_meta（避免误建 meta 干扰 review 初始化）。
    if price_only:
        if not positions:
            print("[price-only] 无持仓，跳过价格刷新")
            return {"cash": ZERO, "stock_value": ZERO, "total_equity": ZERO,
                    "unrealized_pnl": ZERO, "positions": []}
        open_tickers = sorted({str(p.get("Ticker", "")).upper()
                               for p in positions if str(p.get("Status", "")).upper() == "OPEN"})
        prices = {} if offline else fetch_last_closes(open_tickers)
        if open_tickers and not prices:
            print("⚠️ 未取到实时价，沿用上一快照价格（不编造价格）")
        stock_value, unrealized = mark_to_market(positions, prices, today)
        cash = derive_cash(transactions)   # 只读，不写交易流水
        total_equity = (cash + stock_value).quantize(CENT, rounding=ROUND_HALF_UP)
        fill_weights(positions, total_equity)
        # 只写回持仓 CSV（含 Extended_Price / Extended_Time），不动交易/历史
        write_csv_rows(data_dir / POSITIONS_FILE, POSITION_COLUMNS, positions)
        print("=" * 62)
        print(f"  [price-only] Cash (unchanged) : {cash}")
        print(f"  [price-only] Stock Value      : {stock_value}")
        print(f"  [price-only] Total Equity     : {total_equity}")
        _open_n = sum(1 for p in positions if str(p.get('Status', '')).upper() == 'OPEN')
        _sp = (stock_value / total_equity * Decimal("100")).quantize(CENT) if total_equity > 0 else ZERO
        print(f"  [price-only] Open Positions   : {_open_n} 只（浮动，目标 3-5）  股票占比 {_sp}%")
        print("=" * 62)
        return {
            "cash": cash,
            "stock_value": stock_value,
            "total_equity": total_equity,
            "unrealized_pnl": unrealized,
            "positions": positions,
        }

    meta = ensure_meta(data_dir, today)

    recs = load_recommendations(data_dir)
    print(f"📋 推荐事件 {len(recs)} 条，其中 Core_Dragon "
          f"{sum(1 for r in recs.values() if r['Tag'] == CORE_TAG)} 条")

    # 1) 先卖后买：释放 Unit 与现金
    for line in process_sells(positions, transactions, recs, today):
        print("   " + line)
    for line in process_buys(positions, transactions, recs, meta, today):
        print("   " + line)

    # 2) 交易流水按日期排序，回填 Cash_After（审计可核对）
    transactions.sort(key=lambda t: (str(t.get("Date", "")), str(t.get("Txn_ID", ""))))
    cash = INITIAL_CAPITAL
    realized_total = ZERO
    for t in transactions:
        amt = dec(t.get("Amount")) or ZERO
        act = str(t.get("Action", "")).upper()
        if act == "BUY":
            cash -= amt
        elif act == "SELL":
            cash += amt
            realized_total += dec(t.get("Realized_PnL")) or ZERO
        t["Cash_After"] = str(cash.quantize(CENT, rounding=ROUND_HALF_UP))
    cash = cash.quantize(CENT, rounding=ROUND_HALF_UP)

    # 3) 盯市
    open_tickers = sorted({str(p.get("Ticker", "")).upper()
                           for p in positions if str(p.get("Status", "")).upper() == "OPEN"})
    prices = {} if offline else fetch_last_closes(open_tickers)
    if open_tickers and not prices:
        print("⚠️ 未取到实时收盘价，沿用上一快照价格（不编造价格）")
    stock_value, unrealized = mark_to_market(positions, prices, today)

    total_equity = (cash + stock_value).quantize(CENT, rounding=ROUND_HALF_UP)
    realized_total = realized_total.quantize(CENT, rounding=ROUND_HALF_UP)
    total_pnl = (realized_total + unrealized).quantize(CENT, rounding=ROUND_HALF_UP)
    return_pct = (total_pnl / INITIAL_CAPITAL * Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
    fill_weights(positions, total_equity)

    # 4) 写回
    write_csv_rows(data_dir / POSITIONS_FILE, POSITION_COLUMNS, positions)
    write_csv_rows(data_dir / TRANSACTIONS_FILE, TRANSACTION_COLUMNS, transactions)
    upsert_history(history, {
        "Date": today,
        "Cash": str(cash),
        "Stock_Value": str(stock_value),
        "Total_Equity": str(total_equity),
        "Realized_PnL": str(realized_total),
        "Unrealized_PnL": str(unrealized),
        "Total_PnL": str(total_pnl),
        "Return_Pct": str(return_pct),
        "Open_Positions": str(sum(1 for p in positions if str(p.get("Status", "")).upper() == "OPEN")),
        "Portfolio_ID": PORTFOLIO_ID,
    })
    history.sort(key=lambda h: str(h.get("Date", "")))
    write_csv_rows(data_dir / HISTORY_FILE, HISTORY_COLUMNS, history)

    print("=" * 62)
    print(f"  Initial Capital : {INITIAL_CAPITAL}")
    print(f"  Cash            : {cash}")
    print(f"  Stock Value     : {stock_value}")
    print(f"  Total Equity    : {total_equity}")
    print(f"  Realized PnL    : {realized_total}")
    print(f"  Unrealized PnL  : {unrealized}")
    print(f"  Total PnL       : {total_pnl}   (Return {return_pct}%)")
    _open_n = sum(1 for p in positions if str(p.get('Status','')).upper()=='OPEN')
    _sp = (stock_value / total_equity * Decimal("100")).quantize(CENT) if total_equity > 0 else ZERO
    print(f"  Open Positions  : {_open_n} 只（浮动，目标 3-5）  股票占比 {_sp}%")
    print("=" * 62)
    return {
        "initial_capital": INITIAL_CAPITAL,
        "cash": cash,
        "stock_value": stock_value,
        "total_equity": total_equity,
        "realized_pnl": realized_total,
        "unrealized_pnl": unrealized,
        "total_pnl": total_pnl,
        "return_pct": return_pct,
        "positions": positions,
        "transactions": transactions,
        "history": history,
        "meta": meta,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="$50,000 Long-Term Portfolio Ledger")
    ap.add_argument("--data-dir", default=".", help="数据目录（需包含 trade_history.csv）")
    ap.add_argument("--offline", action="store_true", help="不联网取价（测试/离线用）")
    ap.add_argument("--price-only", action="store_true",
                    help="仅刷新持仓价格（含盘前/盘后 Extended_Price），不处理买卖、不写交易/历史")
    ap.add_argument("--intraday-stop", action="store_true",
                    help="盘中机械止损检查（09:30-16:00 ET）：实时价≤止损线则机械卖出；"
                         "不调用 process_buys/process_sells，不影响盘后 Review 路径")
    args = ap.parse_args(argv)
    d = Path(args.data_dir).resolve()
    if not (d / "trade_history.csv").exists():
        print(f"❌ 缺少 trade_history.csv：{d}")
        return 1
    run(d, offline=args.offline, price_only=args.price_only,
        intraday_stop=args.intraday_stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
