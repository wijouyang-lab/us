# scan 首次真实运行失败：AI 输入字段缺失 KeyError —— 诊断与修复报告

> 生成时间：2026-10-09 21:46 (GMT+8)
> 修复 commit：`944673d`（已推送 `origin/main`）
> 改动范围：仅 `quant_filter.py` + `scan.py` + `tests/test_quant_filter.py`；未激活任何 flag，未碰监控与其他逻辑。

---

## 1. 诊断结论：缺哪些字段

`scan.py:2590` 的 `generate_ai_report` 在拼 prompt 时对以下字段做**硬索引**（`x['字段']`，缺失即 `KeyError`）：

| 硬索引字段 | 是否必备 | 说明 |
|-----------|---------|------|
| `x['Ticker']` | ✅ | `build_ai_input` 总会写入，不会缺 |
| `x['Name']` | ❌ 缺 → 崩溃 | 持仓行缺失（本次崩溃点） |
| `x['Price']` | ❌ 缺 → 崩溃 | 持仓行缺失 |
| `x['RSI']` | ❌ 缺 → 崩溃 | 持仓行缺失 |
| `x['乖离率(%)']` | ❌ 缺 → 崩溃 | 持仓行缺失 |
| `x['MACD趋势']` | ❌ 缺 → 崩溃 | 持仓行缺失 |
| `x['KDJ_J']` | ❌ 缺 → 崩溃 | 持仓行缺失 |
| `x['量比']` | ❌ 缺 → 崩溃 | 持仓行缺失 |

> 其余 prompt 字段（`Premarket_Price`、`MA20`、`Quant_Score`、`Fundamental_Score` 等都用 `x.get(..., default)`）是安全的，不会崩。

**根因（为什么持仓行缺这些字段）：**

- `build_ai_input(pool_data, positions, candidates)`（quant_filter.py:202）构造持仓行时逻辑是：`row = dict(pool_by.get(t) or {})`。
- `pool_by` 来自 `pool_data`（`build_stock_pool(get_scan_pool())` —— 即**扫描候选池**，由 `scan.py:3729-3731` 构造）。
- **持仓 Ticker（`load_positions`，scan.py:3755）并不在 `pool_data` 中** —— 持仓是经「角色重定义」后被强制塞进 AI 输入的，而扫描候选池只是正常扫描宇宙，不含持仓。
- 因此 `pool_by.get(t)` 对持仓返回 `None` → `row = {}`（空 dict），只被写入 `Ticker/Tag/_is_position`，**完全缺少 `Name/Price/RSI/乖离率(%)/MACD趋势/KDJ_J/量比`**。
- `generate_ai_report` 拿到这 4 个空持仓行后硬索引 `x['Name']` → `KeyError`，整次 scan 崩在 2590 行。日志 `持仓=4 / 严筛候选=0 / AI输入=4` 与此完全吻合：4 个 AI 输入全部是缺字段的持仓行。

---

## 2. 修复 diff

### 2.1 `quant_filter.py` —— `build_ai_input` 兜底补全必填字段（主修复）

新增常量，定义 prompt 硬索引的必填字段与默认值（默认 `"N/A"`，与 prompt 中 `x.get(..., 'N/A')` 约定一致）：

```python
AI_INPUT_REQUIRED_FIELDS = {
    "Name": "N/A", "Price": "N/A", "RSI": "N/A", "乖离率(%)": "N/A",
    "MACD趋势": "N/A", "KDJ_J": "N/A", "量比": "N/A",
}
```

持仓行与候选行在构造后统一 `setdefault` 兜底（命中 pool 则保留真实值，未命中则填 `N/A`）：

```python
row = dict(pool_by.get(t) or {})
row["Ticker"] = t
row["Tag"] = "Core_Dragon"
row["_is_position"] = True
for k, v in AI_INPUT_REQUIRED_FIELDS.items():
    row.setdefault(k, v)        # 持仓不在 pool_data 时也保证不缺字段
out.append(row)
# 候选行同样兜底
row = dict(c, Tag="Candidate")
for k, v in AI_INPUT_REQUIRED_FIELDS.items():
    row.setdefault(k, v)
out.append(row)
```

### 2.2 `scan.py` —— `generate_ai_report` 2590 行防御性兜底（双保险 / 极小适配）

把 8 个硬索引字段改为 `.get(..., "N/A")`：

```python
_name = x.get("Name", "N/A"); _price = x.get("Price", "N/A")
_rsi = x.get("RSI", "N/A"); _bias = x.get("乖离率(%)", "N/A")
_macd = x.get("MACD趋势", "N/A"); _kdj = x.get("KDJ_J", "N/A")
_vol = x.get("量比", "N/A")
pool_lines.append(
    f"[{x.get('Ticker','')}] {_name} | 昨收:${_price} | ... RSI:{_rsi} | Bias:{_bias}% | MACD:{_macd} | KDJ:{_kdj} | Vol:{_vol} ..."
)
```

> 两点修复职责分明：`build_ai_input` 是**数据契约层**（保证输出完整），`generate_ai_report` 是**消费防御层**（即便未来字段漂移也绝不整次扫描崩溃）。

---

## 3. 测试结果

- **本地验证场景**：构造「4 持仓 + 0 候选，且 4 持仓均不在 pool_data」的生产真实场景，跑 `build_ai_input` → 4 行全部含 8 个硬索引字段（默认 `N/A`），prompt 可正常拼装，**不再 KeyError**。
- **新增回归测试**（tests/test_quant_filter.py，3 个）：
  - `test_build_ai_input_position_not_in_pool_has_all_prompt_fields` —— 锁定「持仓不在 pool 时必须含全部 prompt 字段」（本次崩溃场景）。
  - `test_build_ai_input_position_in_pool_keeps_real_values` —— 持仓命中 pool 时保留真实值不被覆盖。
  - `test_build_ai_input_candidate_row_has_all_prompt_fields` —— 候选行同样兜底。
- **全量测试**：`pytest tests/` → **267 passed, 7 warnings**（基线 264 + 新增 3）。满足 ≥264 要求。
- **编译检查**：`python3.12 -m py_compile quant_filter.py scan.py` → OK。

---

## 4. commit SHA + push 结果

| 项 | 值 |
|----|----|
| 本地 commit | `944673d` fix(scan): guarantee AI-input rows carry prompt-required fields to stop KeyError |
| 改动文件 | `quant_filter.py` (+25/−1)、`scan.py` (+11/−1)、`tests/test_quant_filter.py` (+57) |
| rebase | 远端在推送前有 dashboard 刷新提交 `9eef1a2..98d26a4`；本 commit 在其之上干净 rebase（文件无交集，无冲突） |
| push | ✅ 成功：`98d26a4..944673d  main -> main` |
| 未激活 flag | 是（未碰 ENABLE_TARGET_FILE 等任何开关） |
| 未碰监控 / 其他逻辑 | 是（仅 3 个文件） |

---

## 5. 为什么测试没抓到（关键）

> 说明：本次基线实际为 **264 passed**（历史报告里曾出现 261，是早一个增量节点的计数；结论一致）。下面以「既有测试为何对本次崩溃全绿」作答。

既有测试 `test_build_ai_input_*` **用 `_pool()` 帮具构造 fixture，把持仓 Ticker 直接放进 pool 里**，例如：

```python
def _pool(tickers):
    return [{"Ticker": t, "Price": 100, "Final_Score": 95, "Sector": f"S{i}"} for i, t in enumerate(tickers)]

def test_build_ai_input_positions_at_least_three():
    pool = _pool(["AAA","BBB","CCC","DDD","EEE"])
    positions = ["AAA","BBB","CCC","DDD"]   # ← 持仓恰好也在 pool 里
```

三重掩盖，使 bug 在测试里永远不暴露：

1. **fixture 把持仓放进 pool**：`pool_by.get(t)` 能命中 → 持仓行是「完整 pool 行」而非空 dict，根本走不到「缺字段」分支。生产里持仓不在 pool，测试里却在，前提就不一致。
2. **测试只断言 Ticker/Tag/_is_position**：从不检查 `Name/RSI/Price` 等 prompt 必填字段是否存在，缺口在测试层面不可见。
3. **测试完全不调用 `generate_ai_report`**：prompt 的硬索引 `x['Name']` 路径从未被任何单元测试执行，崩溃点本身没被覆盖。

> 一句话：测试用「持仓在 pool 内」的幸运 fixture + 不校验 prompt 字段 + 不跑 prompt 拼装，三重巧合把生产必现的 `KeyError` 完全屏蔽了。本次新增的 `test_build_ai_input_position_not_in_pool_has_all_prompt_fields` 正是补齐「持仓不在 pool」这一被遗漏的生产真实分支，并用字段完整性断言锁死契约。

---

## 下一步（手动验证）

push 后请到 **GitHub Actions → 美股盘中扫描 → Run workflow** 手动触发一次，确认 `🔎 [角色重定义] 持仓=4 / 严筛候选=0 / AI输入=4` 之后不再报 `x['Name'] KeyError`，并能正常进入 AI 报告拼装。
