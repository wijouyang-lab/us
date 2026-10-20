#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Paper Trading：按信号日后的首个完整交易日开盘成交，显式计入滑点/佣金。

重要口径：
- Scan 信号按文件日期记录为 Signal_Date；成交日期是其后第一根有效完整日线 bar。
- 只使用价格历史中的真实 Open；缺失时保留 PENDING，不回退到旧 Close。
- 每笔固定名义资金 10,000 美元，最多同时持有 5 只，持有 20 个实际价格交易日；
  以完整日线收盘价触发 -5% 止损或 20 个后续交易日退出。
- 买入和卖出都计入可配置的滑点、佣金。默认每边 5 bps 滑点、0.5 bps 佣金；
  该成本是假设而非券商报价，应在报告中显式展示。
- 本账本只作模拟，不影响 portfolio_50000_* 实盘账本。
"""
from __future__ import annotations

import csv
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
PENDING_GLOB = "us_stocks_pending_*.csv"
PRICE_FILE = REPO / "quant_factor_price_history.csv"
LEDGER = REPO / "portfolio_paper_transactions.csv"

COLUMNS = [
    "Txn_ID", "Signal_Date", "Ticker", "Action", "Shares",
    "Reference_Entry_Price", "Entry_Date", "Entry_Source_Date", "Entry_Price",
    "Entry_Slippage_Bps", "Entry_Commission",
    "Exit_Date", "Exit_Source_Date", "Exit_Reference_Price", "Exit_Price",
    "Exit_Slippage_Bps", "Exit_Commission", "Gross_PnL", "PnL", "PnL_Pct",
    "Hold_Days", "Mode", "Reason",
]
INITIAL_CAPITAL = 50000.0
UNIT = 10000.0
MAX_OPEN = 5
HOLD_DAYS = 20
STOP_PCT = 0.95
SLIPPAGE_BPS = 5.0
COMMISSION_BPS = 0.5
US_TZ = ZoneInfo("America/New_York")


def et_today() -> str:
    return datetime.now(US_TZ).strftime("%Y-%m-%d")


def read_rows(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})
    tmp.replace(path)


def _positive_float(value):
    try:
        x = float(value)
        return x if math.isfinite(x) and x > 0 else None
    except (TypeError, ValueError):
        return None


def load_prices(path: Path = PRICE_FILE) -> dict[str, list[dict]]:
    """返回 {ticker: [{date, open, high, low, close}, ...]}，按真实日线日期升序。"""
    out: dict[str, list[dict]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            tk = (r.get("Ticker") or "").strip().upper()
            d = (r.get("Date") or "").strip()
            close = _positive_float(r.get("Close"))
            if not tk or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or close is None:
                continue
            try:
                # 日期列必须严格可解析，防止错误标签参与交易。
                datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                continue
            out.setdefault(tk, []).append({
                "date": d,
                "open": _positive_float(r.get("Open")),
                "high": _positive_float(r.get("High")),
                "low": _positive_float(r.get("Low")),
                "close": close,
            })
    for tk in out:
        out[tk].sort(key=lambda b: b["date"])
        # Duplicate dates are unsafe: retain the last file row deterministically.
        by_date = {b["date"]: b for b in out[tk]}
        out[tk] = [by_date[d] for d in sorted(by_date)]
    return out


def next_open_bar(series: list[dict], signal_date: str):
    """返回 signal_date 之后首个具有有效 Open 的 bar；没有则返回 None。"""
    for bar in series:
        if bar["date"] > signal_date and _positive_float(bar.get("open")) is not None:
            return bar
    return None


def buy_execution_price(reference_open: float, slippage_bps: float = SLIPPAGE_BPS) -> float:
    if _positive_float(reference_open) is None or slippage_bps < 0:
        raise ValueError("买入参考价必须为正数，滑点不能为负")
    return reference_open * (1.0 + slippage_bps / 10000.0)


def sell_execution_price(reference_close: float, slippage_bps: float = SLIPPAGE_BPS) -> float:
    if _positive_float(reference_close) is None or slippage_bps < 0:
        raise ValueError("卖出参考价必须为正数，滑点不能为负")
    return reference_close * (1.0 - slippage_bps / 10000.0)


def commission(notional: float, commission_bps: float = COMMISSION_BPS) -> float:
    if not math.isfinite(notional) or notional < 0 or commission_bps < 0:
        raise ValueError("名义金额必须非负且有限，佣金不能为负")
    return notional * commission_bps / 10000.0


def net_trade_pnl(entry_exec: float, exit_exec: float, shares: float,
                  entry_commission: float, exit_commission: float) -> tuple[float, float, float]:
    gross = (exit_exec - entry_exec) * shares
    net = gross - entry_commission - exit_commission
    denominator = entry_exec * shares + entry_commission
    pct = (net / denominator * 100.0) if denominator > 0 else float("nan")
    return gross, net, pct


def _parse_signal_date(path: Path, today: str) -> str | None:
    m = re.fullmatch(r"us_stocks_pending_(\d{8})\.csv", path.name)
    if not m:
        return None
    raw = m.group(1)
    try:
        return datetime.strptime(raw, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _open_positions(rows: list[dict]) -> int:
    return sum(
        1 for r in rows
        if (r.get("Action") or "").upper() == "BUY"
        and not r.get("Exit_Date")
        and _positive_float(r.get("Entry_Price")) is not None
    )


def close_positions(rows: list[dict], prices: dict[str, list[dict]], today: str) -> int:
    """按每一根完整 bar 顺序退出，避免只检查最新价而漏掉历史止损。"""
    closed = 0
    for r in rows:
        if (r.get("Action") or "").upper() != "BUY" or r.get("Exit_Date"):
            continue
        tk = (r.get("Ticker") or "").strip().upper()
        entry_date = (r.get("Entry_Date") or "").strip()
        entry_exec = _positive_float(r.get("Entry_Price"))
        shares = _positive_float(r.get("Shares"))
        entry_comm = max(0.0, float(r.get("Entry_Commission") or 0.0))
        if not tk or not entry_date or entry_exec is None or shares is None:
            continue
        series = prices.get(tk, [])
        elapsed = 0
        chosen = None
        reason = ""
        for bar in series:
            d = bar["date"]
            if d < entry_date or d > today:
                continue
            if d > entry_date:
                elapsed += 1
            close = _positive_float(bar.get("close"))
            if close is None:
                continue
            if close <= entry_exec * STOP_PCT:
                chosen, reason = bar, "Stop_Loss_Close"
                break
            if elapsed >= HOLD_DAYS:
                chosen, reason = bar, "Hold_20_Trading_Bars"
                break
        if chosen is None:
            continue
        ref_exit = float(chosen["close"])
        exec_exit = sell_execution_price(ref_exit)
        exit_comm = commission(exec_exit * shares)
        gross, net, net_pct = net_trade_pnl(entry_exec, exec_exit, shares, entry_comm, exit_comm)
        r["Action"] = "SELL"
        r["Exit_Date"] = chosen["date"]
        r["Exit_Source_Date"] = chosen["date"]
        r["Exit_Reference_Price"] = f"{ref_exit:.6f}"
        r["Exit_Price"] = f"{exec_exit:.6f}"
        r["Exit_Slippage_Bps"] = f"{SLIPPAGE_BPS:.2f}"
        r["Exit_Commission"] = f"{exit_comm:.4f}"
        r["Gross_PnL"] = f"{gross:.2f}"
        r["PnL"] = f"{net:.2f}"
        r["PnL_Pct"] = f"{net_pct:.4f}"
        r["Hold_Days"] = str(elapsed)
        r["Reason"] = reason
        closed += 1
    return closed


def _candidate_tickers(candidate_rows: list[dict]) -> list[str]:
    result = []
    for c in candidate_rows:
        tk = (c.get("Ticker") or "").strip().upper()
        if not tk:
            continue
        # Pending file normally has Status=pending. If present, reject all other statuses.
        status = (c.get("Status") or "").strip().lower()
        if status and status != "pending":
            continue
        if tk not in result:
            result.append(tk)
    return result


def _create_signal_orders(rows: list[dict], pending_files: list[Path], today: str) -> int:
    if not pending_files:
        return 0
    pf = pending_files[-1]
    signal_date = _parse_signal_date(pf, today)
    if signal_date is None:
        print(f"[paper] 无法识别 pending 日期，跳过文件：{pf.name}")
        return 0
    candidates = read_rows(pf)
    existing = {r.get("Txn_ID", "") for r in rows}
    created = 0
    for tk in _candidate_tickers(candidates):
        tid = f"{tk}|{signal_date}|BUY"
        if tid in existing:
            continue
        rows.append({
            "Txn_ID": tid,
            "Signal_Date": signal_date,
            "Ticker": tk,
            "Action": "PENDING",
            "Shares": "",
            "Reference_Entry_Price": "",
            "Entry_Date": "",
            "Entry_Source_Date": "",
            "Entry_Price": "",
            "Entry_Slippage_Bps": "",
            "Entry_Commission": "",
            "Exit_Date": "",
            "Exit_Source_Date": "",
            "Exit_Reference_Price": "",
            "Exit_Price": "",
            "Exit_Slippage_Bps": "",
            "Exit_Commission": "",
            "Gross_PnL": "",
            "PnL": "",
            "PnL_Pct": "",
            "Hold_Days": "",
            "Mode": "PAPER",
            "Reason": "Await_Next_Trading_Day_Open",
        })
        existing.add(tid)
        created += 1
        print(f"[paper] QUEUED {tk} signal={signal_date}; waiting for next valid Open")
    return created


def _fill_pending_orders(rows: list[dict], prices: dict[str, list[dict]]) -> tuple[int, int]:
    filled = expired = 0
    for r in rows:
        if (r.get("Action") or "").upper() != "PENDING":
            continue
        tk = (r.get("Ticker") or "").strip().upper()
        signal_date = (r.get("Signal_Date") or "").strip()
        if not tk or not signal_date:
            r["Action"] = "EXPIRED"
            r["Reason"] = "INVALID_PENDING_ORDER_FIELDS"
            expired += 1
            continue
        bar = next_open_bar(prices.get(tk, []), signal_date)
        if bar is None:
            # Fail closed: retain pending order until the first post-signal bar's Open exists.
            continue
        if _open_positions(rows) >= MAX_OPEN:
            r["Action"] = "EXPIRED"
            r["Reason"] = "MAX_OPEN_AT_ENTRY"
            r["Entry_Source_Date"] = bar["date"]
            expired += 1
            print(f"[paper] EXPIRED {tk} signal={signal_date}: max positions at entry")
            continue
        ref_open = float(bar["open"])
        exec_open = buy_execution_price(ref_open)
        shares = round(UNIT / ref_open, 4)
        entry_comm = commission(exec_open * shares)
        r["Action"] = "BUY"
        r["Shares"] = f"{shares:.4f}"
        r["Reference_Entry_Price"] = f"{ref_open:.6f}"
        r["Entry_Date"] = bar["date"]
        r["Entry_Source_Date"] = bar["date"]
        r["Entry_Price"] = f"{exec_open:.6f}"
        r["Entry_Slippage_Bps"] = f"{SLIPPAGE_BPS:.2f}"
        r["Entry_Commission"] = f"{entry_comm:.4f}"
        r["Reason"] = "Filled_Next_Trading_Day_Open"
        filled += 1
        print(f"[paper] BUY {tk} {shares:.4f} @ {exec_open:.4f} "
              f"(reference open={ref_open:.4f}, signal={signal_date}, entry={bar['date']})")
    return filled, expired


def main() -> int:
    today = et_today()
    rows = read_rows(LEDGER)
    prices = load_prices()

    # Existing open positions are evaluated against all available completed bars.
    closed_before = close_positions(rows, prices, today)

    candidates = sorted(REPO.glob(PENDING_GLOB))
    candidates = [p for p in candidates if not p.name.endswith(".processed")]
    created = _create_signal_orders(rows, candidates, today)

    filled, expired = _fill_pending_orders(rows, prices)
    # If an order is filled from a historical bar after a delayed data refresh, replay
    # subsequent completed bars so the ledger does not pretend that the position is still open.
    closed_after = close_positions(rows, prices, today)

    write_rows(LEDGER, rows)
    opened_now = sum(1 for r in rows if (r.get("Action") or "").upper() == "BUY" and not r.get("Exit_Date"))
    pending_now = sum(1 for r in rows if (r.get("Action") or "").upper() == "PENDING")
    print(
        f"[paper] 完成：新增信号 {created} / 新成交 {filled} / 新平仓 {closed_before + closed_after} / "
        f"过期订单 {expired} / 当前持仓 {opened_now} / 待成交 {pending_now} / "
        f"账本共 {len(rows)} 行 → {LEDGER.name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
