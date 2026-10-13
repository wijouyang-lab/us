# 宏观板块（ENABLE_MACRO_PANEL）激活清单

> 生成日期：2026-10-11 21:15（GMT+8）｜ 性质：**激活操作手册（只读调研 + 操作步骤），未改任何文件、未激活 flag**
> 数据源：`scan.py`（L1791-1963）、`dashboard_export.py`（L2891-2915, L3212-3213）、`scan.yml`（L40-48, L112-116）

---

## 1. 前置检查（代码现状）

| 检查项 | 位置 | 现状 |
|---|---|---|
| scan.py 读取 flag | `scan.py:1812` `return os.environ.get("ENABLE_MACRO_PANEL") == "1"`（函数 `macro_panel_enabled()`） | ✅ 已实现，读**环境变量** |
| scan.py 落盘调用 | `scan.py:3908-3913` `if macro_panel_enabled(): try: write_macro_data(...) except ...` | ✅ 已实现，失败不阻断 scan |
| 经济/讲话 payload 构造 | `scan.py:1863-1884` `_build_macro_payload` | ✅ 已有（经济指标 dict + 讲话列表） |
| 单批次 AI 判断 | `scan.py:1887-1939` `_macro_ai_judge`（**1 次**批量调用，max_tokens=2000） | ✅ 已实现；失败 → 所有 `sentiment=null` |
| dashboard 读取 | `dashboard_export.py:2891-2913` `build_macro(data_dir)`（文件缺失→`None`） | ✅ 已接线，缺失则前端隐藏板块 |
| dashboard 注入 | `dashboard_export.py:3212-3213` `macro = build_macro(data_dir)` | ✅ 已注入 payload |
| 密钥依赖 | `CLAWSOCKET_API_KEY` + `CLAWSOCKET_BASE_URL`（`scan.yml:43-44` 已注入 secrets） | ✅ 已配，无需新增 |
| **scan.yml env 注入 flag** | `scan.yml:40-48`（env 块） | ⚠️ **缺失**（见 §5 缺口） |

> ⚠️ **关键缺口（见 §5）**：`scan.yml` 的 scan 步骤 env 块只注入了 `ENABLE_TARGET_FILE` 与 `ENABLE_SCAN_BUY_DECISION`，**没有**把 `ENABLE_MACRO_PANEL` 注入给 `scan.py`。`scan.py:1812` 读的是环境变量，若 scan.yml 不传，`os.environ.get(...)` 永远为 `None` → **宏观面板永远不激活**。

---

## 2. 激活步骤（逐条，**含必需但缺失的 scan.yml 接线**）

> 与最初设想不同：仅建 repo variable **不够**。必须同步在 `scan.yml` 注入 env（保持 repo-variable 门控，未设即关）。

1. **改 `scan.yml` env 块**（在 L47 `ENABLE_SCAN_BUY_DECISION: ${{ vars... }}` 之后加一行）：
   ```yaml
             ENABLE_MACRO_PANEL: ${{ vars.ENABLE_MACRO_PANEL }}
   ```
   → 这样 repo variable 未设时该值为空 → scan 走旧路径；设了才激活（与 `ENABLE_SCAN_BUY_DECISION` 同款门控语义，无硬编码 `"1"`）。
2. **GitHub → Settings → Variables → New repository variable**：
   - Name: `ENABLE_MACRO_PANEL`
   - Value: `1`
3. **等下次 scan 跑**（下一交易日 **21:00 北京**，scan.yml 的 scan 步骤触发）。
4. **验证 A（数据落库）**：`macro_data.json` 是否出现在 `origin/main`：
   ```bash
   git ls-files | grep macro_data.json          # 应存在
   git show origin/main:macro_data.json | head  # 看 economic[] / speakers[] 是否非空
   ```
5. **验证 B（前端显示）**：Dashboard 刷新后"宏观"板块（`index.html #macroCard`，`app.js renderMacro`）是否渲染经济指标网格 + 讲话列表。若 `macro_data.json` 缺失则板块隐藏（不报错）。

---

## 3. 预期 token 成本（单批次调用）

- **调用次数**：每次 scan **仅 1 次** AI 调用（所有经济数据 + 讲话合并为一个 prompt，`scan.py:1897-1911`）。
- **输入条目数**：`economic`（来自 `economic_structured` 指标 dict，典型 ~6–10 条：CPI/PCE/核心通胀/非农/失业率/联邦基金利率等）+ `speakers`（关键人物讲话，典型 ~3–8 条）≈ **合计 N+M ≈ 10–18 条**。
- **token 估算**：
  - 输入：系统规则 ~300 tok + 每条 `(指标:值,前值,来源)` ~50–70 tok ⇒ ≈ **0.9K–1.5K 输入 token**。
  - 输出：`{"items":[...]}` 每条 `sentiment`+`rationale≤30字` ~40 tok ⇒ ≈ **0.4K–0.8K 输出 token**。
  - `max_tokens` 上限 2000（实际远用不满）。
  - **单次 scan ≈ 1.5K–2.5K token**。
- **频率**：每周 5 个交易日各跑 1 次 scan ⇒ **~5 次/周，~22 次/月**。
- **成本估算（¥）**：ClawSocket 经代理转发 `claude-opus-5-5`，单价以代理费率为准（本仓库无公开单价）。按 opus 参考价（$15/1M 输入 + $75/1M 输出）粗略折算：
  - 单次 ≈ 2K tok ⇒ ≈ **$0.03–0.06/次** ⇒ **≈ ¥0.2–0.5/次（汇率 ~7.2）**。
  - 月度 ≈ **¥4–11/月**（极低，主要成本在既有的 signal/market 分析 AI 调用，宏观增量可忽略）。

> 此估算为上限；实际 `rationale` 多为短中文，`sentiment` 失败置 `null` 不重试，真实开销更低。

---

## 4. 回滚

| 方式 | 操作 | 影响 |
|---|---|---|
| **软回滚（首选）** | ① 删 repo variable `ENABLE_MACRO_PANEL`；② 撤销 §2 第 1 步的 `scan.yml` env 改动（或保留——未设变量即失效） | 下次 scan 不再落盘 `macro_data.json`；前端板块自动隐藏（缺失→`None`）。零代码回滚 |
| **硬回滚** | `git revert <宏观相关 commit>`（`scan.py` 宏观落盘 + `dashboard_export` 注入 + `app.js` 渲染 + 测试） | 产生新提交，彻底移除功能 |

> 软回滚即可，无需 revert。

---

## 5. 风险与缺口

1. **⚠️ 接线缺口（最高优先）**：如 §1/§2 所述，`scan.yml` 未注入 `ENABLE_MACRO_PANEL` env → 仅建 variable 无法激活。**必须先补 scan.yml env 行**（已列入第 2 步第 1 条）。
2. **AI 判断失败 → 不崩**：`_macro_ai_judge` 异常捕获后所有 `sentiment=null`、`rationale=null`（`scan.py:1937-1939`），前端按"无判断"展示；`write_macro_data` 外层 `try/except` 失败也不阻断 scan（`scan.py:3909-3913`）。** fail-closed，安全**。
3. **token 超预算**：若实测开销超出预期，直接删 repo variable 关 flag 即可；宏观为纯展示增强，关闭不影响选股/交易主链路。
4. **数据新鲜度**：`macro_data.json` 由 scan（21:00 北京）落盘，Dashboard 每 15 分钟刷新读取；若某日 scan 失败，前端读到的是上一期（或缺失隐藏），无崩溃。

---

## 附：铁律确认
- 本文件为**操作手册草稿**；`scan.yml` / `scan.py` / `dashboard_export.py` **未改动**、未激活 flag；
- 未执行 `git push` / `git rebase`；未调用任何 AI。
