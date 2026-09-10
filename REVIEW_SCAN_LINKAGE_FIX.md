# Review→Scan 风控提醒修复

修改文件：`scan.py`

1. `get_review_risk_linkage_warning()` 现在只读取最近一批已完成 Review 的 `Review_Risk_Date`，避免后续交易行的空风险字段覆盖上一批 Review 状态。
2. `STOP_TRIGGERED` 硬禁入、`STOP_NEAR` 强提醒继续进入 AI Prompt。
3. 新增 `build_review_risk_banner_html()`，在 Scan 邮件中确定性展示昨日 Review 风控提醒，不依赖 AI 是否输出。
4. 邮件明确显示硬禁入数量、STOP_NEAR 数量与具体股票。
5. `py_compile` 已通过。
