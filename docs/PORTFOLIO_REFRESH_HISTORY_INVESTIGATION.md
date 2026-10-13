# 50k 组合价格刷新跟随 dashboard-data 历史调查

> 只读调查 · 未改代码 · 未 push/rebase · 未碰监控
> 调查对象仓库：`/tmp/us`（HEAD = `c492601` → 含后续新闻修复 `a42233f`）
> 调查时间：2026-10-09

## 结论速览

**用户记忆"以前跟随 dashboard-data 一起更新"不成立。** 经 git 全历史核查，`portfolio_50000.py` 这个模块本身直到 **2026-10-06 19:22 北京**才随 `review.yml` 一起被创建，且**从诞生那一刻起，唯一触发点就是 `review.yml`**。`dashboard-data.yml` 在其整个 git 生命史中**从未**包含 `portfolio_50000`、`portfolio`、`ledger`、`positions.csv`、`transactions.csv` 任何引用。

→ 归属 **选项 B：从来没有**。这不是"被移除后又想恢复"，而是需要**新建**一个跟随刷新机制。

---

## 1. dashboard-data.yml 的 git 历史摘要

```
1266a4b chore: pin production python dependencies
2eaf13d chore(ci): unify Python runtime to 3.12 across all workflows
20a29e5 fix(ci): prevent dashboard-data retry from deleting concurrent files
59f350e fix(dashboard): stabilize data commits and disable legacy mirror
5d65f84 fix(workflow): refresh dashboard when runtime collector changes
06a44d4 feat(dashboard): add scan/review runtime status and drop email
2e77f4b fix(ci): dashboard-data 推送冲突时 rebase 重试，避免并发定时任务撞车丢数据
bc02357 feat(dashboard): 工作日 24h 每 15 分钟刷新 + Core/Observation AI 渲染分级
912fc07 fix(dashboard): 无 pending CSV 时复用上一版 dashboard_data.json 的名单并照常刷新行情
d738b92 chore(dashboard): 定时改为美东 04:00-20:00 每 15 分钟 (*/15 8-23 * * 1-5)
c17b9f8 fix(dashboard): 无 pending CSV 时优雅降级
1d6a699 feat(dashboard): 24 小时每 10 分钟刷新 + 盘前盘后行情 + ...
825ef62 chore(dashboard): 盘中刷新改为 5 分钟 + 前端三文件平铺到根目录
ed4543a feat(dashboard): 阶段 C 数据链路 + 阶段 D GitHub Actions 行情刷新
```

可见 dashboard-data.yml 的职能演进始终围绕 **`dashboard_export.py` / `fetch_runtimes.py` / `summarize_run.py`** 这三条，从未触碰投资组合账本。

## 2. portfolio_50000.py 是否曾在其中被调用

两个独立口径都返回**空**：

```bash
# 口径 A：精确模块名
git log -p --all -- .github/workflows/dashboard-data.yml | grep -n "portfolio_50000"
# （无输出）

# 口径 B：宽泛（portfolio / ledger / positions.csv / transactions.csv）
git log -p --all -- .github/workflows/dashboard-data.yml | grep -niE "portfolio|ledger|positions\.csv|transactions\.csv"
# （无输出）
```

仓库历史上**唯一存在过的 portfolio 脚本**就是下面这组（均诞生于 `99d14d1`）：

```
portfolio_50000.py
portfolio_50000_positions.csv
portfolio_50000_transactions.csv
portfolio_50000_history.csv
portfolio_50000_meta.json
tests/test_portfolio_50000.py
# 注：portfolio_target.py 是更晚的 ENABLE_TARGET_FILE 实验模块，与 50k 主账本无关
```

其中没有任何一个在 dashboard-data.yml 的任一历史版本里出现过。

## 3. 移除的 commit SHA / 原因

**不存在"移除"事件**——因为从未加入过。无相关 commit SHA、无 commit message。

## 4. review.yml 何时接管

`review.yml` 本身很早就有（`0d15769` Create review.yml），但**调用 `portfolio_50000.py` 是在模块诞生那次提交**：

```
99d14d1075b31d3ad19b013b18c77267f41a13cd
Author: wijouyang-lab <wijouyang@gmail.com>
Date:   Tue Oct 6 19:22:05 2026 +0800
Subject: feat(portfolio): add $50,000 long-term simulated portfolio ledger

 .github/workflows/review.yml  |  17 ++
 portfolio_50000.py            | 534 +++++++++++++++++++++++++++++++++++++++++++
 ...
```

`review.yml` 当前（第 56–57 行）步骤：

```yaml
- name: 更新 $50,000 Portfolio Ledger
  run: python portfolio_50000.py --data-dir .
```

触发时段：`schedule: '23 22 * * 1-5'` = **周一~周五 22:00 UTC = 北京次日 06:00（盘后）**，每天只跑一次。commit 阶段（第 83–87 行）显式把 4 个 portfolio CSV 入库。

## 5. 当前是否可安全"恢复"

没有"恢复"对象。但**新建跟随刷新是可行且有价值的**——前提是规避下面 3 个真实风险（详见第 6 节）。

关键事实：`portfolio_50000.py::run()` 的定价逻辑是**幂等且每次都重取价**（`portfolio_50000.py:429` 起）：

```python
# run() 第 3 步 盯市（:462-468）
open_tickers = sorted({... for p in positions if Status == "OPEN"})
prices = {} if offline else fetch_last_closes(open_tickers)   # 无条件重取
stock_value, unrealized = mark_to_market(positions, prices, today)
```

- `fetch_last_closes()`（:140-162）对每个 OPEN ticker 调 `yf.Ticker(t).history(period="5d", auto_adjust=False)["Close"].iloc[-1]`，**每次跑都打实时行情**。
- `mark_to_market()`（:381-406，写回在 :399）只覆盖 `Status == "OPEN"` 的仓位 `Current_Price`，CLOSED 仓位保留历史价格。
- `upsert_history()`（:419-425）按交易日去重，同日重复跑只覆盖当天那一行。

→ 把 `run()` 挂到每 15 分钟跑一次，**技术上确实会每 15 分钟重定价**（且交易时段内 `.iloc[-1]` 是当日盘中价，不是昨收；盘后/夜盘才退化成当日收盘）。所以"跟随刷新"的效果可达成。

但有 3 个阻断性问题必须先解决：

1. **`run()` 不只定价，还处理买卖**（`process_sells`/`process_buys`，:442-445）。它会读推荐 CSV、改 `positions`/`transactions`。若 dashboard-data 每 15 分钟跑一次，等于让投资组合在 review 之前就自行执行 scan 推荐，与 `review.yml`（盘后先跑 `review.py`）**抢同一份推荐 CSV**，可能造成时序错乱或重复入账风险（虽标称"幂等"，但交易执行时点被前移，审计语义变味）。
2. **`dashboard-data.yml` 的 commit 范围守卫**只放行 3 个文件（:139、:148、:172、:175）：
   ```
   ^dashboard/data/(dashboard_data\.json|last_run\.json|last_run\.log)$
   ```
   即便加了 portfolio 步骤，portfolio CSV **会被守卫拒绝提交**，推不出去。
3. **并发冲突**：dashboard-data 用自己的并发组 `dashboard-data-refresh`（:38-44），review 用 `us-stock-review`（:11-13）。两者会**同时写 `portfolio_50000_positions.csv`** → 文件级 race，且 dashboard-data 的并发重试用 `reset --soft` 重建提交（:166-171），可能把 review 刚提交的 portfolio 快照误判为删除。

结论：**直接把 `python portfolio_50000.py` 塞进 dashboard-data.yml 不安全**，需要按第 6 节方案改造。

## 6. 建议（仅列出，不实施）

| 方案 | 做法 | 优点 | 风险/代价 |
|------|------|------|-----------|
| **A. 新增 `--price-only` 模式** | 给 `portfolio_50000.py` 加 flag，跳过 `process_sells/buys`、只跑 `fetch_last_closes`+`mark_to_market`，改写 `positions.csv` 的 `Current_Price`/`Market_Value`/`Last_Update` | 改动最小，复用现有定价函数 | 仍要扩展 dashboard-data 的 commit 守卫；与 review 仍有写同一 CSV 的并发冲突 |
| **B.（推荐）独立轻量 workflow** | 新建 `portfolio-price-refresh.yml`：工作日 `*/15 * * * 1-5`，调用 `portfolio_50000.py --price-only`，**独立并发组**（不与 review 互斥），只 add+commit `portfolio_50000_positions.csv` | 与 dashboard-data、review 三者职责清晰；并发隔离；不污染 dashboard-data 的提交守卫 | 多一个 workflow；需新增 `--price-only` 分支 |
| **C. 在 dashboard_export 内联取价** | 让 `dashboard_export.build_portfolio` 直接调 `fetch_last_closes` | 单次运行内聚 | **破坏现有设计铁律**（导出层只读 CSV 透传，不取实时价）；会拖慢每 15 分钟导出且混入定价职责，不推荐 |

**落地前的必做清单（若用户决定实施）：**

1. 给 `portfolio_50000.py` 增加 `--price-only`：跳过推荐处理，仅盯市写回 OPEN 仓位的 `Current_Price`。
2. 选方案 B：独立 workflow + 独立并发组，避免与 `review.yml` 抢写 portfolio CSV。
3. review 的盘后跑仍负责"交易执行 + 快照"，price-only workflow 只负责"日内价格跟随"，两者**写同一文件但职责不重叠**（review 写交易后全量，price-only 只改价格字段）。
4. 注意时段语义：`run()` 用的是 `history(period="5d")` 默认日线 → 交易时段内 `.iloc[-1]` 为当日盘中价（接近实时），盘后/夜盘退化为当日收盘。若用户要的是"盘前/盘后价"，需另加 `prepost=True` 的取价分支（属另一项改造，不在本调查范围）。

## 附：与上一轮价格来源调查的衔接

- `Current_Price` 来源（`PORTFOLIO_PRICE_SOURCE_INVESTIGATION.md`）：`fetch_last_closes` 默认 `prepost=False` → **纯 EOD 收盘价**，不含盘前/盘后/夜盘。
- 本轮补充：`run()` **每次都重取价**，所以只要把触发频率提到每 15 分钟（方案 B），`Current_Price` 就会按"当日盘中价/收盘"跟随刷新；但**仍不会自动变成盘前/盘后扩展时段价**，除非再改 `fetch_last_closes` 的 `prepost` 参数。
