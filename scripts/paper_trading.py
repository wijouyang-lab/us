#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Paper Trading 每日记账（完全独立，不复用 portfolio_50000.py 任何逻辑）。

输入：us_stocks_pending_YYYYMMDD.csv（当日 scan 产物）
      quant_factor_price_history.csv（价格源）
账本：portfolio_paper_transactions.csv
规则：每笔固定 1 万；最多同时 5 只；持有 20 交易日；跌破 entry×0.95 止损。
幂等：Txn_ID 已存在则跳过。
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
PENDING_GLOB = "us_stocks_pending_*.csv"
PRICE_FILE = REPO / "quant_factor_price_history.csv"
LEDGER = REPO / "portfolio_paper_transactions.csv"

COLUMNS = ["Txn_ID", "Entry_Date", "Ticker", "Action", "Shares", "Entry_Price",
           "Exit_Date", "Exit_Price", "PnL", "PnL_Pct", "Hold_Days", "Mode", "Reason"]
INITIAL_CAPITAL = 50000.0
UNIT = 10000.0
MAX_OPEN = 5
HOLD_DAYS = 20
STOP_PCT = 0.95


def et_today() -> str:
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def read_rows(path: Path) -> list:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def load_prices() -> dict:
    """{ticker: [(date, close), ...] 升序}"""
    out: dict = {}
    if not PRICE_FILE.exists():
        return out
    with PRICE_FILE.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            tk = (r.get("Ticker") or "").strip().upper()
            d = (r.get("Date") or "").strip()
            try:
                px = float(r.get("Close") or "")
            except ValueError:
                continue
            if tk and d:
                out.setdefault(tk, []).append((d, px))
    for k in out:
        out[k].sort()
    return out


def price_on_or_before(series: list, date: str):
    best = None
    for d, px in series:
        if d <= date:
            best = px
        else:
            break
    return best


def main() -> int:
    today = et_today()
    rows = read_rows(LEDGER)
    existing = {r.get("Txn_ID", "") for r in rows}

    # ---------- 1) 平仓检查 ----------
    closed = 0
    for r in rows:
        if r.get("Exit_Date"):
            continue
        tk = r.get("Ticker", "").strip().upper()
        try:
            entry_px = float(r.get("Entry_Price") or "")
            shares = float(r.get("Shares") or "")
        except ValueError:
            continue
        series = load_prices().get(tk, [])
        cur = price_on_or_before(series, today)
        if cur is None:
            continue
        try:
            d0 = datetime.strptime(r["Entry_Date"], "%Y-%m-%d")
            d1 = datetime.strptime(today, "%Y-%m-%d")
            hold = (d1 - d0).days
        except Exception:
            hold = 0
        reason = None
        if cur <= entry_px * STOP_PCT:
            reason = "Stop_Loss"
        elif hold >= HOLD_DAYS:
            reason = "Hold_20D"
        if not reason:
            continue
        pnl = (cur - entry_px) * shares
        r["Action"] = "SELL"
        r["Exit_Date"] = today
        r["Exit_Price"] = f"{cur:.4f}"
        r["PnL"] = f"{pnl:.2f}"
        r["PnL_Pct"] = f"{(cur / entry_px - 1) * 100:.4f}"
        r["Hold_Days"] = str(min(hold, HOLD_DAYS) if reason == "Hold_20D" else hold)
        r["Reason"] = reason
        closed += 1

    # ---------- 2) 买入 ----------
    pending = sorted(REPO.glob(PENDING_GLOB))
    pending = [p for p in pending if not p.name.endswith(".processed")]
    opened = 0
    skipped = 0
    if not pending:
        print("[paper] 今日无 pending 文件（无新候选），仅做平仓检查")
    else:
        pf = pending[-1]                     # 最新一份
        pdate = pf.name.replace("us_stocks_pending_", "").replace(".csv", "")
        pdate = f"{pdate[:4]}-{pdate[4:6]}-{pdate[6:8]}" if len(pdate) == 8 else today
        cand = read_rows(pf)
        prices = load_prices()
        open_cnt = sum(1 for r in rows if not r.get("Exit_Date"))
        for c in cand:
            if open_cnt >= MAX_OPEN:
                print(f"[paper] 已达最大持仓 {MAX_OPEN}，停止买入")
                break
            tk = (c.get("Ticker") or "").strip().upper()
            if not tk:
                continue
            tid = f"{tk}|{pdate}|BUY"
            if tid in existing:
                skipped += 1
                continue
            series = prices.get(tk, [])
            px = price_on_or_before(series, pdate)
            if px is None:
                print(f"[paper] {tk}: 无价格数据，跳过")
                skipped += 1
                continue
            shares = round(UNIT / px, 4)
            rows.append({"Txn_ID": tid, "Entry_Date": pdate, "Ticker": tk,
                         "Action": "BUY", "Shares": f"{shares:.4f}",
                         "Entry_Price": f"{px:.4f}", "Exit_Date": "", "Exit_Price": "",
                         "PnL": "", "PnL_Pct": "", "Hold_Days": "", "Mode": "PAPER",
                         "Reason": "Scan_Pending"})
            existing.add(tid)
            open_cnt += 1
            opened += 1
            print(f"[paper] BUY {tk} {shares:.2f} @ {px:.2f} ({pdate})")

    write_rows(LEDGER, rows)
    open_now = sum(1 for r in rows if not r.get("Exit_Date"))
    print(f"[paper] 完成：新开 {opened} / 平仓 {closed} / 跳过 {skipped} / "
          f"在持 {open_now} / 账本共 {len(rows)} 行 → {LEDGER.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
