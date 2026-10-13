# Review Field Mapping Fix Report

> 修复性质：字段透传 + Dashboard 展示修复，**未改变任何交易逻辑/价格计算/止损/胜率/Options RR**。
> 完成时刻：2026-10-02（北京 19:10）

---

## 1. Modified Files

| 文件 | 改动 |
| --- | --- |
| `review.py` | `TRADE_COLUMNS` 增加 `Market_Regime`/`VIX`/`Sector_RS_20D_Pct`；pending→trade_history 写入时原样透传三字段 |
| `dashboard_export.py` | `_TRADE_TO_PENDING` 增加 `Market_Regime`/`VIX` 映射；`build_current_event_rows` 新增独立 `Rec_Price`；`build_stocks` 新增 `rec_price` 字段 |
| `app.js` | normalize 增加 `recPrice: num(s.rec_price)`；`posMatrix` 新增"买入价"行 |
| `tests/test_review_dashboard_fields.py` | **新增** 38 项测试 |

```
git diff --stat
 app.js              |  7 +++++++
 dashboard_export.py | 13 ++++++++++++-
 review.py           |  7 +++++++
 3 files changed, 26 insertions(+), 1 deletion(-)
```

> 范围校验：`scan.py` / `scan_us_option_engine.py` / `.github/` / Email / `us-market-terminal` **均未被触碰**。

---

## 2. Buy Price Fix

### source
`trade_history.csv` 的 `Price` 字段 = **推荐日真实 Open**（经 `safe_record_price()` 确认，禁止 fallback 到 Scan_Ref_Price / Close / 实时价）。

### transformation

| 层 | 处理 |
| --- | --- |
| `build_current_event_rows`（dashboard_export.py:1105） | 新增独立 `row["Rec_Price"] = str(rec_price)`，**保留**原有 `row["Scan_Ref_Price"]`（未删除、未替换） |
| `_TRADE_TO_PENDING` | 不涉及（Rec_Price 由 build_current_event_rows 直接写入） |
| `build_stocks`（dashboard_export.py:1240） | `"rec_price": round_num(parse_num(row.get("Rec_Price")), 2)` |

### dashboard JSON
`stocks[].rec_price = 479.88`（两位小数，独立字段）

### frontend rendering
```js
// normalize
recPrice: num(s.rec_price),
// posMatrix
mx('买入价', nv(s.recPrice, 2))   // null 时 nv() 返回 "—"
```

---

## 3. Market_Regime Fix

| 层 | 处理 |
| --- | --- |
| source | pending CSV 的 `Market_Regime` 列（scan.py 写入，有值） |
| review persistence | `review.py` TRADE_COLUMNS 新增 `"Market_Regime"`；pending→trade_history 写入 `clean_text(row.get("Market_Regime"))`（**原样透传，不重算/不重新调用 AI/不推导**） |
| dashboard mapping | `_TRADE_TO_PENDING` 新增 `"Market_Regime": "Market_Regime"`；`build_stocks` 已读 `row.get("Market_Regime")` → `stocks[].market_regime` |
| frontend rendering | 既有 `s.regime = s.market_regime \|\| ''`；`mx('Market Regime', esc(s.regime \|\| NA))` —— 有值显示真实值，无值显示 `—` |

> 前端 key 保持一致：`market_regime`（JSON）→ `s.regime`（前端），无 `marketRegime`/`regime` 混乱映射。

---

## 4. VIX Fix

同 Market_Regime 链路：
- `review.py` TRADE_COLUMNS 新增 `"VIX"`，pending 写入时 `clean_text(row.get("VIX"))`（不重新抓取市场数据）
- `dashboard_export.py` `_TRADE_TO_PENDING` 新增 `"VIX": "VIX"`
- `build_stocks` → `stocks[].vix`；前端 `nv(s.vix, 2)`

---

## 5. Sector_RS_20D_Pct Fix

- `review.py` TRADE_COLUMNS 新增 `"Sector_RS_20D_Pct"`，pending 写入时 `clean_text(row.get("Sector_RS_20D_Pct"))`（不重新计算）
- `_TRADE_TO_PENDING` **已存在**该映射（`"Sector_RS_20D_Pct": "Sector_RS_20D_Pct"`），此前因 trade_history 无此列而为空；现 review 已写入该列，链路打通
- `build_stocks` → `stocks[].sector_rs_20d_pct`；前端 `nv(s.rs, 2)`（sector RS 20D）

---

## 6. MSFT 2026-08-21 Verification（真实数据回归）

输入：真实 `trade_history.csv` 中 MSFT / Date=2026-08-21 行

| 项 | 值 | 校验 |
| --- | --- | --- |
| **Buy Price（rec_price）** | **479.88** | ✅ 与推荐日真实 Open 一致 |
| **Current Price（price）** | **515.96** | ✅ 仍为当前价，未被 rec_price 替换 |
| **Prev Close（prev_close）** | **483.24** | ✅ 未改变 |
| Stop Loss | 493.94 | ✅ 未改变 |
| **Market Regime（market_regime）** | **None → 前端显示 `—`** | ⚠️ 该**历史行本身无 Market_Regime 值**（旧 review 从未写过该列） |

**三个价格语义严格分离验证**：`{479.88, 515.96, 483.24}` 三个互不相同的值 ✅

> Market Regime 对历史记录仍为 `—` 属**预期行为**：本次修复只打通"未来/当前管线"，不回填历史、不伪造值。修复后新产生的推荐事件将携带真实 Market_Regime。

---

## 7. Backward Compatibility

| 场景 | 处理 | 结果 |
| --- | --- | --- |
| `rec_price` 缺失 | `round_num(parse_num(None), 2)` → `None` | ✅ 不报错 |
| 前端 `recPrice = null` | `nv(null, 2)` → `NA`（`—`） | ✅ 不会 `null.toFixed()` 崩溃 |
| `market_regime` / `vix` / `sector_rs` 缺失 | 均为 `None` | ✅ 前端显示 `—` |
| 无 `Rec_Price` 的极旧 row | `rec_price = None` | ✅ 测试 5e 验证 |
| `Scan_Ref_Price` | **保留**，价格回退链不变 | ✅ |

历史数据：**未批量重写** `trade_history.csv` / `review_history.csv`，未修改旧 Entry Price / PnL / 胜率。

---

## 8. Tests

### 静态检查

| 检查 | 结果 |
| --- | --- |
| `python -m py_compile review.py dashboard_export.py` | ✅ OK |
| `node --check app.js` | ✅ OK |
| `git diff --check` | ✅ OK（无空白错误） |

### 新增测试 `tests/test_review_dashboard_fields.py`：**38 / 38 ✅**

| Test | 内容 | 结果 |
| --- | --- | --- |
| Test 1 | rec_price=479.88 进入 `stocks[].rec_price`；Scan_Ref_Price 保留 | ✅ |
| Test 2 | Market_Regime 非空 → `stocks[].market_regime` | ✅ |
| Test 3 | VIX 非空 → Dashboard | ✅ |
| Test 4 | Sector_RS_20D_Pct 非空 → Dashboard | ✅ |
| Test 5 | 旧数据 rec_price/market_regime=None 不崩溃 | ✅ |
| Test 6 | Current Price 仍为 current price（515.96 ≠ 479.88） | ✅ |
| Test 7 | Prev Close 未改变（483.24） | ✅ |
| Test 8 | Stop Loss 未改变（493.94） | ✅ |
| 9a-9j | review/dashboard/app.js 结构与映射回归 | ✅ |
| 10a-10e | 红线：Options RR / 胜率 / safe_record_price 未变 | ✅ |

### 项目全部测试（脚本式，按项目现有方式运行）：**241 / 241 ✅**

| 测试文件 | 结果 |
| --- | --- |
| test_dashboard_runtime.py | 19 / 19 ✅ |
| test_event_key_p2.py | 15 / 15 ✅ |
| test_milestone_win_rate.py | 16 / 16 ✅ |
| test_p05_repair_regression.py | 45 / 45 ✅ |
| test_p3_5_rec_price_repair.py | 12 / 12 ✅ |
| test_p3_data_quality.py | 16 / 16 ✅ |
| test_options_reward_risk.py | 80 / 80 ✅ |
| **test_review_dashboard_fields.py（新增）** | **38 / 38 ✅** |
| **合计** | **241 / 241** |

---

## 9. Regression Check

| 项 | 状态 | 证据 |
| --- | --- | --- |
| Scan unchanged | ✅ | `scan.py` 未在 diff 中 |
| Options unchanged | ✅ | `scan_us_option_engine.py` 未在 diff 中；MIN_REWARD_RISK=2.0、MIN_SPREAD_REWARD_RISK=0.40 测试守护 |
| Stop-loss unchanged | ✅ | Test 8（493.94 未变）；review.py 仅增字段透传 |
| PnL unchanged | ✅ | `rec_price` 仅展示，未参与 PnL；胜率公式测试守护 |
| Win-rate unchanged | ✅ | 10d：`win_rate = (wins / eligible * 100) if eligible else None` 未变 |
| Runtime unchanged | ✅ | `dashboard/fetch_runtimes.py` 未在 diff 中 |
| Schedule unchanged | ✅ | `.github/` 未在 diff 中 |
| Email unchanged | ✅ | 未触碰任何 Email 代码 |
| 历史数据未重写 | ✅ | 未批量改写 CSV；仅 schema 扩展（新列空值） |

---

## 10. Final Diff Summary

```
 app.js              |  7 +++++++     (recPrice 映射 + 买入价渲染)
 dashboard_export.py | 13 +++++++++++  (_TRADE_TO_PENDING + Rec_Price + rec_price)
 review.py           |  7 +++++++     (TRADE_COLUMNS + 三字段透传)
 3 files changed, 26 insertions(+), 1 deletion(-)
```

**未触碰**：scan.py、scan_us_option_engine.py、.github/workflows/、Email、us-market-terminal、Runtime、Schedule、Options RR、止损算法、胜率算法。

---

## 11. Final Status

# PASS

修复后 Review Dashboard 卡片可清晰区分：

| 字段 | 值 |
| --- | --- |
| 买入价 | **479.88**（新显示） |
| Price（当前价） | **515.96**（未改变） |
| Prev Close | **483.24**（未改变） |
| Market Regime | 有值显示真实值；历史记录仍 `—`（待新推荐携带） |
| VIX / Sector RS 20D | 有值显示真实值 |

任何交易策略、价格计算、止损、胜率、Options RR、Runtime、Schedule **均未发生行为变化**。

---

## 变更操作状态

| 项 | 值 |
| --- | --- |
| **Files modified** | **4**（review.py、dashboard_export.py、app.js + 新增 tests/test_review_dashboard_fields.py） |
| **Tests** | **241 / 241 全部通过**（新增 38 / 38） |
| **Commit** | **0**（未 commit） |
| **Push** | **0**（未 push） |
| **Workflow dispatch** | **0**（未 dispatch） |

> 按要求：修改与测试结果已报告，**未自行 commit / push / dispatch**，等待你决定是否提交。
