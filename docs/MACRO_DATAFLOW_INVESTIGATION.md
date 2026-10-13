# 宏观数据在 scan 链条里的完整流向 — 只读调查

> 只读调查，未改任何代码、未 push/rebase/fetch、未碰监控 PID 536931、未跑真实 scan、未碰 us-market-terminal/。
> 行号以当前 `/tmp/us/scan.py` 为准（**注意**：角色重定义删除了 207 行内联函数，故你背景里引用的 `:3681-3690` / `:2497-2503` 等行号已前移，本报告用真实行号并附旧行号对照）。

---

## 1. 宏观数据抓取源头（类别 + 数据源 + 变量名）

抓取集中在主程序 `__main__`（:3693-3707），共 6 个函数：

| 函数（行号） | 类别 | 数据源 | 产出变量 |
|---|---|---|---|
| `get_latest_macro_news()` (:310) | 宏观新闻 | RSS：CNBC search XML + MarketWatch RSS + Google News RSS（`Federal Reserve inflation tariff economy markets`） | `macro_news` |
| `get_megacap_breaking_news()` (:353) | Mega-Cap 新闻（META/NVDA/MSFT/GOOGL/AMZN/AAPL/TSLA/AMD/INTC/MU） | Yahoo Finance RSS headline feed（失败降级 yfinance `.news`） | `megacap_news` |
| `get_key_people_policy_news(macro_news)` (:1386) | 重要人物讲话（Warsh/Powell/Waller/Bowman/Trump/Fed 政策） | Google News RSS 搜索（失败从 `macro_news` 过滤兜底） | `key_people_news` |
| `get_us_economic_data(preliminary_news)` (:1589) | **结构化经济数据**（利率/CPI/核心CPI/失业率/核心PCE） | Yahoo Finance（^TNX/^FVX/^IRX）→ FRED API（CPIAUCSL/CPILFESL/UNRATE/PCEPILFE）→ BLS API → BEA 网页 → Google News | `economic_text` + `economic_structured` |
| `get_macro_market_data()` (:416) | 全球宏观市场（10Y/5Y/Vix/金/银/铜/WTI/布油/标普/纳指/美元指数） | yfinance（^TNX/^FVX/^VIX/GC=F/SI=F/HG=F/CL=F/BZ=F/^GSPC/^IXIC/DX-Y.NYB） | `macro_market` |
| `get_us_sector_performance()` (:2159) | 板块 ETF 表现（半导体/科技/金融/能源/医疗/消费/工业/材料） | yfinance（SOXX/SMH/XLK/ARKK/XLF/XLE/XLV/XLY/XLI/XLB） | `sector_text` |

拼接（:3696-3704）：
```
preliminary_news = macro_news + 【Mega-Cap】megacap_news + 【重要人物】key_people_news
combined_news = preliminary_news + 【结构化美国经济数据】economic_text
```

---

## 2. 消费点清单（每个变量被谁读、影响什么）

| 变量 | 消费点（行号） | 影响 |
|---|---|---|
| `combined_news` | ① `build_event_regime_gate` (:3710) | **程序硬门控**（见 §3） |
| | ② `analyze_market_signals` (:3718) | AI 生成跨市场信号（AVOID/BUY_DIP/…）→ `market_signal_text` 进主 prompt |
| | ③ `pre_scan_portfolio_review` (:3722) | AI 持仓风控 → `restricted_tickers`（从扫描池剔除） |
| | ④ `generate_ai_report` (:3814) | 主 AI 报告 prompt 的【宏观新闻】段 |
| `macro_market` | ① `build_event_regime_gate` (:3711) | 程序硬门控（VIX/10Y 正则提取） |
| | ② `pre_scan_portfolio_review` (:3722) | 持仓风控 prompt 的【市场】段 |
| | ③ `generate_ai_report` (:3815) | 主 prompt 的【宏观市场数据】段 |
| | ④ `enrich_verified_items_with_ai_details` (:3843) | 最终解释层【宏观市场】段 |
| `event_regime`（由宏观生成） | ① `apply_entry_quality_gate` (:3745) | **硬门控**：`EVENT_HARD_AVOID` / `EVENT_WATCH_TECH_FAIL` |
| | ② `match_pool_to_report` (:3843 附近) | **Core 门槛**：hawkish_watch 提高技术/量化门槛 |
| `economic_text` | 进入 `combined_news` + 主 prompt【结构化美国经济数据】段 | AI 可见 |
| `economic_structured` | **无任何消费点（死变量）** | 结构化 dict 被丢弃，仅 :3701 定义 |
| `key_people_news` | 进入 `combined_news` + 主 prompt【重要人物讲话】段 | AI 可见 |
| `sector_text` | `build_event_regime_gate` (:3711) | 板块涨跌 → hard_avoid/buy_dip 判定 |

**持仓风控 prompt（:2508-2514，旧 :2497-2503）**：输入 `macro_news_text[:6000]` + `macro_market_text` + 持仓行；输出 `{"decision":{"TICKER":"Dropped|Active"}}` → 只影响"哪些股票被剔除扫描池"，**不参与 Core 判定**。

---

## 3. 是否影响 Core 选股 —— 明确结论：**影响，且走程序硬门控（零 token，在 AI 之前）**

宏观 → Core 的真实影响路径有两条：

**路径 A（程序硬门控，决定性）**：
1. `build_event_regime_gate`（:2049）把 `combined_news`+`macro_market`+`sector_text` 转成 `event_regime`：
   - 关键词匹配 hawkish/dovish 术语（:2062-2072）
   - 正则提取 CPI/PCE/10Y/VIX 数值（:2083-2086）
   - 输出 `market_regime`（HAWKISH_REPRICING / HAWKISH_WATCH / DOVISH_WATCH / NEUTRAL）、`hard_avoid_sectors`、`watch_sectors`（:2088-2141）
2. `apply_entry_quality_gate`（:1223）消费 `event_regime`：
   - `EVENT_HARD_AVOID`（:1246-1248）：`hard_avoid_sectors` 板块的股票**直接剔出候选池** → 无法进 Core
   - `EVENT_WATCH_TECH_FAIL`（:1252-1257）：高置信度鹰派重定价下，watch 板块技术确认门槛提到 3
3. `match_pool_to_report`（:2767）消费 `event_regime`：
   - `hawkish_watch`（:2770-2773）+ `watch_sectors` → Core 的技术确认提到 3、量化分提到 68（:2948-2950）

**路径 B（AI 文本判断，辅助性）**：
- `generate_ai_report` 的 prompt（:2604-2641）**有完整宏观段**：【事件驱动 Regime Gate】+【跨市场信号】+【宏观新闻】`combined_news[:12000]`+【宏观市场数据】`macro_market`+【重要人物讲话】+【结构化美国经济数据】。
- 但 prompt 首句即约束："只从通过程序硬门槛的候选中选择"（:2605）；`match_pool_to_report` 注释明确"候选集合、Core/Observation 标签和最终入账由程序决定"（:2775-2776）。AI 的宏观判断只影响 **AI_Score（最终分 30% 权重）** 与文本解释，不决定 Core 集合。

> 结论：**宏观确实硬性影响 Core 选股**，但主杠杆是 `build_event_regime_gate → apply_entry_quality_gate / match_pool_to_report` 这条**程序化零 token 门控**，而非 AI 读新闻选股。

---

## 4. 市场 regime 的输入/输出（与事件 regime 是两套独立体系）

`get_market_regime_context()`（:1078）：

- **输入**：SPY 60d 收盘、^VIX 15d、11 只行业 ETF（XLK/XLC/XLY/XLP/XLF/XLV/XLI/XLE/XLB/XLU/XLRE）30d 相对 SPY 强弱。**纯价格/波动率，不含宏观新闻**。
- **输出**：`market_ctx = {spy, spy_ma20, spy_above_ma20, spy_5d_return, vix, regime(PANIC/STRESSED/NORMAL/UNKNOWN), sector_rs, reason}`。
- **影响 Core**：`apply_market_context_to_pool`（:1125）把 `Market_Regime/VIX/Sector_RS` 写进每只股票；`apply_entry_quality_gate` 用 regime 硬门控——STRESSED/PANIC 技术确认提 3（:1234-1235）、`SECTOR_RS_FAIL`（:1263-1265）、`SPY_TREND_FAIL`（:1268-1278）、`PANIC_FAIL`（:1279-1281）。

**两套 regime 对比**：

| 体系 | 驱动源 | 输出 | 消费点 |
|---|---|---|---|
| 市场 regime `market_ctx` | SPY/VIX/行业 ETF 价格 | regime=PANIC/STRESSED/NORMAL | `apply_entry_quality_gate` 硬门控 |
| 事件 regime `event_regime` | 宏观新闻/经济数据/板块 | hard_avoid/watch_sectors | `apply_entry_quality_gate` + `match_pool_to_report` |

两者在 `apply_entry_quality_gate` 中**同时作用**，都硬性影响 Core。

---

## 5. 有无独立宏观数据源 —— **有结构化源，但被丢弃**

- `get_us_economic_data`（:1589）**是独立结构化宏观数据**：FRED API（CPI/核心CPI/失业率/核心PCE）+ BLS API + BEA 网页 + Yahoo 利率，非新闻文本。
- **关键发现**：`economic_structured`（dict）在 :3701 解包后**再无任何消费点**——结构化数值被丢弃，只有 `economic_text`（文本化）进入 `combined_news` 和 prompt。
- **无独立宏观产物文件**：全仓 grep 无 `macro_data.json` / `economic_data.json` 等，宏观数据不落盘，只以文本进 prompt。

---

## 6. Dashboard 宏观展示现状

| 层 | 现状 | 证据 |
|---|---|---|
| `dashboard_export.py` | 读 pending CSV 的 `Market_Regime`/`VIX` 列（scan 落盘的市场 regime，非宏观新闻），输出 `regime:{market,vix}`；另读 ^VIX/^GSPC 行情 | :1285-1286、:2893-2908、:129、:395 |
| `index.html` | 标题含"全球宏观"，但**无宏观新闻文本板块** | 仅 title/brand-sub |
| `app.js` | `renderRegime`（:861-892）展示 regime + VIX + Core/Observation 计数；`TOP_KEYS`（:841）展示宏观资产（S&P500/Nasdaq/Dow/VIX/US10Y/DXY/Gold/WTI） | :841、:861-892 |

> Dashboard 只展示"市场 regime + VIX + 宏观资产价格"，**不展示宏观新闻（combined_news）与结构化经济数据（CPI/PCE）**。

---

## 7. 结论：宏观在链条里的真实位置

```
宏观新闻/经济数据/市场数据/板块表现（RSS + yfinance + FRED/BLS/BEA）
        │
        ├─► build_event_regime_gate（程序化关键词/正则，零 token）
        │        └─► event_regime ──► apply_entry_quality_gate / match_pool_to_report
        │                              └─► 【硬性决定 Core 候选集合】  ★ 主杠杆
        │
        ├─► pre_scan_portfolio_review（AI 持仓风控）
        │        └─► Dropped/Active ──► 剔除扫描池（不参与 Core 判定）
        │
        └─► generate_ai_report / enrich_verified_items_with_ai_details（AI prompt 宏观段）
                 └─► 影响 AI_Score（30%）+ 文本解释，不决定 Core 集合
```

**一句话**：宏观对 Core 的**硬约束在 AI 之前的程序门控里完成（零 token）**；AI 里看到的宏观只用于打分（30%）和写解释。

---

## 8. 对 scan 角色重定义的影响

1. **宏观门控与角色重定义正交，不受影响**：`event_regime → apply_entry_quality_gate` 的 `EVENT_HARD_AVOID`/`EVENT_WATCH_TECH_FAIL`、以及 `match_pool_to_report` 的 hawkish_watch 门槛，全部发生在 AI 调用**之前**、基于全池 `pool_data` 逐项判定。角色重定义只收缩"AI 输入从 262 只→≤7 只"，**不改动这条程序门控**。
2. **宏观 token 不随收缩节省**：`generate_ai_report` prompt 里的宏观段（`combined_news[:12000]` + `event_regime_text` + `macro_market` + `economic_block` + `key_people_block`）是**全局段**，与 `pool_lines`（逐股段）独立。角色重定义省的是逐股 `pool_lines` 的 token，宏观全局段 token 不变。
3. **持仓每日重评分仍吃宏观**：`build_ai_input` 把持仓强制纳入 AI 输入后，`match_pool_to_report` 的 `_is_position` 强制 Core，但 hawkish_watch 门槛对持仓同样生效（:2948-2950 不豁免 `_is_position` 前先过 core_quant_min——注意：`_is_position` 走 `or` 短路，会绕过 hawkish_watch 的技术/量化门槛，仅 `_is_position=True` 即 core_ok）。这一点在实施换股规则时需留意：**持仓股在高置信度鹰派重定价下不会被 hawkish_watch 降级**，符合"持仓走重评分、不重复严筛"的设计，但需在报告/复盘里显式确认是否要单独处理。

> 附带待留意项（不属本次修复）：`economic_structured` 死变量——结构化宏观 dict 被丢弃，若未来想让宏观数值化（如写 dashboard 或做规则），需先接上这个已断开的变量。
