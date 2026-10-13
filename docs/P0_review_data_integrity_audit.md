# P0 数据完整性审查：真实生产 Review（commit `138dc09` / `美股盘后补充成交 2026-09-30`）

> 审查对象：GitHub `wijouyang-lab/us` 上本次真实生产 Review 运行输出
> 运行前快照：`40eba4c`（origin/main，运行父提交）的 `review_history.csv`
> 运行后快照：`138dc09`（生产运行提交）的 `review_history.csv`
> 会话日 `REVIEW_SESSION_DATE = 2026-09-29`
> 方法：只读比对两份数据 + 代码逻辑核对；**未修改任何代码/数据，未 commit/push/触发 workflow**
> 说明：本沙箱 yfinance 被限流，无法联网复验 OHLC 存在性，故「OHLC 是否存在」以数据模式推断（见下）。

---

## 结论速览（是否发现 P0 数据退化风险：**是，确认存在**）

- **`Rec_Price` 有值→空值 = 1225 行**（与运行日志「1225 行因无 OHLC 置空」完全吻合）。
- 这 1225 行**运行前全部持有有效 `Rec_Price`**（经代码核对，无一行原值为空/非法），即**已知有效的推荐价被清空**。
- 根因：**生产运行 yfinance 限流**导致 149 个 ticker（占全部 226 的 66%）历史行情整批抓取失败 → `backfill_rec_price()` 在 `Rec_Date` 无 OHLC 时**无条件把已有有效 `Rec_Price` 覆盖为空**（review.py 第 2295 行），而非保留原值。
- 连锁影响：PnL_5D 丢失 18 条、PnL_10D 丢失 6 条、Review_Stage 在 12 行变化；**PnL_20D 全表 = 0**，且 1207 个本应达 20 交易日的事件 `Rec_Price` 全部为空 → 20D=0 由清空直接保证成立。

---

## Q1｜运行前后 Rec_Price 计数

| 指标 | 数量 |
|---|---|
| 运行前 `Rec_Price` 有值（既有 1464 行） | **1464** |
| 运行后 `Rec_Price` 有值（全部 1508 行 = 1464 既有 + 44 新增当日快照） | **283** |
| **有值 → 空值（退化）** | **1225** |
| 空值 → 有值（既有记录） | **0** |
| 有值 → 有值（相同，幂等跳过） | 186 |
| 有值 → 有值（改为 Rec_Date Open，不同） | 53 |
| 空值 → 空值 | 0 |
| 新增 44 行（当日 Review 快照，自带有效 Rec_Price） | 44 |

勾稽：`1464 − 1225(清空) + 44(新增) = 283` ✓ 与「运行后 283 有值」一致。
日志 `changed=1290` 复核：既有改动 `1225+53=1278` + 新增 44 行中 12 行 scan 价≠Open 被纠正 = **1290** ✓ 完全吻合。

---

## Q2｜「有值→空值」原因分类（共 1225 行）

| 原因 | 数量 | 说明 |
|---|---|---|
| (a) Rec_Date 本身无对应 OHLC（非交易日/周末假日） | **0** | 所有 1225 行 `Rec_Date` 均为工作日（周一~周五计数 282/258/246/236/203，周六日=0） |
| (b) ticker / 日期匹配失败 | **0** | 被清空 ticker 均为合法代码（AMZN、AVGO、MRK、UBER…），非拼写/匹配错误 |
| (c) 历史 OHLC 下载窗口不足 / 抓取失败 | **1225（全部）** | 见下「成片失败」分析 |
| (d) yfinance 实际返回空数据（个股真实缺口） | 0（推断） | 流动性标的不会整段缺失；空值来自抓取失败而非真实缺口 |
| (e) 其他 | 0 | — |

**关键模式——成片失败**：1225 行全部来自 **149 个 ticker，且这些 ticker 的每一行都被清空**（整 ticker 历史缺失 1225 行；零散缺口 = 0 行；完全未被清空 77 个 ticker）。
这恰好是 **yfinance 限流**特征：批量抓取（CHUNK=30）时前段 ticker 成功（77 个，Rec_Price 保留/纠正、里程碑可算），后段 ticker 整批被限流（149 个，历史全空 → 全部清空）。

- 被清空行 `Rec_Date` 距会话日年龄：中位 50 天，范围 22–125 天；分桶 `<30d:18 / 30-60d:872 / 60-90d:81 / 90-120d:199 / 120-180d:55`。
- 其中 254 行 `Rec_Date` 超 90 天基础窗口（即便无限流也需靠 `build_milestone_history` 拓宽）；971 行在 90 天内本应被基础窗口覆盖——它们的缺失只能来自「该 ticker 整段抓取失败」，而非窗口问题。

---

## Q3｜既有有效 Rec_Price 是否被 backfill 误清空

**确认：是。** 代码逻辑（review.py `backfill_rec_price`，第 2290–2298 行）：

```python
ohlc = get_exact_date_ohlc(hist, tk, rec)
new_price = safe_float(ohlc.get("open")) if ohlc else None   # 无 OHLC → None
old_price = safe_float(row.get("Rec_Price"))
if (old is None and new is None) or (old is not None and new is not None and abs(old-new)<1e-6):
    continue
od.at[idx, "Rec_Price"] = "" if new_price is None else str(new_price)  # 无条件覆盖
```

- 当 `new_price is None`（OHLC 缺失）且原 `Rec_Price` 有效时，落入变更分支并**置空**。
- 数据核对：1225 个「有→空」行，**运行前 `Rec_Price` 全部有效（0 行原值非法）** → 即原有效值被清空。
- 结论：本次运行**确实因 `backfill_rec_price()` 找不到 OHLC 而清空了原本有效的 `Rec_Price`**。该函数在 OHLC 缺失时未保留既有有效值，是退化的直接代码原因。

---

## Q4｜随机抽 10 条「有值→空值」记录

> 注：本沙箱 yfinance 限流，无法联网确认 OHLC 存在性；「OHLC 是否存在」据「整 ticker 成片缺失」模式推断——这些 ticker（AMZN/AVGO/MRK 等）历史 OHLC **应真实存在**，清空系生产运行抓取失败所致。

| Ticker | Rec_Date | 原 Rec_Price | 当前 Rec_Price | OHLC 是否存在 | 原因 |
|---|---|---|---|---|---|
| ACN | 2026-06-22 (周一) | 127.98 | （空） | 应存在（未联网确认） | 整 ticker 抓取失败（限流） |
| WMT | 2026-05-27 (周三) | 118.57 | （空） | 应存在 | 整 ticker 抓取失败 |
| VICI | 2026-08-14 (周五) | 26.38 | （空） | 应存在 | 整 ticker 抓取失败 |
| MRK | 2026-08-13 (周四) | 133.86 | （空） | 应存在 | 整 ticker 抓取失败 |
| MRK | 2026-08-13 (周四) | 133.86 | （空） | 应存在 | 整 ticker 抓取失败（同事件第 2 行） |
| MDLZ | 2026-07-30 (周四) | 63.79 | （空） | 应存在 | 整 ticker 抓取失败 |
| GGB | 2026-06-04 (周四) | 4.75 | （空） | 应存在 | 整 ticker 抓取失败 |
| UBER | 2026-08-25 (周二) | 79.38 | （空） | 应存在 | 整 ticker 抓取失败 |
| GRAB | 2026-06-03 (周三) | 3.60 | （空） | 应存在 | 整 ticker 抓取失败 |
| AES | 2026-08-24 (周一) | 14.75 | （空） | 应存在 | 整 ticker 抓取失败 |

（注：MRK 出现两次为同事件两条 Review 快照，属数据既有重复键，非两独立事件。）

---

## Q5｜对 PnL / 胜率 / Review Stage 的影响

被清空 `Rec_Price` 的 1225 行中（先在 `backfill_review_milestones` 用旧有效 Rec_Price 算过里程碑，再被 `backfill_rec_price` 连带清空 PnL）：

| 指标 | 影响 |
|---|---|
| PnL_5D | 失去（原有效→现空）= **18 行** |
| PnL_10D | 失去 = **6 行** |
| PnL_20D | 失去 = **0 行**（这些行原就无 20D，见 Q7） |
| Review_Stage | 在 **12 行**发生变化（因里程碑字段被清，阶段重算降级） |
| Core_Dragon 标签 | 被清空 1077 行 |
| Observation 标签 | 被清空 124 行（其中 18 行失去 PnL_5D） |

**胜率影响**：Core / Observation 的胜率通常依赖 PnL_5D/10D/20D 与 PnL_Pct。1225 行（含 124 条 Observation、1077 条 Core_Dragon）的里程碑 PnL 历史被清空，其中 18/6 条原本已有 PnL_5D/10D 现变空 → **基于里程碑 PnL 的胜率统计对这些事件退化为空/不可用**。这是真实的数据退化，非显示问题。

---

## Q6｜本次 P0 里程碑中因 Rec_Price 缺失而无法计算的数量

日志里程碑新增：`5D=87 / 10D=112 / 20D=0`。这些新增来自**未被清空**的 77 个 ticker（抓取成功）。

因 Rec_Price 缺失（被清空）而无法计算/被连带清空的里程碑：

| 里程碑 | 因 Rec_Price 缺失无法保留/计算 |
|---|---|
| 5D | 被清空行中 **达到 5D 的 1225 行全部失去 Rec_Price**；其中原本已有 PnL_5D 被连带清空 = **18 行** |
| 10D | 达到 10D 的 1225 行全部失去 Rec_Price；原本已有 PnL_10D 被清空 = **6 行** |
| 20D | **1207 个达到 20 交易日的事件 Rec_Price 全部为空** → PnL_20D 无法计算，故 **20D 新增 = 0 全部归因于此** |

即：20D=0 的 100% 源于 Rec_Price 被清空（所有达 20D 事件均失去 Rec_Price）；5D/10D 各有 18/6 条已算出的 PnL 被连带抹除。

---

## Q7｜20D=0 纯数据诊断（不修改 20D 逻辑）

- 运行后全表 `Price_20D` 有值 = **0**；`PnL_20D` 有值 = **0**（20D 列整体为空）。
- 理论上达到 20 个交易日（会话日 2026-09-29，按交易日近似，扣 2026 已知假日）的事件数：**1207**。
- 这 1207 个事件中：
  - 运行后仍有 `Rec_Price`：**0**
  - 运行后有 `Price_20D`：**0**
  - 运行后有 `PnL_20D`：**0**
- 全部 1207 个达 20D 事件均落在被清空的 1225 行内（即其 ticker 历史抓取失败）。

**诊断**：20D=0 由两个因素叠加，但**清空 Rec_Price 是充分且主导的原因**——
1. 这些旧事件（Rec_Date 多在 60–125 天前）的 ticker 历史在生产运行中被限流整批未抓到，其第 20 交易日 OHLC 不在内存历史中 → `Price_20D` 为空（fail-closed，合理但受限于抓取失败）；
2. 即便 `Price_20D` 能取到，因 `Rec_Price` 已被清空，PnL 公式 `（Price−Rec_Price)/Rec_Price` 也无法计算 → 必然为空。

由于**所有达 20D 事件都失去了 Rec_Price**，20D=0 由清空操作直接保证成立，与 OHLC 是否可取无关。

---

## 最终判定：是否发现 P0 数据退化风险

**是，确认存在 P0 数据退化风险。**

1. **有效数据被销毁**：1225 个运行前持有有效 `Rec_Price` 的推荐事件，因生产运行 yfinance 限流（149 ticker 整批抓取失败）被 `backfill_rec_price()` 无条件置空。这些推荐价是历史真实记录，清空后不可恢复（无备份、无保留逻辑）。
2. **连锁破坏里程碑**：18 条 PnL_5D、6 条 PnL_10D 被连带清空；**PnL_20D 全表归零**，1207 个本应达 20D 的事件胜率/复盘指标全部失效。
3. **根因在代码而非数据**：`backfill_rec_price()` 在 OHLC 缺失时未保留既有有效 `Rec_Price`（应 fail-closed 保留原值，而非用空值覆盖）。即便本次是限流触发，任何「OHLC 暂时取不到」的场景都会以同样方式销毁有效数据。
4. **复现性强**：只要生产运行再遇 yfinance 限流（历史上频发），每次都会重复清空并扩大退化。

**建议（仅建议，未执行任何修改）**：在 `backfill_rec_price()` 中，当 `new_price is None` 且 `old_price is not None` 时**保留原 `Rec_Price` 不覆盖**（仅对新空值做回填）；并给 yfinance 抓取增加重试/退避与按 ticker 的失败标记，避免限流导致整 ticker 历史缺失。

---

### 附：本次审查未改动项
未修改 `review.py` / `scan.py` / `dashboard` / `workflow` / 期权策略 / 数据文件结构；未 commit、未 push、未手动触发任何 workflow。所有结论基于对 `40eba4c`（前）与 `138dc09`（后）两份 `review_history.csv` 的只读比对。
