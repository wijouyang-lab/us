# 新闻模块本地验证报告（判决前 · 只读 + 本地运行）

> **验证时间**：2026-10-08（本地）
> **铁律遵守**：未 push / 未 rebase / 未 commit / 未碰监控 PID 536931 / 未修改源码（仅运行脚本、并临时对齐数据做渲染验证后 `git checkout` 还原，未改动任何 `.py/.js/.html/.css` 源码）。
> **方法说明**：JS 错误检查使用仓库内 `/usr/bin/chromium` 以 headless 模式 `dump-dom` + 捕获控制台日志（无 GUI 开发者工具，故用 `--enable-logging` 抓 V8 报错；结果已排除 chromium 的 `dbus` 沙箱环境噪声，仅报告页面自身 JS 错误）。

---

## 1. 抓取结果（任务 1）

**命令**
```bash
export FINNHUB_API_KEY=$(grep FINNHUB_API_KEY /tmp/us/.env | cut -d= -f2)
cd /tmp/us
python dashboard/fetch_news.py --tickers ADSK,ANET,ISRG,KR
```

**结果：成功 ✅**

- API key 有效（长度 40，未被 revoke），无 401/403。
- 输出落点：`/tmp/us/dashboard/data/news_data.json`（新增，未跟踪文件）。
- 脚本打印：`✅ 新闻数据已写入 …（市场 100 条 / 个股 110 条 / error=None）`。

**输出 JSON 结构**
```json
{
  "schema_version": "news.v1",
  "generated_at": "2026-10-08T04:51:50Z",
  "market_news": [ { "headline","source","url","datetime","summary" }, … ],  // 100 条
  "ticker_news": {
    "ADSK":  [ {…}, … ],
    "ANET":  [ {…}, … ],
    "ISRG":  [ {…}, … ],
    "KR":    [ {…}, … ]
  },                                                                          // 合计 110 条
  "error": null
}
```

| 项 | 值 |
|---|---|
| `schema_version` | `news.v1` |
| `market_news` | **100 条** |
| `ticker_news` | **110 条**（标的 ADSK / ANET / ISRG / KR，与请求一致） |
| `error` 字段 | **null**（无错误） |
| 单条字段 | `headline` / `source` / `url` / `datetime` / `summary`（齐全） |

**有无真实 Finnhub 格式问题**：**无** ✅
- 字段名与 `dashboard_export.build_news` / `app.js newsRow` 期望完全匹配。
- `url` 为真实 Finnhub / Google News 格式（`https://finnhub.io/api/news?id=...`、`https://news.google.com/rss/...`）。
- `datetime` 为 epoch 秒，`app.js fmtBJ()`（app.js:718）能正确转为北京时间显示（渲染验证中已确认显示 `10-08 11:03` 等）。
- 抓取侧 429 指数退避 + 0.5s 限流（fetch_news.py）本次未触发。

---

## 2. Dashboard 渲染结果（任务 2）

**命令**
```bash
cd /tmp/us
python dashboard_export.py        # 退出码 0
python -m http.server 8080 &
```

**关键事实（先说结论）**：新闻**抓取与嵌入均正常**，但**按用户原命令预览时新闻卡片不会显示真实数据**——根因是「export 输出路径」与「根前端读取路径」错位，且「部署前端 `us-market-terminal/` 仍是旧版无新闻卡片」。以下为三场景实证。

### 场景 A —— 用户原命令（`serve /tmp/us`）
- 根前端 `index.html`（:269）加载 `app.js`，`app.js:16` 以相对路径 `dashboard/data/dashboard_data.json` 读取 → 实际取 `/tmp/us/dashboard/data/dashboard_data.json`。
- 该文件为**陈旧旧数据（无 `news` 键）**，export 从未写入它（见问题 1）。
- headless 渲染结果：`newsMarket` = **「暂无新闻（数据尚未生成）」**，0 个 `news-item`，`newsTickers` 为空。
- **页面自身 JS 错误：无**（仅 chromium `dbus` 环境噪声，非代码错误）。

### 场景 B —— `serve /tmp/us/us-market-terminal`（export 实际写入处）
- 该目录 `dashboard_data.json` **含 news**（market_news 100 + ticker_news 4 标的，error null）。
- 但 `us-market-terminal/index.html` **不含 `newsCard` 元素**、其 `app.js` 无 `DATA_URL`/无 news 渲染逻辑（旧版前端）。
- headless 渲染结果：DOM 中**无 `newsMarket`**，0 个 `news-item`。
- 结论：部署前端陈旧，即便数据到位也不渲染新闻。

### 场景 C —— 临时对齐路径验证卡片本身（验证后已还原）
- 把含 news 的 JSON 拷到 `/tmp/us/dashboard/data/dashboard_data.json`，headless 渲染根前端，随后 `git checkout` 还原（未改源码）。
- 渲染结果：**正常 ✅**
  - `newsMarket` → `📡 市场动态` + 真实条目（如 "Yemen's Houthis say …"）。
  - `newsTickers` → `🏷️ 持仓 / 推荐联动` + ADSK / ANET / ISRG / KR 各自条目。
  - 真实 `news-item` 合计 **32 条**，无占位，4 个请求 ticker 全部高亮出现。
  - **页面自身 JS 错误：无**。
- 结论：新闻卡片**代码本身正确**，能正常渲染真实新闻；问题只在数据到达路径。

### 有数据 / 空数据时分别显示什么（代码逻辑 + 验证）
| 状态 | 显示 |
|---|---|
| `news` 为 null / undefined | 「暂无新闻（数据尚未生成）」 |
| `news.error` 为真 | 「新闻暂不可用：<错误>」 |
| `market_news` 为空 | 「今日暂无市场新闻」 |
| `ticker_news` 为空 | 「暂无个股新闻」 |
| 正常有数据 | 市场动态 + 持仓/推荐联动（已验证） |

### 与其他卡片布局协调性
- 新闻卡片复用全局 `.card / .sec` 基类（app.css:66-71），与 runtime（`.rcard`）、持仓/推荐（`.pcard/.ocard`）、宏观（`.gcard`）卡片**布局体系一致**（同圆角/边框/阴影/内边距），无脱节。
- 内部用 `.news-block / .news-sub / .news-item / .news-ticker` 独立样式（app.css:279-290），与现有风格统一。

---

## 3. 发现的问题

1. **【关键】export 输出路径 ≠ 根前端读取路径**
   - `dashboard_export.py:2759-2761`：`若 (SCRIPT_DIR/"us-market-terminal").is_dir()` 为真，则 `out_path` 写到 `us-market-terminal/dashboard/data/dashboard_data.json`。
   - 但根前端 `app.js:16` 读相对路径 `dashboard/data/dashboard_data.json` → `/tmp/us/dashboard/data/dashboard_data.json`。
   - 而根目录这份是**旧数据（无 `news` 键）**，export 默认不会更新它。
   - 后果：用户按 `cd /tmp/us; python -m http.server 8080` 预览，新闻卡片恒显示「暂无新闻」。

2. **【关键】部署前端 `us-market-terminal/` 陈旧**
   - 该目录是 git 跟踪的「部署前端」（4 个跟踪文件：index.html / assets/app.js / assets/app.css / dashboard/data/dashboard_data.json）。
   - 其 `index.html` 无 `newsCard`、`app.js` 无 news 渲染逻辑（新闻 commit `ab6adb7` 等**未同步进** `us-market-terminal`）。
   - 后果：export 把含 news 的数据写进了 `us-market-terminal`，但旧前端不渲染 → 生产/部署侧也看不到新闻。

3. **两问题叠加**：任何本地 serve 方式（根 或 `us-market-terminal`）都看不到真实新闻，除非手动对齐路径（场景 C 已证明卡片本身 OK）。

4. **副作用（非代码改动）**：运行 `dashboard_export.py` 修改了被跟踪文件 `us-market-terminal/dashboard/data/dashboard_data.json`（`git status` 显示 ` M`，diff 巨大，因提交内为旧全量数据）；`dashboard/data/news_data.json` 为新增未跟踪文件。两者均为脚本正常输出产物，**未 commit / 未 push**。

---

## 4. 是否需要修（只列，不修）

| # | 建议修复 | 性质 | 是否必改 |
|---|---|---|---|
| 1 | **统一 export 输出与前端读取路径**：要么让 `dashboard_export.py` 同时/改写到 `/tmp/us/dashboard/data/dashboard_data.json`（根前端读取路径），要么把部署目标统一为 `us-market-terminal` 并让根前端读取该路径 | 路径对齐 | **必改（否则新闻永远不显示）** |
| 2 | **同步 `us-market-terminal` 前端代码**（`index.html` / `assets/app.js` / `assets/app.css`）与根前端，使其具备 `newsCard` 渲染能力 | 部署前端过时 | **必改（否则生产侧看不到）** |
| 3 | **清理根目录陈旧文件** `/tmp/us/dashboard/data/dashboard_data.json`（无 `news` 键），避免误导；或明确 export 应覆盖它 | 数据卫生 | 建议改 |
| 4 | 新闻抓取 429 退避已就绪（fetch_news.py），本次未触发 → **无需改** | — | 否 |
| 5 | 建议 CI（`dashboard-data.yml`）增加「export 输出目录」与「前端读取目录」一致性校验，防止再次错位 | 流程加固 | 建议改 |

> 以上均**未实施**，待判决后由相应任务处理。本次仅做本地验证。
