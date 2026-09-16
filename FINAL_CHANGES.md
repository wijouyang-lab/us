# US 最终修复版 v6

本版核心修正：

1. 所有有效 Scan 股票推荐均纳入股票绩效统计：Core_Dragon / Core_Double_Dragon / Sub_Pioneer / Observation。
2. Observation 不再排除在胜率统计之外：仍按首次推荐价持续计算当前盈亏；但不视为实际持仓，不触发实际持仓移动止损。
3. Scan 推荐综合胜率 = 已了结股票 + 当前实际持仓 + Observation；期权完全独立。
4. 当前推荐跟踪胜率 = 当前持仓 + Observation，全部按推荐价追踪。
5. 当日 OHLC 缺失时，止损判断继续暂停，但绩效统计可以使用最近可用完整收盘价，避免推荐因数据源暂时缺失而从胜率样本消失。
6. Observation 写入 review_history.csv 时同步写入 PnL_Pct，并在报告中显示推荐跟踪盈亏。
7. 保留真实期权链策略引擎，不生成虚假期权报价。
8. 保留 Review / Scan 风控联动和动态移动止损。
9. 不把 Trap_Warning 视为股票推荐；它是风险警告，不进入推荐胜率。
10. 仓库不包含 __pycache__ 或 *.pyc。

上传说明：代码与 workflow 可直接覆盖；不要用包内旧 CSV 覆盖你 GitHub 当前最新账本，除非你确认这些 CSV 就是你要保留的版本。
