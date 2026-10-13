# 期权策略风险逻辑 — 只读审计报告

> 阶段：**第一阶段只读审计，未修改任何文件、未 commit、未 push**。
> 审计对象：期权策略 Reward/Risk 门槛缺失问题（`ALL · SHORT_PUT` 案例）
> 审计时刻：2026-10-02（GMT+8）

---

## 0. 问题现象确认（数据验证）

用户报告的案例在 `option_strategies.csv` 中**已确认存在**：

| 字段 | 值 |
| --- | --- |
| Ticker | ALL |
| Strategy | SHORT_PUT |
| Strike | 210.0 |
| PremiumCollected | 3.7 |
| Quantity | 1 |
| MaxProfit | 370.0 |
| MaxLoss | **20630.0** |
| BreakEven | 206.3 |
| **RewardRisk 字段** | **空**（未计算） |
| **Status** | **Active** ❌ |

**理论盈亏比**：`370 / 20630 = 0.0179:1`（≈ 0.018:1，与用户计算一致）

> Max Loss 计算本身是正确的：`(210 - 3.7) × 100 = 20630`。**问题不在 Max Loss 数值，而在于没有任何 R/R 门槛阻止它成为 Active 推荐。**

### 全表现状（10 条记录）

| Ticker | Strategy | MaxProfit | MaxLoss | 理论 R/R | RewardRisk 字段 | Status |
| --- | --- | --- | --- | --- | --- | --- |
| ALL | SHORT_PUT | 370.00 | 20630.00 | **0.0179** | 空 | Active ❌ |
| ALL | SHORT_PUT | 380.00 | 20620.00 | **0.0184** | 空 | Active ❌ |
| CBOE | SHORT_PUT | 570.00 | 23430.00 | **0.0243** | 空 | Active ❌ |
| NTAP | SHORT_PUT | 650.00 | 18350.00 | **0.0354** | 空 | Active ❌ |
| TER | SHORT_PUT | 2170.00 | 33830.00 | **0.0641** | 空 | Active ❌ |
| FTNT | CALL_DEBIT_SPREAD | 548.00 | 452.00 | **1.212** | 空 | Active ❌ |
| PAYX | CALL_DEBIT_SPREAD | 295.00 | 205.00 | **1.439** | 1.439 | Active ❌ |
| APA | CALL_DEBIT_SPREAD | 145.00 | 105.00 | **1.381** | 1.381 | Active ❌ |
| SCHW | CALL_DEBIT_SPREAD | 441.00 | 309.00 | **1.427** | 1.427 | Active ❌ |
| MPC | CALL_DEBIT_SPREAD | 1100.00 | 900.00 | **1.222** | 1.222 | Active ❌ |

**结论：10 条记录全部 Status=Active，且 R/R 全部 < 2.0**（SHORT_PUT 全部 < 0.07，CALL_DEBIT_SPREAD 全部 1.21–1.44）。

---

## 1. 当前期权策略架构

### 文件与职责

| 文件 | 职责 |
| --- | --- |
| `scan_us_option_engine.py`（652 行） | **核心引擎**：期权链读取、策略结构生成、盈亏计算、CSV 写入 |
| `option_strategies.csv` | 策略账本（56 字段，10 行） |
| `scan.py` | 调用引擎生成策略；生成邮件 HTML |
| `review.py` | 读取 Active 期权持仓；到期/价内平仓 |
| `dashboard_export.py` | 读取 CSV → `dashboard_data.json` 的 `options[]` |
| `app.js` | 渲染 `options[]` |

### 当前支持的策略类型（仅 3 种）

| 策略 | 常量/标识 | 当前数据条数 |
| --- | --- | --- |
| 现金担保 Short Put | `SHORT_PUT` | 5 |
| Call Debit Spread | `CALL_DEBIT_SPREAD` | 5 |
| Long Call（兜底） | `LONG_CALL` | 0 |

> ⚠️ **Bull Put Spread 当前不存在**（详见第 7 节）。

### 调用链

```
scan.py: generate_option_recommendations()          [line 3296]
   └─ 仅处理 Tag == "Core_Dragon"                    [line 3300]
       └─ append_option_strategy(item)               [line 3303]
           └─ build_option_recommendation(item)      [engine line 532]
               ├─ _pick_short_put_structure()        [line 311]  → SHORT_PUT
               └─ _pick_call_structure()             [line 372]  → CALL_DEBIT_SPREAD / LONG_CALL
           └─ 写 option_strategies.csv               [line 606]
```

下游消费：

| 消费方 | 位置 | 是否过滤 Status |
| --- | --- | --- |
| scan 邮件 HTML | `scan.py: get_recent_option_recommendations` [line 645] | ✅ 过滤 `Status == "Active"` |
| review 持仓 | `review.py: load_option_positions` [line 918] | ✅ 过滤 `Status == "Active"` |
| **dashboard 导出** | `dashboard_export.py: build_options` [line 1600] | ❌ **不过滤**，status 仅透传 |
| **前端渲染** | `app.js: renderOptions(OPTIONS)` [line 343] | ❌ **不过滤** |

> 这是最小改动方案中**必须处理的关键点**：仅改 Status 不足以阻止 Dashboard 显示。

---

## 2. Max Profit 来源

| 策略 | 代码位置 | 公式 | 是否乘 Qty |
| --- | --- | --- | --- |
| **SHORT_PUT** | `scan_us_option_engine.py` **line 361** | `sell_price * 100.0`（= Premium × 100） | ❌ 未乘（Quantity 恒为 1，line 598 硬编码） |
| **CALL_DEBIT_SPREAD** | **line 421** | `(width - net) * 100.0` | ❌ 未乘 |
| **LONG_CALL** | **line 464** | `None`（不限） | — |

SHORT_PUT 案例校验：`3.7 × 100 = 370` ✅ 与 CSV 一致。

---

## 3. Max Loss 来源

| 策略 | 代码位置 | 公式 | 是否正确 |
| --- | --- | --- | --- |
| **SHORT_PUT** | **line 354**：`max_loss = max(0.0, effective_entry) * 100.0`<br>其中 line 350：`effective_entry = strike - sell_price` | **(Strike − Premium) × 100** | ✅ **正确，符合真实期权数学** |
| **CALL_DEBIT_SPREAD** | **line 420** | `net * 100.0`（净权利金支出） | ✅ 正确 |
| **LONG_CALL** | **line 463** | `long_price * 100` | ✅ 正确 |

SHORT_PUT 案例校验：`(210 − 3.7) × 100 = 20630` ✅ 与 CSV 一致。

> **结论：Max Loss 计算正确，不应修改。** 问题的根源不是数字，而是"没有门槛"。

---

## 4. Break Even 来源

| 策略 | 代码位置 | 公式 |
| --- | --- | --- |
| **SHORT_PUT** | **line 362**：`"break_even": effective_entry` | `Strike − Premium` ✅ |
| **CALL_DEBIT_SPREAD** | **line 422** | `long_strike + net` |
| **LONG_CALL** | **line 451** | `long_strike + long_price` |

SHORT_PUT 案例校验：`210 − 3.7 = 206.3` ✅ 与 CSV 一致。

---

## 5. 当前推荐 / Active 判断（**问题核心**）

### 位置

`scan_us_option_engine.py` **line 598**：

```python
"Status":"Active","Quantity":1,
```

### 判定

> **Status 是无条件硬编码字符串 `"Active"`，没有任何条件判断、没有任何 R/R 检查。**

这是整个问题的**直接根因**：无论策略盈亏比是多少（哪怕是 0.018:1），只要结构被生成，就会被标记为 Active，从而进入邮件推荐、review 持仓和 Dashboard。

**全表 10 条记录 Status 唯一值：`['Active']`，无一条被拒绝。**

---

## 6. Short Put 当前计算链（完整）

```python
# _pick_short_put_structure()  line 311-369

# ① 长期价值门槛（line 314）
ok, reasons = _long_term_value_gate(item)     # Quant≥70, 基本面≥24, EPS>0, 现金流, PE≤45 ...
if not ok: return None, reasons

# ② 财报窗口过滤（line 317）
if 0 <= earnings_days <= 14: return None, [...]

# ③ Strike 筛选（line 319-327）
work = puts[strike < spot]
discount_pct = (1 - strike/spot) * 100
work = work[3.0 <= discount_pct <= 15.0]      # 正股下方 3%~15%

# ④ 流动性（line 327）
liquid = work[(volume + openInterest) > 0]

# ⑤ 逐个候选（line 332-365）
sell_price = bid 或 mid/last                  # line 335-338
iv        = Yahoo chain IV 或 BS 反解          # line 339-344
delta     = _put_delta(...)                   # line 345
if not (0.15 <= |delta| <= 0.35): continue    # line 348
cash_secured     = strike * 100.0             # line 349
effective_entry  = strike - sell_price        # line 350
premium_yield    = sell_price/strike*100      # line 351
if premium_yield < 0.50: continue             # line 352
max_loss   = max(0, effective_entry) * 100.0  # line 354  ← (Strike-Premium)×100
max_profit = sell_price * 100.0               # line 361  ← Premium×100

candidates.append((score, {
    ...
    "max_loss":   max_loss,                   # line 361
    "max_profit": sell_price*100.0,           # line 361
    "break_even": effective_entry,            # line 362
    "reward_risk": None,                      # line 362  ← ❌ 从不计算！
    ...
}))

# ⑥ 选 score 最小的候选返回（line 368-369）
```

### 关键缺口

| 环节 | 现状 |
| --- | --- |
| `reward_risk` | **硬编码 `None`**（line 362），导致 CSV `RewardRisk` 字段为空 |
| R/R 门槛 | **完全不存在**（SHORT_PUT 路径无任何 R/R 检查） |
| Status | 后续在 line 598 无条件设为 `Active` |

---

## 7. Bull Put Spread 当前计算链

> **结论：`Bull Put Spread（牛市看跌价差）在当前代码中完全不存在。**

证据：
- `_pick_short_put_structure()` 只返回单一腿的 `"strategy": "SHORT_PUT"`（line 358），`short_strike` 恒为 `None`（line 358）
- `_pick_call_structure()` 只处理 **Call**（line 372-472），不处理 Put 价差
- 全表 `Strategy` 唯一值：`SHORT_PUT`、`CALL_DEBIT_SPREAD`，无 `BULL_PUT_SPREAD`
- 全表无 `LONG_CALL` 数据（0 条）

因此用户要求的 Bull Put Spread 公式：

```
Max Profit = Net Credit × 100 × Qty
Max Loss   = (Strike Width − Net Credit) × 100 × Qty
```

**属于"新增策略"，当前无对应代码可审计。** 若要支持，需在第二阶段新增 `_pick_bull_put_spread_structure()`。

> 注意：现有的 `CALL_DEBIT_SPREAD` 已具备正确的价差公式结构（line 420-423），可作为新增 Put 价差的模板：
> ```python
> max_loss   = net * 100.0            # 净支出
> max_profit = (width - net) * 100.0  # 宽度 - 净支出
> reward_risk = max_profit / max_loss # line 423 ← 已计算
> ```

---

## 8. 现有 Risk/Reward 逻辑

### 8.1 现有常量

```python
# scan_us_option_engine.py line 28-31
MIN_SPREAD_REWARD_RISK   = 0.40   # 价差质量门槛
MAX_BREAKEVEN_PCT        = 12.0
MAX_DEBIT_PCT_OF_SPOT    = 4.0
```

### 8.2 `MIN_SPREAD_REWARD_RISK = 0.40` 的实际作用范围

**仅用于 `CALL_DEBIT_SPREAD` 的 short strike 选择**（line 429-431）：

```python
if (reward_risk >= MIN_SPREAD_REWARD_RISK          # 0.40
        and breakeven_pct <= MAX_BREAKEVEN_PCT
        and debit_pct <= MAX_DEBIT_PCT_OF_SPOT):
    return {... "strategy": "CALL_DEBIT_SPREAD" ...}
```

| 特性 | 说明 |
| --- | --- |
| 作用对象 | **仅 CALL_DEBIT_SPREAD** |
| 作用时机 | 挑选 short strike 时（结构筛选） |
| 门槛值 | **0.40**（远低于用户要求的 2.0） |
| 失败后果 | 回退到 `LONG_CALL` 兜底（line 450-472），**不是拒绝** |
| SHORT_PUT | **完全不适用**（`reward_risk` 为 None，路径无此检查） |

### 8.3 Planned Risk 是否存在（关键判断）

用户要求：只有存在明确的 technical stop / underlying stop / ATR stop / support stop / option exit price / target price 时，才允许计算 `Trading Reward/Risk`。

审计结果：

| 策略 | StopLoss 字段内容（line 599） | 是否可执行 Planned Risk |
| --- | --- | --- |
| SHORT_PUT | `"现金担保Put无固定技术止损；若长期基本面/接货逻辑失效，应重新评估并主动平仓"` | ❌ **纯文本描述，无数值** |
| 其他 | `"权利金为最大亏损；若正股趋势破坏，Review重新评估"` | ❌ **纯文本描述，无数值** |

代码中**不存在**：
- 任何数值型 technical stop / ATR stop / support stop 字段
- 任何 option exit price（期权止损价）
- 任何 target price（目标价）

> **结论：当前 100% 的策略都不具备可执行的 Planned Risk。**
> 因此按用户规则，必须全部使用 **Theoretical R/R = MaxProfit / MaxLoss** 判定，且当前全部 < 2.0 → **全部应被 REJECT**。

### 8.4 缺口汇总

| # | 缺口 | 位置 |
| --- | --- | --- |
| 1 | SHORT_PUT 从不计算 `reward_risk` | line 362 |
| 2 | Status 无条件硬编码 Active | line 598 |
| 3 | 无最终推荐的 R/R 门槛（2.0） | 全局缺失 |
| 4 | 价差门槛 0.40 过低，且不覆盖 SHORT_PUT | line 29 / 429 |
| 5 | 无 Planned Risk 概念 | 全局缺失 |
| 6 | Dashboard 与前端不过滤 status | `dashboard_export.py:1600`、`app.js:343` |

---

## 9. 最小修改方案（待用户确认后实施）

### 设计原则

| 原则 | 落实方式 |
| --- | --- |
| ✅ 不改真实 Max Loss / Max Profit | 保留 line 354/361/420/421/463 全部公式 |
| ✅ 不删除现有策略 | 仅改 Status 判定，不移除任何生成逻辑 |
| ✅ 不改期权数据源 | 不动 `_load_chain` / `_direct_yahoo_option_chain` |
| ✅ 不动股票 Scan / Review / Runtime / Schedule | 不涉及 |
| ✅ 不大规模重构 | 集中改 1 个主文件 + 1 处过滤 |

### 方案步骤（4 步）

#### 步骤 1：新增双风险概念常量（`scan_us_option_engine.py`）

```python
MIN_REWARD_RISK = 2.0                  # 最终推荐门槛（新增）
MIN_SPREAD_REWARD_RISK = 0.40          # 保留：仅用于价差结构筛选（不动）
```

#### 步骤 2：新增 R/R 计算 helper（`scan_us_option_engine.py`）

```python
def _theoretical_rr(max_profit, max_loss):
    """Theoretical Reward/Risk；max_loss<=0 或缺失时返回 None（不可判定）。"""
    if max_profit is None or max_loss is None or max_loss <= 0:
        return None
    return max_profit / max_loss

def _planned_rr(structure):
    """Trading/Planned R/R：仅当存在明确可执行止损/目标时返回数值。
    当前代码无任何数值止损字段 → 恒返回 None（预留扩展点）。"""
    return None
```

> 按用户要求：**无明确 Planned Risk 时不允许编造**，因此 `_planned_rr` 当前返回 `None`，判定回落到 Theoretical R/R。

#### 步骤 3：填充 reward_risk + Status 判定（`scan_us_option_engine.py`）

1. **SHORT_PUT**（line 361-362）：把 `"reward_risk": None` 改为计算值
   ```python
   "reward_risk": round(_theoretical_rr(sell_price*100.0, max_loss), 4) if max_loss > 0 else None
   ```
2. **Status 判定**（替换 line 598 的硬编码）：
   ```python
   _rr = _planned_rr(structure) or _theoretical_rr(max_profit, max_loss)
   if _rr is None:
       status = "Rejected_NoRiskData"
   elif _rr >= MIN_REWARD_RISK:
       status = "Active"
   else:
       status = "Rejected_RR"
   ```
   并在 `Reason` 追加拒绝原因（如 `Reward/Risk=0.018 < 2.0，已拒绝`）。

#### 步骤 4：Dashboard 过滤（`dashboard_export.py`）

在 `build_options()`（line 1600）中，仅保留 `status == "Active"` 的行（或在输出时标记）。
> **必须做**：否则 Rejected 策略仍会出现在 Dashboard（`app.js` 也不过滤）。

### 预期效果（基于现有 10 条数据）

| 策略 | 理论 R/R | 新 Status |
| --- | --- | --- |
| ALL SHORT_PUT | 0.0179 | **Rejected_RR** |
| ALL SHORT_PUT (9-30) | 0.0184 | **Rejected_RR** |
| CBOE SHORT_PUT | 0.0243 | **Rejected_RR** |
| NTAP SHORT_PUT | 0.0354 | **Rejected_RR** |
| TER SHORT_PUT | 0.0641 | **Rejected_RR** |
| FTNT / PAYX / APA / SCHW / MPC (Spread) | 1.212–1.439 | **Rejected_RR** |

> 按当前数据，**10 条全部会被拒绝**。这是符合用户规则的预期结果（真实反映"当前无任何策略达到 2:1"），不是 bug。
> 后续若要产生 Active 推荐，需要真实存在高 R/R 结构（如 Bull Put Spread 或通过 Planned Risk 定义可执行止损）。

### 不做的事（明确保留）

- ❌ 不改 `(Strike − Premium) × 100` 的 Max Loss 公式
- ❌ 不降低 Max Loss 数值以"凑" 2:1
- ❌ 不删除任何现有策略或 CSV 行
- ❌ 不加 Bull Put Spread（属新增功能，需用户另行确认）
- ❌ 不动 scan/review/runtime/schedule 的既有逻辑

---

## 10. 预计会影响哪些文件

| 文件 | 改动类型 | 说明 |
| --- | --- | --- |
| **`scan_us_option_engine.py`** | **主要改动** | 新增 `MIN_REWARD_RISK=2.0`；新增 `_theoretical_rr()` / `_planned_rr()`；SHORT_PUT 填充 `reward_risk`；line 598 Status 由硬编码改为判定 |
| **`dashboard_export.py`** | **小改动** | `build_options()` 增加 `status` 过滤（否则 Rejected 仍会显示） |
| `option_strategies.csv` | 数据变化 | 由 scan 运行时重新生成；Status 由 Active → Rejected_RR（**不手工编辑**） |
| `scan.py` | 可选 | 邮件 HTML 可增加 R/R 与拒绝原因展示（不改也可，因已过滤 Active） |
| `review.py` | **不改** | 已过滤 `Status == "Active"`，自动生效 |
| `app.js` / `index.html` / `app.css` | **不改** | 前端透传，由导出层过滤后可自动生效 |
| `tests/test_options_reward_risk.py` | 可选新增 | 建议新增回归测试覆盖 2.0 门槛与 SHORT_PUT 拒绝路径 |

---

## 只读校验

审计全程仅执行：文件读取、`grep` 检索、CSV 只读解析（pandas `read_csv`）、git 只读查询。**未写入、未修改、未提交任何文件。**

---

## 待用户确认事项

1. 是否按上述 4 步方案实施（尤其是 **步骤 4 Dashboard 过滤** 的必要性）？
2. Rejected 状态的取值命名：`Rejected_RR` 是否可接受？（影响 review/dashboard 的状态语义）
3. 是否需要在本次一并**新增 Bull Put Spread** 策略（当前不存在，属新功能而非修复）？
4. 是否接受"当前 10 条历史记录全部变为 Rejected"这一结果？（历史数据不手工改，由下次 scan 重算覆盖）
