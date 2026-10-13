# Review Price / Market_Regime Field Audit

> 性质：**只读审计**。未修改代码/CSV/JSON/Dashboard，未 commit/push/dispatch，未做任何生产数据变更。
> 审计时刻：UTC 2026-10-02 10:50（北京 18:50）

---

## 1. Target Record

| 项 | 值 |
| --- | --- |
| Ticker | **MSFT**（Microsoft） |
| Scan Date（Rec_Date） | 2026-08-21 |
| 当前价（卡片显示 Price） | 515.96（JSON 快照为 515.32，语义一致：**当前价**） |
| Prev Close | 483.24（= trade_history.Close_Price = 483.239990234375） |
| 止损价 | 497.51（JSON 快照 493.94，语义一致） |

> 注意：`trade_history.csv` 中 Date=2026-08-21 有 4 条（COIN/MSFT/ROST/NEM）；本记录对应 MSFT，`Price=479.88`（买入价）、`Close_Price=483.24`。

---

## 2. Buy Price（买入价）逐层追踪

| 层 | 字段 | 值 | 证据 |
| --- | --- | --- | --- |
| CSV（trade_history） | `Price` | **479.8800048828125** | 表头第 6 列；`safe_record_price()` 注释"正式买入价 = 推荐日真实 Open" |
| CSV（review_history） | `Rec_Price` | **479.8800048828125** | 表头第 6 列，Rec_Date=2026-08-21 |
| Review | `safe_record_price(row)` | 返回 `row["Price"]` | `review.py:424-431`，仅当 `>0` 返回，否则 None |
| JSON（review.records） | `rec_price` | **479.8800048828125** | `dashboard_data.json` review.records[MSFT\|2026-08-21\|Core_Dragon].rec_price |
| JSON（stocks[]） | `rec_price` / `entry_price` | **None（无独立字段）** | stocks[] 只有 `recommendation_date/id/tag`，买入价被写入 `Scan_Ref_Price` 仅作价格回退 |
| Frontend（app.js） | — | **不渲染** | `grep rec_price/entry_price/buy_price` 无任何命中 |

### Actual Buy Price
**479.88**（= MSFT 2026-08-21 推荐日真实 Open）

### Actual source
`trade_history.csv` 的 `Price` 字段（scan.py 写入，= 推荐日真实 Open）

### Actual formula
`safe_record_price(row)` = `parse_num(row["Price"])`（>0 才返回）—— 无任何 fallback

---

## 3. Is Buy Price Persisted?

**YES**（在 trade_history / review_history / review.records 三层均有保存）

---

## 4. Is Buy Price Displayed?

**NO**（前端 detail 页 `#posMatrix` 不渲染买入价；`grep` 证明 app.js 全文件无 `rec_price`/`entry_price`/`buy_price` 引用）

---

## 5. Market_Regime 逐层追踪

| 层 | 字段 | 值 | 证据 |
| --- | --- | --- | --- |
| CSV（pending） | `Market_Regime` | ✅ 有值（scan.py 写） | `dashboard_export.py:991` 写列定义 |
| CSV（trade_history） | `Market_Regime` | ❌ **无此列** | 表头 51 列无 Market_Regime；`review.py:380 TRADE_COLUMNS` 无该列 |
| Review | — | ❌ **完全不碰** | `grep Market_Regime review.py` 无命中 |
| JSON（stocks[]） | `market_regime` | **None** | 全部 42 只股票 market_regime 均为 None |
| JSON（market.regime） | `market` | **null** | `meta.missing_fields = ['regime.market','regime.vix']` |
| Frontend | `s.regime` | `''` → 显示 `—` | `app.js:231 regime: s.market_regime \|\| ''`；`app.js:974/1060 mx('Market Regime', esc(s.regime \|\| NA))` |

---

## 6. Why Dashboard Shows "—"

**根因：数据在 review.py 写 trade_history 时被丢弃（Data persistence bug）。**

完整链路：

```
scan.py 写 pending CSV（含 Market_Regime 列，有值）
   ↓
review.py 读 pending → 写 trade_history
   ✗ TRADE_COLUMNS（review.py:380-386）无 Market_Regime / VIX / Sector_RS_20D_Pct
   ✗ review.py 完全不读取 Market_Regime
   → Market_Regime 在此被丢弃
   ↓
dashboard_export 股票池 = trade_history active_events（meta.stocks_source="active_events"）
   ✗ _TRADE_TO_PENDING 映射（dashboard_export.py:1013-1030）无 Market_Regime
   → market_regime = None
   ↓
market.regime.market = null（meta.missing_fields 标记 regime.market 缺失）
   ↓
前端 s.regime = '' → 显示 "—"
```

**关键证据**：
- `meta.pending_csv = None`（生产环境当前无 pending CSV 文件）
- `meta.stocks_source = "active_events"`（股票池回退到 trade_history 活跃事件）
- `meta.missing_fields = ['regime.market', 'regime.vix']`

即：即便 pending CSV 有 Market_Regime，一旦被 review 消费并转写为 trade_history，该字段就永久丢失；dashboard 的股票池又主要来自 trade_history，故 Market_Regime 必然为 "—"。

---

## 7. Other Missing Field Mappings

字段映射表（CSV → Review → JSON → Frontend → Display）：

| CSV 字段 | pending | trade_history | _TRADE_TO_PENDING | JSON stocks[] | 前端字段 | 显示 | 定性 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Market_Regime | ✅ | ❌ 无列 | ❌ 无映射 | None | s.regime | "—" | **persistence 丢失** |
| VIX | ✅ | ❌ 无列 | ❌ 无映射 | None | s.vix | "—" | **persistence 丢失** |
| Sector_RS_20D_Pct | ✅ | ❌ 无列 | ✅（源无列） | None | s.rs | "—" | **persistence 丢失** |
| Event_Score | ✅ | ✅ 有列 | ✅ | None（MSFT 值空） | s.eventScore | "—" | 历史数据本身空 |
| 20D成交额(Avg_Dollar_Volume_20D) | ✅ | ✅ 有列 | ✅ | None（MSFT 值空） | s.adv | "—" | 历史数据本身空 |
| Price（买入价=推荐日 Open） | — | ✅ Price | ❌ 无直接映射 | 无独立字段 | ❌ 不渲染 | 不显示 | **mapping 丢失** |
| Stop_Loss | ✅ | ✅ | ✅ | stop_loss | s.stop | 显示 | ✅ |
| Exit_Price / Exit_Date | — | ✅ | 部分 | 部分 | 部分渲染 | 部分 | 部分 |

> 关键区分：Market_Regime/VIX/Sector_RS 是**当前代码就丢失**（review 未透传）；Event_Score/20D成交额 是**该历史记录本身为空**（trade_history 该行确实无值）。

---

## 8. Current Code vs Historical Data

### Current code（当前代码）

- **买入价**：✅ 已能正确保存。`safe_record_price()` = trade_history.Price = 推荐日真实 Open，链路完整到 review.records[].rec_price。
- **Market_Regime / VIX / Sector_RS**：❌ **当前代码就丢失**。review.py 的 TRADE_COLUMNS 从未包含这三个字段，pending → trade_history 转写时必然丢弃（非历史遗留，是持续存在的断层）。

### Historical record（2026-08-21 旧记录）

- **买入价**：✅ 该记录**有**买入价（Price=479.88），不缺字段。
- **Market_Regime**：该记录在 trade_history 中**无 Market_Regime 列**——但这不是"旧数据缺字段"，而是"review 从未写过这个字段"（任何时期的记录都没有）。

> 结论：不能把 Market_Regime 丢失归因于"旧记录缺字段"；它是**当前代码链路的持续性缺陷**。买入价则相反：数据一直在，只是前端没显示。

---

## 9. Findings

### P0（错误交易/持仓/生产结果）
无。

### P1（统计/Review/Dashboard 错误）
无（买入价在 review.records 中正确，胜率/止损口径不受影响）。

### P2（展示缺陷 / 字段丢失）

| # | Severity | File:Line | Evidence | Impact |
| --- | --- | --- | --- | --- |
| P2-1 | P2 | `review.py:380-386`（TRADE_COLUMNS）+ `dashboard_export.py:1013-1030`（_TRADE_TO_PENDING） | trade_history 无 Market_Regime/VIX/Sector_RS_20D_Pct 列，review 完全不透传 | Dashboard Review 卡片 Market Regime / VIX / Sector RS 恒为 "—" |
| P2-2 | P2 | `dashboard_export.py:1103`（rec_price→Scan_Ref_Price）+ `app.js:1058-1077`（posMatrix） | 买入价被降级为价格回退源，stocks[] 无独立买入价字段，前端不渲染 | Review 卡片无法区分"买入价/当前价/前收"，用户只能靠 Price（当前价）猜测 |

### P3（历史数据空值）
| # | Severity | 说明 |
| --- | --- | --- |
| P3-1 | P3 | MSFT 08-21 记录 Event_Score / Avg_Dollar_Volume_20D 在 trade_history 中本身为空 → 显示 "—" 属历史数据缺值，非链路缺陷 |

---

## 10. Recommended Fix（仅方案，不执行）

1. **P2-1（Market_Regime 透传）**：将 `Market_Regime` / `VIX` / `Sector_RS_20D_Pct` 纳入 `review.py` 的 `TRADE_COLUMNS`，并在 pending → trade_history 转写时透传；同步在 `dashboard_export.py` 的 `_TRADE_TO_PENDING` 增加对应映射。
2. **P2-2（买入价展示）**：在 `build_stocks` 中新增独立 `rec_price`（买入价）字段（而非仅作 `Scan_Ref_Price` 回退），并在 `app.js` 的 `#posMatrix` 增加"买入价 / Buy Price"行，与 `Price`（当前价）、`Prev Close` 并列区分。

---

## 11. Modification Check

| 项 | 值 |
| --- | --- |
| Files modified | **0** |
| Commits | **0** |
| Pushes | **0** |
| Dispatches | **0** |

---

## 核心问题最终回答

> **"当前 Review 是否真的记录了推荐日真实 Open 作为买入价，还是只是代码声称如此？"**

**答案：真的记录了，不是只声称。** 基于实际字段链路的完整证据：

1. `trade_history.csv` `Price` 列 = **479.88**（= MSFT 2026-08-21 推荐日真实 Open，由 `safe_record_price()` 返回，注释明确禁止 fallback 到 Scan_Ref_Price/Close/实时价）。
2. `review_history.csv` `Rec_Price` 列 = **479.88**（透传）。
3. `dashboard_data.json` `review.records[].rec_price` = **479.88**（透传）。

**但买入价没有在 Review 卡片显示**，原因是：
- `stocks[]`（前端详情页数据源）中，买入价被 `dashboard_export.py:1103` 降级写入 `Scan_Ref_Price` 仅作价格回退，未保留独立 `rec_price` 字段；
- `app.js` 的 `#posMatrix` 完全未渲染买入价（全文件 grep 无 rec_price/entry_price/buy_price）。

因此定性为 **情况 A（Presentation / mapping bug）+ 情况 D 之外**：数据持久化正确，问题出在 stocks[] 层未透传独立买入价字段 + 前端未渲染。

**而 Market_Regime 显示 "—" 是情况 B（Data persistence bug）**：review.py 从未把 pending CSV 的 Market_Regime 透传到 trade_history（TRADE_COLUMNS 无该列），导致链路在 review 层断裂，与"历史记录缺字段"无关。
