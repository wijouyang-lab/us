# 系统每日 AI Token 消耗估算（静态分析）

> **方法**：纯静态分析——只读源文件/数据文件、数字符、统计数据行数。
> **未运行任何项目 .py 脚本**（scan/review/fetch_news/evolve 一律未执行）；
> **未调用任何 API**（无 ClawSocket / OpenAI / Anthropic / Finnhub 请求）；
> 对数据文件仅用 Python 标准库 `csv`/`json` 做本地解析（等价 grep/计数，不消耗 AI token）。
> 调查时间：2026-10-09（仓库 HEAD `9d3a369`）

## 结论速览

| 项 | 数值 | 性质 |
|---|---|---|
| **输入 token / 工作日** | **≈ 34,000 – 36,000** | 估算（±50%） |
| **输出 token 上限 / 工作日** | **≤ 79,000** | **静态实测**（max_tokens 累加，非实际用量） |
| **理论上限（输出跑满）** | ≈ 113,000 / 工作日 | 上限值 |
| **实际输出 token** | **无法静态估算** | 需 ClawSocket 日志/账单 |
| **占比最大** | **scan ≈ 72–78%** | 估算 |

> ⚠️ **最重要的诚实声明**：`max_tokens` 是**上限**，不是实际用量。实际输出 token 只能从账单/日志得到，**本文无法静态估算**。输入部分可较好估算（输入由代码拼装，规模可数）。

---

## 1. 每个 workflow 的消耗明细

### 触发频率（静态实测，读 workflow 文件）

| Workflow | 触发方式 | cron | 频率 |
|---|---|---|---|
| scan.yml | 仅 `workflow_dispatch` | **无**（已删 schedule） | 由 cron-job.org 外部触发 → **~1×/工作日**（取决于你的外部配置，静态不可见） |
| news-fetch.yml | `workflow_call` + `workflow_dispatch` | 无 | **1×/工作日**（挂在 scan 成功后，`needs: scan`） |
| review.yml | `workflow_dispatch` + `schedule` | `23 22 * * 1-5` | **1×/工作日**（22:23 UTC） |
| evolve.yml | `workflow_dispatch` + `schedule` | `0 2 1 * *` | **1×/月**（每月 1 日 02:00 UTC） |
| quant-research.yml | `workflow_dispatch` | cron 被注释 `# - cron: 'TBD'` | **0×/天**（纯手工） |
| dashboard-data.yml | `*/15 * * * 1-5` | — | — **不调用任何 AI**（见下方说明） |

**模型**：scan / review / evolve / news-fetch 的 workflow 均 `CLAWSOCKET_LIVE_MODEL: claude-opus-5-5`。

---

### AI 调用点清单（静态实测）

| # | 文件:行 | 调用点 | 模型 | max_tokens（静态值） |
|---|---|---|---|---|
| S1 | `scan.py:2255` | `analyze_market_signals()` | claude-opus-5-5 | **12,000** |
| S2 | `scan.py:2518` | `pre_scan_portfolio_review()` | claude-opus-5-5 | **3,000** |
| S3 | `scan.py:2756` | `generate_ai_report()` | claude-opus-5-5 | **8,000**（`2755`：`claude-` 前缀走 8000，否则 30000）|
| S4 | `scan.py:3137` | `enrich_verified_items_with_ai_details()` | claude-opus-5-5 | **10,000** |
| R1 | `review.py:3600` | `client.messages.stream()` | claude-opus-5-5 | **30,000** ← 全系统最大单个上限 |
| E1 | `evolve.py:416` | `evolve_strategy()` 主调用 | EVOLVE_MODEL=claude-opus-5-5 | **2,000** |
| E2 | `evolve.py:318` | `claude_red_team_audit()` | CLAUDE_AUDIT_MODEL=claude-opus-5 | **1,800** |
| N1 | `fetch_news.py:327` | `translate_headlines()` + **1 次 gap-retry** | claude-opus-5-5 | **8,000**（每次）|

每次调用的**主流程调用次数均为 1**（单一调用点：`scan.py:3722/3726/3816/3844`，`review.py:3600`，`evolve.py:554→evolve_strategy→433 审计`，`fetch_news.py:427`），无逐标的循环。
→ **scan 每跑一次 = 4 次 AI 调用；review = 1 次；evolve = 2 次；news-fetch = 1–2 次。**

**quant-research.yml = 0 token**（`quant_research_runner.py` 全文件无 clawsocket 导入，纯 pandas/numpy 计算）。
**dashboard-data.yml = 0 token**（AI 六段由 scan 离线产出，导出层只透传；且 `DASHBOARD_AI_ENABLED: "false"`）。

---

### 明细表

> token 换算采用给定口径：中文 1.5 字符/token、英文 4 字符/token、混合 3 字符/token。
> **模板字符数 = 静态实测**（`sed` 取行区间 + `wc -m`）；**动态部分 = 估算**。

| Workflow | 触发频率 | 单次调用数 | 单次输入 token（估算） | 单次输出上限 | **每天输入 token（估算）** |
|---|---|---|---|---|---|
| **scan** | 1×/工作日 | 4 | S1≈2,900 / S2≈8,900 / S3≈10,000 / S4≈6,500 | 12k+3k+8k+10k = **33,000** | **≈ 28,000** |
| **review** | 1×/工作日 | 1 | ≈ 4,000 – 5,000 | **30,000** | **≈ 4,500** |
| **news-fetch** | 1×/工作日 | 1–2 | ≈ 1,200 / 次 | 8,000（×1–2） | **≈ 1,800** |
| **evolve** | 1×/月 | 2 | ≈ 2,000 – 6,000 | 2,000+1,800 | **≈ 250**（摊到每天）|
| **quant-research** | 0 | 0 | 0 | 0 | **0** |
| **总计** | — | — | — | 输出 caps 合计 **≤79,000/工作日** | **≈ 34,500 / 工作日** |

### 各调用点的输入构成（静态实测部分）

**S1 `analyze_market_signals`**（`scan.py:2227-2253`）
- 模板 **612 字符**（中英混排）→ ≈408 token
- `{combined_news_text[:10000]}` → 上限 **10,000 字符英文** → ≈2,500 token
- **输入估算 ≈ 2,900 token**

**S2 `pre_scan_portfolio_review`**（`scan.py:2508-2514`）
- 模板 **260 字符** → ≈173 token
- `{macro_news_text[:6000]}` → ≈1,500 token
- **position_lines**：`active = Status=="Active"`（**无行数上限**）→ 当前 **54 条**（静态实测：trade_history.csv 共 393 行、Active 54 行）；每条含 4 条新闻 → 54×~400 字符 ≈21,600 字符混合 → ≈7,200 token
- **输入估算 ≈ 8,900 token**

**S3 `generate_ai_report`**（`scan.py:2604-2751`）
- 模板 **5,326 字符**（含大段中文纪律 + HTML 规格）→ ≈2,100 token
- `{combined_news[:12000]}` → ≈3,000 token
- `pool_lines`：每只 **838 字符模板** × **≤7 只**（见第 5 步验证）→ ≈2,300–3,000 token
- event_regime / macro_market / key_people / economic 合计 → ≈2,000 token
- **输入估算 ≈ 10,000 token**

**S4 `enrich_verified_items_with_ai_details`**（`scan.py:3105-3134`）
- 模板 **1,224 字符** → ≈816 token
- `event_regime[:5000]` ≈1,667 + `macro_market[:5000]` ≈1,250
- `payload`：入账 Core≤5 + Observation≤3 ≈7–8 只，每只含 news[:3] + `initial_ai`(limit 800) → ≈2,800 token
- **输入估算 ≈ 6,500 token**

**R1 review**（`review.py:3570-3601`）
- 模板 **仅 313 字符** → ≈209 token（**模板很小，量全在动态块**）
- `active_list` ≈54 条 + `observation_list` + `stopped_list` + 期权四块
- **输入估算 ≈ 4,000–5,000 token**；**输出上限 30,000（全系统最高）**

**N1 fetch_news**（`_build_translation_prompt`）
- 翻译范围：市场 top 10 + **每只持仓 top 5**（`position_tickers` ← `portfolio_50000_positions.csv`，当前 **4 只 OPEN**）→ ≤30 条
- ≤30 条 × ~120 字符英文 ≈3,600 字符 → ≈900 token + 模板 ≈270
- **输入估算 ≈ 1,200 token / 次**

---

## 2. 最大消耗点

### 输入侧：**scan 占 ≈ 72–78%**（约 28,000 / 34,500 token 每天）

scan 内部三巨头（单次）：

| 排名 | 调用 | 输入估算 | 主要成因 |
|---|---|---|---|
| 1 | S3 report | ~10,000 | 5,326 字符超长模板 + `combined_news[:12000]` |
| 2 | **S2 pre-scan** | ~8,900 | **54 条 Active 流水全量入 prompt（未收窄）** |
| 3 | S4 enrich | ~6,500 | 同一份 macro_market 第三次重复发送 |

### 输出侧：**review 的 30,000 上限是全系统最大单点风险**

若 review 的实际输出接近 30,000 token，单这一项就可能超过 scan 全部。这正是最需要实测确认、且我**无法静态估算**的部分。

### 一个值得注意的重复传输

`macro_market` / `combined_news` 这类大块在 scan 内被**重复发送 3 次**（S1、S3、S4），`combined_news` 更是以 10,000 + 12,000 字符两次入参。这是纯浪费，也是最直接的优化点。

---

## 3. 不确定点（务必注意）

| 项 | 性质 | 说明 |
|---|---|---|
| **实际输出 token** | **无法静态估算** | `max_tokens` 只是上限。**必须查 ClawSocket 账单/日志**。本报告所有"每天 token"若含输出，只能用 caps 给下限/上限 |
| scan 触发频率 | 静态不可见 | scan.yml 已删 schedule → 频率由 cron-job.org 配置决定。若配置了周末也跑，上表需相应放大 |
| S2/S3/S4 的动态块体积 | ±50% | 新闻/行情/regime 文本实际长度取决于当日数据量；我按上限/典型值估算 |
| `combined_news` 实际长度 | ±100% | 代码只是 `[:12000]` 截断，真实可能是 0–12,000 任意值 |
| review `active_list` 条目序列化宽度 | ±50% | 未逐一读每行序列化代码；按 ~150 字符/条估算 |
| 模型单价 | 未知 | claude-opus-5-5 的 input/output 单价不在代码里 → **无法静态估算成本金额** |
| 运行时 fallback | 未知 | `clawsocket_compat` 有 `claude-fable-5-1` / `gpt-6-astra` 自动降级链（`:118, :378`）。若发生降级，实际调用数会增加（重试/备用），消耗上浮 |

**误差范围总结**：输入侧的每日 34,500 token，合理区间约 **±50%（17,000 – 52,000）**；若叠加输出且输出接近 caps，则每日总量区间约 **40,000 – 113,000 token**。

---

## 4. 第 5 步：scan 重定义后 AI 输入是否真收缩？

### ✅ 已生效（给 `generate_ai_report` 的输入确实是 ≤7，不是 262）

三条硬证据：

1. `quant_filter.py:28` —— `AI_INPUT_MAX = 7   # AI 输入硬顶（持仓 + 候选 ≤7 只）`
2. `quant_filter.py:237` —— `return out[:AI_INPUT_MAX]`（`build_ai_input` 结尾硬截断）
3. `scan.py:3770` 构建 `ai_input`，**`scan.py:3816-3817` 传入的第一个实参就是 `ai_input`**：
   ```python
   ai_html = generate_ai_report(
       ai_input,          # ← 窄版 ≤7，而非 pool_data
       combined_news,
       ...
   )
   ```
   且 `scan.py:3772` 有对照日志：`/ AI输入={len(ai_input)}（旧：全闸口池 {len(pool_data or [])} 只）`

→ **S3 报告的 stock 行 ≤7 只 × 838 字符 ≈ 5,900 字符**。若仍是 262 只，仅此一项就是 ~220,000 字符，会比现在大 **≈37 倍**。第 5 步结论：**改动真生效，S3 没有失控。**

### ⚠️ 但有一个漏网的：S2 没有跟着收窄

`pre_scan_portfolio_review`（`scan.py:2468`）：
```python
active = df[df["Status"].astype(str).str.strip() == "Active"].copy()   # 无行数上限
```
它遍历**全部 54 条 Active 流水**（每条还现抓 4 条新闻），这是当前 S2 ≈8,900 token 的来源，且**随 trade_history 累积线性增长**。

→ 严格说：**"AI 输入收缩"只对 S3 成立；S2 仍是全量。** 若你以为整体已收缩，这里可能低估。

### 第 6 步：review 是否调 AI？

**是，且只有 1 次。** `review.py:3566-3600` 构造 `anthropic.Anthropic`（base_url = CLAWSOCKET_BASE_URL）→ `client.messages.stream(model=TARGET_MODEL, max_tokens=30000)`。`review.py` 全文再无第二个 ClawSocket 调用点。

---

## 5. 优化建议（按性价比排序，只列不实施）

### ① 消重：把重复发送的大块合并（预计降 25–35% 输入）

`combined_news` 以 10,000（S1）+ 12,000（S3）字符各发一次，`macro_market` 在 S2/S3/S4 发三次。最有效的三种做法：
- S1 与 S3 合并为一次调用（市场信号本来就是报告的输入）；
- 或把 `combined_news` 先做去重/压缩（例如只留前 4,000 字符）再分给各调用；
- S2 与 S4 复用同一份缓存的 macro/regime 文本。

### ② 给 S2 加上限（预计降 8,900 → ~2,000，即降约 20% 总输入）

`pre_scan_portfolio_review` 的 `active` 加 `head(N)`（如只保留最近 20 条或仅今日新增），或按 Ticker 去重后再入 prompt。这是当前唯一还在全量遍历流水、且会**随时间线性变贵**的调用。

### ③ 压 output 上限 + 引入结果缓存（直接砍不确定部分）

- review 的 `max_tokens=30000` 是全系统最高单点；若实测输出远低于此，改 prompt 要求更短 HTML（如 ≤6,000）可立竿见影。
- S4 的 `initial_ai(limit=800)` 已有缓存痕迹；可把 S4 的六段解释**按 ticker 缓存**（隔日不变就不重算）。

> 另注：evolve 每月才跑，news-fetch 已有多层缓存，**动它们收益最小**，建议先动 scan。

---

## 附：如何把"无法静态估算"变成实测（不消耗额外 AI token 的做法）

由于实际输出 token 无法从代码推断，想拿到真实数字建议（均非 AI 调用）：
1. 在 ClawSocket 中转站后台看按模型/日期的 usage 报表；
2. 或让 `clawsocket_compat._request_one()` 打印返回的 `usage.total_tokens`（多数网关响应体自带），跑一天看 GH Actions 日志即可 —— 这不产生额外 token；
3. 关注 `claude-opus-5-5` 之外的调用：若日志出现 `claude-fable-5-1` / `gpt-6-astra`，说明发生了降级重试，实际消耗高于本报告估算。
