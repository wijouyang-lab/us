# US V20 — Core / Observation 账本一致性修复

日期：2026-09-22

## 本次修复

### 1. Scan 邮件 Core / Observation 串栏修复
- 不再直接保留 AI 原始 Rank 6-12 区块。
- 邮件 Core 与 Observation 均从 `verified_items -> to_write` 程序最终入账集合重新生成。
- 同一 Ticker 在本次 Scan 中只允许进入一个栏目。
- 已进入 Core 的 Ticker 会从 Observation 自动排除。
- pending CSV 与邮件栏目使用同一 Tag 来源。

### 2. Review 绩效口径修复
- Observation 继续作为有效 Scan 推荐事件进入推荐跟踪绩效。
- 新增 Core 推荐跟踪胜率，与 Observation 胜率分开展示。
- Scan 推荐综合胜率明确包含 Core + Observation。
- 已了结股票推荐胜率改为 Core + Observation 都纳入，期权独立排除。
- Review 分类从单纯按 Ticker 分组调整为 `Ticker + Tag`，避免同一股票历史上从 Observation 转 Core 时互相覆盖。

### 3. 明确口径
- Observation：有效推荐，但不是实际持仓。
- Actual Active：仅真实持仓。
- Scan 综合推荐绩效：Core + Observation。
- Option：始终独立统计。
