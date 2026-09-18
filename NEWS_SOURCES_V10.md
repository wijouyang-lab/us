# 新闻源升级说明

本版本新增官方与独立来源，但不把新闻数量简单越堆越多。

### 第一优先级：官方数据/政策
- Federal Reserve RSS：Press Releases、Monetary Policy
- BLS RSS：Latest Numbers、CPI

### 第二优先级：高可信市场新闻
- Reuters：通过 Google News `site:reuters.com` 定向聚合，避免依赖不稳定的直接 RSS。

### 第三优先级：市场补充
- CNBC
- Yahoo Finance RSS
- Google News
- MarketWatch（失败时安全降级）

所有新闻仍限制在最近 72 小时，并做标题去重。单一来源不能覆盖多个独立事实来源；模型必须标出冲突并降低结论强度。
