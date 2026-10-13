# Trade History 数据质量修复专项 — 交付报告

## 结论：两个 P1 问题均已修复并部署，duplicate = 0，float pollution = 0

| 项 | Before | After |
|---|---|---|
| trade_history 行数 | 414 | **373** |
| duplicate event | 41 | **0** |
| Buy Price 浮点尾数 | 155 条 | **0** |
| Exit_Price / Close_Price 浮点尾数 | 17 / 143 条 | **0** |
| review_history Rec_Price / Cur_Price 浮点尾数 | 1281 / 1250 条 | **0** |

---

## A. Duplicate 根因（实证）

41 个 duplicate event（82 行冗余）是**历史遗留**，分两批、两种成因：

| 批次 | 数量 | 成因 |
|---|---|---|
| 2026-06-02/03/04 | 36 个（字段更新型：Hold_Period/Stop_Loss 一行 N/A/观望、另一行具体值） | 早期代码版本的入账逻辑无事件级去重 |
| 2026-09-22 | 5 个（完全重复） | `6f6a6b9 "Add files via upload"`（09-23 手动上传 commit）覆盖 trade_history.csv 时引入 |

**关键证据**：`6f6a6b9` commit 的 stat 显示 `trade_history.csv | 730 ++++...`（411 insertions / 391 deletions）且同时改了 `us_stocks_pending_20260922.csv(.processed)`。

**当前代码不再产生 duplicate**：`supplement_us_stocks_from_pending()` 已用 `find_existing_record(Date+Ticker)` 拦截重复入账；本次又加 `deduplicate_trade_history()` 作为写入前/读取时的防御层。

## B. Canonical Record 规则（已写进代码注释 + 测试）

Review Event Key = `Ticker|Date|Tag`（大写 Ticker、日期归一 YYYY-MM-DD）。

对同一 key 的多行：
1. 优先保留**信息更完整**的一行 —— `Hold_Period` / `Stop_Loss` 越"非空/非 N/A/非观望"优先级越高；
2. 完整性相同则稳定保留最先出现的行（stable sort + keep='first'）；
3. **关键业务字段（Price / Exit_Date / Exit_Price / Status / PnL）在 41 个 duplicate 间实测 100% 一致**，因此该规则不丢失任何交易状态。

实测验证：41 个 duplicate key 中，业务字段不一致的 key 数 = **0**；保留行均为信息最完整 = **True**。

## C. 41 个 duplicate event 处理

全部按 canonical 规则去重：移除 41 行冗余，保留 41 行信息最完整的 canonical record。备份存于 `/tmp/trade_history.backup_20261007_*.csv`（两份）。

## D/E. trade_history 与 Buy Price before/after

- 行数：414 → 373（-41 duplicate）
- unique event：373 → 373（非重复事件 **332 个完全不变**）
- Price（Buy Price）：`479.8800048828125` → `479.88`，`483.2999877929688` → `483.30`（保留尾零）

## F/G. 测试

| 项 | 结果 |
|---|---|
| 新增测试 `test_trade_history_quality.py` | **23 / 23 PASS**（覆盖 13 项要求 + 边界） |
| 全量脚本式测试 | **646 / 646 PASS**（623 原有 + 23 新增，0 回归） |
| py_compile（3.11 / 3.12） | 全 PASS |
| git diff --check | PASS |

## H. Review 实跑结果（隔离环境，3.12）

`python review.py` **exit 0**，完整跑通。清理前后 KPI **完全一致**（证明去重未改变任何统计语义）：

- Scan推荐 111 笔；Core 19 / Observation 92
- Core 已完成 25.00%、Core 当前 46.67%、Observation 当前 46.48%
- Milestone：5D 47.13% / 10D 50.00% / 20D 49.15%

## I/J/K. PnL / Win Rate / Stop Loss 是否变化

| 项 | 结论 |
|---|---|
| PnL | **不变**（round 只改显示精度，不改变数值语义，PnL 公式零改动） |
| Win Rate | **不变**（Review 实跑 KPI 与清理前逐项一致） |
| Stop Loss | **不变**（canonical 规则保留信息完整行，且业务字段一致） |

## L. MSFT 回归结果

| 项 | 值 |
|---|---|
| trade_history MSFT Price | `479.88`（两位小数，原 `479.8800048828125`） |
| review_history 2026-08-21 Rec_Price | `479.88` |
| MSFT Rec_Price 浮点尾数 | **0** |
| 价格来源 | 仍为推荐日真实 Open（代码零改动，仅 round 持久化） |

## 修改 / 新增文件

| 文件 | 改动 | 必要性 |
|---|---|---|
| `review.py`（改） | +18/-4：import 质量层；`load_trade_history` 加去重；3 处价格 `fmt_price` | 幂等防重复 + 价格精度 |
| `trade_history_quality.py`（新） | 纯函数层：`deduplicate_trade_history` / `fmt_price` / `review_event_key` / `field_is_informative` | 与测试共享同一规则，避免口径漂移 |
| `tests/test_trade_history_quality.py`（新） | 23 项回归测试 | 固化 canonical 规则 |
| `trade_history.csv`（改） | 去重 41 行 + 价格 round | 历史数据清理 |
| `review_history.csv`（改） | Rec_Price/Cur_Price round | 历史浮点清理 |

**零改动**：scan.py / portfolio / dashboard / options / Quant 1-7 / workflow / strategy_params（违禁文件全部未触碰）。

## M/N. Git

| 项 | 值 |
|---|---|
| commit SHA | `728722c`（rebase 前 `802efd5`） |
| push | ✅ 无 force（`2561963..728722c`） |
| HEAD == origin/main | ✅ **TRUE** |

## O/P. 遗留状态

- **duplicate：0**（trade_history 373 行 = 373 unique）
- **float pollution：0**（trade_history 全部价格字段 + review_history Rec_Price/Cur_Price 均归零）
- 未处理（按约束刻意保留）：pytest INTERNALERROR、Forward Return 双实现、Python 版本分裂、Quant workflow 入口、9 个 tracked .pyc —— 均为 P2/P3，本次不碰。

---

## 一句话总结

去重规则（保留信息最完整行）经过"业务字段 100% 一致 + 保留行均为最完整"双重验证后落地，41 个 duplicate 安全移除；价格浮点污染从源头（review.py 3 处未 round）到历史数据（trade_history + review_history 全量 round）彻底清理。全量 646/646 测试通过，Review 实跑 exit 0 且 KPI 零漂移，已推送并保持 HEAD == origin/main。
