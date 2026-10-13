# Quant Phase 1 数据源只读审计报告

> **审计性质**：READ-ONLY AUDIT
> **修改文件 = 0  ·  commit = 0  ·  push = 0**
> **审计基准**：`HEAD = origin/main = a220233`（`feat: add quant research dashboard`）
> **审计时间**：2026-10-07 10:13 UTC（2026-10-07 18:13 +0800，周三）
> **审计目标**：确定现有 Scan 每日已产生的真实行情数据，是否可直接作为 Quant Phase 1 Factor Lab 的输入

---

## 1. Executive Summary

### 核心结论

**Quant Phase 1 Factor Lab 已经完整接入现有 Scan 生产链路，并且已经在复用 Scan 已获取的 OHLCV 数据。**

这不是一个"待实现"的假设，而是代码库中已经存在的事实（由提交 `01db04f feat(quant): add factor library and daily snapshot`，2026-10-07 02:56 UTC 引入）：

| 环节 | 状态 | 位置 |
|---|---|---|
| 因子计算已接入 Scan | ✅ 已实现 | `scan.py:887` |
| SPY 基准已复用 | ✅ 已实现 | `scan.py:879` |
| Snapshot 写入已接入 | ✅ 已实现 | `scan.py:3729` |
| Snapshot 文件入库 | ✅ 已实现 | `.github/workflows/scan.yml:88-89` |
| 价格历史层已接入 | ✅ 已实现 | `.github/workflows/scan.yml:54` |
| **Snapshot 文件本体** | ⏳ **NOT YET GENERATED** | `quant_factor_snapshot.csv` 不存在 |

### 为什么数据文件尚不存在

这是**时序问题，不是缺陷**：

```
01db04f  2026-10-07 02:56 UTC   引入 Phase 1 代码
   ↓
scan.yml cron = '7 13 * * 1-5'  即每日 13:07 UTC 运行 Scan
   ↓
当前时间     2026-10-07 10:13 UTC  → 今日 Scan 尚未触发（约 2h54m 后）
   ↓
git log --all -- quant_factor_snapshot.csv  →  空（历史从未生成过）
```

即：**代码已就位，但代码落地后的第一次 Scan 还没跑**。今日 13:07 UTC 的 Scan 若成功，`quant_factor_snapshot.csv` 将自然产生。

### 最终判定

> **A. 可以直接复用现有 Scan 数据**（已事实成立）
>
> 附带一项次要建议：存在 2 处**口径不一致**需要在后续"最小适配"中修正（非必须，不影响可用性），见第 15、16 节。

### 关键数据一览

| 项 | 结论 |
|---|---|
| 个股 OHLCV 来源 | `yf.download(period="6mo", auto_adjust=False)` |
| 历史深度 | ≈126 交易日（满足 60D Beta 需求） |
| SPY | Scan 已单独下载 `6mo`，可直接复用 |
| Factor 计算消耗的网络请求 | 个股 0 次 / 日；SPY +1 次 / 日 |
| Candidate Pool | Gate **后**的全池 + 每项 `Gate_Status`（防选择性偏差设计） |
| Look-ahead bias | Factor 侧无；Forward Return 侧严格隔离（`side="right"`） |

---

## 2. Scan Data Flow

### 2.1 主流程（`main()` 实际执行顺序）

依据 `scan.py:3704-3735`：

```
get_scan_pool()                      3707  → S&P500 + Nasdaq100 + Dow → Top300（成交量）
   ↓  剔除 restricted_tickers（pre_scan_portfolio_review + review_triggered）  3708
build_stock_pool(pool_tickers)       3709  ← ★ Quant 因子在此计算
   ↓
apply_premarket_snapshot()           3715  盘前 1m 报价（仅 04:00-09:29 ET）
screen_technical_setups()            3716
enrich_pool_with_fundamentals(limit=120)  3717
enrich_pool_with_news()              3718
get_market_regime_context()          3719  ← SPY 60d / ^VIX 15d / 11 个行业 ETF 30d
apply_market_context_to_pool()       3720
score_candidate_quality()            3722  → Quant_Score
   ↓
snapshot_pool = pool_data            3726  ★ 保存全池引用（gate 前）
apply_entry_quality_gate()           3727  → 原地标记 Gate_Status
write_factor_snapshot(...)           3729  ★ 写 quant_factor_snapshot.csv（try/except 包裹）
   ↓
sys.exit(0) 若无合格标的           3733-3735
```

> **重要**：`write_factor_snapshot` 位于 **3733 的提前退出之前**。即使当日 Gate 后无合格标的，**快照仍会写入** —— 这对研究数据的连续性是正确设计。

### 2.2 Phase 1 在 Scan 内部的确切位置

`scan.py:875-1045` `build_stock_pool()`：

```python
# Quant Factor Lab：SPY 基准日线只抓取一次，供 Beta / Stock_RS 复用（绝不逐股重复下载）。
spy_close = _download_close_series("SPY", "6mo")            # 879
for ticker, name in tickers.items():
    df = get_kline_data(ticker)                             # 882  ← 现有 OHLCV，非新增
    if df is None or df.empty or len(df) < 40: continue     # 883
    # Quant Factor Lab：在 dropna 之前用完整 Close/Volume 计算扩展因子（零额外请求）。
    ext_factors = calculate_extended_quant_factors(df, spy_close)   # 887
    ...
    pool.append({ ... , **ext_factors })                    # 1040
```

要点：
- 因子在 **`df.dropna()`（第 900 行）之前**计算 —— 完整使用未截断的 Close/Volume；
- 因子结果通过 `**ext_factors` 并入 pool item，随后续 enrichment 一同流动；
- **每只个股没有任何新的网络请求**。

---

## 3. OHLCV Source

### 3.1 唯一 authority：`get_kline_data()`

**`scan.py:760-773`**

```python
def get_kline_data(ticker):
    for attempt in range(3):
        try:
            df = yf.download(ticker, period="6mo", progress=False,
                             auto_adjust=False, threads=False)     # 763
            if df is not None and not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)   # 765-766
                df = _filter_completed_daily_bars(df, get_scan_asof_us())  # 768
                if not df.empty:
                    return df
        except Exception:
            time.sleep(1.0 + attempt)
    return pd.DataFrame()
```

| 问题 | 答案 | 依据 |
|---|---|---|
| 从哪里获取？ | Yahoo Finance | `scan.py:763` |
| 使用什么 API / library？ | **yfinance**（`yf.download`） | `scan.py:41 import yfinance as yf` |
| yfinance 是否使用？ | **是**（唯一个股 OHLCV 来源） | `scan.py:41, 763` |
| 是否存在其他行情来源？ | ❌ 个股 OHLCV 无备选源；宏观走 FRED/BLS/BEA，与个股 K 线无关 | 见 3.3 |
| 每次 Scan 是否已下载历史 K 线？ | **是**，逐股 6mo 日线 | `scan.py:882` |

### 3.2 yf.download 在 scan.py 中的全部调用点

| 行 | 调用 | 用途 | 是否 trend signal 输入 |
|---|---|---|---|
| 420 | `period="7d" auto_adjust=False` | 个股新闻相关快照 | 否 |
| 591 | `period="5d" group_by="ticker" auto_adjust=True` | 全市场批量成交量 → Top300 筛选 | 否 |
| **763** | **`period="6mo" auto_adjust=False`** | **★ 主日线 OHLCV → Phase 1 输入** | **是** |
| 789 | `period="1d" interval="1m" prepost=True` | 盘前 1m 报价（仅 PREMARKET 窗口） | 否 |
| 921 | `period="1y" interval="1wk" auto_adjust=True` | 周线 MACD（结果最终由日线收盘重构，见 934） | 否 |
| **1051** | **`auto_adjust=True`** `_download_close_series` | SPY / VIX / 行业 ETF 收盘序列 | **是（SPY）** |
| 1458 / 2152 / 2468 | `5d` / `2d` | Yahoo 标量兜底 / 价格补漏 | 否 |

### 3.3 其他"行情"途径（非个股 OHLCV）

- **FRED / BLS / BEA 网页抓取**（`scan.py:1455-1830`）：宏观面 Core PCE / CPI / 非农等，**不包含任何个股 OHLCV**。
- **`dashboard_export.py` 的 Stooq 降级**：存在于 Dashboard 导出器（评分 its own `QuoteProvider`），**与 Scan 无关**，不可作为 Phase 1 输入。

---

## 4. OHLCV Schema

### 4.1 实际字段

`get_kline_data` 返回 DataFrame 经 `_filter_completed_daily_bars`（`scan.py:741-757`）处理后：

| 字段 | 存在 | 消费位置 |
|---|---|---|
| `Open` | ✅ | `scan.py:988`（蜡烛形态） |
| `High` | ✅ | `scan.py:893`（ATR）、951 |
| `Low` | ✅ | `scan.py:893`、952 |
| `Close` | ✅ | `scan.py:889-892`、**Quant 因子唯一价格输入** |
| `Volume` | ✅ | `scan.py:967-979`、`quant_factor_lab` Volume_Ratio_20D |
| `Adj Close` | ⚠️ 可能存在（auto_adjust=False 时 yfinance 会带此列） | **无人消费**；`get_level_values(0)` 展平后保留但被忽略 |

**Quant Phase 1 实际只消费 2 列**：`Close`、`Volume`（`quant_factor_lab.py:205-206`）。

### 4.2 数据类型 / 日期 / 时区 / 复权

| 维度 | 实测结论 | 依据 |
|---|---|---|
| 数值 dtype | `float64`（yfinance 默认；`Volume` 可能为 `int64`） | `scan.py:950-952` 显式 `.astype(float)` |
| 索引类型 | `pd.DatetimeIndex` | `scan.py:746` `pd.to_datetime` |
| **日期时区** | **`America/New_York`（tz-aware）** | `scan.py:755` `out.index = idx_us`；751-753 `tz_convert(US_TZ)` |
| 索引名 | `"Date"` | `scan.py:756` `out.index.name = "Date"` |
| **是否复权** | **`auto_adjust=False` → 未复权原始价** | `scan.py:763` |
| **SPY 是否复权** | ⚠️ **`auto_adjust=True`（与个股不一致）** | `scan.py:1051` |
| 时区定义 | `ZoneInfo("America/New_York")` | `scan.py:133` |

### 4.3 NaN / 重复日期

| 项 | 结论 |
|---|---|
| **NaN 处理** | 原始 `df` **可能存在 NaN**（因子刻意在第 900 行 `dropna()` **之前**计算）；但每个因子函数内部 `_clean_series()` 会 `.dropna()`（`quant_factor_lab.py:97`）→ **因子结果 NaN 安全，返回 None 而非脏值** |
| **重复日期** | yfinance 日线一般不产生重复；代码层面**未显式去重**（`_filter_completed_daily_bars` 只做 NaT 剔除 + cutoff 过滤）。判定为**低风险 / 未验证**（见第 16 节 Unknowns） |
| **索引丢弃副作用** | `_clean_series` 末尾 `reset_index(drop=True)`（`quant_factor_lab.py:98`）→ **丢弃全部日期信息**，所有窗口变为纯位置切片。若序列中间存在缺口，位置切片会漂移 |

---

## 5. Historical Depth

### 5.1 下载窗口

| 数据源 | period | ≈交易日数 | 位置 |
|---|---|---|---|
| 个股日线 | `"6mo"` | **≈126** | `scan.py:763` |
| SPY（Quant 专用） | `"6mo"` | ≈126 | `scan.py:879` |
| SPY（Regime） | `"60d"` | ≈41 | `scan.py:1068` |
| ^VIX | `"15d"` | ≈11 | `scan.py:1075` |
| 行业 ETF × 11 | `"30d"` | ≈21 | `scan.py:1099` |
| Dashboard 日线 | `"2y"` → 保留 180 | 180 | `dashboard_export.py:616-617` |

> 无显式 `start=`/`end=`，全部使用 `period=` 相对窗口。

### 5.2 因子最小样本需求 vs 实际供给

| 因子 | 所需 bars | 依据 | 6mo 是否满足 |
|---|---|---|---|
| Momentum 5D | 6 | `quant_factor_lab.py:116` | ✅ |
| Momentum 20D | 21 | 同上 | ✅ |
| **Momentum 60D** | **61** | 同上 | ✅ |
| Realized Volatility 20D | 21 | `quant_factor_lab.py:127` | ✅ |
| Volume Ratio 20D | 21 | `quant_factor_lab.py:142` | ✅ |
| ZScore 20D | 21 | `quant_factor_lab.py:154` | ✅ |
| **Beta 60D SPY** | **61（股）+ 61（SPY）** | `quant_factor_lab.py:167` | ✅ |
| **Stock RS 20D vs SPY** | **21 + 21** | `quant_factor_lab.py:189` | ✅ |

**结论：6mo ≈126 交易日，全部因子均可满足，且有余量（约 2×）。**

补充约束：
- `scan.py:883` 要求 `len(df) >= 40` 才进入 pool —— 低于此的个股被丢弃（不出现在 snapshot 中）；
- 即便通过 40 门槛，61 根不足的个股其 60D 因子会返回 `None`（优雅降级，非报错）。

---

## 6. Candidate Pool

### 6.1 结论：**C —— Gate 后的 candidate pool，但记录全池 + 每项 Gate_Status**

准确表述：**Phase 1 snapshot 覆盖"进入 Gate 的完整候选池"，并在每行记录该项是否通过 Gate**（而非仅保留通过者）。

### 6.2 池的形成链

| 步骤 | 位置 | 结果规模 |
|---|---|---|
| 维基百科抓 S&P500 + Nasdaq100 + Dow | `scan.py:578-583` | ~600+ |
| 批量 5d 成交量 → Top300 | `scan.py:591-609` | **300** |
| 剔除 restricted（pre_scan_portfolio_review / review_triggered） | `scan.py:3706-3708` | ≤300 |
| `get_kline_data` 成功且 `len(df) >= 40` | `scan.py:882-883` | ≤300（实际由此决定） |
| snapshot 收录 | `scan.py:3726, 3729` | **上述全部（含 Gate 失败项）** |

> 注意：`enrich_pool_with_fundamentals(pool_data, limit=120)`（`scan.py:3717`）**只影响基本面字段**，不影响 pool 成员；技术面最弱者的 `Fundamental_Score` 会为空，但**仍然进入 snapshot**。这是一个需要知晓的行为：snapshot 中部分行的 `Fundamental_Score` 会是空字符串。

### 6.3 Gate_Status 的生成位置与含义

**生成位置**：`scan.py:1206-1270` `apply_entry_quality_gate()`

关键机制 —— **原地标记**：

```python
def fail(item, status):
    item["Gate_Status"] = status      # 1209  原地写入 dict 对象
    fail_counts[status] = fail_counts.get(status, 0) + 1
...
for item in pool_data:                # 1217  遍历全池
    ...
    item["Gate_Status"] = "PASS_PRE_AI"   # 1257
    out.append(item)                       # 仅通过者进 out
return out                                 # 1271
```

由于 `snapshot_pool = pool_data`（`scan.py:3726`）与 `pool_data` 是**同一批 dict 对象**，第 3727 行调用 gate 后这批对象已被打上 `Gate_Status`，因此第 3729 行写入时，**全池都带有 Gate_Status**。

设计意图由代码注释明确（`scan.py:3724-3725`）：

> "Quant Factor Lab：保存完整候选池引用（gate 会原地给每项标记 Gate_Status），这样快照能记录'全候选池 + 每项是否过 gate'，避免只保留最终 Core/Observation 的 selection bias。"

### 6.4 Gate_Status 取值枚举

| 值 | 触发条件 | 位置 |
|---|---|---|
| `PASS_PRE_AI` | 全部通过（进入 AI 阶段） | `scan.py:1257` |
| `TECH_FAIL` | 技术确认数 < min_tech | `1220-1222` |
| `QUANT_FAIL` | Quant_Score < pre_ai_min_quant_score | `1223-1225` |
| `EVENT_HARD_AVOID` | Sector 在 hard_avoid 中 | `1226-1228` |
| `EVENT_WATCH_TECH_FAIL` | 鹰派重定价 + watch sector + 技术不足 | `1235-1240` |
| `ATR_FAIL` | ATR_Pct > atr_max_pct | `1241-1244` |
| `SECTOR_RS_FAIL` | Sector_RS_20D_Pct < sector_rs_min_pct | `1245-1248` |
| `SPY_TREND_FAIL` | SPY 跌破 MA20 + 压力/恐慌，非防御板块 | `1250-1256` |
| `PANIC_FAIL` | PANIC regime + 非防御 + Quant < 68 | `1258-1260` |

> **研究用途**：`Gate_Status` 允许 Phase 2/3 分别统计"全池 vs 仅 PASS_PRE_AI"的因子有效性，检验 gate 本身是否丢弃了有效信号。这是该设计的直接收益。

---

## 7. SPY Data

### 7.1 是否已由 Scan 获取：**是，且已有两处**

| # | 位置 | 调用 | 用途 | 能否供 Phase 1 复用 |
|---|---|---|---|---|
| 1 | `scan.py:879` | `_download_close_series("SPY", "6mo")` | **Quant 因子专用**（Beta / RS） | ✅ **正是 Phase 1 在用** |
| 2 | `scan.py:1068` | `_download_close_series("SPY", "60d")` | Market Regime（MA20、5D 收益） | ❌ 太短（41 根 < Beta 需 61）且时序靠后 |

第 1 处是本次 Phase 1 提交(`01db04f`) **专门新增**的，注释写明：

> `# Quant Factor Lab：SPY 基准日线只抓取一次，供 Beta / Stock_RS 复用（绝不逐股重复下载）。`

### 7.2 两个因子的实际数据需求

| 因子 | 输入 | 需求 | 当前供给 |
|---|---|---|---|
| `Beta_60D_SPY` | stock_close + spy_close | 各 ≥61 bars；按日期交集取最近 60 个重叠收益率 | SPY 6mo ≈126 ✅ |
| `Stock_RS_20D_vs_SPY` | stock_close + spy_close | 各 ≥21 bars；**位置切片** `[-1]/[-21]` | SPY 6mo ≈126 ✅ |

### 7.3 是否可以直接复用 / 是否需要额外请求

- **直接复用：是**。`spy_close` 已在 `build_stock_pool` 作用域内，逐股循环共用同一个 Series（`scan.py:879` 在循环外）。
- **额外网络请求：每日 +1 次**（SPY 6mo）。个股维度 +0。详见第 12 节。

### 7.4 ⚠️ 发现的两处口径风险

**风险 S1 —— SPY 复权口径与个股不一致**

| 序列 | auto_adjust |
|---|---|
| 个股 Close（`get_kline_data`） | `False`（未复权）`scan.py:763` |
| SPY Close（`_download_close_series`） | **`True`（已复权）**`scan.py:1051` |

Beta / RS 均为**收益率比值**，股息差异属二阶小量，短期影响有限；但口径不统一本身是隐患，且会让 `Stock_RS_20D_vs_SPY` 在除息日附近出现系统性微小偏移。

**风险 S2 —— SPY 序列未做"完整 bar"过滤**

`_download_close_series`（`scan.py:1049-1058`）仅返回 `df["Close"].dropna()`，**未调用** `_filter_completed_daily_bars`。而个股侧已过滤。

- 对 `Beta_60D_SPY`：影响被缓解 —— `beta_60d` 使用日期交集（`quant_factor_lab.py:171`），多出来的 SPY 日期会被 `intersection` 丢弃。
- 对 `Stock_RS_20D_vs_SPY`：**无保护** —— 该函数不使用任何日期对齐，只做位置切片（`quant_factor_lab.py:191-192`）。若 SPY 多出 1 根未完成 bar，RS 两端会错位一天。

> 当前 cron 固定在 **13:07 UTC = 09:07 ET（盘前）**，此时 Yahoo 通常不返回当日 bar，因此**实践中大概率不触发**；但手动触发盘中 Scan 时会暴露。定为 **P3 风险**。

---

## 8. quant_factor_lab.py Interface

### 8.1 是否自己抓取行情：**否。零网络请求。**

证据：
- 模块 docstring 明确声明（`quant_factor_lab.py:11`）：
  > `- 本模块不 import yfinance，不做任何网络请求（SPY 数据由 scan.py 传入）。`
- 实际 import 清单（`quant_factor_lab.py:61-64`）：仅 `os`、`numpy as np`、`pandas as pd`。
- 全模块 grep `request|urlopen|download|fetch|http|socket` → **无任何命中**（除上述注释行）。

**已审计确认：`quant_factor_lab.py` 不存在网络请求。**

### 8.2 接口清单

| 对象 | 类型 | 签名 / 内容 | 位置 |
|---|---|---|---|
| `calculate_extended_quant_factors` | 主入口 | `(df, spy_close=None) -> dict[str, float\|None]` | `196-216` |
| `build_snapshot_rows` | 构造行 | `(pool, scan_date) -> list[dict]` | `237-276` |
| `write_factor_snapshot` | 落盘 | `(pool, path, scan_date) -> int` | `279-309` |
| `KEY_COLUMNS` | 唯一键 | `("Scan_Date", "Ticker")` | `83` |
| `SNAPSHOT_COLUMNS` | schema | 32 列 | `68-80` |

### 8.3 输入参数与数据结构

**`calculate_extended_quant_factors(df, spy_close)`**
- `df`：`pd.DataFrame`，需含 `Close` / `Volume` 列，索引为交易日（`196-206`）。缺列时降级为空 Series。
- `spy_close`：`pd.Series`，可空；为空时 `Beta_60D_SPY` / `Stock_RS_20D_vs_SPY` → `None`。
- 返回 8 键 dict（`207-216`），值均为 `float` 或 **`None`（不是 0、不是 NaN）**。

**是否设计为接收 Scan 数据：是。** 输入契约（`pd.DataFrame` with Close/Volume + 可选 SPY Series）与 `get_kline_data()` 的输出形状完全吻合，并由 `scan.py:887` 直接注入。

### 8.4 snapshot 写入位置与 schema

- **路径**：`quant_factor_snapshot.csv`
  - 常量 `QUANT_FACTOR_SNAPSHOT_FILE`，`scan.py:59`
- **格式**：CSV，UTF-8，`index=False`，全列以 `dtype=str, keep_default_na=False` 读取（空值 = 空字符串）

**`SNAPSHOT_COLUMNS`（32 列，`quant_factor_lab.py:68-80`）**：

```
Scan_Date, Technical_Date, Ticker, Name, Sector,
Price,
RSI_14, Bias_Pct, MACD_Hist, MA20, MA50, MA20_Slope_5D,
ATR_Pct, KDJ_J, Volume_Ratio_5D,
Momentum_5D_Pct, Momentum_20D_Pct, Momentum_60D_Pct,
Realized_Volatility_20D_Pct, Volume_Ratio_20D, ZScore_20D,
Beta_60D_SPY, Stock_RS_20D_vs_SPY,
Sector_RS_20D_Pct, VIX, Market_Regime,
Fundamental_Score, Event_Score, Technical_Score_25,
Risk_Liquidity_Score, Quant_Score,
技术确认数, Gate_Status
```

> **关键观察：schema 中不含任何 Forward Return 列。** 前瞻收益完全不落 A snapshot —— 这是 look-ahead 隔离的结构性保证（见第 10 节）。

---

## 9. quant_factor_price.py

### 9.1 它为什么存在

模块定位（docstring `quant_factor_price.py:2-8`）：

> `Persistent Price History Layer —— 阶段 2B：为 Factor Snapshot 提供 Forward Return 的真实历史价格。`

根因：**Scan 从不持久化任何 OHLCV**。`get_kline_data()` 的 6mo 日线用完即弃，只留下技术指标标量。而 Backtest 计算 `T → T+5/10/20` 前瞻收益**必须在 T 之后的若干天才可能得到真实价格**，届时那只股票的 6mo 窗口早已滚动过去。

因此需要一个**按 Date|Ticker 长期留存、只增不改**的收盘价仓库。

### 9.2 是否与 Scan 行情数据重复

| 维度 | 判断 |
|---|---|
| **用途重复？** | ❌ **不重复**。Scan 的 6mo OHLCV 是易失内存数据；本层是持久化历史价格仓库。目标不同。 |
| **网络抓取重复？** | ⚠️ **有重叠**。它重新下载同一批 ticker 的收盘价（`101-118`），与当日 Scan 已抓过的数据存在 HTTP 层面的重复。但由于 Scan 不落盘，**功能上无法绕过**，除非改造 Scan 额外持久化 OHLCV（属于超出本任务的改动）。 |
| 能否省掉？ | 仅在"让 Scan 自行持久化 OHLCV"时才可省 —— 需改 Scan 生产逻辑，**本阶段不建议**。 |

### 9.3 是否已被生产 workflow 使用：**是**

`.github/workflows/scan.yml:52-54`：

```yaml
# Quant Research 价格历史层：扫描成功后，为 Factor Snapshot 的历史 ticker
# 批量更新 quant_factor_price_history.csv（幂等 upsert，绝不逐股重复请求）。
- name: 更新 Quant 价格历史
  run: python quant_factor_price.py
```

并在 `scan.yml:68-69`（artifact 上传）与 `scan.yml:92-93`（条件提交）中登记。

### 9.4 storage schema 与幂等性

| 项 | 内容 | 位置 |
|---|---|---|
| 文件 | `quant_factor_price_history.csv` | `38` |
| 列 | `Date, Ticker, Close` | `39` |
| 唯一键 | `Date \| Ticker` | `25, 186` |
| 幂等策略 | **历史记录永不被覆盖**，只追加不存在的新 key | `164-188` |
| 写入方式 | `.tmp` → `os.replace()` 原子替换 | `263-265` |
| Close 精度 | `round(float(c), 6)` | `138` |
| **当前存在？** | ❌ **NOT YET GENERATED** | — |

### 9.5 是否需要历史数据初始化

**不需要手工 seed。** `update_price_history()`（`210-268`）自动：

```
start = min(snapshot.Technical_Date) - 7d      # 246-250
end   = now(US_TZ) + 1d                        # 251-252
fn(tickers, start, end)                        # 255  单次批量
```

即"自 snapshot 最早日期起回溯 7 天到今天"的整段历史，**首次运行即可全量拉取**。

代价：**首次运行是一次较大的批量下载**（300 tickers × 全部历史区间），但为**单次批量 `yf.download(tickers, ..., threads=True, group_by="ticker")`**，不是逐股请求（`101-118`）。

**天然限制**：`T+n` 的前瞻收益只有在 `T+n` 真实到来后才会存在。这是物理约束，非缺陷 —— 且 `forward_return_nd` 对未到期样本返回 `None`，**绝不填 0 / 插值**。

---

## 10. Date / Look-ahead Audit

> 本节为本次审计的核心。

### 10.1 Factor Snapshot 的 Date 到底是什么

**存在两个不同的日期字段，语义必须区分：**

| 字段 | 来源 | 含义 | 位置 |
|---|---|---|---|
| `Scan_Date` | `today_us_str()` = `datetime.now(US_TZ)` | **运行日**（cron 当日） | `scan.py:144-145, 3729` |
| `Technical_Date` | `pd.Timestamp(df.index[-1])` | **最后完整常规交易日 T** | `scan.py:1012` |

**用 Scan 举例**（cron 13:07 UTC = 09:07 ET，周三）：
- `Scan_Date` = `2026-10-07`（周三）
- `_last_completed_regular_date_us(09:07 ET)` → 因为 `time() < 16:00` → cutoff = `2026-10-06`（周二）
- 保留全部 `date <= 2026-10-06` 的 bar → `Technical_Date` = `2026-10-06`（周二最后一根日线）

**→ Phase 1 Factor 计算的 T = `Technical_Date`，而非 `Scan_Date`。这是正确且必须的设计。**

### 10.2 Factor 侧：只能使用 <= T 的数据 —— ✅ 满足

四道防线：

1. **未完成 bar 剔除**（`scan.py:741-757`）
   ```python
   cutoff = _last_completed_regular_date_us(asof)
   return out.loc[out.index.date <= cutoff].copy()   # 757
   ```
   
2. **固定 as-of，防盘内漂移**（`scan.py:134, 140-142`）
   ```python
   RUN_ASOF_UTC = datetime.datetime.now(datetime.timezone.utc)
   RUN_ASOF_US  = RUN_ASOF_UTC.astimezone(US_TZ)
   def get_scan_asof_us(): return RUN_ASOF_US
   ```
   > docstring 原文：*"整次 Scan 固定一个快照时间，避免 300 只股票抓取期间出现时间口径漂移。"*
   → **Top300 逐股下载耗时数十分钟，但所有股票共享同一个 cutoff，不存在"先抓的用旧、后抓的用新"。**

3. **所有因子为纯 trailing 窗口**（`quant_factor_lab.py:113-193`）
   - `momentum_pct`：`c.iloc[-1]` vs `c.iloc[-1-n]`（历史）
   - `realized_volatility_20d_pct`：`pct_change()` 后 `.iloc[-20:]`（历史）
   - `volume_ratio_20d`：`v.iloc[-1]` vs `v.iloc[-21:-1]`（**注意：前瞻排除当日，`[:-21:-1]` 刻意不含 `iloc[-1]`**）
   - `zscore_20d`：`prev = c.iloc[-21:-1]`（同样排除当日，避免自包含）
   - `beta_60d` / `stock_rs_20d_vs_spy`：同构 trailing
   
   > 所有窗口均严格指向 `T` 或 `T` 之前。**无任何 factor 引用 `T+1` 或更晚的数据。**

4. **snapshot schema 不含前瞻列**（`quant_factor_lab.py:68-80`）
   → 结构上不可能把未来收益写进 snapshot。

### 10.3 Forward Return 侧：严格隔离 —— ✅ 满足

`quant_factor_backtest.py:80-107`：

```python
pos = price_series.index.searchsorted(ts, side="right")   # 100
target = pos + n - 1                                       # 101  T 之后第 n 个交易日
if target < 0 or target >= len(price_series):
    return None                                            # 102-103
future_close = _to_float(price_series.iloc[target])
if future_close is None or future_close <= 0:
    return None                                            # 105-106
return round((future_close / close_t - 1.0), 6)            # 107
```

| 检查项 | 结论 |
|---|---|
| `side="right"` | ✅ **严格排除 T 自身**，`T+0` 不会被当作 `T+1` |
| 未来不足 → 返回 `None` | ✅ `102-103, 105-106`，**绝不填 0、不插值、不复用最近交易日** |
| 分母 `close_t` = snapshot `Price`（= `Close[T]`） | ✅ `123` 取自 `row["Price"]`，与因子基准同源 |
| Forward Return 存放位置 | ✅ 仅在 backtest 产物中，**从不回写 snapshot** |

### 10.4 职责分离结论

```
 ┌─────────────── Factor Snapshot ──────────────┐        ┌──── Backtest ────┐
 │ 只用 <= T 的数据                              │        │  T → T+n         │
 │ 8 个 Quant 因子 + V1 scores + Gate_Status     │───────▶│  真实未来收盘价   │
 │ 无任何 forward 列                             │        │  来自 price hist │
 └──────────────────────────────────────────────┘        └──────────────────┘
              Scan 当日写出                                    n 天后才可得
```

**审计结论：现有实现的 look-ahead 隔离是正确的。**

### 10.5 残留风险（详见第 16 节）

| 编号 | 风险 | 等级 |
|---|---|---|
| L1 | `_clean_series` 丢弃 index（`reset_index(drop=True)`），所有窗口退化为位置切片；若序列有缺口会漂移 | P3 |
| L2 | SPY 未过滤未完成 bar + auto_adjust 不一致，可能影响 `Stock_RS_20D_vs_SPY`（该函数无日期对齐保护） | P3 |
| L3 | `reverse factor-snapshot backfill` 被 docstring 禁止（`quant_factor_price.py:19`），但**未见代码级强制守卫**，属流程约束 | P3 |

---

## 11. Snapshot Storage

### 11.1 Phase 1 设计的 snapshot 文件

| 项 | 内容 | 位置 |
|---|---|---|
| **文件路径** | `quant_factor_snapshot.csv`（仓库根目录，与 data-dir 同级） | `scan.py:59` |
| **格式** | CSV / UTF-8 | `quant_factor_lab.py:307` |
| **Schema** | 32 列，见 8.4 | `quant_factor_lab.py:68-80` |
| **唯一键** | `Scan_Date \| Ticker` | `quant_factor_lab.py:83, 296, 299` |
| **幂等** | ✅ 是（`key_map` dict 覆盖，重复写不产生 duplicate） | `294-302` |
| **允许每日 upsert** | ✅ 是（新 `Scan_Date` 追加；同 `Scan_Date` 覆盖） | `298-300` |
| **原子性** | ✅ `.tmp` + `os.replace()` | `306-308` |
| **排序** | 按 `key` 字符串升序 | `302` |

### 11.2 是否已有历史 snapshot

```
git log --all -- quant_factor_snapshot.csv     →  （空）
ls quant_factor_snapshot.csv                   →  不存在
```

# ⚠️ NOT YET GENERATED

**原因**：生成器 `scan.py:3729` 由 `01db04f`（2026-10-07 02:56 UTC）引入，而唯一的触发途径是 `scan.yml` 的 `cron: '7 13 * * 1-5'`。当前 10:13 UTC，**今日 13:07 UTC 的 Scan 尚未运行**。

**预期**：今日 13:07 UTC Scan 成功后首次产生。**本审计未创建、也不会创建该文件。**

### 11.3 相关存储一览

| 文件 | 状态 | schema | 键 |
|---|---|---|---|
| `quant_factor_snapshot.csv` | ⏳ **NOT YET GENERATED** | 32 列 | `Scan_Date\|Ticker` |
| `quant_factor_price_history.csv` | ⏳ **NOT YET GENERATED** | `Date, Ticker, Close` | `Date\|Ticker` |
| `quant_factor_backtest.csv` | ⏳ **NOT YET GENERATED** | — | — |
| `quant_factor_validation.csv` | ⏳ **NOT YET GENERATED** | — | — |
| `quant_score_v2_candidates.csv` | ⏳ **NOT YET GENERATED** | — | — |
| `quant_walk_forward_results.csv` | ⏳ **NOT YET GENERATED** | — | — |
| `quant_shadow_performance.csv` | ⏳ **NOT YET GENERATED** | — | — |
| `quant_production_state.json` | ⏳ **NOT YET GENERATED** | — | — |

---

## 12. Network Request Analysis

### 12.1 Phase 1 增量成本明细

| 维度 | 增量请求 | 依据 |
|---|---|---|
| **个股 OHLCV** | **0** | `scan.py:882` 复用既有的技术面 6mo K 线；因子在内存中计算（`887`）。逐股维度：0 新增 |
| **SPY** | **+1 / 日** | `scan.py:879` 新增 `_download_close_series("SPY","6mo")` |
| Phase 2B 价格历史 | **+1 批量 / 日** | `quant_factor_price.py:101-118` 单次批量（非逐股） |
| **合计（Phase 1 因子层）** | **1** | — |

### 12.2 为什么 SPY 不是 0

这是个**时序 + 长度**双重问题：

| 现有 SPY 来源 | 长度 | 获取时机 | 能否复用 |
|---|---|---|---|
| Regime SPY `60d`（`scan.py:1068`） | ≈41 根 | **第 3719 行，在 build_stock_pool(3709) 之后** | ❌ 太短（Beta 需 61）且顺序靠后 |

因此 Phase 1 提交专门在 `build_stock_pool` 开头加了第 879 行的 `6mo` SPY 拉取。**这是为保证数据充分而付出的 +1 请求，是合理的代价，但技术上可优化到 0。**

### 12.3 归零路径（仅建议，本阶段不实施）

把 Regime 的 SPY 下载**提前**到 `build_stock_pool` 之前，并统一使用 ≥6mo 窗口，让两处共用同一个 Series → **SPY 增量归 0**。这需要改动 `scan.py`（禁止范围），本报告仅记录。

### 12.4 已存在但与 Phase 1 无关的成本

| 系统 | 请求 | 说明 |
|---|---|---|
| `dashboard_export.py` | 每 Stock 一次 `2y` 日线（≈34 只） | Dashboard 自带图表/指标需求（`dashboard_export.py:616-617, 1306`），**独立系统，不应作为 Phase 1 输入源** |
| Regime | SPY 60d + ^VIX 15d + 11×行业 ETF 30d | V1 宏观门控，pre-existing |
| `get_scan_pool` | 1× 批量 Top300 5d 成交量 | pre-existing |

---

## 13. Workflow Analysis

### 13.1 现有 workflows

```
.github/workflows/
├── scan.yml            ← ★ Phase 1 在此
├── review.yml          （无 quant 引用）
├── evolve.yml          （无 quant 引用）
└── dashboard-data.yml  （无 quant 引用）
```

### 13.2 Phase 1 在 scan.yml 的完整接线

| 环节 | 行号 | 内容 |
|---|---|---|
| 触发 | `7` | `cron: '7 13 * * 1-5'`（13:07 UTC，周一至周五）＋ `workflow_dispatch` |
| 并发 | `12-13` | `group: us-stock-scan`，`cancel-in-progress: false` |
| 运行 Scan | `49` | `python scan.py` → 计算因子 + 写 `quant_factor_snapshot.csv` |
| **价格历史** | **`54`** | `python quant_factor_price.py` |
| Artifact 保护 | `68-69` | `quant_factor_snapshot.csv`、`quant_factor_price_history.csv` 上传（`if: always()`） |
| 条件入库 | `88-93` | `if [ -f ... ]; then git add ...`（文件不存在时不失败） |

### 13.3 明确回答 Phase 1

| 问题 | 答案 |
|---|---|
| 有没有 production workflow？ | ✅ **有** —— 不需要新建，已寄生在 `scan.yml` |
| 是否被 scan.yml 调用？ | ✅ **是**（全部环节） |
| 是否独立运行？ | ❌ 否，随 Scan 主流程运行 |
| 是否需要新增 workflow？ | ❌ **Phase 1 不需要**（不改 V1、零风险的最小方案） |

### 13.4 尚未接入生产的部分（Phase 2 及以后）

`grep -rn "quant_" .github/workflows/` 命中项**仅限** `quant_factor_price.py` 与两个数据文件名。

| Phase | 模块 | 生产 runner |
|---|---|---|
| 1 Factor Lab | `quant_factor_lab.py` | ✅ scan.yml |
| 2B Price History | `quant_factor_price.py` | ✅ scan.yml |
| **2 Backtest** | `quant_factor_backtest.py` | ❌ **无** |
| **3 Validation** | `quant_factor_validation.py` | ❌ **无** |
| **4–7** | `quant_score_v2 / walk_forward / shadow / production` | ❌ **无** |

> Phase 2–7 目前**只有测试覆盖，无生产调度**。这解释了为何 Dashboard 显示 `NOT_ENOUGH_DATA` —— 数据链在 Phase 2 处断开。

---

## 14. Data Availability Matrix

### 14.1 逐项回答

| 项 | 结论 | 说明 |
|---|---|---|
| **OHLCV** | **YES**（内存中） / **NO**（未持久化） | Scan 每次运行可取得 `period="6mo"`、`auto_adjust=False`、含 O/H/L/C/V 的日线（`scan.py:763`）。但**用完即弃，磁盘上无留存** |
| **Volume** | **YES** | `Volume` 列随 OHLCV 一同返回；`Volume_Ratio_20D` 已可计算（`quant_factor_lab.py:139-148`） |
| **SPY** | **YES** | `scan.py:879` 已专门下载 `6mo`；⚠️ `auto_adjust=True` 与个股不一致 |
| **60D history** | **YES** | 6mo ≈126 交易日 > 所需 61 根（`quant_factor_lab.py:167`），余量约 2× |
| **Candidate Pool** | **YES** | 每交易日 cron 触发；Top300 → restricted 剔除 → `len(df)>=40` 过滤，规模稳定 |
| **Snapshot storage** | ⏳ **NOT YET GENERATED** | `quant_factor_snapshot.csv` 从未产生；等今日 13:07 UTC Scan |

### 14.2 缺什么？

**唯一缺项是"已落盘的 snapshot"，且它会在约 2h54m 后自动补齐。**

其余所有输入（OHLCV / Volume / SPY / 60D 深度 / Candidate Pool）**每一项在每次 Scan 运行时都真实可得**。

**没有任何一项需要通过"下载新行情"或"backfill"来获得。**

> ⚠️ 但请注意一个连锁依赖：**Backtest 的 Forward Return 依赖 `quant_factor_price_history.csv`，而后者又依赖 snapshot 先存在**（`quant_factor_price.py:224-226`）。链条为：
> `Scan → snapshot → price history → (n 天后) backtest`
> 即使今日 13:07 UTC 产出第一批 snapshot，**Phase 2 的有效样本仍要等 T+20 个交易日才足够做统计**。这是时间成本，非数据缺失。

---

## 15. Recommended Phase 1 Implementation Architecture

### 15.1 现状架构（已实现，无需重建）

```
[Wikipedia] → S&P500 + Nasdaq100 + Dow ──┐
                                          ▼
                              [批量 5d 成交量] → Top300
                                          ▼
                         ┌──── get_kline_data(ticker) ────┐
                         │  yf.download 6mo               │  ← 复用现有技术面抓取（0 增量）
                         │  auto_adjust=False             │
                         │  _filter_completed_daily_bars  │  ← look-ahead 防线
                         └────────────┬───────────────────┘
                                      ▼
                    calculate_extended_quant_factors(df, spy_close)   ← quant_factor_lab.py
                         ↑                              ↑
                    8 因子纯函数                  _download_close_series("SPY","6mo")
                    （零网络）                          (+1 请求/日)
                                      ▼
                         **ext_factors → pool item
                                      ▼
                    ┌── apply_entry_quality_gate（原地标记 Gate_Status）
                    ↓
              write_factor_snapshot(snapshot_pool, ...)   ← 全池 + Gate_Status
                                      ▼
                    quant_factor_snapshot.csv  （Scan_Date|Ticker，幂等 upsert，原子写）
                                      ▼
                    [scan.yml] artifact 上传 + 条件 git add
```

### 15.2 建议（均属"最小适配"，非重建）

| # | 建议 | 等级 | 是否阻塞启动 |
|---|---|---|---|
| **R1** | **什么都不改，等今日 13:07 UTC Scan 自然产出第一批 snapshot** | — | 否（推荐路径） |
| R2 | 统一 SPY 与个股的 `auto_adjust`（建议 SPY 也用 `False`） | P3 | 否 |
| R3 | 对 SPY 序列补做 `_filter_completed_daily_bars`，或至少给 `stock_rs_20d_vs_spy` 加日期对齐 | P3 | 否 |
| R4 | 将 Regime 的 SPY 下载提前并加长到 6mo，与 Phase 1 共用 → SPY 增量请求归 0 | P3 | 否 |
| R5 | 给 `write_factor_snapshot` 的 try/except（当前仅 `print` 告警）加**显式可观测信号**（如写 `last_run.json` 或非零退出码提示），避免静默失败 | P2 | 否 |
| R6 | snapshot 写入后再加一次存在性断言 log，让"数据是否真的落下"在 Scan 日志中显式可见 | P3 | 否 |
| R7 | Phase 2 及以后需新增独立 workflow（当前无 runner），但**建议等 T+20 样本足够后再启用** | — | 否 |

### 15.3 明确不建议做的事

- ❌ 不建议让 Phase 1 依赖 `dashboard_export.py` 的行情（不同系统、不同触发时机、不同 purpose）
- ❌ 不建议为 Phase 1 新建 workflow（scan.yml 已足够，新增会引入并发与重复写入风险）
- ❌ 不建议此刻做 backfill（`quant_factor_price.py:19` 明确禁止反向生成历史 snapshot）

---

## 16. Risks / Unknowns

### 16.1 已识别风险

| # | 风险 | 等级 | 影响 | 缓解 |
|---|---|---|---|---|
| **R-P1** | **snapshot 尚未由任何一次真实 Scan 验证** —— 代码路径从未端到端跑通过 | **P2** | 若 `write_factor_snapshot` 抛异常，只会 print 一行 warning 并被吞掉（`scan.py:3730-3731`），Scan 照常成功 | 今日 Scan 后必须立即核验文件是否产生（R5/R6） |
| **R-P2** | **静默失败不可观测** —— try/except 仅 print，无退出码/无 metrics | P2 | 长期缺数也无人察觉 | R5 |
| **R-P3** | Scan 在到达 3729 之前存在多个提前退出点（如 `scan.py:129` 环境变量缺失、`3712` 无有效标的） | P3 | 这些情况下不产 snapshot | 属设计预期，但需知晓 |
| **L1** | `_clean_series` 丢弃 index → 纯位置窗口 | P3 | 若个股出现停牌/缺 bar，60D 窗口会"跨过"缺口，隐含少量失真 | 未来可为 `_clean_series` 保留日期感知版 |
| **L2** | SPY `auto_adjust=True` vs 个股 `False`；SPY 未完成 bar 未过滤 | P3 | `Stock_RS_20D_vs_SPY` 在盘中手动 Scan 或除息日附近可能错位/偏移 | R2 + R3 |
| **L3** | 禁止"反向回填历史 snapshot"仅为文档约定（`quant_factor_price.py:19`），无代码守卫 | P3 | 未来若有人误写，无机制拦截 | 建议后续加只读断言 |
| **F1** | `enrich_pool_with_fundamentals(limit=120)` 只覆盖部分标的 | P3 | snapshot 中部分行 `Fundamental_Score` 为空；若研究时把该列作为因子/过滤条件，会引入非随机的样本缺失 | Backtest 需显式处理空值（当前 `compute_forward_returns` 不依赖此列） |
| **F2** | `scan.py:883` 的 `len(df) >= 40` 门槛会静默丢弃新股/长期停牌股 | P3 | 候选池存在结构性筛选，非随机采样 | 研究结论需在此边界内解读 |

### 16.2 Unknowns（本次未实地验证）

| # | 未验证项 | 原因 | 验证方式 |
|---|---|---|---|
| U1 | yfinance 日线是否存在**重复日期** | 需实际数据；本报告全程未下载行情（遵守禁止条款） | Scan 产出后对 `quant_factor_snapshot.csv` 做日期唯一性检查 |
| U2 | 6mo 实际返回的确切交易日数 | 依赖 Yahoo 端数据 | 同上，统计 `Technical_Date` 序列间距 |
| U3 | Adj Close 列是否真的被 `get_level_values(0)` 保留且未干扰 | 需运行时 inspect | 同上 |
| U4 | 今日 13:07 UTC Scan 的实际成功率 | 尚未发生 | 观察下一次 workflow run |

### 16.3 无风险的确认项

以下均已**实地代码审计确认**，不存在风险：

- ✅ `quant_factor_lab.py` **零网络请求**
- ✅ Factor 计算 **零 look-ahead**（四道防线）
- ✅ Forward Return **严格 `side="right"` 隔离**，未到期返回 `None` 而非 0
- ✅ snapshot **幂等 + 原子写**，支持每日 upsert
- ✅ Phase 1 **未改变 V1 任何生产逻辑**（因子只是附加写入，不参与 `Quant_Score` / Gate / 止损 / 推荐）
- ✅ Phase 1 **未启用 V2 / Shadow**
- ✅ Dashboard 展示层 **未生产任何 Quant 数据**

---

## 17. 最终结论

# **A. 可以直接复用现有 Scan 数据**

### 判定依据

| 判据 | 结论 |
|---|---|
| Scan 是否已产生 Quant 所需的 OHLCV？ | ✅ 是，每日 `get_kline_data()` 的 6mo 日线 |
| 历史深度是否满足 60D Beta？ | ✅ 是，≈126 根 vs 需 61 根 |
| SPY 是否已可得？ | ✅ 是，`scan.py:879` 专门一次性下载 6mo |
| Phase 1 是否需要新抓行情？ | ✅ 否，个股维度 0 增量 |
| 是否已在代码中实际接入？ | ✅ **是，且已提交、已上线** |
| 是否存在 look-ahead bias？ | ✅ 否，隔离设计正确 |
| 是否需要改变 V1？ | ✅ 否 |

### 补充说明

这一结论**不是建议**，而是**对既有事实的确认**：Quant Phase 1 Factor Lab 已经在复用 Scan 的行情数据，且自 `01db04f`（2026-10-07 02:56 UTC）起随每次 Scan 运行。

需要做的**只有一件事：等今日 13:07 UTC 的 Scan 跑完，然后核验 `quant_factor_snapshot.csv` 是否落盘。** 由于 `write_factor_snapshot` 外层 try/except 只 print 不报警，这一步核验不可省略。

### 附带的最小适配建议（不影响即刻可用性）

```
R2  统一 SPY auto_adjust=False                      P3
R3  SPY 补做完整 bar 过滤 / RS 加日期对齐            P3
R4  Regime SPY 提前并加长到 6mo → 增量请求归 0        P3
R5  write_factor_snapshot 失败改为显式可观测          P2  ← 优先级最高
```

> **以上均属未来可选优化，本阶段不实施。**

---

## 附录 A：审计操作清单（合规性自证）

| 操作类别 | 次数 |
|---|---|
| 修改代码文件 | **0** |
| 创建 Quant snapshot | **0** |
| 下载新行情 / 触发任何 yfinance 请求 | **0** |
| Backfill / 历史回填 | **0** |
| 运行 Quant production | **0** |
| 改变 V1 逻辑 | **0** |
| 启用 V2 / Shadow | **0** |
| 新增或修改 workflow | **0** |
| commit | **0** |
| push | **0** |

**使用的命令全部为只读**：`git log / git status / grep / sed -n p（打印） / date / ls`。

**唯一写操作**：生成本报告文件 `/workspace/QUANT_PHASE1_DATA_SOURCE_AUDIT.md`。

---

## 附录 B：仓库最终状态

| 项 | 值 |
|---|---|
| HEAD | `a220233995651a7698ce98e1a9643e71b3a474b3` |
| origin/main | `a220233995651a7698ce98e1a9643e71b3a474b3` |
| HEAD vs origin/main | ✅ 完全一致 |
| 已跟踪文件修改数 | **0** |
| 分支状态 | `## main...origin/main`（无 ahead / behind） |

---

*报告结束 · Quant Phase 1 数据源只读审计 · 2026-10-07 10:13 UTC*
