# 美股 Scan / Review / 期权完整修复版

本版本基于用户提供的 us-main(3).zip 完整代码整理。

## 已修改

1. `scan.py`
   - 扫描邮件改为在股票推荐、期权策略生成之后发送，避免邮件只有占位符而没有真实期权信息。
   - AI 正文不再允许虚构行权价、到期日、权利金、Delta、IV；真实期权数据由程序后置注入。
   - 新增可验证期权推荐区域。
   - 仅对本次新产生的 `Core_Dragon` 生成期权策略。

2. `scan_us_option_engine.py`
   - 新增真实期权链策略引擎。
   - 45-90 DTE，优先约 60 天。
   - 优先 `CALL_DEBIT_SPREAD`，无法形成有效价差时使用 `LONG_CALL`。
   - 使用期权链中的真实 bid/ask/lastPrice。
   - 计算/记录 Delta、IV、链内 IV 分位、Call Wall、Put Wall、财报日期和到期天数。
   - 不会在没有可验证期权链时伪造报价。

3. `review.py`
   - `Observation` 不再被当作实际持仓，也不会因为今日行情缺失而从 Review 消失。
   - 新增“最近30天新增/观察推荐”区域。
   - 实际持仓当日行情缺失时保留 Review 卡片并标记 `DATA_MISSING`，不做虚假止损判断。
   - Review 历史记录增加 `Observation` 状态。
   - 期权账本兼容新策略字段，并支持 `CALL_DEBIT_SPREAD` 到期内在价值结算。
   - Review 增加期权持仓/推荐区域。

4. `.github/workflows/scan.yml`
   - 使用 `git add -A`，防止新增 `option_strategies.csv`、推荐历史等遗漏。
   - 增加 fetch/rebase/retry，避免远程更新造成 push 失败。

5. `.github/workflows/review.yml`
   - 同样改为完整暂存并安全同步。
   - 保证 trade_history、review_history、option_strategies、报告和 pending processed 状态都能提交。

6. `.github/workflows/evolve.yml`
   - 增加安全同步逻辑，减少与 Scan/Review 并发提交冲突。

7. `.gitignore`
   - 排除 `__pycache__/`、`*.pyc` 等缓存文件。

## 特别说明

`Observation` 是有效的 Scan 推荐，但不计入实际持仓盈亏和股票止损触发。

期权策略只在期权链存在可验证报价时生成；没有数据时报告会明确显示“没有生成可验证期权策略”，而不是编造合约。
