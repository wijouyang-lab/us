# Scan 幂等性调查（同一天重复跑会怎样）

> 调查日期：2026-10-09 · **只读，未改任何代码，未 push/rebase**
> 一句话结论：**数据层幂等（不会产生重复行），但没有「今日已跑」守卫 —— 同日跑 2 次 = 最后一次覆盖前一次 + 成本翻倍**。

---

## 1. 各输出文件的幂等行为

| 输出文件 | 写入方 | 幂等键 | 同日重复跑的结果 |
|---|---|---|---|
| `quant_factor_snapshot.csv` | scan.py:3800 → `write_factor_snapshot()`（`quant_factor_lab.py:402`） | `Scan_Date\|Ticker` | ✅ **upsert**：同 key 行被本次结果覆盖，其余历史行不动，**不产生重复行** |
| `quant_factor_price_history.csv` | `quant_factor_price.py` → `upsert_price_history()`（:169） | `Date\|Ticker` | ✅ **只追加历史中不存在的 key，绝不覆盖历史**（`new_only = incoming[~incoming._key.isin(existing._key)]`），完全幂等 |
| `us_stocks_pending_YYYYMMDD.csv` | scan.py:3895 `open(pending_file, "w")` | 文件名带日期 | ⚠️ **整文件 truncate 覆盖**（不是 append）——同日 2 次跑，文件内容 = **最后一次**的结果 |
| `trade_history.csv` | **scan.py 不写它**（只读用于去重）；由 review.py 把 pending 提升进来 | `Ticker\|Date\|Tag`（`deduplicate_trade_history`，`trade_history_quality.py:23-52`） | ✅ 不会产生重复行 |
| `ai_snapshot.csv` | scan.py:3933 → `upsert_ai_snapshot()`（:3519） | `Ticker\|Rec_Date\|Tag`（`make_snapshot_id`，:3510） | ✅ upsert，幂等 |
| `scan_version.txt` | `update_version_marker()`（:233） | scan.py 的 md5 | ✅ hash 不变则不重写，幂等（是**版本标记**，不是运行锁） |

### 1.1 关键代码摘录

**snapshot upsert**（`quant_factor_lab.py:402-432`）：
```python
"""幂等 upsert 写因子快照
- 唯一键 = Scan_Date | Ticker；
- 本次运行结果覆盖同 key 的旧行，其余历史行保持不变；
- 原子写 temp 文件后 replace，绝不重复 append duplicate。"""
key_map = {}
for r in existing: key_map[f"{r['Scan_Date']}|{r['Ticker']}"] = r
for r in new_rows:  key_map[f"{r['Scan_Date']}|{r['Ticker']}"] = r   # 同 key → 覆盖
```

**pending 覆盖写**（scan.py:3895）：
```python
pending_file = f"us_stocks_pending_{get_us_time().strftime('%Y%m%d')}.csv"
with open(pending_file, "w", encoding="utf-8", newline="") as f:   # ← "w" = 截断覆盖
```

**trade_history 去重**（review.py:609 + `trade_history_quality.py:51`）：
```python
if find_existing_record(existing, target_date, ticker):
    continue                          # 同 Date+Ticker 已存在 → 跳过
...
dd = dd.drop_duplicates(subset=["_key"], keep="first")   # _key = Ticker|Date|Tag
```

---

## 2. portfolio 买入会不会重复买

`portfolio_50000.py` 有**三重守卫**（`process_buys`，:292-378）：

| 守卫 | 代码位置 | 说明 |
|---|---|---|
| BUY 幂等键 | :312-314 `buy_id = f"{rid}\|BUY"`；`if buy_id in existing_txn: continue` | 同一推荐（Ticker\|Rec_Date\|Tag）**只买一次** |
| 已持有则跳过 | :315-317 `if rec["Ticker"] in open_tickers: → HOLD（不重复买入）` | 持仓里已有该 ticker 就绝不重复建仓 |
| Unit 上限 | :318-319 `if open_count >= MAX_OPEN_POSITIONS` | 最多 4 个 Unit，满仓不再买 |
| 空闲 Unit | :335 `next_free_unit(positions)` | 无空闲 Unit 直接跳过 |

**结论**：即使 trade_history 里出现重复记录，也**不会买 2 次**。且 scan.py 自身还有一层去重（:3871-3880，跳过已在 active 持仓中的 ticker）。

---

## 3. 已有防护

| 防护 | 是否存在 | 说明 |
|---|---|---|
| 周末休市跳过 | ✅ 有 | scan.py:179-181 `if get_us_time().weekday() >= 5: sys.exit(0)` |
| **「今日已跑」判断** | ❌ **无** | 未找到 `if today == last_run_date: skip` 之类 |
| **.lock 文件 / 运行状态标记** | ❌ **无** | `scan_version.txt` 是 **scan.py 的 md5 版本标记**（:233），不是运行锁，也不会拦截同日重跑 |
| 邮件重复发送 | ✅ 不会 | scan.py:3950 注释明确：「邮件发送已移除（生产不再发邮件）」 |

---

## 4. 重复跑的最坏后果

| 维度 | 后果 | 严重度 |
|---|---|---|
| 数据完整性 | **安全** —— 全部 upsert/覆盖，无重复行、无脏数据 | 🟢 无风险 |
| 最终采纳结果 | ⚠️ **最后一次跑的覆盖前一次**（pending 整文件覆盖 + snapshot 同 key 覆盖）。两次 AI 输出可能不同 → 等于"同一天换了一批推荐" | 🟡 需知晓 |
| AI 成本 | 💰 两次完整 AI 调用（scan 单次约 4 次 GPT 调用：12000/3000/报告/10000 tokens）→ **翻倍** | 🟡 成本 |
| news-fetch 成本 | 💰 news 现在是 scan 的子 job（`needs: scan`）→ 跑 2 次 scan = **跑 2 次 news**（每次 ~50 次 Finnhub 调用 + 1 次 30 条翻译）→ **翻倍** | 🟡 成本 |
| 邮件 | ✅ 不会重复发（已移除） | 🟢 无风险 |
| git 提交 | 两次 bot commit + push（scan 有 5 次 rebase/push 重试保护）→ 多一条提交，无数据损坏 | 🟢 低风险 |
| 并发撞车 | 若两次几乎同时跑 → push 重试机制会处理（同 dashboard-data 撞车那套） | 🟢 已防护 |

---

## 5. 双触发源（外部定时 + GitHub schedule）是否可行

**结论：数据上可行，但不推荐无条件双开。**

- ✅ **可行性**：幂等设计保证了不会出现重复行、重复买入、数据损坏。从这个意义上说"双保险"不会炸。
- ⚠️ **但有三个实际代价**：
  1. 成本翻倍（AI + news-fetch）；
  2. 当天最终采纳的是**后跑那次**的结果，前一次白跑；
  3. 两次 AI 输出不同 → 同一天可能出现"两版推荐"，review 只看最后一版，中间态无意义。

---

## 6. 建议（不实施，供决策）

### 方案 A：只保留一个触发源（最省事，推荐）
- 如果外部定时服务比 GitHub schedule **更可靠** → 删掉 scan.yml 的 `schedule`，只留 `workflow_dispatch` 给外部服务调用。
- 如果 GitHub schedule 已经够用 → 别加外部服务。
- **理由**：幂等性只保证"不会坏"，不保证"不浪费"。

### 方案 B：双触发 + 加幂等守卫（推荐，如果你确实要双保险）
在 scan.py 开头（weekend 判断之后）加一个「今日已跑则跳过」守卫，两种实现任选：

1. **pending 文件存在即跳过**（最简单、零新文件）：
   ```python
   pending_today = f"us_stocks_pending_{get_us_time().strftime('%Y%m%d')}.csv"
   if os.path.exists(pending_today) and os.environ.get("SCAN_FORCE") != "1":
       print("今日已有 pending，跳过重复扫描")
       sys.exit(0)
   ```
   代价：想主动重跑时需设 `SCAN_FORCE=1`。

2. **运行标记文件**（更明确，但需处理"文件是否提交"）：
   写 `scan_last_run.txt`（内容 = 美股日期），存在且等于今天则跳过。
   注意：该文件会被 scan 的 git 提交一起推上去，需确认 review/portfolio 不受影响。

### 方案 C：外部服务"先探活再触发"（不动代码）
外部定时任务在触发前，先用 GitHub API 查当天是否已有成功的 scan run；有则跳过。
- 优点：零代码改动；缺点：依赖 API 可用性，且要处理鉴权。

### 我的倾向
**方案 B-1（pending 存在即跳过）** —— 一行判断、零新文件、与现有"pending 文件名带日期"的设计天然契合，且 `SCAN_FORCE=1` 保留了主动重跑能力。配合保留 GitHub schedule，就能实现真正的"双保险且只跑一次"。

---

## 附：速查

| 项 | 值 |
|---|---|
| scan.yml 主 job | `scan`（8 steps，cron `7 11 * * 1-5` = 北京时间 19:07） |
| news job | `needs: scan` + `uses: ./.github/workflows/news-fetch.yml` + `secrets: inherit` |
| 幂等键·snapshot | `Scan_Date\|Ticker` |
| 幂等键·price history | `Date\|Ticker`（不覆盖历史） |
| 幂等键·trade_history | `Ticker\|Date\|Tag` |
| 幂等键·BUY | `Ticker\|Rec_Date\|Tag\|BUY` |
| 「今日已跑」守卫 | **不存在** |
| lock 文件 | **不存在** |
| 周末跳过 | 有（`weekday() >= 5` → `sys.exit(0)`） |
| 邮件重复发送 | 不会（邮件已移除，scan.py:3950） |
