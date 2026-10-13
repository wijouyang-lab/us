# Technical_Date 滞后问题 · 只读调查报告

> **性质**：纯只读调查，未改任何代码、未重跑 snapshot、未 backfill、未 commit/push
> **调查对象**：首份真实 snapshot（`d030f0fb`，2026-10-07 13:32:03 UTC）
> **调查时间**：2026-10-07 14:08 UTC
> **核心结论**：**有明确设计意图，但实现结果未达该契约 → 属数据新鲜度缺陷（defect），不是刻意设计**

---

## 1. Executive Summary

| 项 | 值 |
|---|---|
| Snapshot `Technical_Date` | **2026-10-05**（262/262 行，全池一致） |
| Snapshot `Scan_Date` | 2026-10-07 |
| Price history 最新日期 | **2026-10-06**（261/262 ticker 有） |
| Snapshot `Price` 对应哪天收盘 | **2026-10-05**（262/262 全部吻合） |
| 文档声明的语义 | 「最后完整常规交易日」 |
| 理论最后完整常规交易日 | **2026-10-06**（周三 09:07 EDT 回看，周二收盘） |
| **判定** | **实际值比文档契约滞后 1 个交易日 → 缺陷，非设计** |

**最关键的一条证据**：我原本怀疑是时区错位（`_filter_completed_daily_bars` 里的 `tz_localize("UTC").tz_convert(US_TZ)` 会把 naive 00:00 的 bar 挪到前一日 20:00 EDT）。但**价格比对证伪了这个假设** —— snapshot 的 `Price` 匹配的是 price history 的 **10-05** 收盘，不是 10-06。也就是说 Scan 拿到的 K 线数据**真的就到 10-05 为止**，不是"拿到 10-06 却标错日期"。

---

## 2. Technical_Date 赋值位置（文件 + 行号）

### 2.1 赋值点

**`scan.py:1012`**

```python
"Technical_Date": pd.Timestamp(df.index[-1]).strftime("%Y-%m-%d"),
```

即在 `build_stock_pool()` 构造 pool item 时，取 `df.index[-1]` —— **K 线 DataFrame 最后一根 bar 的日期**。

### 2.2 `df` 的完整变换链（决定 index[-1] 到底是哪根）

`scan.py:880-1012`：

| 行 | 操作 | 说明 |
|---|---|---|
| 882 | `df = get_kline_data(ticker)` | 下载 + 未完成 bar 过滤 |
| 883 | `if len(df) < 40: continue` | 样本下限 |
| 887 | `calculate_extended_quant_factors(df, spy_close)` | **在 dropna 之前**用完整 Close/Volume |
| 889-899 | 追加 `MACDh / RSI / MA20 / MA50 / ATR` 五列 | — |
| **900** | **`df = df.dropna()`** | **删掉任一列为 NaN 的行** |
| 901 | `if len(df) < 10: continue` | — |
| **1012** | `Technical_Date = df.index[-1]` | **取 dropna 之后的最后一根** |

> **结论**：`Technical_Date` = 「下载并过滤后、再经 `dropna()` 的 K 线最后一根 bar 的日期」。
> 它**不是** `max(date)`、不是「倒数第 N 天」、不是硬编码偏移 —— 它就是"数据里最后一根"。
> 因此 **Technical_Date 完全由数据源的末端决定**：源给到哪天，它就是哪天。

### 2.3 数据源与过滤

**`scan.py:760-773` `get_kline_data()`**

```python
df = yf.download(ticker, period="6mo", progress=False,
                 auto_adjust=False, threads=False)      # 763  单只股票，range 形态
if isinstance(df.columns, pd.MultiIndex): ...            # 765-766
df = _filter_completed_daily_bars(df, get_scan_asof_us()) # 768  剔除未完成 bar
```

**`scan.py:741-757` `_filter_completed_daily_bars()`**

```python
cutoff = _last_completed_regular_date_us(asof)
out.index = idx_us
return out.loc[out.index.date <= cutoff].copy()          # 757
```

**`scan.py:733-738` `_last_completed_regular_date_us()`**

```python
"""返回本次 Scan 可以使用的最后完整美股常规交易日日期。"""
now = asof or get_scan_asof_us()
if now.time() < datetime.time(16, 0):
    return now.date() - datetime.timedelta(days=1)       # 09:07 EDT → 10-07 - 1天 = 10-06
return now.date()
```

**关键推论**：cutoff 计算本身**是对的** —— 周三 09:07 EDT 回看得 **2026-10-06**，`<= cutoff` 会**保留 10-06 的 bar**。所以**过滤逻辑没有把 10-06 砍掉**；是**数据源里根本没有 10-06 这根 bar**。

---

## 3. 数据源对比（snapshot vs price history）

| 维度 | Snapshot（Phase 1） | Price History（Phase 2B） |
|---|---|---|
| 生成脚本 | `scan.py` → `get_kline_data()` | `quant_factor_price.py` → `fetch_batch_prices()` |
| workflow 步骤 | `scan.yml:49`（先） | `scan.yml:54`（**后**） |
| yfinance 调用 | `yf.download(ticker, period="6mo", auto_adjust=False, threads=False)` — **单只、range 形态** | `yf.download(tickers, start=start, end=end, auto_adjust=False, threads=True, group_by="ticker")` — **批量、start/end 形态** |
| 请求次数 | 每只 1 次（~300 次串行） | **1 次批量** |
| 未完成 bar 过滤 | `_filter_completed_daily_bars`（cutoff=10-06） | `filter_completed_daily_bars`（cutoff 同口径） |
| 日期处理 | `tz_localize("UTC").tz_convert(US_TZ)` | `tz_localize(None)` + `.normalize()`（保留原始 naive 日期） |
| **实得末端** | **2026-10-05** | **2026-10-06** |

**两者差异集中在两点**：① 调用形态（单只 `period=` vs 批量 `start/end`）；② 执行时刻（先 vs 后）。

### 3.1 决定性价格比对（证伪"时区错位"假设）

对 262 行逐行比对 snapshot `Price` 与 price history 各日收盘：

```
可比对行数: 262
  匹配 2026-10-05 收盘:  262 行   (例: AAPL snapshot=333.63, history=333.630005)
  匹配 2026-10-06 收盘:    0 行
```

**→ snapshot 用的确实是 10-05 的收盘价，数据末端就是 10-05。时区错位假设被证伪。**

### 3.2 若真是时区错位会怎样（供对照）

`_filter_completed_daily_bars` 对 naive index 做 `tz_localize("UTC").tz_convert(US_TZ)`：
naive `10-06 00:00` → UTC → EDT（UTC-4）→ `10-05 20:00` → `.date()` = **10-05**。

若如此，则 Technical_Date=10-05 但 Price 应为 **10-06 收盘**。实测 Price=10-05 收盘 → **不是时区错位**。
（也说明 yfinance 日线 index 大概率是 tz-aware，`tz_convert` 为空操作，日期未被挪动。）

---

## 4. 全池一致性统计

```
行数: 262
Technical_Date 分布: {'2026-10-05': 262}   ← 全部一致，无例外
Scan_Date 分布:      {'2026-10-07': 262}
```

- **262 行 Technical_Date 全部 = 2026-10-05**，没有任何一行是 10-06
- **不存在"部分行更新、部分行滞后"的混合状态**

**这个"全池统一"很重要**：说明不是某些股票数据缺失，而是**整批下载的数据末端统一停在 10-05** —— 指向**数据源/调用形态的系统性差异**，而非个别标的的偶然缺口。

> 附带发现：`TJX` 是 262 个 ticker 中唯一在 price history 里也没有 10-06 的（末端 10-05）。这是**个别标的的数据缺口**，与本次问题无关，但说明 price history 本身也存在零星缺口（后续需关注 `forward_return_nd` 返回 None 的比例）。

---

## 5. 对 Phase 2 forward return 的实际影响

### 5.1 Phase 2 如何取值

`quant_factor_backtest.py:80-107`：

```python
def forward_return_nd(price_series, technical_date, close_t, n):
    ts = pd.Timestamp(technical_date).normalize()          # 10-05
    pos = price_series.index.searchsorted(ts, side="right")  # 100  → 10-05 之后第一根
    target = pos + n - 1                                     # 101  T 之后第 n 个交易日
    future_close = _to_float(price_series.iloc[target])
    return round((future_close / close_t - 1.0), 6)          # 107
```

- `technical_date` ← snapshot 的 `Technical_Date`（**10-05**）
- `close_t` ← snapshot 的 `Price`（**10-05 收盘**）

### 5.2 是否错位？—— **没有错位**

**关键校验**：`close_t`（snapshot 的 10-05 收盘）与 `price_series` 里 10-05 的收盘**是否为同一值**？

第 3.1 节已验证：**262/262 完全吻合**。因此：

- `searchsorted(10-05, side="right")` 精确落在 10-06（第一根之后）
- 分母 `close_t` 与该序列的 10-05 值一致
- **Phase 2 内部自洽，不存在 snapshot 与 price history 的错位**

### 5.3 真正的影响：**锚点整体前移 1 个交易日**

| | 理想（T=10-06） | 实际（T=10-05） |
|---|---|---|
| 前瞻收益起算 | 从 **10-06 收盘** 起 | 从 **10-05 收盘** 起 |
| T+5 | 10-06 后第 5 个交易日 | 10-05 后第 5 个交易日 |
| 与 Scan_Date 的间距 | 1 个交易日 | **2 个交易日** |

- **不是正确性错误**：无未来数据、无错位、无 NaN 污染
- **是系统性的 1 个交易日新鲜度损失**：整条研究链的时序锚点都早 1 天
- 由于当前只有单日 snapshot，**Phase 3 / Phase 5 的内部一致性未受影响**（所有行共享同一个 T）
- **潜在风险**：若后续某些 scan 滞后、某些不滞后，snapshot 日期序列会出现不规则间隔，可能影响 Phase 5 的 `split_windows()` 开窗（它按 unique Technical_Date 切 train/OOS）

---

## 6. 设计意图判定：**有说明，但实现未满足**

### 6.1 文档原文（`quant_factor_price.py:10-16`）

> **【T 日价格口径（与 Phase 1 严格一致，勿擅自更改）】**
> - Phase 1 因子计算使用 `get_kline_data()`，其 yfinance 参数为 `auto_adjust=False`（未复权），
>   并经 `_filter_completed_daily_bars()` 剔除未完成 bar，因此 **close[-1] 一定是
>   "最后完整常规交易日"的未复权收盘价**。
> - Snapshot 行的 `Technical_Date` = **该最后完整交易日**；`Price` = 该日 Close。
> - 本模块的 Price History 同样使用 `auto_adjust=False` + 完整交易日过滤，
>   保证 `Close[T]` 与 Snapshot 的 `Price` **同源同口径**。

### 6.2 其它相关注释

- `scan.py:734` docstring：`"""返回本次 Scan 可以使用的最后完整美股常规交易日日期。"""`
- `scan.py:767` 注释：`# Yahoo 在 09:30-16:00 ET 可能返回当天的未收盘日线；技术指标禁止使用它。`
- `quant_factor_backtest.py:28`：`T = Technical_Date（snapshot 行中的"最后完整交易日"）`

### 6.3 判定结论

| 检查 | 结果 |
|---|---|
| 是否存在语义说明 | ✅ **有**，且相当明确（三处一致表述） |
| 说明的语义 | `Technical_Date` = **最后完整常规交易日** |
| 实际值 | 2026-10-05 |
| 理论值（周三 09:07 EDT 回看） | **2026-10-06** |
| **一致性** | ❌ **不一致 —— 实现未满足自己声明的契约** |

> **所以这不是"未定义语义"，而是"语义已定义但实现未达标"。**
> 文档里那句断言 **close[-1] "一定是"最后完整常规交易日的收盘价**，在当前这次运行中**不成立**。

### 6.4 根因假设（未能 100% 实证，需一次针对性验证）

**主假设（最可能）**：`get_kline_data()` 用**单只 `period="6mo"`**（Yahoo range 形态端点），而 `fetch_batch_prices()` 用**批量 `start/end`**（period 形态端点）。两者在 Yahoo 侧的数据新鲜度不同 —— range 形态端点可能比 period 形态晚约 1 个交易日更新。两者执行时刻也不同（前者先、后者后约 20-25 分钟），无法仅凭本次数据区分是"端点差异"还是"当时恰好未更新"。

**已排除的假设**：
- ❌ 时区错位（`tz_localize("UTC").tz_convert(US_TZ)`）→ 被价格比对方证伪
- ❌ cutoff 算错 → cutoff 确为 10-06，`<=` 过滤不会砍掉 10-06
- ❌ `dropna()` 删掉了 10-06 → 若如此 Price 仍应是 10-06 值（不成立）；且 262 行全一致不像个别 NaN
- ❌ 全市场 10-06 无数据 → price history 里 261/262 个 ticker 有 10-06

**如何一次验证（本次未做，因涉及行情请求）**：

```python
# 在同一时刻、同一只票上对比两种调用形态的末端日期
a = yf.download("AAPL", period="6mo", auto_adjust=False)              # range 形态
b = yf.download("AAPL", start="2026-04-07", end="2026-10-08",
                auto_adjust=False)                                     # start/end 形态
print(a.index[-1], b.index[-1])
```

若 `a` 末端比 `b` 早 1 天 → **主假设成立，属系统性**，每次 scan 都会滞后 1 天。
若两者相同 → 本次属**偶发的数据更新时点问题**，下次 scan 可能自愈。

**次优验证（零行情请求）**：直接观察**下一个交易日的 Scan**。若下一次 `Technical_Date` 仍比理论值早 1 天 → 系统性；若对齐 → 偶发。

---

## 7. 三种修复方案代价对比（**不实施，仅供决策**）

### 方案 A：不改代码，仅补充语义说明 + 观测告警

| 项 | 内容 |
|---|---|
| 改动 | 在 `quant_factor_lab.py` / 文档里把 `Technical_Date` 语义改写为「snapshot 数据末端 bar 的日期（**可能**比理论最后完整交易日滞后）」；在 `write_factor_snapshot` 前加一条校验日志，当 `Technical_Date != 理论值` 时打印 warning |
| 代码风险 | **0**（不改任何业务逻辑，不改数据源） |
| 是否需重跑 snapshot | 否 |
| 对 V1 生产的影响 | **0** |
| 代价 | 语义承认滞后；下游必须接受"T 可能比理想早 1 天" |
| 遗留 | 若属系统性，则研究链永久早 1 天；Phase 5 日期序列可能不规则 |

### 方案 B：让 `get_kline_data()` 改用 `start/end`（对齐 Phase 2B 调用形态）

| 项 | 内容 |
|---|---|
| 改动 | `scan.py:763` 一行：`period="6mo"` → 显式 `start=(today - 200天)`, `end=today+1天` |
| 代码风险 | **中**：这是 **Scan 生产代码**，且会改变技术指标输入的数据末端（MA20/MA50/RSI/MACD/ATR 全部随之改变）→ 可能影响 `Technical_Score_25`、技术确认数、Gate 结果，即 **V1 生产行为** |
| 是否需重跑 snapshot | 否（历史不可回填）；只影响后续 scan |
| 对 V1 生产的影响 | ⚠️ **有** —— 需完整回归（对比新旧 Technical_Score / Gate 分布） |
| 收益 | T 真正等于最后完整交易日，兑现文档契约 |
| 代价 | 需一次带回归验证的生产改动，**与"不动 Scan"原则冲突，需你单独批准** |

### 方案 C：保持数据源，改为"取理论最后完整交易日并校验数据是否具备"

| 项 | 内容 |
|---|---|
| 改动 | 在 `build_stock_pool` 里计算理论 `expected_date`；若 `df.index[-1] < expected_date`，则**丢弃该标的或标记为 STALE**（而不是静默用旧数据） |
| 代码风险 | **中高**：会让当天"数据陈旧"的标的**直接不进入候选池** → 可能大幅减少池子规模甚至清空（若全批次陈旧则 262→0），**直接改变 V1 生产行为** |
| 是否需重跑 | 否 |
| 收益 | 保证不会基于陈旧数据做技术面判断 |
| 代价 | 风险过高；若 Yahoo 常态滞后 1 天，会导致 Scan 长期空池。**不建议** |

### 代价对比表

| | 代码风险 | 触及 Scan 生产 | 需重跑 snapshot | 兑现文档契约 | 推荐度 |
|---|---|---|---|---|---|
| **A 语义+告警** | **0** | 否 | 否 | 否（承认现状） | ⭐⭐⭐ **先做** |
| **B 改调用形态** | 中 | **是** | 否 | **是** | ⭐⭐ 若确认系统性再议 |
| **C 严格校验丢弃** | 高 | **是** | 否 | 是 | ⭐ 不建议 |

---

## 8. 建议

1. **先做方案 A（零风险）**：把 `Technical_Date` 语义写实，并加一条"是否等于理论最后完整交易日"的告警日志。**这能立刻把"静默滞后"变成"可见可观测"。**

2. **不要重跑今天的 snapshot。** 理由：
   - 若根因是系统性（端点差异），重跑结果**完全一样**，白白冒险
   - 重跑会二次写入 pending CSV / AI snapshot / trade_history，**有污染生产推荐与事件账本的真实风险**
   - 设计文档明确禁止"根据价格历史反向生成/回填历史 Factor Snapshot"
   - 当前 262 行**内部完全自洽**（T 与 Price 同源、与 price history 吻合），作为 T=10-05 的研究样本**是有效的**

3. **用下一个交易日的 Scan 做判别**（零成本）：
   - 若下次 `Technical_Date` 对齐理论值 → 本次偶发，方案 A 即可收尾
   - 若仍早 1 天 → 系统性，届时再评估方案 B，且必须走"单独批准 + 完整回归"流程

4. **STEP 4–8 可以启动，但需带一条时序约束**：
   - 测试数据里**显式构造"`Technical_Date` 与 price history 末端相差 1 天"的场景**，验证 Phase 2 的 `forward_return_nd` 在此情形下仍正确（当前代码应能通过，因为它只依赖 snapshot 的 T 与 close_t）
   - 加一条断言：`close_t == price_series[T]`（同源校验），防止未来两者漂移时静默出错

---

## 9. 一句话结论

> **有明确设计意图（Technical_Date = 最后完整常规交易日），但首份真实数据给出的是 10-05 而非 10-06 —— 实现未兑现自己的契约。已证伪时区错位；最可能是 `period="6mo"` 单只下载与批量 `start/end` 下载的数据新鲜度差异。不影响正确性（无 look-ahead、无错位），但使整条研究链锚点早 1 个交易日。建议先做零风险的语义写实 + 告警，观察下次 Scan 判别是否系统性，暂不重跑、暂不改 Scan。**

---

*Technical_Date 只读调查报告 · 未修改任何代码 · 未重跑 snapshot · commit 0 · push 0*
