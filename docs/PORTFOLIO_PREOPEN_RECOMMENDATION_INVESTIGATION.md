# 盘前推荐机制调查报告（scan 写推荐 + review 补成交价 可行性）

> 类型：**只读调查**，未改任何代码、未 push/rebase、未碰监控。
> 时间：2026-10-09 14:04 GMT+8
> 背景：用户要做自动量化交易，要求 scan（盘前）写"50k 今日推荐"（Ticker+参考价），review（盘后）补成交价（开盘价）+技术，防前视偏差。
> 铁律：只读；今晚 21:00 首次外部触发验证前不改任何东西。

---

## 0. 一句话结论

**用户要的"scan 写推荐 + review 补成交价"在数据层已经大部分实现**，且防前视偏差已结构性成立：

- scan 盘前已写推荐 + 参考价 → `us_stocks_pending_{YYYYMMDD}.csv`（`Scan_Ref_Price`）。
- review 盘后已把真实开盘价填入 → `trade_history.csv.Price`（= 推荐日真实 Open）。
- 参考价（盘前）与成交价（盘后）来自不同时点，天然无前视偏差。

**真正的差距不在后端架构，而在两点**：
1. `portfolio_50000_positions.csv`（50k 持仓结构）只在 review 跑完后生成，盘前不含新推荐；
2. 前端没有专门的"今日推荐（盘前锁定 / 盘后填价）"面板——scan 推荐虽然在 `STOCKS[]` 里（置灰 `pending`），但用户看的"持仓卡片"区只渲染已填成交价的 OPEN 持仓，所以"看不到"。

属于**"部分已实现，前端/数据标签未显式化"**，不是需要新架构的从零项目。

---

## 1. scan 阶段实际写入的文件清单（已核实）

源码 `/tmp/us/scan.py`，写入点逐行核对。scan.yml 负责把这些文件 commit+push。

| 写入文件 | 代码位置 | 内容 | 是否"50k/推荐"相关 |
|---------|---------|------|------|
| `us_stocks_pending_{YYYYMMDD}.csv` | scan.py:3895 | **今日推荐候选**：Ticker/Name/Tag/Prev_Close/Premarket_Price/**Scan_Ref_Price**/全套技术+基本面+AI 六段，`Status="pending"` | ✅ 就是"今日推荐" |
| `ai_text_cache.csv` | scan.py:3919 | 按 Ticker upsert AI 六段文本 | 推荐附属 |
| `ai_snapshot.csv` | scan.py:3933 | 按 (Ticker,Rec_Date,Tag) 持久化六段 | 推荐附属 |
| `option_strategies.csv` | scan.yml 步骤 | 期权策略账本 | 否 |
| `quant_factor_snapshot.csv` | scan.py:2544 | 因子快照 | 否 |
| `quant_factor_price_history.csv` | scan.yml `更新 Quant 价格历史` 步 | 价格历史 | 否 |
| `scan_version.txt` | scan.py:253 | 版本哈希 | 否 |

**关键事实**：
- scan.py **不写任何 `portfolio_50000_*` 文件**。它只**读** `portfolio_50000_positions.csv`（scan.py:3751，取 OPEN 持仓 Ticker 用于新闻注入）。
- scan.py **只读不写** `trade_history.csv`（scan.py:2344/2371/2448/3846，用于风控禁入/去重）。
- 所以 **scan 不直接产出 50k 持仓/成交/历史三件套**。它们由 review.yml 末尾调 `portfolio_50000.py` 从 `trade_history.csv` 派生（见 §2）。

---

## 2. 现有推荐机制（trade_history / pending）与完整链路

### 2.1 三个核心文件的角色

| 文件 | 写入者 | 何时写 | 承载的语义 |
|------|--------|--------|-----------|
| `us_stocks_pending_{YYYYMMDD}.csv` | **scan.py** | 盘前 | 今日推荐候选 + **参考价（Scan_Ref_Price，盘前/昨收）** + 技术/AI；`Status="pending"`；**无成交价** |
| `trade_history.csv` | **review.py** | 盘后 | 把 pending 转为正式推荐事件，写入 `Price`=**推荐日真实 Open（成交价）**、Status、技术字段；活跃持仓账本 |
| `review_history.csv` | **review.py** | 盘后 | 每日快照：里程碑 5D/10D/20D、Review_Stage、Cur_Price 兜底 |
| `portfolio_50000_positions.csv` | **portfolio_50000.py**（review.yml:55-57 调用） | review 后 | 50k 组合 OPEN 持仓：`Entry_Price`=成交价、`Recommendation_ID` 回链 trade_history |
| `portfolio_50000_transactions.csv` / `portfolio_50000_history.csv` | 同上 | review 后 | 成交明细 / 历史序列 |

### 2.2 完整链路（scan → review → 50k）

```
[盘前] scan.py
   └─> us_stocks_pending_YYYYMMDD.csv   ← 今日推荐 + 参考价 (Scan_Ref_Price)，Status=pending
        ├─> ai_text_cache.csv / ai_snapshot.csv (AI 六段)
        └─> (读 trade_history.csv 做风控禁入/去重，不写)

[盘后] review.py
   ├─> trade_history.csv                ← 填成交价 Price=推荐日真实 Open + 技术/Status
   ├─> review_history.csv               ← 每日快照
   └─> option_strategies.csv

[review 后] review.yml 调 portfolio_50000.py --data-dir .
   └─> portfolio_50000_positions.csv / transactions.csv / history.csv   ← 50k 三件套（OPEN 持仓含成交价）
```

### 2.3 防前视偏差已成立

- `pending.Scan_Ref_Price` = `item.get("Price", item.get("Open_Price"))`（scan.py:3905），是 scan 盘前基于昨收+盘前数据算出的**参考价**，非未来开盘价。
- `trade_history.Price` = review.py:438 文档明确："正式买入价 = trade_history 的 Price 字段 = 推荐日真实 Open"。
- 两者时点不同、来源不同 → **结构上无前视偏差**。前端 `app.js:214` `recPrice = 正式买入价（=推荐日真实 Open，缺失为 null）` 也印证：盘前（review 未跑）`recPrice` 为 null，盘后回填。

---

## 3. 用户需求 vs 现状的差距

| 用户需求 | 现状 | 差距 |
|---------|------|------|
| scan 盘前写"50k 今日推荐"(Ticker+参考价) | scan 盘前已写 `us_stocks_pending_*.csv`（Ticker + Scan_Ref_Price） | ✅ 已有，但文件叫 pending 不叫"50k 推荐" |
| 参考价来源 = 昨收 + 盘前 | `Scan_Ref_Price` = 昨收/盘前价 | ✅ 一致 |
| review 盘后补成交价(开盘价) | `trade_history.Price` = 真实 Open | ✅ 已实现 |
| review 补技术数据 | review 写技术字段到 trade_history | ✅ 已实现 |
| 防前视偏差 | 参考价≠成交价，时点分离 | ✅ 已成立 |
| **"50k 组合"盘前即见今日推荐** | `portfolio_50000_positions.csv` 仅 review 后生成，盘前不含新推荐 | ❌ 缺口 1 |
| **前端显式"今日推荐"面板** | scan 推荐在 `STOCKS[]`（置灰 pending），但无专门面板；持仓卡片只显 OPEN 持仓 | ❌ 缺口 2 |

**判断**：属于**部分已实现 + 显式化缺失**，不是需要新架构。后端"scan 写推荐 + review 补成交"的语义已落地；缺的是把 pending 推荐**显式呈现为 50k 盘前推荐**，以及前端面板。

---

## 4. 改动方案对比（若要落地）

### 方案 A —— 最小改动：复用 pending，只加前端"今日推荐"面板（推荐先做）

- 思路：scan 已产出 pending（含 `Scan_Ref_Price`/`pending_price`），`dashboard_export.py` 已把 `pending_price` 透传到 `stocks[]`（`dashboard_export.py:1253,975`）。只需前端新增一个面板，读 `STOCKS[]` 中 `status==='pending'` 或 `META.pending_csv`，展示 Ticker + 参考价；review 跑完成交价回填后该条 status 变 OPEN/active，面板自动更新。
- 改动文件：`app.js`（新增 `renderPreopenRecommendations()` + CSS）。**不动 scan/review/portfolio_50000/dashboard_export。**
- 改动半径：~80–150 行新增；0 数据迁移；0 Python。
- 优点：零后端风险，最快满足"盘前看到今日推荐"。
- 缺点：50k 持仓结构盘前仍不含这些推荐（逻辑上它们还没建仓），但可视化诉求已满足。

### 方案 B —— 中改动：scan 盘前即把推荐写进 50k 持仓结构

- 思路：scan.py 写 pending 之后，新增一步把当日 chosen 项以 `Status=PENDING` + 参考价写入 `portfolio_50000_positions.csv`（或新文件 `portfolio_50000_pending.csv`）；review 跑时把 `PENDING→OPEN` 并填成交价。使"50k 组合盘前即含今日推荐"，与用户心智完全一致。
- 改动文件：`scan.py`（+seed pending 逻辑 ~60–100 行）、`portfolio_50000.py`（抽取可复用函数）、`review.py`（PENDING→OPEN 更新）、`app.js`（持仓卡片支持 PENDING 状态显示参考价）、`dashboard_export.py`（可选透传）。
- 改动半径：~200–400 行；需处理**幂等**（同天重跑 scan 不重复建仓）、与现有"portfolio_50000.py 从 trade_history 派生"逻辑协调；需回归测试。
- 优点：50k 持仓结构盘前即含今日推荐，最贴合需求描述。
- 缺点：改动面较大，需谨慎协调权威数据源（避免 scan seed 与 review 派生互相覆盖）。

### 方案 C —— 架构级：独立 fill 步骤（不推荐）

- review 不再填成交价，改由开盘后独立步骤跑；scan 负责全部推荐+参考价+预建仓。
- 改动半径大、风险高，而 review 填成交价已工作良好 → **不建议**。

**建议路径**：先上方案 A（看到盘前推荐），若确需"50k 持仓盘前即含推荐"再上方案 B。

---

## 5. 改动半径评估

| 方案 | 涉及文件 | 估算行数 | 数据迁移 | Python 改动 | 风险 |
|------|---------|---------|---------|------------|------|
| A | `app.js`(+CSS) | 80–150 | 无 | 无 | 低 |
| B | `scan.py`+`portfolio_50000.py`+`review.py`+`app.js`(+`dashboard_export.py`可选) | 200–400 | 无（复用 pending） | 有（需幂等/协调） | 中 |
| C | 多文件重构 | 500+ | 有 | 有 | 高 |

> 铁律友好度：方案 A 完全符合"不改 Python、不碰后端、今晚 21:00 前不动"——可在 21:00 外部触发验证完成后再做。方案 B 涉及后端，需专项实施 + 测试，不在本次只读范围内。

---

## 6. 前端当前显示的是什么（为什么用户"看不到 scan 的推荐"）

### 6.1 前端实际渲染（`app.js` 核实）

| 区域 | 数据来源 | 渲染内容 |
|------|---------|---------|
| `STOCKS[]` | `dashboard_data.json.stocks` = `dashboard_export` 由 **pending CSV + trade_history 活跃事件** 构建 | 含 scan 推荐（`status:'pending'` 时**置灰**）、含已跟踪事件 |
| 持仓卡片（`renderPortfolio`） | `portfolio.positions[]`（= `portfolio_50000_positions.csv` 的 OPEN 持仓）join `STOCKS[]` | 只显示**已填成交价的 OPEN 持仓** |
| `recPrice` | `trade_history.Price`（=推荐日真实 Open，盘前为 null） | 正式买入价 |
| 新闻区（`renderNews`） | 持仓 + 推荐联动 | 只渲染持仓/推荐联动标记 |

### 6.2 "看不到"的根因

1. **scan 推荐其实在 `STOCKS[]` 里**（置灰 `pending`），并非完全不可见——但它是"推荐列表"里的灰条，没有专门突出面板。
2. **用户通常看"持仓卡片"区**：该区只渲染 `portfolio_50000_positions.csv` 的 OPEN 持仓，而这些持仓**只在 review 填完成交价后才出现**。盘前 scan 跑完、review 未跑时，持仓区显示 `空仓（等待新的 Core 推荐触发建仓）`（app.js:467）——自然"看不到今日推荐"。
3. **时序**：`dashboard-data.yml` 每 15 分钟刷一次，scan 跑完 15 分钟内前端即更新 `STOCKS[]`；但持仓区要等 review 跑完才有数据。

### 6.3 结论

- scan 的推荐**数据上已存在且已推到前端**（`STOCKS[]` + `pending_price`），只是：
  - 在推荐列表里被置灰，无"今日推荐(盘前锁定)"专用面板；
  - 在持仓区因 review 未跑而空缺。
- 用户"看不到"是**展示组织问题**，不是数据缺失——对应 §4 方案 A 即可解决。

---

## 7. 给用户的下一步建议（只读，待决策）

1. 若只要"盘前看到今日推荐+参考价，盘后看成交价回填" → **方案 A**（前端面板，~100 行，零后端风险）。
2. 若要求"50k 组合盘前即含今日推荐"（语义上预建仓）→ **方案 B**（需动 scan/review/portfolio_50000，专项实施）。
3. 两者都**不破坏现有防前视偏差**（参考价与成交价时点已分离）。
4. 本次只读调查未做任何改动；建议等今晚 21:00 cron-job.org 外部触发验证通过后再启动实施。
