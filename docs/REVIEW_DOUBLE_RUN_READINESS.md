# Review 双跑就绪度检查（只读）

> 生成时间：2026-10-12 23:59 GMT+8（周一）
> 目的：确认「明天 06:23 review 双跑」是否准备好，并列出阻塞点。
> 本文为**只读审查**，未改动 `review.yml` / `review.py` / `scan.yml` / `scan.py` / 任何 macro 文件。

## 一、review.yml 配置摘要（来自 `.github/workflows/review.yml`）

| 项 | 值 | 说明 |
|----|----|------|
| `name` | `美股盘后复盘` | — |
| `on.workflow_dispatch` | ✅ 存在（空配置，允许手动 / API 触发） | 满足「可手动 dispatch」 |
| `on.schedule.cron` | `'23 22 * * 1-5'` | 见下方时区换算 |
| `concurrency.group` | `us-stock-portfolio-ledger` | 与 `dashboard-data.yml` **同一 group** |
| `concurrency.cancel-in-progress` | `false` | 不取消进行中的运行，后者排队等待 |

### cron 时区换算（关键）

GitHub 原生 cron **只认 UTC**，不读 `timezone` 字段。

```
cron '23 22 * * 1-5'
  └─ 分钟 23，小时 22，周一到周五（1-5）UTC
  └─ 22:23 UTC + 8h = 次日 06:23 北京
```

- 周一 22:23 UTC → **周二 06:23 北京**
- 周二 22:23 UTC → 周三 06:23 北京
- ……
- 周五 22:23 UTC → 周六 06:23 北京

对应「明天 = 周二 10-13 06:23 北京」的那一次，是 **周一 10-12 22:23 UTC**——
也就是**今晚约 22:23 UTC（≈ 明天 06:23 北京）**会触发，落在 `1-5`（周一）范围内 ✅。

> 注意：GitHub 不保证 cron 精确到分钟，通常 ±1~15 分钟抖动，请预留时间窗口。

## 二、双跑前 3 项检查

### 检查 1：review.yml 自身配置（已自动确认 ✅）

- [x] `workflow_dispatch:` 存在 → 可被 cron-job.org 经 API 手动触发
- [x] `schedule` cron = `'23 22 * * 1-5'` → 与「06:23 北京」一致
- [x] `concurrency.group = us-stock-portfolio-ledger`，`cancel-in-progress: false`

**双跑安全性结论**：两套触发（GitHub 定时 + cron-job.org dispatch）同属一个
concurrency group 且 `cancel-in-progress: false` → 不会互相取消，后到者**排队串行**执行，
两次 review 都会跑完，账本（`trade_history.csv` / `review_history.csv` / `portfolio_50000_*`）
由各自运行独立提交，**不会因双跑丢数据**。

### 检查 2：cron-job.org 的 review job（⚠️ 需你手动确认）

以下 3 项**只能你在 cron-job.org 控制台目视确认**，沙箱无法访问该站点：

- [ ] **Enable job 开关**：review job 是否为 `Enabled` 状态
- [ ] **Next execution**：下次执行时间是否 ≈ 周二 10-13 06:23 北京（与 GitHub 定时对齐）
- [ ] **Last execution 状态**：最近一次执行是否 `SUCCESS`（非 error / disabled）

> 若 cron-job.org 与 GitHub 定时都指向 06:23 北京，则构成「双跑」；若其一关闭，则只有单跑，不影响正确性。

### 检查 3：判断与阻塞点

| 项目 | 状态 |
|------|------|
| GitHub 定时 06:23 北京能否触发 | ✅ 能（cron 已配，周一 UTC 22:23 对应） |
| cron-job.org 能否同时触发 | ⚠️ 待你确认（检查 2） |
| 双跑是否安全（不丢数据 / 不互删） | ✅ 安全（同 group + cancel-in-progress:false 串行） |
| 与 dashboard-data 冲突 | ⚠️ 同 group；dashboard-data 每 15 分钟跑一次，review 会在其当前运行结束后**排队**，仅延迟、不失败 |
| 阻塞点 | 仅「检查 2 的 cron-job.org 配置」需你确认；代码/配置层面无阻塞 |

## 三、明天验证步骤

1. **06:23 前后** → 打开 GitHub **Actions**，确认 `_temp-test-datasources` 与
   `_temp-acceleration` 两个临时 workflow 的 run 结果（见下方「顺带查看」）。
2. **06:23 review 双跑** → 看 Actions 中 `美股盘后复盘` 是否出现 **1~2 次**运行：
   - 1 次 = 仅 GitHub 定时触发（cron-job.org 未开）
   - 2 次 = 双跑（定时 + cron-job.org）串行执行
3. **07:00** → 跑 `monday_check.sh`，并数 `美股盘后复盘` 的 review run 数，核对是否等于预期（1 或 2）。
4. **21:00** → `scan.yml` 运行（**macro 首次跑**，与本次任务无关，仅提醒勿动 macro 相关文件）。
5. **顺带查看两个 `_temp-` workflow 的 run 结果**：
   - `_temp-test-datasources`：`FG_OK` / `FW_OK` 是否打印（验证 F&G + FedWatch 在 CI 出口可拉到）
   - `_temp-acceleration`：4 步是否跑通，下载 `acceleration-results` artifact（`results.json` / `report.json`）看真实 IC

## 四、铁律遵守确认

- ❌ 未碰 `review.yml` / `review.py` / `scan.yml` / `scan.py`（只读审查）
- ❌ 未碰任何 macro 相关文件（macro 明日 21:00 首次跑不受影响）
- ❌ 未 amend / 未 force push
- ✅ 临时文件均以 `_temp-` 前缀命名（`_temp-test-datasources.yml` / `_temp-acceleration.yml` / `_temp_experiment/`），跑完即删
- ✅ 未改动 `/tmp/us` 现有业务文件（仅新增临时文件）
