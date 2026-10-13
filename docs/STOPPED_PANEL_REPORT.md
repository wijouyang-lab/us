# 已止损记录前端面板 — 实施报告

> 纯前端新增「已止损记录（近 30 天）」板块。铁律已遵守：未触碰 scan.py / review.py / review.yml / portfolio_50000.py / dashboard_export.py / 任何 workflow。

## 1. 第一步：只读确认结果（transactions 字段）

**① `build_portfolio` 是否全量透传 transactions（含 SELL）？**
- ✅ 是。`dashboard_export.py:2506-2517` 对 `read_csv_rows(txn_p)` 的**每一行**建字典，无 action 过滤，`action`（UPPER）一并保留。
- ⚠️ 但 `:2518` 有全局截断：`txns = sorted(...)[:20]` —— 只保留**按日期降序最近 20 条**（不分 action）。SELL 记录只有在最近 20 条内才进 `portfolio.transactions[]`。止损离场多为近期事件，实践中可见。这是后端既有行为，按铁律不碰 `dashboard_export.py`。

**② 每条 transaction 字段（`dashboard_export.py:2507-2517`，全部透传）：**
`date` / `ticker`(UPPER) / `action`(BUY·SELL) / `shares`(int) / `price`(成交价=退出价) / `amount`(成交额) / `realized_pnl`(已实现盈亏) / `reason` / `unit_id`

需求列字段 `date/action/ticker/shares/price/realized_pnl/reason` **全部齐备**。

**③ `entry_price` / `entry_date`？**
- ❌ **不存在**于 transactions 透传字典（持仓 `positions[]` 才有，但那是另一个数组）。
- 补救（不捏造）：
  - **盈亏/胜率**：`realized_pnl` 已直接给出 → 胜率、平均收益全可算。
  - **入场价 `$entry → $exit`**：由 `cost_basis = amount − realized_pnl`（SELL 时 amount 为成交额）反推 `entry = cost_basis / shares`，数学可靠。
  - **持有天数**：无 `entry_date`，**无法推导** → 需求示例也未要求，不展示，缺则显 `—`。

**结论：字段足够，无需硬写。**

## 2. 改动 diff（仅 4 个文件，+280 / -1）

| 文件 | 改动 |
|---|---|
| `index.html` | 在 `portfolioSec` 之后插入 `#stoppedCard`（含 `#stoppedSub` 统计行 + `#stoppedBody` 容器），+9 行 |
| `app.js` | 新增 `renderStopped()`（+~95 行）；在 `renderDashboard` 的 `renderPortfolio()` 后调用 `renderStopped()`，+1 行 |
| `app.css` | 新增 `.stp-*` 样式（卡片行/日期/价格/收益/原因），+14 行 |
| `tests/test_stopped_frontend.py` | 新增（node harness，3 用例） |
| `tests/test_quant_dashboard.py` | 放宽一处正则（允许 `renderPortfolio()` 与 `renderQuant()` 之间插入其它渲染调用），-1/+3 |

**`index.html` 新增卡片：**
```html
<section class="card sec" id="stoppedCard">
  <div class="sec-h">
    <h2>已止损记录（近 30 天）</h2>
    <span class="sec-sub" id="stoppedSub">—</span>
  </div>
  <div id="stoppedBody"></div>
</section>
```

**`app.js` 渲染逻辑要点（`renderStopped`）：**
- 数据源：`DATA.portfolio.transactions`。
- 筛选：`action === 'SELL'` 且 `reason` 含 `stop loss`（不区分大小写）→ 仅展示止损离场。
- 时间窗：以交易流水最新日期为锚点（不依赖本地时钟，避免时区漂移），保留近 30 天。
- 排序：按 `date` 降序。
- 统计：总计 / 胜率（`realized_pnl > 0` 占比，**样本 < 10 → 显 "—"**）/ 平均收益率（由 `realized_pnl / cost_basis` 反推，cost_basis = amount − realized_pnl）。
- 单行：`Ticker  MM-DD  $entry → $exit  ±x.x%` + `原因: …`；入场价由 amount/realized_pnl/shares 反推，缺字段显 `—`。
- 边界：`transactions` 缺失 / 空 / 无 SELL-StopLoss → `stoppedBody` 显示「暂无止损记录」；单条字段缺失 → 不崩、缺值显 `—`。

## 3. 测试结果

- 新增 `tests/test_stopped_frontend.py`（node harness 直跑真实 `app.js` 的 `renderStopped`）：
  1. 空 / 缺失 transactions → 显示「暂无止损记录」 ✅
  2. 含 SELL + Stop Loss → 正确渲染（筛选 / 统计 / 入场价反推 / 日期降序 / ≥10 样本胜率数字） ✅
  3. 单条字段缺失 → 不崩、显 `—` ✅
- 全量 pytest：**294 passed**（基线 291 + 新增 3），满足 ≥ 291 要求。
- 一处既有测试 `test_app_js_has_render_quant` 因我在 `renderPortfolio()` 与 `renderQuant()` 间插入 `renderStopped()` 调用而放宽正则（意图不变：renderQuant 仍在 renderPortfolio 之后调用）。

## 4. review 安全性硬证据

- `git diff --name-only` 命中文件仅：`app.css app.js index.html tests/test_quant_dashboard.py`，外加新增 `tests/test_stopped_frontend.py`。
- `git diff --name-only | grep -E "review\.py|review\.yml|scan\.py|portfolio_50000\.py|dashboard_export\.py|\.github/"` → **NONE**，未触碰任何禁止文件。
- `git diff app.js | grep -E "renderReview|review"` → **NONE**，`renderStopped` 为自包含新增函数，不调用也不修改 review 渲染路径。
- review 路径（`renderReview()`、`review.records[]`、review_history.csv 展开）零改动，明早 06:23 的 Review 运行不受影响。

## 5. commit SHA + push 结果

- 本地提交：`feat(dashboard): add stopped-out positions panel`
- 流程：`git fetch origin && git rebase origin/main && git push origin main`（rebase 干净通过，无冲突）
- **最终推送 SHA：`3ba1ceb`**（`HEAD == origin/main`，已确认一致）
- 上游在 rebase 前新增了 `032f60e`（market data refresh [skip ci]），我们的提交已线性接在其上。

## 6. 前端截图

- 文件：`/workspace/stopped_panel_preview.png`（见下方预览；为便于展示，预览时隐藏了新闻/运行时条，并用合成的 12 笔 SELL-StopLoss 流水填充——真实数据当前全为 BUY，会显示「暂无止损记录」）。
- 渲染 DOM 实测（Chromium `--dump-dom` 校验）：
  - 标题 `已止损记录（近 30 天）`
  - 统计行 `总计: 12 笔 | 胜率: 33% | 平均: -4.7%`（≥10 样本→数字胜率；<10 则显 "—"）
  - 行按日期降序，入场价反推正确，例如 `ADSK 10-08 $160.14 → $143.53 -10.4% 原因: Intraday Stop Loss`
  - 盈利行显绿 `+x.x%`、亏损行显红 `-x.x%`；`Trailing Stop Loss` 等同被 `stop loss` 命中纳入。
