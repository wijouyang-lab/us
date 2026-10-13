# 周末实施计划（WEEKEND IMPLEMENTATION PLAN）

> 本文档为 **diff 级设计**，仅描述「改哪一行 / 新函数放哪 / 调用点在哪」。
> 状态：**纯设计，未改任何 `.py`、未 push / rebase**（见文末 git 状态）。
> 所有行号基于当前 `/tmp/us` 工作树（`HEAD == origin/main == 3ba1ceb`，2026-10-10 核查）。

---

## 0. 事实基线（只读确认，非假设）

| 项 | 结论 | 证据 |
|---|---|---|
| `process_buys` 位置 | 在 `portfolio_50000.py:335`（**不在** scan.py） | `def process_buys(...)` |
| `positions.csv` 当前列 | 18 列，**无 `Cooldown_Until`** | `POSITION_COLUMNS`（portfolio_50000.py:57-62）末列 `Last_Update` |
| `transactions.csv` 代码列 | `TRANSACTION_COLUMNS`（:63-67）末列 `Pending_Reason`（磁盘 CSV 是旧 header，代码已定义） | 止损写 `Pending_Reason="True"`（:581） |
| 止损写入点 | `intraday_stop_loss`（:500-601），:583-590 把持仓置 `CLOSED` | 正是写 `Cooldown_Until` 的时机 |
| 持仓强制进池 | `build_ai_input`（quant_filter.py:233-247）**已强制合并**持仓（`_is_position=True` + 字段兜底） | `scan.py:3779` 调用，`generate_ai_report`（:2588）直接遍历，**不剔除** |
| scan 调度 | `scan.yml` **无 cron**（仅 `workflow_dispatch` + `news`/`quant-research` 链式 `needs: scan`） | grep 全文件无 `schedule:`/`cron:` 配置块 |
| review 调度 | `review.yml` `23 22 * * 1-5` = **22:23 UTC（周一至五）** | 唯一固定夜间 job |
| review 碰 transactions? | **否**，`review.py` 当前不读写 `portfolio_50000_transactions.csv` | grep 无 `Pending_Reason`/`TRANSACTION_COLUMNS` |

---

## 1. 买入侧冷却（碰 `portfolio_50000.py`）

### 1.1 设计目标
- 持仓 ticker 被止损后，**7 天内禁止同名重买**（=`Cooldown_Until` 未到）。
- 止损**当天 + 次日**额外硬禁（独立于冷却字段的防御，覆盖字段尚未写入的旧数据）。
- **全清仓当天停手**：若当日所有持仓被止损（组合归零），当天不再开新仓。

### 1.2 Diff A — `POSITION_COLUMNS` 追加字段（portfolio_50000.py:57-62）

```python
POSITION_COLUMNS = [
    "Portfolio_ID", "Unit_ID", "Ticker", "Shares", "Entry_Price", "Entry_Date",
    "Cost_Basis", "Current_Price", "Extended_Price", "Extended_Time", "Market_Value", "Unrealized_PnL",
    "Unrealized_PnL_Pct", "Weight_Pct", "Status", "Stop_Loss",
    "Recommendation_ID", "Last_Update",
    "Cooldown_Until",          # ← 新增：YYYY-MM-DD；空=无冷却
]
```
> 口径与历史 `Pending_Reason` 一致：**仅追加末列**，向前兼容旧 CSV（读不到则该字段为空）。

### 1.3 Diff B — 止损时写 `Cooldown_Until`（portfolio_50000.py:583-590）

在 `intraday_stop_loss` 把持仓置 `CLOSED` 的同一处，补一行：

```python
        p["Shares"] = "0"
        p["Status"] = "CLOSED"
        p["Current_Price"] = str(money(px))
        p["Market_Value"] = "0.00"
        p["Unrealized_PnL"] = "0.00"
        p["Unrealized_PnL_Pct"] = "0.00"
        p["Weight_Pct"] = "0.00"
        p["Last_Update"] = today
        p["Cooldown_Until"] = (parse_date(today) + timedelta(days=7)).strftime("%Y-%m-%d")  # ← 新增：止损日+7天
        existing_txn.add(txn_id)
```

### 1.4 Diff C — `process_buys` 顶部建冷却集合（portfolio_50000.py:342 之后）

在 `open_count = ...`（:342）之后、`candidates = ...`（:346）之前插入：

```python
    # —— 买入冷却（新增）——
    from datetime import timedelta
    today_d = parse_date(today)
    yesterday = (today_d - timedelta(days=1)).strftime("%Y-%m-%d")

    # (1) 7 天字段冷却：所有持仓（含 CLOSED）带 Cooldown_Until 且 >= today
    cooled = {str(p.get("Ticker", "")).upper()
              for p in positions
              if str(p.get("Cooldown_Until", "")).strip() >= today}

    # (2) 止损当天+次日防御：transactions 中 SELL 且 Reason 含 "Stop Loss"、Date∈{today,yesterday}
    recent_stop = {str(t.get("Ticker", "")).upper()
                   for t in transactions
                   if str(t.get("Action", "")).upper() == "SELL"
                   and "stop loss" in str(t.get("Reason", "")).lower()
                   and str(t.get("Date", "")) in (today, yesterday)}

    # (3) 全清仓停手：当前无 OPEN 持仓 且 今日发生过止损
    stops_today = any(
        str(t.get("Action", "")).upper() == "SELL"
        and "stop loss" in str(t.get("Reason", "")).lower()
        and str(t.get("Date", "")) == today
        for t in transactions
    )
    halted_today = (open_count == 0) and stops_today
    if halted_today:
        log.append("⏸ 今日组合已全清仓（止损），当天停止新买入")
```
> `parse_date` 用仓库既有的 `normalize_date`（review.py:156）或 portfolio 内等价实现；此处仅示意。

### 1.5 Diff D — 买入循环内加三道闸门（portfolio_50000.py:358 附近）

现有 `:358-360` 已挡「已持仓重买」，在其**之前**插入冷却与近期止损判断：

```python
        tkr = rec["Ticker"]
        if tkr in cooled or tkr in recent_stop:
            log.append(f"⏸  {tkr} 处于买入冷却期 → 跳过")
            continue
        if tkr in open_tickers:                 # 现有：已持仓不重买
            log.append(f"⏸  {tkr} 已持仓 → HOLD（不重复买入）")
            continue
        if open_count >= MAX_OPEN_POSITIONS:
            ...
```
- **注意**：Diff C 的 `halted_today` 已在函数顶部整体停手；Diff D 的三道闸门是逐 ticker 的细粒度保护（即使未触发全清仓，单只仍受冷却约束）。
- 循环内 `rec["Ticker"]` 原为 `rec["Ticker"] in open_tickers` 比较（大小写已统一为 UPPER），新增比较同样用裸 `rec["Ticker"]` 即可（rec 内 Ticker 已是大写）。

### 1.6 边界与风险
- 旧 CSV 无 `Cooldown_Until` → `str(p.get("Cooldown_Until",""))` 为空，空串 `>= today` 为 `False`，**自动视为无冷却**（安全默认）。
- 冷却只挡 `BUY`（`process_buys`），不影响止损、不影响 `mark_to_market`。
- `Cooldown_Until` 不随持仓 OPEN 续期；一旦写入只在被止损那一刻算 7 天。

### 1.7 可直接抄的实现草稿（完整代码，非伪代码）

> 以下片段均按 `portfolio_50000.py` 真实行号与风格给出，可直接复制粘贴。
> 设计目标与 1.1–1.6 一致：7 天字段冷却 + 止损当天/次日防御 + 全清仓停手。

#### 1.7.1 `POSITION_COLUMNS` 改动（portfolio_50000.py:57-62）

**改前（真实文本）：**
```python
POSITION_COLUMNS = [
    "Portfolio_ID", "Unit_ID", "Ticker", "Shares", "Entry_Price", "Entry_Date",
    "Cost_Basis", "Current_Price", "Extended_Price", "Extended_Time", "Market_Value", "Unrealized_PnL",
    "Unrealized_PnL_Pct", "Weight_Pct", "Status", "Stop_Loss",
    "Recommendation_ID", "Last_Update",
]
```

**改后（新增末列 `Cooldown_Until`）：**
```python
POSITION_COLUMNS = [
    "Portfolio_ID", "Unit_ID", "Ticker", "Shares", "Entry_Price", "Entry_Date",
    "Cost_Basis", "Current_Price", "Extended_Price", "Extended_Time", "Market_Value", "Unrealized_PnL",
    "Unrealized_PnL_Pct", "Weight_Pct", "Status", "Stop_Loss",
    "Recommendation_ID", "Last_Update", "Cooldown_Until",
]
```
> **插入位置：第 61 行 `"Last_Update",` 之后，新增一行 `"Cooldown_Until",`。**
> 向前兼容：旧 CSV 无此列 → `read_csv_rows` 返回字典缺键 → `p.get("Cooldown_Until","")` 为空，自动视为无冷却。

#### 1.7.2 止损写入点（两处，均含上下文 5 行）

**A) 盘中机械止损 `_run_intraday_stop`（portfolio_50000.py:583-590）** —— 真正的"止损"路径。

```python
        p["Shares"] = "0"
        p["Status"] = "CLOSED"
        p["Current_Price"] = str(money(px))
        p["Market_Value"] = "0.00"
        p["Unrealized_PnL"] = "0.00"
        p["Unrealized_PnL_Pct"] = "0.00"
        p["Weight_Pct"] = "0.00"
        p["Last_Update"] = today
        p["Cooldown_Until"] = _cooldown_until(today)   # ← 新增：止损日 + 7 天
        existing_txn.add(txn_id)
        triggered += 1
```
> **插入位置：第 590 行 `p["Last_Update"] = today` 之后、`existing_txn.add(txn_id)` 之前。**

**B) Review 终态裁决卖出 `process_sells`（portfolio_50000.py:323-330）** —— 仅当终态是 `Stop_Loss_Hit` 才写冷却（止盈/到期不冷却）。

```python
        p["Shares"] = "0"
        p["Status"] = "CLOSED"
        p["Current_Price"] = str(money(exit_px))
        p["Market_Value"] = "0.00"
        p["Unrealized_PnL"] = "0.00"
        p["Unrealized_PnL_Pct"] = "0.00"
        p["Weight_Pct"] = "0.00"
        p["Last_Update"] = today
        if rec["Status"] == "Stop_Loss_Hit":          # ← 新增：仅止损才冷却
            p["Cooldown_Until"] = _cooldown_until(today)
        existing_txn.add(txn_id)
```
> **插入位置：第 330 行 `p["Last_Update"] = today` 之后、`existing_txn.add(txn_id)` 之前。**

#### 1.7.3 `process_buys` 完整函数（含三道闸门）

完整可复制粘贴替换 portfolio_50000.py:335-421。仅新增冷却相关逻辑（顶部停手 + 字段冷却 + 近期止损防御），其余与线上完全一致。

```python
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

    # —— 闸门 0：全清仓当天停手 ——
    # 持仓已全 CLOSED 且今日发生过盘中/盘后止损 → 当日不再新开买入（防反复止损）。
    if open_count == 0 and _had_stop_today(transactions, today):
        log.append("⏸  今日已全清仓（含止损）→ 当日停手，不再新开买入")
        return log

    # —— 闸门 1 数据：7 天字段冷却 + 近 1-2 日止损防御 ——
    cooldowns = _load_cooldowns(positions)                       # {TICKER: "YYYY-MM-DD"}
    stopped_recent = _recent_stop_tickers(transactions, today)    # 止损当天+次日

    # 候选：按推荐日期升序（确定性，不受 dict 顺序影响）
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

        if open_count >= MAX_OPEN_POSITIONS:
            log.append(f"⏸  {rec['Ticker']} 无空闲 Unit（{open_count}/{MAX_OPEN_POSITIONS}）→ 仅保留为推荐")
            continue
        price = rec["Price"]
        shares = int((UNIT_DOLLARS / price).to_integral_value(rounding=ROUND_DOWN))
        if shares < 1:
            log.append(f"⏸  {rec['Ticker']} 单价 {money(price)} 超过 1 Unit 预算 {UNIT_DOLLARS} → 跳过")
            continue
        amount = money(Decimal(shares) * price)
        if amount > UNIT_DOLLARS:        # 双保险：绝不超预算
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
```
> **返回**：`list[str]` 日志，与原函数签名/语义一致，不修改 positions/transactions 之外的全局状态。
> **关键约束**：三道闸门只挡 `BUY`，不影响止损、不影响 `mark_to_market`；旧数据无 `Cooldown_Until` 时由闸门 2（近期止损防御）兜底。

#### 1.7.4 新增辅助函数（放在 `us_today_str` 之后，portfolio_50000.py:113 之后）

```python
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
```

#### 1.7.5 测试用例草稿（tests/test_process_buys_cooldown.py）

> 5 个用例仅给**函数签名 + 核心断言**（按需求不写完整实现）；`...` 为占位字段，落地时填齐其余列（如 `Shares/Entry_Price` 等，函数内 `dec()` 对缺失返回 0/None，不影响冷却判断）。

```python
import pytest
from datetime import date, timedelta
from decimal import Decimal

def _today() -> str:
    return date.today().strftime("%Y-%m-%d")

def _rec(ticker, price, rdate):  # 构造一条 Active Core 推荐
    return {"Recommendation_ID": f"R_{ticker}", "Ticker": ticker, "Tag": "Core_Dragon",
            "Status": "Active", "Rec_Date": rdate, "Price": Decimal(str(price)),
            "Stop_Loss": Decimal(str(price * 0.9))}

def test_cooldown_active_blocks_buy():
    """用例1：冷却期内不买——持仓含 CLOSED + Cooldown_Until=今+3，候选应被跳过。"""
    cd = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
    positions = [{"Ticker": "ADSK", "Status": "CLOSED", "Cooldown_Until": cd, ...}]
    recs = {r["Recommendation_ID"]: r for r in [_rec("ADSK", 200, _today())]}
    log = process_buys(positions, [], recs, {"start_date": "2026-01-01"}, _today())
    assert any("冷却期" in s for s in log)        # 日志出现冷却跳过
    # 断言：没有产生 BUY 交易（log 不含 "BUY ADSK"）

def test_cooldown_expired_allows_buy():
    """用例2：冷却期满可买——Cooldown_Until=昨天，候选应通过冷却走完买入。"""
    yest = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    positions = [{"Ticker": "ADSK", "Status": "CLOSED", "Cooldown_Until": yest, ...}]
    recs = {r["Recommendation_ID"]: r for r in [_rec("ADSK", 200, _today())]}
    log = process_buys(positions, [], recs, {"start_date": "2026-01-01"}, _today())
    assert any("BUY ADSK" in s for s in log)      # 走完买入，日志出现 BUY

def test_full_liquidation_halts_buys():
    """用例3：全清仓当天不买——open_count==0 且今日有止损 → 顶部停手。"""
    t = _today()
    positions = [{"Ticker": "NVDA", "Status": "CLOSED", ...}]
    txns = [{"Action": "SELL", "Reason": "Intraday Stop Loss", "Date": t, "Ticker": "NVDA", ...}]
    recs = {r["Recommendation_ID"]: r for r in [_rec("NEW", 100, t)]}
    log = process_buys(positions, txns, recs, {"start_date": "..."}, t)
    assert any("全清仓" in s for s in log)         # 顶部停手日志

def test_stop_same_day_and_next_day_blocked():
    """用例4：止损当天+次日不买——用 _recent_stop_tickers 防御（无 Cooldown_Until 字段）。"""
    today, yest = _today(), (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    txns = [{"Action": "SELL", "Reason": "Intraday Stop Loss", "Date": yest, "Ticker": "AMD", ...}]
    positions = []                                 # 无字段冷却，仅靠防御
    recs = {r["Recommendation_ID"]: r for r in [_rec("AMD", 150, today)]}
    log = process_buys(positions, txns, recs, {"start_date": "..."}, today)
    assert any("刚止损" in s for s in log)         # 防御跳过日志

def test_no_stop_history_buys_normally():
    """用例5：无止损记录正常买——干净持仓 + 无止损交易 → 正常 BUY。"""
    t = _today()
    positions = [{"Ticker": "CRM", "Status": "OPEN", ...}]   # 已持 CRM
    recs = {r["Recommendation_ID"]: r for r in [_rec("NEW", 100, t)]}  # 新 ticker
    log = process_buys(positions, [], recs, {"start_date": "..."}, t)
    assert any("BUY NEW" in s for s in log)        # 正常买入新标的
```

---

## 2. AI 原因回填（碰 `portfolio_50000.py`，触发挂 `review.yml`）

### 2.1 设计目标
- 读 `transactions.csv` 中 `Pending_Reason == "True"` 的记录。
- **一次 AI 调用分析 N 条**（批量，非逐条），降低 token/次数。
- 回写 `Reason` 字段并清空 `Pending_Reason`。

### 2.2 触发时机：推荐 **review 22:23 UTC**（非 scan）

| 候选 | 结论 | 理由 |
|---|---|---|
| scan 21:00 | ❌ 不存在固定调度 | `scan.yml` 无 `cron`（仅 dispatch + 链式）；"21:00" 是人工/口头习惯，非 job |
| **review 22:23 UTC** | ✅ **推荐** | 唯一固定夜间 job；盘后 22:23 当日所有盘中止损（09:30-16:00 ET）已落库、组合状态终态；`review.py` 已是「日终对账」角色，加一步 portfolio 原因回填自然 |
| 新增独立 cron | 可选 | 若不想耦合 review，可新建 `backfill-reasons.yml`（`0 2 * * 1-5` UTC，避开 review 争写） |

> 关键约束：pending 原因由 `intraday_stop_loss`（盘中）产生，必须在**当日组合状态冻结后**回填。22:23 UTC = 美东 18:23（夏令时），已充分晚于收盘，安全。

### 2.3 新函数落点：`portfolio_50000.py`（transactions 数据拥有者）

在 `intraday_stop_loss`（:601 之后）新增：

```python
def backfill_pending_reasons(data_dir: Path, batch_size: int = 20) -> int:
    """批量回填待补原因的止损交易。返回成功回填条数。"""
    transactions = read_csv_rows(data_dir / TRANSACTIONS_FILE)
    pending = [t for t in transactions
              if str(t.get("Pending_Reason", "")).strip().lower() == "true"]
    if not pending:
        print("[backfill-reasons] 无待补原因记录")
        return 0
    # 组装批量 prompt：一次调用分析 N 条，要求返回 JSON{txn_id: reason}
    prompt = _build_reason_prompt(pending)
    try:
        client = ClawSocketClient(api_key=os.environ["CLAWSOCKET_API_KEY"],
                                  base_url=os.environ["CLAWSOCKET_BASE_URL"])
        resp = client.chat(model=REASON_MODEL, messages=[{"role": "user", "content": prompt}])
        reasons = _parse_reason_json(resp)          # {Txn_ID: "..."}
    except Exception as e:
        print(f"[backfill-reasons] AI 调用失败（保留 Pending_Reason）: {type(e).__name__}: {e}")
        return 0
    by_id = {str(t.get("Txn_ID", "")): t for t in transactions}
    filled = 0
    for tid, reason in reasons.items():
        t = by_id.get(tid)
        if t and reason:
            t["Reason"] = reason
            t["Pending_Reason"] = "False"
            filled += 1
    write_csv_rows(data_dir / TRANSACTIONS_FILE, TRANSACTION_COLUMNS, transactions)
    print(f"[backfill-reasons] 回填 {filled}/{len(pending)} 条")
    return filled
```
> 复用 scan.py 已有的 `ClawSocketClient` 模式（scan.py:2586）与 `TRANSACTION_COLUMNS`（:63-67）。`_build_reason_prompt` 把每条 pending 的 `Ticker/Date/Shares/Price/Realized_PnL` 拼成清单，要求模型按 `Txn_ID` 返回结构化止损原因（如 "Gap-down open triggered intraday stop"）。

### 2.4 调用点：`review.yml`（22:23 UTC job 内，写完 review 后）

在 `review.yml` 的 Python 运行 step 中，于 review 主流程之后追加一步（**不碰 review.py 主逻辑**，仅在 workflow 调 `portfolio_50000.py` 的 CLI/子命令）：

```yaml
      - name: 回填待补止损原因（AI 批量）
        env:
          CLAWSOCKET_API_KEY: ${{ secrets.CLAWSOCKET_API_KEY }}
          CLAWSOCKET_BASE_URL: ${{ secrets.CLAWSOCKET_BASE_URL }}
        run: |
          python portfolio_50000.py --backfill-reasons --data-dir .
```
> 需在 `portfolio_50000.py` 的 `__main__` / `argparse` 增加 `--backfill-reasons` 分支（轻量，仅加一个分支，不碰现有 `run()`）。若严格不想动 review.py，这是最干净的落点。
> **争写提示**：review 与 dashboard-data 曾存在争写（前序审计 H2），本步只写 `portfolio_50000_transactions.csv`，与 dashboard-data 写的 `portfolio_50000_transactions.csv` 是同一文件——需复用既有的 `if [ -f ... ]` 守卫与单次 commit 节奏（参考 M2 修复），避免并发覆盖。

### 2.5 边界
- AI 失败 → **保留 `Pending_Reason="True"`**，下一日重试（幂等：已填的不在 pending 列表）。
- 批量 JSON 解析缺失某条 → 该条保留 pending，其余正常回填。
- 不覆盖已有 `Reason`（只处理 pending 子集）。

---

## 3. 持仓强制进池（碰 `quant_filter.py` + `scan.py`）

### 3.1 现状确认（关键）
`build_ai_input`（quant_filter.py:233-247）**已经强制合并持仓**：

```python
    for t in (positions or []):
        t = str(t).upper()
        if not t or t in seen: continue
        seen.add(t)
        row = dict(pool_by.get(t) or {})     # 命中 pool_data 复制完整行；否则空 dict
        row["Ticker"] = t
        row["Tag"] = "Core_Dragon"
        row["_is_position"] = True
        for k, v in AI_INPUT_REQUIRED_FIELDS.items():
            row.setdefault(k, v)             # ← 缺字段兜底，防 2590 行 KeyError
        out.append(row)
```
且 `scan.py:3779` `ai_input = build_ai_input(pool_data, redef_positions, redef_candidates)`，`:3825` `generate_ai_report(ai_input, ...)` 直接遍历 **不剔除**（scan.py:2588）。

**结论：持仓已进入 AI 输入与渲染路径，"前端卡片降级" 的根因（持仓不在 pool_data 时缺字段）已被 `setdefault` 兜底解决（见 test_quant_filter.py:288 回归）。**

### 3.2 是否还需改？
- **AI 输入侧**：**无需改动**。覆盖性已确认。
- **若担心 `AI_INPUT_MAX` 截断**（quant_filter.py:260 `out[:AI_INPUT_MAX]`）：当前 `AI_INPUT_MAX` 容纳 持仓(~4)+候选(≤3)=≤7，持仓恒在前、优先保留；只要 `AI_INPUT_MAX >= 7` 即不截断持仓。
- **"stocks[] 渲染" 若指 dashboard 前端持仓卡片**：那是 `dashboard_export.build_portfolio` 读 `positions.csv` 的独立路径（前序已硬化），**不经由 scan.py**，本项不触及。

### 3.3 唯一建议的「改哪一行」（防御性，非必需）
若要在 scan 端再加一道显式保险，确认持仓不被任何下游过滤丢弃，在 `scan.py:3779` 调用后加一行断言/日志即可（**不改逻辑**）：

```python
    ai_input = build_ai_input(pool_data, redef_positions, redef_candidates)
    assert all(str(x.get("Ticker","")) in {str(t).upper() for t in redef_positions}
               for x in ai_input if x.get("_is_position")), "持仓未全进 AI 输入"  # 防御断言
```
> 默认**不建议加断言**（生产路径怕误崩）；列为可选项。多数情况下该项**零改动**即已满足需求。

---

## 4. 浮动只数 + 百分比仓位（决策已拍板，未实施）

> 来源：`SCAN_ROLE_REDEFINITION_DESIGN.md` §0.8 / §0.9（2026-10-08 补拍板，**代码未改**，判决后实施）。
> 本项把"固定 4 只 × 固定 1 Unit"改为"浮动 3-5 只 + 百分比仓位 + 按信号强度动态 Unit"。与 #1 冷却互不冲突（#1 只挡 BUY 的"何时能买同名"，本项改 BUY 的"配额与尺寸"）。

### 4.1 决策基线（引用 §0.8/§0.9 原文）

| 维度 | 现状（代码实际） | 新决策 |
|---|---|---|
| 持仓只数 | `MAX_OPEN_POSITIONS = 4` 硬守卫（portfolio_50000.py:42，:361 卡死） | **浮动 3-5 只，无固定只数** |
| 单只尺寸 | `UNIT_DOLLARS = 10000` 固定 1 Unit（:41，:365/:370 用） | **按信号强度动态** |
| 单只上限 | 无 | ≤ **25%** |
| 总股票 | 无 | ≤ **80%** |
| 总期权 | 无 | ≤ **15%** |
| 现金下限 | 无 | ≥ **5%** |
| 加仓 / 换股 | Core 信号即开仓 | 有空间(<80%)→评分≥90 直接加仓；满仓(=80%)→评分≥最差+20 换股 |
| AI 候选数 | `out[:AI_INPUT_MAX]` 总顶 7（quant_filter.py:260） | `候选数 = min(3, 7 - 持仓数)`（§0.9） |

> §0.8 原文："删 `portfolio_50000.py:42` 的 `MAX_OPEN_POSITIONS=4` 逻辑守卫；常量本身可保留作历史参考。"
> §0.9 原文："候选数随持仓数动态调整，`AI_INPUT_MAX = 7` 保持不变。规则：`候选数 = min(3, AI_INPUT_MAX - 持仓数)`。"

### 4.2 Diff A — 删 `MAX_OPEN_POSITIONS` 逻辑守卫（portfolio_50000.py:361-362）

**现状（真实文本）：**
```python
        if open_count >= MAX_OPEN_POSITIONS:
            log.append(f"⏸  {rec['Ticker']} 无空闲 Unit（{open_count}/{MAX_OPEN_POSITIONS}）→ 仅保留为推荐")
            continue
```
> **改**：整段删除（逻辑守卫移除）。常量 `:42` 改名为 `MAX_OPEN_POSITIONS_DEPRECATED = 4  # 仅历史参考，不再作硬守卫`；同步改 `:224` meta 导出、`:639`/`:716` 日志打印为浮动只数/百分比口径（见 4.6）。

### 4.3 Diff B — `UNIT_DOLLARS` 改为按信号强度动态（portfolio_50000.py:41 + :365/:367/:370）

**改前（固定值）：**
```python
UNIT_DOLLARS = Decimal("10000.00")          # 1 Unit 目标资金（固定值，v1 不复利）
```
**改后（保留常量作回退，新增尺寸函数）：**
```python
UNIT_DOLLARS = Decimal("10000.00")          # 回退基准（信号缺失时仍用 1 Unit）

def unit_dollars_for(rec, equity) -> Decimal:
    """按信号强度动态 Unit：评分越高单只可配越多，但受 25% 单只上限钳制。"""
    score = float(rec.get("AI_Score") or 0)          # 候选/持仓 AI 评分（需 §0.8 评分链路先落地）
    factor = max(0.5, min(1.25, (score - 60) / 30 + 0.5))   # 60→0.5U, 90→1.0U, 100→1.25U
    size = UNIT_DOLLARS * Decimal(str(factor))
    return min(size, equity * Decimal("0.25"))        # 单只 ≤ 25%
```
> **插入位置**：`unit_dollars_for` 放 `us_today_str` 之后（与 #1 辅助函数同位）。`:365` 的 `UNIT_DOLLARS` 改为 `unit_dollars_for(rec, equity)`（equity = 现金 + 现有股票市值）；`:367`/`:370` 的日志与预算判断同步用动态值。
> **依赖**：`rec` 当前无 `AI_Score` 字段（process_buys 只取 `Price/Stop_Loss/Rec_Date`），需评分链路先打通（见 4.7）。评分未落地时 `factor` 退化为 0.5U 下限，仍向后兼容。

### 4.4 Diff C — 新增百分比仓位守卫（portfolio_50000.py，新增函数 + process_buys 调用）

当前代码**无任何百分比约束**。在 `process_buys` 内替换 Diff A 删掉的守卫，改为四维占比检查。新增辅助函数（放工具区）：
```python
def _stock_pct(positions, transactions) -> Decimal:
    """当前总股票市值 / 总资产（现金+股票）。期权由 scan_us_option_engine 另计。"""
    cash = derive_cash(transactions)
    stock = ZERO
    for p in positions:
        if str(p.get("Status", "")).upper() == "OPEN":
            stock += dec(p.get("Market_Value")) or ZERO
    total = cash + stock
    return (stock / total) if total > 0 else ZERO

def _within_alloc(rec, positions, transactions, equity) -> tuple[bool, str]:
    """四维占比预审：单只≤25% / 总股票≤80% / 期权≤15% / 现金≥5%。返回 (ok, 原因)。"""
    stock_pct = _stock_pct(positions, transactions)
    new_size = unit_dollars_for(rec, equity)
    proj_stock = stock_pct * equity + new_size
    if new_size > equity * Decimal("0.25"):
        return False, "单只将超 25%"
    if proj_stock > equity * Decimal("0.80"):
        return False, "总股票将超 80%"
    # 期权≤15% 由期权引擎单独走；现金≥5% 等价于 总股票≤95%，已被 80% 约束覆盖
    return True, ""
```
> **调用点（替换 Diff A 删除处）**：在 `process_buys` 循环内、原 `open_count >= MAX...` 位置改为：
```python
        ok, why = _within_alloc(rec, positions, transactions, equity)
        if not ok:
            log.append(f"⏸  {rec['Ticker']} 占比约束拦截（{why}）→ 跳过")
            continue
```
> `equity` 在循环外算一次：`equity = derive_cash(transactions) + 现有 OPEN 股票市值`。期权(≤15%)与现金(≥5%)的硬顶由期权引擎/预算双保险兜底，本函数只挡股票侧超配。

### 4.5 Diff D — AI 候选数动态（quant_filter.py:260，§0.9）

**现状（真实文本）：**
```python
    return out[:AI_INPUT_MAX]
```
**改后（候选 ≤ min(3, 7 - 持仓数)，持仓优先）：**
```python
    positions = [x for x in out if x.get("_is_position")]
    candidates = [x for x in out if not x.get("_is_position")]
    cand_cap = min(3, AI_INPUT_MAX - len(positions))   # §0.9：候选数 = min(3, 7-持仓数)
    return positions + candidates[:max(0, cand_cap)]
```
> **插入位置**：`quant_filter.py:260` 整行替换。`AI_INPUT_MAX = 7`（:28）不动；`_is_position` 字段已在 `build_ai_input`（quant_filter.py:233-247）由持仓合并写入，可直接用。`build_ai_input` 的持仓合并（#3 已确认覆盖）不受影响。

### 4.6 Diff E — Dashboard 显示口径（dashboard_export.py:2552 + app.js renderPortfolio）

§0.8 实施要点要求 "Open Units 4/4" 改为百分比/浮动只数：
- `dashboard_export.py:2552` 的 `max_open_positions`：保留但标注"历史常量/未启用"，新增 `open_pct = 总股票占比` 透传。
- `app.js` 的 `renderPortfolio` 中 "X/4 Units" 文案改为 "N 只持仓 · 股票 Y% · 现金 Z%"（浮动只数 + 百分比，去掉固定 4 暗示）。
> 纯展示改动，不影响买入/止损逻辑；铁律允许改 `app.js`/`app.css`/`index.html`（见历史任务 #126-128）。

### 4.7 依赖与未决（只读提示，本项不实施）
- **评分字段缺失**：`rec` 当前无 `AI_Score`（process_buys 只取 `Price/Stop_Loss/Rec_Date`）。§0.8 的"按信号强度""评分≥90/≥最差+20"依赖 scan/quant 评分链路先打通（SCAN_ROLE_REDEFINITION_DESIGN.md §3 / §5.4）。本 diff 用 `rec.get("AI_Score") or 0` 兜底，未落地时退化为固定 1 Unit（向后兼容）。
- **换股逻辑**：§0.8 的"满仓换股（评分≥最差+20）+ 每周≤1 + 冷启动 3 月只读"属 `review.py` 调仓执行层（SCAN_ROLE_REDEFINITION_DESIGN.md:290），超出本项"买入侧配额/尺寸"范围 → **本 diff 不触及 review.py**（与全局铁律一致）。
- **测试**：`test_portfolio_50000.py:282` 断言 `open_cnt == 4` 需改为浮动区间（`3 <= open_cnt <= 5`）；新增 `_within_alloc` / `unit_dollars_for` / 候选数动态单测。

---

## 5. 实施顺序与验证方法

| 顺序 | 项 | 优先级 | 改动文件 | 验证方法 |
|---|---|---|---|---|
| **P0** | #1 买入冷却 | 高（防反复止损） | `portfolio_50000.py` | 单测：模拟持仓 CLOSED+Cooldown_Until=today+3 → `process_buys` 跳过；today/yesterday 止损 → 跳过；全清仓 → 顶部停手。断言 `log` 含 "冷却"/"全清仓"。回归 `test_intraday_stop.py` 不破。 |
| **P1** | #2 AI 原因回填 | 中（数据完整性） | `portfolio_50000.py` + `review.yml` | 单测：`backfill_pending_reasons` mock AI 返回 JSON → 断言 `Reason` 写入、`Pending_Reason="False"`、失败路径保留 pending。集成：本地造 3 条 pending → 跑 `--backfill-reasons` → 校验 CSV。观察 22:23 UTC 夜跑是否零争写。 |
| **P2** | #3 持仓进池 | 低（已满足） | 大概率**零改动** | 已有 `test_quant_filter.py:288` 回归持仓缺字段不崩；新增断言：4 持仓 + 3 候选 → `build_ai_input` 输出含全部 4 持仓且 `_is_position=True`。 |

### 5.1 通用验证纪律（沿用前序铁律）
- Python **3.12-only**（`/usr/bin/python3.12` 或 workflow 的 `3.12`）。
- 不碰 `review.py` 主逻辑、`scan.py` 主逻辑（#3 仅确认）、`dashboard_export.py`、`portfolio_50000.py` 之外的数据链路。
- 每次改动配测试，全量 `pytest` ≥ 当前基线（294 passed）后再 commit。
- commit 顺序：先 #1（独立逻辑），再 #2（含 review.yml 守卫），#3 若无改动则不开 commit。
- 清 `__pycache__`，rebase 冲突即停。

### 5.2 风险与未决项
- **#2 争写**：review 与 dashboard-data 争写 `portfolio_50000_transactions.csv`（前序 H2），需复用 `if [ -f ... ]` 守卫 + 单一 commit 节奏。
- **#1 冷却字段回填历史**：旧 CSV 无 `Cooldown_Until`，仅对新止损生效；历史上的已止损 ticker 不受 7 天约束（可接受，因已不在持仓）。
- **scan 无 cron**：#2 若选 scan 触发需先给 scan.yml 加 cron（偏离现状），故推荐 review。

---

## 6. 报告（git 状态）

```
$ git -C /tmp/us status --short
（空）—— 工作树干净

$ git -C /tmp/us rev-parse HEAD origin/main
3ba1ceb094b7f3da476f145b285b234628e6b7c9   # HEAD
3ba1ceb094b7f3da476f145b285b234628e6b7c9   # origin/main（一致）

禁止文件触碰核验：grep 本次无修改；本文档仅新建 /workspace/WEEKEND_IMPLEMENTATION_PLAN.md
（位于 /workspace，非仓库 /tmp/us），未改任何 .py、未 push、未 rebase。
```

### 文档摘要
- **#1 买入冷却**：`POSITION_COLUMNS` 追加 `Cooldown_Until`（末列，向前兼容）；止损时（portfolio_50000.py:583-590）写 `止损日+7天`；`process_buys`（:342 后 / :358 前）建冷却集合 + 近期止损防御 + 全清仓停手三道闸门。
- **#2 AI 原因回填**：新增 `backfill_pending_reasons()`（portfolio_50000.py），批量一次 AI 调用分析 N 条 pending，回写 `Reason` 并清 `Pending_Reason`；**推荐挂在 review.yml 22:23 UTC**（scan 无 cron），复用既有 `if [ -f ... ]` 守卫防争写。
- **#3 持仓进池**：`build_ai_input`（quant_filter.py:233-247）**已强制合并持仓并兜底字段**，经 scan.py:3779/3825 进入 AI 渲染，**覆盖性已确认，大概率零改动**。
- **#4 浮动只数 + 百分比仓位**（决策已拍板、代码未改）：引用 `SCAN_ROLE_REDEFINITION_DESIGN.md` §0.8/§0.9。Diff A 删 `MAX_OPEN_POSITIONS` 守卫（portfolio_50000.py:361-362，常量 :42 留作历史）；Diff B `UNIT_DOLLARS` 改按信号强度动态（:41 留回退 + 新增 `unit_dollars_for`，:365/:370 改用动态值）；Diff C 新增 `_within_alloc`（单只≤25%/总股票≤80%）替换原守卫；Diff D `quant_filter.py:260` 候选数改 `min(3, 7-持仓数)`；Diff E dashboard_export.py:2552 + app.js 显示改百分比/浮动只数。**依赖**：`rec` 无 `AI_Score` 字段、换股逻辑属 review.py（本项不触及）。
- **铁律遵守**：仅写本文档，未改任何 `.py`、未 push、未 rebase；git 工作树干净，`HEAD == origin/main`。
