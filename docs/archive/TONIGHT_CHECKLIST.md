# 今晚验证清单（Tonight Checklist）

> 周一 2026-10-12，scan 北京 21:00 会跑。可打印，逐项勾选。
> 全程只读观测，不手动改任何文件、不激活任何 flag。

---

## 【21:00 前】
- [ ] 什么都不做

## 【21:05】
- [ ] 打开 GitHub Actions → 美股盘中扫描
- [ ] 有新 run？→ 是 ✅ / 否 ❌（手动 Run workflow 兜底）

## 【21:30】
- [ ] 跑 `bash /workspace/monday_check.sh`
- [ ] 看 §2 scan 是否 ✅
- [ ] 看 §9 flag 状态是否全 ✅

## 【21:45】
- [ ] 打开网页 https://wijouyang-lab.github.io/us/
- [ ] 组合：4 只
- [ ] AI 目标持仓卡片：出现？
- [ ] 交易观测面板：出现？
- [ ] 宏观板块：不显示（预期，flag 关）

## 【异常时】
- [ ] scan 失败 → 截图贴给 ChatGPT
- [ ] 21:05 没触发 → 手动 Run workflow
- [ ] 其他 → 按 ../WEEKEND_CHANGELOG.md §3 报告

---

## 备注
- 宏观 / 买入决策前置（scan）两个 flag 均关闭 → 今晚 scan 走旧路径（与上周一致）。
- 若 §9 flag 出现 ❌，立即按 `../WEEKEND_CHANGELOG.md` 回滚矩阵处理（删 repo variable）。
- 交易观测面板为纯观测（无硬闸门），应正常显示。
