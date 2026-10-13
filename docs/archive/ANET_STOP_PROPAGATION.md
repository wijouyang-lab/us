# ANET STOP_TRIGGERED 写回与账本消费溯源报告（只读调查）

> 调查对象：review 日志 ANET `Trigger=STOP_TRIGGERED Exit=210.24`，但 `portfolio_50000_positions.csv` 中 ANET 仍 `Status=OPEN`。
> 怀疑点：dry-run / 时序 / 读写不同文件。
> 调查方式：纯只读（`git fetch` / `git show` / Read / 一次性 Python 校验脚本），未改动任何代码、未 push、未碰监控。

---

## 0. 结论速览

- **review 确实把 `Stop_Loss_Hit` 写回了生产 `trade_history.csv`**（origin/main）。→ 排除了"未写回/无害（A）"。**没有 dry-run 守卫**。
- review 与账本在 `review.yml` 的**同一个 job** 内先后运行（先 `review.py` 写、后 `portfolio_50000.py` 读），读的是**同一份** `trade_history.csv`。→ 排除了"读写不同文件（C 的狭义版）"。
- **账本没卖的真正原因：推荐键（Recommendation_ID）格式不一致导致 `process_sells` 匹配失败、静默跳过。**
  - 仓位行存储的 `Recommendation_ID` = `ANET|2026-10-07|Core_Dragon`（**日期，无时分秒**）。
  - `load_recommendations` 用 trade_history 的 `Date`（= `2026-10-07 00:00:00`，**带时分秒**）拼键 → `ANET|2026-10-07 00:00:00|Core_Dragon`。
  - 二者不相等 → `recs.get(rid)` 返回 `None` → `process_sells` 走 `if not rec: continue` → **永不卖出**。
- **判定：C（数据链断裂）**，但断裂点是"同一份文件内键格式不一致"，而非"两个不同文件"。属于潜伏的、影响所有同格式仓位的系统性 bug。

---

## 1. 生产 trade_history 里 ANET 当前 Status / Exit_Price

`git fetch origin` 后 `git show origin/main:trade_history.csv | grep ANET`：

```
2026-10-07 00:00:00,ANET,...,动态持有,209.36,MA20/MA50 + ATR + MACD/KDJ,209.36,2026-10-12,210.24,Stop_Loss_Hit,...,STOP_TRIGGERED,2026-10-12,0.3,今日最低价 210.18 已触及/跌破移动止损 210.24；次日 Scan 禁止重新推荐。,
```

| 字段 | 值 |
|------|-----|
| `Status` | **`Stop_Loss_Hit`**（不是 Active） |
| `Exit_Date` | `2026-10-12` |
| `Exit_Price` | **`210.24`** |
| `Review_Risk_Status` | `STOP_TRIGGERED` |
| `Review_Risk_Note` | 今日最低价 210.18 已触及/跌破移动止损 210.24 |

**判定：生产 trade_history 确实是 `Stop_Loss_Hit`**。review 那次触发**已写回生产**，并不是 dry-run 漏写。

---

## 2. review 写回的条件（有没有 dry-run 守卫）

写回调用点：`review.py:1848`
```python
update_trade_history_status(ticker, rec_date_str, "Stop_Loss_Hit", exitp)
```

函数本体：`review.py:1450-1469`
```python
def update_trade_history_status(ticker, buy_date, new_status, exit_price):
    if not os.path.exists(TRADE_HISTORY): return          # 仅文件不存在时跳过
    d = pd.read_csv(TRADE_HISTORY, dtype=str, keep_default_na=False)
    ...
    mask = (Ticker==ticker) & (Date[:10]==buy_date[:10]) & (Status=="Active")
    if mask.any():
        d.loc[mask,"Status"]    = new_status      # Stop_Loss_Hit
        d.loc[mask,"Exit_Date"] = REVIEW_SESSION_DATE
        d.loc[mask,"Exit_Price"]= str(exit_price) # 210.24
        d.to_csv(TRADE_HISTORY, index=False, ...) # 直接落盘
```

- **没有 dry-run / `if not WRITE` / 开关类守卫**（全仓 `review.py` 搜 `dry_run` 无命中）。
- 唯一前置条件：当前行 `Status == "Active"`（写完即变为 `Stop_Loss_Hit`，重跑不会覆盖）。
- `TRADE_HISTORY = "trade_history.csv"`（`review.py:379`，相对工作目录）。
- 写入的是**本地工作区文件**；随后由 `review.yml` 的提交/推送步骤（`git add trade_history.csv` → commit → rebase → push）入库。origin/main 已含该变更，证明写回+推送成功。

> review.yml 当次 env（`review.yml:51-52`）为 `CLAWSOCKET_LIVE_MODEL: gpt-6-astra`（此前的临时调试改动）+ `ENABLE_AI_REASON_BACKFILL=1`。**无任何 dry-run 相关 flag**。

---

## 3. 账本消费的路径与文件名

消费函数：`process_sells`（`portfolio_50000.py:384`）
```python
def process_sells(positions, transactions, recs, today):
    for p in positions:
        if p["Status"] != "OPEN": continue
        rid = str(p.get("Recommendation_ID", ""))      # ← 仓位行存的 RecID
        rec = recs.get(rid)                            # ← 用 RecID 查 recs
        if not rec: continue                           # ← 查不到就静默跳过！
        if rec["Status"] not in TERMINAL_STATUSES: continue   # 含 "Stop_Loss_Hit"
        exit_px = rec["Exit_Price"]; exit_date = rec["Exit_Date"]
        ... 卖出逻辑（SELL @ exit_px） ...
```

推荐来源：`load_recommendations`（`portfolio_50000.py:350-372`）
```python
def load_recommendations(data_dir):
    rows = read_csv_rows(data_dir / "trade_history.csv")   # 同文件名
    for r in rows:
        rid = rec_id_of(ticker, r["Date"], tag)            # ← 用 trade_history 的 Date（带时分秒）
        out[rid] = {... "Status":..., "Exit_Price":...}
# rec_id_of = f"{ticker}|{rec_date}|{tag}"   （portfolio_50000.py:241）
```

- **文件名/路径**：账本读 `data_dir / "trade_history.csv"`，`--data-dir` 默认 `"."`（`portfolio_50000.py:884`）。review 写 `TRADE_HISTORY="trade_history.csv"`（相对 cwd）。**同一文件名、同一工作目录**——在 `review.yml` 同一 job 内先写后读，**不是两份不同文件**。

### 3.1 关键断裂点（已用一次性 Python 脚本验证）

```
POSITION    Recommendation_ID        = 'ANET|2026-10-07|Core_Dragon'        # 日期，无时分秒
TRADE_HISTORY Date                   = '2026-10-07 00:00:00'               # 带时分秒
RECS key (load_recommendations)      = 'ANET|2026-10-07 00:00:00|Core_Dragon'
MATCH?  False
```

`recs.get('ANET|2026-10-07|Core_Dragon')` → `None` → `process_sells` 第 393 行 `continue` → **ANET 永远不会被卖出**，尽管 trade_history 已是 `Stop_Loss_Hit` + `Exit_Price=210.24`。

### 3.2 系统性（不止 ANET）

当前 4 个 OPEN 仓位的 `Recommendation_ID` 全部是**日期格式**（无时分秒）：
```
ADSK | Status=OPEN | RecID=ADSK|2026-10-07|Core_Dragon
ANET | Status=OPEN | RecID=ANET|2026-10-07|Core_Dragon
ISRG | Status=OPEN | RecID=ISRG|2026-10-07|Core_Dragon
KR   | Status=OPEN | RecID=KR|2026-10-07|Core_Dragon
```
即：**任何一个这些仓位若进入终态（Stop_Loss_Hit / Dropped / Period_Matured / …），账本都会因同样的键不匹配而静默漏卖。** 这是潜伏的系统性风险。

> 注：盘中机械止损（`portfolio_50000.py:684` `stop = dec(p.get("Stop_Loss"))`）走的是 `p.stop_loss` 字段、**不经过 rec 键**，所以那条 197.69 的机械线仍能工作；但 review 驱动的 `Stop_Loss_Hit` 退出路径因键不匹配已失效。当前 ANET 现价 216.74，既远离 197.69 机械线、又因键问题无法被 210.24 的移动止损线驱动卖出 → 实际"卡在 OPEN"。

---

## 4. 判断：A / B / C

| 场景 | 条件 | 是否符合 |
|------|------|----------|
| **A 无害** | 生产 trade_history 仍 `Active`（review 没写回） | ❌ 否。生产 = `Stop_Loss_Hit` + `Exit_Price=210.24`，已写回。 |
| **B 时序** | 生产 = `Stop_Loss_Hit` 但账本还没消费（时序/未跑到） | ⚠️ 非主因。review 与 portfolio 在**同一 job** 先写后读；且即使反复重跑，键不匹配也会**永久**跳过，不是"等下一次就消费"。 |
| **C 断裂** | 数据链断裂（键/格式不一致，账本无法消费） | ✅ 是。同一份 `trade_history.csv`，但 `load_recommendations` 拼的键（带时分秒）与仓位存储的 `Recommendation_ID`（日期）不一致 → `process_sells` 匹配失败、静默漏卖。 |

**最终判定：C（数据链断裂）** —— 精确说是"同文件内 Recommendation_ID 键格式不一致"，而非"生产/本地两份文件"。review 写回成功（A 排除）；不是单纯时序（B 排除）；根因是键不匹配导致账本消费失败（C）。

---

## 5. 修复方向（仅列出，不实施）

1. **统一 Recommendation_ID 键格式（治本）**
   - 推荐：`load_recommendations` 在拼键时把 `Date` 归一化为日期（`r["Date"][:10]` 或 `pd.to_datetime(...).date()`），与仓位存储的 date-only `RecID` 对齐。
   - 或反向：在历史 `portfolio_50000_positions.csv` 的 `Recommendation_ID` 补上 ` 00:00:00` 时间戳。优先"归一化键"，因为 positions 是持久状态、trade_history 的 Date 带时分秒是后期格式，改读取侧更稳。

2. **让消费失败可见（防静默漏卖）**
   - `process_sells` 对 `rec is None` 的 OPEN 仓位**打印告警**（而非直接 `continue`），并在出现 `Stop_Loss_Hit` 等终态却无对应 rec 时可选择 fail，避免"已落库却从未成交"无人察觉。

3. **对账 + 批量修复**
   - 扫描所有 `OPEN` 持仓，凡 `Recommendation_ID` 无法在 `recs` 命中者，列出并修复；否则任一终态都不会被账本执行。当前 4 个 OPEN 仓位全部命中此问题。

4. **补端到端断言**
   - 在 review→portfolio 同 job 内加一道校验：review 写回 `Stop_Loss_Hit` 后，`portfolio_50000.py` 应产出对应 `SELL` 流水；若无则使 job 失败，防止再次静默漏卖。

5. **区分两套退出路径**
   - 明确：盘中机械止损（197.69）走 `p.stop_loss`、不经过 rec 键，仍有效；review 驱动的 `Stop_Loss_Hit` 退出（210.24 一带）经 rec 键、当前已失效。修复键问题后，210.24 这套移动止损才能真正驱动实际卖出。

---

## 附：关键定位清单

| 关注点 | 位置 |
|--------|------|
| 生产 trade_history ANET 状态 | `git show origin/main:trade_history.csv` → `Status=Stop_Loss_Hit, Exit_Price=210.24` |
| review 写回调用点 | `review.py:1848` |
| 写回函数（无 dry-run 守卫） | `review.py:1450-1469` |
| review 写回前置条件 | `review.py:1461`（当前 `Status=="Active"`） |
| review 写回文件路径 | `TRADE_HISTORY="trade_history.csv"`（`review.py:379`） |
| review→portfolio 同 job 顺序 | `review.yml:53`（review.py）→ `review.yml:59-65`（portfolio_50000.py） |
| 账本消费函数 | `process_sells`（`portfolio_50000.py:384`） |
| 消费匹配逻辑（漏卖点） | `portfolio_50000.py:391-393`（`recs.get(rid)` → `None` → `continue`） |
| 推荐读取与键构建 | `load_recommendations`（`portfolio_50000.py:350-372`）+ `rec_id_of`（`portfolio_50000.py:241`） |
| 账本读取文件名/路径 | `data_dir / "trade_history.csv"`，`--data-dir` 默认 `"."`（`portfolio_50000.py:884`） |
| 仓位存储 RecID 格式 | `portfolio_50000_positions.csv`：`ANET|2026-10-07|Core_Dragon`（日期，无时分秒） |
| 键不匹配验证 | 一次性 Python 脚本：`MATCH? False` |
| 系统性范围 | 4 个 OPEN 仓位 RecID 全部为 date-only 格式 |
| 机械止损（不受影响） | `portfolio_50000.py:684`（走 `p.stop_loss`，不经 rec 键） |
