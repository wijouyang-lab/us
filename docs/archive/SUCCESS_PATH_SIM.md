# 周末「意外成功」全链路模拟报告

> **执行方式**：只读真实数据 + 跑纯函数（`quant_filter` / `portfolio_target` / `portfolio_50000`）。
> 未调 AI、未触发真实 scan、未写任何仓库文件；所有产物在 `/tmp` 与本文档。
> 真实数据基准：`quant_factor_snapshot.csv` 最新日 **2026-10-09（255 行）**；真实持仓 **4 只**（ADSK/ANET/ISRG/KR）。

---

## 0. 核心结论（先看这个）

| 问题 | 结论 |
|------|------|
| 周一若真出 1-3 只候选，会被买入吗？ | **不会**（双重拦截，预期行为非 bug） |
| 拦截器 1 | **80% 股票天花板**：当前股票占比 **79.64%**，任何新买入触发 `总股票将超 80%` 被拒 |
| 拦截器 2 | **Unit 饱和**：`UNIT_IDS` 固定 4 个，4 只持仓已占满，`next_free_unit` 返回 `None` → 第 5 只无 Unit |
| 真实候选数会是多少？ | 取决于动态条件（评分≥80 + R/R≥2.0 + 止损 2-5%，前 20 日高点≥现价 1.10）；机制正常可用（见 §5 根因 1 更正、§7），周一真实 scan 见分晓 |

**一句话**：周一即使 scan 产出候选，组合也处于「满仓 4 单元 / 79.64% 股票」状态，**无新买入**——这是设计预期的「Bonus D 天花板」兑现，不是 bug。要产生新买入，必须先有持仓被 SELL（释放 Unit + 现金 + 降低占比）。

---

## 1. 场景 A：严筛出 1 只候选 → AI 输入 / target 写入 / 前端匹配 / 股数

**构造**：取真实票 `A`（Agilent，Price=171.14），把 `Quant_Score` 改为 85，合成 `target_price=Price×1.12=191.68`、`Stop_Loss=Price×0.96=164.29`（见 §6 边界坑）。

| 步骤 | 结果 | 预期 | 判定 |
|------|------|------|------|
| `strict_filter([A])` | 候选数 **1**（A: score=85, rr=3.0, sd=0.04） | 1 | ✅ |
| `build_ai_input(持仓4 + 候选1)` | AI 输入数 **5**（核心龙 4 + 候选 1） | 5 | ✅ |
| `build_portfolio_target_rows` | 行数 5：**BUY=1 / HOLD=4 / SELL=0** | 1 只 BUY | ✅ |

**BUY 行字段齐吗？**
- `A`: `Action=BUY, Target_Shares=58, Ref_Price=171.14, Stop_Loss=164.29, AI_Reason=''`，`Scan_Date` 齐全 → **字段齐全=True** ✅
- `AI_Reason` 为空是预期的（候选行无 `AI_premarket_conclusion` 等字段，`_target_reason` 回退空串；AI 理由由 review 回填）。

**股数计算对吗（单只 25% 上限钳制）？**
- `per = 50000/5 = 10000`；`budget = min(10000, 12500) = 10000`；`shares = floor(10000/171.14) = 58` → **实际=58，匹配=True** ✅

**前端 `renderTarget` 能渲染吗（字段名匹配）？**
- `dashboard_export._read_portfolio_target` 注入键：`scan_date / ticker / action / target_shares / ref_price / stop_loss / ai_reason`
- `app.js renderTarget` 读取键：`ticker / action / target_shares / ref_price / ai_reason / scan_date`
- **键完全匹配=True** ✅（`renderTarget` 不读 `stop_loss`，但导出层也给了，无碍；缺字段时前端用 `NA` 兜底不崩）

---

## 2. 场景 B：新候选真的被买入 → `process_buys` 闸门

**真实当前账本**：现金 `$10438.80`，股票市值 `$40837.39`，权益 `$51276.19`，**股票占比 = 79.64%**。

| 闸门 | 预览结果 |
|------|----------|
| 闸门 1（7 天冷却） | 无冷却记录 → 不拦 |
| 闸门 2（近 1-2 日止损防御） | 无近期止损 → 不拦 |
| **闸门 3（`_within_alloc` 总股票≤80%）** | **`ok=False, why='总股票将超 80%'`** ❌ 拦截 |
| 空闲 Unit 预览 | `next_free_unit=None`（4 单元占满）→ 次级拦截 |

**实跑 `process_buys`（内存副本，不写文件）日志**：
```
⏸  A 占比约束拦截（总股票将超 80%）→ 跳过
```
- `proj_stock = 当前股票MV + 新size = 40837.39 + 10000 = 50837.39` vs `80% 上限 = 41020.95` → 远超。
- **结论：新候选未被买入 = True（被拦截，预期/非 bug）**。

> **这是最关键发现**：当前组合已贴 80% 红线，任何新增买入都会被占比闸门拒绝；即便放开占比，`UNIT_IDS` 仅 4 个、全部占满，第 5 只还会卡在「无空闲 Unit」。→ 周一真实路径：只有先 SELL 掉一只持仓，才能释放 Unit + 现金 + 降低占比，进而允许新买入。

---

## 3. 场景 C：盘中止损真触发 → 冷却生效（只读代码追踪 + 日期演示）

追踪 `portfolio_50000._run_intraday_stop`（L638-741）与 `process_buys` 闸门，以 `today=2026-10-12` 演示：

| 检查项 | 结果 |
|--------|------|
| 触发后写 `Cooldown_Until` | `= today + 7 天` → `2026-10-12 → 2026-10-19` ✅ |
| 触发后写 `Pending_Reason` | `="True"`（transactions 行，`Reason="Intraday Stop Loss"`）✅ |
| 单日止损上限 | `MAX_INTRADAY_STOPS_PER_DAY = 2` ✅ |
| 幂等 | `txn_id = INTRADAY|TKR|today`，今日已止损不重复处理 ✅ |

**`process_buys` 冷却拦截验证**（cd = 2026-10-19）：

| 日期 | 闸门1（today≤cd） | 闸门2（近1-2日防御） | 结果 |
|------|------------------|---------------------|------|
| 2026-10-12（当日） | True | True | **拦截** |
| 2026-10-13（次日） | True | True | **拦截** |
| 2026-10-18（第 7 天） | True | False | **拦截** |
| 2026-10-20（第 8 天） | False | False | **放行** |

→ 冷却对「当日 + 其后 7 天（共 8 个自然日）」生效，第 9 天起可复买。**盘中止损冷却链路完整、有效** ✅。

---

## 4. 场景 D：MIN_SCORE=80 跑全部 255 只（合成 target/stop）—— 各闸计数

对 2026-10-09 全量 255 只合成 `target_price=Price×1.12`、`Stop_Loss=Price×0.96`，逐闸漏斗：

| 闸 | 通过数 |
|----|--------|
| 分数闸（≥80） | **3** |
| + R/R 闸（≥2.0）& 止损距离 [2%,5%] | **3** |
| + 板块 ≤1/板块（`strict_filter`） | **2**（最终候选） |

**最终候选**：`PLTR`（score=87, Technology）、`HUM`（score=81, Other）。

> ⚠️ **现实注记（已更正 2026-10-11）**：以上基于「Price×1.12 / Price×0.96」合成假设以演示漏斗。**真实 scan 的 `target_price` 在运行时动态补算**——`scan.py:3767-3776` 在调用 `strict_filter` 前，对每只非持仓候选执行 `_it["target_price"] = compute_20d_high(get_kline_data(ticker))`（前 20 日高点）。因此候选机制本身可用，**不会因 snapshot 无列而恒为 0**。`quant_factor_snapshot.csv` 无 `target_price` 列仅影响离线模拟，不影响真实 scan。真实候选数取决于动态条件（评分≥80 + R/R≥2.0 + 止损 2-5% + 前 20 日高点≥现价 1.10），周一真实 scan 见分晓（见 §5 根因 1 更正、§7）。

---

## 5. 发现的问题（只列不改）

### 🔴 高优先
1. **【已更正 2026-10-11】根因 1 不成立（假阴性）。**
snapshot CSV 确实无 `target_price` 列，但真实 scan 运行时动态补算——`scan.py:3767-3776` 在调用 `strict_filter` 前，对每只非持仓候选执行 `_it["target_price"] = compute_20d_high(get_kline_data(ticker))`（前 20 日高点）。
因此候选机制本身可用，不会因缺 target 而恒为 0。之前结论误把"snapshot 无列"当作"运行时无值"。
真实候选数取决于动态条件（评分≥80 + R/R≥2.0 + 止损 2-5%），周一真实 scan 见分晓。
2. **80% 天花板 + Unit 饱和 双重锁死新买入**：即便出候选，当前 79.64% 占比 + 4 单元占满 → 无新买入。这是结构性约束（Bonus D），需先 SELL 才能 BUY。非 bug，但周一若期待"候选被买入"会落空。

### 🟡 中优先
3. **设计「浮动 3-5 只」与代码「固定 4 单元」矛盾**：`UNIT_IDS = ["U001".."U004"]` 写死 4 个，`next_free_unit` 只能返回这 4 个。组合永远无法持有第 5 只 → "5 只"目标不可达。若想支持 5 只，需扩 `UNIT_IDS` 或改为动态分配 Unit_ID。
4. **占比闸门公式偏保守**：`proj_stock = 当前股票MV + 新size`，把"新增金额"全算进股票侧。当前 79.64% 时加 $10k 直接把占比推到 ~99% 视角（实际是 cash↔stock 互换，权益不变），阈值判定正确但数值观感反直觉。逻辑无误，仅提醒。

### 🟢 低优先 / 观察
5. **合成 `Stop_Loss=Price×0.95` 会越界被拒**：`(price - price*0.95)/price` 经浮点 = **5.0016% > MAX_STOP_DIST(0.05)** 硬上限 → strict_filter 拒。0.95 看似"正好 5%"，实则超界。本模拟改用 0.96（4%）以产出有效候选。真实 scan 用 ATR 派生止损，一般不踩此坑，但提示 5% 上限为**含边界**且浮点敏感。
6. **BUY 行 `Stop_Loss` 浮点尾差**：合成值写入 CSV 会成 `164.29439999999997`（`write_csv_rows` 直写 float repr）。前端 `renderTarget` 不展示 `stop_loss`，无碍；但若别处展示需注意 `round_num`。
7. **场景 A 的 `AI_Reason` 为空**：候选行无 AI 结论字段时 `_target_reason` 回退空串，target 板块不渲染理由行（前端 `reason ? ... : ''` 容错）。属预期。

---

## 6. 周一预期：如果出 1-3 只候选，会发生什么？

- **若真实 scan 未补算 `target_price`**：候选数 = **0**（同前几轮），target 文件为空/不更新，前端不显示目标板块。无风险。
- **若 scan 已补算 target 且真出 2-3 只候选**：
  1. `build_ai_input` 收缩到 ≤7 只（持仓 4 + 候选 ≤3）→ AI 输入正常；
  2. `build_portfolio_target_rows` 写 1-3 只 **BUY** + 4 只 **HOLD**（字段齐全、前端可渲染、股数计算正确，已验证）；
  3. **但 `process_buys` 会拦截这些 BUY**（80% 占比 + 无空闲 Unit）→ 候选"出现在 target 文件 / 前端目标板块"，却**不会真买入**；
  4. 盘中止损冷却链路完整有效（7 天冷却 + 单日 2 只上限）。
- **结论**：周一"候选出现但买不进"是**预期且安全**的——target 板块会显示建议买入，实际账本不动，不会超 80%、不会超 4 单元。无需周一前修代码，但**需在周报/值班说明中讲清**，避免误判"候选功能失效"。

---

## 7. 周一预期（更正后）

| 现象 | 判断 |
|------|------|
| 0 候选 | ✅ 可能（动态条件未达标） |
| 1-3 候选 | ✅ 可能（机制正常） |
| target.csv 写 BUY 行 | ✅ 可能（但不会执行） |
| 组合维持 4 只不动 | ✅ 预期（80% 已满） |

> 更正要点：`quant_factor_snapshot.csv` 无 `target_price` 列 **不等于** 真实 scan 缺 target——`scan.py:3767-3776` 已在前置阶段动态补算（前 20 日高点）。根因 1（假阴性）已撤销；根因 2（80% 天花板 + Unit 饱和）依然成立，是周一"有候选也买不进"的真正原因。

---

*生成于周末只读模拟；不涉及任何代码改动或推送。模拟脚本：`/tmp/sim_success_path.py`，原始输出：`/tmp/sim_success_path.out`。*
