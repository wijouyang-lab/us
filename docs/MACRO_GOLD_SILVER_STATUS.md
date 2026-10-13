# 黄金 / 白银 宏观数据状态调查报告

> 生成时间：2026-10-09 19:07 (GMT+8)
> 调查方式：**只读**（读源码 `dashboard_export.py` + 工作流 `dashboard-data.yml` + 线上公开 JSON + 本地克隆的 git 历史）。未改任何代码、未 push、未 rebase、未碰监控、未调 AI、未调 ClawSocket。

---

## 结论速览（先回答用户的核心问题）

| 问题 | 答案 |
|------|------|
| 黄金/白银数据当前是否正常？ | **正常**。线上实时值：黄金 ≈ $4203.30/oz，白银 ≈ $60.43/oz，`available=True`。 |
| 走什么数据源？ | 名义符号是 `XAUUSD=X`/`XAGUSD=X`（伦敦现货），**实际取值符号是备用期货 `GC=F`/`SI=F`**（COMEX）。来源 `source=yfinance`。 |
| 日志里的 404 是否被 fallback 拯救？ | **是**。主抓现货 `XAUUSD=X`/`XAGUSD=X` 在 Yahoo 一直 404，但代码先主抓失败再回退到 `GC=F`/`SI=F` 成功，所以 `15/15 可用` 是真实的，不是假象。 |
| 是否跟随 dashboard-data 每 15 分钟更新？ | **是**。工作流 `*/15 * * * 1-5` 每 15 分钟跑一次，每次都**实时重抓**宏观数据（明确禁止复用旧 JSON 宏观缓存）。实测 `updated_at` 在两个 curl 之间就从 `11:01:05Z` 变成了 `11:15:54Z`。 |

---

## 1. 黄金/白银的实际符号 + 数据源

源码 `dashboard_export.py`（`MARKET_ASSETS`，约 135–136 行）：

```python
("Gold",   "XAUUSD=X", "GC=F", "commodity", "usd/oz", None, False),
("Silver", "XAGUSD=X", "SI=F", "commodity", "usd/oz", None, False),
```

每一项是 `(输出名, 主抓 symbol, 备用 symbol, 分组, 单位, CNBC符号, 仅常规时段)`。

- **`symbol`（名义/展示符号）**：`XAUUSD=X`（黄金现货）、`XAGUSD=X`（白银现货）。
- **`fallback`（实际取值符号）**：`GC=F`（COMEX 黄金期货）、`SI=F`（COMEX 白银期货）。
- **数据源优先级**（`QuoteProvider`，约 388 / 444–562 行）：
  1. `yfinance`（与 scan.py 同源）
  2. `yahoo_http`（裸 urllib 打 Yahoo chart API）
  3. `stooq`（备用源，仅前两者全失败时启用；`XAUUSD=X`→`xauusd`、`GC=F`→`gc.f`）

**主抓 → 备用 回退顺序**（约 1504–1509 行）：

```python
quote = provider.quote(primary)        # 先试 XAUUSD=X
quote_used = primary
if not quote and fallback:
    quote = provider.quote(fallback)    # 失败再试 GC=F
    quote_used = fallback if quote else primary
```

回退成功后，JSON 里会如实记录 `symbol_used = GC=F`（实际提供数据的符号），`symbol` 仍是 `XAUUSD=X`（身份/展示用）。全程透明可查。

---

## 2. 404 符号是否被 fallback 拯救

**被拯救了，而且是“每次都救”**。

- 日志里 `HTTP 404: Quote not found for symbol: XAUUSD=X` 与 `$XAUUSD=X: No data found` 是**主抓现货符号**在 Yahoo chart API 上的真实失败（Yahoo 对这类现货 FX 符号经常返回 404）。
- 但代码紧接着对**备用期货** `GC=F`/`SI=F` 发起报价请求，成功拿到真实价格。
- 当 fallback 取到价格时，`item["error"]` 会被重置为 `None`（约 1571 行），因此**线上 JSON 里黄金/白银的 `error` 字段为 `None`** —— 那次 404 只是运行内部日志，**不会污染对外 JSON**，也不会让 `available` 变 `False`。
- 这正是“日志报 404、却显示 15/15 可用”的表面矛盾的根因：**404 的是名义现货符号，救它的是期货备用符号**。

实测线上 JSON（2026-10-09 11:15:54Z）：

```
Gold:   symbol=XAUUSD=X  symbol_used=GC=F   price=4203.2998  available=True  error=None
Silver: symbol=XAGUSD=X  symbol_used=SI=F   price=60.43       available=True  error=None
```

---

## 3. 线上当前值（具体数字 + 时间戳）

两次 curl 实测（公开 URL，间隔约 15 分钟，证明在持续刷新）：

| 字段 | 黄金 Gold | 白银 Silver |
|------|-----------|-------------|
| 主符号 symbol | XAUUSD=X | XAGUSD=X |
| 实际取值 symbol_used | **GC=F** | **SI=F** |
| 价格 price (usd/oz) | 4203.2998（首拉 4204.70） | 60.43（首拉 60.515） |
| 涨跌幅 change_1d (%) | +1.1138 | +2.3127 |
| 涨跌幅 change_5d (%) | +0.0238 | −0.4858 |
| 涨跌幅 change_20d (%) | −4.6287 | −5.9953 |
| 数据源 source | yfinance | yfinance |
| 价格性质 price_kind | live | live |
| 可用 available | True | True |
| 错误 error | None | None |
| 最近日线棒 last_bar_date | 2026-10-08 | 2026-10-08 |
| 更新时间 updated_at | 2026-10-09T11:15:54Z | 2026-10-09T11:15:54Z |

> 完整 15 个市场标的清单（供对照）：`^DJI` 道指、`^GSPC` 标普、`^IXIC` 纳指、`^VIX`、`^TNX` US10Y、`2YY=F` US2Y、`^FVX` US5Y、`^TYX` US30Y、`DX-Y.NYB` DXY、`XAUUSD=X` 黄金、`XAGUSD=X` 白银、`HG=F` 铜、`CL=F` WTI、`BZ=F` 布油、`NG=F` 天然气。共 15 个，`available_count` 当前为 `15/15`。

---

## 4. 刷新机制（每次重取？缓存？）

- **调度**：`dashboard-data.yml` 的 `on.schedule` 为 `cron: "*/15 * * * 1-5"` —— **周一至周五全天，每 15 分钟一次**（注释明确写“确保宏观资产在亚洲时段也持续更新”）。另有 `workflow_dispatch`（可手动触发）和 `push` 触发（改 `dashboard_export.py` 等文件时）。
- **每次是否重取**：**是，每次 run 都实时重抓**。`build_market()` 里对每个资产都调用 `provider.daily_bars()` + `provider.quote()` 实时拉取，不读旧 JSON。
- **是否缓存旧宏观 JSON**：**明确禁止**。`refresh_policy` 字段原文：
  > `indices_frozen_outside_session; rates_cnbc_24h; commodities_forex_24h（禁止复用旧 JSON 宏观缓存）`
  且代码注释（约 1460 行）写明“任何情况下都不读取、不复用旧 dashboard_data.json 里的宏观缓存”。
- **`15/15 可用` 是否每次打印**：该数字来自 `available_count = market_ok`（约 2969 行，即本轮真正取到价的资产数）。每轮 run 重算，并非缓存上一次的结果。
- **兜底设计**：黄金/白银本身就有“主抓现货失败 → 回退期货”的双源兜底；整条宏观链路还有 yfinance → yahoo_http → stooq 三级后端兜底。价格**绝不伪造、绝不硬编码**，全部失败时输出 `null` + 真实 `error`。

---

## 5. 当前状态：现在正常吗？跟随更新吗？

**现在完全正常，并且严格跟随 dashboard-data 每 15 分钟更新。**

证据：

1. **实时可取值**：线上黄金 $4203.30、白银 $60.43，`available=True`，`error=None`。
2. **持续正常（非间歇性故障）**：扫描本地克隆最近 **40 次** dashboard-data 提交（覆盖 2026-10-09 02:31–10:01 UTC，约 10 小时、每 15 分钟一刷），黄金/白银**每一次都是 `available=True`、每一次 `symbol_used` 都是 `GC=F`/`SI=F`、每一次 `available_count` 都是 `15/15`**。价格随真实 24h 交易平滑波动（黄金 4196–4225、白银 60.3–60.8），无任何一次掉线。
3. **主抓 404 是常态、备用是主力**：在这 40 次窗口里，黄金/白银的 `symbol_used` **从未**出现过 `XAUUSD=X`/`XAGUSD=X`，说明**名义现货符号在 Yahoo 上一直 404，期货备用符号一直稳定顶上**。这不是“间歇性 404”，而是“主源长期不可用、备源长期扛活”。
4. **持续刷新**：两次 curl 间隔约 15 分钟，`updated_at` 从 `11:01:05Z` 变到 `11:15:54Z`，证明 15 分钟刷新链路在跑。

### 一句话总结
> 黄金/白银数据**目前完全正常、实时可用**，名义符号 `XAUUSD=X`/`XAGUSD=X` 在 Yahoo 一直 404，但代码的主抓→备用回退机制每次都用 `GC=F`/`SI=F` 期货救回真实价格（所以 `15/15 可用` 是真值、非假象）；数据**每 15 分钟跟随 dashboard-data 实时重抓**，且明确禁止复用旧 JSON 宏观缓存。无需任何代码改动。

---

## 附：调查用到的位置索引

| 内容 | 文件 / 位置 |
|------|-------------|
| 资产定义（主/备符号） | `dashboard_export.py` ~135–136 行（`MARKET_ASSETS`） |
| 主抓→备用回退逻辑 | `dashboard_export.py` ~1504–1509 行 |
| 三级数据源优先级 | `dashboard_export.py` ~388、444–562 行（`QuoteProvider`） |
| Stooq 备用符号映射 | `dashboard_export.py` ~394–400 行 |
| “禁止复用旧宏观缓存”注释 | `dashboard_export.py` ~1460 行 |
| refresh_policy 字段 | `dashboard_export.py` ~2975 行 |
| 可用计数 available_count | `dashboard_export.py` ~2969–2972 行 |
| 15 分钟调度 | `.github/workflows/dashboard-data.yml` `on.schedule` ~16 行 |
| 线上实时数据 | `https://wijouyang-lab.github.io/us/dashboard/data/dashboard_data.json` |
