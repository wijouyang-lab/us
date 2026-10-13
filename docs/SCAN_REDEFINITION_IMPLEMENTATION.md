# Scan 角色重定义 — 本地实现报告（选 B：抽独立模块）

> 判决前本地实施，严格隔离：不 commit / 不 push / 不 rebase、不碰监控 PID 536931、
> 不跑真实 scan（不触网 / 不调真实 AI）、不碰 us-market-terminal/。
> 生成时间：2026-10-08（判决前）。

---

## 1. quant_filter.py 函数清单

新建 `/tmp/us/quant_filter.py`，**纯函数模块**：无模块级 sys.exit、无时间门控、无环境变量校验、不触网、不写文件（`load_positions` 例外，只读传入路径），可在任意 Python 3.12 环境直接 `import quant_filter`（不 import scan）。

| 函数 | 签名 | 职责 |
|---|---|---|
| `compute_20d_high` | `(df) -> float\|None` | 前 20 日高点 = 日线 `High` 列最近 20 个有效值的 `max`；缺列/全 NaN/空 → `None` |
| `compute_rr_ratio` | `(price, stop_loss, target) -> float\|None` | R/R = `(target - price) / (price - stop_loss)`；止损 ≥ 现价 → `None`（fail-closed） |
| `strict_filter` | `(rows) -> list[dict]` | 严筛：评分≥90 & R/R≥2.0 & 2%≤止损距离≤5% & ≤1只/板块 → ≤3 只（评分降序） |
| `load_positions` | `(path) -> list[str]` | 读 `portfolio_50000_positions.csv` 返回持仓 Ticker 列表（大写去重）；缺失/异常/空 → `[]` |
| `build_ai_input` | `(pool_data, positions, candidates) -> list[dict]` | 收缩 AI 输入：持仓（从 pool_data 补全字段，强制 Core_Dragon）+ ≤3 候选 → ≤7 只去重 |

模块级常量：`MIN_SCORE=90` / `MIN_RR=2.0` / `MIN_STOP_DIST=0.02` / `MAX_STOP_DIST=0.05` / `MAX_CANDIDATES=3` / `DEFAULT_STOP_PCT=0.05` / `AI_INPUT_MAX=7`。
私有辅助（同模块纯函数）：`_to_float` / `_last_n_max` / `_stop_distance` / `_score_of` / `_price_of` / `_stop_of`。

---

## 2. scan.py 改动摘要（import 替换点）

只做「搬函数 + 换调用」，**输出路径、AI 调用点、写文件逻辑零改动**。

| 位置 | 改动 |
|---|---|
| `:53-58` | 新增 `from quant_filter import build_ai_input, compute_20d_high, load_positions, strict_filter` |
| `:25` | 删除 `import math`（仅内联函数用过，搬走后 scan.py 不再需要） |
| `:59-70` | 删除 6 个 `STRICT_FILTER_*` 常量 + 内联函数块，仅保留 `POSITIONS_CSV_PATH = "portfolio_50000_positions.csv"` |
| `get_kline_data` 之后 | 删除 207 行内联纯函数块（`compute_target_price_20d_high` / `compute_stop_distance_pct` / `compute_rr_ratio` / `load_portfolio_positions` / `enrich_positions_with_pool` / `strict_filter_candidates` / `build_ai_analysis_input`） |
| `__main__` 编排层 | 改为调用模块函数：`load_positions()` → 剔除持仓 → `compute_20d_high(get_kline_data())` 补目标价 → `strict_filter(redef_eligible)` → `build_ai_input(pool_data, positions, candidates)` |

**未改动（保留上一轮已定的行为变更）**：`match_pool_to_report` 的 `Observation → Candidate` 标签、`_is_position` 强制 Core_Dragon、`generate_ai_report` / `match_pool_to_report` 输入从 `pool_data` → `ai_input`、写盘循环标签过滤。

---

## 3. 行为一致性对照（改前 vs 改后逐项）

| 能力 | 改前（内联版） | 改后（模块版） | 输出是否一致 |
|---|---|---|---|
| 前 20 日高点 | `compute_target_price_20d_high(highs: Series)` | `compute_20d_high(df: DataFrame)`（内部取 `df["High"]`） | ✅ 同为 `max(High[-20:])`，仅入参形态调整 |
| R/R 计算 | `compute_rr_ratio(price, target_price, stop_price)` | `compute_rr_ratio(price, stop_loss, target)` | ✅ 同公式 `(目标-现价)/(现价-止损)`，参数顺序按新规格 |
| 止损距离 | `compute_stop_distance_pct` | `_stop_distance`（模块私有） | ✅ 同为 `(现价-止损)/现价` |
| 严筛 | `strict_filter_candidates(eligible, positions)`（内部排除持仓） | `strict_filter(rows)`（持仓排除上移到编排层 `redef_eligible`） | ✅ 阈值/排序/≤3 一致；持仓不抢候选位由编排层保证 |
| 读持仓 | `load_portfolio_positions` → dict 列表 | `load_positions` → Ticker 列表 | ⚠️ 返回形态简化（Ticker 列表），Stop_Loss 改由 pool 补全 |
| AI 输入收缩 | `enrich_positions_with_pool` + `build_ai_analysis_input` | `build_ai_input(pool_data, positions, candidates)`（富化折叠进单函数） | ✅ 持仓优先去重、≤7、持仓=Core_Dragon/候选=Candidate 一致 |

> 唯一形态差异：持仓 `Stop_Loss` 不再从 CSV 读取（`load_positions` 只返回 Ticker），改由 `build_ai_input` 从 pool_data 的 ATR 止损字段补全——语义等价，且符合"持仓每日重评分复用 scan 池字段"的设计。

---

## 4. 测试结果

- **`tests/test_quant_filter.py`**：`26 passed`（0 fail），覆盖 20 日高点（正常/不足/NaN/全 NaN/缺列）、R/R（正常/止损≥现价/目标≤现价/None 入参）、严筛（全过/评分<90/R/R<2/止损距离越界/板块重复/≤3/降序/缺目标价/诊断字段）、load_positions（存在/缺失/空/None）、AI 输入收缩（持仓≥3/<3/无候选/去重+硬顶）。
- **全量 `tests/`**：`217 passed`（= 191 基线 + 26 新增，**0 回归**）。
- **`py_compile`**：`quant_filter.py` + `scan.py` 均通过。
- 无硬编码绝对日期、无真实 AI/网络调用（`load_positions` 用 `tmp_path` 临时文件）。

---

## 5. evolve.yml / dashboard BUCKET_MAP 改动

- **`.github/workflows/evolve.yml`**：
  - cron `'37 2 * * 6'` → `'0 2 1 * *'`（每月 1 号 02:00 UTC）。
  - 删除周六门控（`BJ_DOW=="6"` & `BJ_DAY<=7` 判断），`SHOULD_RUN=true` 直通，`grep BJ_DOW` 已无命中。
- **`dashboard_export.py`**：`BUCKET_MAP` 增加 `"Candidate": "Candidate"`（`Observation` 自然归零）。

---

## 6. git 状态（未 commit，无污染）

```
 M .github/workflows/evolve.yml
 M dashboard_export.py
 M scan.py
?? quant_filter.py
?? tests/test_quant_filter.py
```

- HEAD 仍为 `0a76ac6`，**未 commit / 未 push / 未 rebase / 未 fetch**。
- `__pycache__/*.pyc` 已还原（无 pyc 污染）；未碰 us-market-terminal/；未写任何生产数据文件（trade_history.csv / Core_Dragon.json / 因子快照等均未改动）。

---

## 7. 距判决剩余时间

> **约 6 小时 49 分**（当前 UTC ≈ 06:18，目标 10-08 13:07 UTC）。

判决后按此实现顺序推进：严筛层（已就绪）→ AI 输入收缩（已就绪）→ trade_history schema → 换股规则 → 冷启动开关 → dashboard 兼容（BUCKET_MAP 已就绪）→ evolve cron+删门控（已就绪）→ 回归测试（当前 217 passed 保底）。
