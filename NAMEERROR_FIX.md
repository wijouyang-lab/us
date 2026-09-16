# 2026-09-16 US Review 修复说明

本次 GitHub Actions 报错：
NameError: name '_load_recent_option_recommendations' is not defined

原因：review.py 在第一次调用 `_load_recent_option_recommendations()` 时，函数定义仍位于后面的 HTML 构建代码之后。Python 是按顺序执行模块级代码，因此会在到达后面的定义前直接抛出 NameError。

修复：将 `_load_recent_option_recommendations()` 的定义移动到第一次调用之前，并保留最近 7 天、Status=Active 的过滤逻辑；同时增加日志：`📋 最近7天可用期权推荐 N 条。`

本次还确认：
- 9/15 的 PANW / APA / LUV / BBY / LHX Observation 已进入 trade_history/review_history，不再因为 pending `.processed` 而丢失。
- Review 的 `git add -A` 提交策略会同时持久化账本、Review、报告和期权文件。
- 未把 `__pycache__/*.pyc` 放进最终包。
