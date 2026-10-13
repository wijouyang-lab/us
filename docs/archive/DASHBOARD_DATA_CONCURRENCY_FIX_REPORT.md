# dashboard-data.yml 并发删除 Bug 修复报告

> 交付时间：2026-10-07 · commit `20a29e5` · 状态：已 push，`HEAD == origin/main` ✅
> 性质：独立 P0/P1 稳定性修复，不进入任何 Quant Phase

## 1. 修改文件

仅 1 个：`.github/workflows/dashboard-data.yml`（**13 insertions / 0 deletions**）

未触碰：dashboard_export.py / scan.py / review.py / portfolio / Quant Research 文件 / Dashboard 前端 / schedule / concurrency 策略 / 数据生成逻辑。

## 2. 精确修复逻辑

**问题根因**（已在本地用真实 git 精确复现）：

```
dashboard-data checkout 旧 commit（无新文件）
  → 其他 workflow 并行 push 新文件到 main
  → dashboard-data push 被拒 → git fetch → git reset --soft FETCH_HEAD
  → index 仍是旧 HEAD 的暂存快照，新文件被标记为 D（删除）
  → 旧逻辑直接 git commit → 新文件从 main 被误删
```

**修复**：在 retry 循环的 `git reset --soft FETCH_HEAD` 之后、`git commit` 之前，插入两步：

```bash
git reset HEAD              # 把 index 重置到最新 HEAD（清除 D 误判），工作区改动保留
git add dashboard/data/dashboard_data.json dashboard/data/last_run.json dashboard/data/last_run.log
# 提交范围守卫（与首次提交等价）
STAGED="$(git diff --cached --name-only)"
if echo "$STAGED" | grep -vE '^dashboard/data/(dashboard_data\.json|last_run\.json|last_run\.log)$'; then
  echo "::error::重试阶段检测到非预期文件进入提交范围，已中止提交"
  exit 1
fi
```

## 3. 为什么可以阻止 D（删除）泄漏

`git reset HEAD`（mixed reset）把 index 重置为 FETCH_HEAD（最新 main）的状态，但**保留工作区改动**。此时：
- 并行新增的文件在 index 中恢复为"存在"状态，不再显示 D；
- 本 workflow 生成的 dashboard 数据仍在工作区；
- 重新 `git add` 只加入允许的 3 个文件；
- 范围守卫兜底：即使出现任何非允许路径（含误判的 D），立即 `exit 1` 中止提交。

双重保护确保最终 commit 只含允许文件，且不会删除并行期间的新文件。

## 4. 三个竞态模拟结果（真实 git 环境，非 mock）

| 场景 | 结果 |
|---|---|
| 1. 并行新增单个 NEW_FILE | ✅ NEW_FILE 保留 |
| 2. 并行新增 quant_factor_backtest.py + test + price.py | ✅ 3 个文件全部保留 |
| 3. 并行修改 README.md + 新增文件 | ✅ README 修改保留 + 新文件保留 |
| 4. 无并发，首次 push 成功路径 | ✅ 正常提交 dashboard 数据 |

竞态回归脚本固化于 `/tmp/dd_race_test.sh`，可重复执行：**通过 5 / 5**。

## 5. 全量测试 / 检查

| 项 | 结果 |
|---|---|
| 竞态回归测试 | **5 / 5 PASS** |
| 全量 Python 测试 | **397 / 397 PASS**（无回归） |
| git diff --check | ✅ 空（OK） |
| YAML 解析 | ✅ 通过（concurrency/steps 正常） |

## 6. Git 状态

| 项 | 值 |
|---|---|
| commit SHA | `20a29e54c7b7bca769cad29dfaa4b6960cc36a26` |
| push | ✅ 成功（无 force，无 reset --hard，无 amend） |
| HEAD == origin/main | ✅ **TRUE** |

## 7. 未解决问题

**无 P0/P1 遗留。** 修复严格限定在 retry 循环，未扩大范围、未清理任何历史遗留（旧 us-market-terminal / EMAIL secrets / dead scripts / Quant Research 等全部保持不动）。

**附带说明**：`git reset HEAD` 执行时 git 会打印 `Unstaged changes after reset:` 提示（列出工作区仍存在的 D/M 状态），这是 git 的正常 stdout 提示、非错误，不影响 commit 结果——范围守卫会在此时精确识别并放行仅允许文件。已在模拟中确认该提示下的最终提交结果正确。
