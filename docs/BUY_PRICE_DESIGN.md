# 买入价时点设计文档

> 背景：当前"买入成交价"固定取**推荐日 09:30 ET Open**。
> 新需求：若 scan 在盘中完成，应按"完成时价"成交（更贴近真实可执行价格）。
> 本文档为**设计 + 改动半径分析**，不实施、不触碰仓库任何文件。

---

## 1. 现状

### 1.1 `trade_history.Price` 是什么
- scan 落盘推荐时，`trade_history.Price` 初始 = `0`（占位，`scan.py` 推荐写入段）。
- **正式买入价 = 推荐日（Rec_Date）真实 Open**，由 `review.py` 的 `backfill_rec_price`（`review.py:2488`）幂等回填。
- `safe_record_price`（`review.py:437`）**显式禁止 fallback 到实时价**：
  ```python
  # review.py:437 附近
  def safe_record_price(...):
      # 绝不以实时价 / 完成时价回填，保证价格口径与推荐时点一致
      ...
  ```
- 即便买入决策已前置到 scan（`ENABLE_SCAN_BUY_DECISION`，flag 门控），
  `process_buys` 仍读 `rec["Price"]`（= Rec_Date Open）。

### 1.2 scan 是否记录"完成时刻"
**没有。**
- `scan.py` 的 `RUN_ASOF_US`（`scan.py:152`）是**进程开始**的固定快照，用于避免抓取期间时间漂移。
- scan **不写任何"完成时间戳 / 完成价"**到任何输出（推荐 CSV / `ai_snapshot` / `ai_text_cache`）。
- 因此"scan 是什么时候完成的""完成时价是多少"在现有数据流里**不存在**。

### 1.3 `process_buys` 怎么用 Price
`portfolio_50000.py` 的 `process_buys`：`成交价 = rec["Price"]`，`成交日 = rec["Rec_Date"]`。
这条路径在迁移到 scan 后**不变**（仍读 `rec["Price"]`），只是执行入口从 review 变 scan。

---

## 2. 新方案

### 2.1 新增字段（scan.py 推荐写入 / 落盘）
在 `trade_history.csv` 增加两列（向后兼容，旧记录为空）：

| 字段 | 含义 | 写入时机 |
|---|---|---|
| `Scan_Completed_At` | scan 进程**完成**时刻（ET，ISO 带时区） | scan 末尾、所有抓取/AI 完成后 |
| `Scan_Completed_Price` | scan 完成时的实时价（仅当已开盘可取到） | scan 末尾，取该 ticker 的最新可得价 |

```python
# scan.py 末尾（所有抓取 / AI 决策完成后）
completed_at = get_us_time()                      # ET
for ticker in recommended_tickers:
    completed_price = fetch_latest_price(ticker)  # 需 yfinance / 缓存，注意 prepost
    write_field(trade_history_row[ticker],
                Scan_Completed_At=completed_at.isoformat(),
                Scan_Completed_Price=completed_price)
```

> ⚠️ 取"完成时价"的依赖：`fetch_latest_price` 需覆盖**盘前/盘中/盘后**。
> 现状 `prepost=True` 的抓取覆盖 04:00–09:30 / 16:00–20:00，但 **21:00–04:00 夜盘覆盖未知**
> （见 `23H_TRADING_IMPACT.md` §任务1 #4）——夜盘情景下取价会失败，需 fail-closed 回退 Open。

### 2.2 成交价选择规则
```python
def resolve_buy_price(rec):
    """成交价优先级：
    1. 若 scan 已完成且完成时刻 >= 09:30 ET（盘中/盘后）→ 用 Scan_Completed_Price
    2. 否则（盘前 / 夜盘 / 无完成记录）→ 用推荐日 Open（rec["Price"]）
    3. 任何异常（完成价缺失 / 负数 / 0）→ 回退 Open，绝不捏造
    """
    completed_at = parse_et(rec.get("Scan_Completed_At"))
    if completed_at is not None and completed_at.time() >= time(9, 30):
        cp = rec.get("Scan_Completed_Price")
        if isinstance(cp, (int, float)) and cp > 0:
            return cp
    return rec["Price"]   # Open fallback（现状行为）
```

### 2.3 规则映射表

| scan 完成时刻（ET） | 用价 | 说明 |
|---|---|---|
| `< 09:30`（盘前 / 夜盘） | **Open**（现状） | 盘前无可靠成交价，沿用推荐日开盘 |
| `>= 09:30`（盘中 / 盘后） | **完成时价**（新） | 贴近真实可执行价格 |
| 无 `Scan_Completed_At`（旧记录） | **Open**（现状） | 向后兼容 |

---

## 3. 改动半径

| 文件 | 改什么 | 风险 |
|---|---|---|
| **scan.py** | 进程末尾新增"完成时刻 + 完成价"记录；`trade_history.csv` 表头加 2 列；取价需 `prepost` 覆盖 | 中（新增抓取，注意夜盘 fail-closed） |
| **review.py** | `backfill_rec_price`（L2488）改判断：优先用 `Scan_Completed_Price` 当 `completed_at >= 09:30`，否则 Open；`safe_record_price`（L437）放开"完成价"白名单 | 中（回填语义变更，须同步改前端/历史口径文档） |
| **portfolio_50000.py** | `process_buys` 调 `resolve_buy_price(rec)` 取代直接 `rec["Price"]` | 低（纯读字段变更） |
| **trade_history.csv** | 加 `Scan_Completed_At` / `Scan_Completed_Price` 两列 | 低（向后兼容，旧行为空） |
| **dashboard_export.py** | 若前端展示"成交价来源"（Open vs 完成价），需透传标记 | 低（可选） |

### 3.1 历史数据影响（旧记录怎么办）
- 旧 `trade_history.csv` 记录**没有** `Scan_Completed_At` / `Scan_Completed_Price` 两列（或为空）。
- `resolve_buy_price` 第 2/3 分支保证：**缺字段 → 一律回退 Open**（= 现状行为）。
- **无需回填历史**：旧已成交记录的价格已固化在 `transactions.csv`，不受新字段影响；
  只有"未来新增的推荐"会走新规则。
- 建议在迁移 commit 里**显式**说明：历史 PnL / Stage 不重算（避免引入对账噪声）。

---

## 4. 测试方案

```python
# tests/test_buy_price_resolution.py
def test_premarket_completion_uses_open():
    rec = {"Price": 100.0, "Scan_Completed_At": "2026-12-07T08:00:00-05:00",
           "Scan_Completed_Price": 102.5}
    assert resolve_buy_price(rec) == 100.0      # 盘前完成 → Open

def test_intraday_completion_uses_completed_price():
    rec = {"Price": 100.0, "Scan_Completed_At": "2026-12-07T11:30:00-05:00",
           "Scan_Completed_Price": 103.1}
    assert resolve_buy_price(rec) == 103.1      # 盘中完成 → 完成时价

def test_afterhours_completion_uses_completed_price():
    rec = {"Price": 100.0, "Scan_Completed_At": "2026-12-07T17:00:00-05:00",
           "Scan_Completed_Price": 101.9}
    assert resolve_buy_price(rec) == 101.9      # 盘后完成 → 完成时价

def test_missing_completed_fields_falls_back_open():
    rec = {"Price": 100.0}                       # 无完成记录（旧数据）
    assert resolve_buy_price(rec) == 100.0

def test_bad_completed_price_falls_back_open():
    rec = {"Price": 100.0, "Scan_Completed_At": "2026-12-07T11:30:00-05:00",
           "Scan_Completed_Price": 0}            # 异常值
    assert resolve_buy_price(rec) == 100.0

def test_zero_completed_price_falls_back_open():
    rec = {"Price": 100.0, "Scan_Completed_At": "2026-12-07T11:30:00-05:00",
           "Scan_Completed_Price": -5}           # 负值
    assert resolve_buy_price(rec) == 100.0
```

**断言要点**：
1. 5 条边界（盘前/盘中/盘后/缺字段/坏值）价格选择正确。
2. 旧记录（无新字段）行为 = 现状（Open）。
3. 含 `process_buys` 集成测试：构造带新字段的 rec，断言 `transactions.csv` 写入价 = 期望值。

---

## 5. 实施时机

**周后**（等周一周二旧路径验证完）。原因：
- 与"买入决策迁移到 scan"（flag `ENABLE_SCAN_BUY_DECISION`）强耦合——
  scan 只有接管买入后，"完成时价"才有意义（否则 scan 不写账本，完成价无处落地）。
- 周一 / 周二必须走旧路径（铁律），本周内不碰。
- 建议顺序：先确认 `ENABLE_SCAN_BUY_DECISION` 周二激活后稳定 → 再排本方案。

---

## 6. 与 23h 交易的关系（提醒）

本方案**不依赖** 23h 交易，但 23h（2026-12-06）后"完成时价"的取价窗口会扩展：
- 夜盘（21:00–04:00）完成 → 按规则 `< 09:30` → 用 Open（与现状一致，安全）。
- 但夜盘取价需 `prepost=True` 覆盖 21:00–04:00（**静态无法判定**，见 `23H_TRADING_IMPACT.md`）。
- 若 12-06 前本方案已上线，夜盘完成价取不到 → fail-closed 回退 Open，不会出错。

---

## 7. 附：铁律确认
- 本文为设计文档，**仓库 `/tmp/us` 零改动**。
- 未运行任何会修改数据的 `.py`（仅只读查看 `review.py:437/2488`、`scan.py:152`）。
- 未调用 AI。今晚 21:00 scan 与周二 06:23 review 不受影响。
