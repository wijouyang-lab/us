# US Scan Core / Pending 同步修复 v8

## 本次只修改
- `scan.py`

## 修复的问题
1. AI 可以在邮件 Core Top1-5 中写出候选池之外的股票（例如本次 GNRC），导致 RSI / 乖离率显示 N/A。
2. `match_pool_to_report()` 只会把候选池内、能匹配到的股票写入 `pending`，因此出现“邮件推荐 5 只，但 pending 只有 2 只”。
3. 旧 Fallback 在 AI 完全匹配失败时可能强行凑 Core，与硬门槛设计不一致。

## v8 的处理原则
- AI 只能解释和排序程序候选池里的股票，不能新增股票。
- Core / Observation 最终标签由程序硬门槛决定，不由 AI 的文字标签决定。
- 候选池外 Ticker 自动记录并忽略。
- 邮件 Core Top1-5 改为从实际最终 `to_write` 集合重新渲染，因此邮件 Core 与 pending 使用同一集合。
- 不再用旧的“技术 Top10 强行凑 Core” Fallback 绕过硬门槛。
- 当天如果只有 2 只股票真正通过硬门槛，就只显示 2 只，不会为了凑 5 只而加入候选池外股票。

## 部署
用本包中的 `scan.py` 替换 GitHub 仓库根目录的 `scan.py`。
不要覆盖 `trade_history.csv`、`review_history.csv`、每日 pending/processed CSV、HTML、evolved_rules.json 等运行历史文件。

## 预期日志
- `🚫 [AI校验] 忽略候选池外推荐：...`
- `🔒 [程序校验] Core=X / Observation=Y / AI候选池外忽略=Z`

## 验证
- Python AST / py_compile 已通过。
- 已用“候选池只有 AMGN + ABBV、AI 额外写 GNRC(N/A)”的回归样例验证：GNRC 被剔除，邮件 Core 与程序候选集合保持一致。
