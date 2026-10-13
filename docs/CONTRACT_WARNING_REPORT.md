# 契约告警实施报告 · Technical_Date（方案 A 告警版）

> **性质**：只读比对 + 日志输出
> **未改**：Technical_Date 的值、数据源调用方式、Scan 生产决策、Gate 逻辑
> **commit**：`efc23bfe270cace011ae49a7e3d7a7799a171d3c`（未 push）
> **测试**：**174 passed**（173 + 1 新增）

---

## 1. 设计说明：为什么不是"直接读 price history 最新日期"比对

你的原始要求是「读取 price history 的最新可得完成交易日，与 snapshot 的 Technical_Date 比对」。

**但直接这么做会产生必然误报**，原因是时序错位：

| 时刻 | price history 状态 |
|---|---|
| `scan.yml:49` 运行 scan.py 时 | 文件里只有**上一次运行**写入的数据（末端 = 上一交易日） |
| `scan.yml:54` 运行 quant_factor_price.py 之后 | 才更新到当前 |

所以在 scan 写入 snapshot 的那一刻，price history 一定比 snapshot 的 T **旧至少一个交易日** —— 直接比对会**每天都告警**，信号失去意义。

### 实际采用的做法

**把 price history 当"交易日历"用，而不是当"期望值"用**：

1. `cutoff` = 理论最后完成常规交易日（沿用 Scan 已有的 `_last_completed_regular_date_us()`，无需新逻辑）
2. 从 price history 读取**已知交易日集合**（`Date` 列去重），在其上取 `max(d for d in known if d <= cutoff)` 作为**期望日** —— 这样期望日一定落在真实交易日上
3. 若 `实际 T < 期望日` → **STALE**，并统计中间隔了几个**交易日**（用同一份日历精确计数）
4. 若 `实际 T > 期望日` → **AHEAD**（price history 尚未更新到该日，属正常，**不误报**）

> 这样既达到了"每天可见偏差是否发生、多大"的目的，又不会天天误报。

---

## 2. 校验代码位置（文件 + 行号）

### 2.1 纯函数（可测试、零副作用）

**`quant_factor_lab.py`** —— `check_technical_date_contract()`，位于 `write_factor_snapshot()` 之前。

```python
def check_technical_date_contract(technical_date, cutoff_date, trading_dates=None):
    """比对 snapshot 的 Technical_Date 与「理论最后完成交易日」，返回只读诊断。
    【严格只读】
        · 不修改 Technical_Date 的值
        · 不修改数据源 / 调用方式
        · 不阻断 snapshot 生成
        · 无任何文件写入、无网络请求
    """
```

内部辅助：`_norm_date()`（把 str/date/datetime 统一为 `datetime.date`）。

状态枚举：

| status | 含义 |
|---|---|
| `OK` | T == 理论最后完成交易日，契约成立 |
| `STALE` | T 早于理论值 → **触发告警** |
| `AHEAD` | T 晚于已知日历末端（history 未更新，**不告警**） |
| `NO_REFERENCE` | 缺 cutoff，无法判定 |
| `NO_DATA` | 缺 Technical_Date，无法判定 |

### 2.2 调用点（scan.py）

**`scan.py`** —— 位于 `write_factor_snapshot()` **之前**（原 3726-3731 区块内）：

```python
    snapshot_pool = pool_data
    pool_data = apply_entry_quality_gate(pool_data, market_ctx, event_regime)

    # ---- Quant 契约告警（只读比对 + 日志；绝不改值、绝不改数据源、绝不阻断落盘）----
    try:
        _cutoff = _last_completed_regular_date_us(get_scan_asof_us())
        _known_dates = []
        if os.path.exists(QUANT_PRICE_HISTORY_FILE):
            _ph = pd.read_csv(QUANT_PRICE_HISTORY_FILE, dtype=str, keep_default_na=False)
            if "Date" in _ph.columns:
                _known_dates = sorted({...})
        _t_dates = sorted({... Technical_Date ...})
        _diag = check_technical_date_contract(_t_dates[-1] if _t_dates else None,
                                              _cutoff, trading_dates=_known_dates)
        if _diag.get("status") == "STALE":
            print("⚠️ " + _diag["message"])
        else:
            print(f"[Quant Factor Lab][契约] Technical_Date=... status=...")
    except Exception as _cw_e:
        print(f"⚠️ [Quant Factor Lab] 契约告警校验异常（不影响落盘）：...")

    try:
        write_factor_snapshot(snapshot_pool, QUANT_FACTOR_SNAPSHOT_FILE, today_us_str())
```

配套新增：
- `scan.py:64` 常量 `QUANT_PRICE_HISTORY_FILE = "quant_factor_price_history.csv"`（注明"仅用于契约告警的只读比对，绝不写入"）
- `scan.py:47-51` 导入新增 `check_technical_date_contract`

---

## 3. Warning 格式

触发条件：`status == STALE`（实际 T 早于理论最后完成交易日）

**实际输出（用今日真实数据复现）**：

```
⚠️ [Quant Factor Lab][契约告警] Technical_Date=2026-10-05 早于理论最后完成交易日 2026-10-06，相差 1 个交易日。设计契约要求 Technical_Date = 最后完整常规交易日（见 quant_factor_price.py:10-16），本次未兑现。可能原因：get_kline_data() 使用单只 period="6mo" 下载，与 fetch_batch_prices() 的批量 start/end 下载存在数据新鲜度差异；也可能是该时点行情源尚未更新。建议：持续观测，先不改数据源，累积数日后判定是否为系统性滞后。本次不修改 Technical_Date、不阻断落盘。
```

**要求的四项要素齐备**：

| 要素 | 是否包含 | 片段 |
|---|---|---|
| ① Technical_Date 实际值 | ✅ | `Technical_Date=2026-10-05` |
| ② 理论/最新可得值 | ✅ | `理论最后完成交易日 2026-10-06` |
| ③ 相差交易日数 | ✅ | `相差 1 个交易日` |
| ④ 建议 | ✅ | `建议：持续观测，先不改数据源…` |

非 STALE 时输出一行 INFO（不告警）：

```
[Quant Factor Lab][契约] Technical_Date=2026-10-06 理论=2026-10-06 status=OK gap=0
```

---

## 4. 严格约束的落实验证

| 约束 | 落实方式 | 验证 |
|---|---|---|
| 不阻断 snapshot 生成 | 整段包在 `try/except`；告警后继续 `write_factor_snapshot` | 代码结构 + 测试 |
| 不修改 Technical_Date 的值 | 纯函数只返回诊断 dict，不回写 pool | 测试断言入参未被修改 |
| 不修改数据源调用方式 | 未触碰 `get_kline_data` / `yf.download` 任何参数 | **暂存 diff 检索 `period="6mo"` / `start=` / `end=` / `auto_adjust` → 0 命中** |
| 不修改 Scan 生产逻辑 | 只在写盘前插入一段只读比对 + print | diff 仅 3 处（导入、常量、调用块） |
| 不修改 Gate 逻辑 | 未触碰 `apply_entry_quality_gate` | diff 未涉及 |
| 只加只读比对 + 日志 | 纯函数无文件写入、无网络 | 测试：调用后临时目录文件数不变 |

---

## 5. 测试

新增 **1 个测试函数**：`tests/test_quant_factor_lab.py::test_technical_date_contract_warning`

**遵守"不硬编码绝对日期"约束** —— 全部用 `pandas.bdate_range` 动态生成日历，按相对位置取日期（`cal[-1]` / `cal[-2]` / `cal[-3]`）。

覆盖 8 组断言：

| # | 断言 | 结果 |
|---|---|---|
| 1 | 滞后 1 个交易日 → `STALE`，`gap=1`，`expected=理论值` | ✅ |
| 2 | warning 含实际 T / 理论值 / 相差交易日数 / 建议 / 契约出处 | ✅ |
| 3 | 滞后 2 个交易日 → `STALE` 且 `gap=2`（可区分滞后幅度） | ✅ |
| 4 | 契约成立 → `OK`，`gap=0` | ✅ |
| 5 | T 晚于日历末端 → `AHEAD`，**不误报为 STALE** | ✅ |
| 6 | 无 price history 参考时降级为自然日差，仍可判定且不崩溃 | ✅ |
| 7 | 缺输入 → `NO_DATA` / `NO_REFERENCE`，不崩溃 | ✅ |
| 8 | **只读性**：不修改入参 `trading_dates`；调用后临时目录文件数不变 | ✅ |
| 9 | 确定性：同输入两次调用结果一致 | ✅ |

### 全量测试

```
$ python3 -m pytest -q
174 passed, 2 warnings in 11.03s
```

**173 → 174（+1），符合 ≥174 要求，0 regression。**

---

## 6. `git diff --stat`

```
 quant_factor_lab.py            | 116 +++++++++++++++++++++++++++++++++++++++++
 scan.py                        |  38 +++++++++++++-
 tests/test_quant_factor_lab.py |  67 ++++++++++++++++++++++++
 3 files changed, 220 insertions(+), 1 deletion(-)
```

明细：
- `quant_factor_lab.py` +116：纯函数 `check_technical_date_contract` + `_norm_date` + 文档
- `scan.py` +38/-1：导入 +4、常量 +2、调用块 +32
- `tests/test_quant_factor_lab.py` +67：1 个测试 + 注册到 `_tests` 列表

### Commit

```
efc23bfe270cace011ae49a7e3d7a7799a171d3c
feat(quant): add Technical_Date contract warning (read-only)
```

（提交前已 `git fetch` + `merge --ff-only` 同步上游 12 条 dashboard-data 刷新，分支与 origin/main 对齐）

---

## 7. 一处需要你知道的技术细节

`scan.py` **无法用本机 Python 3.11 编译** —— 报 `SyntaxError: f-string expression part cannot include a backslash`（scan.py:2503）。

**这是既有问题，与本次改动无关**：
- 用 `git show HEAD:scan.py`（改动前版本）在 3.11 下编译，同样失败（行号 2497，差 6 行正是我新增的行数）
- 成因：scan.py 里有 PEP 701 风格的 f-string（f-string 表达式内含反斜杠），仅 Python 3.12+ 支持
- **生产 workflow 用的正是 3.12** → `python3.12 -m py_compile scan.py quant_factor_lab.py` **通过** ✅

所以本机全量 pytest 不覆盖 scan.py（它从未被测试引入），但生产侧编译无虞。

---

## 8. 一个重要提醒：告警要生效必须 push

契约告警代码目前**只 commit 未 push**。而 `scan.yml` 从 `origin/main` 运行 —— 因此：

> **10-08（周四）13:07 UTC 的那次 Scan 不会执行这段代码。**

好消息是：10-08 的判决可以**纯只读**完成 —— 我已在 10-08 观测器里内置同样的判定逻辑（比较新 snapshot 的 Technical_Date 与 price history 末端 + 理论值），不依赖告警是否上线。

若你希望 10-08 当天就在生产日志里看到告警行，需要在 **10-08 13:07 UTC 之前** push 这个 commit。按你"先 commit 不 push"的指令，我没推 —— **请你决定是否要我为生效而提前 push**。

---

## 9. 后续

- 10-08 观测器已启动：`PID 536931`，日志 `/tmp/scan_1008_monitor.log`
- 它将自动记录新 snapshot 的 `Technical_Date`、price history 末端、是否含该日期，并给出四选一判决
- STEP 4–8（Phase 3–7 补测）随后推进，带两条约束

---

*契约告警报告 · commit 1（`efc23bfe`）· push 0 · 未重跑 snapshot · 未 backfill*
