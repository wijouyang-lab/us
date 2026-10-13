# $50,000 组合买入价时点调查报告

> 调查日期：2026-10-09
> 结论一句话：**无后见之明（look-ahead bias）**。买入价 = 推荐日真实 Open（次日开盘价），不是 review 时点价。

---

## 1. trade_history.csv 字段结构

表头（仅列与买入价相关的关键字段）：

| 字段 | 含义 | 写入阶段 |
|---|---|---|
| `Date` | 推荐日（= Rec_Date = scan 日） | scan 产生推荐时 |
| `Ticker` | 标的 | scan |
| `Tag` | `Core_Dragon` / `Observation` | scan |
| `Price` | **正式买入价 = 推荐日真实 Open** | review（pending→trade_history 提升时写入） |
| `Close_Price` | 推荐日收盘价（仅展示/参考，与买入价分离） | review |
| `Status` | `Active` / 终态 | review 裁决 |
| `Exit_Date` / `Exit_Price` | 卖出终态 | review 裁决 |

**注意**：trade_history.csv **没有** `Entry_Price` / `Entry_Date` / `Rec_Date` 这三个字段。
- `Entry_Price` / `Entry_Date` 在 **`portfolio_50000_positions.csv`**（组合账本，由 `portfolio_50000.py` 生成）。
- `Rec_Date` 对应 trade_history 的 `Date` 字段。

---

## 2. process_buys 买入价来源

`portfolio_50000.py`：

| 位置 | 内容 |
|---|---|
| `:8`（模块 docstring） | 「买入价：直接取 trade_history.Price（= 推荐日真实 Open，项目正式定义）」 |
| `:217` | `load_recommendations` 读 `r.get("Price")` → `rec["Price"]` |
| `:321` | `price = rec["Price"]` ← **买入价唯一来源** |
| `:361` | `"Entry_Price": str(money(price))`，注释「买入价永久固定，之后永不更新」 |

**结论**：`process_buys` 的买入价 = `trade_history.Price`，**不引用任何 review 时点的实时价格 / 收盘价 / 实时 quote**。

---

## 3. 价格时点对齐：scan 盘前推荐 → review 盘后以「推荐日 Open」记账

**Cron（`grep cron:` 各 workflow）：**

| 工作流 | Cron（UTC） | 北京时间 | 美股时点（EDT） | 角色 |
|---|---|---|---|---|
| scan | `7 11 * * 1-5` | 19:07 | **07:07 盘前** | 生成推荐 → 写 `us_stocks_pending_YYYYMMDD.csv`（含 `Scan_Ref_Price`） |
| review | `23 22 * * 1-5` | 次日 06:23 | **18:23 盘后** | 提升 pending→trade_history + 跑 `portfolio_50000.py` 记账 |

**关键代码（`review.py:611-632`）**——pending 提升到 trade_history 时，买入价怎么定：

```python
pdx = target_map.get(ticker)          # 从推荐日 OHLC 取
op  = safe_float(pdx.get("open"))     # ← 正式买入价 = 推荐日 Open
cp  = safe_float(pdx.get("close"))    # ← Close 只作参考，与买入价分离
...
# :617-619 注释（关键护栏）：
# op（正式买入价 = 推荐日 Open）在盘前/盘中尚未产生时必须保持 None，
# 绝不 get_live_quote_bootstrap() 把实时价假装成 Open。Price 列随之留空，
# 由后续 Review 的 backfill_rec_price() 取得 Rec_Date 真实 Open 后幂等回填。
"Price": fmt_price(op)
```

**且 `review.py:437-444` 明确**：

```python
def safe_record_price(row):
    """正式买入价 = trade_history 的 Price 字段 = 推荐日真实 Open。
    禁止 fallback 到 Scan_Ref_Price / Close_Price / Prev_Close / 实时 quote。"""
```

**谁跑 `portfolio_50000.py`？** 不是 review.py 直接调用——是 **`review.yml` 工作流**在 review 脚本跑完后，单独执行一步 `python portfolio_50000.py --data-dir .`（review.yml:56）。它只读 trade_history 里的 `Price`（推荐日 Open），不接任何实时价。

---

## 4. 明确结论

### ✅ 无后见之明（look-ahead bias）

| 检查项 | 结论 |
|---|---|
| 买入决策时点 | **scan 盘前**（推荐在 07:07 ET 产生） |
| 买入执行价 | **推荐日真实 Open**（次日开盘价，9:30 ET 才产生） |
| 记账时点 | review 盘后（此时 Open 已可知，用真实 Open 记账） |
| 是否用 review 时点价 | **否**——代码显式禁止用实时 quote / Close 冒充 Open |
| 是否用当日收盘价 | **否**——`Close_Price` 单独存，仅参考，与 `Price` 分离 |

这是一个标准的「**盘前推荐 → 次日开盘成交**」模型：

1. 盘前（scan）决定买什么（这是决策，无后见）；
2. 开盘产生真实 Open；
3. 盘后（review）以**推荐日 Open** 记账（这是执行价，发生在决策之后，合法）。

后见之明只会在「用 review 时点价（收盘/盘后价）记账」时出现——而代码里有三重护栏杜绝了这一点（`safe_record_price` 的禁止清单 + `:617-619` 的 None 保持 + `Close_Price` 与 `Price` 分离）。

### 无问题，无需修复

---

## 5. 修复方向（仅当未来改了语义才需要，当前不实施）

仅记录防御性提醒，**当前代码不需要改动**：

1. **若**未来有人把 `process_buys` 改成读实时 quote / `Close_Price`，应立即回退——那会引入后见之明。
2. **若**未来把 scan 挪到盘后（与 review 同时或更晚），「推荐日 Open」仍合法（Open 在推荐之后），但需重新审视「盘前推荐」的语义是否仍成立。
3. 唯一可留意的**流程**细节：买入记账由 review 工作流触发（而非 scan 立即记账），但因为是按「推荐日 Open」记账、且幂等，**语义上等价于 scan 时点买入**，无偏差。若想更贴近「scan 买入」的心智模型，可将 `portfolio_50000.py` 移到 scan 工作流——但那样 Open 尚未产生，反而会更复杂，不推荐。

---

## 附：关键文件/行号速查

| 文件 | 行号 | 关键点 |
|---|---|---|
| `portfolio_50000.py` | :8, :217, :321, :361 | 买入价 = trade_history.Price，永久固定 |
| `review.py` | :437-444 | 正式买入价 = 推荐日真实 Open，禁止 fallback 实时价 |
| `review.py` | :611-632 | pending→trade_history，`Price = fmt_price(op)` |
| `review.py` | :617-619 | 盘前 Open 未产生时保持 None，幂等回填 |
| `review.yml` | :56 | `python portfolio_50000.py --data-dir .` |
| `scan.yml` | :8 | `7 11 * * 1-5`（盘前） |
| `review.yml` | :8 | `23 22 * * 1-5`（盘后） |
