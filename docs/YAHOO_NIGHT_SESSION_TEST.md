# Yahoo 夜盘（Night Session）数据覆盖实测

> 目的：判断 `prepost=True` 能否覆盖 23h 交易后的夜盘（**21:00–04:00 ET**），
> 从而决定夜盘是「只读刷新」还是「完全静默」。
> 本文件为**只读实测记录 + 方法论**，未修改任何数据/代码。

---

## 0. 重要声明：本次未能在本沙箱完成实证

实测环境（沙箱共享出口 IP）被 Yahoo Finance **持续 429 限流**（含 `yfinance` 的 crumb 路径与
`query1`/`query2` 的 v8 chart API 端点，等待 45s 后重试仍 429）。

| 尝试 | 方法 | 结果 |
|---|---|---|
| 1 | `yfinance 1.1.0` `Ticker("AAPL").history(period="5d", interval="1m", prepost=True)` | `YFRateLimitError: Too Many Requests` |
| 2 | `query1.finance.yahoo.com/v8/...chart/AAPL?interval=1m&range=5d&includePrePost=true` | `HTTP 429` |
| 3 | `query2...chart/AAPL?interval=1m&range=1d&includePrePost=true` | `HTTP 429` |
| 4 | 等待 45s 后 `query1`+`query2` 各重试一次 | 均 `HTTP 429` |

> ⚠️ **结论状态：夜盘覆盖情况「本沙箱无法实证」**。下面是本应跑出、且可在非限流环境复跑的完整方法论；
> 在拿到真实数据前，夜盘策略应**保守默认「完全静默 / 至多只读刷新（且不依赖该数据做决策）」**——
> 这与 `US_SESSION_DESIGN.md` 的既定默认（Night Session = 静默）一致，不矛盾。

---

## 1. 实测方法论（已写好，待非限流环境运行）

文件：`/tmp/night_session_test.py`（已生成，沙箱内可保留）。

```python
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")

df = yf.Ticker("AAPL").history(period="5d", interval="1m", prepost=True)
# 以及 period="1d" 各跑一次

# 对每个 index 时间戳：
#   转 ET: ts.astimezone(ET)
#   统计每小时 bar 数 -> hours[0..23]
#   夜盘定义: hours[h] for h in (21,22,23,0,1,2,3)  # 21:00-04:00 ET
night_bars = sum(hours[h] for h in range(24) if h >= 21 or h < 4)

# 判定：
if night_bars > 0:
    print("覆盖夜盘 -> 夜盘可只读刷新")
else:
    print("不覆盖 -> 夜盘完全静默")
```

### 1.1 关键判定口径
- **夜盘窗口（ET）**：`21:00 ≤ t < 24:00` 与 `00:00 ≤ t < 04:00`（跨午夜，需 wrap-around 处理）。
- **换算**：Yahoo 返回的 index 为 tz-aware（多为 UTC），必须 `astimezone(ET)` 后再按 hour 归类；
  切忌直接用 UTC hour 判断。
- **判据**：夜盘窗口内 `bar 数 > 0` → 覆盖；否则不覆盖。（注：即便有零星 bar，若稀疏/缺整段，
  仍应判定为「不可用」，因为决策需要连续分钟级数据。）

### 1.2 备用端点（绕过 yfinance crumb）
```bash
# 直接 chart API（有时免 crumb）
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1m&range=5d&includePrePost=true"
# 解析 chart.result[0].timestamp（UTC 秒），转 ET 后按上法统计
```

---

## 2. 已知事实（无需网络即可确认的部分）

1. `prepost=True` **必定覆盖** 现有盘前（04:00–09:30 ET）与盘后（16:00–20:00 ET）——
   这是 `dashboard_export.py:587-620` 已在用的能力，**不依赖本次实测**。
2. 需要本次实测才能确认的，仅是新夜盘 **20:00–04:00 ET（Blue Ocean / overnight ATS 段）** 的分钟级连续性。
3. Yahoo 对「overnight session」的 1m 覆盖在行业里**口碑参差**：多数免费源只对
   04:00–20:00 ET 可靠，20:00–04:00 段常缺失或稀疏。即**先验预期偏向「不覆盖」**，
   但须以真实数据为准。

---

## 3. 对 23h 方案的影响（分两种实证结果）

### 情形 A：实测覆盖（night_bars 充足连续）
- 夜盘可「只读刷新」：`dashboard_export.py:587-620` 的 prepost 取价可延伸到夜盘时段，
  网页在夜盘也能显示近似实时价。
- **但仍不建议在夜盘做任何 AI / 交易决策**——流动性仅全天 ~1%（见 `US_SESSION_DESIGN.md §2`）。
- `_us_session.py` 的 `is_ai_decision_window()` 仍对 Night 返回 `False`。

### 情形 B：实测不覆盖（或稀疏不可用）★ 当前保守默认
- 夜盘「完全静默」：`is_trading_active`/`is_ai_decision_window` 对 Night 均 `False`；
  dashboard 在夜盘只展示上一 Regular 收盘快照（不刷新价）。
- 这与 `US_SESSION_DESIGN.md §5` 的策略矩阵（Night: scan ❌ / review ❌ / 止损 ❌ / dashboard ✅只读刷新）
  中「dashboard ✅」一项需修正为「只读刷新但取不到新价则显示快照」——已在该设计文档 §8 待确认问题 3 留口。

---

## 4. 行动建议（待 Phase 2 前完成）

| 优先级 | 动作 |
|---|---|
| 🔴 必做 | 从**非限流环境**（本地机器 / 未被 Yahoo 限流的云主机）复跑 `night_session_test.py`，拿到真实 night_bars。 |
| 🟡 建议 | 若情形 B，直接采用 `US_SESSION_DESIGN.md` 的 Night=静默默认，无需额外开发。 |
| 🟡 建议 | 若情形 A 且坚持夜盘刷新，需实测 Blue Ocean 数据源（如 `boac.ai` 免费 API）作为 Yahoo 的补充，而非依赖 Yahoo prepost。 |

> 复跑命令（非限流环境）：
> ```bash
> python3 /tmp/night_session_test.py
> # 或
> curl -s "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1m&range=5d&includePrePost=true" \
>   | python3 -c "import sys,json; d=json.load(sys.stdin); ts=d['chart']['result'][0]['timestamp']; \
>   from datetime import datetime; from zoneinfo import ZoneInfo; ET=ZoneInfo('America/New_York'); \
>   h=[datetime.fromtimestamp(t,ET).hour for t in ts]; print('night bars=',sum(1 for x in h if x>=21 or x<4))"
> ```

---

## 5. 铁律确认
- 本文件为**只读实测记录**；`/tmp/us` 仓库未被触碰（`git status` 干净）。
- 未运行任何会修改数据的脚本；`yfinance`/`curl` 均为只读拉取。
- 未 push / rebase / commit；未调 AI。
