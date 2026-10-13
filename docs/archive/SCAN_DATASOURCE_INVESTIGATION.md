# Scan 数据源与时间敏感性调查

> 生成时间：2026-10-08 00:32 GMT+8
> 方式：只读代码审查（scan.py / quant_factor_lab.py / quant_factor_price.py / dashboard_export.py）。未改任何代码、未跑网络请求。

---

## 0. 一句话结论

**scan 是"前一日收盘型因子 + 实时盘前参考价"的混合体（代码显式双价格口径）。**
- **技术因子（MA20 / RSI / MACD / KDJ / 乖离率 / 周线 / 宏观 Regime）**：锚定"最后完整常规交易日"收盘，**在盘前窗口内（早于美东 09:30 开盘）任何时刻跑都完全相同** —— 即"前一日收盘型"。
- **盘前参考价（Premarket_Price / Change_Pct / AsOf_ET）**：运行时刻实时拉取的盘前 1m 成交 —— 即"实时盘前型"。
- **新闻快照（News_AsOf_ET + 内容）**：每次运行即时抓取 —— "运行时刻新鲜度"。

**提前到 11:07 UTC 是否会改变因子值？不会。** 改变的是（软性的）盘前参考价与新闻快照的"早 2 小时"，技术因子零影响。你担心的"越早盘前数据越少→因子越不全"的硬权衡，**对因子不成立**（因子本就不含当日盘前）；只对盘前参考价成立，而那是显示字段、不进因子数学。

---

## 1. scan.py 的因子计算用什么数据

| 数据 | 代码位置 | 数据源 | 周期/参数 | 锚定口径 |
|---|---|---|---|---|
| 个股技术日线 | `scan.py:766` `get_kline_data` → `yf.download(ticker, period="6mo", auto_adjust=False)` | **yfinance** | 6mo 日线，未复权 | 经 `_filter_completed_daily_bars` 剔除未完成日 → **最后完整常规交易日** |
| 股指/宏观日线 | `scan.py:885,927,1055` `_download_close_series` | yfinance | SPY 6mo/30d、周线 1y、VIX 15d | 同上，日线 ≤ cutoff |
| 盘前 1m 实时 | `scan.py:782` `get_premarket_snapshot_batch` → `yf.download(..., period="1d", interval="1m", prepost=True)` | yfinance | 1m，含盘前 | **运行时刻实时**（`prepost=True`） |
| Phase 2B 价格历史 | `quant_factor_price.py:105` `fetch_batch_prices` → `yf.download(tickers, start, end, auto_adjust=False)` | yfinance | 批量日线 | 经 `cutoff = last_completed_regular_date_us()` 封顶 → 仅完整日 |
| 新闻 | `scan.py:322-387` `yf.Ticker(ticker).news` + Google News | yfinance / Google | 运行时刻 | **运行时刻新鲜度** |

- **数据源统一是 yfinance**（未用其他行情源做因子）。
- 因子口径为 `auto_adjust=False`（未复权），与 Phase 1/2B 一致（`quant_factor_price.py:11,15,109`）。
- 关键封顶函数 `_last_completed_regular_date_us`（`scan.py:739`）：

```python
def _last_completed_regular_date_us(asof=None):
    now = asof or get_scan_asof_us()
    if now.time() < datetime.time(16, 0):      # 美东 16:00 收盘前
        return now.date() - datetime.timedelta(days=1)   # → 昨天
    return now.date()                                      # 收盘后 → 今天
```

即：**交易日内、美东 16:00 前的任何一次运行，Technical_Date 都是"昨天"**。

---

## 2. 是否使用盘前数据

**是，但仅用于"当前参考价"显示字段，绝不进入技术因子。**

- `scan.py:839-877` `apply_premarket_snapshot`：仅当 `state == "PREMARKET"`（美东 04:00–09:29）才拉盘前 1m；否则 `snap = {}`。
- `scan.py:864` `item["Price_Reference"] = "PREMARKET" if q else "REGULAR_CLOSE"` —— 盘前有报价才标 PREMARKET，否则回退昨收。
- `scan.py:3720` 注释："双价格口径：技术K线=最后完整常规交易日；当前参考=盘前最新成交。两者禁止混算。"
- `scan.py:773` 注释："Yahoo 在 09:30-16:00 ET 可能返回当天的未收盘日线；技术指标禁止使用它。"

**盘前数据是否影响因子值（MA20/RSI/MACD）？不影响。** 因子输入经 `_filter_completed_daily_bars` 强制截断到 cutoff（最后完整日），盘前跳动被排除。盘前只影响 `Premarket_Price` 等显示列。

---

## 3. 时间敏感性验证

**同一交易日，10:00 UTC（06:00 ET）跑 vs 13:00 UTC（09:00 ET）跑，snapshot 是否相同？**

| 输出 | 10:00 UTC | 13:00 UTC | 是否相同 | 原因 |
|---|---|---|---|---|
| `Technical_Date` | 昨天 | 昨天 | ✅ 同 | 都早于 16:00 ET → cutoff 都是昨天 |
| MA20 / RSI / MACD / KDJ / 乖离率 / 周线 | 同序列 | 同序列 | ✅ 同 | 输入日线被截断到同一 cutoff |
| 宏观 Regime（VIX/SPY MA20） | 同 | 同 | ✅ 同 | 日线口径一致 |
| `Premarket_Price / Change_Pct / AsOf_ET` | 06:00 ET 盘前报价 | 09:00 ET 盘前报价 | ❌ 不同 | 实时盘前 1m，多 3h 价格发现 |
| 新闻快照 `News_AsOf_ET` + 内容 | 较早 | 较晚 | ❌ 略不同 | 新闻运行时刻抓取 |

**差异仅来自 2 个软性字段（盘前参考价、新闻），技术因子完全不变。** 这是从代码逻辑**确定性**得出的结论（cutoff 与 daily-bar 过滤对任意"美东 16:00 前"的运行都产出相同输入序列），无需跑网络实证即可下结论。

- 可选实证（非必需，会触网）：同一天分别 07:07 / 09:07 ET 跑两次 `get_kline_data` 并 diff MA20/RSI，预期逐位相同。鉴于逻辑已确定，不建议现在跑。
- **是否有"应在某时刻跑"的注释？** 有设计意图注释，非代码内硬约束：
  - `tencent_scf_review_trigger.py:35`："Scan Timer（用户已确认）：0 0 21 * * 1-5 * = 工作日 21:00 北京 = 美东 09:00 盘前" —— 设计期望 scan 在**美东盘前 ~09:00** 执行。
  - `scan.py:153-195` 的 session 守卫：美东 ≥16:00（盘后）→ **直接 `sys.exit`，不运行**；09:30–16:00（盘中）→ "盘中补发"，明令"不伪造盘前价格，技术K线仍用最后完整常规交易日"。

---

## 4. 提前到 11:07 UTC 的后果

当前 `scan.yml` cron = `7 13 * * 1-5`（13:07 UTC 触发 → ~13:32 启动 ≈ 美东 09:32，已略过 09:30 开盘）。改为 11:07 UTC 触发 → ~11:32 启动 ≈ 美东 07:32。

| 维度 | 13:07 UTC（现状） | 11:07 UTC（提议） | 影响 |
|---|---|---|---|
| 运行时段 | 美东 09:07（盘前末尾） | 美东 07:07（盘前） | 都属 PREMARKET，模式不变 |
| 技术因子 / Technical_Date | 锚昨天 | 锚昨天 | **零变化** |
| 盘前参考价 | 09:07 ET 盘前报价（5h 积累） | 07:07 ET 盘前报价（3h 积累） | 早 2h、积累更少——**软字段，不影响因子** |
| 新闻快照 | 晚 2h 新闻 | 早 2h 新闻 | 轻微 |
| 开市前可见性（硬需求） | 落地 ~09:32 ET，**刚过开盘** ⚠️ | 落地 ~07:57 ET，**开盘前 1.5h** ✅ | **显著改善** |

**结论：提前到 11:07 UTC 不牺牲任何因子质量，反而更好满足"开市前拿到"。你预判的"越早盘前越不全→因子越差"对因子不成立；只对盘前参考价成立，而那是显示字段。这正是"双价格口径"设计带来的红利。**

> 注意：若提前到 **美东 04:00 之前（UTC 08:00 前）**，会落入 `PREMARKET_NOT_STARTED`，盘前抓取被跳过（`apply_premarket_snapshot` 仅 PREMARKET 才拉），参考价回退昨收。11:07 UTC（07:07 ET）安全在盘前窗口内。

---

## 5. 是否存在"当日锁定"机制（同日重跑）

| 产物 | 同日重跑行为 | 代码 |
|---|---|---|
| `us_stocks_pending_{YYYYMMDD}.csv` | **按日期覆盖**（同名重写，非追加） | `scan.py:3852` 日期命名 |
| `quant_factor_snapshot.csv` | **单文件覆盖**（每次写最新快照） | `scan.py:3765` `write_factor_snapshot(...)` |
| `quant_factor_price_history.csv` | **按 Date\|Ticker 幂等 upsert**（历史不被覆盖，只追加/更新最新日） | `quant_factor_price.py:169-192` |
| `ai_snapshot.csv` | **按 (Ticker, Rec_Date, Tag) upsert**（同键更新，异键新增，绝不按 Ticker 覆盖旧快照） | `scan.py:3507-3513` |
| `ai_text_cache.csv` | 按 Ticker upsert | `scan.py:3419-3463` |

- **同日重跑会覆盖** pending 与 factor snapshot（最新一次为准）。
- **price_history 是追加/幂等**，不会因重跑丢失历史——这也是 Phase 2B 的关键保护。
- **session 守卫兜底**：美东 ≥16:00（盘后）重跑 → `sys.exit`，根本不写；美东 <04:00 → 不拉盘前但照常跑（参考价回退昨收）。
- 10-08 监控器（PID 536931）靠"检测到更新 `quant_factor_snapshot.csv` 的新 commit"触发判决——单文件覆盖 + 每日一次 commit，机制成立。

---

## 6. 最终判定（回答指令的三个必答题）

1. **scan 是"前一日收盘型"还是"实时盘前型"？**
   → **混合（双价格口径，代码设计如此）**：技术因子 = 前一日收盘型（冻结）；盘前参考价 = 实时盘前型；新闻 = 运行时刻新鲜度。

2. **提前到 11:07 UTC 是否会改变因子值？**
   → **不会。** 技术因子与技术 Date 锚定"最后完整常规交易日"，在美东 16:00 前任何时刻运行都产出自同输入序列，逐位相同。仅盘前参考价（软字段）与新闻快照早 2 小时。

3. **若不确定，需何种验证？**
   → 逻辑已确定性成立，无需网络实证。若仍要双重保险：同日 07:07 / 09:07 ET 各跑一次 `get_kline_data` 对比 MA20/RSI（会触网，不建议现在做）。

**对"scan 提前"决策的含义**：提前到 11:07 UTC 是**低风险的合理优化**（改善开市前可见性、因子零退化）。但本指令的铁律仍是"判决前不改 scan cron"——本调查仅出文档，未改任何 workflow。

---

## 附：本调查未触碰的项
- 未改 `scan.yml` / 任何 workflow / 任何代码。
- 未跑 `yf.download` 等任何网络请求（纯静态代码审查）。
- 未碰监控 PID 536931 与 `/tmp/scan_1008_monitor.log`。
