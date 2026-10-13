# 外部触发验证手册（External Trigger Verification）

> 状态：**准备阶段（只读 + 文档）**，尚未删除 schedule。
> 生成时间：2026-10-09 13:29 GMT+8
> 目标：用 cron-job.org 外部触发替换 GitHub 原生 `schedule`，扫描时间改为 **21:00 北京 = 13:00 UTC**（原 19:00 北京 = 11:00 UTC）。

---

## 0. 铁律（执行前必须确认）

| # | 铁律 | 当前遵守情况 |
|---|------|------|
| 1 | **不删 schedule**，直到外部触发验证成功 | ✅ 未删 |
| 2 | **不改任何 Python 代码** | ✅ 未碰 `scan.py` / `review.py` / `evolve.py` 等 |
| 3 | **不碰监控**（PID 108842） | ✅ 未碰 |

---

## 1. 当前 `scan.yml` 的 `on:` 段（只读，已核实）

真实文件：`/tmp/us/.github/workflows/scan.yml`（行 3–8）。

> ⚠️ 与你最初贴的假设不同：真实文件里 `workflow_dispatch:` 在**前**，`schedule:` 在**后**（GitHub 不关心顺序，语义等价）。下面的 diff 以**真实文件**为准。

```yaml
name: 美股盘中扫描

on:
  workflow_dispatch:
  schedule:
    # Schedule: UTC (GitHub 原生 cron 只认 UTC，不依赖 timezone 字段)
    # Scan: Mon-Fri 19:00 Beijing = 11:00 UTC
    - cron: '7 11 * * 1-5'
```

其余 `on:` 之外内容（concurrency / jobs）**本轮不动**。`news:` job（needs: scan）也不受影响。

---

## 2. 删除 schedule 的精确 diff（仅记录，未执行）

> 此 diff **只写进本文档**。删除动作在「Run now 测试成功」后由人工/助手执行并 commit + push。

```diff
 .github/workflows/scan.yml
 on:
   workflow_dispatch:
-  schedule:
-    # Schedule: UTC (GitHub 原生 cron 只认 UTC，不依赖 timezone 字段)
-    # Scan: Mon-Fri 19:00 Beijing = 11:00 UTC
-    - cron: '7 11 * * 1-5'
```

删除后预期 `on:` 段：

```yaml
on:
  workflow_dispatch:
```

---

## 3. A 部分 —— 用户先做（删 schedule 之前必须完成）

### A.1 生成 PAT（Personal Access Token）

1. 进入 GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained tokens**
2. 点 **Generate new token**
3. 关键配置：
   - **Token name**：任意，如 `us-external-trigger`
   - **Expiration**：建议 1 年或更长（避免中途失效）
   - **Resource owner**：`wijouyang-lab`
   - **Repository access**：选 **Only select repositories** → 仅勾选 **`wijouyang-lab/us`**
   - **Repository permissions** → **Actions** → 设为 **Read and write**
   - （其余权限保持 No access）
4. 点 **Generate token**，复制完整 token（格式 `github_pat_xxx...`），**只显示一次**，妥善保存。

### A.2 配置 cron-job.org

1. 打开 https://cron-job.org → 注册/登录
2. 点 **Create cronjob** / **New cron job**
3. 字段填写：

| 字段 | 值 |
|------|-----|
| **URL** | `https://api.github.com/repos/wijouyang-lab/us/actions/workflows/scan.yml/dispatches` |
| **Request method** | `POST` |
| **Schedule** | `0 13 * * 1-5`（UTC）**或** `0 21 * * 1-5`（Shanghai，取决于 cron-job.org 账户时区设置） |
| **Timezone** | 与上面 Schedule 对应：UTC 则用 `0 13 * * 1-5`；账户设上海时区则用 `0 21 * * 1-5` |
| **Enabled** | ✅ 勾选 |

> ⚠️ **时区必对齐**：cron-job.org 的 Schedule 解释依赖账户时区。若账户时区是 UTC，填 `0 13 * * 1-5`（=21:00 北京）；若账户时区是 Asia/Shanghai，填 `0 21 * * 1-5`（=21:00 北京）。两者结果都要落在 **21:00 北京 / 13:00 UTC**。设错会偏 8 小时。

4. **Headers**（添加 3 条）：

| Header | Value |
|--------|-------|
| `Authorization` | `Bearer <你的PAT>`（替换 `<你的PAT>` 为真实 token） |
| `Accept` | `application/vnd.github+json` |
| `Content-Type` | `application/json` |

5. **Body / Payload**（raw JSON）：

```json
{"ref":"main"}
```

> 说明：`ref` 指触发分支，固定 `main`。dispatch 走 `workflow_dispatch` 事件，删掉 `schedule` 后此路径仍有效。

### A.3 立即触发测试（Run now / Test）

1. 在 cron-job.org 该 cronjob 详情页，找 **Run now** / **Execute now** / **Test** 按钮，立即发一次。
2. 或直接用 curl 自检（可选，本地验证 PAT + endpoint 是否通）：
   ```bash
   curl -X POST \
     -H "Authorization: Bearer <你的PAT>" \
     -H "Accept: application/vnd.github+json" \
     -H "Content-Type: application/json" \
     -d '{"ref":"main"}' \
     https://api.github.com/repos/wijouyang-lab/us/actions/workflows/scan.yml/dispatches
   ```
   - 成功：返回 HTTP `204 No Content`（无 body）。
   - 失败：返回 `401`（PAT 无效/权限不足）、`404`（repo 名或 workflow 名错）、`422`（ref 不存在）。

### A.4 去 GitHub 确认新 run

1. 打开 `https://github.com/wijouyang-lab/us/actions`
2. 找 workflow **美股盘中扫描**
3. 看是否出现一条**新 run**，触发来源显示 **workflow_dispatch**（不是 schedule）
4. 点进 run，确认它正常起步（checkout → setup-python → 安装依赖…）

> ✅ **判定「测试成功」标准**：GitHub Actions 出现一条由 dispatch 触发的新 run，且至少跑过 checkout 步骤（不一定等它全跑完，但建议看一眼是否绿灯推进）。

---

## 4. B 部分 —— 验证成功后，删 schedule

> 仅在用户明确反馈「Run now 测试成功」后执行。

步骤：
1. 应用第 2 节的 diff（删除 `schedule:` 整段及注释）。
2. 提交：
   ```
   git commit -m "ci(scan): 移除 GitHub schedule，改用外部 cron 触发（21:00 北京）"
   ```
3. push 到 `origin/main`。
4. 验证 `.github/workflows/scan.yml` 的 `on:` 仅剩 `workflow_dispatch:`。

---

## 5. C 部分 —— 验证失败

> 不删 schedule，把失败信息贴回来。

可能失败点：
- **401 Unauthorized**：PAT 无效、过期，或 Fine-grained token 没授权 `wijouyang-lab/us`、Actions 权限非 Read and write。
- **404 Not Found**：repo 全名拼错（应为 `wijouyang-lab/us`）、workflow 文件名拼错（应为 `scan.yml`）、或 PAT 的 resource owner 不是 `wijouyang-lab`。
- **422 Unprocessable**：body 的 `ref` 不是 `main`、或 repo 默认分支已改名。
- **GitHub 无新 run**：cron-job.org 时区/ schedule 配错导致没真正发送；或 Run now 被限频。
- **GitHub 有 run 但立即失败**：与触发方式无关，可能是 scan 自身问题（此时先排查 scan，不要归咎外部触发）。

把对应的错误信息（curl 返回码 + body，或 GitHub run 日志截图要点）贴回，再决定下一步。

---

## 6. 时间线（关键：避免双跑 / 漏跑）

| 时点 | 事件 |
|------|------|
| **现在** | 配 PAT + cron-job.org + 用 Run now 测试（见 A） |
| **测试成功** | 删 schedule + commit + push（见 B） |
| **今天 21:00 北京** | cron-job.org 首次按外部触发跑 scan（新时间 13:00 UTC） |
| **明天起** | 只有外部触发（单跑，不再双跑） |

### ⚠️ 关于「今天」的关键说明

- 删 schedule 后，**今天 19:07 北京（11:00 UTC 附近）不会有 scan**——那一次的 GitHub 原生 cron 已被移除。
- 今天唯一一次 scan = **21:00 北京的外部触发**（13:00 UTC）。
- 即：删 schedule 与首次外部触发在同一天，中间空档约 2 小时，**不会双跑，也不会漏跑**——只要你确认删 schedule 的动作发生在 21:00 之前。
- 推荐节奏：收到「Run now 测试成功」→ 立刻删 schedule + push（远早于 21:00）→ 21:00 由 cron-job.org 接管。

---

## 7. 验证成功后的回归注意

- 时区一致性：cron-job.org 账户的 Timezone 设置要和你填的 schedule 表达式一致（见 A.2 警告）。
- 周一至周五：`1-5` 已覆盖，周末不跑（与原本一致）。
- PAT 过期：Fine-grained token 有 Expiration，到期前需续期，否则静默停跑——建议加到日历提醒。
- 监控 PID 108842：外部触发不影响本地观测器，无需改动。
