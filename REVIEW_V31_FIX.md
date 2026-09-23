# V31 Review 修复

1. Observation 缺失推荐价：从 review_history / pending 回填，并持久化回 trade_history.csv。另恢复了 2026-09-07 的 6 条历史 Observation 推荐价：DELL 563.289978、BEN 32.720001、VST 140.389999、CRH 86.699997、CVNA 65.400002、ODFL 174.360001。
2. 期权 Wall：优先真实 OI Wall；OI 不可用时使用成交量最高执行价作为成交量代理，并明确显示“成交量代理 / OI N/A”。Review 会实时重新读取期权链；yfinance 失败时使用 Yahoo options API。
3. NXPI 类止损：只有经过目标日期精确匹配的完整当日 OHLC，才允许触发当日移动止损。最近有效收盘价或 fast_info 仅用于跟踪，绝不允许触发 Stop。
4. 期权 Review 对活跃策略重新读取当前到期链，动态刷新 Wall。
