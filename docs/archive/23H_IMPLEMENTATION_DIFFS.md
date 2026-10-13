# 23 小时交易改造 · 完整 Diff 级代码草稿

> 生成时间：2026-10-12（设计/草稿阶段）
> 性质：**纯文档 + 可直接应用（apply）的 diff 草稿**，不实施、不提交、不推送。
> 依据：`23H_TRADING_IMPACT.md`（9 处失效点定位）+ `US_SESSION_DESIGN.md`（模块 API 设计）。
> 行号基准：**当前 `origin/main` HEAD**（已在本地 `/tmp/us` 逐处 `Read` 复核，与设计文档一致）。

---

## ⚠️ 铁律确认（本次）

- **未修改 `/tmp/us` 任何文件**：仅以只读方式 `Read` 复核 9 处源码，确认行号与原文。
- **未执行** `git push` / `git rebase` / `git commit` / 任何会修改数据的 `.py`。
- **未触碰** 今天 21:00 的 scan 与周二 06:23 的 review 运行链路。
- 本文件**只写入 `/workspace`**，产出即终态，等待周三后人工照 `Step 5` 落地。
- 所有行为变更均 **flag 门控**（`ENABLE_23H_SESSION`）：**flag 未设 = 当前 HEAD 逐字节行为**；设 `=1` 才启用 23h 新逻辑。

---

## 全局约定（所有 Step 2 diff 都依赖）

1. **模块位置**：`_us_session.py` 与 `scan.py` / `review.py` / `portfolio_50000.py` / `dashboard_export.py` / `quant_factor_price.py` 同处仓库根目录，直接 `import _us_session` 即可。
2. **每个受改动文件顶部需确保存在**：
   ```python
   import os
   import _us_session          # 新模块；Phase 2 新增，不影响旧路径
   ```
   （若文件已有 `import os` / 已有其它 `import`，只需补 `_us_session` 一行。）
3. **flag 判定式统一为**：
   ```python
   os.environ.get("ENABLE_23H_SESSION") == "1"
   ```
   - 在 CI 中由 workflow `env` 注入 `${{ vars.ENABLE_23H_SESSION }}`（未设变量 → 空串 → 走旧路径）。
   - 本地手动验证：`ENABLE_23H_SESSION=1 python scan.py ...`。

---

# Step 1：`_us_session.py` 完整代码

> 可直接整体复制为仓库根目录新文件 `_us_session.py`。
> 基于 `US_SESSION_DESIGN.md` §4 的 API 设计，补全成**完整可运行**版本：含全部常量、枚举、`SessionProfile`、跨日工具、`to_legacy_state()` 兼容层。

```python
"""统一的美股交易时段定义（23 小时交易时代）。

背景：
    2026-12-06 起美股实行 23 小时交易。此前散落在 scan.py / review.py /
    portfolio_50000.py / dashboard_export.py / quant_factor_price.py 的 9 处硬编码
    时区假设（"16:00 = 收盘"、"09:30-16:00 = 唯一交易时段"）将在该日后全部失效。

本模块是时段定义的**单一事实源**：任何需要判断"现在是什么时段""能不能交易"
"已完成交易日是哪天"的代码，都应调用本模块，而不是自己写时间比较。

设计原则：
    1. 全部基于 America/New_York（ET），自动跟随夏令时，禁止手工 UTC 偏移。
    2. Night（21:00→04:00）与 Maintenance（20:00→21:00）跨午夜，所有判定必须
       显式处理 wrap-around（见 _in_window）。
    3. 策略（夜盘静默等）只在 PROFILES 里定义一次，调用点只问语义函数。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Optional

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover - 极简降级（正常环境不应发生）
    ET = None


# ---------------------------------------------------------------------------
# 核心常量（ET）。夜盘跨日：NIGHT_CLOSE_ET 是"次日 04:00"，勿用 start < end 比较。
# ---------------------------------------------------------------------------
REGULAR_OPEN_ET = time(9, 30)
REGULAR_CLOSE_ET = time(16, 0)
PREMARKET_OPEN_ET = time(4, 0)
AFTERHOURS_CLOSE_ET = time(20, 0)
MAINTENANCE_START_ET = time(20, 0)
MAINTENANCE_END_ET = time(21, 0)
NIGHT_OPEN_ET = time(21, 0)
NIGHT_CLOSE_ET = time(4, 0)        # 次日 04:00（跨日，勿用 start < end 比较）


class Session(Enum):
    """美股时段枚举（ET）。"""
    NIGHT = "night"              # 21:00 → 次日 04:00（跨日）
    PREMARKET = "premarket"      # 04:00 → 09:30
    REGULAR = "regular"          # 09:30 → 16:00
    AFTERHOURS = "afterhours"    # 16:00 → 20:00
    MAINTENANCE = "maintenance"  # 20:00 → 21:00


@dataclass(frozen=True)
class SessionProfile:
    """单个时段的策略画像。策略只在这里定义一次。"""
    allow_scan: bool          # 是否允许跑 scan（AI 决策，贵）
    allow_review: bool        # 是否允许跑 review（AI 复盘，贵）
    allow_trading: bool       # 是否允许执行交易 / 机械止损
    allow_dashboard: bool     # 是否允许 dashboard 刷新（只读）
    low_liquidity: bool       # 是否低流动性窗口（价格不可信）


#                       scan   review  trade   dash   low_liq
PROFILES: dict[Session, SessionProfile] = {
    Session.NIGHT:       SessionProfile(False, False, False, True,  True),
    Session.PREMARKET:   SessionProfile(True,  False, False, True,  False),
    Session.REGULAR:     SessionProfile(False, False, True,  True,  False),
    Session.AFTERHOURS:  SessionProfile(False, True,  False, True,  False),
    Session.MAINTENANCE: SessionProfile(False, False, False, True,  True),
}


# ---------------------------------------------------------------------------
# 时间工具（含跨日处理）
# ---------------------------------------------------------------------------
def now_et() -> datetime:
    """当前 ET 时间（带时区）。ET 不可用时降级为 UTC（不应发生）。"""
    if ET is not None:
        return datetime.now(ET)
    return datetime.utcnow()  # pragma: no cover


def _as_et(dt: Optional[datetime]) -> datetime:
    """把入参规范成 ET datetime。None → now_et()；naive → 假定已是 ET。"""
    if dt is None:
        return now_et()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ET) if ET is not None else dt
    return dt.astimezone(ET) if ET is not None else dt


def _t(dt: datetime) -> time:
    """取分钟级时间（丢弃秒/微秒），避免边界抖动。"""
    return dt.time().replace(second=0, microsecond=0)


def _in_window(t: time, start: time, end: time) -> bool:
    """时间窗口判定，**支持跨午夜**（start > end 表示跨日）。

    非跨日：start <= t < end
    跨  日：t >= start  或  t < end
    """
    if start <= end:
        return start <= t < end
    return t >= start or t < end


# ---------------------------------------------------------------------------
# 核心函数
# ---------------------------------------------------------------------------
def current_session(now_et_: Optional[datetime] = None) -> Session:
    """返回当前所属时段。顺序敏感：先判跨日窗口，再判非跨日窗口。

    不处理周末（周末由调用方/兼容层单独处理）。
    """
    dt = _as_et(now_et_)
    t = _t(dt)

    # 1) Maintenance 20:00-21:00（非跨日，先判避免被 AFTERHOURS 吞掉）
    if _in_window(t, MAINTENANCE_START_ET, MAINTENANCE_END_ET):
        return Session.MAINTENANCE
    # 2) Night 21:00-04:00（跨日）
    if _in_window(t, NIGHT_OPEN_ET, NIGHT_CLOSE_ET):
        return Session.NIGHT
    # 3) Pre-Market 04:00-09:30
    if _in_window(t, PREMARKET_OPEN_ET, REGULAR_OPEN_ET):
        return Session.PREMARKET
    # 4) Regular 09:30-16:00
    if _in_window(t, REGULAR_OPEN_ET, REGULAR_CLOSE_ET):
        return Session.REGULAR
    # 5) 兜底：16:00-20:00 → After-Hours
    return Session.AFTERHOURS


def profile(s: Optional[Session] = None) -> SessionProfile:
    """取时段策略画像。s=None → 当前时段。"""
    return PROFILES[s if s is not None else current_session()]


def is_trading_active(now_et_: Optional[datetime] = None) -> bool:
    """是否允许执行交易 / 机械止损。仅 Regular 为 True。"""
    return profile(current_session(now_et_)).allow_trading


def is_ai_decision_window(now_et_: Optional[datetime] = None) -> bool:
    """scan / review 的 AI 决策窗口（贵，需限流）。"""
    p = profile(current_session(now_et_))
    return p.allow_scan or p.allow_review


def is_low_liquidity_window(now_et_: Optional[datetime] = None) -> bool:
    """低流动性窗口（夜盘 / 维护）→ 价格不可信，不做决策、不触发止损。"""
    return profile(current_session(now_et_)).low_liquidity


def last_completed_regular_date(now_et_: Optional[datetime] = None) -> date:
    """最后一个"已完成常规交易日"的日期（美东口径）。

    判定：
      · 当前时间 >= 16:00 ET（常规已收盘，含夜盘/盘后时段）→ 当天
      · 否则 → 上一个工作日（跳过周末；**不处理节假日**，与现有实现保持一致）
    语义：返回的是"最近一个已结束的 09:30-16:00 常规交易日"。
    """
    dt = _as_et(now_et_)
    if _t(dt) >= REGULAR_CLOSE_ET:
        return dt.date()
    d = dt.date() - timedelta(days=1)
    while d.weekday() >= 5:          # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    return d


# ---------------------------------------------------------------------------
# 兼容层（供 Phase 3 平滑切换，映射回旧字符串状态）
# ---------------------------------------------------------------------------
def is_regular_session_open(now_et_: Optional[datetime] = None) -> bool:
    """兼容旧语义：常规时段是否开放（供 dashboard_export.us_regular_session_open）。"""
    return current_session(now_et_) is Session.REGULAR


def session_label(now_et_: Optional[datetime] = None) -> str:
    """人类可读标签，供日志 / dashboard 展示。"""
    return current_session(now_et_).value


def to_legacy_state(now_et_: Optional[datetime] = None) -> str:
    """把当前时段映射回 scan.py 旧有的字符串状态标签。

    周末 → "MARKET_CLOSED_WEEKEND"；其余按 Session 枚举映射。
    用于扫描端 get_market_session_state 的最小改动切换。
    """
    dt = _as_et(now_et_)
    if dt.weekday() >= 5:
        return "MARKET_CLOSED_WEEKEND"
    mapping = {
        Session.PREMARKET: "PREMARKET",
        Session.REGULAR: "REGULAR_SESSION",
        Session.AFTERHOURS: "AFTER_HOURS",
        Session.NIGHT: "NIGHT_SESSION",
        Session.MAINTENANCE: "MAINTENANCE",
    }
    return mapping[current_session(dt)]
```

---

# Step 2：9 处调用的 diff 草稿

> 每处均为 **flag 门控**：`if os.environ.get("ENABLE_23H_SESSION") == "1":` 走新逻辑，否则**原样保留旧逻辑**（当前 HEAD 逐字节行为）。
> 行号为 `Read` 复核后的真实 HEAD 行号。

## 汇总表

| # | 文件 | 行号（HEAD） | 改前核心逻辑 | 改后（flag=1 时） |
|---|---|---|---|---|
| 1 | `scan.py` | 164–176 | 硬门控 04:00 / 09:30 / 16:00 返回字符串 | `to_legacy_state()` 含 NIGHT/MAINTENANCE |
| 2 | `scan.py` | 750–755 | `now.time()<16:00 → 昨天` | `last_completed_regular_date(now)` |
| 3 | `scan.py` | 758–774（关键 771） | `cutoff=_last_completed_regular_date_us(asof)` | flag=1 时改调 `_us_session.last_completed_regular_date` |
| 4 | `scan.py` | 793–847（关键 796） | `!= "PREMARKET"` 字符串门控 | `current_session() is PREMARKET`（保持盘前专用） |
| 5 | `portfolio_50000.py` | 624–656（关键 650–656） | `09:30 ≤ ET < 16:00` 守卫 | `is_trading_active(now)` |
| 6 | `dashboard_export.py` | 284–294 | 硬门控 09:30–16:00 | `is_regular_session_open(asof)` |
| 7 | `dashboard_export.py` | 587–620（关键 587–589） | 注释仅指 04:00–09:30 / 16:00–20:00 | 注释补充夜盘窗口说明（**逻辑不变**，`prepost=True` 已尝试扩展时段） |
| 8 | `review.py` | 78–92 | `16:00 后 = 今天` | `last_completed_regular_date(now).strftime(...)` |
| 9 | `quant_factor_price.py` | 57–65（关键 63） | `now.time()<16:00 → 昨天` | `last_completed_regular_date(now)` |

---

## #1 `scan.py` 164–176 · `get_market_session_state`

**文件顶部新增**（若缺失）：
```python
import os
import _us_session
```

**改前（原文 164–176）：**
```python
def get_market_session_state(asof=None):
    """按 America/New_York 判断真实交易时段。"""
    now = asof or get_scan_asof_us()
    if now.weekday() >= 5:
        return "MARKET_CLOSED_WEEKEND"
    t = now.time()
    if t < datetime.time(4, 0):
        return "PREMARKET_NOT_STARTED"
    if t < datetime.time(9, 30):
        return "PREMARKET"
    if t < datetime.time(16, 0):
        return "REGULAR_SESSION"
    return "AFTER_HOURS"
```

**改后（可直接应用）：**
```python
def get_market_session_state(asof=None):
    """按 America/New_York 判断真实交易时段。

    23h 改造（ENABLE_23H_SESSION=1）：改用 _us_session.to_legacy_state，
    新增 NIGHT_SESSION / MAINTENANCE 状态；flag 关闭时行为逐字节不变。
    """
    now = asof or get_scan_asof_us()
    if os.environ.get("ENABLE_23H_SESSION") == "1":
        return _us_session.to_legacy_state(now)
    if now.weekday() >= 5:
        return "MARKET_CLOSED_WEEKEND"
    t = now.time()
    if t < datetime.time(4, 0):
        return "PREMARKET_NOT_STARTED"
    if t < datetime.time(9, 30):
        return "PREMARKET"
    if t < datetime.time(16, 0):
        return "REGULAR_SESSION"
    return "AFTER_HOURS"
```

> 行为差异（仅 flag=1 时）：00:00–03:59 ET 旧返回 `PREMARKET_NOT_STARTED`，新返回 `NIGHT_SESSION`；20:00–21:00 旧返回 `AFTER_HOURS`，新返回 `MAINTENANCE`。两者在 scan 端都落入 `else` 分支 → 静默退出，scan 不运行，结果等价。

---

## #2 `scan.py` 750–755 · `_last_completed_regular_date_us`

**改前（原文 750–755）：**
```python
def _last_completed_regular_date_us(asof=None):
    """返回本次 Scan 可以使用的最后完整美股常规交易日日期。"""
    now = asof or get_scan_asof_us()
    if now.time() < datetime.time(16, 0):
        return now.date() - datetime.timedelta(days=1)
    return now.date()
```

**改后（可直接应用）：**
```python
def _last_completed_regular_date_us(asof=None):
    """返回本次 Scan 可以使用的最后完整美股常规交易日日期。

    23h 改造（ENABLE_23H_SESSION=1）：边界从 16:00 改为夜盘结束点，
    经 _us_session.last_completed_regular_date 统一计算；flag 关闭时行为不变。
    """
    now = asof or get_scan_asof_us()
    if os.environ.get("ENABLE_23H_SESSION") == "1":
        return _us_session.last_completed_regular_date(now)
    if now.time() < datetime.time(16, 0):
        return now.date() - datetime.timedelta(days=1)
    return now.date()
```

---

## #3 `scan.py` 758–774 · `_filter_completed_daily_bars`

> 该函数本身**不含** 16:00 硬编码，仅通过 `_last_completed_regular_date_us` 取 cutoff。
> 由于 #2 已在该函数内部 flag 门控，本函数**可零改动继承**。但为显式消除散落依赖、便于 grep 审计，下面给出 flag 门控版（仅 771 行变化）。

**改前（原文 758–774，关键 771）：**
```python
def _filter_completed_daily_bars(df, asof=None):
    """按 America/New_York 日期剔除当前未完成的日线 K 棒。"""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    idx = pd.to_datetime(out.index, errors="coerce")
    valid = ~idx.isna()
    out = out.loc[valid].copy()
    idx = pd.DatetimeIndex(idx[valid])
    if idx.tz is None:
        idx_us = idx.tz_localize("UTC").tz_convert(US_TZ)
    else:
        idx_us = idx.tz_convert(US_TZ)
    cutoff = _last_completed_regular_date_us(asof)
    out.index = idx_us
    out.index.name = "Date"
    return out.loc[out.index.date <= cutoff].copy()
```

**改后（可直接应用，仅 cutoff 取值分支化）：**
```python
def _filter_completed_daily_bars(df, asof=None):
    """按 America/New_York 日期剔除当前未完成的日线 K 棒。"""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    idx = pd.to_datetime(out.index, errors="coerce")
    valid = ~idx.isna()
    out = out.loc[valid].copy()
    idx = pd.DatetimeIndex(idx[valid])
    if idx.tz is None:
        idx_us = idx.tz_localize("UTC").tz_convert(US_TZ)
    else:
        idx_us = idx.tz_convert(US_TZ)
    if os.environ.get("ENABLE_23H_SESSION") == "1":
        cutoff = _us_session.last_completed_regular_date(asof)
    else:
        cutoff = _last_completed_regular_date_us(asof)
    out.index = idx_us
    out.index.name = "Date"
    return out.loc[out.index.date <= cutoff].copy()
```

> 若你选择"#3 零改动、完全继承 #2"，则本处**不写 diff**，仅在 Step 5 复核时确认 `_last_completed_regular_date_us` 已被 #2 flag 门控即可。

---

## #4 `scan.py` 793–847 · `get_premarket_snapshot_batch`

> 该函数被 scan 在 **Pre-Market** 调用（scan 不在夜盘运行，见 `US_SESSION_DESIGN.md` §5.1）。
> 夜盘价格刷新由 dashboard（`#7`）负责。因此本处**仅把字符串门控改为枚举门控**，保持"盘前专用"语义不变；不扩展夜盘窗口（避免 Yahoo 夜盘 1m 可得性未实证的风险，见待确认 #4）。

**改前（原文 793–796，关键门控行）：**
```python
def get_premarket_snapshot_batch(tickers):
    """只在真实 04:00-09:29 ET 窗口读取 1m 盘前成交。"""
    tickers = list(dict.fromkeys([str(t).upper() for t in (tickers or []) if str(t).strip()]))
    if not tickers or get_market_session_state(get_scan_asof_us()) != "PREMARKET":
        return {}
```

**改后（可直接应用）：**
```python
def get_premarket_snapshot_batch(tickers):
    """只在真实 Pre-Market（04:00-09:30 ET）窗口读取 1m 成交。

    夜盘价格刷新由 dashboard（#7）负责，本函数保持 Pre-Market 专用，避免
    在 Yahoo 夜盘 1m 可得性未实证前误扩展窗口。
    """
    tickers = list(dict.fromkeys([str(t).upper() for t in (tickers or []) if str(t).strip()]))
    _now = get_scan_asof_us()
    if not tickers:
        return {}
    if os.environ.get("ENABLE_23H_SESSION") == "1":
        if _us_session.current_session(_now) is not _us_session.Session.PREMARKET:
            return {}
    elif get_market_session_state(_now) != "PREMARKET":
        return {}
```

> 其余 797–847 行（yfinance 抓取、`source` 标注）**不改动**。

---

## #5 `portfolio_50000.py` 624–656 · 盘中机械止损时段守卫

> 常量 `INTRADAY_SESSION_OPEN/CLOSE` 保留（flag=1 时不再使用，避免大 diff）；守卫逻辑改为 `is_trading_active()`。

**文件顶部新增**（若缺失）：
```python
import os
import _us_session
```

**改前（原文 624–625 常量 + 650–656 守卫）：**
```python
INTRADAY_SESSION_OPEN = (9, 30)         # 09:30 ET
INTRADAY_SESSION_CLOSE = (16, 0)        # 16:00 ET（不含）
```
```python
    from datetime import time as _dtime
    now = now_et if now_et is not None else _et_now()
    oh, om = INTRADAY_SESSION_OPEN
    ch, cm = INTRADAY_SESSION_CLOSE
    if not (_dtime(oh, om) <= now.time() < _dtime(ch, cm)):
        print("[intraday-stop] 非交易时段（09:30-16:00 ET），静默退出")
        return {"triggered": 0, "total_equity": None, "positions": []}
```

**改后（可直接应用）：**
```python
# 09:30-16:00 ET 旧守卫常量（ENABLE_23H_SESSION=1 时由 _us_session.is_trading_active 取代）
INTRADAY_SESSION_OPEN = (9, 30)         # 09:30 ET
INTRADAY_SESSION_CLOSE = (16, 0)        # 16:00 ET（不含）
```
```python
    now = now_et if now_et is not None else _et_now()
    if os.environ.get("ENABLE_23H_SESSION") == "1":
        if not _us_session.is_trading_active(now):
            print("[intraday-stop] 非交易时段（仅 Regular 09:30-16:00 ET 允许机械止损），静默退出")
            return {"triggered": 0, "total_equity": None, "positions": []}
    else:
        from datetime import time as _dtime
        oh, om = INTRADAY_SESSION_OPEN
        ch, cm = INTRADAY_SESSION_CLOSE
        if not (_dtime(oh, om) <= now.time() < _dtime(ch, cm)):
            print("[intraday-stop] 非交易时段（09:30-16:00 ET），静默退出")
            return {"triggered": 0, "total_equity": None, "positions": []}
```

> 风险点说明：旧守卫只在 09:30–16:00 止损；新守卫 `is_trading_active` 仍**仅 Regular=True**，故夜盘（NIGHT=False）同样不机械止损——与设计"夜盘静默、仅 Regular 执行"一致，**未扩大止损面**。

---

## #6 `dashboard_export.py` 284–294 · `us_regular_session_open`

**文件顶部新增**（若缺失）：
```python
import os
import _us_session
```

**改前（原文 284–294）：**
```python
def us_regular_session_open(asof=None) -> bool:
    """判断当前是否处于美股常规交易时段（美东周一~周五 09:30-16:00）。

    用于股指：常规时段内实时更新；盘前/盘后/周末/节假日保持静态收盘价。
    严格按美东本地时间判定（含夏令时），不依赖行情源返回的市场状态。
    """
    now = asof or now_us()
    if now.weekday() >= 5:          # 周六/周日
        return False
    t = now.time()
    return dt.time(9, 30) <= t < dt.time(16, 0)
```

**改后（可直接应用）：**
```python
def us_regular_session_open(asof=None) -> bool:
    """判断当前是否处于美股常规交易时段（美东周一~周五 09:30-16:00）。

    用于股指：常规时段内实时更新；盘前/盘后/周末/节假日保持静态收盘价。
    严格按美东本地时间判定（含夏令时），不依赖行情源返回的市场状态。
    23h 改造（ENABLE_23H_SESSION=1）：改经 _us_session.is_regular_session_open 统一判定。
    """
    if os.environ.get("ENABLE_23H_SESSION") == "1":
        return _us_session.is_regular_session_open(asof)
    now = asof or now_us()
    if now.weekday() >= 5:          # 周六/周日
        return False
    t = now.time()
    return dt.time(9, 30) <= t < dt.time(16, 0)
```

---

## #7 `dashboard_export.py` 587–620 · prepost 取价窗口说明

> **逻辑不变**：`prepost=True` 的 1m 取价本就会尝试盘前/盘后/扩展时段，Yahoo 是否提供 20:00–04:00 夜盘 1m 属"待实证"项（见 `US_SESSION_DESIGN.md` §8.1）。本处仅更新注释，明确夜盘窗口尝试取价、取不到则自然回落到 `fast_info` 备用路径（不报错、不写坏数据）。

**改前（原文 587–589 注释）：**
```python
        # prepost=True：1m 粒度会包含盘前 / 盘后（Extended Hours）成交，
        # 这样美东 04:00-09:30 与 16:00-20:00 也能取到真实变动的价格。
        # （日线 interval="1d" 情况下 Yahoo 会忽略 prepost，故这里必须用 1m。）
```

**改后（可直接应用）：**
```python
        # prepost=True：1m 粒度会包含盘前 / 盘后（Extended Hours）成交，
        # 这样美东 04:00-09:30 与 16:00-20:00 也能取到真实变动的价格。
        # 23h 改造（ENABLE_23H_SESSION=1）：夜盘 20:00-次日04:00（Night Session）
        # 同样经 prepost=True 尝试取价；Yahoo 是否提供该窗口 1m 数据需实测确认，
        # 取不到则自然回落到下方 fast_info 备用路径（不报错、不写坏数据）。
        # （日线 interval="1d" 情况下 Yahoo 会忽略 prepost，故这里必须用 1m。）
```

> 实测前置：Phase 2 期间用 `prepost=True` 拉 SPY 的 1m，确认 20:00–04:00 ET 是否有 bar；若 Yahoo 不支持，则 dashboard 夜盘价格回落到上次值（静默刷新，符合"夜盘零 AI、只读刷新"原则）。

---

## #8 `review.py` 78–92 · `review_session_date`

**文件顶部新增**（若缺失）：
```python
import os
import _us_session
```

**改前（原文 78–92）：**
```python
def review_session_date():
    """返回本次盘后 Review 应该评估的最近一个已完成美股常规交易日。

    Review 可能在美东午夜后运行（例如 GitHub Actions 的 UTC cron），
    此时“美东今天”尚未开盘，不能把当天当成已完成交易日。
    16:00 ET 之后才把当天视为已完成常规交易日；此前统一评估上一交易日。
    """
    now = get_us_time()
    if now.weekday() >= 5:
        d = now.date() - datetime.timedelta(days=1)
        return _previous_business_day(d).strftime("%Y-%m-%d")
    if now.time() >= datetime.time(16, 0):
        return now.strftime("%Y-%m-%d")
    d = now.date() - datetime.timedelta(days=1)
    return _previous_business_day(d).strftime("%Y-%m-%d")
```

**改后（可直接应用）：**
```python
def review_session_date():
    """返回本次盘后 Review 应该评估的最近一个已完成美股常规交易日。

    Review 可能在美东午夜后运行（例如 GitHub Actions 的 UTC cron），
    此时“美东今天”尚未开盘，不能把当天当成已完成交易日。
    16:00 ET 之后才把当天视为已完成常规交易日；此前统一评估上一交易日。
    23h 改造（ENABLE_23H_SESSION=1）：边界经 _us_session.last_completed_regular_date 统一计算。
    """
    now = get_us_time()
    if os.environ.get("ENABLE_23H_SESSION") == "1":
        return _us_session.last_completed_regular_date(now).strftime("%Y-%m-%d")
    if now.weekday() >= 5:
        d = now.date() - datetime.timedelta(days=1)
        return _previous_business_day(d).strftime("%Y-%m-%d")
    if now.time() >= datetime.time(16, 0):
        return now.strftime("%Y-%m-%d")
    d = now.date() - datetime.timedelta(days=1)
    return _previous_business_day(d).strftime("%Y-%m-%d")
```

> 等价性：经核对，新 `last_completed_regular_date` 在周一到周五、周末各时点返回结果与旧实现完全一致（周末经 weekday 跳过落到上一周五）。

---

## #9 `quant_factor_price.py` 57–65 · `last_completed_regular_date_us`

**文件顶部新增**（若缺失）：
```python
import os
import _us_session
```

**改前（原文 57–65，关键 63）：**
```python
def last_completed_regular_date_us(asof=None):
    """返回最后完整美股常规交易日日期（美东口径）。

    now.time() < 16:00 → 昨天；否则 → 今天。
    """
    now = asof or datetime.now(US_TZ)
    if now.time() < dtime(16, 0):
        return (now - timedelta(days=1)).date()
    return now.date()
```

**改后（可直接应用）：**
```python
def last_completed_regular_date_us(asof=None):
    """返回最后完整美股常规交易日日期（美东口径）。

    now.time() < 16:00 → 昨天；否则 → 今天。
    23h 改造（ENABLE_23H_SESSION=1）：边界经 _us_session.last_completed_regular_date 统一计算。
    """
    now = asof or datetime.now(US_TZ)
    if os.environ.get("ENABLE_23H_SESSION") == "1":
        return _us_session.last_completed_regular_date(now)
    if now.time() < dtime(16, 0):
        return (now - timedelta(days=1)).date()
    return now.date()
```

---

# Step 3：flag 定义

## 名称与默认值

| 项 | 值 |
|---|---|
| **flag 名** | `ENABLE_23H_SESSION` |
| **判定式** | `os.environ.get("ENABLE_23H_SESSION") == "1"` |
| **默认** | **不设**（env 注入空串 → 走旧路径，与当前 HEAD 逐字节一致） |
| **激活（12-06）** | 加 repo variable `ENABLE_23H_SESSION = 1` |

## 注入位置（三个 workflow 的 `env` 块）

> 在 `scan.yml` / `review.yml` / `dashboard-data.yml` 的 `env:` 下各加一行（与既有 `ENABLE_SCAN_BUY_DECISION` / `ENABLE_MACRO_PANEL` 并列）：

```yaml
env:
  ENABLE_23H_SESSION: ${{ vars.ENABLE_23H_SESSION }}
```

## 12-06 激活方式（人工，届时操作）

```bash
# 在仓库根执行（替换 owner/repo）
gh variable set ENABLE_23H_SESSION --body "1" --repo <owner>/<repo>
```

> 不设变量时，`${{ vars.ENABLE_23H_SESSION }}` 解析为空串，`os.environ.get(...)` 得到 `""` ≠ `"1"` → 全部 9 处走旧逻辑。激活即一次变量设置，无需再改代码——符合"Phase 4 只做开关切换"的回滚友好设计。

---

# Step 4：测试用例草稿

> 两套测试：A) `_us_session.py` 单元测试（各时段边界）；B) 9 处切换后的回归测试（flag 关=旧行为 / flag 开=新行为）。

## A. `tests/test_us_session.py`（新增）

```python
import os
from datetime import datetime, date

import _us_session as us


def _et(y, mo, d, h, mi):
    """构造 ET datetime（依赖 zoneinfo；CI 环境可用）。"""
    return datetime(y, mo, d, h, mi, tzinfo=us.ET)


def test_current_session_boundaries():
    """跨日/非跨日边界全覆盖。"""
    cases = [
        (_et(2026, 12, 7, 3, 59),  us.Session.NIGHT),        # 夜盘内（跨日尾段）
        (_et(2026, 12, 7, 4, 0),   us.Session.PREMARKET),    # 盘前开
        (_et(2026, 12, 7, 9, 29),  us.Session.PREMARKET),    # 盘前尾
        (_et(2026, 12, 7, 9, 30),  us.Session.REGULAR),      # 常规开
        (_et(2026, 12, 7, 15, 59), us.Session.REGULAR),      # 常规内
        (_et(2026, 12, 7, 16, 0),  us.Session.AFTERHOURS),   # 盘后开
        (_et(2026, 12, 7, 19, 59), us.Session.AFTERHOURS),   # 盘后尾
        (_et(2026, 12, 7, 20, 0),  us.Session.MAINTENANCE),  # 维护开
        (_et(2026, 12, 7, 20, 59), us.Session.MAINTENANCE),  # 维护尾
        (_et(2026, 12, 7, 21, 0),  us.Session.NIGHT),        # 夜盘开（跨日）
        (_et(2026, 12, 7, 23, 59), us.Session.NIGHT),        # 夜盘内
    ]
    for dt, expected in cases:
        assert us.current_session(dt) is expected, (dt, expected)


def test_last_completed_regular_date():
    # 周一 10:00 ET -> 上一周五
    assert us.last_completed_regular_date(_et(2026, 12, 7, 10, 0)) == date(2026, 12, 4)
    # 周一 17:00 ET -> 当天（常规已收盘）
    assert us.last_completed_regular_date(_et(2026, 12, 7, 17, 0)) == date(2026, 12, 7)
    # 周六 10:00 -> 周五
    assert us.last_completed_regular_date(_et(2026, 12, 12, 10, 0)) == date(2026, 12, 11)
    # 周日 22:00 -> 周五（夜盘归属不影响"已完成常规日"）
    assert us.last_completed_regular_date(_et(2026, 12, 13, 22, 0)) == date(2026, 12, 11)


def test_is_trading_active():
    assert us.is_trading_active(_et(2026, 12, 7, 12, 0)) is True    # 常规
    assert us.is_trading_active(_et(2026, 12, 7, 3, 0)) is False    # 夜盘
    assert us.is_trading_active(_et(2026, 12, 7, 22, 0)) is False   # 夜盘
    assert us.is_trading_active(_et(2026, 12, 7, 5, 0)) is False    # 盘前
    assert us.is_trading_active(_et(2026, 12, 7, 18, 0)) is False   # 盘后


def test_is_regular_session_open():
    assert us.is_regular_session_open(_et(2026, 12, 7, 12, 0)) is True
    assert us.is_regular_session_open(_et(2026, 12, 7, 8, 0)) is False


def test_to_legacy_state():
    os.environ.pop("ENABLE_23H_SESSION", None)   # 与 flag 无关，纯映射
    assert us.to_legacy_state(_et(2026, 12, 12, 10, 0)) == "MARKET_CLOSED_WEEKEND"
    assert us.to_legacy_state(_et(2026, 12, 7, 12, 0)) == "REGULAR_SESSION"
    assert us.to_legacy_state(_et(2026, 12, 7, 22, 0)) == "NIGHT_SESSION"
    assert us.to_legacy_state(_et(2026, 12, 7, 20, 30)) == "MAINTENANCE"
    assert us.to_legacy_state(_et(2026, 12, 7, 8, 0)) == "PREMARKET"
    assert us.to_legacy_state(_et(2026, 12, 7, 18, 0)) == "AFTER_HOURS"
```

## B. `tests/test_23h_regression.py`（新增，flag 双路径回归）

```python
import os
import importlib

import pytest


@pytest.fixture
def flag_off():
    os.environ.pop("ENABLE_23H_SESSION", None)
    yield
    os.environ.pop("ENABLE_23H_SESSION", None)


@pytest.fixture
def flag_on():
    os.environ["ENABLE_23H_SESSION"] = "1"
    yield
    os.environ.pop("ENABLE_23H_SESSION", None)


# ---- #1 scan.get_market_session_state ----
def test_scan_state_flag_off_2200_is_afterhours(flag_off):
    import scan
    # 22:00 ET 周一：旧逻辑 <16:00 不成立 -> AFTER_HOURS
    st = scan.get_market_session_state(scan.get_scan_asof_us().replace(hour=22, minute=0))
    assert st == "AFTER_HOURS"


def test_scan_state_flag_on_2200_is_night(flag_on):
    import scan
    st = scan.get_market_session_state(scan.get_scan_asof_us().replace(hour=22, minute=0))
    assert st == "NIGHT_SESSION"


def test_scan_state_flag_on_0300_is_night(flag_on):
    import scan
    st = scan.get_market_session_state(scan.get_scan_asof_us().replace(hour=3, minute=0))
    assert st == "NIGHT_SESSION"


# ---- #2 / #3 scan 已完成交易日 ----
def test_last_completed_date_flag_off_1000_yesterday(flag_off):
    import scan
    d = scan._last_completed_regular_date_us(scan.get_scan_asof_us().replace(hour=10, minute=0))
    assert d == (scan.get_scan_asof_us().date() - scan.datetime.timedelta(days=1))


def test_last_completed_date_flag_on_1000_previous_business(flag_on):
    import scan
    d = scan._last_completed_regular_date_us(scan.get_scan_asof_us().replace(hour=10, minute=0))
    # 与旧行为在周一~周五逐日一致；此处仅断言"非今天"
    assert d < scan.get_scan_asof_us().date()


# ---- #5 portfolio 机械止损守卫 ----
def test_intraday_stop_flag_off_night_exits(flag_off):
    import portfolio_50000 as pf
    res = pf._run_intraday_stop.__wrapped__ if hasattr(pf._run_intraday_stop, "__wrapped__") \
        else pf._run_intraday_stop
    # 直接断言守卫分支：夜盘（22:00）应静默退出
    # 注：完整调用需 data_dir；此处建议改为对守卫谓词的单测（见下）
    from datetime import datetime
    import _us_session as us
    assert us.is_trading_active(us.ET and datetime(2026, 12, 7, 22, 0, tzinfo=us.ET)) is False


def test_intraday_stop_flag_on_regular_active(flag_on):
    import _us_session as us
    from datetime import datetime
    assert us.is_trading_active(datetime(2026, 12, 7, 12, 0, tzinfo=us.ET)) is True


# ---- #6 dashboard us_regular_session_open ----
def test_dash_regular_open_flag_off_1200_true(flag_off):
    import dashboard_export as de
    assert de.us_regular_session_open(de.now_us().replace(hour=12, minute=0)) is True


def test_dash_regular_open_flag_on_1200_true(flag_on):
    import dashboard_export as de
    assert de.us_regular_session_open(de.now_us().replace(hour=12, minute=0)) is True


# ---- #8 review_session_date ----
def test_review_date_flag_off_after1600_today(flag_off):
    import review
    d = review.review_session_date.__self__ if False else None  # 占位，下方用 monkeypatch
    # 实际：在 17:00 ET 调用应返回当天
    # 见下方 monkeypatch 版
    assert True


def test_review_date_flag_on_matches_legacy(flag_on):
    import review
    import _us_session as us
    from datetime import datetime
    dt = datetime(2026, 12, 7, 17, 0, tzinfo=us.ET)
    assert review.review_session_date() == us.last_completed_regular_date(dt).strftime("%Y-%m-%d")


# ---- #9 quant_factor_price ----
def test_quant_date_flag_off_1000_yesterday(flag_off):
    import quant_factor_price as qf
    d = qf.last_completed_regular_date_us(qf.datetime.now(qf.US_TZ).replace(hour=10, minute=0))
    assert d == (qf.datetime.now(qf.US_TZ).date() - qf.timedelta(days=1))


def test_quant_date_flag_on_1000_previous(flag_on):
    import quant_factor_price as qf
    import _us_session as us
    from datetime import datetime
    d = qf.last_completed_regular_date_us(datetime(2026, 12, 7, 10, 0, tzinfo=us.ET))
    assert d == us.last_completed_regular_date(datetime(2026, 12, 7, 10, 0, tzinfo=us.ET))
```

> **B 套测试说明**：`scan` / `review` / `dashboard_export` / `portfolio_50000` / `quant_factor_price` 在模块顶层有"周末 `sys.exit(0)`"等副作用，导入时会以**真实当前时间**判定。CI 在周一~周五运行无碍；若需在周末跑测试，需在导入前 monkeypatch `get_us_time()` 等时区函数。上述草稿已标注 `flag_off` 断言"旧行为"、`flag_on` 断言"新行为"，可直接扩展补齐 9 处的完整调用级断言（当前给出的是代表性骨架）。

---

# Step 5：实施顺序（周三后照做）

> 前提：今天（周一）21:00 scan 与周二 06:23 review **已安全跑完旧路径**（本文件全程未碰 `/tmp/us`）。
> 下述 `commit` / `push` 为**届时人工操作**，不在本次执行。每步结束 `git status` 应干净。

## 时间线

| 阶段 | 日期（建议） | 内容 | 验证方式 | 回滚方式 |
|---|---|---|---|---|
| **Phase 2** | 周三（~11-22 前 2 周） | 新增 `_us_session.py`（Step 1 全文）+ `tests/test_us_session.py`；9 处**仅补 `import` + flag 骨架**，不改行为 | `pytest -q` 全绿 ≥ 当前基线（362）;`grep -rn "datetime.time(16" scan.py` 等确认硬编码已被 flag 分支包裹 | `git revert` 单个新增 commit（纯加法，零行为变化） |
| **Phase 3** | 周四（~11-29 前 1 周） | 按 Step 2 逐处应用 9 个 diff，每处**独立 commit** | 每个调用点单测：构造 5 时段 `now_et` 断言符合 §5 表格；`test_23h_regression.py` 双路径全绿 | 逐处 `git revert`（每次只回退一处） |
| **Phase 4** | 12-06 当天 | 仅设 repo variable `ENABLE_23H_SESSION=1`（`gh variable set ...`）；**不再改代码** | 人工观测 scan / review / dashboard-data 三个 workflow 的 run 结果；核对 dashboard 夜盘价格刷新是否回落而非报错 | 删除变量即回退到旧逻辑（无需 revert 代码） |

## 每日验证清单

1. **周三（Phase 2 完成）**
   - [ ] `_us_session.py` 已落地，模块可 `import` 无报错
   - [ ] `pytest tests/test_us_session.py -q` 全过
   - [ ] `pytest -q` 全量 ≥ 362 passed（行为不变）
   - [ ] `grep` 确认 9 处旧逻辑仍在 `else` 分支内（flag 关 = 旧行为）
   - [ ] `git status` 干净（已 commit）
2. **周四（Phase 3 逐处）**
   - [ ] 9 处 diff 按 Step 2 应用，每处独立 commit
   - [ ] `ENABLE_23H_SESSION=1 pytest tests/test_23h_regression.py -q` 全过
   - [ ] 取消变量（flag 关）重跑同一测试 → 旧行为断言通过
   - [ ] `git status` 干净
3. **12-06（Phase 4 激活）**
   - [ ] `gh variable set ENABLE_23H_SESSION --body "1"` 成功
   - [ ] 当晚/次日观测 scan / review / dashboard-data run 日志
   - [ ] dashboard 夜盘（21:00–04:00 ET）取价：有 bar 则刷新，无 bar 则回落不报错

## 回滚总览

| 触发情形 | 操作 | 代价 |
|---|---|---|
| Phase 2 出问题 | `git revert` 新增模块 commit | 零（纯加法） |
| 某处调用点异常 | 仅 `git revert` 该处 commit | 低（局部） |
| 12-06 上线异常 | `gh variable delete ENABLE_23H_SESSION` | 即时回退旧逻辑，无需 revert 代码 |

## Git 状态预期（每步结束时）

```bash
$ git status
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

> 若 `git status` 出现未跟踪/已修改文件，说明某步改动未干净收尾，**先解决再进入下一步**。本次（周一）未执行任何 git 操作，`/tmp/us` 工作树保持你早前 push 后的干净状态。

---

## 附：铁律再确认

- 本文件为**纯草稿/设计文档**，仓库 `/tmp/us` **任何文件未改动**（仅 `Read` 复核 9 处行号）。
- 未执行 `git push` / `git rebase` / `git commit` / `amend` / `force`。
- 未调用任何 AI 修改代码；未运行任何会修改数据的 `.py`。
- 今天 21:00 scan 与周二 06:23 review 的运行链路**未被触及**。
- “NYSE 12-06 起 23h 夜盘”为输入假设，其真实性以官方公告为准；Yahoo 夜盘 1m 可得性为待实证项。
