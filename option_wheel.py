# -*- coding: utf-8 -*-
"""期权 Wheel（CSP → CC）执行模块 —— L2 实现（flag 关闭时完全惰性）。

> **隔离原则**：本模块**不 import `portfolio_50000`**，也不直写股票组合。
> 它只负责「期权执行账本」`option_positions.csv` 的读写与 wheel 状态汇总；
> 被行权转股票、担保现金冻结等「影响 $50k 组合」的动作，由调用方（未来集成点）
> 依据本模块返回的事件自行落库——本模块零副作用、零反向依赖。
>
> **flag 门控**：`ENABLE_OPTIONS_WHEEL` 默认关闭。所有公开函数的**第一行**即检查该 flag；
> 关闭时一律返回安全空值（None / []），不读写账本、不产生任何副作用。
> 当前（2026-10-10）**没有任何调用点**（未接入 scan.py / review.py / dashboard_export.py），
> 故线上主流程零影响。
>
> 复用约定：信号层 `option_strategies.csv`（由 `scan_us_option_engine` 产出，本模块只读不写）；
> 期权链 `yfinance.option_chain()`（`scan_us_option_engine.py:600-609` 已用，实盘前再验证）。
>
> 设计来源：`OPTIONS_WHEEL_DESIGN.md` §附「L2 实现草稿」。
"""

import csv
import os
import datetime as dt
from typing import List, Dict, Optional, Callable

# ── 常量 ──────────────────────────────────────────────────────────────
LEDGER = "option_positions.csv"          # 执行层账本（本模块读写，首次写入时创建）
MAX_DAILY_WRITES = 2                     # 单日最多开仓 2 张（硬性上限）
CONTRACT_MULTIPLIER = 100                # 1 张 = 100 股

# 白名单：仅现金担保 Put（CSP）/ 备兑 Call（CC）可通过
ALLOWED_STRATEGIES = {"CSP", "CC"}
# 显式黑名单：亏损不封顶或超出现金担保范围的策略一律拒绝
FORBIDDEN_STRATEGIES = {"NAKED_CALL", "NAKED_PUT", "STRANGLE", "STRADDLE"}


def _enabled() -> bool:
    """flag 门控：仅当 ENABLE_OPTIONS_WHEEL == '1' 时启用本模块逻辑。"""
    return os.environ.get("ENABLE_OPTIONS_WHEEL") == "1"


def is_strategy_allowed(strategy: str) -> bool:
    """白名单 + 显式黑名单校验。仅 CSP/CC 通过；Naked Call/Put、Strangle/Straddle 等拒绝。

    防御层：任何不在白名单的策略类型在单元测试中断言失败，杜绝未来误加裸卖/组合策略。
    """
    s = (strategy or "").upper().strip()
    if s in FORBIDDEN_STRATEGIES:
        return False
    return s in ALLOWED_STRATEGIES


# ── 内部工具 ──────────────────────────────────────────────────────────
def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def _today() -> str:
    return dt.date.today().isoformat()


def _read_ledger() -> List[Dict]:
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _append_row(row: Dict) -> None:
    write_header = not os.path.exists(LEDGER)
    with open(LEDGER, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)


def _daily_writes(day: Optional[str] = None) -> int:
    d = day or _today()
    return sum(1 for r in _read_ledger() if (r.get("opened_at") or "").startswith(d))


def _get_option_quote(ticker: str, kind: str, strike: float, expiry: str) -> float:
    """取权利金（美元/张）。

    TODO(实盘前确认): `yfinance` `Ticker(ticker).option_chain(expiry)` 取 strikes / calls / puts
    中匹配 strike 的 mid 价（参考 `scan_us_option_engine.py:600-609`）。
    现用占位——**单元测试以 monkeypatch 覆盖**，不在单测内打真实 API。
    """
    raise NotImplementedError(
        "用 yfinance.option_chain 实现；测试请 monkeypatch option_wheel._get_option_quote")


# ── ① 卖 CSP（现金担保卖 Put）────────────────────────────────────────
def sell_csp(ticker: str, strike: float, expiry: str, ref_price: float) -> Optional[Dict]:
    """现金担保卖 Put。担保现金 = strike * 100 * contracts。

    flag 关闭 → 返回 None（零副作用）。flag 开启 → 写一条 OPEN 的 PUT 行到执行账本，
    返回该行（调用方据此冻结组合可用现金）。硬性约束：单日最多 MAX_DAILY_WRITES 张。
    """
    if not _enabled():
        return None
    if not is_strategy_allowed("CSP"):          # 防御：CSP 必须在白名单（恒真，但保留断言语义）
        raise RuntimeError("CSP 不在策略白名单，拒绝")
    contracts = 1
    if _daily_writes() >= MAX_DAILY_WRITES:
        raise RuntimeError(f"单日写入已达上限 {MAX_DAILY_WRITES} 张，今日不再开仓")
    premium = _get_option_quote(ticker, "PUT", strike, expiry)
    collateral = strike * CONTRACT_MULTIPLIER * contracts
    row = {
        "ticker": ticker, "kind": "PUT", "side": "SELL",
        "strike": strike, "expiry": expiry, "contracts": contracts,
        "premium": round(premium, 2),
        "status": "OPEN",
        "cash_collateral": round(collateral, 2),
        "assigned_shares": 0,
        "opened_at": _now(), "closed_at": "",
    }
    _append_row(row)
    return row   # 调用方据此冻结组合可用现金 = cash_collateral


# ── ② 检查到期指派 ───────────────────────────────────────────────────
def check_assignment(positions: List[Dict], live_price_fn: Callable[[str], float]) -> List[Dict]:
    """遍历 OPEN 的 CSP/CC，按到期日与实时价判定指派/过期。

    flag 关闭 → 返回 []（零副作用）。flag 开启 → 原地更新传入 rows 的 status，
    返回指派事件列表（由调用方落库到股票组合，本模块不直写）。
      · PUT 到期且 实时价 ≤ strike → 被行权：转入 100×contracts 股 @ strike，释放担保现金
      · 否则（价外或 CC 未触及）→ 过期
    """
    if not _enabled():
        return []
    today = dt.date.today()
    events = []
    for r in positions:
        if r.get("status") != "OPEN":
            continue
        try:
            exp = dt.date.fromisoformat(str(r["expiry"]))
        except (ValueError, KeyError, TypeError):
            continue
        if exp > today:
            continue
        px = live_price_fn(r["ticker"])
        if r["kind"] == "PUT" and px <= float(r["strike"]):
            r["status"] = "ASSIGNED"
            r["assigned_shares"] = CONTRACT_MULTIPLIER * int(r["contracts"])
            r["closed_at"] = _now()
            events.append({"type": "PUT_ASSIGNED", "ticker": r["ticker"],
                           "shares": r["assigned_shares"],
                           "price": float(r["strike"])})
        else:
            r["status"] = "EXPIRED"
            r["assigned_shares"] = 0
            r["closed_at"] = _now()
            events.append({"type": "EXPIRED", "ticker": r["ticker"]})
    return events


# ── ③ 卖 CC（备兑看涨）──────────────────────────────────────────────
def sell_covered_call(ticker: str, strike: float, expiry: str,
                      long_shares: int) -> Optional[Dict]:
    """备兑看涨。硬性要求正股 ≥ 100 * contracts（禁止裸卖 Call）。

    flag 关闭 → 返回 None（零副作用）。flag 开启 → 写一条 OPEN 的 CALL 行。
    """
    if not _enabled():
        return None
    if not is_strategy_allowed("CC"):           # 防御：CC 必须在白名单
        raise RuntimeError("CC 不在策略白名单，拒绝")
    contracts = 1
    if long_shares < CONTRACT_MULTIPLIER * contracts:
        raise RuntimeError(
            f"卖 CC 需正股 ≥ {CONTRACT_MULTIPLIER * contracts} 股，当前 {long_shares} 股"
            f"（禁止裸卖 Call）")
    if _daily_writes() >= MAX_DAILY_WRITES:
        raise RuntimeError(f"单日写入已达上限 {MAX_DAILY_WRITES} 张")
    premium = _get_option_quote(ticker, "CALL", strike, expiry)
    row = {
        "ticker": ticker, "kind": "CALL", "side": "SELL",
        "strike": strike, "expiry": expiry, "contracts": contracts,
        "premium": round(premium, 2), "status": "OPEN",
        "cash_collateral": 0.0, "assigned_shares": 0,
        "opened_at": _now(), "closed_at": "",
    }
    _append_row(row)
    return row


# ── ④ wheel 状态汇总（供 dashboard）─────────────────────────────────
def wheel_status() -> Optional[Dict]:
    """读执行账本，汇总当前 wheel 状态。flag 关闭 → 返回 None（不读账本）。"""
    if not _enabled():
        return None
    rows = _read_ledger()
    open_csp = [r for r in rows if r.get("kind") == "PUT" and r.get("status") == "OPEN"]
    open_cc = [r for r in rows if r.get("kind") == "CALL" and r.get("status") == "OPEN"]
    frozen = sum(float(r.get("cash_collateral") or 0) for r in open_csp)
    assigned = sum(int(r.get("assigned_shares") or 0) for r in rows)
    return {
        "open_csp": open_csp, "open_cc": open_cc,
        "frozen_cash": round(frozen, 2),
        "assigned_shares": assigned,
        "total_open": len(open_csp) + len(open_cc),
    }
