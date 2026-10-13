# Market Indicators 面板设计（F&G + FedWatch）

> 设计阶段文档，未实施、未改代码、未提交。
> 性质：**纯设计 + 可落地接口草稿**，落地时间 12-06 后（与 23h 改造同批）。
> 铁律：本文件不碰 `/tmp/us` 任何代码；激活前 flag 默认关闭。

---

## 0. 一句话目标

在 Dashboard 的 **Global Market 板块下方**新增一个"市场情绪 / 利率预期"子面板：
左侧 CNN 恐惧贪婪指数（环形图 + 文字标签），右侧 CME FedWatch（下次 FOMC + 加减息概率条形图）。
**全程零 AI token**——纯数据透传，成本为零。

---

## 1. 数据源

| 指标 | 源 | 是否免费 | 更新频率 | 备注 |
|---|---|---|---|---|
| **CNN Fear & Greed** | `fear-greed`（PyPI 包 v0.1.1，`pip install fear-greed`） | ✅ 免费 | 实时（约每几分钟） | 封装 CNN F&G，一次调用拿总分 + 7 个子指标 + ~251 交易日历史，绕过 Cloudflare 反爬 |
| **CME FedWatch** | `cme-fedwatch`（开源 PyPI 包） | ✅ 免费 | 实时 | 解析 CME FedWatch Tool 的概率表 |

### 1.1 CNN F&G（改用 `fear-greed` 包）
> 原方案直接用 `curl` 拉 `production.dataviz.cnn.com/.../graphdata`，实测返回 **HTTP 418**（Cloudflare 反爬拦截脚本访问，带浏览器 UA 也被挡）。
> 改用社区包 [`fear-greed`](https://pypi.org/project/fear-greed/)（v0.1.1），它封装了 CNN F&G 的抓取与解析，绕开反爬。

```python
# pip install fear-greed
from fear_greed import fear_greed
data = fear_greed.get()
# data 结构（简化）：
# {
#   "score": 72,                       # 总分 0-100
#   "rating": "Greed",                 # Extreme Fear / Fear / Neutral / Greed / Extreme Greed
#   "previous_close": 68,              # 上一交易日总分
#   "previous_timestamp": "...",
#   "updated": "...",
#   "one_week_ago": 65,                # 子指标（各周期）
#   "one_month_ago": 60,
#   "one_year_ago": 45,
#   "seven_day_ma": 70,
#   "history": [ { "score":..., "rating":..., "timestamp":... }, ... ]  # 过去约 251 个交易日
# }
```
- 无需 API Key，一次调用拿**总分 + 7 个子指标 + 历史**，比原 curl 端点信息量更大。
- 仍属 CNN 口径，前端 5 档中/英标签映射不变（见 §2.1）。

### 1.2 FedWatch（`cme-fedwatch` 包）
```python
from fedwatch import FedWatch, CMEClient
# FedWatch 返回下一次（及后续）FOMC 会议的利率概率分布
fw = FedWatch(CMEClient())
meetings = fw.get_meetings()   # 每个 meeting 含各档 change(bps) 的概率
```
> 若该包在目标环境不可用（网络/依赖），降级方案：直接抓取 CME FedWatch 页面 HTML 并解析概率表（实现细节在实现期确认，不影响本设计）。

### 1.3 环境限制说明（cme-fedwatch）
`cme-fedwatch` 抓取 `cmegroup.com` 的公开 FedWatch 页面，**无需 API Key**。
- **GitHub Actions 出口**：正常可达 ✅（CI 环境实测应能成功）。
- **沙箱 / 受限网络**：可能被阻断（`curl error 7` —— `Failed to connect to www.cmegroup.com`）——这是**环境问题，非代码问题**，不要据此判定该包不可用。
- **失败处理**：超时 → 不写文件 → 前端不显示 → **不阻断主流程**（详见 §8 失败兜底）。

---

## 2. 前端展示

**位置**：并入现有 **Global Market** 板块下方，**不新建顶级 section**（与宏观面板 `renderMacro` 的并入策略一致）。

### 2.1 F&G 环形图
- 一个 **0–100 环形进度图**（SVG `circle` + `stroke-dasharray`，或 CSS `conic-gradient`）。
- 中心显示分数（大号），下方文字标签：
  | score | 标签（EN） | 标签（ZH） | 颜色 |
  |---|---|---|---|
  | 0–24 | Extreme Fear | 极度恐惧 | 红 |
  | 25–44 | Fear | 恐惧 | 橙 |
  | 45–55 | Neutral | 中性 | 黄 |
  | 56–74 | Greed | 贪婪 | 浅绿 |
  | 75–100 | Extreme Greed | 极度贪婪 | 绿 |
- 可附"昨日收盘"对比（从 `fear_and_greed_historical` 取上一根）。

### 2.2 FedWatch 条形图
- 标题：**下次 FOMC：`YYYY-MM-DD`**
- 主体：各档概率横向条形（`-25bp / 0bp / +25bp ...`），条宽 ∝ 概率，右侧标注百分比。
- 高亮概率最大的那一档（市场共识）。

---

## 3. 数据流

```
新脚本 dashboard/fetch_market_indicators.py
   （或由 dashboard-data.yml 每 15 分钟调用）
        ↓ 拉 CNN F&G + FedWatch
        ↓ 规整为 dashboard/data/market_indicators.json
        ↓
dashboard_export.py：读取 market_indicators.json，注入 payload.market_indicators
        ↓
前端 app.js renderMarketIndicators(payload.market_indicators)
        ↓
index.html 的 Global Market 板块内新增子容器渲染
```

`market_indicators.json` 规整 schema：
```json
{
  "updated_at": "2026-12-07T14:30:00-05:00",
  "source_ok": { "fear_greed": true, "fedwatch": true },
  "fear_greed": {
    "score": 72,
    "rating": "Greed",
    "label_zh": "贪婪",
    "prev_score": 68
  },
  "fedwatch": {
    "next_meeting": "2026-12-16",
    "probabilities": [
      { "change_bps": -25, "probability": 64.5 },
      { "change_bps": 0,   "probability": 30.1 },
      { "change_bps": 25,  "probability": 5.4 }
    ]
  }
}
```

---

## 4. flag 门控

| 项 | 值 |
|---|---|
| **flag 名** | `ENABLE_MARKET_INDICATORS` |
| **默认** | **不设**（关闭） |
| **关闭时行为** | ① 抓取脚本跳过（或 workflow 条件步骤不执行）；② 不写 `market_indicators.json`；③ `dashboard_export` 不注入；④ 前端 `renderMarketIndicators` 命中空/隐藏标记 → 板块不渲染 |
| **激活（12-06）** | 加 repo variable `ENABLE_MARKET_INDICATORS=1` |

```python
# fetch_market_indicators.py 头部
if os.environ.get("ENABLE_MARKET_INDICATORS") != "1":
    print("[market-indicators] flag 关闭，跳过")
    sys.exit(0)
```

```python
# dashboard_export.py（注入处，flag 包裹）
if os.environ.get("ENABLE_MARKET_INDICATORS") == "1":
    payload["market_indicators"] = _load_json_safe("dashboard/data/market_indicators.json")
```

---

## 5. 成本

- **零 AI token**：两个指标都是公开 API 数据的透传与格式化，不经过任何 LLM 调用。
- 网络成本可忽略（两个轻量请求，每 15 分钟一次）。
- 与现有 dashboard-data（每 15 分钟刷新）同节奏，**边际算力几乎为零**。

---

## 6. 改动半径

| 类型 | 文件 | 改动 |
|---|---|---|
| **新增** | `dashboard/fetch_market_indicators.py` | 拉取 + 规整 + 写 `market_indicators.json`（flag 门控） |
| **新增** | `tests/test_market_indicators.py` | ① 离线 fixture 测试 JSON 规整；② flag 关=不写文件；③ 渲染函数单测 |
| **修改** | `dashboard_export.py` | 新增 `build_market_indicators()` 读取并注入 `payload.market_indicators` |
| **修改** | `app.js` | 新增 `renderMarketIndicators(data)`，挂到 Global Market 板块 |
| **修改** | `app.css` | 环形图 / 条形图样式 |
| **修改** | `index.html` | Global Market 板块内新增子容器 `#marketIndicators` |
| **修改** | `dashboard-data.yml` | 新增条件步骤调用 `fetch_market_indicators.py`；`env` 注入 `ENABLE_MARKET_INDICATORS` |

> 不涉及 `scan.py` / `review.py` / `portfolio_50000.py`，与主 AI 决策链路零耦合。

---

## 7. 实施时机

- **12-06 后** 与 23h 改造一起落地（同批 flag 激活）。
- 前置：实现期确认 `cme-fedwatch` 包在 CI 环境可用（否则走 CME 页面抓取降级）。
- 灰度：先开 `ENABLE_MARKET_INDICATORS=1` 观察 1 周，确认面板渲染与数据新鲜度，再长期保留。

---

## 8. 失败兜底

两个数据源都可能失败（网络 / 反爬 / 限流）。处理规则：

| 场景 | 行为 |
|---|---|
| F&G 拉取失败 | `market_indicators.json` 的 `fear_greed` 字段为 `null` |
| FedWatch 拉取失败 | `market_indicators.json` 的 `fedwatch` 字段为 `null` |
| 两个都失败 | 不写文件（或写空结构 `{"updated_at":..., "source_ok":{"fear_greed":false,"fedwatch":false}, "fear_greed":null, "fedwatch":null}`） |
| 前端拿到 `null` | 隐藏对应子板块，不崩 |

**绝不**：
- 用旧数据冒充（避免误导）
- 让数据源失败阻断 `dashboard-data` workflow
- 用 `alternative.me` 的加密 F&G 冒充美股 F&G

> `alternative.me/fng` 是**加密货币** F&G 指数（实测返回 `value` / `value_classification`），语义与美股 CNN F&G 不同，**不作为主源或替代源**。仅可作为"F&G 与 FedWatch 全部失败"时的**最后兜底展示**，且必须明确标注 **"加密市场情绪，仅供参考"**，不得与美股口径混用。

---

## 9. 回滚

| 情形 | 操作 | 代价 |
|---|---|---|
| 面板异常 | 删 repo variable `ENABLE_MARKET_INDICATORS` | 即时：前端隐藏、抓取停止 |
| 彻底移除 | 删 variable + 删 `fetch_market_indicators.py` + 删前端 3 处渲染代码 | 低（独立新增文件，主流程无依赖） |

---

## 10. 铁律确认

- 本文为**设计文档**，未修改 `/tmp/us` 任何文件；未 `push` / `rebase` / `commit`。
- 今日 21:00 scan 与周二 06:23 review 链路未被触及。
- `ENABLE_MARKET_INDICATORS` 默认关闭，激活前对现有运行零影响。
