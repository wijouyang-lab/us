# 周二检查清单（Tomorrow Checklist）

> 可打印版 · 生成于 2026-10-13
> 用途：明天（含 06:23 review 双跑、21:00 macro 首次跑）逐项核对。
> 铁律：不碰 review.yml / review.py / scan.yml / scan.py / macro 相关文件；不 amend / force push。

---

## ⏰ 06:23 — Review 定时触发 + 双跑核对

**看什么**
- GitHub Actions：是否出现 `美股盘后复盘`（review.yml）运行记录。
- 同时确认是否有第二来源（cron-job.org）也触发了一次 review（若已配置）。
- `_temp-test-datasources` 与 `_temp-acceleration` 两个临时 workflow 的运行结果。

**判断标准**
- review 出现 **1 次** → 仅 GitHub 定时触发（正常）。
- review 出现 **2 次** → 定时 + cron-job.org 串行双跑（两条 job 同属 `us-stock-portfolio-ledger` group，`cancel-in-progress:false`，互不取消、账本各自独立提交，不丢数据）。
- 两个 `_temp-` workflow 均跑完且步骤绿（无 `FG_FAILED` / `FW_FAILED` / 步骤异常）。

**对应动作**
- 正常：记录次数，无需干预。
- 异常（review 0 次 / 报错）：保留日志，明天 07:00 用 `monday_check.sh` 复核，不要在此时手动改任何 workflow。
- 临时 workflow 异常：先看失败步骤日志，定位是网络（418）还是解析错误，再决定是否重新手动 dispatch。

---

## ⏰ 07:00 — monday_check.sh 复核

**看什么**
- 执行 `monday_check.sh` 的输出。
- 脚本统计的 **review run 数**，与上面 06:23 的肉眼计数是否一致。

**判断标准**
- run 数 = 1（或 2，若双跑）→ 与预期一致，核对通过。
- run 数异常（0 / 远大于预期）→ 说明 06:23 触发失败或有重复堆积。

**对应动作**
- 一致：继续。
- 不一致：截图保留 `monday_check.sh` 输出与 Actions 列表，作为后续排查依据；**不要**手动补跑 review 以免账本重复。

---

## ⏰ 21:00 — Scan 运行（macro 首次跑）

**看什么**
- GitHub Actions：`scan.yml` 正常运行。
- 本次是 **macro 首次跑**（与本次任务无关，macro 相关文件未改动）。

**判断标准**
- scan.yml 成功、无新增报错 → 正常。
- 出现 macro 相关报错 → 属于首次运行磨合，先读日志，不要动 macro / scan 源码。

**对应动作**
- 正常：无需干预。
- 报错：记录日志，单独评估是否需要后续修复；本轮**不改变**任何 scan / macro 文件。

---

## 🧹 收尾 — 两个 temp workflow 跑完后的清理命令

> 前提：你已在 Actions 看完两个 `_temp-` 运行结果、下载了 acceleration artifact、确认 F&G / FedWatch 数据源可拉取。

```bash
cd /tmp/us

# 1) 删除临时文件（workflow + 实验脚本）
git rm -r .github/workflows/_temp-test-datasources.yml \
          .github/workflows/_temp-acceleration.yml \
          _temp_experiment/

# 2) 提交清理
git commit -m "chore(ci): remove temporary datasource/acceleration workflows"

# 3) 同步远端（不 amend / 不 force）
git fetch origin
git rebase origin/main
git push origin main
```

**判断是否还需要保留**
- 若两个临时 workflow 结果还需复核 / 重新跑 → **先不删**，看完再说。
- 已确认无用 → 执行上面清理，使 `git ls-files | grep _temp` 为空，工作树恢复干净。

---

## 📋 一句话总览

| 时点 | 动作 | 异常处理要点 |
|------|------|------|
| 06:23 | 看 Actions：review 双跑 + 两个 `_temp-` 结果 | review 0/报错 → 留日志，07:00 复核，不手动改 |
| 07:00 | 跑 `monday_check.sh`，数 review run 数 | 与 06:23 计数不一致 → 截图留证，不补跑 |
| 21:00 | scan.yml 跑（macro 首次） | macro 报错 → 读日志，不动源码 |
| 收尾 | 确认结果后删 `_temp-` 文件并 push | 结果待复核则先不删 |
