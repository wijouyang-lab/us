# OHLCV 补采实施报告

> 时间：2026-10-09 23:25 GMT+8（明早 06:23 北京 review 之前）
> 目标：price_history 从 `Date,Ticker,Close` 扩到 `Date,Ticker,Open,High,Low,Close,Volume`
> 铁律：不改 review.py / review.yml / scan.py 主逻辑 / portfolio_50000.py / 34 列 snapshot；明早 review 安全性必须证明。

---

## 1. 第一步：只读确认爆炸半径（先做，已通过）

| 检查项 | 命令 | 结果 | 危险？ |
|---|---|---|---|
| review.py 读 price_history | `grep -n "price_history\|quant_factor_price" review.py` | **零匹配** | ✅ 不读 |
| review.yml 读 price_history | `grep -n "price_history" .github/workflows/review.yml` | **零匹配** | ✅ 不读 |
| scan.py 写/读 price_history | `grep -n "price_history\|quant_factor_price" scan.py` | 仅定义常量 + 第 3790 行**按列名** `pd.read_csv` 只读 `Date` 列做契约诊断；**不写、不按位置** | ✅ 安全 |
| dashboard_export.py 读 price_history | `grep -n "price_history" dashboard_export.py` | **零匹配** | ✅ 不读 |
| backtest 取数 | `quant_factor_backtest.py:450` `from quant_factor_price import load_price_history, price_map_from_history` | 仅经 `price_map_from_history` 取 **Close** | ✅ 加列无影响 |
| schema_version 严格相等校验 | `grep -rn "schema_version =="` | 无 | ✅ 混入 v1/v2 行安全 |

**判定**：review 根本不读 price_history，scan 只按列名读 `Date` 一列。加列不影响任何读取路径。**爆炸半径为零 → 继续。**

---

## 2. 改动 diff（`quant_factor_price.py`，共 3 处）

**(a) 常量 / schema 版本**
```python
-PRICE_HISTORY_COLUMNS = ["Date", "Ticker", "Close", "schema_version"]
+PRICE_HISTORY_COLUMNS = ["Date", "Ticker", "Open", "High", "Low", "Close", "Volume", "schema_version"]
-SCHEMA_VERSION = "phase2b.v1"
+SCHEMA_VERSION = "phase2b.v2"   # 新增 Open/High/Low/Volume 四列 → 主版本 v1→v2
```

**(b) `fetch_batch_prices` —— 从只取 Close 改为取 OHLCV**
- 批量 `yf.download` 后，原仅取 `Close`；现取 `Open/High/Low/Close/Volume` 五列。
- `Close` 仍为**必填**（前瞻收益口径不变）；`Open/High/Low/Volume` 缺失则该行留空（不强行补 0 / 不阻断，与模块"绝不填 0 / 插值"铁律一致）。
- `Volume` 存为整数，`Open/High/Low` 存 6 位小数，`Close` 列名与含义**完全不变**。

**(c) 文档字符串** —— 数据文件字段描述更新为含 OHLCV，并注明 Close 仍为 Forward Return 唯一口径、四列仅供未来使用。

> 未改动：`load_price_history`（已自动为新列补空）、`upsert_price_history`（幂等，历史不被覆盖）、`price_map_from_history`（仅 Close）、`update_price_history`（原子写逻辑）。

---

## 3. 回填结果（10-07 / 10-08 的 OHLCV 补上了吗？）

**未补上 —— 回填失败，按约定留空。**

- 实际 CSV 现状：**3250 行 / 325 个 ticker / 10 个交易日（09-27 ~ 10-08）**，全部缺 OHLCV（不止用户以为的 2 天）。
- 回填脚本用 `yf.download(325 tickers, auto_adjust=False)` 联网拉取，**yfinance 返回 HTTP 429（Too Many Requests）限流，325 个全部失败**，`filled=0 / unfilled=3250`。
- 已执行"留空"降级：CSV 升到 8 列结构，**历史行 O/H/L/V 留空、Close 原值保留**（抽样校验 `A 09-27 Close=175.210007` 与原始一致）。`schema_version` 保持 `phase2b.v1`（历史行 provenance），新数据将写 `phase2b.v2`。
- **如需后续补历史**：限流解除后重跑 `/tmp/backfill_ohlc.py` 即可（脚本幂等，已填行跳过，仅填空行并把该行 `schema_version` 升 v2）。

---

## 4. 全量测试

```
pytest tests/ -q  →  284 passed, 7 warnings in 12.99s
```
- 基线 281 → 现 **284**（+3 新测试：`test_schema_has_ohlcv` / `test_update_writes_ohlcv`（mock 不联网验证 OHLCV 落盘 + Close 不变）/ `test_load_backward_compat_old_csv`（旧 4 列 CSV 向后兼容））。
- 仅改 `quant_factor_price.py` + 测试，全链路无回归。

---

## 5. review 安全性硬证据

`git diff --name-only`（含未跟踪，staged 后）：
```
quant_factor_price.py
quant_factor_price_history.csv
tests/test_quant_factor_price.py
```
**不含 `review.py` / `review.yml` / `scan.py` / `portfolio_50000.py` / `quant_factor_lab.py`。** 明早 06:23 review 走 `python portfolio_50000.py --data-dir .`（无 --intraday-stop），只读 `portfolio_50000_transactions.csv` 等自身数据，**完全不触碰 price_history**，故本次改动对其零影响。

---

## 6. commit SHA + push 结果

- Commit：`07ac19e` → rebase 合入 origin/main 新提交 `0b1112f` 后变基为 **`605559c`**
- Push：`0b1112f..605559c  main -> main`（已推送）
- 工作树：clean（已清理 `__pycache__`）

---

## 7. 下周一（及之后）预期

- **新数据自动带 OHLCV**：price_history 更新器（`quant_factor_price.update_price_history`，由 dashboard-data / quant 流水线触发）在下一个交易日运行时会以新 `fetch_batch_prices` 拉取 OHLCV 并 upsert；新交易日行带 `Open/High/Low/Close/Volume`，旧 09-27~10-08 行保持空（upsert 不覆盖历史）。
- **scan 主逻辑不变**：scan.py 仍只按列名读 `Date` 做契约诊断，不写 price_history；本次仅扩了 price_history 的列。
- **Phase 2–7 零影响**：backtest/validation/candidate/Walk-Forward/Shadow/治理 当前均不消费 O/H/L/V 四列，仅供未来（开盘跳空、真实止损/止盈、流动性建模）使用。
- **历史 OHLCV 缺口**：在限流解除前，09-27~10-08 共 3250 行 O/H/L/V 为空；不影响回测（仍用 Close），仅未来用到 OHLCV 的功能才需要补。重跑回填脚本即可补齐。

---

## 8. 2026-10-10 重试探测（限流仍未解除）

> 时间：2026-10-10 ~14:00 GMT+8（距首次 429 失败已 14+ 小时）
> 目的：确认 yfinance 限流是否冷却，决定是否重跑 `/tmp/backfill_ohlc_batch.py`

**实时探测结果**（单 ticker `AAPL`，与回填脚本同口径 `auto_adjust=False, threads=False`）：

```
yfinance 版本: 1.1.0
probe 形状: (0, 6)            ← 返回空 DataFrame
probe 耗时: 16.4s
1 Failed download:
['AAPL']: YFRateLimitError('Too Many Requests. Rate limited. Try after a while.')
RESULT: 限流未解除
```

**判定**：

- 限流为 **IP 级持续性封锁**（非短冷却），14+ 小时未解除。
- 此时重跑整任务（17 批 ×20 ticker，批间 3s）只会得到 `filled=0 / unfilled=3250`，白烧约 5 分钟，且反复触发 429 可能加深封锁。**暂不执行整跑。**
- CSV 现状复核：3250 行 / 325 ticker / 09-27~10-08，**Open/High/Low/Volume 仍 0 已填**，schema 维持 `phase2b.v1`，Close 原值未损。

**可行路径（按推荐顺序）**：

1. **等冷却**：Yahoo 封锁通常数小时~1 天解除。建议次日（或隔数小时）再探测；解除后用 `python3.11 /tmp/backfill_ohlc_batch.py` 重跑（幂等、已填跳过、不覆盖 Close）。
2. **降频重试**：若必须现在尝试，可把 `SLEEP` 提到 30~60s、单批降到 5 ticker，给服务端充分呼吸——但持续性封锁下大概率仍失败，仅作最后手段。
3. **换源兜底**：若 yfinance 长期不可用，改从 `stooq` / `pandas-datareader` / 自有快照回填 O/H/L/V（脚本在 /tmp，改源不违反"不碰仓库 .py"铁律），仅填 O/H/L/V、Close 保持。

**影响评估**：该缺口**不影响回测与现有流水线**（backtest 仍只用 Close；review/scan/dashboard 均不消费 O/H/L/V）。仅未来启用"开盘跳空 / 真实止损止盈 / 流动性建模"时才需补齐，属**低优先级、非阻塞**。
