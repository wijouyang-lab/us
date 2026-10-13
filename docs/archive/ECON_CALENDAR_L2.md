# 事件日历 L2 调研（只读 / 不实施）

> 目的：评估"宏观板块"从当前 L1（数值快照）升级到 L2（带"下次公布时间 + 预期值"的事件日历）所需的能力缺口与落地路径。
> 本文档**只做调研与方案**，不含任何代码改动。涉及文件与代码行号均来自当前 `scan.py` / `portfolio_50000.py` 现状。

---

## 1. 现有能力（L1 数值快照）

### 1.1 `economic_structured` 的来源与结构

`scan.py:3890`：

```python
economic_text, economic_structured = get_us_economic_data(preliminary_news)
```

`economic_structured` 就是 `get_us_economic_data()`（`scan.py:1589`）返回的 `data` 字典，**按中文标签做 key**，每个指标是一个条目：

| 标签 | 数据源链路 | 条目字段（实测） |
|---|---|---|
| `10Y国债` / `5Y国债` / `13周国债` | Yahoo Finance（`^TNX`/`^FVX`/`^IRX`） | `value, prev, date, source` |
| `CPI指数` / `核心CPI指数` / `失业率` | FRED → BLS API → BLS 网页 | `value, prev, date, source, yoy?` |
| `核心PCE指数` | FRED → BEA 官网 → 新闻文本 | `value, date, source, yoy?` |

条目字典的实际字段（`scan.py:1611 / 1627 / 1655 / 1704` 等）：

```python
{
  "value": <float>,          # 实际值（利率为 %，CPI/PCE 为指数或 %）
  "prev":  <float|None>,     # 前值（部分来源提供）
  "date":  "<YYYY-MM-DD>",   # 实际数据期（已公布的那个周期）
  "source": "FRED" | "BLS API" | "BEA 官方网页" | "Yahoo Finance" | ...,
  "yoy":   <float|None>,     # 同比（仅 CPI/PCE 在可得时计算）
}
```

### 1.2 已有，但**不**属于"事件日历"的东西

- `date` 字段是**已公布数据的统计期**（例如 2026-09 的 CPI），不是"下次公布日"。
- `value` / `yoy` 是**实际值**，没有"市场预期/一致预期"。
- `key_people_news`（人物讲话）由 Google News 抓取，只有 `MM-DD HH:MM` 级别的时间戳，**没有**"下次讲话日程"。

### 1.3 结论（现有有什么 / 缺什么）

| 能力 | 现状 |
|---|---|
| 指标实际值 + 数据期 | ✅ 有（L1 快照） |
| 同比 / 前值 | ⚠️ 部分有（CPI/PCE 有 yoy；利率有 prev） |
| **下次公布时间（release date）** | ❌ 完全没有 |
| **预期值 / 一致预期（consensus）** | ❌ 完全没有 |
| 讲话日程（未来） | ❌ 只有历史新闻时间戳 |

---

## 2. 缺口分析：要显示"11-14 公布 CPI，预期 3.1%"差什么

目标文案 = **未来日程（11-14）+ 指标名（CPI）+ 预期值（3.1%）**。逐项映射：

| 文案要素 | 现有能否提供 | 缺什么 |
|---|---|---|
| `CPI`（指标名） | ✅ `economic_structured["CPI指数"]` | — |
| `11-14`（下次公布日） | ❌ | 需要 **release calendar** 数据源，目前 `get_us_economic_data` 只取"已公布期" |
| `预期 3.1%`（一致预期） | ❌ | 需要 **consensus/forecast** 数据源（市场一致预期通常不在 FRED/BLS 原始库） |

> 核心矛盾：**FRED / BLS / BEA 提供的是"历史实际值"，不是"未来日程"也不是"市场预期"**。
> L1 的抓取链路（多层备用）天生拿不到 L2 所需的两种新信息。

### 2.1 现有数据源能不能补？

- **FRED**：有 `releases` 与 `release/series` 接口，可查某 series 的**发布日历**（下一次 release 日期）。**免费**，但发布日历的"下一次"往往在数据真正发布后才滚动更新，且**不含市场预期值**。
- **BLS**：有官方"发布日历"页面与 API（按指标系列给未来发布日）。**免费**，同样**不含预期值**。
- **BEA**：提供 PCE 的发布日程页，**免费**，不含预期值。
- 结论：现有免费源**能补"下次公布日"，补不了"预期值"**。预期值必须来自第三方经济日历 / 行情商。

---

## 3. 可行数据源（只列，不实施）

| 数据源 | 提供"公布日" | 提供"预期值" | 成本 | 备注 |
|---|---|---|---|---|
| **FRED Releases API** | ✅（发布日历） | ❌ | 免费（需 API key，已有 FRED 取数基础） | 与现有 FRED 链路同源，集成成本最低；只解决"下次公布日" |
| **BLS Release Calendar** | ✅ | ❌ | 免费 | CPI/失业率/PCE 的官方日程，权威 |
| **TradingEconomics Calendar API** | ✅ | ✅（consensus） | 免费层有限（日调用限额）/ 付费层充裕 | 一站式同时给日程 + 预期值，但需新增 key 与速率控制 |
| **Finnhub Economic Calendar** | ✅ | ✅（consensus 部分） | 免费层有月度额度 | 与现有 `news-fetch` 可能已用 Finnhub，复用成本低 |
| **Yahoo Finance / 行情商** | ⚠️ 间接 | ✅（分析师预期，非官方 consensus） | 免费 | 预期值口径不一致，仅作兜底 |

> 推荐组合（若做 L2）：**FRED/BLS 拿权威"公布日" + Finnhub/TradingEconomics 拿"预期值"**，二者解耦，任一层失败都有降级。

---

## 4. 落地路径（最小实现，待拍板）

### 4.1 需要改的文件（预估）

| 文件 | 改动 |
|---|---|
| `scan.py` | `get_us_economic_data()` 增加 L2 抓取（release date + expected）；`economic_structured` 条目新增 `next_release`、`expected` 字段；`_build_macro_payload()`（:1863）把这两个字段透传进 `macro_data.json` |
| `dashboard_export.py` | `build_macro()`（:2769）原样透传新字段即可，无需大改 |
| `app.js` | `renderMacro()` 经济指标卡片新增"下次公布：MM-DD / 预期 X%"展示位 |
| `index.html` / `app.css` | 卡片布局微调（非必须） |

### 4.2 Token 成本（若引入 AI 判断）

- L2 **不需要**额外的 AI 判断：公布日与预期值都是**结构化 API 直接返回**，不像 L1 的"利好/利空"那样需要语义判断。
- 现有 L1 的 `_macro_ai_judge`（`scan.py:1951`）对每条经济/讲话做 sentiment 判断，token 成本已在 macro 功能内。L2 是**纯数据增强**，不增加 AI 调用，**0 额外 token**。
- 唯一新增成本：抓取 release calendar / consensus 的**网络请求 + 解析**，属运行时开销，非 token。

### 4.3 与现有 L1（数值快照）的关系

- L2 **不替代** L1：`value / yoy / date` 继续由现有 FRED→BLS→BEA 多层链路提供（已验证稳定）。
- L2 是 **L1 条目的字段扩展**：在每条指标上叠加 `next_release`（何时公布下次）与 `expected`（市场预期）。
- 降级原则：L2 抓取失败时，**L1 快照照常落盘**，只是 `next_release` / `expected` 为 `null`，前端显示"暂无日程/暂无预期"——与现有 `error` 兜底思路一致。

### 4.4 风险与注意

- **预期值口径差异**：不同源的 consensus 可能不同，需固定一个主源 + 标注 source。
- **公布日漂移**：官方日历偶尔调整，需标注"截至抓取日"并允许 stale。
- **flag 门控延续**：L2 仍应只在 `ENABLE_MACRO_PANEL=1` 时落盘，默认关闭（与现有 L1 一致），不激活 flag 不影响周一 scan。

---

## 5. 小结（待用户决策）

- L1（数值快照）已具备，缺"下次公布日"与"预期值"两类字段。
- "下次公布日"可由 **FRED/BLS 免费发布日历**补齐；"预期值"需 **Finnhub/TradingEconomics** 等第三方。
- 落地改动集中在 `scan.py`（抓取+透传）、`app.js`（展示），**不增加 AI token**，**不破坏 L1**。
- 本文档未做任何代码改动，等待是否启动 L2 实施的明确指示。
