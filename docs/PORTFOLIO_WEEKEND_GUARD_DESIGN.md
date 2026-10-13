# `portfolio_50000.py` 周末守卫设计文档

> 背景：今日（周一）review TEST RUN 暴露——`review.py` 有周末守卫（美东周末 → `sys.exit`），
> 但账本执行器 `portfolio_50000.py` 的 `run()` **没有**周末守卫，美东周末会照常跑。
> 本文档为**设计 + 修法对比**，不实施、不触碰仓库任何文件。

---

## 0. 现状澄清（重要，纠正一个预设）

任务预设是"review 有守卫、scan 无守卫、portfolio 无守卫"。**实测与预设有一处出入**：

| 模块 | 周末守卫 | 位置 | 行为 |
|---|---|---|---|
| `review.py` | ✅ 有 | L96-97 | `if get_us_time().weekday() >= 5: print(...); sys.exit(0)` |
| `scan.py` | ✅ **有**（预设以为无） | L179-180 | `if get_us_time().weekday() >= 5: print(...); sys.exit(0)` |
| `portfolio_50000.py` 的 `run()` | ❌ **无** | — | 无任何 weekday 检查 |

> ⚠️ 结论：**`portfolio_50000.py` 是唯一的缺口**。scan 与 review 在入口都拦了周末，
> 但 `portfolio_50000.py` 由 `review.yml` 作为**独立 step** 调起（`python portfolio_50000.py --data-dir .`），
> review 的 `sys.exit` 不会阻止后续 step，于是周末仍会执行账本写入与 commit。
> （`scan.py` 的守卫是它自己跑 scan 时用的，与 portfolio 无关，本次不删、不碰。）

---

## 1. 问题

### 1.1 现状
- `review.py`：L96-97 周末 `sys.exit(0)`。
- `scan.py`：L179-180 周末 `sys.exit(0)`。
- `portfolio_50000.py`：`run()` 内 **只有** `intraday-stop` 模式的时段守卫（L648-655，仅拦"非交易时段 09:30–16:00 ET"），**没有周末 / 节假日守卫**。

### 1.2 后果（周末跑 portfolio）
`run()` 会照常执行：
- `process_sells`（卖出裁决）
- `process_buys`（**买入决策 + 账本写入**）← 风险点
- `mark_to_market` + 写回 `positions.csv` / `transactions.csv` / `history.csv` / `meta.json`
- 若 `review.yml` 后续有 `git add` + commit → **产生周末 commit**

> 周末美股休市，任何"买入"都不可能真实成交；但账本会记录一笔"买入"，
> 直到下一个交易日 Review 才发现无法成交 → 数据与真实持仓脱节。

### 1.3 本次为何无害
**被 80% 天花板拦住。** `portfolio_50000.py` 的 `_within_alloc`（四维占比预审，L210-218）：

```python
# L217-218
if proj_stock > equity * Decimal("0.80"):
    return False, "总股票将超 80%"
```

当前组合股票占比已高（接近 80% 上限），周末即便走到 `process_buys`，
新买入会触发 `_within_alloc` 返回 `False` → **不实际买入**。
所以本次 weekend run 没有产生错误持仓——**但仍是"侥幸"**：

- 一旦某次 Review 卖出腾出空间、或新增候选触发，`process_buys` 就会**真买入**；
- 周末 run 仍会执行 `process_sells`、写 `meta.json`、并产生**空 commit**（噪音）。

> ✅ 结论：**本次无害 ≠ 永远安全**。缺口必须补。

---

## 2. 修法对比（3 种）

### 方案 A —— `run()` 顶部加周末检查（**推荐**）

```python
def run(data_dir, offline=False, price_only=False, intraday_stop=False,
        buy_only=False, no_buy=False) -> dict:
    # 周末美股休市：账本不执行任何买卖 / 写回 / commit（与 review.py / scan.py 一致）
    if get_us_time().weekday() >= 5:
        print(f"[{get_us_time()}] 周末休市，portfolio 账本自动跳过。")
        return {}
    ...
```

| 维度 | 评估 |
|---|---|
| 安全性 | ⭐⭐⭐ 全局兜底，任何调用路径（review step / 手动 / CI）都拦 |
| 误伤风险 | 极低——只在 Sat/Sun 跳过，工作日逐字节一致 |
| 改动半径 | 小（~3 行 + 复用 `get_us_time`） |
| 一致性 | 与 review.py / scan.py 用同一 `get_us_time().weekday() >= 5` 判定 |

### 方案 B —— `process_buys` 内加周末检查

```python
def process_buys(positions, transactions, recs, meta, today):
    if get_us_time().weekday() >= 5:
        return ["[weekend] 周末休市，跳过买入决策"]
    ...
```

| 维度 | 评估 |
|---|---|
| 安全性 | ⭐⭐ 只拦买入，**不拦卖出**（周末卖出同样无法成交） |
| 误伤风险 | 同 A，但半拦截——卖出周末仍会跑 |
| 改动半径 | 小 |
| 问题 | 卖出也应拦；且周末卖出在账本上同样造成"假成交" |

### 方案 C —— `review.yml` 条件包裹

```yaml
      - name: 更新 $50,000 Portfolio Ledger
        run: |
          TZ=America/New_York
          DOW=$(date +%u)   # 1=Mon ... 7=Sun
          if [ "$DOW" -le 5 ]; then
            python portfolio_50000.py --data-dir .
          else
            echo "周末休市，跳过 portfolio 账本"
          fi
```

| 维度 | 评估 |
|---|---|
| 安全性 | ⭐⭐⭐ 在 CI 层拦截 |
| 误伤风险 | 中——**GitHub runner 默认 UTC**，必须显式 `TZ=America/New_York`，否则时区错判 |
| 改动半径 | 改 workflow（YAML），不碰 .py |
| 问题 | 仅保护 review.yml 路径；手动跑 `python portfolio_50000.py` 仍会绕过 |

### 2.1 对比结论

| 方案 | 拦买入 | 拦卖出 | 拦手动跑 | 时区安全 | 推荐度 |
|---|---|---|---|---|---|
| A（run 顶部） | ✅ | ✅ | ✅ | ✅ ET 内判 | ⭐⭐⭐ |
| B（process_buys） | ✅ | ❌ | ✅ | ✅ ET 内判 | ⭐⭐ |
| C（workflow） | ✅ | ✅ | ❌ | ⚠️ 需 TZ | ⭐⭐ |

**选 A**：最不易误伤、覆盖所有调用路径、且与 review/scan 用同一判定函数。
B 可作为 A 的补充（双保险），但不是首选。C 不推荐（时区坑 + 漏手动）。

---

## 3. 周末定义

### 3.1 "美东周末"如何判断
```python
get_us_time().weekday() >= 5     # Sat=5, Sun=6
```
- 与 `review.py:96` / `scan.py:179` **完全一致** → **必须复用，禁止三处各写一遍**（避免将来一处改、两处漏）。
- 基于 `America/New_York`（自动跟随夏令时），无手工 UTC 偏移。

### 3.2 节假日怎么办
**当前三个模块都不处理节假日**（只拦周末）。美国常规假期举例：
New Year, MLK, Presidents' Day, Good Friday, Memorial Day, Juneteenth,
Independence Day, Labor Day, Thanksgiving, Christmas。

- 节假日美股同样休市，但 `weekday() >= 5` **拦不住**（周一到周五的假期）。
- **本期不强制处理**：缺口与周末守卫正交，可单独立项（引入 `pandas_market_calendars` 或静态交易日列表）。
- 若要先堵，可在 A 的基础上扩展：
  ```python
  if get_us_time().weekday() >= 5 or is_us_market_holiday(get_us_time().date()):
      return {}
  ```
  但 `is_us_market_holiday` 需另建（本期不在范围内）。

---

## 4. 改动半径与副作用

### 4.1 改哪个文件、几行
- **`portfolio_50000.py`**：`run()` 顶部加 **~3 行**（方案 A）。
- 不碰 `review.py` / `scan.py`（它们已有守卫）。
- 不碰任何 workflow（方案 C 不采用）。

### 4.2 是否影响 `--price-only` / `--intraday-stop`

| 模式 | 当前行为 | 加守卫后 |
|---|---|---|
| 默认（`run()` 全跑） | 周末照常买卖 | 周末 `return {}`（跳过）✅ |
| `--price-only` | 只定价、不买卖（`L770-799`） | 周末也跳过定价。⚠️ 取舍：周末美股休市无新价，定价无意义 → 跳过合理，但若有"周末想刷新周五收盘市值"的需求则需例外 |
| `--intraday-stop` | 已有自身时段守卫（L648-655，`09:30–16:00 ET` 之外静默退出） | 周末本就不在 `09:30–16:00`，守卫已静默退出；加 A 后更早返回，行为一致 |

> **建议**：方案 A 放在 `run()` 最顶部（任何模式分支之前），保证三模式周末都安全。
> 若担心 `--price-only` 周末也跳过，可把守卫放在 `if price_only:` 之后、`if not buy_only:` 之前——
> 但那样 `--price-only` 周末会跑而默认模式跳过，不一致。**优先统一早退**。

---

## 5. 测试方案

```python
# tests/test_portfolio_weekend_guard.py
import importlib
from datetime import datetime
from unittest import mock

def _load_pf():
    spec = importlib.util.spec_from_file_location("pf", "portfolio_50000.py")
    return importlib.util.module_from_spec(spec)

def test_run_skips_saturday(monkeypatch):
    pf = _load_pf()
    monkeypatch.setattr(pf, "get_us_time", lambda: datetime(2026, 10, 10))  # Sat
    # 若 run() 早退返回 {}，则未触碰账本
    result = pf.run("/tmp/fake", offline=True)
    assert result == {}   # 或断言 process_buys 未被调用（mock 计数）

def test_run_skips_sunday(monkeypatch):
    pf = _load_pf()
    monkeypatch.setattr(pf, "get_us_time", lambda: datetime(2026, 10, 11))  # Sun
    assert pf.run("/tmp/fake", offline=True) == {}

def test_run_runs_weekday(monkeypatch):
    pf = _load_pf()
    monkeypatch.setattr(pf, "get_us_time", lambda: datetime(2026, 10, 12))  # Mon
    # 工作日：mock process_buys/process_sells 计数，断言均被调用
    ...

def test_guard_before_any_write(monkeypatch):
    # 关键：周末早退必须在 write_csv_rows / git add 之前
    # 断言周末 run 不调用任何 write_csv_rows（mock 验证）
    ...
```

**断言要点**：
1. 周末 `run()` 不调用 `process_buys` / `process_sells` / `write_csv_rows`（mock 计数 = 0）。
2. 周末 `run()` 返回空 dict / None（不落盘）。
3. 工作日 `run()` 行为与改动前逐字节一致（对照基线测试）。

---

## 6. 实施时机

**周二验证后**（等今晚 21:00 scan、周二 06:23 review 都跑完、确认旧路径正常）。
- 不应在今晚前改：避免影响今晚 scan / 周二 review 的旧路径（铁律：周一周二走旧路径）。
- 最小改动：方案 A 单 commit `fix(portfolio): skip ledger on US weekend`。
- 回滚：`git revert` 即可（纯加法式守卫）。

---

## 7. 附：铁律确认
- 本文为设计文档，**仓库 `/tmp/us` 零改动**（无新增 / 修改 / 提交 / 推送）。
- 未运行任何会修改数据的 `.py`（仅只读 grep / sed 查看）。
- 未调用 AI。今晚 21:00 scan 与周二 06:23 review 不受影响。
