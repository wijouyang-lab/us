# news_cn 5/42 覆盖缺口根因调查

> 生成时间：2026-10-08 01:11 GMT+8
> 性质：**只读调查，不改代码、不实施修复、不 push**。仅定位 37/42 空白的根因（设计 vs bug），并列出修复方向供判决后规划。
> 数据源：`dashboard/data/dashboard_data.json`（42 只）、`us_stocks_pending_20261007.csv`、`ai_snapshot.csv`（47 条）、`ai_text_cache.csv`（47 条）、`scan.py:3109`、`dashboard_export.py:863/2844`。

---

## 1. 42 只按 Tag 分组统计

> 重要前提：`dashboard_data.json` 里 42 只股票的 `tag` 字段**全部为 `None`**（当前事件视图不携带 Tag）。因此无法从 JSON 直接分 Core/Observation，改用 `ai_snapshot.csv` 按 Ticker 反查 Tag。

| 分组 | 总数 | 有 news_cn | 空白 | 说明 |
|---|---|---|---|---|
| 全部 42 只 | 42 | 5 | 37 | — |
| 有 news_cn 的 5 只 | 5 | 5 | 0 | **全部 Tag=Core_Dragon**（FANG/GEV/HWM/SNPS/WRB，见 `ai_snapshot.csv`） |
| 空白 37 只 — Observation | 26 | 0 | 26 | `ai_snapshot.csv` 中 Tag=Observation |
| 空白 37 只 — 不在 ai_snapshot | 11 | 0 | 11 | 从未进入 AI 管线（未 review） |
| 空白 37 只 — 仅 cache 有（APA） | 1 | 0 | 1 | 缓存有 news_cn 但被反污染规则抑制 |

`ai_snapshot.csv` 全量 Tag 分布：`Observation=32 / Core_Dragon=18 / 空=9`（共 47 条，其中 21 条 AI_news_cn 非空）。

---

## 2. 5 只有 / 37 只无的对照（来源路径）

**有 news_cn 的 5 只来源：**
- `FANG / HWM / WRB`：当日 `pending CSV` 直写 `AI_news_cn`（scan 当天生成并写入）。
- `GEV / SNPS`：`pending` 无，但 `ai_text_cache.csv` 有（Rec_Date 2026-10-02 的 Core_Dragon，经缓存命中回退）。

**空白 37 只来源判定：**
- 36 只：**两处均无 news_cn（从未生成）** —— 26 只 Observation + 11 只从未进 AI 管线。
- 1 只（APA）：`ai_text_cache.csv` 有 `AI_news_cn`（Update_Date 2026-10-02），但 `dashboard_data.json` 显示空。

---

## 3. 根因判定：**以设计为主，无三元组匹配 bug**

你提出的二分假设（设计=Observation 禁止 / bug=三元组匹配失败）结论如下：

- **26/37 = Observation**：`scan.py:3109` 明确**禁止** Observation 输出 `news_cn`（只输出 industry_logic / catalysts / risks 三字段）。空白**正确、符合设计**。
- **11/37 = 从未进入 AI 管线**：这些股票没有 `ai_snapshot.csv` 记录，AI 生成阶段根本没覆盖它们 → 空白是**范围问题（设计）**，不是匹配失败。
- **0/37 在 `ai_snapshot.csv` 有 news_cn 却没匹配上**：即**三元组 `(Ticker, Rec_Date, Tag)` 匹配没有失败案例**。匹配逻辑本身工作正常，只是今天"当前事件"股票的 Tag=None，三元组路径对这些股票本就不触发，news_cn 只来自 pending 直写 + 极少数 cache 命中。
- **1/37（APA）= 反污染规则的边缘抑制**：`ai_text_cache.csv` 有 news_cn，但 `dashboard_export.py:863`（backfill_ai_fields 已停用）+ `:2844-2846`（禁止 Ticker-only 回退）**故意**不让缓存兜底，防止把 A 事件的 AI 错配给 B 事件。APA 的 news_cn 因此"有却显示不出"——这是**有意的安全取舍**，非意外 bug，但属于"过度严格"的可商榷边缘。

**结论：37 空白 ≈ 设计（26 Observation + 11 未覆盖）+ 1 例设计取舍边缘（APA）。不存在"该有却因匹配失败而没有"的 bug。**

---

## 4. 若为 bug 的具体失败点（本调查结论：无此情形）

- 三元组匹配逻辑（`dashboard_export.py` build_current_event_rows）：**无失败案例**，不列失败点。
- 唯一可商榷的"软缺口"：`ai_text_cache.csv` 已持有部分 Ticker 的 news_cn（如 APA），但显示层因反污染规则不消费它。这是**设计权衡**而非代码缺陷，对应下方修复方向 (c)。

---

## 5. 修复方向（只列方向，不实施）

子任务 A 的本质被本次调查**重新定义**：它不是"修匹配 bug"，而是**"扩大 AI 生成覆盖范围"的设计变更**。候选方向：

| # | 方向 | 性质 | 影响范围 | 取舍 |
|---|---|---|---|---|
| a | 放宽 `scan.py:3109`，允许 Observation 也生成 `news_cn` | 设计变更 | 可新增约 26 只覆盖 | 需重跑 AI 生成成本；Observation 当前刻意极简 |
| b | 把 11 只"未进管线"的股票纳入 AI 生成 scope | 设计/scope 变更 | 新增约 11 只覆盖 | 需确认这 11 只是否应被 AI 处理 |
| c | 放宽反污染规则，允许 cache 在"无同事件文本时"兜底 | 设计权衡 | 救回 APA 类边缘 | 有跨事件错配风险，需加 Tag/日期校验 |
| d | 让 news_cn 在 Dashboard 更显眼 + 加"相关 ticker"标签 | UI 增强 | 不改覆盖率 | 低成本，独立于 a/b/c |

> 方向 a/b 是"覆盖率"的真正杠杆；d 是纯展示增强；c 是安全取舍。三者优先级与取舍需在判决后、且你拍板子任务 A 范围时定。

---

## 6. ai_text_cache.csv 作用（回应问题三）

- **设计意图**：scan 每跑一次，把已生成的 AI 六段按 **Ticker Upsert** 进持久化缓存（`scan.py:3417-3422`），供云端回填。
- **是否跨日复用**：**当前显示层刻意不跨日复用**——`dashboard_export.py:863` 标记 `backfill_ai_fields` 为"已停用"，`:2844-2846` 明确"禁止 Ticker-only 回退到 ai_text_cache.csv"。原因：防止把昨天 A 事件的 AI 错配给今天 B 事件。
- **"昨天有今天空"是否存在**：**存在，即 APA**（cache Update_Date 2026-10-02 有 news_cn，今天显示空）。这是反污染规则的必然结果，不是 bug，但是否"过度严格"待子任务 A 评估。

---

## 7. 本调查未做的事

- 未改 `scan.py` / `dashboard_export.py` / 任何 CSV / 任何 workflow。
- 未 push / rebase / 碰监控 PID 536931 / 未启动子任务 A 或 B 的实际开发。
- 仅做只读数据交叉核对与根因判定。

---

## 8. 对"子任务 A 优先级提升"的修正提醒

你的指令把子任务 A 定为"判决后第一优先"。本次调查发现它**不是修 bug，而是扩大 AI 生成覆盖范围的设计变更**（主要杠杆 = 方向 a/b）。因此：
- 子任务 A 的工作量/风险比原先"修匹配"的设想**更大**（涉及 scan.py AI 契约 + 重跑生成成本），不是一行匹配修复。
- 真正的"零改动、纯展示增强"只有方向 d（更显眼 + 相关 ticker 标签），可独立快做。
- 建议判决后先确认：要的是"覆盖率"（a/b，设计变更）还是"展示增强"（d，低风险）还是"救边缘"（c，安全权衡）。
