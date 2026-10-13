# Pre-Weekend 组合体检：今晚 5 处改动的交叉风险

> 只读静态分析，**未运行任何 `.py`**，未改代码、未 push、未碰监控。
> 结论基调：今晚主改动（OHLCV 8 列）对 review/scan 路径零影响（已验证）；
> 但**早期累积改动**（intraday-stop + 激活 flag + quant-research 接 scan）的组合，暴露 2 个高危、3 个中危。

---

## 0. 故障面速览

| 编号 | 风险 | 严重度 | 是否今晚新引入 | 是否数据丢失 |
|---|---|---|---|---|
| H1 | quant-research.yml 的 `git push` 永远被拒（无 fetch/rebase/retry） | **高危** | 是（接 scan 后首次真实跑） | 是（研究产物丢失） |
| H2 | review 与 dashboard-data 争写 positions/transactions（整文件覆盖） | **高危** | 否（intraday-stop 加剧） | 可能（时序相关） |
| M1 | target 文件写了但 scan.yml 不提交 + dashboard-data 不读 | 中危 | 是（激活 flag 后） | 否（功能不显示） |
| M2 | dashboard-data 单条 `git add` 目标文件，首触发缺失会 fatal | 中危 | 否（潜在） | 可能（首触发） |
| M3 | quant-research `git add -A` 过宽（含 __pycache__/未跟踪） | 中危 | 是（接 scan 后） | 否（脏提交） |
| L1 | fetch_runtimes 实际在第 4 步（非预期的 6） | 低危 | 否 | 否 |
| L2 | OHLCV 8 列空值对各消费方安全 | 低危 | 否 | 否 |
| L3 | review 先 `git pull --ff-only` 再 rebase（冗余） | 低危 | 否 | 否 |

---

## 1. 高危隐患（数据丢失 / 功能失效）

### H1 · quant-research.yml 推送必然失败，研究产物丢失

**证据链：**
- `quant-research.yml:48-50`：提交/推送逻辑为
  ```yaml
  git add -A
  git diff --cached --quiet || git commit -m "..."
  git push
  ```
  **没有 `git fetch`、没有 `git rebase`、没有重试循环。**
- `scan.yml:163-166`：quant-research 是**独立 job**，`needs: scan` + `uses:`。
  `needs: scan` 意味着该 job 在 **scan job 全部步骤（含其 push）完成后**才启动。
- scan job（`scan.yml:120-125`）先 `git push origin HEAD:main` 成功，origin/main 已前进。
- quant-research job 通过 `checkout@v4` 拉的是**触发这次 run 的旧 SHA**（scan push 之前），
  其本地 `main` **落后于 origin/main 一个 scan 提交**。直接 `git push` → **non-fast-forward 被拒**。
- 被拒后无 rebase、无重试 → 该 job 以失败/未推送结束 → **本轮生成的 backtest/validation/walk-forward/shadow/production 全部产物随 runner 销毁丢失**。

**更严重**：`scan.yml` 同时触发 `news`（news-fetch.yml，带 3 次重试 + reset --soft）与 `quant-research`（无重试）。
二者几乎同时 push 到 main：news 的重试会成功，quant-research 不会 → **量化研究产物必丢，且每次都丢**。

**修复方向（只列不改）：**
1. 在 `git push` 前插入 `git fetch origin main && git rebase origin/main`（与 scan/review/news 同款模式）。
2. 加 3 次重试循环（仿 news-fetch.yml:56-73）。
3. 把 `git add -A` 换成**显式文件清单**（见 M3）。

---

### H2 · review 与 dashboard-data 争写 positions.csv / transactions.csv（整文件覆盖竞态）

**证据链：**
- `review.yml:83-88`：review 提交 `portfolio_50000_positions.csv` + `portfolio_50000_transactions.csv`
  （经 `python portfolio_50000.py --data-dir .` 写账本）。
- `dashboard-data.yml:151`：dashboard-data 提交**同样两个文件**（positions 由 price-only 写、transactions 由 intraday-stop 写）。
- 二者都走**整文件覆盖**（非 append/merge）。`portfolio_50000.py` 读已提交状态 → 重写 → 提交。
- 调度重叠：`review.yml:8` cron `23 22 * * 1-5`（周一~周五 22:23 UTC）；
  `dashboard-data.yml:16` cron `*/15 * * * 1-5`（周一~周五每 15 分，含 22:15 / 22:30 UTC）。
  → 周一~周五 22:xx 区间两 workflow 几乎必然并发。

**竞态场景：** 若 dashboard-data@22:15 的 intraday-stop 触发卖出（写 transactions.csv），
而 review@22:23 的账本更新基于**更早的远端基底**重写同一文件 → 后提交者整文件覆盖前者
→ 可能丢 intraday-stop 那一笔成交，或丢 review 的账本更新。取决于二者 rebase 到的最终基底。

**缓解：** 两 workflow 各自有 3~5 次 push 重试，且 `cancel-in-progress: false`（排队不取消），
实际同时进入 push 的概率有限；且 intraday-stop 仅 09:30–16:00 ET 触发（美东盘中），
22:23 UTC = 美东 18:23（盘后）→ **intraday-stop 在 review 时段本就不触发**。
→ 所以 transactions.csv 在 22:xx 的争写概率**极低**（盘后无止损触发）；
真正重叠的是 **positions.csv**（price-only 在盘后也跑、review 也写）。positions.csv 整文件覆盖风险同理，但因其内容为确定性账本（同基底重算结果一致），覆盖通常不丢信息。

**结论：** 理论高危，但受"盘后无 intraday-stop"与"确定性账本"双重抑制，实际风险低。
**修复方向（只列不改）：** 若要求零风险，可在 review 时段对 dashboard-data 的 price-only 步骤加互斥，
或在 positions/transactions 上改用 append+去重而非整文件覆盖（改动大，不建议本期做）。

---

## 2. 中危问题（噪音 / 警告 / 功能不显示）

### M1 · target 文件"写了却没接上"——端到端不可见

**证据链：**
- `scan.py:3957-3961`：flag=1 时调用 `write_portfolio_target_csv(...)`，**外层 try/except 包裹**（失败仅告警，不挂 scan）✅。
- `scan.yml:70-95`：scan job 的 commit 清单为
  `ai_text_cache / ai_snapshot / option_strategies / quant_factor_snapshot / quant_factor_price_history / us_stocks_pending_*.csv`
  → **不含 `portfolio_50000_target.csv`**。**scan 写了文件，但从不提交** → 文件停在 runner 工作区，下一轮 scan 整文件重写，永远到不了 main。
- `dashboard_export.py:2543`：仅当 `os.environ.get("ENABLE_TARGET_FILE") == "1"` 才 `_read_portfolio_target(...)`。
- `dashboard-data.yml:50-55`：该 workflow 的 env **只设** `DASHBOARD_AI_ENABLED / GITHUB_TOKEN / GITHUB_REPOSITORY`，**未设 `ENABLE_TARGET_FILE`**
  → 即便 target 文件已在 main 上，dashboard_export 也返回 `target=None` → 前端 `renderTarget()` 静默隐藏（app.js:485-486）。

**净效果：** 激活 flag 后，scan 每轮产出 target 文件但（a）不入库、（b）dashboard 不读 → **「AI 目标持仓」板块永远不会显示**。
- `app.js:485-486` 与 `dashboard_export.py:2418-2430` 对 null / 缺文件均**安全降级**（不崩溃）✅。

**修复方向（只列不改）：**
1. 在 `scan.yml` 的 commit 清单加入 `portfolio_50000_target.csv`（否则永远丢）。
2. 在 `dashboard-data.yml` 的 env 加 `ENABLE_TARGET_FILE: "1"`（让 export 真正注入 target）。
   二者缺一不可；只做其一仍不显示。

---

### M2 · dashboard-data 单条 `git add` 目标文件，首触发缺失会 fatal

**证据：** `dashboard-data.yml:151` 用单行 `git add ... portfolio_50000_transactions.csv`。
若某次运行时该文件尚不存在（如 intraday-stop 首次触发、且历史 review 从未落过该文件），
`git add` 未加 `-f` 且路径不存在 → 命令返回 fatal → **整个 Commit 步骤失败** →
连带 dashboard_data.json 也推不上去（数据丢失扩大化）。

**现状抑制：** review.yml:86 也提交 transactions.csv 且其 artifact 上传（review.yml:73）已长期运行，
该文件几乎必然已存在于 main → dashboard-data checkout 中存在 → 不会 fatal。
**属潜在中危**，非今晚引入。

**修复方向（只列不改）：** 改为 `if [ -f portfolio_50000_transactions.csv ]; then git add ...; fi`（与 scan/review 同款防御）。

---

### M3 · quant-research `git add -A` 过宽

**证据：** `quant-research.yml:48` 用 `git add -A`，会暂存 checkout 内**所有修改 + 未跟踪文件**
（含 `__pycache__/*.pyc`、本轮量化产物外的任何残留）。
虽不直接丢数据，但会把脏文件带进 main（历史已有 scan/review 因未清理 pyc 导致 rebase 失败的教训，
见 scan.yml:104-116 注释）。与 H1 同源（同一份有缺陷的提交段）。

**修复方向（只列不改）：** 替换为显式清单，如
`git add quant_factor_backtest.csv quant_factor_validation.csv ...`（仅 Phase 2–7 产物）。

---

## 3. 低危观察项（不影响功能）

### L1 · fetch_runtimes 实际在第 4 步，非用户预期的第 6 步
`dashboard-data.yml` 实际顺序：① Checkout ② Set up Python ③ Install ④ **Fetch workflow runtimes**(74)
⑤ Refresh portfolio prices(80) ⑥ Intraday stop loss(86) ⑦ dashboard_export(92) ⑧ Summarize(107) ⑨ Validate(113) ⑩ Commit(145)。
用户预期④=price-only、⑥=fetch_runtimes。差异仅为 fetch_runtimes 提前，**无功能影响**
（它只读 GitHub Actions API 的 scan/review/evolve 最近成功 run，与本地价格无关）。

### L2 · OHLCV 8 列空值对各消费方安全
- scan.py:3791 `pd.read_csv(..., dtype=str, keep_default_na=False)` → 空 O/H/L/V 读作 `""`，且 scan 仅取 `Date` 列（契约诊断），不碰 O/H/L/V ✅。
- Phase 2 只读 `Close`（`price_map_from_history`），空 OHLCV 列被忽略 ✅。
- 现有 3250 行历史 OHLCV 全空（回填因 yfinance 429 失败，已降级留空），不影响任何读取方。

### L3 · review 先 `git pull --ff-only` 再 rebase（冗余无害）
`review.yml:27` `git pull origin main --ff-only` 之后，提交段又做 `git fetch + git rebase`（127-131）。
二者不冲突，仅多一次网络操作，无副作用。

---

## 4. 逐项证据与修复方向汇总（只读，不改）

| 项 | 关键证据（文件:行） | 修复方向 |
|---|---|---|
| H1 | quant-research.yml:48-50；scan.yml:120-125,163-166；news-fetch.yml:56-73 | push 前 fetch+rebase + 3 次重试 + 显式 git add |
| H2 | review.yml:83-88；dashboard-data.yml:151；cron review:8 / dashboard:16 | 盘后无 intraday-stop 已抑制；可选 positions 互斥或 append 去重 |
| M1 | scan.py:3957-3961；scan.yml:70-95；dashboard_export.py:2543；dashboard-data.yml:50-55 | scan.yml 加 target 到 commit；dashboard-data.yml 加 ENABLE_TARGET_FILE=1 |
| M2 | dashboard-data.yml:151 | 改 `if [ -f ... ]; then git add ...; fi` |
| M3 | quant-research.yml:48 | 显式文件清单替代 `git add -A` |
| L1 | dashboard-data.yml:74 vs 用户预期 | 无（仅记录） |
| L2 | scan.py:3791；backtest 仅读 Close | 无（已安全） |
| L3 | review.yml:27,127-131 | 无（冗余无害） |

---

## 5. 给明早 06:23 review 与下周一 scan 的结论

- **明早 review 安全：** review.py 不读 price_history（OHLCV 改动零影响）；review 路径未触碰。
  唯一需留意的是 H2 的 positions.csv 争写——但盘后无 intraday-stop 触发，实际风险极低。
- **下周一 scan 新链路：** 
  - 价格历史会首次以 8 列 + 真实 OHLCV 落盘（新交易日自动带 O/H/L/V，历史行继续留空）。
  - **quant-research 首次真实跑会推送失败（H1）** —— 这是本周最该修的一项，否则量化研究产物每轮丢失。
  - target 文件会写但不入库、dashboard 不读（M1）——板块不显示，但不崩溃。
- **优先级建议：** 先修 H1（确定性数据丢失），再修 M1 两处（让 target 板块真正可用），其余可延后。
