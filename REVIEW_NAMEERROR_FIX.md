# US Review NameError 修复

问题：review.py 在第 2263 行先调用 `_load_recent_option_recommendations()`，但该函数直到约 2744 行才定义，导致 GitHub Actions 运行时报 `NameError`。

修复：将 `_load_recent_option_recommendations()` 移到首次调用之前，并保留最近 7 天、Active 状态过滤逻辑。增加日志显示最近 7 天可用期权推荐数量。

本次不改变股票风控算法、Observation 逻辑或期权策略算法，仅修正函数定义顺序。
