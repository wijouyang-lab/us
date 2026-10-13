# Dashboard Data 并发提交稳定性修复 + 废弃 Mirror 隔离 · 全链路生产验收报告

> 本报告为「夜间全自动任务」的最终交付。全程自主执行，未 force push、未 reset --hard、未改写 main 历史、未修改 Scan/Review/Options/Schedule/Email。

---

## 【A】审计结论

只读审计确认了生产验收暴露的两个真实问题，且均为既有架构缺陷的首次实际发作：

1. **P1 — Dashboard Data 并发提交冲突**：`concurrency.cancel-in-progress: true` 会让已进入 commit/push 阶段的 run 被后一个 run 取消；且提交重试使用 `git pull --rebase`，两次运行写同一批 JSON，rebase 重放必然行级冲突（run #951 实测：三文件 CONFLICT，重试 3/3 全失败，正确数据被丢弃）。
2. **P2 — 废弃 mirror 参与提交**：`dashboard_export.py` 默认把同一份 JSON 同步写入已停止维护的 `us-market-terminal/dashboard/data/`，workflow 又显式 `git add` 该副本 —— 两个同源提交目标叠加，进一步放大了冲突面。

**数据流结论**：

| 问题 | 答案 |
|---|---|
| A. 正式 Dashboard 数据路径 | `dashboard/data/dashboard_data.json` + `last_run.json` + `last_run.log`（保持不变） |
| B. 废弃 mirror | `us-market-terminal/dashboard/data/dashboard_data.json`（旧前端目录） |
| C. 谁产生 mirror | `dashboard_export.py` 写出段的 `mirror_path` 逻辑（原 `if not args.no_mirror`） |
| D. 谁把 mirror 加入 commit | `dashboard-data.yml` 第 134-136 行 `git add us-market-terminal/...` |
| E. concurrency 是否允许两个 run 同时改 main | 是，`cancel-in-progress: true` 下仍可能并发进入 push |
| F. retry 为何三文件冲突 | `git pull --rebase` 把数据 commit 当补丁重放，两次运行改同一 JSON 行级必冲突 |
| G. #951 数据为何没进 main | 冲突后 `git rebase --abort` 再用旧 HEAD 强推，最终 `! [rejected] non-fast-forward`，数据保留在工作区被丢弃 |

---

## 【B】实际根因

- mirror 默认开启 + workflow 显式 add mirror = 两个同源提交目标 → 冲突必然化
- concurrency cancel = 进行中的正确 run 被取消 → 数据丢失
- `pull --rebase` 重试 = 对同源 JSON 重放补丁 → 冲突不可自动解

---

## 【C】修改文件列表

| 文件 | 性质 |
|---|---|
| `.github/workflows/dashboard-data.yml` | 修改 |
| `dashboard_export.py` | 修改 |
| `tests/test_dashboard_data_stability.py` | 新增（回归测试） |

仅此 3 个文件。未触碰 `review.py` / `scan.py` / `scan_us_option_engine.py` / `app.js` / 其他 workflow / 数据文件。

---

## 【D】每个文件具体修改内容

### 1. `.github/workflows/dashboard-data.yml`
- `concurrency.cancel-in-progress: true → false`（后到 run 排队，不再取消进行中的 run）
- 删除 `git add us-market-terminal/dashboard/data/dashboard_data.json`
- 新增**提交范围守卫**：`git diff --cached --name-only` 必须只匹配三个正式数据文件，否则 `::error::` 并 `exit 1`
- 重写提交/push 重试逻辑：
  - `git fetch origin main` → `git reset --soft FETCH_HEAD` → 重新 `git commit` → `git push`
  - 替换原 `git pull --rebase`
  - 保留 3 次上限；失败 `exit 1` 明确报错，不静默通过

### 2. `dashboard_export.py`
- mirror 改为**显式 opt-in**：新增 `--mirror` 开关
- `--no-mirror` 保留为兼容参数（当前已是默认行为）
- 写出段 `if not args.no_mirror:` → `if args.mirror:`

### 3. `tests/test_dashboard_data_stability.py`（新增）
- 30 项回归断言，覆盖 A–G 全部验收点（见【F】）

---

## 【E】为什么这些修改是最小必要修改

| 修改 | 为什么必要 | 为什么最小 |
|---|---|---|
| mirror 改 opt-in | 唯一能停止废弃副本被提交的方式 | 只改一个布尔判定 + 新增一个 flag，不删目录、不删历史 |
| 删 `git add mirror` | 唯一能阻止 mirror 进 commit 的方式 | 删 3 行 |
| concurrency 改 false | 唯一能阻止进行中 run 被取消 | 改 1 个布尔值 |
| retry 改 reset --soft | 唯一能在"数据已在本轮生成"的前提下无冲突重建提交 | 替换 retry 内部 4 行 |
| 提交范围守卫 | 防止未来误加文件 | 新增 6 行防御 |

无任何重构、无任何旧架构清理、无任何无关逻辑改动。

---

## 【F】测试结果

| 检查 | 结果 |
|---|---|
| Python compile（`py_compile`） | ✅ PASS |
| YAML syntax（PyYAML 解析） | ✅ PASS |
| workflow 内嵌 shell（`bash -n`） | ✅ PASS |
| 新增回归测试 | ✅ **30 / 30** |
| 项目完整测试套件 | ✅ **271 / 271** |
| `git diff --check` | ✅ PASS（无空白错误） |

### 新增回归测试覆盖（30 项）

| 组 | 内容 |
|---|---|
| A | 默认运行不产生 mirror（临时目录 + 仓库 mtime 双重验证）；`--mirror`/`--no-mirror` 均存在；写入由 `args.mirror` 控制 |
| B | 正式 `dashboard_data.json` 正常产出、JSON 合法且含全部顶层字段 |
| C | stocks 29/29 携带 `rec_price`，且取自 `trade_history.Price`（非当前价/非 Scan_Ref_Price） |
| D | workflow 无 `git add us-market-terminal`、无 `git add .`/`-A`、明确列出三文件、存在范围守卫 |
| E | `cancel-in-progress: false`、group 唯一、schedule 与 push.paths 未被改动 |
| F | 无 force push、无 `pull --rebase`、retry 前 fetch、上限 3 次、失败 exit 1 |
| G | 已有修复（Review 字段 / rec_price / 买入价渲染 / Options RR 2.0 / 无 Email）均未被回退 |

### 并发行为实测（隔离 git 沙箱模拟）

| 场景 | 结果 |
|---|---|
| 旧逻辑 `git pull --rebase` | ❌ `CONFLICT`，进入 rebase 冲突状态（与 #951 完全一致） |
| 新逻辑 `fetch + reset --soft + 重提交` | ✅ 推送成功，全程无冲突 |

---

## 【G】测试数量

**271 / 271 PASS**（新增 30 + 既有 241）

---

## 【H】Code Review

**PASS**

独立 review 逐项核查：未修改非必要文件、未改 Scan/Review/Options/frontend/schedule、未恢复 Email、未删历史文件、不再写 mirror、不再 add mirror、concurrency 仅限 dashboard-data、retry 安全（fetch + reset --soft + 无 force）、不会丢数据、不会让 stocks 变空、不破坏 rec_price / Market Regime / Runtime。

---

## 【I】Git

| 项 | 值 |
|---|---|
| commit SHA（原始） | `325fc97` |
| rebase 后 SHA | `59f350e82d923c7644e8bf489eb8d5770befa360` |
| push | ✅ 成功（`9333556..59f350e`） |
| 最终 HEAD | `5dc09af935622eec5ffbcf012d93af827bfa1a31` |
| 最终 origin/main | `5dc09af935622eec5ffbcf012d93af827bfa1a31` |
| HEAD == origin/main | ✅ **TRUE** |

> 说明：`5dc09af` 是本次 push 自然触发的 run #957 生成的自动数据提交；修复 commit `59f350e` 是其父提交，位于 main 历史链中。

---

## 【J】生产 Workflow

| Run | Run ID | event | status | conclusion |
|---|---|---|---|---|
| **#957** | `37043170698` | **push**（自然触发） | completed | **success** |

时间：created/started `2026-10-02T17:48:06Z`，updated `17:48:56Z`，head_sha `59f350e8`（本次修复 commit）。

---

## 【K】是否发生异常

| 项 | 结果 |
|---|---|
| cancelled | ❌ 无 |
| conflict | ❌ **无**（日志 `CONFLICT` 命中 0 次） |
| retry 3/3 失败 | ❌ 无（一次拒绝后即通过新逻辑收敛） |
| mirror conflict | ❌ **无**（`同步副本` 命中 0 次，且 commit 文件列表 0 个 `us-market-terminal`） |
| mirror 参与 commit | ❌ **无**（run #957 的 commit 只含 3 个正式数据文件） |

---

## 【L】Dashboard Data

| 项 | 值 |
|---|---|
| stocks 数量 | **29** |
| rec_price 覆盖率 | **29/29**（键与非空均为 29） |
| 三价格语义分离 | ✅（如 ABBV：买入价 262.61 / 当前价 261.45 / 前收 264.02） |
| Market Regime / VIX / Sector RS | 历史数据无值 → 显示 `—`（未伪造，符合预期） |
| market_updated_at | `2026-10-02T17:48:49Z` |

---

## 【M】Options

| 项 | 值 |
|---|---|
| active_options_count | **0** |
| rejected_options_count | **10** |

RR ≥ 2.0 门槛逻辑保持不变，无一回退。

---

## 【N】最终 git status

**clean** —— 仅 `?? dashboard/__pycache__/`、`?? tests/__pycache__/`（untracked 缓存，非业务文件）。modified = **0**，tracked `.pyc` = 8 个（未删）。

---

## 【O】未完成问题 / 后续建议

**本次任务范围内**：无遗留问题。

**后续建议（不属本任务范围，未处理）**：

- **P2**：`dashboard_export.py` 的 `--out` 缺省值仍指向 `us-market-terminal/dashboard/data/`（仅当未显式传 `--out` 时生效）。生产 workflow 始终显式传 `--out`，故无实际影响；若未来有其它调用方裸跑该脚本，建议把缺省路径改为正式 `dashboard/data/`。
- **P3**：`us-market-terminal/` 目录与 4 个 tracked 旧前端文件仍是死代码，建议择期由你决定是否归档。
- **P3**：3 个 workflow 仍注入未消费的 `EMAIL_*` secrets（stale configuration）。

以上均**未修改**。

---

## 最终结论

**IMPLEMENTATION COMPLETE AND VERIFIED**

- 根因已定位并最小化修复
- 271/271 测试通过
- Code Review PASS
- 自然触发 run #957 成功，无 conflict、无 mirror 参与提交
- 生产数据 stocks=29、rec_price=29/29、Options Active=0/Rejected=10、Runtime 三键完整
- 线上 Pages 数据与远端一致
- workspace clean，HEAD==origin/main
