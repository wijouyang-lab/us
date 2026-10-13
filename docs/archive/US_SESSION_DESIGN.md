# `_us_session.py` 设计文档

> 美股 23 小时交易（2026-12-06 生效）时段逻辑集中化方案
> 版本：v1（设计阶段）　日期：2026-10-12　状态：**Phase 1 — 只写文档，未动任何代码**

---

## 0. 本文的性质与边界

| 项 | 说明 |
|---|---|
| 性质 | **设计文档 + 可直接抄的模块草稿**，不是实施记录 |
| 代码状态 | 仓库 `/tmp/us` **零改动**（无新增/修改/提交/推送） |
| 生效条件 | 本文件本身不产生任何运行时影响；实施需走 §6 的 Phase 2–4 |
| 依赖前置 | 前次只读调查 `23H_TRADING_IMPACT.md`（已定位 9 处硬编码时区假设） |

> ⚠️ 本文撰写当天（周一）21:00 有 scan、dashboard-data 每 15 分钟在跑。
> 全程未触碰仓库任何文件，未 `push` / `rebase` / `commit`，未调用 AI。

---

## 1. 背景

### 1.1 时间线

| 日期 | 事件 |
|---|---|
| 2026-12-06 | 美股 23 小时交易实施（Night Session 上线） |
| 12-06 前 2 周（~2026-11-22） | Phase 2：抽出 `_us_session.py`（行为不变） |
| 12-06 前 1 周（~2026-11-29） | Phase 3：9 处调用点切换到新模块（行为改变） |
| 2026-12-06 | Phase 4：激活新时段逻辑 |

### 1.2 新时段划分（ET）

```
00:00        04:00        09:30        16:00        20:00        21:00        24:00
  |------------|-------------|------------|------------|------------|------------|
  |   Night    |  Pre-Market |   Regular  | After-Hours| Maintenance|   Night    |
  | 21:00→04:00| 04:00→09:30 | 09:30→16:00| 16:00→20:00| 20:00→21:00| 21:00→04:00|
  |            |             |            |            |            |            |
  | 低流动性   | 中等流动性  | 核心流动性 | 中等流动性 | 系统维护   | 低流动性   |
  | 跨日！     |             |            |            |            | 跨日！     |
```

| 时段 | 窗口（ET） | 流动性 | 备注 |
|---|---|---|---|
| **Night Session** | 21:00 → 04:00（**跨日**） | 极低 | 建议静默，仅只读价格刷新 |
| **Pre-Market** | 04:00 → 09:30 | 中等 | scan 跑；不交易 |
| **Regular** | 09:30 → 16:00 | 核心 | 唯一允许机械止损 / 交易执行 |
| **After-Hours** | 16:00 → 20:00 | 中等 | review 跑；不交易 |
| **Maintenance** | 20:00 → 21:00 | 无 | 系统维护窗口 |

> ⚠️ **实现陷阱**：Night 与 Maintenance 都涉及跨日（21:00→04:00 跨过午夜）。
> 任何 `start < end` 的朴素比较都会失效，时段判定必须显式处理 wrap-around。

### 1.3 为什么必须改

现有代码的两套硬假设：

1. **`16:00 ET = 一天结束`** → 用于「已完成交易日」判定（4 处）
2. **`09:30–16:00 ET = 唯一存在的交易时段`** → 用于状态机 / 门控（5 处）

23h 之后这两条都失效：夜盘 20:00 起（ET 21:00）就有成交，16:00 不再是"收盘"，
而 04:00–09:30 与 16:00–20:00 也都有真实成交量。

---

## 2. 流动性数据（决策依据）

> 数据来源：公开市场结构研究（夜盘成交结构统计）。以下数字用于**支撑"夜盘静默"策略**，
> 不作为任何硬编码阈值的依据。

| 指标 | 数值 | 含义 |
|---|---|---|
| 夜盘成交量占比 | **~1%** of 全天 | 夜盘定价有效性极低 |
| 夜盘集中度 | **15 只**股票贡献 50% 成交量 | 极度集中，样本外不可泛化 |
| 常规时段对照 | 需 **256 只**才达到同样 50% 占比 | 常规时段分散度高 ~17× |
| 夜盘参与者结构 | 机构仅 **7%**，海外散户 **37%** | 定价由非机构主导 → 噪音大 |
| 核心流动性高峰 | 09:30–10:00 **11%** + 15:30–16:00 **20%** | 合计 **~31%** 集中在 1 小时 |

### 2.1 由此推导出的三条设计原则

1. **夜盘不做决策**（占比 1% + 机构仅 7% → 价不可信）
   → Night 时段：❌ scan、❌ review、❌ 止损，仅 ✅ 只读价格刷新。
2. **只在核心流动性时段执行交易**（09:30–16:00 承担 ~69% 之外的分散流动性）
   → `is_trading_active()` 仅 Regular 返回 True。
3. **AI 决策窗口绑在流动性中等以上的时段**
   → scan 落 Pre-Market（盘前定计划）、review 落 After-Hours（盘后复盘），
   两者都**不在**交易执行时段，天然与执行解耦。

---

## 3. 设计目标

> 把散落在 **5 个文件、9 处**硬编码的时区假设，集中到一个模块 `_us_session.py`。

### 3.1 9 处定位（来自前次只读调查）

| # | 文件:行 | 现状 | 失效方式（12-06 后） |
|---|---|---|---|
| 1 | `scan.py:164-176` `get_market_session_state` | 硬门控 09:30 / 16:00 | 夜盘 21:00–04:00 被误判为 AFTER_HOURS 或 PREMARKET_NOT_STARTED |
| 2 | `scan.py:750-755` `_last_completed_regular_date_us` | `now < 16:00 → 昨天` | 夜盘时段会错切"已完成交易日" |
| 3 | `scan.py:758-774` `_filter_completed_daily_bars` | 依赖 #2 的日期归属 | 夜盘 K 棒日期归属错乱 / 被错剔 |
| 4 | `scan.py:793-847` `get_premarket_snapshot_batch` | 硬门控 `== PREMARKET`（04:00–09:29） | 夜盘 21:00–04:00 的价格不被读取 |
| 5 | `portfolio_50000.py:624-656` 盘中止损守卫 | `09:30 ≤ ET < 16:00` | 夜盘跌破止损线不机械卖出（**风险点**） |
| 6 | `dashboard_export.py:284-294` `us_regular_session_open` | 门控 09:30–16:00 | 股指实时门控不认夜盘 |
| 7 | `dashboard_export.py:587-620` prepost 取价 | 仅覆盖 04:00–09:30 / 16:00–20:00 | 未含夜盘窗口 |
| 8 | `review.py:78-92` `review_session_date` | 16:00 后才是"已完成交易日" | 夜盘打破该假设 |
| 9 | `quant_factor_price.py:60` | `now < 16:00 → 昨天` | 交易日边界错切 |

### 3.2 目标（可验收）

| 目标 | 验收标准 |
|---|---|
| **单一事实源** | 9 处时区常量全部来自 `_us_session.py`，grep 不到第二份 09:30/16:00 硬编码 |
| **跨日正确** | Night（21:00→04:00）与 Maintenance（20:00→21:00）wrap-around 有单测覆盖 |
| **策略集中** | "夜盘静默"只在模块内定义一次，调用点只问 `is_trading_active()` |
| **行为可回滚** | Phase 2 纯加法不改行为；Phase 3/4 可 `git revert` |
| **时区安全** | 全部基于 ET（`America/New_York`），自动跟随夏令时，无手工 UTC 偏移 |

---

## 4. `_us_session.py` API 设计

### 4.1 模块骨架（可直接抄）

```python
"""统一的美股交易时段定义（23 小时交易时代）。

背景：2026-12-06 起美股实行 23 小时交易。此前散落在 scan.py / review.py /
portfolio_50000.py / dashboard_export.py / quant_factor_price.py 的 9 处硬编码
时区假设（"16:00 = 收盘"、"09:30-16:00 = 唯一交易时段"）将全部失效。

本模块是时段定义的**单一事实源**：任何需要判断"现在是什么时段""能不能交易"
"已完成交易日是哪天"的代码，都应调用本模块，而不是自己写时间比较。

设计原则：
  1. 全部基于 America/New_York（ET），自动跟随夏令时，禁止手工 UTC 偏移。
  2. Night（21:00→04:00）跨午夜，所有判定必须显式处理 wrap-around。
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
except Exception:  # pragma: no cover - 极简降级（不应发生）
    ET = None


# ---------------------------------------------------------------------------
# 核心常量（ET）
# ---------------------------------------------------------------------------
REGULAR_OPEN_ET = time(9, 30)
REGULAR_CLOSE_ET = time(16, 0)
PREMARKET_OPEN_ET = time(4, 0)
AFTERHOURS_CLOSE_ET = time(20, 0)
MAINTENANCE_START_ET = time(20, 0)
MAINTENANCE_END_ET = time(21, 0)
NIGHT_OPEN_ET = time(21, 0)
NIGHT_CLOSE_ET = time(4, 0)      # 次日 04:00（跨日，勿用 start < end 比较）


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
    allow_scan: bool        # 是否允许跑 scan（AI 决策，贵）
    allow_review: bool      # 是否允许跑 review（AI 复盘，贵）
    allow_trading: bool     # 是否允许执行交易 / 机械止损
    allow_dashboard: bool   # 是否允许 dashboard 刷新（只读）
    low_liquidity: bool     # 是否低流动性窗口（价格不可信）


PROFILES: dict[Session, SessionProfile] = {
    #                       scan   review trade  dash   low_liq
    Session.NIGHT:       SessionProfile(False, False, False, True,  True),
    Session.PREMARKET:   SessionProfile(True,  False, False, True,  False),
    Session.REGULAR:     SessionProfile(False, False, True,  True,  False),
    Session.AFTERHOURS:  SessionProfile(False, True,  False, True,  False),
    Session.MAINTENANCE: SessionProfile(False, False, False, True,  True),
}
```

### 4.2 时间工具（含跨日处理）

```python
def now_et() -> datetime:
    """当前 ET 时间（带时区）。ET 不可用时降级为 UTC 并标记。"""
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
    return dt.time().replace(second=0, microsecond=0)


def _in_window(t: time, start: time, end: time) -> bool:
    """时间窗口判定，**支持跨午夜**（start > end 表示跨日）。

    非跨日：start <= t < end
    跨  日：t >= start  或  t < end
    """
    if start <= end:
        return start <= t < end
    return t >= start or t < end
```

### 4.3 核心函数

```python
def current_session(now_et_: Optional[datetime] = None) -> Session:
    """返回当前所属时段。顺序敏感：先判跨日窗口，再判非跨日窗口。"""
    dt = _as_et(now_et_)
    t = _t(dt)

    # 1) Maintenance 20:00-21:00（非跨日，先判，避免被 AFTERHOURS 吞掉）
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
    # 5) 兜底：16:00-20:00
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
    """最后一个"已完成常规交易日"的日期。

    判定：
      · Regular 收盘后（>= 16:00，且非 Maintenance 造成的歧义）→ 今天
      · 否则 → 上一个工作日（跳过周末；**不处理节假日**，与现有实现保持一致）
    注意：夜盘时段属于"次一交易日的夜盘"，常规日仍是**昨天**。
    """
    dt = _as_et(now_et_)
    if _t(dt) >= REGULAR_CLOSE_ET:
        return dt.date()

    d = dt.date() - timedelta(days=1)
    while d.weekday() >= 5:      # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    return d
```

### 4.4 兼容层（供 Phase 3 平滑切换）

```python
def is_regular_session_open(now_et_: Optional[datetime] = None) -> bool:
    """兼容旧语义：常规时段是否开放（供 dashboard_export.us_regular_session_open）。"""
    return current_session(now_et_) is Session.REGULAR


def session_label(now_et_: Optional[datetime] = None) -> str:
    """人类可读标签，供日志 / dashboard 展示。"""
    return current_session(now_et_).value
```

---

## 5. 每个时段的策略映射

| 时段 | 窗口（ET） | scan | review | 交易 / 止损 | dashboard | 说明 |
|---|---|---|---|---|---|---|
| **Night** | 21:00→04:00 | ❌ | ❌ | ❌ | ✅（只读刷新） | 静默；低流动性，价格不可信 |
| **Pre-Market** | 04:00→09:30 | ✅ **1 次** | ❌ | ❌ | ✅ | 盘前定计划 |
| **Regular** | 09:30→16:00 | ❌ | ❌ | ✅ **每 15 分钟** | ✅ | 唯一执行窗口 |
| **After-Hours** | 16:00→20:00 | ❌ | ✅ **1 次** | ❌ | ✅ | 盘后复盘 |
| **Maintenance** | 20:00→21:00 | ❌ | ❌ | ❌ | ✅ | 系统维护窗口 |

### 5.1 与现有 schedule 的对应（不变 vs 待调整）

| workflow | 现有触发 | 对应时段 | 12-06 后是否需要调整 |
|---|---|---|---|
| scan | 手动（无 schedule） | Pre-Market（04:00–09:30 ET） | 见 §8 待确认 #4 |
| review | `cron '23 22 * * 1-5'` = 22:23 UTC | 夏令时 18:23 ET / 冬令时 17:23 ET → **After-Hours** | ✅ 已落在合规窗口 |
| dashboard-data | 每 15 分钟 | 全时段（各时段策略不同） | 见 §8 待确认 #3 |
| 盘中机械止损 | `--intraday-stop` | Regular | ✅ 无需调整 |

> 注：scan 目前**没有 schedule**（`scan.yml` 的 `on:` 块只有 `workflow_dispatch`），
> 属既有缺口，与 23h 无直接耦合——详见 `SCHEDULE_TRIGGER_INVESTIGATION.md`。

---

## 6. 迁移方案（分阶段）

### Phase 1 — 现在：只写文档，不动代码 ✅ 当前

- 产出：本文 `US_SESSION_DESIGN.md`
- 代码改动：**无**
- 风险：**零**

### Phase 2 — 12-06 前 2 周（~11-22）：抽模块，**行为不变**

| 步骤 | 内容 | 行为变化 |
|---|---|---|
| 2.1 | 新增 `_us_session.py`（§4 完整代码） | 无（新文件，无人调用） |
| 2.2 | 新增 `tests/test_us_session.py` | 无 |
| 2.3 | **常量回填**：让现有 9 处的硬编码常量改为 `from _us_session import REGULAR_OPEN_ET, REGULAR_CLOSE_ET` | **无**（值完全相同） |
| 2.4 | 全量测试 ≥ 当前基线（362 passed） | — |

**关键**：Phase 2 结束时，9 处的**值**与现在逐字节相同，只是来源变成模块。
这一步的产物是"可 revert 的纯加法"。

### Phase 3 — 12-06 前 1 周（~11-29）：切换调用点，**行为改变**

| # | 目标 | 改为 |
|---|---|---|
| 1 | `scan.py:164-176` `get_market_session_state` | 内部调 `current_session()`，返回枚举映射 |
| 2 | `scan.py:750-755` `_last_completed_regular_date_us` | 改为 `last_completed_regular_date()` |
| 3 | `scan.py:758-774` `_filter_completed_daily_bars` | 依赖 #2，随 #2 自动正确 |
| 4 | `scan.py:793-847` `get_premarket_snapshot_batch` | 门控改 `current_session() is Session.PREMARKET` |
| 5 | `portfolio_50000.py:624-656` 盘中止损守卫 | 改为 `is_trading_active()` |
| 6 | `dashboard_export.py:284-294` `us_regular_session_open` | 改为 `is_regular_session_open()` |
| 7 | `dashboard_export.py:587-620` prepost 取价 | 窗口表改为读 `PROFILES` |
| 8 | `review.py:78-92` `review_session_date` | 改为 `last_completed_regular_date()` |
| 9 | `quant_factor_price.py:60` | 改为 `last_completed_regular_date()` |

Phase 3 每处**独立 commit**，每处单独验证。

### Phase 4 — 12-06 当天：激活新时段逻辑

- 若 Phase 3 的切换已包含行为变化，则 Phase 4 **只是观察日**（无需再改代码）。
- 若采取"双逻辑并存 + 开关"方案，则 Phase 4 是**一次开关切换**（环境/日期门控）。
- 推荐：**Phase 3 直接改行为 + 单测覆盖**，Phase 4 只做线上观测，避免两套逻辑并存的风险。

### 6.1 每阶段的验证方式

| 阶段 | 验证 |
|---|---|
| Phase 2 | `pytest -q` 全绿 ≥ 362；grep 确认硬编码常量已消失 |
| Phase 3 | 每个调用点单测：构造 5 个时段的 `now_et`，断言行为符合 §5 表格 |
| Phase 4 | 12-06 当天人工观测 scan / review / dashboard 三个 workflow 的 run 结果 |

---

## 7. 回滚

| 阶段 | 回滚方式 | 代价 |
|---|---|---|
| Phase 2 | `git revert` 单个 commit（纯加法） | 零（无行为变化可回滚） |
| Phase 3 | 逐处 `git revert`（每个调用点独立 commit） | 低（每次只回退一处） |
| Phase 4 | 若为开关方案 → 关开关；若为直接改行为 → `git revert` 该 commit | 中（需重跑一次 scan/review） |

**关键保障**：Phase 2 与 Phase 3 均为"新模块 + 调用点切换"的**加法式改造**，
旧逻辑在 git 历史里完整保留，任何时候都可以干净回退。
Phase 4 若采用双逻辑并存方案，旧逻辑在运行期也可切回。

---

## 8. 待确认问题

| # | 问题 | 现状 / 影响 | 建议倾向 |
|---|---|---|---|
| 1 | 盘中止损是否覆盖盘前/盘后（04:00–09:30 / 16:00–20:00）？ | 现状守卫仅 `09:30–16:00`；扩到盘前盘后会增加误触发（流动性中等、价格噪音大） | **暂不覆盖**，保持仅 Regular；如要覆盖需单独评估 |
| 2 | 夜盘是否只做"价格刷新"（零 AI 只读）？ | 现状 dashboard-data 每 15 分钟刷新；夜盘 1% 成交量 + 机构仅 7% | **是**，夜盘零 AI、只读刷新、不触发任何决策 |
| 3 | 维护窗口（20:00–21:00）内 dashboard-data 是否继续跑？ | 现状每 15 分钟无条件跑；维护窗口数据源可能不可用 | **继续跑但容错**：取价失败保留上次值，不报错、不写坏数据 |
| 4 | scan / review 触发时点是否相应调整？ | scan 无 schedule（既有缺口）；review 22:23 UTC 已落 After-Hours | review **不改**；scan 需补 schedule 时按 §5 落在 Pre-Market |

### 8.1 补充：两个实现层面的待验证项

| 项 | 说明 | 何时验证 |
|---|---|---|
| **Yahoo 夜盘 1m 数据可得性** | `prepost=True` 能否覆盖 21:00–04:00 ET 的 Night Session（静态无法判定） | Phase 2 期间实测一次 |
| **节假日处理** | `last_completed_regular_date()` 当前只跳周末、不处理节假日（与现有实现一致） | 若需精确，Phase 3 引入交易日历 |

---

## 9. 附：铁律确认

- 本文件为**设计文档**，仓库 `/tmp/us` **任何文件未改动**（无新增 / 修改 / 删除）。
- 未执行 `git push` / `git rebase` / `git commit`。
- 未调用任何 AI。
- 未运行任何会修改数据的 `.py`。
- 撰写当天（周一）21:00 的 scan 与每 15 分钟的 dashboard-data 均未受干扰。
