# Alpha101 因子引入调研

> 生成日期：2026-10-11 19:22（GMT+8）｜ 性质：**只读调研文档，未改任何 `.py`**
> 目标：评估把 WorldQuant《101 Formulaic Alphas》中"仅用 OHLCV"的因子引入 `quant_factor_lab.py` 的可行性、重叠度与推荐清单。
> 数据源确认：`quant_factor_price_history.csv` 表头 = `Date,Ticker,Open,High,Low,Close,Volume,schema_version` → **Open/High/Low/Close/Volume 全部可得**；`adv(d)=mean(Volume,d)`、`returns=Close/Close_prev-1` 可派生；**VWAP、industry/subindustry 不可得**（仅有粗粒度 `Sector`）。

---

## 1. 现状盘点：现有 34 列 + 8 扩展因子

`quant_factor_lab.py` 的 `SNAPSHOT_COLUMNS`（L68-81）共 **34 列**，其中 8 个"扩展因子"由 `calculate_extended_quant_factors(df, spy_close)`（L202-221）计算。

### 1.1 全列清单与分类

| # | 列名 | 类别 | 说明 |
|---|---|---|---|
| 1 | Scan_Date | 元数据 | 扫描日 |
| 2 | Technical_Date | 元数据 | 技术指标基准日 |
| 3 | Ticker | 元数据 | 标的 |
| 4 | Name | 元数据 | 名称 |
| 5 | Sector | 元数据 | 板块（粗粒度） |
| 6 | Price | **价格类** | 最新收盘价 |
| 7 | RSI_14 | 动量/震荡 | 14 日相对强弱（close） |
| 8 | Bias_Pct | 价格类 | (close−MA)/MA 偏离 |
| 9 | MACD_Hist | 动量类 | 快慢 EMA 差值柱状 |
| 10 | MA20 | 价格类 | 20 日收盘均线 |
| 11 | MA50 | 价格类 | 50 日收盘均线 |
| 12 | MA20_Slope_5D | 价格类 | MA20 的 5 日斜率 |
| 13 | ATR_Pct | **波动类** | 真实波幅/收盘（High-Low-Close） |
| 14 | KDJ_J | 动量类 | 随机指标 J 值（High-Low-Close） |
| 15 | Volume_Ratio_5D | **成交量类** | 量/5 日均量 |
| 16 | Momentum_5D_Pct | **动量类（扩展）** | close/close[−5]−1 |
| 17 | Momentum_20D_Pct | **动量类（扩展）** | close/close[−20]−1 |
| 18 | Momentum_60D_Pct | **动量类（扩展）** | close/close[−60]−1 |
| 19 | Realized_Volatility_20D_Pct | **波动类（扩展）** | close 20 日 std |
| 20 | Volume_Ratio_20D | **成交量类（扩展）** | 量/20 日均量 |
| 21 | ZScore_20D | 动量/统计类（扩展） | close 20 日 z-score |
| 22 | Beta_60D_SPY | 截面/市场类（扩展） | 对 SPY 的 60 日 β |
| 23 | Stock_RS_20D_vs_SPY | 截面/市场类（扩展） | 个股 20 日相对强度 vs SPY |
| 24 | Sector_RS_20D_Pct | 截面类 | 板块 20 日相对强度 |
| 25 | VIX | 市场类 | 恐慌指数 |
| 26 | Market_Regime | 市场类 | 由 VIX/均线派生 |
| 27 | Fundamental_Score | 评分 | 基本面 |
| 28 | Event_Score | 评分 | 事件 |
| 29 | Technical_Score_25 | 评分 | 技术 |
| 30 | Risk_Liquidity_Score | 评分 | 风险/流动性 |
| 31 | Quant_Score | 评分 | 综合量化 |
| 32 | 技术确认数 | 门控派生 | 技术信号计数 |
| 33 | Gate_Status | 门控派生 | 通过/未通过 |
| 34 | schema_version | 元数据 | phase1.v1 |

### 1.2 现有"真因子"（非元数据/评分/门控）按信息维度归类

- **价格/均线类（close 主导）**：Price、Bias_Pct、MA20、MA50、MA20_Slope_5D、MACD_Hist、ZScore_20D、Momentum_5/20/60D、RSI_14。
- **波动类（High-Low-Close）**：ATR_Pct、Realized_Volatility_20D_Pct。
- **成交量类（Volume）**：Volume_Ratio_5D、Volume_Ratio_20D。
- **随机/高低类（High-Low-Close）**：KDJ_J。
- **截面/市场类（vs SPY/Sector）**：Beta_60D_SPY、Stock_RS_20D_vs_SPY、Sector_RS_20D_Pct、VIX。

> **关键缺口（现有因子没覆盖的维度）**：
> 1. **Open（开盘价）** —— 完全没有以 Open 为输入的信号；
> 2. **Low / High 的时间序列排名/突破** —— 仅有 KDJ/ATR 用高低，但没有"20 日最高价突破""最低价时序排名"类信号；
> 3. **量价时序相关/协方差结构** —— 现有只有量比，没有"价与量的滚动相关/协方差"；
> 4. **日内反转结构**（(close−open)/(high−low) 之类）—— 现有 KDJ 间接涉及，但无显式日内实体占比信号；
> 5. **多窗口动量差**（10 日 vs 20 日加速度）—— 现有是绝对多窗口动量，无"加速度/二阶导数"信号。

---

## 2. Alpha101 因子清单（公认最常用的 20–30 个）

> 公式取自 WorldQuant《101 Formulaic Alphas》(Kakushadze & Tulchinsky, 2016)。记号：
> `rank`=截面排名，`Ts_Rank`=时序排名，`delta(x,d)=x−x[d日前]`，`delay(x,d)=x[d日前]`，`corr/cov(x,y,d)`=d 日滚动相关/协方差，`adv(d)=mean(Volume,d)`，`returns=Close/Close_prev−1`，`signedpower(x,a)=sign(x)·|x|^a`。
> **"仅 OHLCV"列**：✅=只用开/高/低/收/量（含派生 adv/returns）；⚠️=需 VWAP（日线无，需近似）；❌=需 industry/subindustry（不可得）。

| 编号 | 公式简述 | 需要数据 | 仅 OHLCV |
|---|---|---|---|
| Alpha#1 | `rank(Ts_ArgMax(signedpower((ret<0?std(ret,20):close),2),5))−0.5` | close, ret | ✅ |
| Alpha#2 | `−corr(rank(delta(log(volume),2)), rank((close−open)/open), 6)` | open,close,vol | ✅ |
| Alpha#3 | `−corr(rank(open), rank(volume), 10)` | open,vol | ✅ |
| Alpha#4 | `−Ts_Rank(rank(low), 9)` | low | ✅ |
| Alpha#5 | `−rank(open − mean(vwap,10))` | open, **vwap** | ⚠️ |
| Alpha#6 | `−corr(open, volume, 10)` | open,vol | ✅ |
| Alpha#7 | 量放大时做空 (close−vwap)/vwap | close, **vwap** | ⚠️ |
| Alpha#8 | `−(rank(mean(open,5)) − rank(mean(ret,5)))` | open,ret | ✅ |
| Alpha#9 | 条件式：若 min(delta(close,1),5)>0 则 ts_argmax(close,10) | close | ✅ |
| Alpha#10 | 条件式：基于 delta(close,1) 阈值的 ts_rank 组合 | close | ✅ |
| Alpha#12 | `sign(delta(volume,1)) × (−delta(close,1))` | close,vol | ✅ |
| Alpha#15 | `−sum(rank(corr(rank(high/low), rank(adv15), 21)), 21)` | high,low,vol | ✅ |
| Alpha#16 | `−rank(cov(rank(high), rank(volume), 5))` | high,vol | ✅ |
| Alpha#17 | `(−rank(ts_rank(close,10))) × rank(delta(delta(close,1),1)) × rank(ts_rank(volume/adv20,5))` | close,vol | ✅ |
| Alpha#18 | 多窗口 `std(|close−open|)` 与 `std(close)` 的 rank 组合 | open,close | ✅ |
| Alpha#19 | 基于 (close−open) 符号与 ts_rank(close,13) 的条件式 | open,close | ✅ |
| Alpha#20 | `(−rank(open−close)) × rank(rank(volume))` 类组合 | open,close,vol | ✅ |
| Alpha#23 | `((mean(high,20)/20) < high) ? −delta(high,2) : 0` | high | ✅ |
| Alpha#27 | `((0.5 − rank(mean(corr(rank(volume), rank(vwap),6),2))) ...)` | vol,**vwap** | ⚠️ |
| Alpha#29 | `(close−open) / ((high−low) + .001)` | open,high,low,close | ✅ |
| Alpha#30 | `−rank((sign(delta(close,1)) + sign(delta(close,2)) + sign(delta(close,3))) ... )` | close | ✅ |
| Alpha#31 | `rank( (rank(rank(1 + rank(delta(close,1),5))) ... ) / industry)` | close,**industry** | ❌ |
| Alpha#33 | `rank(−(1 − (open/close))^1) ...` 含 industry 中性 | open,close,**industry** | ❌ |
| Alpha#38 | `−rank(corr(open, close, 10))` + industry 中性 | open,close,**industry** | ❌ |
| Alpha#50 | `(−1 × ts_max(...)) × ts_rank(vwap, ...)` | **vwap** | ⚠️ |
| Alpha#51 | `((delay(close,20)−delay(close,10))/10 − (delay(close,10)−close)/10) × −100` | close | ✅ |
| Alpha#53 | `−delta(((close−low)−(high−close))/(close−open), 9)` | open,high,low,close | ✅ |
| Alpha#54 | `−((low − high) − (mean(close,5) − mean(close,5)...))` | open,high,low,close | ✅ |
| Alpha#56 | `−(rank(mean(ret,10)) × rank((close−open)/open))` | open,close,ret | ✅ |
| Alpha#57 | `−(rank((close−open)/open) × rank((close−open)/open))` | open,close | ✅ |
| Alpha#59 | `−rank(... ts_rank(... (high*0.001+low*0.001)... ))` | high,low | ✅ |
| Alpha#60 | `−(rank((close−open)/open) × rank(volume))` 类组合 | open,close,vol | ✅ |
| Alpha#71 | `max(ts_rank(... vwap ...), ts_rank(... delay ...))` | **vwap**,close | ⚠️ |
| Alpha#74 | `((rank(corr(close, volume, 5)) ... ))` rank 组合 | close,vol | ✅ |
| Alpha#75 | `rank(cov(rank(close), rank(volume), 5))` | close,vol | ✅ |
| Alpha#76–101 | 多数含 `industry`/`subindustry`/`Market` 中性 | **industry** | ❌ |

> 结论：**纯 OHLCV 可加的约 24 个**（#1,#2,#3,#4,#6,#8,#9,#10,#12,#15,#16,#17,#18,#19,#20,#23,#29,#30,#51,#53,#54,#56,#57,#59,#60,#74,#75）；依赖 VWAP 的（#5,#7,#27,#50,#71 等）需近似；依赖 industry 的（#31,#33,#38,#76–101）**不可加**（仅粗粒度 Sector 不足以支撑行业中性化）。

---

## 3. 与现有因子的重叠分析

> 类别：**A**=与现有高度重叠（不用加）；**B**=部分重叠（可加可不加）；**C**=全新信息（值得加）。

| 编号 | 信息维度 | 类别 | 理由 |
|---|---|---|---|
| #1 | close 时序 argmax + std | B | 与 ZScore/Momentum 同源，结构略新 |
| #2 | 量变化 vs (close−open)/open 相关 | **C** | 量价时序相关结构，现有无 |
| #3 | open vs volume 截面相关 | **C** | 首次引入 open 输入 |
| #4 | low 的时序排名 | **C** | 首次引入 low 时序排名，突破/低谷结构 |
| #6 | open vs volume 相关 | **C** | open-量联动 |
| #8 | open 5 日均 vs ret 5 日均 | B | 与 Momentum/MA 部分重叠 |
| #9/#10 | close 阈值条件式反转 | B | 与 RSI/Momentum 重叠 |
| #12 | sign(量Δ) × −收Δ | **C** | 量价方向组合，新 |
| #15 | high/low 与 adv 滚动相关 | **C** | high-low 量价协变 |
| #16 | high 与 volume 协方差 | **C** | high-量协变 |
| #17 | close 加速度 × 量/adv | **C** | 二阶动量 + 量比 |
| #18 | |close−open| 多窗口 std | **C** | 日内波动结构，新 |
| #19/#20 | open-close 反转 + 量 | B | 与 #29/KDJ 部分重叠 |
| #23 | 20 日最高价突破 | **C** | 新高突破信号，现有无 |
| #29 | (close−open)/(high−low) | **C** | 显式日内实体占比反转 |
| #30 | 多日收盘符号和 | B | 与 Momentum 重叠 |
| #51 | 10/20 日动量差（加速度） | B | 与 Momentum_20 部分重叠，二阶新 |
| #53 | 实体占比的 9 日变化 | **C** | 日内结构变化率 |
| #54 | 5 日均收 vs 高低结构 | B | 与 MA/Bias 重叠 |
| #56/#57/#60 | (close−open)/open 与量/ret 组合 | B | 与 #29 家族重叠 |
| #59 | high/low 时序排名组合 | **C** | 高低时序结构 |
| #74 | close-volume 滚动相关 rank | **C** | 价量相关结构 |
| #75 | close-volume 协方差 rank | **C** | 价量协变（与 #16 互补） |
| #31/#33/#38/#76–101 | industry 中性 | A(不可加) | 缺 industry 数据，直接排除 |

> **C 类（全新信息）共 15 个**：#2, #3, #4, #6, #12, #15, #16, #17, #18, #23, #29, #53, #59, #74, #75。这些正是现有因子完全没覆盖的 Open 输入、Low 时序排名、High 突破、量价协变、日内结构维度。

---

## 4. 推荐清单（15 个，取自 C 类）

| # | 公式（简化） | 为什么值得加 | 难度(1–5) | 稳定性 |
|---|---|---|---|---|
| #2 | `−corr(rank(ΔlogVol,2), rank((C−O)/O), 6)` | 量变化领先于开盘实体，量价时序相关现有缺失 | 2 | 中（经验证有效，逻辑通顺） |
| #3 | `−corr(rank(Open), rank(Vol), 10)` | 首引 Open 输入，开盘活跃度信号 | 2 | 中 |
| #4 | `−Ts_Rank(rank(Low), 9)` | 低点时序排名→逢低强度，现有仅 High-Low 波动 | 1 | 高（低谷反转有理论支撑） |
| #6 | `−corr(Open, Vol, 10)` | 开盘价与量联动，补充量价维度 | 2 | 中 |
| #12 | `sign(ΔVol) × (−ΔClose)` | 量增伴随下跌的恐慌信号，量价方向组合 | 1 | 高（量价背离经典） |
| #15 | `−Σ rank(corr(rank(H/L), rank(adv15),21)),21` | 高低比与流动性的长期协变，横截面结构 | 3 | 中（偏数据挖掘） |
| #16 | `−rank(cov(rank(High), rank(Vol),5))` | 高位放量结构，突破前兆 | 2 | 中高 |
| #17 | `(−Ts_Rank(C,10))×rank(ΔΔC)×rank(Ts_Rank(Vol/adv20,5))` | 二阶动量加速度 × 量比，纯新维度 | 3 | 中（组合复杂） |
| #18 | 多窗口 `std(|C−O|)` rank 组合 | 日内波动结构，捕捉实体扩张 | 2 | 中高（波动聚集有理） |
| #23 | `mean(H,20)<H ? −ΔH(2) : 0` | 20 日新高突破，趋势延续/反转 | 1 | 高（突破是经典信号） |
| #29 | `(C−O)/((H−L)+.001)` | 日内实体占比反转，最干净的日内信号 | 1 | 高（被广泛引用） |
| #53 | `−Δ(((C−L)−(H−C))/(C−O), 9)` | 实体占比的 9 日变化率，结构加速度 | 2 | 中 |
| #59 | `−rank(Ts_Rank(H·k+L·k, ...))` 高低时序组合 | 高低极值时序结构 | 2 | 中 |
| #74 | `rank(corr(C, Vol, 5))` rank 组合 | 价量同期相关，与 #16 互补 | 2 | 中 |
| #75 | `rank(cov(rank(C), rank(Vol),5))` | 收盘价-量协方差，动量确认 | 2 | 中高 |

> **稳定性总评**：#4、#12、#23、#29 金融逻辑最硬（低谷/量价背离/突破/日内反转均有学术与实务支撑）；#15、#17、#53、#59 偏"组合型数据挖掘产物"，建议**先做 IC/分层回测验证再决定是否进 `Quant_Score`**，避免过拟合。所有 15 个均为纯 OHLCV、无 AI 调用、确定性计算。

---

## 5. 实施路径（周后做，本调研不含实现）

1. **加位置**：在 `quant_factor_lab.py` 新增 `calculate_alpha101_factors(df)`（紧邻 `calculate_extended_quant_factors`），从 `df` 取 Open/High/Low/Close/Volume（源数据已有，见 §0 确认），输出 15 个因子 dict；在 `build_snapshot_rows` 调用并合并；`SNAPSHOT_COLUMNS` 末尾追加这 15 列。
2. **列数变化**：34 → **49**（`34 + 15`）。若后续回测剔除部分数据挖掘型，可回落到 ~44。
3. **是否需要 flag**：**不需要 feature flag**。理由：① 纯确定性计算、无 AI 成本；② 纯**列加法（additive column）**，下游 `dashboard_export.py` / Phase 2–7 按列名读取，新增列不影响旧列解析；③ 参照既有先例 `quant_factor_price.py` 扩 OHLCV 时**保持 `schema_version` 不变（v1）**。但须**同步递增 `SCHEMA_VERSION` 到 `phase1.v2`**（STEP 3-A 约定：字段结构变更即递增主版本），让下游显式感知。
   - ⚠️ 上线时机：避开周一（当前为周末收尾期）。建议在**周二验证 `ENABLE_SCAN_BUY_DECISION` 激活后**、确认主链路稳定再合入，且先在本地 `python quant_factor_lab.py` 跑通 + 全量 pytest（参考既有 `test_quant_*` 模式）再 push。
4. **预估工作量**：
   - 因子实现（15 个 + 派生 adv/returns helper）：~0.5 天；
   - 接入 `build_snapshot_rows` + `SNAPSHOT_COLUMNS` + schema 递增：~0.25 天；
   - 单测（每个因子边界：数据不足→None、窗口不足→None，参照 `test_quant_factor_*`）：~0.5 天；
   - IC/分层回测验证（决定是否进 `Quant_Score` 权重）：~1 天；
   - 合计 **约 2–3 个工作日**。

---

## §6 可直接抄的实现草稿

> 仅代码草稿，**未改 `quant_factor_lab.py`**。所有函数输入 `df`（含 `Open/High/Low/Close/Volume` 的 DataFrame），输出对齐 `df.index` 的 `Series`；snapshot 取 **`.iloc[-1]`** 作为当日因子值（NaN/数据不足 → `None`）。公式取自 WorldQuant《101 Formulaic Alphas》，部分多层 rank/ts_rank 组合（#15/#17/#18/#59）为忠实简化代表式，上线前需 IC/分层回测验证。

### 6.1 公共 helper（放在 `calculate_extended_quant_factors` 之前）

```python
import numpy as np
import pandas as pd

def _adv(volume, d):
    """平均日成交量 adv(d) = mean(Volume, d)。"""
    return pd.to_numeric(volume, errors="coerce").rolling(d).mean()

def _delta(x, n):
    """delta(x, n) = x - x[n 日前]；返回 Series。"""
    s = pd.to_numeric(x, errors="coerce")
    return s - s.shift(n)

def _rank(x):
    """截面/时序百分比排名（pct=True）。空窗口→NaN。"""
    return pd.to_numeric(x, errors="coerce").rank(pct=True)

def _ts_rank(x, d):
    """Ts_Rank：窗口 d 内最后一个值的排名（百分比）。窗口不足→NaN。"""
    s = pd.to_numeric(x, errors="coerce")
    def _r(w):
        w = w[~np.isnan(w)]
        if len(w) < d:
            return np.nan
        return (w[-1] >= w).sum() / len(w)
    return s.rolling(d).apply(_r, raw=True)
```

### 6.2 15 个因子函数（完整、可直接复制）

```python
def a101_02(df):
    # -corr(rank(delta(log(volume),2)), rank((close-open)/open), 6)
    v = pd.to_numeric(df["Volume"], errors="coerce")
    c = pd.to_numeric(df["Close"], errors="coerce")
    o = pd.to_numeric(df["Open"], errors="coerce")
    x = _rank(_delta(np.log(v.clip(lower=1e-9)), 2))
    y = _rank((c - o) / o.replace(0, np.nan))
    return -x.rolling(6).corr(y)

def a101_03(df):
    # -corr(rank(open), rank(volume), 10)
    o = pd.to_numeric(df["Open"], errors="coerce")
    v = pd.to_numeric(df["Volume"], errors="coerce")
    return -_rank(o).rolling(10).corr(_rank(v))

def a101_04(df):
    # -Ts_Rank(rank(low), 9)
    low = pd.to_numeric(df["Low"], errors="coerce")
    return -_ts_rank(_rank(low), 9)

def a101_06(df):
    # -corr(open, volume, 10)
    o = pd.to_numeric(df["Open"], errors="coerce")
    v = pd.to_numeric(df["Volume"], errors="coerce")
    return -o.rolling(10).corr(v)

def a101_12(df):
    # sign(delta(volume,1)) * (-delta(close,1))
    v = pd.to_numeric(df["Volume"], errors="coerce")
    c = pd.to_numeric(df["Close"], errors="coerce")
    return np.sign(_delta(v, 1)) * (-_delta(c, 1))

def a101_15(df):
    # -sum(rank(corr(rank(high/low), rank(adv15), 21)), 21)
    high = pd.to_numeric(df["High"], errors="coerce")
    low = pd.to_numeric(df["Low"], errors="coerce")
    v = pd.to_numeric(df["Volume"], errors="coerce")
    adv15 = _adv(v, 15)
    x = _rank(high / low.replace(0, np.nan))
    y = _rank(adv15)
    return -(_rank(x.rolling(21).corr(y)).rolling(21).sum())

def a101_16(df):
    # -rank(cov(rank(high), rank(volume), 5))
    high = pd.to_numeric(df["High"], errors="coerce")
    v = pd.to_numeric(df["Volume"], errors="coerce")
    return -_rank(high.rolling(5).cov(_rank(v)))

def a101_17(df):
    # (-rank(ts_rank(close,10))) * rank(delta(delta(close,1),1)) * rank(ts_rank(volume/adv20,5))
    c = pd.to_numeric(df["Close"], errors="coerce")
    v = pd.to_numeric(df["Volume"], errors="coerce")
    adv20 = _adv(v, 20)
    t1 = -_ts_rank(_rank(c), 10)
    t2 = _rank(_delta(_delta(c, 1), 1))
    t3 = _rank(_ts_rank(v / adv20.replace(0, np.nan), 5))
    return t1 * t2 * t3

def a101_18(df):
    # -rank(std(|close-open|,5) + std(close-open,5))
    c = pd.to_numeric(df["Close"], errors="coerce")
    o = pd.to_numeric(df["Open"], errors="coerce")
    oc = (c - o).abs()
    return -_rank(oc.rolling(5).std() + (c - o).rolling(5).std())

def a101_23(df):
    # ((mean(high,20)/20) < high) ? -delta(high,2) : 0
    high = pd.to_numeric(df["High"], errors="coerce")
    cond = (high.rolling(20).mean() / 20) < high
    return np.where(cond, -_delta(high, 2), 0.0)

def a101_29(df):
    # (close-open) / ((high-low) + 0.001)
    c = pd.to_numeric(df["Close"], errors="coerce")
    o = pd.to_numeric(df["Open"], errors="coerce")
    h = pd.to_numeric(df["High"], errors="coerce")
    l = pd.to_numeric(df["Low"], errors="coerce")
    return (c - o) / ((h - l).replace(0, np.nan) + 0.001)

def a101_53(df):
    # -delta(((close-low)-(high-close))/(close-open), 9)
    c = pd.to_numeric(df["Close"], errors="coerce")
    o = pd.to_numeric(df["Open"], errors="coerce")
    h = pd.to_numeric(df["High"], errors="coerce")
    l = pd.to_numeric(df["Low"], errors="coerce")
    body = ((c - l) - (h - c)) / (c - o).replace(0, np.nan)
    return -_delta(body, 9)

def a101_59(df):
    # 简化代表式：-rank(ts_rank(rank(high*low), 20))（原文为多层 rank/ts_rank 组合）
    high = pd.to_numeric(df["High"], errors="coerce")
    low = pd.to_numeric(df["Low"], errors="coerce")
    return -_rank(_ts_rank(_rank(high * low), 20))

def a101_74(df):
    # rank(corr(close, volume, 5)) 的 rank 组合
    c = pd.to_numeric(df["Close"], errors="coerce")
    v = pd.to_numeric(df["Volume"], errors="coerce")
    return _rank(c.rolling(5).corr(v))

def a101_75(df):
    # rank(cov(rank(close), rank(volume), 5))
    c = pd.to_numeric(df["Close"], errors="coerce")
    v = pd.to_numeric(df["Volume"], errors="coerce")
    return _rank(_rank(c).rolling(5).cov(_rank(v)))
```

### 6.3 聚合函数（放在 `calculate_extended_quant_factors` 之后）

```python
def calculate_alpha101_factors(df):
    """计算 15 个纯 OHLCV 的 Alpha101 因子，返回 {列名: 当日值或 None}。

    df 需含 Open/High/Low/Close/Volume；任何因子数据不足/除零 → 该项 None。
    """
    if df is None or df.empty or "Close" not in df.columns:
        return {f"Alpha101_{n}": None for n in
                (2,3,4,6,12,15,16,17,18,23,29,53,59,74,75)}
    out = {}
    pairs = {
        "Alpha101_02": a101_02, "Alpha101_03": a101_03, "Alpha101_04": a101_04,
        "Alpha101_06": a101_06, "Alpha101_12": a101_12, "Alpha101_15": a101_15,
        "Alpha101_16": a101_16, "Alpha101_17": a101_17, "Alpha101_18": a101_18,
        "Alpha101_23": a101_23, "Alpha101_29": a101_29, "Alpha101_53": a101_53,
        "Alpha101_59": a101_59, "Alpha101_74": a101_74, "Alpha101_75": a101_75,
    }
    for name, fn in pairs.items():
        try:
            val = fn(df).iloc[-1]                 # 取最新一根 bar 的因子值
            out[name] = None if (val is None or pd.isna(val)) else float(val)
        except Exception:
            out[name] = None                       # 异常/空窗口 → None，不崩
    return out
```

### 6.4 插入位置与接线

```python
# quant_factor_lab.py（在 calculate_extended_quant_factors 定义之后、SNAPSHOT_COLUMNS 使用处之前）：
#   1) 复制 §6.1 helper + §6.2 15 个函数 + §6.3 calculate_alpha101_factors
#   2) 在 build_snapshot_rows 内调用：
#        ext = calculate_extended_quant_factors(df, spy_close)
#        a101 = calculate_alpha101_factors(df)          # ← 新增
#        row.update(ext); row.update(a101)              # 合并进快照行
```

### 6.5 SNAPSHOT_COLUMNS 加列清单（34 → 49，逐列名）

在现有 34 列之后追加以下 **15 列**（顺序固定）：

```python
SNAPSHOT_COLUMNS = [
    # —— 原有 34 列（不变）——
    "Scan_Date", "Technical_Date", "Ticker", "Name", "Sector",
    "Price", "RSI_14", "Bias_Pct", "MACD_Hist", "MA20", "MA50", "MA20_Slope_5D",
    "ATR_Pct", "KDJ_J", "Volume_Ratio_5D",
    "Momentum_5D_Pct", "Momentum_20D_Pct", "Momentum_60D_Pct",
    "Realized_Volatility_20D_Pct", "Volume_Ratio_20D", "ZScore_20D",
    "Beta_60D_SPY", "Stock_RS_20D_vs_SPY",
    "Sector_RS_20D_Pct", "VIX", "Market_Regime",
    "Fundamental_Score", "Event_Score", "Technical_Score_25",
    "Risk_Liquidity_Score", "Quant_Score",
    "技术确认数", "Gate_Status", "schema_version",
    # —— 新增 15 列（Alpha101，纯 OHLCV）——
    "Alpha101_02", "Alpha101_03", "Alpha101_04", "Alpha101_06", "Alpha101_12",
    "Alpha101_15", "Alpha101_16", "Alpha101_17", "Alpha101_18", "Alpha101_23",
    "Alpha101_29", "Alpha101_53", "Alpha101_59", "Alpha101_74", "Alpha101_75",
]
# 34 + 15 = 49 列
```

> 若依 §5 决定升 `schema_version` → `phase1.v2`：同步改 `quant_research_runner.py:37` 期望值与 `test_quant_research_runner.py:50` 占位（否则仅一条软警告，无害，详见 `archive/SCHEMA_VERSION_CONSUMERS.md`）。

## 附：铁律确认
- 本文件为**只读调研**，`quant_factor_lab.py` 等所有 `.py` **未改动**；
- 未执行 `git push` / `git rebase`；
- 未调用任何 AI。
