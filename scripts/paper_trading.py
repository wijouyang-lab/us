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
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
PENDING_GLOB = "us_stocks_pending_*.csv"
PRICE_FILE = REPO / "quant_factor_price_history.csv"
LEDGER = REPO / "portfolio_paper_transactions.csv"
OBSERVATIONS_FILE = REPO / "portfolio_paper_observation_dates.csv"
OBSERVATION_COLUMNS = [
    "Run_Date", "Data_AsOf_Date", "Candidate_File", "Signals_Queued",
    "Fills", "Closes", "Orders_Expired", "Open_Positions", "Pending_Orders",
]

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
PENDING_MAX_AGE_CALENDAR_DAYS = 4
SLIPPAGE_BPS = float(os.environ.get("PAPER_SLIPPAGE_BPS", "5.0"))
COMMISSION_BPS = float(os.environ.get("PAPER_COMMISSION_BPS", "0.5"))
PRICE_SCHEMA_VERSION = "phase2b.v2"
if not math.isfinite(SLIPPAGE_BPS) or SLIPPAGE_BPS < 0:
    raise ValueError("PAPER_SLIPPAGE_BPS must be finite and non-negative")
if not math.isfinite(COMMISSION_BPS) or COMMISSION_BPS < 0:
    raise ValueError("PAPER_COMMISSION_BPS must be finite and non-negative")
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
    """返回 {ticker: [{date, open, high, low, close}, ...]}；不完整/旧版历史一律拒绝交易。"""
    out: dict[str, list[dict]] = {}
    if not path.exists():
        print(f"[paper] 等待价格历史：{path.name} 不存在")
        return out
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "schema_version" not in reader.fieldnames:
            print("[paper] FAIL-CLOSED：价格历史没有 schema_version；请运行手动历史重建工作流")
            return out
        source_rows = list(reader)
    # Do not mix shifted legacy dates with corrected session-date bars. Normal incremental
    # updates may append v2 rows to the v1 file, so require the entire file to be rebuilt.
    versions = {str(r.get("schema_version") or "").strip() for r in source_rows}
    if not source_rows or versions != {PRICE_SCHEMA_VERSION}:
        print(
            "[paper] FAIL-CLOSED：价格历史不是全量 "
            f"{PRICE_SCHEMA_VERSION}（versions={sorted(versions)}）；"
            "模拟成交暂停，需先运行 Rebuild Quant Price History"
        )
        return out
    for r in source_rows:
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


def next_open_bar(series: list[dict], signal_date: str, asof_date: str | None = None,
                   expected_session_date: str | None = None):
    """只检查预期的首个后续市场交易日；缺 bar/Open 就拒绝成交，不能延迟到更晚日期。"""
    for bar in series:
        if bar["date"] > signal_date:
            if asof_date is not None and bar["date"] > asof_date:
                return None
            if expected_session_date is not None and bar["date"] != expected_session_date:
                return None
            return bar if _positive_float(bar.get("open")) is not None else None
    return None


def buy_execution_price(reference_open: float, slippage_bps: float = SLIPPAGE_BPS) -> float:
    if _positive_float(reference_open) is None or not math.isfinite(slippage_bps) or slippage_bps < 0:
        raise ValueError("买入参考价必须为正数，滑点必须有限且不能为负")
    return reference_open * (1.0 + slippage_bps / 10000.0)


def sell_execution_price(reference_close: float, slippage_bps: float = SLIPPAGE_BPS) -> float:
    if _positive_float(reference_close) is None or not math.isfinite(slippage_bps) or slippage_bps < 0:
        raise ValueError("卖出参考价必须为正数，滑点必须有限且不能为负")
    return reference_close * (1.0 - slippage_bps / 10000.0)


def commission(notional: float, commission_bps: float = COMMISSION_BPS) -> float:
    if not math.isfinite(notional) or notional < 0 or not math.isfinite(commission_bps) or commission_bps < 0:
        raise ValueError("名义金额必须非负且有限，佣金费率必须有限且不能为负")
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
    """Exit only on today's completed bar; never backdate a fill to an older close.

    The holding period is measured from Signal_Date (the previous close used to form the
    signal), so the 20th post-signal session matches Forward_Return_20D. If a scheduled
    execution was missed, an earlier trigger is recorded as delayed and priced at today's
    close, never at the stale trigger-day price.
    """
    closed = 0
    for r in rows:
        if (r.get("Action") or "").upper() != "BUY" or r.get("Exit_Date"):
            continue
        tk = (r.get("Ticker") or "").strip().upper()
        entry_date = (r.get("Entry_Date") or "").strip()
        signal_date = (r.get("Signal_Date") or "").strip()
        entry_exec = _positive_float(r.get("Entry_Price"))
        shares = _positive_float(r.get("Shares"))
        entry_comm = max(0.0, float(r.get("Entry_Commission") or 0.0))
        if not tk or not entry_date or not signal_date or entry_exec is None or shares is None:
            continue
        series = sorted(prices.get(tk, []), key=lambda b: b.get("date", ""))
        today_bar = next(
            (b for b in reversed(series)
             if b.get("date") == today and _positive_float(b.get("close")) is not None),
            None,
        )
        if today_bar is None:
            # No complete daily bar for the current session means no current executable mark.
            continue

        elapsed = 0
        trigger = None
        for bar in series:
            d = bar.get("date", "")
            if d <= signal_date or d > today:
                continue
            elapsed += 1
            if d < entry_date:
                continue
            close = _positive_float(bar.get("close"))
            if close is None:
                continue
            if close <= entry_exec * STOP_PCT:
                trigger = (bar, "Stop_Loss_Close")
                break
            if elapsed >= HOLD_DAYS:
                trigger = (bar, "Hold_20_Trading_Bars")
                break
        if trigger is None:
            continue

        trigger_bar, trigger_reason = trigger
        if trigger_bar["date"] < today:
            chosen = today_bar
            reason = f"Delayed_{trigger_reason}_Trigger_{trigger_bar['date']}"
            print(
                f"[paper] 延迟退出 {tk}：原触发日={trigger_bar['date']}，"
                f"使用当前完整收盘价 {today}，不回写旧日成交价"
            )
        else:
            chosen = trigger_bar
            reason = trigger_reason

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
        elapsed_to_exit = sum(
            1 for bar in series
            if signal_date < bar.get("date", "") <= chosen["date"]
            and _positive_float(bar.get("close")) is not None
        )
        r["Hold_Days"] = str(elapsed_to_exit)
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
    if signal_date != today:
        print(f"[paper] 跳过过期候选文件 {pf.name}（today={today}）；不补建历史模拟订单")
        return 0
    candidates = read_rows(pf)
    # VOID rows are audit traces only; they must not block a corrected replacement order.
    existing = {
        r.get("Txn_ID", "") for r in rows
        if (r.get("Action") or "").upper() != "VOID"
    }
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


def _fill_pending_orders(rows: list[dict], prices: dict[str, list[dict]], today: str | None = None) -> tuple[int, int]:
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
        if today is not None:
            try:
                signal_dt = datetime.strptime(signal_date, "%Y-%m-%d").date()
                today_dt = datetime.strptime(today, "%Y-%m-%d").date()
                age = (today_dt - signal_dt).days
            except ValueError:
                age = PENDING_MAX_AGE_CALENDAR_DAYS + 1
            if age > PENDING_MAX_AGE_CALENDAR_DAYS:
                r["Action"] = "EXPIRED"
                r["Reason"] = "SIGNAL_TOO_OLD_TO_FILL"
                expired += 1
                print(f"[paper] EXPIRED {tk} signal={signal_date}: order age={age} calendar days exceeds limit")
                continue
        series = prices.get(tk, [])
        # Infer the first completed market session after the signal from the full cross-ticker
        # history, not just this ticker's next available row (which could skip a missing bar).
        session_dates = sorted({
            b["date"]
            for ticker_bars in prices.values()
            for b in ticker_bars
            if b["date"] > signal_date and (today is None or b["date"] <= today)
        })
        if not session_dates:
            # Daily bars only become "complete" after the session has closed. Allow a short
            # data-publication window, but never backfill a weeks-old order after a later rebuild.
            try:
                signal_dt = datetime.strptime(signal_date, "%Y-%m-%d").date()
                today_dt = datetime.strptime(today, "%Y-%m-%d").date() if today else signal_dt
                age = (today_dt - signal_dt).days
            except ValueError:
                age = PENDING_MAX_AGE_CALENDAR_DAYS + 1
            if today is not None and age > PENDING_MAX_AGE_CALENDAR_DAYS:
                r["Action"] = "EXPIRED"
                r["Reason"] = "PRICE_HISTORY_UNAVAILABLE_TOO_LONG"
                expired += 1
                print(f"[paper] EXPIRED {tk} signal={signal_date}: no corrected price history after {age} calendar days")
            # Otherwise the next completed daily bar may not have been published yet.
            continue
        expected_session = session_dates[0]
        if today is None:
            # An execution date is required; helper calls without an explicit as-of date
            # must not create retroactive fills.
            print(f"[paper] PENDING {tk}: missing execution as-of date; no fill")
            continue
        if expected_session > today:
            # The current session's completed daily bar is not available yet.
            continue
        bar = next_open_bar(
            series, signal_date, asof_date=today, expected_session_date=expected_session
        )
        if bar is None:
            # A session exists in the market-wide history but this ticker lacks that session/Open.
            r["Action"] = "EXPIRED"
            r["Entry_Source_Date"] = expected_session
            r["Reason"] = "MISSING_TICKER_BAR_OR_OPEN_ON_FIRST_POST_SIGNAL_SESSION"
            expired += 1
            print(f"[paper] EXPIRED {tk} signal={signal_date}: missing ticker bar/Open on {expected_session}")
            continue
        if expected_session < today:
            r["Action"] = "EXPIRED"
            r["Entry_Source_Date"] = expected_session
            r["Reason"] = "MISSED_EXPECTED_SESSION_EXECUTION_WINDOW"
            expired += 1
            print(
                f"[paper] EXPIRED {tk} signal={signal_date}: expected session "
                f"{expected_session} was missed; refusing historical open backfill"
            )
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
        shares = round(UNIT / exec_open, 4)
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


def execution_window_enabled() -> bool:
    """Historical daily-bar fills/exits are processed only in the after-close EOD workflow."""
    return os.environ.get("PAPER_EXECUTION_WINDOW", "SCAN").strip().upper() == "EOD"


def observation_eligible() -> bool:
    """Only successful Scan-triggered workflow runs count toward the evaluation window."""
    return os.environ.get("PAPER_RECORD_OBSERVATION", "0") == "1"


MIN_OBSERVATION_TICKERS = 30


def observation_data_ready(prices: dict[str, list[dict]], run_date: str) -> bool:
    """Require recent completed bars across a minimum breadth of distinct tickers.

    Allow up to four calendar days of lag to cover weekends and a Monday market holiday.
    A single fresh ticker must not advance the 40-run observation gate when the rest of the
    available price history is stale. The 30-ticker floor is a minimum breadth guard, not a
    claim that the entire scan universe has complete coverage.
    """
    try:
        run_day = datetime.strptime(run_date, "%Y-%m-%d").date()
    except ValueError:
        return False
    fresh_tickers = set()
    for ticker, bars in prices.items():
        ticker_dates = []
        for bar in bars:
            raw = bar.get("date", "")
            try:
                day = datetime.strptime(raw, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                continue
            if day <= run_day:
                ticker_dates.append(day)
        if not ticker_dates:
            continue
        latest = max(ticker_dates)
        age = (run_day - latest).days
        if 0 <= age <= PENDING_MAX_AGE_CALENDAR_DAYS:
            fresh_tickers.add(str(ticker).strip().upper())
    return len(fresh_tickers) >= MIN_OBSERVATION_TICKERS


def record_observation(run_date: str, prices: dict[str, list[dict]], candidate_file: str,
                       signals_queued: int, fills: int, closes: int, expired: int,
                       open_positions: int, pending_orders: int,
                       path: Path = OBSERVATIONS_FILE) -> None:
    """Record one successful paper-workflow observation per ET calendar date, including zero-signal days."""
    previous = []
    if path.exists() and path.stat().st_size:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            previous = list(csv.DictReader(fh))
    by_date = {r.get("Run_Date", ""): r for r in previous if r.get("Run_Date")}
    asof_dates = [
        bar["date"] for ticker_bars in prices.values() for bar in ticker_bars
        if bar.get("date") and bar["date"] <= run_date
    ]
    by_date[run_date] = {
        "Run_Date": run_date,
        "Data_AsOf_Date": max(asof_dates) if asof_dates else "",
        "Candidate_File": candidate_file,
        "Signals_Queued": str(signals_queued),
        "Fills": str(fills),
        "Closes": str(closes),
        "Orders_Expired": str(expired),
        "Open_Positions": str(open_positions),
        "Pending_Orders": str(pending_orders),
    }
    rows = [by_date[d] for d in sorted(by_date) if d]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OBSERVATION_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def main() -> int:
    today = et_today()
    rows = read_rows(LEDGER)
    prices = load_prices()

    # Scan-triggered runs only register signals and observations. Execution is reserved for
    # the separate after-close EOD workflow after refreshing today's completed daily bars.
    execution_enabled = execution_window_enabled()
    closed_before = close_positions(rows, prices, today) if execution_enabled else 0

    candidates = sorted(REPO.glob(PENDING_GLOB))
    candidates = [p for p in candidates if not p.name.endswith(".processed")]
    latest_candidate = candidates[-1] if candidates else None
    candidate_file = (
        latest_candidate.name
        if latest_candidate is not None and _parse_signal_date(latest_candidate, today) == today
        else ""
    )
    created = _create_signal_orders(rows, candidates, today)

    if execution_enabled:
        filled, expired = _fill_pending_orders(rows, prices, today=today)
        closed_after = close_positions(rows, prices, today)
    else:
        filled, expired, closed_after = 0, 0, 0

    write_rows(LEDGER, rows)
    opened_now = sum(1 for r in rows if (r.get("Action") or "").upper() == "BUY" and not r.get("Exit_Date"))
    pending_now = sum(1 for r in rows if (r.get("Action") or "").upper() == "PENDING")
    if observation_eligible() and observation_data_ready(prices, today):
        record_observation(
            run_date=today, prices=prices, candidate_file=candidate_file,
            signals_queued=created, fills=filled, closes=closed_before + closed_after,
            expired=expired, open_positions=opened_now, pending_orders=pending_now,
        )
    elif observation_eligible():
        latest_price_date = max(
            (bar.get("date", "") for bars in prices.values() for bar in bars if bar.get("date") <= today),
            default="N/A",
        )
        print(
            f"[paper] Scan 成功但价格历史未确认当日完整 bar（as_of={latest_price_date}, run_date={today}）；"
            "本次不计入 40 日有效观察期"
        )
    else:
        print("[paper] 本次不是 Scan 成功后自动触发；账本可维护，但不计入有效观察日")
    print(
        f"[paper] 完成：新增信号 {created} / 新成交 {filled} / 新平仓 {closed_before + closed_after} / "
        f"过期订单 {expired} / 当前持仓 {opened_now} / 待成交 {pending_now} / "
        f"账本共 {len(rows)} 行 → {LEDGER.name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
